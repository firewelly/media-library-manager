#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
更新数据库中tags列为空的记录，从CSV文件中的"匹配标签列表"获取标签
不更新description列和javdb对应的标签
"""

import csv
import os
import sqlite3
import argparse
from tqdm import tqdm
import re


def is_javdb_record(file_name):
    """判断是否为javdb相关的记录"""
    # 定义需要跳过的特定javdb相关的文件类型或关键词
    skip_keywords = ['javdb', 'fc2', 'ppv', 'FC2', 'PPV']
    
    # 检查文件名是否包含需要跳过的关键词
    for keyword in skip_keywords:
        if keyword in file_name.lower():
            return True
    
    # 仅当文件名完全匹配番号格式时才视为javdb记录，避免误判
    # 严格的番号格式判断：大写字母+连字符+数字格式
    strict_jav_pattern = r'^[A-Z]+-\d+\.mp4$'
    if re.match(strict_jav_pattern, file_name):
        return True
    
    return False


def update_tags_from_csv(db_path, csv_path):
    """从CSV文件更新数据库中的tags列"""
    # 统计信息
    total_records = 0
    updated_records = 0
    skipped_javdb_records = 0
    already_has_tags_records = 0
    not_found_in_db_records = 0
    
    try:
        # 连接数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 读取CSV文件
        with open(csv_path, 'r', encoding='utf-8') as csv_file:
            csv_reader = csv.reader(csv_file)
            headers = next(csv_reader)  # 获取表头
            
            # 查找需要的列索引
            full_path_idx = headers.index('完整路径')
            file_name_idx = headers.index('文件名')
            tags_list_idx = headers.index('匹配标签列表')
            
            # 获取CSV文件的总行数（用于进度条）
            csv_file.seek(0)
            total_csv_rows = sum(1 for _ in csv_reader) - 1  # 减去表头行
            csv_file.seek(0)
            next(csv_reader)  # 跳过表头
            
            # 使用进度条遍历CSV记录
            print(f"开始处理CSV文件: {csv_path}")
            for row in tqdm(csv_reader, total=total_csv_rows, desc="处理进度"):
                total_records += 1
                
                full_path = row[full_path_idx]
                file_name = row[file_name_idx]
                tags_list = row[tags_list_idx].strip()
                
                # 检查是否为javdb相关记录，如果是则跳过
                if is_javdb_record(file_name):
                    skipped_javdb_records += 1
                    continue
                
                # 获取文件名（不包含扩展名）用于更灵活的匹配
                file_name_without_ext = os.path.splitext(file_name)[0]
                
                # 查找数据库中的记录，使用多种匹配策略
                # 策略1: 完整路径匹配
                cursor.execute("SELECT id, tags FROM videos WHERE file_path = ?", (full_path,))
                result = cursor.fetchone()
                
                # 策略2: 如果没有找到，尝试使用文件名完全匹配
                if not result:
                    cursor.execute("SELECT id, tags FROM videos WHERE file_name = ?", (file_name,))
                    result = cursor.fetchone()
                
                # 策略3: 如果仍然没有找到，尝试使用文件名（不含扩展名）匹配
                if not result:
                    cursor.execute("SELECT id, tags FROM videos WHERE file_name LIKE ?", (f"{file_name_without_ext}%",))
                    result = cursor.fetchone()
                
                # 策略4: 如果仍然没有找到，尝试使用路径中的文件名部分进行模糊匹配
                if not result:
                    base_name = os.path.basename(full_path)
                    cursor.execute("SELECT id, tags FROM videos WHERE file_path LIKE ?", (f"%{base_name}",))
                    result = cursor.fetchone()
                
                # 如果找到记录且tags列为空，则更新
                if result:
                    video_id, current_tags = result
                    current_tags = current_tags if current_tags else ""
                    
                    if not current_tags and tags_list:
                        # 更新tags列
                        cursor.execute("UPDATE videos SET tags = ? WHERE id = ?", 
                                     (tags_list, video_id))
                        updated_records += 1
                    else:
                        already_has_tags_records += 1
                else:
                    not_found_in_db_records += 1
            
            # 提交更改
            conn.commit()
            print(f"\n已成功提交所有更改到数据库。")
            
    except Exception as e:
        print(f"处理过程中发生错误: {str(e)}")
        # 如果发生错误，回滚事务
        if 'conn' in locals():
            conn.rollback()
    finally:
        # 关闭数据库连接
        if 'conn' in locals():
            conn.close()
    
    # 输出统计信息
    print("\n===== 处理统计 =====")
    print(f"总处理CSV记录数: {total_records}")
    print(f"成功更新tags列的记录数: {updated_records}")
    print(f"跳过的javdb相关记录数: {skipped_javdb_records}")
    print(f"已存在tags的记录数: {already_has_tags_records}")
    print(f"数据库中未找到的记录数: {not_found_in_db_records}")
    print("==================")


def main():
    # 命令行参数解析
    parser = argparse.ArgumentParser(description='从CSV文件更新数据库中的tags列')
    parser.add_argument('-db', '--database', 
                       default='/Users/firewell/Library/CloudStorage/OneDrive-个人/bioinfo/media/media_library.db',
                       help='数据库文件路径')
    parser.add_argument('-csv', '--csv_file', 
                       default='/Users/firewell/Library/CloudStorage/OneDrive-个人/bioinfo/media/HC530_1_待整理_merged_analysis.csv',
                       help='CSV文件路径')
    parser.add_argument('-y', '--yes', action='store_true', help='跳过确认提示')
    
    args = parser.parse_args()
    
    # 检查文件是否存在
    if not os.path.exists(args.database):
        print(f"错误: 数据库文件不存在: {args.database}")
        return
    
    if not os.path.exists(args.csv_file):
        print(f"错误: CSV文件不存在: {args.csv_file}")
        return
    
    # 确认操作
    if not args.yes:
        confirm = input(f"即将从CSV文件 '{args.csv_file}' 更新数据库 '{args.database}' 中的tags列。\n" \
                       "此操作不会更新description列和javdb相关的标签。\n" \
                       "是否继续? (y/n): ")
        if confirm.lower() != 'y':
            print("操作已取消。")
            return
    
    # 执行更新
    update_tags_from_csv(args.database, args.csv_file)


if __name__ == '__main__':
    main()