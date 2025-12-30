#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
媒体库扩展功能模块
从media_library.py提取的核心业务功能，适配到PySide6界面
"""

import os
import sqlite3
import xml.etree.ElementTree as ET
import shutil
import threading
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Callable
from datetime import datetime
import re
from .logger import get_logger
from .progress_manager import ThreadedProgress
from .file_utils import FileUtils
from .database import DatabaseManager

logger = get_logger("MediaExtensions")

class NFOImporter:
    """NFO文件导入器"""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def parse_nfo_file(self, nfo_file_path: str) -> Dict[str, Any]:
        """解析NFO文件"""
        try:
            if not os.path.exists(nfo_file_path):
                return {}

            tree = ET.parse(nfo_file_path)
            root = tree.getroot()

            nfo_data = {}

            # 解析标题
            title_element = root.find('.//title')
            if title_element is not None:
                nfo_data['title'] = title_element.text

            # 解析演员
            actors = []
            for actor in root.findall('.//actor'):
                name_element = actor.find('name')
                if name_element is not None:
                    actors.append(name_element.text)
            if actors:
                nfo_data['actors'] = ', '.join(actors)

            # 解析年份
            year_element = root.find('.//year')
            if year_element is not None:
                try:
                    nfo_data['year'] = int(year_element.text)
                except ValueError:
                    pass

            # 解析标签
            tags = []
            for tag in root.findall('.//tag'):
                if tag.text:
                    tags.append(tag.text)
            if tags:
                nfo_data['tags'] = ', '.join(tags)

            # 解析评分
            rating_element = root.find('.//rating')
            if rating_element is not None:
                try:
                    rating = float(rating_element.text)
                    nfo_data['stars'] = int(rating)  # 转换为星级
                except ValueError:
                    pass

            # 解析时长
            runtime_element = root.find('.//runtime')
            if runtime_element is not None and runtime_element.text:
                # 提取分钟数
                runtime_match = re.search(r'(\d+)', runtime_element.text)
                if runtime_match:
                    minutes = int(runtime_match.group(1))
                    hours = minutes // 60
                    mins = minutes % 60
                    nfo_data['duration'] = f"{hours:02d}:{mins:02d}"

            # 解析简介
            plot_element = root.find('.//plot')
            if plot_element is not None and plot_element.text:
                nfo_data['description'] = plot_element.text

            logger.info(f"NFO解析完成: {nfo_file_path}")
            return nfo_data

        except Exception as e:
            logger.error(f"NFO文件解析失败 {nfo_file_path}: {e}")
            return {}

    def import_nfo_for_video(self, video_id: int, video_path: str) -> bool:
        """为指定视频导入NFO信息"""
        try:
            # 查找同目录下的NFO文件
            video_dir = os.path.dirname(video_path)
            video_name = os.path.splitext(os.path.basename(video_path))[0]

            # 可能的NFO文件名
            nfo_candidates = [
                f"{video_name}.nfo",
                "movie.nfo",
                "tvshow.nfo"
            ]

            nfo_file = None
            for candidate in nfo_candidates:
                candidate_path = os.path.join(video_dir, candidate)
                if os.path.exists(candidate_path):
                    nfo_file = candidate_path
                    break

            if not nfo_file:
                logger.warning(f"未找到NFO文件: {video_path}")
                return False

            # 解析NFO文件
            nfo_data = self.parse_nfo_file(nfo_file)
            if not nfo_data:
                return False

            # 更新数据库
            return self.db_manager.update_video(video_id, nfo_data) > 0

        except Exception as e:
            logger.error(f"导入NFO失败 {video_path}: {e}")
            return False

class DuplicateManager:
    """重复文件管理器"""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def find_duplicate_files(self) -> List[Dict[str, Any]]:
        """查找重复文件"""
        try:
            # 查找MD5重复
            md5_query = """
                SELECT md5_hash, COUNT(*) as count, GROUP_CONCAT(id) as video_ids
                FROM videos
                WHERE md5_hash IS NOT NULL AND md5_hash != ''
                GROUP BY md5_hash
                HAVING COUNT(*) > 1
            """

            md5_results = self.db_manager.execute_query(md5_query)
            duplicates = []

            for md5_hash, count, video_ids_str in md5_results:
                video_ids = [int(vid) for vid in video_ids_str.split(',') if vid]
                videos = []

                for video_id in video_ids:
                    video = self.db_manager.execute_query(
                        "SELECT * FROM videos WHERE id = ?", (video_id,)
                    )
                    if video:
                        columns = [desc[0] for desc in self.db_manager.cursor.description]
                        video_dict = dict(zip(columns, video[0]))
                        videos.append(video_dict)

                duplicates.append({
                    'type': 'md5',
                    'hash': md5_hash,
                    'count': count,
                    'videos': videos
                })

            # 查找文件哈希重复
            hash_query = """
                SELECT file_hash, COUNT(*) as count, GROUP_CONCAT(id) as video_ids
                FROM videos
                WHERE file_hash IS NOT NULL AND file_hash != ''
                GROUP BY file_hash
                HAVING COUNT(*) > 1
            """

            hash_results = self.db_manager.execute_query(hash_query)

            for file_hash, count, video_ids_str in hash_results:
                video_ids = [int(vid) for vid in video_ids_str.split(',') if vid]
                videos = []

                for video_id in video_ids:
                    video = self.db_manager.execute_query(
                        "SELECT * FROM videos WHERE id = ?", (video_id,)
                    )
                    if video:
                        columns = [desc[0] for desc in self.db_manager.cursor.description]
                        video_dict = dict(zip(columns, video[0]))
                        videos.append(video_dict)

                duplicates.append({
                    'type': 'file_hash',
                    'hash': file_hash,
                    'count': count,
                    'videos': videos
                })

            return duplicates

        except Exception as e:
            logger.error(f"查找重复文件失败: {e}")
            return []

    def remove_duplicates_by_criteria(self, keep_criteria: str = 'largest') -> Dict[str, int]:
        """根据条件删除重复文件"""
        try:
            duplicates = self.find_duplicate_files()
            removed_count = 0
            skipped_count = 0

            for duplicate_group in duplicates:
                videos = duplicate_group['videos']

                if len(videos) < 2:
                    continue

                # 根据条件选择保留的文件
                if keep_criteria == 'largest':
                    # 保留文件最大的
                    keep_video = max(videos, key=lambda v: v.get('file_size', 0) or 0)
                elif keep_criteria == 'newest':
                    # 保留最新的文件
                    keep_video = max(videos, key=lambda v: v.get('file_created_time', ''))
                elif keep_criteria == 'shortest_path':
                    # 保留路径最短的
                    keep_video = min(videos, key=lambda v: len(v.get('file_path', '')))
                else:
                    keep_video = videos[0]

                # 删除其他重复文件
                for video in videos:
                    if video['id'] != keep_video['id']:
                        try:
                            # 删除数据库记录
                            self.db_manager.delete_video(video['id'])
                            removed_count += 1
                            logger.info(f"删除重复文件: {video['file_name']}")
                        except Exception as e:
                            logger.error(f"删除重复文件失败 {video['file_name']}: {e}")
                            skipped_count += 1

            return {
                'removed': removed_count,
                'skipped': skipped_count
            }

        except Exception as e:
            logger.error(f"批量删除重复文件失败: {e}")
            return {'removed': 0, 'skipped': 0}

class BatchOperations:
    """批量操作管理器"""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def batch_update_stars(self, video_ids: List[int], stars: int) -> int:
        """批量更新星级"""
        try:
            if not video_ids:
                return 0

            placeholders = ','.join(['?' for _ in video_ids])
            query = f"UPDATE videos SET stars = ?, updated_at = CURRENT_TIMESTAMP WHERE id IN ({placeholders})"

            params = [stars] + video_ids
            return self.db_manager.execute_update(query, tuple(params))

        except Exception as e:
            logger.error(f"批量更新星级失败: {e}")
            return 0

    def batch_add_tags(self, video_ids: List[int], tags: List[str]) -> int:
        """批量添加标签"""
        try:
            if not video_ids or not tags:
                return 0

            updated_count = 0
            tag_str = ', '.join(tags)

            for video_id in video_ids:
                # 获取现有标签
                existing_tags = self.db_manager.execute_query(
                    "SELECT tags FROM videos WHERE id = ?", (video_id,)
                )

                if existing_tags:
                    current_tags = existing_tags[0][0] or ""
                    # 合并标签，避免重复
                    current_tag_list = [tag.strip() for tag in current_tags.split(',') if tag.strip()]
                    for tag in tags:
                        if tag.strip() not in current_tag_list:
                            current_tag_list.append(tag.strip())

                    new_tag_str = ', '.join(current_tag_list)

                    if self.db_manager.update_video(video_id, {'tags': new_tag_str}) > 0:
                        updated_count += 1

            return updated_count

        except Exception as e:
            logger.error(f"批量添加标签失败: {e}")
            return 0

    def batch_move_files(self, video_ids: List[int], target_dir: str) -> Dict[str, int]:
        """批量移动文件"""
        try:
            if not video_ids or not target_dir:
                return {'moved': 0, 'failed': 0}

            # 确保目标目录存在
            FileUtils.create_directory(target_dir)

            moved_count = 0
            failed_count = 0

            for video_id in video_ids:
                # 获取视频信息
                videos = self.db_manager.execute_query(
                    "SELECT id, file_path, file_name FROM videos WHERE id = ?", (video_id,)
                )

                if not videos:
                    failed_count += 1
                    continue

                video = videos[0]
                old_path = video[1]
                file_name = video[2]

                if not FileUtils.file_exists(old_path):
                    logger.warning(f"源文件不存在: {old_path}")
                    failed_count += 1
                    continue

                # 生成新路径
                new_path = os.path.join(target_dir, file_name)

                # 如果目标文件已存在，生成唯一文件名
                counter = 1
                base_name, ext = os.path.splitext(file_name)
                while FileUtils.file_exists(new_path):
                    new_file_name = f"{base_name}_{counter}{ext}"
                    new_path = os.path.join(target_dir, new_file_name)
                    counter += 1

                # 移动文件
                if FileUtils.move_file(old_path, new_path):
                    # 更新数据库
                    if self.db_manager.update_video(video_id, {
                        'file_path': new_path,
                        'source_folder': target_dir
                    }) > 0:
                        moved_count += 1
                        logger.info(f"文件移动成功: {file_name}")
                    else:
                        failed_count += 1
                else:
                    failed_count += 1
                    logger.error(f"文件移动失败: {file_name}")

            return {'moved': moved_count, 'failed': failed_count}

        except Exception as e:
            logger.error(f"批量移动文件失败: {e}")
            return {'moved': 0, 'failed': 0}

    def batch_recalculate_hash(self, video_ids: List[int] = None,
                              progress_callback: Optional[Callable] = None) -> Dict[str, int]:
        """批量重新计算哈希值"""
        try:
            # 如果没有指定ID，则处理所有视频
            if video_ids is None:
                videos = self.db_manager.get_videos()
                video_ids = [video['id'] for video in videos]

            if not video_ids:
                return {'updated': 0, 'failed': 0}

            updated_count = 0
            failed_count = 0

            total = len(video_ids)
            for i, video_id in enumerate(video_ids):
                try:
                    # 获取视频信息
                    videos = self.db_manager.execute_query(
                        "SELECT id, file_path FROM videos WHERE id = ?", (video_id,)
                    )

                    if not videos:
                        failed_count += 1
                        continue

                    video = videos[0]
                    file_path = video[1]

                    if not FileUtils.file_exists(file_path):
                        failed_count += 1
                        continue

                    # 计算哈希值
                    md5_hash = FileUtils.calculate_md5(file_path)
                    file_hash = FileUtils.calculate_file_hash(file_path)
                    file_size = FileUtils.get_file_size(file_path)

                    # 更新数据库
                    if self.db_manager.update_video(video_id, {
                        'md5_hash': md5_hash,
                        'file_hash': file_hash,
                        'file_size': file_size
                    }) > 0:
                        updated_count += 1
                    else:
                        failed_count += 1

                    # 进度回调
                    if progress_callback:
                        progress_callback(i + 1, total, f"处理: {os.path.basename(file_path)}")

                except Exception as e:
                    logger.error(f"计算哈希失败 ID:{video_id}: {e}")
                    failed_count += 1

            return {'updated': updated_count, 'failed': failed_count}

        except Exception as e:
            logger.error(f"批量重新计算哈希失败: {e}")
            return {'updated': 0, 'failed': 0}

class MediaScanner:
    """媒体文件扫描器"""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def scan_folder(self, folder_path: str, recursive: bool = True,
                   progress_callback: Optional[Callable] = None,
                   cancel_check: Optional[Callable] = None) -> Dict[str, int]:
        """扫描文件夹中的媒体文件"""
        try:
            if not FileUtils.directory_exists(folder_path):
                return {'scanned': 0, 'added': 0, 'updated': 0, 'failed': 0}

            # 统计变量
            scanned_count = 0
            added_count = 0
            updated_count = 0
            failed_count = 0

            # 收集所有视频文件
            video_files = list(FileUtils.scan_directory(folder_path, recursive, video_only=True))
            total_files = len(video_files)

            for i, file_path in enumerate(video_files):
                # 检查是否取消
                if cancel_check and cancel_check():
                    break

                try:
                    scanned_count += 1

                    # 进度回调
                    if progress_callback:
                        progress_callback(i + 1, total_files, f"扫描: {os.path.basename(file_path)}")

                    # 检查文件是否已存在
                    existing = self.db_manager.execute_query(
                        "SELECT id, md5_hash, file_size FROM videos WHERE file_path = ?", (file_path,)
                    )

                    # 获取文件信息
                    file_size = FileUtils.get_file_size(file_path)
                    file_name = FileUtils.extract_filename_from_path(file_path)
                    md5_hash = FileUtils.calculate_md5(file_path)
                    file_hash = FileUtils.calculate_file_hash(file_path)
                    duration = FileUtils.get_video_duration(file_path)
                    resolution = FileUtils.get_video_resolution(file_path)
                    created_time = FileUtils.get_file_created_time(file_path)
                    top_folder = FileUtils.get_top_folder(file_path)

                    video_data = {
                        'file_name': file_name,
                        'file_path': file_path,
                        'file_size': file_size,
                        'md5_hash': md5_hash,
                        'file_hash': file_hash,
                        'duration': duration,
                        'resolution': resolution,
                        'file_created_time': created_time,
                        'source_folder': folder_path,
                        'top_folder': top_folder,
                        'is_nas_online': 1
                    }

                    if existing:
                        # 更新现有记录
                        video_id = existing[0][0]
                        old_md5 = existing[0][1]
                        old_size = existing[0][2]

                        # 检查文件是否有变化
                        if old_md5 != md5_hash or old_size != file_size:
                            if self.db_manager.update_video(video_id, video_data) > 0:
                                updated_count += 1
                    else:
                        # 添加新记录
                        if self.db_manager.insert_video(video_data) > 0:
                            added_count += 1

                except Exception as e:
                    logger.error(f"处理文件失败 {file_path}: {e}")
                    failed_count += 1

            return {
                'scanned': scanned_count,
                'added': added_count,
                'updated': updated_count,
                'failed': failed_count
            }

        except Exception as e:
            logger.error(f"扫描文件夹失败 {folder_path}: {e}")
            return {'scanned': 0, 'added': 0, 'updated': 0, 'failed': 0}