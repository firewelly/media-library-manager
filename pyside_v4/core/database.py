# -*- coding: utf-8 -*-
"""
数据库连接管理
复用现有 media_library.db，支持读写操作
"""

import os
import sys
import sqlite3
import logging

logger = logging.getLogger(__name__)


def _find_db_path() -> str:
    """定位 media_library.db 路径"""
    # 优先：脚本所在目录
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(sys.argv[0]))

    # pyside_v4 在根目录下，db 也在根目录
    candidates = [
        os.path.join(base, 'media_library.db'),
        os.path.join(os.path.dirname(base), 'media_library.db'),
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p

    # 回退：当前工作目录
    cwd = os.path.join(os.getcwd(), 'media_library.db')
    if os.path.isfile(cwd):
        return cwd

    return candidates[0]  # 返回第一个候选路径（可能不存在）


class Database:
    """数据库连接管理器（读写）"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or _find_db_path()
        self.conn = None
        self._connect()

    def _connect(self):
        """建立连接"""
        if not os.path.isfile(self.db_path):
            logger.warning(f"数据库文件不存在: {self.db_path}")
            self.conn = None
            return

        try:
            self.conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=10,
            )
            self.conn.row_factory = sqlite3.Row
            # 性能优化
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA temp_store=MEMORY")
            self.conn.execute("PRAGMA cache_size=-64000")  # 64MB 缓存
            logger.info(f"已连接数据库: {self.db_path}")
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            self.conn = None

    @property
    def is_connected(self) -> bool:
        return self.conn is not None

    def execute(self, sql: str, params: tuple = ()) -> list:
        """执行查询，返回结果列表"""
        if not self.conn:
            return []
        try:
            cursor = self.conn.execute(sql, params)
            return cursor.fetchall()
        except Exception as e:
            logger.error(f"SQL 执行失败: {e}\nSQL: {sql}")
            return []

    def execute_one(self, sql: str, params: tuple = ()) -> dict:
        """执行查询，返回单行结果"""
        rows = self.execute(sql, params)
        if rows:
            return dict(rows[0])
        return {}

    def execute_count(self, sql: str, params: tuple = ()) -> int:
        """执行 COUNT 查询"""
        rows = self.execute(sql, params)
        if rows and rows[0]:
            return rows[0][0] or 0
        return 0

    def execute_write(self, sql: str, params: tuple = ()) -> int:
        """执行写操作（INSERT/UPDATE/DELETE），返回受影响行数"""
        if not self.conn:
            return 0
        try:
            cursor = self.conn.execute(sql, params)
            self.conn.commit()
            return cursor.rowcount
        except Exception as e:
            logger.error(f"SQL 写操作失败: {e}\nSQL: {sql}")
            self.conn.rollback()
            return 0

    def commit(self):
        """提交事务"""
        if self.conn:
            self.conn.commit()

    def rollback(self):
        """回滚事务"""
        if self.conn:
            self.conn.rollback()

    def close(self):
        """关闭连接"""
        if self.conn:
            self.conn.close()
            self.conn = None
