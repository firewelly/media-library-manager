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
- `ThumbnailGenerator.get_ffmpeg_command() -> Optional[str]` 获取 FFmpeg 路径。
- `ThumbnailGenerator.detect_gpu_acceleration() -> Optional[str]` 检测 GPU 加速 (videotoolbox/d3d11va)。
- `ThumbnailGenerator.generate_thumbnail(video_path, output_path, seek_time="00:00:10") -> bool` 生成缩略图。

## batch_ops (New in v2.0)
`BatchOperationManager` 类提供批量操作接口：
- `batch_calculate_md5(video_ids, progress_callback, cancel_check) -> Dict` 批量计算 MD5。
- `batch_import_nfo(video_ids, filter_no_actors, ...) -> Dict` 批量导入 NFO。
- `batch_import_javdb(video_ids, filter_no_title, ...) -> Dict` 批量获取 JavDB 信息。
- `batch_clean_filenames(video_ids, ...) -> Dict` 批量清理文件名。
- `batch_move_files(video_ids, target_dir, ...) -> Dict` 批量移动文件。
- `batch_generate_thumbnails(video_ids, force, ...) -> Dict` 批量生成缩略图。

## maintenance (New in v2.0)
`MaintenanceManager` 类提供系统维护功能：
- `find_duplicates(criteria='md5') -> List[Dict]` 查找重复文件。
- `clean_actor_data() -> Dict` 清理无效演员数据。
- `sync_stars_to_filename(video_ids, ...) -> Dict` 同步星级到文件名 (添加 ! 前缀)。
- `scan_for_file_move(source_dir, ...) -> List[Dict]` 扫描目录用于文件移动管理器。

## jav
- `extract_code(filename) -> Optional[str]` 番号提取（优先 `code_extractor`）。
- `search_movie_info(code) -> Optional[dict]` 使用 `JavSPIntegration` 搜索。
- `save_movie_info_to_db(conn, video_id, info) -> bool` 保存到数据库。
- `batch_fetch_and_save(conn, video_ids, code_getter, progress_cb=None)` 批量处理。
- `fix_error_titles(conn, titles, search_from_title, progress_cb=None)` 错误标题修复占位。
