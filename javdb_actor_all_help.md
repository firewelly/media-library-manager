# javdb_actor_all.py 使用说明（帮助文档）

本文档说明 `javdb_actor_all.py` 的调用方法、默认行为与可选开关，帮助你根据需求调整筛选与登录策略。

## 快速开始

- 默认仅抓取“单体且有磁性链接”的作品（`t=d,s`），并在所有分页保持一致筛选：
  - `python javdb_actor_all.py https://javdb.com/actors/yAW`
- 恢复旧行为（不限定单体，仅“有磁性链接”，`t=d`）：
  - `python javdb_actor_all.py https://javdb.com/actors/yAW --legacy-filter`

## 调用方法

- 基本参数：
  - `actor_url` 必填，示例：`https://javdb.com/actors/yAW`
  - `--from` 起始页，默认 `1`
  - `--to` 结束页，默认自动探测最大页
  - `--name` 指定演员名（可选，不提供则自动提取或使用ID）
  - `--csv` 输出 CSV 路径（可选，存在则启用断点续爬并追加写入）

- Edge 配置与会话持久化：
  - `--user-data-dir` 指定 Edge 用户数据目录，如 `~/Library/Application Support/Microsoft Edge`
  - `--profile-directory` 指定 Edge 配置目录名（一般为 `Default`）
  - `--use-dedicated-profile` 使用项目专用目录持久化登录态，避免与系统 Edge 冲突（推荐）
    - 专用目录位置：项目根目录下 `.<edge_driver_user_data>/<timestamp>/Default`
    - 首次需要手动登录，后续将复用同一目录保持登录态

- 行为开关与节奏：
  - `--legacy-filter` 恢复旧筛选（仅 `t=d`，不限定单体）。默认行为为 `t=d,s`（单体且有磁性链接）。
  - `--min-delay` 最小随机等待秒数，默认 `3.0`
  - `--max-delay` 最大随机等待秒数，默认 `7.0`
  - `--no-human-actions` 禁用模拟人类滚动与鼠标移动（默认开启）

## 默认行为与差异说明

- 作品筛选：
  - 默认：`t=d,s`，仅抓取“单体且有磁性链接”。
  - 旧版：`t=d`，抓取“有磁性链接”（包含合辑/合集等非单体）。
  - 程序会在第 1 页和后续分页统一覆盖 URL 的 `t` 参数与 `sort_type=0`，确保筛选与排序一致。

- Edge 运行状态与会话目录：
  - 若系统 Edge 处于运行状态，脚本会自动避免复用系统登录态以规避用户数据目录被占用的锁冲突。
  - 推荐启用 `--use-dedicated-profile` 使用项目专用目录，以实现登录态持久化且不与系统 Edge 冲突。

- 登录流程：
  - 首次或登录态失效时，脚本会检测到安全验证/登录页，提示你在浏览器中手动完成认证。
  - 默认最大等待时间为约 300 秒；完成后继续爬取流程。

## 示例

- 仅抓取单体且有磁性链接（默认）：
  - `python javdb_actor_all.py https://javdb.com/actors/yAW`

- 恢复旧行为（包含非单体的有磁性链接）：
  - `python javdb_actor_all.py https://javdb.com/actors/yAW --legacy-filter`

- 指定输出 CSV 并使用专用会话目录（推荐）：
  - `python javdb_actor_all.py https://javdb.com/actors/yAW --csv actor_yAW.csv --use-dedicated-profile`

- 自定义分页与节奏：
  - `python javdb_actor_all.py https://javdb.com/actors/yAW --from 1 --to 5 --min-delay 2 --max-delay 4`

## 常见问题

- 为什么结果数量与旧版不同？
  - 默认筛选已改为 `t=d,s`，仅抓取单体作品；旧版 `t=d` 会包含合辑等非单体条目。使用 `--legacy-filter` 可恢复旧行为。

