#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复重复文件检测问题
问题：导入功能中的去重检查使用md5_hash字段，但add_video_to_db函数只设置了file_hash字段
解决方案：将file_hash的值复制到md5_hash字段，或者修改去重逻辑
"""

import sqlite3
import os

def analyze_hash_fields():
    """分析数据库中file_hash和md5_hash字段的情况"""
    db_path = os.path.join(os.path.dirname(__file__), 'media_library.db')
    
    if not os.path.exists(db_path):
        print(f"数据库文件不存在: {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 统计总记录数
        cursor.execute("SELECT COUNT(*) FROM videos")
        total_count = cursor.fetchone()[0]
        print(f"总视频记录数: {total_count}")
        
        # 统计file_hash字段情况
        cursor.execute("SELECT COUNT(*) FROM videos WHERE file_hash IS NOT NULL AND file_hash != ''")
        file_hash_count = cursor.fetchone()[0]
        print(f"有file_hash的记录数: {file_hash_count}")
        
        # 统计md5_hash字段情况
        cursor.execute("SELECT COUNT(*) FROM videos WHERE md5_hash IS NOT NULL AND md5_hash != ''")
        md5_hash_count = cursor.fetchone()[0]
        print(f"有md5_hash的记录数: {md5_hash_count}")
        
        # 统计两个字段都有的记录
        cursor.execute("""
            SELECT COUNT(*) FROM videos 
            WHERE (file_hash IS NOT NULL AND file_hash != '') 
            AND (md5_hash IS NOT NULL AND md5_hash != '')
        """)
        both_hash_count = cursor.fetchone()[0]
        print(f"两个哈希字段都有的记录数: {both_hash_count}")
        
        # 统计两个字段值相同的记录
        cursor.execute("""
            SELECT COUNT(*) FROM videos 
            WHERE file_hash = md5_hash 
            AND file_hash IS NOT NULL AND file_hash != ''
        """)
        same_hash_count = cursor.fetchone()[0]
        print(f"两个哈希字段值相同的记录数: {same_hash_count}")
        
        # 查找只有file_hash没有md5_hash的记录
        cursor.execute("""
            SELECT COUNT(*) FROM videos 
            WHERE (file_hash IS NOT NULL AND file_hash != '') 
            AND (md5_hash IS NULL OR md5_hash = '')
        """)
        only_file_hash_count = cursor.fetchone()[0]
        print(f"只有file_hash没有md5_hash的记录数: {only_file_hash_count}")
        
        # 查找重复的file_hash
        cursor.execute("""
            SELECT file_hash, COUNT(*) as count
            FROM videos 
            WHERE file_hash IS NOT NULL AND file_hash != ''
            GROUP BY file_hash
            HAVING COUNT(*) > 1
            ORDER BY count DESC
        """)
        duplicate_file_hashes = cursor.fetchall()
        print(f"\n重复的file_hash数量: {len(duplicate_file_hashes)}")
        
        if duplicate_file_hashes:
            print("前10个重复的file_hash:")
            for i, (file_hash, count) in enumerate(duplicate_file_hashes[:10]):
                print(f"  {i+1}. {file_hash[:16]}... (重复{count}次)")
                
                # 显示这些重复文件的详细信息
                cursor.execute("""
                    SELECT id, file_name, file_path, file_size
                    FROM videos 
                    WHERE file_hash = ?
                    ORDER BY id
                """, (file_hash,))
                files = cursor.fetchall()
                for video_id, file_name, file_path, file_size in files:
                    print(f"    - ID {video_id}: {file_name} ({file_size} bytes)")
                    print(f"      路径: {file_path}")
                print()
        
        conn.close()
        
    except Exception as e:
        print(f"分析出错: {e}")

def fix_md5_hash_field():
    """修复md5_hash字段：将file_hash的值复制到md5_hash字段"""
    db_path = os.path.join(os.path.dirname(__file__), 'media_library.db')
    
    if not os.path.exists(db_path):
        print(f"数据库文件不存在: {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 查找需要更新的记录
        cursor.execute("""
            SELECT id, file_hash FROM videos 
            WHERE (file_hash IS NOT NULL AND file_hash != '') 
            AND (md5_hash IS NULL OR md5_hash = '')
        """)
        records_to_update = cursor.fetchall()
        
        print(f"需要更新md5_hash字段的记录数: {len(records_to_update)}")
        
        if records_to_update:
            # 确认是否继续
            response = input("是否继续更新？(y/n): ")
            if response.lower() != 'y':
                print("操作已取消")
                return
            
            # 执行更新
            updated_count = 0
            for video_id, file_hash in records_to_update:
                cursor.execute(
                    "UPDATE videos SET md5_hash = ? WHERE id = ?",
                    (file_hash, video_id)
                )
                updated_count += 1
                
                if updated_count % 100 == 0:
                    print(f"已更新 {updated_count}/{len(records_to_update)} 条记录")
            
            conn.commit()
            print(f"成功更新了 {updated_count} 条记录的md5_hash字段")
        else:
            print("没有需要更新的记录")
        
        conn.close()
        
    except Exception as e:
        print(f"修复出错: {e}")

def show_menu():
    """显示菜单"""
    print("\n=== 重复文件检测修复工具 ===")
    print("1. 分析哈希字段情况")
    print("2. 修复md5_hash字段（将file_hash复制到md5_hash）")
    print("3. 退出")
    print()

if __name__ == "__main__":
    while True:
        show_menu()
        choice = input("请选择操作 (1-3): ").strip()
        
        if choice == '1':
            analyze_hash_fields()
        elif choice == '2':
            fix_md5_hash_field()
        elif choice == '3':
            print("退出程序")
            break
        else:
            print("无效选择，请重新输入")