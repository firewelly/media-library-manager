#!/usr/bin/env python3
"""
增强版批量视频分析器
支持SMB网络路径访问，筛选大于200MB的视频文件，并将分析结果输出到CSV文件
新增功能：
1. MD5值计算
2. 逐个文件处理，先检查CSV是否已存在
3. 先提取帧，再并行进行视频分析和MD5计算
4. 追加模式写入CSV文件
"""

import os
import sys
import csv
import json
import argparse
import subprocess
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import tempfile
import shutil
from collections import Counter
import time
import hashlib
import threading
import concurrent.futures
from queue import Queue
import pandas as pd
import requests


class EnhancedBatchVideoAnalyzer:
    def __init__(self, lm_studio_url: str = "http://127.0.0.1:1234", 
                 vocabulary_file: str = "vocabulary_tags.txt",
                 num_frames: int = 10):
        """
        初始化增强版批量视频分析器
        
        Args:
            lm_studio_url: LM Studio服务器地址
            vocabulary_file: 词汇标签文件路径
            num_frames: 每个视频抽取的帧数
        """
        self.lm_studio_url = self._detect_available_server(lm_studio_url)
        self.vocabulary_file = vocabulary_file
        self.num_frames = num_frames
        self.video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'}
        self.min_file_size = 200 * 1024 * 1024  # 200MB in bytes
        self.analyzer_script = "video_multimodal_analyzer.py"
    
    def _detect_available_server(self, preferred_url: str = "http://127.0.0.1:1234") -> str:
        """
        检测可用的LM Studio服务器，优先使用localhost，如果不可用则使用备用服务器
        
        Args:
            preferred_url: 首选服务器地址
            
        Returns:
            可用的服务器地址
        """
        servers_to_try = [
            "http://127.0.0.1:1234",
            "http://192.168.110.213:1234"
        ]
        
        # 如果用户指定了特定的URL，优先尝试
        if preferred_url not in servers_to_try:
            servers_to_try.insert(0, preferred_url)
        
        for server_url in servers_to_try:
            try:
                print(f"正在测试服务器: {server_url}")
                response = requests.get(f"{server_url}/v1/models", timeout=5)
                if response.status_code == 200:
                    print(f"✓ 服务器可用: {server_url}")
                    return server_url
                else:
                    print(f"✗ 服务器响应异常: {server_url} (状态码: {response.status_code})")
            except requests.exceptions.RequestException as e:
                print(f"✗ 服务器不可用: {server_url} ({str(e)})")
        
        # 如果所有服务器都不可用，返回默认值并警告
        print("警告: 所有服务器都不可用，使用默认地址，可能会导致分析失败")
        return preferred_url
        
    def calculate_md5(self, file_path: str) -> str:
        """
        计算文件的MD5值
        
        Args:
            file_path: 文件路径
            
        Returns:
            MD5哈希值
        """
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                # 分块读取文件以处理大文件
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            print(f"计算MD5失败 {file_path}: {str(e)}")
            return ""
    
    def check_file_in_csv(self, file_path: str, csv_path: str) -> bool:
        """
        检查文件是否已在CSV中处理过（基于文件大小、路径和名称）
        
        Args:
            file_path: 文件路径
            csv_path: CSV文件路径
            
        Returns:
            True如果文件已存在，False如果不存在
        """
        if not os.path.exists(csv_path):
            return False
        
        try:
            # 获取当前文件信息
            file_size = os.path.getsize(file_path)
            file_name = os.path.basename(file_path)
            
            # 使用pandas读取CSV文件
            df = pd.read_csv(csv_path, encoding='utf-8')
            
            # 检查是否有必要的列
            required_columns = ['完整路径', '文件大小', '文件名']
            if not all(col in df.columns for col in required_columns):
                # 如果没有新的列结构，回退到路径检查
                if '完整路径' in df.columns:
                    return file_path in df['完整路径'].values
                elif '文件路径' in df.columns:
                    return file_path in df['文件路径'].values
                else:
                    return False
            
            # 基于文件大小、路径和名称进行重复检查
            matches = df[
                (df['完整路径'] == file_path) |
                ((df['文件大小'] == file_size) & (df['文件名'] == file_name))
            ]
            
            if not matches.empty:
                print(f"发现重复文件: {file_path} (基于文件属性)")
                return True
            
            return False
                
        except Exception as e:
            print(f"读取CSV文件失败: {str(e)}")
            return False
    
    def mount_smb_share(self, smb_path: str) -> str:
        """
        挂载SMB共享到本地临时目录
        
        Args:
            smb_path: SMB路径，格式如 smb://server/share/path
            
        Returns:
            本地挂载点路径
        """
        print(f"正在挂载SMB共享: {smb_path}")
        
        # 创建临时挂载点
        mount_point = tempfile.mkdtemp(prefix="smb_mount_")
        
        try:
            # 使用mount命令挂载SMB共享
            # 注意：在macOS上，SMB路径需要转换为适当的格式
            smb_url = smb_path.replace('smb://', '//')
            cmd = ['mount', '-t', 'smbfs', smb_url, mount_point]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                print(f"SMB共享已挂载到: {mount_point}")
                return mount_point
            else:
                print(f"挂载失败: {result.stderr}")
                os.rmdir(mount_point)
                return None
                
        except subprocess.TimeoutExpired:
            print("挂载超时")
            os.rmdir(mount_point)
            return None
        except Exception as e:
            print(f"挂载出错: {str(e)}")
            os.rmdir(mount_point)
            return None
    
    def unmount_smb_share(self, mount_point: str):
        """
        卸载SMB共享
        
        Args:
            mount_point: 挂载点路径
        """
        if mount_point and os.path.exists(mount_point):
            try:
                subprocess.run(['umount', mount_point], check=True)
                os.rmdir(mount_point)
                print(f"已卸载SMB共享: {mount_point}")
            except Exception as e:
                print(f"卸载失败: {str(e)}")
    
    def find_video_files(self, directory: str) -> List[Tuple[str, int]]:
        """
        查找目录下所有大于200MB的视频文件
        
        Args:
            directory: 搜索目录
            
        Returns:
            视频文件路径和大小的列表
        """
        video_files = []
        
        print(f"正在搜索视频文件: {directory}")
        
        try:
            for root, dirs, files in os.walk(directory):
                for file in files:
                    file_path = os.path.join(root, file)
                    file_ext = Path(file).suffix.lower()
                    
                    # 检查是否为视频文件
                    if file_ext in self.video_extensions:
                        try:
                            file_size = os.path.getsize(file_path)
                            
                            # 检查文件大小是否大于200MB
                            if file_size > self.min_file_size:
                                video_files.append((file_path, file_size))
                                print(f"找到视频文件: {file} ({file_size / (1024*1024):.1f}MB)")
                                
                        except OSError as e:
                            print(f"无法获取文件大小: {file_path} - {str(e)}")
                            
        except Exception as e:
            print(f"搜索文件时出错: {str(e)}")
            
        print(f"共找到 {len(video_files)} 个符合条件的视频文件")
        return video_files
    
    def extract_frames_only(self, video_path: str) -> Optional[str]:
        """
        仅提取视频帧到临时目录
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            临时输出目录路径，失败返回None
        """
        # 创建临时输出目录
        temp_output_dir = tempfile.mkdtemp(prefix="video_frames_")
        
        try:
            # 构建命令行参数，仅提取帧
            cmd = [
                'python', self.analyzer_script,
                video_path,
                '--lm-studio-url', self.lm_studio_url,
                '--vocabulary-file', self.vocabulary_file,
                '--output-dir', temp_output_dir,
                '--num-frames', str(self.num_frames),
                '--extract-only'  # 假设脚本支持仅提取帧的选项
            ]
            
            # 执行帧提取
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                return temp_output_dir
            else:
                print(f"帧提取失败: {result.stderr}")
                shutil.rmtree(temp_output_dir, ignore_errors=True)
                return None
                
        except subprocess.TimeoutExpired:
            print("帧提取超时")
            shutil.rmtree(temp_output_dir, ignore_errors=True)
            return None
        except Exception as e:
            print(f"帧提取出错: {str(e)}")
            shutil.rmtree(temp_output_dir, ignore_errors=True)
            return None
    
    def analyze_single_video(self, video_path: str) -> Dict:
        """
        调用video_multimodal_analyzer.py分析单个视频
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            分析结果字典
        """
        # 创建临时输出目录
        temp_output_dir = tempfile.mkdtemp(prefix="video_analysis_")
        
        try:
            # 构建命令行参数
            cmd = [
                'python', self.analyzer_script,
                video_path,
                '--lm-studio-url', self.lm_studio_url,
                '--vocabulary-file', self.vocabulary_file,
                '--output-dir', temp_output_dir,
                '--num-frames', str(self.num_frames)
            ]
            
            # 执行分析
            start_time = time.time()
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
            analysis_time = time.time() - start_time
            
            if result.returncode == 0:
                # 读取分析结果
                result_file = os.path.join(temp_output_dir, "analysis_result.json")
                if os.path.exists(result_file):
                    with open(result_file, 'r', encoding='utf-8') as f:
                        analysis_data = json.load(f)
                    
                    # 添加分析时间
                    analysis_data['analysis_time_seconds'] = round(analysis_time, 1)
                    analysis_data['success'] = True
                    
                    return analysis_data
                else:
                    return {
                        'success': False,
                        'error': '分析结果文件未找到',
                        'analysis_time_seconds': round(analysis_time, 1)
                    }
            else:
                return {
                    'success': False,
                    'error': f'分析脚本执行失败: {result.stderr}',
                    'analysis_time_seconds': round(analysis_time, 1)
                }
                
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': '分析超时（5分钟）',
                'analysis_time_seconds': 300
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'执行出错: {str(e)}',
                'analysis_time_seconds': 0
            }
        finally:
            # 清理临时目录
            shutil.rmtree(temp_output_dir, ignore_errors=True)
    
    def parallel_process_video(self, video_path: str, file_size: int) -> Dict:
        """
        并行处理单个视频：同时进行视频分析和MD5计算
        
        Args:
            video_path: 视频文件路径
            file_size: 文件大小
            
        Returns:
            处理结果字典
        """
        print(f"开始并行处理: {os.path.basename(video_path)}")
        
        # 使用线程池并行执行MD5计算和视频分析
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            # 提交MD5计算任务
            md5_future = executor.submit(self.calculate_md5, video_path)
            
            # 提交视频分析任务
            analysis_future = executor.submit(self.analyze_single_video, video_path)
            
            # 等待两个任务完成
            try:
                md5_hash = md5_future.result(timeout=600)  # 10分钟超时
                analysis_result = analysis_future.result(timeout=600)  # 10分钟超时
                
                # 合并结果
                result = {
                    'video_path': video_path,
                    'video_name': os.path.basename(video_path),
                    'file_size_bytes': file_size,
                    'file_size_mb': round(file_size / (1024*1024), 1),
                    'md5_hash': md5_hash,
                    'analysis_time_seconds': analysis_result.get('analysis_time_seconds', 0),
                }
                
                if analysis_result.get('success', False):
                    result.update({
                        'total_frames_analyzed': analysis_result.get('total_frames_analyzed', 0),
                        'successful_analyses': analysis_result.get('successful_analyses', 0),
                        'matched_tags': analysis_result.get('all_matched_tags', []),
                        'tag_frequency': analysis_result.get('tag_frequency', {}),
                        'success': True
                    })
                else:
                    result.update({
                        'total_frames_analyzed': 0,
                        'successful_analyses': 0,
                        'matched_tags': [],
                        'tag_frequency': {},
                        'error': analysis_result.get('error', '未知错误'),
                        'success': False
                    })
                
                return result
                
            except concurrent.futures.TimeoutError:
                return {
                    'video_path': video_path,
                    'video_name': os.path.basename(video_path),
                    'file_size_mb': round(file_size / (1024*1024), 1),
                    'md5_hash': '',
                    'matched_tags': [],
                    'tag_frequency': {},
                    'error': '处理超时',
                    'success': False
                }
    
    def append_to_csv(self, result: Dict, csv_path: str):
        """
        以追加模式将单个结果写入CSV文件
        
        Args:
            result: 处理结果字典
            csv_path: CSV文件路径
        """
        # 定义CSV列
        fieldnames = [
            '完整路径', '文件名', '文件大小', '文件大小(MB)', 'MD5值', 
            '分析时间(秒)', '分析帧数', '成功分析帧数', 
            '匹配标签数', '匹配标签列表', '标签详情', '错误信息'
        ]
        
        # 检查文件是否存在，如果不存在则创建并写入头部
        file_exists = os.path.exists(csv_path)
        
        with open(csv_path, 'a', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            # 如果文件不存在，写入头部
            if not file_exists:
                writer.writeheader()
            
            # 准备行数据
            row_data = {
                '完整路径': result['video_path'],
                '文件名': result['video_name'],
                '文件大小': result.get('file_size_bytes', 0),
                '文件大小(MB)': result['file_size_mb'],
                'MD5值': result['md5_hash'],
                '分析时间(秒)': result.get('analysis_time_seconds', 0),
                '分析帧数': result.get('total_frames_analyzed', 0),
                '成功分析帧数': result.get('successful_analyses', 0),
                '匹配标签数': len(result.get('matched_tags', [])),
                '匹配标签列表': ', '.join(result.get('matched_tags', [])),
                '标签详情': json.dumps(result.get('tag_frequency', {}), ensure_ascii=False),
                '错误信息': result.get('error', '')
            }
            
            writer.writerow(row_data)
    
    def process_video_files_sequentially(self, video_files: List[Tuple[str, int]], 
                                       output_csv: str) -> Dict:
        """
        逐个处理视频文件
        
        Args:
            video_files: 视频文件路径和大小的列表
            output_csv: 输出CSV文件路径
            
        Returns:
            处理结果汇总
        """
        total_files = len(video_files)
        processed_count = 0
        skipped_count = 0
        success_count = 0
        failed_count = 0
        
        print(f"\n开始逐个处理 {total_files} 个视频文件...")
        
        for i, (video_path, file_size) in enumerate(video_files, 1):
            print(f"\n=== 处理第 {i}/{total_files} 个视频 ===")
            print(f"文件: {os.path.basename(video_path)}")
            print(f"大小: {file_size / (1024*1024):.1f}MB")
            
            # 检查文件是否已在CSV中
            if self.check_file_in_csv(video_path, output_csv):
                print("文件已存在于CSV中，跳过处理")
                skipped_count += 1
                continue
            
            # 并行处理视频
            start_time = time.time()
            result = self.parallel_process_video(video_path, file_size)
            process_time = time.time() - start_time
            
            # 立即追加到CSV文件
            self.append_to_csv(result, output_csv)
            
            processed_count += 1
            
            if result.get('success', False):
                success_count += 1
                print(f"处理完成! 用时: {process_time:.1f}秒")
                print(f"MD5: {result['md5_hash']}")
                print(f"匹配标签: {len(result.get('matched_tags', []))} 个")
            else:
                failed_count += 1
                print(f"处理失败: {result.get('error', '未知错误')}")
        
        # 返回汇总结果
        summary = {
            'total_files': total_files,
            'processed_count': processed_count,
            'skipped_count': skipped_count,
            'success_count': success_count,
            'failed_count': failed_count
        }
        
        return summary


def main():
    parser = argparse.ArgumentParser(description='增强版批量视频分析器')
    parser.add_argument('path', help='视频文件路径，支持SMB网络路径(smb://server/share/path)或本地路径')
    parser.add_argument('--output-csv', default='enhanced_batch_analysis_results.csv', 
                       help='输出CSV文件路径')
    parser.add_argument('--lm-studio-url', default='http://127.0.0.1:1234', 
                       help='LM Studio服务器地址')
    parser.add_argument('--vocabulary-file', default='vocabulary_tags.txt', 
                       help='词汇标签文件路径')
    parser.add_argument('--num-frames', type=int, default=10, 
                       help='每个视频抽取的帧数')
    
    args = parser.parse_args()
    
    # 检查video_multimodal_analyzer.py是否存在
    if not os.path.exists('video_multimodal_analyzer.py'):
        print("错误: 找不到video_multimodal_analyzer.py文件")
        sys.exit(1)
    
    # 创建增强版批量分析器
    batch_analyzer = EnhancedBatchVideoAnalyzer(
        lm_studio_url=args.lm_studio_url,
        vocabulary_file=args.vocabulary_file,
        num_frames=args.num_frames
    )
    
    mount_point = None
    search_path = None
    
    try:
        # 判断是SMB路径还是本地路径
        if args.path.startswith('smb://'):
            # 挂载SMB共享
            mount_point = batch_analyzer.mount_smb_share(args.path)
            if not mount_point:
                print("无法挂载SMB共享，退出")
                sys.exit(1)
            search_path = mount_point
        else:
            # 本地路径
            if not os.path.exists(args.path):
                print(f"错误: 路径不存在: {args.path}")
                sys.exit(1)
            search_path = args.path
            print(f"使用本地路径: {search_path}")
        
        # 查找视频文件
        video_files = batch_analyzer.find_video_files(search_path)
        if not video_files:
            print("未找到符合条件的视频文件")
            sys.exit(0)
        
        # 逐个处理视频文件
        summary = batch_analyzer.process_video_files_sequentially(video_files, args.output_csv)
        
        # 打印汇总结果
        print(f"\n=== 处理完成 ===")
        print(f"总文件数: {summary['total_files']}")
        print(f"已处理: {summary['processed_count']}")
        print(f"跳过: {summary['skipped_count']}")
        print(f"成功: {summary['success_count']}")
        print(f"失败: {summary['failed_count']}")
        print(f"\n结果已保存到: {args.output_csv}")
        
    except KeyboardInterrupt:
        print("\n用户中断处理")
    except Exception as e:
        print(f"处理过程中出错: {str(e)}")
        sys.exit(1)
    finally:
        # 清理：卸载SMB共享
        if mount_point:
            batch_analyzer.unmount_smb_share(mount_point)


if __name__ == "__main__":
    main()