# Python脚本功能文档

## 概述
本文档详细描述了media目录下所有Python脚本的功能、用途和主要特性，帮助用户了解项目结构和各组件的作用。文档按照音序排列所有Python脚本，并提供功能检索表以便快速查找。

## 功能检索表

| 功能分类 | 包含脚本 |
|---------|---------|
| 数据库相关 | `init_database.py`, `database_extension.py`, `merge_duplicate_actors.py`, `merge_duplicate_actors_enhance.py`, `extend_actors_table.py` |
| 爬虫与数据获取 | `javdb_actor_all.py`, `javdb_actor_stream.py`, `javdb_crawler.py`, `javdb_crawler_single.py`, `actor_crawler_headless_db.py`, `actor_crawler_with_db.py`, `actor_detail_crawler.py`, `search_and_crawl_actors.py`, `javbus_crawler_single.py`, `update_msedge_driver.py` |
| 视频处理与分析 | `batch_video_analyzer_enhanced.py`, `video_content_analyzer.py`, `video_multimodal_analyzer.py`, `video_integrity_checker.py`, `batch_video_integrity_checker.py`, `delete_small_videos.py`, `recalculate_md5.py`, `reprocess_failed_videos.py`, `resumable_smart_importer.py`, `fast_import_from_md5.py`, `import_videos_from_md5.py`, `check_invalid_records.py`, `video_subtitle_extractor.py` |
| 元数据与标签处理 | `title_analysis.py`, `batch_title_cleanup.py`, `update_tags_from_csv.py`, `update_video_descriptions.py`, `clean_duplicate_tags.py`, `auto_clean_tags.py`, `comprehensive_tag_cleaner.py`, `video_tagging.py`, `code_extractor.py`, `enhanced_code_extractor.py` |
| 配置与管理 | `config.py`, `config.json`, `javsp_config.py`, `javsp_config.yaml`, `javsp_config_manager.py`, `media_library.py`, `gui_config.json` |
| JavaSP相关模块 | `javsp_avsox.py`, `javsp_base.py`, `javsp_crawler_manager.py`, `javsp_datatype.py`, `javsp_example.py`, `javsp_fc2.py`, `javsp_integration.py`, `javsp_javbus.py`, `javsp_javlib.py` |
| 实用工具 | `cfn4.py`, `batch_update_actors.py`, `cleanup_image_cache.py`, `edge_cookie_reader.py`, `fix_dot_cleanup.py`, `fix_duplicate_detection.py`, `fix_missing_avatars.py`, `find_duplicate_videos.py`, `merge_analysis_results.py`, `smart_video_updater.py`, `unified_video_updater.py` |

## 脚本详细功能说明（按音序排列）

### `actor_crawler_headless_db.py`
无界面模式的演员信息爬虫，直接将数据存入数据库。
- 采用无头浏览器模式运行，适合服务器环境
- 自动爬取演员信息并实时写入数据库
- 支持错误处理和重试机制

### `actor_crawler_with_db.py`
带数据库支持的演员信息爬虫。
- 提供可视化浏览器界面，便于监控爬取过程
- 实现完整的演员信息爬取和数据库存储流程
- 支持配置爬取速度和并发数

### `actor_detail_crawler.py`
专门用于爬取演员详细信息的爬虫工具。
- 针对演员个人页面进行深度爬取
- 提取演员的详细个人资料、作品列表等信息
- 支持处理分页和动态加载内容

### `analysis_out.csv`
分析输出结果CSV文件，包含视频分析的结果数据。
- 存储视频的元数据、标签、评分等分析结果
- 便于后续数据处理和分析

### `auto_clean_tags.py`
自动清理和规范化标签的工具。
- 根据预设规则自动修正标签格式
- 合并相似标签，删除冗余标签
- 支持批量处理数据库中的标签

### `av_codes_list.txt`
AV编码列表文件，包含常见的AV作品编码格式和示例。
- 提供编码格式参考，用于编码识别和验证
- 便于开发和测试编码处理功能

### `batch_title_cleanup.py`
批量清理和规范化视频标题。
- 移除标题中的冗余信息、特殊字符
- 统一标题格式，提高可读性和一致性
- 支持自定义清理规则和模式

