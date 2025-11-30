## 需求解读
- 单次导入：去掉手动选择 NFO 文件，按 requirements/JavSP 规则自动定位并导入与视频对应的 NFO。
- 批量导入：面向“所有在线文件”，自动找出缺失信息的视频集合，按 JavSP 目录结构定位 NFO 并导入。

## 现状梳理
- 单次导入入口：`media_library.py:3412` 的 `import_nfo(self)` 仍弹文件选择框（早期简版解析在 `media_library.py:3431`）。
- 上下文导入（JavSP 完整映射）：`media_library.py:9619` 的 `import_nfo_from_context(self, video_id, video_path)` + `media_library.py:9791` 的增强版 `parse_nfo_file(self, nfo_path)`，已对齐 JavSP NFO 字段并入库到 `videos/javdb_info/actors/tags`，支持 `poster.jpg`/`fanart.jpg`。
- 批量范围判定：
  - 缺演员：`media_library.py:9875` 的 `batch_import_nfo_for_no_actors` 以选择目录 + `LEFT JOIN video_actors`（`va.video_id IS NULL`）。
  - 缺 JAVDB 标题：`media_library.py:10004` 的 `batch_import_javdb_for_no_title` 以选择目录 + `LEFT JOIN javdb_info`（`(j.javdb_title IS NULL OR j.javdb_title = '')`）。
- 在线状态：运行时以 `is_video_online(video_id)` 判断（`media_library.py:1904`），列表过滤基于活跃且存在的 `folders.folder_path`（`media_library.py:2305`、`2359`）。
- JavSP 规则文档：`requirements/JavSP整理规则与文件夹结构说明.md`，定义 `movie.nfo`/同名 `.nfo`、`poster.jpg`、`fanart.jpg`、字段映射。

## 设计与改动点
- 统一采用增强版解析：淘汰早期简版 `parse_nfo_file`（`media_library.py:3431`），所有入口均调用增强版解析（`media_library.py:9791`）。
- 改造 `import_nfo(self)`（`media_library.py:3412`）：
  - 不再弹文件选择器；改为对当前选中视频行（或焦点行）自动定位 NFO 并导入。
  - 选中项提取参照 `batch_*_selected_videos` 系列（如 `media_library.py:5922`、`6024`），通过 `self.video_tree.selection()` 获取 `video_id` 列表。
- 新增 `auto_import_nfo_for_video(self, video_id)`：
  - 从 DB 拉取 `file_path/source_folder`。
  - 候选 NFO 路径（按 JavSP 规则）：
    - 同目录优先 `movie.nfo`；
    - 回退为 `<basename>.nfo`（大小写不敏感）；
    - 仍未命中时，在同目录枚举 `*.nfo`，解析 `uniqueid/code/title` 与文件名番号匹配后选用。
  - 解析：调用增强版 `parse_nfo_file(nfo_path)` 返回 `nfo_data`。
  - 入库：复用上下文导入完整逻辑（`media_library.py:9656`–`9769`）：
    - `videos` 更新 `title/description/year/genre/thumbnail_data`（`fanart.jpg` 存在时写入）；
    - `javdb_info` 插入/更新 `javdb_code/javdb_title/release_date/studio/rating/score/cover_image_data`（`poster.jpg` 存在时写入）；
    - 建立 `actors` 与 `tags` 关联。
  - 字段覆盖策略：仅填补空缺；保留已有非空值。
- 批量导入（全库在线 + 缺失信息）：新增 `batch_import_nfo_for_missing_info(self)`：
  - 在线范围：基于活跃且存在的 `folders.folder_path` 列表，获取所有在线视频 ID；或在循环中以 `is_video_online(video_id)` 二次过滤。
  - 缺失信息集合（SQL）：合并以下条件之一即可进入批量：
    - 缺演员：`LEFT JOIN video_actors va ON v.id = va.video_id WHERE va.video_id IS NULL`；
    - 缺 JAVDB：`LEFT JOIN javdb_info j ON v.id = j.video_id WHERE (j.javdb_title IS NULL OR j.javdb_title = '')`；
    - 可选：`v.title IS NULL OR v.title = '' OR v.description IS NULL OR v.description = ''`。
  - 处理流：对每个 `video_id` 调用 `auto_import_nfo_for_video`。
  - 进度与统计：成功/无 NFO/解析失败/入库失败计数；完成后刷新列表。
- 菜单调整：
  - `导入NFO文件`：指向改造后的自动导入实现（作用于选中项，无文件对话框）。
  - `批量导入NFO信息`：指向新 `batch_import_nfo_for_missing_info`（全库在线 + 缺失信息）。
  - 保留 `批量导入JAVDB信息` 作为无 NFO 时的回退路径。
- 兼容性与鲁棒性：
  - 路径大小写不敏感、支持多平台分隔符；
  - 解析失败/字段缺失安全回退；
  - 二进制图片读取加异常捕获；
  - 多 NFO 冲突时优先 `movie.nfo`，次选同名 `.nfo`。

## 实现步骤（按文件定位）
1. `media_library.py:3412` 改造 `import_nfo(self)`：去除 `filedialog`，读取选中视频 ID，逐个调用 `auto_import_nfo_for_video`。
2. 删除或重定向早期 `parse_nfo_file`（`media_library.py:3431`–`3479`）到增强版；统一返回结构化 `nfo_data`。
3. 新增 `auto_import_nfo_for_video(self, video_id)`，路径匹配与入库复用 `import_nfo_from_context` 的写入逻辑（`media_library.py:9656`–`9769`）。
4. 新增 `batch_import_nfo_for_missing_info(self)`：
   - 生成在线视频集合；
   - 以合并条件查询缺失信息视频；
   - 遍历调用 `auto_import_nfo_for_video`；
   - 进度/统计与刷新。
5. 更新菜单绑定：
   - `file_menu.add_command(label="导入NFO文件", command=self.import_nfo)`（`media_library.py:793`）保持不变但指向新行为；
   - 将 `批量导入NFO信息` 绑定到新批量函数。

## 失败回退与边界
- 无 NFO：保留到计数“未找到 NFO”，不写库；可引导改用 `批量导入JAVDB信息`。
- NFO 解析异常：计数并跳过该视频；日志记录文件路径。
- 字段缺失：按“仅填补空缺”策略处理，避免覆盖已有人工整理。

## 验证
- 选取含 JavSP 结构样例目录，测试：
  - 单次导入针对选中行，自动识别 `movie.nfo`/同名 `.nfo` 并完整入库；
  - 批量导入在“仅显示在线”开启的场景下，能覆盖无演员/无 JAVDB 标题/无标题描述的项；
  - 完成后检查 `videos/javdb_info/actors/tags`、封面与缩略图字段均正确填充；
  - 统计输出与 UI 刷新如预期。