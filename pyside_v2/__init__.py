#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pyside_v2 - PySide6 v2 前端重构包

在不改动 media_library.py(后端) / gui_adapter.py(桥接) / utils/(工具层) 的前提下，
重构一个更漂亮、更现代、运行更快的跨系统前端。

入口：
    python -m pyside_v2.app
    python pyside_v2/app.py

设计要点：
    - 复用现有 MediaLibraryCore（纯后端 facade）与 gui_adapter.setup_full_integration 桥接机制
    - 模块化包结构，按职责拆分（widgets/dialogs/workers/theme/windows/actions）
    - 暗色 + 亮色双主题
    - QTableView + QAbstractTableModel 取代 QTreeWidget（性能优化）
    - 异步任务统一用 BaseWorker + QThreadPool（消除阻塞型 UI 冻结）
"""

__version__ = "2.0"
__app_name__ = "媒体库管理器 v2"