### `batch_update_actors.py`
批量更新演员信息的工具。
- 读取外部数据源，批量更新数据库中的演员记录
- 支持字段映射和数据转换
- 提供更新报告和统计信息

### `batch_video_analyzer_enhanced.py`
增强版的批量视频分析工具。
- 支持同时分析多个视频文件的元数据
- 提取视频编码、分辨率、时长等信息
- 实现多线程并行处理，提高分析效率

### `batch_video_integrity_checker.py`
批量检查视频文件完整性的工具。
- 验证视频文件格式是否正确
- 检查文件是否损坏或不完整
- 生成完整性报告，标识问题文件

### `cfn4.py`
特定格式或算法的处理工具，可能用于特定视频编码或元数据的解析。
- 实现特定的编码格式处理逻辑
- 提供格式转换和验证功能

### `check_invalid_records.py`
检查数据库中的无效记录。
- 扫描数据库中的异常或不完整记录
- 提供记录验证和修复建议
- 支持导出无效记录列表

### `clean_duplicate_tags.py`
清理重复的标签记录。
- 识别并移除数据库中的重复标签
- 保留主要标签，合并关联关系
- 提供重复标签报告和清理统计

### `cleanup_image_cache.py`
清理图像缓存的工具。
- 删除过期或不再需要的图像缓存文件
- 释放存储空间
- 支持配置缓存保留策略

### `code_extractor.py`
从文本中提取编码信息的工具，主要用于识别视频编码。
- 实现正则表达式匹配和编码提取逻辑
- 支持多种常见编码格式的识别
- 提供编码验证功能

### `comprehensive_tag_cleaner.py`
全面的标签清理工具。
- 整合多种标签清理策略和规则
- 提供标签规范化、合并、删除等全方位功能
- 支持自定义清理规则和优先级

### `config.json`
JSON格式的配置文件，存储项目的配置信息。
- 包含数据库连接、爬虫设置等配置项
- 支持动态加载和热更新

### `config.py`
项目的主要配置文件。
- 定义全局配置常量，如代理设置、基础URL、登录凭据等
- 提供配置项的默认值和类型定义
- 支持从环境变量或配置文件覆盖默认值

### `database_extension.py`
扩展数据库功能的工具。
- 添加新的表、字段或索引到现有数据库
- 实现数据库结构升级和迁移
- 提供数据备份和恢复功能

### `database_schema_documentation.md`
数据库Schema文档，详细描述数据库结构和关系。
- 包含表结构、字段定义、索引和约束说明
- 提供实体关系图和数据流程说明
- 便于开发人员理解和使用数据库

### `delete_small_videos.py`
删除小文件视频的工具。
- 根据文件大小或时长筛选并删除过小的视频文件
- 支持设置最小文件大小或时长阈值
- 提供删除前预览和确认功能

### `edge_cookie_reader.py`
读取Edge浏览器Cookie的工具。
- 从Edge浏览器配置中提取Cookie信息
- 用于爬虫身份验证和会话维持
- 支持导出Cookie为标准格式

### `enhanced_code_extractor.py`
增强版的编码提取工具。
- 在基础版基础上增加了更多编码格式的支持
- 提高编码识别准确率和速度
- 支持复杂文本中的编码提取

### `example_video_analysis.py`
视频分析的示例脚本。
- 展示视频分析功能的使用方法
- 包含示例代码和配置
- 便于新用户快速上手

### `extend_actors_table.py`
扩展演员表结构的工具。
- 向演员表添加新的字段或修改现有字段
- 实现数据迁移和兼容性处理
- 提供字段类型和约束定义

### `fast_import_from_md5.py`
通过MD5值快速导入视频信息的工具。
- 基于文件MD5值匹配和导入视频元数据
- 实现高效的文件识别和信息关联
- 支持批量导入和进度显示

### `filelist.txt`
文件列表，记录项目中的关键文件或目录。
- 用于文件管理和版本控制
- 便于跟踪项目组成部分

### `find_duplicate_videos.py`
查找重复视频的工具。
- 基于文件名、文件大小、MD5值等属性识别重复视频
- 提供重复视频列表和相似度评分
- 支持自定义重复检测规则

