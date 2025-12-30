#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查数据库中不在配置文件夹范围内的视频记录
"""

import sqlite3
import os
from datetime import datetime

def check_invalid_records():
    """检查数据库中不在配置文件夹范围内的视频记录"""
    
    # 连接数据库
    db_path = 'media_library.db'
    if not os.path.exists(db_path):
        print(f"错误：找不到数据库文件 {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 获取所有配置的文件夹路径
        cursor.execute("SELECT folder_path FROM folders WHERE is_active = 1")
        all_configured_folders = [row[0] for row in cursor.fetchall() if row[0]]
        
        print("=== 配置的文件夹列表 ===")
        for i, folder in enumerate(all_configured_folders, 1):
            status = "在线" if os.path.exists(folder) else "离线"
            print(f"{i}. {folder} ({status})")
        
        if not all_configured_folders:
            print("没有找到配置的文件夹")
            return
        
        # 获取所有视频记录
        cursor.execute("SELECT id, file_path, file_name, source_folder FROM videos")
        all_videos = cursor.fetchall()
        
        print(f"\n=== 检查结果 ===")
        print(f"数据库中共有 {len(all_videos)} 个视频记录")
        
        # 检查哪些记录不在配置文件夹范围内
        invalid_records = []
        valid_records = []
        
        for video_id, file_path, file_name, source_folder in all_videos:
            file_folder = os.path.dirname(file_path)
            is_from_configured_folder = any(file_folder.startswith(configured_folder) for configured_folder in all_configured_folders)
            
            if not is_from_configured_folder:
                invalid_records.append((video_id, file_path, file_name, source_folder))
            else:
                valid_records.append((video_id, file_path, file_name, source_folder))
        
        print(f"有效记录: {len(valid_records)} 个")
        print(f"无效记录: {len(invalid_records)} 个")
        
        if invalid_records:
            print("\n=== 不在配置文件夹范围内的记录 ===")
            for i, (video_id, file_path, file_name, source_folder) in enumerate(invalid_records, 1):
                print(f"{i}. ID: {video_id}")
                print(f"   文件名: {file_name}")
                print(f"   文件路径: {file_path}")
                print(f"   来源文件夹: {source_folder}")
                print(f"   文件存在: {'是' if os.path.exists(file_path) else '否'}")
                print()
            
            # 询问是否删除这些记录
            print(f"\n发现 {len(invalid_records)} 个不在配置文件夹范围内的记录。")
            choice = input("是否要删除这些记录？(y/N): ").strip().lower()
            
            if choice == 'y':
                deleted_count = 0
                for video_id, file_path, file_name, source_folder in invalid_records:
                    cursor.execute("DELETE FROM videos WHERE id = ?", (video_id,))
                    deleted_count += 1
                    print(f"已删除: {file_name}")
                
                conn.commit()
                print(f"\n成功删除 {deleted_count} 个无效记录")
            else:
                print("取消删除操作")
        else:
            print("\n✅ 所有记录都在配置的文件夹范围内，没有需要清理的记录")
        
        # 显示按文件夹分组的统计
        print("\n=== 按来源文件夹统计 ===")
        folder_stats = {}
        for video_id, file_path, file_name, source_folder in valid_records:
            if source_folder not in folder_stats:
                folder_stats[source_folder] = 0
            folder_stats[source_folder] += 1
        
        for folder, count in sorted(folder_stats.items()):
            status = "在线" if os.path.exists(folder) else "离线"
            print(f"{folder}: {count} 个文件 ({status})")
        
    except Exception as e:
        print(f"检查过程中出错: {e}")
    finally:
        conn.close()

def main():
    print("检查数据库中不在配置文件夹范围内的视频记录")
    print(f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    check_invalid_records()

if __name__ == "__main__":
    main()