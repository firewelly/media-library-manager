#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
麻豆系列：用 DeepSeek 批量提取演员与 metadata
================================================

证据来源（每部影片）:
  - JavDB 标题
  - **全部磁链的文件名**（不只最大那条；常含演员名/系列/厂牌）
  - 封面 OCR 文本（macOS Vision，快照文字）
  - JavDB 已有的演员字段（本系列为空）

做法: 按批（默认 15 部/批）调用 deepseek-flash（**纯文本输入**，规避成人图片拒答），
要求逐条返回 JSON：actresses[] / studio / series / tags[]；并提供高频候选名单作参考。

输出: results/madou/llm_meta.json（每条影片的提取结果）+ 统计

用法:
    python3 extract_madou_meta_llm.py --limit 30        # 试跑
    python3 extract_madou_meta_llm.py                  # 全量（断点续跑）
"""

import os
import re
import sys
import json
import time
import argparse
import collections
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils.secrets import get_key, load_keys

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "madou")
INDEX_PATH = os.path.join(OUT_DIR, "series_index.json")
DETAILS_PATH = os.path.join(OUT_DIR, "series_details.json")
OCR_PATH = os.path.join(OUT_DIR, "cover_ocr.json")
CAND_PATH = os.path.join(OUT_DIR, "name_candidates.json")
META_PATH = os.path.join(OUT_DIR, "llm_meta.json")
MODEL = "deepseek-flash"

STOPWORDS = set("""中文 無碼 无码 有码 有碼 高清 中字 字幕 麻豆 传媒 傳媒 映画 映畫 影片 视频 視頻 在线 在線 播放 下载 下載
制服 人妻 学生 學生 老师 老師 护士 護士 系列 独家 獨家 新片 首发 首發 精品 推荐 推薦 完整版 无删减 无码破解
出品 代理 最新域名 第一會所 共同监制 粉丝 回馈 下载 链接 地址 复制 磁力 种子 種子 合集 精选 精選 作品 更多 更新
大尺度 无套 中出し 中出 素人 原创 原創 自拍 偷拍 外流 流出 网红 網紅 主播 直播 福利 写真 寫真 套图 圖集""".split())
CJK = re.compile(r"[\u4e00-\u9fff]{2,4}")


def load(p, d=None):
    if os.path.exists(p):
        try:
            return json.load(open(p, encoding="utf-8"))
        except Exception:
            pass
    return d if d is not None else {}


def build_evidence(idx, det, ocr):
    """每部影片的证据文本"""
    rows = []
    for code, it in idx.items():
        d = det.get(code) or {}
        dns = [m.get("dn", "") for m in (d.get("magnets") or [])]
        text = (it.get("title", "") + " " + " ".join(dns) + " " + " ".join(ocr.get(code) or [])).replace("&amp;", "&")
        rows.append({"code": code, "title": it.get("title", ""),
                     "dns": dns[:30],                       # 全部磁链名（上限 30，足够）
                     "ocr": " ".join(ocr.get(code) or "")})  # 封面 OCR 全文
    return rows


def candidate_names(idx, det, ocr, min_df=3):
    df = collections.Counter()
    for code, it in idx.items():
        d = det.get(code) or {}
        txt = (it.get("title", "") + " " + " ".join(m.get("dn", "") for m in (d.get("magnets") or []))
               + " " + " ".join(ocr.get(code) or []))
        for w in set(CJK.findall(txt)):
            if w in STOPWORDS or len(w) < 2:
                continue
            df[w] += 1
    return [{"name": w, "df": c} for w, c in df.most_common() if c >= min_df]


PROMPT = """你是影片资料整理助手。下面给出「麻豆傳媒」系列若干部影片的资料（JavDB 标题、磁链文件名、封面文字）。
请**仅依据给定资料**，为每部影片提取：
- actresses: 演员姓名数组（中文人名；可能是 2-4 字中文名或艺名；不要填厂牌名如 麻豆/蜜桃影像/大象传媒/性视界/兔子先生，不要填剧情词、标签词）
- studio: 出品方/厂牌（如 麻豆傳媒、大象傳媒、蜜桃影像、性视界、兔子先生…没有则空串）
- series: 系列名（如「麻豆女优私密档案」「淫靡生活物语」等；没有则空串）
- tags: 内容标签数组（如 中文字幕/无码/巨乳/制服…最多 6 个）

可参考的候选人名（不限于此，高频出现者更可能是演员）：{cands}

