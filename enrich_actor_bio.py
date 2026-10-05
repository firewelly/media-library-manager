#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
演员「详细介绍(bio)」与「罩杯(cup)」采集 —— av-wiki + 千帆搜索 + 百度百科正文
==============================================================================

信息流（每位演员依次执行）:
  1. **av-wiki.net（优先源）**：结构化档案（生日/身高/三围）、罩杯（サイズ里的 B88(F)），
     以及词条开头的叙述性简介。
  2. **百度千帆 AI 搜索**（baidu-search 技能同一 API）：中文检索该演员，
     取网页引用片段；若结果里带百度百科词条链接，
  3. **打开百科词条**（Playwright 渲染 —— 百科是 JS 页面，requests 只能拿到空壳），
     抓词条正文段落与基本信息框，作为最详尽的介绍来源。

写入字段:
  - ``cup`` —— 罩杯（单字母），独立字段
  - ``bio`` —— 详细介绍（多来源拼装、去重、尽量详尽）
  - 顺带以「只填空字段」方式补 birth_date / height / measurements / debut_date

安全策略:
  - 只填空字段，不覆盖已有内容；
  - 网页片段须提及该演员姓名（繁简归一后比较）才采信；
  - av-wiki 与百科冲突时以 av-wiki 为准。

依赖: requests、zhconv、playwright（已配置 msedge）
用法:
  python3 enrich_actor_bio.py --favorites-only            # 干跑（收藏）
  python3 enrich_actor_bio.py --favorites-only --apply    # 写库
  python3 enrich_actor_bio.py --all --apply --limit 300   # 全量（断点续跑）
