# 架构总览（PySide6 整合版）
 - 版本: 开发版
 - 最后更新: 2025-11-29
 - 适用系统: Windows/macOS/Linux

## 目标
- 保持原有 `media_library.py` 不变，功能抽象为 `utils/` 包供 GUI 调用。
- 在 `media_library_pyside.py` 接入扫描、索引、封面、去重、JAV 信息抓取与保存等功能。

## 组件
- GUI：`media_library_pyside.py`
  - `MainWindow` 主界面，菜单、列表、详情、状态栏。
  - `JavInfoDialog` 面板，手动输入番号搜索与保存。
  - 详情页按钮“获取JAV信息”与菜单“批量导入JAV信息”接入服务层。
- 服务：`utils/`
  - `logging.py` 日志输出与级别控制。
  - `progress.py` 通用进度管理与回调。
  - `db.py` 数据库连接与 JAV 信息/标签/演员关联维护。
  - `filesystem.py` 媒体文件遍历与打开。
  - `hash.py` 文件 MD5 计算。
  - `metadata.py` 文件名处理与媒体信息占位。
  - `thumbnails.py` 缩略图占位实现。
  - `jav.py` 番号提取、JavSP 搜索、保存与批处理。

## 数据库
- 仍使用现有 `media_library.db`，PySide6 仅连接不建表、不迁移。

## 关键调用链
- 详情页“获取JAV信息” → `utils.jav.extract_code` → `utils.jav.search_movie_info` → `utils.jav.save_movie_info_to_db` → 刷新列表。
- 菜单“批量导入JAV信息” → 查询无标题视频 → 循环调用上述流程并显示进度。
