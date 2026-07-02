#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
媒体库扩展功能模块
从media_library.py提取的核心业务功能，适配到PySide6界面
"""

import os
import base64
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

            # 解析演员（含头像URL）
            actors = []
            actor_thumbs = {}
            for actor in root.findall('.//actor'):
                name_element = actor.find('name')
                if name_element is not None and name_element.text:
                    actor_name = name_element.text.strip()
                    actors.append(actor_name)
                    thumb_element = actor.find('thumb')
                    if thumb_element is not None and thumb_element.text:
                        actor_thumbs[actor_name] = thumb_element.text.strip()
            if actors:
                nfo_data['actors'] = ', '.join(actors)
            if actor_thumbs:
                nfo_data['actor_thumbs'] = actor_thumbs

            # 解析年份（优先用premiered的年份）
            year_element = root.find('.//year')
            if year_element is not None:
                try:
                    nfo_data['year'] = int(year_element.text)
                except ValueError:
                    pass
            premiered_element = root.find('.//premiered')
            if premiered_element is not None and premiered_element.text and 'year' not in nfo_data:
                try:
                    nfo_data['year'] = int(premiered_element.text[:4])
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

            # 解析片商
            studio_element = root.find('.//studio')
            if studio_element is not None and studio_element.text:
                nfo_data['studio'] = studio_element.text.strip()

            # 解析番号
            uniqueid_element = root.find('.//uniqueid')
            if uniqueid_element is not None and uniqueid_element.text:
                nfo_data['javdb_code'] = uniqueid_element.text.strip()

            logger.info(f"NFO解析完成: {nfo_file_path}")
            return nfo_data

        except Exception as e:
            logger.error(f"NFO文件解析失败 {nfo_file_path}: {e}")
            return {}

    def _find_cover_image(self, video_dir: str, video_name: str) -> Optional[str]:
        """查找视频同目录下的封面图片"""
        # 按优先级查找封面图片
        cover_candidates = [
            os.path.join(video_dir, f"{video_name}-poster.jpg"),
            os.path.join(video_dir, f"{video_name}.jpg"),
            os.path.join(video_dir, "poster.jpg"),
            os.path.join(video_dir, "folder.jpg"),
            os.path.join(video_dir, "cover.jpg"),
        ]
        for candidate in cover_candidates:
            if os.path.exists(candidate):
                return candidate
        return None

    def _load_image_as_base64(self, image_path: str) -> Optional[str]:
        """读取图片文件为base64编码"""
        try:
            with open(image_path, 'rb') as f:
                data = f.read()
            return base64.b64encode(data).decode('utf-8')
        except Exception as e:
            logger.error(f"读取图片失败 {image_path}: {e}")
            return None

    def _sync_actor_thumbs(self, actor_thumbs: Dict[str, str]) -> int:
        """将NFO中的演员头像URL同步到actors表"""
        updated = 0
        for actor_name, thumb_url in actor_thumbs.items():
            try:
                result = self.db_manager.execute_update(
                    "UPDATE actors SET avatar_url = ?, updated_at = CURRENT_TIMESTAMP "
                    "WHERE name = ? AND (avatar_url IS NULL OR avatar_url = '')",
                    (thumb_url, actor_name)
                )
                updated += result
            except Exception as e:
                logger.error(f"更新演员头像失败 {actor_name}: {e}")
        return updated

    def _update_javdb_info_from_nfo(self, video_id: int, javdb_fields: Dict[str, Any]):
        """将NFO中的番号/片商等字段更新到javdb_info表"""
        try:
            # 检查是否已有 javdb_info 记录
            existing = self.db_manager.execute_query(
                "SELECT id FROM javdb_info WHERE video_id = ?", (video_id,)
            )
            if existing:
                # 有记录则补充缺失字段（不覆盖已有值）
                set_clauses = []
                values = []
                field_map = {
                    'javdb_code': 'javdb_code',
                    'release_date': 'release_date',
                    'studio': 'studio',
                    'director': None,  # javdb_info无director字段，跳过
                }
                for nfo_key, db_key in field_map.items():
                    if db_key and nfo_key in javdb_fields and javdb_fields[nfo_key]:
                        set_clauses.append(f"{db_key} = CASE WHEN {db_key} IS NULL OR {db_key} = '' THEN ? ELSE {db_key} END")
                        values.append(javdb_fields[nfo_key])
                if set_clauses:
                    set_clauses.append("updated_at = CURRENT_TIMESTAMP")
                    values.append(video_id)
                    self.db_manager.execute_update(
                        f"UPDATE javdb_info SET {', '.join(set_clauses)} WHERE video_id = ?",
                        tuple(values)
                    )
            else:
                # 无记录则插入（至少要有番号）
                code = javdb_fields.get('javdb_code', '')
                if code:
                    self.db_manager.execute_update(
                        "INSERT INTO javdb_info (video_id, javdb_code, release_date, studio, created_at, updated_at) "
                        "VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
                        (video_id, code, javdb_fields.get('release_date'), javdb_fields.get('studio'))
                    )
        except Exception as e:
            logger.error(f"更新javdb_info失败 video_id={video_id}: {e}")

    def _sync_video_actors(self, video_id: int, actors_str: str) -> List[str]:
        """将NFO中的演员字符串同步到video_actors关联表
        
        匹配顺序：name精确 → name_traditional → name_common → aliases模糊 → 创建新演员
        Returns:
            未匹配到已有演员（创建了新演员）的名字列表
        """
        unmatched = []
        try:
            actor_names = [a.strip() for a in actors_str.split(',') if a.strip()]
            for actor_name in actor_names:
                actor_id = None

                # 1. 精确匹配 name
                result = self.db_manager.execute_query(
                    "SELECT id FROM actors WHERE name = ?", (actor_name,)
                )
                if result:
                    actor_id = result[0][0]

                # 2. 匹配 name_traditional（繁体名）
                if not actor_id:
                    result = self.db_manager.execute_query(
                        "SELECT id FROM actors WHERE name_traditional = ?", (actor_name,)
                    )
                    if result:
                        actor_id = result[0][0]

                # 3. 匹配 name_common（常用名）
                if not actor_id:
                    result = self.db_manager.execute_query(
                        "SELECT id FROM actors WHERE name_common = ?", (actor_name,)
                    )
                    if result:
                        actor_id = result[0][0]

                # 4. 模糊匹配 aliases（别名）
                if not actor_id:
                    result = self.db_manager.execute_query(
                        "SELECT id FROM actors WHERE aliases LIKE ?", (f'%{actor_name}%',)
                    )
                    if result:
                        actor_id = result[0][0]

                # 5. 都没匹配到，创建新演员
                if not actor_id:
                    self.db_manager.execute_update(
                        "INSERT INTO actors (name, created_at, updated_at) VALUES (?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
                        (actor_name,)
                    )
                    created = self.db_manager.execute_query(
                        "SELECT id FROM actors WHERE name = ?", (actor_name,)
                    )
                    actor_id = created[0][0] if created else None
                    if actor_id:
                        unmatched.append(actor_name)

                # 建立关联（忽略已存在的）
                if actor_id:
                    self.db_manager.execute_update(
                        "INSERT OR IGNORE INTO video_actors (video_id, actor_id, created_at) "
                        "VALUES (?, ?, CURRENT_TIMESTAMP)",
                        (video_id, actor_id)
                    )
        except Exception as e:
            logger.error(f"同步演员关联失败 video_id={video_id}: {e}")
        
        return unmatched

    def import_nfo_for_video(self, video_id: int, video_path: str, return_unmatched: bool = False):
        """为指定视频导入NFO信息（含封面图片和演员头像）
        
        Args:
            video_id: 视频ID
            video_path: 视频文件路径
            return_unmatched: 是否返回未匹配的演员名列表
            
        Returns:
            默认返回 bool（是否成功）；
            return_unmatched=True 时返回 (bool, List[str])，第二个元素是未匹配到已有演员的名字列表
        """
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

            # 查找并导入封面图片
            cover_path = self._find_cover_image(video_dir, video_name)
            if cover_path:
                cover_b64 = self._load_image_as_base64(cover_path)
                if cover_b64:
                    nfo_data['thumbnail_data'] = cover_b64
                    nfo_data['thumbnail_path'] = cover_path
                    logger.info(f"导入封面: {os.path.basename(cover_path)}")

            # 提取演员头像URL（单独处理）
            actor_thumbs = nfo_data.pop('actor_thumbs', {})

            # 提取演员列表（单独处理）
            actors_str = nfo_data.pop('actors', '')
            
            # 提取需要写入 javdb_info 表的字段（不在 videos 表里）
            javdb_fields = {}
            for field in ['release_date', 'studio', 'javdb_code']:
                if field in nfo_data:
                    javdb_fields[field] = nfo_data.pop(field)

            # 剩余的 nfo_data 都是 videos 表的合法字段
            # 更新 videos 表
            success = True
            if nfo_data:
                try:
                    self.db_manager.update_video(video_id, nfo_data)
                except Exception as e:
                    logger.error(f"更新videos表失败: {e}")
                    success = False

            # 更新 javdb_info 表（如果NFO有番号/片商等额外信息）
            if javdb_fields:
                self._update_javdb_info_from_nfo(video_id, javdb_fields)

            # 同步演员关联到 video_actors 表
            unmatched_actors = []
            if actors_str:
                unmatched_actors = self._sync_video_actors(video_id, actors_str)

            # 同步演员头像URL到actors表
            if actor_thumbs:
                self._sync_actor_thumbs(actor_thumbs)

            if return_unmatched:
                return success, unmatched_actors
            return success

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