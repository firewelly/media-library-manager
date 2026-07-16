#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
计算在线文件夹中缺失的md5值
支持断点续传，可以中断后继续运行
"""

import sqlite3
import os
import hashlib
import time
import sys

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'media_library.db')
PROGRESS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.md5_progress.txt')

def calculate_md5(file_path, chunk_size=8192):
    """计算文件的MD5哈希值"""
    try:
        md5_hash = hashlib.md5()
        with open(file_path, "rb") as f:
            while chunk := f.read(chunk_size):
                md5_hash.update(chunk)
        return md5_hash.hexdigest()
    except Exception as e:
        print(f"计算MD5失败 {file_path}: {e}")
        return ""

def load_progress():
    """加载已处理的记录ID"""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r') as f:
            return set(int(line.strip()) for line in f if line.strip())
    return set()

def save_progress(vid):
    """保存已处理的记录ID"""
    with open(PROGRESS_FILE, 'a') as f:
        f.write(f"{vid}\n")

def clear_progress():
    """清除进度文件"""
    if os.path.exists(PROGRESS_FILE):
        os.remove(PROGRESS_FILE)

def main():
    if not os.path.exists(DB_PATH):
        print(f"数据库不存在: {DB_PATH}")
        sys.exit(1)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 获取所有活跃文件夹
    c.execute("SELECT folder_path FROM folders WHERE is_active = 1")
    active_folders = [r[0] for r in c.fetchall()]
    
    # 筛选在线文件夹
    online_folders = [f for f in active_folders if os.path.exists(f)]
    
    print(f'在线文件夹: {len(online_folders)} 个')
    for f in online_folders:
        print(f'  ✅ {f}')
    
    # 构建查询条件
    like_clauses = [f"source_folder LIKE '{f}%'" for f in online_folders]
    where_clause = f"({' OR '.join(like_clauses)})"
    
    # 查询无md5的记录
    c.execute(f"""
        SELECT id, file_path 
        FROM videos 
        WHERE {where_clause} 
          AND (md5_hash IS NULL OR md5_hash = '')
    """)
    all_records = c.fetchall()
    
    # 加载已处理的记录
    processed_ids = load_progress()
    
    # 过滤出未处理的记录
    records = [(vid, fp) for vid, fp in all_records if vid not in processed_ids]
    
    print(f'\n无md5记录总数: {len(all_records)} 个')
    print(f'已处理: {len(processed_ids)} 个')
    print(f'待处理: {len(records)} 个')
    
    if not records:
        print('\n所有记录已处理完成！')
        clear_progress()
        conn.close()
        return
    
    # 计算md5并更新
    updated = 0
    failed = 0
    skipped = 0
    start_time = time.time()
    
    # 使用进度条
    if HAS_TQDM:
        iterator = tqdm(records, desc="计算MD5", unit="条", 
                       bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]')
    else:
        iterator = records
    
    try:
        for i, (vid, file_path) in enumerate(iterator):
            if not file_path or not os.path.exists(file_path):
                skipped += 1
                save_progress(vid)
                continue
            
            md5 = calculate_md5(file_path)
            if md5:
                c.execute("UPDATE videos SET md5_hash = ? WHERE id = ?", (md5, vid))
                conn.commit()  # 每条都提交
                updated += 1
            else:
                failed += 1
            
            save_progress(vid)
            
            # 更新进度条描述
            if HAS_TQDM and (i + 1) % 10 == 0:
                elapsed = time.time() - start_time
                speed = (i + 1) / elapsed if elapsed > 0 else 0
                speed_per_hour = speed * 3600
                iterator.set_description(f"计算MD5 ({speed:.1f}条/秒, {speed_per_hour:.0f}条/小时)")
        
        conn.commit()
        
    except KeyboardInterrupt:
        print('\n\n用户中断，已保存进度。下次运行将继续处理。')
        conn.commit()
        conn.close()
        return
    
    conn.close()
    
    total_time = time.time() - start_time
    print(f'\n=== 完成 ===')
    print(f'已更新: {updated} 个')
    print(f'失败: {failed} 个')
    print(f'跳过(文件不存在): {skipped} 个')
    print(f'总耗时: {total_time:.1f}秒 ({total_time/60:.1f}分钟)')
    
    # 清除进度文件
    clear_progress()

if __name__ == '__main__':
    main()
