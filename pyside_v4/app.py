# -*- coding: utf-8 -*-
"""
pyside_v4 - 媒体库管理器 v4
深色影院风界面（琥珀金强调色 + 玻璃拟态面板）
"""

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from .windows import MainWindow


def main():
    """应用入口"""
    # 高 DPI 支持
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    app = QApplication(sys.argv)
    app.setApplicationName("媒体库管理器 v4")
    app.setOrganizationName("MediaLibrary")
    
    # 创建主窗口
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
