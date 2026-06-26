#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
针对所有在线且没有标签的视频，使用30B模型自动打标签
用法:
  # 预览模式（只看不改，默认）
  python3 retag_scored_videos.py

  # 实际执行打标签
  python3 retag_scored_videos.py --execute

  # 限制处理数量（调试用）
  python3 retag_scored_videos.py --execute --limit 10

  # 只处理指定文件夹下的
  python3 retag_scored_videos.py --execute --folder /path/to/folder
"""

import sqlite3
import os
import sys
import time
import argparse

# 确保可以导入项目模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from video_analyzer.adapter import VideoContentAnalyzer


def get_db_path():
    """获取数据库路径"""
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "media_library.db")
    if not os.path.exists(db_path):
        print(f"错误: 数据库文件不存在: {db_path}")
        sys.exit(1)
    return db_path


def get_untagged_online_videos(conn, folder=None):
    """
    获取所有在线且没有标签的视频
    返回: [(id, file_path, title, stars, current_tags), ...]
    """
    cursor = conn.cursor()

    if folder:
        cursor.execute("""
            SELECT id, file_path, title, stars, tags
            FROM videos
            WHERE (tags IS NULL OR tags = '' OR tags = '<无标签>')
              AND is_nas_online = 1
              AND file_path LIKE ? || '%'
            ORDER BY id
        """, (folder,))
    else:
        cursor.execute("""
            SELECT id, file_path, title, stars, tags
            FROM videos
            WHERE (tags IS NULL OR tags = '' OR tags = '<无标签>')
              AND is_nas_online = 1
            ORDER BY id
        """)

    rows = cursor.fetchall()

    # 二次过滤：只保留文件实际存在的
    valid = []
    for row in rows:
        vid, fpath, title, stars, tags = row
        if os.path.exists(fpath):
            valid.append(row)
        else:
            print(f"  跳过(文件不存在): {fpath}")

    return valid


def retag_videos(videos, conn, execute=False, use_pipeline=True, max_workers=3, delay=2.0):
    """对视频列表重新打标签"""
    analyzer = VideoContentAnalyzer(
        db_path="media_library.db",
        use_pipeline=use_pipeline,
        max_workers=max_workers
    )

    cursor = conn.cursor()
    processed = 0
    failed = 0
    updated = 0
    no_tag_count = 0

    total = len(videos)

    for i, (video_id, file_path, title, stars, current_tags) in enumerate(videos, 1):
        file_name = os.path.basename(file_path)
        print(f"\n[{i}/{total}] 分析: {file_name}")
        print(f"  现有标签: {current_tags or '无'}")

        # 使用带重试的分析方法
        analysis_result = analyzer.analyze_video_content_with_retry(file_path)

        if 'error' in analysis_result and not analysis_result.get('no_tag'):
            print(f"  ✗ 分析失败: {analysis_result['error']}")
            failed += 1
            continue

        generated_tags = analysis_result.get('generated_tags', [])

        # 标记为无标签
        if analysis_result.get('no_tag'):
            if execute:
                cursor.execute(
                    "UPDATE videos SET tags = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    ('<无标签>', video_id)
                )
                conn.commit()
            print(f"  → 标记为 <无标签>")
            no_tag_count += 1
            processed += 1
            continue

        if generated_tags:
            # 重新打标签：用新标签覆盖旧的自动标签，保留JAVDB标签
            existing_set = set(tag.strip() for tag in (current_tags or '').split(',') if tag.strip())
            # JAVDB标签特征：包含繁体字或来自javdb的
            # 简单处理：合并新旧标签
            new_set = set(generated_tags)
            all_tags = existing_set.union(new_set)

            final_tags = ', '.join(sorted(all_tags))

            if execute:
                cursor.execute(
                    "UPDATE videos SET tags = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (final_tags, video_id)
                )
                conn.commit()

            print(f"  ✓ 新标签: {', '.join(generated_tags)}")
            print(f"  ✓ 合并后: {final_tags}")
            updated += 1
        else:
            print(f"  - 未生成标签")

        processed += 1

        # 每次处理后暂停，控制TPM速率
        if delay > 0 and i < total:
            time.sleep(delay)

        # 每10个打印一次统计
        if i % 10 == 0:
            print(f"\n--- 进度统计: 已处理 {processed}/{total}, 更新 {updated}, 失败 {failed}, 无标签 {no_tag_count} ---\n")

    return processed, updated, failed, no_tag_count


def main():
    parser = argparse.ArgumentParser(description="针对所有在线且没有标签的视频自动打标签")
    parser.add_argument("--execute", action="store_true", help="实际执行更新（默认为预览模式）")
    parser.add_argument("--limit", type=int, help="限制处理数量（调试用）")
    parser.add_argument("--folder", type=str, help="只处理指定文件夹下的视频")
    parser.add_argument("--no-pipeline", action="store_true", help="不使用流水线模式（串行处理）")
    parser.add_argument("--workers", type=int, default=1, help="流水线模式的工作线程数（默认1，避免TPM限流）")
    parser.add_argument("--delay", type=float, default=2.0, help="每次API调用后的暂停秒数（默认2.0，控制TPM速率）")

    args = parser.parse_args()

    db_path = get_db_path()
    conn = sqlite3.connect(db_path)

    print(f"数据库: {db_path}")

    # 获取无标签的在线视频
    videos = get_untagged_online_videos(conn, folder=args.folder)

    print(f"在线且无标签的视频总数: {len(videos)}")

    if not videos:
        print("没有符合条件的视频")
        conn.close()
        return

    # 星级分布（可选参考）
    star_counts = {}
    for _, _, _, stars, _ in videos:
        if stars and stars > 0:
            star_counts[stars] = star_counts.get(stars, 0) + 1
    if star_counts:
        print("  已打分视频:")
        for s in sorted(star_counts.keys(), reverse=True):
            print(f"    ⭐{s}: {star_counts[s]} 个")

    if args.limit:
        videos = videos[:args.limit]
        print(f"\n限制处理前 {args.limit} 个视频")

    if not args.execute:
        print(f"\n=== 预览模式（不会实际更新数据库）===")
        print(f"将处理 {len(videos)} 个视频")
        print(f"使用 --execute 参数来实际执行打标签\n")

        # 预览前5个
        for i, (vid, fpath, title, stars, tags) in enumerate(videos[:5], 1):
            print(f"  {i}. ID:{vid} {os.path.basename(fpath)}")
            print(f"     标签: {tags or '无'}")
        if len(videos) > 5:
            print(f"  ... 还有 {len(videos) - 5} 个视频")

        conn.close()
        return

    print(f"\n=== 实际执行模式 ===")
    print(f"将处理 {len(videos)} 个视频")
    print(f"流水线模式: {'否' if args.no_pipeline else '是'}")
    print(f"并发数: {args.workers}")
    print(f"请求间隔: {args.delay}秒")
    print()

    start_time = time.time()

    processed, updated, failed, no_tag_count = retag_videos(
        videos, conn,
        execute=True,
        use_pipeline=not args.no_pipeline,
        max_workers=args.workers,
        delay=args.delay
    )

    elapsed = time.time() - start_time

    print(f"\n{'='*50}")
    print(f"处理完成!")
    print(f"  总处理: {processed}")
    print(f"  标签更新: {updated}")
    print(f"  无标签: {no_tag_count}")
    print(f"  失败: {failed}")
    print(f"  耗时: {elapsed:.1f}秒 ({elapsed/60:.1f}分钟)")
    print(f"{'='*50}")

    conn.close()


if __name__ == "__main__":
    main()