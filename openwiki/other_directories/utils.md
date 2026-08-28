---
type: 参考手册
title: Utils 模块
description: 记录 utils/ 共享工具模块 — DatabaseManager、FileUtils、BatchOperationManager、MaintenanceManager、ThumbnailGenerator、media_extensions（NFO 导入、去重、自动打标签）、进度跟踪以及运行时路径解析。
openwiki:
  roles: [architecture]
  source_paths: [utils/database.py, utils/file_utils.py, utils/batch_ops.py, utils/maintenance.py, utils/thumbnails.py, utils/media_extensions.py, utils/logger.py, utils/runtime.py, utils/db.py, utils/jav.py, utils/javsp_copy.py, utils/javsp_migration.py, utils/progress_manager.py, utils/video_rotate.py]
  symbols: [DatabaseManager, FileUtils, BatchOperationManager, MaintenanceManager, ThumbnailGenerator, NFOImporter]
---

# Utils 模块 (`utils/`)

`utils/` 包是 GUI 版本和所有爬虫/维护脚本使用的共享工具层。它提供数据库访问、文件操作、批处理等功能。

## 核心模块

### `database.py` — `DatabaseManager`
基于 SQLite 的核心数据库抽象：
- `connect()` / `close()` — 连接管理，启用 `PRAGMA foreign_keys = ON`
- `init_database()` — 创建 `actors`、`video_actors` 表及索引
- `execute_query()` / `execute_update()` / `execute_many()` — 通用查询封装
- `get_videos(limit, offset, where_clause, params, order_by)` — 支持分页的视频列表，采用列安全的 SELECT（对可选列使用 `COALESCE`）
- 索引：`file_path`、`md5_hash`、`file_hash`、`title`、`tags`、`year`

### `db.py` — 底层数据库辅助工具
用于直接操作 SQLite 的简化函数：
- `get_connection(base_dir)` — 返回带有 `Row` 工厂的连接
- `upsert_actors(conn, actors)` — 插入或获取演员 ID
- `link_video_actor(conn, video_id, actor_id, actor_name)` — 多对多关联
- `upsert_tags(conn, tags)` — 从 `javdb_tags` 插入或获取标签 ID
- `upsert_jav_info(conn, video_id, info)` — 插入或更新 JAV 元数据（番号、标题、描述、评分、封面、发行日期）

### `file_utils.py` — `FileUtils`
文件操作工具：
- 智能文件移动（同磁盘重命名 / 跨磁盘复制+删除）
- 长文件名自动截断
- 带缓存的 MD5 计算
- 视频文件元数据提取（分辨率、时长、编码格式）

### `batch_ops.py` — `BatchOperationManager`
用于批量数据库操作的批处理编排。

### `maintenance.py` — `MaintenanceManager`
数据库维护：清理、优化、索引重建。

### `media_extensions.py` — 业务逻辑扩展
从 `media_library.py` 中提取的核心业务功能：
- `NFOImporter` — 导入 NFO 元数据文件（封面、演员、年份、字段映射）
- 去重逻辑
- 自动打标签（基于规则）
- 数据库迁移辅助工具

### `thumbnails.py` — `ThumbnailGenerator`
使用 ffmpeg 生成视频缩略图/封面：
- `get_ffmpeg_command()` — 跨平台 ffmpeg 路径解析（内置 → homebrew → PATH）
- 提取封面图像的视频帧

### `video_rotate.py`
视频旋转/校正工具。

## 基础架构模块

### `runtime.py` — 路径解析
用于定位运行时文件的关键模块：
- `runtime_dir()` — 基础目录（来自 `sys.argv[0]` 或冻结的可执行文件路径）
- `resource_dir()` — 资源目录（脚本与 runtime 相同，PyInstaller 为 `_MEIPASS`）
- `runtime_path(*parts)` — 拼接相对于 runtime 目录的路径
- `ensure_file_in_runtime(relative_path)` — 如果资源缺失，则将其复制到 runtime 目录

> **重要提示**：两个 GUI 版本都会操作 `sys.argv[0]`，以将 `runtime_dir()` 锚定到项目根目录。这确保了无论入口点是什么，`media_library.db` 和 `gui_config.json` 都能正确解析。

### `logger.py` — 日志系统
双输出日志（控制台 + GUI）：
- `LogLevel` 枚举：DEBUG、INFO、WARNING、ERROR、CRITICAL
- `get_logger(name)` — 命名日志记录器工厂
- `set_log_level(level)` — 全局级别控制
- 每个日志函数都接受可选的 `gui_log_func` 以进行 GUI 集成

### `progress_manager.py` — `ThreadedProgress`
用于长时间操作的线程安全进度跟踪。

### `progress.py`
轻量级进度回调封装。

## 集成模块

### `jav.py`
JAV 专用工具（番号解析、标准化）。

### `javsp_copy.py`
JavSP“复制到”功能 — 将 JavSP 结果复制到媒体库中。

### `javsp_migration.py`
用于 JavSP 数据格式的迁移工具。

### `javsp_integration.py`
轻量级封装，从根级别的 `javsp_integration.py` 重新导出。

### `hash.py`
哈希计算工具（封装 `hashlib`）。

### `metadata.py`
元数据提取辅助工具。

### `filesystem.py`
文件系统操作辅助工具。

### `code_extractor.py`
从文件名中提取视频番号。

## 另请参阅

- [其他目录概述](overview.md) — 所有支持目录
- [数据库概述](../database/overview.md) — 数据库架构与管理
- [主应用概述](../main_application/overview.md) — 工具的使用方式