#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import os
import sys
from collections import defaultdict

def merge_csv_files(original_file, reprocessed_file, output_file):
    """
    合并原始分析结果和重新处理的结果，确保每个视频只有一行记录
    """
    # 检查文件是否存在
    for file_path in [original_file, reprocessed_file]:
        if not os.path.exists(file_path):
            print(f"错误: 文件 {file_path} 不存在")
            sys.exit(1)

    # 读取原始文件数据
    original_data = []
    original_md5_map = {}
    original_path_map = {}
    
    try:
        with open(original_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames  # 保存表头
            for i, row in enumerate(reader):
                original_data.append(row)
                # 构建MD5到行索引的映射
                if row['MD5值']:
                    original_md5_map[row['MD5值']] = i
                # 构建文件路径到行索引的映射
                if row['完整路径']:
                    original_path_map[row['完整路径']] = i
    except Exception as e:
        print(f"读取原始文件时出错: {e}")
        sys.exit(1)

    # 读取重新处理的文件数据
    reprocessed_data = []
    try:
        with open(reprocessed_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                reprocessed_data.append(row)
    except Exception as e:
        print(f"读取重新处理文件时出错: {e}")
        sys.exit(1)

    # 统计信息
    total_original = len(original_data)
    total_reprocessed = len(reprocessed_data)
    replaced_count = 0

    # 用重新处理的数据替换原始数据中的失败记录
    for reprocessed_row in reprocessed_data:
        # 优先使用MD5值匹配
        if reprocessed_row['MD5值'] and reprocessed_row['MD5值'] in original_md5_map:
            index = original_md5_map[reprocessed_row['MD5值']]
            original_data[index] = reprocessed_row
            replaced_count += 1
        # 如果MD5不匹配或为空，尝试使用文件路径匹配
        elif reprocessed_row['完整路径'] and reprocessed_row['完整路径'] in original_path_map:
            index = original_path_map[reprocessed_row['完整路径']]
            original_data[index] = reprocessed_row
            replaced_count += 1
        else:
            # 如果都不匹配，添加为新记录
            original_data.append(reprocessed_row)

    # 去重，确保每个视频只有一行记录
    # 使用文件路径作为唯一标识符
    unique_data = {}
    for row in original_data:
        # 如果文件路径不为空，使用文件路径去重
        if row['完整路径']:
            unique_data[row['完整路径']] = row
        # 否则使用MD5值去重
        elif row['MD5值']:
            unique_data[row['MD5值']] = row

    # 转换回列表
    merged_data = list(unique_data.values())

    # 写入合并后的文件
    try:
        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(merged_data)
    except Exception as e:
        print(f"写入合并文件时出错: {e}")
        sys.exit(1)

    # 输出统计信息
    print(f"合并完成！")
    print(f"原始文件记录数: {total_original}")
    print(f"重新处理文件记录数: {total_reprocessed}")
    print(f"成功替换的记录数: {replaced_count}")
    print(f"合并后唯一记录数: {len(merged_data)}")
    print(f"合并结果已保存到: {output_file}")

if __name__ == "__main__":
    # 定义文件路径
    # 使用相对路径以支持不同环境(OneDrive-Personal/OneDrive-个人)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(current_dir) # obs/.. -> media/
    
    original_file = os.path.join(root_dir, "HC530_1_待整理_enhanced_parallel_analysis.csv")
    reprocessed_file = os.path.join(root_dir, "HC530_1_待整理_reprocessed_failed.csv")
    output_file = os.path.join(root_dir, "HC530_1_待整理_merged_analysis.csv")
    
    # 简单的兼容性检查(检查第一个文件)
    if not os.path.exists(original_file):
        root_paths = [
            "/Users/firewell/Library/CloudStorage/OneDrive-Personal/bioinfo/media",
            "/Users/firewell/Library/CloudStorage/OneDrive-个人/bioinfo/media"
        ]
        for r in root_paths:
            if os.path.exists(os.path.join(r, "HC530_1_待整理_enhanced_parallel_analysis.csv")):
                original_file = os.path.join(r, "HC530_1_待整理_enhanced_parallel_analysis.csv")
                reprocessed_file = os.path.join(r, "HC530_1_待整理_reprocessed_failed.csv")
                output_file = os.path.join(r, "HC530_1_待整理_merged_analysis.csv")
                break

    print(f"开始合并CSV文件...")
    print(f"原始文件: {original_file}")
    print(f"重新处理文件: {reprocessed_file}")
    
    merge_csv_files(original_file, reprocessed_file, output_file)