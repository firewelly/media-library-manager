#!/usr/bin/env python3
"""
综合测试JavSP复制功能
测试两种情况：
1. 复制到新位置
2. 复制到已存在文件的位置（合并模式）
"""

import sqlite3
import os
import shutil
import tempfile
from utils.javsp_copy import copy_single

def test_copy_comprehensive():
    # 连接到数据库
    conn = sqlite3.connect('media_library.db')
    cursor = conn.cursor()
    
    # 创建临时测试目录
    test_dir = tempfile.mkdtemp(prefix="javsp_copy_test_")
    print(f"测试目录: {test_dir}")
    
    try:
        # 测试1: 复制到新位置
        print("\n=== 测试1: 复制到新位置 ===")
        cursor.execute("SELECT id, file_path FROM videos WHERE file_path LIKE '%mp42%' LIMIT 1")
        video = cursor.fetchone()
        
        if not video:
            print("未找到测试视频")
            return
            
        video_id, old_file_path = video
        target_dir = os.path.join(test_dir, "new_location")
        
        print(f"测试视频: ID={video_id}, 路径={old_file_path}")
        
        result = copy_single(cursor, conn, old_file_path, video_id, target_dir)
        
        if result['ok']:
            print(f"✓ 复制成功！新视频ID: {result['new_video_id']}")
            print(f"✓ 最终路径: {result['final_path']}")
            print(f"✓ 合并模式: {result.get('merged', False)}")
            
            # 验证数据库记录
            new_video_id = result['new_video_id']
            cursor.execute("SELECT * FROM videos WHERE id = ?", (new_video_id,))
            new_video = cursor.fetchone()
            if new_video:
                print("✓ videos表记录创建成功")
            
            # 验证演员关联
            cursor.execute("SELECT COUNT(*) FROM video_actors WHERE video_id = ?", (new_video_id,))
            actor_count = cursor.fetchone()[0]
            print(f"✓ 演员关联数量: {actor_count}")
            
            # 验证JAVDB信息
            cursor.execute("SELECT COUNT(*) FROM javdb_info WHERE video_id = ?", (new_video_id,))
            javdb_count = cursor.fetchone()[0]
            print(f"✓ JAVDB信息数量: {javdb_count}")
            
            # 验证JAVDB标签
            if javdb_count > 0:
                cursor.execute("SELECT id FROM javdb_info WHERE video_id = ?", (new_video_id,))
                javdb_info_id = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM javdb_info_tags WHERE javdb_info_id = ?", (javdb_info_id,))
                tag_count = cursor.fetchone()[0]
                print(f"✓ JAVDB标签数量: {tag_count}")
            
            # 测试2: 复制到已存在文件的位置（合并模式）
            print("\n=== 测试2: 复制到已存在位置（合并模式） ===")
            
            # 使用相同的目标目录，应该触发合并模式
            result2 = copy_single(cursor, conn, old_file_path, video_id, target_dir)
            
            if result2['ok']:
                print(f"✓ 合并成功！新视频ID: {result2['new_video_id']}")
                print(f"✓ 最终路径: {result2['final_path']}")
                print(f"✓ 合并模式: {result2.get('merged', False)}")
                
                # 验证文件是否存在
                if os.path.exists(result2['final_path']):
                    print("✓ 文件存在")
                else:
                    print("✗ 文件不存在")
                    
            else:
                print(f"✗ 合并失败: {result2['error']}")
                import traceback
                traceback.print_exc()
        else:
            print(f"✗ 复制失败: {result['error']}")
            import traceback
            traceback.print_exc()
            
    finally:
        # 清理测试目录
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)
            print(f"\n清理测试目录: {test_dir}")
        
        conn.close()

if __name__ == "__main__":
    test_copy_comprehensive()