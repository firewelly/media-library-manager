# -*- coding: utf-8 -*-
"""
数据加载工作线程
"""

from PySide6.QtCore import QThread, Signal

from ..core import VideoRepository


class DataLoaderWorker(QThread):
    """异步数据加载"""

    finished = Signal(list, int, int)  # rows, total, elapsed_ms
    error = Signal(str)

    def __init__(
        self,
        repo: VideoRepository,
        offset: int = 0,
        limit: int = 200,
        search: str = "",
        filters: dict = None,
        sort_by: str = "created_at",
        sort_order: str = "DESC",
        parent=None,
    ):
        super().__init__(parent)
        self.repo = repo
        self.offset = offset
        self.limit = limit
        self.search = search
        self.filters = filters or {}
        self.sort_by = sort_by
        self.sort_order = sort_order

    def run(self):
        try:
            rows, total, elapsed_ms = self.repo.get_videos(
                offset=self.offset,
                limit=self.limit,
                search=self.search,
                filters=self.filters,
                sort_by=self.sort_by,
                sort_order=self.sort_order,
            )
            self.finished.emit(rows, total, elapsed_ms)
        except Exception as e:
            self.error.emit(str(e))