严格输出 JSON 对象，形如
{{"videos":[{{"code":"MD0362","actresses":[],"studio":"","series":"","tags":[]}}, ...]}}
（videos 数组需覆盖上面给出的每一部影片，顺序不限）不要输出解释文字。

影片资料：
{items}"""


def call_llm(batch, cands, key):
    items = "\n\n".join(
        f"【{r['code']}】\n标题: {r['title']}\n磁链名: {' | '.join(r['dns']) or '（无）'}"
        + (f"\n下载文件名: {r.get('file')}" if r.get("file") else "")
        + f"\n封面文字: {r['ocr'] or '（无）'}"
        for r in batch)
    prompt = PROMPT.format(cands="、".join(cands[:150]), items=items)
    body = {"model": MODEL, "messages": [{"role": "user", "content": prompt}],
            "temperature": 0, "max_tokens": 4000, "thinking": {"type": "disabled"},
            "response_format": {"type": "json_object"}}
    for attempt in range(3):
        try:
            r = requests.post("https://api.deepseek.com/chat/completions",
                              headers={"Authorization": f"Bearer {key}"}, json=body, timeout=180)
            if r.status_code != 200:
                time.sleep(2 * (attempt + 1))
                continue
            txt = r.json()["choices"][0]["message"]["content"]
            data = json.loads(txt)
            arr = data if isinstance(data, list) else (data.get("videos") or data.get("data") or data.get("items") or [])
            if isinstance(arr, list) and arr:
                return arr
            if attempt == 2:
                print("    [调试] 返回无法解析:", str(txt)[:200])
        except Exception as e:
            if attempt == 2:
                print("    [调试] 调用异常:", str(e)[:120])
            time.sleep(2 * (attempt + 1))
    return []


def main():
    ap = argparse.ArgumentParser(description="DeepSeek 批量提取演员与 metadata")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--refill", action="store_true", help="只重跑当前没有演员的条目")
    ap.add_argument("--batch", type=int, default=15)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    load_keys()
    key = get_key("DEEPSEEK_API_KEY")
    if not key:
        print("缺少 DEEPSEEK_API_KEY"); return 1

    idx = load(INDEX_PATH); det = load(DETAILS_PATH); ocr = load(OCR_PATH)
    if not idx:
        print("缺少 series_index.json，请先 --enumerate"); return 1

    cands = [c["name"] for c in candidate_names(idx, det, ocr, min_df=3)]
    json.dump(cands, open(CAND_PATH, "w"), ensure_ascii=False, indent=1)
    print(f"候选人名 {len(cands)} 个（示例: {', '.join(cands[:20])}）")

    rows = build_evidence(idx, det, ocr)
    meta = load(META_PATH, {})
    if args.refill:
        todo = [r for r in rows if not (meta.get(r["code"]) or {}).get("actresses")]
        # 同时带上「下载文件名」等额外证据（若存在）
        try:
            ov = json.load(open(os.path.join(OUT_DIR, "download_actress_overrides.json"), encoding="utf-8"))
            for r in todo:
                if ov.get(r["code"], {}).get("file"):
                    r["file"] = ov[r["code"]]["file"]
        except Exception:
            pass
    else:
        todo = [r for r in rows if r["code"] not in meta]
    if args.limit:
        todo = todo[:args.limit]
    print(f"待提取 {len(todo)} 部（批 {args.batch}，并发 {args.workers}）")

    batches = [todo[i:i + args.batch] for i in range(0, len(todo), args.batch)]
    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(call_llm, b, cands, key): b for b in batches}
        for fut in as_completed(futs):
            got = fut.result()
            for item in got:
                code = str(item.get("code", "")).strip()
                if code:
                    old = meta.get(code) or {}
                    meta[code] = {"actresses": item.get("actresses") or old.get("actresses") or [],
                                  "studio": item.get("studio") or old.get("studio") or "",
                                  "series": item.get("series") or old.get("series") or "",
                                  "tags": item.get("tags") or old.get("tags") or []}
            done += 1
            if done % 10 == 0 or done == len(batches):
                json.dump(meta, open(META_PATH, "w"), ensure_ascii=False)
                print(f"  批次 {done}/{len(batches)} | 已入库 {len(meta)} 部", flush=True)

    json.dump(meta, open(META_PATH, "w"), ensure_ascii=False)
    n_act = sum(1 for v in meta.values() if v.get("actresses"))
    print(f"\n完成: {len(meta)} 部 | 提取到演员的 {n_act} 部 → {META_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
