#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能视频描述更新器
通过文件名匹配CSV数据并更新数据库，同时可选择重新计算MD5值
"""

import sqlite3
import pandas as pd
import hashlib
import os
from pathlib import Path
import argparse

def calculate_md5(file_path):
    """计算文件的MD5值"""
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        print(f"计算MD5失败 {file_path}: {e}")
        return None

def merge_description_fields(row):
    """合并CSV中的描述字段"""
    parts = []
    
    # 女性人物形象描述
    if pd.notna(row['女性人物形象描述']) and str(row['女性人物形象描述']).strip():
        parts.append(f"【人物形象】\n{row['女性人物形象描述']}")
    
    # 场景和剧情推测
    if pd.notna(row['场景和剧情推测']) and str(row['场景和剧情推测']).strip():
        parts.append(f"【场景剧情】\n{row['场景和剧情推测']}")
    
    # 提取关键词
    if pd.notna(row['提取关键词']) and str(row['提取关键词']).strip():
        parts.append(f"【关键词】\n{row['提取关键词']}")
    
    return '\n\n'.join(parts)

def clean_tags(tags_str):
    """清理标签字符串"""
    if pd.isna(tags_str) or not str(tags_str).strip():
        return ""
    
    # 移除重复标签并清理
    tags = str(tags_str).split('、')
    unique_tags = []
    seen = set()
    
    for tag in tags:
        tag = tag.strip()
        if tag and tag not in seen:
            unique_tags.append(tag)
            seen.add(tag)
    
    return '、'.join(unique_tags)

def smart_update_videos(csv_file, db_file='media_library.db', recalculate_md5=False, preview_mode=True):
    """智能更新视频描述和标签"""
    
    print(f"开始处理...")
    print(f"CSV文件: {csv_file}")
    print(f"数据库: {db_file}")
    print(f"重新计算MD5: {'是' if recalculate_md5 else '否'}")
    print(f"预览模式: {'是' if preview_mode else '否'}")
    print("-" * 50)
    
    # 读取CSV文件
    try:
        df = pd.read_csv(csv_file)
        print(f"✓ 成功读取CSV文件，共 {len(df)} 条记录")
    except Exception as e:
        print(f"✗ 读取CSV文件失败: {e}")
        return
    
    # 连接数据库
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        print(f"✓ 成功连接数据库")
    except Exception as e:
        print(f"✗ 连接数据库失败: {e}")
        return
    
    # 统计变量
    matched_count = 0
    updated_count = 0
    md5_updated_count = 0
    failed_count = 0
    
    # 处理每条CSV记录
    for index, row in df.iterrows():
        try:
            file_name = row['file_name']
            csv_md5 = row['file_md5']
            
            # 通过文件名查找数据库记录
            cursor.execute("SELECT id, file_path, md5_hash FROM videos WHERE file_name = ?", (file_name,))
            db_record = cursor.fetchone()
            
            if not db_record:
                continue
            
            video_id, file_path, db_md5 = db_record
            matched_count += 1
            
            print(f"\n处理文件: {file_name}")
            print(f"  视频ID: {video_id}")
            
            # 检查是否需要重新计算MD5
            new_md5 = db_md5
            if recalculate_md5 and file_path and os.path.exists(file_path):
                calculated_md5 = calculate_md5(file_path)
                if calculated_md5 and calculated_md5 != db_md5:
                    new_md5 = calculated_md5
                    print(f"  MD5更新: {db_md5} -> {calculated_md5}")
                    if not preview_mode:
                        cursor.execute("UPDATE videos SET md5_hash = ? WHERE id = ?", (calculated_md5, video_id))
                        md5_updated_count += 1
                elif calculated_md5:
                    print(f"  MD5验证: 一致 ({calculated_md5})")
                else:
                    print(f"  MD5计算: 失败")
            
            # 准备描述和标签
            description = merge_description_fields(row)
            tags = clean_tags(row['存在的标签有'])
            
            print(f"  描述长度: {len(description)} 字符")
            print(f"  标签: {tags}")
            
            # 更新数据库
            if not preview_mode:
                update_fields = []
                update_values = []
                
                if description:
                    update_fields.append("description = ?")
                    update_values.append(description)
                
                if tags:
                    update_fields.append("tags = ?")
                    update_values.append(tags)
                
                if update_fields:
                    update_fields.append("updated_at = CURRENT_TIMESTAMP")
                    update_values.append(video_id)
                    
                    sql = f"UPDATE videos SET {', '.join(update_fields)} WHERE id = ?"
                    cursor.execute(sql, update_values)
                    updated_count += 1
                    print(f"  ✓ 已更新")
                else:
                    print(f"  - 无需更新")
            else:
                print(f"  [预览] 将要更新描述和标签")
                updated_count += 1
            
        except Exception as e:
            failed_count += 1
            print(f"  ✗ 处理失败: {e}")
    
    # 提交更改
    if not preview_mode:
        conn.commit()
    
    conn.close()
    
    # 输出统计结果
    print("\n" + "=" * 50)
    print("处理完成统计:")
    print(f"  CSV总记录数: {len(df)}")
    print(f"  匹配的记录: {matched_count}")
    print(f"  更新的记录: {updated_count}")
    if recalculate_md5:
        print(f"  MD5更新数: {md5_updated_count}")
    print(f"  失败的记录: {failed_count}")
    
    if preview_mode:
        print(f"\n注意: 当前为预览模式，未实际修改数据库")
        print(f"要执行实际更新，请使用 --execute 参数")

def main():
    parser = argparse.ArgumentParser(description='智能视频描述更新器')
    parser.add_argument('--csv', default='/Users/firewell/Library/CloudStorage/OneDrive-个人/bioinfo/media/analysis_out.csv',
                       help='CSV文件路径')
    parser.add_argument('--db', default='media_library.db', help='数据库文件路径')
    parser.add_argument('--recalc-md5', action='store_true', help='重新计算MD5值')
    parser.add_argument('--execute', action='store_true', help='执行实际更新（默认为预览模式）')
    
    args = parser.parse_args()
    
    smart_update_videos(
        csv_file=args.csv,
        db_file=args.db,
        recalculate_md5=args.recalc_md5,
        preview_mode=not args.execute
    )

if __name__ == "__main__":
    main()