#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查 media_library.db 中可能的重复视频记录：
- 基于完全相同的 `file_path`
- 基于相同的文件名（basename）但 `file_path` 不同
- 标记同一组里 `source_folder` 存在与缺失的情况

使用示例：
python3 check_duplicate_file_records.py --db media_library.db --limit 20
"""

import os
import sys
import sqlite3
import argparse
from collections import defaultdict


def load_videos(conn):
    cur = conn.cursor()
    cur.execute("SELECT id, file_path, title, IFNULL(source_folder, '') FROM videos")
    rows = cur.fetchall()
    videos = []
    for rid, file_path, title, source_folder in rows:
        file_path = file_path or ''
        title = title or ''
        source_folder = source_folder or ''
        videos.append({
            'id': rid,
            'file_path': file_path,
            'basename': os.path.basename(file_path) if file_path else '',
            'title': title,
            'source_folder': source_folder,
        })
    return videos


def group_by_file_path(videos):
    groups = defaultdict(list)
    for v in videos:
        groups[v['file_path']].append(v)
    # 仅保留重复（数量>1）的组
    return {k: vs for k, vs in groups.items() if len(vs) > 1}


def group_by_basename(videos):
    groups = defaultdict(list)
    for v in videos:
        groups[v['basename']].append(v)
    # 仅保留重复（数量>1）的组
    dup = {k: vs for k, vs in groups.items() if len(vs) > 1 and k}
    # 过滤掉 file_path 完全相同的纯重复，保留不同路径但同名的情况
    filtered = {}
    for k, vs in dup.items():
        unique_paths = {v['file_path'] for v in vs}
        if len(unique_paths) > 1:
            filtered[k] = vs
    return filtered


def has_mixed_source_folder(vs):
    # 同一组里，有的有 source_folder（非空），有的为空
    has_sf = any(v['source_folder'] for v in vs)
    no_sf = any(not v['source_folder'] for v in vs)
    return has_sf and no_sf


def print_groups(title, groups, limit=20):
    print(f"\n=== {title} 重复组（显示前 {limit} 组）===")
    print(f"组总数: {len(groups)}")
    shown = 0
    for key, vs in sorted(groups.items(), key=lambda kv: len(kv[1]), reverse=True):
        if shown >= limit:
            break
        mixed = has_mixed_source_folder(vs)
        print(f"\n[{shown+1}] 键: {key!r} | 记录数: {len(vs)} | source_folder 混合: {mixed}")
        for v in vs:
            print(f"  - id={v['id']} | file_path={v['file_path']} | basename={v['basename']} | title={v['title'][:60]} | source_folder={v['source_folder']}")
        shown += 1


def main():
    parser = argparse.ArgumentParser(description='检查 media_library.db 中可能的重复视频记录')
    parser.add_argument('--db', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'media_library.db'), help='数据库文件路径')
    parser.add_argument('--limit', type=int, default=20, help='每类重复组最多显示的数量')
    args = parser.parse_args()

    db_path = args.db
    if not os.path.exists(db_path):
        print(f"数据库不存在: {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    try:
        videos = load_videos(conn)
        # 基于 file_path 的重复
        dup_by_path = group_by_file_path(videos)
        # 基于 basename 的重复（路径不同但文件名相同）
        dup_by_base = group_by_basename(videos)

        print(f"总记录数: {len(videos)}")
        print(f"file_path 重复组数量: {len(dup_by_path)}")
        print(f"basename 重复组数量(路径不同): {len(dup_by_base)}")

        print_groups('file_path', dup_by_path, limit=args.limit)
        print_groups('basename(路径不同)', dup_by_base, limit=args.limit)

        # 额外：统计存在 source_folder 混合的重复组数量
        mixed_path_groups = sum(1 for vs in dup_by_path.values() if has_mixed_source_folder(vs))
        mixed_base_groups = sum(1 for vs in dup_by_base.values() if has_mixed_source_folder(vs))
        print(f"\n包含 source_folder 混合的重复组统计:")
        print(f"- file_path 组: {mixed_path_groups} / {len(dup_by_path)}")
        print(f"- basename 组: {mixed_base_groups} / {len(dup_by_base)}")

    finally:
        conn.close()


if __name__ == '__main__':
    main()