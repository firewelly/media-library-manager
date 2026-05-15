#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Production版本视频分析工具
- 使用siliconflow GLM版本进行视频分析
- 从media_library.db数据库中读取输入视频文件
- 输入条件：在线的文件且没有标签的视频
- 不计算MD5
- 输出：CSV文件和直接写入数据库
"""

# Production版本视频分析工具 - 修复版
import os
import sys
import sqlite3
import csv
import time
import re
from datetime import datetime
from typing import List, Dict, Any, Optional

from video_analyzer_local_model_adult import VideoAnalyzerLocalModelAdult
from video_analyzer_pipeline import PipelineVideoAnalyzer


class ProductionVideoAnalyzer:
    """Production版本视频分析器"""
    
    def __init__(self, db_path: str, output_dir: str = None, verbose: bool = True, 
                 api_key: str = None, use_pipeline: bool = False, max_workers: int = 3):
        """
        初始化分析器
        
        Args:
            db_path: 数据库文件路径
            output_dir: 输出目录，默认为当前脚本目录
            verbose: 是否显示详细信息
            api_key: API密钥
            use_pipeline: 是否使用流水线模式
            max_workers: 流水线模式下API并行数
        """
        self.db_path = db_path
        self.verbose = verbose
        self.processed_count = 0
        self.success_count = 0
        self.error_count = 0
        self.use_pipeline = use_pipeline
        self.max_workers = max_workers
        
        self.api_key = api_key or os.environ.get('SILICONFLOW_API_KEY')
        
        if use_pipeline:
            self.pipeline_analyzer = PipelineVideoAnalyzer(
                api_base_url="https://api.siliconflow.cn",
                model_name="Qwen/Qwen3-VL-30B-A3B-Instruct",
                api_key=self.api_key,
                max_api_workers=max_workers,
                verbose=verbose
            )
        else:
            self.analyzer = VideoAnalyzerLocalModelAdult(
                api_base_url="https://api.siliconflow.cn",
                model_name="Qwen/Qwen3-VL-30B-A3B-Instruct",
                verbose=verbose
            )
        
        # 设置输出目录
        if output_dir:
            self.output_dir = output_dir
            os.makedirs(output_dir, exist_ok=True)
        else:
            self.output_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 创建CSV文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.csv_file = os.path.join(self.output_dir, f"production_analysis_{timestamp}.csv")
        
        self.log_message("Production视频分析器初始化完成")
        self.log_message(f"数据库路径: {self.db_path}")
        self.log_message(f"输出目录: {self.output_dir}")
        self.log_message(f"CSV报告: {self.csv_file}")
    
    def log_message(self, message: str):
        """记录日志信息"""
        if self.verbose:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] {message}")
            
            # 同时写入日志文件
            try:
                log_file = os.path.join(self.output_dir, "analysis_log.txt")
                with open(log_file, 'a', encoding='utf-8') as f:
                    f.write(f"[{timestamp}] {message}\n")
            except Exception:
                pass  # 忽略日志写入错误
    
    def get_available_folders(self) -> List[str]:
        """
        获取所有管理文件夹（从folders表获取，只返回在线的文件夹）

        Returns:
            在线文件夹路径列表
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 查询所有管理文件夹
            query = """
            SELECT DISTINCT folder_path, folder_type, device_name
            FROM folders
            WHERE is_active = 1
            ORDER BY folder_path
            """

            cursor.execute(query)
            rows = cursor.fetchall()

            online_folders = []
            offline_folders = []

            for row in rows:
                if len(row) >= 3:
                    folder_path, folder_type, device_name = row[:3]
                else:
                    folder_path = row[0]
                    folder_type = "local"
                    device_name = "Unknown"

                # 参考media_library.py的逻辑检查路径是否存在
                if os.path.exists(folder_path):
                    online_folders.append(folder_path)
                else:
                    offline_folders.append(folder_path)

            conn.close()

            # 详细日志信息
            self.log_message(f"管理文件夹状态统计:")
            self.log_message(f"  总文件夹数: {len(rows)}")
            self.log_message(f"  在线文件夹: {len(online_folders)}")
            self.log_message(f"  离线文件夹: {len(offline_folders)}")

            if offline_folders:
                self.log_message(f"被过滤的离线文件夹:")
                for folder in offline_folders:
                    self.log_message(f"  - {folder} (离线)")

            if not online_folders:
                self.log_message("警告: 没有可用的在线文件夹！")
                self.log_message("建议:")
                self.log_message("  1. 检查网络连接和NAS设备")
                self.log_message("  2. 确认外接硬盘已挂载")
                self.log_message("  3. 使用media_library.py启用其他文件夹")

            return online_folders

        except Exception as e:
            self.log_message(f"查询管理文件夹失败: {e}")
            return []
    
    def get_videos_without_tags(self, folder: str = None) -> List[Dict[str, Any]]:
        """
        从数据库中获取在线的且没有标签的视频
        
        Args:
            folder: 可选，指定管理文件夹路径进行筛选
        
        Returns:
            视频信息列表
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            where_conditions = [
                "(v.tags IS NULL OR v.tags = '' OR TRIM(v.tags) = '')",
                "v.file_path IS NOT NULL",
                "v.file_path != ''",
                "f.is_active = 1"
            ]
            
            if folder:
                where_conditions.append("v.source_folder LIKE ? || '%'")
            
            query = f"""
            SELECT v.id, v.title, v.file_path, v.file_size, v.duration, 
                   v.resolution, v.description, v.tags
            FROM videos v
            INNER JOIN folders f ON v.source_folder = f.folder_path
            WHERE {' AND '.join(where_conditions)}
            ORDER BY v.id
            """
            
            if folder:
                cursor.execute(query, (folder,))
            else:
                cursor.execute(query)
                
            rows = cursor.fetchall()
            
            videos = []
            for row in rows:
                if not os.path.exists(row[2]):
                    continue
                video = {
                    'id': row[0],
                    'title': row[1],  # 直接使用title字段
                    'code': '',  # 数据库中没有code字段
                    'path': row[2],
                    'file_size': row[3],
                    'duration': row[4],
                    'resolution': row[5],
                    'description': row[6],
                    'existing_tags': row[7]
                }
                videos.append(video)
            
            conn.close()
            
            folder_info = f" 来自管理文件夹 '{folder}'" if folder else ""
            self.log_message(f"找到 {len(videos)} 个需要分析的视频{folder_info}")
            return videos
            
        except Exception as e:
            self.log_message(f"查询数据库失败: {e}")
            return []
    
    def extract_description_from_analysis(self, analysis_text: str) -> str:
        """
        从分析结果中提取描述信息
        
        Args:
            analysis_text: 分析文本
            
        Returns:
            描述文本
        """
        if not analysis_text:
            return ""
        
        # 尝试提取场景描述或剧情描述
        patterns = [
            r'场景描述[：:]\s*([^\n]+)',
            r'剧情描述[：:]\s*([^\n]+)',
            r'内容描述[：:]\s*([^\n]+)',
            r'视频描述[：:]\s*([^\n]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, analysis_text)
            if match:
                description = match.group(1).strip()
                # 清理描述文本
                description = re.sub(r'[\n\r\t]', ' ', description)
                return description
        
        # 如果没有找到特定模式，返回分析文本的前200个字符作为描述
        clean_text = re.sub(r'[\n\r\t]+', ' ', analysis_text).strip()
        return clean_text[:200] + "..." if len(clean_text) > 200 else clean_text
    
    def get_or_create_tag(self, conn: sqlite3.Connection, tag_name: str) -> int:
        """
        获取或创建标签，返回标签ID
        
        Args:
            conn: 数据库连接
            tag_name: 标签名称
            
        Returns:
            标签ID
        """
        cursor = conn.cursor()
        
        # 查找现有标签
        cursor.execute("SELECT id FROM tags WHERE tag_name = ?", (tag_name,))
        result = cursor.fetchone()

        if result:
            return result[0]

        # 创建新标签
        cursor.execute("""
            INSERT INTO tags (tag_name, tag_color, created_at)
            VALUES (?, '#007bff', CURRENT_TIMESTAMP)
        """, (tag_name,))
        
        return cursor.lastrowid
    
    def save_tags_to_database(self, video_id: int, tags: List[str], description: str = None):
        """
        将标签和描述保存到数据库
        
        Args:
            video_id: 视频ID
            tags: 标签列表
            description: 描述信息
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 将标签列表转换为字符串（用逗号分隔）
            tags_str = ', '.join(tags) if tags else ''
            
            # 更新视频描述和标签
            cursor.execute("""
                UPDATE videos 
                SET description = ?, tags = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (description, tags_str, video_id))
            
            # 同时在tags表中记录标签（如果不存在的话）
            for tag in tags:
                cursor.execute("""
                    INSERT OR IGNORE INTO tags (tag_name) 
                    VALUES (?)
                """, (tag.strip(),))
            
            conn.commit()
            conn.close()
            
            self.log_message(f"成功保存 {len(tags)} 个标签到数据库")
            
        except Exception as e:
            self.log_message(f"保存标签到数据库失败: {e}")
    
    def initialize_csv(self):
        """初始化CSV文件"""
        try:
            with open(self.csv_file, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow([
                    '视频ID', '标题', '番号', '文件路径', '文件大小(字节)', 
                    '时长(秒)', '分辨率', 'MD5值', '分析状态', '标签数量', 
                    '标签列表', '描述', '分析时间', '错误信息'
                ])
            self.log_message(f"CSV文件初始化完成: {self.csv_file}")
        except Exception as e:
            self.log_message(f"初始化CSV文件失败: {e}")
    
    def save_to_csv(self, video: Dict[str, Any], tags: List[str], description: str, 
                   analysis_time: float, error_msg: str = ""):
        """
        保存结果到CSV文件
        
        Args:
            video: 视频信息
            tags: 标签列表
            description: 描述信息
            analysis_time: 分析耗时
            error_msg: 错误信息
        """
        try:
            with open(self.csv_file, 'a', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow([
                    video['id'],
                    video.get('title', ''),
                    video.get('code', ''),
                    video['path'],
                    video.get('file_size', 0),
                    video.get('duration', 0),
                    video.get('resolution', ''),
                    '',  # MD5值留空
                    '成功' if not error_msg else '失败',
                    len(tags),
                    ', '.join(tags),
                    description,
                    f"{analysis_time:.2f}秒",
                    error_msg
                ])
        except Exception as e:
            self.log_message(f"保存CSV失败: {e}")
    
    def process_single_video(self, video: Dict[str, Any]) -> bool:
        """
        处理单个视频
        
        Args:
            video: 视频信息
            
        Returns:
            是否处理成功
        """
        video_path = video['path']
        video_id = video['id']
        
        # 检查文件是否存在
        if not os.path.exists(video_path):
            error_msg = "文件不存在"
            self.log_message(f"跳过不存在的文件: {video_path}")
            self.save_to_csv(video, [], "", 0, error_msg)
            return False
        
        self.log_message(f"开始分析视频: {os.path.basename(video_path)} (ID: {video_id})")
        
        start_time = time.time()
        
        try:
            result = self.analyzer.analyze_video(video_path)
            
            analysis_time = time.time() - start_time
            
            if result.get('success', False):
                analysis_text = result.get('analysis', '')
                
                tags = self.analyzer.extract_tags_from_analysis(analysis_text)
                description = self.extract_description_from_analysis(analysis_text)
                
                self.log_message(f"分析成功，提取到 {len(tags)} 个标签: {', '.join(tags[:5])}{'...' if len(tags) > 5 else ''}")
                
                # 保存到数据库
                self.save_tags_to_database(video_id, tags, description)
                
                # 保存到CSV
                self.save_to_csv(video, tags, description, analysis_time)
                
                self.success_count += 1
                return True
                
            else:
                error_msg = result.get('error', '未知错误')
                self.log_message(f"分析失败: {error_msg}")
                
                # 保存失败记录到CSV
                self.save_to_csv(video, [], "", analysis_time, error_msg)
                
                self.error_count += 1
                return False
                
        except Exception as e:
            analysis_time = time.time() - start_time
            error_msg = str(e)
            self.log_message(f"处理视频异常: {error_msg}")
            
            # 保存异常记录到CSV
            self.save_to_csv(video, [], "", analysis_time, error_msg)
            
            self.error_count += 1
            return False
    
    def process_batch_pipeline(self, videos: List[Dict[str, Any]]) -> int:
        """
        使用流水线模式批量处理视频
        
        Args:
            videos: 视频列表
            
        Returns:
            成功处理的数量
        """
        valid_videos = []
        for video in videos:
            if os.path.exists(video['path']):
                valid_videos.append({
                    'id': video['id'],
                    'path': video['path'],
                    'title': video.get('title', '')
                })
            else:
                self.log_message(f"跳过不存在的文件: {video['path']}")
                self.save_to_csv(video, [], "", 0, "文件不存在")
                self.error_count += 1
        
        if not valid_videos:
            self.log_message("没有有效的视频文件")
            return 0
        
        self.log_message(f"流水线模式: 处理 {len(valid_videos)} 个视频，API并行数={self.max_workers}")
        
        def progress_callback(stage, task):
            if stage == 'frame_extracted':
                self.log_message(f"帧提取完成: ID={task.video_id}")
            elif stage == 'api_completed':
                video_info = next((v for v in videos if v['id'] == task.video_id), None)
                if video_info:
                    analysis_time = task.end_time - task.start_time if task.end_time > task.start_time else 0
                    
                    if task.api_error:
                        self.log_message(f"API失败: ID={task.video_id} - {task.api_error}")
                        self.save_to_csv(video_info, [], "", analysis_time, task.api_error)
                        self.error_count += 1
                    else:
                        self.log_message(f"API成功: ID={task.video_id} - 标签: {task.final_tags}")
                        self.save_tags_to_database(task.video_id, task.final_tags, task.final_description)
                        self.save_to_csv(video_info, task.final_tags, task.final_description, analysis_time)
                        self.success_count += 1
                    
                    self.processed_count += 1
        
        self.pipeline_analyzer.progress_callback = progress_callback
        
        completed_tasks = self.pipeline_analyzer.analyze_videos(valid_videos)
        
        return self.success_count
    
    def run(self, limit: int = None, folder: str = None):
        """运行分析流程
        
        Args:
            limit: 限制处理的视频数量
            folder: 指定文件夹路径进行筛选
        """
        folder_info = f" 来自文件夹 '{folder}'" if folder else ""
        self.log_message(f"开始Production视频分析流程{folder_info}")
        
        # 检查数据库文件
        if not os.path.exists(self.db_path):
            self.log_message(f"数据库文件不存在: {self.db_path}")
            return
        
        # 获取需要分析的视频
        videos = self.get_videos_without_tags(folder)
        if not videos:
            self.log_message(f"没有找到需要分析的视频{folder_info}")
            return
        
        # 如果设置了limit，则限制处理数量
        if limit and limit > 0:
            videos = videos[:limit]
            self.log_message(f"限制处理数量为: {limit}")
        
        self.log_message(f"准备分析 {len(videos)} 个视频{folder_info}")
        
        self.initialize_csv()
        
        total_videos = len(videos)
        self.log_message(f"开始处理 {total_videos} 个视频")
        
        if self.use_pipeline:
            self.process_batch_pipeline(videos)
        else:
            for i, video in enumerate(videos, 1):
                self.log_message(f"进度: {i}/{total_videos}")
                
                success = self.process_single_video(video)
                self.processed_count += 1
                
                if i % 10 == 0 or i == total_videos:
                    self.log_message(f"已处理: {self.processed_count}, 成功: {self.success_count}, 失败: {self.error_count}")
        
        # 最终统计
        self.log_message("=" * 50)
        self.log_message("分析完成！")
        self.log_message(f"总计处理: {self.processed_count} 个视频")
        self.log_message(f"成功分析: {self.success_count} 个")
        self.log_message(f"分析失败: {self.error_count} 个")
        self.log_message(f"CSV报告: {self.csv_file}")
        self.log_message("=" * 50)

def main():
    """主函数"""
    import argparse
    
    # 默认数据库路径
    # 使用相对路径以支持不同环境(OneDrive-Personal/OneDrive-个人)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # 假设数据库在父目录
    default_db_path = os.path.join(os.path.dirname(current_dir), 'media_library.db')
    
    if not os.path.exists(default_db_path):
         possible_paths = [
             "/Users/firewell/Library/CloudStorage/OneDrive-Personal/bioinfo/media/media_library.db",
             "/Users/firewell/Library/CloudStorage/OneDrive-个人/bioinfo/media/media_library.db"
         ]
         for p in possible_paths:
             if os.path.exists(p):
                 default_db_path = p
                 break
    
    parser = argparse.ArgumentParser(description='Production版本视频分析工具')
    parser.add_argument('--db', default=default_db_path, help=f'数据库文件路径（默认: {default_db_path}）')
    parser.add_argument('--output', help='输出目录，默认为当前脚本目录')
    parser.add_argument('--verbose', action='store_true', default=True, help='显示详细信息')
    parser.add_argument('--limit', type=int, help='限制处理的视频数量（用于测试）')
    parser.add_argument('--api-key', help='SiliconFlow API密钥，如果未提供则从环境变量SILICONFLOW_API_KEY获取')
    parser.add_argument('--all', action='store_true', help='跳过交互模式，直接处理所有文件夹')
    parser.add_argument('--pipeline', action='store_true', help='使用流水线模式（帧提取串行+API并行）')
    parser.add_argument('--workers', type=int, default=3, help='流水线模式下API并行数（默认3）')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.db):
        print(f"错误: 数据库文件不存在: {args.db}")
        print("请确保数据库文件存在，或使用 --db 参数指定正确的数据库路径")
        sys.exit(1)
    
    analyzer = ProductionVideoAnalyzer(
        db_path=args.db,
        output_dir=args.output,
        verbose=args.verbose,
        api_key=args.api_key,
        use_pipeline=args.pipeline,
        max_workers=args.workers
    )
    
    # 获取所有可用文件夹
    folders = analyzer.get_available_folders()
    
    if not folders:
        print("没有找到包含未标记视频的文件夹")
        sys.exit(0)
    
    # 如果指定了--all参数，直接处理所有文件夹
    if args.all:
        print(f"找到 {len(folders)} 个管理文件夹，开始处理所有文件夹...")
        analyzer.run(limit=args.limit)
        return
    
    # 显示文件夹选项
    print("=" * 50)
    print("视频分析工具 - 交互模式")
    print("=" * 50)
    print(f"\n在线文件夹列表 (共{len(folders)}个可用):")
    print("0. 处理所有在线文件夹 (默认)")
    for i, folder in enumerate(folders, 1):
        # 显示更友好的文件夹名称
        if folder.startswith("/Users/firewell/"):
            display_name = folder.replace("/Users/firewell/", "~/")
        elif folder.startswith("/Volumes/"):
            volume_name = folder.split('/')[2] if len(folder.split('/')) > 2 else "Volume"
            display_name = f"[NAS] {volume_name}"
        else:
            display_name = folder

        print(f"{i}. {display_name}")
        print(f"   路径: {folder}")
    
    # 用户选择
    print(f"\n提示: 所有显示的文件夹都已验证为在线状态，可以安全选择")
    while True:
        choice = input(f"\n请选择要处理的文件夹 (0-{len(folders)}, 默认为0): ").strip()
        
        # 空输入默认为0（处理所有文件夹）
        if not choice:
            choice = "0"
        
        # 选择所有文件夹
        if choice == "0":
            print("已选择处理所有文件夹")
            analyzer.run(limit=args.limit)
            break
        
        # 选择特定文件夹
        try:
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(folders):
                selected_folder = folders[choice_idx]
                print(f"已选择文件夹: {selected_folder}")
                analyzer.run(limit=args.limit, folder=selected_folder)
                break
            else:
                print(f"无效选择，请输入 0-{len(folders)}")
        except ValueError:
            print("无效输入，请输入数字")

if __name__ == "__main__":
    main()