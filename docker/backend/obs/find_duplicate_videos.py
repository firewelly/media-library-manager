#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查找数据库中包含特定关键词的视频并检查MD5值
"""

import sqlite3
import os

def find_videos_by_keyword(keyword):
    """根据关键词查找视频"""
    # 数据库路径
    db_path = os.path.join(os.path.dirname(__file__), 'media_library.db')
    
    if not os.path.exists(db_path):
        print(f"数据库文件不存在: {db_path}")
        return
    
    try:
        # 连接数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 查询包含关键词的视频
        query = """
        SELECT id, file_name, title, file_path, md5_hash, file_hash, file_size
        FROM videos 
        WHERE (file_name LIKE ? OR title LIKE ?)
        ORDER BY file_name
        """
        
        search_pattern = f"%{keyword}%"
        cursor.execute(query, (search_pattern, search_pattern))
        results = cursor.fetchall()
        
        if not results:
            print(f"未找到包含关键词 '{keyword}' 的视频")
            return
        
        print(f"找到 {len(results)} 个包含关键词 '{keyword}' 的视频:")
        print("=" * 100)
        
        for i, (video_id, file_name, title, file_path, md5_hash, file_hash, file_size) in enumerate(results, 1):
            print(f"\n视频 {i}:")
            print(f"  ID: {video_id}")
            print(f"  文件名: {file_name}")
            print(f"  标题: {title or '无'}")
            print(f"  文件路径: {file_path}")
            print(f"  MD5哈希: {md5_hash or '无'}")
            print(f"  文件哈希: {file_hash or '无'}")
            print(f"  文件大小: {file_size} 字节" if file_size else "  文件大小: 未知")
        
        # 检查是否有重复的哈希值
        print("\n" + "=" * 100)
        print("哈希重复检查:")
        
        # 检查MD5哈希重复
        md5_groups = {}
        for video_id, file_name, title, file_path, md5_hash, file_hash, file_size in results:
            if md5_hash:
                if md5_hash not in md5_groups:
                    md5_groups[md5_hash] = []
                md5_groups[md5_hash].append((video_id, file_name, file_path))
        
        # 检查文件哈希重复
        file_hash_groups = {}
        for video_id, file_name, title, file_path, md5_hash, file_hash, file_size in results:
            if file_hash:
                if file_hash not in file_hash_groups:
                    file_hash_groups[file_hash] = []
                file_hash_groups[file_hash].append((video_id, file_name, file_path))
        
        duplicates_found = False
        
        # 显示MD5重复
        for md5_hash, videos in md5_groups.items():
            if len(videos) > 1:
                duplicates_found = True
                print(f"\n发现重复MD5哈希: {md5_hash}")
                for video_id, file_name, file_path in videos:
                    print(f"  - ID {video_id}: {file_name}")
                    print(f"    路径: {file_path}")
        
        # 显示文件哈希重复
        for file_hash, videos in file_hash_groups.items():
            if len(videos) > 1:
                duplicates_found = True
                print(f"\n发现重复文件哈希: {file_hash}")
                for video_id, file_name, file_path in videos:
                    print(f"  - ID {video_id}: {file_name}")
                    print(f"    路径: {file_path}")
        
        if not duplicates_found:
            print("未发现哈希重复的视频")
        
        conn.close()
        
    except Exception as e:
        print(f"查询出错: {e}")

if __name__ == "__main__":
    keyword = "工地献身"
    find_videos_by_keyword(keyword)