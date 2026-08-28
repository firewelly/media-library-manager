# 文件

- [迁移脚本](migration_scripts.md) - 介绍数据库迁移脚本——模式扩展（database_extension.py）、NAS 文件迁移（migrate_av_to_nas.py）、旧视频迁移（migrate_old_videos.py）以及演员记录清理。
- [数据库概述](overview.md) - 记录 SQLite 数据库架构、DatabaseManager 类、索引策略以及关键表（videos、actors、video_actors、javdb_info、javdb_tags、folders）。
- [同步脚本](synchronization_scripts.md) - 介绍数据库同步工具——基于文件名的双向同步 (sync_db_by_filename.py)、NAS JavDB 更新器，以及用于保持数据库与实际文件一致的智能媒体更新器。