### `fix_dot_cleanup.py`
修复文件名中多余点号的工具。
- 识别并修正文件名中不规范的点号使用
- 统一文件名格式，避免系统兼容性问题
- 支持批量重命名和预览功能

### `fix_duplicate_detection.py`
修复重复检测逻辑的工具。
- 诊断和修复重复检测算法中的问题
- 优化重复检测的准确率和性能
- 提供检测结果验证和调整功能

### `fix_missing_avatars.py`
修复缺失头像的工具。
- 识别数据库中缺少头像的演员记录
- 自动尝试从网络获取缺失的头像
- 支持头像缓存和本地存储

### `gui_config.json`
GUI界面的配置文件。
- 存储界面布局、主题、字体等配置
- 支持用户自定义界面设置

### `HC530_1_待整理_enhanced_parallel_analysis.csv`
HC530_1待整理的增强并行分析结果CSV文件。
- 包含并行处理的视频分析结果
- 存储多维度的分析数据

### `HC530_1_待整理_merged_analysis.csv`
HC530_1待整理的合并分析结果CSV文件。
- 包含多个分析模块结果的整合数据
- 提供综合的视频分析视图

### `HC530_1_待整理_reprocessed_failed.csv`
HC530_1待整理的重新处理失败记录CSV文件。
- 记录重新处理过程中仍失败的视频信息
- 便于后续分析失败原因和进行手动处理

### `import_videos_from_md5.py`
从MD5值导入视频信息的工具。
- 根据预存的MD5值数据库导入视频元数据
- 实现视频文件和元数据的自动关联
- 支持批量导入和错误处理

### `init_database.py`
初始化项目数据库结构的工具。
- 创建所有必要的表、索引和视图
- 设置初始数据和默认配置
- 提供数据库初始化状态检查

### `javbus_crawler_single.py`
从JavBus网站爬取单个视频或演员的信息。
- 实现对JavBus网站的单资源爬取
- 提取视频详细信息、演员信息等
- 支持代理和延迟设置，避免被封

### `javdb_actor_all.py`
从JavDB网站爬取演员信息和相关视频数据。
- 实现批量演员信息爬取
- 收集演员的作品列表和详细信息
- 支持分页爬取和数据持久化

### `javdb_actor_stream.py`
流式处理JavDB演员数据的工具。
- 支持持续爬取和更新演员信息
- 实现数据流处理和增量更新
- 适用于长期运行的爬取任务

### `javdb_crawler.py`
JavDB网站通用爬虫。
- 提供爬取JavDB网站的基础功能
- 支持爬取视频列表、演员列表等多种资源
- 实现通用的爬取逻辑和数据处理框架

### `javdb_crawler_single.py`
爬取单个JavDB视频或演员的详细信息。
- 专注于单个资源的深度爬取
- 提取详细的元数据和关联信息
- 支持处理复杂的页面结构和动态内容

### `javsp_avsox.py`
与AVSOX网站交互的JavaSP模块。
- 实现AVSOX网站的特定爬取逻辑
- 提供数据提取和解析功能
- 支持该网站的特定数据结构和API

### `javsp_base.py`
JavaSP的基础模块。
- 提供通用功能和接口定义
- 实现基础的HTTP请求、解析等功能
- 作为其他JavaSP模块的基础依赖

### `javsp_config.py`
JavaSP相关的配置文件。
- 存储JavaSP模块的特定配置
- 支持自定义爬取行为和参数

### `javsp_config_manager.py`
管理JavaSP配置的工具。
- 提供配置加载、验证和保存功能
- 支持配置的层级继承和覆盖
- 实现配置的热更新和监控

### `javsp_config.yaml`
YAML格式的JavaSP配置文件。
- 提供更易读的配置格式
- 支持复杂的配置结构和注释

### `javsp_crawler_manager.py`
JavaSP爬虫管理器。
- 协调多个爬虫任务的执行
- 实现任务队列和调度功能
- 提供爬虫状态监控和错误处理

### `javsp_datatype.py`
JavaSP的数据类型定义。
- 定义系统中使用的各种数据结构和类型
- 提供类型验证和转换功能
- 确保数据一致性和完整性

