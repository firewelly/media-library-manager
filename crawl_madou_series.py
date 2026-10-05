#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
麻豆傳媒映畫（JavDB maker N73g）全量采集 + 演员识别
=====================================================

背景: 该系列在 JavDB 上演员字段为空，需从**封面 OCR / 标题 / 磁链文件名**中提取。
本机可用 macOS Vision（快速模式支持中文），无需下载模型；DeepSeek 视觉对成人封面会拒答，故不采用。

流程（按需分阶段执行）:
  1. ``--enumerate``: 登录态顺序翻页枚举全部作品（番号/标题/封面URL/href），
     直到连续若干页无新番号为止；结果写入 results/madou/series_index.json
  2. ``--details``  : 逐条打开作品页，抓取磁链（含 dn 文件名）、分类标签、发行日期
  3. ``--ocr``      : 下载封面并用 macOS Vision OCR（zh-Hans/zh-Hant/ja）
  4. ``--covers``   : 把封面图片下载到 results/madou/covers/
  5. ``--extract``  : 汇总三类证据（标题 / 磁链文件名 / 封面OCR），输出可读报告与 CSV

用法:
    python3 crawl_madou_series.py --enumerate
    python3 crawl_madou_series.py --details --workers 12
    python3 crawl_madou_series.py --covers --ocr
    python3 crawl_madou_series.py --extract
