#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修正「演员文件夹」记录中的错配（番号 / 演员）
================================================

背景: 库里存在两类问题（以数据库记录为准，与卷是否在线无关）:
  A. 番号不符: 文件名番号 ≠ javdb_info.javdb_code
     （如 REBD-429 被配成 REC-29、SVDVD-436 被配成 LUXU-404）
  B. 演员错配: 文件所在文件夹的演员 ∉ 该记录挂的演员

判定办法（每条回 JavDB 核对演员表）:
  1. 取「文件名番号」在 JavDB 的作品页与演员表；
  2. 若 **文件夹演员** ∈ JavDB 演员表 → 库里的映射错了 → 按 JavDB 修正番号+演员；
  3. 若 **库里挂的演员** ∈ JavDB 演员表 → 库映射没错 → 是文件放错文件夹 → 只报告，不动库；
  4. 两者都不在 / JavDB 查不到 → 记入人工确认。

输出: 修正日志 + 待人工确认清单（都不改库，除 --apply）。

用法:
    python3 fix_folder_mappings.py                # 干跑，输出判定
    python3 fix_folder_mappings.py --apply        # 写库
"""

import os
import re
import sys
import json
import time
import random
import sqlite3
import argparse
import collections
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "media_library.db")
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "magnets")
ISSUES = os.path.join(OUT_DIR, "actress_folder_real_issues.json")
BASE = "https://javdb580.com"
UA = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


def code_in_text(t):
    """从文本中任意位置提取番号（标题可能不以番号开头）"""
    m = re.search(r"([A-Za-z]{2,6})[-_ ]?(\d{2,5})", str(t or ""))
    return norm_code(f"{m.group(1)}-{m.group(2)}") if m else None


def norm_code(c):
    m = re.match(r"^([A-Za-z]{2,6})[-_]?(\d{2,5})$", str(c or "").strip().replace("_", "-").upper())
    return f"{m.group(1)}-{int(m.group(2))}" if m else None


def norm_name(s):
    """名称归一：去括号/空格（无需第三方繁简转换库）"""
    s = re.sub(r"[\(（].*?[\)）]", "", str(s or "")).strip()
    return re.sub(r"[\s·・]", "", s).lower()


def same_person(a, b):
    """同名判定：完全包含 或 相似度≥0.75（覆盖繁简/中英译名差异，如 波多野結衣≈波多野结衣）"""
    na, nb = norm_name(a), norm_name(b)
    if not (na and nb):
        return False
    if na == nb or na in nb or nb in na:
        return True
    import difflib
    return difflib.SequenceMatcher(None, na, nb).ratio() >= 0.75


def parse_actors(d, title):
    h2 = re.search(r"<h2[^>]*>(.*?)</h2>", d, re.S)
    page_title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h2.group(1))).strip() if h2 else title
    acts = [a[1] for a in re.findall(r'href="/actors/([A-Za-z0-9]+)"[^>]*>([^<]{1,20})<', d)
            if a[0] not in ("censored", "uncensored", "western")]
    return page_title, acts


def fetch_work(code, sess, url=None):
    """返回 {'actors': [...], 'title': str, 'href': str, 'verified': bool} 或 None

    优先用库里已有的 javdb_url 直接打开作品页（省一次搜索请求，降低被限流概率）。
    """
    if url:
        for attempt in range(2):
            try:
                time.sleep(random.uniform(0.25, 0.6))
                d = sess.get(url, headers=UA, timeout=25).text
                if "您已年滿 18 歲嗎" in d or "Cloudflare" in d:
                    time.sleep(3.0 * (attempt + 1)); continue
                page_title, acts = parse_actors(d, "")
                return {"actors": acts, "title": page_title[:90], "href": url.split("/v/")[-1],
                        "verified": norm_code(page_title) == code}
            except Exception:
                time.sleep(2.0 * (attempt + 1))
    for attempt in range(3):
        try:
            time.sleep(random.uniform(0.25, 0.6))
            r = sess.get(f"{BASE}/search?q={code}&f=all", headers=UA, timeout=25)
            m = re.search(r'<a href="/v/([A-Za-z0-9]+)" class="box" title="([^"]*)"', r.text)
            if not m:
                return None
            href, title = m.group(1), m.group(2)
            time.sleep(random.uniform(0.25, 0.6))
            d = sess.get(f"{BASE}/v/{href}", headers=UA, timeout=25).text
            if "您已年滿 18 歲嗎" in d or "Cloudflare" in d:
                time.sleep(2.0 * (attempt + 1))
                continue
            page_title, acts = parse_actors(d, title)
            return {"actors": acts, "title": page_title[:90], "href": href,
                    "verified": norm_code(page_title) == code}
        except Exception:
            time.sleep(1.5 * (attempt + 1))
    return None


def build_alias_index(cur):
    """名称 → 演员ID 索引（含别名），用于按 ID 判定同一人"""
    alias2ids, id2name = {}, {}
    for r in cur.execute("SELECT id,name,name_common,name_traditional,aliases FROM actors"):
        id2name[r["id"]] = r["name"]
        names = [r["name"], r["name_common"], r["name_traditional"]]
        names += (r["aliases"] or "").split(",")
        for n in names:
            n = norm_name(n)
            if n:
                alias2ids.setdefault(n, set()).add(r["id"])
    return alias2ids, id2name


def ids_of(name, alias2ids):
    """名称 → 演员ID 集合（先精确，再用相似度兜底）"""
    n = norm_name(name)
    if not n:
        return set()
    if n in alias2ids:
        return set(alias2ids[n])
    import difflib
    best, best_ratio = set(), 0.0
    for k, ids in alias2ids.items():
        if not k:
            continue
        if abs(len(k) - len(n)) > 2:
            continue
        r = difflib.SequenceMatcher(None, k, n).ratio()
        if r > best_ratio:
            best, best_ratio = set(ids), r
    return best if best_ratio >= 0.9 else set()


def main():
    ap = argparse.ArgumentParser(description="修正演员文件夹记录错配")
    ap.add_argument("--db-path", default=DB_PATH)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    issues = json.load(open(ISSUES, encoding="utf-8"))
    # 合并两类问题记录（按 video_id 去重，保留文件名番号与库内番号）
    targets = {}
    for actor, items in issues["code_mismatch"].items():
        for it in items:
            targets.setdefault(it["vid"], {"vid": it["vid"], "folder_actor": actor,
                                           "file": it["file"], "file_code": it["name_code"],
                                           "db_code": it["db_code"]})
    for actor, items in issues["actor_mismatch"].items():
        for it in items:
            t = targets.setdefault(it["vid"], {"vid": it["vid"], "folder_actor": actor,
                                               "file": it["file"], "file_code": None, "db_code": None})
            t["mapped_actor"] = (it.get("mapped") or [None])[0]
    conn = sqlite3.connect(args.db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    alias2ids, id2name = build_alias_index(cur)
    for t in targets.values():
        if not t.get("file_code"):
            m = re.search(r"([A-Za-z]{2,6}[-_]?\d{2,5})", t["file"] or "")
            t["file_code"] = norm_code(m.group(1)) if m else None
        row = cur.execute("""SELECT ji.javdb_code, ji.javdb_title, ji.javdb_url,
                             (SELECT GROUP_CONCAT(a.name,'|') FROM video_actors va JOIN actors a ON a.id=va.actor_id WHERE va.video_id=v.id) AS acts
                             FROM videos v LEFT JOIN javdb_info ji ON ji.video_id=v.id WHERE v.id=?""", (t["vid"],)).fetchone()
        t["db_code"] = t["db_code"] or (row["javdb_code"] if row else None)
        t["mapped_actors"] = [a for a in ((row["acts"] if row else "") or "").split("|") if a]
        t["javdb_url"] = (row["javdb_url"] if row else None)
    todo = [t for t in targets.values() if t.get("file_code")]
    if args.limit:
        todo = todo[:args.limit]
    print(f"待判定记录: {len(todo)} 条（并发 {args.workers}）", flush=True)

    sess = requests.Session()
    sess.cookies.set("over18", "1", domain="javdb580.com")
    sess.cookies.set("locale", "zh", domain="javdb580.com")
    cache = {}
    cache_path = os.path.join(OUT_DIR, "work_actors_cache2.json")
    if os.path.exists(cache_path):
        try:
            cache = json.load(open(cache_path))
            print(f"[续跑] 已复用 {len(cache)} 个番号的核对结果", flush=True)
        except Exception:
            cache = {}
    todo = [t for t in todo if t.get("file_code") not in cache]
    print(f"本次需新核对: {len(todo)} 条", flush=True)

    def work(t):
        c = t["file_code"]
        if c not in cache:
            cache[c] = fetch_work(c, sess, t.get("javdb_url"))
            json.dump(cache, open(cache_path, "w"), ensure_ascii=False)
        return t, cache[c]

    fix, misplaced, manual = [], [], []
    todo = [t for t in targets.values() if t.get("file_code")]
    if args.limit:
        todo = todo[:args.limit]
    for t in todo:
        info = cache.get(t["file_code"])
        folder, mapped = t.get("folder_actor"), (t.get("mapped_actor") or (t["mapped_actors"][0] if t["mapped_actors"] else None))
        if not info or not info.get("actors"):
            manual.append({**t, "reason": "JavDB 未取到演员表"})
            continue
        title_code = norm_code(info.get("title") or "") or code_in_text(info.get("title") or "")
        same_number = (title_code and t["file_code"] and
                       title_code.split("-")[1] == t["file_code"].split("-")[1])
        if not (info.get("verified") or title_code == t["file_code"] or same_number):
            manual.append({**t, "reason": f"页面番号不符（{title_code}）",
                           "javdb_title": (info.get("title") or "")[:60]})
            continue
        ja = info["actors"]
        ja_ids = set()
        for a in ja:
            ja_ids |= ids_of(a, alias2ids)
        folder_ids = ids_of(folder, alias2ids) if folder else set()
        mapped_ids = ids_of(mapped, alias2ids) if mapped else set()
        if folder and not folder_ids:
            manual.append({**t, "reason": f"文件夹名无法对应到库内演员（{folder}）"})
            continue
        folder_in = bool(folder_ids & ja_ids) or (bool(folder) and any(same_person(folder, a) for a in ja))
        mapped_in = bool(mapped_ids & ja_ids) or (bool(mapped) and any(same_person(mapped, a) for a in ja))
        rec = {**t, "javdb_actors": ja[:8], "javdb_title": info["title"]}
        if folder_in and not mapped_in:
            fix.append(rec)
        elif mapped_in and not folder_in:
            misplaced.append(rec)
        elif folder_in and mapped_in:
            fix.append({**rec, "note": "双方都在演员表（合集）"})
        else:
            manual.append({**rec, "reason": "双方都不在演员表"})

    print(f"\n判定结果: 可修正 {len(fix)} | 文件放错文件夹 {len(misplaced)} | 人工确认 {len(manual)}")
    if args.apply and fix:
        for t in fix:
            cur.execute("""UPDATE javdb_info SET javdb_code=?, javdb_title=?, updated_at=CURRENT_TIMESTAMP
                           WHERE video_id=?""", (t["file_code"], t["javdb_title"], t["vid"]))
            cur.execute("DELETE FROM video_actors WHERE video_id=?", (t["vid"],))
            for a in t["javdb_actors"]:
                r = cur.execute("""SELECT id FROM actors WHERE name=? OR name_common=? OR name_traditional=?
                                   OR aliases LIKE ? LIMIT 1""",
                                (a, a, a, f"%{a}%")).fetchone()
                if r:
                    cur.execute("INSERT OR IGNORE INTO video_actors (video_id, actor_id) VALUES (?,?)", (t["vid"], r["id"]))
        conn.commit()
        print(f"✅ 已修正 {len(fix)} 条")
    json.dump({"fixed": fix, "misplaced_files": misplaced, "manual": manual},
              open(os.path.join(OUT_DIR, "folder_mapping_fix.json"), "w"), ensure_ascii=False, indent=1)
    print("报告: results/magnets/folder_mapping_fix.json")
    print("\n【示例·可修正】")
    for t in fix[:6]:
        print(f"   {t['file'][:26]:<28} {t['db_code'] or '-'} → {t['file_code']} 演员={t['javdb_actors'][:3]}")
    print("\n【示例·文件放错文件夹】")
    for t in misplaced[:6]:
        print(f"   {t['file'][:26]:<28} 文件夹={t['folder_actor']} 实际={t['javdb_actors'][:3]}")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
