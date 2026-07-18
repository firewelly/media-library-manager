# 智能媒体库管理系统

一个功能强大的跨平台视频媒体库管理软件，支持本地和NAS存储的视频文件智能管理。具备MD5去重、智能更新、演员信息管理、批量操作等高级功能。

## 📂 核心组件说明

本系统包含多个专门的工具脚本，分别负责爬虫、维护、更新等不同任务。以下是根目录下主要脚本的功能说明：

### 🖥️ 主程序

本项目有两个**可用入口**（共享同一套后端：数据库、爬虫、文件操作、`utils/` 工具层）：

| 版本 | 入口 | 工具包 | 定位 | 推荐场景 |
|------|------|--------|------|----------|
| **经典版（Tkinter）** | `media_library.py` | Tkinter | 单文件、历史悠久、功能最全 | 老用户、轻量环境、兼容旧系统 |
| **PySide6 v2（推荐）** | `media_library_v2.py` | PySide6 | 模块化包、双主题、高性能、对齐 ui_design | 日常使用、大数据量 |

> ⚠️ **关于其他版本**：
> - `media_library_pyside.py`（PySide6 v1）：v2 的前身，单文件桥接版，已被 v2 取代，**不再维护**。
> - `media_library_v4.py`（PySide6 v4）：早期并行实验版本，**已废弃、不可用**，勿使用。
>
> **可用的主要是 Tk 版和 v2 两个入口。**

> **Tk 与 v2 的关系**：v2 通过 `gui_adapter` 桥接复用 Tk 版（`media_library.py`）的全部后端方法（166 个方法动态绑定到 Qt 窗口），**零改动后端代码**。Tk 版既是独立应用，也是 v2 的逻辑库。

#### PySide6 v2（推荐版本）

基于 `ui_design/` 设计稿实现，模块化包结构，支持双主题切换，针对万级数据量做了性能优化。

**启动：**
```bash
# 方式 1：模块入口（推荐）
python -m pyside_v2.app

# 方式 2：直接运行
python pyside_v2/app.py
```

**主要特性：**
- 🎨 **双主题**：影院感深色（琥珀金强调）+ Fluent 浅色（青蓝强调），顶部一键切换，选择持久化
- ⚡ **高性能列表**：`QTableView + QAbstractTableModel` 分页（300条/页），首屏 0.5s（Tk 全量加载需 31s+）
- 🔍 **异步查询**：搜索/筛选在后台线程执行，UI 不冻结（SQLite 大库冷查询 2-5s 期间仍可操作）
- 🧭 **侧栏导航**：全部/收藏/最近/无标签 + 存储位置（自动加载 NAS 文件夹）+ 管理入口
- 🎴 **卡片式详情**：右侧悬浮卡片（封面 + 可编辑标题/标签/描述 + 8 个操作按钮）
- 🗂️ **模块化结构**：按职责拆分（`widgets/` `dialogs/` `workers/` `theme/` `windows/`）

**与 Tk 经典版的关系：**
- ✅ **完全对齐**：文件/工具/界面菜单全部功能（扫描、导入、去重、MD5、JAVDB 抓取、标签/文件夹管理、演员详情等）均通过 `gui_adapter` 桥接复用，零改动后端
- 🆕 **v2 新增**（Tk 版没有的增强功能）：
  - **演员库浏览**：网格卡片式浏览全部演员（头像/名字/作品数），支持搜索/排序/收藏筛选/翻页，点击进详情（v1 只能搜索单个演员）
  - **双主题切换**：深色影院风 ↔ 浅色 Fluent，运行时一键切换并持久化
  - **高性能分页**：49000+ 视频首屏 0.5s（v1 全量加载 31s+）
  - **异步查询**：搜索/筛选不冻结 UI
  - **侧栏导航**：收藏/最近/无标签/存储位置一键筛选

**性能优化（针对 49000+ 视频的真实库验证）：**

| 场景 | Tk 经典版 | PySide v2 | 提升 |
|------|-----------|-----------|------|
| 首屏加载 | ~31s（全量 JOIN 卡顿） | **0.5s**（分页 + 索引） | 60x |
| 搜索（热查询） | 卡顿 | **0.1-0.6s** | - |
| 翻页 | 重新全量查询 | **0.04s** | - |
| UI 响应 | 查询时冻结 | **异步不冻结** | - |

