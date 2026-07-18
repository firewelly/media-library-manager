# -*- coding: utf-8 -*-
"""
演员库对话框
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QFrame, QScrollArea,
    QWidget, QGridLayout
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QImage

from ..core import Database, ActorRepository
from ..theme import get_main_qss


class ActorDialog(QDialog):
    """演员库对话框"""

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.setWindowTitle("演员库")
        self.setMinimumSize(1000, 700)
        self.setStyleSheet(get_main_qss())

        self.db = db
        self.repo = ActorRepository(db)
        self._current_actor = None

        self._setup_ui()
        self._load_actors()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 左侧列表
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        # 搜索栏
        search_bar = QFrame()
        search_bar.setStyleSheet("background-color: #1a1e26; padding: 12px;")
        search_layout = QHBoxLayout(search_bar)
        search_layout.setContentsMargins(12, 12, 12, 12)
        search_layout.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索演员…")
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #0a0c0f;
                border: 1px solid #1f232c;
                border-radius: 8px;
                padding: 0 12px;
                min-height: 32px;
                color: #f2f4f8;
            }
        """)
        self.search_input.textChanged.connect(self._on_search)
        search_layout.addWidget(self.search_input)

        self.fav_btn = QPushButton("★ 收藏")
        self.fav_btn.clicked.connect(self._toggle_fav_filter)
        search_layout.addWidget(self.fav_btn)

        left_layout.addWidget(search_bar)

        # 演员表格
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["头像", "姓名", "作品数", "收藏"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setColumnWidth(0, 60)
        self.table.setColumnWidth(1, 200)
        self.table.setColumnWidth(2, 80)
        self.table.setColumnWidth(3, 60)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.currentCellChanged.connect(self._on_actor_selected)

        left_layout.addWidget(self.table)

        layout.addWidget(left, 1)

        # 右侧详情
        right = QFrame()
        right.setFixedWidth(360)
        right.setStyleSheet("background-color: #1a1e26; border-left: 1px solid #1f232c;")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(12)

        # 头像
        self.avatar_label = QLabel()
        self.avatar_label.setFixedSize(200, 200)
        self.avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar_label.setStyleSheet("background-color: #1e2229; border-radius: 8px;")
        content_layout.addWidget(self.avatar_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # 姓名
        self.name_label = QLabel("选择演员查看详情")
        self.name_label.setStyleSheet("font-size: 18px; font-weight: 600;")
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(self.name_label)

        # 别名
        self.alias_label = QLabel("")
        self.alias_label.setStyleSheet("color: #6b7382; font-size: 12px;")
        self.alias_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(self.alias_label)

        # 信息行
        self.info_rows = {}
        for key, label in [("birth_date", "生日"), ("height", "身高"), ("measurements", "三围"), ("movie_count", "作品数")]:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            k = QLabel(label)
            k.setStyleSheet("color: #6b7382; min-width: 60px;")
            v = QLabel("")
            v.setStyleSheet("color: #f2f4f8;")
            row_layout.addWidget(k)
            row_layout.addWidget(v)
            row_layout.addStretch()
            content_layout.addWidget(row)
            self.info_rows[key] = v

        # 操作按钮
        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 16, 0, 0)
        btn_layout.setSpacing(8)

        self.fav_action_btn = QPushButton("★ 收藏")
        self.fav_action_btn.setProperty("primary", "true")
        self.fav_action_btn.clicked.connect(self._toggle_favorite)
        btn_layout.addWidget(self.fav_action_btn)

        content_layout.addWidget(btn_row)
        content_layout.addStretch()

        scroll.setWidget(content)
        right_layout.addWidget(scroll)

        layout.addWidget(right)

    def _load_actors(self, search: str = "", favorites_only: bool = False):
        actors, total, _ = self.repo.get_actors(search=search, favorites_only=favorites_only, limit=500)
        self.table.setRowCount(len(actors))

        for row, actor in enumerate(actors):
            # 头像
            avatar_widget = QLabel()
            avatar_widget.setFixedSize(50, 50)
            avatar_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            avatar_widget.setStyleSheet("background-color: #1e2229; border-radius: 4px;")
            self.table.setCellWidget(row, 0, avatar_widget)

            # 姓名
            name_item = QTableWidgetItem(actor.get("name", ""))
            self.table.setItem(row, 1, name_item)

            # 作品数
            count_item = QTableWidgetItem(str(actor.get("movie_count", 0)))
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 2, count_item)

            # 收藏
            fav = "★" if actor.get("is_favorite") else ""
            fav_item = QTableWidgetItem(fav)
            fav_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            fav_item.setForeground(Qt.GlobalColor.yellow if fav else Qt.GlobalColor.darkGray)
            self.table.setItem(row, 3, fav_item)

            self.table.setRowHeight(row, 60)

        self._actors_data = actors

    def _on_search(self, text: str):
        self._load_actors(search=text)

    def _toggle_fav_filter(self):
        active = self.fav_btn.property("active")
        self.fav_btn.setProperty("active", "false" if active else "true")
        self.fav_btn.style().unpolish(self.fav_btn)
        self.fav_btn.style().polish(self.fav_btn)
        self._load_actors(favorites_only=not active)

    def _on_actor_selected(self, row, col, prev_row, prev_col):
        if 0 <= row < len(self._actors_data):
            actor = self._actors_data[row]
            self._current_actor = actor
            self._show_actor_detail(actor)

    def _show_actor_detail(self, actor: dict):
        self.name_label.setText(actor.get("name", ""))

        aliases = []
        if actor.get("name_en"):
            aliases.append(actor["name_en"])
        if actor.get("name_common"):
            aliases.append(actor["name_common"])
        self.alias_label.setText(" · ".join(aliases) if aliases else "")

        self.info_rows["birth_date"].setText(actor.get("birth_date", "") or "未知")
        self.info_rows["height"].setText(f"{actor.get('height', '')} cm" if actor.get("height") else "未知")
        self.info_rows["measurements"].setText(actor.get("measurements", "") or "未知")
        self.info_rows["movie_count"].setText(str(actor.get("movie_count", 0)))

        # 加载头像
        avatar_path = actor.get("local_avatar_path") or actor.get("avatar_url")
        if avatar_path:
            pixmap = QPixmap(avatar_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.avatar_label.setPixmap(scaled)

    def _toggle_favorite(self):
        if self._current_actor:
            self.repo.toggle_favorite(self._current_actor["id"])
            self._load_actors()
