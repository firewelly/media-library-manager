# -*- coding: utf-8 -*-
"""
侧栏导航行 —— 替代「mousePressEvent = lambda」猴子补丁。

原有代码在 QWidget 实例上直接覆写 mousePressEvent，绕过 Qt 事件分发。
本类提供正规子类方案：整行可点击，发出 clicked(key) 信号。

两种模式：
    - checkable=True：导航项（全部/收藏/最近…），按钮可勾选，用于互斥高亮
    - checkable=False：管理项（演员库/标签/文件夹…），点击即触发动作
"""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, Signal


class NavRow(QWidget):
    """侧栏导航行：图标 + 文本按钮 + （可选）计数，整行可点击。"""

    clicked = Signal(str)   # key

    def __init__(self, icon, text, key, checkable=True, count=None, parent=None):
        super().__init__(parent)
        self.setObjectName("navRow")
        self._key = key
        self._checkable = checkable

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 8, 0)
        lay.setSpacing(12)

        # 图标
        self.icon_label = QLabel(icon)
        self.icon_label.setFixedWidth(18)
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setStyleSheet("background:transparent;")
        lay.addWidget(self.icon_label)

        # 文本按钮
        self.button = QPushButton(text)
        self.button.setObjectName("navBtn")
        self.button.setProperty("role", "nav")
        self.button.setCheckable(checkable)
        self.button.setCursor(Qt.PointingHandCursor)
        self.button.setFlat(True)
        self.button.setStyleSheet("text-align:left;")
        # 点击按钮也转发到行的 clicked（统一入口）
        self.button.clicked.connect(lambda: self.clicked.emit(self._key))
        lay.addWidget(self.button, 1)

        # 计数（可选）
        self.count_label = QLabel(str(count) if count else "")
        self.count_label.setStyleSheet("color: palette(mid); font-size:11px; background:transparent;")
        lay.addWidget(self.count_label)

    def mousePressEvent(self, event):
        """整行可点击：左键 → 发出 clicked 信号。"""
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._key)
        super().mousePressEvent(event)
