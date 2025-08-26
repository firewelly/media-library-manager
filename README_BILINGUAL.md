# 媒体库管理系统 / Media Library Management System

一个功能强大的本地媒体文件管理系统，支持视频文件的组织、标记、评分和预览功能。

A powerful local media file management system that supports organization, tagging, rating, and preview of video files.

## 功能特性 / Features

### 核心功能 / Core Features
- 📁 **文件扫描与导入 / File Scanning & Import** - 自动扫描指定目录下的视频文件 / Automatically scan video files in specified directories
- 🏷️ **智能标记系统 / Smart Tagging System** - 支持标题、描述、标签、类型等metadata管理 / Support for title, description, tags, genre and other metadata management
- ⭐ **星级评分系统 / Star Rating System** - 5星评分，支持点击直接评分 / 5-star rating with click-to-rate functionality
- 🖼️ **缩略图生成 / Thumbnail Generation** - 自动生成视频缩略图预览 / Automatically generate video thumbnail previews
- 🔍 **强大的搜索与筛选 / Powerful Search & Filter** - 支持关键词搜索、星级筛选、来源文件夹筛选 / Support keyword search, star rating filter, source folder filter
- 📊 **表格排序 / Table Sorting** - 点击列标题进行升序/降序排序 / Click column headers for ascending/descending sort
- 💾 **数据库存储 / Database Storage** - 使用SQLite数据库持久化存储 / Persistent storage using SQLite database

### 界面特性 / UI Features
- 🎨 **现代化UI / Modern UI** - 基于Tkinter的直观用户界面 / Intuitive user interface based on Tkinter
- 📱 **响应式布局 / Responsive Layout** - 支持窗口大小调整 / Support window resizing
- 🌟 **交互式星级 / Interactive Stars** - 在列表和详情面板中直接点击星级评分 / Direct click-to-rate in list and detail panel
- 📋 **详细信息面板 / Detail Panel** - 显示完整的文件metadata信息 / Display complete file metadata information

### 高级功能 / Advanced Features
- 🔄 **NAS同步支持 / NAS Sync Support** - 支持网络存储设备文件同步 / Support network storage device file synchronization
- 📝 **批量操作 / Batch Operations** - 支持批量标记和管理 / Support batch tagging and management
- 🎯 **智能文件名解析 / Smart Filename Parsing** - 从文件名自动提取星级信息 / Automatically extract star rating from filename
- 📈 **统计信息 / Statistics** - 显示文件数量、总大小等统计数据 / Display file count, total size and other statistics

### 最新功能 / Latest Features
- 🧠 **智能媒体库更新 / Smart Media Library Update** - 自动检测文件移动、添加新文件、更新MD5哈希 / Automatically detect file moves, add new files, update MD5 hashes
- 🔐 **MD5哈希计算 / MD5 Hash Calculation** - 计算文件前1MB的MD5用于去重和移动检测 / Calculate MD5 of first 1MB for deduplication and move detection
- 🔍 **智能去重 / Smart Deduplication** - 基于MD5哈希值智能检测和处理重复文件 / Smart detection and handling of duplicate files based on MD5 hash
- 📁 **文件移动检测 / File Move Detection** - 通过MD5哈希自动检测文件移动并更新路径 / Automatically detect file moves via MD5 hash and update paths
- 🔄 **批量MD5计算 / Batch MD5 Calculation** - 支持批量计算缺失或重新计算所有文件的MD5 / Support batch calculation of missing or recalculation of all file MD5s
- 📊 **实时进度显示 / Real-time Progress Display** - 在批量操作时显示详细进度和统计信息 / Display detailed progress and statistics during batch operations
- 🗂️ **多文件夹管理 / Multi-folder Management** - 支持同时管理多个活跃文件夹 / Support managing multiple active folders simultaneously
- 🎬 **视频信息提取 / Video Info Extraction** - 自动提取视频时长、分辨率等技术信息 / Automatically extract video duration, resolution and other technical info

## 安装要求 / Requirements

### 系统要求 / System Requirements
- Python 3.7+
- macOS / Windows / Linux

### 依赖包 / Dependencies
```bash
pip install -r requirements.txt
```

主要依赖 / Main Dependencies：
- `tkinter` - GUI界面 / GUI interface
- `sqlite3` - 数据库（Python内置）/ Database (Python built-in)
- `Pillow` - 图像处理 / Image processing
- `opencv-python` - 视频处理 / Video processing
- `python-magic` - 文件类型检测 / File type detection

