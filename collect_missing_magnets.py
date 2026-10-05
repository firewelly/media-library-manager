#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
收集「库外单体作品」磁力链接（按偏好优选）并复制到剪贴板
==========================================================

偏好规则（用户设定）:
  1. 有字幕的优先：``-UC``（无码破解+中字）> ``-C``（中字）
  2. 其次无码（``-U``）
  3. 再比码率/体积：4K > 高清/FHD > HD > 体积更大者

实现说明:
  - 详情页（/v/<id>）与演员页均可**匿名** requests 直接抓取（无需登录、无需浏览器），
    因此可并发；单体判定用详情页的「單體作品」类别标签。
  - 范围裁剪：先按演员页的「含磁鏈」标记过滤（无磁链的作品对下载无意义），
    再逐条读详情页确认单体 + 优选磁链。

用法:
    python3 collect_missing_magnets.py 美乃すずめ 篠田ゆう --copy
    python3 collect_missing_magnets.py 篠田ゆう --copy --max-details 300
    python3 collect_missing_magnets.py 美乃すずめ --with-comments --out /tmp/list.txt
"""

import os
import json
import re
import sys
import time
import sqlite3
import argparse
import subprocess
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compare_actor_filmography import local_codes, normalize_code, BASE

UA = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
}
MAX_PAGES = 80


def crawl_actor_works(actor_id, session=None):
    """抓演员页全部作品：返回 [{code,title,has_mag,href}]（含分页）"""
    sess = session or requests.Session()
    out, seen = [], set()
    for p in range(1, MAX_PAGES + 1):
        url = f"{BASE}/actors/{actor_id}?sort_type=0" + (f"&page={p}" if p > 1 else "")
        try:
            r = sess.get(url, headers=UA, timeout=25)
        except Exception as e:
            print(f"    [列表失败] p{p}: {str(e)[:50]}", file=sys.stderr)
            break
        items = re.findall(r'<a href="/v/([A-Za-z0-9]+)" class="box" title="([^"]*)">(.*?)</a>',
                           r.text, re.S)
        if not items:
            break
        new = 0
        for href, title, body in items:
            m = re.search(r"<strong>([^<]+)</strong>", body)
            code = normalize_code(m.group(1)) if m else None
            if not code or code in seen:
                continue
            seen.add(code)
            out.append({"code": code, "title": title[:70],
                        "has_mag": ("含磁鏈" in body or "含中字磁鏈" in body), "href": href})
            new += 1
        if new == 0 or f"page={p+1}" not in r.text:
            break
    return out


MAGNET_CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "results", "magnets", "censored_magnets_cache.json")
_MAGNET_CACHE = {}
if os.path.exists(MAGNET_CACHE_PATH):
    try:
        _MAGNET_CACHE = json.load(open(MAGNET_CACHE_PATH))
    except Exception:
        _MAGNET_CACHE = {}


def save_magnet_cache():
    try:
        os.makedirs(os.path.dirname(MAGNET_CACHE_PATH), exist_ok=True)
        json.dump(_MAGNET_CACHE, open(MAGNET_CACHE_PATH, "w"), ensure_ascii=False)
    except Exception:
        pass


def parse_detail(html):
    """解析详情页：是否单体作品 + 磁链条目"""
    tags = re.findall(r'href="/tags[^"]*"[^>]*>([^<]{2,16})<', html)
    solo = any("單體" in t for t in tags)
    magnets, seen = [], set()
    for blk in re.split(r'<div class="item ', html)[1:]:
        mm = re.search(r"btih:([a-fA-F0-9]{32,40})", blk)
        if not mm:
            continue
        h = mm.group(1).lower()
        if h in seen:
            continue
        seen.add(h)
        dn = re.search(r'dn=([^"&\s]+)', blk)
        link = f"magnet:?xt=urn:btih:{mm.group(1)}" + (f"&dn={dn.group(1)}" if dn else "")
        nm = re.search(r'<span class="name">([^<]+)</span>', blk)
        sz = re.search(r'data-size="(\d+)"', blk)
        tg = [t for t in re.findall(r'<span class="tag[^"]*">([^<]+)</span>', blk)
              if t.strip() not in ("是", "否")]      # 过滤页面筛选标签噪音
        magnets.append({"link": link, "name": nm.group(1) if nm else "",
                        "tags": tg, "size_mb": int(sz.group(1)) if sz else 0})
    return solo, magnets


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


def magnet_score(m):
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


def copy_to_clipboard(text):
    try:
        subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
        return True
    except Exception as e:
        print(f"[警告] 复制剪贴板失败: {e}", file=sys.stderr)
        return False


def main():
    ap = argparse.ArgumentParser(description="收集库外单体作品磁链并复制")
    ap.add_argument("actor_names", nargs="*")
    ap.add_argument("--actors-file", default="", help="演员名清单文件（每行一个）")
    ap.add_argument("--db-path", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "media_library.db"))
    ap.add_argument("--copy", action="store_true")
    ap.add_argument("--all", action="store_true", help="不做单体筛选")
    ap.add_argument("--include-no-badge", action="store_true", help="连未标『含磁鏈』的作品也检查")
    ap.add_argument("--max-details", type=int, default=0, help="详情页检查数量上限")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--with-comments", action="store_true", help="磁链前附『# 番号 标题』注释")
    ap.add_argument("--out", default="", help="写出清单文件（增量追加，可续跑）")
    ap.add_argument("--progress", default="", help="进度文件（记录已处理演员，默认与 --out 同名的 .progress）")
    ap.add_argument("--max-per-actor", type=int, default=0, help="每位演员最多检查的详情数（0=不限）")
    args = ap.parse_args()
    if args.actors_file:
        with open(args.actors_file, encoding="utf-8") as f:
            args.actor_names = list(args.actor_names) + [l.strip() for l in f if l.strip()]
    if not args.actor_names:
        print("未指定演员（位置参数或 --actors-file）")
        return 1

    conn = sqlite3.connect(args.db_path, timeout=30)
    local = local_codes(conn)
    import json as _json
    prog_path = args.progress or (args.out + ".progress" if args.out else "")
    done_actors = set()
    if prog_path and os.path.exists(prog_path):
        try:
            done_actors = set(_json.load(open(prog_path)))
        except Exception:
            done_actors = set()
    if done_actors:
        print(f"[续跑] 已完成演员 {len(done_actors)} 位: {', '.join(sorted(done_actors))}", flush=True)
    results = []
    sections = []

    # 已完成的演员也要占用其 JavDB ID，避免别名行重复处理
    seen_actor_ids = set()
    for _n in done_actors:
        _r = conn.execute("SELECT profile_url FROM actors WHERE name=? LIMIT 1", (_n,)).fetchone()
        if _r and _r[0]:
            _m = re.search(r"/actors/([A-Za-z0-9]+)", _r[0])
            if _m:
                seen_actor_ids.add(_m.group(1))
    for actor_name in args.actor_names:
        row = conn.execute("""SELECT id,name,profile_url FROM actors
                              WHERE name=? OR name_common=? OR name_traditional=? LIMIT 1""",
                           (actor_name,) * 3).fetchone()
        if not row or not row[2]:
            print(f"[跳过] 未找到演员或缺少 JavDB 链接: {actor_name}")
            continue
        name = row[1]
        if name in done_actors:
            continue
        m = re.search(r"/actors/([A-Za-z0-9]+)", row[2])
        actor_id = m.group(1)
        if actor_id in seen_actor_ids:
            print(f"[跳过] {name}: 与已处理演员同属 JavDB {actor_id}（别名行）")
            continue
        seen_actor_ids.add(actor_id)
        works = crawl_actor_works(actor_id)
        all_missing = [w for w in works if w["code"] not in local]
        missing = all_missing if args.include_no_badge else [w for w in all_missing if w["has_mag"]]
        if args.max_details:
            missing = missing[:args.max_details]
        if args.max_per_actor:
            missing = missing[:args.max_per_actor]
        print(f"\n=== {name} (JavDB {actor_id}) ===")
        print(f"全部 {len(works)} 部 | 库外 {len(all_missing)} 部 | 待查详情 {len(missing)} 部"
              f"（并发 {args.workers}）", flush=True)
        if not missing:
            continue

        def fetch(w):
            # 每个任务独立 Session（requests.Session 非线程安全，共用会导致请求失败）
            if w["href"] in _MAGNET_CACHE:            # 命中缓存：离线重选，无需再抓
                solo, magnets = _MAGNET_CACHE[w["href"]]
                return w, (solo, magnets)
            for attempt in range(3):
                try:
                    r = requests.get(f"{BASE}/v/{w['href']}", headers=UA, timeout=25)
                    if r.status_code == 200:
                        solo, magnets = parse_detail(r.text)
                        _MAGNET_CACHE[w["href"]] = [solo, magnets]
                        return w, (solo, magnets)
                except Exception:
                    time.sleep(0.6 * (attempt + 1))
            return w, (None, [])

        done = 0
        actor_rows = []
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            for fut in as_completed([pool.submit(fetch, w) for w in missing]):
                w, (solo, magnets) = fut.result()
                done += 1
                if (args.all or solo) and magnets:
                    ranked = sorted(magnets, key=magnet_score, reverse=True)
                    rec = {"actor": name, "code": w["code"], "title": w["title"],
                           "best": ranked[0], "n": len(ranked)}
                    results.append(rec)
                    actor_rows.append(rec)
                if done % 50 == 0 or done == len(missing):
                    print(f"  详情 {done}/{len(missing)} | 本演员已选 {len(actor_rows)} 部", flush=True)
        # 本演员完成：立即写盘 + 刷新剪贴板 + 记录进度（便于随时暂停/续跑）
        if args.out:
            parts = [f"# {name}"] + [r["best"]["link"] for r in actor_rows]
            with open(args.out, "a", encoding="utf-8") as f:
                f.write("\n".join(parts) + "\n\n")
        if prog_path:
            done_actors.add(name)
            try:
                _json.dump(sorted(done_actors), open(prog_path, "w"), ensure_ascii=False)
            except Exception:
                pass
        if args.copy and actor_rows:
            try:
                existing = open(args.out, encoding="utf-8").read() if args.out else ""
                copy_to_clipboard(existing.strip())
            except Exception:
                pass
        save_magnet_cache()
        print(f"  [完成] {name}: {len(actor_rows)} 条已追加到 {args.out or '(未指定)'}", flush=True)

    if prog_path:
        try:
            _json.dump(sorted({r["actor"] for r in results}), open(prog_path, "w"))
        except Exception:
            pass
    print("\n" + "=" * 64)
    print(f"命中: {len(results)} 部作品（库外{'全部' if args.all else '单体'} + 有磁链）")
    print("选取规则: 字幕(UC>C) > 无码(U) > 4K/高清/大文件\n")
    for r in results:
        b = r["best"]
        gb = (b.get("size_mb") or 0) / 1024.0
        flag = "  ⚠️ 体积偏大(无更小资源)" if gb > 15 else ("  (体积未知)" if not b.get("size_mb") else "")
        tag = "/".join(b["tags"]) or "-"
        print(f"  {r['code']:<12} {b['name'][:40]:<40} [{tag}] {gb:.1f}GB{flag}")

    by_actor = {}
    for r in results:
        by_actor.setdefault(r["actor"], []).append(r)
    lines = []
    for actor, rs in by_actor.items():
        lines.append(f"# {actor}")
        for r in rs:
            b = r["best"]
            if args.with_comments:
                lines.append(f"#   {r['code']} {r['title'][:44]} [{b['name'][:36]}] "
                             f"{'/'.join(b['tags']) or '-'} {b['size_mb']}MB")
            lines.append(b["link"])
        lines.append("")
    payload = "\n".join(lines).strip()

    if args.out:
        print(f"\n清单文件: {args.out}（累计 {len(results)} 条 / {len(by_actor)} 位演员，已增量写入）")
    if args.copy and payload:
        ok = copy_to_clipboard(payload)
        print(f"[剪贴板] {'已复制' if ok else '复制失败'} | {len(results)} 条磁链 | {len(payload)} 字符")
    elif not args.copy:
        print("\n(未加 --copy，仅打印)")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
