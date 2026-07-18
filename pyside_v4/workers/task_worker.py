# -*- coding: utf-8 -*-
"""
pyside_v4.workers.task_worker — 通用任务 Worker
直接 import media_library_pyside.py 的 GenericWorker，不复制代码
"""

import sys
import os

# 确保项目根目录在 sys.path 中
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# 直接 import 已有后端
from media_library_pyside import GenericWorker  # noqa: E402

# 别名导出
TaskWorker = GenericWorker

__all__ = ['TaskWorker', 'GenericWorker']
