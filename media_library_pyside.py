#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PySide6版本的媒体库管理器
通过导入现有模块的方式重构GUI，保持原有功能完全不变
"""

import sys
import os
import sqlite3
import threading
import json
from datetime import datetime
from pathlib import Path

# PySide6 导入
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QLineEdit, QTextEdit, QPushButton, QFrame,
    QTreeWidget, QTreeWidgetItem, QCheckBox, QRadioButton, QButtonGroup,
    QMenuBar, QMenu, QStatusBar, QSplitter, QScrollArea, QGroupBox,
    QProgressBar, QFileDialog, QMessageBox, QDialog, QDialogButtonBox,
    QSpinBox, QComboBox, QTabWidget, QToolBar, QListWidget, QListWidgetItem,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QInputDialog
)
from PySide6.QtCore import Qt, QTimer, Signal, QObject, QThread, QPoint, QKeyCombination
from PySide6.QtGui import QPixmap, QFont, QIcon, QKeySequence, QStandardItemModel, QStandardItem, QColor, QImage, QAction
from PIL import Image
import io
import base64
import subprocess
import tempfile
import hashlib

# 导入现有模块的功能部分，排除GUI相关代码
import importlib
import media_library as ml_module
from gui_adapter import setup_full_integration
from utils import jav as utils_jav

# 导入非GUI类和函数
class LogLevel:
    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3
    CRITICAL = 4

CURRENT_LOG_LEVEL = LogLevel.INFO
LOG_TO_CONSOLE = True
LOG_TO_GUI = True

def set_log_level(level):
    global CURRENT_LOG_LEVEL
    CURRENT_LOG_LEVEL = level

def log_debug(message, gui_log_func=None):
    if CURRENT_LOG_LEVEL <= LogLevel.DEBUG:
        _output_log_qt("DEBUG", message, gui_log_func)

def log_info(message, gui_log_func=None):
    if CURRENT_LOG_LEVEL <= LogLevel.INFO:
        _output_log_qt("INFO", message, gui_log_func)

def log_warning(message, gui_log_func=None):
    if CURRENT_LOG_LEVEL <= LogLevel.WARNING:
        _output_log_qt("WARNING", message, gui_log_func)

def log_error(message, gui_log_func=None):
    if CURRENT_LOG_LEVEL <= LogLevel.ERROR:
        _output_log_qt("ERROR", message, gui_log_func)

def log_critical(message, gui_log_func=None):
    if CURRENT_LOG_LEVEL <= LogLevel.CRITICAL:
        _output_log_qt("CRITICAL", message, gui_log_func)

class ProgressUpdateManager:
    def __init__(self, update_interval=10):
        self.update_interval = update_interval
        self.last_update_count = 0

    def should_update(self, current_count, total_count=None, force_update=False):
        if force_update:
            return True
        if total_count and current_count >= total_count:
            return True
        if current_count - self.last_update_count >= self.update_interval:
            self.last_update_count = current_count
            return True
        return False

    def update_progress(self, progress_var, status_var, current_count, total_count, status_text, progress_window=None, update_stats_func=None, *args):
        if self.should_update(current_count, total_count):
            if progress_var is not None:
                progress = (current_count / total_count) * 100 if total_count and total_count > 0 else 0
                try:
                    progress_var(progress)
                except Exception:
                    pass
            if status_var is not None:
                try:
                    status_var(status_text)
                except Exception:
                    pass
            if update_stats_func:
                try:
                    update_stats_func(*args)
                except Exception:
                    pass
            if progress_window is not None:
                try:
                    progress_window.update()
                except Exception:
                    pass

class ProgressWindow:
    def destroy(self):
        try:
            pass
        except Exception:
            pass

class QtLogHandler(QObject):
    """用于将日志信号发送到GUI的处理器"""
    log_signal = Signal(str)

# 创建全局日志处理器实例
qt_log_handler = QtLogHandler()

def _output_log_qt(level, message, gui_log_func=None):
    """输出日志的内部函数，兼容Qt信号"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    formatted_message = f"[{level}] {message}"

    if LOG_TO_CONSOLE:
        print(f"{timestamp} - {formatted_message}")
    if LOG_TO_GUI:
        qt_log_handler.log_signal.emit(formatted_message)

# 替换原有的日志函数
def init_qt_logging():
    """初始化Qt日志系统"""
    import media_library
    media_library._output_log = _output_log_qt
global _output_log
_output_log = _output_log_qt

class MediaLibraryCore:
    """媒体库核心功能类，复用原有的非GUI逻辑"""

    def __init__(self):
        # 配置文件路径
        self.config_path = os.path.join(os.path.dirname(__file__), 'gui_config.json')

        # 默认列配置
        self.default_columns = {
            'title': {'width': 300, 'position': 0, 'text': '标题'},
            'file_name': {'width': 200, 'position': 1, 'text': '文件名'},
            'stars': {'width': 75, 'position': 2, 'text': '星级'},
            'tags': {'width': 120, 'position': 3, 'text': '标签'},
            'file_size': {'width': 80, 'position': 4, 'text': '大小'},
            'duration': {'width': 80, 'position': 5, 'text': '时长'},
            'resolution': {'width': 100, 'position': 6, 'text': '分辨率'},
            'year': {'width': 60, 'position': 7, 'text': '年份'},
            'is_nas_online': {'width': 60, 'position': 8, 'text': '在线'},
            'source_folder': {'width': 150, 'position': 9, 'text': '来源文件夹'},
            'file_created_time': {'width': 120, 'position': 10, 'text': '文件创建时间'},
            'created_at': {'width': 120, 'position': 11, 'text': '入库时间'},
            'javdb_code': {'width': 100, 'position': 12, 'text': '番号'},
            'javdb_title': {'width': 250, 'position': 13, 'text': 'JAVDB标题'},
            'javdb_rating': {'width': 80, 'position': 14, 'text': 'JAVDB评分'},
            'file_path': {'width': 400, 'position': 15, 'text': '文件路径'}
        }

        # 初始化数据库连接
        self.init_database()
        print("数据库初始化完成")

        # 加载列配置
        self.load_column_config()

        # 当前选中的视频
        self.current_video = None

        # 排序状态
        self.sort_column_name = None
        self.sort_reverse = False

        # GPU加速状态
        self.gpu_acceleration = None
        self.check_gpu_acceleration_status()

    def __del__(self):
        """析构函数，确保数据库连接被正确关闭"""
        try:
            if hasattr(self, 'conn') and self.conn:
                self.conn.close()
        except:
            pass

    def load_column_config(self):
        """加载列配置"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    saved_config = json.load(f)
                    self.column_config = saved_config.get('columns', self.default_columns.copy())
            else:
                self.column_config = self.default_columns.copy()
        except Exception as e:
            print(f"加载配置失败: {e}")
            self.column_config = self.default_columns.copy()

    def save_column_config(self):
        """保存列配置"""
        try:
            config_data = {
                'columns': self.column_config
            }
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存配置失败: {e}")

    def init_database(self):
        """仅连接现有SQLite数据库，不创建或修改任何表结构"""
        self.db_path = os.path.join(os.path.dirname(__file__), 'media_library.db')
        db_exists = os.path.exists(self.db_path)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()

        if db_exists:
            print("已连接到现有数据库（不进行建表或迁移）")
        else:
            print("数据库不存在：请先使用原始 media_library.py 初始化数据库或导入备份")

    def migrate_database(self):
        """数据库迁移：添加新字段"""
        try:
            # 检查videos表是否需要添加新字段
            self.cursor.execute("PRAGMA table_info(videos)")
            video_columns = [column[1] for column in self.cursor.fetchall()]

            # 添加videos表缺失的字段
            if 'thumbnail_data' not in video_columns:
                self.cursor.execute('ALTER TABLE videos ADD COLUMN thumbnail_data BLOB')
                print("添加字段: thumbnail_data")

            if 'thumbnail_path' not in video_columns:
                self.cursor.execute('ALTER TABLE videos ADD COLUMN thumbnail_path TEXT')
                print("添加字段: thumbnail_path")

            if 'duration' not in video_columns:
                self.cursor.execute('ALTER TABLE videos ADD COLUMN duration INTEGER')
                print("添加字段: duration")

            if 'resolution' not in video_columns:
                self.cursor.execute('ALTER TABLE videos ADD COLUMN resolution TEXT')
                print("添加字段: resolution")

            if 'file_created_time' not in video_columns:
                self.cursor.execute('ALTER TABLE videos ADD COLUMN file_created_time TIMESTAMP')
                print("添加字段: file_created_time")

            if 'source_folder' not in video_columns:
                self.cursor.execute('ALTER TABLE videos ADD COLUMN source_folder TEXT')
                print("添加字段: source_folder")

            if 'md5_hash' not in video_columns:
                self.cursor.execute('ALTER TABLE videos ADD COLUMN md5_hash TEXT')
                print("添加字段: md5_hash")

            # 检查folders表是否需要添加新字段
            self.cursor.execute("PRAGMA table_info(folders)")
            folder_columns = [column[1] for column in self.cursor.fetchall()]

            # 添加folders表缺失的字段
            if 'device_name' not in folder_columns:
                self.cursor.execute('ALTER TABLE folders ADD COLUMN device_name TEXT')
                print("添加字段: device_name")
                # 为现有记录设置当前设备名称
                current_device = self.get_current_device_name()
                self.cursor.execute('UPDATE folders SET device_name = ? WHERE device_name IS NULL', (current_device,))
                print(f"为现有文件夹设置设备名称: {current_device}")

        except Exception as e:
            print(f"数据库迁移失败: {str(e)}")

    def get_current_device_name(self):
        """获取当前设备名称"""
        import platform
        return platform.node() or "Unknown"

    def check_gpu_acceleration_status(self):
        """检查GPU加速状态"""
        try:
            import cv2
            # 检查是否支持CUDA
            if cv2.cuda.getCudaEnabledDeviceCount() > 0:
                self.gpu_acceleration = True
            else:
                self.gpu_acceleration = False
        except:
            self.gpu_acceleration = False

    def get_ffmpeg_command(self):
        """获取可用的FFmpeg命令路径"""
        # 首先尝试相对路径（用户通过homebrew安装的情况）
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
            return "ffmpeg"
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        # 如果相对路径失败，尝试常见的绝对路径
        possible_paths = [
            "/opt/homebrew/bin/ffmpeg",
            "/usr/local/bin/ffmpeg",
            "/usr/bin/ffmpeg"
        ]

        for path in possible_paths:
            try:
                subprocess.run([path, "-version"], capture_output=True, check=True)
                return path
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue

        return None

    def detect_gpu_acceleration(self):
        """检测可用的GPU加速选项"""
        ffmpeg_cmd = self.get_ffmpeg_command()
        if not ffmpeg_cmd:
            return None

        try:
            # 检查FFmpeg支持的硬件加速器
            result = subprocess.run([ffmpeg_cmd, "-hwaccels"], capture_output=True, text=True)
            if result.returncode == 0:
                hwaccels = result.stdout.lower()

                # macOS优先级：videotoolbox > opencl
                if "videotoolbox" in hwaccels:
                    return "videotoolbox"
                elif "opencl" in hwaccels:
                    return "opencl"

        except Exception as e:
            print(f"检测GPU加速失败: {e}")

        return None

    def get_optimized_ffmpeg_cmd(self, input_path, output_path, seek_time="00:00:10"):
        """获取优化的FFmpeg命令（包含GPU加速）"""
        ffmpeg_cmd = self.get_ffmpeg_command()
        if not ffmpeg_cmd:
            return None

        # 检测GPU加速
        hwaccel = self.detect_gpu_acceleration()

        cmd = [ffmpeg_cmd]

        # 添加输入参数
        cmd.extend(["-i", input_path])

        # 添加时间定位
        cmd.extend(["-ss", seek_time])

        # 添加帧数限制
        cmd.extend(["-vframes", "1"])

        # 根据GPU加速添加参数
        if hwaccel:
            if hwaccel == "videotoolbox":
                cmd.extend(["-hwaccel", "videotoolbox"])
                cmd.extend(["-pix_fmt", "yuv420p"])
            elif hwaccel == "opencl":
                cmd.extend(["-hwaccel", "opencl"])
                cmd.extend(["-pix_fmt", "yuv420p"])
        else:
            # 无GPU加速，使用CPU
            cmd.extend(["-pix_fmt", "yuv420p"])

        # 添加输出参数
        cmd.extend(["-y", output_path])

        return cmd

    def check_connection(self):
        """检查数据库连接是否有效"""
        try:
            if not self.conn or not self.cursor:
                return False
            # 执行一个简单查询来测试连接
            self.cursor.execute("SELECT 1")
            return True
        except sqlite3.Error:
            return False

    def ensure_connection(self):
        """确保数据库连接有效，如果无效则重新连接"""
        if not self.check_connection():
            print("数据库连接已关闭，重新连接...")
            try:
                self.init_database()
                print("数据库重新连接完成")
                return True
            except Exception as e:
                print(f"数据库重新连接失败: {e}")
                return False
        return True

    # 以下是从tkinter版本移植的核心功能方法

    def parse_stars_from_filename(self, filename):
        """从文件名解析星级"""
        exclamation_count = 0
        for char in filename:
            if char == '!':
                exclamation_count += 1
            else:
                break

        # 1个叹号=2星，2个叹号=3星，3个叹号=4星，4个叹号=5星
        if exclamation_count == 1:
            return 2
        elif exclamation_count == 2:
            return 3
        elif exclamation_count == 3:
            return 4
        elif exclamation_count >= 4:
            return 5
        else:
            return 0

    def parse_title_from_filename(self, filename):
        """从文件名解析标题"""
        # 去除开头的叹号
        title = filename.lstrip('!')
        # 去除扩展名
        title = os.path.splitext(title)[0]
        return title

    def is_video_online(self, video_id):
        """判断视频是否在线（基于文件路径存在性）"""
        try:
            # 获取视频的文件路径
            self.cursor.execute("SELECT file_path FROM videos WHERE id = ?", (video_id,))
            video_result = self.cursor.fetchone()
            if not video_result or not video_result[0]:
                return False

            file_path = video_result[0]

            # 直接检查文件是否存在
            return os.path.exists(file_path) and os.path.isfile(file_path)
        except Exception as e:
            print(f"检查视频在线状态时出错: {e}")
            return False

    def check_nas_status(self, file_path):
        """检查NAS状态"""
        try:
            return os.path.exists(file_path)
        except:
            return False

    def get_video_info(self, file_path):
        """获取视频信息（时长和分辨率）"""
        try:
            if not os.path.exists(file_path):
                return None, None

            # 首先尝试使用opencv-python获取视频信息
            try:
                import cv2
                cap = cv2.VideoCapture(file_path)

                if cap.isOpened():
                    # 获取帧率和总帧数来计算时长
                    fps = cap.get(cv2.CAP_PROP_FPS)
                    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

                    duration = None
                    resolution = None

                    if fps > 0 and frame_count > 0:
                        duration = int(frame_count / fps)

                    if width > 0 and height > 0:
                        resolution = f"{width}x{height}"

                    cap.release()
                    return duration, resolution
                else:
                    cap.release()

            except ImportError:
                print("opencv-python未安装，尝试使用ffprobe...")
            except Exception as e:
                print(f"使用opencv获取视频信息失败: {str(e)}")

            # 如果opencv不可用，尝试使用ffprobe
            ffprobe_cmd = self.get_ffprobe_command()
            if ffprobe_cmd is None:
                print(f"ffprobe未找到，无法获取视频信息: {file_path}")
                return None, None

            # 获取时长
            duration_cmd = [
                ffprobe_cmd, "-v", "quiet", "-show_entries", "format=duration",
                "-of", "csv=p=0", file_path
            ]
            duration_result = subprocess.run(duration_cmd, capture_output=True, text=True)
            duration = None
            if duration_result.returncode == 0 and duration_result.stdout.strip():
                try:
                    duration = int(float(duration_result.stdout.strip()))
                except ValueError:
                    pass

            # 获取分辨率
            resolution_cmd = [
                ffprobe_cmd, "-v", "quiet", "-select_streams", "v:0",
                "-show_entries", "stream=width,height", "-of", "csv=p=0", file_path
            ]
            resolution_result = subprocess.run(resolution_cmd, capture_output=True, text=True)
            resolution = None
            if resolution_result.returncode == 0 and resolution_result.stdout.strip():
                try:
                    width, height = resolution_result.stdout.strip().split(',')
                    resolution = f"{width}x{height}"
                except ValueError:
                    pass

            return duration, resolution

        except Exception as e:
            print(f"获取视频信息失败 {file_path}: {str(e)}")
            return None, None

    def get_ffprobe_command(self):
        """获取可用的FFprobe命令路径"""
        # 首先尝试相对路径（用户通过homebrew安装的情况）
        try:
            subprocess.run(["ffprobe", "-version"], capture_output=True, check=True)
            return "ffprobe"
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        # 如果相对路径失败，尝试常见的绝对路径
        possible_paths = [
            "/opt/homebrew/bin/ffprobe",
            "/usr/local/bin/ffprobe",
            "/usr/bin/ffprobe"
        ]

        for path in possible_paths:
            try:
                subprocess.run([path, "-version"], capture_output=True, check=True)
                return path
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue

        return None

    def get_optimized_ffmpeg_cmd(self, input_path, output_path, seek_time="00:00:10"):
        """获取优化的FFmpeg命令（包含GPU加速）"""
        ffmpeg_cmd = self.get_ffmpeg_command()
        if not ffmpeg_cmd:
            return None

        # 检测GPU加速
        hwaccel = self.detect_gpu_acceleration()

        cmd = [ffmpeg_cmd]

        # 添加输入参数
        cmd.extend(["-i", input_path])

        # 添加时间定位
        cmd.extend(["-ss", seek_time])

        # 添加帧数限制
        cmd.extend(["-vframes", "1"])

        # 添加GPU加速参数
        if hwaccel:
            cmd.extend(["-hwaccel", hwaccel])
            if hwaccel == "videotoolbox":
                cmd.extend(["-pix_fmt", "yuv420p"])

        # 添加输出路径
        cmd.extend(["-y", output_path])

        return cmd

    def calculate_md5_hash(self, file_path):
        """计算完整文件的MD5哈希值"""
        try:
            if not os.path.exists(file_path):
                return None

            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                # 读取完整文件计算MD5哈希
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except:
            return None

    def add_video_to_db(self, file_path, folder_type):
        """添加视频到数据库"""
        try:
            # 检查文件是否已存在
            self.cursor.execute("SELECT id FROM videos WHERE file_path = ?", (file_path,))
            existing = self.cursor.fetchone()
            if existing:
                return

            # 检查是否有同名文件但路径不同（可能是移动的文件）
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

            # 查找同名且大小相同但路径不同的文件
            self.cursor.execute(
                "SELECT id, file_path FROM videos WHERE file_name = ? AND file_size = ? AND file_path != ?",
                (file_name, file_size, file_path)
            )
            potential_moved = self.cursor.fetchone()

            if potential_moved:
                old_id, old_path = potential_moved
                # 检查旧路径是否还存在
                if not os.path.exists(old_path):
                    # 旧文件不存在，新文件存在，很可能是移动了
                    # 更新路径而不是创建新记录
                    new_source_folder = os.path.dirname(file_path)
                    self.cursor.execute(
                        "UPDATE videos SET file_path = ?, source_folder = ? WHERE id = ?",
                        (file_path, new_source_folder, old_id)
                    )
                    print(f"自动更新移动的文件: {old_path} -> {file_path}")
                    return

            # 获取文件信息
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

            # 获取文件创建时间
            file_created_time = None
            if os.path.exists(file_path):
                try:
                    stat = os.stat(file_path)
                    file_created_time = datetime.fromtimestamp(stat.st_birthtime if hasattr(stat, 'st_birthtime') else stat.st_ctime)
                except:
                    pass

            # 获取来源文件夹
            source_folder = os.path.dirname(file_path)

            # 计算文件MD5哈希（用于去重）
            md5_hash = self.calculate_md5_hash(file_path)

            # 从文件名解析星级
            stars = self.parse_stars_from_filename(file_name)

            # 解析标题（去除星号和扩展名）
            title = self.parse_title_from_filename(file_name)

            # 获取视频信息
            duration, resolution = self.get_video_info(file_path)

            # NAS路径处理
            nas_path = file_path if folder_type == "nas" else None
            # 统一使用文件路径存在性判断在线状态
            is_nas_online = os.path.exists(file_path) and os.path.isfile(file_path)

            self.cursor.execute(
                """INSERT INTO videos
                   (file_path, file_name, file_size, md5_hash, title, stars, nas_path, is_nas_online, duration, resolution, file_created_time, source_folder)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (file_path, file_name, file_size, md5_hash, title, stars, nas_path, is_nas_online, duration, resolution, file_created_time, source_folder)
            )
            self.conn.commit()

        except Exception as e:
            print(f"添加视频失败 {file_path}: {str(e)}")

    def get_all_videos(self, where_clause=None, params=None, order_clause="ORDER BY title"):
        """获取视频数据的基础查询方法"""
        try:
            # 构建基础查询，连接javdb_info表获取JAVDB信息
            base_query = """
                SELECT v.*,
                       j.javdb_code, j.javdb_title, j.score, j.release_date,
                       GROUP_CONCAT(DISTINCT a.name, ', ') as actors_display,
                       GROUP_CONCAT(DISTINCT jt.tag_name, ', ') as javdb_tags_display
                FROM videos v
                LEFT JOIN javdb_info j ON v.id = j.video_id
                LEFT JOIN video_actors va ON v.id = va.video_id
                LEFT JOIN actors a ON va.actor_id = a.id
                LEFT JOIN javdb_info_tags jit ON j.id = jit.javdb_info_id
                LEFT JOIN javdb_tags jt ON jit.tag_id = jt.id
            """

            if where_clause:
                full_query = f"{base_query} {where_clause} GROUP BY v.id {order_clause}"
            else:
                full_query = f"{base_query} GROUP BY v.id {order_clause}"

            if params:
                self.cursor.execute(full_query, params)
            else:
                self.cursor.execute(full_query)

            return self.cursor.fetchall()

        except Exception as e:
            print(f"查询视频数据失败: {str(e)}")
            return []

    def update_video(self, video_id, **kwargs):
        """更新视频信息"""
        try:
            if not kwargs:
                return False

            # 构建SET子句
            set_clauses = []
            params = []

            for key, value in kwargs.items():
                set_clauses.append(f"{key} = ?")
                params.append(value)

            params.append(video_id)

            query = f"UPDATE videos SET {', '.join(set_clauses)} WHERE id = ?"
            self.cursor.execute(query, params)
            self.conn.commit()
            return True

        except Exception as e:
            print(f"更新视频信息失败: {str(e)}")
            return False

    def delete_video(self, video_id):
        """从数据库删除视频记录"""
        try:
            # 删除相关的演员关联记录
            self.cursor.execute("DELETE FROM video_actors WHERE video_id = ?", (video_id,))

            # 删除相关的JAVDB标签关联记录
            self.cursor.execute("""
                DELETE FROM javdb_info_tags
                WHERE javdb_info_id IN (
                    SELECT id FROM javdb_info WHERE video_id = ?
                )
            """, (video_id,))

            # 删除JAVDB信息记录
            self.cursor.execute("DELETE FROM javdb_info WHERE video_id = ?", (video_id,))

            # 删除视频记录
            self.cursor.execute("DELETE FROM videos WHERE id = ?", (video_id,))

            self.conn.commit()
            return True

        except Exception as e:
            print(f"删除视频记录失败: {str(e)}")
            return False

    def search_videos(self, title="", tags="", actors="", stars=0, folder_path=""):
        """搜索视频的简化接口"""
        conditions = []
        params = []

        if title:
            conditions.append("(v.title LIKE ? OR v.file_name LIKE ? OR j.javdb_title LIKE ?)")
            title_param = f"%{title}%"
            params.extend([title_param, title_param, title_param])

        if tags:
            conditions.append("(v.tags LIKE ? OR EXISTS (SELECT 1 FROM javdb_info_tags jit JOIN javdb_tags jt ON jit.tag_id = jt.id JOIN javdb_info ji2 ON jit.javdb_info_id = ji2.id WHERE ji2.video_id = v.id AND jt.tag_name LIKE ?))")
            tag_param = f"%{tags}%"
            params.extend([tag_param, tag_param])

        if actors:
            conditions.append("EXISTS (SELECT 1 FROM video_actors va JOIN actors a ON va.actor_id = a.id WHERE va.video_id = v.id AND a.name LIKE ?)")
            actor_param = f"%{actors}%"
            params.append(actor_param)

        if stars > 0:
            conditions.append("v.stars = ?")
            params.append(stars)

        if folder_path:
            conditions.append("v.source_folder LIKE ?")
            params.append(f"{folder_path}%")

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        return self.get_all_videos(where_clause, params)

    def scan_media_files(self, progress_callback=None, cancel_check=None):
        """扫描媒体文件的核心逻辑（支持进度回调和取消机制）"""
        try:
            # 获取所有活跃的文件夹
            self.cursor.execute("SELECT folder_path, folder_type FROM folders WHERE is_active = 1")
            folders = self.cursor.fetchall()

            if not folders:
                return {'error': '没有找到活跃的文件夹'}

            # 统计变量
            scanned_count = 0
            added_count = 0
            updated_count = 0
            skipped_count = 0

            # 视频文件扩展名
            video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'}

            # 第一阶段：收集所有文件
            if progress_callback:
                progress_callback("第一阶段：统计文件数量...")

            files_to_process = []
            for folder_path, folder_type in folders:
                if cancel_check and cancel_check():
                    return {'cancelled': True}

                if not os.path.exists(folder_path):
                    if progress_callback:
                        progress_callback(f"文件夹不存在，跳过: {folder_path}")
                    continue

                if progress_callback:
                    progress_callback(f"扫描文件夹: {folder_path}")

                for root, dirs, files in os.walk(folder_path):
                    for file in files:
                        if any(file.lower().endswith(ext) for ext in video_extensions):
                            file_path = os.path.join(root, file)
                            files_to_process.append((file_path, folder_type))

            if progress_callback:
                progress_callback(f"发现 {len(files_to_process)} 个视频文件")

            if not files_to_process:
                return {'error': '没有找到视频文件'}

            # 第二阶段：处理文件
            if progress_callback:
                progress_callback("第二阶段：处理文件...")

            total_files = len(files_to_process)
            batch_size = 50

            for i, (file_path, folder_type) in enumerate(files_to_process):
                # 检查取消
                if cancel_check and cancel_check():
                    return {'cancelled': True}

                try:
                    # 检查文件是否已存在
                    self.cursor.execute("SELECT id FROM videos WHERE file_path = ?", (file_path,))
                    existing = self.cursor.fetchone()

                    if existing:
                        # 文件已存在，跳过
                        skipped_count += 1
                    else:
                        # 添加新文件
                        self.add_video_to_db(file_path, folder_type)
                        added_count += 1

                    scanned_count += 1

                    # 进度更新
                    progress = int((scanned_count / total_files) * 100)
                    if progress_callback:
                        progress_callback(f"处理文件 {scanned_count}/{total_files}", progress, scanned_count, added_count, updated_count, skipped_count)

                    # 批量提交
                    if scanned_count % batch_size == 0:
                        self.conn.commit()
                        if progress_callback:
                            progress_callback(f"已处理 {scanned_count} 个文件，批量提交数据库", progress, scanned_count, added_count, updated_count, skipped_count)

                except Exception as e:
                    if progress_callback:
                        progress_callback(f"处理文件失败: {os.path.basename(file_path)} - {str(e)}", None, scanned_count, added_count, updated_count, skipped_count + 1)
                    skipped_count += 1

            # 最终提交
            self.conn.commit()

            if progress_callback:
                progress_callback("扫描完成", 100, scanned_count, added_count, updated_count, skipped_count)

            return {
                'success': True,
                'scanned': scanned_count,
                'added': added_count,
                'updated': updated_count,
                'skipped': skipped_count
            }

        except Exception as e:
            return {'error': f'扫描过程中出错: {str(e)}'}

    def import_nfo_file(self, nfo_file_path, video_id=None, video_path=None):
        """导入NFO文件"""
        try:
            if not os.path.exists(nfo_file_path):
                return False, "NFO文件不存在"

            import xml.etree.ElementTree as ET

            # 解析NFO文件
            tree = ET.parse(nfo_file_path)
            root = tree.getroot()

            # 提取基本信息
            title = root.findtext('title', '').strip()
            genre = root.findtext('genre', '').strip()
            year = None
            year_text = root.findtext('year')
            if year_text and year_text.isdigit():
                year = int(year_text)

            # 提取演员信息
            actors = []
            for actor_elem in root.findall('actor'):
                name = actor_elem.findtext('name', '').strip()
                if name:
                    actors.append(name)

            # 提取标签信息
            tags = []
            for tag_elem in root.findall('tag'):
                tag_text = tag_elem.text.strip() if tag_elem.text else ''
                if tag_text:
                    tags.append(tag_text)

            # 如果提供了video_id，直接更新数据库
            if video_id:
                # 更新视频基本信息
                update_data = {}
                if title:
                    update_data['title'] = title
                if genre:
                    update_data['genre'] = genre
                if year:
                    update_data['year'] = year

                if update_data:
                    self.update_video(video_id, **update_data)

                # 处理演员信息
                if actors:
                    # 先删除原有的演员关联
                    self.cursor.execute("DELETE FROM video_actors WHERE video_id = ?", (video_id,))

                    # 添加新的演员关联
                    for actor_name in actors:
                        # 检查演员是否已存在
                        self.cursor.execute("SELECT id FROM actors WHERE name = ?", (actor_name,))
                        actor_result = self.cursor.fetchone()

                        if actor_result:
                            actor_id = actor_result[0]
                        else:
                            # 创建新演员记录
                            self.cursor.execute("INSERT INTO actors (name) VALUES (?)", (actor_name,))
                            actor_id = self.cursor.lastrowid

                        # 建立视频和演员的关联
                        self.cursor.execute(
                            "INSERT INTO video_actors (video_id, actor_id) VALUES (?, ?)",
                            (video_id, actor_id)
                        )

                # 处理标签信息
                if tags:
                    tags_str = ', '.join(tags)
                    self.update_video(video_id, tags=tags_str)

                self.conn.commit()
                return True, f"成功导入NFO文件: {nfo_file_path}"

            elif video_path:
                # 如果提供了video_path，通过路径查找视频ID
                self.cursor.execute("SELECT id FROM videos WHERE file_path = ?", (video_path,))
                video_result = self.cursor.fetchone()

                if video_result:
                    video_id = video_result[0]
                    return self.import_nfo_file(nfo_file_path, video_id=video_id)
                else:
                    return False, "未找到对应的视频记录"

            else:
                return False, "必须提供video_id或video_path参数"

        except Exception as e:
            return False, f"导入NFO文件失败: {str(e)}"

    def generate_thumbnail_for_video(self, video_path, output_path=None, seek_time="00:00:10"):
        """为指定视频生成缩略图"""
        try:
            if not os.path.exists(video_path):
                return False, "视频文件不存在"

            # 如果没有指定输出路径，使用临时文件
            if not output_path:
                import tempfile
                with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
                    output_path = tmp_file.name

            # 获取FFmpeg命令
            ffmpeg_cmd = self.get_optimized_ffmpeg_cmd(video_path, output_path, seek_time)
            if not ffmpeg_cmd:
                return False, "未找到FFmpeg"

            # 执行命令生成缩略图
            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
            if result.returncode == 0 and os.path.exists(output_path):
                return True, output_path
            else:
                error_msg = result.stderr if result.stderr else "未知错误"
                return False, f"生成缩略图失败: {error_msg}"

        except Exception as e:
            return False, f"生成缩略图异常: {str(e)}"

