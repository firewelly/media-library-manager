# -*- coding: utf-8 -*-
"""
视频操作模块
播放、打开文件夹、删除、旋转等
"""

import os
import subprocess
import platform
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class VideoActions:
    """视频操作"""

    def __init__(self, db, parent_window=None):
        self.db = db
        self.parent = parent_window

    def play_video(self, video_id: int) -> bool:
        """播放视频"""
        row = self.db.execute_one(
            "SELECT file_path FROM videos WHERE id = ?", (video_id,)
        )
        if not row:
            logger.error(f"视频不存在: {video_id}")
            return False

        file_path = row["file_path"]
        if not os.path.isfile(file_path):
            logger.error(f"文件不存在: {file_path}")
            return False

        try:
            system = platform.system()
            if system == "Darwin":  # macOS
                subprocess.Popen(["open", file_path])
            elif system == "Windows":
                os.startfile(file_path)
            else:  # Linux
                subprocess.Popen(["xdg-open", file_path])
            return True
        except Exception as e:
            logger.error(f"播放失败: {e}")
            return False

    def open_folder(self, video_id: int) -> bool:
        """打开视频所在文件夹"""
        row = self.db.execute_one(
            "SELECT file_path FROM videos WHERE id = ?", (video_id,)
        )
        if not row:
            return False

        file_path = row["file_path"]
        folder = os.path.dirname(file_path)

        if not os.path.isdir(folder):
            logger.error(f"文件夹不存在: {folder}")
            return False

        try:
            system = platform.system()
            if system == "Darwin":
                subprocess.Popen(["open", folder])
            elif system == "Windows":
                subprocess.Popen(["explorer", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
            return True
        except Exception as e:
            logger.error(f"打开文件夹失败: {e}")
            return False

    def delete_video(self, video_id: int, delete_file: bool = False) -> bool:
        """删除视频记录（可选删除文件）"""
        try:
            if delete_file:
                row = self.db.execute_one(
                    "SELECT file_path FROM videos WHERE id = ?", (video_id,)
                )
                if row and os.path.isfile(row["file_path"]):
                    # 使用 send2trash 安全删除
                    try:
                        from send2trash import send2trash
                        send2trash(row["file_path"])
                    except ImportError:
                        os.remove(row["file_path"])

            # 删除关联记录
            self.db.execute_write("DELETE FROM video_actors WHERE video_id = ?", (video_id,))
            self.db.execute_write(
                "DELETE FROM javdb_info_tags WHERE javdb_info_id IN (SELECT id FROM javdb_info WHERE video_id = ?)",
                (video_id,)
            )
            self.db.execute_write("DELETE FROM javdb_info WHERE video_id = ?", (video_id,))
            self.db.execute_write("DELETE FROM videos WHERE id = ?", (video_id,))

            return True
        except Exception as e:
            logger.error(f"删除失败: {e}")
            return False

    def rotate_video(self, video_id: int, degrees: int) -> bool:
        """旋转视频（90/180/270度）"""
        row = self.db.execute_one(
            "SELECT file_path FROM videos WHERE id = ?", (video_id,)
        )
        if not row:
            return False

        file_path = row["file_path"]
        if not os.path.isfile(file_path):
            return False

        # 使用 ffmpeg 旋转
        temp_path = file_path + ".rotated.mp4"
        transpose_map = {90: "1", 180: "2,2", 270: "3"}
        transpose = transpose_map.get(degrees, "1")

        cmd = [
            "ffmpeg", "-i", file_path,
            "-vf", f"transpose={transpose}",
            "-c:a", "copy",
            "-y", temp_path
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, timeout=3600)
            if result.returncode == 0:
                # 替换原文件
                os.replace(temp_path, file_path)
                return True
            else:
                logger.error(f"ffmpeg 失败: {result.stderr.decode()}")
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                return False
        except Exception as e:
            logger.error(f"旋转失败: {e}")
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return False

    def move_video(self, video_id: int, target_folder: str) -> bool:
        """移动视频到指定文件夹"""
        row = self.db.execute_one(
            "SELECT file_path, file_name FROM videos WHERE id = ?", (video_id,)
        )
        if not row:
            return False

        source_path = row["file_path"]
        if not os.path.isfile(source_path):
            return False

        target_path = os.path.join(target_folder, row["file_name"])

        try:
            import shutil
            shutil.move(source_path, target_path)
            # 更新数据库
            self.db.execute_write(
                "UPDATE videos SET file_path = ?, source_folder = ? WHERE id = ?",
                (target_path, target_folder, video_id)
            )
            return True
        except Exception as e:
            logger.error(f"移动失败: {e}")
            return False

    def generate_thumbnail(self, video_id: int) -> bool:
        """生成视频封面"""
        row = self.db.execute_one(
            "SELECT file_path FROM videos WHERE id = ?", (video_id,)
        )
        if not row:
            return False

        file_path = row["file_path"]
        if not os.path.isfile(file_path):
            return False

        # 生成缩略图路径
        thumb_path = file_path.rsplit(".", 1)[0] + "_thumb.jpg"

        # 使用 ffmpeg 提取第 10 秒的帧
        cmd = [
            "ffmpeg", "-i", file_path,
            "-ss", "00:00:10",
            "-vframes", "1",
            "-vf", "scale=320:-1",
            "-y", thumb_path
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, timeout=60)
            if result.returncode == 0 and os.path.isfile(thumb_path):
                # 更新数据库
                with open(thumb_path, "rb") as f:
                    thumb_data = f.read()
                self.db.execute_write(
                    "UPDATE videos SET thumbnail_path = ?, thumbnail_data = ? WHERE id = ?",
                    (thumb_path, thumb_data, video_id)
                )
                return True
            return False
        except Exception as e:
            logger.error(f"生成封面失败: {e}")
            return False