> 优化手段：复合索引 `(is_nas_online, file_created_time)`、`id IN (子查询)` 替代 OR LIKE、查询在 `QueryWorker` 后台线程执行。

**包结构：**
```
pyside_v2/
├── app.py                 # 入口：init_qt_logging → 主题 → MainWindow
├── core/
│   ├── bridge.py          # MediaLibraryCore（后端 facade，原样移入）
│   └── logging.py         # Qt 日志路由（monkey-patch 后端 _output_log）
├── theme/
│   ├── base.qss           # 双主题共用样式模板（占位符插值）
│   ├── theme_manager.py   # 主题加载/切换/持久化
│   └── colors.py          # 设计令牌 + 调色板（对齐 ui_design）
├── widgets/
│   ├── video_model.py     # QAbstractTableModel（分页 + 核心字段）
│   ├── video_table.py     # QTableView（翻页/排序/右键）
│   ├── star_delegate.py   # 星级金黄色绘制
│   └── sidebar.py         # 左侧导航栏
├── dialogs/
│   ├── import_videos.py   # 导入视频（三阶段 worker，对齐 Tk 流程）
│   ├── tag_manager.py     # 标签管理
│   ├── folder_manager.py  # 文件夹管理
│   ├── jav_info_dialog.py # JAV 信息面板
│   ├── actor_browser.py   # 演员库浏览（v2 新增·网格卡片）
│   └── actor_detail.py    # 演员详情
├── workers/
│   └── query_worker.py    # 异步查询线程
└── windows/
    └── main_window.py     # 主窗口（组装 + 菜单 + 桥接 + 信号路由）
```

#### Tk 经典版

单文件 `media_library.py`（~12600 行），自包含的 Tkinter 应用。既是独立 GUI，也是 v1/v2 import 的逻辑库（`MediaLibrary` 类）。

```bash
python media_library.py
```

### 🚀 启动入口

两个可用入口在根目录都有对应的 Python 入口文件：

| 入口文件 | 启动版本 | 说明 |
|----------|----------|------|
| `media_library.py` | Tk 经典版 | 单文件，历史悠久 |
| `media_library_v2.py` | PySide6 v2（推荐） | 模块化包 `pyside_v2/`，双主题·高性能 |

```bash
python media_library.py            # Tk 经典版
python media_library_v2.py         # PySide6 v2（推荐·双主题·高性能）
```

另有跨平台启动脚本（自动检查 Python + 按需装 PySide6）：

| 脚本 | 平台 | 启动版本 |
|------|------|----------|
| `start_media_library.sh` | macOS / Linux | Tk 经典版 |
| `start_media_library_v2.sh` | macOS / Linux | PySide6 v2（推荐） |
| `start_media_library_v2.bat` | Windows | PySide6 v2（推荐） |

> macOS 用户也可用 Spotlight（`⌘ + 空格`）搜索 `Media Library` 启动 Tk 版，或 `Media Library v2` 启动 v2（双击对应的 `.app`）。

### 🕷️ 数据爬虫与登录
- **`javdb_login_helper.py`**: **[基础组件]** JAVDB 登录助手。使用独立的浏览器用户数据目录（`~/.javdb_scraper/user_data` 或本地 `.edge_driver_user_data`）来持久化登录状态，只需登录一次即可供所有爬虫脚本使用。
- **`javdb_crawler.py`**: 批量爬虫工具，支持自动遍历页面抓取视频信息。
- **`javdb_crawler_single.py`**: 单视频抓取工具，用于精确获取指定番号的信息。
- **`javdb_actor_all.py`**: 演员作品全量爬虫，支持抓取指定演员的所有作品、磁力链接，并支持断点续传。
- **`actor_crawler_with_db.py`**: 演员资料爬虫，抓取演员头像及详细资料并存入数据库。
- **`javbus_crawler_single.py`**: JavBus 源的抓取工具，作为数据补充。
- **`javsp_*.py` (JavSP 系统)**: **[三级回退备选]** 多源爬虫系统，集成了 JavBus、JavLibrary、AvSox、FC2 等多个数据源。当主爬虫无法获取完整信息时自动降级使用，通过 `javsp_integration.py` 与媒体库无缝集成。

