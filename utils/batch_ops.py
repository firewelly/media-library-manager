#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量操作管理器
处理视频文件的批量操作，如MD5计算、NFO导入、JavDB信息获取等
"""

import os
import shutil
from typing import List, Dict, Callable, Optional, Any
from .database import DatabaseManager
from .file_utils import FileUtils
from .thumbnails import ThumbnailGenerator
from .media_extensions import NFOImporter
from .javsp_integration import JavSPIntegration, get_integration_instance
from .logger import get_logger

logger = get_logger("BatchOps")

class BatchOperationManager:
    """批量操作管理器"""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.nfo_importer = NFOImporter(db_manager)
        self.javsp = get_integration_instance(db_manager.db_path)

    def _get_videos_by_ids(self, video_ids: List[int]) -> List[Dict]:
        """根据ID获取视频信息列表"""
        if not video_ids:
            return []
        
        placeholders = ','.join(['?' for _ in video_ids])
        query = f"SELECT * FROM videos WHERE id IN ({placeholders})"
        
        # 使用DatabaseManager执行查询
        self.db_manager.cursor.execute(query, video_ids)
        columns = [desc[0] for desc in self.db_manager.cursor.description]
        return [dict(zip(columns, row)) for row in self.db_manager.cursor.fetchall()]

    def batch_calculate_md5(self, video_ids: List[int], 
                           progress_callback: Optional[Callable[[str, int, dict], None]] = None,
                           cancel_check: Optional[Callable[[], bool]] = None) -> Dict[str, int]:
        """批量计算MD5"""
        videos = self._get_videos_by_ids(video_ids)
        total = len(videos)
        success_count = 0
        failed_count = 0
        
        for i, video in enumerate(videos):
            if cancel_check and cancel_check():
                break
                
            file_path = video.get('file_path')
            if not file_path or not os.path.exists(file_path):
                failed_count += 1
                continue
                
            if progress_callback:
                progress_callback(f"正在计算MD5: {os.path.basename(file_path)}", int((i / total) * 100))
                
            md5 = FileUtils.calculate_md5(file_path)
            if md5:
                self.db_manager.update_video(video['id'], {'md5_hash': md5})
                success_count += 1
            else:
                failed_count += 1
                
        return {'success': success_count, 'failed': failed_count}

    def batch_import_nfo(self, video_ids: List[int], 
                        filter_no_actors: bool = False,
                        progress_callback: Optional[Callable[[str, int, dict], None]] = None,
                        cancel_check: Optional[Callable[[], bool]] = None) -> Dict[str, Any]:
        """
        批量导入NFO信息
        :param filter_no_actors: 是否只处理没有演员信息的视频
        :return: dict含 success/failed/skipped/unmatched_actors(未匹配到已有演员的名字列表)
        """
        videos = self._get_videos_by_ids(video_ids)
        
        # 如果需要过滤，先检查演员信息
        if filter_no_actors:
            filtered_videos = []
            for video in videos:
                # 检查是否有关联演员
                self.db_manager.cursor.execute(
                    "SELECT COUNT(*) FROM video_actors WHERE video_id = ?", (video['id'],)
                )
                count = self.db_manager.cursor.fetchone()[0]
                if count == 0:
                    filtered_videos.append(video)
            videos = filtered_videos

        total = len(videos)
        success_count = 0
        failed_count = 0
        skipped_count = 0
        all_unmatched_actors = []  # 收集所有未匹配的演员
        
        if total == 0:
            return {'success': 0, 'failed': 0, 'skipped': 0, 'unmatched_actors': []}

        for i, video in enumerate(videos):
            if cancel_check and cancel_check():
                break
                
            file_path = video.get('file_path')
            if not file_path:
                failed_count += 1
                continue
                
            if progress_callback:
                progress_callback(f"正在导入NFO: {os.path.basename(file_path)}", int((i / total) * 100))
            
            # 尝试导入（收集未匹配的演员）
            success, unmatched = self.nfo_importer.import_nfo_for_video(
                video['id'], file_path, return_unmatched=True
            )
            if success:
                success_count += 1
                if unmatched:
                    all_unmatched_actors.extend(unmatched)
            else:
                # 检查NFO是否存在，区分失败和跳过
                nfo_path = os.path.splitext(file_path)[0] + '.nfo'
                movie_nfo = os.path.join(os.path.dirname(file_path), 'movie.nfo')
                if os.path.exists(nfo_path) or os.path.exists(movie_nfo):
                    failed_count += 1
                else:
                    skipped_count += 1
        
        # 去重
        all_unmatched_actors = list(dict.fromkeys(all_unmatched_actors))
                    
        return {
            'success': success_count, 
            'failed': failed_count, 
            'skipped': skipped_count,
            'unmatched_actors': all_unmatched_actors
        }

    def batch_import_javdb(self, video_ids: List[int],
                          filter_no_title: bool = False,
                          progress_callback: Optional[Callable[[str, int, dict], None]] = None,
                          cancel_check: Optional[Callable[[], bool]] = None) -> Dict[str, int]:
        """
        批量导入JavDB信息
        :param filter_no_title: 是否只处理标题较短(可能是番号)的视频
        """
        if not self.javsp.is_available():
            return {'error': 'JavSP集成不可用'}

        videos = self._get_videos_by_ids(video_ids)
        
        if filter_no_title:
            # 简单的逻辑：标题长度小于15或者等于番号的，认为是没有正确标题
            filtered_videos = []
            for video in videos:
                title = video.get('title', '')
                # 这里可以根据实际情况调整判断逻辑
                if not title or len(title) < 15: 
                    filtered_videos.append(video)
            videos = filtered_videos

        total = len(videos)
        success_count = 0
        failed_count = 0
        
        if total == 0:
            return {'success': 0, 'failed': 0}

        for i, video in enumerate(videos):
            if cancel_check and cancel_check():
                break
            
            file_path = video.get('file_path')
            file_name = video.get('file_name', '')
            
            if progress_callback:
                progress_callback(f"正在获取JavDB信息: {file_name}", int((i / total) * 100))
            
            # 尝试从文件名提取番号
            code = self.javsp.extract_code_from_filename(file_name)
            if not code:
                failed_count += 1
                continue
                
            # 搜索信息
            info = self.javsp.search_movie_info(code, use_parallel=False)
            if info:
                # 保存到数据库
                if self.javsp.save_movie_info_to_db(video['id'], info):
                    # 同时更新videos表的基础信息(标题、标签等)
                    update_data = {}
                    if info.get('title'):
                        update_data['title'] = info['title']
                    if info.get('rating'):
                        try:
                            update_data['stars'] = int(float(info['rating']) / 2) # 10分制转5星
                        except:
                            pass
                    
                    if update_data:
                        self.db_manager.update_video(video['id'], update_data)
                        
                    success_count += 1
                else:
                    failed_count += 1
            else:
                failed_count += 1
                
        return {'success': success_count, 'failed': failed_count}

    def batch_clean_filenames(self, video_ids: List[int],
                            progress_callback: Optional[Callable[[str, int, dict], None]] = None,
                            cancel_check: Optional[Callable[[], bool]] = None) -> Dict[str, int]:
        """批量清理文件名"""
        videos = self._get_videos_by_ids(video_ids)
        total = len(videos)
        renamed_count = 0
        failed_count = 0
        
        for i, video in enumerate(videos):
            if cancel_check and cancel_check():
                break
                
            old_path = video.get('file_path')
            if not old_path or not os.path.exists(old_path):
                failed_count += 1
                continue
                
            directory = os.path.dirname(old_path)
            filename = os.path.basename(old_path)
            
            # 使用FileUtils清理文件名
            new_filename = FileUtils.clean_filename(filename)
            
            if new_filename != filename:
                if progress_callback:
                    progress_callback(f"重命名: {filename} -> {new_filename}", int((i / total) * 100))
                    
                new_path = os.path.join(directory, new_filename)
                
                try:
                    if FileUtils.move_file(old_path, new_path):
                        # 更新数据库
                        self.db_manager.update_video(video['id'], {
                            'file_path': new_path,
                            'file_name': new_filename
                        })
                        renamed_count += 1
                    else:
                        failed_count += 1
                except Exception as e:
                    logger.error(f"重命名失败 {filename}: {e}")
                    failed_count += 1
            else:
                if progress_callback:
                    progress_callback(f"无需清理: {filename}", int((i / total) * 100))
                    
        return {'renamed': renamed_count, 'failed': failed_count}

    def batch_generate_thumbnails(self, video_ids: List[int],
                                force: bool = False,
                                progress_callback: Optional[Callable[[str, int, dict], None]] = None,
                                cancel_check: Optional[Callable[[], bool]] = None) -> Dict[str, int]:
        """
        批量生成缩略图
        :param force: 是否强制重新生成
        """
        videos = self._get_videos_by_ids(video_ids)
        total = len(videos)
        generated_count = 0
        failed_count = 0
        skipped_count = 0
        
        # 缩略图存储目录 (假设在 covers/thumbnails 下，或者与视频同目录)
        # 这里使用与视频同目录的隐藏文件夹 .thumbnails
        
        for i, video in enumerate(videos):
            if cancel_check and cancel_check():
                break
                
            file_path = video.get('file_path')
            if not file_path or not os.path.exists(file_path):
                failed_count += 1
                continue

            # 确定缩略图路径
            # 策略：在视频所在目录的 .thumbnails 子目录下
            video_dir = os.path.dirname(file_path)
            thumb_dir = os.path.join(video_dir, '.thumbnails')
            video_name = os.path.splitext(os.path.basename(file_path))[0]
            thumb_path = os.path.join(thumb_dir, f"{video_name}.jpg")
            
            if os.path.exists(thumb_path) and not force:
                skipped_count += 1
                # 确保数据库中有记录
                self.db_manager.update_video(video['id'], {'thumbnail_path': thumb_path})
                continue
                
            if progress_callback:
                progress_callback(f"生成缩略图: {video_name}", int((i / total) * 100))
                
            if ThumbnailGenerator.generate_thumbnail(file_path, thumb_path):
                # 更新数据库
                self.db_manager.update_video(video['id'], {'thumbnail_path': thumb_path})
                generated_count += 1
            else:
                failed_count += 1
                
        return {'generated': generated_count, 'failed': failed_count, 'skipped': skipped_count}

    def batch_move_files(self, video_ids: List[int], target_dir: str,
                        progress_callback: Optional[Callable[[str, int, dict], None]] = None,
                        cancel_check: Optional[Callable[[], bool]] = None) -> Dict[str, int]:
        """批量移动文件"""
        videos = self._get_videos_by_ids(video_ids)
        total = len(videos)
        moved_count = 0
        failed_count = 0
        
        if not os.path.exists(target_dir):
            try:
                os.makedirs(target_dir, exist_ok=True)
            except Exception:
                return {'moved': 0, 'failed': total}

        for i, video in enumerate(videos):
            if cancel_check and cancel_check():
                break
                
            old_path = video.get('file_path')
            if not old_path or not os.path.exists(old_path):
                failed_count += 1
                continue
                
            filename = os.path.basename(old_path)
            new_path = os.path.join(target_dir, filename)
            
            # 处理文件名冲突
            if os.path.exists(new_path):
                base, ext = os.path.splitext(filename)
                counter = 1
                while os.path.exists(new_path):
                    new_path = os.path.join(target_dir, f"{base}_{counter}{ext}")
                    counter += 1
            
            if progress_callback:
                progress_callback(f"移动文件: {filename}", int((i / total) * 100))
                
            try:
                if FileUtils.move_file(old_path, new_path):
                    self.db_manager.update_video(video['id'], {
                        'file_path': new_path,
                        'source_folder': target_dir
                    })
                    moved_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                logger.error(f"移动文件失败 {filename}: {e}")
                failed_count += 1
                
        return {'moved': moved_count, 'failed': failed_count}
