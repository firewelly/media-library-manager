#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 BLACK(U盘) 搬进 DXP4800 的视频登记进 tk 版 media_library.db，直接使用预算好的 MD5。

数据来源：
  black_jav_migration_plan.json  本次分发计划（源/目标/MD5/大小）
  black_jav_md5_index.json       预算索引（含源文件 mtime，用于 file_created_time）
  usb_copy_ok.tsv                 NAS 侧校验通过的账本（只登记真正校验过的文件）
  probe_result.tsv                NAS 侧 ffprobe 结果（时长/分辨率）

规则：
  - 目标路径已有记录 -> 跳过
  - 原 /Volumes/BLACK/JAV/... 记录 -> 更新为新路径（保留 tags/actors/stars 等既有元数据）
  - 其余 -> 新增记录，字段语义对齐 tk 版导入：
      title = 文件名去扩展名并去掉 '!'；stars 由 '!' 个数映射（无 '!' 为 0）
      is_nas_online=1；source_folder 用库标记 /Volumes/Video/{usr,JAV}
      file_created_time 取源文件 mtime（datetime 字符串，与库内主流格式一致）

用法：python3 db_import_usb_videos.py --ok-ledger usb_copy_ok.tsv --probe probe_result.tsv [--dry-run|--apply]
"""
import argparse
import json
import os
import shutil
import sqlite3
import sys
import time
import unicodedata
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, 'media_library.db')
PLAN = os.path.join(HERE, 'black_jav_migration_plan.json')
INDEX = os.path.join(HERE, 'black_jav_md5_index.json')


def nfd(s):
    """Mac 侧（SMB）看到的是 NFD 形式，库里 Mac 路径统一按 NFD 写。"""
    return unicodedata.normalize('NFD', s)


def parse_title_and_stars(file_name):
    base = os.path.splitext(file_name)[0]
    n = base.count('!')
    stars = min(5, max(2, n + 1)) if n > 0 else 0
    return base.replace('!', '').strip(), stars


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', default=DB)
    ap.add_argument('--plan', default=PLAN)
    ap.add_argument('--index', default=INDEX)
    ap.add_argument('--ok-ledger', required=True, help='NAS 侧 usb_copy_ok.tsv')
    ap.add_argument('--probe', default='', help='probe_result.tsv（时长/分辨率）')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    if not (args.dry_run or args.apply):
        print("请指定 --dry-run 或 --apply")
        return 1

    plan = {p['target_path']: p for p in json.load(open(args.plan, encoding='utf-8'))['plan']}
    idx = json.load(open(args.index, encoding='utf-8'))['entries']
    mtime_by_key = {(v['name'], v['size']): v['mtime'] for v in idx.values()}

    probe = {}
    if args.probe and os.path.exists(args.probe):
        for line in open(args.probe, encoding='utf-8'):
            p = line.rstrip('\n').split('\t')
            if len(p) >= 3:
                probe[p[0]] = (p[1], p[2])

    verified = {}
    for line in open(args.ok_ledger, encoding='utf-8'):
        p = line.rstrip('\n').split('\t')
        if len(p) >= 4:
            verified[p[1]] = (p[0], int(p[2]), p[3])   # target -> (src, size, md5)

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    updates = []   # (new_path, source_folder, id)
    inserts = []   # tuple
    md5_fixes = []  # (md5, id) 目标已有记录但 MD5 与实测不符（历史错值）
    stats = {'skip_exists': 0, 'update': 0, 'insert': 0, 'not_in_ledger': 0, 'fix_md5': 0, 'left_as_is': 0}

    # 按 NFD 规范化建索引，避免 NFC/NFD 差异导致匹配不上；同一路径可能有多条记录
    by_nfd = {}
    for r in cur.execute("SELECT id, file_path, md5_hash FROM videos WHERE file_path LIKE '/Volumes/%'"):
        by_nfd.setdefault(nfd(r['file_path']), []).append((r['id'], r['md5_hash'] or ''))

    for target, (src, size, md5) in verified.items():
        p = plan.get(target)
        if not p:
            stats['not_in_ledger'] += 1
            continue
        mac_path = nfd(p['mac_path'])
        source_folder = '/Volumes/Video/' + p['parent']
        old_path = nfd(p['src'].replace('/mnt/@usb/sde2/JAV/', '/Volumes/BLACK/JAV/'))
        old_ids = [vid for vid, _ in by_nfd.get(old_path, [])]

        # 目标已有记录
        rows = by_nfd.get(mac_path)
        if rows:
            wrong = [(vid, m) for vid, m in rows if m != md5]
            if wrong:
                # 库里值跟实测不符：按账本里的 MD5 修正
                for vid, _ in wrong:
                    md5_fixes.append((md5, vid))
                stats['fix_md5'] += 1
            else:
                stats['skip_exists'] += 1
            # 目标路径已被占用（file_path 有唯一约束），BLACK 记录保持原样不动
            if old_ids:
                stats['left_as_is'] += 1
            continue

        # 原 BLACK 记录 -> 更新路径
        if old_ids:
            updates.append((mac_path, source_folder, old_ids[0]))
            stats['update'] += 1
            continue

        # 新增
        title, stars = parse_title_and_stars(p['src'].rsplit('/', 1)[-1])
        dur, res = probe.get(target, (None, None))
        mt = mtime_by_key.get((p['src'].rsplit('/', 1)[-1], size))
        fct = datetime.fromtimestamp(mt).strftime('%Y-%m-%d %H:%M:%S') if mt else None
        inserts.append((mac_path, p['src'].rsplit('/', 1)[-1], title, stars, size,
                        source_folder, md5, dur, res, fct))
        stats['insert'] += 1

    # 唯一约束防线：目标路径已被占用（或本次有重复目标）的更新改为保留原记录
    seen = set()
    safe_updates = []
    for mp, sf, vid in updates:
        if mp in by_nfd or mp in seen:
            stats['left_as_is'] += 1
            continue
        seen.add(mp)
        safe_updates.append((mp, sf, vid))
    updates = safe_updates

    print(f"校验账本 {len(verified)} 条（计划 {len(plan)} 条）")
    print(f"  跳过（目标已有记录且 MD5 正确）: {stats['skip_exists']}")
    print(f"  修正错误 MD5（目标已有记录但库里值不对）: {stats['fix_md5']} -> {len(md5_fixes)} 条记录")
    print(f"  更新（原 BLACK 记录迁移）: {stats['update']}")
    print(f"  保留原样（目标路径已被占用）: {stats['left_as_is']}")
    print(f"  新增: {stats['insert']}")
    if stats['not_in_ledger']:
        print(f"  账本中不在计划里的: {stats['not_in_ledger']}")
    for u in updates[:2]:
        print(f"   更新例: id={u[2]} -> {u[0][:100]}")
    for i in inserts[:2]:
        print(f"   新增例: {i[1]}  {i[6][:12]}…  {i[8] or '-'}  {i[9] or '-'}")

    if args.dry_run:
        print("\n[dry-run] 未写入")
        return 0
    if not (updates or inserts):
        print("\n无改动")
        return 0

    backup_dir = os.path.join(HERE, 'db_backups')
    os.makedirs(backup_dir, exist_ok=True)
    bp = os.path.join(backup_dir, f"media_library_before_blackimport_{time.strftime('%Y%m%d_%H%M%S')}.db")
    shutil.copy2(args.db, bp)
    print(f"\n已备份 -> {bp}")

    cur.executemany(
        "UPDATE videos SET file_path = ?, source_folder = ?, is_nas_online = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        updates)
    cur.executemany(
        "UPDATE videos SET md5_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        md5_fixes)
    cur.executemany(
        """INSERT INTO videos (file_path, file_name, title, stars, file_size, source_folder, md5_hash,
                               duration, resolution, file_created_time, is_nas_online, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
        inserts)
    conn.commit()
    print(f"已写入：更新路径 {len(updates)} 条，修正 MD5 {len(md5_fixes)} 条，新增 {len(inserts)} 条")
    return 0


if __name__ == '__main__':
    sys.exit(main())
