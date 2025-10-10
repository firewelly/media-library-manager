# 归档（Obsolete）脚本

此目录用于存放已被新功能替代的脚本，保留以便参考历史实现。

归档原因：`javdb_actor_profile_repair.py` 已整合并增强以下功能：
- 规范化与修复 `profile_url`（统一到 `javdb.com`，非 JavDB 链接通过搜索修复）
- 基于 `profile_url` 的重复演员合并（以最近爬取记录为主，合并别名并删除重复）
- 对已有 JavDB 链接但头像为空的记录，基于 `profile_url` 补抓头像

归档脚本（移动于此）：
- merge_duplicate_actors.py
- merge_duplicate_actors_enhance.py
- actors_one_off_pipeline.py

如需恢复使用，可从此目录移回根目录。但建议优先使用 `javdb_actor_profile_repair.py`。