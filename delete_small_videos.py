#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
删除小于1MB的视频文件脚本

功能：
1. 查找数据库中小于1MB的视频记录
2. 删除对应的物理文件
3. 从数据库中删除记录
4. 提供预览模式和实际执行模式
"""

import sqlite3
import os
import sys
from pathlib import Path

def get_small_videos(db_path, size_limit=1048576):
    """
    获取小于指定大小的视频记录
    
    Args:
        db_path: 数据库路径
        size_limit: 文件大小限制（字节），默认1MB
    
    Returns:
        list: 包含视频记录的列表
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    query = """
    SELECT id, title, file_path, file_size 
    FROM videos 
    WHERE file_size < ? 
    ORDER BY file_size DESC
    """
    
    cursor.execute(query, (size_limit,))
    records = cursor.fetchall()
    
    conn.close()
    return records

def delete_video_files_and_records(db_path, size_limit=1048576, preview_mode=True):
    """
    删除小于指定大小的视频文件和数据库记录
    
    Args:
        db_path: 数据库路径
        size_limit: 文件大小限制（字节），默认1MB
        preview_mode: 是否为预览模式，True时只显示将要删除的文件，不实际删除
    
    Returns:
        dict: 删除结果统计
    """
    records = get_small_videos(db_path, size_limit)
    
    if not records:
        print("没有找到小于1MB的视频文件。")
        return {"total": 0, "files_deleted": 0, "db_records_deleted": 0, "errors": []}
    
    print(f"找到 {len(records)} 个小于1MB的视频记录：")
    print("=" * 80)
    
    files_deleted = 0
    db_records_deleted = 0
    errors = []
    
    # 显示将要删除的文件
    for record in records:
        video_id, title, file_path, file_size = record
        size_mb = file_size / 1024 / 1024
        print(f"ID: {video_id}")
        print(f"标题: {title[:60]}{'...' if len(title) > 60 else ''}")
        print(f"文件路径: {file_path}")
        print(f"文件大小: {size_mb:.2f} MB ({file_size} bytes)")
        print("-" * 80)
    
    if preview_mode:
        print("\n[预览模式] 以上文件将被删除。")
        print("要实际执行删除，请使用 --execute 参数。")
        return {"total": len(records), "files_deleted": 0, "db_records_deleted": 0, "errors": []}
    
    # 实际删除模式
    print("\n开始删除文件和数据库记录...")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    for record in records:
        video_id, title, file_path, file_size = record
        
        try:
            # 删除物理文件
            if os.path.exists(file_path):
                os.remove(file_path)
                files_deleted += 1
                print(f"✓ 已删除文件: {file_path}")
            else:
                print(f"⚠ 文件不存在: {file_path}")
            
            # 从数据库删除记录
            cursor.execute("DELETE FROM videos WHERE id = ?", (video_id,))
            db_records_deleted += 1
            print(f"✓ 已删除数据库记录 ID: {video_id}")
            
        except Exception as e:
            error_msg = f"删除失败 ID {video_id}: {str(e)}"
            errors.append(error_msg)
            print(f"✗ {error_msg}")
    
    # 提交数据库更改
    conn.commit()
    conn.close()
    
    print(f"\n删除完成！")
    print(f"总记录数: {len(records)}")
    print(f"删除文件数: {files_deleted}")
    print(f"删除数据库记录数: {db_records_deleted}")
    print(f"错误数: {len(errors)}")
    
    if errors:
        print("\n错误详情:")
        for error in errors:
            print(f"  - {error}")
    
    return {
        "total": len(records),
        "files_deleted": files_deleted,
        "db_records_deleted": db_records_deleted,
        "errors": errors
    }

def main():
    """
    主函数
    """
    db_path = "media_library.db"
    
    if not os.path.exists(db_path):
        print(f"错误: 数据库文件 {db_path} 不存在！")
        sys.exit(1)
    
    # 检查命令行参数
    preview_mode = "--execute" not in sys.argv
    
    if preview_mode:
        print("=== 预览模式 ===")
        print("将显示所有小于1MB的视频文件，但不会实际删除。")
        print("要实际执行删除，请运行: python3 delete_small_videos.py --execute")
        print()
    else:
        print("=== 执行模式 ===")
        print("警告: 这将永久删除小于1MB的视频文件和数据库记录！")
        confirm = input("确认要继续吗？(输入 'yes' 确认): ")
        if confirm.lower() != 'yes':
            print("操作已取消。")
            sys.exit(0)
        print()
    
    # 执行删除操作
    result = delete_video_files_and_records(db_path, preview_mode=preview_mode)
    
    if not preview_mode and result["total"] > 0:
        print("\n建议重新启动媒体库应用程序以刷新数据。")

if __name__ == "__main__":
    main()