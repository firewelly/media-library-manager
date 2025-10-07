#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试按番号刷新特定视频的功能
"""
import os
import sys
import sqlite3

# 数据库路径
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'media_library.db')

def test_refresh_by_code(video_code):
    """测试按番号刷新特定视频的功能"""
    print(f"\n===== 测试按番号刷新特定视频: {video_code} =====")
    
    try:
        # 检查数据库连接
        print(f"连接到数据库: {DB_PATH}")
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 查询该番号的视频信息
        print(f"查询番号为 {video_code} 的视频信息...")
        query = """
            SELECT v.id, v.title, v.file_path, j.javdb_code, j.id as javdb_info_id 
            FROM videos v
            LEFT JOIN javdb_info j ON v.id = j.video_id
            WHERE j.javdb_code = ?
        """
        cursor.execute(query, (video_code,))
        video_info = cursor.fetchone()
        
        if not video_info:
            print(f"错误: 数据库中未找到番号为 {video_code} 的视频")
            conn.close()
            return False
        
        video_id, title, file_path, javdb_code, javdb_info_id = video_info
        print(f"找到视频信息:")
        print(f"- ID: {video_id}")
        print(f"- 标题: {title}")
        print(f"- 文件路径: {file_path}")
        print(f"- JAVDB番号: {javdb_code}")
        print(f"- JAVDB信息ID: {javdb_info_id}")
        
        # 查询该视频的演员信息
        print(f"\n查询该视频的演员信息...")
        actor_query = """
            SELECT a.name, a.profile_url 
            FROM actors a
            JOIN video_actors va ON a.id = va.actor_id
            WHERE va.video_id = ?
        """
        cursor.execute(actor_query, (video_id,))
        actors = cursor.fetchall()
        
        if actors:
            print(f"找到 {len(actors)} 个演员:")
            for actor in actors:
                print(f"- {actor[0]} ({actor[1] if actor[1] else '无链接'})")
        else:
            print("该视频没有演员信息")
        
        # 查询该视频的标签信息（如果表存在）
        print(f"\n查询该视频的标签信息...")
        try:
            tag_query = """
                SELECT t.name 
                FROM tags t
                JOIN video_tags vt ON t.id = vt.tag_id
                WHERE vt.video_id = ?
            """
            cursor.execute(tag_query, (video_id,))
            tags = cursor.fetchall()
            
            if tags:
                print(f"找到 {len(tags)} 个标签:")
                tag_names = [tag[0] for tag in tags]
                print(f"- {', '.join(tag_names)}")
            else:
                print("该视频没有标签信息")
        except sqlite3.OperationalError:
            print("注意: 数据库中可能没有标签相关的表")
        
        conn.close()
        
        # 输出如何使用命令行刷新该视频
        print(f"\n要刷新该视频的信息，请运行以下命令:")
        print(f"python3 javdb_information_updater.py --code {video_code}")
        return True
    
    except sqlite3.Error as e:
        print(f"数据库错误: {e}")
        return False
    except Exception as e:
        print(f"发生错误: {e}")
        return False

if __name__ == "__main__":
    # 默认测试ADN-347
    video_code = "ADN-347"
    
    # 如果命令行提供了番号参数，则使用命令行参数
    if len(sys.argv) > 1:
        video_code = sys.argv[1]
    
    test_refresh_by_code(video_code)