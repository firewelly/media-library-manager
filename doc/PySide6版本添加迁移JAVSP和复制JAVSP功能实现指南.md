# PySide6版本迁移JAVSP和复制JAVSP功能实现说明

## 状态：已实现 (v2.0.0)

本功能已在 v2.0.0 版本中完全实现。PySide6 版本的媒体库管理器现在具备与原版对齐的"迁移JAVSP到"和"复制JAVSP到"功能，并支持批量操作。

## 功能概述

### 1. 单文件操作
在视频列表右键菜单中，选择：
- **迁移JavSP到...**: 将视频文件及其关联的 JavSP 元数据文件移动到选定的在线库文件夹。
- **复制JavSP到...**: 将视频文件及其关联的 JavSP 元数据文件复制到选定的在线库文件夹。

### 2. 批量操作
选中多个视频文件后，右键菜单提供：
- **批量迁移JavSP到...**: 批量处理选中的视频。
- **批量复制JavSP到...**: 批量处理选中的视频。

### 3. 在线文件夹检测
系统会自动检测 `folders` 表中标记为 `is_active=1` 且实际路径存在的文件夹，并在菜单中列出。对于 NAS 挂载路径，会显示完整路径；对于普通路径，显示最后两级目录以便识别。

## 技术实现细节

该功能基于 `utils.batch_ops` 和 `utils.javsp_integration` 实现。

- **核心逻辑**: 
  - `media_library_pyside.py` 中的 `batch_migrate_javsp_selected` 方法负责收集选中的视频 ID。
  - 通过 `GenericWorker` 在后台线程执行迁移/复制任务，避免阻塞 UI。
  - 底层调用 `javsp_integration` 模块执行实际的文件移动和数据库更新。

- **UI 交互**:
  - 动态生成的右键菜单，根据当前在线文件夹列表实时刷新。
  - 操作前会弹出确认对话框，显示将要处理的文件数量和目标路径。
  - 操作过程中显示进度条，结束后显示成功/失败统计。

## 相关代码引用

- `media_library_pyside.py`: `show_context_menu`, `batch_migrate_javsp_selected`
- `utils/batch_ops.py`: `BatchOperationManager`
- `utils/javsp_integration.py`: JavSP 集成包装器
