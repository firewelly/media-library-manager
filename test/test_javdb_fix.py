#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试JAVDB评分转换修复
"""

import sqlite3
import json
from media_library import MediaLibrary

def test_javdb_rating_conversion():
    """测试JAVDB评分转换修复"""
    print("开始测试JAVDB评分转换修复...")
    
    # 创建MediaLibrary实例
    media_lib = MediaLibrary()
    
    # 模拟包含'N/A'评分的JAVDB信息
    test_javdb_info = {
        'video_id': 'CWDV-27',
        'detail_url': 'https://javdb.com/v/test',
        'title': '(CWDV-27) ふんわり雪肌美人 湯けむり 中出し旅行。上原志織',
        'release_date': '2023-01-01',
        'duration': '120分钟',
        'studio': 'Test Studio',
        'rating': 'N/A',  # 这是导致错误的关键
        'cover_image_url': '',
        'local_image_path': '',
        'magnet_links': [],
        'tags': [],
        'actors': []
    }
    
    # 测试视频ID
    video_id = 20929
    
    try:
        # 尝试保存JAVDB信息到数据库
        media_lib.save_javdb_info_to_db(video_id, test_javdb_info)
        print("✓ 成功保存JAVDB信息，rating='N/A'转换修复有效！")
        
        # 验证数据库中的记录
        media_lib.cursor.execute(
            "SELECT score FROM javdb_info WHERE video_id = ?", 
            (video_id,)
        )
        result = media_lib.cursor.fetchone()
        if result:
            score = result[0]
            print(f"✓ 数据库中的score字段值: {score} (应该为None)")
        else:
            print("! 未找到对应的JAVDB记录")
            
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False
    
    finally:
        # 清理测试数据
        try:
            media_lib.cursor.execute(
                "DELETE FROM javdb_info WHERE video_id = ?", 
                (video_id,)
            )
            media_lib.conn.commit()
            print("✓ 清理测试数据完成")
        except:
            pass
        
        # 关闭数据库连接
        media_lib.conn.close()
    
    return True

if __name__ == "__main__":
    test_javdb_rating_conversion()