### 📦 媒体库维护与更新
- **`smart_video_updater.py`**: **[核心维护]** 智能更新工具。支持 NAS 路径映射，可利用预计算的 MD5 CSV 文件加速大型媒体库的导入和更新。
- **`fast_smart_media_updater.py`**: 快速扫描工具。针对特定文件夹进行增量更新，高效处理文件的移动和删除。
- **`unified_video_updater.py`**: 元数据同步工具。根据 MD5 或文件名匹配，批量更新视频的标签、描述等信息。
- **`import_videos_from_md5.py`**: 批量导入工具。基于 MD5 列表快速导入视频，支持过滤特定文件。
- **`resumable_smart_importer.py`**: 支持断点续传的智能导入器，适合超大规模文件库。

### 🛠️ 辅助工具
- **`video_integrity_checker.py`**: 坏档检测工具。批量检查视频文件是否完整、能否正常播放（基于 OpenCV）。
- **`update_msedge_driver.py`**: 驱动更新工具。自动检测系统 Edge 浏览器版本并下载对应的 WebDriver，解决爬虫驱动不兼容问题。
- **`init_database.py`**: 数据库初始化脚本，用于首次运行时创建必要的数据库表结构。

### 🔬 基于 AI 的视频内容分析（video_analyzer/）

`video_analyzer/` 目录提供了一套基于 SiliconFlow API 的视频内容分析工具，能够自动为成人视频生成内容标签：

- **`production_video_analyzer_fixed.py`**: 生产级批量分析主脚本
- **`video_analyzer_local_model_adult.py`**: 基于 Qwen3-VL-30B-A3B（MoE架构）的帧分析器
- **`video_analyzer_pipeline.py`**: 流水线分析器，帧提取串行 + API 调用并行
- **`adapter.py`**: GUI 桥接层

#### 核心技术参数

| 项目 | 配置 |
|------|------|
| API | `https://api.siliconflow.cn` |
| 模型 | `Qwen/Qwen3-VL-30B-A3B-Instruct`（MoE，比8B更快更强） |
| 动态帧数 | >10分钟按1帧/分钟，最多30帧；≤10分钟固定8帧 |
| 标签 | 最多7个，特殊特征优先 |
| 分析规则 | 仅关注女性主角，忽略男性人物 |

#### 推荐使用命令

```bash
# 全量补标签（流水线模式，帧提取串行+API并行）
cd /Users/firewell/bin/media/video_analyzer && python3 production_video_analyzer_fixed.py --pipeline --workers 10 --verbose

# 测试模式（处理10个视频）
cd /Users/firewell/bin/media/video_analyzer && python3 production_video_analyzer_fixed.py --pipeline --workers 10 --limit 10 --verbose
```

> `--workers` 限制同时等待API响应的线程数（建议10）。帧提取始终单线程串行，不抢占CPU。

#### 标签优先级

```
特殊特征（最高）→ 如：体型特征、身体状态类标签
服装特征         → 如：衣着、配饰类标签
情节特征         → 如：剧情、关系类标签
人物特征         → 如：身份、年龄、体态类标签
行为特征（最低） → 如：动作、互动类标签
```

---

## 📺 JAVDB信息更新工具

`javdb_information_updater.py`是一个专门用于从JAVDB网站获取和更新JAV视频信息的工具。这个工具可以帮助您自动获取视频的详细信息，包括演员、标签、发布日期、时长、评分等。

### 🔧 主要功能

- **自动登录JAVDB** - 使用专用的浏览器用户数据目录来持久化登录状态
- **批量更新视频信息** - 自动识别需要更新的视频
- **按番号刷新特定视频** - 可以单独刷新某个特定番号的视频信息
- **刷新所有视频信息** - 可以重新刷新所有视频的信息

### 🖥️ 命令行参数

```bash
python3 javdb_information_updater.py [选项]
```

#### 选项说明

- `--code <番号>`: 按番号刷新特定视频，如 `--code ADN-347`
- `--refresh-all`: 刷新所有视频信息，包括已更新的视频
- `--test`: 测试模式
- `--test-folder <路径>`: 测试文件夹路径

### 🚀 使用示例

#### 1. 按番号刷新特定视频

```bash
python3 javdb_information_updater.py --code ADN-347
```

这个命令会：
- 启动浏览器并检查登录状态
- 如果未登录，会提示您手动登录
- 自动搜索并更新番号为ADN-347的视频信息

