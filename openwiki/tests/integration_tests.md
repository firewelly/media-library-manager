---
type: 参考文档
title: 集成测试
description: 介绍 v2 集成测试 — test_v2_gui.py（小部件和对话框验证）、test_v2_refactor.py（核心数据访问审计、主题颜色令牌、SQL 隔离）以及 smoke_test_v2.py（视觉截图验证）。
openwiki:
  roles: [testing]
  source_paths: [tests/test_v2_gui.py, tests/test_v2_refactor.py, tests/smoke_test_v2.py]
---

# 集成测试

验证 v2 GUI 组件、重构审计和视觉渲染的测试。

## `test_v2_gui.py`（约 350 行）

v2 GUI 包的集成测试：
- 验证小部件初始化（VideoModel、VideoTable、Sidebar）
- 测试对话框创建（ImportVideos、TagManager、FolderManager）
- 验证主题应用和切换
- 使用 QT_QPA_PLATFORM=offscreen 运行以进行无头执行

## `test_v2_refactor.py`（约 720 行）

对 v2 重构进行全面审计。分为以下几个部分：

**第 1 部分：核心数据访问层（17 个新方法）**
- 测试所有替代了小部件中直接 SQL 的 `MediaLibraryCore` 方法
- 验证查询正确性和返回类型

**第 2 部分：主题颜色令牌**
- 测试 `theme/colors.py` 中的 `color_hex()` 函数
- 验证深色和浅色主题令牌解析

**第 3 部分：新 UI 组件**
- 测试 `NavRow` 和 `ClickableLabel` 小部件行为

**第 4 部分：完整 GUI 功能**
- 列表渲染、搜索、筛选、排序
- 详情面板加载
- 主题切换持久化

**第 5 部分：SQL 隔离**
- 扫描小部件和对话框源文件中的 `cursor.execute` 调用
- **不变量**：`pyside_v2/widgets/` 或 `pyside_v2/dialogs/` 中不存在 `cursor.execute`
- 所有数据访问必须通过 `MediaLibraryCore` 进行

**第 6 部分：导入流程**
- 验证三阶段导入工作线程

## `smoke_test_v2.py` — 视觉冒烟测试

启动真实的 v2 窗口并捕获截图以进行视觉验证：

1. **截图 1**：浅色主题主界面
2. **截图 2**：已加载详情面板（选择第一行后）
3. **截图 3**：深色主题（切换后）
4. **截图 4**：“更多”菜单已展开

截图保存至 /tmp/v2_smoke_*.png。

**运行冒烟测试：**
```bash
cd /Users/firewell/bin/media
python3 tests/smoke_test_v2.py
```

> 注意：冒烟测试需要显示器（非无头模式）。它会打开一个真实的窗口。

## 运行

```bash
cd /Users/firewell/bin/media
python3 tests/test_v2_gui.py
python3 tests/test_v2_refactor.py
```

## 另请参阅

- [测试概述](overview.md) — 完整测试套件
- [单元测试](unit_tests.md) — 工具类和 Tk 列测试
- [PySide6 v2](../main_application/v2.md) — 这些测试的验证目标