#!/usr/bin/env python3
"""
测试JavSP复制功能 - 包含附属文件的情况
"""

import sqlite3
import os
import shutil
import tempfile
from utils.javsp_copy import copy_single

def test_copy_with_sidecar_files():
    # 连接到数据库
    conn = sqlite3.connect('media_library.db')
    cursor = conn.cursor()
    
    # 创建临时测试目录
    test_dir = tempfile.mkdtemp(prefix="javsp_sidecar_test_")
    print(f"测试目录: {test_dir}")
    
    try:
        # 找一个有JAVDB信息的视频进行测试
        cursor.execute("""
            SELECT v.id, v.file_path 
            FROM videos v 
            JOIN javdb_info j ON v.id = j.video_id 
            WHERE v.file_path LIKE '%mp42%' 
            LIMIT 1
        """)
        video = cursor.fetchone()
        
        if not video:
            print("未找到有JAVDB信息的测试视频，使用普通视频")
            cursor.execute("SELECT id, file_path FROM videos WHERE file_path LIKE '%mp42%' LIMIT 1")
            video = cursor.fetchone()
        
        if not video:
            print("未找到测试视频")
            return
            
        video_id, old_file_path = video
        video_dir = os.path.dirname(old_file_path)
        base_name = os.path.splitext(os.path.basename(old_file_path))[0]
        
        print(f"测试视频: ID={video_id}, 路径={old_file_path}")
        print(f"视频目录: {video_dir}")
        print(f"基础名称: {base_name}")
        
        # 创建一些模拟的附属文件
        sidecar_files = [
            os.path.join(video_dir, base_name + ".nfo"),
            os.path.join(video_dir, base_name + "-thumb.jpg"),
            os.path.join(video_dir, "poster.jpg"),
            os.path.join(video_dir, "fanart.jpg"),
        ]
        
        # 创建附属目录
        extrafanart_dir = os.path.join(video_dir, "extrafanart")
        if not os.path.exists(extrafanart_dir):
            os.makedirs(extrafanart_dir)
            # 创建一些模拟文件
            for i in range(3):
                with open(os.path.join(extrafanart_dir, f"fanart{i+1}.jpg"), 'w') as f:
                    f.write(f"模拟fanart图片 {i+1}")
        
        # 创建附属文件
        for sidecar_file in sidecar_files:
            if not os.path.exists(sidecar_file):
                with open(sidecar_file, 'w') as f:
                    f.write(f"模拟附属文件: {os.path.basename(sidecar_file)}")
        
        target_dir = os.path.join(test_dir, "target_library")
        
        print(f"\n开始复制测试...")
        result = copy_single(cursor, conn, old_file_path, video_id, target_dir)
        
        if result['ok']:
            print(f"✓ 复制成功！新视频ID: {result['new_video_id']}")
            print(f"✓ 最终路径: {result['final_path']}")
            
            # 验证文件是否存在
            if os.path.exists(result['final_path']):
                print("✓ 主文件存在")
            else:
                print("✗ 主文件不存在")
            
            # 验证附属文件
            target_video_dir = os.path.dirname(result['final_path'])
            print(f"目标视频目录: {target_video_dir}")
            
            for sidecar_file in sidecar_files:
                expected_file = os.path.join(target_video_dir, os.path.basename(sidecar_file))
                if os.path.exists(expected_file):
                    print(f"✓ 附属文件存在: {os.path.basename(sidecar_file)}")
                else:
                    print(f"✗ 附属文件缺失: {os.path.basename(sidecar_file)}")
            
            # 验证extrafanart目录
            expected_extrafanart = os.path.join(target_video_dir, "extrafanart")
            if os.path.exists(expected_extrafanart) and os.path.isdir(expected_extrafanart):
                print("✓ extrafanart目录存在")
                files_in_dir = os.listdir(expected_extrafanart)
                print(f"✓ extrafanart目录中的文件: {files_in_dir}")
            else:
                print("✗ extrafanart目录不存在")
                
        else:
            print(f"✗ 复制失败: {result['error']}")
            import traceback
            traceback.print_exc()
            
    finally:
        # 清理创建的测试附属文件（只清理我们创建的）
        try:
            for sidecar_file in sidecar_files:
                if os.path.exists(sidecar_file) and "模拟附属文件" in open(sidecar_file).read():
                    os.remove(sidecar_file)
            
            if os.path.exists(extrafanart_dir):
                files = os.listdir(extrafanart_dir)
                if all("模拟fanart图片" in open(os.path.join(extrafanart_dir, f)).read() for f in files):
                    shutil.rmtree(extrafanart_dir)
        except Exception as e:
            print(f"清理测试文件时出错: {e}")
        
        # 清理测试目录
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)
            print(f"\n清理测试目录: {test_dir}")
        
        conn.close()

if __name__ == "__main__":
    test_copy_with_sidecar_files()