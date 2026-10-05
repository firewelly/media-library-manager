#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 av-wiki.net 补全演员档案字段（生日 / 身高 / 三围 / 罗马字名）
================================================================

背景: JavDB 改版后演员页已不再提供 生日/身高/三围 等档案字段，
本地 actors 表的 birth_date / debut_date / height / measurements 基本为空
（且历史遗留 height 值存在 '4'、'5' 这类明显错误的数据）。

数据来源: av-wiki.net（女優名まとめサイト），其演员页 meta 描述包含:
    AV女優名：河北彩花（かわきたさいか）- kawakita saika
    別名義：河北彩伽（かわきたさいか）
    生年月日：1999年04月24日
    サイズ：T169-B87-W57-H86

匹配策略: 用库里该演员的全部名称（name / name_common / name_traditional / aliases）
逐个搜索，取 av-wiki 演员页的「女優名 / 別名義」与本地名称**精确匹配**的结果，
避免同名或近名误配。

用法:
    python3 enrich_actor_profiles.py                # 干跑，只打印将写入的内容
    python3 enrich_actor_profiles.py --apply        # 写入数据库
    python3 enrich_actor_profiles.py --apply --limit 10
"""

import os
import re
import sys
import time
import random
import sqlite3
import argparse

import requests
from html import unescape

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "media_library.db")
BASE = "https://av-wiki.net"
REQUEST_SLEEP = (0.6, 1.2)   # 请求间隔（秒），批量并发时可调小
UA = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept-Language": "ja,zh-CN;q=0.9,zh;q=0.8",
}


def actor_tokens(row):
    """演员的全部可搜索名称"""
    toks = []
    for key in ("name", "name_common", "name_traditional"):
        v = (row[key] or "").strip()
        if v and v not in toks:
            toks.append(v)
    for a in (row["aliases"] or "").split(","):
        a = a.strip()
        if a and a not in toks:
            toks.append(a)
    return toks


def parse_size(size_text):
    """解析 av-wiki 的「サイズ」字段。

    兼容多种写法: "T169-B87-W57-H86" / "T161 B88(F) W59 H90" /
    "T158 / B92(Hカップ) / W54 / H86"
    返回 (height, measurements, cup)
    """
    if not size_text:
        return None, None, None
    height = measurements = cup = None
    m = re.search(r"T\s*(\d{2,3})", size_text)
    if m and 120 <= int(m.group(1)) <= 210:
        height = m.group(1)
    mb = re.search(r"B\s*(\d{2,3})\s*(?:[\(\（]\s*([A-Ka-k])(?:\s*カップ)?\s*[\)\）])?", size_text)
    b = mb.group(1) if mb else None
    if mb and mb.group(2):
        cup = mb.group(2).upper()
    mw = re.search(r"W\s*(\d{2,3})", size_text)
    mh = re.search(r"H\s*(\d{2,3})", size_text)
    if b and mw and mh:
        measurements = f"B{b}-W{mw.group(1)}-H{mh.group(1)}"
    if not cup:
        m2 = re.search(r"([A-Ka-k])\s*カップ", size_text)
        if m2:
            cup = m2.group(1).upper()
    return height, measurements, cup


def parse_profile_meta(page_html):
    """从演员页 meta 描述解析档案字段"""
    # 取 og:description（内容最完整），退化为页面里的 profile 区块
    m = re.search(r'<meta property="og:description" content="([^"]*)"', page_html)
    text = unescape(m.group(1)) if m else ""
    if not text:
        m2 = re.search(r"AV女優名[：:].{0,600}", page_html, re.S)
        text = unescape(m2.group(0)) if m2 else ""
    info = {"names": [], "birth_date": None, "height": None,
            "measurements": None, "cup": None, "romaji": None, "bio": None, "debut_date": None}

    # 简介：位于「AV女優名：」之前的叙述性文字（如「青森県出身。2011年にAVデビューした…」）
    head = text.split("AV女優名")[0].strip()
    if 15 <= len(head) <= 400 and "AV女優名" not in head:
        info["bio"] = head
    md = re.search(r"(\d{4})年\s*(\d{1,2})?\s*月?に?[^。]{0,40}?AVデビュー", text)
    if md:
        info["debut_date"] = f"{md.group(1)}-{int(md.group(2)):02d}" if md.group(2) else md.group(1)

    mn = re.search(r"AV女優名[：:]\s*([^（(\-]+)", text)
    if mn:
        info["names"].append(mn.group(1).strip())
    mr = re.search(r"-\s*([a-z][a-z\s\-']{2,40})", text)
    if mr:
        info["romaji"] = mr.group(1).strip()
    m2 = re.search(r"別名義[：:]\s*([^生]*?)生年月日", text)
    if m2:
        for part in re.split(r"[、,／/]", m2.group(1)):
            n = re.sub(r"（[^）]*）|\([^)]*\)", "", part).strip()
            # 过滤 "– – –" 之类占位符（需含至少一个文字/数字字符）
            if n and len(n) < 30 and re.search(r"[\w\u3040-\u30ff\u4e00-\u9fff]", n, re.U):
                info["names"].append(n)
    mb = re.search(r"生年月日[：:]\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", text)
    if mb:
        info["birth_date"] = f"{mb.group(1)}-{int(mb.group(2)):02d}-{int(mb.group(3)):02d}"
    msz = re.search(r"サイズ[：:]\s*(.*?)(?:SNS|Twitter|Instagram|$)", text)
    if msz:
        h, meas, cup = parse_size(msz.group(1))
        if h:
            info["height"] = h
        if meas:
            info["measurements"] = meas
        if cup:
            info["cup"] = cup
    return info


def search_actress_page(session, name, cache):
    """搜索 av-wiki，返回与 name 精确匹配的演员页 URL 与解析结果"""
    if name in cache:
        return cache[name]
    url = f"{BASE}/"
    result = (None, None)
    try:
        r = session.get(url, params={"s": name}, headers=UA, timeout=25)
        if r.status_code != 200:
            cache[name] = result
            return result
        cands = []
        for m in re.finditer(r'href="(https://av-wiki\.net/av-actress/[^"]+)"[^>]*>([^<]*)<', r.text):
            href, anchor = m.group(1), m.group(2).strip()
            if href not in [c[0] for c in cands]:
                cands.append((href, anchor))
        for href, anchor in cands[:4]:
            time.sleep(random.uniform(*REQUEST_SLEEP))
            try:
                pr = session.get(href, headers=UA, timeout=25)
            except Exception:
                continue
            if pr.status_code != 200:
                continue
            info = parse_profile_meta(pr.text)
            # URL slug 是官方罗马字（如 /av-actress/nito-sayaka/），比 meta 文本可靠
            slug = href.rstrip("/").rsplit("/", 1)[-1].replace("-", " ").strip()
            info["romaji"] = slug or info["romaji"]
            # 仅当 wiki 主名与本地名一致时才采信罗马字（别名/改名页的罗马字属于新名）
            info["primary_match"] = bool(info["names"]) and info["names"][0] == name
            names = set(info["names"]) | {anchor}
            if name in names:
                result = (href, info)
                break
    except Exception:
        pass
    cache[name] = result
    return result


def main():
    ap = argparse.ArgumentParser(description="从 av-wiki 补全演员档案")
    ap.add_argument("--db-path", default=DB_PATH)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--with-bio", action="store_true",
                    help="同时补全简介与出道年（来自 av-wiki 档案叙述）")
    ap.add_argument("--clear-bad-height", action="store_true",
                    help="把不合理的历史身高值（如 '4'）清空")
    args = ap.parse_args()

    conn = sqlite3.connect(args.db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, name, name_common, name_traditional, aliases, "
        "birth_date, height, measurements, name_en, debut_date, description FROM actors "
        "WHERE is_favorite=1 ORDER BY id"
    ).fetchall()
    if args.limit:
        rows = rows[:args.limit]

    session = requests.Session()
    cache = {}
    filled_birth = filled_h = filled_m = filled_en = 0
    hit_rows, miss_rows = [], []

    for row in rows:
        toks = actor_tokens(row)
        found = None
        for t in toks:
            href, info = search_actress_page(session, t, cache)
            if href and info and (info["birth_date"] or info["height"]):
                found = (href, info, t)
                break
        if not found:
            miss_rows.append((row["id"], row["name"]))
            print(f"[未收录] DB#{row['id']} {row['name']}")
            continue

        href, info, matched_tok = found
        sets, vals, changed = [], [], []
        if info["birth_date"] and not (row["birth_date"] or "").strip():
            sets.append("birth_date=?"); vals.append(info["birth_date"]); changed.append(f"生日={info['birth_date']}")
        if info["height"] and not (row["height"] or "").strip():
            sets.append("height=?"); vals.append(info["height"]); changed.append(f"身高={info['height']}")
        if info["measurements"] and not (row["measurements"] or "").strip():
            sets.append("measurements=?"); vals.append(info["measurements"]); changed.append(f"三围={info['measurements']}")
        if info["romaji"] and info.get("primary_match") and not (row["name_en"] or "").strip():
            raw = info["romaji"].strip()
            romaji = raw if " " in raw else raw.replace("-", " ")
            romaji = " ".join(w.capitalize() for w in romaji.split())
            sets.append("name_en=?"); vals.append(romaji); changed.append(f"name_en={romaji}")
        if args.with_bio:
            if info.get("debut_date") and not (row["debut_date"] or "").strip():
                sets.append("debut_date=?"); vals.append(info["debut_date"]); changed.append(f"出道={info['debut_date']}")
            if info.get("bio") and not (row["description"] or "").strip():
                sets.append("description=?"); vals.append(info["bio"]); changed.append("简介=已补")

        hit_rows.append((row["id"], row["name"], matched_tok, changed, href))
        print(f"[命中] DB#{row['id']} {row['name']} (匹配 '{matched_tok}') -> {'; '.join(changed) if changed else '无新增字段'}")

        if args.apply and changed:
            sets.append("updated_at=CURRENT_TIMESTAMP")
            conn.execute(f"UPDATE actors SET {', '.join(sets)} WHERE id=?", vals + [row["id"]])
            filled_birth += any(s.startswith("birth_date") for s in sets)
            filled_h += any(s.startswith("height") for s in sets)
            filled_m += any(s.startswith("measurements") for s in sets)
            filled_en += any(s.startswith("name_en") for s in sets)
        time.sleep(random.uniform(0.8, 1.6))

    if args.apply:
        conn.commit()

    # 清理历史遗留的不合理身高值
    if args.clear_bad_height and args.apply:
        bad = conn.execute(
            "SELECT id, name, height FROM actors WHERE is_favorite=1 AND height IS NOT NULL "
            "AND height<>'' AND CAST(height AS INTEGER) NOT BETWEEN 120 AND 210"
        ).fetchall()
        for b in bad:
            conn.execute("UPDATE actors SET height=NULL, updated_at=CURRENT_TIMESTAMP WHERE id=?", (b["id"],))
        conn.commit()
        print(f"[清理] 清除 {len(bad)} 个不合理身高值: "
              + ", ".join(f"{b['name']}({b['height']})" for b in bad[:10]))

    print("-" * 60)
    print(f"收藏演员 {len(rows)} 人 | av-wiki 命中 {len(hit_rows)} 人 | 未收录 {len(miss_rows)} 人")
    if args.apply:
        print(f"写入: 生日 {filled_birth} | 身高 {filled_h} | 三围 {filled_m} | name_en {filled_en}")
    else:
        print("(干跑模式，未写库；加 --apply 执行)")
    conn.close()


if __name__ == "__main__":
    main()
