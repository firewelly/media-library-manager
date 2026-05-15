#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JAVDB系统 - 右键菜单 + 顶部菜单入口
从 media_library.py 中提取的 JAVDB 相关菜单项

字段映射说明:
  - show_context_menu(): 右键菜单 → fetch_javdb_info() (单个), batch_javdb_info_selected_videos() (批量)
  - 顶部菜单 "批量导入JAVDB信息" → batch_import_javdb_for_no_title()
  - 顶部菜单 "修正JAVDB错误信息" → fix_javdb_error_titles()
  - 详情面板 "获取JAVDB信息" 按钮 → fetch_current_javdb_info()
"""

# =============================================================================
# 右键菜单 (show_context_menu)
# 位置: media_library.py 第 6566-6731 行
# =============================================================================
def show_context_menu(self, event):
    """显示右键菜单 - 包含JAVDB相关操作入口"""
    # 获取点击的项目
    item = self.video_tree.identify_row(event.y)
    if not item:
        return
    
    # 获取当前选中的所有项目
    selected_items = self.video_tree.selection()
    
    # 如果点击的项目不在选中列表中，且当前没有多选，则只选中点击的项目
    if item not in selected_items:
        if len(selected_items) <= 1:
            self.video_tree.selection_set(item)
            selected_items = [item]
        else:
            self.video_tree.selection_add(item)
            selected_items = list(selected_items) + [item]
    
    # 获取所有选中项目的信息
    selected_videos = []
    online_count = 0
    
    for selected_item in selected_items:
        try:
            video_id = self.video_tree.item(selected_item)['tags'][0]
            self.cursor.execute("SELECT file_path FROM videos WHERE id = ?", (video_id,))
            result = self.cursor.fetchone()
            
            if result:
                file_path = result[0]
                is_nas_online = self.get_cached_video_online_status(video_id, file_path)
                selected_videos.append({
                    'id': video_id,
                    'path': file_path,
                    'online': is_nas_online
                })
                if is_nas_online:
                    online_count += 1
        except (IndexError, TypeError):
            continue
    
    if len(selected_videos) == 0:
        return
    
    # 创建右键菜单
    context_menu = tk.Menu(self.root, tearoff=0)
    
    if len(selected_videos) == 1:
        # 单文件菜单 - JAVDB相关条目
        video_info = selected_videos[0]
        # ... (其他菜单项)
        context_menu.add_command(
            label="JAVDB信息获取",
            command=lambda: self.fetch_javdb_info(video_info['id'])
        )
        # ... (其他菜单项)
    else:
        # 多文件菜单 - JAVDB相关条目
        context_menu.add_command(
            label=f"批量JAVDB信息获取 ({len(selected_videos)}个文件)", 
            command=lambda: self.batch_javdb_info_selected_videos()
        )
    
    # 显示菜单
    try:
        context_menu.tk_popup(event.x_root, event.y_root)
    finally:
        context_menu.grab_release()


# =============================================================================
# 顶部菜单创建 (create_menu)
# 位置: media_library.py 第 926-962 行 (JAVDB相关部分)
# =============================================================================
def create_top_menu_javdb(self):
    """创建顶部菜单栏中的JAVDB相关菜单项"""
    # 文件菜单
    file_menu.add_command(
        label="批量导入JAVDB信息",
        command=self.batch_import_javdb_for_no_title
    )
    
    # 工具菜单
    tools_menu.add_command(
        label="修正JAVDB错误信息",
        command=self.fix_javdb_error_titles
    )


# =============================================================================
# 详情面板按钮 (create_gui)
# 位置: media_library.py 第 1311 行
# =============================================================================
def detail_panel_javdb_button(self):
    """详情面板中的获取JAVDB信息按钮"""
    ttk.Button(
        detail_right,
        text="获取JAVDB信息",
        command=self.fetch_current_javdb_info
    ).pack(fill=tk.X, pady=1)
