#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于video_md5.csv的简洁高效视频导入脚本
"""

import csv
import sqlite3
import os
import sys
from datetime import datetime

# 配置
# 使用相对路径
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
MD5_CSV_PATH = os.path.join(root_dir, "video_md5.csv")
DB_PATH = os.path.join(root_dir, "media_library.db")

# 兼容性检查
if not os.path.exists(DB_PATH):
    for r in ["/Users/firewell/Library/CloudStorage/OneDrive-Personal/bioinfo/media", 
              "/Users/firewell/Library/CloudStorage/OneDrive-个人/bioinfo/media"]:
        if os.path.exists(os.path.join(r, "media_library.db")):
            DB_PATH = os.path.join(r, "media_library.db")
            MD5_CSV_PATH = os.path.join(r, "video_md5.csv")
            break

MIN_SIZE = 10 * 1024 * 1024  # 10MB

def normalize_path(original_path):
    """路径转换：/volume1/Video/ → /Volumes/Video/"""
    return original_path.replace('/volume1/Video/', '/Volumes/Video/')

def should_skip_file(file_name, file_path, file_size):
    """判断是否应该跳过该文件"""
    # 跳过回收站文件
    if '#recycle' in file_path:
        return True

    # 跳过隐藏文件
    if file_name.startswith('.'):
        return True

    # 跳过小文件
    if file_size < MIN_SIZE:
        return True

    return False

def file_exists_in_database(cursor, md5_hash):
    """检查文件是否已存在于数据库中"""
    try:
        cursor.execute("SELECT COUNT(*) FROM videos WHERE md5_hash = ?", (md5_hash,))
        return cursor.fetchone()[0] > 0
    except:
        return False

def insert_video_to_database(cursor, file_name, file_path, file_size, md5_hash):
    """将视频文件插入数据库"""
    try:
        title = os.path.splitext(file_name)[0]
        now = datetime.now().isoformat()

        cursor.execute("""
            INSERT INTO videos
            (title, file_name, file_path, file_size, md5_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (title, file_name, file_path, file_size, md5_hash, now, now))

        return True
    except Exception as e:
        print(f"插入失败 {file_name}: {e}")
        return False

def main():
    # 统计信息
    stats = {
        'total': 0,
        'valid': 0,
        'new': 0,
        'existing': 0,
        'skipped': 0,
        'error': 0
    }

    # 连接数据库
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        print(f"连接数据库成功: {DB_PATH}")
    except Exception as e:
        print(f"数据库连接失败: {e}")
        sys.exit(1)

    try:
        print("开始导入MD5文件...")
        print(f"CSV文件: {MD5_CSV_PATH}")
        print(f"目标路径: /Volumes/Video/")
        print("-" * 50)

        with open(MD5_CSV_PATH, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)

            for row in reader:
                stats['total'] += 1

                file_name = row['文件名']
                original_path = row['文件路径']
                file_size = int(row['大小(字节)'])
                md5_hash = row['MD5值']

                # 路径转换
                file_path = normalize_path(original_path)

                # 检查是否应该跳过
                if should_skip_file(file_name, file_path, file_size):
                    stats['skipped'] += 1
                    continue

                # 检查文件是否存在
                if not os.path.exists(file_path):
                    stats['error'] += 1
                    if stats['error'] <= 5:
                        print(f"文件不存在: {file_path}")
                    continue

                stats['valid'] += 1

                # 检查是否已存在
                if file_exists_in_database(cursor, md5_hash):
                    stats['existing'] += 1
                    continue

                # 插入新文件
                if insert_video_to_database(cursor, file_name, file_path, file_size, md5_hash):
                    stats['new'] += 1
                    conn.commit()

                # 每1000个文件显示一次进度
                if stats['total'] % 1000 == 0:
                    print(f"已处理 {stats['total']} 个文件，有效 {stats['valid']} 个，新增 {stats['new']} 个")

        # 提交所有更改
        conn.commit()

    except Exception as e:
        print(f"处理过程中出错: {e}")
    finally:
        conn.close()

    # 显示统计结果
    print("\n" + "=" * 60)
    print("导入完成统计")
    print("=" * 60)
    print(f"总扫描: {stats['total']:,}")
    print(f"有效文件: {stats['valid']:,}")
    print(f"新增文件: {stats['new']:,}")
    print(f"已存在: {stats['existing']:,}")
    print(f"跳过文件: {stats['skipped']:,}")
    print(f"错误文件: {stats['error']:,}")

    if stats['skipped'] > 0:
        print(f"\n跳过原因:")
        print(f"- 回收站文件: #recycle")
        print(f"- 隐藏文件: 以.开头")
        print(f"- 小文件: 小于10MB")
        print(f"- 不存在文件: 路径中找不到")

    print(f"\n导入成功完成！")

if __name__ == "__main__":
    import argparse

    # 添加命令行参数解析
    parser = argparse.ArgumentParser(description='基于MD5的视频导入工具')
    parser.add_argument('-y', '--yes', action='store_true', help='跳过确认，直接执行导入')

    args = parser.parse_args()

    # 确认操作
    print("基于MD5的视频导入工具")
    print("将跳过回收站、隐藏文件、小于10MB的文件")
    print()

    if not args.yes:
        print("确认要执行导入操作吗？(y/N): ", end="")
        try:
            response = input().lower().strip()
            if response != 'y':
                print("操作已取消")
                sys.exit(0)
        except EOFError:
            print("无法读取输入，使用 -y 参数跳过确认")
            print("操作已取消")
            sys.exit(0)

    main()