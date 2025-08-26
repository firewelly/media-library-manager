# Media Library Functions Documentation

## Database Functions

### init_database()
**功能**: 初始化媒体库数据库，创建所有必要的表结构
**输入**: 无
**输出**: 无（直接操作数据库）
**调用格式**: `init_database()`

### create_tables()
**功能**: 创建媒体库所需的所有数据库表
**输入**: cursor对象（数据库游标）
**输出**: 无
**调用格式**: `create_tables(cursor)`

### setup_indexes()
**功能**: 为数据库表创建索引以优化查询性能
**输入**: cursor对象
**输出**: 无
**调用格式**: `setup_indexes(cursor)`

## Utility Functions

### format_duration(duration_seconds)
**功能**: 将秒数格式化为易读的时间字符串
**输入**: duration_seconds (int) - 视频时长（秒）
**输出**: str - 格式化后的时间字符串（如"1h 23m 45s"）
**调用格式**: `format_duration(5025)` → `"1h 23m 45s"`

### calculate_file_hash(file_path)
**功能**: 计算文件的MD5哈希值
**输入**: file_path (str) - 文件完整路径
**输出**: str - 32位MD5哈希值字符串
**调用格式**: `calculate_file_hash("/path/to/video.mp4")` → `"a1b2c3d4e5f6..."`

### get_video_info(file_path)
**功能**: 获取视频的时长和分辨率信息
**输入**: file_path (str) - 视频文件路径
**输出**: tuple - (duration_seconds, resolution_string)
**调用格式**: `get_video_info("/path/to/video.mp4")` → `(3600, "1920x1080")`

### parse_title_from_filename(filename)
**功能**: 从文件名中解析视频标题（移除扩展名和特殊字符）
**输入**: filename (str) - 原始文件名
**输出**: str - 清理后的标题
**调用格式**: `parse_title_from_filename("Movie_Name_2024.mp4")` → `"Movie Name 2024"`

### parse_stars_from_filename(filename)
**功能**: 从文件名中解析星级评分（基于感叹号数量）
**输入**: filename (str) - 文件名
**输出**: int - 星级评分（1-5）
**调用格式**: `parse_stars_from_filename("!!movie.mp4")` → `3`

### is_video_online(video_id)
**功能**: 检查视频文件是否存在于文件系统中
**输入**: video_id (int) - 数据库中的视频ID
**输出**: bool - 文件是否在线
**调用格式**: `is_video_online(123)` → `True/False`

## File Management Functions

### comprehensive_update()
**功能**: 智能更新媒体库，扫描新文件、处理文件移动、清理无效记录
**输入**: 无（通过GUI调用）
**输出**: 无（更新数据库并显示进度窗口）
**调用格式**: `comprehensive_update()`

### add_folder()
**功能**: 添加新的监控文件夹到媒体库
**输入**: 无（通过GUI文件选择器）
**输出**: 无（更新数据库和文件夹列表）
**调用格式**: `add_folder()`

### remove_folder(folder_path)
**功能**: 从媒体库中移除指定的监控文件夹
**输入**: folder_path (str) - 要移除的文件夹路径
**输出**: 无（更新数据库）
**调用格式**: `remove_folder("/path/to/folder")`

### toggle_folder_status(folder_path)
**功能**: 切换文件夹的启用/禁用状态
**输入**: folder_path (str) - 文件夹路径
**输出**: 无（更新数据库状态）
**调用格式**: `toggle_folder_status("/path/to/folder")`

### batch_move_files_to_folder(video_ids, target_folder)
**功能**: 批量将视频文件移动到指定文件夹
**输入**: 
- video_ids (list[int]) - 要移动的视频ID列表
- target_folder (str) - 目标文件夹路径
**输出**: 无（移动文件并更新数据库）
**调用格式**: `batch_move_files_to_folder([1,2,3], "/new/folder")`

### batch_delete_selected_videos()
**功能**: 批量删除选中的视频文件和数据库记录
**输入**: 无（通过GUI选择）
**输出**: 无（删除文件和数据库记录）
**调用格式**: `batch_delete_selected_videos()`

### remove_duplicates()
**功能**: 基于文件哈希值移除重复的视频文件
**输入**: 无（通过GUI调用）
**输出**: 无（删除重复文件并更新数据库）
**调用格式**: `remove_duplicates()`

### sync_stars_to_filename()
**功能**: 将数据库中的星级评分同步到文件名
**输入**: 无（通过GUI调用）
**输出**: 无（重命名文件并更新数据库）
**调用格式**: `sync_stars_to_filename()`

## Thumbnail Functions

