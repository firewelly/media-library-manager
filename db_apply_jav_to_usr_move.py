#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 JAV->usr 搬移反映到 media_library.db：按路径前缀精确更新，不做 MD5 猜测。

- file_path:      /…/Video/JAV/<目录>/…  ->  /…/Video/usr/<目录>/…
- source_folder:  '/…/Video/JAV'（库标记）-> '/…/Video/usr'
                  或位于被搬目录内 -> 同步换前缀；其它取值不动
同时覆盖 /Volumes/Video（Mac 挂载）与 /volume1/Video（NAS 内部）两种写法。

用法：python3 db_apply_jav_to_usr_move.py --folders /tmp/folders.txt [--dry-run|--apply]
"""
import argparse
import os
import shutil
import sqlite3
import sys
import time
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, 'media_library.db')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--folders', default='/tmp/folders.txt')
    ap.add_argument('--db', default=DB)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--from-usr', action='store_true', help='合并 usr 内部的异体目录')
    args = ap.parse_args()
    if not (args.dry_run or args.apply):
        print("请指定 --dry-run 或 --apply")
        return 1

    # 每行：源目录名  或  源目录名<TAB>目标目录名（异体名并入规范目录时用）
    pairs = []
    for l in open(args.folders, encoding='utf-8'):
        l = l.rstrip('\n')
        if not l.strip():
            continue
        parts = l.split('\t')
        pairs.append((parts[0], parts[1] if len(parts) > 1 and parts[1] else parts[0]))
    src_base = 'usr' if args.from_usr else 'JAV'
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    stats = {'path': 0, 'marker': 0, 'sf_deep': 0, 'unchanged_sf': 0}
    path_updates = []   # (new_path, id)
    sf_updates = []     # (new_sf, id)

    for f, dst in pairs:
        # 库里 Mac 路径是 NFD、NAS 内部是 NFC，两种形式都要匹配，且按原形式写回
        variants = {f, unicodedata.normalize('NFC', f), unicodedata.normalize('NFD', f)}
        dst_variants = {dst, unicodedata.normalize('NFC', dst), unicodedata.normalize('NFD', dst)}
        for root in ('/Volumes/Video', '/volume1/Video'):
            for v in variants:
                old_pfx = f"{root}/{src_base}/{v}"
                # 目标名按同一规范化形式对应
                if unicodedata.normalize('NFD', v) == v and dst != f:
                    dv = unicodedata.normalize('NFD', dst)
                elif unicodedata.normalize('NFC', v) == v and dst != f:
                    dv = unicodedata.normalize('NFC', dst)
                else:
                    dv = dst
                new_pfx = f"{root}/usr/{dv}"
                for r in cur.execute(
                    "SELECT id,file_path,source_folder FROM videos WHERE file_path = ? OR file_path LIKE ?",
                    (old_pfx, old_pfx + '/%')):
                    new_path = new_pfx + r['file_path'][len(old_pfx):]
                    path_updates.append((new_path, r['id']))
                    sf = r['source_folder'] or ''
                    if sf == f"{root}/{src_base}":
                        sf_updates.append((f"{root}/usr", r['id']))
                        stats['marker'] += 1
                    elif sf == old_pfx or sf.startswith(old_pfx + '/'):
                        sf_updates.append((new_pfx + sf[len(old_pfx):], r['id']))
                        stats['sf_deep'] += 1
                    else:
                        stats['unchanged_sf'] += 1
    stats['path'] = len(path_updates)

    print(f"待更新 file_path: {len(path_updates)} 条")
    print(f"待更新 source_folder: {len(sf_updates)} 条"
          f"（库标记 {stats['marker']}，目录内深层路径 {stats['sf_deep']}）")
    print(f"source_folder 保持原值: {stats['unchanged_sf']} 条")
    for np, vid in path_updates[:3]:
        print(f"   例: id={vid} -> {np[:110]}")

    if args.dry_run:
        print("\n[dry-run] 未写入")
        return 0

    backup_dir = os.path.join(HERE, 'db_backups')
    os.makedirs(backup_dir, exist_ok=True)
    bp = os.path.join(backup_dir, f"media_library_before_jav2usr_{time.strftime('%Y%m%d_%H%M%S')}.db")
    shutil.copy2(args.db, bp)
    print(f"\n已备份 -> {bp}")

    cur.executemany("UPDATE videos SET file_path = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", path_updates)
    cur.executemany("UPDATE videos SET source_folder = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", sf_updates)
    conn.commit()
    print(f"已更新：file_path {len(path_updates)} 条，source_folder {len(sf_updates)} 条")
    return 0


if __name__ == '__main__':
    sys.exit(main())
