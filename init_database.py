#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YY Media Library - 数据库初始化脚本

这个脚本用于创建一个空的媒体库数据库。
如果数据库已存在，会先备份再重新创建。
"""

import sqlite3
import os
import shutil
from datetime import datetime

def init_empty_database():
    """初始化空的媒体库数据库"""
    db_path = os.path.join(os.path.dirname(__file__), 'media_library.db')
    
    # 如果数据库已存在，先备份
    if os.path.exists(db_path):
        backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(db_path, backup_path)
        print(f"已备份现有数据库到: {backup_path}")
        os.remove(db_path)
    
    # 创建新的空数据库
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 创建videos表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE NOT NULL,
            file_name TEXT NOT NULL,
            file_size INTEGER,
            file_hash TEXT,
            title TEXT,
            description TEXT,
            genre TEXT,
            year INTEGER,
            rating REAL,
            stars INTEGER DEFAULT 0,
            tags TEXT,
            nas_path TEXT,
            is_nas_online BOOLEAN DEFAULT 1,
            thumbnail_data BLOB,
            thumbnail_path TEXT,
            duration INTEGER,
            resolution TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 创建folders表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS folders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folder_path TEXT UNIQUE NOT NULL,
            folder_type TEXT DEFAULT 'local',
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 创建tags表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tag_name TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 创建索引以提高查询性能
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_videos_file_path ON videos(file_path)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_videos_file_hash ON videos(file_hash)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_videos_stars ON videos(stars)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_videos_title ON videos(title)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_folders_path ON folders(folder_path)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tags_name ON tags(tag_name)')
    
    conn.commit()
    conn.close()
    
    print(f"已创建空的媒体库数据库: {db_path}")
    print("数据库包含以下表:")
    print("- videos: 视频文件信息")
    print("- folders: 文件夹配置")
    print("- tags: 标签管理")
    print("\n现在可以运行 media_library.py 开始使用媒体库！")

if __name__ == "__main__":
    init_empty_database()