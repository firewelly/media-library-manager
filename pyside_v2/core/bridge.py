# -*- coding: utf-8 -*-
"""
后端桥接 - 从 media_library_pyside.py 原样移入 MediaLibraryCore (179-1509行)
与 GenericWorker (1511-1547行)。

MediaLibraryCore 是纯后端 facade：
    - 持有共享 SQLite conn/cursor（check_same_thread=False，多线程共用）
    - 持有 db_manager / batch_manager / maintenance_manager
    - 持有 column_config（列布局）
    - 封装 ffmpeg/GPU/MD5/扫描/导入/缩略图/标签/演员/去重等非GUI逻辑

gui_adapter.setup_full_integration(qt_window) 会注入共享的 conn/cursor，
把 Tkinter 版 media_library.py 的 ~140 个方法重新绑定到 qt_window。
因此本类是与后端对接的唯一入口，**一行不动原有逻辑**。
"""

# .env 加载（与 v1 顶部一致，确保 utils 导入前环境变量就位）
import os as _os
try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(_os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))), '.env'))
except ImportError:
    _env_path = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))), '.env')
    if _os.path.exists(_env_path):
        try:
            with open(_env_path, 'r', encoding='utf-8') as _f:
                for _line in _f:
                    _s = _line.strip()
                    if not _s or _s.startswith('#') or '=' not in _s:
                        continue
                    _k, _v = _s.split('=', 1)
                    _k = _k.strip()
                    _v = _v.strip().strip('"').strip("'")
                    if _k and _v and (_k not in _os.environ):
                        _os.environ[_k] = _v
        except Exception:
            pass

import os
import json
import platform
import sqlite3
import hashlib
import subprocess
from datetime import datetime

from PySide6.QtCore import QThread, Signal

# 复用现有工具层（不改动）
from utils import javsp_migration, javsp_copy
from utils.batch_ops import BatchOperationManager
from utils.maintenance import MaintenanceManager
from utils.database import DatabaseManager
from utils.file_utils import FileUtils
from utils.runtime import ensure_file_in_runtime, runtime_path


