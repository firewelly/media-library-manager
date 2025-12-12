# 复制JAVSP到和迁移JAVSP到功能问题记录

## 问题描述

用户反馈：
1. "复制JAVSP到"和"迁移JAVSP到"功能中显示的文件夹似乎不都是在线的文件夹
2. 有一些不在线的文件夹也显示在菜单中
3. 文件夹显示不完整，需要显示完整的挂载路径方便识别

## 问题分析

### 1. 文件夹在线状态检查不完整

在Tkinter版本的`media_library.py`中，右键菜单创建时使用了以下SQL查询：

```python
self.cursor.execute("SELECT DISTINCT folder_path FROM folders WHERE is_active = 1 ORDER BY folder_path")
```

这个查询只检查了`is_active = 1`，但没有检查文件夹是否实际在线（存在且可访问）。

### 2. 文件夹显示名称不完整

当前显示文件夹时只使用`os.path.basename(folder_path)`，这只会显示文件夹名称，而不是完整的挂载路径。例如：
- 完整路径：`/Volumes/Media/Movies/HD Movies`
- 当前显示：`HD Movies`

这在有多个相似名称的文件夹时会造成混淆。

## 现有解决方案参考

在`resumable_smart_importer.py`中已经有一个完善的`get_active_folders()`方法：

```python
def get_active_folders(self) -> List[str]:
    """获取所有活跃且在线的文件夹路径"""
    try:
        self.cursor.execute("SELECT folder_path FROM folders WHERE is_active = 1")
        all_folders = [row[0] for row in self.cursor.fetchall()]
        
        # 只返回在线（可访问）的文件夹
        online_folders = []
        for folder in all_folders:
            if os.path.exists(folder) and os.path.isdir(folder):
                online_folders.append(folder)
                print(f"✓ 在线文件夹: {folder}")
            else:
                print(f"✗ 离线文件夹: {folder}")
        
        return online_folders
    except Exception as e:
        print(f"获取活跃文件夹失败: {e}")
        return []
```

## 建议的修复方案

### 1. 添加在线状态检查

在`media_library.py`中添加一个类似的方法：

```python
def get_online_folders(self):
    """获取所有在线的文件夹路径"""
    try:
        self.cursor.execute("SELECT folder_path FROM folders WHERE is_active = 1")
        all_folders = [row[0] for row in self.cursor.fetchall()]
        
        # 只返回在线（可访问）的文件夹
        online_folders = []
        for folder in all_folders:
            if os.path.exists(folder) and os.path.isdir(folder):
                online_folders.append(folder)
        
        return online_folders
    except Exception as e:
        print(f"获取在线文件夹失败: {e}")
        return []
```

### 2. 修改右键菜单创建代码

将原来的：
```python
self.cursor.execute("SELECT DISTINCT folder_path FROM folders WHERE is_active = 1 ORDER BY folder_path")
for row in self.cursor.fetchall():
    _folder_path = row[0]
    _folder_name = os.path.basename(_folder_path)
    migrate_menu.add_command(label=_folder_name,
                             command=lambda fp=_folder_path: self.migrate_javsp_file_to_library(video_info['id'], video_info['path'], fp))
```

改为：
```python
online_folders = self.get_online_folders()
for folder_path in online_folders:
    # 显示完整路径或智能截断的路径
    display_name = self.get_folder_display_name(folder_path)
    migrate_menu.add_command(label=display_name,
                             command=lambda fp=folder_path: self.migrate_javsp_file_to_library(video_info['id'], video_info['path'], fp))
```

### 3. 添加文件夹显示名称格式化方法

```python
def get_folder_display_name(self, folder_path, max_length=50):
    """获取文件夹的显示名称"""
    # 如果路径较短，直接显示完整路径
    if len(folder_path) <= max_length:
        return folder_path
    
    # 对于长路径，显示开头和结尾部分
    # 例如：/Volumes/Media/Movies/HD Movies -> /Volumes.../HD Movies
    parts = folder_path.split('/')
    if len(parts) > 3:
        # 显示前两级和最后两级
        return f"{parts[0]}/{parts[1]}/.../{parts[-2]}/{parts[-1]}"
    else:
        # 对于较短的路径，显示完整路径
        return folder_path
```

### 4. 同样修改PySide6版本

在`media_library_pyside.py`中也需要进行类似的修改，确保两个版本的GUI都有一致的行为。

## 测试建议

1. **在线状态测试**：
   - 创建一个测试文件夹并添加到媒体库
   - 卸载/断开该文件夹（使其离线）
   - 检查右键菜单中是否还显示该文件夹

2. **路径显示测试**：
   - 添加具有长路径的文件夹
   - 检查右键菜单中是否正确显示完整路径或智能截断的路径
   - 验证显示的路径是否足够清晰以便识别

3. **批量操作测试**：
   - 测试批量迁移和复制功能是否也只显示在线文件夹

## 相关文件

- `media_library.py` - Tkinter版本主文件
- `media_library_pyside.py` - PySide6版本主文件  
- `resumable_smart_importer.py` - 包含正确的文件夹过滤逻辑
- `javsp_migration.py` - 迁移功能实现
- `javsp_copy.py` - 复制功能实现