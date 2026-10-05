#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对比演员的 JavDB 作品与本地影片库（缺哪些作品）
==================================================

场景: 想知道某演员在 JavDB 上还有多少作品（默认为"單體作品"）没有收进本地库。

做法:
  1. 从 actors.profile_url 取该演员的 JavDB 主页；
  2. 用 Playwright 持久化登录态打开演员页（默认加 t=28 單體作品筛选）并翻页，
     抓取每个作品的番号；
  3. 与本地库比对：javdb_info.javdb_code + videos.file_name 中提取的番号；
  4. 输出：JavDB 总数 / 本地已有 / 缺失清单（可只输出缺失）。

用法:
    python3 compare_actor_filmography.py 美乃すずめ
    python3 compare_actor_filmography.py 美乃すずめ --all-works        # 不加单体筛选
    python3 compare_actor_filmography.py 美乃すずめ --missing-only --limit 60
"""

import os
import re
import sys
import time
import random
import sqlite3
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from javdb_crawler_single import (
    setup_playwright_session, close_playwright_session, is_cloudflare_challenge_pw,
)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "media_library.db")
BASE = "https://javdb580.com"
SOLO_FILTER = "t=28"          # JavDB: 單體作品
MAX_PAGES = 60


def local_codes(conn, actor_name=None):
    """本地库中已有的番号集合（javdb_info + 文件名提取）"""
    codes = set()
    for (c,) in conn.execute("SELECT javdb_code FROM javdb_info WHERE javdb_code IS NOT NULL AND javdb_code<>''"):
        codes.add(normalize_code(c))
    for (fn,) in conn.execute("SELECT file_name FROM videos WHERE file_name IS NOT NULL"):
        c = extract_code(fn)
        if c:
            codes.add(c)
    return codes


def normalize_code(code):
    return re.sub(r"[\s_]+", "-", str(code).strip().upper())


def extract_code(text):
    m = re.search(r"\b([A-Z]{2,6})[-_ ]?(\d{2,5})\b", str(text).upper())
    return f"{m.group(1)}-{m.group(2)}" if m else None


def classify_solo(session, href, cache=None):
    """打开作品详情页，判断是否为「單體作品」（JavDB 类别标签）"""
    if cache is not None and href in cache:
        return cache[href]
    page = session["page"]
    solo = None
    try:
        page.goto(f"{BASE}/v/{href}", wait_until="domcontentloaded", timeout=45000)
        time.sleep(random.uniform(0.8, 1.6))
        html = page.content()
        tags = re.findall(r'href="/tags[^"]*"[^>]*>([^<]{2,16})<', html)
        solo = any("單體" in t for t in tags)
    except Exception:
        solo = None
    if cache is not None:
        cache[href] = solo
    return solo


def crawl_actor_codes(actor_id, solo=True, max_pages=MAX_PAGES):
    """抓取演员页作品番号；返回 [(code, title, has_magnet, href)]"""
    session = setup_playwright_session(use_proxy=False, headless=True,
                                       browser_name="msedge", profile_mode="persisted")
    if not session:
        print("[错误] 无法启动浏览器会话", file=sys.stderr)
        return []
    page = session["page"]
    out, seen = [], set()
    try:
        for p in range(1, max_pages + 1):
            # 注意: 该镜像不支持 t=<标签> 筛选（会返回空页），故全量抓取，
            # 单体判定改由作品详情页的「單體作品」标签完成
            params = ["sort_type=0"]
            if p > 1:
                params.append(f"page={p}")
            url = f"{BASE}/actors/{actor_id}?" + "&".join(params)
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(random.uniform(1.2, 2.2))
            if is_cloudflare_challenge_pw(page):
                print("[警告] 遇到 Cloudflare 验证，等待 15s", file=sys.stderr)
                time.sleep(15)
            html = page.content()
            items = re.findall(
                r'<a href="/v/([A-Za-z0-9]+)" class="box" title="([^"]*)">(.*?)</a>', html, re.S)
            if not items:
                break
            new = 0
            for href, title, body in items:
                m = re.search(r"<strong>([^<]+)</strong>", body)
                code = normalize_code(m.group(1)) if m else None
                if not code or code in seen:
                    continue
                seen.add(code)
                has_magnet = "含磁鏈" in body or "含中字磁鏈" in body
                out.append((code, title[:70], has_magnet, href))
                new += 1
            print(f"  第 {p} 页: +{new} 条（累计 {len(out)}）", flush=True)
            if new == 0:
                break
            # 判断是否还有下一页
            if f"page={p+1}" not in html:
                break
    finally:
        close_playwright_session(session)
    return out


def main():
    ap = argparse.ArgumentParser(description="对比演员 JavDB 作品与本地库")
    ap.add_argument("actor_name")
    ap.add_argument("--db-path", default=DB_PATH)
    ap.add_argument("--all-works", action="store_true", help="不筛选单体作品")
    ap.add_argument("--missing-only", action="store_true", help="只列出库外的单体作品")
    ap.add_argument("--show-all", action="store_true", help="列出全部单体作品（默认只列库外）")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    conn = sqlite3.connect(args.db_path, timeout=30)
    row = conn.execute("SELECT id,name,profile_url FROM actors WHERE name=? OR name_common=? OR name_traditional=? LIMIT 1",
                       (args.actor_name, args.actor_name, args.actor_name)).fetchone()
    if not row or not row[2]:
        print(f"未找到演员或缺少 JavDB 链接: {args.actor_name}")
        return 1
    actor_db_id, name, profile_url = row
    m = re.search(r"/actors/([A-Za-z0-9]+)", profile_url or "")
    if not m:
        print(f"无法解析 JavDB 演员 ID: {profile_url}")
        return 1
    actor_id = m.group(1)
    print(f"演员: {name} (DB#{actor_db_id}) | JavDB: {actor_id} | 筛选: {'全部作品' if args.all_works else '單體作品'}")

    works = crawl_actor_codes(actor_id, solo=not args.all_works)
    local = local_codes(conn)
    print(f"JavDB 作品总数: {len(works)} | 本地番号库: {len(local)}")

    # 逐条判定是否单体作品（镜像站筛选参数无效，只能读详情页标签）
    session = setup_playwright_session(use_proxy=False, headless=True,
                                       browser_name="msedge", profile_mode="persisted")
    solo_cache = {}
    if session:
        try:
            total = len(works)
            for i, w in enumerate(works, 1):
                w_solo = classify_solo(session, w[3], solo_cache)
                works[i-1] = w + (w_solo,)
                if i % 20 == 0 or i == total:
                    n_solo = sum(1 for x in works if len(x) > 4 and x[4])
                    print(f"  判定 {i}/{total}（单体 {n_solo}）", flush=True)
        finally:
            close_playwright_session(session)

    solo_works = [w for w in works if len(w) > 4 and w[4]]
    have = [w for w in solo_works if w[0] in local]
    miss = [w for w in solo_works if w[0] not in local]

    print("\n" + "=" * 64)
    print(f"单体作品: {len(solo_works)} 部 | 本地已有: {len(have)} 部 | **库外: {len(miss)} 部**")
    print(f"（全部作品 {len(works)} 部；本地番号库 {len(local)} 条）")
    show = miss if args.missing_only else solo_works
    if args.limit:
        show = show[:args.limit]
    if show:
        print(f"\n{'库外单体作品' if args.missing_only else '单体作品'}清单:")
        for w in show:
            code, title, mag = w[0], w[1], w[2]
            flag = "有磁链" if mag else "无磁链"
            mark = "缺" if code not in local else "有"
            print(f"  [{mark}] {code:<12} {flag}  {title}")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