## 快速开始 / Quick Start

### 1. 克隆项目 / Clone Project
```bash
git clone <repository-url>
cd media-library
```

### 2. 安装依赖 / Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. 初始化数据库 / Initialize Database
```bash
python init_database.py
```

### 4. 启动应用 / Start Application
```bash
python media_library.py
```

或使用启动脚本 / Or use startup script：
```bash
./start_media_library.sh
```

## 使用说明 / Usage Guide

### 首次使用 / First Time Use
1. 启动应用后，点击"添加文件夹"按钮 / After starting the app, click "Add Folder" button
2. 选择包含视频文件的目录 / Select directory containing video files
3. 系统会自动扫描并导入视频文件 / System will automatically scan and import video files
4. 等待缩略图生成完成 / Wait for thumbnail generation to complete

### 文件管理 / File Management
- **查看文件 / View Files**：在主列表中浏览所有导入的视频文件 / Browse all imported video files in the main list
- **搜索文件 / Search Files**：使用顶部搜索框输入关键词 / Use the top search box to enter keywords
- **筛选文件 / Filter Files**：使用星级筛选器和来源文件夹筛选器 / Use star rating filter and source folder filter
- **排序文件 / Sort Files**：点击列标题进行排序（支持所有列）/ Click column headers to sort (supports all columns)

### 评分系统 / Rating System
- **快速评分 / Quick Rating**：直接点击列表中的星级进行评分 / Click stars directly in the list to rate
- **详细评分 / Detailed Rating**：在右侧详情面板中点击星级 / Click stars in the right detail panel
- **文件名评分 / Filename Rating**：文件名中的感叹号会自动转换为星级 / Exclamation marks in filename automatically convert to star rating
  - movie!!!.mp4 = 3星 / 3 stars

### 信息编辑 / Information Editing
1. 选择视频文件 / Select video file
2. 在右侧详情面板中编辑信息 / Edit information in the right detail panel：
   - 标题 / Title
   - 描述 / Description
   - 标签 / Tags
   - 年份 / Year
   - 类型 / Genre
3. 点击"保存修改"按钮 / Click "Save Changes" button

### 播放视频 / Play Video
- 双击列表中的文件 / Double-click file in the list
- 或在详情面板中点击"播放视频"按钮 / Or click "Play Video" button in detail panel

### 智能功能 / Smart Features

#### 智能媒体库更新 / Smart Media Library Update
- 自动检测文件移动并更新路径 / Automatically detect file moves and update paths
- 扫描新文件并添加到数据库 / Scan new files and add to database
- 计算缺失的MD5哈希值 / Calculate missing MD5 hash values
- 删除无效的文件记录 / Remove invalid file records

#### 智能去重 / Smart Deduplication
- 基于MD5哈希值检测重复文件 / Detect duplicate files based on MD5 hash
- 提供多种保留策略 / Provide multiple retention strategies：
  - 保留最新文件 / Keep newest file
  - 保留最老文件 / Keep oldest file
  - 保留特定文件夹中的文件 / Keep files in specific folder

#### 批量操作 / Batch Operations
- 批量生成缩略图 / Batch generate thumbnails
- 批量计算MD5哈希 / Batch calculate MD5 hashes
- 批量导入元数据 / Batch import metadata

## 配置说明 / Configuration

### GUI配置 / GUI Configuration
编辑 `gui_config.json` 文件可以自定义界面显示 / Edit `gui_config.json` file to customize interface display：
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

### 文件命名约定 / File Naming Convention
系统支持从文件名自动解析星级 / System supports automatic star rating parsing from filename：
- 只有叹号在文件名称的开头才算 / Only exclamation marks at the beginning of the filename are counted
- `!movie.mp4` → 2星 / 2 stars
- `!!movie.mp4` → 3星 / 3 stars
- `!!!movie.mp4` → 4星 / 4 stars
- `!!!!movie.mp4` → 5星 / 5 stars
- `movie.mp4` → 0星 / 0 stars (没有叹号 / no exclamation marks)
- `movie.mp4!` → 0星 / 0 stars (叹号不在开头 / exclamation marks not at the beginning)

## 数据库结构 / Database Structure

