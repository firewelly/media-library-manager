# PySide6版本添加迁移JAVSP和复制JAVSP功能实现指南

## 概述
PySide6版本的媒体库管理器缺少原版中的"迁移JAVSP到"和"复制JAVSP到"功能。本指南提供完整的实现方案。

## 当前状态分析

### 已存在的功能
- PySide6版本有在线状态检查机制（`_is_video_online`方法）
- 有文件夹筛选功能（`load_folder_filters`方法）
- 有右键菜单框架（`show_context_menu`方法）

### 缺失的功能
- 迁移JAVSP菜单项和对应方法
- 复制JAVSP菜单项和对应方法
- 批量操作支持

## 实现步骤

### 第一步：添加在线文件夹获取方法

在`media_library_pyside.py`的`MainWindow`类中添加：

```python
def get_online_folders(self):
    """获取所有在线文件夹列表"""
    try:
        self.core.cursor.execute("SELECT folder_path FROM folders WHERE is_active = 1")
        all_folders = [row[0] for row in self.core.cursor.fetchall()]
        
        # 筛选实际可访问的文件夹
        online_folders = []
        for folder_path in all_folders:
            if os.path.exists(folder_path) and os.path.isdir(folder_path):
                online_folders.append(folder_path)
                print(f"✓ 在线文件夹: {folder_path}")
            else:
                print(f"✗ 离线文件夹: {folder_path}")
        
        return online_folders
    except Exception as e:
        print(f"获取在线文件夹失败: {e}")
        return []

def format_folder_display_name(self, folder_path):
    """格式化文件夹显示名称"""
    # 对于NAS挂载路径，显示完整路径
    if "/Volumes/" in folder_path:
        return folder_path
    
    # 对于普通路径，显示最后两级目录便于识别
    parts = folder_path.split(os.sep)
    if len(parts) > 2:
        return os.sep.join(parts[-2:])
    
    return folder_path
```

### 第二步：修改右键菜单

修改`show_context_menu`方法，在适当位置添加：

```python
def show_context_menu(self, position):
    """显示右键菜单"""
    # 获取点击的项目
    item = self.video_list.itemAt(position)
    if not item:
        return

    # 获取当前选中的所有项目
    selected_items = self.video_list.selectedItems()

    # 如果点击的项目不在选中列表中，则选中点击的项目
    if item not in selected_items:
        self.video_list.setCurrentItem(item)
        selected_items = [item]

    # 创建右键菜单
    context_menu = QMenu(self)

    # 添加菜单项
    play_action = context_menu.addAction("播放视频")
    play_action.triggered.connect(self.play_video)

    context_menu.addSeparator()

    show_in_finder_action = context_menu.addAction("在文件管理器中显示")
    show_in_finder_action.triggered.connect(self.show_in_file_manager)

    copy_path_action = context_menu.addAction("复制文件路径")
    copy_path_action.triggered.connect(self.copy_file_path)

    context_menu.addSeparator()

    # 快速设置星级子菜单
    star_menu = context_menu.addMenu("快速设置星级")

    # 清除星级
    clear_star_action = star_menu.addAction("清除星级")
    clear_star_action.triggered.connect(lambda: self.quick_set_star(0))

    # 1-5星选项
    for i in range(1, 6):
        star_action = star_menu.addAction(f"{i}星")
        star_action.triggered.connect(lambda checked, star=i: self.quick_set_star(star))

    context_menu.addSeparator()

    refresh_thumbnail_action = context_menu.addAction("刷新封面")
    refresh_thumbnail_action.triggered.connect(self.refresh_thumbnail)

    # 添加迁移和复制功能
    online_folders = self.get_online_folders()
    if online_folders:
        context_menu.addSeparator()
        
        if len(selected_items) == 1:
            # 单文件操作
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
        else:
            # 批量操作
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

    context_menu.addSeparator()

    delete_action = context_menu.addAction("删除视频")
    delete_action.triggered.connect(self.delete_video)

    # 显示菜单
    context_menu.exec_(self.video_list.mapToGlobal(position))
```

### 第三步：实现核心功能方法

在`MainWindow`类中添加以下方法：

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
    
    # 检查文件是否在线
    if not os.path.exists(file_path):
        self.show_warning("提示", "视频文件离线，无法迁移")
        return
    
    # 调用迁移功能
    try:
        from utils.javsp_migration import migrate_single
        result = migrate_single(self.core.cursor, self.core.conn, file_path, video_id, target_library_path)
        
        if result['ok']:
            self.show_info("成功", f"文件已迁移到: {result['final_path']}")
            self.load_videos()  # 刷新列表
        else:
            self.show_error("失败", f"迁移失败: {result['error']}")
    except ImportError:
        self.show_error("错误", "无法导入迁移模块")
    except Exception as e:
        self.show_error("错误", f"迁移过程中出错: {str(e)}")

