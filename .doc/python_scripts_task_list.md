# Python脚本任务列表

## 概述
本文档提供了media目录下所有Python脚本的任务列表，包括每个脚本的功能描述、调用方法和参数说明，并按照是否被media_library.py调用进行了分类组织。

## 功能检索表（按media_library.py调用关系分类）

### 第一类：被media_library.py调用的脚本

#### 数据库相关
- `init_database.py` - 初始化数据库结构
- `database_extension.py` - 扩展数据库功能
- `merge_duplicate_actors.py` - 处理重复演员记录
- `merge_duplicate_actors_enhance.py` - 增强版演员去重处理
- `extend_actors_table.py` - 扩展演员表结构

#### 爬虫与数据获取
- `javdb_actor_all.py` - 批量爬取JavDB演员信息
- `javdb_crawler.py` - JavDB通用爬虫
- `javdb_crawler_single.py` - 单个JavDB资源爬取
- `actor_crawler_with_db.py` - 带数据库支持的演员爬虫
- `actor_detail_crawler.py` - 演员详细信息爬虫
- `search_and_crawl_actors.py` - 搜索并爬取演员信息

#### 视频处理与分析
- `batch_video_analyzer_enhanced.py` - 增强版批量视频分析
- `video_content_analyzer.py` - 视频内容分析
- `video_integrity_checker.py` - 视频完整性检查
- `batch_video_integrity_checker.py` - 批量视频完整性检查
- `resumable_smart_importer.py` - 支持断点续传的智能视频导入
- `fast_import_from_md5.py` - 通过MD5快速导入视频
- `import_videos_from_md5.py` - 从MD5导入视频信息
- `check_invalid_records.py` - 检查无效记录

#### 元数据与标签处理
- `title_analysis.py` - 视频标题分析
- `batch_title_cleanup.py` - 批量标题清理
- `update_tags_from_csv.py` - 从CSV更新标签
- `update_video_descriptions.py` - 更新视频描述
- `clean_duplicate_tags.py` - 清理重复标签
- `auto_clean_tags.py` - 自动标签清理
- `video_tagging.py` - 视频标签添加
- `code_extractor.py` - 编码提取
- `enhanced_code_extractor.py` - 增强版编码提取

### 第二类：不被media_library.py直接调用的脚本

#### 爬虫与数据获取
- `javdb_actor_stream.py` - 流式处理JavDB演员数据
- `actor_crawler_headless_db.py` - 无头模式演员爬虫
- `javbus_crawler_single.py` - JavBus单资源爬取
- `update_msedge_driver.py` - 更新Edge驱动

#### 视频处理与分析
- `video_multimodal_analyzer.py` - 多模态视频分析
- `delete_small_videos.py` - 删除小视频
- `recalculate_md5.py` - 重新计算MD5
- `reprocess_failed_videos.py` - 重新处理失败视频
- `video_subtitle_extractor.py` - 视频字幕提取

#### 实用工具
- `cfn4.py` - 特定格式处理工具
- `batch_update_actors.py` - 批量更新演员
- `cleanup_image_cache.py` - 清理图像缓存
- `edge_cookie_reader.py` - Edge Cookie读取器
- `fix_dot_cleanup.py` - 修复文件名点号
- `fix_duplicate_detection.py` - 修复重复检测
- `fix_missing_avatars.py` - 修复缺失头像
- `find_duplicate_videos.py` - 查找重复视频
- `merge_analysis_results.py` - 合并分析结果
- `smart_video_updater.py` - 智能视频更新
- `unified_video_updater.py` - 统一视频更新
- `comprehensive_tag_cleaner.py` - 全面标签清理

#### 配置与辅助
- `config.py` - 主配置文件
- `config.json` - JSON配置文件
- `javsp_config.py` - JavaSP配置
- `javsp_config.yaml` - YAML格式JavaSP配置
- `javsp_config_manager.py` - 管理JavaSP配置
- `gui_config.json` - GUI配置文件

## 脚本详细功能与调用方法（按音序排列）

### `actor_crawler_headless_db.py`
**功能**: 无界面模式的演员信息爬虫，直接将数据存入数据库
**调用方法**: `python actor_crawler_headless_db.py [options]`
**主要参数**:
- `--proxy`: 设置代理服务器
- `--delay`: 设置爬取延迟时间（秒）
- `--start-id`: 开始爬取的演员ID

### `actor_crawler_with_db.py`
**功能**: 带数据库支持的演员信息爬虫，提供可视化浏览器界面
**调用方法**: `python actor_crawler_with_db.py [options]`
**主要参数**:
- `--db`: 指定数据库路径
- `--limit`: 限制爬取的演员数量
- `--resume`: 从上次中断处继续爬取

