#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
关联 JavDB「無碼」演员页
==========================

背景: JavDB 上同一演员可能有两个独立演员页——有碼页与無碼页
（如 長澤あずさ = /actors/Q7G7 有碼 + /actors/8Ad9 無碼）。
无码页需登录才能打开，但**搜索结果里带 <span class="info">無碼</span> 标记**，
因此不登录即可识别并建立关联。

本脚本:
  1. 对指定演员（默认收藏）搜索 JavDB 演员条目；
  2. 识别带「無碼」标记的那一条，写入 actors.javdb_uncensored_id / profile_url_uncensored；
  3. 输出有/无无码页的统计。

用法:
    python3 link_uncensored_actors.py                    # 收藏演员
    python3 link_uncensored_actors.py --all              # 全库演员
    python3 link_uncensored_actors.py --limit 20
"""

import os
import re
import sys
import json
import time
import random
import sqlite3
import argparse
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "media_library.db")
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "magnets")
CACHE_PATH = os.path.join(OUT_DIR, "uncensored_actor_cache.json")
BASE = "https://javdb580.com"
UA = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
}
BOX_RE = re.compile(r'<div class="box actor-box">\s*<a href="/actors/([A-Za-z0-9]+)" title="([^"]*)">(.*?)</a>', re.S)


def find_uncensored(name, sess):
    """返回 (無碼页id, 有码页id) —— 无则 None"""
    for _ in range(2):
        try:
            r = sess.get(f"{BASE}/search?q={name}&f=actor", headers=UA, timeout=25)
            boxes = BOX_RE.findall(r.text)
            if not boxes:
                return None, None
            censored = uncensored = None
            for href, title, body in boxes:
                if "無碼" in body:
                    uncensored = href
                else:
                    censored = href
            return uncensored, censored
        except Exception:
            time.sleep(1.2)
    return None, None


def main():
    ap = argparse.ArgumentParser(description="关联 JavDB 无码演员页")
    ap.add_argument("--db-path", default=DB_PATH)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()

    conn = sqlite3.connect(args.db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    sql = "SELECT id,name,name_common,name_traditional,aliases,profile_url FROM actors"
    if not args.all:
        sql += " WHERE is_favorite=1"
    sql += " ORDER BY is_favorite DESC, movie_count DESC, id"
    rows = cur.execute(sql).fetchall()
    if args.limit:
        rows = rows[:args.limit]
    print(f"待处理演员: {len(rows)}（并发 {args.workers}）", flush=True)

    cache = {}
    if os.path.exists(CACHE_PATH):
        try:
            cache = json.load(open(CACHE_PATH))
        except Exception:
            cache = {}

    sess = requests.Session()
    sess.cookies.set("over18", "1", domain="javdb580.com")

    todo = [r for r in rows if r["name"] not in cache]
    print(f"需新查询 {len(todo)} 位（缓存 {len(cache)}）", flush=True)

    def work(row):
        time.sleep(random.uniform(0.3, 0.7))
        unc, cen = find_uncensored(row["name"], sess)
        return row["name"], {"uncensored": unc, "censored": cen}

    done = hit = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for fut in as_completed([pool.submit(work, r) for r in todo]):
            name, info = fut.result()
            cache[name] = info
            done += 1
            if info["uncensored"]:
                hit += 1
            if done % 20 == 0 or done == len(todo):
                json.dump(cache, open(CACHE_PATH, "w"), ensure_ascii=False)
                print(f"  进度 {done}/{len(todo)} | 发现无码页 {hit}", flush=True)
    json.dump(cache, open(CACHE_PATH, "w"), ensure_ascii=False)

    # 写库
    updated = 0
    for r in rows:
        info = cache.get(r["name"]) or {}
        uid = info.get("uncensored")
        if uid and not (r["profile_url_uncensored"] if "profile_url_uncensored" in r.keys() else None):
            cur.execute("""UPDATE actors SET javdb_uncensored_id=?, profile_url_uncensored=?, updated_at=CURRENT_TIMESTAMP
                           WHERE id=?""", (uid, f"https://javdb.com/actors/{uid}", r["id"]))
            updated += 1
    conn.commit()

    with_unc = [r["name"] for r in rows if (cache.get(r["name"]) or {}).get("uncensored")]
    print("\n" + "=" * 60)
    print(f"处理 {len(rows)} 位 | 有独立无码页 {len(with_unc)} 位 | 写库 {updated} 条")
    print("无码页示例:")
    for n in with_unc[:15]:
        print(f"   {n:<12} 無碼页 = /actors/{cache[n]['uncensored']}")
    if not args.all:
        seeds = [r["name"] for r in rows if not (cache.get(r["name"]) or {}).get("uncensored")]
        print(f"\n未发现独立无码页的: {len(seeds)} 位（示例 {', '.join(seeds[:8])}）")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
