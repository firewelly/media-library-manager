# javdb_actor_all.py 使用说明（帮助文档）

本文档说明 `javdb_actor_all.py`（**Playwright 版**）的调用方法、默认行为与可选开关，帮助你根据需求调整筛选与登录策略。

> 版本说明：本脚本已由 Selenium + Edge 重构为 Playwright，登录态改由持久化浏览器配置目录保存；
> Edge 专属参数（`--user-data-dir` / `--profile-directory` / `--use-dedicated-profile`）已移除，
> 替换为 `--browser` / `--profile-mode` / `--headless` / `--proxy`。

## 快速开始

- 默认仅抓取“单体且有磁性链接”的作品（`t=d,s`），并在所有分页保持一致筛选：
  - `python javdb_actor_all.py https://javdb.com/actors/yAW`
- 抓取该演员**全部单体作品**（含无磁力，`t=s`）：
  - `python javdb_actor_all.py https://javdb.com/actors/yAW --filter s`
- 恢复旧行为（不限定单体，仅“有磁性链接”，`t=d`）：
  - `python javdb_actor_all.py https://javdb.com/actors/yAW --legacy-filter`
- 兼容 README 旧的位置参数写法（演员名、最大页数）：
  - `python javdb_actor_all.py https://javdb.com/actors/yAW あやみ旬果 3`

## 调用方法

- 位置参数：
  - `actor_url` 必填，示例：`https://javdb571.com/actors/5Dya`
  - `actor_name_pos` 可选，演员名，等价于 `--name`
  - `max_pages_pos` 可选，最大页数，等价于 `--to`

- 基本参数：
  - `--from` 起始页，默认 `1`
  - `--to` 结束页，默认自动翻到末页（连续两页无新链接即判定末页）
  - `--name` 指定演员名（可选，不提供则从页面 `strong.current-title` 自动提取，兜底使用演员ID）
  - `--csv` 输出 CSV 路径（可选，存在则启用断点续爬并追加写入）

- 筛选参数：
  - `--filter` 列表过滤参数 `t` 的值，默认 `d,s`（单体 + 可下载）
    - `s` = 全部单体作品（含无磁力）；`d` = 仅可下载；`a` = 全部
  - `--legacy-filter` 等价于 `--filter d`（旧版行为，不限定单体）

- 浏览器与登录态（Playwright）：
  - `--browser {msedge,chromium,firefox}` 浏览器内核，默认 `msedge`（缺失时自动回退 chromium）
  - `--profile-mode {persisted,fresh}` 默认 `persisted`：
    - `persisted`：复用固定配置目录 `.playwright_user_data/<browser>`，**与 `javdb_crawler_single.py` 共用登录态**
    - `fresh`：每次新建临时配置目录，用完自动清理
  - `--headless` 无头运行（默认有头窗口，便于通过 Cloudflare/人工验证）
  - `--login` 只打开持久会话浏览器进行手动登录，登录态保存后退出（无需演员链接）

- 代理与网络：
  - 自动判断：`javdb.com` 主站默认走 SOCKS5 代理（`config.py` 的 `SOCKS5_PROXY_HOST/PORT`）；
    镜像域名（`javdbNNN.com`）默认直连。
  - `--proxy` 强制走代理；`--no-proxy` 强制直连。
  - 注意：登录态按域名隔离。若用镜像域名抓取且未登录，会被重定向到登录页；此时建议改用
    `https://javdb.com/actors/<id>`（走代理）复用已有登录态。

- 行为开关与节奏：
  - `--min-delay` 最小随机等待秒数，默认 `3.0`
  - `--max-delay` 最大随机等待秒数，默认 `7.0`
  - `--no-human-actions` 禁用模拟人类滚动与鼠标移动（默认开启）

## 默认行为与差异说明

- 作品筛选：
  - 默认：`t=d,s`，仅抓取“单体且有磁性链接”。
  - 旧版：`t=d`，抓取“有磁性链接”（包含合辑/合集等非单体）。
  - 程序会在第 1 页和后续分页统一覆盖 URL 的 `t` 参数与 `sort_type=0`，确保筛选与排序一致。

- 分页终止：
  - 逐页解析 `div.item a[href*="/v/"]`；连续 2 页没有新链接即判定到达末页。