### generate_thumbnail(video_path, output_path)
**功能**: 为视频文件生成缩略图
**输入**: 
- video_path (str) - 视频文件路径
- output_path (str) - 缩略图输出路径
**输出**: bool - 是否生成成功
**调用格式**: `generate_thumbnail("/video.mp4", "/thumb.jpg")` → `True`

### batch_generate_thumbnails()
**功能**: 批量为所有视频生成缩略图
**输入**: 无（通过GUI调用）
**输出**: 无（生成缩略图并存储到数据库）
**调用格式**: `batch_generate_thumbnails()`

### get_thumbnail_data(video_id)
**功能**: 从数据库获取视频的缩略图数据
**输入**: video_id (int) - 视频ID
**输出**: bytes - 缩略图的二进制数据
**调用格式**: `get_thumbnail_data(123)` → `b'...'`

## Search and Filter Functions

### search_videos(query)
**功能**: 根据关键词搜索视频
**输入**: query (str) - 搜索关键词
**输出**: list[tuple] - 匹配的视频记录列表
**调用格式**: `search_videos("keyword")` → `[(id, title, ...), ...]`

### filter_videos_by_stars(min_stars, max_stars)
**功能**: 根据星级范围过滤视频
**输入**: 
- min_stars (int) - 最低星级
- max_stars (int) - 最高星级
**输出**: list[tuple] - 过滤后的视频列表
**调用格式**: `filter_videos_by_stars(3, 5)` → `[(id, title, stars), ...]`

### filter_videos_by_tags(tags)
**功能**: 根据标签过滤视频
**输入**: tags (list[str]) - 标签列表
**输出**: list[tuple] - 包含所有指定标签的视频列表
**调用格式**: `filter_videos_by_tags(["action", "2024"])` → `[(id, title, tags), ...]`

### sort_videos(column, reverse=False)
**功能**: 按指定列对视频列表进行排序
**输入**: 
- column (str) - 排序列名（"title", "file_size", "stars", "created_at"）
- reverse (bool) - 是否降序排序
**输出**: 无（更新GUI显示）
**调用格式**: `sort_videos("file_size", True)`

## Metadata Functions

### update_single_file_metadata(video_id)
**功能**: 更新单个视频文件的元数据信息
**输入**: video_id (int) - 要更新的视频ID
**输出**: 无（更新数据库记录）
**调用格式**: `update_single_file_metadata(123)`

### batch_update_metadata_selected_videos()
**功能**: 批量更新选中视频的元数据
**输入**: 无（通过GUI选择）
**输出**: 无（更新数据库记录）
**调用格式**: `batch_update_metadata_selected_videos()`

### reimport_metadata_for_incomplete_videos()
**功能**: 重新导入元数据信息不完整的视频
**输入**: 无（通过GUI调用）
**输出**: 无（更新数据库记录）
**调用格式**: `reimport_metadata_for_incomplete_videos()`

### full_database_reset()
**功能**: 重置整个数据库，重新扫描所有文件
**输入**: 无（通过GUI确认）
**输出**: 无（重置数据库并重新导入）
**调用格式**: `full_database_reset()`

## Tag Management Functions

### manage_tags()
**功能**: 打开标签管理界面，管理所有标签
**输入**: 无（通过GUI调用）
**输出**: 无（显示标签管理窗口）
**调用格式**: `manage_tags()`

### add_tag_to_video(video_id, tag_name)
**功能**: 为指定视频添加标签
**输入**: 
- video_id (int) - 视频ID
- tag_name (str) - 标签名称
**输出**: 无（更新数据库）
**调用格式**: `add_tag_to_video(123, "action")`

### remove_tag_from_video(video_id, tag_name)
**功能**: 从指定视频移除标签
**输入**: 
- video_id (int) - 视频ID
- tag_name (str) - 标签名称
**输出**: 无（更新数据库）
**调用格式**: `remove_tag_from_video(123, "action")`

### get_all_tags()
**功能**: 获取数据库中所有标签列表
**输入**: 无
**输出**: list[str] - 标签名称列表
**调用格式**: `get_all_tags()` → `["action", "2024", "drama"]`

### get_video_tags(video_id)
**功能**: 获取指定视频的所有标签
**输入**: video_id (int) - 视频ID
**输出**: list[str] - 该视频的标签列表
**调用格式**: `get_video_tags(123)` → `["action", "2024"]`

### rename_tag(old_name, new_name)
**功能**: 重命名标签
**输入**: 
- old_name (str) - 原标签名称
- new_name (str) - 新标签名称
**输出**: 无（更新数据库）
**调用格式**: `rename_tag("action", "action-movie")`

### delete_tag(tag_name)
**功能**: 删除标签及其所有关联关系
**输入**: tag_name (str) - 要删除的标签名称
**输出**: 无（更新数据库）
**调用格式**: `delete_tag("old-tag")`

