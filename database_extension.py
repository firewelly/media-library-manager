#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库扩展脚本 - 添加JAVDB相关表
为现有的媒体库数据库添加演员表和JAVDB信息表
"""

import sqlite3
import os
from datetime import datetime

def extend_database():
    """扩展数据库，添加JAVDB相关表"""
    db_path = os.path.join(os.path.dirname(__file__), 'media_library.db')
    
    if not os.path.exists(db_path):
        print(f"错误：找不到数据库文件 {db_path}")
        print("请先运行 init_database.py 创建基础数据库")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 创建演员表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS actors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                name_en TEXT,
                profile_url TEXT,
                avatar_url TEXT,
                local_avatar_path TEXT,
                birth_date TEXT,
                debut_date TEXT,
                height TEXT,
                measurements TEXT,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 创建JAVDB信息表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS javdb_info (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id INTEGER NOT NULL,
                javdb_code TEXT NOT NULL,
                javdb_url TEXT,
                javdb_title TEXT,
                release_date TEXT,
                duration TEXT,
                studio TEXT,
                series TEXT,
                rating TEXT,
                score TEXT,
                cover_url TEXT,
                local_cover_path TEXT,
                cover_image_data BLOB,
                magnet_links TEXT,
                preview_images TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (video_id) REFERENCES videos (id) ON DELETE CASCADE
            )
        ''')
        
        # 创建视频-演员关联表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS video_actors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id INTEGER NOT NULL,
                actor_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (video_id) REFERENCES videos (id) ON DELETE CASCADE,
                FOREIGN KEY (actor_id) REFERENCES actors (id) ON DELETE CASCADE,
                UNIQUE(video_id, actor_id)
            )
        ''')
        
        # 创建JAVDB标签表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS javdb_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tag_name TEXT UNIQUE NOT NULL,
                tag_type TEXT DEFAULT 'general',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 创建JAVDB信息-标签关联表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS javdb_info_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                javdb_info_id INTEGER NOT NULL,
                tag_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (javdb_info_id) REFERENCES javdb_info (id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES javdb_tags (id) ON DELETE CASCADE,
                UNIQUE(javdb_info_id, tag_id)
            )
        ''')
        
        # 创建索引以提高查询性能
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_actors_name ON actors(name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_javdb_info_video_id ON javdb_info(video_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_javdb_info_code ON javdb_info(javdb_code)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_video_actors_video_id ON video_actors(video_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_video_actors_actor_id ON video_actors(actor_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_javdb_tags_name ON javdb_tags(tag_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_javdb_info_tags_javdb_info_id ON javdb_info_tags(javdb_info_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_javdb_info_tags_tag_id ON javdb_info_tags(tag_id)')
        
        # 检查是否需要为videos表添加新字段
        cursor.execute("PRAGMA table_info(videos)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # 添加md5_hash字段（如果不存在）
        if 'md5_hash' not in columns:
            cursor.execute('ALTER TABLE videos ADD COLUMN md5_hash TEXT')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_videos_md5_hash ON videos(md5_hash)')
            print("已添加md5_hash字段到videos表")
        
        # 添加source_folder字段（如果不存在）
        if 'source_folder' not in columns:
            cursor.execute('ALTER TABLE videos ADD COLUMN source_folder TEXT')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_videos_source_folder ON videos(source_folder)')
            print("已添加source_folder字段到videos表")
        
        # 添加file_created_time字段（如果不存在）
        if 'file_created_time' not in columns:
            cursor.execute('ALTER TABLE videos ADD COLUMN file_created_time TIMESTAMP')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_videos_file_created_time ON videos(file_created_time)')
            print("已添加file_created_time字段到videos表")
        
        conn.commit()
        print("数据库扩展完成！")
        print("已添加以下表：")
        print("- actors: 演员信息表")
        print("- javdb_info: JAVDB视频信息表")
        print("- video_actors: 视频-演员关联表")
        print("- javdb_tags: JAVDB标签表")
        print("- javdb_info_tags: JAVDB信息-标签关联表")
        
        return True
        
    except Exception as e:
        print(f"数据库扩展失败: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()

def check_database_structure():
    """检查数据库结构"""
    db_path = os.path.join(os.path.dirname(__file__), 'media_library.db')
    
    if not os.path.exists(db_path):
        print(f"错误：找不到数据库文件 {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 获取所有表名
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        print("当前数据库包含的表：")
        for table in tables:
            table_name = table[0]
            print(f"\n表名: {table_name}")
            
            # 获取表结构
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            
            for column in columns:
                cid, name, type_, notnull, default, pk = column
                print(f"  {name}: {type_}")
                
    except Exception as e:
        print(f"检查数据库结构失败: {e}")
        
    finally:
        conn.close()

if __name__ == "__main__":
    print("JAVDB数据库扩展工具")
    print("=" * 30)
    
    choice = input("请选择操作：\n1. 扩展数据库\n2. 检查数据库结构\n请输入选择 (1/2): ")
    
    if choice == "1":
        if extend_database():
            print("\n数据库扩展成功！现在可以使用JAVDB功能了。")
        else:
            print("\n数据库扩展失败，请检查错误信息。")
    elif choice == "2":
        check_database_structure()
    else:
        print("无效选择")