### `actor_detail_crawler.py`
**功能**: 专门用于爬取演员详细信息的爬虫工具
**调用方法**: `python actor_detail_crawler.py --actor-id [ID] [options]`
**主要参数**:
- `--actor-id`: 指定要爬取的演员ID（必需）
- `--depth`: 爬取深度（控制获取信息的详细程度）
- `--save-images`: 是否保存演员头像

### `auto_clean_tags.py`
**功能**: 自动清理和规范化标签的工具
**调用方法**: `python auto_clean_tags.py [options]`
**主要参数**:
- `--dry-run`: 仅显示将要执行的操作，不实际修改
- `--aggressive`: 使用更激进的清理规则

### `batch_title_cleanup.py`
**功能**: 批量清理和规范化视频标题
**调用方法**: `python batch_title_cleanup.py [options]`
**主要参数**:
- `--all`: 处理所有视频标题
- `--pattern`: 指定要清理的特定模式

### `batch_update_actors.py`
**功能**: 批量更新演员信息的工具
**调用方法**: `python batch_update_actors.py --source [file] [options]`
**主要参数**:
- `--source`: 指定数据源文件（CSV格式，必需）
- `--match-field`: 指定用于匹配的字段名
- `--force`: 强制更新现有记录

### `batch_video_analyzer_enhanced.py`
**功能**: 增强版的批量视频分析工具，支持元数据提取和内容分析
**调用方法**: `python batch_video_analyzer_enhanced.py --dir [directory] [options]`
**主要参数**:
- `--dir`: 指定要分析的视频目录（必需）
- `--recursive`: 递归处理子目录
- `--threads`: 指定并行处理的线程数

### `batch_video_integrity_checker.py`
**功能**: 批量检查视频文件完整性的工具
**调用方法**: `python batch_video_integrity_checker.py --dir [directory] [options]`
**主要参数**:
- `--dir`: 指定要检查的视频目录（必需）
- `--report`: 指定生成报告的文件路径
- `--fix`: 自动修复检测到的问题

### `cfn4.py`
**功能**: 特定格式或算法的处理工具，可能用于特定视频编码或元数据的解析
**调用方法**: `python cfn4.py [input_file] [output_file]`
**主要参数**:
- 输入文件路径（必需）
- 输出文件路径（必需）

### `check_invalid_records.py`
**功能**: 检查数据库中的无效记录
**调用方法**: `python check_invalid_records.py [options]`
**主要参数**:
- `--type`: 指定要检查的记录类型（video/actor/tag）
- `--export`: 将无效记录导出到文件
- `--fix`: 尝试自动修复无效记录

### `clean_duplicate_tags.py`
**功能**: 清理重复的标签记录
**调用方法**: `python clean_duplicate_tags.py [options]`
**主要参数**:
- `--dry-run`: 仅显示将要执行的操作
- `--merge-synonyms`: 合并同义标签

### `cleanup_image_cache.py`
**功能**: 清理图像缓存的工具
**调用方法**: `python cleanup_image_cache.py [options]`
**主要参数**:
- `--cache-dir`: 指定缓存目录
- `--days`: 删除多少天前的缓存文件

### `code_extractor.py`
**功能**: 从文本中提取编码信息的工具，主要用于识别视频编码
**调用方法**: `python code_extractor.py --text [text]` 或 `python code_extractor.py --file [file]`
**主要参数**:
- `--text`: 直接提供要分析的文本
- `--file`: 指定包含文本的文件

### `comprehensive_tag_cleaner.py`
**功能**: 全面的标签清理工具，整合多种清理策略
**调用方法**: `python comprehensive_tag_cleaner.py [options]`
**主要参数**:
- `--steps`: 指定要执行的清理步骤
- `--config`: 指定自定义配置文件

### `database_extension.py`
**功能**: 扩展数据库功能，添加新表、字段或索引
**调用方法**: `python database_extension.py [options]`
**主要参数**:
- `--action`: 指定要执行的操作（add_field/add_table）
- `--table`: 指定目标表名
- `--field`: 指定要添加的字段名和类型

### `delete_small_videos.py`
**功能**: 删除小文件视频的工具
**调用方法**: `python delete_small_videos.py --dir [directory] --size [size_in_mb]`
**主要参数**:
- `--dir`: 指定要检查的目录（必需）
- `--size`: 指定最小文件大小阈值（MB，必需）
- `--dry-run`: 仅显示将要删除的文件