class ScanProgressDialog(QDialog):
    """扫描进度对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("媒体文件扫描")
        self.setFixedSize(500, 400)
        self.setModal(True)

        self.setup_ui()
        self.cancelled = False

    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout()

        # 标题
        title_label = QLabel("正在扫描媒体文件...")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; margin: 10px;")
        layout.addWidget(title_label)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # 状态标签
        self.status_label = QLabel("准备扫描...")
        layout.addWidget(self.status_label)

        # 统计信息
        self.stats_label = QLabel("已扫描: 0 | 新增: 0 | 更新: 0 | 跳过: 0")
        self.stats_label.setStyleSheet("font-family: monospace; background-color: #f5f5f5; padding: 5px; border: 1px solid #ddd;")
        layout.addWidget(self.stats_label)

        # 日志区域
        log_group = QGroupBox("扫描日志")
        log_layout = QVBoxLayout()

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        log_layout.addWidget(self.log_text)

        log_group.setLayout(log_layout)
        layout.addWidget(log_group)

        # 按钮
        button_layout = QHBoxLayout()

        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.cancel)
        button_layout.addWidget(self.cancel_button)

        button_layout.addStretch()

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def update_progress(self, value, status=""):
        """更新进度"""
        self.progress_bar.setValue(value)
        if status:
            self.status_label.setText(status)

    def update_stats(self, scanned, added, updated, skipped):
        """更新统计信息"""
        self.stats_label.setText(f"已扫描: {scanned} | 新增: {added} | 更新: {updated} | 跳过: {skipped}")

    def append_log(self, message):
        """添加日志"""
        from datetime import datetime
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_text.append(f"[{timestamp}] {message}")
        # 滚动到底部
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def cancel(self):
        """取消操作"""
        self.cancelled = True
        self.cancel_button.setText("正在取消...")
        self.cancel_button.setEnabled(False)

class VideoListWidget(QTreeWidget):
    """视频列表组件，对应原版的Treeview"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.setSelectionMode(QTreeWidget.ExtendedSelection)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(False)  # 禁用默认排序，使用自定义排序

        # 连接信号
        self.itemSelectionChanged.connect(self.trigger_selection_changed)
        self.itemDoubleClicked.connect(self.trigger_double_clicked)
        self.header().sectionClicked.connect(self.trigger_header_clicked)

        # 设置右键菜单
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.trigger_context_menu)

    def mouseDoubleClickEvent(self, event):
        """重写双击事件，支持星级列的快速编辑"""
        item = self.itemAt(event.pos())
        if not item:
            return

        # 获取点击的列
        column = self.columnAt(event.pos())

        # 获取列名
        sorted_columns = sorted(self.parent_window.core.column_config.items(), key=lambda x: x[1]['position'])
        column_names = [col[0] for col in sorted_columns]

        if column < len(column_names) and column_names[column] == 'stars':
            # 点击的是星级列，显示快速设置对话框
            video_id = item.data(0, Qt.UserRole)
            self.parent_window.show_quick_star_dialog(video_id)
        else:
            super().mouseDoubleClickEvent(event)

    def trigger_context_menu(self, position):
        if hasattr(self.parent_window, 'show_context_menu') and callable(self.parent_window.show_context_menu):
            self.parent_window.show_context_menu(position)
        else:
            item = self.itemAt(position)
            if not item:
                return
            menu = QMenu(self)
            if hasattr(self.parent_window, 'play_video') and callable(self.parent_window.play_video):
                play_action = menu.addAction("播放视频")
                play_action.triggered.connect(self.parent_window.play_video)
            copy_action = menu.addAction("复制文件路径")
            def _copy_path():
                path = item.text(0)
                from PySide6.QtGui import QGuiApplication
                QGuiApplication.clipboard().setText(path)
            copy_action.triggered.connect(_copy_path)
            menu.exec(self.viewport().mapToGlobal(position))

    def trigger_selection_changed(self):
        if hasattr(self.parent_window, 'on_video_selection_changed') and callable(self.parent_window.on_video_selection_changed):
            self.parent_window.on_video_selection_changed()
        else:
            selected_items = self.selectedItems()
            if selected_items and hasattr(self.parent_window, 'load_video_detail') and callable(self.parent_window.load_video_detail):
                video_id = selected_items[0].data(0, Qt.UserRole)
                self.parent_window.load_video_detail(video_id)

    def trigger_double_clicked(self, item, column):
        if hasattr(self.parent_window, 'on_video_double_clicked') and callable(self.parent_window.on_video_double_clicked):
            self.parent_window.on_video_double_clicked(item, column)
        else:
            if hasattr(self.parent_window, 'play_video') and callable(self.parent_window.play_video):
                self.parent_window.play_video()

    def trigger_header_clicked(self, column):
        if hasattr(self.parent_window, 'on_video_header_clicked') and callable(self.parent_window.on_video_header_clicked):
            self.parent_window.on_video_header_clicked(column)
        else:
            sorted_columns = sorted(self.parent_window.core.column_config.items(), key=lambda x: x[1]['position'])
            column_names = [col[0] for col in sorted_columns]
            if column < len(column_names):
                column_name = column_names[column]
                if hasattr(self.parent_window.core, 'sort_column_name') and self.parent_window.core.sort_column_name == column_name:
                    self.parent_window.core.sort_reverse = not getattr(self.parent_window.core, 'sort_reverse', False)
                else:
                    self.parent_window.core.sort_column_name = column_name
                    self.parent_window.core.sort_reverse = False
                if hasattr(self.parent_window, 'load_videos') and callable(self.parent_window.load_videos):
                    self.parent_window.load_videos()

