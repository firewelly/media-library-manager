#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
媒体库管理器 v2 - PySide6 前端入口。

启动：
    python -m pyside_v2.app
    python pyside_v2/app.py
"""

import os
import sys

# ---------------------------------------------------------------------------
# 关键：把 runtime 基准目录锚定到项目根（media/），而非 pyside_v2/。
#
# utils.runtime.runtime_dir() 用 sys.argv[0]（入口脚本路径）作为运行时基准，
# 用来定位 media_library.db / gui_config.json / md5_cache.json。
# 当从 pyside_v2/app.py 启动时，基准会错误地变成 pyside_v2/，导致连到空库。
#
# 约束：不能改 utils/runtime.py。解法：在 import 任何依赖 runtime 的模块之前，
# 把 sys.argv[0] 设为项目根路径，使 runtime_dir() 返回正确的 media/ 目录。
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if not sys.argv or not os.path.exists(sys.argv[0]) or \
   not os.path.exists(os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), 'media_library.py')):
    sys.argv = [os.path.join(_PROJECT_ROOT, 'media_library.py')]
# 确保进程工作目录在项目根，便于相对路径资源（ffmpeg 脚本、crawler 等也依赖此）
if os.getcwd() != _PROJECT_ROOT:
    os.chdir(_PROJECT_ROOT)

from PySide6.QtWidgets import QApplication

from pyside_v2 import __app_name__, __version__
from pyside_v2.core import init_qt_logging
from pyside_v2.windows import MainWindow


def main():
    # 1. 把后端日志路由到 Qt 信号（关键：media_library.py 内部用 _output_log）
    init_qt_logging()

    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setApplicationVersion(__version__)

    # 2. 创建并显示主窗口（主题在 MainWindow.__init__ 内初始化）
    window = MainWindow()
    window.show()
    window.raise_()
    window.activateWindow()

    # 3. 让初次绘制尽快发生
    app.processEvents()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