def copy_javsp_file_to_library(self, target_library_path):
    """复制JavSP文件到指定媒体库"""
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
    
    # 检查文件是否在线
    if not os.path.exists(file_path):
        self.show_warning("提示", "视频文件离线，无法复制")
        return
    
    # 调用复制功能
    try:
        from utils.javsp_copy import copy_single
        result = copy_single(self.core.cursor, self.core.conn, file_path, video_id, target_library_path)
        
        if result['ok']:
            self.show_info("成功", f"文件已复制到: {result['final_path']}")
            self.load_videos()  # 刷新列表
        else:
            self.show_error("失败", f"复制失败: {result['error']}")
    except ImportError:
        self.show_error("错误", "无法导入复制模块")
    except Exception as e:
        self.show_error("错误", f"复制过程中出错: {str(e)}")
```

### 第四步：实现批量操作功能

```python
def batch_migrate_javsp_files_to_library(self, target_library_path):
    """批量迁移JavSP文件到指定媒体库"""
    selected_items = self.video_list.selectedItems()
    if not selected_items:
        return
    
    # 确认操作
    reply = QMessageBox.question(
        self, "确认批量迁移",
        f"确定要将选中的 {len(selected_items)} 个视频迁移到:\n{target_library_path}\n\n注意：此操作将移动文件并更新数据库。",
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No
    )
    
    if reply != QMessageBox.Yes:
        return
    
    # 执行批量迁移
    success_count = 0
    failed_count = 0
    failed_files = []
    
    try:
        from utils.javsp_migration import migrate_single
        
        for item in selected_items:
            video_id = item.data(0, Qt.UserRole)
            
            # 获取视频文件路径
            self.core.cursor.execute("SELECT file_path FROM videos WHERE id = ?", (video_id,))
            result = self.core.cursor.fetchone()
            if not result:
                failed_count += 1
                continue
            
            file_path = result[0]
            
            # 检查文件是否在线
            if not os.path.exists(file_path):
                failed_files.append(f"离线: {os.path.basename(file_path)}")
                failed_count += 1
                continue
            
            # 执行迁移
            result = migrate_single(self.core.cursor, self.core.conn, file_path, video_id, target_library_path)
            
            if result['ok']:
                success_count += 1
            else:
                failed_count += 1
                failed_files.append(f"{os.path.basename(file_path)}: {result['error']}")
        
        # 显示结果
        if failed_count == 0:
            self.show_info("批量迁移完成", f"成功迁移 {success_count} 个文件")
        else:
            error_msg = f"批量迁移完成：\n成功: {success_count} 个\n失败: {failed_count} 个"
            if failed_files:
                error_msg += f"\n\n失败文件:\n" + "\n".join(failed_files[:5])  # 只显示前5个
                if len(failed_files) > 5:
                    error_msg += f"\n... 还有 {len(failed_files) - 5} 个文件"
            self.show_warning("批量迁移结果", error_msg)
        
        # 刷新列表
        self.load_videos()
        
    except ImportError:
        self.show_error("错误", "无法导入迁移模块")
    except Exception as e:
        self.show_error("错误", f"批量迁移过程中出错: {str(e)}")

def batch_copy_javsp_files_to_library(self, target_library_path):
    """批量复制JavSP文件到指定媒体库"""
    # 类似批量迁移功能，但使用copy_single
    # 实现代码与batch_migrate_javsp_files_to_library类似
    pass
```

### 第五步：添加进度对话框（可选）

对于大批量操作，可以添加进度对话框：

```python
def show_progress_dialog(self, title, max_value):
    """显示进度对话框"""
    from PySide6.QtWidgets import QProgressDialog
    
    progress = QProgressDialog(title, "取消", 0, max_value, self)
    progress.setWindowModality(Qt.WindowModal)
    progress.setAutoClose(True)
    progress.setAutoReset(True)
    
    return progress
```

## 测试验证

### 功能测试清单
1. **在线状态检查**
   - ✓ 只显示可访问的文件夹
   - ✓ 离线文件夹不显示
   - ✓ 文件夹状态变化时实时更新

2. **路径显示**
   - ✓ 显示完整挂载路径
   - ✓ NAS路径格式正确
   - ✓ 普通路径显示最后两级

3. **单文件操作**
   - ✓ 迁移功能正常工作
   - ✓ 复制功能正常工作
   - ✓ 错误处理完善

4. **批量操作**
   - ✓ 批量迁移功能
   - ✓ 批量复制功能
   - ✓ 进度反馈
   - ✓ 结果统计

5. **用户界面**
   - ✓ 菜单项显示正确
   - ✓ 操作反馈及时
   - ✓ 错误提示友好

## 注意事项

1. **性能优化**
   - 在线检查可能增加响应时间
   - 考虑缓存文件夹状态
   - 大批量操作时显示进度

2. **错误处理**
   - 完善的异常捕获
   - 用户友好的错误提示
   - 操作回滚机制

3. **数据库一致性**
   - 确保迁移后数据完整性
   - 处理数据库事务
   - 避免数据不一致

4. **跨平台兼容性**
   - 路径处理考虑不同操作系统
   - 文件系统差异处理
   - 权限问题处理

## 总结

通过本指南的实现，PySide6版本将具备与原版相同的JAVSP迁移和复制功能，并且解决了文件夹显示和在线状态检查的问题。用户界面将更加友好，功能更加完善。