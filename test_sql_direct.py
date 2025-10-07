#!/usr/bin/env python3
"""
直接测试SQL查询逻辑，无需导入原模块
"""
import sqlite3
import os

# 数据库路径
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'media_library.db')

if __name__ == "__main__":
    print("===== JAVDB信息更新器SQL查询测试 ====\n")
    
    # 连接数据库
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 测试1：原SQL查询 - 只查找没有JAVDB女演员链接的视频
        print("测试1: 原SQL查询逻辑 (只查找没有JAVDB女演员链接的视频)...")
        old_query = """
            SELECT v.id, v.file_path, v.title, j.javdb_code 
            FROM videos v
            LEFT JOIN javdb_info j ON v.id = j.video_id
            LEFT JOIN video_actors va ON v.id = va.video_id
            LEFT JOIN actors a ON va.actor_id = a.id
            WHERE v.source_folder = ? 
            AND NOT EXISTS (
                SELECT 1 FROM video_actors va2 
                JOIN actors a2 ON va2.actor_id = a2.id 
                WHERE va2.video_id = v.id 
                AND a2.profile_url LIKE '%javdb.com%'
            )
            GROUP BY v.id
        """
        
        test_folder = '/Volumes/app/usr'
        cursor.execute(old_query, (test_folder,))
        old_result = cursor.fetchall()
        print(f"原查询返回 {len(old_result)} 条记录")
        
        # 测试2：新SQL查询 - 查找没有JAVDB信息或没有完整演员信息的视频
        print("\n测试2: 新SQL查询逻辑 (查找没有JAVDB信息或没有完整演员信息的视频)...")
        new_query = """
            SELECT v.id, v.file_path, v.title, j.javdb_code 
            FROM videos v
            LEFT JOIN javdb_info j ON v.id = j.video_id
            WHERE v.source_folder = ? 
            AND (
                j.id IS NULL -- 没有JAVDB信息
                OR NOT EXISTS (
                    SELECT 1 FROM video_actors va 
                    JOIN actors a ON va.actor_id = a.id 
                    WHERE va.video_id = v.id 
                    AND a.profile_url LIKE '%javdb.com%'
                ) -- 没有JAVDB女演员链接
            )
        """
        
        cursor.execute(new_query, (test_folder,))
        new_result = cursor.fetchall()
        print(f"新查询返回 {len(new_result)} 条记录")
        
        # 测试3：直接查询ADN-347视频
        print("\n测试3: 直接查询ADN-347视频信息...")
        cursor.execute("""
            SELECT v.id, v.file_path, v.title, j.javdb_code, a.profile_url 
            FROM videos v 
            LEFT JOIN javdb_info j ON v.id = j.video_id 
            LEFT JOIN video_actors va ON v.id = va.video_id 
            LEFT JOIN actors a ON va.actor_id = a.id 
            WHERE j.javdb_code = 'ADN-347'
        """)
        adn347_videos = cursor.fetchall()
        
        if adn347_videos:
            print(f"找到 {len(adn347_videos)} 个ADN-347视频记录")
            for video in adn347_videos:
                print(f"ID={video[0]}, 标题='{video[2]}', 番号='{video[3]}', 演员链接='{video[4]}'")
        else:
            print("未找到ADN-347视频")
        
    except Exception as e:
        print(f"测试过程中发生错误: {e}")
    finally:
        if conn:
            conn.close()
    
    print("\n===== 测试完成 ====")