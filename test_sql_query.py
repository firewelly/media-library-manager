#!/usr/bin/env python3
"""
测试脚本：直接测试get_videos_without_actors函数的SQL查询逻辑
"""
import os
import sys

# 确保可以导入当前目录的模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入get_videos_without_actors函数
sys.modules['selenium'] = type('obj', (object,), {})
from javdb_information_updater import get_videos_without_actors, DB_PATH
import sqlite3

if __name__ == "__main__":
    print("===== JAVDB信息更新器SQL查询测试 ====\n")
    
    # 测试1：获取指定文件夹下需要更新的视频列表
    test_folder = '/Volumes/app/usr'
    print(f"测试1: 查询文件夹 '{test_folder}' 下需要更新的视频...")
    videos = get_videos_without_actors(test_folder)
    
    if videos:
        print(f"找到 {len(videos)} 个需要更新的视频")
        # 打印前5个视频作为示例
        for i, video in enumerate(videos[:5]):
            print(f"视频 {i+1}: ID={video['id']}, 标题='{video['title']}', 番号='{video['av_code']}'")
    else:
        print("没有找到需要更新的视频")
    
    print("\n测试2: 直接查询ADN-347视频信息...")
    # 直接查询数据库中的ADN-347视频
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT v.id, v.file_path, v.title, j.javdb_code, a.profile_url 
        FROM videos v 
        LEFT JOIN javdb_info j ON v.id = j.video_id 
        LEFT JOIN video_actors va ON v.id = va.video_id 
        LEFT JOIN actors a ON va.actor_id = a.id 
        WHERE j.javdb_code = 'ADN-347'
    """)
    adn347_videos = cursor.fetchall()
    conn.close()
    
    if adn347_videos:
        print(f"找到 {len(adn347_videos)} 个ADN-347视频记录")
        for video in adn347_videos:
            print(f"ID={video[0]}, 标题='{video[2]}', 番号='{video[3]}', 演员链接='{video[4]}'")
    else:
        print("未找到ADN-347视频")
    
    print("\n===== 测试完成 ====")