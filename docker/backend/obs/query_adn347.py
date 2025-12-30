#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查询ADN-347.mp4的相关数据库记录
包括视频信息、JAVDB信息和演员信息
"""
import sqlite3
import os

def query_adn347_info():
    # 使用正确的数据库路径
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'media_library.db')
    
    print(f"数据库路径: {db_path}")
    if not os.path.exists(db_path):
        print(f"错误：找不到数据库文件 {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 检查数据库中是否存在videos表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='videos'")
        table_exists = cursor.fetchone()
        if not table_exists:
            print("错误：数据库中不存在videos表")
            
            # 显示所有表以帮助调试
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            print("当前数据库包含的表:")
            for table in tables:
                print(f"- {table[0]}")
            return
        
        # 查询ADN-347相关的视频记录
        print("\n===== 查询ADN-347相关视频记录 ====")
        # 尝试通过文件名查询
        cursor.execute("""
            SELECT id, file_name, title, file_path, source_folder 
            FROM videos 
            WHERE file_name LIKE ? OR title LIKE ?
        """, ("%ADN-347%", "%ADN-347%"))
        
        video_records = cursor.fetchall()
        
        if not video_records:
            print("没有找到ADN-347相关的视频记录")
            return
        
        print(f"找到 {len(video_records)} 条相关视频记录")
        
        for video_id, file_name, title, file_path, source_folder in video_records:
            print(f"\n视频ID: {video_id}")
            print(f"文件名: {file_name}")
            print(f"标题: {title}")
            print(f"文件路径: {file_path}")
            print(f"源文件夹: {source_folder}")
            
            # 查询JAVDB信息
            cursor.execute("""
                SELECT javdb_code, javdb_url, javdb_title, studio 
                FROM javdb_info 
                WHERE video_id = ?
            """, (video_id,))
            javdb_info = cursor.fetchone()
            
            if javdb_info:
                javdb_code, javdb_url, javdb_title, studio = javdb_info
                print("\nJAVDB信息:")
                print(f"  识别码: {javdb_code}")
                print(f"  URL: {javdb_url}")
                print(f"  标题: {javdb_title}")
                print(f"  工作室: {studio}")
            else:
                print("\n没有找到相关的JAVDB信息")
            
            # 查询演员信息
            cursor.execute("""
                SELECT a.id, a.name, a.name_en, a.profile_url 
                FROM actors a 
                JOIN video_actors va ON a.id = va.actor_id 
                WHERE va.video_id = ?
            """, (video_id,))
            actors = cursor.fetchall()
            
            if actors:
                print("\n演员信息:")
                for actor_id, name, name_en, profile_url in actors:
                    print(f"  演员ID: {actor_id}")
                    print(f"  演员名称: {name}")
                    print(f"  英文名称: {name_en}")
                    print(f"  个人主页: {profile_url}")
            else:
                print("\n没有找到相关的演员信息")
            
            # 检查是否有javdb相关的演员链接
            cursor.execute("""
                SELECT COUNT(*) 
                FROM video_actors va 
                JOIN actors a ON va.actor_id = a.id 
                WHERE va.video_id = ? AND a.profile_url LIKE ?
            """, (video_id, "%javdb.com%"))
            javdb_actor_count = cursor.fetchone()[0]
            
            print(f"\n包含JAVDB演员链接的数量: {javdb_actor_count}")
            
    except sqlite3.Error as e:
        print(f"数据库错误: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    query_adn347_info()
