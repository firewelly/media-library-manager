#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
媒体库管理器 v4 - 入口文件
深色影院风界面（琥珀金强调色 + 玻璃拟态面板）

使用方式：
    python media_library_v4.py
"""

import sys
import os

# 确保项目根目录在 sys.path 中
_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from pyside_v4.windows import MainWindow


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