### `edge_cookie_reader.py`
**功能**: 读取Edge浏览器Cookie的工具
**调用方法**: `python edge_cookie_reader.py [options]`
**主要参数**:
- `--domain`: 过滤特定域名的Cookie
- `--export`: 将Cookie导出到文件

### `enhanced_code_extractor.py`
**功能**: 增强版的编码提取工具，支持更多编码格式
**调用方法**: `python enhanced_code_extractor.py --text [text]` 或 `python enhanced_code_extractor.py --file [file]`
**主要参数**:
- `--text`: 直接提供要分析的文本
- `--file`: 指定包含文本的文件
- `--format`: 指定输出格式

### `example_video_analysis.py`
**功能**: 视频分析的示例脚本
**调用方法**: `python example_video_analysis.py`
**主要参数**: 无特定参数，直接运行查看示例

### `extend_actors_table.py`
**功能**: 扩展演员表结构，添加新字段或修改现有字段
**调用方法**: `python extend_actors_table.py [options]`
**主要参数**:
- `--add-field`: 添加新字段（格式：字段名:类型）
- `--modify-field`: 修改现有字段

### `fast_import_from_md5.py`
**功能**: 通过MD5值快速导入视频信息的工具
**调用方法**: `python fast_import_from_md5.py --md5-file [file] [options]`
**主要参数**:
- `--md5-file`: 包含MD5值和视频信息的文件（必需）
- `--skip-existing`: 跳过已存在的记录

### `find_duplicate_videos.py`
**功能**: 查找重复视频的工具
**调用方法**: `python find_duplicate_videos.py --dir [directory] [options]`
**主要参数**:
- `--dir`: 指定要扫描的目录（必需）
- `--method`: 指定检测方法（name/size/md5）
- `--export`: 将重复列表导出到文件

### `fix_dot_cleanup.py`
**功能**: 修复文件名中多余点号的工具
**调用方法**: `python fix_dot_cleanup.py --dir [directory]`
**主要参数**:
- `--dir`: 指定要处理的目录（必需）
- `--dry-run`: 仅显示将要执行的重命名操作

### `fix_duplicate_detection.py`
**功能**: 修复重复检测逻辑的工具
**调用方法**: `python fix_duplicate_detection.py [options]`
**主要参数**:
- `--analyze`: 分析现有检测逻辑的问题
- `--apply-fixes`: 应用修复方案

### `fix_missing_avatars.py`
**功能**: 修复缺失头像的工具
**调用方法**: `python fix_missing_avatars.py [options]`
**主要参数**:
- `--force`: 强制重新下载所有头像
- `--threads`: 指定并行下载的线程数

### `import_videos_from_md5.py`
**功能**: 从MD5值导入视频信息的工具
**调用方法**: `python import_videos_from_md5.py --md5-file [file]`
**主要参数**:
- `--md5-file`: 包含MD5值和视频信息的文件（必需）
- `--match-fields`: 指定用于匹配的字段

### `init_database.py`
**功能**: 初始化项目数据库结构的工具
**调用方法**: `python init_database.py [options]`
**主要参数**:
- `--db`: 指定数据库文件路径
- `--overwrite`: 覆盖已存在的数据库
- `--with-sample-data`: 初始化时添加示例数据

### `javbus_crawler_single.py`
**功能**: 从JavBus网站爬取单个视频或演员的信息
**调用方法**: `python javbus_crawler_single.py --url [url] [options]`
**主要参数**:
- `--url`: 指定要爬取的JavBus页面URL（必需）
- `--proxy`: 设置代理服务器

### `javdb_actor_all.py`
**功能**: 从JavDB网站爬取演员信息和相关视频数据
**调用方法**: `python javdb_actor_all.py [options]`
**主要参数**:
- `--pages`: 指定要爬取的页数
- `--output`: 指定输出文件路径
- `--delay`: 设置爬取延迟

### `javdb_actor_stream.py`
**功能**: 流式处理JavDB演员数据的工具
**调用方法**: `python javdb_actor_stream.py [options]`
**主要参数**:
- `--start-page`: 开始爬取的页码
- `--continuous`: 持续运行，定期更新
- `--output-format`: 指定输出格式

### `javdb_crawler.py`
**功能**: JavDB网站通用爬虫
**调用方法**: `python javdb_crawler.py --type [type] --query [query] [options]`
**主要参数**:
- `--type`: 指定要爬取的资源类型（video/actor/tag）
- `--query`: 指定搜索关键词
- `--pages`: 指定要爬取的页数

### `javdb_crawler_single.py`
**功能**: 爬取单个JavDB视频或演员的详细信息
**调用方法**: `python javdb_crawler_single.py --url [url] [options]`
**主要参数**:
- `--url`: 指定要爬取的JavDB页面URL（必需）
- `--with-videos`: 对于演员页面，同时爬取其作品信息
- `--save-cover`: 保存封面图片

