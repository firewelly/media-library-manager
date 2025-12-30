#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查特定视频的详细信息，包括JAVDB信息和演员信息
"""
import sqlite3
import os

def check_specific_videos():
    # 使用正确的数据库路径
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'media_library.db')
    
    print(f"数据库路径: {db_path}")
    if not os.path.exists(db_path):
        print(f"错误：找不到数据库文件 {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 查询指定ID的视频记录的详细信息
        video_ids = [34485, 46048]
        
        print("\n===== 特定视频详细信息检查 ====")
        
        for video_id in video_ids:
            print(f"\n===== 检查视频ID: {video_id} =====")
            
            # 基本视频信息
            cursor.execute("""
                SELECT id, file_name, file_path, source_folder 
                FROM videos 
                WHERE id = ?
            """, (video_id,))
            
            video = cursor.fetchone()
            if video:
                vid, file_name, file_path, source_folder = video
                print(f"视频ID: {vid}")
                print(f"文件名: {file_name}")
                print(f"文件路径: {file_path}")
                print(f"源文件夹: {source_folder if source_folder else 'None'}")
            else:
                print(f"未找到视频ID: {video_id}")
                continue
            
            # JAVDB信息
            cursor.execute("""
                SELECT id, javdb_code, javdb_url, javdb_title 
                FROM javdb_info 
                WHERE video_id = ?
            """, (video_id,))
            
            javdb_info = cursor.fetchone()
            if javdb_info:
                jid, javdb_code, javdb_url, javdb_title = javdb_info
                print("\nJAVDB信息:")
                print(f"  ID: {jid}")
                print(f"  识别码: {javdb_code}")
                print(f"  URL: {javdb_url}")
                print(f"  标题: {javdb_title[:50]}..." if javdb_title else "  标题: None")
            else:
                print("\n没有找到相关的JAVDB信息")
            
            # 演员信息
            cursor.execute("""
                SELECT a.id, a.name, a.profile_url 
                FROM actors a 
                JOIN video_actors va ON a.id = va.actor_id 
                WHERE va.video_id = ?
            """, (video_id,))
            
            actors = cursor.fetchall()
            if actors:
                print("\n演员信息:")
                for actor_id, name, profile_url in actors:
                    print(f"  演员ID: {actor_id}")
                    print(f"  演员名称: {name}")
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
            
            # 检查用户测试的文件夹下符合更新条件的视频数量
            if video_id == 46048 and source_folder:
                print(f"\n检查文件夹 '{source_folder}' 下符合更新条件的视频数量:")
                
                # 执行与get_videos_to_update函数相同的查询（非refresh_all模式）
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM videos v
                    LEFT JOIN javdb_info j ON v.id = j.video_id
                    WHERE v.source_folder = ? 
                    AND (
                        j.id IS NULL
                        OR NOT EXISTS (
                            SELECT 1 FROM video_actors va 
                            JOIN actors a ON va.actor_id = a.id 
                            WHERE va.video_id = v.id 
                            AND a.profile_url LIKE '%javdb.com%'
                        )
                    )
                """, (source_folder,))
                
                eligible_count = cursor.fetchone()[0]
                print(f"符合更新条件的视频数量: {eligible_count}")
                
                # 显示前3个符合条件的视频ID
                cursor.execute("""
                    SELECT v.id 
                    FROM videos v
                    LEFT JOIN javdb_info j ON v.id = j.video_id
                    WHERE v.source_folder = ? 
                    AND (
                        j.id IS NULL
                        OR NOT EXISTS (
                            SELECT 1 FROM video_actors va 
                            JOIN actors a ON va.actor_id = a.id 
                            WHERE va.video_id = v.id 
                            AND a.profile_url LIKE '%javdb.com%'
                        )
                    )
                    LIMIT 3
                """, (source_folder,))
                
                sample_ids = cursor.fetchall()
                if sample_ids:
                    print(f"符合条件的视频ID示例: {[id[0] for id in sample_ids]}")
    
    except sqlite3.Error as e:
        print(f"数据库错误: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    check_specific_videos()