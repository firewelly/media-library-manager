#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
媒体库管理器 v2 启动脚本（Python 版，跨平台）。

放在项目根目录，双击或命令行运行即可启动 PySide6 v2：
    python start_v2.py

会自动：
  1. 切换到脚本所在目录（确保 import 路径正确）
  2. 锚定 runtime 目录到项目根（media_library.db/gui_config.json 路径）
  3. 检查并按需安装 PySide6
  4. 启动 pyside_v2.app
"""

import os
import sys
import subprocess


def main():
    # 1. 切换到脚本所在目录（项目根）
    project_root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_root)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    # 2. 锚定 runtime 目录：utils.runtime 用 sys.argv[0] 作基准，
    #    这里设为项目根的 media_library.py，确保连到真实数据库
    sys.argv = [os.path.join(project_root, "media_library.py")]

    # 3. 检查 PySide6，缺失则用 pip 安装
    try:
        import PySide6  # noqa: F401
    except ImportError:
        print("未找到 PySide6，正在安装…")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "PySide6",
             "-i", "https://pypi.tuna.tsinghua.edu.cn/simple"]
        )

    # 4. 启动 v2
    from pyside_v2.app import main as run_v2
    sys.exit(run_v2())


if __name__ == "__main__":
    main()
