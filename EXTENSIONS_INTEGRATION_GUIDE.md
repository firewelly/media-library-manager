# PySide6扩展功能集成指南

本文档说明如何将media_library.py的功能集成到现有的PySide6界面中。

## 📁 新增文件结构

```
media/
├── utils/                          # 新增工具模块
│   ├── __init__.py                  # 包初始化文件
│   ├── logger.py                    # 日志系统
│   ├── progress_manager.py          # 进度管理
│   ├── database.py                  # 数据库操作
│   ├── file_utils.py                # 文件处理工具
│   └── media_extensions.py          # 媒体库扩展功能
├── extension_dialogs.py             # 扩展功能GUI对话框
├── pyside_extensions_patch.py       # PySide6集成补丁
└── EXTENSIONS_INTEGRATION_GUIDE.md  # 本文档
```

## 🔧 集成步骤

### 1. 集成到现有PySide6主窗口

在`media_library_pyside.py`的主窗口类（通常是`MediaLibraryGUI`或类似名称）的`__init__`方法最后添加：

```python
# 在__init__方法的最后添加
try:
    from pyside_extensions_patch import apply_all_extensions
    apply_all_extensions(self)
except ImportError as e:
    print(f"扩展功能模块未找到: {e}")
except Exception as e:
    print(f"扩展功能加载失败: {e}")
```

### 2. 确保依赖关系

确保你的PySide6主窗口有以下属性：
- `self.core` - 核心功能对象，包含`db_manager`属性
- `self.video_tree` - 视频列表树控件

如果属性名称不同，需要相应修改`pyside_extensions_patch.py`中的代码。

## 🆕 新增功能

### 1. NFO文件导入
- **菜单**: 扩展功能 → 导入NFO文件 (Ctrl+N)
- **功能**: 解析和导入视频的NFO文件信息
- **支持**: 标题、演员、年份、标签、评分、时长、简介等信息

### 2. 重复文件管理
- **菜单**: 扩展功能 → 重复文件管理 (Ctrl+D)
- **功能**:
  - 基于MD5和文件哈希查找重复视频
  - 多种删除策略（保留最大、最新、路径最短等）
  - 详细的重复文件信息显示

### 3. 批量操作
- **菜单**: 扩展功能 → 批量操作 (Ctrl+B)
- **功能**:
  - 批量更新星级
  - 批量添加标签
  - 批量移动文件
  - 批量重新计算哈希

### 4. 工具功能
- **菜单**: 扩展功能 → 工具
- **包含**:
  - 重新计算所有文件哈希
  - 数据库维护（清理、优化、重建索引）

### 5. 增强右键菜单
- 在视频列表右键菜单中添加：
  - 导入NFO
  - 重新计算哈希
  - 在文件管理器中显示

## 🛠️ 工具模块功能

### logger.py - 日志系统
```python
from utils import LogLevel, get_logger

# 设置日志级别
from utils import set_log_level
set_log_level(LogLevel.DEBUG)

# 使用日志器
logger = get_logger("MyModule")
logger.info("信息消息")
logger.error("错误消息")
```

### progress_manager.py - 进度管理
```python
from utils import ThreadedProgress, create_threaded_tracker

# 创建线程安全的进度跟踪器
tracker = create_threaded_tracker(100, "处理文件")

# 添加进度回调
def progress_callback(info):
    print(f"进度: {info['current']}/{info['total']} - {info['message']}")

tracker.add_callback(progress_callback)

# 更新进度
tracker.update(1, "正在处理文件1")
```

### database.py - 数据库管理
```python
from utils import DatabaseManager

# 使用上下文管理器
with DatabaseManager("media_library.db") as db:
    videos = db.get_videos(limit=10)
    stats = db.get_statistics()
    duplicates = db.find_duplicates()
```

### file_utils.py - 文件工具
```python
from utils import FileUtils

# 文件操作
md5_hash = FileUtils.calculate_md5("video.mp4")
file_size = FileUtils.get_file_size("video.mp4")
duration = FileUtils.get_video_duration("video.mp4")
resolution = FileUtils.get_video_resolution("video.mp4")
is_video = FileUtils.is_video_file("video.mp4")
```

### media_extensions.py - 扩展功能
```python
from utils import NFOImporter, DuplicateManager, BatchOperations, MediaScanner

# NFO导入
nfo_importer = NFOImporter(db_manager)
success = nfo_importer.import_nfo_for_video(video_id, video_path)

# 重复文件管理
duplicate_manager = DuplicateManager(db_manager)
duplicates = duplicate_manager.find_duplicate_files()
result = duplicate_manager.remove_duplicates_by_criteria('largest')

# 批量操作
batch_ops = BatchOperations(db_manager)
count = batch_ops.batch_update_stars(video_ids, 5)
count = batch_ops.batch_add_tags(video_ids, ['标签1', '标签2'])

# 媒体扫描
scanner = MediaScanner(db_manager)
result = scanner.scan_folder("/path/to/videos", recursive=True)
```

## 🎨 自定义界面

### 修改扩展功能对话框

可以修改`extension_dialogs.py`中的对话框类来自定义界面：

1. **NFODialog** - NFO导入界面
2. **DuplicateManagerDialog** - 重复文件管理界面
3. **BatchOperationsDialog** - 批量操作界面

### 添加新的扩展功能

1. 在`utils/media_extensions.py`中添加新的功能类
2. 在`extension_dialogs.py`中添加对应的GUI对话框
3. 在`pyside_extensions_patch.py`中添加菜单和工具栏按钮

## 🐛 故障排除

### 常见问题

1. **导入错误**
   ```
   ImportError: No module named 'utils'
   ```
   **解决方案**: 确保在项目根目录运行，或添加项目路径到Python路径

2. **数据库连接错误**
   ```
   sqlite3.OperationalError: unable to open database file
   ```
   **解决方案**: 检查数据库文件路径是否正确

3. **属性不存在错误**
   ```
   AttributeError: 'MediaLibraryGUI' object has no attribute 'core'
   ```
   **解决方案**: 检查主窗口类中的属性名称，并相应修改补丁文件

### 调试模式

启用调试日志：
```python
from utils import set_log_level, LogLevel
set_log_level(LogLevel.DEBUG)
```

## 📝 开发注意事项

1. **线程安全**: 所有耗时操作都应该在工作线程中执行
2. **进度反馈**: 长时间操作需要提供进度反馈
3. **错误处理**: 所有操作都应该有适当的错误处理
4. **数据验证**: 在执行操作前验证输入数据
5. **用户体验**: 提供清晰的状态反馈和确认对话框

## 🔄 更新和维护

当更新`media_library.py`时，需要注意：

1. 新增的功能需要提取到对应的utils模块中
2. 数据库结构变更需要同步更新`utils/database.py`
3. GUI相关的变更需要同步更新扩展对话框

## 📞 技术支持

如果在使用过程中遇到问题：

1. 检查日志输出中的错误信息
2. 确认所有依赖模块都已正确安装
3. 验证数据库文件和路径的配置
4. 查看本指南中的故障排除部分

---

**注意**: 这个扩展功能系统设计为模块化和可扩展的，便于后续添加新功能和维护。