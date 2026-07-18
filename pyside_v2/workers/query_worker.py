# -*- coding: utf-8 -*-
"""
异步查询 worker - 让列表查询不阻塞 UI。

用途：搜索/筛选的冷查询可能 2-5s（SQLite 大库磁盘 IO），放后台线程执行，
UI 保持响应（显示"加载中"），完成后通过信号回到主线程更新模型。

注意：SQLite 连接用 check_same_thread=False 共享，但并发写需小心；
这里只读查询，安全。
"""

from PySide6.QtCore import QThread, Signal, QObject


class QueryWorker(QThread):
    """在后台执行一次列表查询（COUNT + 分页）。"""

    finished_signal = Signal(object, int, int)   # (rows, total, page_no)
    error_signal = Signal(str)

    def __init__(self, query_fn, page_no, parent=None):
        """
        query_fn: () -> (rows, total)  闭包，执行 COUNT + 分页查询
        page_no: 当前页码（透传回信号）
        """
        super().__init__(parent)
        self._query_fn = query_fn
        self._page_no = page_no

    def run(self):
        try:
            rows, total = self._query_fn()
            self.finished_signal.emit(rows, total, self._page_no)
        except Exception as e:
            self.error_signal.emit(str(e))
