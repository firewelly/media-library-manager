#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查视频记录的源文件夹路径
"""
import sqlite3
import os

def check_video_folders():
    # 使用正确的数据库路径
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'media_library.db')
    
    print(f"数据库路径: {db_path}")
    if not os.path.exists(db_path):
        print(f"错误：找不到数据库文件 {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 查询指定ID的视频记录
        video_ids = [23140, 34485, 46048]
        
        print("\n===== 视频记录文件夹路径检查 ====")
        
        for video_id in video_ids:
            cursor.execute("""
                SELECT id, file_name, file_path, source_folder 
                FROM videos 
                WHERE id = ?
            """, (video_id,))
            
            video = cursor.fetchone()
            if video:
                vid, file_name, file_path, source_folder = video
                print(f"\n视频ID: {vid}")
                print(f"文件名: {file_name}")
                print(f"文件路径: {file_path}")
                print(f"源文件夹: {source_folder if source_folder else 'None'}")
            else:
                print(f"\n未找到视频ID: {video_id}")
        
        # 查询用户指定的文件夹 /Volumes/Video/usr/ 下的视频数量
        cursor.execute("""
            SELECT COUNT(*) 
            FROM videos 
            WHERE source_folder LIKE ?
        """, ("/Volumes/Video/usr/%",))
        
        count = cursor.fetchone()[0]
        print(f"\n/Volumes/Video/usr/ 文件夹下的视频数量: {count}")
        
    except sqlite3.Error as e:
        print(f"数据库错误: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    check_video_folders()