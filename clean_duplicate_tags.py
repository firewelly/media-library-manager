#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理数据库中重复标签的脚本
"""

import sqlite3
import os
from datetime import datetime

def clean_duplicate_tags(db_path="media_library.db"):
    """
    清理数据库中videos表的tags字段中的重复标签
    
    Args:
        db_path (str): 数据库文件路径
    """
    if not os.path.exists(db_path):
        print(f"错误：找不到数据库文件 {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 查询所有有标签的视频
        cursor.execute("""
            SELECT id, tags, title, file_name 
            FROM videos 
            WHERE tags IS NOT NULL AND tags != '' AND TRIM(tags) != ''
        """)
        
        videos = cursor.fetchall()
        
        if not videos:
            print("没有找到需要清理的标签数据")
            return True
        
        print(f"找到 {len(videos)} 个视频需要清理标签")
        print("开始清理重复标签...\n")
        
        updated_count = 0
        
        for video_id, tags, title, file_name in videos:
            if not tags:
                continue
                
            # 分割标签并去重
            tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
            
            # 检查是否有重复标签
            unique_tags = []
            seen_tags = set()
            
            for tag in tag_list:
                # 转换为小写进行比较，但保持原始大小写
                tag_lower = tag.lower()
                if tag_lower not in seen_tags:
                    seen_tags.add(tag_lower)
                    unique_tags.append(tag)
            
            # 如果标签数量发生变化，说明有重复
            if len(unique_tags) != len(tag_list):
                # 重新组合标签
                cleaned_tags = ', '.join(unique_tags)
                
                # 更新数据库
                cursor.execute(
                    "UPDATE videos SET tags = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (cleaned_tags, video_id)
                )
                
                updated_count += 1
                print(f"✓ 更新视频 ID {video_id}: {file_name or title or 'Unknown'}")
                print(f"  原标签: {tags}")
                print(f"  新标签: {cleaned_tags}")
                print(f"  去除重复: {len(tag_list) - len(unique_tags)} 个\n")
        
        # 提交更改
        conn.commit()
        conn.close()
        
        print(f"清理完成！")
        print(f"总共处理: {len(videos)} 个视频")
        print(f"更新标签: {updated_count} 个视频")
        print(f"无需更新: {len(videos) - updated_count} 个视频")
        
        return True
        
    except Exception as e:
        print(f"清理标签时发生错误: {e}")
        return False

def preview_duplicate_tags(db_path="media_library.db"):
    """
    预览数据库中有重复标签的视频，不进行实际清理
    
    Args:
        db_path (str): 数据库文件路径
    """
    if not os.path.exists(db_path):
        print(f"错误：找不到数据库文件 {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 查询所有有标签的视频
        cursor.execute("""
            SELECT id, tags, title, file_name 
            FROM videos 
            WHERE tags IS NOT NULL AND tags != '' AND TRIM(tags) != ''
        """)
        
        videos = cursor.fetchall()
        conn.close()
        
        if not videos:
            print("没有找到标签数据")
            return
        
        print(f"检查 {len(videos)} 个视频的标签重复情况...\n")
        
        duplicate_count = 0
        
        for video_id, tags, title, file_name in videos:
            if not tags:
                continue
                
            # 分割标签
            tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
            
            # 检查重复（忽略大小写）
            seen_tags = set()
            duplicates = []
            
            for tag in tag_list:
                tag_lower = tag.lower()
                if tag_lower in seen_tags:
                    duplicates.append(tag)
                else:
                    seen_tags.add(tag_lower)
            
            if duplicates:
                duplicate_count += 1
                print(f"视频 ID {video_id}: {file_name or title or 'Unknown'}")
                print(f"  标签: {tags}")
                print(f"  重复标签: {', '.join(duplicates)}")
                print(f"  重复数量: {len(duplicates)}\n")
        
        print(f"预览完成！")
        print(f"总视频数: {len(videos)}")
        print(f"有重复标签: {duplicate_count} 个视频")
        print(f"无重复标签: {len(videos) - duplicate_count} 个视频")
        
    except Exception as e:
        print(f"预览标签时发生错误: {e}")

def main():
    """
    主函数
    """
    print("数据库标签清理工具")
    print("=" * 50)
    print("1. 预览重复标签")
    print("2. 清理重复标签")
    print("3. 退出")
    
    while True:
        choice = input("\n请选择操作 (1-3): ").strip()
        
        if choice == '1':
            print("\n开始预览重复标签...")
            preview_duplicate_tags()
        elif choice == '2':
            print("\n警告：此操作将修改数据库中的标签数据！")
            confirm = input("确认要清理重复标签吗？(y/N): ").strip().lower()
            if confirm in ['y', 'yes']:
                print("\n开始清理重复标签...")
                clean_duplicate_tags()
            else:
                print("操作已取消")
        elif choice == '3':
            print("退出程序")
            break
        else:
            print("无效选择，请输入 1-3")

if __name__ == "__main__":
    main()