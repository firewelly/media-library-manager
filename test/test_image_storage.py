#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试图片存储功能
验证从爬虫JSON读取本地图片路径，并将图片二进制数据存储到数据库
"""

import json
import sqlite3
import os
from datetime import datetime

def test_image_storage():
    """测试图片存储功能"""
    # 模拟从javdb_crawler_single.py获取的JSON数据
    javdb_info = {
        "title": "IPZZ-565 俺のことが昔から大好きな幼馴染に1ヶ月の禁欲をさせて彼女不在中にハメまくった甘くも切ない3日間 愛才りあ （ブルーレイディスク） 生写真3枚付き",
        "video_id": "IPZZ-565",
        "detail_url": "https://javdb.com/v/r3PNeD",
        "release_date": "2025-06-11",
        "duration": "120 分鍾",
        "rating": "3.97",
        "studio": "IDEA POCKET",
        "cover_image_url": "https://c0.jdbstatic.com/covers/r3/r3PNeD.jpg",
        "local_image_path": "results/images/IPZZ-565_IPZZ-565 俺のことが昔から大好きな幼馴染に1ヶ月の禁欲をさせて彼女不在中にハメまくった甘くも切ない3日間 愛才りあ （ブルーレイディスク） 生写真3枚付き",
        "magnet_links": []
    }
    
    # 连接数据库
    db_path = 'media_library.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 读取本地图片文件并转换为二进制数据
        cover_image_data = None
        local_image_path = javdb_info.get('local_image_path', '')
        
        if local_image_path and os.path.exists(local_image_path):
            try:
                with open(local_image_path, 'rb') as f:
                    cover_image_data = f.read()
                print(f"✓ 成功读取图片文件: {local_image_path}")
                print(f"✓ 图片大小: {len(cover_image_data)} 字节")
            except Exception as e:
                print(f"✗ 读取图片文件失败 {local_image_path}: {e}")
                return False
        else:
            print(f"✗ 图片文件不存在: {local_image_path}")
            return False
        
        # 插入测试数据到javdb_info表
        cursor.execute("""
            INSERT OR REPLACE INTO javdb_info 
            (video_id, javdb_code, javdb_url, javdb_title, release_date, duration, 
             studio, score, cover_url, local_cover_path, cover_image_data, magnet_links, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
        """, (
            999,  # 测试用的video_id
            javdb_info.get('video_id', ''),
            javdb_info.get('detail_url', ''),
            javdb_info.get('title', ''),
            javdb_info.get('release_date', ''),
            javdb_info.get('duration', ''),
            javdb_info.get('studio', ''),
            float(javdb_info.get('rating', 0)) if javdb_info.get('rating') else None,
            javdb_info.get('cover_image_url', ''),
            javdb_info.get('local_image_path', ''),
            cover_image_data,
            json.dumps(javdb_info.get('magnet_links', []), ensure_ascii=False)
        ))
        
        conn.commit()
        print("✓ 成功将图片二进制数据存储到数据库")
        
        # 验证数据是否正确存储
        cursor.execute("""
            SELECT javdb_code, javdb_title, cover_image_data 
            FROM javdb_info 
            WHERE video_id = 999
        """)
        
        result = cursor.fetchone()
        if result:
            code, title, stored_image_data = result
            print(f"✓ 验证成功 - 代码: {code}")
            print(f"✓ 验证成功 - 标题: {title[:50]}...")
            if stored_image_data:
                print(f"✓ 验证成功 - 存储的图片大小: {len(stored_image_data)} 字节")
                print(f"✓ 图片数据完整性: {'通过' if len(stored_image_data) == len(cover_image_data) else '失败'}")
            else:
                print("✗ 验证失败 - 图片数据为空")
                return False
        else:
            print("✗ 验证失败 - 未找到插入的数据")
            return False
            
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    print("开始测试图片存储功能...")
    print("=" * 50)
    
    success = test_image_storage()
    
    print("=" * 50)
    if success:
        print("🎉 测试通过！图片存储功能正常工作")
    else:
        print("❌ 测试失败！请检查错误信息")