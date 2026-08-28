# 媒体库管理系统 / Media Library Management System

> 版本 / Version: v2.1.0  
> 最后更新 / Last Updated: 2026-08-13  
> 适用系统 / Supported OS: Windows / macOS / Linux

---

## 项目概述 / Project Overview

**中文**  
媒体库管理系统是一个功能完备的视频内容管理平台，专注于视频文件的组织、分析、去重和元数据管理。系统结合了网络爬虫、视频内容分析、数据库管理和用户界面等多个组件，提供从视频元数据获取、内容特征分析到重复文件检测与清理的全流程解决方案。

**English**  
Media Library Management System is a comprehensive video content management platform focused on organizing, analyzing, deduplicating, and managing metadata for video files. The system integrates web crawlers, video content analysis, database management, and user interface components, providing a complete workflow solution from video metadata acquisition, content feature analysis, to duplicate file detection and cleanup.

---

## 系统架构 / System Architecture

**中文**  
系统采用模块化设计，主要包含以下核心组件：

1. **数据爬取模块**：通过网络爬虫从 JAVDB 等网站获取视频元数据
2. **视频分析模块**：基于 SiliconFlow API 的多模态视频内容分析
3. **数据库管理模块**：基于 SQLite 的数据库系统（约 3.5G，49,000+ 条记录）
4. **文件管理模块**：负责视频文件的导入、路径管理、MD5 计算
5. **去重与清理模块**：检测并清理重复视频记录
6. **批量处理模块**：提供批量视频分析、元数据更新等功能
7. **前端界面模块**：PySide6 实现的现代桌面界面（pyside_v4）

**English**  
The system adopts a modular design, mainly containing the following core components:

1. **Data Crawling Module**: Acquires video metadata from websites like JAVDB through web crawlers
2. **Video Analysis Module**: Multi-modal video content analysis based on SiliconFlow API
3. **Database Management Module**: SQLite-based database system (approximately 3.5G, 49,000+ records)
4. **File Management Module**: Handles video file import, path management, MD5 calculation
5. **Deduplication & Cleanup Module**: Detects and cleans up duplicate video records
6. **Batch Processing Module**: Provides batch video analysis, metadata update functions
7. **Frontend Interface Module**: Modern desktop interface implemented with PySide6 (pyside_v4)

---

## 核心模块 / Core Modules

### 1. 前端界面 / Frontend Interface (pyside_v4)

**中文**  
- **设计风格**：深色影院风（琥珀金 + 玻璃拟态）
- **技术栈**：PySide6（Qt for Python）
- **核心功能**：57 个功能模块，100% 完成率
- **性能优化**：数据库查询从 14 秒降至 9 毫秒
- **目录结构**：
  - `core/`：数据库连接 + 数据访问层
  - `theme/`：主题系统（深色/浅色双主题）
  - `widgets/`：UI 组件（侧边栏、表格、详情面板等）
  - `windows/`：主窗口
  - `dialogs/`：对话框（演员库、标签管理、设置等）
  - `workers/`：后台任务

**English**  
- **Design Style**: Dark cinema theme (amber gold + glassmorphism)
- **Tech Stack**: PySide6 (Qt for Python)
- **Core Features**: 57 functional modules, 100% completion rate
- **Performance Optimization**: Database query reduced from 14 seconds to 9 milliseconds
- **Directory Structure**:
  - `core/`: Database connection + data access layer
  - `theme/`: Theme system (dark/light dual themes)
  - `widgets/`: UI components (sidebar, table, detail panel, etc.)
  - `windows/`: Main window
  - `dialogs/`: Dialogs (actor library, tag management, settings, etc.)
  - `workers/`: Background tasks

### 2. 视频分析 / Video Analysis