系统使用SQLite数据库存储以下信息 / System uses SQLite database to store the following information：
- 文件基本信息（路径、大小、哈希值等）/ Basic file info (path, size, hash, etc.)
- 媒体信息（标题、描述、标签、年份、类型等）/ Media info (title, description, tags, year, genre, etc.)
- 技术信息（时长、分辨率、编码等）/ Technical info (duration, resolution, encoding, etc.)
- 用户数据（星级评分、缩略图等）/ User data (star rating, thumbnails, etc.)
- 时间戳（创建时间、更新时间等）/ Timestamps (creation time, update time, etc.)
- MD5哈希值（用于去重和移动检测）/ MD5 hash (for deduplication and move detection)

## 故障排除 / Troubleshooting

### 常见问题 / Common Issues

**Q: 缩略图无法生成 / Thumbnails cannot be generated**
A: 确保安装了opencv-python包，并检查视频文件是否损坏 / Ensure opencv-python package is installed and check if video files are corrupted

**Q: 文件扫描很慢 / File scanning is slow**
A: 大量文件的首次扫描需要时间，请耐心等待。后续扫描会跳过已处理的文件 / Initial scanning of large number of files takes time, please be patient. Subsequent scans will skip already processed files

**Q: 数据库损坏 / Database corrupted**
A: 使用备份文件恢复，或重新运行init_database.py重建数据库 / Restore from backup file, or re-run init_database.py to rebuild database

**Q: 界面显示异常 / Interface display abnormal**
A: 检查gui_config.json配置文件格式是否正确 / Check if gui_config.json configuration file format is correct

**Q: MD5计算失败 / MD5 calculation failed**
A: 检查文件是否存在且可读，或文件是否被其他程序占用 / Check if file exists and is readable, or if file is being used by other programs

### 日志查看 / Log Viewing
应用运行时会在界面底部显示日志信息，包括 / Application displays log information at the bottom of the interface during runtime, including：
- 文件扫描进度 / File scanning progress
- 错误信息 / Error messages
- 操作状态 / Operation status

## 开发说明 / Development Notes

### 项目结构 / Project Structure
```
media-library/
├── media_library.py      # 主程序文件 / Main program file
├── init_database.py      # 数据库初始化 / Database initialization
├── gui_config.json       # 界面配置 / Interface configuration
├── requirements.txt      # 依赖包列表 / Dependencies list
├── start_media_library.sh # 启动脚本 / Startup script
└── README.md            # 项目说明 / Project documentation
```

### 主要类和方法 / Main Classes and Methods
- `MediaLibrary` - 主应用类 / Main application class
- `create_gui()` - 创建用户界面 / Create user interface
- `scan_folder()` - 扫描文件夹 / Scan folder
- `load_videos()` - 加载视频列表 / Load video list
- `set_stars()` - 设置星级评分 / Set star rating
- `save_video_info()` - 保存视频信息 / Save video information
- `comprehensive_media_update()` - 智能媒体库更新 / Smart media library update
- `smart_remove_duplicates()` - 智能去重 / Smart deduplication
- `batch_calculate_md5()` - 批量计算MD5 / Batch calculate MD5
- `calculate_file_hash()` - 计算文件哈希 / Calculate file hash

## 许可证 / License

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 贡献 / Contributing

欢迎提交Issue和Pull Request来改进这个项目！

Welcome to submit Issues and Pull Requests to improve this project!

## 更新日志 / Changelog

### v3.0.0 (Latest / 最新版本)
- ✨ 新增智能媒体库更新功能 / Added smart media library update feature
- 🔐 新增MD5哈希计算和文件移动检测 / Added MD5 hash calculation and file move detection
- 🔍 新增智能去重功能 / Added smart deduplication feature
- 📊 新增批量操作进度显示 / Added batch operation progress display
- 🗂️ 新增多文件夹管理支持 / Added multi-folder management support
- 🎬 改进视频信息提取 / Improved video information extraction
- 🐛 修复数据库字段不匹配问题 / Fixed database field mismatch issues

### v2.0.0
- ✨ 新增表头点击排序功能 / Added table header click sorting
- ⭐ 优化星级显示为实心/空心星星组合 / Optimized star display with solid/hollow star combination
- 🖱️ 支持直接点击星级进行评分 / Support direct click-to-rate stars
- 📊 增强视频详情面板，显示完整metadata / Enhanced video detail panel with complete metadata
- 💾 改进数据保存功能 / Improved data saving functionality

### v1.0.0
- 🎉 初始版本发布 / Initial version release
- 📁 基础文件扫描和管理功能 / Basic file scanning and management
- ⭐ 星级评分系统 / Star rating system
- 🔍 搜索和筛选功能 / Search and filter functionality
- 🖼️ 缩略图生成 / Thumbnail generation