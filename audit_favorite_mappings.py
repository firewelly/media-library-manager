#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
收藏演员影片映射体检（对照 JavDB 演员表）
==========================================

背景: 库里曾出现「番号配错 → 演员挂错」的问题（如 REBD-584 被配成 REC-084，
演员从 涼森れむ 变成 ももかりん；IDBD 蓝光合集被配到 ID/AD/TD 系列）。
本脚本对**收藏演员**名下所有影片做系统体检：

  1. 取每个影片的番号（优先 javdb_info.javdb_code，其次文件名中的番号）；
  2. 打开 JavDB 该作品页，解析演员表；
  3. 若「库里挂的收藏演员」不在 JavDB 演员表中 → 标记为可疑（错配/错标）；
  4. 输出报告（JSON + 终端摘要），**不改库**。

用法:
    python3 audit_favorite_mappings.py                 # 全量体检
    python3 audit_favorite_mappings.py --limit 300     # 先跑一部分
    python3 audit_favorite_mappings.py --resume        # 续跑（复用已有结果）
"""

import os
import re
import sys
import json
import time
import sqlite3
import argparse
import random
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "media_library.db")
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "magnets")
CACHE_PATH = os.path.join(OUT_DIR, "work_actors_cache.json")
REPORT_PATH = os.path.join(OUT_DIR, "favorite_mapping_report.json")
BASE = "https://javdb580.com"
UA = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


def norm_code(c):
    if not c:
        return None
    m = re.match(r"^([A-Za-z]{2,6})[-_ ]?(\d{2,5})", str(c).strip())
    return f"{m.group(1).upper()}-{int(m.group(2))}" if m else None


def code_from_name(fn):
    if not fn:
        return None
    s = re.sub(r"\.(mp4|mkv|avi|wmv|ts|rmvb|mov|iso)$", "", str(fn), flags=re.I)
    s = re.sub(r"[-_ ]?(UC|U|C|CD\d|[45]K|HD|FHD|SD|BD|VR|LEAK|无码破解|中文字幕|字幕)$", "", s, flags=re.I)
    return norm_code(s)


def session():
    s = requests.Session()
    s.cookies.set("over18", "1", domain="javdb580.com")
    s.cookies.set("locale", "zh", domain="javdb580.com")
    return s


def work_actors(code, sess, cache):
    """返回 {'actors': […], 'title': str, 'href': str, 'verified': bool} 或 None

    严格模式：仅当作品页标题里的番号与查询番号**完全一致**时才采信，
    否则记 None（避免把 ABF-175 误当 ABF-17 这类子串命中）。
    """
    if code in cache:
        return cache[code]
    res = None
    for attempt in range(3):
        try:
            time.sleep(random.uniform(0.3, 0.8))
            r = sess.get(f"{BASE}/search?q={code}&f=all", headers=UA, timeout=25)
            m = re.search(r'<a href="/v/([A-Za-z0-9]+)" class="box" title="([^"]*)"', r.text)
            if not m:
                break
            href, title = m.group(1), m.group(2)
            time.sleep(random.uniform(0.3, 0.8))
            d = sess.get(f"{BASE}/v/{href}", headers=UA, timeout=25).text
            if "您已年滿 18 歲嗎" in d or "Cloudflare" in d:
                time.sleep(2.0 * (attempt + 1))
                continue
            h2 = re.search(r"<h2[^>]*>(.*?)</h2>", d, re.S)
            page_title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h2.group(1))).strip() if h2 else ""
            page_code = norm_code(page_title)
            if page_code != code:
                res = {"actors": [], "title": page_title[:80], "href": href,
                       "verified": False, "reason": f"页面番号={page_code}"}
                break
            acts = [a[1] for a in re.findall(r'href="/actors/([A-Za-z0-9]+)"[^>]*>([^<]{1,20})<', d)
                    if a[0] not in ("censored", "uncensored", "western")]
            res = {"actors": acts, "title": page_title[:80], "href": href, "verified": True}
            break
        except Exception:
            time.sleep(1.5 * (attempt + 1))
    cache[code] = res
    return res


def main():
    ap = argparse.ArgumentParser(description="收藏演员影片映射体检")
    ap.add_argument("--db-path", default=DB_PATH)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()

    conn = sqlite3.connect(args.db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    rows = cur.execute("""
        SELECT v.id AS vid, v.file_name, v.file_path,
               (SELECT ji.javdb_code FROM javdb_info ji WHERE ji.video_id=v.id) AS db_code,
               a.id AS aid, a.name AS aname
        FROM videos v
        JOIN video_actors va ON va.video_id = v.id
        JOIN actors a ON a.id = va.actor_id
        WHERE a.is_favorite = 1
    """).fetchall()
    print(f"待体检记录: {len(rows)} 条")

    # 按番号归并（同一番号只查一次 JavDB）
    by_code = {}
    for r in rows:
        code = norm_code(r["db_code"]) or code_from_name(r["file_name"])
        if not code:
            continue
        by_code.setdefault(code, []).append((r["vid"], r["aid"], r["aname"], r["file_name"]))
    codes = sorted(by_code)
    if args.limit:
        codes = codes[:args.limit]
    print(f"去重后需核对番号: {len(codes)} 个")

    cache = {}
    if args.resume and os.path.exists(CACHE_PATH):
        try:
            cache = json.load(open(CACHE_PATH))
            print(f"[续跑] 已缓存 {len(cache)} 个番号结果")
        except Exception:
            cache = {}
    todo = [c for c in codes if c not in cache]
    print(f"本次核对: {len(todo)} 个（并发 {args.workers}）", flush=True)

    sess = session()
    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(work_actors, c, sess, cache): c for c in todo}
        for fut in as_completed(futs):
            done += 1
            if done % 100 == 0 or done == len(todo):
                json.dump(cache, open(CACHE_PATH, "w"), ensure_ascii=False)
                print(f"  进度 {done}/{len(todo)}", flush=True)

    json.dump(cache, open(CACHE_PATH, "w"), ensure_ascii=False)

    # 比对
    report = {"checked_at": time.strftime("%Y-%m-%d %H:%M:%S"), "suspects": [], "no_data": []}
    for code in codes:
        info = cache.get(code)
        if not info or not info.get("verified") or not info.get("actors"):
            report["no_data"].append({"code": code, "reason": (info or {}).get("reason", "无结果/被限流")})
            continue
        acts = info["actors"]
        for vid, aid, aname, fname in by_code[code]:
            matched = any(norm_in(aname, a) or norm_in(a, aname) for a in acts)
            if not matched:
                report["suspects"].append({
                    "video_id": vid, "code": code, "file_name": fname,
                    "mapped_actor": aname, "javdb_actors": acts[:8],
                    "javdb_title": info["title"], "code_match": info.get("code_match"),
                })
    json.dump(report, open(REPORT_PATH, "w"), ensure_ascii=False, indent=1)

    print("\n" + "=" * 64)
    print(f"可疑错配: {len(report['suspects'])} 条 | 无法核对: {len(report['no_data'])} 个番号")
    by_actor = {}
    for s in report["suspects"]:
        by_actor.setdefault(s["mapped_actor"], []).append(s)
    print("\n按「库里挂的演员」汇总:")
    for a, items in sorted(by_actor.items(), key=lambda x: -len(x[1]))[:20]:
        print(f"   {a:<12} {len(items):>4} 条")
    print(f"\n报告: {REPORT_PATH}")
    conn.close()
    return 0


def norm_in(needle, hay):
    """名包含判断（忽略括号后缀，如 赤井美月(無碼) ≈ 赤井美月）"""
    if not needle or not hay:
        return False
    n = re.sub(r"[\(\（].*?[\)\）]", "", str(needle)).strip()
    h = re.sub(r"[\(\（].*?[\)\）]", "", str(hay)).strip()
    return bool(n) and (n in h or h in n)


if __name__ == "__main__":
    sys.exit(main())