**中文**  
- **AI 模型**：Qwen3-VL-30B-A3B-Instruct（视觉语言模型）
- **API 服务**：SiliconFlow (https://api.siliconflow.cn)
- **功能**：
  - 自动抽取视频帧（最大 30 帧）
  - 内容理解与智能标签匹配
  - 标签词典：122 个预定义标签
  - 批量处理能力
- **关键脚本**：
  - `retag_scored_videos.py`：批量打标签
  - `video_analyzer/adapter.py`：视频内容分析适配器

**English**  
- **AI Model**: Qwen3-VL-30B-A3B-Instruct (Vision-Language Model)
- **API Service**: SiliconFlow (https://api.siliconflow.cn)
- **Features**:
  - Automatic video frame extraction (up to 30 frames)
  - Content understanding and intelligent tag matching
  - Tag vocabulary: 122 predefined tags
  - Batch processing capability
- **Key Scripts**:
  - `retag_scored_videos.py`: Batch tagging
  - `video_analyzer/adapter.py`: Video content analysis adapter

### 3. 数据爬取 / Data Crawling

**中文**  
- **JAVDB 爬虫系统**：
  - `javdb_crawler.py`：主爬虫脚本
  - `javdb_actor_all.py`：演员信息爬取
  - `javdb_information_updater.py`：信息更新
  - `javdb_login_helper.py`：登录助手
- **JavSP 集成**：
  - `javsp_avsox.py`、`javsp_javbus.py`、`javsp_javlib.py`
  - 多来源数据聚合

**English**  
- **JAVDB Crawler System**:
  - `javdb_crawler.py`: Main crawler script
  - `javdb_actor_all.py`: Actor information crawling
  - `javdb_information_updater.py`: Information update
  - `javdb_login_helper.py`: Login helper
- **JavSP Integration**:
  - `javsp_avsox.py`, `javsp_javbus.py`, `javsp_javlib.py`
  - Multi-source data aggregation

### 4. 数据库管理 / Database Management

**中文**  
- **数据库文件**：`media_library.db`（SQLite，约 3.5G）
- **主要表结构**：
  - `videos`：视频基本信息（tags、is_nas_online、file_path、stars 等字段）
  - `actors`：演员信息
  - `tags`：标签信息
  - `video_actors`：视频-演员关联
  - `video_tags`：视频-标签关联
  - `javdb_info`：JAVDB 元数据
  - `folders`：文件夹信息
- **关键脚本**：
  - `database_extension.py`：数据库扩展
  - `migrate_av_to_nas.py`：NAS 迁移
  - `sync_db_by_filename.py`：文件名同步

**English**  
- **Database File**: `media_library.db` (SQLite, approximately 3.5G)
- **Main Table Structure**:
  - `videos`: Video basic information (tags, is_nas_online, file_path, stars fields)
  - `actors`: Actor information
  - `tags`: Tag information
  - `video_actors`: Video-actor associations
  - `video_tags`: Video-tag associations
  - `javdb_info`: JAVDB metadata
  - `folders`: Folder information
- **Key Scripts**:
  - `database_extension.py`: Database extension
  - `migrate_av_to_nas.py`: NAS migration
  - `sync_db_by_filename.py`: Filename synchronization

---

## 存储环境 / Storage Environment

**中文**  
视频分布在本地和 NAS 存储：

| 存储位置 / Location | 路径 / Path | 说明 / Description |
|---|---|---|
| 本地 / Local | `/Users/firewell` | 本地视频文件 |
| NAS 卷 / NAS Volume | `/Volumes/app` | NAS 应用卷 |
| NAS 卷 / NAS Volume | `/Volumes/Video` | NAS 视频卷 |
| NAS 卷 / NAS Volume | `/Volumes/国产_DX4600` | DX4600 国产卷 |
| NAS 卷 / NAS Volume | `/Volumes/HC530_1` | HC530 硬盘卷 |
| NAS 卷 / NAS Volume | `/Volumes/Jav_HDD4` | JAV HDD4 卷 |

**NAS 路径映射 / NAS Path Mapping**：

| macOS SMB 挂载 / macOS SMB Mount | NAS 本地路径 / NAS Local Path |
|---|---|
| `/Volumes/国产_DX4600/` | `/volume4/国产_DX4600/` |
| `/Volumes/app/usr/` | `/volume1/app/usr/` |
| `/Volumes/HC530_1/` | `/volume2/HC530_1/` |
| `/Volumes/Jav_HDD4/` | `/volume4/Jav_HDD4/` |

**English**  
Videos are distributed across local and NAS storage:

| Location | Path | Description |
|---|---|---|
| Local | `/Users/firewell` | Local video files |
| NAS Volume | `/Volumes/app` | NAS application volume |
| NAS Volume | `/Volumes/Video` | NAS video volume |
| NAS Volume | `/Volumes/国产_DX4600` | DX4600 domestic volume |
| NAS Volume | `/Volumes/HC530_1` | HC530 hard drive volume |
| NAS Volume | `/Volumes/Jav_HDD4` | JAV HDD4 volume |

**NAS Path Mapping**:

| macOS SMB Mount | NAS Local Path |
|---|---|
| `/Volumes/国产_DX4600/` | `/volume4/国产_DX4600/` |
| `/Volumes/app/usr/` | `/volume1/app/usr/` |
| `/Volumes/HC530_1/` | `/volume2/HC530_1/` |
| `/Volumes/Jav_HDD4/` | `/volume4/Jav_HDD4/` |

---

## 技术栈 / Technology Stack

**中文**  
- **编程语言**：Python 3.x
- **数据库**：SQLite 3.0+
- **GUI 框架**：PySide6（主界面）、Tkinter（旧版界面）
- **网络爬虫**：Requests, Selenium, BeautifulSoup
- **视频处理**：OpenCV, FFmpeg, PIL
- **AI 模型**：Qwen3-VL-30B-A3B-Instruct（视频内容分析）
- **API 服务**：SiliconFlow (https://api.siliconflow.cn)
- **数据处理**：Pandas, NumPy, JSON, CSV
- **操作系统支持**：跨平台 (Windows, macOS, Linux)

**English**  
- **Programming Language**: Python 3.x
- **Database**: SQLite 3.0+
- **GUI Framework**: PySide6 (main interface), Tkinter (legacy interface)
- **Web Crawling**: Requests, Selenium, BeautifulSoup
- **Video Processing**: OpenCV, FFmpeg, PIL
- **AI Model**: Qwen3-VL-30B-A3B-Instruct (video content analysis)
- **API Service**: SiliconFlow (https://api.siliconflow.cn)
- **Data Processing**: Pandas, NumPy, JSON, CSV
- **OS Support**: Cross-platform (Windows, macOS, Linux)

---

## 部署指南 / Deployment Guide

**中文**  

### 环境要求 / Requirements
- Python 3.7 或更高版本 / Python 3.7 or higher
- 足够的磁盘空间存储视频和元数据 / Sufficient disk space for videos and metadata
- 支持 OpenCV 的图形处理环境 / Graphics processing environment with OpenCV support
- （可选）用于 AI 分析的 SiliconFlow API Key / (Optional) SiliconFlow API Key for AI analysis

### 安装步骤 / Installation Steps

1. **克隆仓库 / Clone Repository**：
   ```bash
   git clone https://github.com/firewelly/media-library-manager.git
   cd media-library-manager
   ```

2. **安装依赖 / Install Dependencies**：
   ```bash
   pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
   ```

3. **配置 API Key / Configure API Key**：
   ```bash
   export SILICONFLOW_API_KEY="your-api-key"
   ```

4. **启动应用 / Start Application**：
   ```bash
   # PySide6 版本（推荐）/ PySide6 version (recommended)
   python media_library_v2.py
   
   # 或 Tkinter 版本 / Or Tkinter version
   python media_library.py
   ```

### Docker 部署 / Docker Deployment

系统支持 Docker 容器化部署，详见 `docker/` 目录。

The system supports Docker containerized deployment, see `docker/` directory for details.

**English**  

### Requirements
- Python 3.7 or higher
- Sufficient disk space for videos and metadata
- Graphics processing environment with OpenCV support
- (Optional) SiliconFlow API Key for AI analysis

### Installation Steps

1. **Clone Repository**:
   ```bash
   git clone https://github.com/firewelly/media-library-manager.git
   cd media-library-manager
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
   ```

3. **Configure API Key**:
   ```bash
   export SILICONFLOW_API_KEY="your-api-key"
   ```

4. **Start Application**:
   ```bash
   # PySide6 version (recommended)
   python media_library_v2.py
   
   # Or Tkinter version
   python media_library.py
   ```

### Docker Deployment

The system supports Docker containerized deployment, see `docker/` directory for details.

---

## 版本历史 / Version History

### v2.1.0 (2026-08-12)

**中文**  
- pyside_v4 前端界面重构（深色影院风设计、57 个功能模块）
- MD5 完整性修复（覆盖率 69.8% → 97.9%）
- 视频批量打标签系统（AI 视觉模型集成）
- NAS 存储迁移（DXP4800）
- 数据库去重清理与路径修正
- 安全与隐私增强

**English**  
- pyside_v4 frontend interface refactoring (dark cinema design, 57 functional modules)
- MD5 integrity fix (coverage 69.8% → 97.9%)
- Batch video tagging system (AI vision model integration)
- NAS storage migration (DXP4800)
- Database deduplication cleanup and path correction
- Security and privacy enhancement

### v2.0.0 (2025-12-27)

**中文**  
- PySide6 版本功能完整化
- 代码架构重构（Utils 模块分离）
- 批量操作增强
- 右键菜单重构

**English**  
- PySide6 version feature completion
- Code architecture refactoring (Utils module separation)
- Batch operation enhancement
- Context menu refactoring

---

## 许可证 / License

MIT License

---

## 联系方式 / Contact

- **GitHub**: https://github.com/firewelly/media-library-manager
- **问题反馈 / Issue Report**: https://github.com/firewelly/media-library-manager/issues

---

*本文档由 OpenWiki 辅助生成 / This document was assisted by OpenWiki*
