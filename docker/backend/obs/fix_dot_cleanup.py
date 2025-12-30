#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复前后句号问题的全面清理脚本
清理数据库中的标题、文件名、文件路径字段的前后句号，并重命名实际文件

作者: AI Assistant
创建时间: 2025
"""

import sqlite3
import os
import shutil
from pathlib import Path

def clean_dots_from_string(text):
    """
    清理字符串前后的句号
    
    Args:
        text (str): 原始字符串
        
    Returns:
        str: 清理后的字符串
    """
    if not text:
        return text
    
    # 去除开头和结尾的句号
    cleaned = text.strip('.')
    return cleaned

def fix_database_and_files(db_path="media_library.db", dry_run=True):
    """
    修复数据库记录和实际文件名
    
    Args:
        db_path (str): 数据库文件路径
        dry_run (bool): 是否为预览模式，不实际执行修改
    """
    if not os.path.exists(db_path):
        print(f"错误：找不到数据库文件 {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 查询所有受影响的记录（包括只有开头句号的记录）
        cursor.execute("""
            SELECT id, title, file_name, file_path, source_folder
            FROM videos 
            WHERE title LIKE '.%.' OR file_name LIKE '.%.' OR file_path LIKE '.%.' 
               OR title LIKE '.%' OR file_name LIKE '.%' OR file_path LIKE '.%'
        """)
        
        affected_records = cursor.fetchall()
        
        if not affected_records:
            print("没有找到需要清理的记录")
            return True
        
        print(f"找到 {len(affected_records)} 条需要清理的记录")
        print(f"模式: {'预览模式' if dry_run else '执行模式'}")
        print("=" * 60)
        
        updated_count = 0
        file_rename_count = 0
        
        for record_id, title, file_name, file_path, source_folder in affected_records:
            print(f"\n处理记录 ID: {record_id}")
            
            # 清理各个字段
            new_title = clean_dots_from_string(title) if title else title
            new_file_name = clean_dots_from_string(file_name) if file_name else file_name
            new_file_path = clean_dots_from_string(file_path) if file_path else file_path
            
            # 检查是否需要更新
            needs_update = (title != new_title or 
                          file_name != new_file_name or 
                          file_path != new_file_path)
            
            if needs_update:
                print(f"  原标题: {title}")
                print(f"  新标题: {new_title}")
                print(f"  原文件名: {file_name}")
                print(f"  新文件名: {new_file_name}")
                print(f"  原文件路径: {file_path}")
                print(f"  新文件路径: {new_file_path}")
                
                # 处理实际文件重命名
                if file_path and new_file_path and file_path != new_file_path:
                    old_full_path = os.path.join(source_folder, file_path) if source_folder else file_path
                    new_full_path = os.path.join(source_folder, new_file_path) if source_folder else new_file_path
                    
                    if os.path.exists(old_full_path):
                        print(f"  文件重命名: {old_full_path} -> {new_full_path}")
                        
                        if not dry_run:
                            try:
                                # 确保目标目录存在
                                os.makedirs(os.path.dirname(new_full_path), exist_ok=True)
                                # 重命名文件
                                shutil.move(old_full_path, new_full_path)
                                file_rename_count += 1
                                print(f"  ✓ 文件重命名成功")
                            except Exception as e:
                                print(f"  ✗ 文件重命名失败: {e}")
                                continue
                    else:
                        print(f"  ⚠ 原文件不存在: {old_full_path}")
                
                # 更新数据库记录
                if not dry_run:
                    try:
                        cursor.execute("""
                            UPDATE videos 
                            SET title = ?, file_name = ?, file_path = ?, updated_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                        """, (new_title, new_file_name, new_file_path, record_id))
                        updated_count += 1
                        print(f"  ✓ 数据库记录更新成功")
                    except Exception as e:
                        print(f"  ✗ 数据库更新失败: {e}")
            else:
                print(f"  无需更新")
        
        if not dry_run:
            conn.commit()
            print(f"\n清理完成！")
            print(f"数据库记录更新: {updated_count} 条")
            print(f"文件重命名: {file_rename_count} 个")
        else:
            print(f"\n预览完成！")
            print(f"将要更新的数据库记录: {len([r for r in affected_records if any([clean_dots_from_string(r[1]) != r[1], clean_dots_from_string(r[2]) != r[2], clean_dots_from_string(r[3]) != r[3]])])} 条")
            print(f"将要重命名的文件: {len([r for r in affected_records if r[3] and clean_dots_from_string(r[3]) != r[3]])} 个")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"处理过程中发生错误: {e}")
        return False

def main():
    """
    主函数
    """
    print("前后句号清理工具")
    print("=" * 30)
    
    # 检查数据库文件
    db_path = "media_library.db"
    if not os.path.exists(db_path):
        print(f"错误：找不到数据库文件 {db_path}")
        print("请确保在媒体库项目目录中运行此脚本")
        return
    
    # 首先运行预览模式
    print("\n=== 预览模式 ===")
    fix_database_and_files(db_path, dry_run=True)
    
    # 询问是否执行实际清理
    print("\n" + "=" * 50)
    choice = input("是否执行实际清理？(y/N): ").strip().lower()
    
    if choice in ['y', 'yes', '是']:
        print("\n=== 执行模式 ===")
        success = fix_database_and_files(db_path, dry_run=False)
        if success:
            print("\n清理完成！建议重新启动媒体库应用程序以查看更改。")
        else:
            print("\n清理过程中出现错误，请检查日志。")
    else:
        print("\n已取消清理操作。")

if __name__ == "__main__":
    main()