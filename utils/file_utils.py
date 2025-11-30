#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件处理工具模块
从media_library.py提取的文件操作功能
"""

import os
import hashlib
import shutil
import subprocess
import platform
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Generator
from datetime import datetime
import cv2
from .logger import get_logger

logger = get_logger("FileUtils")

class FileUtils:
    """文件处理工具类"""

    @staticmethod
    def calculate_md5(file_path: str, chunk_size: int = 8192) -> str:
        """计算文件的MD5哈希值"""
        try:
            md5_hash = hashlib.md5()
            with open(file_path, "rb") as f:
                # 分块读取文件，避免内存占用过大
                while chunk := f.read(chunk_size):
                    md5_hash.update(chunk)
            return md5_hash.hexdigest()
        except Exception as e:
            logger.error(f"计算MD5失败 {file_path}: {e}")
            return ""

    @staticmethod
    def calculate_file_hash(file_path: str) -> str:
        """计算文件哈希值（基于文件内容和大小）"""
        try:
            file_size = os.path.getsize(file_path)
            # 读取文件开头和结尾的部分内容来计算哈希
            with open(file_path, "rb") as f:
                # 读取前1KB和后1KB
                header = f.read(1024)
                f.seek(-min(1024, file_size), 2)
                footer = f.read(1024)

            # 组合文件大小、头部和尾部来计算哈希
            content = str(file_size).encode() + header + footer
            return hashlib.md5(content).hexdigest()
        except Exception as e:
            logger.error(f"计算文件哈希失败 {file_path}: {e}")
            return ""

    @staticmethod
    def get_file_size(file_path: str) -> int:
        """获取文件大小（字节）"""
        try:
            return os.path.getsize(file_path)
        except Exception as e:
            logger.error(f"获取文件大小失败 {file_path}: {e}")
            return 0

    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """格式化文件大小显示"""
        if size_bytes == 0:
            return "0 B"

        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        size = float(size_bytes)

        while size >= 1024.0 and i < len(size_names) - 1:
            size /= 1024.0
            i += 1

        return f"{size:.1f} {size_names[i]}"

    @staticmethod
    def get_video_duration(file_path: str) -> str:
        """获取视频时长"""
        try:
            # 使用OpenCV获取视频信息
            cap = cv2.VideoCapture(file_path)
            if not cap.isOpened():
                return ""

            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)

            cap.release()

            if fps > 0:
                duration_seconds = frame_count / fps
                minutes = int(duration_seconds // 60)
                seconds = int(duration_seconds % 60)
                return f"{minutes:02d}:{seconds:02d}"

        except Exception as e:
            logger.error(f"获取视频时长失败 {file_path}: {e}")

        return ""

    @staticmethod
    def get_video_resolution(file_path: str) -> str:
        """获取视频分辨率"""
        try:
            cap = cv2.VideoCapture(file_path)
            if not cap.isOpened():
                return ""

            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            cap.release()

            if width > 0 and height > 0:
                return f"{width}x{height}"

        except Exception as e:
            logger.error(f"获取视频分辨率失败 {file_path}: {e}")

        return ""

    @staticmethod
    def is_video_file(file_path: str) -> bool:
        """判断是否为视频文件"""
        video_extensions = {
            '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm',
            '.m4v', '.mpg', '.mpeg', '.3gp', '.rmvb', '.rm', '.ts',
            '.mts', '.m2ts', '.vob', '.f4v', '.asf'
        }

        _, ext = os.path.splitext(file_path.lower())
        return ext in video_extensions

    @staticmethod
    def scan_directory(directory: str, recursive: bool = True,
                      video_only: bool = True) -> Generator[str, None, None]:
        """扫描目录中的文件"""
        try:
            if recursive:
                for root, dirs, files in os.walk(directory):
                    for file in files:
                        file_path = os.path.join(root, file)
                        if not video_only or FileUtils.is_video_file(file_path):
                            yield file_path
            else:
                for file in os.listdir(directory):
                    file_path = os.path.join(directory, file)
                    if os.path.isfile(file_path):
                        if not video_only or FileUtils.is_video_file(file_path):
                            yield file_path
        except Exception as e:
            logger.error(f"扫描目录失败 {directory}: {e}")

    @staticmethod
    def file_exists(file_path: str) -> bool:
        """检查文件是否存在"""
        try:
            return os.path.isfile(file_path)
        except Exception:
            return False

    @staticmethod
    def directory_exists(dir_path: str) -> bool:
        """检查目录是否存在"""
        try:
            return os.path.isdir(dir_path)
        except Exception:
            return False

    @staticmethod
    def create_directory(dir_path: str) -> bool:
        """创建目录"""
        try:
            os.makedirs(dir_path, exist_ok=True)
            return True
        except Exception as e:
            logger.error(f"创建目录失败 {dir_path}: {e}")
            return False

    @staticmethod
    def move_file(src: str, dst: str) -> bool:
        """移动文件"""
        try:
            # 确保目标目录存在
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(src, dst)
            return True
        except Exception as e:
            logger.error(f"移动文件失败 {src} -> {dst}: {e}")
            return False

    @staticmethod
    def copy_file(src: str, dst: str) -> bool:
        """复制文件"""
        try:
            # 确保目标目录存在
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            return True
        except Exception as e:
            logger.error(f"复制文件失败 {src} -> {dst}: {e}")
            return False

    @staticmethod
    def delete_file(file_path: str, use_trash: bool = True) -> bool:
        """删除文件"""
        try:
            if use_trash:
                from send2trash import send2trash
                send2trash(file_path)
            else:
                os.remove(file_path)
            return True
        except Exception as e:
            logger.error(f"删除文件失败 {file_path}: {e}")
            return False

    @staticmethod
    def get_file_created_time(file_path: str) -> Optional[datetime]:
        """获取文件创建时间"""
        try:
            if platform.system() == "Windows":
                # Windows系统
                timestamp = os.path.getctime(file_path)
            else:
                # Unix-like系统
                stat = os.stat(file_path)
                timestamp = stat.st_birthtime if hasattr(stat, 'st_birthtime') else stat.st_mtime

            return datetime.fromtimestamp(timestamp)
        except Exception as e:
            logger.error(f"获取文件创建时间失败 {file_path}: {e}")
            return None

    @staticmethod
    def get_file_modified_time(file_path: str) -> Optional[datetime]:
        """获取文件修改时间"""
        try:
            timestamp = os.path.getmtime(file_path)
            return datetime.fromtimestamp(timestamp)
        except Exception as e:
            logger.error(f"获取文件修改时间失败 {file_path}: {e}")
            return None

    @staticmethod
    def extract_filename_from_path(file_path: str) -> str:
        """从路径中提取文件名"""
        try:
            return os.path.basename(file_path)
        except Exception:
            return ""

    @staticmethod
    def get_directory_from_path(file_path: str) -> str:
        """从路径中提取目录"""
        try:
            return os.path.dirname(file_path)
        except Exception:
            return ""

    @staticmethod
    def get_top_folder(file_path: str) -> str:
        """获取顶级文件夹名称"""
        try:
            # 将路径标准化
            path = os.path.normpath(file_path)
            parts = path.split(os.sep)

            # 查找videos或类似的顶级目录
            video_keywords = ['videos', 'video', 'movies', 'movie', 'media']

            for i, part in enumerate(parts):
                if part.lower() in video_keywords and i + 1 < len(parts):
                    return parts[i + 1]

            # 如果没找到关键词，返回倒数第二级目录
            if len(parts) >= 2:
                return parts[-2]

            return ""
        except Exception as e:
            logger.error(f"获取顶级文件夹失败 {file_path}: {e}")
            return ""

    @staticmethod
    def open_file_manager(file_path: str) -> bool:
        """在文件管理器中打开文件"""
        try:
            if platform.system() == "Windows":
                subprocess.run(["explorer", "/select,", file_path])
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", "-R", file_path])
            else:  # Linux
                subprocess.run(["xdg-open", os.path.dirname(file_path)])
            return True
        except Exception as e:
            logger.error(f"打开文件管理器失败 {file_path}: {e}")
            return False

    @staticmethod
    def open_file(file_path: str) -> bool:
        """使用默认程序打开文件"""
        try:
            if platform.system() == "Windows":
                os.startfile(file_path)
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", file_path])
            else:  # Linux
                subprocess.run(["xdg-open", file_path])
            return True
        except Exception as e:
            logger.error(f"打开文件失败 {file_path}: {e}")
            return False

    @staticmethod
    def clean_filename(filename: str) -> str:
        """清理文件名，移除非法字符"""
        # Windows非法字符
        illegal_chars = '<>:"/\\|?*'
        for char in illegal_chars:
            filename = filename.replace(char, '_')

        # 移除前后空格和点
        filename = filename.strip(' .')

        # 限制长度
        if len(filename) > 200:
            name, ext = os.path.splitext(filename)
            filename = name[:200-len(ext)] + ext

        return filename

    @staticmethod
    def find_duplicate_files(directory: str) -> Dict[str, List[str]]:
        """查找目录中的重复文件（基于MD5）"""
        file_hashes = {}
        duplicates = {}

        try:
            for file_path in FileUtils.scan_directory(directory, recursive=True):
                if not FileUtils.file_exists(file_path):
                    continue

                md5_hash = FileUtils.calculate_md5(file_path)
                if md5_hash:
                    if md5_hash not in file_hashes:
                        file_hashes[md5_hash] = []
                    file_hashes[md5_hash].append(file_path)

            # 找出重复的文件
            for md5_hash, files in file_hashes.items():
                if len(files) > 1:
                    duplicates[md5_hash] = files

        except Exception as e:
            logger.error(f"查找重复文件失败 {directory}: {e}")

        return duplicates

    @staticmethod
    def get_drive_info(path: str) -> Dict[str, Any]:
        """获取驱动器信息"""
        try:
            if platform.system() == "Windows":
                import psutil
                partition = psutil.disk_usage(path)
                return {
                    'total': partition.total,
                    'used': partition.used,
                    'free': partition.free,
                    'percent_used': (partition.used / partition.total) * 100
                }
            else:
                stat = os.statvfs(path)
                total = stat.f_frsize * stat.f_blocks
                free = stat.f_frsize * stat.f_bavail
                used = total - free
                return {
                    'total': total,
                    'used': used,
                    'free': free,
                    'percent_used': (used / total) * 100
                }
        except Exception as e:
            logger.error(f"获取驱动器信息失败 {path}: {e}")
            return {}