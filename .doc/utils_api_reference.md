# utils 包接口参考
 - 版本: 开发版
 - 最后更新: 2025-11-29
 - 适用系统: Windows/macOS/Linux

## logging
- `set_log_level(level)` 设置日志级别。
- `output_log(level, message, sink=None)` 输出日志到控制台与可选 GUI sink。

## progress
- `ProgressState` 进度数据类。
- `ProgressUpdateManager(cb)` 创建进度管理器，`update(**kwargs)` 更新并回调。

## db
- `get_connection(base_dir) -> Connection` 连接现有数据库。
- `upsert_actors(conn, actors) -> List[int]` 根据名字插入/获取演员ID。
- `link_video_actor(conn, video_id, actor_id, actor_name)` 建立视频-演员关联。
- `upsert_tags(conn, tags) -> List[int]` 插入/获取标签ID。
- `upsert_jav_info(conn, video_id, info) -> int` 插入或更新 `javdb_info` 并维护标签/演员关联。

## filesystem
- `walk_videos(folders, exts=None) -> List[str]` 遍历收集视频文件路径。
- `open_file_cross_platform(path)` 跨平台打开文件。

## hash
- `calculate_md5(path, chunk_size=4MB) -> str` 流式计算 MD5。

## metadata
- `process_filename(name) -> str` 去扩展名。
- `extract_title(name) -> str` 提取标题占位实现。
- `parse_stars(name) -> int` 星级占位实现。
- `get_video_media_info(path) -> (duration, resolution)` 媒体信息占位实现。

## thumbnails
- `generate_thumbnail(path, timepoint=None)` 缩略图占位实现。

## jav
- `extract_code(filename) -> Optional[str]` 番号提取（优先 `code_extractor`）。
- `search_movie_info(code) -> Optional[dict]` 使用 `JavSPIntegration` 搜索。
- `save_movie_info_to_db(conn, video_id, info) -> bool` 保存到数据库。
- `batch_fetch_and_save(conn, video_ids, code_getter, progress_cb=None)` 批量处理。
- `fix_error_titles(conn, titles, search_from_title, progress_cb=None)` 错误标题修复占位。
