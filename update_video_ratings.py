#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为标题以英文叹号开头的视频文件打分
规则：1个叹号=2分，2个=3分，3个=4分，4个=5分
仅计算文件开头的英文叹号
"""

import sqlite3
import os
import re
from pathlib import Path

def get_database_path():
    """获取数据库路径"""
    # 假设数据库文件在当前目录下
    db_path = os.path.join(os.path.dirname(__file__), "media_library.db")
    if not os.path.exists(db_path):
        print(f"错误: 数据库文件不存在: {db_path}")
        return None
    return db_path

def calculate_stars_from_title(title):
    """
    根据标题开头的英文叹号数量计算星级
    规则：1个叹号=2分，2个=3分，3个=4分，4个=5分
    """
    if not title:
        return 0
    
    # 只计算标题开头的连续英文叹号
    match = re.match(r'^(!+)', title.strip())
    if not match:
        return 0
    
    exclamation_count = len(match.group(1))
    
    # 根据叹号数量计算星级
    if exclamation_count >= 4:
        return 5
    elif exclamation_count == 3:
        return 4
    elif exclamation_count == 2:
        return 3
    elif exclamation_count == 1:
        return 2
    else:
        return 0

def update_video_ratings(dry_run=True):
    """
    更新视频评分
    :param dry_run: 是否为试运行模式，True表示不实际更新数据库
    """
    db_path = get_database_path()
    if not db_path:
        return False
    
    try:
        # 连接数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 查询所有标题以英文叹号开头的视频
        cursor.execute("""
            SELECT id, file_name, title, stars 
            FROM videos 
            WHERE title LIKE '!%' OR file_name LIKE '!%'
        """)
        
        videos = cursor.fetchall()
        
        if not videos:
            print("没有找到标题以英文叹号开头的视频")
            return True
        
        print(f"找到 {len(videos)} 个标题以英文叹号开头的视频")
        
        update_count = 0
        no_change_count = 0
        
        for video_id, file_name, title, current_stars in videos:
            # 优先使用title，如果没有则使用file_name
            video_title = title if title else file_name
            
            # 计算应该设置的星级
            new_stars = calculate_stars_from_title(video_title)
            
            if new_stars == 0:
                continue  # 跳过不符合规则的视频
                
            # 检查是否需要更新
            if current_stars == new_stars:
                no_change_count += 1
                continue
            
            # 显示将要更新的视频信息
            print(f"ID: {video_id}, 文件名: {file_name}")
            print(f"  当前星级: {current_stars}, 新星级: {new_stars}")
            print(f"  标题: {video_title}")
            
            if not dry_run:
                # 更新数据库
                cursor.execute(
                    "UPDATE videos SET stars = ? WHERE id = ?",
                    (new_stars, video_id)
                )
                print(f"  已更新")
            
            update_count += 1
            print()
        
        if not dry_run:
            # 提交事务
            conn.commit()
            print(f"实际更新了 {update_count} 个视频的评分")
        else:
            print(f"[试运行] 将会更新 {update_count} 个视频的评分")
            print(f"[试运行] {no_change_count} 个视频评分无需更改")
        
        # 关闭连接
        conn.close()
        return True
        
    except Exception as e:
        print(f"错误: {e}")
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="为标题以英文叹号开头的视频文件打分")
    parser.add_argument("--execute", action="store_true", help="实际执行更新（默认为试运行模式）")
    
    args = parser.parse_args()
    
    if args.execute:
        print("=== 实际执行模式 ===")
        update_video_ratings(dry_run=False)
    else:
        print("=== 试运行模式 (不会实际更新数据库) ===")
        update_video_ratings(dry_run=True)
        print("\n使用 --execute 参数来实际执行更新")