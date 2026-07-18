# -*- coding: utf-8 -*-
"""
JAV 信息面板对话框（对齐 v1 JavInfoDialog）。

输入番号 → 搜索 → 保存到数据库。对接 utils.jav.search_movie_info / save_movie_info_to_db。
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QGroupBox, QPlainTextEdit, QMessageBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from pyside_v2.theme import Tokens


class JavInfoDialog(QDialog):
    """JAV 信息面板：输入番号搜索并保存。"""

    def __init__(self, main_window, parent=None):
        super().__init__(parent or main_window)
        self.mw = main_window
        self.core = main_window.core
        self.setWindowTitle("JAV 信息面板")
        self.resize(480, 380)
        self._setup_ui()

    def _setup_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(Tokens.SP_5, Tokens.SP_5, Tokens.SP_5, Tokens.SP_5)
        lay.setSpacing(Tokens.SP_3)

        box = QGroupBox("搜索")
        box_lay = QVBoxLayout(box)
        row = QHBoxLayout()
        row.addWidget(QLabel("番号："))
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("如 ABC-123")
        self.code_input.returnPressed.connect(self._search)
        row.addWidget(self.code_input, 1)
        self.btn_search = QPushButton("🔎 搜索并保存")
        self.btn_search.setProperty("role", "primary")
        self.btn_search.setCursor(Qt.PointingHandCursor)
        self.btn_search.clicked.connect(self._search)
        row.addWidget(self.btn_search)
        box_lay.addLayout(row)

        self.result_view = QPlainTextEdit()
        self.result_view.setReadOnly(True)
        self.result_view.setPlaceholderText("搜索结果将显示在此…")
        box_lay.addWidget(self.result_view)
        lay.addWidget(box)

        btn_close = QPushButton("关闭")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.clicked.connect(self.accept)
        row2 = QHBoxLayout()
        row2.addStretch()
        row2.addWidget(btn_close)
        lay.addLayout(row2)

    def _search(self):
        code = self.code_input.text().strip()
        if not code:
            QMessageBox.information(self, "提示", "请输入番号")
            return
        self.btn_search.setEnabled(False)
        self.result_view.setPlainText(f"正在搜索 {code}…")
        QApplication_ref = __import__('PySide6.QtWidgets', fromlist=['QApplication']).QApplication
        QApplication_ref.processEvents()
        try:
            from utils import jav as utils_jav
            info = utils_jav.search_movie_info(code)
            if not info:
                self.result_view.setPlainText(f"未找到 {code} 的信息")
                return
            # 显示
            lines = []
            for k in ('title', 'video_id', 'detail_url', 'release_date', 'duration', 'rating', 'studio'):
                if info.get(k):
                    lines.append(f"{k}: {info[k]}")
            if info.get('tags'):
                lines.append("标签: " + ", ".join(info['tags']))
            if info.get('actors'):
                lines.append("演员: " + ", ".join(a.get('name', str(a)) for a in info['actors']))
            self.result_view.setPlainText("\n".join(lines))

            # 保存：若有当前选中视频，关联；否则仅显示
            vid = self.mw._current_video_id
            if vid is not None:
                ok = utils_jav.save_movie_info_to_db(self.core.conn, vid, info)
                if ok:
                    self.result_view.appendPlainText("\n✅ 已保存到当前选中视频")
                    self.mw.load_detail(vid)
                    self.mw.load_videos()
                else:
                    self.result_view.appendPlainText("\n⚠️ 保存失败")
            else:
                self.result_view.appendPlainText("\n（未选中视频，仅显示未保存）")
        except Exception as e:
            self.result_view.setPlainText(f"搜索失败: {e}")
        finally:
            self.btn_search.setEnabled(True)
