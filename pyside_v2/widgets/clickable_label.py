# -*- coding: utf-8 -*-
"""
可点击 QLabel —— 替代「mousePressEvent = lambda」猴子补丁。

原有代码在实例上直接覆写 mousePressEvent（如详情面板星级标签、演员链接），
绕过 Qt 事件分发，lambda 无法 disconnect，也无法被信号槽管理。
本类提供正规子类方案：发出 clicked() 信号，用 connect 连接。
"""

from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt, Signal


class ClickableLabel(QLabel):
    """可点击的 QLabel，左键点击发出 clicked() 信号。"""

    clicked = Signal()

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
