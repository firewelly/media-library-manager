#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库管理模块
从media_library.py提取的数据库操作功能
"""

import sqlite3
import os
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from .logger import get_logger

logger = get_logger("Database")

class DatabaseManager:
    """数据库管理器，封装所有数据库操作"""

    def __init__(self, db_path: str = "media_library.db"):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self.connect()
        self.init_database()

    def connect(self) -> None:
        """连接数据库"""
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.execute("PRAGMA foreign_keys = ON")  # 启用外键约束
            self.cursor = self.conn.cursor()
            logger.info(f"数据库连接成功: {self.db_path}")
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            raise

    def close(self) -> None:
        """关闭数据库连接"""
        try:
            if self.cursor:
                self.cursor.close()
            if self.conn:
                self.conn.close()
            logger.info("数据库连接已关闭")
        except Exception as e:
            logger.error(f"关闭数据库连接失败: {e}")

    def init_database(self) -> None:
        """初始化数据库表结构（适配现有数据库）"""
        try:
            # 检查并创建actors表（如果不存在）
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS actors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    avatar_path TEXT,
                    info_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 检查并创建video_actors关联表（如果不存在）
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS video_actors (
                    video_id INTEGER,
                    actor_id INTEGER,
                    FOREIGN KEY (video_id) REFERENCES videos (id) ON DELETE CASCADE,
                    FOREIGN KEY (actor_id) REFERENCES actors (id) ON DELETE CASCADE,
                    PRIMARY KEY (video_id, actor_id)
                )
            ''')

            # 检查videos表是否存在必要列，如果不存在则添加（不破坏现有结构）
            # 这里我们只创建索引，不修改表结构以保持兼容性

            # 创建索引（忽略已存在的错误）
            indexes_to_create = [
                'CREATE INDEX IF NOT EXISTS idx_videos_file_path ON videos(file_path)',
                'CREATE INDEX IF NOT EXISTS idx_videos_md5_hash ON videos(md5_hash)',
                'CREATE INDEX IF NOT EXISTS idx_videos_file_hash ON videos(file_hash)',
                'CREATE INDEX IF NOT EXISTS idx_videos_title ON videos(title)',
                'CREATE INDEX IF NOT EXISTS idx_videos_tags ON videos(tags)',
                'CREATE INDEX IF NOT EXISTS idx_videos_year ON videos(year)'
            ]

            for index_sql in indexes_to_create:
                try:
                    self.cursor.execute(index_sql)
                except sqlite3.OperationalError as e:
                    if "no such column" in str(e):
                        logger.warning(f"跳过不存在的列的索引: {e}")
                    else:
                        logger.warning(f"创建索引警告: {e}")

            self.conn.commit()
            logger.info("数据库初始化完成")

        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            raise

    def execute_query(self, query: str, params: Tuple = ()) -> List[Tuple]:
        """执行查询语句"""
        try:
            self.cursor.execute(query, params)
            return self.cursor.fetchall()
        except Exception as e:
            logger.error(f"查询执行失败: {query}, 参数: {params}, 错误: {e}")
            raise

    def execute_update(self, query: str, params: Tuple = ()) -> int:
        """执行更新语句"""
        try:
            self.cursor.execute(query, params)
            self.conn.commit()
            return self.cursor.rowcount
        except Exception as e:
            logger.error(f"更新执行失败: {query}, 参数: {params}, 错误: {e}")
            self.conn.rollback()
            raise

    def execute_many(self, query: str, params_list: List[Tuple]) -> int:
        """批量执行语句"""
        try:
            self.cursor.executemany(query, params_list)
            self.conn.commit()
            return self.cursor.rowcount
        except Exception as e:
            logger.error(f"批量执行失败: {query}, 错误: {e}")
            self.conn.rollback()
            raise

    def get_videos(self, limit: Optional[int] = None, offset: int = 0,
                   where_clause: str = "", params: Tuple = (),
                   order_by: str = "created_at DESC") -> List[Dict]:
        """获取视频列表（适配现有数据库结构）"""
        try:
            # 先获取现有的列结构
            self.cursor.execute("PRAGMA table_info(videos)")
            columns_info = self.cursor.fetchall()
            existing_columns = [col[1] for col in columns_info]

            # 构建查询，只选择存在的列
            # 使用COALESCE来为不存在的列提供默认值
            safe_columns = []
            column_mappings = {
                'id': 'id',
                'file_name': 'file_name',
                'file_path': 'file_path',
                'file_size': 'file_size',
                'title': 'title',
                'actors': 'COALESCE(actors, \'\') as actors',
                'stars': 'COALESCE(stars, 0) as stars',
                'tags': 'COALESCE(tags, \'\') as tags',
                'duration': 'COALESCE(duration, \'\') as duration',
                'resolution': 'COALESCE(resolution, \'\') as resolution',
                'year': 'COALESCE(year, NULL) as year',
                'is_nas_online': 'COALESCE(is_nas_online, 1) as is_nas_online',
                'source_folder': 'COALESCE(source_folder, \'\') as source_folder',
                'file_created_time': 'file_created_time',
                'created_at': 'created_at',
                'md5_hash': 'COALESCE(md5_hash, \'\') as md5_hash',
                'file_hash': 'COALESCE(file_hash, \'\') as file_hash'
            }

            for col_name in existing_columns:
                if col_name in column_mappings:
                    safe_columns.append(column_mappings[col_name])

            query = f"SELECT {', '.join(safe_columns)} FROM videos"

            if where_clause:
                query += f" WHERE {where_clause}"

            query += f" ORDER BY {order_by}"

            if limit:
                query += f" LIMIT {limit} OFFSET {offset}"

            self.cursor.execute(query, params)
            rows = self.cursor.fetchall()

            # 转换为字典列表
            columns = [description[0] for description in self.cursor.description]
            videos = []
            for row in rows:
                video = dict(zip(columns, row))
                videos.append(video)

            return videos

        except Exception as e:
            logger.error(f"获取视频列表失败: {e}")
            return []

    def get_video_count(self, where_clause: str = "", params: Tuple = ()) -> int:
        """获取视频总数"""
        try:
            query = "SELECT COUNT(*) FROM videos"
            if where_clause:
                query += f" WHERE {where_clause}"

            self.cursor.execute(query, params)
            result = self.cursor.fetchone()
            return result[0] if result else 0

        except Exception as e:
            logger.error(f"获取视频总数失败: {e}")
            return 0

    def insert_video(self, video_data: Dict[str, Any]) -> int:
        """插入视频记录"""
        try:
            # 构建字段列表和值列表
            fields = list(video_data.keys())
            placeholders = ["?" for _ in fields]
            values = list(video_data.values())

            query = f"""
                INSERT INTO videos ({', '.join(fields)})
                VALUES ({', '.join(placeholders)})
            """

            self.cursor.execute(query, values)
            self.conn.commit()
            return self.cursor.lastrowid

        except Exception as e:
            logger.error(f"插入视频记录失败: {e}")
            raise

    def update_video(self, video_id: int, video_data: Dict[str, Any]) -> int:
        """更新视频记录"""
        try:
            # 构建SET子句
            set_clauses = []
            values = []

            for field, value in video_data.items():
                set_clauses.append(f"{field} = ?")
                values.append(value)

            values.append(video_id)  # WHERE条件的参数

            query = f"""
                UPDATE videos
                SET {', '.join(set_clauses)}, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """

            self.cursor.execute(query, values)
            self.conn.commit()
            return self.cursor.rowcount

        except Exception as e:
            logger.error(f"更新视频记录失败: {e}")
            raise

    def delete_video(self, video_id: int) -> int:
        """删除视频记录"""
        try:
            query = "DELETE FROM videos WHERE id = ?"
            self.cursor.execute(query, (video_id,))
            self.conn.commit()
            return self.cursor.rowcount

        except Exception as e:
            logger.error(f"删除视频记录失败: {e}")
            raise

    def find_duplicates(self) -> List[Dict]:
        """查找重复的视频记录"""
        try:
            # 根据MD5哈希查找重复
            query = """
                SELECT md5_hash, COUNT(*) as count
                FROM videos
                WHERE md5_hash IS NOT NULL AND md5_hash != ''
                GROUP BY md5_hash
                HAVING COUNT(*) > 1
            """

            self.cursor.execute(query)
            md5_duplicates = self.cursor.fetchall()

            # 根据文件哈希查找重复
            query = """
                SELECT file_hash, COUNT(*) as count
                FROM videos
                WHERE file_hash IS NOT NULL AND file_hash != ''
                GROUP BY file_hash
                HAVING COUNT(*) > 1
            """

            self.cursor.execute(query)
            hash_duplicates = self.cursor.fetchall()

            # 合并结果
            duplicates = []

            for md5_hash, count in md5_duplicates:
                query = "SELECT * FROM videos WHERE md5_hash = ?"
                self.cursor.execute(query, (md5_hash,))
                videos = [dict(zip([col[0] for col in self.cursor.description], row))
                         for row in self.cursor.fetchall()]
                duplicates.append({
                    'type': 'md5',
                    'hash': md5_hash,
                    'count': count,
                    'videos': videos
                })

            for file_hash, count in hash_duplicates:
                query = "SELECT * FROM videos WHERE file_hash = ?"
                self.cursor.execute(query, (file_hash,))
                videos = [dict(zip([col[0] for col in self.cursor.description], row))
                         for row in self.cursor.fetchall()]
                duplicates.append({
                    'type': 'file_hash',
                    'hash': file_hash,
                    'count': count,
                    'videos': videos
                })

            return duplicates

        except Exception as e:
            logger.error(f"查找重复记录失败: {e}")
            return []

    def search_videos(self, search_term: str, search_fields: List[str] = None) -> List[Dict]:
        """搜索视频"""
        try:
            if not search_fields:
                search_fields = ['title', 'file_name', 'actors', 'tags', 'javdb_code']

            # 构建WHERE子句
            conditions = []
            params = []

            for field in search_fields:
                conditions.append(f"{field} LIKE ?")
                params.append(f"%{search_term}%")

            where_clause = " OR ".join(conditions)

            return self.get_videos(where_clause=where_clause, params=tuple(params))

        except Exception as e:
            logger.error(f"搜索视频失败: {e}")
            return []

    def get_statistics(self) -> Dict[str, Any]:
        """获取数据库统计信息"""
        try:
            stats = {}

            # 总视频数
            stats['total_videos'] = self.get_video_count()

            # 总文件大小
            query = "SELECT SUM(file_size) FROM videos WHERE file_size IS NOT NULL"
            self.cursor.execute(query)
            result = self.cursor.fetchone()
            stats['total_size'] = result[0] if result and result[0] else 0

            # 按年份统计
            query = """
                SELECT year, COUNT(*) as count
                FROM videos
                WHERE year IS NOT NULL
                GROUP BY year
                ORDER BY year DESC
            """
            self.cursor.execute(query)
            stats['by_year'] = dict(self.cursor.fetchall())

            # 按星级统计
            query = """
                SELECT stars, COUNT(*) as count
                FROM videos
                WHERE stars IS NOT NULL
                GROUP BY stars
                ORDER BY stars DESC
            """
            self.cursor.execute(query)
            stats['by_stars'] = dict(self.cursor.fetchall())

            # 在线/离线统计
            query = """
                SELECT is_nas_online, COUNT(*) as count
                FROM videos
                GROUP BY is_nas_online
            """
            self.cursor.execute(query)
            stats['online_status'] = dict(self.cursor.fetchall())

            return stats

        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()