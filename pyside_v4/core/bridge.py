# -*- coding: utf-8 -*-
"""
pyside_v4.core.bridge — 薄适配层
直接 import media_library_pyside.py 的 MediaLibraryCore，不复制代码
"""

import sys
import os
import logging

logger = logging.getLogger(__name__)

# 确保项目根目录在 sys.path 中
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# 直接 import 已有后端，不创建 copy
from media_library_pyside import MediaLibraryCore, GenericWorker  # noqa: E402

__all__ = ['Bridge', 'MediaLibraryCore', 'GenericWorker']


class Bridge:
    """pyside_v4 适配层
    
    封装 MediaLibraryCore，提供 Qt Signal 友好的接口。
    所有后端逻辑由 MediaLibraryCore 处理，本类不包含业务逻辑。
    """

    def __init__(self):
        self.core = MediaLibraryCore()
        logger.info(f"Bridge 初始化完成，数据库: {self.core.db_path}")

    @property
    def conn(self):
        return self.core.conn

    @property
    def cursor(self):
        return self.core.cursor

    @property
    def db_manager(self):
        return self.core.db_manager

    @property
    def batch_manager(self):
        return self.core.batch_manager

    @property
    def maintenance_manager(self):
        return self.core.maintenance_manager

    @property
    def column_config(self):
        return self.core.column_config

    # ---------- 代理方法（直接转发，不加逻辑） ----------

    def get_all_videos(self, where_clause=None, params=None, order_clause="ORDER BY title"):
        return self.core.get_all_videos(where_clause, params, order_clause)

    def update_video(self, video_id, **kwargs):
        return self.core.update_video(video_id, **kwargs)

    def delete_video(self, video_id):
        return self.core.delete_video(video_id)

    def move_file(self, video_id, old_file_path, target_folder):
        return self.core.move_file(video_id, old_file_path, target_folder)

    def is_video_online(self, video_id):
        return self.core.is_video_online(video_id)

    def check_nas_status(self, file_path):
        return self.core.check_nas_status(file_path)

    def get_video_info(self, file_path):
        return self.core.get_video_info(file_path)

    def calculate_md5_hash(self, file_path):
        return self.core.calculate_md5_hash(file_path)

    def add_video_to_db(self, file_path, folder_type):
        return self.core.add_video_to_db(file_path, folder_type)

    def get_online_folders(self):
        return self.core.get_online_folders()

    def clean_filename_for_video(self, video_id):
        return self.core.clean_filename_for_video(video_id)

    def auto_tag_video(self, video_path, use_retry=False):
        return self.core.auto_tag_video(video_path, use_retry)

    def search_videos(self, **kwargs):
        return self.core.search_videos(**kwargs)

    def scan_media_files(self, progress_callback=None, cancel_check=None):
        return self.core.scan_media_files(progress_callback, cancel_check)

    def import_nfo_file(self, nfo_file_path, video_id=None, video_path=None):
        return self.core.import_nfo_file(nfo_file_path, video_id, video_path)

    def generate_thumbnail_for_video(self, video_path, output_path=None, seek_time="00:00:10"):
        return self.core.generate_thumbnail_for_video(video_path, output_path, seek_time)

    def set_actor_favorite(self, actor_id, is_favorite):
        return self.core.set_actor_favorite(actor_id, is_favorite)

    def save_column_config(self):
        return self.core.save_column_config()

    def load_column_config(self):
        return self.core.load_column_config()

    def close(self):
        """关闭数据库连接"""
        try:
            if self.core.conn:
                self.core.conn.close()
        except Exception:
            pass
