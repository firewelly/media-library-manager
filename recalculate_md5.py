#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重新计算数据库中md5_hash为空的记录
"""

import sqlite3
import os
import hashlib
import time
from datetime import datetime

# 数据库路径
DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'media_library.db')

def calculate_md5_hash(file_path):
    """计算文件的MD5哈希值"""
    if not os.path.exists(file_path):
        return None
    
    try:
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            # 分块读取文件以处理大文件
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        print(f"计算MD5失败 {file_path}: {e}")
        return None

def recalculate_empty_md5_hashes(batch_size=50, dry_run=False):
    """重新计算md5_hash为空的记录
    
    Args:
        batch_size (int): 批处理大小
        dry_run (bool): 是否为预览模式，不实际执行更新
    """
    if not os.path.exists(DATABASE_PATH):
        print(f"数据库文件不存在: {DATABASE_PATH}")
        return False
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    try:
        # 查询md5_hash为空的记录
        cursor.execute("""
            SELECT id, file_path, file_name, file_size 
            FROM videos 
            WHERE md5_hash IS NULL OR md5_hash = ''
            ORDER BY id
        """)
        
        empty_records = cursor.fetchall()
        
        if not empty_records:
            print("没有找到需要重新计算MD5的记录")
            return True
        
        total_records = len(empty_records)
        print(f"找到 {total_records} 条需要重新计算MD5的记录")
        print(f"模式: {'预览模式' if dry_run else '执行模式'}")
        print(f"批处理大小: {batch_size}")
        print("=" * 60)
        
        success_count = 0
        failed_count = 0
        skipped_count = 0
        start_time = time.time()
        
        # 分批处理记录
        for i in range(0, total_records, batch_size):
            batch = empty_records[i:i + batch_size]
            batch_updates = []
            
            print(f"\n处理批次 {i//batch_size + 1}/{(total_records + batch_size - 1)//batch_size}")
            print(f"记录范围: {i+1}-{min(i+batch_size, total_records)}")
            
            for record_id, file_path, file_name, file_size in batch:
                print(f"\n处理记录 ID: {record_id}")
                print(f"文件: {file_name}")
                print(f"路径: {file_path}")
                
                # 检查文件是否存在
                if not file_path or not os.path.exists(file_path):
                    print(f"  ❌ 文件不存在，跳过")
                    skipped_count += 1
                    continue
                
                # 计算MD5哈希
                print(f"  🔄 计算MD5哈希...")
                md5_hash = calculate_md5_hash(file_path)
                
                if md5_hash:
                    print(f"  ✅ MD5: {md5_hash}")
                    if not dry_run:
                        batch_updates.append((md5_hash, record_id))
                    success_count += 1
                else:
                    print(f"  ❌ MD5计算失败")
                    failed_count += 1
            
            # 批量更新数据库
            if batch_updates and not dry_run:
                try:
                    cursor.executemany(
                        "UPDATE videos SET md5_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        batch_updates
                    )
                    conn.commit()
                    print(f"  💾 批次更新完成: {len(batch_updates)} 条记录")
                except Exception as e:
                    print(f"  ❌ 批次更新失败: {e}")
                    conn.rollback()
                    failed_count += len(batch_updates)
                    success_count -= len(batch_updates)
            
            # 显示进度
            processed = min(i + batch_size, total_records)
            progress = (processed / total_records) * 100
            elapsed_time = time.time() - start_time
            avg_time_per_record = elapsed_time / processed if processed > 0 else 0
            estimated_remaining = avg_time_per_record * (total_records - processed)
            
            print(f"\n📊 进度: {processed}/{total_records} ({progress:.1f}%)")
            print(f"⏱️  已用时间: {elapsed_time:.1f}秒")
            if estimated_remaining > 0:
                print(f"⏳ 预计剩余: {estimated_remaining:.1f}秒")
            
            # 短暂休息以避免过度占用系统资源
            if i + batch_size < total_records:
                time.sleep(0.1)
        
        # 最终统计
        total_time = time.time() - start_time
        print("\n" + "=" * 60)
        print("📈 最终统计:")
        print(f"总记录数: {total_records}")
        print(f"成功处理: {success_count}")
        print(f"失败: {failed_count}")
        print(f"跳过: {skipped_count}")
        print(f"总用时: {total_time:.1f}秒")
        print(f"平均每条记录: {total_time/total_records:.2f}秒")
        
        if not dry_run and success_count > 0:
            print(f"\n✅ 已成功更新 {success_count} 条记录的MD5哈希值")
        elif dry_run:
            print(f"\n🔍 预览模式完成，实际执行时将更新 {success_count} 条记录")
        
        return success_count > 0
        
    except Exception as e:
        print(f"处理过程中出错: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def main():
    """主函数"""
    print("MD5哈希重新计算工具")
    print("=" * 30)
    
    # 首先运行预览模式
    print("\n🔍 运行预览模式...")
    if recalculate_empty_md5_hashes(batch_size=10, dry_run=True):
        # 询问用户是否继续执行
        response = input("\n是否继续执行实际更新？(y/N): ").strip().lower()
        if response in ['y', 'yes', '是']:
            print("\n🚀 开始执行实际更新...")
            recalculate_empty_md5_hashes(batch_size=50, dry_run=False)
        else:
            print("\n❌ 用户取消操作")
    else:
        print("\n❌ 预览模式失败")

if __name__ == "__main__":
    main()