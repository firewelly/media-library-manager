#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 precompute_md5.py 产出的 MD5 索引应用到 media_library.db，或导出成
video_md5.csv 供 NAS 侧导入使用。

匹配方式：以 (文件名, 文件大小) 为键。文件搬到 dxp4800、路径前缀变化后，
文件名与大小不变，因此该键用于回填数据库里指向新路径的记录。

用法：
  python3 apply_md5_index.py --dry-run                       # 预览（默认读 black_jav_md5_index.json）
  python3 apply_md5_index.py                                 # 写入（写前自动备份 db 到 db_backups/）
  python3 apply_md5_index.py --overwrite                     # 连同旧值不同的记录一起覆盖（谨慎）
  python3 apply_md5_index.py --index xxx_index.json --dry-run
  python3 apply_md5_index.py --emit-csv video_md5.csv --remote-prefix /volume1/JAV --local-prefix /Volumes/JAV

默认只补空的 md5_hash；已有值且与新算值不同的记录只列出、不改动，需人工确认后加 --overwrite。
"""
import argparse
import csv
import json
import os
import shutil
import sqlite3
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB = os.path.join(HERE, 'media_library.db')
DEFAULT_INDEX = os.path.join(HERE, 'black_jav_md5_index.json')


def load_entries(path):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    entries = data.get('entries', {})
    return data.get('root', ''), entries


def emit_csv(entries, out_path, remote_prefix, local_prefix, root):
    """导出 4 列 CSV：文件名,文件路径,大小(字节),MD5值。

    文件路径用 remote_prefix 拼接相对路径（NAS 内部路径，如 /volume1/JAV/...），
    便于 smart_video_updater.py 的 MD5CSVIndex 索引。
    """
    rows = []
    for rel, info in sorted(entries.items()):
        if not info.get('md5'):
            continue
        rel_clean = rel.replace(os.sep, '/')
        remote_path = remote_prefix.rstrip('/') + '/' + rel_clean
        rows.append([info['name'], remote_path, info['size'], info['md5']])
    with open(out_path, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['文件名', '文件路径', '大小(字节)', 'MD5值'])
        w.writerows(rows)
    print(f"已导出 {len(rows)} 行 -> {out_path}")
    print(f"路径前缀：{remote_prefix}  （对应本地挂载 {local_prefix or '<未指定>'}）")


def apply_to_db(db_path, entries, dry_run, overwrite):
    by_key = defaultdict(list)
    for rel, info in entries.items():
        if info.get('md5'):
            by_key[(info['name'], info['size'])].append((rel, info['md5']))

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    stats = defaultdict(int)
    updates = []          # (md5, id)
    conflicts = []        # 已有 MD5 且与计算值不同的记录，默认不动
    multi_hit = []
    for key, cand in by_key.items():
        name, size = key
        cur.execute("SELECT id, file_path, md5_hash, file_size FROM videos WHERE file_name = ? AND file_size = ?",
                    (name, size))
        rows = cur.fetchall()
        if not rows:
            stats['no_db_row'] += 1
            continue
        if len(cand) > 1:
            multi_hit.append((name, size, [c[0] for c in cand]))
        md5 = cand[0][1]
        for r in rows:
            stats['db_rows'] += 1
            old = r['md5_hash'] or ''
            if old == md5:
                stats['already_ok'] += 1
                continue
            if not old:
                stats['fill'] += 1
                updates.append((md5, r['id']))
            else:
                conflicts.append((r['id'], r['file_path'], old, md5))
                if overwrite:
                    stats['overwrite'] += 1
                    updates.append((md5, r['id']))

    print(f"索引条目 {len(entries)} 个（有效 {sum(1 for i in entries.values() if i.get('md5'))}）")
    print(f"命中数据库记录 {stats['db_rows']} 条：已是正确 MD5 {stats['already_ok']} 条，"
          f"补空 {stats['fill']} 条，需覆盖旧值 {len(conflicts)} 条"
          f"{'（已按 --overwrite 覆盖）' if overwrite else '（未覆盖）'}")
    print(f"数据库中无对应记录（文件名+大小不匹配）{stats['no_db_row']} 个条目")
    if multi_hit:
        print(f"注意：{len(multi_hit)} 组索引键重复（同名同大小），已取第一条："
              f"{multi_hit[0][0]} 等")
    if conflicts:
        print("\n旧值与新算值不同、需人工确认的记录（同名同大小但字节不同）：")
        for vid, path, old, new in conflicts:
            exists = os.path.exists(path)
            print(f"  id={vid} 旧={old} 新={new}")
            print(f"    库中路径: {path}  [{'存在' if exists else '不可达'}]")

    if dry_run:
        print("\n[dry-run] 未写入数据库")
        return

    if not updates:
        print("\n无需更新")
        return

    backup_dir = os.path.join(HERE, 'db_backups')
    os.makedirs(backup_dir, exist_ok=True)
    stamp = time.strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(backup_dir, f"media_library_before_md5apply_{stamp}.db")
    shutil.copy2(db_path, backup_path)
    print(f"\n已备份数据库 -> {backup_path}")

    cur.executemany("UPDATE videos SET md5_hash = ? WHERE id = ?", updates)
    conn.commit()
    print(f"已更新 {len(updates)} 条记录")
    conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--index', default=DEFAULT_INDEX)
    ap.add_argument('--db', default=DEFAULT_DB)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--overwrite', action='store_true',
                    help='覆盖已有的不同 MD5（默认只补空值，旧值不同的记录仅列出待确认）')
    ap.add_argument('--emit-csv')
    ap.add_argument('--remote-prefix', default='/volume1/JAV')
    ap.add_argument('--local-prefix', default='')
    args = ap.parse_args()

    if not os.path.exists(args.index):
        print(f"索引不存在: {args.index}")
        return 1
    root, entries = load_entries(args.index)
    print(f"索引：{args.index}（扫描根 {root}，{len(entries)} 条）")

    if args.emit_csv:
        emit_csv(entries, args.emit_csv, args.remote_prefix, args.local_prefix, root)
        return 0

    apply_to_db(args.db, entries, args.dry_run, args.overwrite)
    return 0


if __name__ == '__main__':
    sys.exit(main())
