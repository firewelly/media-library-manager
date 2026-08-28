---
type: 参考
title: 迁移脚本
description: 介绍数据库迁移脚本——模式扩展（database_extension.py）、NAS 文件迁移（migrate_av_to_nas.py）、旧视频迁移（migrate_old_videos.py）以及演员记录清理。
openwiki:
  roles: [delivery]
  source_paths: [database_extension.py, migrate_av_to_nas.py, migrate_old_videos.py, doc/演员记录清理合并指南.md]
---

# 迁移脚本

用于演进数据库模式、在不同存储位置之间迁移文件以及清理演员记录的脚本。

## 模式扩展

### `database_extension.py`
将 JavDB 相关的表添加到现有数据库：
- `actors` 表（包含扩展字段：`name_en`、`name_traditional` 等）
- `video_actors` 关联表
- `javdb_info` 表
- `javdb_tags` 和 `javdb_info_tags` 表
- 使用 `CREATE TABLE IF NOT EXISTS` —— 可安全地多次运行

在从 JavDB 之前的模式升级到当前模式时运行。

## 文件迁移

### `migrate_av_to_nas.py`
将本地 AV 库视频迁移到 NAS 存储：
- **收藏演员** (`is_favorite=1`) -> `/Volumes/Video/usr/<normalized_folder>/`
- **常规演员** -> `/Volumes/Video/JAV/<normalized_folder>/`
- 演员到文件夹的映射在 `merge.conf` 中定义（以制表符分隔：文件夹名称 + 别名）
- 进度记录在 `.migration_av_progress.txt` 中以便恢复
- 需要已挂载 NAS 挂载点（`/Volumes/Video`）

### `migrate_old_videos.py`
将旧的未评级本地非 JAV 视频迁移到目标文件夹：
- 来源：`folders` 表中 `id=9` 和 `id=10` 的文件夹
- 目标：`folders` 表中 `id=14` 的文件夹
- 过滤条件：`file_created_time <= 2025-12-31` 且 `stars IS NULL OR stars = 0`
- **MD5 冲突解决**：MD5 相同 -> 删除源文件和数据库记录；MD5 不同 -> 使用 `_dupN` 后缀重命名
- 使用 `utils.FileUtils` 进行跨设备移动和文件名长度处理
- 默认试运行；使用 `--execute` 实际移动文件

## 用法

```bash
# 模式扩展（一次性）
python database_extension.py

# 预览 NAS 迁移（试运行）
python migrate_av_to_nas.py

# 预览旧视频迁移
python migrate_old_videos.py

# 执行迁移
python migrate_old_videos.py --execute

# 限制测试数量
python migrate_old_videos.py --limit 20
```

## 另请参阅

- [数据库概述](overview.md) — 模式参考
- [同步脚本](synchronization_scripts.md) — 持续同步（非一次性迁移）
- [配置](../configuration/overview.md) — `merge.conf` 格式