class VideoDetailWidget(QWidget):
    """视频详情组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.setup_ui()

    def setup_ui(self):
        """设置详情界面UI"""
        layout = QGridLayout()

        # 左侧：封面显示
        self.thumbnail_label = QLabel("无封面")
        self.thumbnail_label.setFixedSize(200, 150)
        self.thumbnail_label.setStyleSheet("""
            QLabel {
                border: 2px solid #ddd;
                border-radius: 5px;
                background-color: #f9f9f9;
            }
        """)
        self.thumbnail_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.thumbnail_label, 0, 0, 6, 1, Qt.AlignTop)

        # 右侧：详细信息
        current_col = 1

        # 标题
        layout.addWidget(QLabel("标题:"), 0, current_col)
        self.title_edit = QLineEdit()
        layout.addWidget(self.title_edit, 0, current_col + 1, 1, 2)

        # 星级
        layout.addWidget(QLabel("星级:"), 1, current_col)
        self.star_layout = QHBoxLayout()
        self.star_layout.setSpacing(2)  # 设置星星间距为2像素，解决距离太远的问题
        self.star_labels = []
        for i in range(5):
            star_label = QLabel("☆")
            star_label.setStyleSheet("font-size: 16px;")
            star_label.mousePressEvent = lambda e, star=i+1: self.parent_window.set_star_rating(star)
            self.star_labels.append(star_label)
            self.star_layout.addWidget(star_label)
        layout.addLayout(self.star_layout, 1, current_col + 1)

        # 描述
        layout.addWidget(QLabel("描述:"), 2, current_col)
        self.desc_edit = QTextEdit()
        self.desc_edit.setMaximumHeight(80)
        layout.addWidget(self.desc_edit, 2, current_col + 1, 1, 2)

        # 标签
        layout.addWidget(QLabel("标签:"), 3, current_col)
        self.tags_edit = QLineEdit()
        layout.addWidget(self.tags_edit, 3, current_col + 1, 1, 2)

        # 更多元数据字段
        current_row = 4

        # 演员
        layout.addWidget(QLabel("演员:"), current_row, current_col)
        self.actors_label = QLabel("无演员信息")
        self.actors_label.setWordWrap(True)
        self.actors_label.setStyleSheet("QLabel { background-color: #f5f5f5; padding: 5px; border: 1px solid #ddd; }")
        # 使演员标签可点击
        self.actors_label.mousePressEvent = self.on_actors_clicked
        self.actors_label.setCursor(Qt.PointingHandCursor)
        layout.addWidget(self.actors_label, current_row, current_col + 1, 1, 2)
        current_row += 1

        # 文件信息
        layout.addWidget(QLabel("文件名:"), current_row, current_col)
        self.filename_label = QLabel("")
        self.filename_label.setWordWrap(True)
        layout.addWidget(self.filename_label, current_row, current_col + 1, 1, 2)
        current_row += 1

        layout.addWidget(QLabel("文件路径:"), current_row, current_col)
        self.filepath_label = QLabel("")
        self.filepath_label.setWordWrap(True)
        self.filepath_label.setStyleSheet("QLabel { font-family: 'Menlo', 'Monaco', 'Courier New'; font-size: 9px; background-color: #f5f5f5; padding: 5px; border: 1px solid #ddd; }")
        layout.addWidget(self.filepath_label, current_row, current_col + 1, 1, 2)
        current_row += 1

        layout.addWidget(QLabel("文件大小:"), current_row, current_col)
        self.filesize_label = QLabel("")
        layout.addWidget(self.filesize_label, current_row, current_col + 1, 1, 2)
        current_row += 1

        layout.addWidget(QLabel("时长:"), current_row, current_col)
        self.duration_label = QLabel("")
        layout.addWidget(self.duration_label, current_row, current_col + 1, 1, 2)
        current_row += 1

        layout.addWidget(QLabel("分辨率:"), current_row, current_col)
        self.resolution_label = QLabel("")
        layout.addWidget(self.resolution_label, current_row, current_col + 1, 1, 2)
        current_row += 1

        # JAVDB信息
        layout.addWidget(QLabel("番号:"), current_row, current_col)
        self.javdb_code_label = QLabel("")
        layout.addWidget(self.javdb_code_label, current_row, current_col + 1, 1, 2)
        current_row += 1

        layout.addWidget(QLabel("JAVDB标题:"), current_row, current_col)
        self.javdb_title_label = QLabel("")
        self.javdb_title_label.setWordWrap(True)
        layout.addWidget(self.javdb_title_label, current_row, current_col + 1, 1, 2)
        current_row += 1

        layout.addWidget(QLabel("JAVDB评分:"), current_row, current_col)
        self.javdb_rating_label = QLabel("")
        layout.addWidget(self.javdb_rating_label, current_row, current_col + 1, 1, 2)
        current_row += 1

        layout.addWidget(QLabel("发行日期:"), current_row, current_col)
        self.release_date_label = QLabel("")
        layout.addWidget(self.release_date_label, current_row, current_col + 1, 1, 2)
        current_row += 1

        # 时间信息
        layout.addWidget(QLabel("创建时间:"), current_row, current_col)
        self.created_time_label = QLabel("")
        layout.addWidget(self.created_time_label, current_row, current_col + 1, 1, 2)
        current_row += 1

        layout.addWidget(QLabel("修改时间:"), current_row, current_col)
        self.updated_time_label = QLabel("")
        layout.addWidget(self.updated_time_label, current_row, current_col + 1, 1, 2)
        current_row += 1

        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line, current_row, current_col, 1, 3)
        current_row += 1

        # 操作按钮
        buttons_layout = QVBoxLayout()

        # 主要操作按钮
        self.play_button = QPushButton("播放视频")
        self.play_button.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; }")
        buttons_layout.addWidget(self.play_button)

        self.save_button = QPushButton("保存修改")
        self.save_button.setStyleSheet("QPushButton { background-color: #2196F3; color: white; font-weight: bold; }")
        buttons_layout.addWidget(self.save_button)

        # 星级和标签操作
        self.set_star_button = QPushButton("设置星级")
        buttons_layout.addWidget(self.set_star_button)

        self.add_tag_button = QPushButton("添加标签")
        buttons_layout.addWidget(self.add_tag_button)

        # 信息获取操作
        self.fetch_info_button = QPushButton("获取JAVDB信息")
        self.fetch_info_button.setStyleSheet("QPushButton { background-color: #FF9800; color: white; }")
        buttons_layout.addWidget(self.fetch_info_button)

        self.generate_thumbnail_button = QPushButton("生成封面")
        buttons_layout.addWidget(self.generate_thumbnail_button)

        # 危险操作
        self.delete_button = QPushButton("删除视频")
        self.delete_button.setStyleSheet("QPushButton { background-color: #F44336; color: white; }")
        buttons_layout.addWidget(self.delete_button)

        buttons_layout.addStretch()
        layout.addLayout(buttons_layout, 0, current_col + 3, current_row, 1)

        self.setLayout(layout)

    def display_thumbnail(self, thumbnail_data):
        """显示封面，与原版Tkinter功能一致"""
        try:
            if thumbnail_data:
                # 处理不同类型的thumbnail_data
                if isinstance(thumbnail_data, str):
                    # 如果是base64字符串，先解码
                    try:
                        thumbnail_data = base64.b64decode(thumbnail_data)
                    except Exception:
                        # 如果解码失败，可能是文件路径
                        if os.path.exists(thumbnail_data):
                            with open(thumbnail_data, 'rb') as f:
                                thumbnail_data = f.read()
                        else:
                            # 如果都不是，直接跳过显示缩略图
                            self.thumbnail_label.setText("无封面")
                            self.thumbnail_label.setPixmap(QPixmap())
                            return
                elif isinstance(thumbnail_data, memoryview):
                    # 如果是memoryview对象，转换为bytes
                    thumbnail_data = thumbnail_data.tobytes()
                elif not isinstance(thumbnail_data, bytes):
                    # 如果不是bytes类型，尝试转换
                    try:
                        thumbnail_data = bytes(thumbnail_data)
                    except Exception:
                        self.thumbnail_label.setText("无封面")
                        self.thumbnail_label.setPixmap(QPixmap())
                        return

                # 确保thumbnail_data是bytes类型
                if not isinstance(thumbnail_data, bytes):
                    self.thumbnail_label.setText("无封面")
                    self.thumbnail_label.setPixmap(QPixmap())
                    return

                # 从二进制数据创建图片
                image = Image.open(io.BytesIO(thumbnail_data))

                # 按比例缩放，保持原始宽高比
                # 设置最大显示尺寸
                max_width = 200
                max_height = 150

                # 计算缩放比例
                width_ratio = max_width / image.width
                height_ratio = max_height / image.height
                scale_ratio = min(width_ratio, height_ratio)

                # 计算新尺寸
                new_width = int(image.width * scale_ratio)
                new_height = int(image.height * scale_ratio)

                # 调整大小 - 兼容不同版本的PIL
                try:
                    # 新版本PIL
                    image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                except AttributeError:
                    # 旧版本PIL
                    image = image.resize((new_width, new_height), Image.LANCZOS)

                # 转换为PySide可用的格式
                # 将PIL Image转换为QPixmap
                width, height = image.size
                bytes_per_line = width * 4

                # 转换为RGBA格式
                image_rgba = image.convert("RGBA")

                # 创建QPixmap
                pixmap = QPixmap.fromImage(
                    QImage(image_rgba.tobytes(), width, height, QImage.Format_RGBA8888)
                )

                # 显示图片
                self.thumbnail_label.setPixmap(pixmap)
                self.thumbnail_label.setText("")
            else:
                self.thumbnail_label.setText("无封面")
                self.thumbnail_label.setPixmap(QPixmap())
        except Exception as e:
            # 静默处理错误，不打印到控制台
            self.thumbnail_label.setText("无封面")
            self.thumbnail_label.setPixmap(QPixmap())

    def on_actors_clicked(self, event):
        """演员点击事件处理"""
        if self.actors_label.text() and self.actors_label.text() != "无演员信息":
            actors_text = self.actors_label.text()
            # 如果有多个演员，让用户选择
            if ', ' in actors_text:
                # 简单分割，实际实现可能需要更复杂的处理
                actors = [actor.strip() for actor in actors_text.split(',')]
                # 这里可以实现一个选择对话框
                selected_actor = actors[0]  # 暂时选择第一个
                self.parent_window.show_actor_detail(selected_actor)
            else:
                self.parent_window.show_actor_detail(actors_text)

class SearchWidget(QWidget):
    """搜索和筛选组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.setup_ui()

    def setup_ui(self):
        """设置搜索界面UI"""
        layout = QVBoxLayout()

        # 搜索框组
        search_group = QGroupBox("搜索")
        search_layout = QVBoxLayout()

        # 标题搜索
        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel("标题:"))
        self.title_search = QLineEdit()
        self.title_search.textChanged.connect(self.trigger_search)
        title_layout.addWidget(self.title_search)
        search_layout.addLayout(title_layout)

        # 标签搜索
        tag_layout = QHBoxLayout()
        tag_layout.addWidget(QLabel("标签:"))
        self.tag_search = QLineEdit()
        self.tag_search.textChanged.connect(self.trigger_search)
        tag_layout.addWidget(self.tag_search)
        search_layout.addLayout(tag_layout)

        # 演员搜索
        actor_layout = QHBoxLayout()
        actor_layout.addWidget(QLabel("演员:"))
        self.actor_search = QLineEdit()
        self.actor_search.textChanged.connect(self.trigger_search)
        actor_layout.addWidget(self.actor_search)
        search_layout.addLayout(actor_layout)

        search_group.setLayout(search_layout)
        layout.addWidget(search_group)

        # 星级筛选
        stars_group = QGroupBox("星级筛选")
        stars_layout = QVBoxLayout()
        self.star_button_group = QButtonGroup()
        for i in range(6):
            star_text = "全部" if i == 0 else f"{i}星"
            radio = QRadioButton(star_text)
            self.star_button_group.addButton(radio, i)
            stars_layout.addWidget(radio)
        stars_layout.addStretch()
        stars_group.setLayout(stars_layout)
        layout.addWidget(stars_group)

        # 标签筛选 - 已隐藏，因为搜索框中已有标签搜索功能
        # tags_group = QGroupBox("标签筛选")
        # self.tags_layout = QVBoxLayout()
        # tags_group.setLayout(self.tags_layout)
        # layout.addWidget(tags_group)

        # 在线状态筛选
        online_group = QGroupBox("在线状态")
        online_layout = QVBoxLayout()

        self.online_only_check = QCheckBox("仅显示在线")
        self.online_only_check.stateChanged.connect(self.trigger_online_only_changed)
        online_layout.addWidget(self.online_only_check)

        online_group.setLayout(online_layout)
        layout.addWidget(online_group)

        # 文件夹来源筛选
        folder_group = QGroupBox("文件夹来源")

        # 创建滚动区域
        folder_scroll = QScrollArea()
        folder_scroll.setWidgetResizable(True)
        folder_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        folder_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        folder_scroll.setMaximumHeight(200)  # 限制最大高度

        # 创建滚动内容的容器
        folder_content = QWidget()
        self.folder_layout = QVBoxLayout()
        folder_content.setLayout(self.folder_layout)

        self.folder_button_group = QButtonGroup()

        # 添加"全部"选项
        all_radio = QRadioButton("全部文件夹")
        self.folder_button_group.addButton(all_radio, 0)
        all_radio.setChecked(True)
        self.folder_layout.addWidget(all_radio)

        # 动态添加文件夹选项
        self.folder_checkboxes = []
        # 延迟加载文件夹筛选，等待主窗口完全初始化
        QTimer.singleShot(100, self.load_folder_filters)

        # 添加伸缩空间，确保布局紧凑
        self.folder_layout.addStretch()

        # 设置滚动区域
        folder_scroll.setWidget(folder_content)

        # 创建文件夹组的布局
        folder_group_layout = QVBoxLayout()
        folder_group_layout.addWidget(folder_scroll)
        folder_group.setLayout(folder_group_layout)

        layout.addWidget(folder_group)

        # 日志输出
        log_group = QGroupBox("日志输出")
        log_layout = QVBoxLayout()

        self.log_console_check = QCheckBox("控制台输出")
        self.log_console_check.setChecked(True)
        log_layout.addWidget(self.log_console_check)

        self.log_gui_check = QCheckBox("界面输出")
        self.log_gui_check.setChecked(True)
        log_layout.addWidget(self.log_gui_check)

        log_group.setLayout(log_layout)
        layout.addWidget(log_group)

        layout.addStretch()
        self.setLayout(layout)

    def load_folder_filters(self):
        """加载文件夹筛选选项"""
        try:
            # 清除现有文件夹选项（保留"全部"选项）
            for checkbox in self.folder_checkboxes:
                checkbox.setParent(None)
            self.folder_checkboxes.clear()

            # 获取所有激活的文件夹
            self.parent_window.core.cursor.execute("""
                SELECT folder_path, device_name
                FROM folders
                WHERE is_active = 1
                ORDER BY device_name, folder_path
            """)
            folders = self.parent_window.core.cursor.fetchall()

            if not folders:
                # 如果没有文件夹，显示提示信息
                no_folders_label = QLabel("暂无激活的文件夹")
                no_folders_label.setStyleSheet("color: #666; font-style: italic; padding: 5px;")
                self.folder_layout.addWidget(no_folders_label)
                return

            # 为每个文件夹创建选项
            for folder_path, device_name in folders:
                # 生成显示名称
                if device_name:
                    display_name = f"{device_name}@{os.path.basename(folder_path)}"
                else:
                    display_name = os.path.basename(folder_path) or folder_path

                # 创建单选按钮
                radio = QRadioButton(display_name)
                radio.setProperty("folder_path", folder_path)

                radio.toggled.connect(self.trigger_search)

                # 添加到按钮组和布局
                self.folder_button_group.addButton(radio, len(self.folder_checkboxes) + 1)
                self.folder_layout.addWidget(radio)
                self.folder_checkboxes.append(radio)

            # 在状态栏显示加载结果
            self.parent_window.statusBar().showMessage(f"已加载 {len(folders)} 个文件夹选项", 3000)

        except Exception as e:
            error_msg = f"加载文件夹筛选失败: {e}"
            print(error_msg)
            # 安全地访问状态栏
            if hasattr(self.parent_window, 'statusBar') and callable(self.parent_window.statusBar):
                self.parent_window.statusBar().showMessage("文件夹筛选加载失败", 5000)
            # 显示错误标签
            error_label = QLabel("加载失败")
            error_label.setStyleSheet("color: red; font-weight: bold; padding: 5px;")
            self.folder_layout.addWidget(error_label)

    def trigger_search(self):
        if hasattr(self.parent_window, 'on_search') and callable(self.parent_window.on_search):
            self.parent_window.on_search()
        else:
            setattr(self.parent_window, 'is_filtering', True)
            if hasattr(self.parent_window, 'load_videos') and callable(self.parent_window.load_videos):
                self.parent_window.load_videos()

    def trigger_online_only_changed(self, state):
        if hasattr(self.parent_window, 'on_online_only_changed') and callable(self.parent_window.on_online_only_changed):
            self.parent_window.on_online_only_changed(state)
        else:
            setattr(self.parent_window, 'show_online_only', state == Qt.Checked)
            setattr(self.parent_window, 'is_filtering', True)
            if hasattr(self.parent_window, 'load_videos') and callable(self.parent_window.load_videos):
                self.parent_window.load_videos()

