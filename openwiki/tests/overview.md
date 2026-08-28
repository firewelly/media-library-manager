---
type: 概述
title: 测试概述
description: 测试系统概述——包括单元测试、集成测试、GUI 冒烟测试以及支持离屏 Qt 平台的测试基础设施。
openwiki:
  roles: [testing]
  source_paths: [tests/test_pyside_utils.py, tests/test_tk_column_width_logic.py, tests/test_v2_gui.py, tests/test_v2_refactor.py, tests/smoke_test_v2.py]
---

# 测试概述

测试套件涵盖了工具函数、Tk 列逻辑、v2 GUI 功能、v2 重构验证以及可视化冒烟测试。

## 测试文件

| 文件 | 类型 | 覆盖范围 |
|------|------|----------|
| `test_pyside_utils.py` | 单元 | `BatchOperationManager`, `MaintenanceManager`, `ThumbnailGenerator`, `JavSPIntegration` |
| `test_tk_column_width_logic.py` | 单元 | Tk Treeview 列调整大小和重新排序逻辑 |
| `test_v2_gui.py` | 集成 | v2 GUI 初始化、小部件、对话框 |
| `test_v2_refactor.py` | 集成 | v2 重构审计——核心数据访问（17 个方法）、主题令牌、组件、SQL 封装 |
| `smoke_test_v2.py` | 可视化 | 启动真实的 v2 窗口，并在两种主题下截取屏幕截图 |

## 测试基础设施

- 所有测试都将 `sys.argv[0]` 锚定到项目根目录（与应用程序相同的机制），以确保 `utils/runtime.runtime_path()` 正确解析
- GUI 测试设置 `QT_QPA_PLATFORM=offscreen` 以进行无头执行
- 测试使用 `unittest` 并结合模拟对象处理数据库连接
- 无需外部测试运行器——每个文件均可直接执行：

```bash
cd /Users/firewell/bin/media
python3 tests/test_pyside_utils.py
python3 tests/test_tk_column_width_logic.py
python3 tests/test_v2_gui.py
python3 tests/test_v2_refactor.py
```

## 另请参阅

- [单元测试](unit_tests.md) — 详细的单元测试文档
- [集成测试](integration_tests.md) — 详细的集成测试文档