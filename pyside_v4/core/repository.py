# -*- coding: utf-8 -*-
"""
数据访问层 —— 封装所有 SQL 查询
"""

import time
import logging
from .database import Database

logger = logging.getLogger(__name__)


class VideoRepository:
    """视频数据访问"""

    def __init__(self, db: Database):
        self.db = db

    # ---------- 统计 ----------

    def total_count(self) -> int:
        return self.db.execute_count("SELECT COUNT(*) FROM videos")

    def favorites_count(self) -> int:
        return self.db.execute_count(
            "SELECT COUNT(*) FROM videos WHERE stars >= 4"
        )

    def recent_count(self, days: int = 30) -> int:
        return self.db.execute_count(
            "SELECT COUNT(*) FROM videos WHERE created_at >= date('now', ?)",
            (f"-{days} days",)
        )

    def no_tags_count(self) -> int:
        return self.db.execute_count(
            "SELECT COUNT(*) FROM videos WHERE tags IS NULL OR tags = '' OR tags = '<无标签>'"
        )

    def count_by_folder(self, folder_path: str) -> int:
        return self.db.execute_count(
            "SELECT COUNT(*) FROM videos WHERE file_path LIKE ?",
            (f"{folder_path}%",)
        )

    # ---------- 列表查询 ----------

    def get_videos(
        self,
        offset: int = 0,
        limit: int = 200,
        search: str = "",
        filters: dict = None,
        sort_by: str = "created_at",
        sort_order: str = "DESC",
    ) -> tuple:
        """
        分页查询视频列表
        返回 (rows, total_count, elapsed_ms)
        """
        t0 = time.time()
        filters = filters or {}

        where_clauses = []
        params = []

        # 搜索
        if search:
            where_clauses.append(
                "(v.title LIKE ? OR v.file_name LIKE ? OR v.tags LIKE ?)"
            )
            like = f"%{search}%"
            params.extend([like, like, like])

        # 筛选
        if filters.get("stars_min"):
            where_clauses.append("v.stars >= ?")
            params.append(filters["stars_min"])

        if filters.get("online_only"):
            where_clauses.append("v.is_nas_online = 1")

        if filters.get("has_tags"):
            where_clauses.append("v.tags IS NOT NULL AND v.tags != '' AND v.tags != '<无标签>'")

        if filters.get("no_tags"):
            where_clauses.append("(v.tags IS NULL OR v.tags = '' OR v.tags = '<无标签>')")

        if filters.get("folder"):
            where_clauses.append("v.file_path LIKE ?")
            params.append(f"{filters['folder']}%")

        if filters.get("tag"):
            where_clauses.append("v.tags LIKE ?")
            params.append(f"%{filters['tag']}%")

        if filters.get("recent_days"):
            where_clauses.append("v.file_created_time >= date('now', ?)")
            params.append(f"-{filters['recent_days']} days")

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        # 排序字段映射（使用有索引的字段）
        sort_map = {
            "title": "v.title",
            "file_size": "v.file_size",
            "stars": "v.stars",
            "created_at": "v.file_created_time",  # 使用有索引的字段
            "duration": "v.duration",
            "file_created_time": "v.file_created_time",
        }
        sort_col = sort_map.get(sort_by, "v.file_created_time")
        order = "ASC" if sort_order.upper() == "ASC" else "DESC"

        # COUNT
        count_sql = f"SELECT COUNT(*) FROM videos v WHERE {where_sql}"
        total = self.db.execute_count(count_sql, tuple(params))

        # DATA
        data_sql = f"""
            SELECT
                v.id, v.file_path, v.file_name, v.title,
                v.stars, v.tags, v.file_size, v.is_nas_online,
                v.duration, v.resolution, v.created_at,
                v.file_created_time, v.source_folder, v.md5_hash,
                j.javdb_code, j.score AS javdb_score,
                j.release_date, j.cover_url, j.local_cover_path,
                j.cover_image_data
            FROM videos v
            LEFT JOIN javdb_info j ON j.video_id = v.id
            WHERE {where_sql}
            ORDER BY {sort_col} {order}
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])
        rows = self.db.execute(data_sql, tuple(params))

        elapsed_ms = int((time.time() - t0) * 1000)

        # 转为 dict 列表
        result = []
        for row in rows:
            d = dict(row)
            d["_actors"] = self._get_actors(d["id"])
            d["_tags_list"] = self._parse_tags(d.get("tags", ""))
            result.append(d)

        return result, total, elapsed_ms

    def get_video_detail(self, video_id: int) -> dict:
        """获取视频详情"""
        sql = """
            SELECT
                v.id, v.file_path, v.file_name, v.title,
                v.stars, v.tags, v.file_size, v.is_nas_online,
                v.duration, v.resolution, v.created_at,
                v.file_created_time, v.source_folder, v.md5_hash,
                j.javdb_code, j.score AS javdb_score,
                j.release_date, j.cover_url, j.local_cover_path,
                j.cover_image_data, j.studio, j.series,
                j.magnet_links
            FROM videos v
            LEFT JOIN javdb_info j ON j.video_id = v.id
            WHERE v.id = ?
        """
        row = self.db.execute_one(sql, (video_id,))
        if row:
            row["_actors"] = self._get_actors(row["id"])
            row["_tags_list"] = self._parse_tags(row.get("tags", ""))
            row["_javdb_tags"] = self._get_javdb_tags(row["id"])
        return row

    def _get_actors(self, video_id: int) -> list:
        """获取视频关联的演员"""
        sql = """
            SELECT a.id, a.name, a.local_avatar_path, a.avatar_url
            FROM video_actors va
            JOIN actors a ON a.id = va.actor_id
            WHERE va.video_id = ?
        """
        rows = self.db.execute(sql, (video_id,))
        return [dict(r) for r in rows]

    def _get_javdb_tags(self, video_id: int) -> list:
        """获取 JAVDB 标签"""
        sql = """
            SELECT jt.tag_name
            FROM javdb_info_tags jit
            JOIN javdb_tags jt ON jt.id = jit.tag_id
            WHERE jit.javdb_info_id = (
                SELECT id FROM javdb_info WHERE video_id = ?
            )
        """
        rows = self.db.execute(sql, (video_id,))
        return [r["tag_name"] for r in rows]

    @staticmethod
    def _parse_tags(tags_str: str) -> list:
        """解析逗号分隔的标签字符串"""
        if not tags_str or tags_str == "<无标签>":
            return []
        return [t.strip() for t in tags_str.split(",") if t.strip()]

    # ---------- 更新操作 ----------

    def update_stars(self, video_id: int, stars: int) -> bool:
        """更新星级评分"""
        affected = self.db.execute_write(
            "UPDATE videos SET stars = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (stars, video_id)
        )
        return affected > 0

    def update_tags(self, video_id: int, tags: str) -> bool:
        """更新标签"""
        affected = self.db.execute_write(
            "UPDATE videos SET tags = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (tags, video_id)
        )
        return affected > 0


class ActorRepository:
    """演员数据访问"""

    def __init__(self, db: Database):
        self.db = db

    def get_actors(
        self,
        search: str = "",
        favorites_only: bool = False,
        sort_by: str = "name",
        offset: int = 0,
        limit: int = 100,
    ) -> tuple:
        """获取演员列表，返回 (rows, total, elapsed_ms)"""
        t0 = time.time()
        where = ["1=1"]
        params = []

        if search:
            where.append("(a.name LIKE ? OR a.name_en LIKE ? OR a.name_common LIKE ?)")
            like = f"%{search}%"
            params.extend([like, like, like])

        if favorites_only:
            where.append("a.is_favorite = 1")

        where_sql = " AND ".join(where)

        sort_map = {
            "name": "a.name",
            "movie_count": "a.movie_count",
            "created_at": "a.created_at",
        }
        sort_col = sort_map.get(sort_by, "a.name")

        count_sql = f"SELECT COUNT(*) FROM actors a WHERE {where_sql}"
        total = self.db.execute_count(count_sql, tuple(params))

        data_sql = f"""
            SELECT a.id, a.name, a.name_en, a.name_common, a.name_traditional,
                   a.aliases, a.local_avatar_path, a.avatar_url,
                   a.birth_date, a.height, a.measurements,
                   a.movie_count, a.is_favorite, a.description
            FROM actors a
            WHERE {where_sql}
            ORDER BY {sort_col}
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])
        rows = self.db.execute(data_sql, tuple(params))

        elapsed_ms = int((time.time() - t0) * 1000)
        return [dict(r) for r in rows], total, elapsed_ms

    def get_actor_detail(self, actor_id: int) -> dict:
        """获取演员详情"""
        sql = """
            SELECT a.id, a.name, a.name_en, a.name_common, a.name_traditional,
                   a.aliases, a.local_avatar_path, a.avatar_url,
                   a.birth_date, a.height, a.measurements, a.description,
                   a.movie_count, a.is_favorite
            FROM actors a WHERE a.id = ?
        """
        return self.db.execute_one(sql, (actor_id,))

    def get_actor_videos(self, actor_id: int, limit: int = 50) -> list:
        """获取演员参演的视频"""
        sql = """
            SELECT v.id, v.title, v.file_name, v.stars, v.tags,
                   v.file_size, v.is_nas_online, v.duration,
                   v.resolution, v.created_at,
                   j.javdb_code, j.score AS javdb_score,
                   j.local_cover_path, j.cover_image_data
            FROM video_actors va
            JOIN videos v ON v.id = va.video_id
            LEFT JOIN javdb_info j ON j.video_id = v.id
            WHERE va.actor_id = ?
            ORDER BY v.created_at DESC
            LIMIT ?
        """
        rows = self.db.execute(sql, (actor_id, limit))
        result = []
        for row in rows:
            d = dict(row)
            d["_tags_list"] = VideoRepository._parse_tags(d.get("tags", ""))
            result.append(d)
        return result

    def toggle_favorite(self, actor_id: int) -> bool:
        """切换演员收藏状态"""
        affected = self.db.execute_write(
            "UPDATE actors SET is_favorite = CASE WHEN is_favorite = 1 THEN 0 ELSE 1 END WHERE id = ?",
            (actor_id,)
        )
        return affected > 0