- 如何确认筛选生效？
  - 在地址栏查看分页 URL，应包含 `t=d,s&sort_type=0&page=N`（或在 legacy 模式下为 `t=d&sort_type=0&page=N`）。

- 登录态如何持久化？
  - 使用 `--use-dedicated-profile` 后，脚本会在项目内创建并复用专用用户数据目录，实现跨会话复用登录（同一天或更长时间）。

## 环境准备

- Python 版本：建议 `Python 3.10+`（本项目使用 `3.12` 开发与测试）。
- 依赖安装：
  - `pip install -r requirements.txt`
- Edge 与驱动：
  - 安装 Microsoft Edge（稳定版）。
  - 确保 `msedgedriver` 版本与 Edge 浏览器版本匹配；若不匹配会出现驱动无法启动或会话异常。
  - 可使用脚本 `update_msedge_driver.py` 更新驱动版本。

## URL 构建与筛选逻辑

- 第 1 页与后续分页统一覆盖筛选与排序：
  - 默认：`t=d,s&sort_type=0`
  - 旧版：`t=d&sort_type=0`（通过 `--legacy-filter` 启用）
- 无论输入的 `actor_url` 原本是否包含 `t` 或 `sort_type`，程序都会按上述规则规范化，分页会追加 `page=N` 并保持相同筛选。
- 设计目的：避免网站在导航或翻页时重置筛选，确保采集结果稳定一致。

## 登录与等待策略

- 随机延迟：默认区间 `3.0–7.0` 秒（可通过 `--min-delay` 与 `--max-delay` 调整）。
- 人类行为模拟：默认启用（滚动、鼠标移动）；使用 `--no-human-actions` 可关闭。
- 驱动启动重试：遇到浏览器驱动瞬时失败时进行短暂重试（约 `1` 秒退避）。
- 登录等待：检测到安全验证/登录页时进入手动登录等待，最长约 `300` 秒；完成后自动继续。

## 会话目录策略（避免锁冲突与持久化登录）

- 系统 Edge 正在运行时：脚本会避免复用系统用户数据目录，以防止“用户数据目录被占用”错误。
- 推荐使用 `--use-dedicated-profile`：
  - 在本项目内创建专用目录并复用，以持久化登录态且不与系统 Edge 冲突。
  - 目录形如：`. <edge_driver_user_data>/<timestamp>/Default`。
- 自定义目录：
  - `--user-data-dir` 指定根目录；`--profile-directory` 指定子目录名（常见为 `Default`）。
  - 可结合专用目录使用，实现更精细的多会话管理。

## CSV 断点续爬

- 指定 `--csv path/to/file.csv` 后：
  - 若文件存在，程序会加载已处理链接并跳过，继续追加写入，避免重复采集。
  - 若不存在，会新建并写入采集结果。

## 并行运行与目录清理建议

- 并行采集：
  - 建议为每个并行实例使用不同的专用会话目录（自动创建或手动指定）。
  - 避免多个实例共用同一用户数据目录，以免出现锁冲突或会话串扰。
- 清理策略：
  - 专用会话目录可按日期或任务清理，删除无用的旧目录以节省空间。

## 常见问题与解决

- Q：运行报错“用户数据目录被占用/锁定”？
  - A：系统 Edge 正在运行或被其他进程占用。使用 `--use-dedicated-profile` 或退出系统 Edge 后再运行。
- Q：始终跳转到登录/安全验证页？
  - A：需要手动完成验证与登录，之后会复用该登录态。若登录态失效，请重新验证或更换专用目录。
- Q：驱动版本不匹配导致无法启动？
  - A：使用 `update_msedge_driver.py` 更新驱动，或手动安装与浏览器版本一致的 `msedgedriver`。
- Q：结果数量与预期不一致？
  - A：检查是否使用了默认筛选 `t=d,s`（仅单体）。如需包含非单体，使用 `--legacy-filter`。