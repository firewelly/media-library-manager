#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
演员表扩展脚本 - 添加详细信息字段
为actors表添加繁体中文名、常用名、别名、头像等字段
"""

import sqlite3
import os
from datetime import datetime

def extend_actors_table():
    """扩展actors表，添加详细信息字段"""
    db_path = os.path.join(os.path.dirname(__file__), 'media_library.db')
    
    if not os.path.exists(db_path):
        print(f"错误：找不到数据库文件 {db_path}")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 检查actors表现有字段
        cursor.execute("PRAGMA table_info(actors)")
        columns = [column[1] for column in cursor.fetchall()]
        print(f"当前actors表字段: {columns}")
        
        # 添加繁体中文名字段
        if 'name_traditional' not in columns:
            cursor.execute('ALTER TABLE actors ADD COLUMN name_traditional TEXT')
            print("已添加name_traditional字段（繁体中文名）")
        
        # 添加常用名字段
        if 'name_common' not in columns:
            cursor.execute('ALTER TABLE actors ADD COLUMN name_common TEXT')
            print("已添加name_common字段（常用名）")
        
        # 添加别名字段（用逗号分隔的字符串）
        if 'aliases' not in columns:
            cursor.execute('ALTER TABLE actors ADD COLUMN aliases TEXT')
            print("已添加aliases字段（别名，逗号分隔）")
        
        # 添加头像二进制数据字段
        if 'avatar_data' not in columns:
            cursor.execute('ALTER TABLE actors ADD COLUMN avatar_data BLOB')
            print("已添加avatar_data字段（头像二进制数据）")
        
        # 添加参演影片数量字段
        if 'movie_count' not in columns:
            cursor.execute('ALTER TABLE actors ADD COLUMN movie_count INTEGER DEFAULT 0')
            print("已添加movie_count字段（参演影片数量）")
        
        # 添加最后爬取时间字段
        if 'last_crawled_at' not in columns:
            cursor.execute('ALTER TABLE actors ADD COLUMN last_crawled_at TIMESTAMP')
            print("已添加last_crawled_at字段（最后爬取时间）")
        
        # 创建新的索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_actors_name_traditional ON actors(name_traditional)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_actors_name_common ON actors(name_common)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_actors_last_crawled ON actors(last_crawled_at)')
        
        conn.commit()
        print("\n演员表扩展完成！")
        print("已添加以下字段：")
        print("- name_traditional: 繁体中文名")
        print("- name_common: 常用名")
        print("- aliases: 别名（逗号分隔）")
        print("- avatar_data: 头像二进制数据")
        print("- movie_count: 参演影片数量")
        print("- last_crawled_at: 最后爬取时间")
        
        return True
        
    except Exception as e:
        print(f"演员表扩展失败: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()

def create_actor_movies_table():
    """创建演员参演影片表"""
    db_path = os.path.join(os.path.dirname(__file__), 'media_library.db')
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 创建演员参演影片表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS actor_movies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_id INTEGER NOT NULL,
                movie_title TEXT NOT NULL,
                movie_url TEXT,
                javdb_code TEXT,
                release_date TEXT,
                has_magnet BOOLEAN DEFAULT 0,
                magnet_links TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (actor_id) REFERENCES actors (id) ON DELETE CASCADE,
                UNIQUE(actor_id, javdb_code)
            )
        ''')
        
        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_actor_movies_actor_id ON actor_movies(actor_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_actor_movies_javdb_code ON actor_movies(javdb_code)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_actor_movies_has_magnet ON actor_movies(has_magnet)')
        
        conn.commit()
        print("演员参演影片表创建完成！")
        
        return True
        
    except Exception as e:
        print(f"创建演员参演影片表失败: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    print("开始扩展演员表...")
    if extend_actors_table():
        print("\n创建演员参演影片表...")
        create_actor_movies_table()
        print("\n所有数据库扩展完成！")
    else:
        print("演员表扩展失败！")