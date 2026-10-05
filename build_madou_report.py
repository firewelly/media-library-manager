#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
麻豆系列：合并报告 + 回填数据库
==================================

输入:
  results/madou/series_index.json    枚举结果（番号/标题/封面/href）
  results/madou/series_details.json  详情（磁链=登录态抓取 / 标签 / 日期）
  results/madou/cover_ocr.json       封面 OCR（macOS Vision）
  results/madou/llm_meta.json        LLM 提取（actresses / studio / series / tags）

输出:
  results/madou/series_report.json / .csv   每部影片的完整 metadata
  results/madou/actress_index.txt           按演员归并的影片清单
  （--apply-db）回填 media_library.db：
     · 为识别出的演员建档（不存在则新建）
     · 把库内同番号影片与演员关联（video_actors）
     · 补 javdb_info 的番号/标题（如缺失）

用法:
    python3 build_madou_report.py                 # 只出报告
    python3 build_madou_report.py --apply-db      # 同时回填数据库
"""

import os
import re
import sys
import json
import csv
import sqlite3
import argparse
import collections
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE_DIR, "results", "madou")
DB_PATH = os.path.join(BASE_DIR, "media_library.db")

STUDIO_WHITELIST = ("麻豆", "大象", "蜜桃", "性视界", "兔子先生", "爱神", "天美", "星空", "皇家", "精东", "果冻", "91", "MD", "PS", "TWAV")


def load(p, d=None):
    if os.path.exists(p):
        try:
            return json.load(open(p, encoding="utf-8"))
        except Exception:
            pass
    return d if d is not None else {}


def norm_code(c):
    c = re.sub(r"[-_\s]", "", str(c or "").upper())
    m = re.match(r"^([A-Z]+)0*(\d+)$", c)
    return f"{m.group(1)}-{m.group(2)}" if m else c


def build():
    idx = load(os.path.join(OUT_DIR, "series_index.json"))
    det = load(os.path.join(OUT_DIR, "series_details.json"))
    ocr = load(os.path.join(OUT_DIR, "cover_ocr.json"))
    meta = load(os.path.join(OUT_DIR, "llm_meta.json"))

    rows = []
    for code, it in idx.items():
        d = det.get(code) or {}
        m = meta.get(code) or {}
        mags = d.get("magnets") or []
        dns = [x.get("dn", "") for x in mags]
        actresses = [a for a in (m.get("actresses") or []) if a]
        rows.append({
            "code": code,
            "title": it.get("title", ""),
            "date": d.get("date", ""),
            "actresses": actresses,
            "studio": m.get("studio", ""),
            "series": m.get("series", ""),
            "tags": m.get("tags") or [],
            "javdb_actors": d.get("javdb_actors") or [],
            "n_magnets": len(mags),
            "sizes_gb": sorted({round((x.get("size_mb") or 0) / 1024, 2) for x in mags if x.get("size_mb")}),
            "all_dn": " | ".join(dns)[:400],
            "ocr": " ".join(ocr.get(code) or [])[:300],
            "cover": it.get("cover", ""),
            "page": it.get("page", ""),
        })
    rows.sort(key=lambda r: r["code"])

    json.dump(rows, open(os.path.join(OUT_DIR, "series_report.json"), "w"), ensure_ascii=False, indent=1)
    cols = ["code", "title", "date", "actresses", "studio", "series", "tags", "javdb_actors",
            "n_magnets", "sizes_gb", "all_dn", "ocr", "cover", "page"]
    with open(os.path.join(OUT_DIR, "series_report.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({**r, "actresses": "|".join(r["actresses"]), "tags": "|".join(r["tags"]),
                        "javdb_actors": "|".join(r["javdb_actors"]),
                        "sizes_gb": "|".join(str(x) for x in r["sizes_gb"])})

    # 按演员归并
    by_act = collections.defaultdict(list)
    for r in rows:
        for a in r["actresses"]:
            by_act[a].append(r)
    with open(os.path.join(OUT_DIR, "actress_index.txt"), "w", encoding="utf-8") as f:
        for a, items in sorted(by_act.items(), key=lambda kv: -len(kv[1])):
            f.write(f"# {a}（{len(items)} 部）\n")
            for r in items:
                f.write(f"   {r['code']:<12} {r['title'][:56]}\n")
            f.write("\n")

    with_act = sum(1 for r in rows if r["actresses"])
    print(f"报告完成: {len(rows)} 部 | 有演员 {with_act} | 有厂牌 {sum(1 for r in rows if r['studio'])} "
          f"| 有系列 {sum(1 for r in rows if r['series'])} | 演员去重 {len(by_act)} 人")
    print(f"  {os.path.join(OUT_DIR, 'series_report.csv')}")
    print(f"  {os.path.join(OUT_DIR, 'actress_index.txt')}")
    print("  TOP 演员:")
    for a, items in sorted(by_act.items(), key=lambda kv: -len(kv[1]))[:15]:
        print(f"     {a:<10} {len(items):>3} 部")
    return rows, by_act


def apply_db(rows):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    created, linked, skipped = 0, 0, 0
    for r in rows:
        actresses = r["actresses"]
        if not actresses:
            continue
        code = r["code"]
        # 找到库内同番号影片（文件名或 javdb_code 匹配）
        pat = f"%{code}%"
        vids = [x["id"] for x in cur.execute(
            """SELECT DISTINCT v.id FROM videos v
               LEFT JOIN javdb_info ji ON ji.video_id = v.id
               WHERE UPPER(REPLACE(v.file_name,'-','')) LIKE UPPER(REPLACE(?,'-',''))
                  OR UPPER(REPLACE(ji.javdb_code,'-','')) LIKE UPPER(REPLACE(?,'-',''))""",
            (pat, pat)).fetchall()]
        if not vids:
            skipped += 1
            continue
        for a in actresses:
            row = cur.execute("SELECT id FROM actors WHERE name=? OR name_common=? OR name_traditional=?",
                              (a, a, a)).fetchone()
            if row:
                aid = row["id"]
            else:
                cur.execute("""INSERT INTO actors (name, name_common, name_traditional, aliases, created_at, updated_at)
                               VALUES (?,?,?,?,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)""", (a, a, a, ""))
                aid = cur.lastrowid
                created += 1
            for vid in vids:
                cur.execute("INSERT OR IGNORE INTO video_actors (video_id, actor_id) VALUES (?,?)", (vid, aid))
                linked += cur.rowcount
    conn.commit()
    print(f"\n数据库回填: 新建演员 {created} 人 | 新增关联 {linked} 条 | 库内无对应影片的作品 {skipped} 部")
    conn.close()
    return 0


def main():
    ap = argparse.ArgumentParser(description="麻豆系列报告与数据库回填")
    ap.add_argument("--apply-db", action="store_true")
    args = ap.parse_args()
    rows, by_act = build()
    if args.apply_db:
        apply_db(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