### `javsp_avsox.py`
**功能**: 与AVSOX网站交互的JavaSP模块
**调用方法**: 作为模块导入使用，一般不直接运行
**主要函数**:
- `search_by_code(code)`: 通过编码搜索视频
- `get_video_detail(url)`: 获取视频详细信息

### `javsp_base.py`
**功能**: JavaSP的基础模块
**调用方法**: 作为模块导入使用，一般不直接运行
**主要函数**:
- `send_request(url, params)`: 发送HTTP请求
- `parse_html(html, selector)`: 解析HTML内容

### `javsp_config_manager.py`
**功能**: 管理JavaSP配置的工具
**调用方法**: `python javsp_config_manager.py [action] [options]`
**主要参数**:
- `--save`: 保存当前配置
- `--load`: 加载配置文件
- `--reset`: 重置配置为默认值

### `javsp_crawler_manager.py`
**功能**: JavaSP爬虫管理器
**调用方法**: 作为模块导入使用，一般不直接运行
**主要类**:
- `CrawlerManager`: 爬虫任务管理类
- `TaskQueue`: 任务队列类

### `javsp_datatype.py`
**功能**: JavaSP的数据类型定义
**调用方法**: 作为模块导入使用，一般不直接运行
**主要数据类型**:
- `VideoInfo`: 视频信息数据类
- `ActorInfo`: 演员信息数据类
- `TagInfo`: 标签信息数据类

### `javsp_example.py`
**功能**: JavaSP的使用示例
**调用方法**: `python javsp_example.py`
**主要参数**: 无特定参数，直接运行查看示例

### `javsp_fc2.py`
**功能**: 与FC2网站交互的JavaSP模块
**调用方法**: 作为模块导入使用，一般不直接运行
**主要函数**:
- `search_by_code(code)`: 通过编码搜索FC2视频
- `get_video_detail(url)`: 获取FC2视频详细信息

### `javsp_integration.py`
**功能**: JavaSP与其他系统集成的模块
**调用方法**: 作为模块导入使用，一般不直接运行
**主要函数**:
- `export_to_json(data, file_path)`: 导出数据为JSON格式
- `import_from_json(file_path)`: 从JSON文件导入数据

### `javsp_javbus.py`
**功能**: 与JavBus网站交互的JavaSP模块
**调用方法**: 作为模块导入使用，一般不直接运行
**主要函数**:
- `search_by_code(code)`: 通过编码搜索JavBus视频
- `get_video_detail(url)`: 获取JavBus视频详细信息

### `javsp_javlib.py`
**功能**: 与JavLib网站交互的JavaSP模块
**调用方法**: 作为模块导入使用，一般不直接运行
**主要函数**:
- `search_by_code(code)`: 通过编码搜索JavLib视频
- `get_video_detail(url)`: 获取JavLib视频详细信息

### `media_library.py`
**功能**: 媒体库管理的主程序
**调用方法**: `python media_library.py [options]`
**主要参数**:
- `--gui`: 启动图形用户界面
- `--headless`: 以无头模式运行
- `--scan`: 扫描指定目录并导入视频
- `--update-all`: 更新所有媒体信息

### `merge_analysis_results.py`
**功能**: 合并分析结果的工具
**调用方法**: `python merge_analysis_results.py --input-files [files] --output [file]`
**主要参数**:
- `--input-files`: 要合并的输入文件列表（多个文件用逗号分隔，必需）
- `--output`: 指定输出文件路径（必需）
- `--method`: 指定合并方法

### `merge_duplicate_actors.py`
**功能**: 处理数据库中的重复演员记录
**调用方法**: `python merge_duplicate_actors.py [options]`
**主要参数**:
- `--dry-run`: 仅显示将要执行的合并操作
- `--force`: 强制合并所有重复记录

### `merge_duplicate_actors_enhance.py`
**功能**: 增强版的演员去重工具，支持JavDB搜索和信息爬取
**调用方法**: `python merge_duplicate_actors_enhance.py [options]`
**主要参数**:
- `--execute`: 实际执行操作（默认仅预览）
- `--actor "演员名称"`: 指定单个演员名称进行处理
- `--process-existing`: 处理数据库中所有缺少profile_url的演员

### `recalculate_md5.py`
**功能**: 重新计算文件MD5值的工具
**调用方法**: `python recalculate_md5.py --dir [directory] [options]`
**主要参数**:
- `--dir`: 指定要扫描的目录（必需）
- `--update-db`: 更新数据库中的MD5记录
- `--threads`: 指定并行计算的线程数

