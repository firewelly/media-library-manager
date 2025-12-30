#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
维护工具管理器
包含文件整理、数据清洗、一致性检查等功能
"""

import os
from typing import List, Dict, Callable, Optional, Any
from .database import DatabaseManager
from .file_utils import FileUtils
from .media_extensions import DuplicateManager
from .logger import get_logger

logger = get_logger("Maintenance")

class MaintenanceManager:
    """维护工具管理器"""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.duplicate_manager = DuplicateManager(db_manager)

    def find_duplicates(self, criteria: str = 'md5') -> List[Dict]:
        """
        查找重复文件
        :param criteria: 'md5' 或 'smart' (这里暂时都映射到MD5和文件哈希)
        """
        # DuplicateManager 已经实现了 find_duplicate_files，返回MD5和Hash重复
        # 如果需要"智能去重"（可能指内容分析），目前暂未实现，回退到普通去重
        return self.duplicate_manager.find_duplicate_files()

    def clean_actor_data(self) -> Dict[str, int]:
        """清理无效的演员数据"""
        try:
            # 1. 清理孤立的演员关联 (视频不存在)
            self.db_manager.cursor.execute("""
                DELETE FROM video_actors 
                WHERE video_id NOT IN (SELECT id FROM videos)
            """)
            orphaned_relations = self.db_manager.cursor.rowcount

            # 2. 清理没有关联视频的演员
            self.db_manager.cursor.execute("""
                DELETE FROM actors 
                WHERE id NOT IN (SELECT DISTINCT actor_id FROM video_actors)
            """)
            unused_actors = self.db_manager.cursor.rowcount
            
            self.db_manager.conn.commit()
            
            return {
                'orphaned_relations': orphaned_relations,
                'unused_actors': unused_actors
            }
        except Exception as e:
            logger.error(f"清理演员数据失败: {e}")
            return {'error': str(e)}

    def sync_stars_to_filename(self, video_ids: List[int] = None,
                             progress_callback: Optional[Callable[[str, int, dict], None]] = None,
                             cancel_check: Optional[Callable[[], bool]] = None) -> Dict[str, int]:
        """
        将星级同步到文件名 (使用 ! 前缀)
        5星=!!!!, 4星=!!!, 3星=!!, 2星=!
        """
        if video_ids:
            # 获取指定视频
            placeholders = ','.join(['?' for _ in video_ids])
            query = f"SELECT id, file_path, stars FROM videos WHERE id IN ({placeholders})"
            self.db_manager.cursor.execute(query, video_ids)
        else:
            # 获取所有视频
            self.db_manager.cursor.execute("SELECT id, file_path, stars FROM videos")
            
        videos = self.db_manager.cursor.fetchall()
        total = len(videos)
        renamed_count = 0
        failed_count = 0
        skipped_count = 0

        for i, (vid, file_path, stars) in enumerate(videos):
            if cancel_check and cancel_check():
                break
                
            if not file_path or not os.path.exists(file_path):
                failed_count += 1
                continue
                
            directory = os.path.dirname(file_path)
            filename = os.path.basename(file_path)
            
            # 移除现有的 ! 前缀
            clean_name = filename.lstrip('!')
            
            # 计算需要的前缀
            prefix = ""
            stars = stars or 0
            if stars >= 5:
                prefix = "!!!!"
            elif stars == 4:
                prefix = "!!!"
            elif stars == 3:
                prefix = "!!"
            elif stars == 2:
                prefix = "!"
            
            new_filename = prefix + clean_name
            
            if new_filename != filename:
                if progress_callback:
                    progress_callback(f"重命名: {filename} -> {new_filename}", int((i / total) * 100))
                    
                new_path = os.path.join(directory, new_filename)
                try:
                    if FileUtils.move_file(file_path, new_path):
                        self.db_manager.update_video(vid, {
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
                skipped_count += 1
                
        return {'renamed': renamed_count, 'failed': failed_count, 'skipped': skipped_count}

    def scan_for_file_move(self, source_dir: str, 
                          progress_callback: Optional[Callable[[str, int, dict], None]] = None,
                          cancel_check: Optional[Callable[[], bool]] = None) -> List[Dict]:
        """
        扫描目录中的视频文件，用于文件移动管理器
        返回文件列表及数据库状态
        """
        results = []
        if not os.path.exists(source_dir):
            return results
            
        video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'}
        
        # 收集所有文件
        all_files = []
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                if any(file.lower().endswith(ext) for ext in video_extensions):
                    all_files.append(os.path.join(root, file))
                    
        total = len(all_files)
        
        for i, file_path in enumerate(all_files):
            if cancel_check and cancel_check():
                break
                
            if progress_callback:
                progress_callback(f"扫描: {os.path.basename(file_path)}", int((i / total) * 100))
                
            file_size = os.path.getsize(file_path)
            
            # 检查数据库状态
            self.db_manager.cursor.execute("SELECT id FROM videos WHERE file_path = ?", (file_path,))
            row = self.db_manager.cursor.fetchone()
            in_db = row is not None
            
            results.append({
                'file_path': file_path,
                'file_name': os.path.basename(file_path),
                'file_size': file_size,
                'in_db': in_db,
                'video_id': row[0] if row else None
            })
            
        return results