### `javsp_example.py`
JavaSP的使用示例。
- 展示JavaSP模块的基本用法和功能
- 包含完整的示例代码和注释
- 便于新用户学习和理解JavaSP

### `javsp_fc2.py`
与FC2网站交互的JavaSP模块。
- 实现FC2网站的特定爬取逻辑
- 处理FC2特有的数据格式和页面结构
- 提供该网站资源的访问和解析功能

### `javsp_integration.py`
JavaSP与其他系统集成的模块。
- 实现JavaSP与外部系统的数据交换
- 提供API接口和数据转换功能
- 支持第三方系统的接入和集成

### `javsp_javbus.py`
与JavBus网站交互的JavaSP模块。
- 实现JavBus网站的特定爬取逻辑
- 处理JavBus特有的数据结构和API
- 提供该网站资源的访问和解析功能

### `javsp_javlib.py`
与JavLib网站交互的JavaSP模块。
- 实现JavLib网站的特定爬取逻辑
- 处理JavLib特有的数据结构和API
- 提供该网站资源的访问和解析功能

### `media_library.py`
媒体库管理的主程序。
- 整个系统的核心模块，提供统一的入口
- 整合各功能模块，提供完整的媒体管理功能
- 支持命令行和可能的GUI操作模式

### `merge_analysis_results.py`
合并分析结果的工具。
- 将多个分析模块的结果整合为统一视图
- 处理结果冲突和数据融合
- 生成综合分析报告

### `merge_duplicate_actors.py`
处理数据库中的重复演员记录。
- 识别相同或相似的演员信息
- 合并重复记录，保留完整信息
- 维护关联的视频记录关系

### `merge_duplicate_actors_enhance.py`
该程序基于 merge_duplicate_actors.py 进行了全面增强，以满足处理NFO导入时无演员链接信息及爬取非javdb链接的需求。

**主要功能实现**：
1. **演员名称去重处理**
   - 从文本中提取可能的演员名称，支持处理逗号分隔的情况
   - 自动去重并保持顺序

2. **数据库匹配机制**
   - 全面查询数据库中是否已存在同名演员（检查name、name_common、name_traditional和aliases字段）
   - 对已有演员但缺少profile_url的记录，自动搜索并更新信息

3. **JavDB搜索与信息爬取**
   - 对不存在于数据库的演员，自动构建搜索URL： `https://javdb.com/search?q=actor_name&f=actor`
   - 选择并爬取第一个搜索结果的详细信息（名称、生日、身高、三围、头像URL等）

4. **即时数据库写入**
   - 每个处理完成的演员立即写入数据库，避免程序中断后需重新开始
   - 支持记录完整的演员信息和profile_url链接

5. **智能浏览器管理**
   - 支持Windows/macOS/Linux多平台浏览器驱动自动设置
   - 集成SOCKS5代理支持
   - 自动检测登录页面并提供手动登录等待功能

**使用方法**：
程序提供了多种灵活的运行模式：

1. **预览模式（默认）**：只显示将要执行的操作，不实际修改数据库

2. **执行模式**：实际执行操作并修改数据库

3. **处理单个演员**：通过命令行参数指定单个演员名称进行处理
   ```
   python merge_duplicate_actors_enhance.py --execute --actor "演员名称"
   ```

4. **处理现有演员**：处理数据库中所有缺少profile_url的演员
   ```
   python merge_duplicate_actors_enhance.py --execute --process-existing
   ```

5. **交互模式**：交互式输入演员名称进行处理（支持逗号分隔的多个名称）
   ```
   python merge_duplicate_actors_enhance.py --execute
   ```

### `recalculate_md5.py`
重新计算文件MD5值的工具。
- 遍历指定目录下的文件，重新计算MD5值
- 更新数据库中对应的MD5记录
- 验证文件完整性和一致性

### `reprocess_failed_videos.py`
重新处理之前处理失败的视频文件。
- 从失败记录中读取视频列表
- 尝试重新分析或导入视频
- 更新处理状态和结果

### `requirements.txt`
项目的主要依赖列表。
- 列出项目运行所需的Python包及其版本
- 用于依赖管理和环境搭建

