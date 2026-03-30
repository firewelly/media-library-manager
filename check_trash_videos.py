#!/usr/bin/env python3
"""检查回收站中的视频是否与数据库重复"""

import os
import sqlite3
import hashlib
from pathlib import Path

DB_PATH = "/Users/firewell/bin/media/media_library.db"
TRASH_PATH = Path.home() / ".Trash"

def get_md5(file_path):
    """计算文件的MD5"""
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        print(f"计算MD5失败: {file_path} - {e}")
        return None

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 获取回收站中的所有mp4文件
    trash_files = list(TRASH_PATH.glob("*.mp4"))
    print(f"回收站中共有 {len(trash_files)} 个mp4文件\n")
    
    true_duplicates = []  # 真正重复的（MD5和大小都匹配）
    md5_only_duplicates = []  # 仅MD5匹配
    not_in_db = []  # 数据库中不存在
    
    for i, file_path in enumerate(trash_files):
        if i % 50 == 0:
            print(f"处理进度: {i}/{len(trash_files)}")
        
        try:
            file_size = file_path.stat().st_size
            md5_hash = get_md5(file_path)
            
            if not md5_hash:
                continue
            
            # 检查数据库中是否存在相同MD5和大小的记录
            cursor.execute(
                "SELECT file_path, file_size FROM videos WHERE md5_hash = ? AND file_size = ?",
                (md5_hash, file_size)
            )
            result = cursor.fetchone()
            
            if result:
                true_duplicates.append({
                    'trash_file': str(file_path),
                    'trash_size': file_size,
                    'db_file': result[0],
                    'db_size': result[1],
                    'md5': md5_hash
                })
            else:
                # 检查是否仅MD5匹配
                cursor.execute(
                    "SELECT file_path, file_size FROM videos WHERE md5_hash = ?",
                    (md5_hash,)
                )
                result = cursor.fetchone()
                
                if result:
                    md5_only_duplicates.append({
                        'trash_file': str(file_path),
                        'trash_size': file_size,
                        'db_file': result[0],
                        'db_size': result[1],
                        'md5': md5_hash
                    })
                else:
                    not_in_db.append({
                        'trash_file': str(file_path),
                        'trash_size': file_size,
                        'md5': md5_hash
                    })
        except Exception as e:
            print(f"处理文件失败: {file_path} - {e}")
    
    conn.close()
    
    print("\n" + "="*80)
    print(f"检查结果:")
    print(f"  - 真正重复的（MD5和大小都匹配）: {len(true_duplicates)} 个")
    print(f"  - 仅MD5匹配（大小不同）: {len(md5_only_duplicates)} 个")
    print(f"  - 数据库中不存在（可能是误删）: {len(not_in_db)} 个")
    print("="*80)
    
    # 保存结果到文件
    with open("/Users/firewell/bin/media/trash_check_result.txt", "w", encoding="utf-8") as f:
        f.write(f"检查结果:\n")
        f.write(f"  - 真正重复的（MD5和大小都匹配）: {len(true_duplicates)} 个\n")
        f.write(f"  - 仅MD5匹配（大小不同）: {len(md5_only_duplicates)} 个\n")
        f.write(f"  - 数据库中不存在（可能是误删）: {len(not_in_db)} 个\n\n")
        
        f.write("\n" + "="*80 + "\n")
        f.write("真正重复的文件:\n")
        f.write("="*80 + "\n")
        for item in true_duplicates[:50]:  # 只显示前50个
            f.write(f"\n回收站文件: {Path(item['trash_file']).name}\n")
            f.write(f"  大小: {item['trash_size']:,} bytes\n")
            f.write(f"数据库文件: {Path(item['db_file']).name}\n")
            f.write(f"  大小: {item['db_size']:,} bytes\n")
            f.write(f"  MD5: {item['md5']}\n")
        
        f.write("\n" + "="*80 + "\n")
        f.write("数据库中不存在的文件（可能是误删）:\n")
        f.write("="*80 + "\n")
        for item in not_in_db:
            f.write(f"\n文件: {Path(item['trash_file']).name}\n")
            f.write(f"  大小: {item['trash_size']:,} bytes\n")
            f.write(f"  MD5: {item['md5']}\n")
    
    print(f"\n详细结果已保存到: /Users/firewell/bin/media/trash_check_result.txt")

if __name__ == "__main__":
    main()
