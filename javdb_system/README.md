# JAVDB 爬虫系统

## 概述

JAVDB 爬虫系统是媒体库管理器的核心组件之一，负责从 JAVDB 网站获取 AV 作品的元数据信息（标题、番号、演员、标签、评分、封面等），并保存到本地数据库中。

## 系统架构

```
┌──────────────────────────────────────────────────────┐
│                    GUI 层 (media_library.py)           │
│  ┌──────────────────────────────────────────────────┐ │
│  │  右键菜单 → "JAVDB信息获取" / "批量JAVDB信息获取" │ │
│  │  顶部菜单 → "批量导入JAVDB信息"                   │ │
│  │  工具菜单 → "修正JAVDB错误信息"                   │ │
│  │  详情面板 → "获取JAVDB信息" 按钮                  │ │
│  └──────────────────────────────────────────────────┘ │
└──────────────────────┬───────────────────────────────┘
                       │ 调用
┌──────────────────────▼───────────────────────────────┐
│              业务逻辑层 (media_library.py)            │
│  fetch_javdb_info()  → 单个视频获取                  │
│  batch_process_javdb_info() → 批量处理                │
│  save_javdb_info_to_db() → 数据持久化                │
│  fix_javdb_error_titles() → 错误修复                 │
└──────────────────────┬───────────────────────────────┘
                       │ 调用
┌──────────────────────▼───────────────────────────────┐
│               爬虫层 (独立脚本)                        │
│  ┌────────────────────────────────────────────────┐  │
│  │  javdb_crawler_single.py  ★ 核心单番号爬虫    │  │
│  │  javdb_crawler.py          列表批量爬虫        │  │
│  │  javdb_information_updater.py  信息更新器      │  │
│  │  javdb_login_helper.py      登录持久化助手     │  │
│  │  javsp_integration.py       JavSP集成模块      │  │
│  │  javbus_crawler_single.py   JavBus备用爬虫     │  │
│  └────────────────────────────────────────────────┘  │
└──────────────────────┬───────────────────────────────┘
                       │ 输出为JSON
                       ▼
┌──────────────────────────────────────────────────────┐
│             数据层 (数据库)                            │
│  javdb_info 表 → 视频元数据                           │
│  actors 表 → 演员信息                                │
│  video_actors 表 → 视频-演员关联                     │
│  javdb_tags 表 → 标签                                │
│  javdb_info_tags 表 → 标签关联                       │
└──────────────────────────────────────────────────────┘
```

## 三级回退策略

在获取视频信息时，系统采用三级回退策略，优先级如下：

1. **JavDB** (javdb_crawler_single.py) - 主爬虫
2. **JavBus** (javbus_crawler_single.py) - 备用1
3. **JavSP** (javsp_integration.py) - 备用2

当主爬虫失败或获取的演员信息为空时，自动切换到下一级。

## 入口脚本

- `media_library.py` — GUI主程序，包含所有JAVDB操作入口
- 直接命令行: `python javdb_crawler_single.py <番号>`

## 文件说明

| 文件 | 说明 |
|------|------|
| `gui_menu_javdb.py` | 从media_library.py提取的右键菜单+顶部菜单中JAVDB相关入口 |
| `gui_fetch_single.py` | 单视频JAVDB信息获取（fetch_javdb_info, fetch_current_javdb_info） |
| `gui_fetch_batch.py` | 批量JAVDB信息获取（batch_javdb_info_selected_videos, batch_process_javdb_info） |
| `gui_fix_titles.py` | JAVDB错误标题修正（fix_javdb_error_titles） |
| `gui_import_batch.py` | 批量导入JAVDB信息（batch_import_javdb_for_no_title） |
| `save_javdb_info.py` | 数据持久化（save_javdb_info_to_db, load_javdb_details） |
| `javdb_crawler_single.py` | 核心单番号爬虫（selenium + playwright） |
| `javdb_crawler.py` | 列表批量爬虫 |
| `javdb_information_updater.py` | 信息批更新器（登录+批量信息获取） |
| `javdb_login_helper.py` | 登录持久化助手 |
| `database_extension.py` | 数据库扩展脚本（创建所有JAVDB相关表） |
| `code_extractor.py` | 番号提取工具 |
| `config.py` | 系统配置 |

> 📚 **相关文档已统一移至 `doc/` 目录**，包括：JAVDB爬虫系统设计文档、README_JAVDB_IMPROVEMENTS.md、README_javdb_information_updater.md、README_javdb_login_helper.md、javdb_actor_all_help.md、javdb_title_mapping_analysis.md、javdb_title_mapping_solutions.md、FIELD_MAPPING.md、keywords_mapping.md 等。
