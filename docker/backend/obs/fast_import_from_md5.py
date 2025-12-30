#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于video_md5.csv的快速视频导入脚本
优化版本：针对/Volumes/Video文件夹的高效导入
"""

import csv
import sqlite3
import os
import sys
import time
from datetime import datetime
import logging
from pathlib import Path

# 配置
MD5_CSV_PATH = "/Users/firewell/Library/CloudStorage/OneDrive-个人/bioinfo/media/video_md5.csv"
DB_PATH = "/Users/firewell/Library/CloudStorage/OneDrive-个人/bioinfo/media/media_library.db"
MIN_SIZE = 10 * 1024 * 1024  # 10MB
NAS_REMOTE_PREFIX = "/volume1/Video"
NAS_LOCAL_PREFIX = "/Volumes/Video"

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("fast_import.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def normalize_path(original_path):
    """路径转换：/volume1/Video/ → /Volumes/Video/"""
    return original_path.replace(NAS_REMOTE_PREFIX, NAS_LOCAL_PREFIX)

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

def file_exists_in_database(cursor, md5_hash, file_path=None):
    """检查文件是否已存在于数据库中"""
    try:
        if md5_hash:
            cursor.execute("SELECT COUNT(*) FROM videos WHERE md5_hash = ?", (md5_hash,))
            if cursor.fetchone()[0] > 0:
                return True
        
        # 如果指定了文件路径，也检查路径
        if file_path:
            cursor.execute("SELECT COUNT(*) FROM videos WHERE file_path = ?", (file_path,))
            if cursor.fetchone()[0] > 0:
                return True
                
        return False
    except Exception as e:
        logger.error(f"检查文件存在性出错: {e}")
        return False

def insert_video_to_database(cursor, file_name, file_path, file_size, md5_hash):
    """将视频文件插入数据库"""
    try:
        title = os.path.splitext(file_name)[0]
        now = datetime.now().isoformat()
        
        # 获取文件创建时间
        try:
            file_created_time = datetime.fromtimestamp(os.path.getctime(file_path)).isoformat()
        except:
            file_created_time = now
        
        # 获取源文件夹
        source_folder = os.path.dirname(file_path)
        
        # 检查文件是否真的存在
        if not os.path.exists(file_path):
            logger.warning(f"文件不存在: {file_path}")
            return False
        
        cursor.execute("""
            INSERT INTO videos
            (title, file_name, file_path, file_size, md5_hash, created_at, updated_at, file_created_time, source_folder)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (title, file_name, file_path, file_size, md5_hash, now, now, file_created_time, source_folder))

        return True
    except Exception as e:
        logger.error(f"插入失败 {file_name}: {e}")
        return False