#### 2. 刷新所有视频信息

```bash
python3 javdb_information_updater.py --refresh-all
```

这个命令会：
- 启动浏览器并检查登录状态
- 让您选择要更新的文件夹
- 刷新该文件夹下所有视频的信息

#### 3. 仅更新需要更新的视频（默认行为）

```bash
python3 javdb_information_updater.py
```

这个命令会：
- 启动浏览器并检查登录状态
- 让您选择要更新的文件夹
- 仅更新那些没有JAVDB信息或演员信息不完整的视频

### 📋 测试脚本

工具还提供了一个测试脚本，用于查看特定番号视频的当前信息：

```bash
python3 test_refresh_by_code.py [番号]
```

如果不提供番号参数，默认会测试ADN-347。

### ⚠️ 注意事项

1. 第一次使用时，需要手动登录JAVDB账号
2. 为避免被JAVDB的反爬机制阻止，工具会在操作之间添加随机延迟
3. 使用专用的浏览器用户数据目录保存登录状态，路径为：`~/.javdb_scraper/user_data`
4. 刷新操作可能需要一些时间，具体取决于需要更新的视频数量

---

## 📺 NAS JAVDB信息更新器

`nas_javdb_updater.py` 是 `javdb_information_updater.py` 的 NAS 批量更新专用变体，固定使用 Playwright 持久化用户目录（`.playwright_user_data/msedge`），适合后台长时间批量运行。

### 🔧 与 `javdb_information_updater.py` 的区别

| 项目 | `javdb_information_updater.py` | `nas_javdb_updater.py` |
|------|------|------|
| 爬虫调用方式 | subprocess 调用 `javdb_crawler_single.py` | 直接 import 调用爬虫函数 |
| 用户目录 | fresh(临时) + persisted(持久) 轮流尝试 | **仅 persisted** 固定目录 |
| 浏览器 | msedge + firefox | **仅 msedge** |
| 登录方式 | 每次运行可能反复要求登录 | 登录一次永久保存 |

### 🖥️ 命令行参数

```bash
python3 nas_javdb_updater.py [选项]
```

#### 选项说明

- `--code <番号>`: 按番号刷新特定视频，如 `--code ADN-347`
- `--refresh-all`: 刷新所有视频信息，包括已更新的视频
- `--test`: 测试模式
- `--test-folder <路径>`: 测试文件夹路径
- `--no-proxy`: 直连模式（不使用 SOCKS5 代理）
- `--min-delay <秒>`: 最小操作间隔（默认 1）
- `--max-delay <秒>`: 最大操作间隔（默认 3）

#### 登录机制

当 Playwright 检测到需要登录时，会自动打开有界面浏览器窗口，用户在该窗口中手工完成登录后，登录态会持久化保存到 `.playwright_user_data/msedge/` 目录，后续所有无头模式调用自动复用此会话。

### 🚀 使用示例

#### 批量更新 NAS 文件夹（直连模式，推荐）

```bash
python3 nas_javdb_updater.py --no-proxy --test --test-folder /Volumes/app/usr
```

#### 批量脚本（三个 NAS 文件夹依次处理）

参考 `_run_batch_update.py`：

```python
FOLDERS = {
    12: "/Volumes/app/usr",
    16: "/Volumes/HC530_1/JAV_H530",
    28: "/Volumes/Jav_HDD4",
}
for fid, fpath in FOLDERS.items():
    subprocess.run([sys.executable, "nas_javdb_updater.py", "--no-proxy", "--test", "--test-folder", fpath])
```

## 🧩 JavSP 多源爬虫系统集成

JavSP 是一套多源爬虫系统，作为本项目的核心数据补充层。当 JAVDB 主爬虫无法获取完整信息时，JavSP 提供三级回退策略，统一管理 JavBus、JavLibrary、AvSox、FC2 等多个数据源。

### 🔄 三级回退策略

```
JavDB (主爬虫) → JavBus (备用1) → JavSP (备用2，含 JavLib/AvSox/FC2)
```

### 📦 JavSP 模块组成

