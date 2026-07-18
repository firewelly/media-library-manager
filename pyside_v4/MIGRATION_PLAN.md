# pyside_v4 迁移计划

## 项目概述

pyside_v4 是基于 media_library_pyside.py 的现代化重构版本，采用深色影院风设计（琥珀金强调色 + 玻璃拟态面板）。

## 迁移来源

- **主要来源**: `media_library_pyside.py` (268KB)
- **辅助来源**: `media_library.py` (Tkinter 版本)
- **原则**: 直接 import 已有后端模块，不创建 copy

## 目录结构

```
media/
├── media_library_v4.py          # 根目录入口文件
├── start_media_library_v4.sh    # 启动脚本
└── pyside_v4/                   # 前端 UI 包
    ├── __init__.py
    ├── app.py                   # 应用入口
    ├── core/                    # 核心模块
    │   ├── __init__.py
    │   ├── bridge.py            # 薄适配层（import MediaLibraryCore）
    │   ├── database.py          # 数据库连接
    │   ├── logging.py           # Qt 信号日志
    │   └── repository.py        # 数据访问层
    ├── theme/                   # 主题系统
    │   ├── __init__.py
    │   ├── colors.py            # 颜色常量
    │   └── qss.py               # QSS 样式表
    ├── widgets/                 # UI 组件
    │   ├── __init__.py
    │   ├── sidebar.py           # 左侧导航
    │   ├── video_table.py       # 视频列表
    │   ├── detail_panel.py      # 右侧详情面板
    │   ├── star_rating.py       # 星级评分
    │   ├── filter_bar.py        # 筛选条
    │   └── pagination.py        # 分页组件
    ├── windows/                 # 窗口
    │   ├── __init__.py
    │   └── main_window.py       # 主窗口
    ├── dialogs/                 # 对话框
    │   ├── __init__.py
    │   ├── actor_dialog.py      # 演员库
    │   ├── tag_dialog.py        # 标签管理
    │   ├── scan_dialog.py       # 扫描进度
    │   ├── settings_dialog.py   # 设置
    │   ├── task_progress_dialog.py  # 任务进度
    │   ├── folder_dialog.py     # 文件夹管理
    │   ├── smart_update_dialog.py   # 智能更新
    │   └── dedup_dialog.py      # 去重
    ├── workers/                 # 后台任务
    │   ├── __init__.py
    │   ├── data_loader.py       # 数据加载
    │   ├── cover_loader.py      # 封面图片加载
    │   └── task_worker.py       # 通用任务（import GenericWorker）
    └── actions/                 # 操作模块
        ├── __init__.py
        └── video_actions.py     # 视频操作
```

## 功能完成状态

### 阶段 1：适配层 ✅

- [x] core/bridge.py — 薄适配层，import MediaLibraryCore
- [x] core/logging.py — Qt 信号日志适配
- [x] workers/task_worker.py — 通用任务 Worker，import GenericWorker

### 阶段 2：菜单栏 + 快捷键 ✅

- [x] 菜单栏（文件/工具/界面/帮助）
- [x] 快捷键（Ctrl+R/Ctrl+F/Space/Ctrl+0-5/Enter）

### 阶段 3：右键菜单 + 批量任务 ✅

- [x] 进度对话框 TaskProgressDialog
- [x] 右键菜单（单文件+多文件）
- [x] 批量任务方法 run_batch_task
- [x] 表格多选支持（ExtendedSelection）
- [x] 功能接入（自动标签、生成封面、删除）

### 阶段 4：UI 增强 + 对话框 ✅

- [x] 分页组件（Pagination）
- [x] 文件夹管理对话框（FolderDialog）
- [x] 智能更新对话框（SmartUpdateDialog）
- [x] 去重对话框（DedupDialog）

### 阶段 5：菜单功能实现 ✅

- [x] 导入 NFO 文件
- [x] 导入视频文件
- [x] 同步打分到文件
- [x] 批量计算 MD5
- [x] 文件移动管理
- [x] 批量生成封面
- [x] 批量自动标签
- [x] 批量清理文件名
- [x] 获取 JAVDB 信息（单个）
- [x] 批量获取 JAVDB 信息
- [x] 智能去重
- [x] 重置界面布局
- [x] 最近添加筛选（30天内）
- [x] 筛选条件解析
- [x] 保存设置到配置文件

### 阶段 6：缺失功能补充 ✅

**文件菜单**
- [x] 批量导入 NFO 信息（为没有演员的视频）
- [x] 批量导入 JAVDB 信息（为没有标题的视频）

