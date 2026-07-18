# -*- coding: utf-8 -*-
"""
演员详情窗口（对齐 v1 ActorDetailWindow + ui_design actor-detail.html）。

布局：左侧演员卡片（头像/信息/收藏/统计）+ 右侧作品列表（番号/标题/在线/星级）。
点击演员名（详情面板/列表）或侧栏"演员库"打开。
"""

import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSplitter,
    QListWidget, QListWidgetItem, QLineEdit, QWidget, QGroupBox,
    QMessageBox, QScrollArea,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QFont

from pyside_v2.theme import Tokens


class ActorDetailWindow(QDialog):
    """演员详情窗口。"""

    def __init__(self, main_window, actor_name=None, parent=None):
        super().__init__(parent or main_window)
        self.mw = main_window
        self.core = main_window.core
        self.setWindowTitle("演员详情")
        self.resize(900, 640)
        self._setup_ui()
        if actor_name:
            self.search_input.setText(actor_name)
            self._search()

    def _setup_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(Tokens.SP_5, Tokens.SP_5, Tokens.SP_5, Tokens.SP_5)
        lay.setSpacing(Tokens.SP_3)

        # 搜索行
        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("演员："))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入演员名搜索…")
        self.search_input.returnPressed.connect(self._search)
        search_row.addWidget(self.search_input, 1)
        self.btn_search = QPushButton("搜索")
        self.btn_search.setProperty("role", "primary")
        self.btn_search.setCursor(Qt.PointingHandCursor)
        self.btn_search.clicked.connect(self._search)
        search_row.addWidget(self.btn_search)
        lay.addLayout(search_row)

        split = QSplitter(Qt.Horizontal)

        # 左：演员卡片
        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        self.avatar_label = QLabel("头像")
        self.avatar_label.setFixedSize(220, 290)
        self.avatar_label.setAlignment(Qt.AlignCenter)
        self.avatar_label.setStyleSheet("background: palette(midlight); border-radius:12px;")
        left_lay.addWidget(self.avatar_label)

        self.name_label = QLabel("—")
        f = QFont(); f.setPointSize(18); f.setBold(True); self.name_label.setFont(f)
        left_lay.addWidget(self.name_label)

        self.alias_label = QLabel("")
        self.alias_label.setStyleSheet("color: palette(mid);")
        left_lay.addWidget(self.alias_label)

        self.stats_label = QLabel("")
        left_lay.addWidget(self.stats_label)
        left_lay.addSpacing(8)

        self.info_label = QLabel("")
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("color: palette(text);")
        left_lay.addWidget(self.info_label)
        left_lay.addStretch()

        # 收藏按钮
        self.btn_fav = QPushButton("☆ 收藏")
        self.btn_fav.setCursor(Qt.PointingHandCursor)
        self.btn_fav.clicked.connect(self._toggle_fav)
        left_lay.addWidget(self.btn_fav)
        split.addWidget(left)

        # 右：作品列表
        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.addWidget(QLabel("作品列表"))
        self.works_list = QListWidget()
        self.works_list.setAlternatingRowColors(True)
        self.works_list.itemDoubleClicked.connect(self._open_movie)
        right_lay.addWidget(self.works_list)
        split.addWidget(right)
        split.setSizes([260, 600])
        lay.addWidget(split, 1)

        btn_close = QPushButton("关闭")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.clicked.connect(self.accept)
        row2 = QHBoxLayout()
        row2.addStretch()
        row2.addWidget(btn_close)
        lay.addLayout(row2)

    def _search(self):
        name = self.search_input.text().strip()
        if not name:
            return
        info = self.mw.get_actor_info_by_name(name)  # 桥接方法
        if not info:
            QMessageBox.information(self, "提示", f"未找到演员：{name}")
            return
        # (id, name, name_traditional, name_common, aliases, avatar_url,
        #  avatar_data, profile_url, movie_count, birth_date, debut_date,
        #  height, measurements, description, is_favorite)
        self._actor_id = info[0]
        self.name_label.setText(info[1] or name)
        aliases = []
        if info[2]:
            aliases.append(info[2])
        if info[3]:
            aliases.append(info[3])
        if info[4]:
            aliases.append(info[4])
        self.alias_label.setText(" · ".join(aliases) if aliases else "")

        # 统计
        movies = self.mw.get_actor_movies_in_library(info[1] or name)
        online_n = sum(1 for m in movies if m[8])
        self.stats_label.setText(f"库内作品 {len(movies)} · 在线 {online_n}")

        # 信息
        lines = []
        if info[9]:
            lines.append(f"生日：{info[9]}")
        if info[10]:
            lines.append(f"出道——{info[10]}")
        if info[11]:
            lines.append(f"身高——{info[11]} cm")
        if info[12]:
            lines.append(f"三围——{info[12]}")
        if info[14]:
            lines.append(info[14])
        self.info_label.setText("\n".join(lines))

        # 收藏状态
        self._update_fav_button(bool(info[14]) if len(info) > 14 else False, info[14])

        # 头像
        self._load_avatar(info[6] or info[5], info[0])

        # 作品列表
        self.works_list.clear()
        for m in movies:
            mid, fname, fpath, jtitle, jcode, jrelease, cover_url, sfolder, is_online = m
            star = ""
            try:
                self.core.cursor.execute("SELECT stars FROM videos WHERE id=?", (mid,))
                sr = self.core.cursor.fetchone()
                if sr and sr[0]:
                    star = " " + "★" * sr[0]
            except Exception:
                pass
            status = "●在线" if is_online else "○离线"
            label = f"{jcode or fname}{star}  [{status}]"
            it = QListWidgetItem(label)
            it.setData(Qt.UserRole, mid)
            self.works_list.addItem(it)

    def _update_fav_button(self, is_fav, fav_val):
        # info[14] 是 is_favorite
        try:
            fav = bool(int(fav_val)) if fav_val is not None else False
        except Exception:
            fav = False
        if fav:
            self.btn_fav.setText("★ 已收藏")
            self.btn_fav.setStyleSheet("color: #e8a009;")
        else:
            self.btn_fav.setText("☆ 收藏")
            self.btn_fav.setStyleSheet("")

    def _load_avatar(self, blob_or_url, actor_id):
        try:
            if blob_or_url and isinstance(blob_or_url, (bytes, bytearray)):
                pix = QPixmap()
                pix.loadFromData(blob_or_url)
                if not pix.isNull():
                    self.avatar_label.setPixmap(
                        pix.scaled(220, 290, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                    )
                    return
            # 尝试 avatar_data 字段
            self.core.cursor.execute("SELECT avatar_data FROM actors WHERE id=?", (actor_id,))
            r = self.core.cursor.fetchone()
            if r and r[0]:
                pix = QPixmap()
                pix.loadFromData(r[0])
                if not pix.isNull():
                    self.avatar_label.setPixmap(
                        pix.scaled(220, 290, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                    )
                    return
            self.avatar_label.setText("无头像")
        except Exception:
            self.avatar_label.setText("无头像")

    def _toggle_fav(self):
        if not getattr(self, '_actor_id', None):
            return
        try:
            self.core.cursor.execute("SELECT is_favorite FROM actors WHERE id=?", (self._actor_id,))
            r = self.core.cursor.fetchone()
            cur = bool(r and r[0])
            self.core.set_actor_favorite(self._actor_id, not cur)
            self._update_fav_button(not cur, 1 if not cur else 0)
        except Exception as e:
            QMessageBox.warning(self, "失败", str(e))

    def _open_movie(self, item):
        mid = item.data(Qt.UserRole)
        if mid is not None:
            self.mw.select_video_by_id(mid) if hasattr(self.mw, 'select_video_by_id') else None
            self.mw.load_detail(mid)
            self.accept()
