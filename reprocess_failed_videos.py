#!/usr/bin/env python3
"""
重新处理失败的视频文件脚本
从CSV文件中提取失败的文件，重新进行分析
"""

import pandas as pd
import os
import sys
from batch_video_analyzer_enhanced import EnhancedBatchVideoAnalyzer

def extract_failed_files(csv_path: str) -> list:
    """从CSV文件中提取失败的文件路径"""
    try:
        df = pd.read_csv(csv_path)
        
        # 查找失败的文件（包含超时和错误的）
        failed_mask = (
            df['错误信息'].str.contains('超时', na=False) |
            df['错误信息'].str.contains('错误', na=False) |
            df['错误信息'].str.contains('失败', na=False) |
            (df['匹配标签数'] == 0)
        )
        
        failed_files = df[failed_mask]['完整路径'].tolist()
        
        print(f"从 {csv_path} 中找到 {len(failed_files)} 个失败的文件")
        return failed_files
        
    except Exception as e:
        print(f"读取CSV文件失败: {e}")
        return []

def main():
    if len(sys.argv) != 3:
        print("用法: python reprocess_failed_videos.py <原始CSV文件> <输出CSV文件>")
        sys.exit(1)
    
    input_csv = sys.argv[1]
    output_csv = sys.argv[2]
    
    # 检查输入文件是否存在
    if not os.path.exists(input_csv):
        print(f"错误: 输入文件 {input_csv} 不存在")
        sys.exit(1)
    
    # 提取失败的文件
    failed_files = extract_failed_files(input_csv)
    
    if not failed_files:
        print("没有找到失败的文件，退出")
        return
    
    # 创建分析器实例
    analyzer = EnhancedBatchVideoAnalyzer(num_frames=11)
    
    # 准备文件列表（路径和大小）
    video_files = []
    for file_path in failed_files:
        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            video_files.append((file_path, file_size))
            print(f"准备重新处理: {os.path.basename(file_path)} ({file_size/1024/1024:.1f}MB)")
        else:
            print(f"警告: 文件不存在，跳过: {file_path}")
    
    if not video_files:
        print("没有有效的文件需要处理")
        return
    
    print(f"\n开始重新处理 {len(video_files)} 个失败的文件...")
    print(f"结果将保存到: {output_csv}")
    print("超时设置已增加到15分钟")
    
    # 开始处理
    results = analyzer.process_video_files_sequentially(video_files, output_csv)
    
    print(f"\n=== 重新处理完成 ===")
    print(f"总文件数: {results['total_files']}")
    print(f"已处理: {results['processed_files']}")
    print(f"跳过: {results['skipped_files']}")
    print(f"成功: {results['successful_files']}")
    print(f"失败: {results['failed_files']}")
    print(f"结果已保存到: {output_csv}")

if __name__ == "__main__":
    main()