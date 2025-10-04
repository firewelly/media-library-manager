#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一视频描述更新器
优先使用MD5匹配，备用文件名匹配，同时更新两个哈希字段
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
    """合并描述字段"""
    description_parts = []
    
    # 添加各个描述字段
    fields = ['外貌特征', '服装穿着', '整体气质', '场景和剧情推测', '提取关键词']
    for field in fields:
        if pd.notna(row.get(field)) and str(row[field]).strip():
            content = str(row[field]).strip()
            if content and content != 'nan':
                description_parts.append(f"**{field}**: {content}")
    
    return "\n\n".join(description_parts)

def clean_tags(tags_str):
    """清理和格式化标签"""
    if pd.isna(tags_str) or not str(tags_str).strip():
        return ""
    
    # 移除方括号并分割标签
    tags_str = str(tags_str).strip()
    if tags_str.startswith('[') and tags_str.endswith(']'):
        tags_str = tags_str[1:-1]
    
    # 分割并清理标签
    tags = [tag.strip().strip("'\"") for tag in tags_str.split(',')]
    tags = [tag for tag in tags if tag and tag != 'nan']
    
    return ', '.join(tags)

def update_video_descriptions(csv_file, db_file, preview_mode=True, recalculate_md5=False):
    """
    更新视频描述和标签
    
    Args:
        csv_file: CSV文件路径
        db_file: 数据库文件路径
        preview_mode: 是否为预览模式
        recalculate_md5: 是否重新计算MD5
    """
    
    # 读取CSV文件
    print(f"读取CSV文件: {csv_file}")
    try:
        df = pd.read_csv(csv_file)
        print(f"CSV文件包含 {len(df)} 条记录")
    except Exception as e:
        print(f"读取CSV文件失败: {e}")
        return
    
    # 连接数据库
    print(f"连接数据库: {db_file}")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    try:
        # 统计信息
        md5_matched_count = 0
        filename_matched_count = 0
        updated_count = 0
        failed_count = 0
        md5_updated_count = 0
        
        print(f"\n{'='*60}")
        print(f"模式: {'预览模式' if preview_mode else '执行模式'}")
        print(f"重新计算MD5: {'是' if recalculate_md5 else '否'}")
        print(f"{'='*60}")
        
        for index, row in df.iterrows():
            csv_md5 = row['file_md5']
            file_name = row['file_name']
            
            print(f"\n处理记录 {index + 1}/{len(df)}: {file_name}")
            
            # 策略1: 优先使用MD5匹配
            cursor.execute("""
                SELECT id, file_path, md5_hash 
                FROM videos 
                WHERE md5_hash = ?
            """, (csv_md5,))
            
            db_record = cursor.fetchone()
            match_method = None
            
            if db_record:
                match_method = "MD5匹配"
                md5_matched_count += 1
            else:
                # 策略2: 使用文件名匹配
                cursor.execute("""
                    SELECT id, file_path, md5_hash 
                    FROM videos 
                    WHERE file_name = ?
                """, (file_name,))
                
                db_record = cursor.fetchone()
                if db_record:
                    match_method = "文件名匹配"
                    filename_matched_count += 1
            
            if not db_record:
                print(f"  ❌ 未找到匹配记录")
                failed_count += 1
                continue
            
            video_id, file_path, db_md5_hash = db_record
            print(f"  ✅ {match_method} - 视频ID: {video_id}")
            
            # 检查MD5一致性并可选重新计算
            current_md5 = db_md5_hash
            new_md5 = current_md5
            
            if recalculate_md5 and file_path and os.path.exists(file_path):
                calculated_md5 = calculate_md5(file_path)
                if calculated_md5:
                    if calculated_md5 != current_md5:
                        print(f"  🔄 MD5更新: {current_md5} -> {calculated_md5}")
                        new_md5 = calculated_md5
                        if not preview_mode:
                            md5_updated_count += 1
                    else:
                        print(f"  ✅ MD5验证: 一致")
                else:
                    print(f"  ❌ MD5计算失败")
            elif match_method == "文件名匹配" and csv_md5 != current_md5:
                print(f"  ⚠️  MD5不一致: DB={current_md5}, CSV={csv_md5}")
                new_md5 = csv_md5  # 使用CSV中的MD5值
            
            # 准备描述和标签
            description = merge_description_fields(row)
            tags = clean_tags(row['存在的标签有'])
            
            print(f"  📝 描述长度: {len(description)} 字符")
            print(f"  🏷️  标签: {tags}")
            
            # 更新数据库
            if not preview_mode:
                try:
                    update_fields = []
                    update_values = []
                    
                    if description:
                        update_fields.append("description = ?")
                        update_values.append(description)
                    
                    if tags:
                        update_fields.append("tags = ?")
                        update_values.append(tags)
                    
                    # 更新MD5哈希字段
                    if new_md5 and new_md5 != current_md5:
                        update_fields.append("md5_hash = ?")
                        update_values.append(new_md5)
                    
                    if update_fields:
                        update_fields.append("updated_at = CURRENT_TIMESTAMP")
                        sql = f"UPDATE videos SET {', '.join(update_fields)} WHERE id = ?"
                        update_values.append(video_id)
                        
                        cursor.execute(sql, update_values)
                        updated_count += 1
                        print(f"  ✅ 更新成功")
                    else:
                        print(f"  ⚠️  无需更新")
                        
                except Exception as e:
                    print(f"  ❌ 更新失败: {e}")
                    failed_count += 1
            else:
                print(f"  🔍 预览: 将更新描述和标签")
        
        # 提交事务
        if not preview_mode:
            conn.commit()
            print(f"\n✅ 事务已提交")
        
        # 最终统计
        print(f"\n{'='*60}")
        print(f"📊 处理统计:")
        print(f"总记录数: {len(df)}")
        print(f"MD5匹配: {md5_matched_count}")
        print(f"文件名匹配: {filename_matched_count}")
        print(f"更新成功: {updated_count}")
        print(f"更新失败: {failed_count}")
        if recalculate_md5:
            print(f"MD5重新计算: {md5_updated_count}")
        print(f"{'='*60}")
        
    except Exception as e:
        print(f"处理过程中出错: {e}")
        conn.rollback()
    finally:
        conn.close()

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='统一视频描述更新器')
    parser.add_argument('--csv', default='analysis_out.csv', help='CSV文件路径')
    parser.add_argument('--db', default='media_library.db', help='数据库文件路径')
    parser.add_argument('--execute', action='store_true', help='执行实际更新（默认为预览模式）')
    parser.add_argument('--recalculate-md5', action='store_true', help='重新计算MD5值')
    
    args = parser.parse_args()
    
    print("统一视频描述更新器")
    print("=" * 30)
    
    # 检查文件是否存在
    if not os.path.exists(args.csv):
        print(f"❌ CSV文件不存在: {args.csv}")
        return
    
    if not os.path.exists(args.db):
        print(f"❌ 数据库文件不存在: {args.db}")
        return
    
    # 执行更新
    update_video_descriptions(
        csv_file=args.csv,
        db_file=args.db,
        preview_mode=not args.execute,
        recalculate_md5=args.recalculate_md5
    )

if __name__ == "__main__":
    main()