"""

import os
import re
import sys
import json
import time
import random
import argparse
import sqlite3
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from javdb_crawler_single import (
    setup_playwright_session, close_playwright_session, is_cloudflare_challenge_pw,
)

BASE = "https://javdb580.com"
MAKER = "N73g"
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "madou")
INDEX_PATH = os.path.join(OUT_DIR, "series_index.json")
DETAILS_PATH = os.path.join(OUT_DIR, "series_details.json")
OCR_PATH = os.path.join(OUT_DIR, "cover_ocr.json")
COVERS_DIR = os.path.join(OUT_DIR, "covers")
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "media_library.db")
UA = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


def load_json(p, default):
    if os.path.exists(p):
        try:
            return json.load(open(p, encoding="utf-8"))
        except Exception:
            pass
    return default


def save_json(p, data):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(data, open(p, "w", encoding="utf-8"), ensure_ascii=False)


def parse_list_page(html):
    items = re.findall(r'<a href="/v/([A-Za-z0-9]+)" class="box" title="([^"]*)">(.*?)</a>', html, re.S)
    out = []
    for href, title, body in items:
        m = re.search(r"<strong>([^<]+)</strong>", body)
        cov = re.search(r'src="(https://c0\.jdbstatic\.com/covers/[^"]+)"', body)
        out.append({
            "href": href, "code": (m.group(1).strip() if m else ""),
            "title": re.sub(r"\s+", " ", title).strip(),
            "cover": cov.group(1) if cov else "",
            "mag": ("含磁鏈" in body or "含中字磁鏈" in body),
        })
    return out


def enumerate_series(max_pages=2000, patience=3):
    """顺序翻页枚举，直到连续 patience 页没有新番号"""
    data = load_json(INDEX_PATH, {})
    session = setup_playwright_session(use_proxy=False, headless=True,
                                       browser_name="msedge", profile_mode="persisted")
    if not session:
        print("[错误] 浏览器会话启动失败")
        return 1
    page = session["page"]
    no_new = 0
    try:
        for p in range(1, max_pages + 1):
            url = f"{BASE}/makers/{MAKER}?f=download" + (f"&page={p}" if p > 1 else "")
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(random.uniform(1.0, 1.8))
            if is_cloudflare_challenge_pw(page):
                time.sleep(10)
            items = parse_list_page(page.content())
            if not items:
                print(f"  第{p}页 无条目，结束")
                break
            new = 0
            for it in items:
                if it["code"] and it["code"] not in data:
                    it["page"] = p
                    data[it["code"]] = it
                    new += 1
            if new == 0:
                no_new += 1
            else:
                no_new = 0
            if p % 10 == 0 or new == 0:
                save_json(INDEX_PATH, data)
                print(f"  第{p}页 +{new}（累计 {len(data)} 部）", flush=True)
            if no_new >= patience:
                print(f"  连续 {patience} 页无新番号 → 认为已到末尾（第 {p} 页）")
                break
    finally:
        close_playwright_session(session)
    save_json(INDEX_PATH, data)
    print(f"\n枚举完成: {len(data)} 部 → {INDEX_PATH}")
    return 0


def fetch_detail(href, sess):
    try:
        r = sess.get(f"{BASE}/v/{href}", headers=UA, timeout=25)
        if r.status_code != 200:
            return None
        html = r.text
        tags = [t for t in re.findall(r'href="/tags[^"]*"[^>]*>([^<]{2,16})<', html) if t.strip() not in ("是", "否")]
        mags = []
        seen = set()
        for blk in re.split(r'<div class="item ', html)[1:]:
            mm = re.search(r"btih:([a-fA-F0-9]{32,40})", blk)
            if not mm:
                continue
            h = mm.group(1).lower()
            if h in seen:
                continue
            seen.add(h)
            dn = re.search(r'dn=([^"&\s]+)', blk)
            sz = re.search(r'data-size="(\d+)"', blk)
            tg = [t for t in re.findall(r'<span class="tag[^"]*">([^<]+)</span>', blk) if t.strip() not in ("是", "否")]
            mags.append({"hash": h, "dn": (dn.group(1) if dn else ""), "size_mb": int(sz.group(1)) if sz else 0, "tags": tg})
        acts = [a[1] for a in re.findall(r'href="/actors/([A-Za-z0-9]+)"[^>]*>([^<]{1,20})<', html)
                if a[0] not in ("censored", "uncensored", "western")]
        date = re.search(r'(\d{4}-\d{2}-\d{2})', html)
        return {"tags": tags, "magnets": mags, "javdb_actors": acts,
                "date": date.group(1) if date else ""}
    except Exception:
        return None


def crawl_details(workers=12):
    data = load_json(INDEX_PATH, {})
    detail = load_json(DETAILS_PATH, {})
    todo = [c for c in data if c not in detail]
    print(f"待抓详情: {len(todo)} / {len(data)}")
    sess = requests.Session()
    sess.cookies.set("over18", "1", domain="javdb580.com")

    def work(code):
        d = fetch_detail(data[code]["href"], sess)
        return code, d

    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for fut in as_completed([pool.submit(work, c) for c in todo]):
            code, d = fut.result()
            detail[code] = d or {}
            done += 1
            if done % 100 == 0 or done == len(todo):
                save_json(DETAILS_PATH, detail)
                print(f"  详情 {done}/{len(todo)}", flush=True)
    save_json(DETAILS_PATH, detail)
    print(f"详情完成: {len(detail)} 条 → {DETAILS_PATH}")
    return 0


def crawl_details_pw(pages=6):
    """用登录态（Playwright 多标签页并发）抓详情——本系列磁链仅登录可见"""
    import asyncio
    from playwright.async_api import async_playwright

    data = load_json(INDEX_PATH, {})
    detail = load_json(DETAILS_PATH, {})
    # 已有磁链的跳过；磁链为空的重新抓
    todo = [c for c in data if not (detail.get(c) or {}).get("magnets")]
    print(f"待抓详情(需登录态): {len(todo)} / {len(data)}", flush=True)
    profile_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".playwright_user_data", "msedge")

    async def run():
        async with async_playwright() as pw:
            ctx = await pw.chromium.launch_persistent_context(
                profile_dir, channel="msedge", headless=True, locale="zh-CN",
                user_agent=UA["User-Agent"],
                extra_http_headers={"Accept-Language": UA["Accept-Language"]},
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )
            pg = ctx.pages[0] if ctx.pages else await ctx.new_page()
            await pg.goto(f"{BASE}/", wait_until="domcontentloaded", timeout=60000)
            try:
                await ctx.add_cookies([{"name": "over18", "value": "1", "domain": "javdb580.com", "path": "/"}])
            except Exception:
                pass

            pool = [await ctx.new_page() for _ in range(pages)]
            lock = asyncio.Lock()
            idx = {"i": 0}
            done = {"n": 0}

            async def parse(page_html):
                tags = [t for t in re.findall(r'href="/tags[^"]*"[^>]*>([^<]{2,16})<', page_html)
                        if t.strip() not in ("是", "否", "類別", "有碼", "無碼", "歐美", "FC2", "動漫")]
                mags, seen = [], set()
                for blk in re.split(r'<div class="item ', page_html)[1:]:
                    mm = re.search(r"btih:([a-fA-F0-9]{32,40})", blk)
                    if not mm:
                        continue
                    h = mm.group(1).lower()
                    if h in seen:
                        continue
                    seen.add(h)
                    dn = re.search(r'dn=([^"&\s]+)', blk)
                    sz = re.search(r'data-size="(\d+)"', blk)
                    tg = [t for t in re.findall(r'<span class="tag[^"]*">([^<]+)</span>', blk) if t.strip() not in ("是", "否")]
                    mags.append({"hash": h, "dn": (dn.group(1) if dn else ""),
                                 "size_mb": int(sz.group(1)) if sz else 0, "tags": tg})
                acts = [a[1] for a in re.findall(r'href="/actors/([A-Za-z0-9]+)"[^>]*>([^<]{1,20})<', page_html)
                        if a[0] not in ("censored", "uncensored", "western")]
                date = re.search(r'<div class="meta">\s*(\d{4}-\d{2}-\d{2})', page_html) or re.search(r'(\d{4}-\d{2}-\d{2})', page_html)
                return {"tags": tags, "magnets": mags, "javdb_actors": acts, "date": date.group(1) if date else ""}

            async def worker(page):
                while True:
                    async with lock:
                        if idx["i"] >= len(todo):
                            return
                        code = todo[idx["i"]]
                        idx["i"] += 1
                    try:
                        await page.goto(f"{BASE}/v/{data[code]['href']}", wait_until="domcontentloaded", timeout=45000)
                        await asyncio.sleep(0.8)
                        info = await parse(await page.content())
                        detail[code] = info
                    except Exception:
                        detail[code] = detail.get(code) or {}
                    async with lock:
                        done["n"] += 1
                        if done["n"] % 100 == 0:
                            save_json(DETAILS_PATH, detail)
                            print(f"  详情 {done['n']}/{len(todo)}", flush=True)

            await asyncio.gather(*[worker(p) for p in pool])
            await ctx.close()

    asyncio.run(run())
    save_json(DETAILS_PATH, detail)
    n_mag = sum(1 for c in detail if (detail[c] or {}).get("magnets"))
    print(f"详情完成: {len(detail)} 条 | 其中有磁链 {n_mag} 条 → {DETAILS_PATH}")
    return 0


def download_covers(workers=16):
    """并发下载封面（串行太慢）"""
    data = load_json(INDEX_PATH, {})
    os.makedirs(COVERS_DIR, exist_ok=True)

    def one(item):
        code, it = item
        if not it.get("cover"):
            return 0
        path = os.path.join(COVERS_DIR, f"{code}{os.path.splitext(it['cover'])[1] or '.jpg'}")
        if os.path.exists(path) and os.path.getsize(path) > 1000:
            return 0
        try:
            r = requests.get(it["cover"], headers=UA, timeout=25)
            if r.status_code == 200 and len(r.content) > 1000:
                open(path, "wb").write(r.content)
                return 1
        except Exception:
            pass
        return 0

    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i, r in enumerate(pool.map(one, list(data.items())), 1):
            done += r
            if i % 200 == 0:
                print(f"  进度 {i}/{len(data)}（新增 {done}）", flush=True)
    print(f"封面下载完成: 新增 {done} 张 → {COVERS_DIR}")
    return 0


def ocr_covers():
    """用 macOS Vision（快速模式，支持中文）识别封面文字"""
    import Vision, Quartz

    def ocr_file(path, langs=("zh-Hans", "zh-Hant", "ja-JP", "en-US")):
        url = Quartz.CFURLCreateFromFileSystemRepresentation(None, path.encode(), len(path.encode()), False)
        src = Quartz.CGImageSourceCreateWithURL(url, None)
        cg = Quartz.CGImageSourceCreateImageAtIndex(src, 0, None)
        if cg is None:
            return []
        req = Vision.VNRecognizeTextRequest.alloc().init()
        req.setRecognitionLevel_(0)          # 0=fast（中文仅在快速模式可用）
        req.setRecognitionLanguages_(list(langs))
        req.setUsesLanguageCorrection_(False)
        Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(cg, None).performRequests_error_([req], None)
        return [r.topCandidates_(1)[0].string() for r in (req.results() or [])]

    data = load_json(INDEX_PATH, {})
    ocr = load_json(OCR_PATH, {})
    todo = [c for c in data if c not in ocr and
            any(os.path.exists(os.path.join(COVERS_DIR, f"{c}{ext}")) for ext in (".jpg", ".png", ".jpeg"))]
    print(f"待 OCR: {len(todo)} 张")

    def one(code):
        for ext in (".jpg", ".png", ".jpeg"):
            p = os.path.join(COVERS_DIR, f"{code}{ext}")
            if os.path.exists(p):
                try:
                    return code, ocr_file(p)
                except Exception:
                    return code, []
        return code, []

    done = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        for code, text in pool.map(one, todo):
            ocr[code] = text
            done += 1
            if done % 100 == 0:
                save_json(OCR_PATH, ocr)
                print(f"  OCR {done}/{len(todo)}", flush=True)
    save_json(OCR_PATH, ocr)
    print(f"OCR 完成: {len(ocr)} 条 → {OCR_PATH}")
    return 0


def extract_report():
    """汇总证据（标题 + 全部磁链文件名 + 封面OCR）输出报告"""
    data = load_json(INDEX_PATH, {})
    detail = load_json(DETAILS_PATH, {})
    ocr = load_json(OCR_PATH, {})

    conn = sqlite3.connect(DB_PATH)
    known = set()
    for (n,) in conn.execute("SELECT name FROM actors WHERE name IS NOT NULL AND length(name)>=2"):
        known.add(n)
    for (a,) in conn.execute("SELECT aliases FROM actors WHERE aliases IS NOT NULL AND aliases<>''"):
        for x in (a or "").split(","):
            if len(x.strip()) >= 2:
                known.add(x.strip())
    conn.close()

    def names_from_text(text):
        if not text:
            return set()
        t = text.replace("&amp;", "&")
        return {n for n in known if n in t}

    rows = []
    for code, it in data.items():
        d = detail.get(code) or {}
        mags = d.get("magnets") or []
        title = it.get("title", "")
        # 全部磁链文件名（不只最大那条）都作为证据
        all_dns = " | ".join(m.get("dn", "") for m in mags)
        ocr_text = " ".join(ocr.get(code) or [])
        names = set()
        names |= names_from_text(title)
        names |= names_from_text(all_dns)
        names |= names_from_text(ocr_text)
        sizes = [round((m.get("size_mb") or 0) / 1024, 2) for m in mags if m.get("size_mb")]
        rows.append({
            "code": code,
            "title": title,
            "date": d.get("date", ""),
            "javdb_actors": d.get("javdb_actors") or [],
            "found_names": sorted(names),
            "n_magnets": len(mags),
            "sizes_gb": sorted(set(sizes)),
            "dn_all": all_dns[:400],
            "ocr": ocr_text[:300],
            "cover": it.get("cover", ""),
        })
    rows.sort(key=lambda r: r["code"])
    save_json(os.path.join(OUT_DIR, "series_report.json"), rows)
    import csv
    cols = ["code", "title", "date", "javdb_actors", "found_names", "n_magnets", "sizes_gb", "dn_all", "ocr", "cover"]
    with open(os.path.join(OUT_DIR, "series_report.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({**r, "javdb_actors": "|".join(r["javdb_actors"]),
                        "found_names": "|".join(r["found_names"]),
                        "sizes_gb": "|".join(str(x) for x in r["sizes_gb"])})

    have = sum(1 for r in rows if r["found_names"] or r["javdb_actors"])
    with_mag = sum(1 for r in rows if r["n_magnets"])
    print(f"报告: {len(rows)} 部 | 有磁链 {with_mag} | 识别出演员 {have}")
    print(f"  {os.path.join(OUT_DIR, 'series_report.json')}")
    print(f"  {os.path.join(OUT_DIR, 'series_report.csv')}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="麻豆傳媒系列全量采集与演员识别")
    ap.add_argument("--enumerate", action="store_true")
    ap.add_argument("--details", action="store_true")
    ap.add_argument("--details-pw", action="store_true", help="登录态多标签页抓详情（本系列磁链仅登录可见）")
    ap.add_argument("--pages", type=int, default=6, help="并发标签页数")
    ap.add_argument("--covers", action="store_true")
    ap.add_argument("--ocr", action="store_true")
    ap.add_argument("--extract", action="store_true")
    ap.add_argument("--workers", type=int, default=12)
    args = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True)
    if args.enumerate:
        return enumerate_series()
    if args.details:
        return crawl_details(args.workers)
    if args.details_pw:
        return crawl_details_pw(args.pages)
    if args.covers:
        download_covers()
    if args.ocr:
        return ocr_covers()
    if args.extract:
        return extract_report()
    print("请指定阶段：--enumerate / --details / --covers --ocr / --extract")
    return 0


if __name__ == "__main__":
    sys.exit(main())