## Video Content Analysis Functions

### auto_tag_selected_videos()
**功能**: 自动分析选中视频内容并生成标签
**输入**: 无（通过GUI选择）
**输出**: 无（分析视频并更新数据库标签）
**调用格式**: `auto_tag_selected_videos()`

### batch_auto_tag_all()
**功能**: 批量分析所有视频内容并生成标签
**输入**: 无（通过GUI调用）
**输出**: 无（分析所有视频并更新数据库标签）
**调用格式**: `batch_auto_tag_all()`

### batch_auto_tag_no_tags()
**功能**: 批量分析无标签视频内容并生成标签
**输入**: 无（通过GUI调用）
**输出**: 无（分析无标签视频并更新数据库标签）
**调用格式**: `batch_auto_tag_no_tags()`

### run_video_content_analyzer(video_path)
**功能**: 运行视频内容分析器，分析视频内容
**输入**: video_path (str) - 视频文件路径
**输出**: list[str] - 生成的标签列表
**调用格式**: `run_video_content_analyzer("/video.mp4")` → `["outdoor", "daytime", "action"]`

### analyze_video_content(video_id)
**功能**: 分析指定视频的内容并更新标签
**输入**: video_id (int) - 视频ID
**输出**: 无（分析视频并更新数据库标签）
**调用格式**: `analyze_video_content(123)`

### merge_video_tags(video_id, new_tags)
**功能**: 合并新标签到视频的现有标签中
**输入**: 
- video_id (int) - 视频ID
- new_tags (list[str]) - 新标签列表
**输出**: 无（更新数据库标签）
**调用格式**: `merge_video_tags(123, ["outdoor", "daytime"])`

## JAVDB Information Functions

### fetch_javdb_info(video_id)
**功能**: 从JAVDB获取指定视频的详细信息
**输入**: video_id (int) - 视频ID
**输出**: 无（获取信息并更新数据库）
**调用格式**: `fetch_javdb_info(123)`

### fetch_current_javdb_info()
**功能**: 获取当前选中视频的JAVDB信息
**输入**: 无（通过GUI选择）
**输出**: 无（获取信息并更新数据库）
**调用格式**: `fetch_current_javdb_info()`

### batch_javdb_info_selected_videos()
**功能**: 批量获取选中视频的JAVDB信息
**输入**: 无（通过GUI选择）
**输出**: 无（批量获取信息并更新数据库）
**调用格式**: `batch_javdb_info_selected_videos()`

### save_javdb_info_to_db(video_id, javdb_data)
**功能**: 将JAVDB信息保存到数据库
**输入**: 
- video_id (int) - 视频ID
- javdb_data (dict) - JAVDB返回的数据字典
**输出**: 无（更新数据库记录）
**调用格式**: `save_javdb_info_to_db(123, {"title": "...", "release_date": "..."})`

### extract_code_from_filename(filename)
**功能**: 从文件名中提取JAV番号
**输入**: filename (str) - 文件名
**输出**: str - 提取的番号，未找到返回None
**调用格式**: `extract_code_from_filename("ABC-123.mp4")` → `"ABC-123"`

### update_javdb_actors(video_id, actors)
**功能**: 更新视频的JAVDB演员信息
**输入**: 
- video_id (int) - 视频ID
- actors (list[dict]) - 演员信息列表
**输出**: 无（更新数据库）
**调用格式**: `update_javdb_actors(123, [{"name": "Actor Name", "image_url": "..."}])`

### update_javdb_tags(video_id, tags)
**功能**: 更新视频的JAVDB标签信息
**输入**: 
- video_id (int) - 视频ID
- tags (list[str]) - JAVDB标签列表
**输出**: 无（更新数据库）
**调用格式**: `update_javdb_tags(123, ["tag1", "tag2"])`

### download_javdb_cover(cover_url, video_id)
**功能**: 下载JAVDB封面图片并保存到数据库
**输入**: 
- cover_url (str) - 封面图片URL
- video_id (int) - 视频ID
**输出**: 无（下载并保存封面图片）
**调用格式**: `download_javdb_cover("https://...", 123)`

## GUI Interface Functions

### show_context_menu(event)
**功能**: 显示右键菜单，提供视频操作选项
**输入**: event (tkinter.Event) - 鼠标右键事件
**输出**: 无（显示右键菜单）
**调用格式**: `show_context_menu(event)`

### on_video_double_click(event)
**功能**: 双击视频时播放或显示详情
**输入**: event (tkinter.Event) - 双击事件
**输出**: 无（播放视频或显示详情窗口）
**调用格式**: `on_video_double_click(event)`

### show_video_details(video_id)
**功能**: 显示视频的详细信息窗口
**输入**: video_id (int) - 视频ID
**输出**: 无（显示详情窗口）
**调用格式**: `show_video_details(123)`

