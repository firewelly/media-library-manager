# -*- coding: utf-8 -*-
"""
左侧导航栏（对齐 ui_design/main-light.html 的 .sidebar）。

结构：
    品牌（logo + 媒体库）
    媒体库分组：全部视频 / 收藏 / 最近添加 / 无标签
    存储位置：动态加载本地磁盘 / NAS 各盘（含在线状态点）
    管理：演员库 / 标签管理 / 文件夹管理 / 设置
    底部：存储在线状态汇总

点击导航项 → 发出 nav_changed(key) 信号，MainWindow 据此筛选。
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QScrollArea
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QFont

from pyside_v2.theme import Tokens


class Sidebar(QWidget):
    """左侧导航栏。"""

    nav_changed = Signal(str)   # key: 'all'/'favorites'/'recent'/'notag'/'folder:<path>'

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(Tokens.SIDEBAR_W)
        self._folder_buttons = {}
        self._nav_buttons = []   # 所有可勾选的导航按钮（用于互斥选中）
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 12, 8, 12)
        root.setSpacing(0)

        # ---- 品牌 ----
        brand_row = self._row_widget()
        logo = QLabel("M")
        logo.setObjectName("brandLogo")
        logo.setFixedSize(28, 28)
        logo.setAlignment(Qt.AlignCenter)
        logo_font = QFont(); logo_font.setWeight(QFont.Bold); logo_font.setPointSize(14)
        logo.setFont(logo_font)
        name = QLabel("媒体库")
        name.setObjectName("brandLabel")
        brand_row.layout().addWidget(logo)
        brand_row.layout().addWidget(name)
        brand_row.layout().addStretch()
        root.addWidget(brand_row)
        root.addSpacing(12)

        # ---- 媒体库分组 ----
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        inner_lay = QVBoxLayout(inner)
        inner_lay.setContentsMargins(0, 0, 0, 0)
        inner_lay.setSpacing(1)

        inner_lay.addWidget(self._section_label("媒体库"))
        for key, icon, text in [
            ('all',       '▦', '全部视频'),
            ('favorites', '★', '收藏'),
            ('recent',    '◷', '最近添加'),
            ('notag',     '⌀', '无标签'),
        ]:
            btn = self._nav_button(icon, text, key)
            inner_lay.addWidget(btn)

        inner_lay.addSpacing(8)
        self._folder_section_label = self._section_label("存储位置")
        inner_lay.addWidget(self._folder_section_label)
        self._folder_container = QVBoxLayout()
        self._folder_container.setSpacing(1)
        inner_lay.addLayout(self._folder_container)

        inner_lay.addSpacing(8)
        inner_lay.addWidget(self._section_label("管理"))
        for key, icon, text, handler in [
            ('actors',  '◉', '演员库',    'actors'),
            ('tags',    '#', '标签管理',  'tags'),
            ('folders', '▸', '文件夹管理','folders'),
            ('settings','⚙', '设置',     'settings'),
        ]:
            btn = self._action_button(icon, text, handler)
            inner_lay.addWidget(btn)

        inner_lay.addStretch()
        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

        # ---- 底部存储状态 ----
        self._footer = QLabel()
        self._footer.setObjectName("sidebarFooter")
        self._footer.setWordWrap(True)
        root.addWidget(self._footer)

    def _row_widget(self):
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(12, 0, 8, 0)
        lay.setSpacing(8)
        return w

    def _section_label(self, text):
        lbl = QLabel(text)
        lbl.setObjectName("navSectionLabel")
        f = QFont(); f.setPointSize(9); lbl.setFont(f)
        # 用 margin 模拟 padding
        lay_wrap = QWidget()
        lay = QVBoxLayout(lay_wrap)
        lay.setContentsMargins(12, 12, 0, 4)
        lay.setSpacing(0)
        lay.addWidget(lbl)
        return lay_wrap

    def _nav_button(self, icon, text, key, count=None):
        w = QWidget()
        w.setObjectName("navRow")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(12, 0, 8, 0)
        lay.setSpacing(12)
        ico = QLabel(icon)
        ico.setFixedWidth(18)
        ico.setAlignment(Qt.AlignCenter)
        ico.setStyleSheet("background:transparent;")
        name = QPushButton(text)
        name.setObjectName("navBtn")
        name.setProperty("role", "nav")
        name.setCheckable(True)
        name.setCursor(Qt.PointingHandCursor)
        name.setFlat(True)
        name.setStyleSheet("text-align:left;")
        name.clicked.connect(lambda checked=False, k=key: self._on_nav_clicked(k))
        cnt = QLabel(str(count) if count else "")
        cnt.setStyleSheet("color: palette(mid); font-size:11px; background:transparent;")
        lay.addWidget(ico)
        lay.addWidget(name, 1)
        lay.addWidget(cnt)
        # 整行可点击
        w.mousePressEvent = lambda e, k=key: self._on_nav_clicked(k)
        w._btn = name
        self._nav_buttons.append(name)   # 记录用于互斥
        return w

    def _action_button(self, icon, text, handler):
        """管理类条目：不可勾选，点击即触发动作。"""
        w = QWidget()
        w.setObjectName("navRow")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(12, 0, 8, 0)
        lay.setSpacing(12)
        ico = QLabel(icon)
        ico.setFixedWidth(18)
        ico.setAlignment(Qt.AlignCenter)
        ico.setStyleSheet("background:transparent;")
        name = QPushButton(text)
        name.setProperty("role", "nav")
        name.setCursor(Qt.PointingHandCursor)
        name.setFlat(True)
        name.setStyleSheet("text-align:left;")
        name.clicked.connect(lambda checked=False, h=handler: self.nav_changed.emit(h))
        lay.addWidget(ico)
        lay.addWidget(name, 1)
        w.mousePressEvent = lambda e, h=handler: self.nav_changed.emit(h)
        return w

    def _on_nav_clicked(self, key):
        # 互斥：取消其他按钮选中态
        sender = self.sender()
        for btn in self._nav_buttons:
            if btn is not sender:
                btn.setChecked(False)
        if isinstance(sender, QPushButton):
            sender.setChecked(True)
        self.nav_changed.emit(key)

    # ---- 动态加载存储位置 ----
    def load_storage_locations(self, core):
        """从数据库加载存储位置（folders 表），更新导航项 + 底部状态。"""
        # 清空旧的
        while self._folder_container.count():
            item = self._folder_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        try:
            core.cursor.execute("SELECT folder_path, folder_type, device_name FROM folders WHERE is_active = 1 ORDER BY folder_path")
            folders = core.cursor.fetchall()
        except Exception:
            folders = []

        import os
        online_count = 0
        offline_count = 0
        for folder_path, folder_type, device_name in folders:
            is_online = os.path.exists(folder_path)
            if is_online:
                online_count += 1
            else:
                offline_count += 1
            # 简短显示名
            parts = folder_path.rstrip('/').replace('\\', '/').split('/')
            short = parts[-1] if parts else folder_path
            icon = '☁' if folder_type == 'nas' else '▣'
            btn = self._nav_button(icon, short, f'folder:{folder_path}')
            self._folder_container.addWidget(btn)

        self._footer.setText(
            f"● 在线 {online_count}    ○ 离线 {offline_count}"
        )

    def select_all(self):
        """默认选中"全部视频"。"""
        if self._nav_buttons:
            self._nav_buttons[0].setChecked(True)
