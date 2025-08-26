#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试JAVDB爬虫与媒体库的集成
"""

import sqlite3
import os
import json
import subprocess
from code_extractor import CodeExtractor

def test_integration():
    """测试完整的集成流程"""
    print("=== JAVDB爬虫与媒体库集成测试 ===")
    
    # 1. 测试番号提取
    print("\n1. 测试番号提取功能")
    extractor = CodeExtractor()
    test_filename = "IPZZ-565.mp4"
    av_code = extractor.extract_code_from_filename(test_filename)
    print(f"文件名: {test_filename}")
    print(f"提取的番号: {av_code}")
    
    if not av_code:
        print("❌ 番号提取失败")
        return False
    print("✅ 番号提取成功")
    
    # 2. 测试JAVDB信息爬取
    print(f"\n2. 测试JAVDB信息爬取 ({av_code})")
    try:
        cmd = ["python", "javdb_crawler_single.py", av_code]
        process = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if process.returncode == 0 and process.stdout:
            try:
                javdb_info = json.loads(process.stdout)
                if "error" in javdb_info:
                    print(f"❌ JAVDB爬取失败: {javdb_info['error']}")
                    return False
                else:
                    print("✅ JAVDB信息爬取成功")
                    print(f"  标题: {javdb_info.get('title', 'N/A')}")
                    print(f"  评分: {javdb_info.get('rating', 'N/A')}")
                    print(f"  发布日期: {javdb_info.get('release_date', 'N/A')}")
                    print(f"  演员数量: {len(javdb_info.get('actors', []))}")
                    print(f"  标签数量: {len(javdb_info.get('tags', []))}")
            except json.JSONDecodeError as e:
                print(f"❌ JSON解析失败: {e}")
                print(f"原始输出: {process.stdout[:200]}...")
                return False
        else:
            print(f"❌ JAVDB爬取失败")
            print(f"返回码: {process.returncode}")
            print(f"错误输出: {process.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("❌ JAVDB爬取超时")
        return False
    except Exception as e:
        print(f"❌ JAVDB爬取异常: {e}")
        return False
    
    # 3. 测试数据库连接和结构
    print("\n3. 测试数据库连接和结构")
    try:
        conn = sqlite3.connect('media_library.db')
        cursor = conn.cursor()
        
        # 检查必要的表是否存在
        required_tables = ['videos', 'javdb_info', 'actors', 'video_actors', 'javdb_tags', 'javdb_info_tags']
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = [row[0] for row in cursor.fetchall()]
        
        missing_tables = [table for table in required_tables if table not in existing_tables]
        if missing_tables:
            print(f"❌ 缺少数据库表: {missing_tables}")
            print("请运行 database_extension.py 来创建必要的表")
            return False
        
        print("✅ 数据库结构检查通过")
        print(f"  现有表: {existing_tables}")
        
        # 4. 测试数据库写入
        print("\n4. 测试数据库写入")
        
        # 插入测试视频记录
        test_video_path = os.path.abspath(test_filename)
        cursor.execute("""
            INSERT OR REPLACE INTO videos (file_path, file_name, file_size, duration, created_at)
            VALUES (?, ?, ?, ?, datetime('now'))
        """, (test_video_path, test_filename, 1024, 3600))
        
        video_id = cursor.lastrowid
        print(f"✅ 测试视频记录已插入，ID: {video_id}")
        
        # 测试JAVDB信息保存（模拟media_library.py中的save_javdb_info_to_db方法）
        cursor.execute("""
            INSERT OR REPLACE INTO javdb_info 
            (video_id, javdb_code, javdb_title, release_date, duration, score, studio, 
             cover_url, local_cover_path, javdb_url, magnet_links)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            video_id,
            javdb_info.get('video_id'),  # 番号
            javdb_info.get('title'),
            javdb_info.get('release_date'),
            javdb_info.get('duration'),
            float(javdb_info.get('rating', 0)) if javdb_info.get('rating') else None,  # JAVDB评分存储到score列
            javdb_info.get('studio'),
            javdb_info.get('cover_image_url'),
            javdb_info.get('local_image_path'),
            javdb_info.get('detail_url'),
            json.dumps(javdb_info.get('magnet_links', []))
        ))
        
        print("✅ JAVDB信息已保存到数据库")
        
        # 保存演员信息
        actors = javdb_info.get('actors', [])
        for actor in actors:
            actor_name = actor.get('name') if isinstance(actor, dict) else actor
            cursor.execute("""
                INSERT OR IGNORE INTO actors (name) VALUES (?)
            """, (actor_name,))
            
            cursor.execute("SELECT id FROM actors WHERE name = ?", (actor_name,))
            actor_id = cursor.fetchone()[0]
            
            cursor.execute("""
                INSERT OR IGNORE INTO video_actors (video_id, actor_id) VALUES (?, ?)
            """, (video_id, actor_id))
        
        print(f"✅ 演员信息已保存 ({len(actors)} 个演员)")
        
        # 保存标签信息
        tags = javdb_info.get('tags', [])
        for tag in tags:
            cursor.execute("""
                INSERT OR IGNORE INTO javdb_tags (tag_name) VALUES (?)
            """, (tag,))
            
            cursor.execute("SELECT id FROM javdb_tags WHERE tag_name = ?", (tag,))
            tag_id = cursor.fetchone()[0]
            
            cursor.execute("""
                INSERT OR IGNORE INTO javdb_info_tags (javdb_info_id, tag_id) VALUES (
                    (SELECT id FROM javdb_info WHERE video_id = ?), ?
                )
            """, (video_id, tag_id))
        
        print(f"✅ 标签信息已保存 ({len(tags)} 个标签)")
        
        conn.commit()
        
        # 5. 验证数据完整性
        print("\n5. 验证数据完整性")
        
        # 查询保存的数据
        cursor.execute("""
            SELECT v.file_name, j.javdb_title, j.score, j.release_date
            FROM videos v
            LEFT JOIN javdb_info j ON v.id = j.video_id
            WHERE v.id = ?
        """, (video_id,))
        
        result = cursor.fetchone()
        if result:
            print(f"✅ 数据验证成功")
            print(f"  文件名: {result[0]}")
            print(f"  标题: {result[1]}")
            print(f"  评分: {result[2]}")
            print(f"  发布日期: {result[3]}")
        else:
            print("❌ 数据验证失败")
            return False
        
        conn.close()
        
    except Exception as e:
        print(f"❌ 数据库操作失败: {e}")
        return False
    
    print("\n=== 集成测试完成 ===")
    print("✅ 所有测试通过！JAVDB爬虫与媒体库集成正常工作")
    return True

if __name__ == "__main__":
    success = test_integration()
    exit(0 if success else 1)