class MainWindow(QMainWindow):
    """主窗口类"""

    def __init__(self):
        super().__init__()
        self.core = MediaLibraryCore()
        self.setup_ui()
        self.setup_connections()
        self.setup_function_integration()
        self.load_data()

        # 应用扩展功能
        try:
            from pyside_extensions_patch import apply_all_extensions
            apply_all_extensions(self)
            print("✅ 扩展功能加载成功")
        except ImportError as e:
            print(f"⚠️ 扩展功能模块未找到: {e}")
        except Exception as e:
            print(f"⚠️ 扩展功能加载失败: {e}")

    def setup_ui(self):
        """设置主界面UI"""
        self.setWindowTitle("视频媒体库管理器 (PySide6版本)")
        self.setGeometry(100, 100, 1200, 800)

        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局
        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)

        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # 左侧面板
        left_widget = QWidget()
        left_widget.setMaximumWidth(300)
        left_layout = QVBoxLayout()
        left_widget.setLayout(left_layout)

        self.search_widget = SearchWidget(self)
        left_layout.addWidget(self.search_widget)

        splitter.addWidget(left_widget)

        # 右侧面板
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        right_widget.setLayout(right_layout)

        # 视频列表
        self.video_list = VideoListWidget(self)
        right_layout.addWidget(self.video_list)

        # 视频详情 - 使用滚动区域
        self.detail_scroll = QScrollArea()
        self.detail_scroll.setWidgetResizable(True)
        self.detail_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.detail_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.detail_scroll.setMinimumHeight(300)
        self.detail_scroll.setMaximumHeight(400)

        # 创建视频详情组件
        self.detail_widget = VideoDetailWidget(self)
        self.detail_scroll.setWidget(self.detail_widget)
        right_layout.addWidget(self.detail_scroll)

        splitter.addWidget(right_widget)

        # 设置分割比例
        splitter.setSizes([300, 900])

        # 创建菜单栏
        self.create_menus()

        # 创建状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")

        # 添加状态栏永久信息
        self.video_count_label = QLabel("0 个视频")
        self.status_bar.addPermanentWidget(self.video_count_label)

        # 连接日志信号
        qt_log_handler.log_signal.connect(self.append_log)

    def create_menus(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("文件")
        file_menu.addAction("扫描媒体文件", self.on_scan_media)
        file_menu.addAction("智能媒体库更新", self.on_comprehensive_media_update)
        file_menu.addSeparator()
        file_menu.addAction("导入NFO文件", self.on_import_nfo)
        file_menu.addAction("导入视频文件", self.on_import_videos)
        file_menu.addSeparator()
        file_menu.addAction("批量导入NFO信息", self.on_batch_import_nfo_for_no_actors)
        file_menu.addAction("批量导入JAVDB信息", self.on_batch_import_javdb_for_no_title)
        file_menu.addSeparator()
        file_menu.addAction("去重复", self.on_remove_duplicates)

        tools_menu = menubar.addMenu("工具")
        tools_menu.addAction("标签管理", self.on_manage_tags)
        tools_menu.addAction("文件夹管理", self.on_manage_folders)
        tools_menu.addSeparator()
        tools_menu.addAction("同步打分到文件", self.on_sync_stars_to_filename)
        tools_menu.addSeparator()
        tools_menu.addAction("批量计算MD5", self.on_batch_calculate_md5)
        tools_menu.addAction("智能去重", self.on_smart_remove_duplicates)
        tools_menu.addAction("文件移动管理", self.on_file_move_manager)

        tools_menu.addSeparator()
        tools_menu.addAction("JAV信息面板", self.open_jav_info_dialog)

        view_menu = menubar.addMenu("界面")
        view_menu.addAction("刷新", self.refresh_data)
        view_menu.addAction("清空筛选", self.clear_filters)

        help_menu = menubar.addMenu("帮助")
        help_menu.addAction("关于", self.show_about)
        help_menu.addAction("快捷键", self.show_shortcuts)

        self.create_shortcuts()

    def create_shortcuts(self):
        refresh_shortcut = QKeySequence(QKeyCombination(Qt.CTRL, Qt.Key_R))
        refresh_action = QAction(self)
        refresh_action.setShortcut(refresh_shortcut)
        refresh_action.triggered.connect(self.refresh_data)
        self.addAction(refresh_action)

        search_shortcut = QKeySequence(QKeyCombination(Qt.CTRL, Qt.Key_F))
        search_action = QAction(self)
        search_action.setShortcut(search_shortcut)
        search_action.triggered.connect(self.focus_search)
        self.addAction(search_action)

        for i in range(6):
            key_combination = QKeyCombination(Qt.CTRL, Qt.Key_0 if i == 0 else getattr(Qt, f'Key_{i}'))
            star_shortcut = QKeySequence(key_combination)
            star_action = QAction(self)
            star_action.setShortcut(star_shortcut)
            star_action.triggered.connect(lambda checked, rating=i: self.quick_set_star_from_shortcut(rating))
            self.addAction(star_action)

        play_shortcut = QKeySequence(Qt.Key_Space)
        play_action = QAction(self)
        play_action.setShortcut(play_shortcut)
        play_action.triggered.connect(self.play_video)
        self.addAction(play_action)

        thumbnail_shortcut = QKeySequence(Qt.Key_Return)
        thumbnail_action = QAction(self)
        thumbnail_action.setShortcut(thumbnail_shortcut)
        thumbnail_action.triggered.connect(self.generate_thumbnail)
        self.addAction(thumbnail_action)

    def open_jav_info_dialog(self):
        dialog = JavInfoDialog(self)
        dialog.exec()

    def focus_search(self):
        self.search_widget.title_search.setFocus()
        self.search_widget.title_search.selectAll()

    def quick_set_star_from_shortcut(self, rating):
        selected_items = self.video_list.selectedItems()
        if not selected_items:
            return
        video_id = selected_items[0].data(0, Qt.UserRole)
        self._set_video_star(video_id, rating)
        self.load_videos()

    def on_scan_media(self):
        self.status_bar.showMessage("开始扫描媒体文件", 2000)

    def on_comprehensive_media_update(self):
        self.status_bar.showMessage("执行智能媒体库更新", 2000)

    def on_import_nfo(self):
        self.status_bar.showMessage("导入NFO文件", 2000)

    def on_import_videos(self):
        self.status_bar.showMessage("导入视频文件", 2000)

    def on_batch_import_nfo_for_no_actors(self):
        self.status_bar.showMessage("批量导入NFO信息", 2000)

    def on_batch_import_javdb_for_no_title(self):
        self.status_bar.showMessage("批量导入JAVDB信息", 2000)

    def on_remove_duplicates(self):
        self.status_bar.showMessage("去重复", 2000)

    def on_manage_tags(self):
        self.status_bar.showMessage("标签管理", 2000)

    def on_manage_folders(self):
        self.status_bar.showMessage("文件夹管理", 2000)

    def on_sync_stars_to_filename(self):
        self.status_bar.showMessage("同步打分到文件", 2000)

    def on_batch_calculate_md5(self):
        self.status_bar.showMessage("批量计算MD5", 2000)

    def on_smart_remove_duplicates(self):
        self.status_bar.showMessage("智能去重", 2000)

    def on_file_move_manager(self):
        self.status_bar.showMessage("文件移动管理", 2000)

class JavInfoDialog(QDialog):
    def __init__(self, parent: QMainWindow):
        super().__init__(parent)
        self.setWindowTitle("JAV信息面板")
        self.resize(480, 360)
        layout = QVBoxLayout()
        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText("输入番号，例如 ABP-123")
        layout.addWidget(QLabel("番号"))
        layout.addWidget(self.code_edit)
        self.search_btn = QPushButton("搜索并保存")
        layout.addWidget(self.search_btn)
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        layout.addWidget(QLabel("结果"))
        layout.addWidget(self.result_text)
        self.setLayout(layout)
        self.search_btn.clicked.connect(self.on_search)

    def on_search(self):
        code = self.code_edit.text().strip()
        if not code:
            QMessageBox.warning(self, "提示", "请输入番号")
            return
        info = utils_jav.search_movie_info(code)
        if not info:
            QMessageBox.information(self, "提示", "未获取到信息")
            return
        # 展示
        self.result_text.setPlainText(json.dumps(info, ensure_ascii=False, indent=2))
        # 如果当前选中视频存在，则尝试保存
        main: MainWindow = self.parent()
        if hasattr(main, 'core') and main.core.current_video:
            vid = main.core.current_video[0]
            if utils_jav.save_movie_info_to_db(main.core.conn, vid, info):
                QMessageBox.information(self, "成功", "已保存到数据库")
                main.load_videos()
            else:
                QMessageBox.critical(self, "错误", "保存失败")

    def create_menus(self):
        """创建菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件")
        file_menu.addAction("扫描媒体文件", self.on_scan_media)
        file_menu.addAction("智能媒体库更新", self.on_comprehensive_media_update)
        file_menu.addSeparator()
        file_menu.addAction("导入NFO文件", self.on_import_nfo)
        file_menu.addAction("导入视频文件", self.on_import_videos)
        file_menu.addSeparator()
        file_menu.addAction("批量导入NFO信息", self.on_batch_import_nfo_for_no_actors)
        file_menu.addAction("批量导入JAVDB信息", self.on_batch_import_javdb_for_no_title)
        file_menu.addSeparator()
        file_menu.addAction("去重复", self.on_remove_duplicates)

        # 工具菜单
        tools_menu = menubar.addMenu("工具")
        tools_menu.addAction("标签管理", self.on_manage_tags)
        tools_menu.addAction("文件夹管理", self.on_manage_folders)
        tools_menu.addSeparator()
        tools_menu.addAction("同步打分到文件", self.on_sync_stars_to_filename)
        tools_menu.addSeparator()
        tools_menu.addAction("批量计算MD5", self.on_batch_calculate_md5)
        tools_menu.addAction("智能去重", self.on_smart_remove_duplicates)
        tools_menu.addAction("文件移动管理", self.on_file_move_manager)

        # JAV 信息面板
        tools_menu.addSeparator()
        tools_menu.addAction("JAV信息面板", self.open_jav_info_dialog)

        # 界面菜单
        view_menu = menubar.addMenu("界面")
        view_menu.addAction("刷新", self.refresh_data)
        view_menu.addAction("清空筛选", self.clear_filters)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助")
        help_menu.addAction("关于", self.show_about)
        help_menu.addAction("快捷键", self.show_shortcuts)

        # 创建快捷键
        self.create_shortcuts()

    def create_shortcuts(self):
        """创建快捷键"""
        # Ctrl+R: 刷新数据
        refresh_shortcut = QKeySequence(QKeyCombination(Qt.CTRL, Qt.Key_R))
        refresh_action = QAction(self)
        refresh_action.setShortcut(refresh_shortcut)
        refresh_action.triggered.connect(self.refresh_data)
        self.addAction(refresh_action)

        # Ctrl+F: 聚焦到搜索框
        search_shortcut = QKeySequence(QKeyCombination(Qt.CTRL, Qt.Key_F))
        search_action = QAction(self)
        search_action.setShortcut(search_shortcut)
        search_action.triggered.connect(self.focus_search)
        self.addAction(search_action)

        # Ctrl+0-5: 快速设置星级
        for i in range(6):
            # 修复Qt6兼容性问题
            key_combination = QKeyCombination(Qt.CTRL, Qt.Key_0 if i == 0 else getattr(Qt, f'Key_{i}'))
            star_shortcut = QKeySequence(key_combination)
            star_action = QAction(self)
            star_action.setShortcut(star_shortcut)
            star_action.triggered.connect(lambda checked, rating=i: self.quick_set_star_from_shortcut(rating))
            self.addAction(star_action)

        # Space: 播放视频
        play_shortcut = QKeySequence(Qt.Key_Space)
        play_action = QAction(self)
        play_action.setShortcut(play_shortcut)
        play_action.triggered.connect(self.play_video)
        self.addAction(play_action)

        # Enter: 生成封面
        thumbnail_shortcut = QKeySequence(Qt.Key_Return)
        thumbnail_action = QAction(self)
        thumbnail_action.setShortcut(thumbnail_shortcut)
        thumbnail_action.triggered.connect(self.generate_thumbnail)
        self.addAction(thumbnail_action)

    def open_jav_info_dialog(self):
        dialog = JavInfoDialog(self)
        dialog.exec()

    def focus_search(self):
        """聚焦到搜索框"""
        self.search_widget.title_search.setFocus()
        self.search_widget.title_search.selectAll()

    def quick_set_star_from_shortcut(self, rating):
        """通过快捷键快速设置星级"""
        selected_items = self.video_list.selectedItems()
        if not selected_items:
            return

        video_id = selected_items[0].data(0, Qt.UserRole)
        self._set_video_star(video_id, rating)
        self.load_videos()  # 刷新列表显示

    def setup_connections(self):
        """设置信号连接"""
        # 搜索筛选相关连接已由子组件设置
        pass

    def setup_function_integration(self):
        """设置功能集成，连接原有功能到新GUI"""
        try:
            # 重新启用功能集成
            self.integration = setup_full_integration(self)

            # 连接日志信号到状态栏
            qt_log_handler.log_signal.connect(self.update_status)

            print("功能集成已重新启用，所有原有功能现已可用")
        except Exception as e:
            print(f"功能集成设置失败: {e}")
            self.show_error("错误", f"功能集成设置失败: {e}")

    def update_status(self, message):
        """更新状态栏"""
        self.status_bar.showMessage(message, 5000)

    def show_error(self, title, message):
        """显示错误消息"""
        QMessageBox.critical(self, title, str(message))

    def show_info(self, title, message):
        """显示信息消息"""
        QMessageBox.information(self, title, str(message))

    def show_warning(self, title, message):
        """显示警告消息"""
        QMessageBox.warning(self, title, str(message))

    def ask_yes_no(self, title, message):
        """询问是否/否"""
        reply = QMessageBox.question(
            self, title, message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        return reply == QMessageBox.Yes

    def load_data(self):
        """加载数据"""
        self.load_tags()
        self.load_videos()

    def load_tags(self):
        """加载标签"""
        # 标签筛选功能已移除，通过搜索框进行标签搜索
        pass

    def load_videos(self):
        """加载视频列表"""
        try:
            # 确保数据库连接有效
            if not self.core.ensure_connection():
                raise Exception("数据库连接失败")

            # 显示加载状态
            self.status_bar.showMessage("正在加载视频列表...")

            # 清空现有列表
            self.video_list.clear()

            # 构建查询条件
            conditions = []
            params = []

            # 检查是否在筛选模式，如果是则添加搜索条件
            if getattr(self, 'is_filtering', False):
                # 标题搜索条件
                title_search_text = self.search_widget.title_search.text().strip()
                if title_search_text:
                    conditions.append("(v.title LIKE ? OR v.file_name LIKE ? OR j.javdb_title LIKE ?)")
                    title_search_param = f"%{title_search_text}%"
                    params.extend([title_search_param, title_search_param, title_search_param])

                # 标签搜索条件
                tag_search_text = self.search_widget.tag_search.text().strip()
                if tag_search_text:
                    conditions.append("(v.tags LIKE ? OR EXISTS (SELECT 1 FROM javdb_info_tags jit JOIN javdb_tags jt ON jit.tag_id = jt.id WHERE jit.javdb_info_id = j.id AND jt.tag_name LIKE ?))")
                    tag_search_param = f"%{tag_search_text}%"
                    params.extend([tag_search_param, tag_search_param])

                # 演员搜索条件
                actor_search_text = self.search_widget.actor_search.text().strip()
                if actor_search_text:
                    conditions.append("EXISTS (SELECT 1 FROM video_actors va JOIN actors a ON va.actor_id = a.id WHERE va.video_id = v.id AND a.name LIKE ?)")
                    actor_search_param = f"%{actor_search_text}%"
                    params.append(actor_search_param)

                # 星级筛选
                star_filter = self.search_widget.star_button_group.checkedId()
                if star_filter > 0:
                    conditions.append("v.stars = ?")
                    params.append(star_filter)

                # 标签筛选功能已移除 - 通过搜索框进行标签搜索

                # 文件夹来源筛选
                folder_filter = self.search_widget.folder_button_group.checkedId()
                if folder_filter > 0:  # 不是"全部文件夹"
                    selected_radio = self.search_widget.folder_button_group.button(folder_filter)
                    if selected_radio:
                        folder_path = selected_radio.property("folder_path")
                        if folder_path:
                            conditions.append("v.source_folder LIKE ?")
                            params.append(f"{folder_path}%")

            # 仅显示在线内容筛选
            show_online_only = getattr(self, 'show_online_only', False)
            if show_online_only:
                # 获取所有激活的文件夹
                self.core.cursor.execute("SELECT folder_path FROM folders WHERE is_active = 1")
                all_folders = [row[0] for row in self.core.cursor.fetchall()]

                # 检查哪些文件夹路径实际存在
                online_folders = []
                for folder_path in all_folders:
                    if os.path.exists(folder_path) and os.path.isdir(folder_path):
                        online_folders.append(folder_path)

                if online_folders:
                    folder_conditions = []
                    for folder_path in online_folders:
                        folder_conditions.append("v.source_folder LIKE ?")
                        params.append(f"{folder_path}%")
                    conditions.append(f"({' OR '.join(folder_conditions)})")
                else:
                    conditions.append("1 = 0")
            else:
                # 显示所有激活文件夹中的视频
                conditions.append("""
                    EXISTS (
                        SELECT 1 FROM folders f
                        WHERE f.is_active = 1
                        AND v.source_folder LIKE f.folder_path || '%'
                    )
                """)

            # 构建排序查询
            order_clause = "ORDER BY v.title"  # 默认排序
            if hasattr(self.core, 'sort_column_name') and self.core.sort_column_name:
                column_mapping = {
                    'title': 'v.title',
                    'stars': 'v.stars',
                    'tags': 'v.tags',
                    'file_size': 'v.file_size',
                    'is_nas_online': 'v.is_nas_online',
                    'duration': 'v.duration',
                    'resolution': 'v.resolution',
                    'file_created_time': 'v.file_created_time',
                    'year': 'v.year',
                    'javdb_code': 'j.javdb_code',
                    'javdb_title': 'j.javdb_title',
                    'javdb_rating': 'j.score'
                }

                db_column = column_mapping.get(self.core.sort_column_name, 'v.title')
                direction = "DESC" if getattr(self.core, 'sort_reverse', False) else "ASC"
                order_clause = f"ORDER BY {db_column} {direction}"

            # 构建最终查询
            if conditions:
                where_clause = f"WHERE {' AND '.join(conditions)}"
            else:
                where_clause = ""

            query = f"""
                SELECT v.*, j.javdb_code, j.javdb_title, j.score, j.release_date
                FROM videos v
                LEFT JOIN javdb_info j ON v.id = j.video_id
                {where_clause}
                {order_clause}
            """

            self.core.cursor.execute(query, params)
            videos = self.core.cursor.fetchall()

            # 设置列标题
            sorted_columns = sorted(self.core.column_config.items(), key=lambda x: x[1]['position'])
            column_names = [col[0] for col in sorted_columns]
            column_texts = [self.core.column_config[col]['text'] for col in column_names]
            self.video_list.setHeaderLabels(column_texts)

            # 添加视频到列表
            for video in videos:
                item_data = []

                # 解包视频数据
                video_id, file_path, file_name, file_size, file_hash, title, description, genre, year, rating, stars, tags, nas_path, is_nas_online, created_at, updated_at, thumbnail_data, thumbnail_path, duration, resolution, file_created_time, source_folder, md5_hash = video[:23]

                # 获取JAVDB信息
                javdb_code = video[23] if len(video) > 23 else None
                javdb_title = video[24] if len(video) > 24 else None
                javdb_rating = video[25] if len(video) > 25 else None
                release_date = video[26] if len(video) > 26 else None

                # 获取演员信息
                actors_display = self._get_video_actors(video_id)

                # 获取JAVDB标签
                javdb_tags_display = self._get_javdb_tags(video_id)

                # 格式化显示值
                for col in column_names:
                    value = ""
                    if col == 'title':
                        value = title or file_name or ""
                    elif col == 'file_name':
                        value = file_name or ""
                    elif col == 'stars':
                        value = self.format_stars_display(stars) if stars else ""
                    elif col == 'tags':
                        value = tags if tags else ""
                    elif col == 'file_size':
                        value = self.format_file_size(file_size) if file_size else ""
                    elif col == 'duration':
                        value = self.format_duration(duration) if duration else ""
                    elif col == 'resolution':
                        value = resolution if resolution else ""
                    elif col == 'year':
                        if year:
                            value = str(year)
                        else:
                            value = self._extract_year_from_filename(file_name or title)
                    elif col == 'is_nas_online':
                        value = "在线" if self._is_video_online(video_id, source_folder, is_nas_online) else "离线"
                    elif col == 'source_folder':
                        value = source_folder or ""
                    elif col == 'file_created_time':
                        value = self._format_timestamp(file_created_time) if file_created_time else ""
                    elif col == 'created_at':
                        value = self._format_timestamp(created_at) if created_at else ""
                    elif col == 'javdb_code':
                        value = javdb_code or ""
                    elif col == 'javdb_title':
                        value = javdb_title or ""
                    elif col == 'javdb_rating':
                        value = str(javdb_rating) if javdb_rating else ""
                    elif col == 'file_path':
                        value = file_path or ""

                    item_data.append(value)

                item = QTreeWidgetItem(item_data)
                item.setData(0, Qt.UserRole, video_id)  # 存储视频ID
                self.video_list.addTopLevelItem(item)

            # 显示加载完成状态
            video_count = len(videos)
            filter_status = " (筛选模式)" if getattr(self, 'is_filtering', False) else ""

            # 更新状态栏
            self.status_bar.showMessage(f"已加载 {video_count} 个视频{filter_status}", 3000)
            self.video_count_label.setText(f"{video_count} 个视频")

        except Exception as e:
            error_msg = f"加载视频失败: {e}"
            print(error_msg)
            import traceback
            traceback.print_exc()
            self.status_bar.showMessage("视频加载失败", 5000)
            self.show_error("错误", f"视频加载失败: {e}")

    def _get_video_actors(self, video_id):
        """获取视频的演员信息"""
        try:
            self.core.cursor.execute("""
                SELECT GROUP_CONCAT(a.name, ', ')
                FROM video_actors va
                JOIN actors a ON va.actor_id = a.id
                WHERE va.video_id = ?
                ORDER BY a.name
            """, (video_id,))
            result = self.core.cursor.fetchone()
            return result[0] if result and result[0] else ""
        except Exception:
            return ""

    def _get_javdb_tags(self, video_id):
        """获取JAVDB标签"""
        try:
            self.core.cursor.execute("""
                SELECT GROUP_CONCAT(jt.tag_name, ', ')
                FROM javdb_info jit
                JOIN javdb_info_tags jitt ON jit.id = jitt.javdb_info_id
                JOIN javdb_tags jt ON jitt.tag_id = jt.id
                WHERE jit.video_id = ?
                ORDER BY jt.tag_name
            """, (video_id,))
            result = self.core.cursor.fetchone()
            return result[0] if result and result[0] else ""
        except Exception:
            return ""

    def _is_video_online(self, video_id, source_folder, is_nas_online):
        """判断视频是否在线"""
        try:
            if source_folder:
                self.core.cursor.execute("""
                    SELECT folder_path, is_active
                    FROM folders
                    WHERE ? LIKE folder_path || '%'
                    ORDER BY LENGTH(folder_path) DESC
                    LIMIT 1
                """, (source_folder,))
                row = self.core.cursor.fetchone()
                if row:
                    folder_path, is_active = row
                    return bool(is_active) and os.path.exists(folder_path)
            return bool(is_nas_online) if is_nas_online is not None else False
        except Exception:
            return bool(is_nas_online) if is_nas_online is not None else False

    def _extract_year_from_filename(self, filename):
        """从文件名中提取年份"""
        if not filename:
            return ""

        import re
        year_pattern = r'\b(19|20)\d{2}\b'
        year_matches = re.findall(year_pattern, filename)
        return year_matches[-1] if year_matches else ""

    def _format_timestamp(self, timestamp):
        """格式化时间戳"""
        if not timestamp:
            return ""

        try:
            if isinstance(timestamp, str):
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            else:
                dt = timestamp
            return dt.strftime("%Y-%m-%d")
        except:
            return str(timestamp)[:10] if timestamp else ""

    def format_stars_display(self, stars):
        """格式化星级显示"""
        if not stars:
            return ""

        full_stars = min(int(stars), 5)
        empty_stars = 5 - full_stars

        return "★" * full_stars + "☆" * empty_stars

    def format_duration(self, duration):
        """格式化时长显示"""
        if not duration:
            return ""

        try:
            duration = int(duration)
            hours = duration // 3600
            minutes = (duration % 3600) // 60
            seconds = duration % 60

            if hours > 0:
                return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                return f"{minutes:02d}:{seconds:02d}"
        except:
            return str(duration)

    def format_file_size(self, size_bytes):
        """格式化文件大小"""
        if not size_bytes:
            return ""

        size = int(size_bytes)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"

    def on_search(self):
        """搜索事件处理"""
        # 设置筛选标志并加载视频
        self.is_filtering = True
        self.load_videos()

    def on_online_only_changed(self, state):
        """仅显示在线状态改变事件"""
        self.show_online_only = (state == Qt.Checked)
        self.is_filtering = True
        self.load_videos()

    def on_video_selection_changed(self):
        """视频选择变化事件"""
        selected_items = self.video_list.selectedItems()
        if selected_items:
            video_id = selected_items[0].data(0, Qt.UserRole)
            self.load_video_detail(video_id)

    def on_video_double_clicked(self, item, column):
        """视频双击事件"""
        self.play_video()

    def on_video_header_clicked(self, column):
        """视频列表标题点击事件（排序）"""
        # 获取列名
        sorted_columns = sorted(self.core.column_config.items(), key=lambda x: x[1]['position'])
        column_names = [col[0] for col in sorted_columns]

        if column < len(column_names):
            column_name = column_names[column]

            # 如果是同一列，切换排序方向；否则设置为升序
            if hasattr(self.core, 'sort_column_name') and self.core.sort_column_name == column_name:
                self.core.sort_reverse = not getattr(self.core, 'sort_reverse', False)
            else:
                self.core.sort_column_name = column_name
                self.core.sort_reverse = False

            # 重新加载数据
            self.load_videos()

    def show_context_menu(self, position):
        """显示右键菜单"""
        # 获取点击的项目
        item = self.video_list.itemAt(position)
        if not item:
            return

        # 获取当前选中的所有项目
        selected_items = self.video_list.selectedItems()

        # 如果点击的项目不在选中列表中，则选中点击的项目
        if item not in selected_items:
            self.video_list.setCurrentItem(item)
            selected_items = [item]

        # 创建右键菜单
        context_menu = QMenu(self)

        # 添加菜单项
        play_action = context_menu.addAction("播放视频")
        play_action.triggered.connect(self.play_video)

        context_menu.addSeparator()

        show_in_finder_action = context_menu.addAction("在文件管理器中显示")
        show_in_finder_action.triggered.connect(self.show_in_file_manager)

        copy_path_action = context_menu.addAction("复制文件路径")
        copy_path_action.triggered.connect(self.copy_file_path)

        context_menu.addSeparator()

        # 快速设置星级子菜单
        star_menu = context_menu.addMenu("快速设置星级")

        # 清除星级
        clear_star_action = star_menu.addAction("清除星级")
        clear_star_action.triggered.connect(lambda: self.quick_set_star(0))

        # 1-5星选项
        for i in range(1, 6):
            star_action = star_menu.addAction(f"{i}星")
            star_action.triggered.connect(lambda checked, star=i: self.quick_set_star(star))

        context_menu.addSeparator()

        refresh_thumbnail_action = context_menu.addAction("刷新封面")
        refresh_thumbnail_action.triggered.connect(self.refresh_thumbnail)

        context_menu.addSeparator()

        delete_action = context_menu.addAction("删除视频")
        delete_action.triggered.connect(self.delete_video)

        # 显示菜单
        context_menu.exec_(self.video_list.mapToGlobal(position))

    def show_in_file_manager(self):
        """在文件管理器中显示文件"""
        selected_items = self.video_list.selectedItems()
        if not selected_items:
            return

        video_id = selected_items[0].data(0, Qt.UserRole)
        try:
            self.core.cursor.execute("SELECT file_path FROM videos WHERE id = ?", (video_id,))
            result = self.core.cursor.fetchone()
            if result and result[0]:
                import subprocess
                import platform

                file_path = result[0]
                if platform.system() == "Darwin":  # macOS
                    subprocess.run(["open", "-R", file_path])
                elif platform.system() == "Windows":
                    subprocess.run(["explorer", "/select,", file_path])
                else:  # Linux
                    subprocess.run(["xdg-open", os.path.dirname(file_path)])
        except Exception as e:
            self.show_error("错误", f"无法打开文件管理器: {e}")

    def copy_file_path(self):
        """复制文件路径"""
        selected_items = self.video_list.selectedItems()
        if not selected_items:
            return

        video_id = selected_items[0].data(0, Qt.UserRole)
        try:
            self.core.cursor.execute("SELECT file_path FROM videos WHERE id = ?", (video_id,))
            result = self.core.cursor.fetchone()
            if result and result[0]:
                clipboard = QApplication.clipboard()
                clipboard.setText(result[0])
                self.status_bar.showMessage("文件路径已复制到剪贴板", 3000)
        except Exception as e:
            self.show_error("错误", f"复制路径失败: {e}")

    def quick_set_star(self, rating):
        """快速设置星级 - 支持批量操作"""
        selected_items = self.video_list.selectedItems()
        if not selected_items:
            return

        # 确认操作
        if len(selected_items) == 1:
            # 单个视频，直接设置
            video_id = selected_items[0].data(0, Qt.UserRole)
            self._set_video_star(video_id, rating)
        else:
            # 多个视频，需要确认
            star_text = f"{rating}星" if rating > 0 else "清除星级"
            reply = self.ask_yes_no(
                "确认批量设置",
                f"确定要将选中的 {len(selected_items)} 个视频设置为{star_text}吗？"
            )
            if reply:
                success_count = 0
                for item in selected_items:
                    video_id = item.data(0, Qt.UserRole)
                    if self._set_video_star(video_id, rating, show_message=False):
                        success_count += 1

                if success_count > 0:
                    self.show_info("成功", f"已将 {success_count} 个视频设置为{star_text}")
                    self.load_videos()  # 刷新列表

    def _set_video_star(self, video_id, rating, show_message=True):
        """设置单个视频的星级"""
        try:
            self.core.cursor.execute(
                "UPDATE videos SET stars = ? WHERE id = ?",
                (rating, video_id)
            )
            self.core.conn.commit()

            if show_message:
                star_text = f"{rating}星" if rating > 0 else "无星级"
                self.status_bar.showMessage(f"已设置为 {star_text}", 3000)

            # 如果当前正在显示该视频的详情，更新详情显示
            if self.core.current_video and self.core.current_video[0] == video_id:
                self.update_star_display(rating)

            return True
        except Exception as e:
            if show_message:
                self.show_error("错误", f"设置星级失败: {e}")
            return False

    def refresh_thumbnail(self):
        """刷新封面 - 重新生成封面"""
        selected_items = self.video_list.selectedItems()
        if not selected_items:
            return

        video_id = selected_items[0].data(0, Qt.UserRole)

        # 确认是否要重新生成封面
        reply = self.ask_yes_no("确认刷新", "确定要重新生成这个视频的封面吗？\n这将覆盖现有的封面。")
        if reply:
            # 获取视频信息
            self.core.cursor.execute("SELECT file_path, source_folder, is_nas_online FROM videos WHERE id = ?", (video_id,))
            result = self.core.cursor.fetchone()
            if not result:
                self.show_error("错误", "找不到视频信息")
                return

            file_path, source_folder, is_nas_online = result

            # 检查视频是否在线
            if not self._is_video_online(video_id, source_folder, is_nas_online):
                self.show_warning("提示", "视频离线，无法刷新封面")
                return

            # 检查文件是否存在
            if not os.path.exists(file_path):
                self.show_error("错误", "视频文件不存在")
                return

            try:
                # 获取FFmpeg命令
                ffmpeg_cmd = self.core.get_ffmpeg_command()
                if ffmpeg_cmd is None:
                    self.show_error("错误", "需要安装FFmpeg才能生成封面\n\nmacOS: brew install ffmpeg")
                    return

                # 创建临时文件
                with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
                    temp_path = temp_file.name

                # 生成缩略图（使用优化的GPU加速命令）
                cmd = self.core.get_optimized_ffmpeg_cmd(file_path, temp_path)
                if cmd is None:
                    self.show_error("错误", "无法构建FFmpeg命令")
                    return

                # 显示进度提示
                self.status_bar.showMessage("正在刷新封面...")

                result = subprocess.run(cmd, capture_output=True)

                if result.returncode == 0 and os.path.exists(temp_path):
                    # 读取图片数据
                    with open(temp_path, 'rb') as f:
                        thumbnail_data = f.read()

                    # 保存到数据库
                    self.core.cursor.execute(
                        "UPDATE videos SET thumbnail_data = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (thumbnail_data, video_id)
                    )
                    self.core.conn.commit()

                    # 如果当前正在显示该视频的详情，更新封面显示
                    if self.core.current_video and self.core.current_video[0] == video_id:
                        self.detail_widget.display_thumbnail(thumbnail_data)

                    self.show_info("成功", "封面刷新成功")
                    self.status_bar.showMessage("封面刷新成功", 3000)

                    # 清理临时文件
                    try:
                        os.unlink(temp_path)
                    except:
                        pass

                else:
                    # 显示详细的FFmpeg错误信息
                    error_msg = "刷新封面失败"
                    if result.stderr:
                        stderr_text = result.stderr.decode('utf-8', errors='ignore')
                        error_msg += f"\n错误详情: {stderr_text.strip()}"
                    if result.returncode != 0:
                        error_msg += f"\n返回码: {result.returncode}"
                    self.show_error("错误", error_msg)
                    self.status_bar.showMessage("封面刷新失败", 5000)

            except Exception as e:
                self.show_error("错误", f"刷新封面失败: {e}")
                self.status_bar.showMessage("封面刷新失败", 5000)

    def delete_video(self):
        """删除视频"""
        selected_items = self.video_list.selectedItems()
        if not selected_items:
            return

        video_id = selected_items[0].data(0, Qt.UserRole)
        if self.ask_yes_no("确认删除", "确定要删除这个视频记录吗？\n此操作不可撤销。"):
            try:
                self.core.cursor.execute("DELETE FROM videos WHERE id = ?", (video_id,))
                self.core.conn.commit()
                self.load_videos()
                self.show_info("成功", "视频记录已删除")
            except Exception as e:
                self.show_error("错误", f"删除视频失败: {e}")

    def load_video_detail(self, video_id):
        """加载视频详情"""
        try:
            # 获取基本信息
            self.core.cursor.execute("SELECT * FROM videos WHERE id = ?", (video_id,))
            video = self.core.cursor.fetchone()

            if not video:
                return

            self.core.current_video = video

            # 获取JAVDB信息
            self.core.cursor.execute("SELECT * FROM javdb_info WHERE video_id = ?", (video_id,))
            javdb_info = self.core.cursor.fetchone()

            # 获取演员信息
            actors = self._get_video_actors(video_id)

            # 解包视频数据
            video_id, file_path, file_name, file_size, file_hash, title, description, genre, year, rating, stars, tags, nas_path, is_nas_online, created_at, updated_at, thumbnail_data, thumbnail_path, duration, resolution, file_created_time, source_folder, md5_hash = video[:23]

            # 填充基本信息
            self.detail_widget.title_edit.setText(title or "")
            self.detail_widget.desc_edit.setPlainText(description or "")
            self.detail_widget.tags_edit.setText(tags or "")

            # 填充新字段
            self.detail_widget.actors_label.setText(actors if actors else "无演员信息")
            self.detail_widget.filename_label.setText(file_name or "")
            self.detail_widget.filepath_label.setText(file_path or "")
            self.detail_widget.filesize_label.setText(self.format_file_size(file_size) if file_size else "")
            self.detail_widget.duration_label.setText(self.format_duration(duration) if duration else "")
            self.detail_widget.resolution_label.setText(resolution or "")

            # 填充JAVDB信息
            if javdb_info:
                self.detail_widget.javdb_code_label.setText(javdb_info[2] if len(javdb_info) > 2 else "")
                self.detail_widget.javdb_title_label.setText(javdb_info[4] if len(javdb_info) > 4 else "")
                self.detail_widget.javdb_rating_label.setText(str(javdb_info[15]) if len(javdb_info) > 15 and javdb_info[15] else "")
                self.detail_widget.release_date_label.setText(javdb_info[5] if len(javdb_info) > 5 else "")
            else:
                self.detail_widget.javdb_code_label.setText("")
                self.detail_widget.javdb_title_label.setText("")
                self.detail_widget.javdb_rating_label.setText("")
                self.detail_widget.release_date_label.setText("")

            # 填充时间信息
            self.detail_widget.created_time_label.setText(self._format_timestamp(created_at) if created_at else "")
            self.detail_widget.updated_time_label.setText(self._format_timestamp(updated_at) if updated_at else "")

            # 显示封面 - 优先级：videos.thumbnail_data > javdb_info.cover_image_data > thumbnail_path
            display_thumbnail_data = None

            # 1) 首先尝试videos表的thumbnail_data
            if thumbnail_data:
                display_thumbnail_data = thumbnail_data

            # 2) 如果videos表没有，尝试从javdb_info获取封面
            if not display_thumbnail_data and javdb_info:
                try:
                    # javdb_info的cover_image_data在索引位置16（从0开始）
                    if len(javdb_info) > 16 and javdb_info[16]:
                        display_thumbnail_data = javdb_info[16]
                except (IndexError, TypeError):
                    pass

            # 3) 如果数据库都没有，尝试从thumbnail_path读取文件
            if not display_thumbnail_data and thumbnail_path and os.path.exists(thumbnail_path):
                display_thumbnail_data = thumbnail_path

            # 显示封面
            self.detail_widget.display_thumbnail(display_thumbnail_data)

            # 更新星级显示
            self.update_star_display(stars if stars else 0)

            # 连接按钮事件
            self._connect_detail_buttons()

        except Exception as e:
            print(f"加载视频详情失败: {e}")
            import traceback
            traceback.print_exc()

    def _connect_detail_buttons(self):
        """连接详情页按钮事件"""
        if not hasattr(self, '_buttons_connected'):
            # 播放按钮
            self.detail_widget.play_button.clicked.connect(self.play_video)
            # 保存按钮
            self.detail_widget.save_button.clicked.connect(self.save_video_info)
            # 设置星级按钮
            self.detail_widget.set_star_button.clicked.connect(self.show_star_dialog)
            # 添加标签按钮
            self.detail_widget.add_tag_button.clicked.connect(self.add_tag_to_video)
            # 获取JAVDB信息按钮
            self.detail_widget.fetch_info_button.clicked.connect(self.fetch_current_javdb_info)
            # 生成封面按钮
            self.detail_widget.generate_thumbnail_button.clicked.connect(self.generate_thumbnail)
            # 删除按钮
            self.detail_widget.delete_button.clicked.connect(self.delete_video)

            self._buttons_connected = True

    def save_video_info(self):
        """保存视频信息"""
        if not self.core.current_video:
            return

        try:
            video_id = self.core.current_video[0]
            title = self.detail_widget.title_edit.text().strip()
            description = self.detail_widget.desc_edit.toPlainText().strip()
            tags = self.detail_widget.tags_edit.text().strip()

            self.core.cursor.execute("""
                UPDATE videos
                SET title = ?, description = ?, tags = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (title, description, tags, video_id))

            self.core.conn.commit()
            self.show_info("成功", "视频信息已保存")
            self.load_videos()  # 刷新列表
        except Exception as e:
            self.show_error("错误", f"保存失败: {e}")

    def show_star_dialog(self):
        """显示星级设置对话框"""
        if not self.core.current_video:
            return

        current_stars = self.core.current_video[10] if self.core.current_video[10] else 0

        dialog = QDialog(self)
        dialog.setWindowTitle("设置星级")
        dialog.setFixedSize(300, 150)

        layout = QVBoxLayout()

        # 星级按钮组
        star_group = QButtonGroup()
        star_layout = QHBoxLayout()

        for i in range(6):
            star_text = "清除" if i == 0 else f"{i}星"
            radio = QRadioButton(star_text)
            star_group.addButton(radio, i)
            star_layout.addWidget(radio)

        # 设置当前星级
        buttons = star_group.buttons()
        if current_stars < len(buttons):
            buttons[current_stars].setChecked(True)

        # 确认按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)

        layout.addLayout(star_layout)
        layout.addWidget(button_box)
        dialog.setLayout(layout)

        if dialog.exec_() == QDialog.Accepted:
            new_stars = star_group.checkedId()
            self.set_star_rating(new_stars)

    def add_tag_to_video(self):
        """为视频添加标签"""
        if not self.core.current_video:
            return

        # 这里可以实现一个更复杂的标签选择对话框
        current_tags = self.detail_widget.tags_edit.text().strip()
        if current_tags:
            new_tag = current_tags + ", "
        else:
            new_tag = ""

        new_tag += "新标签"  # 可以让用户输入

        self.detail_widget.tags_edit.setText(new_tag)
        self.show_info("提示", "请在标签框中编辑标签，然后点击保存")

    def fetch_current_javdb_info(self):
        """获取当前视频的JAV信息（含 JavSP 集成），并保存到数据库"""
        if not self.core.current_video:
            return

        try:
            video_id = self.core.current_video[0]
            file_name = self.core.current_video[2]
            code = utils_jav.extract_code(file_name)
            if not code:
                self.show_warning("提示", "无法从文件名提取番号")
                return

            self.status_bar.showMessage(f"正在获取JAV信息：{code}...")
            info = utils_jav.search_movie_info(code)
            if not info:
                self.show_warning("提示", "未能获取到JAV信息")
                return

            ok = utils_jav.save_movie_info_to_db(self.core.conn, video_id, info)
            if not ok:
                self.show_error("错误", "保存JAV信息到数据库失败")
                return

            self.show_info("成功", "JAV信息已保存")
            self.load_videos()
        except Exception as e:
            self.show_error("错误", f"获取JAV信息失败: {e}")

    def generate_thumbnail(self):
        """生成视频封面"""
        if not self.core.current_video:
            self.show_warning("提示", "请先选择一个视频")
            return

        video_id = self.core.current_video[0]
        file_path = self.core.current_video[1]
        source_folder = self.core.current_video[19]  # source_folder
        is_nas_online = self.core.current_video[13]

        # 检查视频是否在线
        if not self._is_video_online(video_id, source_folder, is_nas_online):
            self.show_warning("提示", "视频离线，无法生成封面")
            return

        # 检查文件是否存在
        if not os.path.exists(file_path):
            self.show_error("错误", "视频文件不存在")
            return

        try:
            # 获取FFmpeg命令
            ffmpeg_cmd = self.core.get_ffmpeg_command()
            if ffmpeg_cmd is None:
                self.show_error("错误", "需要安装FFmpeg才能生成封面\n\nmacOS: brew install ffmpeg")
                return

            # 创建临时文件
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
                temp_path = temp_file.name

            # 生成缩略图（使用优化的GPU加速命令）
            cmd = self.core.get_optimized_ffmpeg_cmd(file_path, temp_path)
            if cmd is None:
                self.show_error("错误", "无法构建FFmpeg命令")
                return

            # 显示进度提示
            self.status_bar.showMessage("正在生成封面...")

            result = subprocess.run(cmd, capture_output=True)

            if result.returncode == 0 and os.path.exists(temp_path):
                # 读取图片数据
                with open(temp_path, 'rb') as f:
                    thumbnail_data = f.read()

                # 保存到数据库
                self.core.cursor.execute(
                    "UPDATE videos SET thumbnail_data = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (thumbnail_data, video_id)
                )
                self.core.conn.commit()

                # 显示封面
                self.detail_widget.display_thumbnail(thumbnail_data)

                self.show_info("成功", "封面生成成功")
                self.status_bar.showMessage("封面生成成功", 3000)

                # 清理临时文件
                try:
                    os.unlink(temp_path)
                except:
                    pass

            else:
                # 显示详细的FFmpeg错误信息
                error_msg = "生成封面失败"
                if result.stderr:
                    stderr_text = result.stderr.decode('utf-8', errors='ignore')
                    error_msg += f"\n错误详情: {stderr_text.strip()}"
                if result.returncode != 0:
                    error_msg += f"\n返回码: {result.returncode}"
                self.show_error("错误", error_msg)
                self.status_bar.showMessage("封面生成失败", 5000)

        except Exception as e:
            self.show_error("错误", f"生成封面失败: {e}")
            self.status_bar.showMessage("封面生成失败", 5000)

    def delete_video(self):
        """删除视频"""
        if not self.core.current_video:
            return

        video_id = self.core.current_video[0]
        if self.ask_yes_no("确认删除", "确定要删除这个视频记录吗？\n此操作不可撤销。"):
            try:
                self.core.cursor.execute("DELETE FROM videos WHERE id = ?", (video_id,))
                self.core.conn.commit()
                self.load_videos()
                self.show_info("成功", "视频记录已删除")

                # 清空详情显示
                self._clear_detail_display()
            except Exception as e:
                self.show_error("错误", f"删除视频失败: {e}")

    def _clear_detail_display(self):
        """清空详情显示"""
        self.detail_widget.title_edit.setText("")
        self.detail_widget.desc_edit.setPlainText("")
        self.detail_widget.tags_edit.setText("")
        self.detail_widget.actors_label.setText("无演员信息")
        self.detail_widget.filename_label.setText("")
        self.detail_widget.filepath_label.setText("")
        self.detail_widget.filesize_label.setText("")
        self.detail_widget.duration_label.setText("")
        self.detail_widget.resolution_label.setText("")
        self.detail_widget.javdb_code_label.setText("")
        self.detail_widget.javdb_title_label.setText("")
        self.detail_widget.javdb_rating_label.setText("")
        self.detail_widget.release_date_label.setText("")
        self.detail_widget.created_time_label.setText("")
        self.detail_widget.updated_time_label.setText("")
        self.update_star_display(0)

    def update_star_display(self, rating):
        """更新星级显示"""
        for i, label in enumerate(self.detail_widget.star_labels):
            if i < rating:
                label.setText("★")
            else:
                label.setText("☆")

    def append_log(self, message):
        """添加日志到状态栏"""
        self.status_bar.showMessage(message)

    # 以下是菜单动作的实现，这些方法将调用原有的核心功能
    def on_scan_media(self):
        """扫描媒体文件"""
        # 创建进度对话框
        progress_dialog = ScanProgressDialog(self)
        progress_dialog.show()

        # 创建工作线程
        class ScanWorker(QThread):
            progress_signal = Signal(str, int, int, int, int, int)  # message, progress, scanned, added, updated, skipped
            finished_signal = Signal(dict)  # result
            error_signal = Signal(str)  # error message

            def __init__(self, core):
                super().__init__()
                self.core = core
                self._cancelled = False

            def run(self):
                try:
                    # 进度回调函数
                    def progress_callback(message, progress=None, scanned=0, added=0, updated=0, skipped=0):
                        if self._cancelled:
                            return
                        self.progress_signal.emit(message, progress or 0, scanned, added, updated, skipped)

                    # 取消检查函数
                    def cancel_check():
                        return self._cancelled

                    # 执行扫描
                    result = self.core.scan_media_files(progress_callback, cancel_check)

                    if not self._cancelled:
                        self.finished_signal.emit(result)

                except Exception as e:
                    self.error_signal.emit(f"扫描过程中出现异常: {str(e)}")

            def cancel(self):
                self._cancelled = True

        # 创建并启动工作线程
        worker = ScanWorker(self.core)

        def on_progress(message, progress, scanned, added, updated, skipped):
            progress_dialog.update_progress(progress, message)
            progress_dialog.update_stats(scanned, added, updated, skipped)
            progress_dialog.append_log(message)

        def on_finished(result):
            progress_dialog.close()

            if result.get('cancelled'):
                return
            elif result.get('error'):
                self.show_error("扫描失败", result['error'])
            else:
                # 显示成功消息
                scanned = result.get('scanned', 0)
                added = result.get('added', 0)
                updated = result.get('updated', 0)
                skipped = result.get('skipped', 0)

                message = (
                    f"媒体文件扫描完成！\n\n"
                    f"总扫描文件: {scanned}\n"
                    f"新增文件: {added}\n"
                    f"更新文件: {updated}\n"
                    f"跳过文件: {skipped}"
                )
                self.show_info("扫描完成", message)

                # 刷新视频列表
                self.load_data()

        def on_error(error_message):
            progress_dialog.close()
            self.show_error("扫描错误", error_message)

        def on_cancel():
            worker.cancel()

        # 连接信号
        worker.progress_signal.connect(on_progress)
        worker.finished_signal.connect(on_finished)
        worker.error_signal.connect(on_error)
        progress_dialog.cancel_button.clicked.connect(on_cancel)

        # 启动扫描
        worker.start()

    def on_comprehensive_media_update(self):
        """智能媒体库更新"""
        try:
            if hasattr(self, 'original_comprehensive_media_update'):
                self.original_comprehensive_media_update()
            else:
                self.show_info("提示", "智能媒体库更新功能正在集成中...")
        except Exception as e:
            self.show_error("错误", f"智能媒体库更新失败: {e}")

    def on_import_nfo(self):
        """导入NFO文件"""
        # 检查是否有选中的视频
        selected_items = self.video_list.selectedItems()
        if not selected_items:
            self.show_warning("提示", "请先选择一个视频，然后导入对应的NFO文件")
            return

        video_id = selected_items[0].data(0, Qt.UserRole)
        if not video_id:
            self.show_error("错误", "无法获取视频ID")
            return

        # 获取视频文件路径
        try:
            self.core.cursor.execute("SELECT file_path FROM videos WHERE id = ?", (video_id,))
            video_result = self.core.cursor.fetchone()
            if not video_result:
                self.show_error("错误", "无法找到视频记录")
                return

            video_path = video_result[0]
            video_dir = os.path.dirname(video_path)
        except Exception as e:
            self.show_error("错误", f"获取视频路径失败: {e}")
            return

        # 打开文件选择对话框，默认到视频文件所在目录
        nfo_file, _ = QFileDialog.getOpenFileName(
            self,
            "选择NFO文件",
            video_dir,
            "NFO文件 (*.nfo);;所有文件 (*)"
        )

        if not nfo_file:
            return  # 用户取消了选择

        try:
            # 调用核心功能导入NFO
            success, message = self.core.import_nfo_file(nfo_file, video_id=video_id)

            if success:
                self.show_info("成功", message)
                # 刷新视频详情和列表
                self.load_video_detail(video_id)
                self.load_videos()
            else:
                self.show_error("导入失败", message)

        except Exception as e:
            self.show_error("错误", f"导入NFO文件时出现异常: {e}")

    def on_import_videos(self):
        """导入视频文件"""
        try:
            if hasattr(self, 'original_import_videos'):
                self.original_import_videos()
            else:
                self.show_info("提示", "导入视频文件功能正在集成中...")
        except Exception as e:
            self.show_error("错误", f"导入视频文件失败: {e}")

    def on_remove_duplicates(self):
        """去重复"""
        try:
            if hasattr(self, 'original_remove_duplicates'):
                self.original_remove_duplicates()
            else:
                self.show_info("提示", "去重复功能正在集成中...")
        except Exception as e:
            self.show_error("错误", f"去重复失败: {e}")

    def on_batch_import_nfo_for_no_actors(self):
        """批量导入NFO信息（为没有演员信息的视频）"""
        try:
            from PySide6.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self, "确认操作",
                "此功能将为没有演员信息的视频批量导入NFO文件。\n"
                "这可能需要较长时间，确定要继续吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.show_info("提示", "批量NFO导入功能正在开发中...")
        except Exception as e:
            self.show_error("错误", f"批量NFO导入失败: {e}")

    def on_batch_import_javdb_for_no_title(self):
        """批量导入JAV信息（为没有标题的视频），使用 JavSP 回退"""
        try:
            from PySide6.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self, "确认操作",
                "此功能将为没有完整标题的视频批量导入JAV信息。\n"
                "这需要网络连接并且可能需要较长时间，确定要继续吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply != QMessageBox.Yes:
                return

            # 查询无标题的视频
            self.core.cursor.execute("SELECT id, file_name FROM videos WHERE (title IS NULL OR title='')")
            rows = self.core.cursor.fetchall()
            if not rows:
                self.show_info("提示", "没有需要导入的项目")
                return

            total = len(rows)
            success = 0
            for idx, (vid, fname) in enumerate(rows, 1):
                code = utils_jav.extract_code(fname)
                info = utils_jav.search_movie_info(code) if code else None
                if info and utils_jav.save_movie_info_to_db(self.core.conn, vid, info):
                    success += 1
                self.status_bar.showMessage(f"批量导入进度：{idx}/{total} 成功 {success}")

            self.show_info("完成", f"批量导入完成：成功 {success}/{total}")
            self.load_videos()
        except Exception as e:
            self.show_error("错误", f"批量JAV导入失败: {e}")


    def on_manage_tags(self):
        """标签管理"""
        try:
            # 使用新的标签管理窗口
            tag_manager = TagManagerWindow(self)
            tag_manager.exec()
        except Exception as e:
            self.show_error("错误", f"标签管理失败: {e}")

    def on_manage_folders(self):
        """文件夹管理"""
        try:
            # 使用新的文件夹管理窗口
            folder_manager = FolderManagerWindow(self)
            folder_manager.exec()
        except Exception as e:
            self.show_error("错误", f"文件夹管理失败: {e}")

    def on_sync_stars_to_filename(self):
        """同步打分到文件"""
        try:
            if hasattr(self, 'original_sync_stars_to_filename'):
                self.original_sync_stars_to_filename()
            else:
                self.show_info("提示", "同步打分到文件功能正在集成中...")
        except Exception as e:
            self.show_error("错误", f"同步打分到文件失败: {e}")

    def on_batch_calculate_md5(self):
        """批量计算MD5"""
        try:
            if hasattr(self, 'original_batch_calculate_md5'):
                self.original_batch_calculate_md5()
            else:
                self.show_info("提示", "批量计算MD5功能正在集成中...")
        except Exception as e:
            self.show_error("错误", f"批量计算MD5失败: {e}")

    def on_smart_remove_duplicates(self):
        """智能去重"""
        try:
            if hasattr(self, 'original_smart_remove_duplicates'):
                self.original_smart_remove_duplicates()
            else:
                self.show_info("提示", "智能去重功能正在集成中...")
        except Exception as e:
            self.show_error("错误", f"智能去重失败: {e}")

    def on_file_move_manager(self):
        """文件移动管理"""
        try:
            if hasattr(self, 'original_file_move_manager'):
                self.original_file_move_manager()
            else:
                self.show_info("提示", "文件移动管理功能正在集成中...")
        except Exception as e:
            self.show_error("错误", f"文件移动管理失败: {e}")

    def refresh_data(self):
        """刷新数据"""
        self.load_data()

    def clear_filters(self):
        """清空筛选"""
        self.search_widget.title_search.clear()
        self.search_widget.tag_search.clear()
        self.search_widget.actor_search.clear()

        # 重置星级筛选
        buttons = self.search_widget.star_button_group.buttons()
        if buttons:
            buttons[0].setChecked(True)

        # 清除标签选择 - 标签筛选功能已移除
        # 不再需要清除标签选择，因为标签筛选已通过搜索框实现

        # 重置文件夹筛选
        folder_buttons = self.search_widget.folder_button_group.buttons()
        if folder_buttons:
            folder_buttons[0].setChecked(True)  # 选择"全部文件夹"

        self.load_videos()

    def show_about(self):
        """显示关于对话框"""
        about_text = """
        <h2>视频媒体库管理器</h2>
        <p><b>版本:</b> 2.0 (PySide6版本)</p>
        <p><b>功能特性:</b></p>
        <ul>
            <li>✓ 视频封面显示与生成</li>
            <li>✓ 快速星级编辑（右键菜单/双击/快捷键）</li>
            <li>✓ 跨平台视频播放</li>
            <li>✓ 智能搜索与筛选</li>
            <li>✓ 演员信息管理</li>
            <li>✓ JAVDB信息集成</li>
            <li>✓ GPU加速封面生成</li>
        </ul>
        <p><b>技术栈:</b> Python + PySide6 + SQLite + FFmpeg</p>
        <hr>
        <p><small>基于原Tkinter版本重构的现代化GUI应用</small></p>
        """

        QMessageBox.about(self, "关于", about_text)

    def show_shortcuts(self):
        """显示快捷键对话框"""
        shortcuts_text = """
        <h2>快捷键指南</h2>

        <h3>基础操作</h3>
        <table>
            <tr><td><b>Ctrl+R</b></td><td>刷新数据</td></tr>
            <tr><td><b>Ctrl+F</b></td><td>聚焦搜索框</td></tr>
        </table>

        <h3>视频操作</h3>
        <table>
            <tr><td><b>Space</b></td><td>播放选中的视频</td></tr>
            <tr><td><b>Enter</b></td><td>生成视频封面</td></tr>
        </table>

        <h3>星级设置</h3>
        <table>
            <tr><td><b>Ctrl+0</b></td><td>清除星级</td></tr>
            <tr><td><b>Ctrl+1</b></td><td>设置1星</td></tr>
            <tr><td><b>Ctrl+2</b></td><td>设置2星</td></tr>
            <tr><td><b>Ctrl+3</b></td><td>设置3星</td></tr>
            <tr><td><b>Ctrl+4</b></td><td>设置4星</td></tr>
            <tr><td><b>Ctrl+5</b></td><td>设置5星</td></tr>
        </table>

        <h3>鼠标操作</h3>
        <table>
            <tr><td><b>双击视频</b></td><td>播放视频</td></tr>
            <tr><td><b>双击星级列</b></td><td>快速设置星级</td></tr>
            <tr><td><b>右键菜单</b></td><td>显示操作选项</td></tr>
        </table>
        """

        dialog = QDialog(self)
        dialog.setWindowTitle("快捷键指南")
        dialog.setFixedSize(500, 600)
        dialog.setModal(True)

        layout = QVBoxLayout()

        # 创建文本显示区域
        text_edit = QTextEdit()
        text_edit.setHtml(shortcuts_text)
        text_edit.setReadOnly(True)
        layout.addWidget(text_edit)

        # 关闭按钮
        close_button = QPushButton("关闭")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)

        dialog.setLayout(layout)
        dialog.exec_()

    def play_video(self):
        """播放视频（跨平台）"""
        try:
            # 获取当前选中的视频
            selected_items = self.video_list.selectedItems()
            if not selected_items:
                self.show_warning("提示", "请先选择一个视频")
                return

            video_id = selected_items[0].data(0, Qt.UserRole)

            # 从数据库获取视频信息
            self.core.cursor.execute("SELECT file_path, source_folder, is_nas_online FROM videos WHERE id = ?", (video_id,))
            result = self.core.cursor.fetchone()
            if not result:
                self.show_error("错误", "找不到视频信息")
                return

            file_path, source_folder, is_nas_online = result

            # 检查视频是否在线
            if not self._is_video_online(video_id, source_folder, is_nas_online):
                self.show_warning("提示", "视频离线，无法播放")
                return

            # 检查文件是否存在
            if not os.path.exists(file_path):
                self.show_error("错误", "视频文件不存在")
                return

            # 跨平台播放
            import platform
            import subprocess

            system = platform.system()
            if system == "Darwin":  # macOS
                subprocess.run(["open", file_path])
            elif system == "Windows":
                os.startfile(file_path)
            elif system == "Linux":
                subprocess.run(["xdg-open", file_path])
            else:
                self.show_error("错误", f"不支持的操作系统: {system}")

        except Exception as e:
            self.show_error("错误", f"播放视频失败: {e}")

    def set_star_rating(self, rating):
        """设置星级评分"""
        if self.core.current_video:
            try:
                self.core.cursor.execute(
                    "UPDATE videos SET stars = ? WHERE id = ?",
                    (rating, self.core.current_video[0])
                )
                self.core.conn.commit()
                self.update_star_display(rating)
                self.status_bar.showMessage(f"已设置为 {rating} 星", 3000)
            except Exception as e:
                QMessageBox.critical(self, "错误", f"设置星级失败: {e}")

    def select_video_by_id(self, video_id):
        """根据视频ID选择并显示视频"""
        try:
            # 遍历所有项目找到对应的视频
            for i in range(self.video_list.topLevelItemCount()):
                item = self.video_list.topLevelItem(i)
                if item.data(0, Qt.UserRole) == video_id:
                    # 选中该项目
                    self.video_list.setCurrentItem(item)
                    # 滚动到该项目
                    self.video_list.scrollToItem(item)
                    # 加载详情
                    self.load_video_detail(video_id)
                    break
        except Exception as e:
            print(f"选择视频失败: {e}")

    def show_quick_star_dialog(self, video_id):
        """显示快速星级设置对话框"""
        try:
            # 获取当前星级
            self.core.cursor.execute("SELECT stars FROM videos WHERE id = ?", (video_id,))
            result = self.core.cursor.fetchone()
            current_stars = result[0] if result and result[0] else 0

            # 创建对话框
            dialog = QDialog(self)
            dialog.setWindowTitle("快速设置星级")
            dialog.setFixedSize(350, 200)
            dialog.setModal(True)

            layout = QVBoxLayout()

            # 说明标签
            info_label = QLabel("点击星星设置星级：")
            layout.addWidget(info_label)

            # 星级按钮组
            star_group = QButtonGroup()
            star_layout = QHBoxLayout()

            for i in range(6):
                star_text = "清除" if i == 0 else "★"
                radio = QRadioButton(star_text)
                if i == 0:
                    radio.setText("✕ 清除")
                else:
                    radio.setText("★" * i)

                star_group.addButton(radio, i)
                star_layout.addWidget(radio)

            # 设置当前星级
            buttons = star_group.buttons()
            if current_stars < len(buttons):
                buttons[current_stars].setChecked(True)

            layout.addLayout(star_layout)

            # 按钮组
            button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            button_box.accepted.connect(dialog.accept)
            button_box.rejected.connect(dialog.reject)
            layout.addWidget(button_box)

            dialog.setLayout(layout)

            if dialog.exec_() == QDialog.Accepted:
                new_stars = star_group.checkedId()
                self._set_video_star(video_id, new_stars)
                self.load_videos()  # 刷新列表显示

        except Exception as e:
            self.show_error("错误", f"快速设置星级失败: {e}")

    def show_actor_detail(self, actor_name):
        """显示演员详情窗口"""
        try:
            dialog = ActorDetailWindow(self, actor_name)
            dialog.exec_()
        except Exception as e:
            self.show_error("错误", f"打开演员详情失败: {e}")