class MediaLibraryCore:
    """媒体库核心功能类，复用原有的非GUI逻辑（原样移入）"""

    def __init__(self):
        # 配置文件路径
        self.config_path = ensure_file_in_runtime('gui_config.json')

        # 默认列配置
        self.default_columns = {
            'title': {'width': 400, 'position': 0, 'text': '标题'},
            'actors': {'width': 150, 'position': 1, 'text': '演员'},
            'stars': {'width': 75, 'position': 2, 'text': '星级'},
            'tags': {'width': 120, 'position': 3, 'text': '标签'},
            'size': {'width': 80, 'position': 4, 'text': '大小'},
            'status': {'width': 60, 'position': 5, 'text': '状态'},
            'device': {'width': 120, 'position': 6, 'text': '设备'},
            'duration': {'width': 120, 'position': 7, 'text': '时长'},
            'resolution': {'width': 150, 'position': 8, 'text': '分辨率'},
            'file_created_time': {'width': 120, 'position': 9, 'text': '创建时间'},
            'top_folder': {'width': 120, 'position': 10, 'text': '顶层文件夹'},
            'full_path': {'width': 200, 'position': 11, 'text': '完整路径'},
            'year': {'width': 60, 'position': 12, 'text': '年份'},
            'javdb_code': {'width': 100, 'position': 13, 'text': '番号'},
            'javdb_title': {'width': 300, 'position': 14, 'text': 'JAVDB标题'},
            'release_date': {'width': 100, 'position': 15, 'text': '发行日期'},
            'javdb_rating': {'width': 80, 'position': 16, 'text': 'JAVDB评分'},
            'javdb_tags': {'width': 200, 'position': 17, 'text': 'JAVDB标签'}
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
        """连接现有SQLite数据库，并执行兼容性迁移"""
        self.db_path = runtime_path('media_library.db')
        db_exists = os.path.exists(self.db_path)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()

        # 初始化新的管理器
        self.db_manager = DatabaseManager(self.db_path)
        self.batch_manager = BatchOperationManager(self.db_manager)
        self.maintenance_manager = MaintenanceManager(self.db_manager)

        if db_exists:
            self.migrate_database()
            self.conn.commit()
            print("已连接到现有数据库并完成兼容性迁移检查")
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

            self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='actors'")
            if self.cursor.fetchone():
                self.cursor.execute("PRAGMA table_info(actors)")
                actor_columns = [column[1] for column in self.cursor.fetchall()]

                if 'is_favorite' not in actor_columns:
                    self.cursor.execute('ALTER TABLE actors ADD COLUMN is_favorite INTEGER DEFAULT 0')
                    print("添加字段: is_favorite")

                self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_actors_is_favorite ON actors(is_favorite)')

            # ---- v2 性能索引：列表排序/分页/详情子查询所需 ----
            # 注：建索引不改表结构(schema)，只是性能优化；media_library.create_database_indexes
            # 已建部分，这里补齐 v2 高频查询路径缺失的索引。
            perf_indexes = [
                # 列表默认排序字段
                ('idx_videos_file_created_time', 'videos', 'file_created_time'),
                # 详情按 video_id 子查询演员/标签
                ('idx_video_actors_video_id', 'video_actors', 'video_id'),
                ('idx_javdb_info_video_id', 'javdb_info', 'video_id'),
                # "仅在线"过滤（COUNT/分页用）
                ('idx_videos_is_nas_online', 'videos', 'is_nas_online'),
            ]
            # 演员库浏览：按真实作品数排序需要按 actor_id 统计 video_actors
            try:
                self.cursor.execute(
                    'CREATE INDEX IF NOT EXISTS idx_video_actors_actor_id ON video_actors(actor_id)'
                )
            except Exception as e:
                print(f"创建索引 idx_video_actors_actor_id 跳过: {e}")
            # 复合索引：is_nas_online + file_created_time DESC
            # 关键性能优化：列表默认查询 "WHERE is_nas_online=1 ORDER BY file_created_time DESC LIMIT n"
            # 单列索引下要 12s（全表扫+排序），复合索引降到 0.008s（1500x）。
            # CREATE INDEX 不支持在表达式里写 DESC 的通用语法，用普通复合索引即可
            # （SQLite 会反向扫描满足 DESC）。
            try:
                self.cursor.execute(
                    'CREATE INDEX IF NOT EXISTS idx_v_online_created '
                    'ON videos(is_nas_online, file_created_time)'
                )
            except Exception as e:
                print(f"创建复合索引跳过: {e}")
            for idx_name, tbl, col in perf_indexes:
                try:
                    self.cursor.execute(
                        f'CREATE INDEX IF NOT EXISTS {idx_name} ON {tbl}({col})'
                    )
                except Exception as e:
                    print(f"创建索引 {idx_name} 跳过: {e}")

        except Exception as e:
            print(f"数据库迁移失败: {str(e)}")

    def set_actor_favorite(self, actor_id, is_favorite):
        """设置演员收藏状态"""
        try:
            self.cursor.execute("""
                UPDATE actors
                SET is_favorite = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (1 if is_favorite else 0, actor_id))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"设置演员收藏状态失败: {e}")
            return False

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
                self.gpu_type = "NVIDIA (CUDA)"
            else:
                self.gpu_acceleration = False
                self.gpu_type = None
        except:
            self.gpu_acceleration = False
            self.gpu_type = None

    def get_ffmpeg_command(self):
        """获取可用的FFmpeg命令路径，优先使用homebrew版本"""
        import platform
        # macOS下优先使用homebrew版本的ffmpeg
        if platform.system() == 'Darwin':
            # 优先检查homebrew路径
            homebrew_ffmpeg = '/opt/homebrew/bin/ffmpeg'
            if os.path.exists(homebrew_ffmpeg):
                try:
                    subprocess.run([homebrew_ffmpeg, "-version"], capture_output=True, check=True)
                    return homebrew_ffmpeg
                except (subprocess.CalledProcessError, FileNotFoundError):
                    pass

        # 首先尝试相对路径（用户通过homebrew安装的情况）
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
            return "ffmpeg"
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        # 如果相对路径失败，尝试常见的绝对路径
        possible_paths = [
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
        """检测可用的GPU加速选项，返回详细的GPU信息"""
        ffmpeg_cmd = self.get_ffmpeg_command()
        if not ffmpeg_cmd:
            return {"available": False, "hwaccel": None, "decoder": None, "encoder": None, "gpu_type": None}

        result = {
            "available": False,
            "hwaccel": None,
            "decoder": None,
            "encoder": None,
            "gpu_type": None
        }

        try:
            # 检查FFmpeg支持的硬件加速器
            hwaccels_result = subprocess.run([ffmpeg_cmd, "-hwaccels"], capture_output=True, text=True, timeout=5)
            if hwaccels_result.returncode != 0:
                return result

            hwaccels = hwaccels_result.stdout.lower()
            system = platform.system()

            # 检测支持的硬件加速器并选择最佳选项
            if system == 'Darwin':
                # macOS: VideoToolbox是原生硬件加速
                if 'videotoolbox' in hwaccels:
                    result.update({
                        "available": True,
                        "hwaccel": "videotoolbox",
                        "decoder": "h264_videotoolbox",
                        "encoder": "h264_videotoolbox",
                        "gpu_type": "Apple Silicon / Intel"
                    })
                elif 'opencl' in hwaccels:
                    result.update({
                        "available": True,
                        "hwaccel": "opencl",
                        "decoder": None,
                        "encoder": None,
                        "gpu_type": "OpenCL"
                    })

            elif system == 'Windows':
                # Windows: 按优先级检测硬件加速器
                # 对于AMD集成显卡，优先选择D3D11VA

                # 1. D3D11VA (DirectX 11 - 包括AMD GPU，推荐用于集成显卡)
                if 'd3d11va' in hwaccels:
                    result.update({
                        "available": True,
                        "hwaccel": "d3d11va",
                        "decoder": "h264_dxva2",
                        "encoder": "h264_qsv",  # Intel编码器备用
                        "gpu_type": "AMD / DirectX 11"
                    })
                # 2. Intel QSV (Intel集成显卡)
                elif 'qsv' in hwaccels:
                    result.update({
                        "available": True,
                        "hwaccel": "qsv",
                        "decoder": "h264_qsv",
                        "encoder": "h264_qsv",
                        "gpu_type": "Intel"
                    })
                # 3. DXVA2 (DirectX 9 - 旧版Windows)
                elif 'dxva2' in hwaccels:
                    result.update({
                        "available": True,
                        "hwaccel": "dxva2",
                        "decoder": "h264_dxva2",
                        "encoder": None,
                        "gpu_type": "DirectX 9"
                    })
                # 4. NVIDIA CUDA (仅当有实际NVIDIA GPU时验证)
                elif 'cuda' in hwaccels:
                    # 验证CUDA是否实际可用
                    try:
                        test_cmd = [ffmpeg_cmd, "-hwaccel", "cuda", "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=1", "-f", "null", "-"]
                        test_result = subprocess.run(test_cmd, capture_output=True, timeout=5)
                        if test_result.returncode == 0:
                            result.update({
                                "available": True,
                                "hwaccel": "cuda",
                                "decoder": "h264_cuvid",
                                "encoder": "h264_nvenc",
                                "gpu_type": "NVIDIA"
                            })
                    except:
                        pass

            elif system == 'Linux':
                # Linux: 按优先级检测硬件加速器

                # 1. VA-API (Video Acceleration API - 适用于AMD/Intel GPU)
                if 'vaapi' in hwaccels:
                    result.update({
                        "available": True,
                        "hwaccel": "vaapi",
                        "decoder": "h264_vaapi",
                        "encoder": "h264_vaapi",
                        "gpu_type": "AMD / Intel (VA-API)"
                    })
                # 2. Intel QSV
                elif 'qsv' in hwaccels:
                    result.update({
                        "available": True,
                        "hwaccel": "qsv",
                        "decoder": "h264_qsv",
                        "encoder": "h264_qsv",
                        "gpu_type": "Intel"
                    })
                # 3. NVIDIA CUDA (验证实际可用性)
                elif 'cuda' in hwaccels:
                    try:
                        test_cmd = [ffmpeg_cmd, "-hwaccel", "cuda", "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=1", "-f", "null", "-"]
                        test_result = subprocess.run(test_cmd, capture_output=True, timeout=5)
                        if test_result.returncode == 0:
                            result.update({
                                "available": True,
                                "hwaccel": "cuda",
                                "decoder": "h264_cuvid",
                                "encoder": "h264_nvenc",
                                "gpu_type": "NVIDIA"
                            })
                    except:
                        pass
                # 4. VDPAU (NVIDIA旧驱动)
                elif 'vdpau' in hwaccels:
                    result.update({
                        "available": True,
                        "hwaccel": "vdpau",
                        "decoder": "h264_vdpau",
                        "encoder": None,
                        "gpu_type": "NVIDIA (VDPAU)"
                    })
                # 5. OpenCL (通用跨平台)
                elif 'opencl' in hwaccels:
                    result.update({
                        "available": True,
                        "hwaccel": "opencl",
                        "decoder": None,
                        "encoder": None,
                        "gpu_type": "OpenCL"
                    })

        except Exception as e:
            print(f"检测GPU加速失败: {e}")

        return result

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
        """确保数据库连接有效，如果无效则重新连接。

        注：只重建 conn/cursor，不调 init_database（避免重建 db_manager 引发连锁）。
        """
        if not self.check_connection():
            print("数据库连接已关闭，重新连接...")
            try:
                import sqlite3
                from utils.runtime import runtime_path
                db_path = runtime_path('media_library.db')
                self.conn = sqlite3.connect(db_path, check_same_thread=False)
                self.cursor = self.conn.cursor()
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
        """获取视频信息（时长和分辨率），优先使用ffprobe以获得更好性能"""
        try:
            if not os.path.exists(file_path):
                return None, None

            # 优先使用ffprobe，因为它更快，不需要完全解码视频
            ffprobe_cmd = self.get_ffprobe_command()
            if ffprobe_cmd is not None:
                try:
                    # 使用硬件加速检测
                    gpu_info = self.detect_gpu_acceleration()

                    # 构建ffprobe命令，如果支持硬件加速则添加相关参数
                    duration_cmd = [
                        ffprobe_cmd, "-v", "quiet"
                    ]

                    # 如果支持硬件解码，添加硬件加速参数
                    if gpu_info["available"] and gpu_info["hwaccel"]:
                        duration_cmd.extend(["-hwaccel", gpu_info["hwaccel"]])
                        if gpu_info["hwaccel"] == "vaapi":
                            # VAAPI需要指定设备
                            dri_path = "/dev/dri/renderD128"
                            if os.path.exists(dri_path):
                                duration_cmd.extend(["-hwaccel_device", dri_path])

                    duration_cmd.extend([
                        "-show_entries", "format=duration",
                        "-of", "csv=p=0", file_path
                    ])

                    duration_result = subprocess.run(duration_cmd, capture_output=True, text=True, timeout=10)
                    duration = None
                    if duration_result.returncode == 0 and duration_result.stdout.strip():
                        try:
                            duration = int(float(duration_result.stdout.strip()))
                        except ValueError:
                            pass

                    # 获取分辨率
                    resolution_cmd = [
                        ffprobe_cmd, "-v", "quiet"
                    ]

                    # 如果支持硬件解码，添加硬件加速参数
                    if gpu_info["available"] and gpu_info["hwaccel"]:
                        resolution_cmd.extend(["-hwaccel", gpu_info["hwaccel"]])
                        if gpu_info["hwaccel"] == "vaapi":
                            dri_path = "/dev/dri/renderD128"
                            if os.path.exists(dri_path):
                                resolution_cmd.extend(["-hwaccel_device", dri_path])

                    resolution_cmd.extend([
                        "-select_streams", "v:0",
                        "-show_entries", "stream=width,height", "-of", "csv=p=0", file_path
                    ])

                    resolution_result = subprocess.run(resolution_cmd, capture_output=True, text=True, timeout=10)
                    resolution = None
                    if resolution_result.returncode == 0 and resolution_result.stdout.strip():
                        try:
                            width, height = resolution_result.stdout.strip().split(',')
                            resolution = f"{width}x{height}"
                        except ValueError:
                            pass

                    # 如果ffprobe成功获取信息，直接返回
                    if duration is not None or resolution is not None:
                        return duration, resolution

                except subprocess.TimeoutExpired:
                    print(f"ffprobe超时: {file_path}")
                except Exception as e:
                    print(f"使用ffprobe获取视频信息失败: {str(e)}")

            # 如果ffprobe不可用或失败，尝试使用opencv-python
            try:
                import cv2

                # 尝试使用GPU加速的OpenCV（如果可用）
                cap = cv2.VideoCapture(file_path)

                # 检查OpenCV是否支持CUDA
                try:
                    if cv2.cuda.getCudaEnabledDeviceCount() > 0:
                        # 尝试使用CUDA解码器
                        cap.set(cv2.CAP_PROP_CUDA_DEVICE, 0)
                except AttributeError:
                    pass

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
                print("opencv-python未安装")
            except Exception as e:
                print(f"使用opencv获取视频信息失败: {str(e)}")

            return None, None

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
        """获取优化的FFmpeg命令（包含GPU加速）

        注：v1 中此方法定义了两次，运行时后定义的覆盖前者，此处保留生效版本。
        """
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

    def move_file(self, video_id, old_file_path, target_folder):
        """移动文件到指定文件夹"""
        import shutil

        # 构建新文件路径
        file_name = os.path.basename(old_file_path)
        new_file_path = os.path.join(target_folder, file_name)

        # 检查目标文件是否已存在
        if os.path.exists(new_file_path):
             # 抛出异常，由UI层处理
             raise FileExistsError(f"目标位置已存在同名文件: {new_file_path}")

        # 移动文件
        success, final_path, error_msg = FileUtils.move_file_smart(old_file_path, new_file_path)
        if not success:
            raise OSError(error_msg)

        # 更新数据库记录
        self.cursor.execute(
            "UPDATE videos SET file_path = ?, source_folder = ? WHERE id = ?",
            (final_path, target_folder, video_id)
        )
        self.conn.commit()
        return new_file_path

    def get_online_folders(self):
        """获取在线文件夹列表"""
        self.cursor.execute("SELECT folder_path FROM folders WHERE is_active = 1")
        folders = [row[0] for row in self.cursor.fetchall()]

        online_folders = []
        for folder in folders:
            if os.path.exists(folder):
                online_folders.append(folder)

        return online_folders

    def process_single_filename(self, filename):
        """处理单个文件名，基于cfn4.py的逻辑"""
        import re

        # 获取文件名和后缀
        filename_no_ext, ext = os.path.splitext(filename)

        # 去除开头和结尾的句号
        filename_no_ext = filename_no_ext.strip('.')

        # 将文件名转换为大写
        filename_upper = filename_no_ext.upper()

        # 将后缀转换为小写
        ext_lower = ext.lower()

        # 构建新的文件名
        new_filename = filename_upper + ext_lower

        # 去掉空格
        if " " in new_filename:
            new_filename = new_filename.replace(" ", "")

        # 去掉常见垃圾字符
        garbage_patterns = [
            "CHINESEHOMEMADEVIDEO", "_CHINESE_HOMEMADE_VIDEO",
            "HHD800.COM@", "WOXAV.COM@",
            r"\[.*?\]", r"\(.*?\)", r"\{.*?\}",  # 去掉括号内容
            r"【.*?】",  # 去掉中文括号内容
        ]

        for pattern in garbage_patterns:
            if pattern.startswith("r"):
                # 处理正则转义
                p = pattern[1:] if pattern.startswith("r") else pattern
                new_filename = re.sub(p, "", new_filename)
            else:
                new_filename = new_filename.replace(pattern, "")

        # 去掉多余的下划线和连字符
        new_filename = re.sub(r"_+", "_", new_filename)
        new_filename = re.sub(r"-+", "-", new_filename)

        return new_filename

    def handle_filename_conflict(self, file_path):
        """处理文件名冲突"""
        base, ext = os.path.splitext(file_path)
        counter = 1
        new_path = f"{base}_{counter}{ext}"
        while os.path.exists(new_path):
            counter += 1
            new_path = f"{base}_{counter}{ext}"
        return new_path

    def clean_filename_for_video(self, video_id):
        """为单个视频清理文件名"""
        try:
            # 获取视频信息
            self.cursor.execute("SELECT file_path, title FROM videos WHERE id = ?", (video_id,))
            result = self.cursor.fetchone()
            if not result:
                return False, "未找到视频记录"

            old_file_path, old_title = result
            if not os.path.exists(old_file_path):
                return False, f"文件不存在: {old_file_path}"

            # 获取文件目录和原始文件名
            file_dir = os.path.dirname(old_file_path)
            old_filename = os.path.basename(old_file_path)

            # 应用清理逻辑
            new_filename = self.process_single_filename(old_filename)

            # 如果文件名没有变化
            if new_filename == old_filename:
                return True, "文件名无需清理"

            # 构建新的完整路径
            new_file_path = os.path.join(file_dir, new_filename)

            # 处理文件名冲突
            if os.path.exists(new_file_path):
                new_file_path = self.handle_filename_conflict(new_file_path)
                new_filename = os.path.basename(new_file_path)

            # 重命名文件
            os.rename(old_file_path, new_file_path)

            # 更新标题 (如果标题为空，则不更新)
            new_title = old_title
            if old_title:
                cleaned_title_with_ext = self.process_single_filename(old_title + ".tmp")
                new_title = os.path.splitext(cleaned_title_with_ext)[0]

            # 更新数据库
            self.cursor.execute("UPDATE videos SET file_path = ?, title = ? WHERE id = ?", (new_file_path, new_title, video_id))
            self.conn.commit()

            return True, f"重命名成功: {new_filename}"

        except Exception as e:
            return False, f"清理失败: {str(e)}"

    def auto_tag_video(self, video_path, use_retry=False):
        """自动为视频生成标签

        Args:
            video_path: 视频文件路径
            use_retry: 是否启用重试模式（首次失败后用30帧随机采样重试，再失败标记<无标签>）
        """
        try:
            from video_analyzer import VideoContentAnalyzer
            analyzer = VideoContentAnalyzer(db_path=self.db_path)

            if not os.path.exists(video_path):
                return False, "文件不存在"

            if use_retry:
                result = analyzer.analyze_video_content_with_retry(video_path)
            else:
                result = analyzer.analyze_video_content(video_path, min_frames=100, max_interval=10, max_frames=300)

            if 'error' in result and not result.get('no_tag'):
                return False, result['error']

            self.cursor.execute("SELECT id, tags FROM videos WHERE file_path = ?", (video_path,))
            res = self.cursor.fetchone()
            if not res:
                return False, "数据库记录未找到"

            video_id, existing_tags = res

            if result.get('no_tag'):
                self.cursor.execute("UPDATE videos SET tags = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", ('<无标签>', video_id))
                self.conn.commit()
                return True, "标记为<无标签>"

            tags = result.get('generated_tags', [])
            if not tags:
                return True, "未生成标签"

            existing_set = set([t.strip() for t in (existing_tags or "").split(",") if t.strip()])
            new_set = set(tags)
            all_tags = existing_set.union(new_set)

            final_tags = ", ".join(sorted(all_tags))

            self.cursor.execute("UPDATE videos SET tags = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (final_tags, video_id))
            self.conn.commit()

            retry_mark = " (30帧重试成功)" if result.get('retry_used') else ""
            return True, f"已添加标签: {', '.join(tags)}{retry_mark}"

        except ImportError:
            return False, "未找到 video_analyzer 模块"
        except Exception as e:
            return False, str(e)

    def migrate_javsp_file(self, video_id, old_file_path, target_library_path, progress_callback=None):
        """迁移JavSP文件到媒体库"""
        return javsp_migration.migrate_single(self.cursor, self.conn, old_file_path, video_id, target_library_path, progress_callback=progress_callback)

    def copy_javsp_file(self, video_id, old_file_path, target_library_path, progress_callback=None):
        """复制JavSP文件到媒体库"""
        return javsp_copy.copy_single(self.cursor, self.conn, old_file_path, video_id, target_library_path, progress_callback=progress_callback)

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
            if platform.system() == "Windows":
                conditions.append("REPLACE(v.source_folder, CHAR(92), '/') LIKE REPLACE(?, CHAR(92), '/') || '%'")
                params.append(folder_path)
            else:
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


class GenericWorker(QThread):
    """通用的后台工作线程（原样移入）。

    注：Phase 4 会迁移到 workers/base_worker.py 并统一为 BaseWorker + QThreadPool。
    此处临时保留以兼容 Phase 0 阶段的调用。
    """

    progress_signal = Signal(str, int, dict)  # message, progress, data
    finished_signal = Signal(dict)  # result
    error_signal = Signal(str)  # error message

    def __init__(self, task_func, **kwargs):
        super().__init__()
        self.task_func = task_func
        self.kwargs = kwargs
        self._cancelled = False

    def run(self):
        try:
            # 进度回调
            def progress_callback(message, progress=0, data=None):
                if self._cancelled:
                    return
                self.progress_signal.emit(message, progress, data or {})

            # 取消检查回调
            def cancel_check():
                return self._cancelled

            # 执行任务
            result = self.task_func(progress_callback=progress_callback, cancel_check=cancel_check, **self.kwargs)

            if not self._cancelled:
                self.finished_signal.emit(result or {})

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.error_signal.emit(str(e))

    def cancel(self):
        self._cancelled = True
