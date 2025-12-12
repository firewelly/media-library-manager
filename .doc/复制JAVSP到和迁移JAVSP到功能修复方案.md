# 复制JAVSP到和迁移JAVSP到功能修复方案

## 当前问题状态

### 已确认的问题
1. **显示不在线文件夹**：右键菜单中显示所有`is_active=1`的文件夹，但未检查实际可访问性
2. **路径显示不完整**：仅显示文件夹名称（`os.path.basename`），不显示完整挂载路径
3. **PySide6版本缺失**：PySide6版本中没有实现"复制JAVSP到"和"迁移JAVSP到"功能

### 已发现的相关代码
- **media_library.py** (6000-6900行)：已实现完整的迁移和复制功能
- **resumable_smart_importer.py**：有`get_active_folders()`方法可筛选在线文件夹
- **media_library_pyside.py**：右键菜单中没有迁移/复制相关代码

## 修复方案

### 1. 修复media_library.py的文件夹筛选

#### 当前代码问题
```python
# 在create_context_menu方法中 (约6000行)
cursor.execute("SELECT folder_path FROM folders WHERE is_active = 1")
active_folders = cursor.fetchall()
for folder in active_folders:
    folder_path = folder[0]
    folder_name = os.path.basename(folder_path)  # 只显示名称，不显示完整路径
    migrate_action = migrate_menu.addAction(f"迁移JavSP到 {folder_name}")
```

#### 修复方案
```python
def get_online_folders(self):
    """获取在线文件夹列表"""
    cursor = self.conn.cursor()
    cursor.execute("SELECT folder_path FROM folders WHERE is_active = 1")
    all_folders = cursor.fetchall()
    
    online_folders = []
    for folder in all_folders:
        folder_path = folder[0]
        if os.path.exists(folder_path) and os.path.isdir(folder_path):
            online_folders.append(folder_path)
            print(f"✓ 在线文件夹: {folder_path}")
        else:
            print(f"✗ 离线文件夹: {folder_path}")
    
    return online_folders

# 在create_context_menu中使用
online_folders = self.get_online_folders()
for folder_path in online_folders:
    # 显示完整路径而不仅仅是名称
    display_name = folder_path  # 或者使用格式化的显示名称
    migrate_action = migrate_menu.addAction(f"迁移JavSP到 {display_name}")
```

### 2. 添加文件夹显示名称格式化方法

```python
def format_folder_display_name(self, folder_path):
    """格式化文件夹显示名称，包含挂载点信息"""
    # 如果是NAS路径，显示完整路径
    if "/Volumes/" in folder_path:
        return folder_path  # 显示完整挂载路径
    
    # 如果是普通路径，显示最后两级目录
    parts = folder_path.split(os.sep)
    if len(parts) > 2:
        return os.sep.join(parts[-2:])
    
    return folder_path
```

### 3. 为PySide6版本添加缺失功能

#### 需要在media_library_pyside.py中添加：
1. **右键菜单项**：在`show_context_menu`方法中添加迁移/复制子菜单
2. **功能方法**：实现`migrate_javsp_file_to_library`等方法
3. **批量操作**：实现批量迁移/复制功能

#### 参考实现结构
```python
def show_context_menu(self, position):
    # ... 现有代码 ...
    
    # 添加迁移和复制菜单
    context_menu.addSeparator()
    
    # 获取在线文件夹
    online_folders = self.get_online_folders()
    
    if online_folders:
        # 单文件操作
        if len(selected_items) == 1:
            migrate_menu = context_menu.addMenu("迁移JavSP到")
            copy_menu = context_menu.addMenu("复制JAVSP到")
            
            for folder_path in online_folders:
                display_name = self.format_folder_display_name(folder_path)
                migrate_action = migrate_menu.addAction(display_name)
                migrate_action.triggered.connect(
                    lambda checked, f=folder_path: self.migrate_javsp_file_to_library(f)
                )
                copy_action = copy_menu.addAction(display_name)
                copy_action.triggered.connect(
                    lambda checked, f=folder_path: self.copy_javsp_file_to_library(f)
                )
        
        # 批量操作
        else:
            batch_migrate_menu = context_menu.addMenu("批量迁移JavSP到")
            batch_copy_menu = context_menu.addMenu("批量复制JAVSP到")
            
            for folder_path in online_folders:
                display_name = self.format_folder_display_name(folder_path)
                batch_migrate_action = batch_migrate_menu.addAction(display_name)
                batch_migrate_action.triggered.connect(
                    lambda checked, f=folder_path: self.batch_migrate_javsp_files_to_library(f)
                )
                batch_copy_action = batch_copy_menu.addAction(display_name)
                batch_copy_action.triggered.connect(
                    lambda checked, f=folder_path: self.batch_copy_javsp_files_to_library(f)
                )
```

### 4. 实现核心功能方法

```python
def migrate_javsp_file_to_library(self, target_library_path):
    """迁移JavSP文件到指定媒体库"""
    selected_items = self.video_list.selectedItems()
    if not selected_items:
        return
    
    video_id = selected_items[0].data(0, Qt.UserRole)
    
    # 获取视频文件路径
    self.core.cursor.execute("SELECT file_path FROM videos WHERE id = ?", (video_id,))
    result = self.core.cursor.fetchone()
    if not result:
        self.show_error("错误", "找不到视频文件")
        return
    
    file_path = result[0]
    
    # 调用迁移功能
    from utils.javsp_migration import migrate_single
    result = migrate_single(self.core.cursor, self.core.conn, file_path, video_id, target_library_path)
    
    if result['ok']:
        self.show_info("成功", f"文件已迁移到: {result['final_path']}")
        self.load_videos()  # 刷新列表
    else:
        self.show_error("失败", f"迁移失败: {result['error']}")

def copy_javsp_file_to_library(self, target_library_path):
    """复制JavSP文件到指定媒体库"""
    # 类似迁移功能，但使用javsp_copy模块
    from utils.javsp_copy import copy_single
    # ... 实现代码 ...
```

## 实施步骤

### 第一步：修复media_library.py
1. 添加`get_online_folders()`方法
2. 修改`create_context_menu()`中的文件夹获取逻辑
3. 添加`format_folder_display_name()`方法

### 第二步：为PySide6版本添加功能
1. 在`show_context_menu()`中添加迁移/复制菜单
2. 实现`get_online_folders()`和`format_folder_display_name()`
3. 实现`migrate_javsp_file_to_library()`等方法
4. 实现批量操作功能

### 第三步：测试验证
1. 测试在线状态检查
2. 测试路径显示格式
3. 测试迁移和复制功能
4. 测试批量操作

## 预期效果

### 修复后功能特点
1. **智能筛选**：只显示实际可访问的在线文件夹
2. **完整路径**：显示包含挂载点信息的完整路径
3. **统一体验**：PySide6版本与原版功能一致
4. **批量支持**：支持多文件批量迁移/复制

### 用户界面改进
- 文件夹路径清晰可识别
- 不再显示离线文件夹
- 支持多文件批量操作
- 操作反馈明确

## 注意事项

1. **性能考虑**：在线检查可能增加菜单响应时间
2. **错误处理**：需要完善的异常处理机制
3. **数据库一致性**：确保迁移/复制后数据完整性
4. **路径格式**：不同操作系统的路径格式处理