class ActorDetailWindow(QDialog):
    """演员详情窗口"""

    def __init__(self, parent, actor_name):
        super().__init__(parent)
        self.parent_window = parent
        self.actor_name = actor_name
        self.core = parent.core

        # 默认头像图片路径
        self.default_avatar_path = '/Users/firewell/Library/CloudStorage/OneDrive-个人/bioinfo/media/covers/default.JPEG'

        # 获取演员信息
        self.actor_info = self.get_actor_info_by_name(actor_name)
        self.actor_movies = self.get_actor_movies_in_library(actor_name)

        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        """设置界面UI"""
        self.setWindowTitle(f"演员详情 - {self.actor_name}")
        self.setGeometry(200, 200, 900, 700)
        self.setModal(True)

        # 主布局
        main_layout = QVBoxLayout()

        # 创建演员信息区域
        self.create_actor_info_section(main_layout)

        # 创建分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        main_layout.addWidget(separator)

        # 创建影片列表区域
        self.create_movies_section(main_layout)

        # 创建底部按钮
        self.create_bottom_buttons(main_layout)

        self.setLayout(main_layout)

    def create_actor_info_section(self, parent):
        """创建演员信息区域"""
        info_frame = QGroupBox("演员信息")
        info_layout = QHBoxLayout()
        info_frame.setLayout(info_layout)
        parent.addWidget(info_frame)

        # 左侧头像区域
        avatar_frame = QFrame()
        avatar_layout = QVBoxLayout()
        avatar_frame.setLayout(avatar_layout)

        # 头像标签
        self.avatar_label = QLabel("头像")
        self.avatar_label.setFixedSize(150, 200)
        self.avatar_label.setStyleSheet("""
            QLabel {
                border: 2px solid #ddd;
                border-radius: 5px;
                background-color: #f9f9f9;
            }
        """)
        self.avatar_label.setAlignment(Qt.AlignCenter)
        avatar_layout.addWidget(self.avatar_label)

        # 头像状态标签
        self.avatar_status_label = QLabel("加载中...")
        self.avatar_status_label.setStyleSheet("color: #666; font-size: 12px;")
        self.avatar_status_label.setAlignment(Qt.AlignCenter)
        avatar_layout.addWidget(self.avatar_status_label)

        info_layout.addWidget(avatar_frame)

        # 右侧详细信息区域
        details_frame = QFrame()
        details_layout = QGridLayout()
        details_frame.setLayout(details_layout)

        # 动态创建信息标签
        self.info_labels = {}
        current_row = 0

        # 基本信息字段
        fields = [
            ("name", "姓名"),
            ("name_traditional", "繁体名"),
            ("name_common", "常用名"),
            ("aliases", "别名"),
            ("movie_count", "媒体库影片"),
            ("birth_date", "出生日期"),
            ("debut_date", "出道日期"),
            ("height", "身高"),
            ("measurements", "三围"),
            ("description", "简介")
        ]

        for field_key, field_label in fields:
            label = QLabel(f"{field_label}:")
            label.setStyleSheet("font-weight: bold;")
            details_layout.addWidget(label, current_row, 0)

            value_label = QLabel("")
            value_label.setWordWrap(True)
            self.info_labels[field_key] = value_label
            details_layout.addWidget(value_label, current_row, 1, 1, 2)
            current_row += 1

        info_layout.addWidget(details_frame)

    def create_movies_section(self, parent):
        """创建影片列表区域"""
        movies_group = QGroupBox(f"在媒体库中的影片 ({len(self.actor_movies)} 部)")
        movies_layout = QVBoxLayout()
        movies_group.setLayout(movies_layout)
        parent.addWidget(movies_group)

        # 创建表格
        self.movies_table = QTreeWidget()
        self.movies_table.setHeaderLabels(['标题', '番号', '发行日期', '文件名', '文件来源', '是否在线'])
        self.movies_table.setAlternatingRowColors(True)
        self.movies_table.setSortingEnabled(True)

        # 设置列宽
        header = self.movies_table.header()
        header.resizeSection(0, 220)  # 标题
        header.resizeSection(1, 100)  # 番号
        header.resizeSection(2, 80)   # 发行日期
        header.resizeSection(3, 220)  # 文件名
        header.resizeSection(4, 120)  # 文件来源
        header.resizeSection(5, 60)   # 是否在线

        # 连接双击事件
        self.movies_table.itemDoubleClicked.connect(self.on_movie_double_clicked)

        movies_layout.addWidget(self.movies_table)

    def create_bottom_buttons(self, parent):
        """创建底部按钮"""
        button_layout = QHBoxLayout()

        # 刷新按钮
        refresh_button = QPushButton("刷新信息")
        refresh_button.clicked.connect(self.refresh_actor_info)
        button_layout.addWidget(refresh_button)

        # 在JAVDB搜索按钮
        search_button = QPushButton("在JAVDB搜索")
        search_button.clicked.connect(self.search_on_javdb)
        button_layout.addWidget(search_button)

        # 关闭按钮
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)

        button_layout.addStretch()
        parent.addLayout(button_layout)

    def get_actor_info_by_name(self, actor_name):
        """根据演员姓名获取演员信息"""
        try:
            self.core.cursor.execute("SELECT * FROM actors WHERE name = ? OR name_traditional = ? OR name_common = ?", (actor_name, actor_name, actor_name))
            return self.core.cursor.fetchone()
        except Exception as e:
            print(f"获取演员信息失败: {e}")
            return None

    def get_actor_movies_in_library(self, actor_name):
        """获取演员在媒体库中的影片"""
        try:
            self.core.cursor.execute("""
                SELECT v.id, v.file_name, v.file_path, j.javdb_title, j.javdb_code, j.release_date, j.javdb_cover_url,
                       v.source_folder, v.is_nas_online
                FROM videos v
                JOIN video_actors va ON v.id = va.video_id
                JOIN actors a ON va.actor_id = a.id
                LEFT JOIN javdb_info j ON v.id = j.video_id
                WHERE a.name = ? OR a.name_traditional = ? OR a.name_common = ?
                ORDER BY j.release_date DESC, v.file_name
            """, (actor_name, actor_name, actor_name))
            return self.core.cursor.fetchall()
        except Exception as e:
            print(f"获取演员影片失败: {e}")
            return []

    def load_data(self):
        """加载数据到界面"""
        # 加载演员信息
        if self.actor_info:
            # 映射字段到显示值
            field_mapping = {
                'name': self.actor_info[1] or "未知",
                'name_traditional': self.actor_info[13] or "",
                'name_common': self.actor_info[14] or "",
                'aliases': self.actor_info[15] or "",
                'movie_count': f"{len(self.actor_movies)} 部",
                'birth_date': self.actor_info[10] or "",
                'debut_date': self.actor_info[11] or "",
                'height': self.actor_info[12] or "",
                'measurements': self.actor_info[13] or "",
                'description': self.actor_info[9] or ""
            }

            for field_key, value in field_mapping.items():
                if field_key in self.info_labels:
                    self.info_labels[field_key].setText(str(value))
        else:
            self.info_labels['name'].setText(f"未找到演员 '{self.actor_name}' 的详细信息")

        # 加载头像
        self.load_avatar()

        # 加载影片列表
        self.load_movies_list()

    def load_avatar(self):
        """加载演员头像"""
        try:
            # 1) 数据库头像优先
            if self.actor_info and self.actor_info[6] is not None:
                avatar_data = self.actor_info[6]
                if len(avatar_data) > 0:
                    pixmap = QPixmap()
                    if pixmap.loadFromData(avatar_data):
                        scaled_pixmap = pixmap.scaled(150, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        self.avatar_label.setPixmap(scaled_pixmap)
                        self.avatar_status_label.setText("数据库头像")
                        return

            # 2) 尝试本地头像文件
            if self.actor_info and self.actor_info[5]:  # local_avatar_path
                local_path = self.actor_info[5]
                if os.path.exists(local_path):
                    pixmap = QPixmap(local_path)
                    scaled_pixmap = pixmap.scaled(150, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.avatar_label.setPixmap(scaled_pixmap)
                    self.avatar_status_label.setText("本地头像")
                    return

            # 3) 尝试默认头像
            if os.path.exists(self.default_avatar_path):
                pixmap = QPixmap(self.default_avatar_path)
                scaled_pixmap = pixmap.scaled(150, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.avatar_label.setPixmap(scaled_pixmap)
                self.avatar_status_label.setText("默认头像")
                return

            # 4) 显示无头像状态
            self.avatar_label.setText("暂无头像")
            self.avatar_status_label.setText("无头像")

        except Exception as e:
            print(f"加载头像失败: {e}")
            self.avatar_label.setText("头像加载失败")
            self.avatar_status_label.setText("加载失败")

    def load_movies_list(self):
        """加载影片列表"""
        try:
            self.movies_table.clear()

            for movie in self.actor_movies:
                # 解包电影数据
                video_id, file_name, file_path, javdb_title, javdb_code, release_date, cover_url, source_folder, is_nas_online = movie

                # 判断在线状态
                is_online = self._is_video_online(video_id, source_folder, is_nas_online)
                online_status = "在线" if is_online else "离线"

                # 获取文件来源显示
                file_source = self._get_managed_source_display(source_folder, file_path)

                # 创建项目
                item = QTreeWidgetItem([
                    javdb_title or file_name or "",
                    javdb_code or "",
                    release_date or "",
                    file_name or "",
                    file_source or "",
                    online_status
                ])
                item.setData(0, Qt.UserRole, video_id)  # 存储视频ID

                self.movies_table.addTopLevelItem(item)

        except Exception as e:
            print(f"加载影片列表失败: {e}")

    def _is_video_online(self, video_id, source_folder, is_nas_online):
        """判断视频是否在线"""
        try:
            if source_folder:
                self.core.cursor.execute("""
                    SELECT folder_path, is_active
                    FROM folders
                    WHERE ? LIKE folder_path || '%'
                    ORDER BY LENGTH(folder_path) DESC
                    LIMIT 1
                """, (source_folder,))
                row = self.core.cursor.fetchone()
                if row:
                    folder_path, is_active = row
                    return bool(is_active) and os.path.exists(folder_path)
            return bool(is_nas_online) if is_nas_online is not None else False
        except Exception:
            return bool(is_nas_online) if is_nas_online is not None else False

    def _get_managed_source_display(self, source_folder, file_path):
        """获取管理文件夹来源显示"""
        try:
            if source_folder:
                self.core.cursor.execute("""
                    SELECT device_name, folder_path
                    FROM folders
                    WHERE ? LIKE folder_path || '%'
                    ORDER BY LENGTH(folder_path) DESC
                    LIMIT 1
                """, (source_folder,))
                row = self.core.cursor.fetchone()
                if row:
                    device_name, folder_path = row
                    if device_name:
                        return f"{device_name}@{os.path.basename(folder_path)}"
                    else:
                        return os.path.basename(folder_path)
            return source_folder or file_path or ""
        except Exception:
            return source_folder or file_path or ""

    def on_movie_double_clicked(self, item, column):
        """影片双击事件"""
        video_id = item.data(0, Qt.UserRole)
        if video_id:
            # 关闭演员详情窗口
            self.accept()
            # 在主窗口中选择并显示该视频
            self.parent_window.select_video_by_id(video_id)

    def refresh_actor_info(self):
        """刷新演员信息"""
        self.show_info("提示", "刷新演员信息功能正在集成中...")

    def search_on_javdb(self):
        """在JAVDB搜索演员"""
        self.show_info("提示", "JAVDB搜索功能正在集成中...")

    def show_info(self, title, message):
        """显示信息消息"""
        QMessageBox.information(self, title, message)

class TagManagerWindow(QDialog):
    """标签管理窗口"""

    def __init__(self, parent):
        super().__init__(parent)
        self.parent_window = parent
        self.core = parent.core

        self.setWindowTitle("标签管理")
        self.setGeometry(200, 200, 450, 350)
        self.setModal(True)

        self.setup_ui()
        self.load_tags()

    def setup_ui(self):
        """设置界面UI"""
        layout = QVBoxLayout()

        # 标签列表区域
        list_group = QGroupBox("标签列表")
        list_layout = QVBoxLayout()

        # 搜索框
        from PySide6.QtWidgets import QLineEdit
        self.tag_search = QLineEdit()
        self.tag_search.setPlaceholderText("搜索标签...")
        self.tag_search.textChanged.connect(self.filter_tags)
        list_layout.addWidget(self.tag_search)

        # 标签列表控件（带滚动条）
        self.tag_list = QListWidget()
        self.tag_list.setAlternatingRowColors(True)
        self.tag_list.setMaximumHeight(300)  # 限制最大高度
        list_layout.addWidget(self.tag_list)

        # 统计信息标签
        self.tag_count_label = QLabel("共 0 个标签")
        list_layout.addWidget(self.tag_count_label)

        list_group.setLayout(list_layout)
        layout.addWidget(list_group)

        # 按钮区域
        button_layout = QHBoxLayout()

        # 添加标签按钮
        self.add_button = QPushButton("添加标签")
        self.add_button.clicked.connect(self.add_tag)
        button_layout.addWidget(self.add_button)

        # 删除标签按钮
        self.delete_button = QPushButton("删除标签")
        self.delete_button.clicked.connect(self.delete_tag)
        button_layout.addWidget(self.delete_button)

        # 编辑标签按钮
        self.edit_button = QPushButton("编辑标签")
        self.edit_button.clicked.connect(self.edit_tag)
        button_layout.addWidget(self.edit_button)

        # 刷新按钮
        self.refresh_button = QPushButton("刷新")
        self.refresh_button.clicked.connect(self.load_tags)
        button_layout.addWidget(self.refresh_button)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        # 底部关闭按钮
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)

        self.setLayout(layout)

    def load_tags(self):
        """加载标签列表"""
        try:
            # 加载所有标签到内存
            self.core.cursor.execute("SELECT tag_name FROM tags ORDER BY tag_name")
            self.all_tags = [tag[0] for tag in self.core.cursor.fetchall()]

            # 更新统计信息
            self.tag_count_label.setText(f"共 {len(self.all_tags)} 个标签")

            # 应用当前搜索过滤
            self.filter_tags()

        except Exception as e:
            self.parent_window.show_error("错误", f"加载标签失败: {e}")

    def filter_tags(self):
        """根据搜索框内容过滤标签"""
        try:
            search_text = self.tag_search.text().strip().lower()

            # 清空当前列表
            self.tag_list.clear()

            # 过滤标签
            filtered_tags = []
            for tag in self.all_tags:
                if search_text == "" or search_text in tag.lower():
                    filtered_tags.append(tag)

            # 添加到列表（限制显示数量，避免界面过长）
            max_display = 100  # 最多显示100个标签
            display_tags = filtered_tags[:max_display]

            for tag in display_tags:
                item = QListWidgetItem(tag)
                self.tag_list.addItem(item)

            # 如果有更多标签，显示提示
            if len(filtered_tags) > max_display:
                remaining = len(filtered_tags) - max_display
                item = QListWidgetItem(f"... 还有 {remaining} 个标签")
                item.setFlags(item.flags() & ~Qt.ItemIsSelectable)  # 不可选择
                self.tag_list.addItem(item)

            # 更新统计信息
            if search_text:
                self.tag_count_label.setText(f"找到 {len(filtered_tags)} 个标签")
            else:
                self.tag_count_label.setText(f"共 {len(self.all_tags)} 个标签")

        except Exception as e:
            print(f"过滤标签失败: {e}")

    def add_tag(self):
        """添加标签"""
        from PySide6.QtWidgets import QInputDialog

        tag_name, ok = QInputDialog.getText(
            self, "添加标签", "请输入标签名称:"
        )

        if ok and tag_name.strip():
            tag_name = tag_name.strip()
            try:
                # 检查标签是否已存在
                self.core.cursor.execute("SELECT COUNT(*) FROM tags WHERE tag_name = ?", (tag_name,))
                if self.core.cursor.fetchone()[0] > 0:
                    QMessageBox.warning(self, "警告", f"标签 '{tag_name}' 已存在")
                    return

                # 添加标签
                self.core.cursor.execute("INSERT INTO tags (tag_name) VALUES (?)", (tag_name,))
                self.core.conn.commit()

                # 刷新列表
                self.load_tags()

                # 刷新主界面的标签筛选器
                self.parent_window.load_tags()

                QMessageBox.information(self, "成功", f"标签 '{tag_name}' 已添加")

            except Exception as e:
                self.parent_window.show_error("错误", f"添加标签失败: {e}")

    def delete_tag(self):
        """删除标签"""
        current_item = self.tag_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "提示", "请先选择要删除的标签")
            return

        tag_name = current_item.text()

        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除标签 '{tag_name}' 吗？\n\n注意：删除标签不会影响已有视频的标签字段。"
        )

        if reply == QMessageBox.Yes:
            try:
                self.core.cursor.execute("DELETE FROM tags WHERE tag_name = ?", (tag_name,))
                self.core.conn.commit()

                # 刷新列表
                self.load_tags()

                # 刷新主界面的标签筛选器
                self.parent_window.load_tags()

                QMessageBox.information(self, "成功", f"标签 '{tag_name}' 已删除")

            except Exception as e:
                self.parent_window.show_error("错误", f"删除标签失败: {e}")

    def edit_tag(self):
        """编辑标签"""
        current_item = self.tag_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "提示", "请先选择要编辑的标签")
            return

        old_tag_name = current_item.text()

        from PySide6.QtWidgets import QInputDialog

        new_tag_name, ok = QInputDialog.getText(
            self, "编辑标签", "修改标签名称:", text=old_tag_name
        )

        if ok and new_tag_name.strip() and new_tag_name != old_tag_name:
            new_tag_name = new_tag_name.strip()
            try:
                # 检查新标签名是否已存在
                self.core.cursor.execute("SELECT COUNT(*) FROM tags WHERE tag_name = ? AND tag_name != ?", (new_tag_name, old_tag_name))
                if self.core.cursor.fetchone()[0] > 0:
                    QMessageBox.warning(self, "警告", f"标签 '{new_tag_name}' 已存在")
                    return

                # 更新标签
                self.core.cursor.execute("UPDATE tags SET tag_name = ? WHERE tag_name = ?", (new_tag_name, old_tag_name))
                self.core.conn.commit()

                # 更新所有使用该标签的视频记录
                self.core.cursor.execute("UPDATE videos SET tags = REPLACE(tags, ',', ?) WHERE tags LIKE ?", (old_tag_name, f"%{old_tag_name}%"))
                self.core.conn.commit()

                # 刷新列表
                self.load_tags()

                # 刷新主界面的标签筛选器和视频列表
                self.parent_window.load_tags()
                self.parent_window.load_videos()

                QMessageBox.information(self, "成功", f"标签已从 '{old_tag}' 修改为 '{new_tag_name}'")

            except Exception as e:
                self.parent_window.show_error("错误", f"编辑标签失败: {e}")

