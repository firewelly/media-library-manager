#!/usr/bin/env python3
import os
import sqlite3
import sys
import shutil
from datetime import datetime

# 数据库路径
DB_PATH = 'media_library.db'

def check_database_exists():
    """检查数据库文件是否存在"""
    if not os.path.exists(DB_PATH):
        print(f"错误: 数据库文件 {DB_PATH} 不存在")
        sys.exit(1)
    print(f"已找到数据库文件: {DB_PATH}")

def get_duplicate_videos_by_path():
    """获取路径和文件名完全相同但ID不同的视频记录"""
    try:
        # 连接数据库
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        print("正在查询路径和文件名完全相同但ID不同的视频记录...")
        
        query = '''
        SELECT 
            v1.id, v1.file_path, v1.file_name, v1.source_folder, v1.created_at, v1.updated_at,
            v2.id, v2.file_path, v2.file_name, v2.source_folder, v2.created_at, v2.updated_at
        FROM videos v1
        JOIN videos v2 ON v1.file_path = v2.file_path 
                      AND v1.file_name = v2.file_name 
                      AND v1.id < v2.id
        '''
        
        cursor.execute(query)
        duplicates = cursor.fetchall()
        
        conn.close()
        return duplicates
        
    except sqlite3.Error as e:
        print(f"数据库错误: {e}")
        return []

def get_duplicate_videos_by_pattern(pattern):
    """获取特定文件名模式的所有视频记录"""
    try:
        # 连接数据库
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        print(f"正在查询包含 '{pattern}' 的所有视频记录...")
        
        query = '''
        SELECT id, file_path, file_name, source_folder, created_at, updated_at 
        FROM videos 
        WHERE file_name LIKE ? OR title LIKE ?
        '''
        
        cursor.execute(query, (f"%{pattern}%", f"%{pattern}%"))
        records = cursor.fetchall()
        
        conn.close()
        return records
        
    except sqlite3.Error as e:
        print(f"数据库错误: {e}")
        return []

def check_file_exists(file_path):
    """检查文件是否真的存在"""
    try:
        return os.path.isfile(file_path)
    except:
        return False

def delete_video_record(video_id):
    """删除视频记录及其相关联的记录"""
    try:
        # 连接数据库
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 先删除相关联的记录
        cursor.execute("DELETE FROM video_actors WHERE video_id = ?", (video_id,))
        cursor.execute("DELETE FROM javdb_info WHERE video_id = ?", (video_id,))
        cursor.execute("DELETE FROM tags WHERE video_id = ?", (video_id,))
        
        # 然后删除主记录
        cursor.execute("DELETE FROM videos WHERE id = ?", (video_id,))
        
        # 提交事务
        conn.commit()
        conn.close()
        return True
        
    except sqlite3.Error as e:
        print(f"删除记录ID={video_id}时出错: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False

def create_backup():
    """创建数据库备份"""
    try:
        backup_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'db_backups')
        os.makedirs(backup_dir, exist_ok=True)
        
        backup_time = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = os.path.join(backup_dir, f'media_library_backup_{backup_time}.db')
        
        shutil.copy2(DB_PATH, backup_path)
        print(f"已创建数据库备份: {backup_path}")
        return backup_path
        
    except Exception as e:
        print(f"创建数据库备份时出错: {e}")
        return None

def process_duplicate_records(duplicates):
    """处理重复记录"""
    if not duplicates:
        print("未找到重复记录")
        return
    
    print(f"找到 {len(duplicates)} 组重复记录")
    
    # 先创建数据库备份
    backup_path = create_backup()
    if not backup_path:
        print("无法创建数据库备份，取消操作")
        return
    
    for i, record in enumerate(duplicates, 1):
        # 如果是通过get_duplicate_videos_by_path获取的记录
        if len(record) == 12:
            v1_id, v1_path, v1_name, v1_folder, v1_created, v1_updated, \
            v2_id, v2_path, v2_name, v2_folder, v2_created, v2_updated = record
            
            print(f"\n--- 重复组 {i} ---")
            print(f"记录1: ID={v1_id}, 路径={v1_path}, 文件名={v1_name}")
            print(f"        源文件夹={'(空)' if not v1_folder else v1_folder}")
            print(f"        创建时间={v1_created}, 更新时间={v1_updated}")
            print(f"        文件存在: {'是' if check_file_exists(v1_path) else '否'}")
            
            print(f"记录2: ID={v2_id}, 路径={v2_path}, 文件名={v2_name}")
            print(f"        源文件夹={'(空)' if not v2_folder else v2_folder}")
            print(f"        创建时间={v2_created}, 更新时间={v2_updated}")
            print(f"        文件存在: {'是' if check_file_exists(v2_path) else '否'}")
            
            # 建议删除哪个记录
            recommendation = """
建议: 请选择要删除的记录。通常，您应该保留源文件夹信息完整且文件实际存在的记录。
如果文件都不存在，建议保留创建时间较新的记录。
"""
            print(recommendation)
            
            # 询问用户要删除哪个记录
            choice = input(f"请选择要删除的记录 (1/2/都不删): ")
            
            if choice == '1':
                if delete_video_record(v1_id):
                    print(f"已删除记录1 (ID={v1_id})")
            elif choice == '2':
                if delete_video_record(v2_id):
                    print(f"已删除记录2 (ID={v2_id})")
            else:
                print("未删除任何记录")
    
def process_specific_duplicates(pattern):
    """处理特定文件名模式的重复记录"""
    records = get_duplicate_videos_by_pattern(pattern)
    
    if len(records) <= 1:
        print(f"未找到包含 '{pattern}' 的重复记录")
        return
    
    print(f"找到 {len(records)} 条包含 '{pattern}' 的记录")
    
    # 先创建数据库备份
    backup_path = create_backup()
    if not backup_path:
        print("无法创建数据库备份，取消操作")
        return
    
    # 显示所有记录
    print("\n所有匹配记录:")
    for i, record in enumerate(records, 1):
        video_id, file_path, file_name, source_folder, created_at, updated_at = record
        print(f"{i}. ID={video_id}, 路径={file_path}, 文件名={file_name}")
        print(f"   源文件夹={'(空)' if not source_folder else source_folder}")
        print(f"   创建时间={created_at}, 更新时间={updated_at}")
        print(f"   文件存在: {'是' if check_file_exists(file_path) else '否'}")
    
    # 询问用户要删除哪些记录
    print("\n建议: 请选择要删除的记录。通常，您应该保留源文件夹信息完整且文件实际存在的记录。")
    choice = input("请输入要删除的记录编号 (多个编号用逗号分隔，如'2,3'; 不删除请按回车): ")
    
    if choice:
        try:
            delete_indices = [int(x.strip()) - 1 for x in choice.split(',')]
            for idx in delete_indices:
                if 0 <= idx < len(records):
                    video_id = records[idx][0]
                    if delete_video_record(video_id):
                        print(f"已删除记录ID={video_id}")
        except ValueError:
            print("输入格式错误，请输入数字编号")

def main():
    """主函数"""
    check_database_exists()
    
    print("\n===== 重复视频记录清理工具 =====")
    print("1. 查找并清理所有路径和文件名相同的重复记录")
    print("2. 查找并清理特定文件名模式的重复记录 (ADN-347)")
    
    choice = input("请选择操作 (1/2): ")
    
    if choice == '1':
        duplicates = get_duplicate_videos_by_path()
        process_duplicate_records(duplicates)
    elif choice == '2':
        process_specific_duplicates("ADN-347")
    else:
        print("无效的选择")
    
    print("\n清理完成")

if __name__ == "__main__":
    main()