class TagRepository:
    """标签数据访问"""

    def __init__(self, db: Database):
        self.db = db

    def get_all_tags(self) -> list:
        """获取所有标签（从 tags 表）"""
        sql = "SELECT id, tag_name, tag_color, created_at FROM tags ORDER BY tag_name"
        return [dict(r) for r in self.db.execute(sql)]

    def get_javdb_tags(self) -> list:
        """获取 JAVDB 标签"""
        sql = """
            SELECT jt.id, jt.tag_name, jt.tag_type,
                   COUNT(jit.id) AS usage_count
            FROM javdb_tags jt
            LEFT JOIN javdb_info_tags jit ON jit.tag_id = jt.id
            GROUP BY jt.id
            ORDER BY usage_count DESC
        """
        return [dict(r) for r in self.db.execute(sql)]

    def get_video_tag_stats(self) -> list:
        """统计视频标签使用情况（从 videos.tags 字段解析）"""
        sql = "SELECT tags FROM videos WHERE tags IS NOT NULL AND tags != '' AND tags != '<无标签>'"
        rows = self.db.execute(sql)
        tag_counts = {}
        for row in rows:
            for tag in row["tags"].split(","):
                tag = tag.strip()
                if tag:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1

        return sorted(tag_counts.items(), key=lambda x: -x[1])

    def get_folders(self) -> list:
        """获取文件夹配置"""
        sql = "SELECT id, folder_path, folder_type, is_active, device_name FROM folders ORDER BY folder_path"
        return [dict(r) for r in self.db.execute(sql)]
