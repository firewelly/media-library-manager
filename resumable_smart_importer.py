#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
可断点续传的智能视频导入脚本
支持MD5缓存和任务状态跟踪，可在中断后从断点继续执行
增强版：集成智能媒体库更新功能
"""

import os
import sys
import json
import hashlib
import sqlite3
import argparse
import shutil
import cv2
import subprocess
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict

class ResumableSmartImporter:
    """可断点续传的智能视频导入器 - 增强版"""
    
    def __init__(self, db_path: str, cache_file: str = "import_cache.json"):
        self.db_path = db_path
        self.cache_file = cache_file
        self.cache_data = self.load_cache()
        self.video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.3gp', '.ts', '.mts', '.m2ts'}
        
        # 连接数据库
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        
        # 确保数据库表存在
        self.ensure_tables_exist()
        
    def ensure_tables_exist(self):
        """确保必要的数据库表存在"""
        try:
            # 检查videos表是否存在
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS videos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_name TEXT NOT NULL,
                    file_path TEXT NOT NULL UNIQUE,
                    file_size INTEGER,
                    duration INTEGER,
                    resolution TEXT,
                    stars INTEGER DEFAULT 0,
                    title TEXT,
                    description TEXT,
                    tags TEXT,
                    actors TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    md5_hash TEXT,
                    source_folder TEXT,
                    device_name TEXT
                )
            """)
            
            # 检查folders表是否存在
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS folders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    folder_path TEXT NOT NULL UNIQUE,
                    folder_name TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            self.conn.commit()
        except Exception as e:
            print(f"创建数据库表失败: {e}")

    def _resolve_filename_column(self) -> str:
        """确定videos表中用于保存文件名的列名（file_name 或 filename）。"""
        try:
            self.cursor.execute("PRAGMA table_info(videos)")
            cols = [row[1] for row in self.cursor.fetchall()]
            if "file_name" in cols:
                return "file_name"
            elif "filename" in cols:
                return "filename"
            else:
                # 如果都不存在，新增file_name列以保持与现有应用一致
                try:
                    self.cursor.execute("ALTER TABLE videos ADD COLUMN file_name TEXT")
                    self.conn.commit()
                    return "file_name"
                except Exception:
                    # 回退：新增filename列
                    self.cursor.execute("ALTER TABLE videos ADD COLUMN filename TEXT")
                    self.conn.commit()
                    return "filename"
        except Exception:
            # 保底返回常用列名
            return "file_name"
    
    def load_cache(self) -> Dict:
        """加载缓存数据"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"加载缓存文件失败: {e}")
                return self.create_empty_cache()
        return self.create_empty_cache()
    
    def create_empty_cache(self) -> Dict:
        """创建空缓存结构"""
        return {
            "version": "2.0",  # 升级版本号
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "task_config": {},
            "files": {},  # 文件处理状态和MD5缓存
            "md5_cache": {},  # 专门的MD5缓存
            "statistics": {
                "total_files": 0,
                "md5_calculated": 0,
                "imported": 0,
                "updated": 0,
                "skipped": 0,
                "failed": 0,
                "removed": 0
            }
        }
    
    def save_cache(self):
        """保存缓存数据"""
        try:
            self.cache_data["last_updated"] = datetime.now().isoformat()
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存缓存文件失败: {e}")
    
    def get_active_folders(self) -> List[str]:
        """获取所有活跃且在线的文件夹路径"""
        try:
            self.cursor.execute("SELECT folder_path FROM folders WHERE is_active = 1")
            all_folders = [row[0] for row in self.cursor.fetchall()]
            
            # 只返回在线（可访问）的文件夹
            online_folders = []
            for folder in all_folders:
                if os.path.exists(folder) and os.path.isdir(folder):
                    online_folders.append(folder)
                    print(f"✓ 在线文件夹: {folder}")
                else:
                    print(f"✗ 离线文件夹: {folder}")
            
            return online_folders
        except Exception as e:
            print(f"获取活跃文件夹失败: {e}")
            return []
    
    def collect_video_files(self, sources: List[str]) -> List[str]:
        """收集所有视频文件"""
        all_files = []
        
        for source in sources:
            try:
                # 首先检查路径是否存在
                if not os.path.exists(source):
                    print(f"警告: 路径不存在: {source}")
                    continue
                
                source_path = Path(source)
                if source_path.is_file():
                    if source_path.suffix.lower() in self.video_extensions:
                        all_files.append(str(source_path.absolute()))
                elif source_path.is_dir():
                    print(f"正在扫描文件夹: {source}")
                    try:
                        for file_path in source_path.rglob('*'):
                            try:
                                if file_path.is_file() and file_path.suffix.lower() in self.video_extensions:
                                    # 过滤小于2MB的文件
                                    if file_path.stat().st_size >= 2 * 1024 * 1024:
                                        all_files.append(str(file_path.absolute()))
                            except (OSError, PermissionError) as e:
                                # 跳过无法访问的文件
                                continue
                    except (OSError, PermissionError) as e:
                        print(f"警告: 无法访问文件夹 {source}: {e}")
                        continue
                else:
                    print(f"警告: 路径类型未知: {source}")
            except Exception as e:
                print(f"警告: 处理路径 {source} 时出错: {e}")
                continue
        
        return all_files
    
    def calculate_md5_with_cache(self, file_path: str) -> Optional[str]:
        """带缓存的MD5计算"""
        try:
            if not os.path.exists(file_path):
                return None
            
            # 获取文件信息
            stat = os.stat(file_path)
            file_size = stat.st_size
            mtime = stat.st_mtime
            
            # 检查缓存
            file_key = str(Path(file_path).absolute())
            if file_key in self.cache_data.get("md5_cache", {}):
                cached_info = self.cache_data["md5_cache"][file_key]
                # 验证缓存有效性（文件大小和修改时间）
                if (cached_info.get("file_size") == file_size and 
                    cached_info.get("mtime") == mtime and 
                    cached_info.get("md5_hash")):
                    return cached_info["md5_hash"]
            
            # 计算MD5
            print(f"计算MD5: {os.path.basename(file_path)}")
            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hash_md5.update(chunk)
            
            md5_hash = hash_md5.hexdigest()
            
            # 更新缓存
            if "md5_cache" not in self.cache_data:
                self.cache_data["md5_cache"] = {}
            
            self.cache_data["md5_cache"][file_key] = {
                "md5_hash": md5_hash,
                "file_size": file_size,
                "mtime": mtime,
                "calculated_at": datetime.now().isoformat()
            }
            
            return md5_hash
            
        except Exception as e:
            print(f"MD5计算失败 {file_path}: {e}")
            return None
    
    def load_md5_cache_from_db(self) -> Dict[str, str]:
        """从数据库加载已有的MD5映射"""
        md5_map = {}
        try:
            self.cursor.execute("SELECT file_path, md5_hash FROM videos WHERE md5_hash IS NOT NULL")
            for file_path, md5_hash in self.cursor.fetchall():
                md5_map[file_path] = md5_hash
        except Exception as e:
            print(f"加载数据库MD5缓存失败: {e}")
        return md5_map
    
    def check_duplicate_in_db(self, md5_hash: str, file_size: int) -> bool:
        """检查数据库中是否存在重复文件"""
        try:
            self.cursor.execute("""
                SELECT COUNT(*) FROM videos 
                WHERE md5_hash = ? AND file_size = ?
            """, (md5_hash, file_size))
            return self.cursor.fetchone()[0] > 0
        except Exception as e:
            print(f"检查重复文件失败: {e}")
            return False
    
    def find_file_by_md5(self, md5_hash: str) -> Optional[str]:
        """通过MD5查找数据库中的文件路径"""
        try:
            self.cursor.execute("SELECT file_path FROM videos WHERE md5_hash = ?", (md5_hash,))
            result = self.cursor.fetchone()
            return result[0] if result else None
        except Exception as e:
            print(f"通过MD5查找文件失败: {e}")
            return None
    
    def parse_stars_from_filename(self, filename: str) -> int:
        """从文件名解析星级"""
        return filename.count('!')
    
    def parse_title_from_filename(self, filename: str) -> str:
        """从文件名解析标题"""
        # 移除扩展名和星级标记
        title = Path(filename).stem
        title = re.sub(r'\d+星', '', title).strip()
        return title
    
    def get_video_info(self, file_path: str) -> Tuple[Optional[int], Optional[str]]:
        """获取视频信息（时长和分辨率）"""
        try:
            # 优先使用opencv
            cap = cv2.VideoCapture(file_path)
            if cap.isOpened():
                fps = cap.get(cv2.CAP_PROP_FPS)
                frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                cap.release()
                
                duration = int(frame_count / fps) if fps > 0 else None
                resolution = f"{width}x{height}" if width > 0 and height > 0 else None
                return duration, resolution
        except Exception:
            pass
        
        # 备用方案：使用ffprobe
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_format', '-show_streams', file_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                duration = None
                resolution = None
                
                if 'format' in data and 'duration' in data['format']:
                    duration = int(float(data['format']['duration']))
                
                for stream in data.get('streams', []):
                    if stream.get('codec_type') == 'video':
                        width = stream.get('width')
                        height = stream.get('height')
                        if width and height:
                            resolution = f"{width}x{height}"
                        break
                
                return duration, resolution
        except Exception:
            pass
        
        return None, None
    
    def can_play_video(self, file_path: str) -> bool:
        """检查视频文件是否可播放"""
        try:
            cap = cv2.VideoCapture(file_path)
            if cap.isOpened():
                ret, frame = cap.read()
                cap.release()
                return ret and frame is not None
        except Exception:
            pass
        return False
    
    def add_video_to_db(self, file_path: str, md5_hash: str, source_folder: str = None) -> bool:
        """添加视频到数据库"""
        try:
            filename = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            stars = self.parse_stars_from_filename(filename)
            title = self.parse_title_from_filename(filename)
            duration, resolution = self.get_video_info(file_path)
            created_time = datetime.fromtimestamp(os.path.getctime(file_path))
            
            fn_col = self._resolve_filename_column()
            self.cursor.execute(f"""
                INSERT INTO videos (
                    {fn_col}, file_path, file_size, duration, resolution,
                    stars, title, md5_hash, source_folder, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                filename, file_path, file_size, duration, resolution,
                stars, title, md5_hash, source_folder, created_time
            ))
            
            self.conn.commit()
            return True
            
        except Exception as e:
            print(f"添加视频到数据库失败: {e}")
            return False
    
    def update_video_path(self, old_path: str, new_path: str) -> bool:
        """更新视频文件路径"""
        try:
            fn_col = self._resolve_filename_column()
            self.cursor.execute(f"""
                UPDATE videos SET file_path = ?, {fn_col} = ?, updated_at = CURRENT_TIMESTAMP
                WHERE file_path = ?
            """, (new_path, os.path.basename(new_path), old_path))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"更新视频路径失败: {e}")
            return False
    
    def update_video_md5(self, file_path: str, md5_hash: str) -> bool:
        """更新视频MD5"""
        try:
            self.cursor.execute("""
                UPDATE videos SET md5_hash = ?, updated_at = CURRENT_TIMESTAMP
                WHERE file_path = ?
            """, (md5_hash, file_path))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"更新视频MD5失败: {e}")
            return False
    
    def remove_video_from_db(self, file_path: str) -> bool:
        """从数据库删除视频记录"""
        try:
            self.cursor.execute("DELETE FROM videos WHERE file_path = ?", (file_path,))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"删除视频记录失败: {e}")
            return False
    
    def batch_insert_videos(self, video_data: List[Tuple]) -> int:
        """批量插入视频记录"""
        try:
            fn_col = self._resolve_filename_column()
            self.cursor.executemany(f"""
                INSERT INTO videos (
                    {fn_col}, file_path, file_size, duration, resolution,
                    stars, title, md5_hash, source_folder, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, video_data)
            self.conn.commit()
            return len(video_data)
        except Exception as e:
            print(f"批量插入视频失败: {e}")
            return 0
    
    def comprehensive_media_update(self, folders: List[str] = None) -> Dict:
        """智能媒体库更新 - 核心功能"""
        print("开始智能媒体库更新...")
        
        # 使用指定文件夹或获取所有活跃文件夹
        if folders is None:
            folders = self.get_active_folders()
        
        if not folders:
            print("没有找到活跃的文件夹")
            return {"error": "没有活跃文件夹"}
        
        # 统计变量
        stats = {
            "scanned_files": 0,
            "new_files": 0,
            "updated_files": 0,
            "removed_files": 0,
            "md5_updated": 0
        }
        
        print(f"扫描文件夹: {folders}")
        
        # 第一阶段：扫描文件并建立映射
        print("\n=== 第一阶段：扫描文件 ===")
        all_files = self.collect_video_files(folders)
        stats["scanned_files"] = len(all_files)
        print(f"找到 {len(all_files)} 个视频文件")
        
        # 加载数据库中的MD5映射
        db_md5_map = self.load_md5_cache_from_db()
        
        # 分类文件：需要计算MD5 vs 已有MD5
        files_need_md5 = []
        files_with_md5 = []
        
        for file_path in all_files:
            if file_path in db_md5_map:
                files_with_md5.append((file_path, db_md5_map[file_path]))
            else:
                files_need_md5.append(file_path)
        
        print(f"需要计算MD5: {len(files_need_md5)} 个文件")
        print(f"已有MD5: {len(files_with_md5)} 个文件")
        
        # 计算MD5
        print("\n计算文件MD5...")
        for i, file_path in enumerate(files_need_md5, 1):
            print(f"[{i}/{len(files_need_md5)}] {os.path.basename(file_path)}")
            md5_hash = self.calculate_md5_with_cache(file_path)
            if md5_hash:
                files_with_md5.append((file_path, md5_hash))
        
        # 建立文件映射
        active_files_map = {}  # MD5 -> 文件信息
        md5_to_path = {}  # MD5 -> 路径
        filename_to_path = {}  # 文件名 -> 路径列表
        
        for file_path, md5_hash in files_with_md5:
            try:
                file_size = os.path.getsize(file_path)
                filename = os.path.basename(file_path)
                title = self.parse_title_from_filename(filename)
                stars = self.parse_stars_from_filename(filename)
                
                # 确定源文件夹
                source_folder = None
                for folder in folders:
                    if file_path.startswith(folder):
                        source_folder = folder
                        break
                
                active_files_map[md5_hash] = {
                    "file_path": file_path,
                    "file_size": file_size,
                    "filename": filename,
                    "title": title,
                    "stars": stars,
                    "source_folder": source_folder
                }
                
                md5_to_path[md5_hash] = file_path
                
                if filename not in filename_to_path:
                    filename_to_path[filename] = []
                filename_to_path[filename].append(file_path)
                
            except Exception as e:
                print(f"处理文件信息失败 {file_path}: {e}")
        
        print(f"建立文件映射: {len(active_files_map)} 个文件")
        
        # 第二阶段：检查数据库记录
        print("\n=== 第二阶段：检查数据库记录 ===")
        
        # 获取所有数据库记录
        fn_col = self._resolve_filename_column()
        self.cursor.execute(f"SELECT id, file_path, md5_hash, {fn_col} FROM videos")
        db_records = self.cursor.fetchall()
        
        records_to_update_md5 = []
        records_to_update_path = []
        records_to_delete = []
        
        for record_id, db_path, db_md5, db_filename in db_records:
            # 检查文件是否仍然存在
            if os.path.exists(db_path):
                # 文件存在，检查是否在配置范围内
                in_scope = any(db_path.startswith(folder) for folder in folders)
                if not in_scope:
                    continue  # 不在配置范围内，跳过
                
                # 检查MD5是否需要更新
                if not db_md5:
                    # 数据库中没有MD5，尝试计算
                    md5_hash = self.calculate_md5_with_cache(db_path)
                    if md5_hash:
                        records_to_update_md5.append((md5_hash, record_id))
                        stats["md5_updated"] += 1
            else:
                # 文件不存在，尝试通过MD5查找迁移
                if db_md5 and db_md5 in md5_to_path:
                    new_path = md5_to_path[db_md5]
                    print(f"检测到文件迁移: {db_filename} -> {new_path}")
                    records_to_update_path.append((new_path, os.path.basename(new_path), record_id))
                    stats["updated_files"] += 1
                    # 从待添加列表中移除
                    if db_md5 in active_files_map:
                        del active_files_map[db_md5]
                elif db_filename in filename_to_path:
                    # 通过文件名查找潜在路径
                    potential_paths = filename_to_path[db_filename]
                    if len(potential_paths) == 1:
                        new_path = potential_paths[0]
                        print(f"通过文件名检测到迁移: {db_filename} -> {new_path}")
                        records_to_update_path.append((new_path, db_filename, record_id))
                        stats["updated_files"] += 1
                        # 从待添加列表中移除（通过路径查找MD5）
                        for md5, info in list(active_files_map.items()):
                            if info["file_path"] == new_path:
                                del active_files_map[md5]
                                break
                else:
                    # 无法找到文件，标记删除
                    records_to_delete.append(record_id)
                    stats["removed_files"] += 1
        
        # 执行批量数据库操作
        print(f"\n执行数据库更新...")
        print(f"更新MD5: {len(records_to_update_md5)} 条记录")
        print(f"更新路径: {len(records_to_update_path)} 条记录")
        print(f"删除记录: {len(records_to_delete)} 条记录")
        
        # 批量更新MD5
        if records_to_update_md5:
            self.cursor.executemany("""
                UPDATE videos SET md5_hash = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            """, records_to_update_md5)
        
        # 批量更新路径
        if records_to_update_path:
            fn_col = self._resolve_filename_column()
            # 记录格式为 (new_path, db_filename_or_basename, id)
            self.cursor.executemany(f"""
                UPDATE videos SET file_path = ?, {fn_col} = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            """, records_to_update_path)
        
        # 批量删除记录
        if records_to_delete:
            self.cursor.executemany("DELETE FROM videos WHERE id = ?", 
                                   [(record_id,) for record_id in records_to_delete])
        
        self.conn.commit()
        
        # 第三阶段：添加新文件
        print(f"\n=== 第三阶段：添加新文件 ===")
        print(f"待添加文件: {len(active_files_map)} 个")
        
        # 准备批量插入数据
        insert_data = []
        batch_size = 50
        
        for md5_hash, file_info in active_files_map.items():
            try:
                file_path = file_info["file_path"]
                duration, resolution = self.get_video_info(file_path)
                created_time = datetime.fromtimestamp(os.path.getctime(file_path))
                
                insert_data.append((
                    file_info["filename"],
                    file_path,
                    file_info["file_size"],
                    duration,
                    resolution,
                    file_info["stars"],
                    file_info["title"],
                    md5_hash,
                    file_info["source_folder"],
                    created_time
                ))
                
                # 批量插入
                if len(insert_data) >= batch_size:
                    inserted = self.batch_insert_videos(insert_data)
                    stats["new_files"] += inserted
                    print(f"批量插入了 {inserted} 个新文件")
                    insert_data = []
                    
            except Exception as e:
                print(f"准备文件失败: {file_info['filename']} - {str(e)}")
        
        # 处理剩余文件
        if insert_data:
            inserted = self.batch_insert_videos(insert_data)
            stats["new_files"] += inserted
            print(f"批量插入了最后 {inserted} 个新文件")
        
        # 更新统计信息
        self.cache_data["statistics"].update(stats)
        self.save_cache()
        
        print(f"\n智能媒体库更新完成！")
        print(f"总扫描文件: {stats['scanned_files']}")
        print(f"新增文件: {stats['new_files']}")
        print(f"路径更新: {stats['updated_files']}")
        print(f"删除无效: {stats['removed_files']}")
        print(f"MD5更新: {stats['md5_updated']}")
        
        return stats

def main():
    parser = argparse.ArgumentParser(description="可断点续传的智能视频导入工具")
    parser.add_argument("sources", nargs="*", help="要导入的文件或文件夹路径")
    parser.add_argument("--db", required=True, help="数据库文件路径")
    parser.add_argument("--cache", default="import_cache.json", help="缓存文件路径")
    parser.add_argument("--target", help="目标文件夹（可选）")
    parser.add_argument("--delete-duplicates", action="store_true", help="删除重复文件")
    parser.add_argument("--delete-invalid", action="store_true", help="删除无效文件")
    parser.add_argument("--status", action="store_true", help="显示当前状态")
    parser.add_argument("--cleanup", action="store_true", help="清理缓存文件")
    parser.add_argument("--smart-update", action="store_true", help="智能媒体库更新模式")
    
    args = parser.parse_args()
    
    # 检查数据库文件
    if not os.path.exists(args.db):
        print(f"错误: 数据库文件不存在: {args.db}")
        sys.exit(1)
    
    # 创建导入器
    importer = ResumableSmartImporter(args.db, args.cache)
    
    # 处理命令
    if args.cleanup:
        importer.cleanup_cache()
        return
    
    if args.status:
        importer.print_status()
        return
    
    # 智能媒体库更新模式
    if args.smart_update:
        print("=== 智能媒体库更新模式 ===")
        
        # 获取活跃文件夹
        folders = importer.get_active_folders()
        if not folders:
            print("错误: 没有找到活跃的文件夹配置")
            sys.exit(1)
        
        print(f"将更新以下文件夹: {folders}")
        
        # 执行智能媒体库更新
        stats = importer.comprehensive_media_update(folders)
        
        # 显示统计结果
        print(f"\n=== 智能媒体库更新完成 ===")
        print(f"扫描文件总数: {stats['scanned_files']}")
        print(f"新增文件: {stats['new_files']}")
        print(f"路径更新: {stats['updated_files']}")
        print(f"删除无效: {stats['removed_files']}")
        print(f"MD5更新: {stats['md5_updated']}")
        
        return
    
    # 检查是否提供了sources参数
    if not args.sources:
        print("错误: 请提供要导入的文件或文件夹路径，或使用 --smart-update 进行智能媒体库更新")
        parser.print_help()
        sys.exit(1)
    
    # 收集文件
    print("正在收集视频文件...")
    all_files = importer.collect_video_files(args.sources)
    
    if not all_files:
        print("没有找到视频文件")
        return
    
    print(f"找到 {len(all_files)} 个视频文件")
    
    # 处理文件
    results = importer.process_files(
        all_files,
        target_folder=args.target,
        delete_duplicates=args.delete_duplicates,
        delete_invalid=args.delete_invalid
    )
    
    # 显示结果
    print(f"\n=== 处理完成 ===")
    print(f"总计处理: {results['processed']}")
    print(f"成功导入: {results['imported']}")
    print(f"跳过重复: {results['skipped_duplicate']}")
    print(f"跳过无效: {results['skipped_invalid']}")
    print(f"处理失败: {results['failed']}")
    
    importer.print_status()


if __name__ == "__main__":
    main()