| 文件 | 说明 |
|------|------|
| `javsp_integration.py` | JavSP 与媒体库的集成接口，封装搜索与数据保存 |
| `javsp_crawler_manager.py` | 多源爬虫管理器，统一调度 JavBus/JavLib/AvSox/FC2 |
| `javsp_base.py` | 网络请求基础模块（代理、CloudScraper、重试） |
| `javsp_config.py` / `javsp_config.yaml` | 爬虫配置（代理、优先级、超时、缓存） |
| `javsp_config_manager.py` | YAML 配置加载与管理 |
| `javsp_datatype.py` | 通用影片数据类型 (`MovieInfo` dataclass) |
| `javsp_javbus.py` | JavBus 爬虫实现 |
| `javsp_javlib.py` | JavLibrary 爬虫实现 |
| `javsp_avsox.py` | AvSox 爬虫实现 |
| `javsp_fc2.py` | FC2 爬虫实现 |
| `utils/javsp_copy.py` | JavSP 视频信息复制工具 |
| `utils/javsp_migration.py` | JavSP 视频迁移工具 |

### 🔧 核心功能

- **多源并行搜索**：并发查询多个数据源，取最优结果
- **智能回退**：某源失败后自动切换到备用源
- **数据清洗**：自动清理标题中的推广关键词
- **统一数据类型**：所有源返回统一的 `MovieInfo` 格式
- **代理支持**：自动应用 SOCKS5 代理（macOS/Linux: `127.0.0.1:1080`，Windows: `127.0.0.1:8800`）

### ⚙️ 配置示例（`javsp_config.yaml`）

```yaml
crawlers:
  enabled:
    - "javbus"
    - "javlib"
    - "avsox"
    - "fc2"
  priority:
    javbus: 1
    javlib: 2
    avsox: 3
    fc2: 4
```

### 📖 GUI 集成

在主程序 GUI 中，可通过以下入口使用 JavSP 功能：
- **详情页按钮**"获取JAV信息"触发单番号搜索
- **菜单**"批量导入JAV信息"批量处理无标题视频
- **工具菜单**"JAV信息面板"手动输入番号获取信息
- 搜索进度显示在状态栏，异常以弹窗提示

---

## 🧩 按番号复制与填充工具

`copy_javdb_info_by_code.py` 用于在同番号存在更完整信息的来源视频时，批量为目标视频填充缺失的 `javdb_info` 字段与标签；当目标当前无任何演员关联时，会复制来源的演员关系。

### 主要功能
- 来源选择排序：按“信息完整度优先、更新时间次之”确定最佳来源
- 字段填充：默认仅填充目标为空的字段；可选 `--overwrite` 覆盖已有值
- 标签复制：在目标无标签时复制来源的 `javdb_info_tags`
- 演员复制：当目标视频无任何演员关联时，复制来源视频的 `video_actors`（INSERT OR IGNORE）

### 使用示例
```bash
# 干跑预览（不写入数据库）
python3 copy_javdb_info_by_code.py --folder-index 11 --dry-run --limit 5

# 小批量正式入库
python3 copy_javdb_info_by_code.py --folder-index 11 --limit 10

# 覆盖已有字段（谨慎使用）
python3 copy_javdb_info_by_code.py --folder-index 11 --overwrite
```

### 日志输出示例
```
优先来源: /Volumes/Video/usr/... (ID=33594) | 完整度=12, 更新时间=2025-10-07 22:54:41
来源: /Volumes/Video/usr/... (ID=33594)
[DRY-RUN] 填充javdb_info空字段到: /Volumes/app/usr/... | fields=<...>
[DRY-RUN] 复制JAVDB标签到目标，共 4 个
[DRY-RUN] 关联演员 726 -> /Volumes/app/usr/...
完成：填充/更新javdb_info及标签关联，并复制演员 1 条
```

## 🌟 项目特色

- 🧠 **智能化管理** - 自动检测文件移动、智能去重、批量MD5计算
- 🎭 **演员信息系统** - 完整的演员数据库，支持头像、别名、清理合并
- 📊 **实时进度显示** - 所有批量操作都有详细的进度和日志显示
- 🌐 **跨平台支持** - 支持macOS、Windows、Linux系统
- 💾 **数据安全** - 自动备份、确认机制、完整的错误处理

## 🎯 核心功能

### 📁 文件管理
- **智能扫描** - 自动扫描指定目录下的视频文件，支持多文件夹管理
- **文件移动检测** - 通过MD5哈希自动检测文件移动并更新路径
- **NAS支持** - 支持网络存储设备，实时监控在线状态
- **批量操作** - 支持批量生成缩略图、计算MD5、导入元数据

