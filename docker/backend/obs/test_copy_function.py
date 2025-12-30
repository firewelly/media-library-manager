#!/usr/bin/env python3
"""测试复制功能的脚本"""

import sqlite3
import os
import sys
from utils.javsp_copy import copy_single

def test_copy_function():
    """测试复制功能"""
    # 连接到数据库
    db_path = "media_library.db"
    if not os.path.exists(db_path):
        print(f"数据库文件不存在: {db_path}")
        return
  # 连接数据库
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 选择一个测试视频
        cursor.execute("SELECT id, file_path FROM videos LIMIT 1")
        video = cursor.fetchone()
        if not video:
            print("数据库中没有视频记录")
            return
        
        video_id, old_file_path = video
        print(f"测试视频: ID={video_id}, 路径={old_file_path}")
        
        # 检查文件是否存在
        if not os.path.exists(old_file_path):
            print(f"视频文件不存在: {old_file_path}")
            return
        
        # 设置目标路径
        target_library_path = "/tmp/test_copy_library"
        os.makedirs(target_library_path, exist_ok=True)
        
        # 执行复制操作
        result = copy_single(cursor, conn, old_file_path, video_id, target_library_path)
        
        if result['ok']:
            print(f"复制成功！新视频ID: {result.get('new_video_id', '未知')}")
            new_video_id = result['new_video_id']
            
            # 检查videos表
            cursor.execute("SELECT * FROM videos WHERE id = ?", (new_video_id,))
            new_video = cursor.fetchone()
            if new_video:
                print("✓ videos表记录创建成功")
            
            # 检查演员关联
            cursor.execute("SELECT COUNT(*) FROM video_actors WHERE video_id = ?", (new_video_id,))
            actor_count = cursor.fetchone()[0]
            print(f"✓ 演员关联数量: {actor_count}")
            
            # 检查JAVDB信息
            cursor.execute("SELECT COUNT(*) FROM javdb_info WHERE video_id = ?", (new_video_id,))
            javdb_count = cursor.fetchone()[0]
            print(f"✓ JAVDB信息数量: {javdb_count}")
            
            # 检查JAVDB标签
            if javdb_count > 0:
                cursor.execute("SELECT id FROM javdb_info WHERE video_id = ?", (new_video_id,))
                javdb_info_id = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM javdb_info_tags WHERE javdb_info_id = ?", (javdb_info_id,))
                tag_count = cursor.fetchone()[0]
                print(f"✓ JAVDB标签数量: {tag_count}")
            
        else:
            print(f"复制失败: {result['error']}")
            import traceback
            traceback.print_exc()
    
    except Exception as e:
        print(f"测试过程中出现错误: {e}")
    
    finally:
        conn.close()

if __name__ == "__main__":
    test_copy_function()