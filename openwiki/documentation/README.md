---
type: 参考
title: README 摘要
description: 仓库 README 的摘要——系统概述、入口点、爬虫描述、视频分析器设置以及双 GUI 架构的性能基准。
tags: [documentation, README]
openwiki:
  roles: [repository]
  source_paths: [README.md]
---

# README 摘要

仓库的 README.md 是主要的项目文档。它涵盖了：

## 系统概述

一个跨平台的视频媒体库管理系统，支持本地和 NAS 存储，具备以下功能：
- MD5 去重
- 智能增量更新
- 演员信息管理
- 批量操作
- 基于 AI 的视频内容分析

## 两种可用的 GUI 入口

| 版本 | 入口 | 工具包 | 备注 |
|---------|-------|---------|-------|
| **经典版 (Tkinter)** | `media_library.py` | Tkinter | 单文件，历史最悠久，功能最多 |
| **PySide6 v2（推荐）** | `media_library_v2.py` | PySide6 | 模块化包，双主题，高性能 |

`media_library_pyside.py` (PySide6 v1) 已被 v2 取代，不再维护。

## 架构关系

v2 使用 `gui_adapter.py` 将 Tkinter `MediaLibrary` 类的 166 个后端方法桥接到 Qt 窗口——**后端代码零更改**。Tk 版本既可作为独立应用程序，也可作为 v2 的逻辑库。

## 性能基准

| 场景 | Tk 经典版 | PySide6 v2 | 提升 |
|----------|-----------|------------|-------------|
| 首屏加载 | 约 31 秒（全表 JOIN） | **0.5 秒**（分页 + 索引） | 60 倍 |
| 搜索（热） | 阻塞 | **0.1-0.6 秒** | — |
| 翻页 | 全量重新查询 | **0.04 秒** | — |
| UI 响应 | 查询时冻结 | **异步，不冻结** | — |

优化：复合索引 `(is_nas_online, file_created_time)`，使用 `id IN (subquery)` 替代 `OR LIKE`，以及后台 `QueryWorker` 线程。

## 组件部分

README 还记录了以下内容：
- **爬虫与登录** — JavDB 登录助手、爬虫、JavSP 多源系统
- **媒体库维护** — 智能更新器、快速更新器、可恢复导入器
- **辅助工具** — 完整性检查器、驱动更新器
- **视频分析器** — SiliconFlow API 集成、模型对比、标签优先级
- **JavDB 信息更新器** — 批量元数据刷新

## 另请参阅

- [主应用程序概述](../main_application/overview.md) — 详细 GUI 文档
- [爬虫概述](../crawlers/overview.md) — 爬虫系统详细信息
- [快速入门](../quickstart.md) — 如何运行系统