**工具菜单**
- [x] 清理演员信息
- [x] 重新导入元数据
- [x] 完全重置数据库
- [x] 批量标注没有标签的文件
- [x] 修正 JAVDB 错误信息
- [x] 快速智能媒体库更新
- [x] JAV 信息面板

**帮助菜单**
- [x] 快捷键帮助

**快捷键**
- [x] Enter 生成封面

**详情面板**
- [x] 保存修改按钮
- [x] 设置星级按钮
- [x] 添加标签按钮
- [x] 获取 JAVDB 信息按钮
- [x] 生成封面按钮
- [x] 删除视频按钮
- [x] 描述编辑框
- [x] 标签编辑框
- [x] 文件名显示
- [x] 文件大小显示
- [x] 修改时间显示
- [x] JAVDB 标题显示
- [x] 发行日期显示

## 当前进度

| 类别 | 总数 | 已完成 | 待实现 |
|------|------|--------|--------|
| 适配层 | 3 | 3 | 0 |
| UI 组件增强 | 2 | 2 | 0 |
| 主窗口增强 | 4 | 4 | 0 |
| 对话框 | 8 | 8 | 0 |
| 后台任务 | 1 | 1 | 0 |
| 菜单功能实现 | 15 | 15 | 0 |
| 缺失功能补充 | 24 | 24 | 0 |
| **合计** | **57** | **57** | **0** |

> **完成率：100%** ✅

## 启动方式

```bash
# 方式 1：直接运行入口文件
python3 media_library_v4.py

# 方式 2：使用启动脚本
./start_media_library_v4.sh
```

## 注意事项

1. **不复制后端代码**：所有后端逻辑通过 import 复用
2. **不修改原文件**：`media_library_pyside.py`、`utils/`、`javdb_system/` 等保持原样
3. **薄适配层**：`core/bridge.py` 只做接口封装，不包含业务逻辑
4. **回调转信号**：后端回调函数通过 `GenericWorker` 转为 Qt Signal
5. **v4 独立**：pyside_v4 目录只包含 UI 代码 + 适配层

## 功能清单

### 核心功能
- [x] 数据库连接（读写，49,057 条记录）
- [x] 异步数据加载（QThread）
- [x] 搜索（300ms 防抖）
- [x] 筛选（星级、在线状态、标签、文件夹、最近添加）
- [x] 排序（创建时间、标题、大小、星级）
- [x] 分页（100/200/500/1000 条/页）
- [x] 封面图片异步加载

### UI 组件
- [x] 深色影院风主题（琥珀金 #f0b429）
- [x] 三栏布局（侧栏 + 列表 + 详情）
- [x] 左侧导航（媒体库分类、存储位置）
- [x] 顶部工具栏（搜索、筛选、排序、视图切换）
- [x] 筛选条（chip 可单独移除）
- [x] 视频列表（9 列，支持多选）
- [x] 右侧详情面板（封面、信息、标签、操作按钮）
- [x] 底部状态栏（统计、性能）
- [x] 分页组件

### 菜单与快捷键
- [x] 菜单栏（文件/工具/界面/帮助）
- [x] 右键菜单（单文件+多文件）
- [x] 快捷键（Ctrl+R/Ctrl+F/Space/Ctrl+0-5/Enter）

### 对话框
- [x] 演员库（ActorDialog）
- [x] 标签管理（TagDialog）
- [x] 扫描进度（ScanDialog）
- [x] 设置（SettingsDialog）
- [x] 任务进度（TaskProgressDialog）
- [x] 文件夹管理（FolderDialog）
- [x] 智能更新（SmartUpdateDialog）
- [x] 去重（DedupDialog）

### 批量操作
- [x] 自动标签（调用 video_analyzer）
- [x] 生成封面（调用 VideoActions）
- [x] 删除视频（调用 VideoActions）
- [x] 批量自动标签
- [x] 批量生成封面
- [x] 批量删除
- [x] 批量计算 MD5
- [x] 批量清理文件名
- [x] 批量获取 JAVDB 信息
- [x] 批量导入 NFO 信息
- [x] 批量导入 JAVDB 信息
- [x] 批量标注没有标签的文件

### 适配层
- [x] core/bridge.py — import MediaLibraryCore
- [x] core/logging.py — Qt 信号日志
- [x] workers/task_worker.py — import GenericWorker

### 设置管理
- [x] 加载/保存设置到配置文件

## 更新日志

### 2026-07-17
- 完成所有缺失功能的补充
- 详情面板增加 13 个功能（按钮、编辑框、字段显示）
- 菜单增加 10 个功能项
- 快捷键增加 Enter 生成封面
- 帮助菜单增加快捷键帮助
- 总完成功能数：57 个
- 完成率：100%
