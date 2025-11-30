## 目标
- 在不修改 `media_library.py` 的前提下，将其核心功能抽象为可复用的 `utils/` 包，供 PySide6 GUI 调用。
- 将 `media_library.py` 的功能整合到 `media_library_pyside.py`，实现扫描、索引、筛选、缩略图、去重、JAV 信息抓取与保存等。
- 在 PySide6 GUI 中新增“JAV 整理”能力，完善 JavSP 集成、批量导入与修复流程。
- 编写配套文档到 `.doc/` 文件夹。

## 范围与约束
- 不修改 `/Users/firewell/Library/CloudStorage/OneDrive-个人/bioinfo/media/media_library.py`。
- 新增 `utils/` 包与若干模块，`media_library_pyside.py` 迁移为调用 `utils/` 的服务接口。
- 保持现有数据库结构与迁移逻辑兼容（含 `videos`, `folders`, `tags`, `javdb_info`, `actors`, 关联表等）。

## 现状要点（参考定位）
- Tk GUI 主类：`/Users/.../media/media_library.py:247`（`class MediaLibrary`）。
- 扫描与索引：`media_library.py:1276-1523`；数据库初始化与迁移：`media_library.py:673-779`。
- 缩略图：`media_library.py:2120-...`；去重与MD5：`media_library.py:3481-...`、`3660-...`、`5397-...`。
- JAV 信息抓取与保存：`save_javdb_info_to_db` 在 `media_library.py:7629-7755`；批量获取与修复：`media_library.py:6249-6460`、`10047-10307`。
- JavSP 集成：`/Users/.../media/javsp_integration.py:31-75`（`class JavSPIntegration`），搜索与保存接口：`javsp_integration.py:118-158`、`301-539`。
- PySide6 GUI 入口与主窗体：`/Users/.../media/media_library_pyside.py:1693-1750`，日志适配：`media_library_pyside.py:46-71`，DB建表：`media_library_pyside.py:149-291`。

## utils/ 包设计
- 路径：`/Users/.../media/utils/`
- 模块与接口
  - `utils/logging.py`
    - `set_log_level(level)`、`output_log(level, message, sink=None)`，支持注入 GUI sink。
  - `utils/progress.py`
    - `ProgressUpdateManager(cb)` 通用进度更新器；结构体：`ProgressState`（scanned/added/updated/skipped/percent）。
  - `utils/db.py`
    - `init_database(db_path) -> conn`；`migrate_database(conn)`；索引创建。
    - CRUD：`insert_or_update_video(...)`、`update_video_path(...)`、`upsert_jav_info(...)`、`upsert_tags(...)`、`upsert_actors(...)`、关联维护函数。
    - 查询：`fetch_videos(filters)`、`get_actor_info_by_name(name)`、`get_actor_movies(name)`。
  - `utils/filesystem.py`
    - `walk_videos(folders, exts)`；`safe_move(src, dst)`；`open_file_cross_platform(path)`；设备与 NAS 判断辅助。
  - `utils/hash.py`
    - `calculate_md5(path) -> str`（流式计算）。
  - `utils/metadata.py`
    - `process_filename(name)`；`parse_stars(name)`；`extract_title(name)`；`get_video_media_info(path) -> (duration, resolution)`。
  - `utils/thumbnails.py`
    - `generate_thumbnail(path, timepoint=None) -> image_data`；`batch_generate(paths, progress_cb)`。
  - `utils/jav.py`
    - `extract_code(filename)`（可复用 `code_extractor`）；
    - `search_movie_info(code, strategy='auto') -> dict|None`（优先 JavDB→JavBus→JavSP，或直接代理 `JavSPIntegration`）；
    - `save_movie_info_to_db(conn, video_id, info)`；
    - `batch_fetch_and_save(conn, video_ids, progress_cb)`；
    - `fix_error_titles(conn, titles, progress_cb)`（错误标题如“官方App下載”等）。

