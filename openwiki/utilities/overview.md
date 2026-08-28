---
type: 概述
title: 实用工具概述
description: 共享 utils/ 工具层概述——涵盖数据库访问、文件操作、批处理操作、维护、日志、缩略图以及 JavSP 集成辅助功能。
openwiki:
  roles: [architecture]
  source_paths: [utils/__init__.py, utils/database.py, utils/file_utils.py, utils/batch_ops.py, utils/maintenance.py, utils/logger.py, utils/thumbnails.py, utils/runtime.py]
---

# 实用工具概述

`utils/` 包是 GUI 版本和所有独立脚本共享的后端工具层。它不包含任何 GUI 代码——仅包含数据库访问、文件操作、批处理、日志记录以及特定领域的辅助功能。

## 包结构

| 模块 | 用途 | 核心类 |
|--------|---------|-------------|
| `database.py` | SQLite 数据库管理 | `DatabaseManager` |
| `db.py` | 底层爬虫数据库辅助功能 | `upsert_jav_info()`、`upsert_actors()` |
| `file_utils.py` | 文件操作（移动、复制、MD5、重命名） | `FileUtils` |
| `batch_ops.py` | 批处理操作（标签、删除、重命名） | `BatchOperationManager` |
| `maintenance.py` | 数据库维护（清理压缩、索引重建） | `MaintenanceManager` |
| `media_extensions.py` | NFO 导入、标签管理、封面处理 | `NFOImporter` |
| `logger.py` | 双输出日志记录（控制台 + GUI） | `log_info()`、`log_error()` |
| `progress.py` / `progress_manager.py` | 长时间操作的进度报告 | `ThreadedProgress` |
| `thumbnails.py` | 通过 ffmpeg 生成视频缩略图 | `ThumbnailGenerator` |
| `video_rotate.py` | 通过 ffmpeg 旋转视频 | — |
| `runtime.py` | 运行时/资源路径解析 | `runtime_path()`、`resource_path()` |
| `jav.py` | 视频代码提取辅助功能 | — |
| `javsp_copy.py` | JavSP 文件复制工具 | — |
| `javsp_migration.py` | JavSP 数据迁移辅助功能 | — |
| `javsp_integration.py` | 轻量级重新导出封装器 | — |

## 核心设计原则

1. **无 GUI 依赖**：`utils/` 绝不导入 Tkinter 或 PySide6。这使得独立脚本能够使用相同的函数。
2. **运行时路径解析**：`utils/runtime.py` 解析相对于 `sys.argv[0]` 的路径，使得无论哪个脚本导入 utils，都能找到数据库和配置文件。
3. **线程安全**：`DatabaseManager` 使用 `check_same_thread=False` 以允许 Qt 工作线程共享连接。
4. **跨设备支持**：`FileUtils` 处理同设备重命名、跨设备复制+删除，以及针对路径长度限制的自动文件名缩短。

## 另请参阅

- [Utils 模块参考](../other_directories/utils.md) — 详细 API 文档
- [数据库概述](../database/overview.md) — 架构和 DatabaseManager 详细信息
- [MD5 工具](md5_tools.md) — MD5 计算工作流
- [重新打标签工具](retagging_tools.md) — 自动打标签系统
- [智能更新工具](smart_updating_tools.md) — 导入和更新脚本