class FolderManagerWindow(QDialog):
    """文件夹管理窗口"""

    def __init__(self, parent):
        super().__init__(parent)
        self.parent_window = parent
        self.core = parent.core

        self.setWindowTitle("文件夹管理")
        self.setGeometry(150, 150, 700, 500)
        self.setModal(True)

        self.setup_ui()
        self.load_folders()

    def setup_ui(self):
        """设置界面UI"""
        layout = QVBoxLayout()

        # 文件夹列表区域
        table_group = QGroupBox("管理文件夹列表")
        table_layout = QVBoxLayout()

        # 文件夹表格
        self.folder_table = QTableWidget()
        self.folder_table.setColumnCount(5)
        self.folder_table.setHorizontalHeaderLabels(['路径', '类型', '设备', '状态', '操作'])

        # 设置列宽
        header = self.folder_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)

        self.folder_table.setAlternatingRowColors(True)
        self.folder_table.setSelectionBehavior(QAbstractItemView.SelectRows)

        table_layout.addWidget(self.folder_table)
        table_group.setLayout(table_layout)
        layout.addWidget(table_group)

        # 按钮区域
        button_layout = QHBoxLayout()

        # 添加文件夹按钮
        add_button = QPushButton("添加文件夹")
        add_button.clicked.connect(self.add_folder)
        button_layout.addWidget(add_button)

        # 删除文件夹按钮
        delete_button = QPushButton("删除文件夹")
        delete_button.clicked.connect(self.delete_folder)
        button_layout.addWidget(delete_button)

        # 激活/停用按钮
        toggle_button = QPushButton("切换状态")
        toggle_button.clicked.connect(self.toggle_folder_status)
        button_layout.addWidget(toggle_button)

        # 刷新按钮
        refresh_button = QPushButton("刷新列表")
        refresh_button.clicked.connect(self.load_folders)
        button_layout.addWidget(refresh_button)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        # 底部关闭按钮
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)

        self.setLayout(layout)

    def load_folders(self):
        """加载文件夹列表"""
        try:
            self.folder_table.setRowCount(0)

            self.core.cursor.execute("""
                SELECT id, folder_path, folder_type, device_name, is_active, created_at
                FROM folders
                ORDER BY created_at DESC
            """)
            folders = self.core.cursor.fetchall()

            for row in folders:
                folder_id, folder_path, folder_type, device_name, is_active, created_at = row

                # 添加行
                row_position = self.folder_table.rowCount()
                self.folder_table.insertRow(row_position)

                # 路径
                self.folder_table.setItem(row_position, 0, QTableWidgetItem(folder_path or ""))

                # 类型
                folder_type_display = folder_type or "本地"
                self.folder_table.setItem(row_position, 1, QTableWidgetItem(folder_type_display))

                # 设备
                device_display = device_name or "未知"
                self.folder_table.setItem(row_position, 2, QTableWidgetItem(device_display))

                # 状态
                status_display = "已激活" if is_active else "已停用"
                status_color = "#4CAF50" if is_active else "#F44336"
                status_item = QTableWidgetItem(status_display)
                status_item.setBackground(QColor(status_color))
                self.folder_table.setItem(row_position, 3, status_item)

                # 操作
                actions_widget = QWidget()
                actions_layout = QHBoxLayout()

                # 编辑按钮
                edit_btn = QPushButton("编辑")
                edit_btn.clicked.connect(lambda _, row=row: self.edit_folder(row))
                edit_btn.setMaximumWidth(60)
                actions_layout.addWidget(edit_btn)

                # 删除按钮
                delete_btn = QPushButton("删除")
                delete_btn.clicked.connect(lambda _, row=row: self.delete_folder(row))
                delete_btn.setMaximumWidth(60)
                actions_layout.addWidget(delete_btn)

                actions_layout.setContentsMargins(0, 0, 0, 0)
                actions_widget.setLayout(actions_layout)
                self.folder_table.setCellWidget(row_position, 4, actions_widget)

            # 调整行高
            self.folder_table.resizeRowsToContents()

        except Exception as e:
            self.parent_window.show_error("错误", f"加载文件夹列表失败: {e}")

    def add_folder(self):
        """添加文件夹"""
        # 创建选择对话框
        choice_dialog = QDialog(self)
        choice_dialog.setWindowTitle("添加文件夹")
        choice_dialog.setGeometry(300, 200, 400, 300)
        choice_dialog.setModal(True)

        choice_layout = QVBoxLayout()
        choice_dialog.setLayout(choice_layout)

        # 说明标签
        info_label = QLabel("选择添加方式：")
        choice_layout.addWidget(info_label)

        # 浏览按钮
        browse_btn = QPushButton("浏览本地文件夹")
        browse_btn.clicked.connect(self.browse_local_folder)
        choice_layout.addWidget(browse_btn)

        # 手动输入按钮
        manual_btn = QPushButton("手动输入路径(支持网络路径)")
        manual_btn.clicked.connect(self.manual_input_path)
        choice_layout.addWidget(manual_btn)

        # 取消按钮
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(choice_dialog.reject)
        choice_layout.addWidget(cancel_btn)

        choice_layout.addStretch()
        choice_dialog.setLayout(choice_layout)

        choice_dialog.exec_()

    def browse_local_folder(self):
        """浏览本地文件夹"""
        folder_path = QFileDialog.getExistingDirectory(
            self, "选择要添加的文件夹", ""
        )
        if folder_path:
            self.add_folder_by_path(folder_path, "local")

    def manual_input_path(self):
        """手动输入路径"""
        from PySide6.QtWidgets import QInputDialog, QLineEdit

        path, ok = QInputDialog.getText(
            self, "手动输入路径",
            "请输入文件夹路径：\n支持本地路径和网络路径(如: smb://server/share)",
            text="smb://"
        )

        if ok and path.strip():
            self.add_folder_by_path(path.strip(), "network")

    def add_folder_by_path(self, folder_path, folder_type="local"):
        """通过路径添加文件夹"""
        try:
            # 检查路径是否已存在
            self.core.cursor.execute("SELECT COUNT(*) FROM folders WHERE folder_path = ?", (folder_path,))
            if self.core.cursor.fetchone()[0] > 0:
                QMessageBox.warning(self, "警告", f"文件夹 '{folder_path}' 已存在")
                return

            # 获取当前设备名称
            device_name = self.core.get_current_device_name()

            # 添加文件夹
            self.core.cursor.execute("""
                INSERT INTO folders (folder_path, folder_type, device_name, is_active)
                VALUES (?, ?, ?, 1)
            """, (folder_path, folder_type, device_name))
            self.core.conn.commit()

            # 刷新列表
            self.load_folders()

            QMessageBox.information(self, "成功", f"文件夹 '{folder_path}' 已添加")

        except Exception as e:
            self.parent_window.show_error("错误", f"添加文件夹失败: {e}")

    def edit_folder(self, row):
        """编辑文件夹"""
        folder_id = self.folder_table.item(row, 0).text()

        current_path = self.folder_table.item(row, 0).text()
        current_type = self.folder_table.item(row, 1).text()

        from PySide6.QtWidgets import QInputDialog

        new_path, ok = QInputDialog.getText(
            self, "编辑文件夹",
            "请输入新的文件夹路径:",
            text=current_path
        )

        if ok and new_path.strip():
            new_path = new_path.strip()
            try:
                # 更新路径
                self.core.cursor.execute(
                    "UPDATE folders SET folder_path = ? WHERE id = ?",
                    (new_path, folder_id)
                )
                self.core.conn.commit()

                # 如果类型是"local"且路径发生变化，更新设备名称
                if current_type == "local" and new_path != current_path:
                    device_name = self.core.get_current_device_name()
                    self.core.cursor.execute(
                        "UPDATE folders SET device_name = ? WHERE id = ?",
                        (device_name, folder_id)
                    )
                    self.core.conn.commit()

                # 刷新列表
                self.load_folders()

                QMessageBox.information(self, "成功", "文件夹信息已更新")

            except Exception as e:
                self.parent_window.show_error("错误", f"编辑文件夹失败: {e}")

    def delete_folder(self, row):
        """删除文件夹"""
        folder_path = self.folder_table.item(row, 0).text()

        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除文件夹 '{folder_path}' 吗？\n\n注意：删除文件夹不会删除实际文件夹，只是从管理列表中移除。"
        )

        if reply == QMessageBox.Yes:
            try:
                self.core.cursor.execute("DELETE FROM folders WHERE folder_path = ?", (folder_path,))
                self.core.conn.commit()

                # 刷新列表
                self.load_folders()

                QMessageBox.information(self, "成功", f"文件夹 '{folder_path}' 已从管理列表中移除")

            except Exception as e:
                self.parent_window.show_error("错误", f"删除文件夹失败: {e}")

    def toggle_folder_status(self):
        """切换文件夹状态"""
        for row in range(self.folder_table.rowCount()):
            folder_id = self.folder_table.item(row, 0).text()
            current_status = self.folder_table.item(row, 3).text()
            is_active = (current_status == "已激活")

            try:
                new_status = not is_active
                self.core.cursor.execute(
                    "UPDATE folders SET is_active = ? WHERE id = ?",
                    (1 if new_status else 0, folder_id)
                )
                self.core.conn.commit()

                # 刷新列表
                self.load_folders()

            except Exception as e:
                self.parent_window.show_error("错误", f"切换状态失败: {e}")

def main():
    """主函数"""
    # 初始化Qt日志系统
    init_qt_logging()

    app = QApplication(sys.argv)

    # 设置应用程序属性
    app.setApplicationName("媒体库管理器")
    app.setApplicationVersion("2.0 (PySide6)")

    print("正在启动PySide6媒体库管理器...")

    # 创建主窗口
    window = MainWindow()

    # 确保窗口显示在前台
    window.show()
    window.raise_()  # 将窗口提升到前台
    window.activateWindow()  # 激活窗口

    # 设置窗口焦点
    window.setFocus()

    # 确保窗口完全显示后再处理其他事件
    app.processEvents()

    print("媒体库管理器已启动")

    # 运行应用程序
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