- 登录流程：
  - 检测到 Cloudflare 验证页时自动等待通过（轮询 + 刷新 + 首页恢复），失败后退回人工处理。
  - 检测到年龄确认页时自动点击确认按钮。
  - 检测到登录页时尝试用环境变量 `LOGIN_EMAIL` / `LOGIN_PASSWORD` 自动填充，
    随后进入人工等待（按回车立即继续，最长约 300 秒）。
  - 游客状态下仍会继续抓取，但 JavDB 多数页面需要登录，建议先执行 `--login`。

## 示例

- 仅抓取单体且有磁性链接（默认）：
  - `python javdb_actor_all.py https://javdb.com/actors/yAW`

- 抓取全部单体作品并写入指定 CSV：
  - `python javdb_actor_all.py https://javdb.com/actors/5Dya --filter s --csv results/javdb_5Dya_solo.csv`

- 恢复旧行为（包含非单体的有磁性链接）：
  - `python javdb_actor_all.py https://javdb.com/actors/yAW --legacy-filter`

- 手动登录并保存登录态（推荐首次使用）：
  - `python javdb_actor_all.py --login`

- 自定义分页与节奏：
  - `python javdb_actor_all.py https://javdb.com/actors/yAW --from 1 --to 5 --min-delay 2 --max-delay 4`

## 常见问题

- 为什么结果数量与旧版不同？
  - 默认筛选为 `t=d,s`（仅单体且可下载）；`--filter s` 会包含无磁力的单体作品；
    旧版 `t=d` 会包含合辑等非单体条目，可用 `--legacy-filter` 恢复。

- 如何确认筛选生效？
  - 在日志输出的分页 URL 中确认包含 `t=<filter>&sort_type=0`（后续页为 `&page=N`）。

- 登录态如何持久化？
  - 默认 `persisted` 模式：登录态保存在 `.playwright_user_data/<browser>`，跨会话复用。
  - 授权 `--login` 或人工登录一次后，后续爬取（含 `javdb_crawler_single.py`）自动复用。

- 抓取时被重定向到登录页怎么办？
  - 先 `python javdb_actor_all.py --login` 完成登录；若使用镜像域名，注意镜像域名与
    `javdb.com` 的登录态不互通，建议直接用 `javdb.com` + 代理。

- 输出到哪里？
  - 未指定 `--csv` 时，CSV 默认写入 `results/javdb_<演员名>.csv`；
    若检测到同名历史 CSV，会自动启用断点续爬。

## 环境准备

- Python 版本：建议 `Python 3.10+`。
- **解释器注意**：本机 `playwright` 安装在 conda base 环境，请使用该环境运行：
  - `/opt/homebrew/Caskroom/miniforge/base/bin/python3 javdb_actor_all.py ...`
  - 若直接用 Homebrew 的 `python3`（`/opt/homebrew/bin/python3`）会报
    “Playwright 未安装，请先: pip install playwright”。
- 依赖安装：
  - `pip install -r requirements.txt`
  - `playwright install msedge`（或 `playwright install chromium`）
- 可选环境变量（自动登录用）：
  - `LOGIN_EMAIL` / `LOGIN_PASSWORD`

## CSV 断点续爬

- 指定 `--csv path/to/file.csv` 后：
  - 若文件存在，程序会加载已处理的 `detail_url` 并跳过，继续追加写入，避免重复采集。
  - 若不存在，会新建并写入采集结果。
- CSV 字段（与 Selenium 版一致，可直接续爬旧文件）：
  - `title, actor, release_date, video_id, detail_url, studio, rating, duration, magnet_link, all_magnet_links`

## 与本地数据库比对

抓取完成后可用 `compare_actor_missing.py` 找出本地缺失作品：

```bash
python3 compare_actor_missing.py "results/javdb_5Dya_solo.csv" --actor-id 489 --link-domain javdb571.com
```

- 输出 CSV + Markdown 缺失清单（含 JavDB 链接、发行日期、评分、是否有磁力）。
- 比对口径：`javdb_info.javdb_code` ∪ 由 `videos.file_name` 提取的番号。

## 并行运行与目录清理建议

- 并行采集：
  - `persisted` 模式下请勿多个实例共用同一配置目录（会出现锁冲突）；
    需要并行时给部分实例加 `--profile-mode fresh`。
- 清理策略：
  - 临时会话目录位于 `.playwright_user_data_fresh/`，正常退出后会自动清理；
    可定期清理残留目录释放空间。
