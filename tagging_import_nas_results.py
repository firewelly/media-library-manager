#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
导入 NAS(dxp4800) 上打标签 runner 产出的 results.csv 到本地 media_library.db

对齐 Tk 版 media_library.py「批量更新无标签文件」(no_tags_update) 的入库语义:
  - status=ok     : tags = ', '.join(sorted(JAVDB标签 ∪ 生成标签))
                    JAVDB标签为权威来源, 从 javdb_info/javdb_info_tags/javdb_tags 关联读取
  - status=no_tag : tags = '<无标签>' (三遍采样全部未打出标签)
  - 其他状态(not_found/no_frames/fail/integrity_fail): 不改动该行, 仅统计
  - 不写 description (Tk 版自动打标流程不覆盖描述)
  - 生成标签同步 INSERT OR IGNORE 到 tags 表 (与 production 分析器一致)

用法:
  python3 tagging_import_nas_results.py --dry-run results.csv   # 预览
  python3 tagging_import_nas_results.py results.csv             # 实际写入
"""
import argparse
import csv
import os
import sqlite3
import sys
from collections import Counter

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'media_library.db')


def get_javdb_tags(cur, video_id):
    cur.execute("""
        SELECT jt.tag_name
        FROM javdb_info j
        JOIN javdb_info_tags jit ON j.id = jit.javdb_info_id
        JOIN javdb_tags jt ON jit.tag_id = jt.id
        WHERE j.video_id = ?
    """, (video_id,))
    tags = set()
    for (name,) in cur.fetchall():
        name = (name or '').strip()
        if name:
            tags.add(name)
    return tags


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('results_csv')
    ap.add_argument('--db', default=DB_PATH)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    cur = conn.cursor()

    stats = Counter()
    samples = []
    with open(args.results_csv, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))

    for row in rows:
        vid_raw = (row.get('id') or '').strip()
        status = (row.get('status') or '').strip()
        if not vid_raw.isdigit():
            stats['bad_row'] += 1
            continue
        vid = int(vid_raw)
        stats[status or 'unknown'] += 1

        if status == 'ok':
            generated = [t.strip() for t in (row.get('tags') or '').split('|') if t.strip()]
            if not generated:
                stats['ok_empty_tags'] += 1
                continue
            javdb_set = get_javdb_tags(cur, vid)
            final = ', '.join(sorted(javdb_set.union(set(generated))))
            if not args.dry_run:
                cur.execute("UPDATE videos SET tags = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                            (final, vid))
                for t in generated:
                    cur.execute("INSERT OR IGNORE INTO tags (tag_name) VALUES (?)", (t,))
            if len(samples) < 5:
                samples.append((vid, 'ok', final))
        elif status == 'no_tag':
            if not args.dry_run:
                cur.execute("UPDATE videos SET tags = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                            ('<无标签>', vid))
            if len(samples) < 5:
                samples.append((vid, 'no_tag', '<无标签>'))
        # not_found / no_frames / fail / integrity_fail: 不动数据库

    if not args.dry_run:
        conn.commit()

    total_ok = stats['ok'] - stats.get('ok_empty_tags', 0)
    print(f"{'[预览] ' if args.dry_run else ''}导入统计:")
    for k in ('ok', 'ok_empty_tags', 'no_tag', 'not_found', 'no_frames',
              'fail', 'integrity_fail', 'bad_row', 'unknown'):
        if stats.get(k):
            print(f"  {k}: {stats[k]}")
    print(f"  => 实际写入标签 {total_ok} 条, 标记<无标签> {stats['no_tag']} 条")

    for vid, st, tags in samples:
        print(f"  样例 id={vid} [{st}]: {tags[:80]}")

    cur.execute("SELECT COUNT(*) FROM videos WHERE (tags IS NULL OR tags = '')")
    print(f"剩余完全无标签记录: {cur.fetchone()[0]}")
    conn.close()


if __name__ == '__main__':
    main()
