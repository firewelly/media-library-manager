## 目标
- 在 `media_library.py` 的右键菜单新增“迁移 JavSP 视频”功能，支持单选与多选。
- 选择目标媒体库路径后，将视频与相关 JavSP 生成文件迁移到目标库中，保留原相对层级，跳过“#整理完成/整理完成”这一层。
- 文件名冲突时执行“库内检查→合并或重命名”的逻辑；更新数据库记录，保持界面与数据一致。

## UI改动
- 在右键菜单构建处新增两项：
  - 单文件：在 `show_context_menu` 里为单选增加“迁移JavSP到”子菜单，列出在线媒体库路径（取自 `folders` 表）。参考 `media_library.py:5737`、`media_library.py:5820`。
  - 多文件：为多选增加“批量迁移JavSP到”子菜单。参考 `media_library.py:5856`、`media_library.py:5866`。
- 子菜单项点击后调用新函数：
  - `migrate_javsp_file_to_library(video_id, file_path, target_library_path)`
  - `batch_migrate_javsp_files_to_library(target_library_path)`

## 迁移规则
- 识别源库根路径：从 `folders` 表（`is_active=1`）取所有路径，执行最长前缀匹配以确定源库根。若找不到，退化为以视频所在目录作为起点。
- 计算相对子路径：`rel = os.path.relpath(dir_of_video, source_root)`，移除首层目录名为 `“#整理完成”` 或 `“整理完成”`（两者都兼容）。
- 目标目录：`dest_dir = os.path.join(target_library_path, rel)`，不存在则递归创建。
- 视频文件迁移：`dest_file = os.path.join(dest_dir, original_file_name)`，执行冲突处理后移动。

## 文件冲突处理
- 若 `dest_file` 已存在：
  - 查询数据库是否已有同名视频位于目标库下（`file_name` 匹配且 `file_path LIKE target_library_path || '%'`）。参考更新逻辑：`media_library.py:6555`、批量：`media_library.py:6173`。
  - 若存在对应视频记录与物理文件：执行“合并”策略（不复制视频，仅迁移元数据到该现有视频所在目录，并删除源视频与其数据库记录）。
  - 若不存在对应记录：对新文件执行 `_1`,`_2` 等序号后缀重命名再移动（参考批量移动的重命名策略 `media_library.py:6196-6201`）。

## 元数据文件处理
- 依据 JavSP 文档识别相关文件（参考 `requirements/JavSP整理规则与文件夹结构说明.md`）：
  - 必选：`[番号].nfo`、`poster.jpg`
  - 可选：`fanart.jpg`、`[番号]-thumb.jpg`、`extrafanart/` 目录
- 在源视频同目录扫描上述文件与目录：
  - 迁移至 `dest_dir`；若合并到库内已有视频，则迁移到该视频目录。
  - 冲突时：若大小一致则跳过；否则添加 `_1` 序号后缀重命名再迁移。

## 数据库更新
- 成功移动视频后：`UPDATE videos SET file_path=?, source_folder=? WHERE id=?`，其中 `source_folder` 设为新视频的父目录。参考 `media_library.py:6571-6574`。
- 合并到库内已有视频：
  - 移动元数据后删除源视频物理文件与其记录：`DELETE FROM videos WHERE id=?`。
  - 保留现有视频记录不变。
- 批量操作采用 `ProgressWindow` 展示进度与可取消。参考 `media_library.py:6173-6247`、`media_library.py:122-234`。

## 实现要点
- 新增方法：
  - `find_source_root_for_path(file_path) -> str | None`（最长前缀匹配）
  - `compute_javsp_relative_subdir(source_root, video_dir) -> str`（移除首层“整理完成/#整理完成”）
  - `collect_javsp_sidecar_files(video_dir, base_num) -> List[paths]`（按规则收集 .nfo / poster / fanart / thumb / extrafanart）
  - `resolve_conflict_for_file(dest_path) -> final_dest_path | existing_video_dir`
- 路径与文件操作使用 `os.path`、`os.makedirs`、`shutil.move`，跨平台兼容。
- 统一刷新视图：批量与单个均在提交后调用 `self.filter_videos()` 刷新。参考 `media_library.py:6577-6579`、`media_library.py:6223-6225`。

## 验证与测试
- 单文件迁移：从 `.../整理完成/.../[番号].mp4` 迁移到其他库，验证相对层级保留与元数据同行迁移。
- 冲突合并：目标目录已有 `[番号].mp4` 与记录，确认仅元数据被合并、源记录被删除。
- 冲突重命名：目标不存在对应记录但有同名文件，确认自动重命名并更新数据库。
- 批量迁移：多选后执行，查看进度窗口与取消逻辑。

## 回退策略
- 出错时显示 `messagebox.showerror`，不中断其他文件的迁移；失败文件列表在进度窗口汇总。
- 避免覆盖：所有覆盖行为需显式确认或走重命名分支。

## 后续扩展（可选）
- 合并时解析 `.nfo` 将标签/演员信息写回数据库或合并到现有记录。
- 可配置“是否保留源文件”的开关（当前默认移动）。