def create_md5_index(csv_path):
    """创建MD5索引以加快查找速度"""
    md5_index = {}
    logger.info(f"正在创建MD5索引，处理文件: {csv_path}")
    
    start_time = time.time()
    try:
        with open(csv_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                file_path = normalize_path(row['文件路径'])
                md5_hash = row['MD5值']
                file_size = int(row['大小(字节)'])
                file_name = row['文件名']
                
                # 只索引有效的视频文件
                if not should_skip_file(file_name, file_path, file_size) and os.path.exists(file_path):
                    md5_index[file_path] = (md5_hash, file_size, file_name)
    except Exception as e:
        logger.error(f"创建MD5索引出错: {e}")
    
    end_time = time.time()
    logger.info(f"MD5索引创建完成，共索引 {len(md5_index)} 个有效文件，耗时 {end_time - start_time:.2f} 秒")
    return md5_index

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
        logger.info(f"连接数据库成功: {DB_PATH}")
    except Exception as e:
        logger.error(f"数据库连接失败: {e}")
        sys.exit(1)

    try:
        logger.info(f"开始导入MD5文件...")
        logger.info(f"CSV文件: {MD5_CSV_PATH}")
        logger.info(f"目标路径: {NAS_LOCAL_PREFIX}/")
        logger.info("-" * 50)
        
        # 首先统计一下数据库中已有的/Volumes/Video文件数量
        cursor.execute("SELECT COUNT(*) FROM videos WHERE file_path LIKE ?", (f"{NAS_LOCAL_PREFIX}%",))
        existing_count = cursor.fetchone()[0]
        logger.info(f"数据库中已存在 {existing_count} 个 {NAS_LOCAL_PREFIX} 路径的文件")

        # 创建MD5索引
        md5_index = create_md5_index(MD5_CSV_PATH)
        
        # 遍历索引中的文件
        start_time = time.time()
        for i, (file_path, (md5_hash, file_size, file_name)) in enumerate(md5_index.items(), 1):
            stats['total'] += 1

            # 路径已经在索引创建时转换过了
            
            # 由于已经在索引时筛选过，这里可以简化检查
            stats['valid'] += 1

            # 检查是否已存在
            if file_exists_in_database(cursor, md5_hash, file_path):
                stats['existing'] += 1
                continue

            # 插入新文件
            if insert_video_to_database(cursor, file_name, file_path, file_size, md5_hash):
                stats['new'] += 1
                
                # 批量提交，每100个文件提交一次
                if stats['new'] % 100 == 0:
                    conn.commit()
                    logger.info(f"已处理 {i}/{len(md5_index)} 个文件，新增 {stats['new']} 个")

        # 提交所有更改
        conn.commit()
        
        end_time = time.time()
        
    except Exception as e:
        logger.error(f"处理过程中出错: {e}")
    finally:
        conn.close()

    # 显示统计结果
    logger.info("\n" + "=" * 60)
    logger.info("导入完成统计")
    logger.info("=" * 60)
    logger.info(f"总扫描CSV记录: {stats['total']:,}")
    logger.info(f"有效文件: {stats['valid']:,}")
    logger.info(f"新增文件: {stats['new']:,}")
    logger.info(f"已存在: {stats['existing']:,}")
    logger.info(f"跳过文件: {stats['skipped']:,}")
    logger.info(f"错误文件: {stats['error']:,}")
    logger.info(f"总耗时: {end_time - start_time:.2f} 秒")

    if stats['skipped'] > 0:
        logger.info(f"\n跳过原因:")
        logger.info(f"- 回收站文件: #recycle")
        logger.info(f"- 隐藏文件: 以.开头")
        logger.info(f"- 小文件: 小于10MB")
        logger.info(f"- 不存在文件: 路径中找不到")

    logger.info(f"\n导入成功完成！")

if __name__ == "__main__":
    import argparse

    # 添加命令行参数解析
    parser = argparse.ArgumentParser(description='基于MD5的视频快速导入工具')
    parser.add_argument('-y', '--yes', action='store_true', help='跳过确认，直接执行导入')
    parser.add_argument('--verbose', action='store_true', help='显示详细日志')

    args = parser.parse_args()

    # 如果需要详细日志
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # 确认操作
    logger.info("基于MD5的视频快速导入工具")
    logger.info("将跳过回收站、隐藏文件、小于10MB的文件")
    logger.info(f"目标路径: {NAS_LOCAL_PREFIX}/")
    
    # 检查CSV文件是否存在
    if not os.path.exists(MD5_CSV_PATH):
        logger.error(f"CSV文件不存在: {MD5_CSV_PATH}")
        sys.exit(1)
    
    # 检查数据库文件是否存在
    if not os.path.exists(DB_PATH):
        logger.error(f"数据库文件不存在: {DB_PATH}")
        sys.exit(1)

    if not args.yes:
        try:
            logger.info("确认要执行导入操作吗？(y/N): ")
            response = input().lower().strip()
            if response != 'y':
                logger.info("操作已取消")
                sys.exit(0)
        except EOFError:
            logger.info("无法读取输入，使用 -y 参数跳过确认")
            logger.info("操作已取消")
            sys.exit(0)

    main()