### 🏷️ 媒体信息管理
- **元数据编辑** - 支持标题、描述、标签、类型、年份等信息管理
- **智能解析** - 从文件名自动提取星级信息和基本信息
- **视频信息提取** - 自动获取视频时长、分辨率等技术信息
- **缩略图生成** - 自动生成视频封面预览

### ⭐ 评分与搜索
- **星级评分系统** - 5星评分，支持点击直接评分
- **智能搜索** - 支持关键词搜索、星级筛选、来源文件夹筛选
- **表格排序** - 点击列标题进行升序/降序排序
- **实时筛选** - 输入即时显示筛选结果

### 🎭 演员信息系统
- **演员数据库** - 完整的演员信息管理，包括姓名、别名、头像
- **智能清理** - 自动检测和合并重复演员记录
- **关联管理** - 演员与视频文件的关联管理
- **批量处理** - 支持批量导入和清理演员信息

### 🔐 智能去重与安全
- **MD5哈希计算** - 计算文件哈希值用于去重和移动检测
- **智能去重** - 基于MD5哈希值智能检测和处理重复文件
- **数据备份** - 操作前自动备份，确保数据安全
- **确认机制** - 重要操作前显示预览和确认对话框

## 🚀 快速开始

### 系统要求
- Python 3.7+
- macOS / Windows / Linux
- 推荐使用SSD存储以获得更好的性能

### 安装步骤

1. **克隆项目**
```bash
git clone <repository-url>
cd media-library
```

2. **安装依赖**
```bash
pip install -r requirements.txt
```

3. **初始化数据库**
```bash
python init_database.py
```

4. **启动应用**
```bash
# 推荐：PySide6 v2（自动检查环境 + 按需装 PySide6）
python media_library_v2.py

# 或用启动脚本（自动检查 Python + 装依赖）
./start_media_library_v2.sh            # macOS/Linux
start_media_library_v2.bat             # Windows

# 或 Tk 经典版
python media_library.py
```

### 主要依赖
- `PySide6` - 现代GUI界面
- `sqlite3` - 数据库（Python内置）
- `Pillow` - 图像处理
- `opencv-python` - 视频处理
- `python-magic` - 文件类型检测
- `requests` - 网络请求
- `beautifulsoup4` - HTML解析
- `selenium` - 网页自动化
- `PyYAML` - JavSP 配置解析
- `cloudscraper` - JavSP CloudFlare 绕过
- `lxml` - JavSP HTML 解析

## 📖 使用指南

### Windows版本

#### 📦 Windows可执行版本

为了方便Windows用户使用，项目提供了预编译的可执行文件版本，无需安装Python环境即可运行。

##### 获取方式
从GitHub Releases页面下载最新版本的 `MediaLibrary-Windows-Complete.zip` 文件。

##### 安装步骤
1. 下载并解压ZIP文件到您选择的目录，建议路径：
   ```
   C:\MediaLibrary\
   D:\MediaLibrary\
   E:\MediaLibrary\
   ```

2. 启动程序：
   - 双击 `MediaLibrary.exe` 文件启动主程序
   - 或双击 `启动媒体库.bat` 快捷启动
   - 双击 `用户手册.exe` 查看详细使用说明

3. 查看可用工具：
   - 双击 `查看可用工具.bat` 查看所有辅助工具列表
   - 所有工具位于 `bin/tools/scripts/` 目录下

##### 包含内容
- **主程序**: `MediaLibrary.exe` - 媒体库管理主程序
- **用户手册**: `用户手册.exe` - HTML格式的详细使用手册
- **辅助工具**: 20+ 个专用工具脚本（位于 `bin/tools/scripts/` 目录）
- **配置文件**: GUI配置、JAVDB配置、标签词汇表等
- **运行依赖**: FFmpeg、Edge WebDriver等必要工具

##### 工具分类
- 🕷️ **数据爬虫工具**: javdb_crawler_single.exe、javdb_actor_all.exe 等
- 📦 **媒体库维护工具**: smart_video_updater.exe、fast_smart_media_updater.exe 等
- 🔧 **系统工具**: video_integrity_checker.exe、update_msedge_driver.exe 等
- 🤖 **AI分析工具**: video_multimodal_analyzer.exe、video_tagging.exe 等