### update_video_list()
**功能**: 刷新视频列表显示
**输入**: 无
**输出**: 无（更新GUI列表）
**调用格式**: `update_video_list()`

### show_progress_window(title, total_items)
**功能**: 显示进度窗口，用于长时间操作
**输入**: 
- title (str) - 窗口标题
- total_items (int) - 总项目数
**输出**: tkinter.Toplevel - 进度窗口对象
**调用格式**: `show_progress_window("Processing Videos", 100)`

### update_progress_window(progress_window, current, message)
**功能**: 更新进度窗口的进度和消息
**输入**: 
- progress_window (tkinter.Toplevel) - 进度窗口
- current (int) - 当前进度
- message (str) - 进度消息
**输出**: 无（更新进度显示）
**调用格式**: `update_progress_window(window, 50, "Processing...")`

### close_progress_window(progress_window)
**功能**: 关闭进度窗口
**输入**: progress_window (tkinter.Toplevel) - 要关闭的进度窗口
**输出**: 无
**调用格式**: `close_progress_window(window)`

## Batch Processing Functions

### batch_process_auto_tag(video_ids)
**功能**: 批量自动标签处理
**输入**: video_ids (list[int]) - 要处理的视频ID列表
**输出**: 无（处理完成后更新数据库）
**调用格式**: `batch_process_auto_tag([1,2,3,4,5])`

### batch_process_delete(video_ids)
**功能**: 批量删除视频文件和数据库记录
**输入**: video_ids (list[int]) - 要删除的视频ID列表
**输出**: 无（删除文件并更新数据库）
**调用格式**: `batch_process_delete([1,2,3])`

### batch_process_move(video_ids, target_folder)
**功能**: 批量移动视频文件到指定文件夹
**输入**: 
- video_ids (list[int]) - 要移动的视频ID列表
- target_folder (str) - 目标文件夹路径
**输出**: 无（移动文件并更新数据库）
**调用格式**: `batch_process_move([1,2,3], "/new/folder")`

### batch_process_javdb_info(video_ids)
**功能**: 批量获取JAVDB信息
**输入**: video_ids (list[int]) - 要获取信息的视频ID列表
**输出**: 无（获取信息并更新数据库）
**调用格式**: `batch_process_javdb_info([1,2,3,4,5])`

### process_batch_with_progress(process_func, items, *args)
**功能**: 带进度显示的批量处理函数
**输入**: 
- process_func (function) - 处理函数
- items (list) - 要处理的项目列表
- *args - 传递给处理函数的额外参数
**输出**: 无（处理完成后显示结果）
**调用格式**: `process_batch_with_progress(batch_process_auto_tag, video_ids)`

## System Configuration Functions

### load_config()
**功能**: 加载系统配置文件
**输入**: 无
**输出**: dict - 配置字典
**调用格式**: `load_config()` → `{"theme": "dark", "language": "zh"}`

### save_config(config)
**功能**: 保存系统配置到文件
**输入**: config (dict) - 配置字典
**输出**: 无
**调用格式**: `save_config({"theme": "light", "language": "en"})`

### get_default_folders()
**功能**: 获取默认监控文件夹列表
**输入**: 无
**输出**: list[str] - 默认文件夹路径列表
**调用格式**: `get_default_folders()` → `["/Users/videos", "/Users/movies"]`

### set_default_folders(folders)
**功能**: 设置默认监控文件夹
**输入**: folders (list[str]) - 文件夹路径列表
**输出**: 无
**调用格式**: `set_default_folders(["/path/to/folder1", "/path/to/folder2"])`

## Error Handling Functions

### log_error(error_message, function_name)
**功能**: 记录错误信息到日志文件
**输入**: 
- error_message (str) - 错误消息
- function_name (str) - 发生错误的函数名
**输出**: 无
**调用格式**: `log_error("File not found", "update_metadata")`

### show_error_dialog(message, title="Error")
**功能**: 显示错误对话框
**输入**: 
- message (str) - 错误消息
- title (str) - 对话框标题（可选）
**输出**: 无
**调用格式**: `show_error_dialog("Failed to load video", "Error")`

### show_info_dialog(message, title="Info")
**功能**: 显示信息对话框
**输入**: 
- message (str) - 信息消息
- title (str) - 对话框标题（可选）
**输出**: 无
**调用格式**: `show_info_dialog("Processing complete", "Success")`

### show_confirmation_dialog(message, title="Confirm")
**功能**: 显示确认对话框
**输入**: 
- message (str) - 确认消息
- title (str) - 对话框标题（可选）
**输出**: bool - 用户是否确认
**调用格式**: `show_confirmation_dialog("Delete selected videos?")` → `True/False`