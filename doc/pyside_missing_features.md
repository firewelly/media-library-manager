# `media_library_pyside.py` vs `media_library.py` 功能差异对比报告

> **状态更新 (2025-12-27)**: 所有核心缺失功能已在 v2.0.0 版本中补全。本报告仅作历史参考。

通过对比 PySide 版本（新版）与 Tkinter 版本（旧版）的代码结构与实现，发现 PySide 版本目前主要集中在核心功能的重构（如播放、搜索、基础管理），但在**批量处理**、**文件高级管理**及**特定工具集**方面存在大量功能缺失或仅预留了 UI 接口但未实现逻辑。

以下是详细的差异对比：

## 1. 批量操作 (Batch Operations)

| 功能名称 | 原始版本 (Tkinter) | PySide 版本 (Qt) | 状态 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| **批量计算 MD5** | `batch_calculate_md5` | `on_batch_calculate_md5` | ✅ 已实现 | 调用 `utils.batch_ops.batch_calculate_md5` |
| **批量导入 NFO (无演员)** | `batch_import_nfo_for_no_actors` | `on_batch_import_nfo_for_no_actors` | ✅ 已实现 | 调用 `utils.batch_ops.batch_import_nfo` |
| **批量导入 JavDB (无标题)** | `batch_import_javdb_for_no_title` | `on_batch_import_javdb_for_no_title` | ✅ 已实现 | 调用 `utils.batch_ops.batch_import_javdb` |
| **批量更新视频元数据** | `batch_update_videos` | 缺失 | ⚠️ 待评估 | 部分功能通过批量 NFO/JavDB 导入实现 |
| **批量移动文件** | `batch_move_files_to_folder` | `batch_move_files_to_folder` | ✅ 已实现 | 上下文菜单中支持 |
| **批量清理文件名** | `batch_clean_filename_selected_videos` | `batch_clean_filename_selected` | ✅ 已实现 | 上下文菜单中支持 |
| **批量自动打标签** | `batch_auto_tag_selected_videos` | `batch_auto_tag_selected` | ✅ 已实现 | 上下文菜单中支持 |
| **批量生成缩略图** | `batch_generate_thumbnails` | 缺失 | ⚠️ 间接支持 | 可通过刷新封面实现，或后续添加独立入口 |

## 2. 文件与目录管理 (File & Folder Management)

| 功能名称 | 原始版本 (Tkinter) | PySide 版本 (Qt) | 状态 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| **文件移动管理器** | `file_move_manager` | `on_file_move_manager` | ✅ 已实现 | 实现了新的 `FileMoveDialog` |
| **智能去重** | `smart_remove_duplicates` | `on_smart_remove_duplicates` | ✅ 已实现 | 基础逻辑已集成 |
| **普通去重** | `remove_duplicates` | `on_remove_duplicates` | ✅ 已实现 | 调用 `MaintenanceManager` |
| **同步星级到文件名** | `sync_stars_to_filename` | `on_sync_stars_to_filename` | ✅ 已实现 | 调用 `MaintenanceManager` |
| **JavSP 文件迁移** | `migrate_javsp_file_to_library` | 右键菜单支持 | ✅ 已实现 | 支持批量迁移和复制 |

## 3. 高级工具与维护 (Advanced Tools)

| 功能名称 | 原始版本 (Tkinter) | PySide 版本 (Qt) | 状态 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| **演员数据清洗** | `clean_actor_data` | `MaintenanceManager.clean_actor_data` | ✅ 后端已实现 | UI入口待添加或整合 |
| **视频内容分析器** | `run_video_content_analyzer` | 缺失 | ❌ 缺失 | 深度分析功能暂未移植 |
| **MD5 缓存管理** | 完整的缓存加载/保存/清理 | 简化/缺失 | ⚠️ 需确认 | 旧版有 `load_md5_cache`, `save_md5_cache` 等独立管理逻辑 |

## 4. UI 交互与细节 (UI/UX)

| 功能名称 | 原始版本 (Tkinter) | PySide 版本 (Qt) | 状态 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| **列拖拽排序** | 支持 (`setup_column_drag`) | 依赖 Qt 原生 | ⚠️ 需确认 | 需确认是否实现了列顺序的持久化保存 (`save_column_config`) |
| **右键菜单功能** | 丰富 (包含大量批量操作) | 增强版 | ✅ 已实现 | 已支持多选操作和批量功能 |

## 建议后续任务 (Suggested Tasks)

根据上述分析，建议按照以下优先级创建开发任务：

1.  **补全基础维护工具**: 实现 `去重` (Smart/Normal) 和 `文件移动管理器`，因为 UI 入口已存在。 (已完成)
2.  **实现批量操作框架**: 移植 `batch_update_videos`, `batch_move_files_to_folder` 等高频使用的批量功能。 (已完成)
3.  **完善元数据工具**: 实现 `batch_import_nfo` 和 `sync_stars_to_filename`。 (已完成)
4.  **迁移高级工具**: 根据需求决定是否迁移 `JavSP` 迁移工具和 `演员数据清洗` 工具。 (JavSP迁移已完成)