##### 快捷启动脚本
- **启动媒体库.bat**: 快速启动主程序
- **查看可用工具.bat**: 列出所有可用的辅助工具

### 首次使用
1. 启动应用后，点击菜单栏 "文件" → "添加文件夹"
2. 选择包含视频文件的目录（支持本地文件夹和NAS挂载点）
3. 系统自动扫描并导入视频文件
4. 等待缩略图生成和MD5计算完成

### 基本操作

#### 文件管理
- **浏览文件** - 在主列表中查看所有导入的视频文件
- **搜索文件** - 使用顶部搜索框输入关键词进行模糊搜索
- **筛选文件** - 使用星级筛选器和来源文件夹筛选器
- **排序文件** - 点击任意列标题进行升序/降序排序

#### 评分系统
- **快速评分** - 直接点击列表中的星级图标
- **详细评分** - 在右侧详情面板中点击星级
- **自动评分** - 文件名中的感叹号自动转换为星级
  - `!movie.mp4` = 2星
  - `!!movie.mp4` = 3星
  - `!!!movie.mp4` = 4星
  - `!!!!movie.mp4` = 5星

#### 信息编辑
1. 选择视频文件
2. 在右侧详情面板中编辑：
   - 标题、描述、标签
   - 年份、类型、评分
3. 点击"保存修改"按钮

#### 视频播放
- **双击播放** - 双击文件名直接播放
- **右键播放** - 右键选择"播放"选项
- **按钮播放** - 详情面板中的"播放视频"按钮
- **智能检测** - 自动检测文件存在性和NAS在线状态

### 高级功能

#### 智能媒体库更新
- 菜单栏 "工具" → "智能媒体库更新"
- 自动检测文件移动、添加新文件、更新MD5
- 实时显示进度和详细日志

#### 演员信息管理
- 菜单栏 "工具" → "清理演员信息"
- 自动检测和合并重复演员记录
- 支持基于URL和名称的智能合并

#### 批量操作
- **批量MD5计算** - 计算缺失或重新计算所有文件的MD5
- **智能去重** - 基于MD5哈希检测和处理重复文件
- **批量生成缩略图** - 为所有视频生成预览图

## ⚙️ 配置说明

### 数据库配置
- 数据库文件：`media_library.db`（SQLite格式）
- 自动备份：每次启动时自动创建备份
- 位置：项目根目录

### GUI配置
编辑 `gui_config.json` 文件可以自定义界面显示：
```json
{
  "columns": {
    "stars": {"text": "星级", "width": 80, "anchor": "center"},
    "title": {"text": "标题", "width": 200, "anchor": "w"},
    "file_size": {"text": "大小", "width": 80, "anchor": "center"},
    "duration": {"text": "时长", "width": 80, "anchor": "center"},
    "resolution": {"text": "分辨率", "width": 100, "anchor": "center"},
    "file_created_time": {"text": "创建时间", "width": 120, "anchor": "center"},
    "source_folder": {"text": "来源文件夹", "width": 150, "anchor": "w"}
  }
}
```

### 文件命名约定
系统支持从文件名自动解析星级：
- 只有叹号在文件名称的开头才算
- `!movie.mp4` → 2星
- `!!movie.mp4` → 3星
- `!!!movie.mp4` → 4星
- `!!!!movie.mp4` → 5星
- `movie.mp4` → 0星 (没有叹号)
- `movie.mp4!` → 0星 (叹号不在开头)

## 🗄️ 数据库结构

### videos表
主要字段：`id`, `filename`, `filepath`, `filesize`, `duration`, `resolution`, `title`, `description`, `tags`, `rating`, `year`, `genre`, `thumbnail_path`, `md5_hash`, `created_at`, `updated_at`

### actors表
主要字段：`id`, `name`, `avatar_url`, `video_id`

## 🔧 故障排除

### 常见问题解决

**视频无法播放**
- 检查文件是否存在及权限设置
- 确认文件格式支持（推荐MP4、AVI、MKV）
- 验证系统默认播放器配置

**缩略图生成失败**
- 确认FFmpeg正确安装并在PATH中
- 检查视频文件完整性
- 确保有足够磁盘空间

**性能优化建议**
- 使用SSD存储提升I/O性能
- 适当调整并发线程数
- 定期清理缓存文件

