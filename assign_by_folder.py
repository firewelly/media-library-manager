#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
按「文件夹归属」为无关联影片补演员（用户规则）
================================================

规则（用户指定）: 对**无法从 JavDB 等外部来源确认**的影片，
若其文件位于按演员命名的目录下（如 …/usr/<演员>/…），则按该目录的演员归属。

处理范围: 当前**没有任何演员关联**的影片。跳过非演员目录
（#未知女优 / misc / 经典合集 / AIAV 等）与无法对应到库内演员的目录名。

用法:
    python3 assign_by_folder.py            # 干跑：列出将归属的条目
    python3 assign_by_folder.py --apply    # 写库（并输出日志）
"""

import os
import re
import sys
import json
import sqlite3
import argparse
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "media_library.db")
LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "results", "magnets", "folder_based_assignments.json")
SKIP_FOLDERS = {"#未知女优", "misc", "经典合集", "AIAV", "av", "JAV", "usr", "DVD", "other", "others"}


def nz(s):
    """名称归一：去括号/空格/点号"""
    s = re.sub(r"[\(（].*?[\)）]", "", str(s or "")).strip()
    return re.sub(r"[\s·・]", "", s).lower()


def build_index(cur):
    alias2ids, id2name = {}, {}
    for r in cur.execute("SELECT id,name,name_common,name_traditional,aliases FROM actors"):
        id2name[r["id"]] = r["name"]
        for f in ("name", "name_common", "name_traditional"):
            n = nz(r[f])
            if n:
                alias2ids.setdefault(n, set()).add(r["id"])
        for a in (r["aliases"] or "").split(","):
            n = nz(a)
            if n:
                alias2ids.setdefault(n, set()).add(r["id"])
    return alias2ids, id2name


def folder_actress(path, alias2ids, id2name):
    """从路径中找出演员名（优先 usr/JAV 之后那一段）；返回 (actor_id, name) 或 (None, 目录名)"""
    parts = [p for p in (path or "").split("/") if p]
    cands = []
    for i, p in enumerate(parts[:-1]):
        base = re.sub(r"[\(（].*?[\)）]", "", p).strip()
        if base in SKIP_FOLDERS or base.lower() in SKIP_FOLDERS:
            continue
        for tok in [base] + [x.strip() for x in re.split(r"[,，]", base)]:
            if tok in SKIP_FOLDERS:
                continue
            ids = alias2ids.get(nz(tok))
            if ids and len(ids) == 1:
                cands.append((next(iter(ids)), tok))
    if not cands:
        # 返回最后一个目录名便于报告跳过原因
        return None, (parts[-2] if len(parts) >= 2 else "")
    aid, tok = cands[-1]          # 取最靠近文件的那一层演员目录
    return aid, id2name.get(aid, tok)


def main():
    ap = argparse.ArgumentParser(description="按文件夹归属补演员")
    ap.add_argument("--db-path", default=DB_PATH)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    conn = sqlite3.connect(args.db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    alias2ids, id2name = build_index(cur)

    rows = cur.execute("""
        SELECT v.id, v.file_name, v.file_path
        FROM videos v
        WHERE NOT EXISTS (SELECT 1 FROM video_actors va WHERE va.video_id = v.id)
          AND (v.file_path LIKE '%/usr/%' OR v.file_path LIKE '%/JAV/%')
    """).fetchall()
    if args.limit:
        rows = rows[:args.limit]
    print(f"待判定（无演员关联且位于演员目录结构下）: {len(rows)} 条")

    assign, skipped = [], []
    for r in rows:
        aid, name = folder_actress(r["file_path"], alias2ids, id2name)
        if aid:
            assign.append({"vid": r["id"], "file": r["file_name"], "path": r["file_path"],
                           "actor_id": aid, "actor": name})
        else:
            skipped.append({"vid": r["id"], "file": r["file_name"], "folder": name})

    print(f"\n可归属 {len(assign)} 条 | 跳过 {len(skipped)} 条（非演员目录/目录名无法对应）")
    by = {}
    for a in assign:
        by.setdefault(a["actor"], []).append(a)
    print("\n按演员汇总:")
    for name, items in sorted(by.items(), key=lambda kv: -len(kv[1])):
        print(f"   {name:<12} {len(items):>3} 条   例: {items[0]['file'][:40]}")

    sk = {}
    for s in skipped:
        sk.setdefault(s["folder"] or "(空)", []).append(s)
    print("\n跳过（按目录）:")
    for folder, items in sorted(sk.items(), key=lambda kv: -len(kv[1]))[:10]:
        print(f"   {folder[:20]:<22} {len(items)} 条")

    if args.apply and assign:
        for a in assign:
            cur.execute("INSERT OR IGNORE INTO video_actors (video_id, actor_id) VALUES (?,?)",
                        (a["vid"], a["actor_id"]))
        conn.commit()
        json.dump({"assigned_at": datetime.now().isoformat(), "count": len(assign),
                   "items": assign, "skipped": skipped},
                  open(LOG_PATH, "w"), ensure_ascii=False, indent=1)
        print(f"\n✅ 已按文件夹归属写入 {len(assign)} 条；日志: {LOG_PATH}")
    elif not args.apply:
        print("\n(干跑，未写库；加 --apply 执行)")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
