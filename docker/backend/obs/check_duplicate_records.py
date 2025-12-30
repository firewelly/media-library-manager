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

def find_duplicate_records():
    """查找路径和文件名相同但ID不同的记录，特别关注没有源文件夹的记录"""
    try:
        # 连接数据库
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        print("正在连接数据库并查询重复记录...")
        
        # 查询路径和文件名相同但ID不同的记录
        query = '''
        SELECT 
            v1.id, v1.file_path, v1.file_name, v1.source_folder, 
            v2.id, v2.file_path, v2.file_name, v2.source_folder
        FROM videos v1
        JOIN videos v2 ON v1.file_path = v2.file_path 
                      AND v1.file_name = v2.file_name 
                      AND v1.id < v2.id
        WHERE (v1.source_folder IS NULL OR v1.source_folder = '') 
           OR (v2.source_folder IS NULL OR v2.source_folder = '')
        '''
        
        cursor.execute(query)
        duplicates = cursor.fetchall()
        
        if not duplicates:
            print("未找到路径和文件名相同但ID不同且缺少源文件夹的记录")
            return False
        
        print(f"找到 {len(duplicates)} 组重复记录:\n")
        
        # 显示每组重复记录
        for i, record in enumerate(duplicates, 1):
            v1_id, v1_path, v1_name, v1_folder, v2_id, v2_path, v2_name, v2_folder = record
            
            print(f"--- 重复组 {i} ---")
            print(f"记录1: ID={v1_id}, 路径={v1_path}, 文件名={v1_name}, 源文件夹={'(空)' if not v1_folder else v1_folder}")
            print(f"记录2: ID={v2_id}, 路径={v2_path}, 文件名={v2_name}, 源文件夹={'(空)' if not v2_folder else v2_folder}")
            print()
            
        # 询问用户是否需要删除缺少源文件夹的记录
        choice = input("是否要删除所有缺少源文件夹的重复记录？(y/n): ")
        if choice.lower() == 'y':
            delete_missing_folder_records(duplicates, cursor, conn)
        
    except sqlite3.Error as e:
        print(f"数据库错误: {e}")
    finally:
        if conn:
            conn.close()
    
    return len(duplicates) > 0

def delete_missing_folder_records(duplicates, cursor, conn):
    """删除缺少源文件夹的重复记录"""
    try:
        deleted_count = 0
        
        for record in duplicates:
            v1_id, v1_path, v1_name, v1_folder, v2_id, v2_path, v2_name, v2_folder = record
            
            # 确定需要删除的记录ID
            ids_to_delete = []
            if not v1_folder:  # 如果记录1缺少源文件夹
                ids_to_delete.append(v1_id)
            if not v2_folder:  # 如果记录2缺少源文件夹
                ids_to_delete.append(v2_id)
            
            # 执行删除操作
            for video_id in ids_to_delete:
                # 先删除相关联的记录
                cursor.execute("DELETE FROM video_actors WHERE video_id = ?", (video_id,))
                cursor.execute("DELETE FROM javdb_info WHERE video_id = ?", (video_id,))
                cursor.execute("DELETE FROM tags WHERE video_id = ?", (video_id,))
                # 然后删除主记录
                cursor.execute("DELETE FROM videos WHERE id = ?", (video_id,))
                deleted_count += 1
                print(f"已删除记录ID={video_id}, 路径={v1_path}, 文件名={v1_name}")
        
        # 提交事务
        conn.commit()
        print(f"\n成功删除 {deleted_count} 条缺少源文件夹的重复记录")
        
    except sqlite3.Error as e:
        print(f"删除记录时出错: {e}")
        conn.rollback()

def main():
    """主函数"""
    check_database_exists()
    find_duplicate_records()
    print("检查完成")

if __name__ == "__main__":
    main()