### 日志查看
应用运行时会在界面底部显示日志信息，包括：
- 文件扫描进度
- 错误信息
- 操作状态

## 🛠️ 开发说明

### 项目结构
```
media-library/
├── media_library.py              # Tk 经典版主程序（也是后端逻辑库）
├── media_library_v2.py           # PySide6 v2 启动入口（推荐）
├── pyside_v2/                    # PySide6 v2 主程序（模块化包）
│   ├── app.py                    # 入口
│   ├── core/                     # 后端桥接 + 日志
│   ├── theme/                    # 双主题 QSS + 设计令牌
│   ├── widgets/                  # 列表/侧栏/delegate
│   ├── dialogs/                  # 导入/标签/文件夹/JAV/演员对话框
│   ├── workers/                  # 异步查询线程
│   └── windows/                  # 主窗口
├── media_library_pyside.py       # [已废弃] PySide6 v1，被 v2 取代
├── media_library_v4.py           # [已废弃] PySide6 v4，不可用
├── gui_adapter.py                # Tk→PySide 桥接层（v2 用）
├── ui_design/                    # v2 设计稿（HTML/CSS 原型）
├── javsp_*.py                    # JavSP多源爬虫系统
├── javsp_config.yaml             # JavSP 配置文件
├── javdb_*.py                    # JAVDB 爬虫模块
├── utils/                        # 核心工具库
│   ├── batch_ops.py              # 批量操作管理器
│   ├── maintenance.py            # 维护工具管理器
│   ├── thumbnails.py             # 缩略图生成器
│   ├── javsp_copy.py             # JavSP 复制工具
│   ├── javsp_migration.py        # JavSP 迁移工具
│   └── ...
├── doc/                          # 完整文档体系
├── init_database.py              # 数据库初始化
├── gui_config.json               # 界面配置
├── requirements.txt              # 依赖包列表
├── start_media_library.sh        # 启动脚本：Tk 经典版（macOS/Linux）
├── start_media_library_v2.sh     # 启动脚本：PySide6 v2（macOS/Linux）
├── start_media_library_v2.bat    # 启动脚本：PySide6 v2（Windows）
└── README.md                     # 项目说明
```

## 📄 许可证

本项目采用 BSD 3-Clause 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🤝 贡献

欢迎提交Issue和Pull Request来改进这个项目！

## 📝 更新日志

### v3.3.0 (当前版本)
- 🎬 演员详情页面增强
- 📊 新增视频在线状态检测
- 💡 直观显示文件状态
- ⚡ 优化用户体验

## 🌐 新增功能详解

### JavDB演员视频爬虫 (javdb_actor_all.py)

#### 功能特点
- 🌟 **优秀架构**：代码结构清晰，错误处理完善
- 🧲 **磁力链接优先级**：-UC > -C > 其他版本
- 🔄 **智能爬取**：支持演员全量爬取，自动分页
- 🌐 **智能代理**：通过浏览器参数设置代理，避免全局修改
- 🔐 **登录处理**：智能检测登录页面，支持手工登录和验证码
- 🛡️ **多重尝试**：多种驱动启动方式，确保稳定性

#### 使用方法
```bash
# 演员全量爬取（推荐）
python javdb_actor_all.py https://javdb.com/actors/yERr 美乃雀 10

# 爬取3页
python javdb_actor_all.py https://javdb.com/actors/yERr 美乃雀 3
```

#### 输出格式
- **CSV格式**：便于Excel查看和编辑
- **JSON格式**：包含完整的爬取信息和统计数据
- **磁力链接**：按优先级排序（-UC > -C > 其他）

### 基于MD5的媒体库批量导入工具 (import_videos_from_md5.py)

#### 功能特点
- ⚡ **简洁高效**：代码结构清晰，性能优秀
- 🎯 **精准过滤**：自动过滤无效文件
- 📊 **详细统计**：提供完整的导入统计信息
- 🔍 **智能匹配**：通过MD5避免重复导入

#### 文件过滤规则
- ✅ **回收站文件**：跳过包含`#recycle`路径的文件
- ✅ **隐藏文件**：跳过以`.`开头的文件
- ✅ **小文件**：跳过小于10MB的文件
- ✅ **不存在文件**：跳过路径中不存在的文件

#### 使用方法
```bash
# 运行导入脚本
python import_videos_from_md5.py
```