### `reprocess_failed_videos.py`
**功能**: 重新处理之前处理失败的视频文件
**调用方法**: `python reprocess_failed_videos.py --log-file [file] [options]`
**主要参数**:
- `--log-file`: 包含失败记录的日志文件（必需）
- `--max-retries`: 最大重试次数

### `resumable_smart_importer.py`
**功能**: 支持断点续传的智能视频导入工具
**调用方法**: `python resumable_smart_importer.py --dir [directory] [options]`
**主要参数**:
- `--dir`: 指定要导入的视频目录（必需）
- `--resume`: 从上次中断处继续导入
- `--skip-existing`: 跳过已存在的记录

### `search_and_crawl_actors.py`
**功能**: 根据搜索条件爬取演员信息的工具
**调用方法**: `python search_and_crawl_actors.py --query [query] [options]`
**主要参数**:
- `--query`: 指定搜索关键词（必需）
- `--site`: 指定搜索网站（javdb/javbus/javlib）
- `--limit`: 限制爬取的结果数量

### `smart_video_updater.py`
**功能**: 智能更新视频信息的工具
**调用方法**: `python smart_video_updater.py [options]`
**主要参数**:
- `--all`: 更新所有视频信息
- `--last-days`: 更新最近N天添加的视频
- `--force`: 强制更新所有字段

### `title_analysis.py`
**功能**: 分析视频标题的工具
**调用方法**: `python title_analysis.py --title [title]` 或 `python title_analysis.py --file [file]`
**主要参数**:
- `--title`: 直接提供要分析的标题文本
- `--file`: 指定包含标题的文件
- `--extract-code`: 仅提取标题中的编码信息

### `unified_video_updater.py`
**功能**: 统一的视频更新工具
**调用方法**: `python unified_video_updater.py [options]`
**主要参数**:
- `--mode`: 指定更新模式（metadata/tags/covers）
- `--source`: 指定更新源（javdb/javbus/local）
- `--video-id`: 指定要更新的特定视频ID

### `update_msedge_driver.py`
**功能**: 更新Microsoft Edge浏览器驱动程序的工具
**调用方法**: `python update_msedge_driver.py [options]`
**主要参数**:
- `--force`: 强制下载最新版本
- `--install-path`: 指定安装路径

### `update_tags_from_csv.py`
**功能**: 从CSV文件更新视频标签的工具
**调用方法**: `python update_tags_from_csv.py --csv [file] [options]`
**主要参数**:
- `--csv`: 包含标签信息的CSV文件（必需）
- `--match-column`: 指定用于匹配视频的列名
- `--tag-column`: 指定包含标签的列名

### `update_video_descriptions.py`
**功能**: 更新视频描述信息的工具
**调用方法**: `python update_video_descriptions.py [options]`
**主要参数**:
- `--source`: 指定描述来源（file/url/db）
- `--all`: 更新所有视频描述
- `--limit`: 限制更新数量

### `video_content_analyzer.py`
**功能**: 分析视频内容的工具
**调用方法**: `python video_content_analyzer.py --video [file] [options]`
**主要参数**:
- `--video`: 指定要分析的视频文件（必需）
- `--extract-keyframes`: 提取关键帧
- `--analyze-audio`: 分析音频内容

### `video_integrity_checker.py`
**功能**: 检查视频文件完整性的工具
**调用方法**: `python video_integrity_checker.py --video [file] [options]`
**主要参数**:
- `--video`: 指定要检查的视频文件（必需）
- `--deep-scan`: 执行深度扫描
- `--report`: 生成详细报告

### `video_multimodal_analyzer.py`
**功能**: 多模态视频分析工具
**调用方法**: `python video_multimodal_analyzer.py --video [file] [options]`
**主要参数**:
- `--video`: 指定要分析的视频文件（必需）
- `--model`: 指定使用的分析模型
- `--output-format`: 指定输出格式

### `video_subtitle_extractor.py`
**功能**: 提取视频中的字幕文件的工具
**调用方法**: `python video_subtitle_extractor.py --video [file] [options]`
**主要参数**:
- `--video`: 指定要处理的视频文件（必需）
- `--output-format`: 指定输出字幕格式
- `--language`: 指定要提取的字幕语言

### `video_tagging.py`
**功能**: 为视频添加标签的工具
**调用方法**: `python video_tagging.py --video-id [id] --tags [tags] [options]`
**主要参数**:
- `--video-id`: 指定要添加标签的视频ID（必需）
- `--tags`: 指定要添加的标签列表（用逗号分隔，必需）
- `--overwrite`: 覆盖现有标签