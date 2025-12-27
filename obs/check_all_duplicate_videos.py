#!/usr/bin/env python3
import os
import sqlite3
import sys

# 数据库路径
DB_PATH = 'media_library.db'

def check_database_exists():
    """检查数据库文件是否存在"""
    if not os.path.exists(DB_PATH):
        print(f"错误: 数据库文件 {DB_PATH} 不存在")
        sys.exit(1)
    print(f"已找到数据库文件: {DB_PATH}")

def check_videos_table():
    """检查videos表是否存在并显示其结构"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 检查videos表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='videos'")
        table_exists = cursor.fetchone()
        
        if not table_exists:
            print("错误: 数据库中不存在videos表")
            # 显示所有表以帮助调试
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            print("当前数据库包含的表:")
            for table in tables:
                print(f"- {table[0]}")
            conn.close()
            sys.exit(1)
        
        # 显示videos表的结构
        print("\nvideos表结构:")
        cursor.execute("PRAGMA table_info(videos)")
        columns = cursor.fetchall()
        print(f"{'字段名':<20}{'数据类型':<15}{'是否主键':<10}{'其他属性':<15}")
        print("-" * 60)
        for col in columns:
            cid, name, type_, notnull, dflt_value, pk = col
            primary_key = "是" if pk == 1 else "否"
            nullable = "NOT NULL" if notnull == 1 else "NULL"
            print(f"{name:<20}{type_:<15}{primary_key:<10}{nullable:<15}")
        
        # 显示记录总数
        cursor.execute("SELECT COUNT(*) FROM videos")
        total_count = cursor.fetchone()[0]
        print(f"\nvideos表共有 {total_count} 条记录")
        
        conn.close()
        return True
        
    except sqlite3.Error as e:
        print(f"数据库错误: {e}")
        return False

def find_all_duplicate_records():
    """查找所有可能的重复视频记录"""
    try:
        # 连接数据库
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        print("\n正在查询所有可能的重复记录...")
        
        # 1. 根据file_path和file_name查找重复记录
        print("\n1. 检查相同文件路径和文件名的重复记录:")
        query1 = '''
        SELECT 
            v1.id, v1.file_path, v1.file_name, v1.source_folder, 
            v2.id, v2.file_path, v2.file_name, v2.source_folder
        FROM videos v1
        JOIN videos v2 ON v1.file_path = v2.file_path 
                      AND v1.file_name = v2.file_name 
                      AND v1.id < v2.id
        '''
        
        cursor.execute(query1)
        duplicates_by_path = cursor.fetchall()
        
        if not duplicates_by_path:
            print("  未找到相同文件路径和文件名的重复记录")
        else:
            print(f"  找到 {len(duplicates_by_path)} 组相同文件路径和文件名的重复记录")
            # 显示前5组记录作为示例
            for i, record in enumerate(duplicates_by_path[:5], 1):
                v1_id, v1_path, v1_name, v1_folder, v2_id, v2_path, v2_name, v2_folder = record
                
                print(f"  --- 重复组 {i} ---")
                print(f"  记录1: ID={v1_id}, 路径={v1_path}, 文件名={v1_name}, 源文件夹={'(空)' if not v1_folder else v1_folder}")
                print(f"  记录2: ID={v2_id}, 路径={v2_path}, 文件名={v2_name}, 源文件夹={'(空)' if not v2_folder else v2_folder}")
                print()
        
        # 2. 根据md5_hash查找重复记录（如果有md5_hash字段）
        print("\n2. 检查相同MD5哈希值的重复记录:")
        cursor.execute("PRAGMA table_info(videos)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'md5_hash' in columns:
            query2 = '''
            SELECT 
                v1.id, v1.file_path, v1.file_name, v1.md5_hash, 
                v2.id, v2.file_path, v2.file_name, v2.md5_hash
            FROM videos v1
            JOIN videos v2 ON v1.md5_hash = v2.md5_hash 
                          AND v1.md5_hash IS NOT NULL 
                          AND v1.md5_hash != '' 
                          AND v1.id < v2.id
            '''
            
            cursor.execute(query2)
            duplicates_by_md5 = cursor.fetchall()
            
            if not duplicates_by_md5:
                print("  未找到相同MD5哈希值的重复记录")
            else:
                print(f"  找到 {len(duplicates_by_md5)} 组相同MD5哈希值的重复记录")
                # 显示前5组记录作为示例
                for i, record in enumerate(duplicates_by_md5[:5], 1):
                    v1_id, v1_path, v1_name, v1_md5, v2_id, v2_path, v2_name, v2_md5 = record
                    
                    print(f"  --- 重复组 {i} ---")
                    print(f"  记录1: ID={v1_id}, 路径={v1_path}, 文件名={v1_name}, MD5={v1_md5}")
                    print(f"  记录2: ID={v2_id}, 路径={v2_path}, 文件名={v2_name}, MD5={v2_md5}")
                    print()
        else:
            print("  表中不包含md5_hash字段，跳过此项检查")
        
        # 3. 检查缺少source_folder的记录
        print("\n3. 检查缺少源文件夹的记录:")
        query3 = '''
        SELECT id, file_path, file_name FROM videos 
        WHERE source_folder IS NULL OR source_folder = ''
        LIMIT 10
        '''
        
        cursor.execute(query3)
        missing_folder_records = cursor.fetchall()
        
        if not missing_folder_records:
            print("  未找到缺少源文件夹的记录")
        else:
            # 先统计总数
            cursor.execute("SELECT COUNT(*) FROM videos WHERE source_folder IS NULL OR source_folder = ''")
            total_missing = cursor.fetchone()[0]
            print(f"  找到 {total_missing} 条缺少源文件夹的记录")
            # 显示前10条记录作为示例
            print("  前10条示例记录:")
            for i, record in enumerate(missing_folder_records, 1):
                video_id, file_path, file_name = record
                print(f"  {i}. ID={video_id}, 路径={file_path}, 文件名={file_name}")
        
        # 4. 检查特定文件名模式的记录（用户之前提到的ADN-347）
        print("\n4. 检查特定文件名模式的记录:")
        target_pattern = "ADN-347"
        query4 = '''
        SELECT id, file_path, file_name, source_folder FROM videos 
        WHERE file_name LIKE ? OR title LIKE ?
        '''
        
        cursor.execute(query4, (f"%{target_pattern}%", f"%{target_pattern}%"))
        target_records = cursor.fetchall()
        
        if not target_records:
            print(f"  未找到包含 '{target_pattern}' 的记录")
        else:
            print(f"  找到 {len(target_records)} 条包含 '{target_pattern}' 的记录")
            for i, record in enumerate(target_records, 1):
                video_id, file_path, file_name, source_folder = record
                print(f"  {i}. ID={video_id}, 路径={file_path}, 文件名={file_name}, 源文件夹={'(空)' if not source_folder else source_folder}")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"数据库错误: {e}")

def main():
    """主函数"""
    check_database_exists()
    if check_videos_table():
        find_all_duplicate_records()
    print("\n检查完成")

if __name__ == "__main__":
    main()