### `requirements_video_analyzer.txt`
视频分析模块的依赖列表。
- 列出视频分析功能所需的特定Python包
- 可能包含较大或特殊的依赖项

### `resumable_smart_importer.py`
支持断点续传的智能视频导入工具。
- 实现导入进度记录和恢复功能
- 支持大批次视频的分步导入
- 提供导入状态监控和错误处理

### `search_and_crawl_actors.py`
根据搜索条件爬取演员信息的工具。
- 支持自定义搜索关键词和过滤条件
- 自动爬取匹配的演员信息
- 实现搜索结果分页处理

### `setup_claude_bigmodel.sh`
设置Claude大模型的Shell脚本。
- 配置Claude模型的运行环境
- 安装必要的依赖和组件
- 提供模型初始化和测试功能

### `smart_video_updater.py`
智能更新视频信息的工具。
- 分析视频文件和现有元数据
- 自动识别需要更新的信息
- 实现智能匹配和信息更新

### `start_media_library.sh`
启动媒体库的Shell脚本。
- 设置运行环境和配置
- 启动媒体库主程序
- 提供启动参数和选项

### `title_analysis.py`
分析视频标题的工具。
- 提取标题中的关键词、编码等信息
- 识别标题结构和模式
- 支持自定义分析规则和输出格式

### `unified_video_updater.py`
统一的视频更新工具。
- 整合多种视频信息更新功能
- 提供统一的更新接口和流程
- 支持批量和单个视频更新

### `update_msedge_driver.py`
更新Microsoft Edge浏览器驱动程序的工具。
- 检查当前Edge浏览器版本
- 下载并安装匹配的驱动程序
- 配置驱动环境和路径

### `update_tags_from_csv.py`
从CSV文件更新视频标签的工具。
- 读取CSV文件中的标签数据
- 匹配视频记录并更新标签
- 提供更新日志和统计信息

### `update_video_descriptions.py`
更新视频描述信息的工具。
- 从外部源获取视频描述
- 更新数据库中的描述字段
- 支持描述格式的规范化处理

### `video_content_analyzer.py`
分析视频内容的工具。
- 提取视频的视觉和音频特征
- 识别视频中的场景、对象等内容
- 生成内容分析报告和标签建议

### `video_integrity_checker.py`
检查视频文件完整性的工具。
- 验证视频文件格式和编码
- 检查文件是否损坏或不完整
- 提供详细的完整性检查报告

### `video_md5.csv`
视频MD5值的CSV文件。
- 存储视频文件的MD5值和基本信息
- 用于文件验证和重复检测

### `video_md5_sample.csv`
视频MD5值的示例CSV文件。
- 提供MD5值文件的格式示例
- 便于用户创建自定义MD5文件

### `video_multimodal_analyzer.py`
多模态视频分析工具。
- 结合视觉、音频、文本等多种分析方法
- 提供综合的视频内容分析
- 生成多维度的分析结果和标签

### `video_subtitle_extractor.py`
提取视频中的字幕文件的工具。
- 支持多种字幕格式的识别和提取
- 处理内嵌字幕和外挂字幕
- 提供字幕转换和导出功能

### `video_tagging.py`
为视频添加标签的工具。
- 支持手动和自动标签添加
- 提供标签建议和管理功能
- 实现标签的层级分类和关联

### `vocabulary_tags.txt`
标签词汇表，包含系统支持的标准标签。
- 提供标签参考和规范
- 用于标签规范化和验证

---

## 使用建议

1. **数据库操作**：在使用数据库相关脚本前，请确保已备份重要数据
2. **爬虫脚本**：使用爬虫脚本时，请遵守网站的robots.txt规则和相关法律法规
3. **批量处理**：大批量处理文件前，建议先使用小样本测试
4. **配置管理**：修改配置文件时，请确保了解每个参数的作用

## 版本信息
根据项目的VERSION_CHANGELOG.md，当前最新版本为：

**版本**: v1.2.0
**发布日期**: 2025-08-17
**提交哈希**: fb94464

此文档基于项目当前文件结构生成，随着项目更新可能需要同步更新文档内容。