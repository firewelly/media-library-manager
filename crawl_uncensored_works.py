#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
抓取 JavDB「無碼」演员页的作品清单（需登录态）
================================================

背景: JavDB 上同一演员常有独立「無碼」页（如 長澤あずさ = Q7G7 有碼 + 8Ad9 無碼），
无码页**需登录**才能打开，因此与无码文件的番号对不上。
本脚本用持久化登录态（.playwright_user_data/msedge）抓取无码页作品清单：

  1. 读取 actors.javdb_uncensored_id（由 link_uncensored_actors.py 写入）；
  2. 用 Playwright 登录态打开无码页并翻页，收集番号+标题；
  3. 与本地库比对（javdb_info.javdb_code + 文件名番号），输出：
       - 该演员无码作品总数 / 本地已有 / 库外缺失（带番号）
  4. 结果写入 results/magnets/uncensored_works_<日期>.txt（gitignore 目录）

用法:
    python3 crawl_uncensored_works.py                    # 全部已关联无码页的演员
    python3 crawl_uncensored_works.py 長澤あずさ          # 指定演员
    python3 crawl_uncensored_works.py --dry-run          # 只统计不写文件
"""

import os
import re
import sys
import json
import time
import random
import sqlite3
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from javdb_crawler_single import (
    setup_playwright_session, close_playwright_session, is_cloudflare_challenge_pw,
)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "media_library.db")
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "magnets")
BASE = "https://javdb580.com"
MAX_PAGES = 60


def norm_code(c):
    m = re.match(r"^([A-Za-z]{2,6})[-_]?(\d{2,5})$", str(c or "").strip().replace("_", "-").upper())
    return f"{m.group(1)}-{int(m.group(2))}" if m else None


def code_from_name(fn):
    if not fn:
        return None
    s = re.sub(r"\.(mp4|mkv|avi|wmv|ts|iso|m4v|rmvb|mov)$", "", str(fn), flags=re.I)
    s = re.sub(r"[-_ ]?(UC|U|C|CD\d|[45]K|HD|FHD|SD|BD|VR|LEAK|uncensored|无码破解|中文字幕|字幕)$", "", s, flags=re.I)
    return norm_code(s)


def local_codes(cur):
    codes = set()
    for (c,) in cur.execute("SELECT javdb_code FROM javdb_info WHERE javdb_code IS NOT NULL AND javdb_code<>''"):
        n = norm_code(c)
        if n:
            codes.add(n)
    for (fn,) in cur.execute("SELECT file_name FROM videos WHERE file_name IS NOT NULL"):
        n = code_from_name(fn)
        if n:
            codes.add(n)
    return codes


def res_tier(name):
    """分辨率偏好：1080p 最佳；720p/4K 可用；8K 及以上不选（用户设备 1080p–1440p）"""
    up = (name or "").upper()
    if "8K" in up:
        return 0
    if "1080" in up or "FHD" in up:
        return 3
    if "4K" in up or "2160" in up:
        return 2                      # 4K 允许，但不比 1080p 优先
    if "720" in up:
        return 2
    return 2                          # 名称未标注分辨率：中性


def is_vr(name, code=""):
    """VR 作品体积天生偏大，体积评分放宽"""
    s = f"{name} {code}".upper()
    return any(k in s for k in ("VR", "IPVR", "PRVR", "VRKM", "SAVR", "TMVR", "3DBD"))


def size_tier(mb, vr=False):
    """体积偏好：非 VR 以 5–10GB 最佳、>20GB 最后才选；VR 放宽到 5–25GB"""
    if not mb:
        return 2
    gb = mb / 1024.0
    if vr:
        if 5 <= gb <= 25:
            return 3
        return 2 if gb <= 40 else 1
    if 5 <= gb <= 10:
        return 3
    if 3 <= gb < 5 or 10 < gb <= 15:
        return 2
    if 2 <= gb < 3 or 15 < gb <= 20:
        return 1
    return 0


def score_magnet(m):
    """优选规则（用户设定，按优先级排序）:
       1) **中文字幕**为第一优先级（``-UC`` 无码破解+中字 > ``-C`` 中字 > 有「字幕/中字」标签）
       2) 其次看**清晰度**：1080p/FHD 最优，4K/720p 可用，8K 不考虑（设备 1080p–1440p）
       3) 体积：5–10GB 最佳，>20GB 仅兜底；VR 类放宽到 5–25GB
       4) 同为字幕/清晰度时，无码(U)、高清标签、体积更接近 7GB 者优先
    """
    name, up = m.get("name", ""), (m.get("name", "") or "").upper()
    tags = " ".join(m.get("tags") or [])
    is_uc = bool(re.search(r"[-_.]UC\b|UC\.|[\[（(]?UC[\]）)]", up))   # UC = 无码+中字（注意：单纯"无码破解"≠有字幕）
    has_sub = bool(is_uc or re.search(r"[-_.]C\b|C\.", up) or "字幕" in tags
                   or "中字" in tags or "中字" in name or "字幕" in name)
    is_uncensored = bool(is_uc or re.search(r"[-_.]U\b|U\.", up)
                         or any(k in name for k in ("无码", "無碼", "破解")))
    quality = 4 if "4K" in up else (3 if ("高清" in tags or "FHD" in up) else (2 if "HD" in up else 1))
    return (1 if has_sub else 0,                     # ① 中文字幕第一优先
            1 if (has_sub and is_uc) else 0,          #    字幕类里 UC 略优
            res_tier(name),                           # ② 清晰度（1080p > 4K/720p > 8K）
            size_tier(m.get("size_mb", 0), is_vr(name)),   # ③ 体积合理
            1 if is_uncensored else 0,
            quality,
            -(abs((m.get("size_mb", 0) or 0) - 7 * 1024)))


def crawl_uncensored(page, actor_id):
    """抓取无码页作品：返回 [{code,title,mag}]"""
    out, seen = [], set()
    for p in range(1, MAX_PAGES + 1):
        url = f"{BASE}/actors/{actor_id}?sort_type=0" + (f"&page={p}" if p > 1 else "")
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        time.sleep(random.uniform(1.2, 2.2))
        if is_cloudflare_challenge_pw(page):
            time.sleep(12)
        html = page.content()
        if "登入" in (page.title() or "") and p == 1:
            print("   [错误] 未登录：无码页需要登录态", flush=True)
            return None
        items = re.findall(r'<a href="/v/([A-Za-z0-9]+)" class="box" title="([^"]*)">(.*?)</a>', html, re.S)
        if not items:
            break
        new = 0
        for href, title, body in items:
            m = re.search(r"<strong>([^<]+)</strong>", body)
            code = norm_code(m.group(1)) if m else None
            if not code:                      # 无番号作品（素人/无码常见）：从标题里再试一次
                code = norm_code(re.search(r"([A-Za-z]{2,6}[-_]?\d{2,5})", title or "").group(1)) \
                       if re.search(r"([A-Za-z]{2,6}[-_]?\d{2,5})", title or "") else None
            key = code or ("_" + href)
            if key in seen:
                continue
            seen.add(key)
            out.append({"code": code, "title": title[:70], "href": href,
                        "mag": ("含磁鏈" in body or "含中字磁鏈" in body)})
            new += 1
        print(f"   第 {p} 页 +{new}（累计 {len(out)}）", flush=True)
        if new == 0 or f"page={p+1}" not in html:
            break
    return out


def main():
    ap = argparse.ArgumentParser(description="抓取无码页作品清单（需登录）")
    ap.add_argument("actors", nargs="*")
    ap.add_argument("--db-path", default=DB_PATH)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--magnets", action="store_true",
                    help="只保留有磁链作品并抓取磁链（无磁链一律丢弃）")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    conn = sqlite3.connect(args.db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    sql = "SELECT id,name,javdb_uncensored_id FROM actors WHERE javdb_uncensored_id IS NOT NULL AND javdb_uncensored_id<>''"
    if args.actors:
        ph = ",".join("?" * len(args.actors))
        sql += f" AND (name IN ({ph}) OR name_common IN ({ph}) OR name_traditional IN ({ph}))"
        rows = cur.execute(sql, tuple(args.actors) * 3).fetchall()
    else:
        rows = cur.execute(sql + " ORDER BY is_favorite DESC, movie_count DESC").fetchall()
    if args.limit:
        rows = rows[:args.limit]
    print(f"待抓取无码页的演员: {len(rows)} 位")

    local = local_codes(cur)
    magnet_cache_path = os.path.join(OUT_DIR, "uncensored_magnets.json")
    magnet_cache = {}
    if os.path.exists(magnet_cache_path):
        try:
            magnet_cache = json.load(open(magnet_cache_path))
        except Exception:
            magnet_cache = {}
    session = setup_playwright_session(use_proxy=False, headless=True,
                                       browser_name="msedge", profile_mode="persisted")
    if not session:
        print("[错误] 无法启动浏览器会话")
        return 1
    page = session["page"]
    mpage = session["context"].new_page()
    report_lines, summary = [], []
    try:
        for r in rows:
            print(f"\n=== {r['name']} (無碼页 {r['javdb_uncensored_id']}) ===", flush=True)
            works = crawl_uncensored(page, r["javdb_uncensored_id"])
            if works is None:
                summary.append((r["name"], None, None, None))
                continue
            if args.magnets:
                keep = []
                for w in works:
                    if not w.get("mag"):
                        continue                      # 无磁链：直接丢弃（无意义）
                    href = w.get("href")
                    if not href:
                        continue
                    if href not in magnet_cache:
                        try:
                            mpage.goto(f"{BASE}/v/{href}", wait_until="domcontentloaded", timeout=45000)
                            time.sleep(random.uniform(0.8, 1.6))
                            mhtml = mpage.content()
                            mags, seen_m = [], set()
                            for blk in re.split(r'<div class="item ', mhtml)[1:]:
                                mm = re.search(r"btih:([a-fA-F0-9]{32,40})", blk)
                                if not mm:
                                    continue
                                h = mm.group(1).lower()
                                if h in seen_m:
                                    continue
                                seen_m.add(h)
                                dn = re.search(r'dn=([^"&\s]+)', blk)
                                link = f"magnet:?xt=urn:btih:{mm.group(1)}" + (f"&dn={dn.group(1)}" if dn else "")
                                tg = re.findall(r'<span class="tag[^"]*">([^<]+)</span>', blk)
                                sz = re.search(r'data-size="(\d+)"', blk)
                                nm = re.search(r'<span class="name">([^<]+)</span>', blk)
                                mags.append({"link": link, "name": nm.group(1) if nm else "",
                                             "tags": tg, "size_mb": int(sz.group(1)) if sz else 0})
                            magnet_cache[href] = mags
                            json.dump(magnet_cache, open(magnet_cache_path, "w"), ensure_ascii=False)
                        except Exception as e:
                            magnet_cache[href] = []
                    w["magnets"] = magnet_cache.get(href) or []
                    if w["magnets"]:
                        keep.append(w)
                works = keep
            have = [w for w in works if w["code"] and w["code"] in local]
            miss = [w for w in works if not (w["code"] and w["code"] in local)]
            nocode = [w for w in works if not w["code"]]
            summary.append((r["name"], len(works), len(have), len(miss)))
            report_lines.append(f"# {r['name']}（無碼：库外 {len(miss)} 部 / 共 {len(works)}）")
            for w in miss:
                if args.magnets:
                    best = sorted(w.get("magnets") or [], key=score_magnet, reverse=True)
                    if not best:
                        continue
                    gb = (best[0].get("size_mb") or 0) / 1024.0
                    hint = f"{w['code'] or '无番号'} | {gb:.1f}GB | {w['title'][:44]}"
                    report_lines.append(f"#   {hint}")
                    report_lines.append(best[0]["link"])
                else:
                    tag = "有磁链" if w["mag"] else "无磁链"
                    report_lines.append(f"   {str(w['code'] or '（无番号）'):<12} {tag}  {w['title'][:60]}")
            report_lines.append("")
    finally:
        close_playwright_session(session)

    print("\n" + "=" * 64)
    print(f"{'演员':<12} {'无码作品':>8} {'本地已有':>8} {'库外':>6}")
    for name, total, have, miss in summary:
        if total is None:
            print(f"{name:<12} {'（未抓取/需登录）':>8}")
        else:
            print(f"{name:<12} {total:>8} {have:>8} {miss:>6}")
    if report_lines and not args.dry_run:
        path = os.path.join(OUT_DIR, f"uncensored_works_{datetime.now():%Y%m%d}.txt")
        open(path, "w", encoding="utf-8").write("\n".join(report_lines))
        print(f"\n清单已写出: {path}")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