"""

import os
import re
import sys
import json
import time
import random
import sqlite3
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import suppress

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils.secrets import get_key, load_keys      # 密钥集中存放于 OneDrive，不入库
from enrich_profiles_baike import (  # 百科卡片 API 与名称归一（已验证）
    baike_lookup, parse_baike, search_names, norm, trim_sentences,
)
import enrich_actor_profiles
from enrich_actor_profiles import search_actress_page  # av-wiki（优先源）

# 批量并发时缩短 av-wiki 请求间隔
enrich_actor_profiles.REQUEST_SLEEP = (0.15, 0.35)
MAX_NAME_TRIES = 3       # 每人最多尝试的候选名数量（别名多的演员否则会逐个试）

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "media_library.db")
PROGRESS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "results", "actor_bio_progress.jsonl")
QIANFAN_URL = "https://qianfan.baidubce.com/v2/ai_search"
load_keys()
QIANFAN_KEY = get_key("BAIDU_API_KEY")

CUP_PATTERNS = [
    r"([A-Ka-k])\s*罩杯",
    r"罩杯\s*[：:]?\s*([A-Ka-k])",
    r"[BＴ]\s*\d{2,3}\s*(?:cm|厘米)?\s*[\(\（]\s*([A-Ka-k])\s*[\)\）]",
    r"([A-Ka-k])\s*カップ",
    r"[BＢ]\s*[：:]?\s*(\d{2,3})\s*(?:cm)?\s*[\(\（]\s*([A-Ka-k])",
]
# 百科正文段落（类名带随机后缀，用前缀匹配）
BAIKE_PARA_JS = """
() => {
  const out = [];
  document.querySelectorAll('div[class*="para_"], div[class*="para "]').forEach(el => {
    const t = (el.innerText || '').trim();
    if (t.length >= 20) out.push(t);
  });
  return out;
}
"""


def mentions(text, tokens):
    """文本是否提及该演员（繁简/大小写归一后比较）"""
    if not text:
        return False
    n = norm(text).lower()
    return any(norm(t).lower() in n for t in tokens if t)


def is_adult_page(text):
    return any(h in (text or "") for h in ("AV", "女优", "女優", "成人", "模特", "性感", "影片", "出道"))


# 定向补漏模式下的"相关"判定：档案式文案（bilibili/资料站）常不含 AV 字样
RELAX_HINTS = ("外文名", "中文名", "艺名", "藝名", "三围", "三圍", "罩杯", "身高", "身長",
               "生日", "出生", "作品", "写真", "寫真", "女优", "女優", "AV", "出道", "星座")


def is_relevant(text, relaxed=False):
    return any(h in (text or "") for h in RELAX_HINTS) if relaxed else is_adult_page(text)


def qianfan_search(query, session=None, retries=3):
    """千帆 AI 搜索，返回网页引用列表（含限流重试）"""
    sess = session or requests
    for attempt in range(retries):
        try:
            r = sess.post(QIANFAN_URL,
                          json={"messages": [{"content": query}], "search_source": "baidu_search_v2"},
                          headers={"Authorization": f"Bearer {QIANFAN_KEY}",
                                   "Content-Type": "application/json"},
                          timeout=40)
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(1.5 * (attempt + 1))
                continue
            r.raise_for_status()
            return r.json().get("references") or []
        except Exception as e:
            if attempt == retries - 1:
                print(f"    [搜索失败] {str(e)[:70]}", file=sys.stderr)
            else:
                time.sleep(1.2 * (attempt + 1))
    return []


class BaikeOpener:
    """用 Playwright 打开百度百科词条并抓正文（百科为 JS 渲染页面）"""

    def __init__(self):
        self.pw = None
        self.browser = None
        self.page = None
        self.cache = {}

    def start(self):
        try:
            from playwright.sync_api import sync_playwright
            self.pw = sync_playwright().start()
            self.browser = self.pw.chromium.launch(channel="msedge", headless=True)
            ctx = self.browser.new_context(
                locale="zh-CN",
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
            self.page = ctx.new_page()
            return True
        except Exception as e:
            print(f"[警告] 百科浏览器启动失败，退化为仅用搜索片段: {str(e)[:80]}", file=sys.stderr)
            self.close()
            return False

    def open(self, url, tokens=None):
        """返回 {'paras': [...], 'text': '...'}；失败或词条与演员不符返回 None

        tokens 非空时会校验页面确为该演员的词条（页面正文/标题需出现其姓名），
        避免搜索结果里无关的百科链接（如同名漫画、同字中文模特）被误用。
        """
        cache_key = (url, tuple(sorted(tokens or ())))
        if cache_key in self.cache:
            return self.cache[cache_key]
        result = None
        if self.page:
            try:
                self.page.goto(url, wait_until="domcontentloaded", timeout=45000)
                time.sleep(random.uniform(1.5, 2.5))
                title = (self.page.title() or "")
                paras = self.page.evaluate(BAIKE_PARA_JS) or []
                text = self.page.inner_text("body")
                full = title + "\n" + text
                if tokens:
                    nfull = norm(full).lower()
                    if not any(norm(t).lower() in nfull for t in tokens if t):
                        print(f"    [百科词条不符] {title[:30]} 未提及该演员，已忽略", file=sys.stderr)
                        self.cache[cache_key] = None
                        return None
                    if not is_adult_page(full[:2000]):
                        print(f"    [百科词条非该类目] {title[:30]}，已忽略", file=sys.stderr)
                        self.cache[cache_key] = None
                        return None
                result = {"title": title,
                          "paras": [p.strip() for p in paras if len(p.strip()) >= 20],
                          "text": text}
            except Exception as e:
                print(f"    [百科打开失败] {str(e)[:60]}", file=sys.stderr)
        self.cache[cache_key] = result
        return result

    def close(self):
        for obj, meth in ((self.browser, "close"), (self.pw, "stop")):
            with suppress(Exception):
                if obj:
                    getattr(obj, meth)()
        self.browser = self.pw = self.page = None


def extract_cup(*texts):
    """提取罩杯字母（A-K）。多分组正则取"看起来像罩杯"的那一组。"""
    for t in texts:
        if not t:
            continue
        for pat in CUP_PATTERNS:
            m = re.search(pat, t)
            if not m:
                continue
            for g in reversed([x for x in m.groups() if x]):
                g = g.upper()
                if len(g) == 1 and "A" <= g <= "K":
                    return g
    return None


def parse_bwh(text):
    """解析三围，返回 (measurements, cup)。

    兼容写法: B87-W57-H86 / B92(H)-W58-H83 / 三围:B:100 / W:55 / H:85 /
              B92cm (H) W54cm H86cm / 胸92 腰54 臀86
    """
    if not text:
        return None, None
    m = re.search(r"[BＢ]\s*[：:]?\s*(\d{2,3})\s*(?:cm)?\s*"
                  r"(?:[\(\（]\s*([A-Ka-k])\s*[\)\）])?\D{1,8}?(\d{2,3})\D{1,8}?(\d{2,3})", text)
    if not m:
        m = re.search(r"胸\s*[：:]?\s*(\d{2,3})\D{1,6}腰\s*[：:]?\s*(\d{2,3})\D{1,6}臀\s*[：:]?\s*(\d{2,3})", text)
    if m:
        g = m.groups()
        if len(g) == 4:
            b, cup, w, h = g
        else:
            b, w, h, cup = g[0], g[1], g[2], None
        b, w, h = int(b), int(w), int(h)
        if 60 <= b <= 130 and 40 <= w <= 100 and 60 <= h <= 130:
            return f"B{b}-W{w}-H{h}", (cup.upper() if cup else None)
    return None, None


def extract_structured(text, tokens, birth_hint=None):
    """从文本片段提取结构化字段（片段须提及该演员）"""
    if not mentions(text, tokens):
        return {}
    out = {}
    m = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", text)
    if not m:
        m = re.search(r"(?:生日|出生)[：:]\s*(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if m and 1940 <= int(m.group(1)) <= 2012:
        out["birth_date"] = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    if "height" not in out:
        m = re.search(r"身高\s*[：:]?\s*(\d{2,3})\s*(?:cm|厘米)", text)
        if m and 120 <= int(m.group(1)) <= 210:
            out["height"] = m.group(1)
    _meas, _cup = parse_bwh(text)
    if _meas and "measurements" not in out:
        out["measurements"] = _meas
    if _cup and not out.get("cup"):
        out["cup"] = _cup
    m = re.search(r"身高\s*[：:]?\s*(\d{2,3})\s*(?:cm|厘米)", text)
    if m and 120 <= int(m.group(1)) <= 210:
        out["height"] = m.group(1)
    m = re.search(r"[BT]?\s*(\d{2,3})\s*[-–—/、]\s*(\d{2,3})\s*[-–—/、]\s*(\d{2,3})", text)
    if m:
        b, w, h = (int(x) for x in m.groups())
        if 60 <= b <= 130 and 40 <= w <= 100 and 60 <= h <= 130:
            out["measurements"] = f"B{b}-W{w}-H{h}"
    cup = extract_cup(text)
    if cup:
        out["cup"] = cup
    m = re.search(r"(\d{4})\s*年\s*(\d{1,2})?\s*月?\s*[^。]{0,24}?(?:正式)?出道", text)
    if not m:
        m = re.search(r"(?:出道|デビュー)[：:]?\s*(\d{4})\s*年\s*(\d{1,2})?\s*月?(?:\s*(\d{1,2})\s*日)?", text)
    if m:
        year = int(m.group(1))
        birth_year = None
        if out.get("birth_date"):
            birth_year = int(out["birth_date"][:4])
        elif birth_hint:
            birth_year = int(str(birth_hint)[:4])
        # 出道年合理性：有生日则需相差 15-45 年；无生日时必须带月份且不早于 1995
        # （只有年份且无生日时极易把"出生年"误判为"出道年"，故不采信）
        month = m.group(2)
        if birth_year is not None:
            ok = 15 <= year - birth_year <= 45
        else:
            ok = bool(month) and year >= 1995
        if ok:
            out["debut_date"] = (f"{year}-{int(month):02d}" if month else str(year))
    return out


def clean_snippet(text):
    """清理网页片段中的站内编号/推广/页码等噪音"""
    t = text or ""
    t = re.sub(r"\bcv\d+\b", "", t)                       # cv44759
    t = re.sub(r"(投稿详情|详情|福利|备用|薇|VX|微信|QQ)[：:]?\s*\S{0,16}", "", t)
    t = re.sub(r"\b\d+\s*/\s*\d+\b", " ", t)             # 2/3 3/3 页码
    t = re.sub(r"https?://\S+", "", t)
    t = re.sub(r"\[\d+\]|\(\d+\)", "", t)
    t = re.sub(r"\s{2,}", " ", t).strip(" 　·|,，、-—")
    return t


def compose_bio(tokens, av_info=None, baike_card=None, baike_page=None, refs=None,
                relaxed=False):
    """拼装详细介绍，尽可能详尽：av-wiki → 百科正文 → 百科卡片 → 搜索片段

    过滤：盘点/榜单类网页（含多名演员数据）不入库；内容高度重复的片段跳过。
    """
    parts, seen, norms = [], set(), []

    def duplicate(text):
        n = norm(text)
        for prev in norms:
            if n and prev and (n[:36] in prev or prev[:36] in n):
                return True
        return False

    def add(text, require_name=False):
        text = clean_snippet((text or "").strip())
        if len(text) < 20:
            return
        if require_name and not mentions(text, tokens):
            return
        key = norm(text)[:40]
        if key in seen or duplicate(text):
            return
        seen.add(key)
        norms.append(norm(text))
        parts.append(text)

    def is_listicle(text):
        """盘点/榜单类内容：编号列表或含多名演员的生年月日"""
        if re.search(r"^\s*\d+\s*[、.）)]", text):
            return True
        if len(re.findall(r"\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日", text)) >= 2:
            return True
        if text.count("出生日期") >= 1 and len(re.findall(r"[\u4e00-\u9fff]{2,4}\(", text)) >= 2:
            return True
        return False

    if av_info and av_info.get("bio"):
        add(av_info["bio"])
    if baike_page:
        for p in (baike_page.get("paras") or []):
            if re.search(r"发行时间|饰演|导演|主演|目录|参考资料", p):
                continue
            add(p, require_name=False)   # 页面级校验已在 BaikeOpener.open 完成
    if baike_card:
        add(baike_card.get("description"), require_name=True)
        extras = [f"{k}：{v}" for k, v in (baike_card.get("extras") or {}).items()
                  if k in ("出生地", "血型", "经纪公司", "民族", "国籍", "职业", "代表作品", "星座") and v]
        if extras:
            add("；".join(extras))
    n_added = 0
    min_len = 30 if relaxed else 40
    for ref in refs or []:
        content = (ref.get("content") or "").strip()
        if not is_relevant(content, relaxed) or is_listicle(content):
            continue
        if min_len <= len(content) <= 400:
            before = len(parts)
            add(content, require_name=True)
            if len(parts) > before:
                n_added += 1
        if n_added >= 3 or sum(len(p) for p in parts) > 1300:
            break
    return trim_sentences("\n".join(parts), 1500) if parts else None


def load_progress(path=None):
    done = {}
    path = path or PROGRESS_PATH
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                try:
                    done[json.loads(line)["id"]] = True
                except Exception:
                    pass
    return done


def append_progress(rec, path=None):
    path = path or PROGRESS_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def actor_tokens(row):
    return [t.strip() for t in [row["name"], row["name_common"], row["name_traditional"]]
            + (row["aliases"] or "").split(",") if t and t.strip()]


QUERY_TEMPLATES = [
    "{name} AV女优 简介 出道",
    "{name} 女优 身高 三围 作品",
    "{name} 中文名 外文名 生日 罩杯",
]


def gather_http(row, tokens, args, no_search=False):
    """HTTP 阶段（可多线程）: av-wiki + 千帆搜索 + 百科卡片。

    返回 dict(av_info, refs, baike_card, baike_url)。浏览器阶段在主线程序列执行。
    """
    session = requests.Session()
    av_info = None
    for q in search_names(row)[:MAX_NAME_TRIES]:
        href, info = search_actress_page(session, q, {})
        if href and info and (info.get("bio") or info.get("cup") or info.get("measurements")):
            av_info = info
            break
    refs = []
    if not no_search:
        queries = (QUERY_TEMPLATES if getattr(args, "missing_only", False)
                   else ["{name} 简介 出生 身高 三围 罩杯 出道"])
        seen_urls = set()
        for tpl in queries:
            for ref in qianfan_search(tpl.format(name=row["name"]), session):
                u = ref.get("url") or ref.get("title") or ""
                if u in seen_urls:
                    continue
                seen_urls.add(u)
                refs.append(ref)
    baike_url = None
    for ref in refs:
        url = ref.get("url") or ""
        if "baike.baidu.com/item" in url:
            baike_url = url
            break
    baike_card = None
    if not av_info or not av_info.get("cup"):
        for q in search_names(row)[:MAX_NAME_TRIES]:
            info = baike_lookup(q, session)
            if not info:
                continue
            parsed = parse_baike(info, tokens)
            if parsed:
                parsed["extras"] = info["card"]
                parsed["cup"] = extract_cup(info["card"].get("罩杯", ""), info["card"].get("三围", ""))
                baike_card = parsed
                break
    return {"av_info": av_info, "refs": refs, "baike_card": baike_card, "baike_url": baike_url}


def main():
    ap = argparse.ArgumentParser(description="采集演员详细介绍与罩杯")
    ap.add_argument("--db-path", default=DB_PATH)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--favorites-only", action="store_true")
    ap.add_argument("--all", action="store_true", help="全量演员")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--redo", action="store_true", help="忽略进度文件重新处理")
    ap.add_argument("--no-search", action="store_true", help="不调用千帆搜索")
    ap.add_argument("--no-baike-page", action="store_true", help="不打开百科正文")
    ap.add_argument("--workers", type=int, default=4, help="HTTP 阶段并发线程数")
    ap.add_argument("--batch", type=int, default=24, help="每批处理人数（批内 HTTP 并发、浏览器串行）")
    ap.add_argument("--progress-file", default=PROGRESS_PATH, help="进度文件（分片并行时各自独立）")
    ap.add_argument("--shard", default="", help="分片: 'N/M' 表示只处理 id%%M==N 的演员")
    ap.add_argument("--ids", default="", help="只处理指定 id（逗号分隔）")
    ap.add_argument("--missing-only", action="store_true",
                    help="只处理缺简介或罩杯的演员，并用多组查询词定向补漏")
    args = ap.parse_args()

    conn = sqlite3.connect(args.db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    sql = ("SELECT id, name, name_common, name_traditional, aliases, birth_date, debut_date, "
           "height, measurements, cup, bio, description, is_favorite FROM actors ")
    if args.favorites_only and not args.all:
        sql += "WHERE is_favorite=1 "
    sql += "ORDER BY is_favorite DESC, movie_count DESC NULLS LAST, id"
    rows = conn.execute(sql).fetchall()

    done = {} if args.redo else load_progress(args.progress_file)
    todo = [r for r in rows if r["id"] not in done]
    if args.shard:
        n, m = (int(x) for x in args.shard.split("/"))
        todo = [r for r in todo if r["id"] % m == n]
    if args.ids:
        wanted = {int(x) for x in args.ids.split(",") if x.strip()}
        todo = [r for r in todo if r["id"] in wanted]
    if args.missing_only:
        todo = [r for r in todo if not (r["bio"] or "").strip() or not (r["cup"] or "").strip()]
    if args.limit:
        todo = todo[:args.limit]
    print(f"待处理 {len(todo)} 人（已完成 {len(done)}，库内 {len(rows)}）| 并发 {args.workers}，批次 {args.batch}")

    opener = BaikeOpener()
    has_browser = False if args.no_baike_page else opener.start()
    stat = {"cup": 0, "bio": 0, "birth_date": 0, "height": 0, "measurements": 0, "debut_date": 0}
    processed = 0

    try:
        for start in range(0, len(todo), args.batch):
            batch = todo[start:start + args.batch]
            # 阶段 1: HTTP 并发
            gathered = {}
            with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
                futs = {pool.submit(gather_http, row, actor_tokens(row), args, args.no_search): row
                        for row in batch}
                for fut in as_completed(futs):
                    row = futs[fut]
                    try:
                        gathered[row["id"]] = fut.result()
                    except Exception as e:
                        print(f"    [HTTP 失败] DB#{row['id']} {row['name']}: {str(e)[:50]}", file=sys.stderr)
                        gathered[row["id"]] = {"av_info": None, "refs": [], "baike_card": None, "baike_url": None}
            # 阶段 2: 浏览器串行打开百科正文
            for row in batch:
                g = gathered[row["id"]]
                g["baike_page"] = None
                if g.get("baike_url") and has_browser:
                    g["baike_page"] = opener.open(g["baike_url"], actor_tokens(row))
            # 阶段 3: 组装并写库
            for row in batch:
                processed += 1
                g = gathered[row["id"]]
                tokens = actor_tokens(row)
                av_info, refs = g.get("av_info"), g.get("refs") or []
                baike_card, baike_page = g.get("baike_card"), g.get("baike_page")
                sets, vals, changed = [], [], []
                page_text = (baike_page or {}).get("text", "")
                snippets = [r.get("content", "") for r in refs]
                named_snips = [s for s in snippets if mentions(s, tokens)]
                if not (row["cup"] or "").strip():
                    cup = ((av_info or {}).get("cup") or (baike_card or {}).get("cup")
                           or extract_cup(*(named_snips + [page_text[:3000]])))
                    if cup:
                        sets.append("cup=?"); vals.append(cup); changed.append(f"罩杯={cup}")
                struct = {}
                for s in named_snips + [page_text[:3000]]:
                    for k, v in extract_structured(s, tokens, row["birth_date"]).items():
                        struct.setdefault(k, v)
                if baike_card:
                    for k in ("birth_date", "height", "measurements", "debut_date"):
                        if baike_card.get(k):
                            struct.setdefault(k, baike_card[k])
                if av_info:
                    for k in ("birth_date", "height", "measurements", "debut_date"):
                        if av_info.get(k):
                            struct[k] = av_info[k]
                for field in ("birth_date", "height", "measurements", "debut_date"):
                    if struct.get(field) and not (row[field] or "").strip():
                        sets.append(f"{field}=?"); vals.append(struct[field]); changed.append(f"{field}={struct[field]}")
                if not (row["bio"] or "").strip():
                    bio_text = compose_bio(tokens, av_info, baike_card, baike_page, refs,
                                           relaxed=args.missing_only)
                    if bio_text:
                        sets.append("bio=?"); vals.append(bio_text); changed.append(f"介绍{len(bio_text)}字")

                flag = "".join(["A" if av_info else "-", "S" if refs else "-", "B" if baike_page else "-"])
                print(f"[{processed}/{len(todo)}] {flag} DB#{row['id']} {row['name']}: "
                      + ("; ".join(changed) if changed else "无新增"), flush=True)

                if args.apply and changed:
                    sets.append("updated_at=CURRENT_TIMESTAMP")
                    conn.execute(f"UPDATE actors SET {', '.join(sets)} WHERE id=?", vals + [row["id"]])
                    conn.commit()
                for f in stat:
                    if any(s.startswith(f + "=") for s in sets):
                        stat[f] += 1
                append_progress({"id": row["id"], "name": row["name"], "changed": changed,
                                 "src": flag, "ts": time.strftime("%Y-%m-%d %H:%M:%S")},
                                args.progress_file)
    finally:
        opener.close()
        if args.apply:
            conn.commit()
        conn.close()

    print("-" * 62)
    print("写入统计: " + " | ".join(f"{k} {v}" for k, v in stat.items()))
    if not args.apply:
        print("(干跑模式，未写库；加 --apply 执行)")


if __name__ == "__main__":
    main()