## GUI 整合方案（PySide6）
- 服务层
  - 在 `media_library_pyside.py` 中通过组合引入 `utils/` 的接口，形成 `CoreServices`（或复用现有 `MediaLibraryCore`）。
  - 所有耗时操作（扫描、缩略图、批量JAV）统一在线程运行，向 `ScanProgressDialog` 或状态栏发信号。
- UI 组件扩展
  - 新增“JAV 信息”标签页：输入番号、搜索保存、展示结果（标题、日期、评分、演员、标签、封面、磁链、来源）。
  - 新增“批量导入/修复”面板：对“无标题”和“错误标题”两类提供批处理，参数可选并行度、超时与策略优先级。
  - 新增“爬虫状态”面板：展示 `JavSPIntegration.get_crawler_status()`。
- 设定与持久化
  - 统一 `settings.json`（或复用 `gui_config.json`）保存：策略优先级、并行度、超时、代理、JavSP配置路径、cookies。

## 关键流程映射
- 扫描与索引
  - GUI 调用：`utils.filesystem.walk_videos` → `utils.hash.calculate_md5`、`utils.metadata.get_video_media_info` → `utils.db.insert_or_update_video`。
- 缩略图
  - GUI 调用：`utils.thumbnails.generate_thumbnail`；批量用 `batch_generate`。
- 筛选与加载
  - GUI 调用：`utils.db.fetch_videos(filters)`，保持 `media_library.py` 的列与过滤器概念一致。
- JAV 信息
  - 单条：从选中项提取番号 `utils.jav.extract_code` → 搜索 `utils.jav.search_movie_info` → 保存 `utils.jav.save_movie_info_to_db`。
  - 批量：`utils.jav.batch_fetch_and_save`；错误标题修复：`utils.jav.fix_error_titles`。

## 实施里程碑
- 阶段1：搭建 `utils/` 包骨架与公共依赖；抽取日志、进度、DB 初始化与迁移。
- 阶段2：文件系统扫描、MD5、媒体信息、缩略图；保证与现有 DB 字段一致。
- 阶段3：JAV 搜索策略与 JavSP 适配；单条与批量保存；错误标题修复。
- 阶段4：PySide6 GUI 接入 `utils/`；新增“JAV 信息”“批量导入/修复”“爬虫状态”面板与信号/槽。
- 阶段5：设置持久化与代理/并行参数；完善异常处理与取消机制。
- 阶段6：编写 `.doc/` 文档并校对；交付与演示。

## 验证与测试
- 单元测试：`utils/` 的扫描、MD5、元数据解析、DB CRUD、JAV 保存；对网络依赖用模拟或超时回退。
- 集成测试：GUI 线程与信号、进度对话框、批量任务取消与恢复；数据库一致性检查（表结构、索引存在）。
- 手动用例：
  - 小样本文件夹扫描→列表加载→缩略图→单条JAV保存。
  - 批量“无标题导入”与“错误标题修复”。

## 风险与缓解
- 网络不稳定：统一超时与回退策略（脚本→JavSP）并可取消重试。
- DB 结构差异：以 `media_library.py:673-779` 为基准，迁移脚本完备并加校验。
- 大文件性能：MD5 流式计算与批量提交；生成缩略图分批、限并发。

## 交付物
- 代码：`utils/` 包与更新后的 `media_library_pyside.py`（只改 GUI 侧）。
- 文档（`.doc/` 文件夹）：
  - `architecture_overview.md`：整体架构与数据流。
  - `utils_api_reference.md`：模块与接口说明。
  - `gui_integration_javsp.md`：JavSP 集成设计与使用指南。
  - `migration_guide.md`：从 Tk 到 PySide6 的映射与注意事项。
  - `usage_workflows.md`：典型工作流（扫描、筛选、缩略图、JAV 导入）。

请确认上述计划；确认后我将开始创建 `utils/` 包、迁移与接入，并在 `.doc/` 写入对应文档。