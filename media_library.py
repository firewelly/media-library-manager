#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MacOS视频媒体库管理软件
功能：本地数据库、NAS扫描、标签管理、NFO导入、去重复、星级评分
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import sqlite3
import os
import hashlib
import threading
import subprocess
import platform
import xml.etree.ElementTree as ET
from pathlib import Path
import re
from datetime import datetime
import shutil
import base64
from PIL import Image, ImageTk
import io
import tempfile
import json
import time
import cv2
from send2trash import send2trash

class ProgressWindow:
    """进度显示窗口"""
    def __init__(self, parent, title="处理进度", total_items=0):
        self.window = tk.Toplevel(parent)
        self.window.title(title)
        self.window.geometry("600x280")
        self.window.resizable(False, False)
        
        # 居中显示
        self.window.transient(parent)
        self.window.grab_set()
        
        # 创建界面元素
        main_frame = ttk.Frame(self.window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 当前处理文件标签
        self.current_file_label = ttk.Label(main_frame, text="准备开始...", font=('Arial', 10))
        self.current_file_label.pack(pady=(0, 10))
        
        # 进度条
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            main_frame, 
            variable=self.progress_var, 
            maximum=100, 
            length=500,
            mode='determinate'
        )
        self.progress_bar.pack(pady=(0, 10))
        
        # 进度文本
        self.progress_text = ttk.Label(main_frame, text=f"0/{total_items} (0%)", font=('Arial', 9))
        self.progress_text.pack(pady=(0, 5))
        
        # 统计信息
        self.stats_label = ttk.Label(main_frame, text="成功: 0 | 失败: 0", font=('Arial', 9), foreground="blue")
        self.stats_label.pack(pady=(0, 10))
        
        # 状态信息
        self.status_label = ttk.Label(main_frame, text="", font=('Arial', 9), foreground="green")
        self.status_label.pack(pady=(0, 10))
        
        # 取消按钮
        self.cancel_button = ttk.Button(main_frame, text="取消", command=self.cancel)
        self.cancel_button.pack()
        
        self.cancelled = False
        self.completed = False
        self.total_items = total_items
        self.success_count = 0
        self.failed_count = 0
        
    def update_progress(self, current, message="", success=None):
        """更新进度"""
        if self.cancelled:
            return
            
        try:
            # 更新成功/失败计数
            if success is True:
                self.success_count += 1
            elif success is False:
                self.failed_count += 1
            
            # 更新进度条和文本
            if self.total_items > 0:
                # 修复进度显示逻辑：处理过程中显示(current-1)/total，完成时显示100%
                if current >= self.total_items:
                    percentage = 100.0
                    display_current = self.total_items
                else:
                    percentage = ((current - 1) / self.total_items) * 100 if current > 0 else 0
                    display_current = current
                self.progress_var.set(percentage)
                self.progress_text.config(text=f"{display_current}/{self.total_items} ({percentage:.1f}%)")
            else:
                self.progress_var.set(0)
                self.progress_text.config(text="0/0 (0%)")
            
            # 更新统计信息
            self.stats_label.config(text=f"成功: {self.success_count} | 失败: {self.failed_count}")
                
            # 更新当前处理文件
            if message:
                self.current_file_label.config(text=f"正在处理: {message}")
                
            # 如果完成
            if self.total_items > 0 and current >= self.total_items:
                self.completed = True
                self.cancel_button.config(text="关闭")
                self.current_file_label.config(text="处理完成！")
                
            self.window.update()
        except tk.TclError:
            # 窗口已关闭
            pass
    
    def update_status(self, status_message, color="green"):
        """更新状态信息"""
        try:
            self.status_label.config(text=status_message, foreground=color)
            self.window.update()
        except tk.TclError:
            pass
            
    def cancel(self):
        """取消操作"""
        if self.completed:
            self.window.destroy()
        else:
            self.cancelled = True
            self.window.destroy()
            
    def is_cancelled(self):
        """检查是否已取消"""
        return self.cancelled
        
    def close(self):
        """关闭窗口"""
        try:
            self.window.destroy()
        except tk.TclError:
            pass

class MediaLibrary:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("视频媒体库管理器")
        self.root.geometry("1200x800")
        
        # 配置文件路径
        self.config_path = os.path.join(os.path.dirname(__file__), 'gui_config.json')
        
        # 默认列配置
        self.default_columns = {
            'title': {'width': 400, 'position': 0, 'text': '标题'},
            'actors': {'width': 150, 'position': 1, 'text': '演员'},
            'stars': {'width': 75, 'position': 2, 'text': '星级'},
            'tags': {'width': 120, 'position': 3, 'text': '标签'},
            'size': {'width': 80, 'position': 4, 'text': '大小'},
            'status': {'width': 60, 'position': 5, 'text': '状态'},
            'device': {'width': 120, 'position': 6, 'text': '设备'},
            'duration': {'width': 120, 'position': 7, 'text': '时长'},
            'resolution': {'width': 150, 'position': 8, 'text': '分辨率'},
            'file_created_time': {'width': 120, 'position': 9, 'text': '创建时间'},
            'top_folder': {'width': 120, 'position': 10, 'text': '顶层文件夹'},
            'full_path': {'width': 200, 'position': 11, 'text': '完整路径'},
            'year': {'width': 60, 'position': 12, 'text': '年份'},
            'javdb_code': {'width': 100, 'position': 13, 'text': '番号'},
            'javdb_title': {'width': 300, 'position': 14, 'text': 'JAVDB标题'},
            'release_date': {'width': 100, 'position': 15, 'text': '发行日期'},
            'javdb_rating': {'width': 80, 'position': 16, 'text': 'JAVDB评分'},
            'javdb_tags': {'width': 200, 'position': 17, 'text': 'JAVDB标签'}
        }
        
        # 加载列配置
        self.load_column_config()
        
        # 数据库初始化
        self.init_database()
        
        # 创建GUI
        self.create_gui()
        
        # 当前选中的视频
        self.current_video = None
        
        # 排序状态
        self.sort_column_name = None
        self.sort_reverse = False
        
        # GPU加速状态
        self.gpu_acceleration = None
        self.check_gpu_acceleration_status()
        
        # 绑定窗口关闭事件保存配置
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def load_column_config(self):
        """加载列配置"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    saved_config = json.load(f)
                    self.column_config = saved_config.get('columns', self.default_columns.copy())
            else:
                self.column_config = self.default_columns.copy()
        except Exception as e:
            print(f"加载配置失败: {e}")
            self.column_config = self.default_columns.copy()
    
    def save_column_config(self):
        """保存列配置"""
        try:
            # 获取当前列宽度
            if hasattr(self, 'video_tree'):
                for col in self.video_tree['columns']:
                    if col in self.column_config:
                        current_width = self.video_tree.column(col, 'width')
                        # 直接保存用户调整的列宽，不做任何限制
                        self.column_config[col]['width'] = current_width
            
            config = {'columns': self.column_config}
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存配置失败: {e}")
    
    def setup_column_drag(self):
        """设置列拖拽功能"""
        # 拖拽状态变量
        self.drag_data = {'dragging': False, 'start_col': None, 'start_x': 0}
        
        # 注意：右键菜单绑定在create_gui中统一处理，避免冲突
    
    def on_drag_start(self, event):
        """开始拖拽"""
        region = self.video_tree.identify_region(event.x, event.y)
        if region == "heading":
            column = self.video_tree.identify_column(event.x)
            if column:
                col_index = int(column.replace('#', '')) - 1
                if 0 <= col_index < len(self.video_tree['columns']):
                    col_name = self.video_tree['columns'][col_index]
                    self.drag_data = {
                        'dragging': True,
                        'start_col': col_name,
                        'start_x': event.x,
                        'current_col': col_name
                    }
                    # 改变鼠标样式
                    self.video_tree.config(cursor="hand2")
                    return "break"  # 阻止事件继续传播
        else:
            # 如果不是表头区域，重置拖拽状态
            self.drag_data = {'dragging': False, 'start_col': None, 'start_x': 0}
    
    def on_drag_motion(self, event):
        """拖拽过程中"""
        if self.drag_data['dragging']:
            # 检查当前鼠标位置对应的列
            region = self.video_tree.identify_region(event.x, event.y)
            if region == "heading":
                column = self.video_tree.identify_column(event.x)
                if column:
                    col_index = int(column.replace('#', '')) - 1
                    if 0 <= col_index < len(self.video_tree['columns']):
                        current_col = self.video_tree['columns'][col_index]
                        if current_col != self.drag_data['current_col']:
                            self.drag_data['current_col'] = current_col
                            # 可以在这里添加视觉反馈
    
    def on_drag_end(self, event):
        """结束拖拽"""
        if self.drag_data['dragging']:
            # 恢复鼠标样式
            self.video_tree.config(cursor="")
            
            # 检查是否需要移动列
            region = self.video_tree.identify_region(event.x, event.y)
            if region == "heading":
                column = self.video_tree.identify_column(event.x)
                if column:
                    col_index = int(column.replace('#', '')) - 1
                    if 0 <= col_index < len(self.video_tree['columns']):
                        target_col = self.video_tree['columns'][col_index]
                        start_col = self.drag_data['start_col']
                        
                        if target_col != start_col:
                            # 执行列移动
                            self.swap_columns(start_col, target_col)
            
            # 重置拖拽状态
            self.drag_data = {'dragging': False, 'start_col': None, 'start_x': 0}
    
    def swap_columns(self, col1, col2):
        """交换两列的位置"""
        pos1 = self.column_config[col1]['position']
        pos2 = self.column_config[col2]['position']
        
        # 交换位置
        self.column_config[col1]['position'] = pos2
        self.column_config[col2]['position'] = pos1
        
        # 重新创建表格
        self.recreate_treeview()
        
        # 保存配置
        self.save_column_config()
        
        # 显示提示
        messagebox.showinfo("列移动", f"已将 '{self.column_config[col1]['text']}' 与 '{self.column_config[col2]['text']}' 交换位置")
    
    def handle_right_click(self, event):
        """统一处理右键点击事件"""
        region = self.video_tree.identify_region(event.x, event.y)
        if region == "heading":
            # 点击在列标题上，显示列管理菜单
            self.show_column_menu(event)
        else:
            # 点击在其他区域，显示上下文菜单
            self.show_context_menu(event)
    
    def show_column_menu(self, event):
        """显示列管理菜单"""
        # 检查是否点击在列标题上
        region = self.video_tree.identify_region(event.x, event.y)
        if region == "heading":
            column = self.video_tree.identify_column(event.x)
            if column:
                col_name = self.video_tree['columns'][int(column.replace('#', '')) - 1]
                
                menu = tk.Menu(self.root, tearoff=0)
                menu.add_command(label=f"向左移动 '{self.column_config[col_name]['text']}'", 
                               command=lambda: self.move_column(col_name, -1))
                menu.add_command(label=f"向右移动 '{self.column_config[col_name]['text']}'", 
                               command=lambda: self.move_column(col_name, 1))
                menu.add_separator()
                menu.add_command(label="拖拽提示", state="disabled")
                menu.add_command(label="💡 按住列标题拖拽可重新排序", state="disabled")
                menu.add_separator()
                menu.add_command(label="重置所有列", command=self.reset_gui_layout)
                
                try:
                    menu.tk_popup(event.x_root, event.y_root)
                finally:
                    menu.grab_release()
    
    def move_column(self, col_name, direction):
        """移动列位置"""
        current_pos = self.column_config[col_name]['position']
        new_pos = current_pos + direction
        
        # 找到目标位置的列
        target_col = None
        for name, config in self.column_config.items():
            if config['position'] == new_pos:
                target_col = name
                break
        
        if target_col:
            # 交换位置
            self.column_config[col_name]['position'] = new_pos
            self.column_config[target_col]['position'] = current_pos
            
            # 重新创建表格
            self.recreate_treeview()
            
            # 保存配置
            self.save_column_config()
    
    def recreate_treeview(self):
        """重新创建表格视图"""
        # 保存当前选中项
        selected_items = self.video_tree.selection()
        selected_values = []
        for item in selected_items:
            selected_values.append(self.video_tree.item(item)['values'])
        
        # 保存滚动位置
        scroll_top = self.video_tree.yview()[0]
        
        # 销毁当前表格和控制栏
        list_frame = self.video_tree.master
        
        # 清理所有子控件
        for widget in list_frame.winfo_children():
            widget.destroy()
        
        # 重新创建顶部控制栏
        control_frame = ttk.Frame(list_frame)
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 重新创建"仅显示在线"复选框
        if not hasattr(self, 'show_online_only'):
            self.show_online_only = tk.BooleanVar(value=False)
        online_checkbox = ttk.Checkbutton(control_frame, text="仅显示在线", 
                                         variable=self.show_online_only,
                                         command=self.filter_videos)
        online_checkbox.pack(side=tk.RIGHT)
        
        # 重新创建表格
        sorted_columns = sorted(self.column_config.items(), key=lambda x: x[1]['position'])
        columns = [col[0] for col in sorted_columns]
        
        self.video_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15, selectmode='extended')
        
        # 设置列标题和宽度
        for col_name in columns:
            config = self.column_config[col_name]
            self.video_tree.heading(col_name, text=config['text'], 
                                  command=lambda c=col_name: self.sort_column(c))
            # 确保列宽不会过小，最小宽度为50
            width = max(config['width'], 50)
            self.video_tree.column(col_name, width=width, minwidth=50)
        
        # 初始化排序状态
        if not hasattr(self, 'sort_column_name'):
            self.sort_column_name = None
        if not hasattr(self, 'sort_reverse'):
            self.sort_reverse = False
        
        # 重新设置滚动条
        v_scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.video_tree.yview)
        self.video_tree.configure(yscrollcommand=v_scrollbar.set)
        
        h_scrollbar = ttk.Scrollbar(list_frame, orient=tk.HORIZONTAL, command=self.video_tree.xview)
        self.video_tree.configure(xscrollcommand=h_scrollbar.set)
        
        # 重新布局
        self.video_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X, before=self.video_tree)
        
        # 重新绑定事件
        self.setup_column_drag()
        self.video_tree.bind('<<TreeviewSelect>>', self.on_video_select)
        
        # 绑定列宽调整事件
        self.video_tree.bind('<ButtonRelease-1>', self.on_column_resize_end)
        # 初始化列宽记录
        self._last_column_widths = {}
        self._is_dragging_column = False
        for col in columns:
            self._last_column_widths[col] = self.video_tree.column(col, 'width')
        
        # 绑定双击事件（使用专门的处理方法）
        self.video_tree.bind('<Double-1>', self.handle_double_click)
        
        # 绑定单击事件
        self.video_tree.bind('<Button-1>', self.handle_single_click)
        
        # 右键菜单绑定 - 支持不同平台，统一处理
        if platform.system() == "Darwin":  # macOS
            self.video_tree.bind('<Button-2>', self.handle_right_click)  # macOS右键
            self.video_tree.bind('<Control-Button-1>', self.handle_right_click)  # macOS Control+点击
        else:
            self.video_tree.bind('<Button-3>', self.handle_right_click)  # Windows/Linux右键
        
        # 重新加载数据
        self.load_videos()
        
        # 恢复滚动位置
        self.root.after(100, lambda: self.video_tree.yview_moveto(scroll_top))
    
    def on_column_resize_end(self, event):
        """列宽调整结束后保存配置"""
        try:
            region = self.video_tree.identify_region(event.x, event.y)
            if region == "separator":
                # 延迟保存以确保获取最新宽度
                if hasattr(self, '_resize_after_id'):
                    self.root.after_cancel(self._resize_after_id)
                self._resize_after_id = self.root.after(100, self.save_column_config_after_resize)
        except Exception as e:
            print(f"Error in on_column_resize_end: {e}")

    def save_column_config_after_resize(self):
        """延迟保存以确保获取最新宽度"""
        try:
            current_widths = {col: self.video_tree.column(col, 'width') for col in self.video_tree['columns']}
            
            # 更新配置中的列宽
            for col, width in current_widths.items():
                if col in self.column_config:
                    self.column_config[col]['width'] = width
            
            # 保存配置
            self.save_column_config()
            
            # 更新记录的宽度
            self._last_column_widths = current_widths.copy()
            
        except Exception as e:
            print(f"Error saving column config: {e}")

    def sort_column(self, col):
        """排序列"""
        try:
            # 确定排序方向
            if self.sort_column_name == col:
                self.sort_reverse = not self.sort_reverse
            else:
                self.sort_column_name = col
                self.sort_reverse = False
            
            # 获取数据
            data = [(self.video_tree.set(item, col), item) for item in self.video_tree.get_children('')]
            
            def sort_key(t):
                val = t[0]
                if isinstance(val, str):
                    # 尝试转换为数字
                    if val.replace('.', '', 1).replace('-', '', 1).isdigit():
                        return float(val)
                    # 处理星级
                    if '★' in val:
                        return len(val)
                return val or ''

            data.sort(key=sort_key, reverse=self.sort_reverse)

            # 重新排列项目
            for index, (val, item) in enumerate(data):
                self.video_tree.move(item, '', index)

            # 更新列标题显示排序方向
            for column in self.video_tree['columns']:
                if column == col:
                    direction = ' ↓' if self.sort_reverse else ' ↑'
                    text = self.column_config[column]['text'] + direction
                else:
                    text = self.column_config[column]['text']
                self.video_tree.heading(column, text=text)
                
        except Exception as e:
            print(f"Error in sort_column for column {col}: {e}")
    
    def reset_gui_layout(self):
        """重置界面布局"""
        if messagebox.askyesno("确认重置", "确定要重置界面布局到默认设置吗？"):
            self.column_config = self.default_columns.copy()
            self.recreate_treeview()
            self.save_column_config()
            messagebox.showinfo("重置完成", "界面布局已重置为默认设置")
    
    def on_closing(self):
        """窗口关闭时保存配置"""
        self.save_column_config()
        self.root.destroy()
        
    def init_database(self):
        """初始化SQLite数据库"""
        self.db_path = os.path.join(os.path.dirname(__file__), 'media_library.db')
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        
        # 创建表
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE NOT NULL,
                file_name TEXT NOT NULL,
                file_size INTEGER,
                file_hash TEXT,
                title TEXT,
                description TEXT,
                genre TEXT,
                year INTEGER,
                rating REAL,
                stars INTEGER DEFAULT 0,
                tags TEXT,
                nas_path TEXT,
                is_nas_online BOOLEAN DEFAULT 1,
                thumbnail_data BLOB,
                thumbnail_path TEXT,
                duration INTEGER,
                resolution TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS folders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                folder_path TEXT UNIQUE NOT NULL,
                folder_type TEXT DEFAULT 'local',
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tag_name TEXT UNIQUE NOT NULL,
                tag_color TEXT DEFAULT '#007AFF',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 数据库迁移：添加新字段（如果不存在）
        self.migrate_database()
        
        self.conn.commit()
        
    def migrate_database(self):
        """数据库迁移：添加新字段"""
        try:
            # 检查videos表是否需要添加新字段
            self.cursor.execute("PRAGMA table_info(videos)")
            video_columns = [column[1] for column in self.cursor.fetchall()]
            
            # 添加videos表缺失的字段
            if 'thumbnail_data' not in video_columns:
                self.cursor.execute('ALTER TABLE videos ADD COLUMN thumbnail_data BLOB')
                print("添加字段: thumbnail_data")
                
            if 'thumbnail_path' not in video_columns:
                self.cursor.execute('ALTER TABLE videos ADD COLUMN thumbnail_path TEXT')
                print("添加字段: thumbnail_path")
                
            if 'duration' not in video_columns:
                self.cursor.execute('ALTER TABLE videos ADD COLUMN duration INTEGER')
                print("添加字段: duration")
                
            if 'resolution' not in video_columns:
                self.cursor.execute('ALTER TABLE videos ADD COLUMN resolution TEXT')
                print("添加字段: resolution")
                
            if 'file_created_time' not in video_columns:
                self.cursor.execute('ALTER TABLE videos ADD COLUMN file_created_time TIMESTAMP')
                print("添加字段: file_created_time")
                
            if 'source_folder' not in video_columns:
                self.cursor.execute('ALTER TABLE videos ADD COLUMN source_folder TEXT')
                print("添加字段: source_folder")
                
            if 'md5_hash' not in video_columns:
                self.cursor.execute('ALTER TABLE videos ADD COLUMN md5_hash TEXT')
                print("添加字段: md5_hash")
            
            # 检查folders表是否需要添加新字段
            self.cursor.execute("PRAGMA table_info(folders)")
            folder_columns = [column[1] for column in self.cursor.fetchall()]
            
            # 添加folders表缺失的字段
            if 'device_name' not in folder_columns:
                self.cursor.execute('ALTER TABLE folders ADD COLUMN device_name TEXT')
                print("添加字段: device_name")
                # 为现有记录设置当前设备名称
                current_device = self.get_current_device_name()
                self.cursor.execute('UPDATE folders SET device_name = ? WHERE device_name IS NULL', (current_device,))
                print(f"为现有文件夹设置设备名称: {current_device}")
                
        except Exception as e:
            print(f"数据库迁移失败: {str(e)}")
        
    def create_gui(self):
        """创建主界面"""
        # 主菜单
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # 文件菜单
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="文件", menu=file_menu)
        file_menu.add_command(label="扫描媒体文件", command=self.scan_media)
        file_menu.add_command(label="智能媒体库更新", command=self.comprehensive_media_update)
        file_menu.add_separator()
        file_menu.add_command(label="导入NFO文件", command=self.import_nfo)
        file_menu.add_command(label="导入视频文件", command=self.import_videos)
        file_menu.add_separator()
        file_menu.add_command(label="批量导入NFO信息", command=self.batch_import_nfo_for_no_actors)
        file_menu.add_command(label="批量导入JAVDB信息", command=self.batch_import_javdb_for_no_title)
        file_menu.add_separator()
        file_menu.add_command(label="去重复", command=self.remove_duplicates)
        
        # 工具菜单
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="工具", menu=tools_menu)
        tools_menu.add_command(label="标签管理", command=self.manage_tags)
        tools_menu.add_command(label="文件夹管理", command=self.manage_folders)
        tools_menu.add_separator()
        tools_menu.add_command(label="同步打分到文件", command=self.sync_stars_to_filename)
        tools_menu.add_separator()
        tools_menu.add_command(label="批量计算MD5", command=self.batch_calculate_md5)
        tools_menu.add_command(label="智能去重", command=self.smart_remove_duplicates)
        tools_menu.add_command(label="文件移动管理", command=self.file_move_manager)
        tools_menu.add_separator()
        tools_menu.add_command(label="清理演员信息", command=self.clean_actor_data)
        tools_menu.add_separator()
        tools_menu.add_command(label="重新导入元数据", command=self.reimport_incomplete_metadata)
        tools_menu.add_command(label="完全重置数据库", command=self.full_database_reset)
        tools_menu.add_separator()
        tools_menu.add_command(label="批量生成封面", command=self.batch_generate_thumbnails)
        tools_menu.add_separator()
        tools_menu.add_command(label="批量自动更新所有标签", command=self.batch_auto_tag_all)
        tools_menu.add_command(label="批量标注没有标签的文件", command=self.batch_auto_tag_no_tags)
        tools_menu.add_separator()
        tools_menu.add_command(label="批量清理文件名", command=self.batch_clean_filename_selected_videos)
        tools_menu.add_separator()
        tools_menu.add_command(label="智能媒体库更新", command=self.comprehensive_media_update)
        
        # 界面菜单
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="界面", menu=view_menu)
        view_menu.add_command(label="重置界面布局", command=self.reset_gui_layout)
        
        # 主框架
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 左侧面板 - 筛选和搜索
        left_frame = ttk.Frame(main_frame, width=300)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_frame.pack_propagate(False)
        
        # 搜索框
        search_frame = ttk.LabelFrame(left_frame, text="搜索")
        search_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 标题搜索
        title_search_frame = ttk.Frame(search_frame)
        title_search_frame.pack(fill=tk.X, padx=5, pady=(5, 2))
        
        ttk.Label(title_search_frame, text="标题:").pack(side=tk.LEFT)
        self.title_search_var = tk.StringVar()
        title_search_entry = ttk.Entry(title_search_frame, textvariable=self.title_search_var)
        title_search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        title_search_entry.bind('<KeyRelease>', self.on_search)
        
        # 标签搜索
        tag_search_frame = ttk.Frame(search_frame)
        tag_search_frame.pack(fill=tk.X, padx=5, pady=(2, 2))
        
        ttk.Label(tag_search_frame, text="标签:").pack(side=tk.LEFT)
        self.tag_search_var = tk.StringVar()
        tag_search_entry = ttk.Entry(tag_search_frame, textvariable=self.tag_search_var)
        tag_search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        tag_search_entry.bind('<KeyRelease>', self.on_search)
        
        # 演员搜索
        actor_search_frame = ttk.Frame(search_frame)
        actor_search_frame.pack(fill=tk.X, padx=5, pady=(2, 5))
        
        ttk.Label(actor_search_frame, text="演员:").pack(side=tk.LEFT)
        self.actor_search_var = tk.StringVar()
        actor_search_entry = ttk.Entry(actor_search_frame, textvariable=self.actor_search_var)
        actor_search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        actor_search_entry.bind('<KeyRelease>', self.on_search)
        
        # 星级筛选
        stars_frame = ttk.LabelFrame(left_frame, text="星级筛选")
        stars_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.star_filter = tk.IntVar(value=0)
        for i in range(6):
            star_text = "全部" if i == 0 else f"{i}星"
            ttk.Radiobutton(stars_frame, text=star_text, variable=self.star_filter, 
                           value=i, command=self.filter_videos).pack(anchor=tk.W, padx=5)
        
        # 标签筛选
        tags_frame = ttk.LabelFrame(left_frame, text="标签筛选")
        tags_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.tags_listbox = tk.Listbox(tags_frame, height=6, selectmode=tk.MULTIPLE)
        self.tags_listbox.pack(fill=tk.BOTH, padx=5, pady=5)
        self.tags_listbox.bind('<<ListboxSelect>>', self.filter_videos)
        
        # NAS状态筛选
        nas_frame = ttk.LabelFrame(left_frame, text="NAS状态")
        nas_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.nas_filter = tk.StringVar(value="all")
        ttk.Radiobutton(nas_frame, text="全部", variable=self.nas_filter, 
                       value="all", command=self.filter_videos).pack(anchor=tk.W, padx=5)
        ttk.Radiobutton(nas_frame, text="在线", variable=self.nas_filter, 
                       value="online", command=self.filter_videos).pack(anchor=tk.W, padx=5)
        ttk.Radiobutton(nas_frame, text="离线", variable=self.nas_filter, 
                       value="offline", command=self.filter_videos).pack(anchor=tk.W, padx=5)
        
        # 文件夹来源筛选
        folder_frame = ttk.LabelFrame(left_frame, text="文件夹来源")
        folder_frame.pack(fill=tk.X)
        
        self.folder_filter = tk.StringVar(value="all")
        self.folder_listbox = tk.Listbox(folder_frame, height=4, selectmode=tk.SINGLE)
        self.folder_listbox.pack(fill=tk.BOTH, padx=5, pady=5)
        self.folder_listbox.bind('<<ListboxSelect>>', self.filter_videos)
        
        # 加载文件夹列表
        self.load_folder_sources()
        
        # 右侧面板 - 视频列表和详情
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # 视频列表
        list_frame = ttk.LabelFrame(right_frame, text="视频列表")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # 顶部控制栏
        control_frame = ttk.Frame(list_frame)
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 仅显示在线内容的checkbox
        self.show_online_only = tk.BooleanVar(value=False)
        online_checkbox = ttk.Checkbutton(control_frame, text="仅显示在线", 
                                         variable=self.show_online_only,
                                         command=self.filter_videos)
        online_checkbox.pack(side=tk.RIGHT)
        
        # 根据配置创建列顺序
        sorted_columns = sorted(self.column_config.items(), key=lambda x: x[1]['position'])
        columns = [col[0] for col in sorted_columns]
        
        # 创建Treeview
        self.video_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15, selectmode='extended')
        
        # 设置列标题和宽度，添加排序功能
        for col_name in columns:
            config = self.column_config[col_name]
            self.video_tree.heading(col_name, text=config['text'], 
                                  command=lambda c=col_name: self.sort_column(c))
            # 确保列宽不会过小，最小宽度为50
            width = max(config['width'], 50)
            self.video_tree.column(col_name, width=width, minwidth=50)
        
        # 绑定列拖拽事件
        self.setup_column_drag()
        
        # 垂直滚动条
        v_scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.video_tree.yview)
        self.video_tree.configure(yscrollcommand=v_scrollbar.set)
        
        # 水平滚动条
        h_scrollbar = ttk.Scrollbar(list_frame, orient=tk.HORIZONTAL, command=self.video_tree.xview)
        self.video_tree.configure(xscrollcommand=h_scrollbar.set)
        
        # 使用pack布局
        self.video_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X, before=self.video_tree)
        
        # 绑定列宽调整事件
        self.video_tree.bind('<ButtonRelease-1>', self.on_column_resize_end)
        # 初始化列宽记录
        self._last_column_widths = {}
        self._is_dragging_column = False
        for col in columns:
            self._last_column_widths[col] = self.video_tree.column(col, 'width')
        
        # 绑定选择事件
        self.video_tree.bind('<<TreeviewSelect>>', self.on_video_select)
        
        # 绑定双击事件（使用专门的处理方法）
        self.video_tree.bind('<Double-1>', self.handle_double_click)
        
        # 绑定单击事件
        self.video_tree.bind('<Button-1>', self.handle_single_click)
        
        # 绑定拖拽事件
        self.video_tree.bind('<B1-Motion>', self.on_drag_motion)
        self.video_tree.bind('<ButtonRelease-1>', self.on_drag_end)
        
        # 右键菜单绑定 - 支持不同平台，统一处理
        if platform.system() == "Darwin":  # macOS
            self.video_tree.bind('<Button-2>', self.handle_right_click)  # macOS右键
            self.video_tree.bind('<Control-Button-1>', self.handle_right_click)  # macOS Control+点击
        else:
            self.video_tree.bind('<Button-3>', self.handle_right_click)  # Windows/Linux右键
        
        # 详情面板
        detail_frame = ttk.LabelFrame(right_frame, text="视频详情")
        detail_frame.pack(fill=tk.X)
        
        # 创建可滚动的详情内容区域
        detail_canvas = tk.Canvas(detail_frame, height=300)
        detail_scrollbar = ttk.Scrollbar(detail_frame, orient="vertical", command=detail_canvas.yview)
        detail_scrollable_frame = ttk.Frame(detail_canvas)
        
        detail_scrollable_frame.bind(
            "<Configure>",
            lambda e: detail_canvas.configure(scrollregion=detail_canvas.bbox("all"))
        )
        
        detail_canvas.create_window((0, 0), window=detail_scrollable_frame, anchor="nw")
        detail_canvas.configure(yscrollcommand=detail_scrollbar.set)
        
        detail_canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        detail_scrollbar.pack(side="right", fill="y")
        
        # 绑定鼠标滚轮事件
        def _on_mousewheel(event):
            detail_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def _bind_to_mousewheel(event):
            detail_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        def _unbind_from_mousewheel(event):
            detail_canvas.unbind_all("<MouseWheel>")
        
        detail_canvas.bind('<Enter>', _bind_to_mousewheel)
        detail_canvas.bind('<Leave>', _unbind_from_mousewheel)
        
        # 详情内容
        detail_content = ttk.Frame(detail_scrollable_frame)
        detail_content.pack(fill=tk.X, padx=5, pady=5)
        
        # 详情内容（移除独立的封面frame）
        detail_left = ttk.Frame(detail_content)
        detail_left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        ttk.Label(detail_left, text="标题:").grid(row=0, column=0, sticky=tk.W, pady=0)
        self.title_var = tk.StringVar()
        ttk.Entry(detail_left, textvariable=self.title_var, width=40).grid(row=0, column=1, sticky=tk.W, pady=0)
        
        # 封面显示（移动到标题下方）
        ttk.Label(detail_left, text="封面:").grid(row=1, column=0, sticky=tk.NW, pady=0)
        thumbnail_frame = ttk.Frame(detail_left)
        thumbnail_frame.grid(row=1, column=1, sticky=tk.W, pady=0)
        self.thumbnail_label = ttk.Label(thumbnail_frame, text="无封面")
        self.thumbnail_label.pack()
        
        # 星级显示和编辑
        ttk.Label(detail_left, text="星级:").grid(row=2, column=0, sticky=tk.W, pady=0)
        star_frame = ttk.Frame(detail_left)
        star_frame.grid(row=2, column=1, sticky=tk.W, pady=0)
        
        self.star_labels = []
        for i in range(5):
            star_label = ttk.Label(star_frame, text="☆", font=('Arial', 16))
            star_label.pack(side=tk.LEFT)
            star_label.bind("<Button-1>", lambda e, star=i+1: self.set_star_rating(star))
            star_label.bind("<Enter>", lambda e, star=i+1: self.highlight_stars(star))
            star_label.bind("<Leave>", lambda e: self.update_star_display())
            self.star_labels.append(star_label)
        
        ttk.Label(detail_left, text="描述:").grid(row=3, column=0, sticky=tk.NW, pady=0)
        self.desc_text = tk.Text(detail_left, height=3, width=40)
        self.desc_text.grid(row=3, column=1, sticky=tk.W, pady=0)
        
        ttk.Label(detail_left, text="标签:").grid(row=4, column=0, sticky=tk.W, pady=0)
        self.tags_var = tk.StringVar()
        ttk.Entry(detail_left, textvariable=self.tags_var, width=40).grid(row=4, column=1, sticky=tk.W, pady=0)
        
        # 添加更多metadata显示
        ttk.Label(detail_left, text="年份:").grid(row=5, column=0, sticky=tk.W, pady=0)
        self.year_var = tk.StringVar()
        ttk.Entry(detail_left, textvariable=self.year_var, width=40).grid(row=5, column=1, sticky=tk.W, pady=0)
        
        ttk.Label(detail_left, text="类型:").grid(row=6, column=0, sticky=tk.W, pady=0)
        self.genre_var = tk.StringVar()
        ttk.Entry(detail_left, textvariable=self.genre_var, width=40).grid(row=6, column=1, sticky=tk.W, pady=0)
        
        ttk.Label(detail_left, text="文件大小:").grid(row=7, column=0, sticky=tk.W, pady=0)
        self.filesize_var = tk.StringVar()
        ttk.Label(detail_left, textvariable=self.filesize_var).grid(row=7, column=1, sticky=tk.W, pady=0)
        
        ttk.Label(detail_left, text="时长:").grid(row=8, column=0, sticky=tk.W, pady=0)
        self.duration_var = tk.StringVar()
        ttk.Label(detail_left, textvariable=self.duration_var).grid(row=8, column=1, sticky=tk.W, pady=0)
        
        ttk.Label(detail_left, text="分辨率:").grid(row=9, column=0, sticky=tk.W, pady=0)
        self.resolution_var = tk.StringVar()
        ttk.Label(detail_left, textvariable=self.resolution_var).grid(row=9, column=1, sticky=tk.W, pady=0)
        
        ttk.Label(detail_left, text="文件路径:").grid(row=10, column=0, sticky=tk.W, pady=0)
        self.filepath_var = tk.StringVar()
        ttk.Label(detail_left, textvariable=self.filepath_var, wraplength=300).grid(row=10, column=1, sticky=tk.W, pady=0)
        
        # JAVDB信息显示
        ttk.Label(detail_left, text="番号:").grid(row=11, column=0, sticky=tk.W, pady=0)
        self.javdb_code_var = tk.StringVar()
        ttk.Label(detail_left, textvariable=self.javdb_code_var).grid(row=11, column=1, sticky=tk.W, pady=0)
        
        ttk.Label(detail_left, text="JAVDB标题:").grid(row=12, column=0, sticky=tk.W, pady=0)
        self.javdb_title_var = tk.StringVar()
        ttk.Label(detail_left, textvariable=self.javdb_title_var, wraplength=300).grid(row=12, column=1, sticky=tk.W, pady=0)
        
        ttk.Label(detail_left, text="发行日期:").grid(row=13, column=0, sticky=tk.W, pady=0)
        self.release_date_var = tk.StringVar()
        ttk.Label(detail_left, textvariable=self.release_date_var).grid(row=13, column=1, sticky=tk.W, pady=0)
        
        ttk.Label(detail_left, text="JAVDB评分:").grid(row=14, column=0, sticky=tk.W, pady=0)
        self.javdb_score_var = tk.StringVar()
        ttk.Label(detail_left, textvariable=self.javdb_score_var).grid(row=14, column=1, sticky=tk.W, pady=0)
        
        ttk.Label(detail_left, text="JAVDB标签:").grid(row=15, column=0, sticky=tk.W, pady=0)
        self.javdb_tags_var = tk.StringVar()
        ttk.Label(detail_left, textvariable=self.javdb_tags_var, wraplength=300).grid(row=15, column=1, sticky=tk.W, pady=0)
        
        ttk.Label(detail_left, text="演员:").grid(row=16, column=0, sticky=tk.W, pady=0)
        self.actors_var = tk.StringVar()
        # 创建演员链接框架
        self.actors_frame = ttk.Frame(detail_left)
        self.actors_frame.grid(row=16, column=1, sticky=tk.W, pady=0)
        
        ttk.Label(detail_left, text="发行商:").grid(row=17, column=0, sticky=tk.W, pady=0)
        self.studio_var = tk.StringVar()
        ttk.Label(detail_left, textvariable=self.studio_var, wraplength=300).grid(row=17, column=1, sticky=tk.W, pady=0)
        
        ttk.Label(detail_left, text="封面图片:").grid(row=18, column=0, sticky=tk.W, pady=0)
        self.cover_var = tk.StringVar()
        ttk.Label(detail_left, textvariable=self.cover_var, wraplength=300).grid(row=18, column=1, sticky=tk.W, pady=0)
        
        ttk.Label(detail_left, text="下载链接:").grid(row=19, column=0, sticky=tk.W, pady=0)
        # 创建下载链接框架
        self.magnet_frame = ttk.Frame(detail_left)
        self.magnet_frame.grid(row=19, column=1, sticky=tk.W, pady=0)
        
        # 右侧操作按钮
        detail_right = ttk.Frame(detail_content)
        detail_right.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        
        ttk.Button(detail_right, text="播放", command=self.play_video).pack(fill=tk.X, pady=1)
        ttk.Button(detail_right, text="保存修改", command=self.save_video_info).pack(fill=tk.X, pady=1)
        ttk.Button(detail_right, text="设置星级", command=self.set_stars).pack(fill=tk.X, pady=1)
        ttk.Button(detail_right, text="添加标签", command=self.add_tag_to_video).pack(fill=tk.X, pady=1)
        ttk.Button(detail_right, text="获取JAVDB信息", command=self.fetch_current_javdb_info).pack(fill=tk.X, pady=1)
        ttk.Button(detail_right, text="生成封面", command=self.generate_thumbnail).pack(fill=tk.X, pady=1)
        ttk.Button(detail_right, text="删除视频", command=self.delete_video).pack(fill=tk.X, pady=1)
        
        # 状态栏
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 加载数据
        self.load_tags()
        self.load_videos()
        
    def add_folder(self):
        """添加文件夹"""
        # 创建选择对话框
        choice_window = tk.Toplevel(self.root)
        choice_window.title("添加文件夹")
        choice_window.geometry("400x200")
        choice_window.transient(self.root)
        choice_window.grab_set()
        
        # 居中显示
        choice_window.geometry("+%d+%d" % (self.root.winfo_rootx() + 50, self.root.winfo_rooty() + 50))
        
        folder_path = None
        
        def browse_folder():
            nonlocal folder_path
            path = filedialog.askdirectory(title="选择要添加的文件夹")
            if path:
                folder_path = path
                choice_window.destroy()
        
        def manual_input():
            nonlocal folder_path
            # 创建手动输入对话框
            input_window = tk.Toplevel(choice_window)
            input_window.title("手动输入路径")
            input_window.geometry("500x150")
            input_window.transient(choice_window)
            input_window.grab_set()
            
            ttk.Label(input_window, text="请输入文件夹路径（支持SMB协议）:").pack(pady=10)
            ttk.Label(input_window, text="例如: smb://username@192.168.1.100/shared_folder", font=("Arial", 9), foreground="gray").pack()
            
            path_var = tk.StringVar()
            entry = ttk.Entry(input_window, textvariable=path_var, width=60)
            entry.pack(pady=10)
            entry.focus()
            
            def confirm_input():
                nonlocal folder_path
                path = path_var.get().strip()
                if path:
                    folder_path = path
                    input_window.destroy()
                    choice_window.destroy()
                else:
                    messagebox.showwarning("警告", "请输入有效的路径")
            
            def cancel_input():
                input_window.destroy()
            
            button_frame = ttk.Frame(input_window)
            button_frame.pack(pady=10)
            ttk.Button(button_frame, text="确定", command=confirm_input).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="取消", command=cancel_input).pack(side=tk.LEFT, padx=5)
            
            # 绑定回车键
            entry.bind('<Return>', lambda e: confirm_input())
        
        def cancel_choice():
            choice_window.destroy()
        
        # 创建选择界面
        ttk.Label(choice_window, text="请选择添加文件夹的方式:", font=("Arial", 12)).pack(pady=20)
        
        button_frame = ttk.Frame(choice_window)
        button_frame.pack(pady=20)
        
        ttk.Button(button_frame, text="浏览文件夹", command=browse_folder, width=15).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="手动输入路径", command=manual_input, width=15).pack(side=tk.LEFT, padx=10)
        
        ttk.Button(choice_window, text="取消", command=cancel_choice).pack(pady=10)
        
        # 等待窗口关闭
        choice_window.wait_window()
        
        if folder_path:
            try:
                # 检查是否为NAS路径
                folder_type = "nas" if folder_path.startswith(("/Volumes", "//", "smb://")) else "local"
                current_device = self.get_current_device_name()
                
                self.cursor.execute(
                    "INSERT OR REPLACE INTO folders (folder_path, folder_type, device_name) VALUES (?, ?, ?)",
                    (folder_path, folder_type, current_device)
                )
                self.conn.commit()
                
                self.status_var.set(f"已添加文件夹: {folder_path}")
                messagebox.showinfo("成功", f"文件夹已添加: {folder_path}")
            except Exception as e:
                messagebox.showerror("错误", f"添加文件夹失败: {str(e)}")
                
    def scan_media(self):
        """扫描媒体文件 - 优化版本：批量处理，提升性能"""
        # 创建进度窗口
        progress_window = tk.Toplevel(self.root)
        progress_window.title("媒体文件扫描")
        progress_window.geometry("500x300")
        progress_window.transient(self.root)
        progress_window.grab_set()
        
        # 进度条
        progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(progress_window, variable=progress_var, maximum=100)
        progress_bar.pack(fill=tk.X, padx=20, pady=10)
        
        # 状态标签
        status_var = tk.StringVar(value="准备扫描...")
        status_label = ttk.Label(progress_window, textvariable=status_var)
        status_label.pack(pady=5)
        
        # 统计信息
        stats_text = tk.Text(progress_window, height=3, state=tk.DISABLED)
        stats_text.pack(fill=tk.X, padx=20, pady=5)
        
        # 日志区域
        log_frame = ttk.LabelFrame(progress_window, text="扫描日志")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        log_text = tk.Text(log_frame, height=8)
        log_scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=log_text.yview)
        log_text.configure(yscrollcommand=log_scrollbar.set)
        log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 取消按钮
        cancel_var = tk.BooleanVar()
        cancel_button = ttk.Button(progress_window, text="取消", command=lambda: cancel_var.set(True))
        cancel_button.pack(pady=10)
        
        def log_message(message):
            log_text.insert(tk.END, f"{datetime.now().strftime('%H:%M:%S')} - {message}\n")
            log_text.see(tk.END)
            progress_window.update()
        
        def update_stats(scanned=0, added=0, updated=0, skipped=0):
            stats_text.config(state=tk.NORMAL)
            stats_text.delete(1.0, tk.END)
            stats_text.insert(tk.END, f"已扫描: {scanned} | 新增: {added} | 更新: {updated} | 跳过: {skipped}")
            stats_text.config(state=tk.DISABLED)
        
        def scan_thread():
            try:
                # 统计变量
                scanned_count = 0
                added_count = 0
                updated_count = 0
                skipped_count = 0
                
                log_message("开始扫描媒体文件...")
                
                # 获取所有活跃的文件夹
                self.cursor.execute("SELECT folder_path, folder_type FROM folders WHERE is_active = 1")
                folders = self.cursor.fetchall()
                
                if not folders:
                    log_message("没有找到活跃的文件夹")
                    messagebox.showinfo("信息", "没有找到活跃的文件夹，请先添加文件夹")
                    progress_window.destroy()
                    return
                
                log_message(f"找到 {len(folders)} 个活跃文件夹")
                
                # 第一阶段：统计总文件数
                log_message("第一阶段：统计文件数量...")
                video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'}
                total_files = 0
                files_to_process = []
                
                for folder_path, folder_type in folders:
                    if not os.path.exists(folder_path):
                        log_message(f"文件夹不存在，跳过: {folder_path}")
                        continue
                    
                    log_message(f"扫描文件夹: {folder_path}")
                    for root, dirs, files in os.walk(folder_path):
                        for file in files:
                            if any(file.lower().endswith(ext) for ext in video_extensions):
                                file_path = os.path.join(root, file)
                                files_to_process.append((file_path, folder_type))
                                total_files += 1
                
                log_message(f"发现 {total_files} 个视频文件")
                
                if total_files == 0:
                    log_message("没有找到视频文件")
                    self.root.after(0, lambda: messagebox.showinfo("信息", "在活跃文件夹中没有找到视频文件"))
                    self.root.after(0, progress_window.destroy)
                    return
                
                # 第二阶段：批量处理文件
                log_message("第二阶段：处理文件...")
                batch_size = 50  # 每批处理50个文件
                
                for i, (file_path, folder_type) in enumerate(files_to_process):
                    if cancel_var.get():
                        log_message("用户取消操作")
                        break
                    
                    scanned_count += 1
                    progress = (scanned_count / total_files) * 100
                    progress_var.set(progress)
                    status_var.set(f"处理文件 {scanned_count}/{total_files}")
                    
                    try:
                        result = self.add_video_to_db_optimized(file_path, folder_type)
                        if result == 'added':
                            added_count += 1
                        elif result == 'updated':
                            updated_count += 1
                        else:
                            skipped_count += 1
                            
                    except Exception as e:
                        log_message(f"处理文件失败: {os.path.basename(file_path)} - {str(e)}")
                        skipped_count += 1
                    
                    # 更新统计信息
                    update_stats(scanned_count, added_count, updated_count, skipped_count)
                    
                    # 批量提交
                    if scanned_count % batch_size == 0:
                        self.conn.commit()
                        log_message(f"已处理 {scanned_count} 个文件，批量提交数据库")
                        progress_window.update()
                
                # 最终提交
                self.conn.commit()
                
                if not cancel_var.get():
                    progress_var.set(100)
                    status_var.set("扫描完成")
                    log_message(f"\n扫描完成！")
                    log_message(f"总扫描文件: {scanned_count}")
                    log_message(f"新增文件: {added_count}")
                    log_message(f"更新文件: {updated_count}")
                    log_message(f"跳过文件: {skipped_count}")
                    
                    # 先显示完成对话框，避免卡顿
                    self.root.after(0, lambda: messagebox.showinfo("完成", 
                        f"媒体文件扫描完成！\n\n"
                        f"总扫描文件: {scanned_count}\n"
                        f"新增文件: {added_count}\n"
                        f"更新文件: {updated_count}\n"
                        f"跳过文件: {skipped_count}"))
                    
                    # 在对话框显示后异步刷新视频列表
                    self.root.after(100, self.load_videos)
                
                self.root.after(0, progress_window.destroy)
                
            except Exception as e:
                error_msg = str(e)
                log_message(f"扫描失败: {error_msg}")
                self.root.after(0, lambda: messagebox.showerror("错误", f"扫描媒体文件时出错: {error_msg}"))
                self.root.after(0, progress_window.destroy)
                
        # 在新线程中执行扫描
        threading.Thread(target=scan_thread, daemon=True).start()
        
    def add_video_to_db_optimized(self, file_path, folder_type):
        """优化版本：添加视频到数据库，返回操作结果"""
        try:
            # 检查文件是否已存在
            self.cursor.execute("SELECT id FROM videos WHERE file_path = ?", (file_path,))
            existing = self.cursor.fetchone()
            if existing:
                return 'skipped'  # 文件已存在，跳过
                
            # 检查是否有同名文件但路径不同（可能是移动的文件）
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            
            # 查找同名且大小相同但路径不同的文件
            self.cursor.execute(
                "SELECT id, file_path FROM videos WHERE file_name = ? AND file_size = ? AND file_path != ?",
                (file_name, file_size, file_path)
            )
            potential_moved = self.cursor.fetchone()
            
            if potential_moved:
                old_id, old_path = potential_moved
                # 检查旧路径是否还存在
                if not os.path.exists(old_path):
                    # 旧文件不存在，新文件存在，很可能是移动了
                    # 更新路径而不是创建新记录
                    new_source_folder = os.path.dirname(file_path)
                    self.cursor.execute(
                        "UPDATE videos SET file_path = ?, source_folder = ? WHERE id = ?",
                        (file_path, new_source_folder, old_id)
                    )
                    return 'updated'  # 文件路径已更新
                
            # 获取文件信息
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            
            # 获取文件创建时间
            file_created_time = None
            if os.path.exists(file_path):
                try:
                    stat = os.stat(file_path)
                    file_created_time = datetime.fromtimestamp(stat.st_birthtime if hasattr(stat, 'st_birthtime') else stat.st_ctime)
                except:
                    pass
            
            # 获取来源文件夹
            source_folder = os.path.dirname(file_path)
            
            # 计算文件哈希（用于去重）
            file_hash = self.calculate_file_hash(file_path)
            
            # 从文件名解析星级
            stars = self.parse_stars_from_filename(file_name)
            
            # 解析标题（去除星号和扩展名）
            title = self.parse_title_from_filename(file_name)
            
            # 获取视频信息
            duration, resolution = self.get_video_info(file_path)
            
            # NAS路径处理
            nas_path = file_path if folder_type == "nas" else None
            # 统一使用文件路径存在性判断在线状态
            is_nas_online = os.path.exists(file_path) and os.path.isfile(file_path)
            
            self.cursor.execute(
                """INSERT INTO videos 
                   (file_path, file_name, file_size, file_hash, title, stars, nas_path, is_nas_online, duration, resolution, file_created_time, source_folder) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (file_path, file_name, file_size, file_hash, title, stars, nas_path, is_nas_online, duration, resolution, file_created_time, source_folder)
            )
            
            return 'added'  # 新文件已添加
            
        except Exception as e:
            print(f"添加视频失败 {file_path}: {str(e)}")
            return 'error'
    
    def add_video_to_db(self, file_path, folder_type):
        """添加视频到数据库"""
        try:
            # 检查文件是否已存在
            self.cursor.execute("SELECT id FROM videos WHERE file_path = ?", (file_path,))
            existing = self.cursor.fetchone()
            if existing:
                return
                
            # 检查是否有同名文件但路径不同（可能是移动的文件）
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            
            # 查找同名且大小相同但路径不同的文件
            self.cursor.execute(
                "SELECT id, file_path FROM videos WHERE file_name = ? AND file_size = ? AND file_path != ?",
                (file_name, file_size, file_path)
            )
            potential_moved = self.cursor.fetchone()
            
            if potential_moved:
                old_id, old_path = potential_moved
                # 检查旧路径是否还存在
                if not os.path.exists(old_path):
                    # 旧文件不存在，新文件存在，很可能是移动了
                    # 更新路径而不是创建新记录
                    new_source_folder = os.path.dirname(file_path)
                    self.cursor.execute(
                        "UPDATE videos SET file_path = ?, source_folder = ? WHERE id = ?",
                        (file_path, new_source_folder, old_id)
                    )
                    print(f"自动更新移动的文件: {old_path} -> {file_path}")
                    return
                
            # 获取文件信息
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            
            # 获取文件创建时间
            file_created_time = None
            if os.path.exists(file_path):
                try:
                    stat = os.stat(file_path)
                    file_created_time = datetime.fromtimestamp(stat.st_birthtime if hasattr(stat, 'st_birthtime') else stat.st_ctime)
                except:
                    pass
            
            # 获取来源文件夹
            source_folder = os.path.dirname(file_path)
            
            # 计算文件哈希（用于去重）
            file_hash = self.calculate_file_hash(file_path)
            
            # 从文件名解析星级
            stars = self.parse_stars_from_filename(file_name)
            
            # 解析标题（去除星号和扩展名）
            title = self.parse_title_from_filename(file_name)
            
            # 获取视频信息
            duration, resolution = self.get_video_info(file_path)
            
            # NAS路径处理
            nas_path = file_path if folder_type == "nas" else None
            # 统一使用文件路径存在性判断在线状态
            is_nas_online = os.path.exists(file_path) and os.path.isfile(file_path)
            
            self.cursor.execute(
                """INSERT INTO videos 
                   (file_path, file_name, file_size, file_hash, title, stars, nas_path, is_nas_online, duration, resolution, file_created_time, source_folder) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (file_path, file_name, file_size, file_hash, title, stars, nas_path, is_nas_online, duration, resolution, file_created_time, source_folder)
            )
            self.conn.commit()
            
        except Exception as e:
            print(f"添加视频失败 {file_path}: {str(e)}")
            
    def calculate_file_hash(self, file_path):
        """计算文件哈希值"""
        try:
            if not os.path.exists(file_path):
                return None
                
            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                # 只读取文件的前1MB来计算哈希，提高性能
                chunk = f.read(1024 * 1024)
                hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except:
            return None
            
    def parse_stars_from_filename(self, filename):
        """从文件名解析星级"""
        exclamation_count = 0
        for char in filename:
            if char == '!':
                exclamation_count += 1
            else:
                break
                
        # 1个叹号=2星，2个叹号=3星，3个叹号=4星，4个叹号=5星
        if exclamation_count == 1:
            return 2
        elif exclamation_count == 2:
            return 3
        elif exclamation_count == 3:
            return 4
        elif exclamation_count >= 4:
            return 5
        else:
            return 0
            
    def parse_title_from_filename(self, filename):
        """从文件名解析标题"""
        # 去除开头的叹号
        title = filename.lstrip('!')
        # 去除扩展名
        title = os.path.splitext(title)[0]
        return title
        
    def get_current_device_name(self):
        """获取当前设备名称"""
        try:
            import platform
            return platform.node()  # 获取计算机名称
        except:
            return "Unknown Device"
    
    def is_video_online(self, video_id):
        """判断视频是否在线（基于文件路径存在性）"""
        try:
            # 获取视频的文件路径
            self.cursor.execute("SELECT file_path FROM videos WHERE id = ?", (video_id,))
            video_result = self.cursor.fetchone()
            if not video_result or not video_result[0]:
                return False
            
            file_path = video_result[0]
            
            # 直接检查文件是否存在
            return os.path.exists(file_path) and os.path.isfile(file_path)
        except Exception as e:
            print(f"检查视频在线状态时出错: {e}")
            return False
    
    def check_nas_status(self, file_path):
        """检查NAS状态"""
        try:
            return os.path.exists(file_path)
        except:
            return False
            
    def get_video_info(self, file_path):
        """获取视频信息（时长和分辨率）"""
        try:
            if not os.path.exists(file_path):
                return None, None
            
            # 首先尝试使用opencv-python获取视频信息
            try:
                import cv2
                cap = cv2.VideoCapture(file_path)
                
                if cap.isOpened():
                    # 获取帧率和总帧数来计算时长
                    fps = cap.get(cv2.CAP_PROP_FPS)
                    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    
                    duration = None
                    resolution = None
                    
                    if fps > 0 and frame_count > 0:
                        duration = int(frame_count / fps)
                    
                    if width > 0 and height > 0:
                        resolution = f"{width}x{height}"
                    
                    cap.release()
                    return duration, resolution
                else:
                    cap.release()
                    
            except ImportError:
                print("opencv-python未安装，尝试使用ffprobe...")
            except Exception as e:
                print(f"使用opencv获取视频信息失败: {str(e)}")
                
            # 如果opencv不可用，尝试使用ffprobe
            ffprobe_cmd = self.get_ffprobe_command()
            if ffprobe_cmd is None:
                print(f"ffprobe未找到，无法获取视频信息: {file_path}")
                return None, None
                
            # 获取时长
            duration_cmd = [
                ffprobe_cmd, "-v", "quiet", "-show_entries", "format=duration",
                "-of", "csv=p=0", file_path
            ]
            duration_result = subprocess.run(duration_cmd, capture_output=True, text=True)
            duration = None
            if duration_result.returncode == 0 and duration_result.stdout.strip():
                try:
                    duration = int(float(duration_result.stdout.strip()))
                except ValueError:
                    pass
                    
            # 获取分辨率
            resolution_cmd = [
                ffprobe_cmd, "-v", "quiet", "-select_streams", "v:0",
                "-show_entries", "stream=width,height", "-of", "csv=p=0", file_path
            ]
            resolution_result = subprocess.run(resolution_cmd, capture_output=True, text=True)
            resolution = None
            if resolution_result.returncode == 0 and resolution_result.stdout.strip():
                try:
                    width, height = resolution_result.stdout.strip().split(',')
                    resolution = f"{width}x{height}"
                except ValueError:
                    pass
                    
            return duration, resolution
            
        except Exception as e:
            print(f"获取视频信息失败 {file_path}: {str(e)}")
            return None, None
            
    def get_ffmpeg_command(self):
        """获取可用的FFmpeg命令路径"""
        # 首先尝试相对路径（用户通过homebrew安装的情况）
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
            return "ffmpeg"
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
            
        # 如果相对路径失败，尝试常见的绝对路径
        possible_paths = [
            "/opt/homebrew/bin/ffmpeg",
            "/usr/local/bin/ffmpeg",
            "/usr/bin/ffmpeg"
        ]
        
        for path in possible_paths:
            try:
                subprocess.run([path, "-version"], capture_output=True, check=True)
                return path
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
                
        return None
    
    def detect_gpu_acceleration(self):
        """检测可用的GPU加速选项"""
        ffmpeg_cmd = self.get_ffmpeg_command()
        if not ffmpeg_cmd:
            return None
            
        try:
            # 检查FFmpeg支持的硬件加速器
            result = subprocess.run([ffmpeg_cmd, "-hwaccels"], capture_output=True, text=True)
            if result.returncode == 0:
                hwaccels = result.stdout.lower()
                
                # macOS优先级：videotoolbox > opencl
                if "videotoolbox" in hwaccels:
                    return "videotoolbox"
                elif "opencl" in hwaccels:
                    return "opencl"
                    
        except Exception as e:
            print(f"检测GPU加速失败: {e}")
            
        return None
    
    def check_gpu_acceleration_status(self):
        """检查GPU加速状态并显示信息"""
        try:
            self.gpu_acceleration = self.detect_gpu_acceleration()
            if self.gpu_acceleration:
                print(f"✓ GPU加速已启用: {self.gpu_acceleration}")
            else:
                print("⚠ 未检测到GPU加速支持")
        except Exception as e:
            print(f"⚠ GPU加速检测失败: {e}")
            self.gpu_acceleration = None
    
    def get_optimized_ffmpeg_cmd(self, input_path, output_path, seek_time="00:00:10"):
        """获取优化的FFmpeg命令（包含GPU加速）"""
        ffmpeg_cmd = self.get_ffmpeg_command()
        if not ffmpeg_cmd:
            return None
            
        # 检测GPU加速
        hwaccel = self.detect_gpu_acceleration()
        
        cmd = [ffmpeg_cmd]
        
        # 添加硬件加速参数
        if hwaccel == "videotoolbox":
            cmd.extend(["-hwaccel", "videotoolbox"])
        elif hwaccel == "opencl":
            cmd.extend(["-hwaccel", "opencl"])
            
        # 添加输入和处理参数
        cmd.extend([
            "-i", input_path,
            "-ss", seek_time,
            "-vframes", "1"
        ])
        
        # 根据硬件加速选择合适的缩放滤镜
        if hwaccel == "videotoolbox":
            cmd.extend(["-vf", "scale_vt=200:150"])
        elif hwaccel == "opencl":
            cmd.extend(["-vf", "scale_opencl=200:150"])
        else:
            cmd.extend(["-vf", "scale=200:150"])
            
        cmd.extend(["-y", output_path])
        
        return cmd

    def get_ffprobe_command(self):
        """获取可用的FFprobe命令路径"""
        # 首先尝试相对路径（用户通过homebrew安装的情况）
        try:
            subprocess.run(["ffprobe", "-version"], capture_output=True, check=True)
            return "ffprobe"
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
            
        # 如果相对路径失败，尝试常见的绝对路径
        possible_paths = [
            "/opt/homebrew/bin/ffprobe",
            "/usr/local/bin/ffprobe",
            "/usr/bin/ffprobe"
        ]
        
        for path in possible_paths:
            try:
                subprocess.run([path, "-version"], capture_output=True, check=True)
                return path
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
                
        return None

    def generate_thumbnail(self):
        """生成视频封面"""
        if not self.current_video:
            messagebox.showwarning("警告", "请先选择一个视频")
            return
            
        file_path = self.current_video[1]
        is_nas_online = self.current_video[13]
        
        if not is_nas_online:
            messagebox.showwarning("警告", "NAS离线，无法生成封面")
            return
            
        if not os.path.exists(file_path):
            messagebox.showerror("错误", "视频文件不存在")
            return
            
        try:
            # 获取FFmpeg命令
            ffmpeg_cmd = self.get_ffmpeg_command()
            if ffmpeg_cmd is None:
                messagebox.showerror("错误", "需要安装FFmpeg才能生成封面")
                return
                
            # 创建临时文件
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
                temp_path = temp_file.name
                
            # 生成缩略图（使用优化的GPU加速命令）
            cmd = self.get_optimized_ffmpeg_cmd(file_path, temp_path)
            if cmd is None:
                messagebox.showerror("错误", "无法构建FFmpeg命令")
                return
            
            result = subprocess.run(cmd, capture_output=True)
            
            if result.returncode == 0 and os.path.exists(temp_path):
                # 读取图片数据
                with open(temp_path, 'rb') as f:
                    thumbnail_data = f.read()
                    
                # 保存到数据库
                video_id = self.current_video[0]
                self.cursor.execute(
                    "UPDATE videos SET thumbnail_data = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (thumbnail_data, video_id)
                )
                self.conn.commit()
                
                # 显示封面
                self.display_thumbnail(thumbnail_data)
                
                messagebox.showinfo("成功", "封面生成成功")
                
                # 清理临时文件
                os.unlink(temp_path)
                
            else:
                messagebox.showerror("错误", "生成封面失败")
                
        except Exception as e:
            messagebox.showerror("错误", f"生成封面失败: {str(e)}")
            
    def display_thumbnail(self, thumbnail_data):
        """显示封面"""
        try:
            if thumbnail_data:
                # 处理不同类型的thumbnail_data
                if isinstance(thumbnail_data, str):
                    # 如果是base64字符串，先解码
                    try:
                        thumbnail_data = base64.b64decode(thumbnail_data)
                    except Exception:
                        # 如果解码失败，可能是文件路径
                        if os.path.exists(thumbnail_data):
                            with open(thumbnail_data, 'rb') as f:
                                thumbnail_data = f.read()
                        else:
                            # 如果都不是，直接跳过显示缩略图
                            self.thumbnail_label.configure(image="", text="无封面")
                            self.thumbnail_label.image = None
                            return
                elif isinstance(thumbnail_data, memoryview):
                    # 如果是memoryview对象，转换为bytes
                    thumbnail_data = thumbnail_data.tobytes()
                elif not isinstance(thumbnail_data, bytes):
                    # 如果不是bytes类型，尝试转换
                    try:
                        thumbnail_data = bytes(thumbnail_data)
                    except Exception:
                        self.thumbnail_label.configure(image="", text="无封面")
                        self.thumbnail_label.image = None
                        return
                
                # 确保thumbnail_data是bytes类型
                if not isinstance(thumbnail_data, bytes):
                    self.thumbnail_label.configure(image="", text="无封面")
                    self.thumbnail_label.image = None
                    return
                
                # 从二进制数据创建图片
                image = Image.open(io.BytesIO(thumbnail_data))
                # 调整大小 - 兼容不同版本的PIL
                try:
                    # 新版本PIL
                    image = image.resize((150, 112), Image.Resampling.LANCZOS)
                except AttributeError:
                    # 旧版本PIL
                    image = image.resize((150, 112), Image.LANCZOS)
                # 转换为Tkinter可用的格式
                photo = ImageTk.PhotoImage(image)
                # 显示图片
                self.thumbnail_label.configure(image=photo, text="")
                self.thumbnail_label.image = photo  # 保持引用
            else:
                self.thumbnail_label.configure(image="", text="无封面")
                self.thumbnail_label.image = None
        except Exception as e:
            # 静默处理错误，不打印到控制台
            self.thumbnail_label.configure(image="", text="无封面")
            self.thumbnail_label.image = None
            
    def load_videos(self):
        """加载视频列表"""
        # 清空现有数据
        for item in self.video_tree.get_children():
            self.video_tree.delete(item)
            
        try:
            # 构建查询条件
            conditions = []
            params = []
            
            # 检查是否在筛选模式，如果是则添加搜索条件
            if getattr(self, 'is_filtering', False):
                # 标题搜索条件 - 同时搜索videos表的title和javdb_info表的javdb_title
                title_search_text = self.title_search_var.get().strip()
                if title_search_text:
                    conditions.append("(v.title LIKE ? OR v.file_name LIKE ? OR j.javdb_title LIKE ?)")
                    title_search_param = f"%{title_search_text}%"
                    params.extend([title_search_param, title_search_param, title_search_param])
                    
                # 标签搜索条件 - 同时搜索videos表的tags和javdb_info表的标签关联
                tag_search_text = self.tag_search_var.get().strip()
                if tag_search_text:
                    conditions.append("(v.tags LIKE ? OR EXISTS (SELECT 1 FROM javdb_tags jt JOIN tags t ON jt.tag_id = t.id WHERE jt.javdb_info_id = j.id AND t.name LIKE ?))")
                    tag_search_param = f"%{tag_search_text}%"
                    params.extend([tag_search_param, tag_search_param])
                    
                # 演员搜索条件
                actor_search_text = self.actor_search_var.get().strip()
                if actor_search_text:
                    conditions.append("EXISTS (SELECT 1 FROM video_actors va JOIN actors a ON va.actor_id = a.id WHERE va.video_id = v.id AND a.name LIKE ?)")
                    actor_search_param = f"%{actor_search_text}%"
                    params.append(actor_search_param)
                    
                # 星级筛选
                star_filter = self.star_filter.get()
                if star_filter > 0:
                    conditions.append("stars = ?")
                    params.append(star_filter)
                    
                # 标签筛选 - 同时支持videos表的tags和javdb_info表的标签关联
                selected_tags = [self.tags_listbox.get(i) for i in self.tags_listbox.curselection()]
                if selected_tags:
                    tag_conditions = []
                    for tag in selected_tags:
                        tag_conditions.append("(v.tags LIKE ? OR EXISTS (SELECT 1 FROM javdb_tags jt JOIN tags t ON jt.tag_id = t.id WHERE jt.javdb_info_id = j.id AND t.name LIKE ?))")
                        params.extend([f"%{tag}%", f"%{tag}%"])
                    if tag_conditions:
                        conditions.append(f"({' OR '.join(tag_conditions)})")
                        
                # NAS状态筛选 - 基于路径存在性判断
                nas_filter = self.nas_filter.get()
                if nas_filter == "online":
                    # 获取所有视频的路径并检查是否存在
                    self.cursor.execute("SELECT DISTINCT source_folder FROM videos WHERE source_folder IS NOT NULL")
                    all_video_folders = [row[0] for row in self.cursor.fetchall()]
                    
                    online_video_folders = []
                    for folder_path in all_video_folders:
                        if os.path.exists(folder_path) and os.path.isdir(folder_path):
                            online_video_folders.append(folder_path)
                    
                    if online_video_folders:
                        folder_conditions = []
                        for folder_path in online_video_folders:
                            folder_conditions.append("v.source_folder LIKE ?")
                            params.append(f"{folder_path}%")
                        conditions.append(f"({' OR '.join(folder_conditions)})")
                    else:
                        # 如果没有在线文件夹，不显示任何视频
                        conditions.append("1 = 0")
                elif nas_filter == "offline":
                    # 获取所有视频的路径并检查是否不存在
                    self.cursor.execute("SELECT DISTINCT source_folder FROM videos WHERE source_folder IS NOT NULL")
                    all_video_folders = [row[0] for row in self.cursor.fetchall()]
                    
                    offline_video_folders = []
                    for folder_path in all_video_folders:
                        if not (os.path.exists(folder_path) and os.path.isdir(folder_path)):
                            offline_video_folders.append(folder_path)
                    
                    if offline_video_folders:
                        folder_conditions = []
                        for folder_path in offline_video_folders:
                            folder_conditions.append("v.source_folder LIKE ?")
                            params.append(f"{folder_path}%")
                        conditions.append(f"({' OR '.join(folder_conditions)})")
                    else:
                        # 如果没有离线文件夹，不显示任何视频
                        conditions.append("1 = 0")
                    
                # 文件夹来源筛选
                selected_folder_indices = self.folder_listbox.curselection()
                if selected_folder_indices and hasattr(self, 'folder_path_mapping'):
                    selected_folder = self.folder_listbox.get(selected_folder_indices[0])
                    if selected_folder != "全部" and selected_folder in self.folder_path_mapping:
                        folder_path = self.folder_path_mapping[selected_folder]
                        if folder_path:  # 确保folder_path不为None
                            conditions.append("v.source_folder LIKE ?")
                            params.append(f"{folder_path}%")
            
            # 设备和在线筛选逻辑
            current_device = self.get_current_device_name()
            
            # 仅显示在线内容筛选
            if hasattr(self, 'show_online_only') and self.show_online_only.get():
                # 当勾选"仅显示在线"时，只显示路径存在的文件夹中的视频
                # 获取所有激活的文件夹
                self.cursor.execute("SELECT folder_path FROM folders WHERE is_active = 1")
                all_folders = [row[0] for row in self.cursor.fetchall()]
                
                # 检查哪些文件夹路径实际存在
                online_folders = []
                for folder_path in all_folders:
                    if os.path.exists(folder_path) and os.path.isdir(folder_path):
                        online_folders.append(folder_path)
                
                if online_folders:
                    # 构建文件夹条件
                    folder_conditions = []
                    for folder_path in online_folders:
                        folder_conditions.append("v.source_folder LIKE ?")
                        params.append(f"{folder_path}%")
                    conditions.append(f"({' OR '.join(folder_conditions)})")
                else:
                    # 如果没有在线文件夹，不显示任何视频
                    conditions.append("1 = 0")
            else:
                # 不勾选时显示所有激活文件夹中的视频
                conditions.append("""
                    EXISTS (
                        SELECT 1 FROM folders f
                        WHERE f.is_active = 1 
                        AND v.source_folder LIKE f.folder_path || '%'
                    )
                """)
            
            # 构建排序查询
            order_clause = "ORDER BY v.title"  # 默认排序
            if hasattr(self, 'sort_column_name') and self.sort_column_name:
                # 映射显示列名到数据库列名（使用表别名）
                column_mapping = {
                    'title': 'v.title',
                    'actors': 'actors_display',  # 演员列需要特殊处理
                    'stars': 'v.stars',
                    'tags': 'v.tags',
                    'size': 'v.file_size',
                    'status': 'v.is_nas_online',
                    'duration': 'v.duration',
                    'resolution': 'v.resolution',
                    'file_created_time': 'v.file_created_time',
                    'top_folder': 'v.source_folder',
                    'full_path': 'v.source_folder',
                    'year': 'v.year',
                    'javdb_code': 'j.javdb_code',
                    'javdb_title': 'j.javdb_title',
                    'release_date': 'j.release_date',
                    'javdb_rating': 'j.score',
                    'javdb_tags': 'javdb_tags_display'  # JAVDB标签需要特殊处理
                }
                
                # 特殊处理演员排序
                if self.sort_column_name == 'actors':
                    direction = "DESC" if self.sort_reverse else "ASC"
                    # 对于演员排序，使用子查询获取演员信息并排序
                    # 降序时，有演员信息的记录排在前面（NULL值排在后面）
                    # 升序时，无演员信息的记录排在前面（NULL值排在前面）
                    if self.sort_reverse:  # 降序：有演员的在前
                        order_clause = f"""ORDER BY 
                            CASE WHEN (
                                SELECT COUNT(*) FROM video_actors va WHERE va.video_id = v.id
                            ) > 0 THEN 0 ELSE 1 END ASC,
                            (
                                SELECT GROUP_CONCAT(a.name, ', ') 
                                FROM video_actors va 
                                JOIN actors a ON va.actor_id = a.id 
                                WHERE va.video_id = v.id
                            ) {direction}"""
                    else:  # 升序：无演员的在前
                        order_clause = f"""ORDER BY 
                            CASE WHEN (
                                SELECT COUNT(*) FROM video_actors va WHERE va.video_id = v.id
                            ) > 0 THEN 1 ELSE 0 END ASC,
                            (
                                SELECT GROUP_CONCAT(a.name, ', ') 
                                FROM video_actors va 
                                JOIN actors a ON va.actor_id = a.id 
                                WHERE va.video_id = v.id
                            ) {direction}"""
                else:
                    db_column = column_mapping.get(self.sort_column_name, 'v.title')
                    direction = "DESC" if self.sort_reverse else "ASC"
                    order_clause = f"ORDER BY {db_column} {direction}"
            
            # 构建最终查询 - 使用LEFT JOIN连接javdb_info表
            if conditions:
                where_clause = f"WHERE {' AND '.join(conditions)}"
            else:
                where_clause = ""
                
            query = f"SELECT v.* FROM videos v LEFT JOIN javdb_info j ON v.id = j.video_id {where_clause} {order_clause}"
            self.cursor.execute(query, params)
            
            videos = self.cursor.fetchall()
            
            for video in videos:
                # 安全解包，处理可能的字段数量不匹配
                video_data = list(video)
                while len(video_data) < 23:  # 确保有足够的字段
                    video_data.append(None)
                
                video_id, file_path, file_name, file_size, file_hash, title, description, genre, year, rating, stars, tags, nas_path, is_nas_online, created_at, updated_at, thumbnail_data, thumbnail_path, duration, resolution, file_created_time, source_folder, md5_hash = video_data[:23]
                
                # 格式化星级显示（实心/空心星星组合）
                star_display = self.format_stars_display(stars)
                size_display = self.format_file_size(file_size) if file_size else ""
                status_display = "在线" if is_nas_online else "离线"
                # 初始化标签显示，稍后会在获取JAVDB标签后更新
                tags_display = tags if tags else ""
                
                # 格式化年份显示 - 如果数据库中没有年份，尝试从文件名中提取
                year_display = ""
                if year:
                    year_display = str(year)
                else:
                    # 尝试从文件名中提取年份，避免从文件夹路径中提取
                    import re
                    year_pattern = r'\b(19|20)\d{2}\b'  # 使用单词边界确保是完整的年份
                    # 优先从文件名中提取年份
                    year_matches = re.findall(year_pattern, file_name or '')
                    if not year_matches and title:
                        # 如果文件名中没有，再从标题中提取
                        year_matches = re.findall(year_pattern, title)
                    if year_matches:
                        # 取最后一个匹配的年份（通常是最相关的）
                        year_display = year_matches[-1]
                
                # 格式化时长显示
                duration_display = self.format_duration(duration)
                
                # 格式化分辨率显示
                resolution_display = resolution if resolution else ""
                
                # 格式化文件创建时间显示
                file_created_display = ""
                if file_created_time:
                    try:
                        if isinstance(file_created_time, str):
                            # 如果是字符串，尝试解析
                            dt = datetime.fromisoformat(file_created_time.replace('Z', '+00:00'))
                        else:
                            # 如果是datetime对象
                            dt = file_created_time
                        file_created_display = dt.strftime("%Y-%m-%d")
                    except:
                        file_created_display = str(file_created_time)[:10] if file_created_time else ""
                
                # 格式化来源文件夹显示
                top_folder_display = ""
                full_path_display = ""
                if source_folder:
                    # 找到对应的顶层文件夹
                    if hasattr(self, 'folder_path_mapping'):
                        # 先尝试精确匹配
                        for folder_name, folder_path in self.folder_path_mapping.items():
                            if folder_path and source_folder.startswith(folder_path):
                                top_folder_display = folder_name
                                break
                    
                    # 如果没有找到匹配的文件夹，显示source_folder的最顶层目录
                    if not top_folder_display and source_folder:
                        # 提取路径的顶层部分作为显示
                        path_parts = source_folder.strip('/').split('/')
                        if len(path_parts) >= 3:  # /Users/username/folder
                            top_folder_display = path_parts[-1] if len(path_parts) > 3 else path_parts[2]
                        else:
                            top_folder_display = os.path.basename(source_folder)
                    
                    # 完整路径显示
                    full_path_display = source_folder
                    
                    # 获取设备名称显示
                    device_display = "Unknown"
                    if source_folder:
                        # 查找匹配的文件夹记录
                        self.cursor.execute("""
                            SELECT folder_type, device_name FROM folders 
                            WHERE ? LIKE folder_path || '%' 
                            ORDER BY LENGTH(folder_path) DESC 
                            LIMIT 1
                        """, (source_folder,))
                        folder_info = self.cursor.fetchone()
                        
                        if folder_info:
                            folder_type, device_name = folder_info
                            
                            if folder_type == "nas":
                                # NAS设备：显示IP或域名
                                if source_folder.startswith("smb://"):
                                    # 从smb://username@192.168.1.100/folder格式中提取IP
                                    import re
                                    ip_match = re.search(r'@([0-9.]+)/', source_folder)
                                    if ip_match:
                                        device_display = ip_match.group(1)
                                    else:
                                        # 尝试提取域名
                                        domain_match = re.search(r'smb://(?:[^@]+@)?([^/]+)/', source_folder)
                                        if domain_match:
                                            device_display = domain_match.group(1)
                                        else:
                                            device_display = "NAS"
                                elif source_folder.startswith("/Volumes/"):
                                    # macOS挂载的网络驱动器，尝试从路径提取名称
                                    volume_name = source_folder.split('/')[2] if len(source_folder.split('/')) > 2 else "NAS"
                                    device_display = volume_name
                                else:
                                    device_display = "NAS"
                            else:
                                # 本地设备：显示设备名称
                                device_display = device_name if device_name and device_name != "Unknown" else "Unknown"
                
                # 查询JAVDB信息
                javdb_code = ""
                javdb_title = ""
                release_date = ""
                javdb_rating = ""
                javdb_tags = ""
                actors_display = ""
                
                try:
                    # 查询JAVDB信息
                    self.cursor.execute("""
                        SELECT javdb_code, javdb_title, release_date, score 
                        FROM javdb_info 
                        WHERE video_id = ?
                    """, (video_id,))
                    javdb_result = self.cursor.fetchone()
                    
                    if javdb_result:
                        javdb_code, javdb_title, release_date, javdb_rating = javdb_result
                        javdb_code = javdb_code or ""
                        javdb_title = javdb_title or ""
                        release_date = release_date or ""
                        javdb_rating = javdb_rating or ""
                        
                        # 查询JAVDB标签
                        self.cursor.execute("""
                            SELECT GROUP_CONCAT(jt.tag_name, ', ') 
                            FROM javdb_info ji
                            JOIN javdb_info_tags jit ON ji.id = jit.javdb_info_id
                            JOIN javdb_tags jt ON jit.tag_id = jt.id
                            WHERE ji.video_id = ?
                        """, (video_id,))
                        javdb_tags_result = self.cursor.fetchone()
                        javdb_tags = javdb_tags_result[0] if javdb_tags_result and javdb_tags_result[0] else ""
                    
                    # 查询演员信息
                    self.cursor.execute("""
                        SELECT GROUP_CONCAT(a.name, ', ') 
                        FROM video_actors va
                        JOIN actors a ON va.actor_id = a.id
                        WHERE va.video_id = ?
                    """, (video_id,))
                    actors_result = self.cursor.fetchone()
                    actors_display = actors_result[0] if actors_result and actors_result[0] else ""
                    
                except Exception as e:
                    print(f"查询JAVDB信息失败: {e}")
                
                # 合并标签显示：优先显示JAVDB标签，然后显示自动标签
                combined_tags = []
                if javdb_tags:
                    combined_tags.append(javdb_tags)
                if tags:
                    combined_tags.append(tags)
                tags_display = ", ".join(combined_tags)
                
                # 根据列配置的位置顺序插入数据
                sorted_columns = sorted(self.column_config.items(), key=lambda x: x[1]['position'])
                values = []
                
                # 构建数据字典
                # 如果有JAVDB标题，优先使用JAVDB标题，否则使用原标题或文件名
                display_title = javdb_title if javdb_title else (title or file_name)
                data_dict = {
                    'title': display_title,
                    'stars': star_display,
                    'tags': tags_display,
                    'size': size_display,
                    'actors': actors_display,
                    'status': status_display,
                    'device': device_display,
                    'duration': duration_display,
                    'resolution': resolution_display,
                    'file_created_time': file_created_display,
                    'top_folder': top_folder_display,
                    'full_path': full_path_display,
                    'year': year_display,
                    'javdb_code': javdb_code,
                    'javdb_title': javdb_title,
                    'release_date': release_date,
                    'javdb_rating': javdb_rating,
                    'javdb_tags': javdb_tags
                }
                
                # 按照配置的位置顺序添加值
                for col_name, _ in sorted_columns:
                    values.append(data_dict.get(col_name, ''))
                
                self.video_tree.insert('', 'end', values=values, tags=(video_id,))
                
        except Exception as e:
            messagebox.showerror("错误", f"加载视频列表失败: {str(e)}")
            
    def format_stars_display(self, stars):
        """格式化星级显示为实心/空心星星组合"""
        if stars is None:
            stars = 0
        stars = max(0, min(5, int(stars)))  # 确保在0-5范围内
        
        filled_stars = "★" * stars  # 实心星星
        empty_stars = "☆" * (5 - stars)  # 空心星星
        return filled_stars + empty_stars
    
    def format_file_size(self, size_bytes):
        """格式化文件大小"""
        try:
            # 确保size_bytes是数值类型
            if isinstance(size_bytes, bytes):
                size_bytes = int.from_bytes(size_bytes, byteorder='big')
            elif isinstance(size_bytes, str):
                size_bytes = int(size_bytes)
            elif size_bytes is None:
                return "0B"
            
            size_bytes = int(size_bytes)
            
            if size_bytes == 0:
                return "0B"
            size_names = ["B", "KB", "MB", "GB", "TB"]
            i = 0
            while size_bytes >= 1024 and i < len(size_names) - 1:
                size_bytes /= 1024.0
                i += 1
            return f"{size_bytes:.1f}{size_names[i]}"
        except (ValueError, TypeError, OverflowError):
            return "0B"
    
    def format_duration(self, duration):
        """格式化时长显示"""
        if not duration:
            return ""
        
        try:
            # 确保duration是整数类型
            if isinstance(duration, bytes):
                duration = int.from_bytes(duration, byteorder='big')
            elif isinstance(duration, str):
                duration = int(duration)
            elif not isinstance(duration, int):
                duration = int(duration)
            
            hours = duration // 3600
            minutes = (duration % 3600) // 60
            seconds = duration % 60
            
            if hours > 0:
                return f"{hours}:{minutes:02d}:{seconds:02d}"
            else:
                return f"{minutes}:{seconds:02d}"
        except (ValueError, TypeError, OverflowError):
            return ""
        
    def load_tags(self):
        """加载标签列表"""
        self.tags_listbox.delete(0, tk.END)
        try:
            self.cursor.execute("SELECT tag_name FROM tags ORDER BY tag_name")
            tags = self.cursor.fetchall()
            for tag in tags:
                self.tags_listbox.insert(tk.END, tag[0])
        except Exception as e:
            print(f"加载标签失败: {str(e)}")
            
    def load_folder_sources(self):
        """加载文件夹来源列表"""
        try:
            # 从folders表获取文件夹信息，包括设备名称和类型
            self.cursor.execute("""
                SELECT DISTINCT folder_path, folder_type, device_name 
                FROM folders 
                WHERE is_active = 1 
                ORDER BY folder_path
            """)
            folders = self.cursor.fetchall()
            
            self.folder_listbox.delete(0, tk.END)
            self.folder_listbox.insert(0, "全部")
            
            # 存储文件夹路径映射，用于筛选
            self.folder_path_mapping = {"全部": None}
            
            for folder_path, folder_type, device_name in folders:
                folder_name = os.path.basename(folder_path)
                
                # 根据文件夹类型生成显示名称
                if folder_type == "nas":
                    # NAS文件夹：提取IP地址
                    if folder_path.startswith("smb://"):
                        # 从smb://username@192.168.1.100/folder格式中提取IP
                        import re
                        ip_match = re.search(r'@([0-9.]+)/', folder_path)
                        if ip_match:
                            nas_ip = ip_match.group(1)
                            display_name = f"{nas_ip}@{folder_name}"
                        else:
                            display_name = f"NAS@{folder_name}"
                    elif folder_path.startswith("/Volumes/"):
                        # macOS挂载的网络驱动器
                        display_name = f"NAS@{folder_name}"
                    else:
                        display_name = f"NAS@{folder_name}"
                else:
                    # 本地文件夹：显示设备名称
                    device_display = device_name if device_name and device_name.strip() else "本地"
                    display_name = f"{device_display}@{folder_name}"
                
                self.folder_listbox.insert(tk.END, display_name)
                self.folder_path_mapping[display_name] = folder_path
                
        except Exception as e:
            print(f"加载文件夹来源失败: {str(e)}")
            
    def on_header_double_click(self, event):
        """处理表头双击事件，用于排序"""
        region = self.video_tree.identify_region(event.x, event.y)
        if region == "heading":
            column = self.video_tree.identify_column(event.x)
            if column:
                col_index = int(column.replace('#', '')) - 1
                columns = list(self.video_tree['columns'])
                if 0 <= col_index < len(columns):
                    col_name = columns[col_index]
                    self.sort_column(col_name)
    
    def handle_single_click(self, event):
        """统一处理单击事件"""
        region = self.video_tree.identify_region(event.x, event.y)
        
        # 处理表头点击（拖拽开始）
        if region == "heading":
            self.on_drag_start(event)
            return
            
        # 处理数据行点击
        self.on_tree_click(event)
    
    def handle_double_click(self, event):
        """统一处理双击事件"""
        region = self.video_tree.identify_region(event.x, event.y)
        
        # 表头双击排序
        if region == "heading":
            self.on_header_double_click(event)
            return
            
        # 数据行双击播放
        self.play_video(event)
        return "break"  # 阻止事件继续传播
    
    def on_tree_click(self, event):
        """处理Treeview点击事件，特别是星级列的点击"""
        # 如果正在拖拽表头，不处理数据行点击事件
        if hasattr(self, 'drag_data') and self.drag_data.get('dragging', False):
            return
            
        item = self.video_tree.identify('item', event.x, event.y)
        column = self.video_tree.identify('column', event.x, event.y)
        
        if item and column:
            # 获取列名
            col_index = int(column.replace('#', '')) - 1
            columns = list(self.video_tree['columns'])
            if 0 <= col_index < len(columns):
                col_name = columns[col_index]
                
                # 如果点击的是星级列
                if col_name == 'stars':
                    video_id = self.video_tree.item(item, 'tags')[0]
                    self.on_star_click(event, item, video_id)
    
    def on_star_click(self, event, item, video_id):
        """处理星级点击事件"""
        # 获取点击位置在星级列中的相对位置
        bbox = self.video_tree.bbox(item, 'stars')
        if bbox:
            x, y, width, height = bbox
            click_x = event.x - x
            
            # 计算点击的是第几颗星（每颗星大约占列宽的1/5）
            star_width = width / 5
            clicked_star = min(5, max(1, int(click_x / star_width) + 1))
            
            # 更新数据库中的星级
            try:
                self.cursor.execute(
                    "UPDATE videos SET stars = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (clicked_star, video_id)
                )
                self.conn.commit()
                
                # 刷新显示
                self.load_videos()
                
                # 如果当前选中的是这个视频，更新详情面板
                if self.current_video and self.current_video[0] == video_id:
                    self.load_video_details(video_id)
                    
            except Exception as e:
                messagebox.showerror("错误", f"设置星级失败: {str(e)}")
    
    def set_star_rating(self, rating):
        """设置星级评分"""
        if not self.current_video:
            return
            
        try:
            video_id = self.current_video[0]
            self.cursor.execute(
                "UPDATE videos SET stars = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (rating, video_id)
            )
            self.conn.commit()
            
            # 更新当前视频数据
            self.load_video_details(video_id)
            
            # 刷新视频列表
            self.load_videos()
            
        except Exception as e:
            messagebox.showerror("错误", f"设置星级失败: {str(e)}")
    
    def highlight_stars(self, rating):
        """高亮显示星级"""
        for i, label in enumerate(self.star_labels):
            if i < rating:
                label.config(text="★", foreground="gold")
            else:
                label.config(text="☆", foreground="black")
    
    def update_star_display(self):
        """更新星级显示"""
        if self.current_video:
            stars = self.current_video[10] or 0  # stars字段在第10个位置
            for i, label in enumerate(self.star_labels):
                if i < stars:
                    label.config(text="★", foreground="gold")
                else:
                    label.config(text="☆", foreground="black")
    
    def on_video_select(self, event):
        """视频选择事件"""
        selection = self.video_tree.selection()
        if selection:
            item = self.video_tree.item(selection[0])
            video_id = item['tags'][0]
            self.load_video_details(video_id)
            
    def load_video_details(self, video_id):
        """加载视频详情"""
        try:
            self.cursor.execute("SELECT * FROM videos WHERE id = ?", (video_id,))
            video = self.cursor.fetchone()
            
            if video:
                self.current_video = video
                # 安全解包，处理可能的字段数量不匹配
                video_data = list(video)
                while len(video_data) < 23:  # 确保有足够的字段
                    video_data.append(None)
                
                video_id, file_path, file_name, file_size, file_hash, title, description, genre, year, rating, stars, tags, nas_path, is_nas_online, created_at, updated_at, thumbnail_data, thumbnail_path, duration, resolution, file_created_time, source_folder, md5_hash = video_data[:23]
                
                # 基本信息
                self.title_var.set(title or file_name)
                self.desc_text.delete(1.0, tk.END)
                if description:
                    self.desc_text.insert(1.0, description)
                self.tags_var.set(tags or "")
                
                # 更多metadata
                self.year_var.set(str(year) if year else "")
                self.genre_var.set(genre or "")
                
                # 文件信息
                self.filesize_var.set(self.format_file_size(file_size) if file_size else "未知")
                self.duration_var.set(self.format_duration(duration) if duration else "未知")
                self.resolution_var.set(resolution or "未知")
                self.filepath_var.set(file_path or "")
                
                # 更新星级显示
                self.update_star_display()
                
                # 显示封面
                self.display_thumbnail(thumbnail_data)
                
                # 加载JAVDB信息
                self.load_javdb_details(video_id)
                
        except Exception as e:
            messagebox.showerror("错误", f"加载视频详情失败: {str(e)}")
            
    def load_javdb_details(self, video_id):
        """加载JAVDB详情信息"""
        try:
            # 查询JAVDB信息
            self.cursor.execute("""
                SELECT javdb_code, javdb_title, release_date, score, studio, cover_url, local_cover_path, cover_image_data, magnet_links
                FROM javdb_info 
                WHERE video_id = ?
            """, (video_id,))
            javdb_result = self.cursor.fetchone()
            
            if javdb_result:
                javdb_code, javdb_title, release_date, javdb_score, studio, cover_url, local_cover_path, cover_image_data, magnet_links = javdb_result
                self.javdb_code_var.set(javdb_code or "")
                self.javdb_title_var.set(javdb_title or "")
                self.release_date_var.set(release_date or "")
                self.javdb_score_var.set(str(javdb_score) if javdb_score else "")
                self.studio_var.set(studio or "")
                
                # 显示封面信息（优先显示JAVDB数据库中的图片）
                if cover_image_data:
                    self.cover_var.set("JAVDB数据库封面")
                    # 显示数据库中的图片
                    self.display_thumbnail(cover_image_data)
                elif cover_url:
                    self.cover_var.set(f"JAVDB在线封面: {cover_url}")
                    # 可以考虑下载并显示在线图片，这里暂时不显示
                    self.display_thumbnail(None)
                else:
                    self.cover_var.set("无封面")
                    self.display_thumbnail(None)
                
                # 显示下载链接
                self.display_magnet_links(magnet_links)
                
                # 从发行日期自动提取年份
                if release_date and not self.year_var.get():
                    try:
                        # 尝试从发行日期中提取年份（支持多种格式）
                        import re
                        year_match = re.search(r'(\d{4})', release_date)
                        if year_match:
                            year = year_match.group(1)
                            self.year_var.set(year)
                    except Exception as e:
                        print(f"提取年份失败: {e}")
                
                # 查询JAVDB标签
                self.cursor.execute("""
                    SELECT GROUP_CONCAT(jt.tag_name, ', ') 
                    FROM javdb_info ji
                    JOIN javdb_info_tags jit ON ji.id = jit.javdb_info_id
                    JOIN javdb_tags jt ON jit.tag_id = jt.id
                    WHERE ji.video_id = ?
                """, (video_id,))
                javdb_tags_result = self.cursor.fetchone()
                javdb_tags = javdb_tags_result[0] if javdb_tags_result and javdb_tags_result[0] else ""
                self.javdb_tags_var.set(javdb_tags)
                
                # 从JAVDB标签中提取类型信息设置到genre字段
                if javdb_tags and not self.genre_var.get().strip():
                    # 将JAVDB标签设置为类型（如果当前类型为空）
                    self.genre_var.set(javdb_tags)
                
                # 合并JAVDB标签和数据库中的原有标签（JAVDB标签优先显示在前面）
                # 注意：这里要从数据库获取原始标签，而不是从界面获取，避免重复累积
                self.cursor.execute("SELECT tags FROM videos WHERE id = ?", (video_id,))
                db_result = self.cursor.fetchone()
                db_tags = db_result[0] if db_result and db_result[0] else ""
                
                if javdb_tags and db_tags:
                    # 分割标签，去重并合并
                    db_tag_list = [tag.strip() for tag in db_tags.split(',') if tag.strip()]
                    javdb_tag_list = [tag.strip() for tag in javdb_tags.split(',') if tag.strip()]
                    # JAVDB标签在前，数据库标签在后，去重
                    all_tags = javdb_tag_list.copy()
                    for tag in db_tag_list:
                        if tag not in all_tags:
                            all_tags.append(tag)
                    merged_tags = ', '.join(all_tags)
                    self.tags_var.set(merged_tags)
                elif javdb_tags and not db_tags:
                    # 只有JAVDB标签时，直接设置
                    self.tags_var.set(javdb_tags)
                elif not javdb_tags and db_tags:
                    # 只有数据库标签时，直接设置
                    self.tags_var.set(db_tags)
                else:
                    # 都没有标签时，清空
                    self.tags_var.set("")
            else:
                # 清空JAVDB信息
                self.javdb_code_var.set("")
                self.javdb_title_var.set("")
                self.release_date_var.set("")
                self.javdb_score_var.set("")
                self.javdb_tags_var.set("")
                self.studio_var.set("")
                self.cover_var.set("")
                self.clear_magnet_links()
            
            # 查询演员信息并显示为超链接
            self.cursor.execute("""
                SELECT a.name, a.profile_url
                FROM video_actors va
                JOIN actors a ON va.actor_id = a.id
                WHERE va.video_id = ?
            """, (video_id,))
            actors_results = self.cursor.fetchall()
            self.display_actor_links(actors_results)
            
        except Exception as e:
            print(f"加载JAVDB详情失败: {e}")
            # 清空所有JAVDB信息
            self.javdb_code_var.set("")
            self.javdb_title_var.set("")
            self.release_date_var.set("")
            self.javdb_score_var.set("")
            self.javdb_tags_var.set("")
            self.studio_var.set("")
            self.cover_var.set("")
            self.actors_var.set("")
            self.clear_actor_links()
            self.clear_magnet_links()
    
    def display_actor_links(self, actors_results):
        """显示演员超链接"""
        # 清空现有的演员链接
        self.clear_actor_links()
        
        if not actors_results:
            return
        
        for i, (actor_name, profile_url) in enumerate(actors_results):
            if i > 0:
                # 添加逗号分隔符
                comma_label = ttk.Label(self.actors_frame, text=", ")
                comma_label.pack(side=tk.LEFT)
            
            # 创建演员链接
            actor_link = ttk.Label(self.actors_frame, text=actor_name, 
                                 foreground="blue", cursor="hand2")
            actor_link.pack(side=tk.LEFT)
            
            # 绑定点击事件 - 弹出演员详情页面
            actor_link.bind("<Button-1>", lambda e, name=actor_name: self.open_actor_detail(name))
    
    def display_magnet_links(self, magnet_links_json):
        """显示下载链接"""
        # 清空现有的下载链接
        self.clear_magnet_links()
        
        if not magnet_links_json:
            return
        
        try:
            import json
            magnet_links = json.loads(magnet_links_json) if isinstance(magnet_links_json, str) else magnet_links_json
            
            if not magnet_links:
                return
            
            # 创建主容器
            main_frame = ttk.Frame(self.magnet_frame)
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # 创建可编辑的文本框，每行一个链接
            magnet_text = "\n".join(magnet_links)
            
            # 创建文本框容器
            text_frame = ttk.Frame(main_frame)
            text_frame.pack(fill=tk.BOTH, expand=True)
            
            # 创建文本框
            text_widget = tk.Text(text_frame, height=min(len(magnet_links), 5), 
                                wrap=tk.NONE, font=('Arial', 9), 
                                selectbackground='#0078d4', selectforeground='white')
            text_widget.insert(tk.END, magnet_text)
            text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            
            # 添加滚动条
            scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text_widget.yview)
            text_widget.configure(yscrollcommand=scrollbar.set)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            # 添加操作按钮
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill=tk.X, pady=(2, 0))
            
            def copy_all_links():
                """复制所有链接"""
                try:
                    all_text = text_widget.get(1.0, tk.END).strip()
                    self.root.clipboard_clear()
                    self.root.clipboard_append(all_text)
                    self.root.update()
                    messagebox.showinfo("成功", "所有下载链接已复制到剪贴板")
                except Exception as e:
                    messagebox.showerror("错误", f"复制失败: {str(e)}")
            
            def copy_selected():
                """复制选中的链接"""
                try:
                    selected_text = text_widget.selection_get()
                    if selected_text:
                        self.root.clipboard_clear()
                        self.root.clipboard_append(selected_text)
                        self.root.update()
                        messagebox.showinfo("成功", "选中的链接已复制到剪贴板")
                    else:
                        messagebox.showwarning("提示", "请先选择要复制的内容")
                except tk.TclError:
                    messagebox.showwarning("提示", "请先选择要复制的内容")
                except Exception as e:
                    messagebox.showerror("错误", f"复制失败: {str(e)}")
            
            # 添加按钮
            ttk.Button(button_frame, text="复制全部", command=copy_all_links, width=10).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(button_frame, text="复制选中", command=copy_selected, width=10).pack(side=tk.LEFT)
                
        except Exception as e:
            print(f"显示下载链接失败: {e}")
    
    def clear_actor_links(self):
        """清空演员链接"""
        for widget in self.actors_frame.winfo_children():
            widget.destroy()
    
    def clear_magnet_links(self):
        """清空下载链接"""
        for widget in self.magnet_frame.winfo_children():
            widget.destroy()
    
    def open_actor_url(self, url):
        """打开演员页面"""
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception as e:
            messagebox.showerror("错误", f"无法打开链接: {str(e)}")
    
    def copy_magnet_link(self, magnet_link):
        """复制磁力链接到剪贴板"""
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(magnet_link)
            self.root.update()  # 确保剪贴板更新
            messagebox.showinfo("成功", "磁力链接已复制到剪贴板")
        except Exception as e:
            messagebox.showerror("错误", f"复制链接失败: {str(e)}")
            
    def play_video(self, event=None):
        """播放视频（跨平台）"""
        # 如果是双击事件，从事件中获取视频信息
        if event:
            # 检查是否在表头区域
            region = self.video_tree.identify_region(event.x, event.y)
            if region == "heading":
                return  # 表头双击不播放视频
            
            # 如果正在拖拽，不处理双击事件
            if hasattr(self, 'drag_data') and self.drag_data.get('dragging', False):
                return
            
            item = self.video_tree.identify('item', event.x, event.y)
            if item:
                # 先选中该项目
                self.video_tree.selection_set(item)
                # 获取视频ID
                try:
                    video_id = self.video_tree.item(item, 'tags')[0]
                except (IndexError, KeyError):
                    messagebox.showwarning("警告", "无法获取视频信息")
                    return
                
                # 从数据库获取视频信息
                try:
                    self.cursor.execute("SELECT file_path FROM videos WHERE id = ?", (video_id,))
                    result = self.cursor.fetchone()
                    if not result:
                        messagebox.showerror("错误", "找不到视频信息")
                        return
                    file_path = result[0]
                    is_nas_online = self.is_video_online(video_id)
                except Exception as e:
                    messagebox.showerror("错误", f"获取视频信息失败: {str(e)}")
                    return
            else:
                messagebox.showwarning("警告", "请先选择一个视频")
                return
        else:
            # 如果不是双击事件，使用当前选中的视频
            if not self.current_video:
                messagebox.showwarning("警告", "请先选择一个视频")
                return
            file_path = self.current_video[1]
            is_nas_online = self.current_video[13]
        
        if not is_nas_online:
            messagebox.showwarning("警告", "NAS离线，无法播放视频")
            return
            
        if not os.path.exists(file_path):
            messagebox.showerror("错误", "视频文件不存在")
            return
            
        try:
            # 跨平台播放
            system = platform.system()
            if system == "Darwin":  # macOS
                subprocess.run(["open", file_path])
            elif system == "Windows":
                os.startfile(file_path)
            elif system == "Linux":
                subprocess.run(["xdg-open", file_path])
            else:
                messagebox.showerror("错误", f"不支持的操作系统: {system}")
        except Exception as e:
            messagebox.showerror("错误", f"播放视频失败: {str(e)}")
            
    def save_video_info(self):
        """保存视频信息"""
        if not self.current_video:
            messagebox.showwarning("警告", "请先选择一个视频")
            return
            
        try:
            video_id = self.current_video[0]
            title = self.title_var.get()
            description = self.desc_text.get(1.0, tk.END).strip()
            tags = self.tags_var.get()
            year = self.year_var.get()
            genre = self.genre_var.get()
            
            # 处理年份字段
            year_value = None
            if year.strip():
                try:
                    year_value = int(year)
                except ValueError:
                    pass
            
            self.cursor.execute(
                "UPDATE videos SET title = ?, description = ?, tags = ?, year = ?, genre = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (title, description, tags, year_value, genre, video_id)
            )
            self.conn.commit()
            
            messagebox.showinfo("成功", "视频信息已保存")
            self.load_videos()
            
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {str(e)}")
            
    def set_stars(self):
        """设置星级"""
        if not self.current_video:
            messagebox.showwarning("警告", "请先选择一个视频")
            return
            
        stars = simpledialog.askinteger("设置星级", "请输入星级 (0-5):", minvalue=0, maxvalue=5)
        if stars is not None:
            try:
                video_id = self.current_video[0]
                self.cursor.execute(
                    "UPDATE videos SET stars = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (stars, video_id)
                )
                self.conn.commit()
                
                messagebox.showinfo("成功", f"星级已设置为 {stars} 星")
                self.load_videos()
                
            except Exception as e:
                messagebox.showerror("错误", f"设置星级失败: {str(e)}")
                
    def add_tag_to_video(self):
        """为视频添加标签"""
        if not self.current_video:
            messagebox.showwarning("警告", "请先选择一个视频")
            return
            
        tag = simpledialog.askstring("添加标签", "请输入标签名称:")
        if tag:
            try:
                # 添加到标签表
                self.cursor.execute("INSERT OR IGNORE INTO tags (tag_name) VALUES (?)", (tag,))
                
                # 添加到视频标签
                current_tags = self.tags_var.get()
                if current_tags:
                    new_tags = f"{current_tags}, {tag}"
                else:
                    new_tags = tag
                    
                self.tags_var.set(new_tags)
                self.save_video_info()
                self.load_tags()
                
            except Exception as e:
                messagebox.showerror("错误", f"添加标签失败: {str(e)}")
                
    def delete_video(self):
        """删除视频记录"""
        if not self.current_video:
            messagebox.showwarning("警告", "请先选择一个视频")
            return
            
        if messagebox.askyesno("确认删除", "确定要删除这个视频记录吗？\n(不会删除实际文件)"):
            try:
                video_id = self.current_video[0]
                self.cursor.execute("DELETE FROM videos WHERE id = ?", (video_id,))
                self.conn.commit()
                
                messagebox.showinfo("成功", "视频记录已删除")
                self.load_videos()
                self.current_video = None
                
            except Exception as e:
                messagebox.showerror("错误", f"删除失败: {str(e)}")
                
    def import_nfo(self):
        """导入NFO文件"""
        nfo_files = filedialog.askopenfilenames(
            title="选择NFO文件",
            filetypes=[("NFO files", "*.nfo"), ("All files", "*.*")]
        )
        
        if nfo_files:
            imported_count = 0
            for nfo_file in nfo_files:
                if self.parse_nfo_file(nfo_file):
                    imported_count += 1
                    
            # 先显示完成对话框，避免卡顿
            messagebox.showinfo("导入完成", f"成功导入 {imported_count} 个NFO文件")
            
            # 在对话框显示后异步刷新视频列表
            self.root.after(100, self.load_videos)
            
    def parse_nfo_file(self, nfo_file):
        """解析NFO文件"""
        try:
            tree = ET.parse(nfo_file)
            root = tree.getroot()
            
            # 查找对应的视频文件
            nfo_dir = os.path.dirname(nfo_file)
            nfo_name = os.path.splitext(os.path.basename(nfo_file))[0]
            
            # 查找同名视频文件
            video_extensions = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v']
            video_file = None
            
            for ext in video_extensions:
                potential_file = os.path.join(nfo_dir, nfo_name + ext)
                if os.path.exists(potential_file):
                    video_file = potential_file
                    break
                    
            if not video_file:
                return False
                
            # 解析NFO内容
            title = root.findtext('title', '')
            plot = root.findtext('plot', '')
            genre = root.findtext('genre', '')
            year = root.findtext('year', '')
            rating = root.findtext('rating', '')
            
            # 更新数据库
            self.cursor.execute(
                """UPDATE videos SET 
                   title = COALESCE(NULLIF(?, ''), title),
                   description = COALESCE(NULLIF(?, ''), description),
                   genre = COALESCE(NULLIF(?, ''), genre),
                   year = CASE WHEN ? != '' THEN CAST(? AS INTEGER) ELSE year END,
                   rating = CASE WHEN ? != '' THEN CAST(? AS REAL) ELSE rating END,
                   updated_at = CURRENT_TIMESTAMP
                   WHERE file_path = ?""",
                (title, plot, genre, year, year, rating, rating, video_file)
            )
            
            self.conn.commit()
            return True
            
        except Exception as e:
            print(f"解析NFO文件失败 {nfo_file}: {str(e)}")
            return False
            
    def batch_calculate_md5(self):
        """批量计算MD5 - 优化版本：批量处理，详细进度显示"""
        try:
            # 询问用户选择
            choice = messagebox.askyesnocancel(
                "批量计算MD5",
                "选择计算范围：\n\n" +
                "是(Yes) - 仅计算缺失MD5的文件\n" +
                "否(No) - 重新计算所有文件的MD5\n" +
                "取消(Cancel) - 取消操作"
            )
            
            if choice is None:  # 取消
                return
                
            if choice:  # 仅计算缺失的
                self.cursor.execute("SELECT id, file_path, file_name FROM videos WHERE md5_hash IS NULL OR md5_hash = ''")
                operation_type = "计算缺失MD5"
            else:  # 重新计算所有
                self.cursor.execute("SELECT id, file_path, file_name FROM videos")
                operation_type = "重新计算所有MD5"
                
            videos = self.cursor.fetchall()
            
            if not videos:
                messagebox.showinfo("信息", "没有需要计算MD5的文件")
                return
                
            # 创建进度窗口
            progress_window = tk.Toplevel(self.root)
            progress_window.title("批量计算MD5")
            progress_window.geometry("600x400")
            progress_window.transient(self.root)
            progress_window.grab_set()
            
            # 进度条
            progress_var = tk.DoubleVar()
            progress_bar = ttk.Progressbar(progress_window, variable=progress_var, maximum=100)
            progress_bar.pack(fill=tk.X, padx=20, pady=10)
            
            # 状态标签
            status_var = tk.StringVar(value=f"准备{operation_type}...")
            status_label = ttk.Label(progress_window, textvariable=status_var)
            status_label.pack(pady=5)
            
            # 统计信息
            stats_text = tk.Text(progress_window, height=3, state=tk.DISABLED)
            stats_text.pack(fill=tk.X, padx=20, pady=5)
            
            # 日志区域
            log_frame = ttk.LabelFrame(progress_window, text="计算日志")
            log_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
            
            log_text = tk.Text(log_frame, height=10)
            log_scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=log_text.yview)
            log_text.configure(yscrollcommand=log_scrollbar.set)
            log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            # 取消按钮
            cancel_var = tk.BooleanVar()
            cancel_button = ttk.Button(progress_window, text="取消", command=lambda: cancel_var.set(True))
            cancel_button.pack(pady=10)
            
            def log_message(message):
                log_text.insert(tk.END, f"{datetime.now().strftime('%H:%M:%S')} - {message}\n")
                log_text.see(tk.END)
                progress_window.update()
            
            def update_stats(processed=0, calculated=0, failed=0, skipped=0):
                stats_text.config(state=tk.NORMAL)
                stats_text.delete(1.0, tk.END)
                stats_text.insert(tk.END, f"已处理: {processed} | 计算成功: {calculated} | 失败: {failed} | 跳过: {skipped}")
                stats_text.config(state=tk.DISABLED)
            
            def calculate_thread():
                try:
                    # 统计变量
                    processed_count = 0
                    calculated_count = 0
                    failed_count = 0
                    skipped_count = 0
                    
                    total_files = len(videos)
                    log_message(f"开始{operation_type}，共 {total_files} 个文件")
                    
                    batch_size = 20  # 每批处理20个文件
                    start_time = time.time()
                    
                    for i, (video_id, file_path, file_name) in enumerate(videos):
                        if cancel_var.get():
                            log_message("用户取消操作")
                            break
                            
                        processed_count += 1
                        progress = (processed_count / total_files) * 100
                        progress_var.set(progress)
                        status_var.set(f"处理文件 {processed_count}/{total_files}: {file_name}")
                        
                        try:
                            if not os.path.exists(file_path):
                                log_message(f"文件不存在，跳过: {file_name}")
                                skipped_count += 1
                                continue
                            
                            # 计算MD5哈希
                            file_hash = self.calculate_file_hash(file_path)
                            if file_hash:
                                # 使用md5_hash字段而不是file_hash
                                self.cursor.execute(
                                    "UPDATE videos SET md5_hash = ? WHERE id = ?",
                                    (file_hash, video_id)
                                )
                                calculated_count += 1
                                
                                if calculated_count % 10 == 0:  # 每10个文件记录一次日志
                                    log_message(f"已计算 {calculated_count} 个文件的MD5")
                            else:
                                log_message(f"MD5计算失败: {file_name}")
                                failed_count += 1
                                
                        except Exception as e:
                            log_message(f"处理文件失败: {file_name} - {str(e)}")
                            failed_count += 1
                        
                        # 更新统计信息
                        update_stats(processed_count, calculated_count, failed_count, skipped_count)
                        
                        # 批量提交
                        if processed_count % batch_size == 0:
                            self.conn.commit()
                            elapsed_time = time.time() - start_time
                            avg_time = elapsed_time / processed_count
                            remaining_time = avg_time * (total_files - processed_count)
                            log_message(f"已处理 {processed_count} 个文件，预计剩余时间: {remaining_time:.1f}秒")
                            progress_window.update()
                    
                    # 最终提交
                    self.conn.commit()
                    
                    if not cancel_var.get():
                        progress_var.set(100)
                        status_var.set("计算完成")
                        
                        total_time = time.time() - start_time
                        log_message(f"\n{operation_type}完成！")
                        log_message(f"总处理文件: {processed_count}")
                        log_message(f"计算成功: {calculated_count}")
                        log_message(f"失败: {failed_count}")
                        log_message(f"跳过: {skipped_count}")
                        log_message(f"总耗时: {total_time:.1f}秒")
                        
                        # 先显示完成对话框，避免卡顿
                        messagebox.showinfo("完成", 
                            f"{operation_type}完成！\n\n"
                            f"总处理文件: {processed_count}\n"
                            f"计算成功: {calculated_count}\n"
                            f"失败: {failed_count}\n"
                            f"跳过: {skipped_count}\n"
                            f"总耗时: {total_time:.1f}秒")
                        
                        # 在对话框显示后异步刷新视频列表
                        self.root.after(100, self.load_videos)
                    
                    progress_window.destroy()
                    
                except Exception as e:
                    error_msg = str(e)
                    log_message(f"批量计算MD5失败: {error_msg}")
                    self.root.after(0, lambda: messagebox.showerror("错误", f"批量计算MD5时出错: {error_msg}"))
                    self.root.after(0, progress_window.close)
                    
            # 在新线程中执行计算
            threading.Thread(target=calculate_thread, daemon=True).start()
            
        except Exception as e:
            messagebox.showerror("错误", f"批量计算MD5失败: {str(e)}")
            
    def smart_remove_duplicates(self):
        """智能去重 - 优化版本：基于MD5哈希的高效去重"""
        try:
            # 第一阶段：统计重复文件
            self.cursor.execute("""
                SELECT md5_hash, COUNT(*) as count
                FROM videos 
                WHERE md5_hash IS NOT NULL AND md5_hash != ''
                GROUP BY md5_hash 
                HAVING count > 1
            """)
            
            duplicate_hashes = self.cursor.fetchall()
            
            if not duplicate_hashes:
                messagebox.showinfo("信息", "没有发现重复文件")
                return
            
            total_groups = len(duplicate_hashes)
            total_files = sum(count for _, count in duplicate_hashes)
            
            # 创建去重选择窗口
            dup_window = tk.Toplevel(self.root)
            dup_window.title("智能去重 - 优化版本")
            dup_window.geometry("700x600")
            dup_window.transient(self.root)
            dup_window.grab_set()
            
            # 主框架
            main_frame = ttk.Frame(dup_window)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # 统计信息
            stats_frame = ttk.LabelFrame(main_frame, text="重复文件统计")
            stats_frame.pack(fill=tk.X, pady=(0, 10))
            
            ttk.Label(stats_frame, text=f"发现 {total_groups} 组重复文件，共 {total_files} 个文件").pack(pady=5)
            ttk.Label(stats_frame, text=f"预计可释放 {total_files - total_groups} 个重复记录").pack(pady=5)
            
            # 策略选择
            strategy_frame = ttk.LabelFrame(main_frame, text="保留策略")
            strategy_frame.pack(fill=tk.X, pady=(0, 10))
            
            strategy_var = tk.StringVar(value="oldest")
            ttk.Radiobutton(strategy_frame, text="保留最老的文件", variable=strategy_var, value="oldest").pack(anchor=tk.W, padx=10, pady=2)
            ttk.Radiobutton(strategy_frame, text="保留最新的文件", variable=strategy_var, value="newest").pack(anchor=tk.W, padx=10, pady=2)
            ttk.Radiobutton(strategy_frame, text="基于位置优先级保留", variable=strategy_var, value="location").pack(anchor=tk.W, padx=10, pady=2)
            ttk.Radiobutton(strategy_frame, text="保留文件大小最大的", variable=strategy_var, value="largest").pack(anchor=tk.W, padx=10, pady=2)
            
            # 位置优先级设置
            priority_frame = ttk.LabelFrame(main_frame, text="位置优先级（从高到低）")
            priority_frame.pack(fill=tk.X, pady=(0, 10))
            
            priority_text = tk.Text(priority_frame, height=3, width=50)
            priority_text.pack(padx=5, pady=5)
            priority_text.insert(tk.END, "本地硬盘\nNAS\n移动硬盘")
            
            # 进度显示区域
            progress_frame = ttk.LabelFrame(main_frame, text="处理进度")
            progress_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
            
            progress_var = tk.DoubleVar()
            progress_bar = ttk.Progressbar(progress_frame, variable=progress_var, maximum=100)
            progress_bar.pack(fill=tk.X, padx=5, pady=5)
            
            status_label = ttk.Label(progress_frame, text="准备开始去重...")
            status_label.pack(pady=5)
            
            # 统计信息显示
            stats_text = tk.Text(progress_frame, height=8, width=70)
            stats_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            # 日志滚动条
            scrollbar = ttk.Scrollbar(progress_frame, orient=tk.VERTICAL, command=stats_text.yview)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            stats_text.config(yscrollcommand=scrollbar.set)
            
            # 按钮框架
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill=tk.X)
            
            cancel_flag = threading.Event()
            
            def log_message(message):
                """添加日志消息"""
                timestamp = datetime.now().strftime("%H:%M:%S")
                stats_text.insert(tk.END, f"[{timestamp}] {message}\n")
                stats_text.see(tk.END)
                dup_window.update_idletasks()
            
            def execute_dedup_thread():
                """在后台线程执行去重"""
                try:
                    strategy = strategy_var.get()
                    removed_count = 0
                    processed_groups = 0
                    
                    log_message(f"开始智能去重，策略：{strategy}")
                    log_message(f"总共需要处理 {total_groups} 组重复文件")
                    
                    # 获取详细的重复文件信息
                    self.cursor.execute("""
                        SELECT md5_hash, COUNT(*) as count, 
                               GROUP_CONCAT(id) as ids, 
                               GROUP_CONCAT(file_path) as paths,
                               GROUP_CONCAT(file_name) as file_names,
                               GROUP_CONCAT(file_created_time) as created_times,
                               GROUP_CONCAT(source_folder) as source_folders,
                               GROUP_CONCAT(file_size) as file_sizes
                        FROM videos 
                        WHERE md5_hash IS NOT NULL AND md5_hash != ''
                        GROUP BY md5_hash 
                        HAVING count > 1
                        ORDER BY count DESC
                    """)
                    
                    duplicates = self.cursor.fetchall()
                    
                    for dup_data in duplicates:
                        if cancel_flag.is_set():
                            log_message("用户取消了去重操作")
                            break
                            
                        md5_hash, count, ids, paths, file_names, created_times, source_folders, file_sizes = dup_data
                        
                        id_list = ids.split(',')
                        path_list = paths.split(',')
                        name_list = file_names.split(',') if file_names else []
                        time_list = created_times.split(',') if created_times else []
                        folder_list = source_folders.split(',') if source_folders else []
                        size_list = file_sizes.split(',') if file_sizes else []
                        
                        keep_index = 0  # 默认保留第一个
                        
                        # 根据策略选择保留的文件
                        if strategy == "oldest" and time_list:
                            oldest_time = None
                            for i, time_str in enumerate(time_list):
                                if time_str and time_str != 'None':
                                    try:
                                        file_time = datetime.fromisoformat(time_str.replace(' ', 'T'))
                                        if oldest_time is None or file_time < oldest_time:
                                            oldest_time = file_time
                                            keep_index = i
                                    except:
                                        pass
                                        
                        elif strategy == "newest" and time_list:
                            newest_time = None
                            for i, time_str in enumerate(time_list):
                                if time_str and time_str != 'None':
                                    try:
                                        file_time = datetime.fromisoformat(time_str.replace(' ', 'T'))
                                        if newest_time is None or file_time > newest_time:
                                            newest_time = file_time
                                            keep_index = i
                                    except:
                                        pass
                                        
                        elif strategy == "location":
                            priorities = priority_text.get(1.0, tk.END).strip().split('\n')
                            best_priority = len(priorities)
                            
                            for i, folder in enumerate(folder_list):
                                for j, priority_location in enumerate(priorities):
                                    if priority_location.lower() in folder.lower():
                                        if j < best_priority:
                                            best_priority = j
                                            keep_index = i
                                        break
                                        
                        elif strategy == "largest" and size_list:
                            max_size = 0
                            for i, size_str in enumerate(size_list):
                                try:
                                    size = int(size_str) if size_str and size_str != 'None' else 0
                                    if size > max_size:
                                        max_size = size
                                        keep_index = i
                                except:
                                    pass
                        
                        # 记录保留的文件
                        keep_file = name_list[keep_index] if keep_index < len(name_list) else f"文件{keep_index+1}"
                        log_message(f"处理重复组 {processed_groups+1}/{total_groups}: 保留 {keep_file}")
                        
                        # 删除除了保留文件外的其他文件
                        group_removed = 0
                        for i, video_id in enumerate(id_list):
                            if i != keep_index:
                                self.cursor.execute("DELETE FROM videos WHERE id = ?", (video_id,))
                                group_removed += 1
                                removed_count += 1
                        
                        log_message(f"  删除了 {group_removed} 个重复记录")
                        
                        processed_groups += 1
                        progress = (processed_groups / total_groups) * 100
                        progress_var.set(progress)
                        status_label.config(text=f"已处理 {processed_groups}/{total_groups} 组重复文件")
                        
                        # 批量提交（每10组提交一次）
                        if processed_groups % 10 == 0:
                            self.conn.commit()
                            log_message(f"已提交数据库更改（批次 {processed_groups//10}）")
                    
                    # 最终提交
                    self.conn.commit()
                    
                    if not cancel_flag.is_set():
                        log_message(f"去重完成！共删除 {removed_count} 个重复文件记录")
                        status_label.config(text=f"去重完成：删除了 {removed_count} 个重复记录")
                        progress_var.set(100)
                        
                        # 刷新视频列表
                        self.root.after(0, self.load_videos)
                        
                        # 显示完成消息
                        self.root.after(0, lambda: messagebox.showinfo("完成", f"智能去重完成！\n删除了 {removed_count} 个重复文件记录"))
                    
                except Exception as e:
                    error_msg = f"去重过程中发生错误: {str(e)}"
                    log_message(error_msg)
                    self.root.after(0, lambda: messagebox.showerror("错误", error_msg))
                finally:
                    # 重新启用按钮
                    execute_btn.config(state=tk.NORMAL)
                    cancel_btn.config(text="关闭")
            
            def start_dedup():
                """开始去重"""
                execute_btn.config(state=tk.DISABLED)
                cancel_btn.config(text="取消")
                cancel_flag.clear()
                
                # 在后台线程中执行
                thread = threading.Thread(target=execute_dedup_thread, daemon=True)
                thread.start()
            
            def cancel_dedup():
                """取消去重"""
                if cancel_btn.cget("text") == "取消":
                    cancel_flag.set()
                    log_message("正在取消去重操作...")
                else:
                    dup_window.destroy()
            
            execute_btn = ttk.Button(button_frame, text="开始去重", command=start_dedup)
            execute_btn.pack(side=tk.LEFT, padx=(0, 10))
            
            cancel_btn = ttk.Button(button_frame, text="关闭", command=cancel_dedup)
            cancel_btn.pack(side=tk.LEFT)
            
            log_message("智能去重工具已准备就绪")
            log_message(f"检测到 {total_groups} 组重复文件，共 {total_files} 个文件")
            
        except Exception as e:
            messagebox.showerror("错误", f"智能去重初始化失败: {str(e)}")
            
    def file_move_manager(self):
        """文件移动管理"""
        move_window = tk.Toplevel(self.root)
        move_window.title("文件移动管理")
        move_window.geometry("800x600")
        move_window.transient(self.root)
        move_window.grab_set()
        
        # 创建界面
        main_frame = ttk.Frame(move_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 源文件夹选择
        source_frame = ttk.LabelFrame(main_frame, text="源文件夹")
        source_frame.pack(fill=tk.X, pady=(0, 10))
        
        source_var = tk.StringVar()
        ttk.Entry(source_frame, textvariable=source_var, width=60).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(source_frame, text="选择", command=lambda: source_var.set(filedialog.askdirectory())).pack(side=tk.LEFT, padx=5)
        
        # 目标文件夹选择
        target_frame = ttk.LabelFrame(main_frame, text="目标文件夹")
        target_frame.pack(fill=tk.X, pady=(0, 10))
        
        target_var = tk.StringVar()
        ttk.Entry(target_frame, textvariable=target_var, width=60).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(target_frame, text="选择", command=lambda: target_var.set(filedialog.askdirectory())).pack(side=tk.LEFT, padx=5)
        
        # 移动选项
        options_frame = ttk.LabelFrame(main_frame, text="移动选项")
        options_frame.pack(fill=tk.X, pady=(0, 10))
        
        copy_mode = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text="复制模式（保留原文件）", variable=copy_mode).pack(anchor=tk.W, padx=5, pady=2)
        
        update_db = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="更新数据库路径", variable=update_db).pack(anchor=tk.W, padx=5, pady=2)
        
        # 文件列表
        list_frame = ttk.LabelFrame(main_frame, text="待移动文件")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        file_tree = ttk.Treeview(list_frame, columns=('size', 'status'), show='tree headings')
        file_tree.heading('#0', text='文件名')
        file_tree.heading('size', text='大小')
        file_tree.heading('status', text='状态')
        file_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 按钮
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        def scan_files():
            source_path = source_var.get()
            if not source_path or not os.path.exists(source_path):
                messagebox.showerror("错误", "请选择有效的源文件夹")
                return
            
            # 创建进度窗口
            progress_window = ProgressWindow(move_window, "扫描文件")
            
            def scan_thread():
                try:
                    # 清空列表
                    for item in file_tree.get_children():
                        file_tree.delete(item)
                    
                    # 第一阶段：统计文件数量
                    progress_window.update_progress(0, 100, "正在统计文件数量...")
                    video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'}
                    
                    all_files = []
                    for root, dirs, files in os.walk(source_path):
                        for file in files:
                            if any(file.lower().endswith(ext) for ext in video_extensions):
                                file_path = os.path.join(root, file)
                                all_files.append((file_path, file))
                    
                    total_files = len(all_files)
                    if total_files == 0:
                        progress_window.close()
                        messagebox.showinfo("信息", "在指定文件夹中没有找到视频文件")
                        return
                    
                    progress_window.update_progress(10, 100, f"找到 {total_files} 个视频文件，开始扫描...")
                    
                    # 第二阶段：处理文件
                    processed = 0
                    for file_path, file_name in all_files:
                        if progress_window.is_cancelled():
                            break
                        
                        try:
                            file_size = os.path.getsize(file_path)
                            size_str = self.format_file_size(file_size)
                            
                            # 检查是否在数据库中
                            self.cursor.execute("SELECT id FROM videos WHERE file_path = ?", (file_path,))
                            status = "数据库中" if self.cursor.fetchone() else "未入库"
                            
                            file_tree.insert('', 'end', text=file_name, values=(size_str, status), tags=(file_path,))
                            
                        except Exception as e:
                            print(f"处理文件失败 {file_path}: {str(e)}")
                        
                        processed += 1
                        progress = 10 + (processed / total_files) * 90
                        progress_window.update_progress(progress, 100, f"已扫描 {processed}/{total_files} 个文件")
                    
                    if not progress_window.is_cancelled():
                        progress_window.update_progress(100, 100, f"扫描完成！找到 {processed} 个视频文件")
                        self.root.after(0, lambda: messagebox.showinfo("完成", f"扫描完成！找到 {processed} 个视频文件"))
                    
                except Exception as e:
                    error_msg = str(e)
                    self.root.after(0, lambda: messagebox.showerror("错误", f"扫描文件时发生错误: {error_msg}"))
                finally:
                    progress_window.close()
            
            # 在后台线程中执行扫描
            thread = threading.Thread(target=scan_thread, daemon=True)
            thread.start()
                        
        def execute_move():
            source_path = source_var.get()
            target_path = target_var.get()
            
            if not source_path or not target_path:
                messagebox.showerror("错误", "请选择源文件夹和目标文件夹")
                return
            
            # 获取要移动的文件列表
            files_to_move = []
            for item in file_tree.get_children():
                old_path = file_tree.item(item)['tags'][0]
                files_to_move.append(old_path)
            
            if not files_to_move:
                messagebox.showwarning("警告", "没有选择要移动的文件")
                return
            
            # 创建进度窗口
            progress_window = ProgressWindow(move_window, "移动文件")
            
            def move_thread():
                try:
                    if not os.path.exists(target_path):
                        os.makedirs(target_path)
                    
                    total_files = len(files_to_move)
                    moved_count = 0
                    failed_count = 0
                    skipped_count = 0
                    
                    progress_window.update_progress(0, 100, f"准备移动 {total_files} 个文件...")
                    
                    for i, old_path in enumerate(files_to_move):
                        if progress_window.is_cancelled():
                            break
                        
                        file_name = os.path.basename(old_path)
                        new_path = os.path.join(target_path, file_name)
                        
                        try:
                            # 检查目标文件是否已存在
                            if os.path.exists(new_path):
                                if os.path.samefile(old_path, new_path):
                                    skipped_count += 1
                                    continue
                                else:
                                    # 生成新的文件名
                                    base, ext = os.path.splitext(file_name)
                                    counter = 1
                                    while os.path.exists(new_path):
                                        new_name = f"{base}_{counter}{ext}"
                                        new_path = os.path.join(target_path, new_name)
                                        counter += 1
                            
                            # 执行移动或复制
                            if copy_mode.get():
                                shutil.copy2(old_path, new_path)
                                operation = "复制"
                            else:
                                shutil.move(old_path, new_path)
                                operation = "移动"
                            
                            # 更新数据库
                            if update_db.get():
                                self.cursor.execute(
                                    "UPDATE videos SET file_path = ?, source_folder = ? WHERE file_path = ?",
                                    (new_path, target_path, old_path)
                                )
                            
                            moved_count += 1
                            
                        except Exception as e:
                            print(f"{operation}文件失败 {old_path}: {str(e)}")
                            failed_count += 1
                        
                        # 更新进度
                        progress = ((i + 1) / total_files) * 100
                        progress_window.update_progress(
                            progress, 100, 
                            f"已处理 {i + 1}/{total_files} 个文件 (成功: {moved_count}, 失败: {failed_count}, 跳过: {skipped_count})"
                        )
                        
                        # 批量提交数据库（每10个文件提交一次）
                        if (i + 1) % 10 == 0 and update_db.get():
                            self.conn.commit()
                    
                    # 最终提交
                    if update_db.get():
                        self.conn.commit()
                    
                    if not progress_window.is_cancelled():
                        operation_name = "复制" if copy_mode.get() else "移动"
                        result_msg = f"{operation_name}完成！\n成功: {moved_count} 个\n失败: {failed_count} 个\n跳过: {skipped_count} 个"
                        progress_window.update_progress(100, 100, result_msg)
                        self.root.after(0, lambda: messagebox.showinfo("完成", result_msg))
                        
                        # 刷新视频列表
                        if update_db.get():
                            self.root.after(0, self.load_videos)
                    
                except Exception as e:
                    error_msg = str(e)
                    self.root.after(0, lambda: messagebox.showerror("错误", f"文件移动过程中发生错误: {error_msg}"))
                finally:
                    progress_window.close()
            
            # 在后台线程中执行移动
            thread = threading.Thread(target=move_thread, daemon=True)
            thread.start()
            
        ttk.Button(button_frame, text="扫描文件", command=scan_files).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="执行移动", command=execute_move).pack(side=tk.LEFT)
        
    def reimport_incomplete_metadata(self):
        """重新导入元数据不完整的视频 - 优化版本"""
        try:
            # 第一阶段：统计元数据不完整的视频
            self.cursor.execute("""
                SELECT COUNT(*) FROM videos 
                WHERE (duration IS NULL OR duration = 0) 
                   OR (resolution IS NULL OR resolution = '') 
                   OR (file_created_time IS NULL)
                   OR (source_folder IS NULL or source_folder = '')
            """)
            
            total_count = self.cursor.fetchone()[0]
            
            if total_count == 0:
                messagebox.showinfo("信息", "所有视频的元数据都已完整，无需重新导入")
                return
            
            # 确认对话框
            if not messagebox.askyesno("确认", f"发现 {total_count} 个元数据不完整的视频\n\n是否重新导入？这可能需要一些时间。"):
                return
            
            # 创建进度窗口
            progress_window = ProgressWindow(self.root, "重新导入元数据")
            
            def reimport_thread():
                try:
                    # 获取详细的不完整视频列表
                    self.cursor.execute("""
                        SELECT id, file_path, file_name FROM videos 
                        WHERE (duration IS NULL OR duration = 0) 
                           OR (resolution IS NULL OR resolution = '') 
                           OR (file_created_time IS NULL)
                           OR (source_folder IS NULL or source_folder = '')
                        ORDER BY id
                    """)
                    incomplete_videos = self.cursor.fetchall()
                    
                    progress_window.update_progress(0, 100, f"开始处理 {len(incomplete_videos)} 个视频...")
                    
                    updated_count = 0
                    failed_count = 0
                    skipped_count = 0
                    
                    for i, (video_id, file_path, file_name) in enumerate(incomplete_videos):
                        if progress_window.is_cancelled():
                            break
                        
                        try:
                            # 检查文件是否存在
                            if not os.path.exists(file_path):
                                print(f"文件不存在，跳过: {file_path}")
                                skipped_count += 1
                                continue
                            
                            # 获取视频信息
                            duration, resolution = self.get_video_info(file_path)
                            if duration is None and resolution is None:
                                print(f"无法获取视频信息: {file_path}")
                            
                            # 获取文件创建时间
                            file_created_time = None
                            try:
                                stat = os.stat(file_path)
                                file_created_time = datetime.fromtimestamp(
                                    stat.st_birthtime if hasattr(stat, 'st_birthtime') else stat.st_ctime
                                )
                            except Exception as e:
                                print(f"无法获取文件创建时间 {file_path}: {str(e)}")
                            
                            # 获取来源文件夹
                            source_folder = os.path.dirname(file_path)
                            
                            # 检查当前数据库中的值
                            self.cursor.execute("SELECT duration, resolution, file_created_time, source_folder FROM videos WHERE id = ?", (video_id,))
                            current_data = self.cursor.fetchone()
                            current_duration, current_resolution, current_file_created_time, current_source_folder = current_data
                            
                            # 更新数据库
                            update_fields = []
                            update_values = []
                            
                            # 记录更新的字段
                            updated_fields = []
                            
                            # 只有当当前值为空且新值不为空时才更新
                            if (current_duration is None or current_duration == 0) and duration is not None:
                                update_fields.append("duration = ?")
                                update_values.append(duration)
                                updated_fields.append(f"时长: {duration}秒")
                            
                            if (current_resolution is None or current_resolution == '') and resolution is not None:
                                update_fields.append("resolution = ?")
                                update_values.append(resolution)
                                updated_fields.append(f"分辨率: {resolution}")
                            
                            if current_file_created_time is None and file_created_time is not None:
                                update_fields.append("file_created_time = ?")
                                update_values.append(file_created_time)
                                updated_fields.append(f"创建时间: {file_created_time}")
                            
                            if (current_source_folder is None or current_source_folder == '') and source_folder:
                                update_fields.append("source_folder = ?")
                                update_values.append(source_folder)
                                updated_fields.append(f"来源文件夹: {source_folder}")
                            
                            if update_fields:
                                update_values.append(video_id)
                                sql = f"UPDATE videos SET {', '.join(update_fields)} WHERE id = ?"
                                self.cursor.execute(sql, update_values)
                                updated_count += 1
                                print(f"更新成功 {file_name}: {', '.join(updated_fields)}")
                            else:
                                skipped_count += 1
                                print(f"无需更新 {file_name}: 所有元数据已完整或无法获取新数据")
                            
                        except Exception as e:
                            print(f"重新导入视频元数据失败 {file_path}: {str(e)}")
                            failed_count += 1
                        
                        # 更新进度
                        progress = ((i + 1) / len(incomplete_videos)) * 100
                        progress_window.update_progress(
                            progress, 100,
                            f"已处理 {i + 1}/{len(incomplete_videos)} 个视频 (成功: {updated_count}, 失败: {failed_count}, 跳过: {skipped_count})"
                        )
                        
                        # 批量提交（每20个视频提交一次）
                        if (i + 1) % 20 == 0:
                            self.conn.commit()
                    
                    # 最终提交
                    self.conn.commit()
                    
                    if not progress_window.is_cancelled():
                        result_msg = f"重新导入完成！\n成功: {updated_count} 个\n失败: {failed_count} 个\n跳过: {skipped_count} 个"
                        progress_window.update_progress(100, 100, result_msg)
                        
                        # 先显示完成对话框，避免卡顿
                        self.root.after(0, lambda: messagebox.showinfo("完成", result_msg))
                        
                        # 在对话框显示后异步刷新视频列表
                        self.root.after(100, self.load_videos)
                    
                except Exception as e:
                    error_msg = f"重新导入元数据过程中发生错误: {str(e)}"
                    self.root.after(0, lambda: messagebox.showerror("错误", error_msg))
                finally:
                    progress_window.close()
            
            # 在后台线程中执行
            thread = threading.Thread(target=reimport_thread, daemon=True)
            thread.start()
            
        except Exception as e:
            messagebox.showerror("错误", f"重新导入元数据初始化失败: {str(e)}")
    
    def update_single_file_metadata(self, video_id):
        """更新单个文件的元数据"""
        try:
            # 获取视频信息
            self.cursor.execute("SELECT file_path, file_name FROM videos WHERE id = ?", (video_id,))
            result = self.cursor.fetchone()
            
            if not result:
                messagebox.showerror("错误", "未找到视频记录")
                return
                
            file_path, file_name = result
            
            # 检查文件是否存在
            if not os.path.exists(file_path):
                messagebox.showerror("错误", f"文件不存在: {file_path}")
                return
            
            # 确认对话框
            if not messagebox.askyesno("确认", f"是否更新文件 '{file_name}' 的元数据？\n\n这将重新获取文件的时长、分辨率、创建时间等信息。"):
                return
            
            def update_thread():
                try:
                    # 获取文件信息
                    file_size = os.path.getsize(file_path)
                    
                    # 获取文件创建时间
                    file_created_time = None
                    try:
                        stat = os.stat(file_path)
                        file_created_time = datetime.fromtimestamp(stat.st_birthtime if hasattr(stat, 'st_birthtime') else stat.st_ctime)
                    except:
                        pass
                    
                    # 获取来源文件夹
                    source_folder = os.path.dirname(file_path)
                    
                    # 获取视频信息（时长和分辨率）
                    duration, resolution = self.get_video_info(file_path)
                    
                    # 准备更新字段
                    update_fields = []
                    update_values = []
                    
                    # 更新文件大小
                    update_fields.append("file_size = ?")
                    update_values.append(file_size)
                    
                    # 更新时长
                    if duration is not None:
                        update_fields.append("duration = ?")
                        update_values.append(duration)
                    
                    # 更新分辨率
                    if resolution:
                        update_fields.append("resolution = ?")
                        update_values.append(resolution)
                    
                    # 更新文件创建时间
                    if file_created_time:
                        update_fields.append("file_created_time = ?")
                        update_values.append(file_created_time)
                    
                    # 更新来源文件夹
                    if source_folder:
                        update_fields.append("source_folder = ?")
                        update_values.append(source_folder)
                    
                    # 更新修改时间
                    update_fields.append("updated_at = CURRENT_TIMESTAMP")
                    
                    if update_fields:
                        update_values.append(video_id)
                        sql = f"UPDATE videos SET {', '.join(update_fields)} WHERE id = ?"
                        self.cursor.execute(sql, update_values)
                        self.conn.commit()
                        
                        # 在主线程中显示成功消息并刷新界面
                        self.root.after(0, lambda: messagebox.showinfo("完成", f"文件 '{file_name}' 的元数据已成功更新"))
                        self.root.after(100, self.load_videos)
                        
                        # 如果当前选中的是这个视频，刷新详情显示
                        if hasattr(self, 'current_video') and self.current_video and self.current_video[0] == video_id:
                            self.root.after(200, lambda: self.load_video_details(video_id))
                    else:
                        self.root.after(0, lambda: messagebox.showinfo("信息", "没有需要更新的元数据"))
                        
                except Exception as e:
                    error_msg = f"更新元数据失败: {str(e)}"
                    self.root.after(0, lambda: messagebox.showerror("错误", error_msg))
            
            # 在后台线程中执行更新
            thread = threading.Thread(target=update_thread, daemon=True)
            thread.start()
            
        except Exception as e:
            messagebox.showerror("错误", f"更新元数据初始化失败: {str(e)}")
        

            
    def full_database_reset(self):
        """完全重置数据库，保留标签和打分信息"""
        # 确认对话框
        result = messagebox.askyesnocancel(
            "完全重置数据库",
            "此操作将：\n\n" +
            "✓ 保留：标签(tags)和星级评分(stars)\n" +
            "✗ 重置：文件路径、大小、时长、分辨率、封面等其他所有信息\n" +
            "✓ 基于MD5匹配保留的信息\n\n" +
            "是否继续？\n\n" +
            "是(Yes) - 执行重置\n" +
            "否(No) - 仅备份数据库\n" +
            "取消(Cancel) - 取消操作"
        )
        
        if result is None:  # 取消
            return
            
        try:
            # 备份数据库
            backup_path = f"media_library.db.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2("media_library.db", backup_path)
            self.status_var.set(f"数据库已备份到: {backup_path}")
            
            if not result:  # 仅备份
                messagebox.showinfo("完成", f"数据库已备份到: {backup_path}")
                return
                
            # 创建进度窗口
            progress_window = tk.Toplevel(self.root)
            progress_window.title("重置数据库进度")
            progress_window.geometry("500x400")
            progress_window.transient(self.root)
            progress_window.grab_set()
            
            # 进度显示
            progress_label = ttk.Label(progress_window, text="准备重置...")
            progress_label.pack(pady=10)
            
            progress_bar = ttk.Progressbar(progress_window, length=400, mode='indeterminate')
            progress_bar.pack(pady=10)
            
            # 日志显示
            log_frame = ttk.LabelFrame(progress_window, text="重置日志")
            log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            log_text = tk.Text(log_frame, height=15, width=60)
            log_scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=log_text.yview)
            log_text.configure(yscrollcommand=log_scrollbar.set)
            log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
            log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            cancel_button = ttk.Button(progress_window, text="取消")
            cancel_button.pack(pady=5)
            
            self.cancel_reset = False
            cancel_button.config(command=lambda: setattr(self, 'cancel_reset', True))
            
            def log_message(message):
                log_text.insert(tk.END, f"{datetime.now().strftime('%H:%M:%S')} - {message}\n")
                log_text.see(tk.END)
                progress_window.update()
                
            def reset_thread():
                try:
                    progress_bar.start()
                    log_message("开始重置数据库...")
                    
                    # 1. 保存需要保留的信息
                    log_message("正在保存标签和星级信息...")
                    self.cursor.execute("""
                        SELECT file_hash, stars, tags 
                        FROM videos 
                        WHERE file_hash IS NOT NULL AND file_hash != ''
                    """)
                    preserved_data = {}
                    for row in self.cursor.fetchall():
                        file_hash, stars, tags = row
                        preserved_data[file_hash] = {
                            'stars': stars or 0,
                            'tags': tags or ''
                        }
                    
                    log_message(f"已保存 {len(preserved_data)} 个文件的标签和星级信息")
                    
                    if self.cancel_reset:
                        log_message("重置已取消")
                        return
                        
                    # 2. 清空videos表
                    log_message("正在清空视频数据...")
                    self.cursor.execute("DELETE FROM videos")
                    self.conn.commit()
                    
                    # 3. 重新扫描所有文件夹
                    log_message("正在获取文件夹列表...")
                    self.cursor.execute("SELECT folder_path FROM folders WHERE is_active = 1")
                    folders = [row[0] for row in self.cursor.fetchall()]
                    
                    if not folders:
                        log_message("警告：没有找到活跃的文件夹")
                        progress_bar.stop()
                        cancel_button.config(text="关闭", command=progress_window.destroy)
                        return
                        
                    log_message(f"开始扫描 {len(folders)} 个文件夹...")
                    
                    total_files = 0
                    restored_files = 0
                    new_files = 0
                    
                    for folder_path in folders:
                        if self.cancel_reset:
                            break
                            
                        log_message(f"扫描文件夹: {folder_path}")
                        
                        if not os.path.exists(folder_path):
                            log_message(f"警告：文件夹不存在 - {folder_path}")
                            continue
                            
                        # 扫描文件夹中的视频文件
                        video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'}
                        
                        for root, dirs, files in os.walk(folder_path):
                            if self.cancel_reset:
                                break
                                
                            for file in files:
                                if self.cancel_reset:
                                    break
                                    
                                file_ext = os.path.splitext(file)[1].lower()
                                if file_ext in video_extensions:
                                    file_path = os.path.join(root, file)
                                    total_files += 1
                                    
                                    try:
                                        # 获取文件信息
                                        file_stats = os.stat(file_path)
                                        file_size = file_stats.st_size
                                        file_created_time = datetime.fromtimestamp(
                                            file_stats.st_birthtime if hasattr(file_stats, 'st_birthtime') else file_stats.st_ctime
                                        )
                                        
                                        # 计算MD5
                                        file_hash = self.calculate_file_hash(file_path)
                                        
                                        # 获取视频信息
                                        duration, resolution = self.get_video_info(file_path)
                                        
                                        # 解析标题和星级
                                        title = self.parse_title_from_filename(file)
                                        parsed_stars = self.parse_stars_from_filename(file)
                                        
                                        # 检查是否有保留的信息
                                        stars = parsed_stars
                                        tags = ''
                                        
                                        if file_hash in preserved_data:
                                            # 使用保留的信息
                                            stars = preserved_data[file_hash]['stars']
                                            tags = preserved_data[file_hash]['tags']
                                            restored_files += 1
                                            log_message(f"恢复: {file} (星级: {stars}, 标签: {tags or '无'})")
                                        else:
                                            # 新文件
                                            new_files += 1
                                            log_message(f"新增: {file} (星级: {stars})")
                                        
                                        # 检查NAS状态
                                        is_nas_online = self.check_nas_status(file_path)
                                        
                                        # 插入数据库
                                        self.cursor.execute("""
                                            INSERT INTO videos (
                                                file_path, file_name, file_size, file_hash, title, 
                                                stars, tags, is_nas_online, duration, resolution, 
                                                file_created_time, source_folder, created_at, updated_at
                                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                        """, (
                                            file_path, file, file_size, file_hash, title,
                                            stars, tags, is_nas_online, duration, resolution,
                                            file_created_time, os.path.dirname(file_path),
                                            datetime.now(), datetime.now()
                                        ))
                                        
                                    except Exception as e:
                                        log_message(f"处理文件失败 {file}: {str(e)}")
                                        
                    self.conn.commit()
                    progress_bar.stop()
                    
                    if not self.cancel_reset:
                        log_message("\n=== 重置完成 ===")
                        log_message(f"总文件数: {total_files}")
                        log_message(f"恢复文件: {restored_files} (保留了标签和星级)")
                        log_message(f"新增文件: {new_files}")
                        log_message(f"数据库备份: {backup_path}")
                        
                        # 刷新界面
                        self.load_videos()
                        self.load_folder_sources()
                        self.load_tags()
                        
                        cancel_button.config(text="完成", command=progress_window.destroy)
                        self.root.after(0, lambda: messagebox.showinfo("完成", f"数据库重置完成！\n\n恢复文件: {restored_files}\n新增文件: {new_files}\n总计: {total_files}"))
                    else:
                        log_message("重置已取消")
                        cancel_button.config(text="关闭", command=progress_window.destroy)
                        
                except Exception as e:
                    error_msg = str(e)
                    progress_bar.stop()
                    log_message(f"重置失败: {error_msg}")
                    cancel_button.config(text="关闭", command=progress_window.destroy)
                    self.root.after(0, lambda: messagebox.showerror("错误", f"重置失败: {error_msg}"))
                    
            threading.Thread(target=reset_thread, daemon=True).start()
            
        except Exception as e:
            messagebox.showerror("错误", f"启动重置失败: {str(e)}")
            
    def batch_generate_thumbnails(self):
        """批量生成封面"""
        # 确认对话框
        result = messagebox.askyesnocancel(
            "批量生成封面",
            "此操作将：\n\n" +
            "✓ 为所有没有封面的视频生成封面\n" +
            "✓ 跳过已有封面的视频\n" +
            "✓ 跳过NAS离线的视频\n" +
            "✓ 需要FFmpeg支持\n\n" +
            "是否继续？\n\n" +
            "是(Yes) - 生成所有缺失封面\n" +
            "否(No) - 重新生成所有封面\n" +
            "取消(Cancel) - 取消操作"
        )
        
        if result is None:  # 取消
            return
            
        try:
            # 获取FFmpeg命令
            ffmpeg_cmd = self.get_ffmpeg_command()
            if ffmpeg_cmd is None:
                messagebox.showerror("错误", "需要安装FFmpeg才能生成封面\n\nmacOS: brew install ffmpeg")
                return
                
            # 创建进度窗口
            progress_window = tk.Toplevel(self.root)
            progress_window.title("批量生成封面进度")
            progress_window.geometry("600x500")
            progress_window.transient(self.root)
            progress_window.grab_set()
            
            # 进度显示
            progress_label = ttk.Label(progress_window, text="准备生成封面...")
            progress_label.pack(pady=10)
            
            progress_bar = ttk.Progressbar(progress_window, length=500, mode='determinate')
            progress_bar.pack(pady=10)
            
            # 统计信息
            stats_frame = ttk.LabelFrame(progress_window, text="统计信息")
            stats_frame.pack(fill=tk.X, padx=10, pady=5)
            
            stats_text = tk.Text(stats_frame, height=4, width=70)
            stats_text.pack(padx=5, pady=5)
            
            # 日志显示
            log_frame = ttk.LabelFrame(progress_window, text="生成日志")
            log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            log_text = tk.Text(log_frame, height=15, width=70)
            log_scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=log_text.yview)
            log_text.configure(yscrollcommand=log_scrollbar.set)
            log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
            log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            # 控制按钮
            button_frame = ttk.Frame(progress_window)
            button_frame.pack(fill=tk.X, padx=10, pady=5)
            
            cancel_button = ttk.Button(button_frame, text="取消")
            cancel_button.pack(side=tk.LEFT, padx=5)
            
            pause_button = ttk.Button(button_frame, text="暂停")
            pause_button.pack(side=tk.LEFT, padx=5)
            
            self.cancel_thumbnail = False
            self.pause_thumbnail = False
            
            cancel_button.config(command=lambda: setattr(self, 'cancel_thumbnail', True))
            pause_button.config(command=self.toggle_pause_thumbnail)
            
            def log_message(message):
                log_text.insert(tk.END, f"{datetime.now().strftime('%H:%M:%S')} - {message}\n")
                log_text.see(tk.END)
                progress_window.update()
                
            def update_stats(total, processed, success, failed, skipped):
                stats_text.delete(1.0, tk.END)
                stats_text.insert(tk.END, f"总数: {total}  已处理: {processed}  成功: {success}  失败: {failed}  跳过: {skipped}\n")
                # 修复进度显示逻辑：避免在处理过程中显示100%
                if processed >= total:
                    progress_percentage = 100.0
                else:
                    progress_percentage = ((processed - 1) / total * 100) if processed > 0 else 0
                stats_text.insert(tk.END, f"进度: {processed}/{total} ({progress_percentage:.1f}%)\n")
                if processed > 0:
                    success_rate = success / processed * 100
                    stats_text.insert(tk.END, f"成功率: {success_rate:.1f}%")
                    
            def thumbnail_thread():
                try:
                    log_message("开始批量生成封面...")
                    
                    # 获取需要生成封面的视频
                    if result:  # 只生成缺失的封面
                        query = """
                            SELECT id, file_path, file_name, is_nas_online, thumbnail_data 
                            FROM videos 
                            WHERE (thumbnail_data IS NULL OR thumbnail_data = '')
                            ORDER BY file_name
                        """
                        log_message("模式：仅生成缺失封面")
                    else:  # 重新生成所有封面
                        query = """
                            SELECT id, file_path, file_name, is_nas_online, thumbnail_data 
                            FROM videos 
                            ORDER BY file_name
                        """
                        log_message("模式：重新生成所有封面")
                        
                    self.cursor.execute(query)
                    videos = self.cursor.fetchall()
                    
                    total_videos = len(videos)
                    if total_videos == 0:
                        log_message("没有找到需要生成封面的视频")
                        cancel_button.config(text="关闭", command=progress_window.destroy)
                        return
                        
                    log_message(f"找到 {total_videos} 个视频需要生成封面")
                    
                    progress_bar.config(maximum=total_videos)
                    
                    processed = 0
                    success_count = 0
                    failed_count = 0
                    skipped_count = 0
                    
                    for video in videos:
                        if self.cancel_thumbnail:
                            log_message("用户取消操作")
                            break
                            
                        # 处理暂停
                        while self.pause_thumbnail and not self.cancel_thumbnail:
                            progress_window.update()
                            threading.Event().wait(0.1)
                            
                        if self.cancel_thumbnail:
                            break
                            
                        video_id, file_path, file_name, is_nas_online, thumbnail_data = video
                        
                        try:
                            # 检查文件是否存在
                            if not os.path.exists(file_path):
                                log_message(f"跳过：文件不存在 - {file_name}")
                                skipped_count += 1
                                processed += 1
                                progress_bar.config(value=processed)
                                update_stats(total_videos, processed, success_count, failed_count, skipped_count)
                                continue
                                
                            # 如果是仅生成缺失封面模式，检查是否已有封面
                            if result and thumbnail_data:
                                log_message(f"跳过：已有封面 - {file_name}")
                                skipped_count += 1
                                processed += 1
                                progress_bar.config(value=processed)
                                update_stats(total_videos, processed, success_count, failed_count, skipped_count)
                                continue
                                
                            log_message(f"正在生成：{file_name}")
                            
                            # 创建临时文件
                            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
                                temp_path = temp_file.name
                                
                            # 生成缩略图（使用优化的GPU加速命令）
                            cmd = self.get_optimized_ffmpeg_cmd(file_path, temp_path)
                            if cmd is None:
                                log_message(f"失败：{file_name} - 无法构建FFmpeg命令")
                                failed_count += 1
                                processed += 1
                                progress_bar.config(value=processed)
                                update_stats(total_videos, processed, success_count, failed_count, skipped_count)
                                continue
                            
                            result_process = subprocess.run(cmd, capture_output=True, timeout=30)
                            
                            if result_process.returncode == 0 and os.path.exists(temp_path):
                                # 读取图片数据
                                with open(temp_path, 'rb') as f:
                                    thumbnail_data = f.read()
                                    
                                # 保存到数据库
                                self.cursor.execute(
                                    "UPDATE videos SET thumbnail_data = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                                    (thumbnail_data, video_id)
                                )
                                self.conn.commit()
                                
                                log_message(f"成功：{file_name}")
                                success_count += 1
                                
                                # 清理临时文件
                                try:
                                    os.unlink(temp_path)
                                except:
                                    pass
                                    
                            else:
                                log_message(f"失败：{file_name} - FFmpeg处理失败")
                                failed_count += 1
                                
                        except subprocess.TimeoutExpired:
                            log_message(f"失败：{file_name} - 处理超时")
                            failed_count += 1
                        except Exception as e:
                            log_message(f"失败：{file_name} - {str(e)}")
                            failed_count += 1
                            
                        processed += 1
                        progress_bar.config(value=processed)
                        update_stats(total_videos, processed, success_count, failed_count, skipped_count)
                        
                    if not self.cancel_thumbnail:
                        log_message("\n=== 批量生成完成 ===")
                        log_message(f"总计处理: {processed} 个视频")
                        log_message(f"成功生成: {success_count} 个封面")
                        log_message(f"生成失败: {failed_count} 个")
                        log_message(f"跳过处理: {skipped_count} 个")
                        
                        # 刷新当前视频的封面显示
                        if self.current_video:
                            self.load_video_details(self.current_video[0])
                            
                        cancel_button.config(text="完成", command=progress_window.destroy)
                        pause_button.config(state="disabled")
                        
                        self.root.after(0, lambda: messagebox.showinfo(
                            "完成", 
                            f"批量生成封面完成！\n\n" +
                            f"成功: {success_count}\n" +
                            f"失败: {failed_count}\n" +
                            f"跳过: {skipped_count}\n" +
                            f"总计: {processed}"
                        ))
                    else:
                        log_message("批量生成已取消")
                        cancel_button.config(text="关闭", command=progress_window.destroy)
                        pause_button.config(state="disabled")
                        
                except Exception as e:
                    error_msg = str(e)
                    log_message(f"批量生成失败: {error_msg}")
                    cancel_button.config(text="关闭", command=progress_window.destroy)
                    pause_button.config(state="disabled")
                    self.root.after(0, lambda: messagebox.showerror("错误", f"批量生成失败: {error_msg}"))
                    
            threading.Thread(target=thumbnail_thread, daemon=True).start()
            
        except Exception as e:
            messagebox.showerror("错误", f"启动批量生成失败: {str(e)}")
            
    def toggle_pause_thumbnail(self):
        """切换暂停状态"""
        self.pause_thumbnail = not self.pause_thumbnail
    
    def sync_stars_to_filename(self):
        """同步星级评分到文件名"""
        # 确认对话框
        result = messagebox.askyesnocancel(
            "同步打分到文件",
            "此操作将：\n\n" +
            "✓ 检查所有有星级评分的视频文件\n" +
            "✓ 为文件名添加对应数量的叹号前缀\n" +
            "✓ 2星=1个叹号(!)，3星=2个叹号(!!)，以此类推\n" +
            "✓ 如果演员信息不为空，则不添加叹号（如已有叹号则删除）\n" +
            "✓ 如果文件名重复会自动添加数字后缀\n" +
            "✓ 同步更新数据库中的文件路径\n\n" +
            "⚠️ 此操作会重命名文件，请确保已备份重要数据\n\n" +
            "是否继续？"
        )
        
        if result is None or not result:  # 取消或否
            return
            
        try:
            # 创建进度窗口
            progress_window = tk.Toplevel(self.root)
            progress_window.title("同步打分到文件进度")
            progress_window.geometry("700x600")
            progress_window.transient(self.root)
            progress_window.grab_set()
            
            # 进度显示
            progress_label = ttk.Label(progress_window, text="准备同步星级到文件名...")
            progress_label.pack(pady=10)
            
            progress_bar = ttk.Progressbar(progress_window, length=500, mode='determinate')
            progress_bar.pack(pady=10)
            
            # 统计信息
            stats_frame = ttk.LabelFrame(progress_window, text="统计信息")
            stats_frame.pack(fill=tk.X, padx=10, pady=5)
            
            stats_text = tk.Text(stats_frame, height=4, width=80)
            stats_text.pack(padx=5, pady=5)
            
            # 日志显示
            log_frame = ttk.LabelFrame(progress_window, text="同步日志")
            log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            log_text = tk.Text(log_frame, height=15, width=80)
            log_scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=log_text.yview)
            log_text.configure(yscrollcommand=log_scrollbar.set)
            log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
            log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            # 控制按钮
            button_frame = ttk.Frame(progress_window)
            button_frame.pack(fill=tk.X, padx=10, pady=5)
            
            cancel_button = ttk.Button(button_frame, text="取消")
            cancel_button.pack(side=tk.LEFT, padx=5)
            
            self.cancel_sync = False
            
            def log_message(message):
                """添加日志消息"""
                timestamp = datetime.now().strftime("%H:%M:%S")
                log_text.insert(tk.END, f"[{timestamp}] {message}\n")
                log_text.see(tk.END)
                progress_window.update()
            
            def cancel_sync():
                """取消同步"""
                self.cancel_sync = True
                cancel_button.config(text="关闭", command=progress_window.destroy)
            
            cancel_button.config(command=cancel_sync)
            
            def sync_thread():
                """同步线程"""
                try:
                    # 获取所有有星级评分的视频，同时查询演员信息
                    cursor = self.conn.cursor()
                    cursor.execute("""
                         SELECT v.id, v.file_path, v.stars, v.title,
                                GROUP_CONCAT(a.name) as actors
                         FROM videos v
                         LEFT JOIN video_actors va ON v.id = va.video_id
                         LEFT JOIN actors a ON va.actor_id = a.id
                         WHERE v.stars > 0 AND v.file_path IS NOT NULL AND v.file_path != ''
                         GROUP BY v.id, v.file_path, v.stars, v.title
                         ORDER BY v.stars DESC, v.title
                     """)
                    videos = cursor.fetchall()
                    
                    if not videos:
                        log_message("没有找到需要同步的视频文件")
                        cancel_button.config(text="关闭", command=progress_window.destroy)
                        return
                    
                    total_videos = len(videos)
                    progress_bar.config(maximum=total_videos)
                    
                    log_message(f"找到 {total_videos} 个有星级评分的视频文件")
                    
                    # 统计变量
                    processed = 0
                    renamed_count = 0
                    skipped_count = 0
                    error_count = 0
                    
                    for video_id, file_path, stars, title, actors in videos:
                        if self.cancel_sync:
                            break
                            
                        processed += 1
                        progress_bar.config(value=processed)
                        progress_label.config(text=f"处理中: {os.path.basename(file_path)} ({processed}/{total_videos})")
                        
                        try:
                            # 检查文件是否存在
                            if not os.path.exists(file_path):
                                log_message(f"跳过: 文件不存在 - {file_path}")
                                skipped_count += 1
                                continue
                            
                            # 解析当前文件名
                            file_dir = os.path.dirname(file_path)
                            filename = os.path.basename(file_path)
                            name, ext = os.path.splitext(filename)
                            
                            # 检查演员字段是否为空
                            has_actors = actors is not None and actors.strip() != ''
                            
                            # 如果有演员信息，则不添加叹号（required_exclamations = 0）
                            # 如果没有演员信息，则按原逻辑添加叹号
                            if has_actors:
                                required_exclamations = 0
                                log_message(f"检测到演员信息，不添加叹号: {filename} (演员: {actors})")
                            else:
                                # 计算需要的叹号数量 (stars - 1，因为1星不加叹号)
                                required_exclamations = max(0, stars - 1)
                            
                            # 检查当前文件名的叹号数量
                            current_exclamations = 0
                            clean_name = name
                            while clean_name.startswith('!'):
                                current_exclamations += 1
                                clean_name = clean_name[1:]
                            
                            # 如果叹号数量已经正确，跳过
                            if current_exclamations == required_exclamations:
                                log_message(f"跳过: 叹号数量已正确 - {filename}")
                                skipped_count += 1
                                continue
                            
                            # 生成新文件名
                            new_exclamations = '!' * required_exclamations
                            new_filename = f"{new_exclamations}{clean_name}{ext}"
                            new_full_path = os.path.join(file_dir, new_filename)
                            
                            # 处理重名冲突
                            counter = 1
                            original_new_path = new_full_path
                            while os.path.exists(new_full_path) and new_full_path != file_path:
                                name_part, ext_part = os.path.splitext(original_new_path)
                                new_full_path = f"{name_part}_{counter}{ext_part}"
                                counter += 1
                            
                            # 如果路径没有变化，跳过
                            if new_full_path == file_path:
                                log_message(f"跳过: 路径未变化 - {filename}")
                                skipped_count += 1
                                continue
                            
                            # 重命名文件
                            os.rename(file_path, new_full_path)
                            
                            # 更新数据库
                            cursor.execute("""
                                UPDATE videos 
                                SET file_path = ? 
                                WHERE id = ?
                            """, (new_full_path, video_id))
                            
                            log_message(f"重命名: {filename} -> {os.path.basename(new_full_path)}")
                            renamed_count += 1
                            
                        except Exception as e:
                            log_message(f"错误: {filename} - {str(e)}")
                            error_count += 1
                        
                        # 更新统计信息
                        stats_text.delete(1.0, tk.END)
                        stats_text.insert(tk.END, 
                            f"处理进度: {processed}/{total_videos}\n" +
                            f"重命名: {renamed_count}\n" +
                            f"跳过: {skipped_count}\n" +
                            f"错误: {error_count}"
                        )
                    
                    # 提交数据库更改
                    self.conn.commit()
                    
                    if not self.cancel_sync:
                        log_message("\n=== 同步完成 ===")
                        log_message(f"总计处理: {processed} 个文件")
                        log_message(f"成功重命名: {renamed_count} 个文件")
                        log_message(f"跳过: {skipped_count} 个文件")
                        log_message(f"错误: {error_count} 个文件")
                        
                        cancel_button.config(text="关闭", command=progress_window.destroy)
                        
                        if renamed_count > 0:
                            # 先显示完成对话框，避免卡顿
                            messagebox.showinfo("同步完成", 
                                f"同步完成！\n\n" +
                                f"成功重命名: {renamed_count} 个文件\n" +
                                f"跳过: {skipped_count} 个文件\n" +
                                f"错误: {error_count} 个文件")
                            
                            # 在对话框显示后异步刷新视频列表
                            self.root.after(100, self.load_videos)
                    else:
                        log_message("同步已取消")
                        cancel_button.config(text="关闭", command=progress_window.destroy)
                        
                except Exception as e:
                    log_message(f"同步失败: {str(e)}")
                    cancel_button.config(text="关闭", command=progress_window.destroy)
                    messagebox.showerror("错误", f"同步失败: {str(e)}")
                    
            threading.Thread(target=sync_thread, daemon=True).start()
            
        except Exception as e:
            messagebox.showerror("错误", f"启动同步失败: {str(e)}")
            
    def remove_duplicates(self):
        """去重复"""
        try:
            # 查找重复的文件（基于哈希值）
            self.cursor.execute(
                """SELECT file_hash, COUNT(*) as count, GROUP_CONCAT(id) as ids 
                   FROM videos 
                   WHERE file_hash IS NOT NULL 
                   GROUP BY file_hash 
                   HAVING count > 1"""
            )
            
            duplicates = self.cursor.fetchall()
            removed_count = 0
            
            for file_hash, count, ids in duplicates:
                id_list = ids.split(',')
                # 保留第一个，删除其余的
                for video_id in id_list[1:]:
                    self.cursor.execute("DELETE FROM videos WHERE id = ?", (video_id,))
                    removed_count += 1
                    
            self.conn.commit()
            
            if removed_count > 0:
                messagebox.showinfo("去重完成", f"已删除 {removed_count} 个重复视频记录")
                self.load_videos()
            else:
                messagebox.showinfo("去重完成", "没有发现重复的视频")
                
        except Exception as e:
            messagebox.showerror("错误", f"去重失败: {str(e)}")
            
    def manage_tags(self):
        """标签管理"""
        tag_window = tk.Toplevel(self.root)
        tag_window.title("标签管理")
        tag_window.geometry("400x300")
        
        # 标签列表
        listbox_frame = ttk.Frame(tag_window)
        listbox_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        tag_listbox = tk.Listbox(listbox_frame)
        tag_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(listbox_frame, orient=tk.VERTICAL, command=tag_listbox.yview)
        tag_listbox.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 按钮
        button_frame = ttk.Frame(tag_window)
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        def add_tag():
            tag = simpledialog.askstring("添加标签", "请输入标签名称:")
            if tag:
                try:
                    self.cursor.execute("INSERT INTO tags (tag_name) VALUES (?)", (tag,))
                    self.conn.commit()
                    load_tags_list()
                    self.load_tags()
                except Exception as e:
                    messagebox.showerror("错误", f"添加标签失败: {str(e)}")
                    
        def delete_tag():
            selection = tag_listbox.curselection()
            if selection:
                tag_name = tag_listbox.get(selection[0])
                if messagebox.askyesno("确认删除", f"确定要删除标签 '{tag_name}' 吗？"):
                    try:
                        self.cursor.execute("DELETE FROM tags WHERE tag_name = ?", (tag_name,))
                        self.conn.commit()
                        load_tags_list()
                        self.load_tags()
                    except Exception as e:
                        messagebox.showerror("错误", f"删除标签失败: {str(e)}")
                        
        def load_tags_list():
            tag_listbox.delete(0, tk.END)
            self.cursor.execute("SELECT tag_name FROM tags ORDER BY tag_name")
            tags = self.cursor.fetchall()
            for tag in tags:
                tag_listbox.insert(tk.END, tag[0])
                
        ttk.Button(button_frame, text="添加标签", command=add_tag).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="删除标签", command=delete_tag).pack(side=tk.LEFT)
        
        load_tags_list()
        
    def manage_folders(self):
        """文件夹管理"""
        folder_window = tk.Toplevel(self.root)
        folder_window.title("文件夹管理")
        folder_window.geometry("600x400")
        
        # 文件夹列表
        columns = ('path', 'type', 'device', 'status')
        folder_tree = ttk.Treeview(folder_window, columns=columns, show='headings')
        
        folder_tree.heading('path', text='路径')
        folder_tree.heading('type', text='类型')
        folder_tree.heading('device', text='设备')
        folder_tree.heading('status', text='状态')
        
        folder_tree.column('path', width=300)
        folder_tree.column('type', width=80)
        folder_tree.column('device', width=120)
        folder_tree.column('status', width=80)
        
        folder_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 按钮
        button_frame = ttk.Frame(folder_window)
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        def add_folder_to_management():
            """在文件夹管理窗口中添加文件夹"""
            # 创建选择对话框
            choice_window = tk.Toplevel(folder_window)
            choice_window.title("添加文件夹")
            choice_window.geometry("400x200")
            choice_window.transient(folder_window)
            choice_window.grab_set()
            
            # 居中显示
            choice_window.geometry("+%d+%d" % (folder_window.winfo_rootx() + 50, folder_window.winfo_rooty() + 50))
            
            folder_path = None
            
            def browse_folder():
                nonlocal folder_path
                path = filedialog.askdirectory(title="选择要添加的文件夹")
                if path:
                    folder_path = path
                    choice_window.destroy()
            
            def manual_input():
                nonlocal folder_path
                # 创建手动输入对话框
                input_window = tk.Toplevel(choice_window)
                input_window.title("手动输入路径")
                input_window.geometry("500x150")
                input_window.transient(choice_window)
                input_window.grab_set()
                
                ttk.Label(input_window, text="请输入文件夹路径（支持SMB协议）:").pack(pady=10)
                ttk.Label(input_window, text="例如: smb://username@192.168.1.100/shared_folder", font=("Arial", 9), foreground="gray").pack()
                
                path_var = tk.StringVar()
                entry = ttk.Entry(input_window, textvariable=path_var, width=60)
                entry.pack(pady=10)
                entry.focus()
                
                def confirm_input():
                    nonlocal folder_path
                    path = path_var.get().strip()
                    if path:
                        folder_path = path
                        input_window.destroy()
                        choice_window.destroy()
                    else:
                        messagebox.showwarning("警告", "请输入有效的路径")
                
                def cancel_input():
                    input_window.destroy()
                
                button_frame = ttk.Frame(input_window)
                button_frame.pack(pady=10)
                ttk.Button(button_frame, text="确定", command=confirm_input).pack(side=tk.LEFT, padx=5)
                ttk.Button(button_frame, text="取消", command=cancel_input).pack(side=tk.LEFT, padx=5)
                
                # 绑定回车键
                entry.bind('<Return>', lambda e: confirm_input())
            
            def cancel_choice():
                choice_window.destroy()
            
            # 创建选择界面
            ttk.Label(choice_window, text="请选择添加文件夹的方式:", font=("Arial", 12)).pack(pady=20)
            
            button_frame = ttk.Frame(choice_window)
            button_frame.pack(pady=20)
            
            ttk.Button(button_frame, text="浏览文件夹", command=browse_folder, width=15).pack(side=tk.LEFT, padx=10)
            ttk.Button(button_frame, text="手动输入路径", command=manual_input, width=15).pack(side=tk.LEFT, padx=10)
            
            ttk.Button(choice_window, text="取消", command=cancel_choice).pack(pady=10)
            
            # 等待窗口关闭
            choice_window.wait_window()
            
            if folder_path:
                try:
                    # 检查是否为NAS路径
                    folder_type = "nas" if folder_path.startswith(("/Volumes", "//", "smb://")) else "local"
                    current_device = self.get_current_device_name()
                    
                    self.cursor.execute(
                        "INSERT OR REPLACE INTO folders (folder_path, folder_type, device_name) VALUES (?, ?, ?)",
                        (folder_path, folder_type, current_device)
                    )
                    self.conn.commit()
                    
                    load_folders()  # 刷新文件夹列表
                    self.load_folder_sources()  # 刷新主界面的文件夹列表
                    messagebox.showinfo("成功", f"文件夹已添加: {folder_path}")
                except Exception as e:
                    messagebox.showerror("错误", f"添加文件夹失败: {str(e)}")
        
        def load_folders():
            for item in folder_tree.get_children():
                folder_tree.delete(item)
                
            self.cursor.execute("SELECT * FROM folders ORDER BY folder_path")
            folders = self.cursor.fetchall()
            current_device = self.get_current_device_name()
            
            for folder in folders:
                if len(folder) == 5:  # 旧格式，没有device_name字段
                    folder_id, folder_path, folder_type, is_active, created_at = folder
                    device_name = "Unknown"
                else:  # 新格式，包含device_name字段
                    folder_id, folder_path, folder_type, is_active, created_at, device_name = folder
                
                # 生成设备显示名称
                if folder_type == "nas":
                    # NAS设备：显示IP或域名
                    if folder_path.startswith("smb://"):
                        # 从smb://username@192.168.1.100/folder格式中提取IP
                        import re
                        ip_match = re.search(r'@([0-9.]+)/', folder_path)
                        if ip_match:
                            device_display = ip_match.group(1)
                        else:
                            # 尝试提取域名
                            domain_match = re.search(r'smb://(?:[^@]+@)?([^/]+)/', folder_path)
                            if domain_match:
                                device_display = domain_match.group(1)
                            else:
                                device_display = "NAS"
                    elif folder_path.startswith("/Volumes/"):
                        # macOS挂载的网络驱动器，尝试从路径提取名称
                        volume_name = folder_path.split('/')[2] if len(folder_path.split('/')) > 2 else "NAS"
                        device_display = volume_name
                    else:
                        device_display = "NAS"
                else:
                    # 本地设备：显示设备名称
                    device_display = device_name if device_name and device_name != "Unknown" else "Unknown"
                
                # 判断状态：仅基于路径存在性和is_active状态
                if not is_active:
                    status = "禁用"
                else:
                    # 检查路径是否存在来判断在线状态
                    if os.path.exists(folder_path):
                        status = "在线"
                    else:
                        status = "离线"
                
                folder_tree.insert('', 'end', values=(folder_path, folder_type, device_display, status), tags=(folder_id,))
                
        def toggle_folder():
            selection = folder_tree.selection()
            if selection:
                item = folder_tree.item(selection[0])
                folder_id = item['tags'][0]
                
                self.cursor.execute("SELECT is_active FROM folders WHERE id = ?", (folder_id,))
                current_status = self.cursor.fetchone()[0]
                new_status = 0 if current_status else 1
                
                self.cursor.execute("UPDATE folders SET is_active = ? WHERE id = ?", (new_status, folder_id))
                self.conn.commit()
                load_folders()
                
        def remove_folder():
            selection = folder_tree.selection()
            if selection:
                item = folder_tree.item(selection[0])
                folder_path = item['values'][0]
                folder_id = item['tags'][0]
                
                if messagebox.askyesno("确认删除", f"确定要删除文件夹 '{folder_path}' 吗？"):
                    self.cursor.execute("DELETE FROM folders WHERE id = ?", (folder_id,))
                    self.conn.commit()
                    load_folders()
                    
        ttk.Button(button_frame, text="添加文件夹", command=add_folder_to_management).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="启用/禁用", command=toggle_folder).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="删除文件夹", command=remove_folder).pack(side=tk.LEFT)
        
        load_folders()
        
    def on_header_double_click(self, event):
        """双击表头排序"""
        # 获取点击的列
        region = self.video_tree.identify_region(event.x, event.y)
        if region == "heading":
            col = self.video_tree.identify_column(event.x)
            if col:
                # 将列号转换为列名
                col_index = int(col.replace('#', '')) - 1
                columns = list(self.video_tree['columns'])
                if 0 <= col_index < len(columns):
                    col_name = columns[col_index]
                    self.sort_column(col_name)
                    return "break"  # 阻止默认的列排序行为
    
    def sort_column(self, col_name):
        """双击列标题排序"""
        # 如果点击的是同一列，则切换排序方向
        if self.sort_column_name == col_name:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column_name = col_name
            self.sort_reverse = False
        
        # 更新列标题显示排序方向
        for col in self.video_tree['columns']:
            config = self.column_config[col]
            if col == col_name:
                arrow = " ↓" if self.sort_reverse else " ↑"
                self.video_tree.heading(col, text=config['text'] + arrow)
            else:
                self.video_tree.heading(col, text=config['text'])
        
        # 重新加载并排序数据
        self.load_videos()
    
    def on_search(self, event=None):
        """搜索事件"""
        self.filter_videos()
        
    def filter_videos(self, event=None):
        """筛选视频"""
        # 设置筛选标志，然后调用load_videos来正确显示数据
        self.is_filtering = True
        self.load_videos()

    
    def show_context_menu(self, event):
        """显示右键菜单"""
        # 获取点击的项目
        item = self.video_tree.identify_row(event.y)
        if not item:
            return
        
        # 获取当前选中的所有项目
        selected_items = self.video_tree.selection()
        
        # 如果点击的项目不在选中列表中，且当前没有多选，则只选中点击的项目
        if item not in selected_items:
            # 如果当前没有选中任何项目，或者只选中了一个项目，则选中点击的项目
            if len(selected_items) <= 1:
                self.video_tree.selection_set(item)
                selected_items = [item]
            else:
                # 如果已经选中了多个项目，则将点击的项目添加到选择中
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
                    is_nas_online = self.is_video_online(video_id)
                    # print(f"Debug: Video ID {video_id}, Online status: {is_nas_online}")
                    selected_videos.append({
                        'id': video_id,
                        'path': file_path,
                        'online': is_nas_online
                    })
                    if is_nas_online:
                        online_count += 1
            except (IndexError, TypeError):
                continue
        
        # 如果没有选中的文件，不显示菜单
        if len(selected_videos) == 0:
            return
        
        # 创建右键菜单
        context_menu = tk.Menu(self.root, tearoff=0)
        
        # 根据选中文件数量调整菜单
        if len(selected_videos) == 1:
            # 单文件菜单
            video_info = selected_videos[0]
            # 播放选项 - 根据在线状态决定是否启用
            if video_info['online']:
                context_menu.add_command(label="播放", command=lambda: self.play_video_from_context(video_info['id']))
            else:
                context_menu.add_command(label="播放 (离线)", state="disabled")
            context_menu.add_separator()
            context_menu.add_command(label="打开所在文件夹", command=lambda: self.open_file_folder(video_info['id']))
            context_menu.add_separator()
            context_menu.add_command(label="自动标签", command=lambda: self.auto_tag_selected_videos())
            context_menu.add_separator()
            context_menu.add_command(label="JAVDB信息获取", command=lambda: self.fetch_javdb_info(video_info['id']))
            context_menu.add_separator()
            context_menu.add_command(label="更新元数据", command=lambda: self.update_single_file_metadata(video_info['id']))
            context_menu.add_separator()
            context_menu.add_command(label="清理文件名", command=lambda: self.clean_filename_from_context(video_info['id']))
            context_menu.add_separator()
            context_menu.add_command(label="导入NFO", command=lambda: self.import_nfo_from_context(video_info['id'], video_info['path']))
            context_menu.add_separator()
            context_menu.add_command(label="删除文件", command=lambda: self.delete_file_from_context(video_info['id'], video_info['path']))
            
            # 添加移动到子菜单
            move_menu = tk.Menu(context_menu, tearoff=0)
            context_menu.add_cascade(label="移动到", menu=move_menu)
            
            # 获取所有在线文件夹
            self.cursor.execute("SELECT folder_path FROM folders WHERE is_active = 1")
            online_folders = self.cursor.fetchall()
            
            for folder in online_folders:
                folder_path = folder[0]
                folder_name = os.path.basename(folder_path)
                move_menu.add_command(label=folder_name, 
                                    command=lambda fp=folder_path: self.move_file_to_folder(video_info['id'], video_info['path'], fp))
        else:
            # 多文件菜单
            context_menu.add_command(label=f"批量自动标签 ({len(selected_videos)}个文件)", 
                                   command=lambda: self.batch_auto_tag_selected_videos())
            context_menu.add_separator()
            context_menu.add_command(label=f"批量JAVDB信息获取 ({len(selected_videos)}个文件)", 
                                   command=lambda: self.batch_javdb_info_selected_videos())
            context_menu.add_separator()
            context_menu.add_command(label=f"批量更新元数据 ({len(selected_videos)}个文件)", 
                                   command=lambda: self.batch_update_metadata_selected_videos())
            context_menu.add_separator()
            context_menu.add_command(label=f"批量清理文件名 ({len(selected_videos)}个文件)", 
                                   command=lambda: self.batch_clean_filename_selected_videos())
            context_menu.add_separator()
            context_menu.add_command(label=f"批量删除文件 ({len(selected_videos)}个文件)", 
                                   command=lambda: self.batch_delete_selected_videos())
            
            # 添加批量移动到子菜单
            move_menu = tk.Menu(context_menu, tearoff=0)
            context_menu.add_cascade(label=f"批量移动到 ({len(selected_videos)}个文件)", menu=move_menu)
            
            # 获取所有在线文件夹
            self.cursor.execute("SELECT folder_path FROM folders WHERE is_active = 1")
            online_folders = self.cursor.fetchall()
            
            for folder in online_folders:
                folder_path = folder[0]
                folder_name = os.path.basename(folder_path)
                move_menu.add_command(label=folder_name, 
                                    command=lambda fp=folder_path: self.batch_move_files_to_folder(fp))
        
        # 显示菜单
        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.grab_release()
    
    def batch_auto_tag_selected_videos(self):
        """批量自动标签选中的视频"""
        selected_items = self.video_tree.selection()
        if not selected_items:
            messagebox.showwarning("警告", "请先选择要处理的视频文件")
            return
        
        # 获取选中的视频ID列表
        video_ids = []
        for item in selected_items:
            try:
                video_id = self.video_tree.item(item)['tags'][0]
                # 检查文件是否在线
                if self.is_video_online(video_id):  # 只处理在线文件
                    video_ids.append(video_id)
            except (IndexError, TypeError):
                continue
        
        if not video_ids:
            messagebox.showwarning("警告", "没有找到可处理的在线视频文件")
            return
        
        # 确认操作
        if not messagebox.askyesno("确认", f"确定要对 {len(video_ids)} 个视频文件进行自动标签吗？"):
            return
        
        # 执行批量自动标签
        self.batch_process_auto_tag(video_ids)
    
    def batch_update_metadata_selected_videos(self):
        """批量更新选中视频的元数据"""
        selected_items = self.video_tree.selection()
        if not selected_items:
            messagebox.showwarning("警告", "请先选择要处理的视频文件")
            return
        
        # 获取选中的视频ID列表
        video_ids = []
        for item in selected_items:
            try:
                video_id = self.video_tree.item(item)['tags'][0]
                # 检查文件是否在线
                if self.is_video_online(video_id):  # 只处理在线文件
                    video_ids.append(video_id)
            except (IndexError, TypeError):
                continue
        
        if not video_ids:
            messagebox.showwarning("警告", "没有找到可处理的在线视频文件")
            return
        
        # 确认操作
        if not messagebox.askyesno("确认", f"确定要更新 {len(video_ids)} 个视频文件的元数据吗？"):
            return
        
        # 执行批量更新元数据
        self.batch_process_metadata_update(video_ids)
    
    def batch_delete_selected_videos(self):
        """批量删除选中的视频文件"""
        selected_items = self.video_tree.selection()
        if not selected_items:
            messagebox.showwarning("警告", "请先选择要删除的视频文件")
            return
        
        # 获取选中的视频信息
        videos_to_delete = []
        for item in selected_items:
            try:
                video_id = self.video_tree.item(item)['tags'][0]
                self.cursor.execute("SELECT file_path, file_name FROM videos WHERE id = ?", (video_id,))
                result = self.cursor.fetchone()
                if result and self.is_video_online(video_id):  # 只处理在线文件
                    videos_to_delete.append({
                        'id': video_id,
                        'path': result[0],
                        'name': result[1]
                    })
            except (IndexError, TypeError):
                continue
        
        if not videos_to_delete:
            messagebox.showwarning("警告", "没有找到可删除的在线视频文件")
            return
        
        # 确认删除
        file_list = "\n".join([f"• {video['name']}" for video in videos_to_delete[:10]])
        if len(videos_to_delete) > 10:
            file_list += f"\n... 还有 {len(videos_to_delete) - 10} 个文件"
        
        if not messagebox.askyesno("确认删除", f"确定要删除以下 {len(videos_to_delete)} 个视频文件吗？\n\n{file_list}\n\n注意：此操作不可撤销！"):
            return
        
        # 执行批量删除
        self.batch_process_delete(videos_to_delete)
    
    def batch_move_files_to_folder(self, target_folder):
        """批量移动选中的文件到指定文件夹"""
        selected_items = self.video_tree.selection()
        if not selected_items:
            messagebox.showwarning("警告", "请先选择要移动的视频文件")
            return
        
        # 获取选中的视频信息
        videos_to_move = []
        for item in selected_items:
            try:
                video_id = self.video_tree.item(item)['tags'][0]
                self.cursor.execute("SELECT file_path, file_name FROM videos WHERE id = ?", (video_id,))
                result = self.cursor.fetchone()
                if result and self.is_video_online(video_id):  # 只处理在线文件
                    videos_to_move.append({
                        'id': video_id,
                        'path': result[0],
                        'name': result[1]
                    })
            except (IndexError, TypeError):
                continue
        
        if not videos_to_move:
            messagebox.showwarning("警告", "没有找到可移动的在线视频文件")
            return
        
        # 确认移动
        target_name = os.path.basename(target_folder)
        if not messagebox.askyesno("确认移动", f"确定要将 {len(videos_to_move)} 个视频文件移动到 '{target_name}' 文件夹吗？"):
            return
        
        # 执行批量移动
        self.batch_process_move(videos_to_move, target_folder)
    
    def batch_javdb_info_selected_videos(self):
        """批量获取选中视频的JAVDB信息"""
        try:
            selected_items = self.video_tree.selection()
            if not selected_items:
                messagebox.showwarning("警告", "请先选择要获取JAVDB信息的视频文件")
                return
            
            # 获取选中视频的数字ID
            video_ids = []
            for item in selected_items:
                try:
                    # 从tags中获取数字ID
                    tags = self.video_tree.item(item, 'tags')
                    if tags:
                        video_id = int(tags[0])  # 数字ID存储在tags中
                        # 获取视频文件路径
                        self.cursor.execute("SELECT file_path FROM videos WHERE id = ?", (video_id,))
                        result = self.cursor.fetchone()
                        if result:
                            file_path = result[0]
                            # 使用统一的is_video_online函数判断视频是否在线
                            is_online = self.is_video_online(video_id)
                            print(f"批量JAVDB调试 - 数字ID: {video_id}, 在线状态: {is_online}")
                            if is_online:
                                video_ids.append(video_id)
                except Exception as e:
                    print(f"获取视频ID时出错: {e}")
                    continue
            
            if not video_ids:
                messagebox.showwarning("警告", "没有选中在线的视频文件")
                return
            
            # 确认对话框
            if not messagebox.askyesno("确认", f"确定要获取 {len(video_ids)} 个视频的JAVDB信息吗？\n\n注意：这可能需要较长时间，请耐心等待。"):
                return
            
            # 执行批量JAVDB信息获取
            self.batch_process_javdb_info(video_ids)
            
        except Exception as e:
            error_msg = f"批量JAVDB信息获取启动失败: {str(e)}"
            print(error_msg)
            messagebox.showerror("错误", error_msg)
    
    def batch_process_auto_tag(self, video_ids):
        """批量处理自动标签"""
        try:
            # 获取视频文件路径
            video_paths = []
            for video_id in video_ids:
                self.cursor.execute("SELECT file_path FROM videos WHERE id = ?", (video_id,))
                result = self.cursor.fetchone()
                if result:
                    video_paths.append(result[0])
            
            if video_paths:
                # 调用带进度条的视频内容分析器
                self.run_video_content_analyzer_with_progress(video_paths)
            
        except Exception as e:
            messagebox.showerror("错误", f"批量自动标签失败: {str(e)}")
    
    def batch_process_metadata_update(self, video_ids):
        """批量处理元数据更新"""
        try:
            # 创建进度窗口
            progress_window = ProgressWindow(self.root, "批量更新元数据", len(video_ids))
            
            def update_metadata():
                try:
                    success_count = 0
                    for i, video_id in enumerate(video_ids):
                        # 更新进度
                        self.cursor.execute("SELECT file_name FROM videos WHERE id = ?", (video_id,))
                        result = self.cursor.fetchone()
                        file_name = result[0] if result else f"ID: {video_id}"
                        
                        progress_window.update_progress(i + 1, f"正在更新: {file_name}")
                        
                        # 调用现有的单文件元数据更新函数
                        self.update_single_file_metadata(video_id)
                        success_count += 1
                        
                        # 检查是否取消
                        if progress_window.cancelled:
                            break
                    
                    progress_window.close()
                    if not progress_window.cancelled:
                        messagebox.showinfo("完成", f"批量更新元数据完成！\n成功处理: {success_count} 个文件")
                    
                except Exception as e:
                    progress_window.close()
                    messagebox.showerror("错误", f"批量更新元数据失败: {str(e)}")
            
            # 在新线程中执行
            import threading
            thread = threading.Thread(target=update_metadata)
            thread.daemon = True
            thread.start()
            
        except Exception as e:
            messagebox.showerror("错误", f"批量更新元数据失败: {str(e)}")
    
    def batch_process_delete(self, videos_to_delete):
        """批量处理删除文件"""
        try:
            # 创建进度窗口
            progress_window = ProgressWindow(self.root, "批量删除文件", len(videos_to_delete))
            
            def delete_files():
                try:
                    success_count = 0
                    failed_files = []
                    
                    for i, video_info in enumerate(videos_to_delete):
                        # 更新进度
                        progress_window.update_progress(i + 1, f"正在删除: {video_info['name']}")
                        
                        try:
                            # 删除物理文件
                            if os.path.exists(video_info['path']):
                                os.remove(video_info['path'])
                            
                            # 删除数据库记录
                            self.cursor.execute("DELETE FROM videos WHERE id = ?", (video_info['id'],))
                            success_count += 1
                            
                        except Exception as e:
                            failed_files.append(f"{video_info['name']}: {str(e)}")
                        
                        # 检查是否取消
                        if progress_window.cancelled:
                            break
                    
                    # 提交数据库更改
                    if not progress_window.cancelled:
                        self.conn.commit()
                        # 刷新列表
                        self.filter_videos()
                    
                    progress_window.close()
                    
                    if not progress_window.cancelled:
                        result_msg = f"批量删除完成！\n成功删除: {success_count} 个文件"
                        if failed_files:
                            result_msg += f"\n失败: {len(failed_files)} 个文件\n\n失败详情:\n" + "\n".join(failed_files[:5])
                            if len(failed_files) > 5:
                                result_msg += f"\n... 还有 {len(failed_files) - 5} 个失败文件"
                        messagebox.showinfo("完成", result_msg)
                    
                except Exception as e:
                    progress_window.close()
                    messagebox.showerror("错误", f"批量删除失败: {str(e)}")
            
            # 在新线程中执行
            import threading
            thread = threading.Thread(target=delete_files)
            thread.daemon = True
            thread.start()
            
        except Exception as e:
            messagebox.showerror("错误", f"批量删除失败: {str(e)}")
    
    def batch_process_move(self, videos_to_move, target_folder):
        """批量处理移动文件"""
        try:
            # 创建进度窗口
            progress_window = ProgressWindow(self.root, "批量移动文件", len(videos_to_move))
            
            def move_files():
                try:
                    success_count = 0
                    failed_files = []
                    
                    for i, video_info in enumerate(videos_to_move):
                        # 更新进度
                        progress_window.update_progress(i + 1, f"正在移动: {video_info['name']}")
                        
                        try:
                            # 构建新文件路径
                            file_name = os.path.basename(video_info['path'])
                            new_file_path = os.path.join(target_folder, file_name)
                            
                            # 检查目标文件是否已存在
                            if os.path.exists(new_file_path):
                                # 生成新的文件名
                                base_name, ext = os.path.splitext(file_name)
                                counter = 1
                                while os.path.exists(new_file_path):
                                    new_file_name = f"{base_name}_{counter}{ext}"
                                    new_file_path = os.path.join(target_folder, new_file_name)
                                    counter += 1
                            
                            # 移动文件
                            shutil.move(video_info['path'], new_file_path)
                            
                            # 更新数据库记录
                            self.cursor.execute(
                                "UPDATE videos SET file_path = ?, source_folder = ? WHERE id = ?",
                                (new_file_path, target_folder, video_info['id'])
                            )
                            success_count += 1
                            
                        except Exception as e:
                            failed_files.append(f"{video_info['name']}: {str(e)}")
                        
                        # 检查是否取消
                        if progress_window.cancelled:
                            break
                    
                    # 提交数据库更改
                    if not progress_window.cancelled:
                        self.conn.commit()
                        # 刷新列表
                        self.filter_videos()
                    
                    progress_window.close()
                    
                    if not progress_window.cancelled:
                        result_msg = f"批量移动完成！\n成功移动: {success_count} 个文件"
                        if failed_files:
                            result_msg += f"\n失败: {len(failed_files)} 个文件\n\n失败详情:\n" + "\n".join(failed_files[:5])
                            if len(failed_files) > 5:
                                result_msg += f"\n... 还有 {len(failed_files) - 5} 个失败文件"
                        messagebox.showinfo("完成", result_msg)
                    
                except Exception as e:
                    progress_window.close()
                    messagebox.showerror("错误", f"批量移动失败: {str(e)}")
            
            # 在新线程中执行
            import threading
            thread = threading.Thread(target=move_files)
            thread.daemon = True
            thread.start()
            
        except Exception as e:
            messagebox.showerror("错误", f"批量移动失败: {str(e)}")
    
    def batch_process_javdb_info(self, video_ids):
        """批量处理JAVDB信息获取"""
        try:
            print(f"开始批量处理JAVDB信息，视频数量: {len(video_ids)}")
            
            # 创建进度窗口
            print("正在创建进度窗口...")
            progress_window = ProgressWindow(self.root, "批量JAVDB信息获取", len(video_ids))
            print("进度窗口创建成功")
            
            def fetch_javdb_info():
                try:
                    print("fetch_javdb_info线程开始执行")
                    failed_files = []
                    
                    for i, video_id in enumerate(video_ids):
                        # 检查是否取消
                        if progress_window.cancelled:
                            break
                        
                        # 获取视频信息
                        self.cursor.execute("SELECT file_name, file_path FROM videos WHERE id = ?", (video_id,))
                        result = self.cursor.fetchone()
                        if not result:
                            failed_files.append(f"ID {video_id}: 未找到视频记录")
                            progress_window.update_progress(i + 1, f"ID {video_id}", success=False)
                            continue
                        
                        file_name, file_path = result
                        
                        # 更新进度 - 开始处理
                        progress_window.update_progress(i + 1, file_name)
                        progress_window.update_status(f"正在提取番号: {file_name}")
                        
                        try:
                            # 导入番号提取器
                            from code_extractor import CodeExtractor
                            
                            # 提取番号
                            extractor = CodeExtractor()
                            av_code = extractor.extract_code_from_filename(file_name)
                            
                            if not av_code:
                                failed_files.append(f"{file_name}: 无法提取番号")
                                progress_window.update_progress(i + 1, file_name, success=False)
                                progress_window.update_status(f"失败: 无法提取番号", "red")
                                continue
                            
                            # 更新状态 - 开始爬取
                            progress_window.update_status(f"正在爬取JAVDB信息: {av_code}")
                            
                            # 调用javdb_crawler_single.py获取信息
                            import subprocess
                            import json
                            
                            # 执行javdb_crawler_single.py
                            cmd = ["python", "javdb_crawler_single.py", av_code]
                            process = subprocess.run(cmd, capture_output=True, text=True, 
                                                   cwd=os.path.dirname(os.path.abspath(__file__)), 
                                                   timeout=60)  # 设置60秒超时
                            
                            if process.returncode == 0 and process.stdout:
                                try:
                                    javdb_result = json.loads(process.stdout)
                                    # 检查是否有错误
                                    if "error" in javdb_result:
                                        failed_files.append(f"{file_name}: {javdb_result['error']}")
                                        progress_window.update_progress(i + 1, file_name, success=False)
                                        progress_window.update_status(f"失败: {javdb_result['error']}", "red")
                                        continue
                                except json.JSONDecodeError:
                                    failed_files.append(f"{file_name}: 解析JAVDB返回数据失败")
                                    progress_window.update_progress(i + 1, file_name, success=False)
                                    progress_window.update_status("失败: 解析返回数据失败", "red")
                                    continue
                            else:
                                failed_files.append(f"{file_name}: JAVDB爬取失败")
                                progress_window.update_progress(i + 1, file_name, success=False)
                                progress_window.update_status("失败: JAVDB爬取失败", "red")
                                continue
                            
                            # 更新状态 - 保存到数据库
                            progress_window.update_status(f"正在保存到数据库: {av_code}")
                            
                            # 立即保存JAVDB信息到数据库
                            self.save_javdb_info_to_db(video_id, javdb_result)
                            
                            # 立即提交数据库事务
                            self.conn.commit()
                            
                            # 更新成功状态
                            progress_window.update_progress(i + 1, file_name, success=True)
                            progress_window.update_status(f"成功保存: {av_code}", "green")
                            
                        except subprocess.TimeoutExpired:
                            failed_files.append(f"{file_name}: 获取超时")
                            progress_window.update_progress(i + 1, file_name, success=False)
                            progress_window.update_status("失败: 获取超时", "red")
                        except ImportError:
                            failed_files.append(f"{file_name}: 无法导入番号提取器")
                            progress_window.update_progress(i + 1, file_name, success=False)
                            progress_window.update_status("失败: 无法导入番号提取器", "red")
                        except Exception as e:
                            failed_files.append(f"{file_name}: {str(e)}")
                            progress_window.update_progress(i + 1, file_name, success=False)
                            progress_window.update_status(f"失败: {str(e)}", "red")
                        
                        # 添加延迟避免请求过于频繁
                        import time
                        time.sleep(1)
                    
                    # 处理完成
                    if not progress_window.cancelled:
                        progress_window.update_status("批量处理完成！", "blue")
                        
                        # 刷新视频列表
                        self.root.after(100, self.load_videos)
                        
                        # 显示结果
                        success_count = progress_window.success_count
                        failed_count = progress_window.failed_count
                        
                        result_msg = f"批量JAVDB信息获取完成！\n成功获取: {success_count} 个文件\n失败: {failed_count} 个文件"
                        if failed_files:
                            result_msg += "\n\n失败详情:\n" + "\n".join(failed_files[:10])
                            if len(failed_files) > 10:
                                result_msg += f"\n... 还有 {len(failed_files) - 10} 个失败文件"
                        
                        # 延迟显示结果对话框，让用户看到最终状态
                        self.root.after(2000, lambda: messagebox.showinfo("完成", result_msg))
                        self.root.after(2000, lambda: progress_window.close())
                    else:
                        # 用户取消了操作
                        progress_window.update_status("操作已取消", "orange")
                        success_count = progress_window.success_count
                        self.root.after(1000, lambda: messagebox.showinfo("取消", f"操作已取消\n已成功处理: {success_count} 个文件"))
                        self.root.after(1000, lambda: progress_window.close())
                    
                except Exception as e:
                    progress_window.close()
                    messagebox.showerror("错误", f"批量JAVDB信息获取失败: {str(e)}")
            
            # 在新线程中执行
            print("正在启动处理线程...")
            import threading
            thread = threading.Thread(target=fetch_javdb_info)
            thread.daemon = True
            thread.start()
            print("处理线程已启动")
            
        except Exception as e:
            messagebox.showerror("错误", f"批量JAVDB信息获取失败: {str(e)}")
     
    def play_video_from_context(self, video_id):
        """从右键菜单播放视频"""
        try:
            # 从数据库获取视频信息
            self.cursor.execute("SELECT file_path FROM videos WHERE id = ?", (video_id,))
            result = self.cursor.fetchone()
            if not result:
                messagebox.showerror("错误", "找不到视频信息")
                return
            
            file_path = result[0]
            is_nas_online = self.is_video_online(video_id)
            
            if not is_nas_online:
                messagebox.showwarning("警告", "文件离线，无法播放视频")
                return
                
            if not os.path.exists(file_path):
                messagebox.showerror("错误", "视频文件不存在")
                return
                
            # 跨平台播放
            system = platform.system()
            if system == "Darwin":  # macOS
                subprocess.run(["open", file_path])
            elif system == "Windows":
                os.startfile(file_path)
            elif system == "Linux":
                subprocess.run(["xdg-open", file_path])
            else:
                messagebox.showerror("错误", f"不支持的操作系统: {system}")
        except Exception as e:
            messagebox.showerror("错误", f"播放视频失败: {str(e)}")
    
    def open_file_folder(self, video_id):
        """打开文件所在文件夹并选中文件"""
        try:
            # 从数据库获取视频信息
            self.cursor.execute("SELECT file_path FROM videos WHERE id = ?", (video_id,))
            result = self.cursor.fetchone()
            if not result:
                messagebox.showerror("错误", "找不到视频信息")
                return
            
            file_path = result[0]
            
            # 检查文件是否存在
            if not os.path.exists(file_path):
                messagebox.showerror("错误", "视频文件不存在")
                return
            
            # 根据操作系统使用不同的命令打开文件夹并选中文件
            system = platform.system()
            if system == "Darwin":  # macOS
                subprocess.run(["open", "-R", file_path])
            elif system == "Windows":
                subprocess.run(["explorer", "/select,", file_path])
            elif system == "Linux":
                # Linux下先尝试使用nautilus，如果失败则使用默认文件管理器打开文件夹
                folder_path = os.path.dirname(file_path)
                try:
                    # 尝试使用nautilus选中文件
                    subprocess.run(["nautilus", "--select", file_path], check=True)
                except (subprocess.CalledProcessError, FileNotFoundError):
                    try:
                        # 如果nautilus不可用，尝试使用dolphin
                        subprocess.run(["dolphin", "--select", file_path], check=True)
                    except (subprocess.CalledProcessError, FileNotFoundError):
                        # 如果都不可用，使用默认文件管理器打开文件夹
                        subprocess.run(["xdg-open", folder_path])
            else:
                messagebox.showerror("错误", f"不支持的操作系统: {system}")
        except Exception as e:
            messagebox.showerror("错误", f"打开文件夹失败: {str(e)}")
    
    def delete_file_from_context(self, video_id, file_path):
        """从右键菜单删除文件"""
        if messagebox.askyesno("确认删除", f"确定要删除文件吗？\n{file_path}"):
            try:
                # 删除物理文件
                if os.path.exists(file_path):
                    os.remove(file_path)
                
                # 删除数据库记录
                self.cursor.execute("DELETE FROM videos WHERE id = ?", (video_id,))
                self.conn.commit()
                
                # 刷新列表
                self.filter_videos()
                messagebox.showinfo("成功", "文件已删除")
                
            except Exception as e:
                messagebox.showerror("错误", f"删除文件失败: {str(e)}")
    
    def move_file_to_folder(self, video_id, old_file_path, target_folder):
        """移动文件到指定文件夹"""
        try:
            # 构建新文件路径
            file_name = os.path.basename(old_file_path)
            new_file_path = os.path.join(target_folder, file_name)
            
            # 检查目标文件是否已存在
            if os.path.exists(new_file_path):
                if not messagebox.askyesno("文件已存在", f"目标位置已存在同名文件，是否覆盖？\n{new_file_path}"):
                    return
            
            # 移动文件
            shutil.move(old_file_path, new_file_path)
            
            # 更新数据库记录
            self.cursor.execute(
                "UPDATE videos SET file_path = ?, source_folder = ? WHERE id = ?",
                (new_file_path, target_folder, video_id)
            )
            self.conn.commit()
            
            # 刷新列表
            self.filter_videos()
            messagebox.showinfo("成功", f"文件已移动到: {target_folder}")
            
        except Exception as e:
            messagebox.showerror("错误", f"移动文件失败: {str(e)}")
            
    def clean_actor_data(self):
        """清理演员信息 - 执行merge_duplicate_actors.py脚本"""
        try:
            # 创建选择对话框
            choice_window = tk.Toplevel(self.root)
            choice_window.title("清理演员信息")
            choice_window.geometry("500x400")
            choice_window.transient(self.root)
            choice_window.grab_set()
            
            # 标题
            title_label = ttk.Label(choice_window, text="演员记录清理选项", font=("Arial", 14, "bold"))
            title_label.pack(pady=10)
            
            # 说明文本
            info_text = tk.Text(choice_window, height=8, wrap=tk.WORD, state=tk.DISABLED)
            info_text.pack(fill=tk.X, padx=20, pady=10)
            
            info_content = """演员记录清理工具可以帮助您：

1. 处理逗号分隔的演员名称
2. 基于相同URL合并重复演员记录
3. 基于相同名称合并重复演员记录

建议按顺序执行以获得最佳效果。每个步骤都会先预览，确认后再执行实际操作。"""
            
            info_text.config(state=tk.NORMAL)
            info_text.insert(tk.END, info_content)
            info_text.config(state=tk.DISABLED)
            
            # 选项框架
            options_frame = ttk.LabelFrame(choice_window, text="选择清理操作")
            options_frame.pack(fill=tk.X, padx=20, pady=10)
            
            # 选项变量
            selected_option = tk.StringVar(value="split_comma")
            
            # 选项按钮
            ttk.Radiobutton(options_frame, text="1. 处理逗号分隔名称", variable=selected_option, value="split_comma").pack(anchor=tk.W, padx=10, pady=5)
            ttk.Radiobutton(options_frame, text="2. 基于URL合并重复演员", variable=selected_option, value="merge_url").pack(anchor=tk.W, padx=10, pady=5)
            ttk.Radiobutton(options_frame, text="3. 基于名称合并重复演员", variable=selected_option, value="merge_names").pack(anchor=tk.W, padx=10, pady=5)
            ttk.Radiobutton(options_frame, text="4. 完整清理流程（推荐）", variable=selected_option, value="full_clean").pack(anchor=tk.W, padx=10, pady=5)
            
            # 按钮框架
            button_frame = ttk.Frame(choice_window)
            button_frame.pack(fill=tk.X, padx=20, pady=10)
            
            def execute_cleaning():
                choice_window.destroy()
                self._execute_actor_cleaning(selected_option.get())
            
            ttk.Button(button_frame, text="开始清理", command=execute_cleaning).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="取消", command=choice_window.destroy).pack(side=tk.LEFT, padx=5)
            
        except Exception as e:
            messagebox.showerror("错误", f"打开清理选项失败: {str(e)}")
    
    def _execute_actor_cleaning(self, operation_type):
        """执行演员清理操作"""
        try:
            # 创建进度窗口
            progress_window = tk.Toplevel(self.root)
            progress_window.title("清理演员信息")
            progress_window.geometry("600x500")
            progress_window.transient(self.root)
            progress_window.grab_set()
            
            # 进度条
            progress_var = tk.DoubleVar()
            progress_bar = ttk.Progressbar(progress_window, variable=progress_var, maximum=100, mode='indeterminate')
            progress_bar.pack(fill=tk.X, padx=20, pady=10)
            progress_bar.start()
            
            # 状态标签
            status_var = tk.StringVar(value="准备执行清理操作...")
            status_label = ttk.Label(progress_window, textvariable=status_var)
            status_label.pack(pady=5)
            
            # 日志区域
            log_frame = ttk.LabelFrame(progress_window, text="清理日志")
            log_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
            
            log_text = tk.Text(log_frame, height=15)
            log_scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=log_text.yview)
            log_text.configure(yscrollcommand=log_scrollbar.set)
            log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            # 关闭按钮（初始禁用）
            close_button = ttk.Button(progress_window, text="关闭", command=progress_window.destroy, state=tk.DISABLED)
            close_button.pack(pady=10)
            
            def log_message(message):
                log_text.insert(tk.END, f"{datetime.now().strftime('%H:%M:%S')} - {message}\n")
                log_text.see(tk.END)
                progress_window.update()
            
            def execute_script():
                try:
                    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "merge_duplicate_actors.py")
                    
                    if not os.path.exists(script_path):
                        log_message(f"错误：找不到脚本文件 {script_path}")
                        return
                    
                    # 根据操作类型构建命令
                    if operation_type == "split_comma":
                        commands = [
                            ["python3", script_path, "--split-comma", "--limit", "5"],  # 预览
                            ["python3", script_path, "--split-comma", "--execute"]  # 执行
                        ]
                        operation_name = "处理逗号分隔名称"
                    elif operation_type == "merge_url":
                        commands = [
                            ["python3", script_path, "--merge-url", "--limit", "5"],  # 预览
                            ["python3", script_path, "--merge-url", "--execute"]  # 执行
                        ]
                        operation_name = "基于URL合并重复演员"
                    elif operation_type == "merge_names":
                        commands = [
                            ["python3", script_path, "--merge-names", "--limit", "5"],  # 预览
                            ["python3", script_path, "--merge-names", "--execute"]  # 执行
                        ]
                        operation_name = "基于名称合并重复演员"
                    elif operation_type == "full_clean":
                        commands = [
                            ["python3", script_path, "--split-comma", "--execute"],
                            ["python3", script_path, "--merge-url", "--execute"],
                            ["python3", script_path, "--merge-names", "--execute"]
                        ]
                        operation_name = "完整清理流程"
                    
                    log_message(f"开始执行{operation_name}...")
                    status_var.set(f"正在执行{operation_name}...")
                    
                    for i, cmd in enumerate(commands):
                        if operation_type == "full_clean":
                            step_names = ["处理逗号分隔名称", "基于URL合并", "基于名称合并"]
                            log_message(f"\n步骤 {i+1}/{len(commands)}: {step_names[i]}")
                            status_var.set(f"步骤 {i+1}/{len(commands)}: {step_names[i]}")
                        else:
                            step_name = "预览" if i == 0 else "执行"
                            log_message(f"\n{step_name}阶段:")
                            status_var.set(f"{operation_name} - {step_name}阶段")
                        
                        # 执行命令
                        process = subprocess.Popen(
                            cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            text=True,
                            cwd=os.path.dirname(script_path)
                        )
                        
                        # 实时读取输出
                        while True:
                            output = process.stdout.readline()
                            if output == '' and process.poll() is not None:
                                break
                            if output:
                                log_message(output.strip())
                        
                        # 等待进程完成
                        return_code = process.wait()
                        
                        if return_code != 0:
                            log_message(f"命令执行失败，返回码: {return_code}")
                            break
                        
                        # 对于非完整流程，在预览后询问是否继续
                        if operation_type != "full_clean" and i == 0:
                            if not messagebox.askyesno("确认执行", f"{operation_name}预览完成。\n\n是否继续执行实际操作？"):
                                log_message("用户取消操作")
                                break
                    
                    progress_bar.stop()
                    progress_bar.config(mode='determinate')
                    progress_var.set(100)
                    status_var.set("清理操作完成")
                    log_message(f"\n{operation_name}完成！")
                    
                    # 启用关闭按钮
                    close_button.config(state=tk.NORMAL)
                    
                    # 刷新界面数据
                    self.root.after(1000, self.load_videos)
                    
                    messagebox.showinfo("完成", f"{operation_name}已完成！\n\n请查看日志了解详细信息。")
                    
                except Exception as e:
                    progress_bar.stop()
                    log_message(f"执行失败: {str(e)}")
                    status_var.set("执行失败")
                    close_button.config(state=tk.NORMAL)
                    messagebox.showerror("错误", f"清理操作失败: {str(e)}")
            
            # 在新线程中执行脚本
            threading.Thread(target=execute_script, daemon=True).start()
            
        except Exception as e:
            messagebox.showerror("错误", f"执行清理操作失败: {str(e)}")

    def comprehensive_media_update(self):
        """智能媒体库更新 - 优化版本：先导入所有活跃文件，再处理无效文件和迁移"""
        if not messagebox.askyesno("确认", "这将扫描所有活跃文件夹，添加新文件并更新移动文件的路径，可能需要一些时间。是否继续？"):
            return
            
        # 创建进度窗口
        progress_window = tk.Toplevel(self.root)
        progress_window.title("智能媒体库更新")
        progress_window.geometry("600x400")
        progress_window.transient(self.root)
        progress_window.grab_set()
        
        # 进度条
        progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(progress_window, variable=progress_var, maximum=100)
        progress_bar.pack(fill=tk.X, padx=10, pady=10)
        
        # 状态标签
        status_var = tk.StringVar(value="准备中...")
        status_label = ttk.Label(progress_window, textvariable=status_var)
        status_label.pack(pady=5)
        
        # 统计信息框架
        stats_frame = ttk.LabelFrame(progress_window, text="统计信息")
        stats_frame.pack(fill=tk.X, padx=10, pady=5)
        
        stats_text = tk.Text(stats_frame, height=3, state=tk.DISABLED)
        stats_text.pack(fill=tk.X, padx=5, pady=5)
        
        # 日志文本框
        log_frame = ttk.LabelFrame(progress_window, text="更新日志")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        log_text = tk.Text(log_frame, height=15)
        log_scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=log_text.yview)
        log_text.configure(yscrollcommand=log_scrollbar.set)
        log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        def log_message(message):
            log_text.insert(tk.END, f"{datetime.now().strftime('%H:%M:%S')} - {message}\n")
            log_text.see(tk.END)
            progress_window.update()
        
        def update_stats(scanned=0, new_files=0, updated_files=0, removed_files=0, md5_updated=0):
            stats_text.config(state=tk.NORMAL)
            stats_text.delete(1.0, tk.END)
            stats_text.insert(tk.END, f"已扫描: {scanned} | 新增: {new_files} | 路径更新: {updated_files} | 删除无效: {removed_files} | MD5更新: {md5_updated}")
            stats_text.config(state=tk.DISABLED)
        
        def comprehensive_update():
            try:
                # 统计变量
                scanned_count = 0
                new_files_count = 0
                updated_files_count = 0
                removed_files_count = 0
                md5_updated_count = 0
                
                # 获取所有活跃且在线的文件夹（只处理实际存在的文件夹）
                self.cursor.execute("SELECT folder_path FROM folders WHERE is_active = 1")
                all_folders = [row[0] for row in self.cursor.fetchall()]
                active_folders = []
                # 获取所有配置的文件夹路径（包括离线的），用于检查文件是否在配置范围内
                all_configured_folders = []
                for folder_path in all_folders:
                    if folder_path:
                        all_configured_folders.append(folder_path)
                        if os.path.exists(folder_path):
                            active_folders.append(folder_path)
                            log_message(f"包含在线文件夹: {folder_path}")
                        else:
                            log_message(f"跳过离线文件夹: {folder_path}")
                
                # 第一阶段：扫描所有活跃文件并建立哈希映射
                log_message("第一阶段：扫描所有活跃文件并计算哈希值...")
                
                # 建立文件映射：{文件路径: {size, md5, metadata}}
                active_files_map = {}
                # 建立MD5映射：{md5: [文件路径列表]} - 用于快速查找迁移文件
                md5_to_paths_map = {}
                # 建立文件名映射：{文件名: [文件路径列表]} - 用于快速查找同名文件
                filename_to_paths_map = {}
                
                # 统计总文件数
                total_files_to_scan = 0
                for folder_path in active_folders:
                    for root, dirs, files in os.walk(folder_path):
                        for file in files:
                            if file.lower().endswith(('.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v')):
                                total_files_to_scan += 1
                
                log_message(f"发现 {total_files_to_scan} 个视频文件需要处理")
                
                # 扫描并建立映射
                for folder_path in active_folders:
                    log_message(f"扫描文件夹: {folder_path}")
                    
                    for root, dirs, files in os.walk(folder_path):
                        for file in files:
                            if file.lower().endswith(('.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v')):
                                file_path = os.path.join(root, file)
                                scanned_count += 1
                                
                                progress = (scanned_count / total_files_to_scan) * 60  # 前60%进度用于扫描文件
                                progress_var.set(progress)
                                status_var.set(f"扫描文件 {scanned_count}/{total_files_to_scan}")
                                update_stats(scanned_count, new_files_count, updated_files_count, removed_files_count, md5_updated_count)
                                
                                try:
                                    # 获取文件信息
                                    file_size = os.path.getsize(file_path)
                                    
                                    # 计算MD5哈希值
                                    md5_hash = self.calculate_file_hash(file_path)
                                    
                                    # 解析文件名获取标题和星级
                                    title = self.parse_title_from_filename(file)
                                    stars = self.parse_stars_from_filename(file)
                                    
                                    # 存储文件信息
                                    active_files_map[file_path] = {
                                        'size': file_size,
                                        'md5': md5_hash,
                                        'filename': file,
                                        'title': title,
                                        'stars': stars,
                                        'source_folder': root
                                    }
                                    
                                    # 建立MD5映射
                                    if md5_hash not in md5_to_paths_map:
                                        md5_to_paths_map[md5_hash] = []
                                    md5_to_paths_map[md5_hash].append(file_path)
                                    
                                    # 建立文件名映射
                                    if file not in filename_to_paths_map:
                                        filename_to_paths_map[file] = []
                                    filename_to_paths_map[file].append(file_path)
                                    
                                except Exception as e:
                                    log_message(f"处理文件失败: {file} - {str(e)}")
                                
                                # 每处理100个文件更新一次界面
                                if scanned_count % 100 == 0:
                                    progress_window.update()
                
                log_message(f"文件扫描完成，共处理 {len(active_files_map)} 个有效文件")
                
                # 第二阶段：处理数据库中的现有记录
                log_message("第二阶段：检查数据库中的现有文件...")
                self.cursor.execute("SELECT id, file_path, source_folder, md5_hash FROM videos")
                existing_videos = self.cursor.fetchall()
                
                total_existing = len(existing_videos)
                log_message(f"数据库中共有 {total_existing} 个文件记录")
                
                for i, (video_id, file_path, source_folder, md5_hash) in enumerate(existing_videos):
                    progress = 60 + (i / total_existing) * 20  # 60%-80%进度用于检查现有文件
                    progress_var.set(progress)
                    status_var.set(f"检查现有文件 {i+1}/{total_existing}")
                    update_stats(scanned_count, new_files_count, updated_files_count, removed_files_count, md5_updated_count)
                    
                    if file_path in active_files_map:
                        # 文件仍然存在于活跃文件夹中
                        if not md5_hash:
                            # 更新MD5哈希值
                            new_md5 = active_files_map[file_path]['md5']
                            self.cursor.execute("UPDATE videos SET md5_hash = ? WHERE id = ?", (new_md5, video_id))
                            md5_updated_count += 1
                            log_message(f"更新MD5: {os.path.basename(file_path)}")
                        # 从映射中移除，表示已处理
                        del active_files_map[file_path]
                    else:
                        # 文件不在原位置，尝试查找迁移
                        file_name = os.path.basename(file_path)
                        found_path = None
                        
                        # 优先使用MD5哈希查找（最准确）
                        if md5_hash and md5_hash in md5_to_paths_map:
                            # 在MD5映射中找到匹配的文件
                            potential_paths = md5_to_paths_map[md5_hash]
                            if len(potential_paths) == 1:
                                # 只有一个匹配，直接使用
                                found_path = potential_paths[0]
                            else:
                                # 多个匹配，优先选择同名文件
                                for path in potential_paths:
                                    if os.path.basename(path) == file_name:
                                        found_path = path
                                        break
                                # 如果没有同名文件，使用第一个
                                if not found_path:
                                    found_path = potential_paths[0]
                        
                        # 如果MD5查找失败，尝试文件名查找
                        if not found_path and file_name in filename_to_paths_map:
                            potential_paths = filename_to_paths_map[file_name]
                            if len(potential_paths) == 1:
                                found_path = potential_paths[0]
                            else:
                                # 多个同名文件，需要进一步验证（如果有MD5的话）
                                if md5_hash:
                                    for path in potential_paths:
                                        if active_files_map[path]['md5'] == md5_hash:
                                            found_path = path
                                            break
                                if not found_path:
                                    found_path = potential_paths[0]  # 使用第一个作为备选
                        
                        if found_path:
                            # 检查新路径是否已存在于数据库中
                            self.cursor.execute("SELECT id FROM videos WHERE file_path = ? AND id != ?", (found_path, video_id))
                            existing = self.cursor.fetchone()
                            
                            if existing:
                                # 删除当前记录（避免重复）
                                self.cursor.execute("DELETE FROM videos WHERE id = ?", (video_id,))
                                removed_files_count += 1
                                log_message(f"删除重复记录: {file_name}")
                            else:
                                # 更新路径和相关信息，保留原有的评分、标签等元数据
                                file_info = active_files_map[found_path]
                                new_source_folder = file_info['source_folder']
                                new_md5 = file_info['md5']
                                new_file_name = file_info['filename']
                                new_file_size = file_info['size']
                                
                                # 只更新文件系统相关的字段，保留用户设置的评分、标签等
                                self.cursor.execute(
                                    "UPDATE videos SET file_path = ?, file_name = ?, file_size = ?, source_folder = ?, md5_hash = ? WHERE id = ?",
                                    (found_path, new_file_name, new_file_size, new_source_folder, new_md5, video_id)
                                )
                                updated_files_count += 1
                                log_message(f"文件移动更新: {file_name} -> {found_path} (保留评分和标签)")
                            
                            # 从映射中移除，表示已处理
                            if found_path in active_files_map:
                                del active_files_map[found_path]
                        else:
                            # 检查文件是否在任何配置的文件夹范围内
                            file_folder = os.path.dirname(file_path)
                            is_from_configured_folder = any(file_folder.startswith(configured_folder) for configured_folder in all_configured_folders)
                            is_from_online_folder = any(file_folder.startswith(online_folder) for online_folder in active_folders)
                            
                            if not is_from_configured_folder:
                                # 删除不在任何配置文件夹范围内的文件记录
                                self.cursor.execute("DELETE FROM videos WHERE id = ?", (video_id,))
                                removed_files_count += 1
                                log_message(f"删除不在配置范围内的记录: {file_name} (路径: {file_path})")
                            elif is_from_online_folder:
                                # 删除来自在线文件夹但不存在的文件记录
                                self.cursor.execute("DELETE FROM videos WHERE id = ?", (video_id,))
                                removed_files_count += 1
                                log_message(f"删除无效记录: {file_name}")
                            else:
                                # 跳过离线文件夹中的文件
                                log_message(f"跳过离线文件夹中的文件: {file_name}")
                    
                    # 每处理100个文件提交一次
                    if i % 100 == 0:
                        self.conn.commit()
                
                # 第三阶段：添加剩余的新文件
                log_message("\n第三阶段：添加新文件...")
                
                remaining_files = list(active_files_map.keys())
                total_new_files = len(remaining_files)
                log_message(f"发现 {total_new_files} 个新文件需要添加到数据库")
                
                for i, file_path in enumerate(remaining_files):
                    progress = 80 + (i / total_new_files) * 20 if total_new_files > 0 else 100  # 80%-100%进度用于添加新文件
                    progress_var.set(progress)
                    status_var.set(f"添加新文件 {i+1}/{total_new_files}")
                    update_stats(scanned_count, new_files_count, updated_files_count, removed_files_count, md5_updated_count)
                    
                    try:
                        file_info = active_files_map[file_path]
                        
                        # 获取视频时长和分辨率信息
                        duration, resolution = self.get_video_info(file_path)
                        
                        # 获取文件创建时间
                        file_created_time = None
                        try:
                            stat = os.stat(file_path)
                            file_created_time = datetime.fromtimestamp(stat.st_birthtime if hasattr(stat, 'st_birthtime') else stat.st_ctime)
                        except:
                            pass
                        
                        # 插入数据库
                        self.cursor.execute("""
                            INSERT INTO videos (file_path, file_name, title, stars, file_size, source_folder, md5_hash, duration, resolution, file_created_time, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            file_path, 
                            file_info['filename'], 
                            file_info['title'], 
                            file_info['stars'], 
                            file_info['size'], 
                            file_info['source_folder'], 
                            file_info['md5'],
                            duration,
                            resolution,
                            file_created_time,
                            datetime.now()
                        ))
                        
                        new_files_count += 1
                        duration_str = self.format_duration(duration) if duration else "未知"
                        resolution_str = resolution if resolution else "未知"
                        log_message(f"新增文件: {file_info['filename']} (时长: {duration_str}, 分辨率: {resolution_str})")
                        
                    except Exception as e:
                        log_message(f"添加文件失败: {file_info['filename']} - {str(e)}")
                    
                    # 每处理100个文件提交一次
                    if i % 100 == 0:
                        self.conn.commit()
                
                # 最终提交
                self.conn.commit()
                
                progress_var.set(100)
                status_var.set("完成")
                update_stats(scanned_count, new_files_count, updated_files_count, removed_files_count, md5_updated_count)
                
                log_message(f"\n智能媒体库更新完成！")
                log_message(f"总扫描文件: {scanned_count}")
                log_message(f"新增文件: {new_files_count}")
                log_message(f"路径更新: {updated_files_count}")
                log_message(f"删除无效: {removed_files_count}")
                log_message(f"MD5更新: {md5_updated_count}")
                
                # 先显示完成对话框，避免卡顿
                self.root.after(0, lambda: messagebox.showinfo("完成", 
                    f"智能媒体库更新完成！\n\n"
                    f"总扫描文件: {scanned_count}\n"
                    f"新增文件: {new_files_count}\n"
                    f"路径更新: {updated_files_count}\n"
                    f"删除无效记录: {removed_files_count}\n"
                    f"MD5更新: {md5_updated_count}"))
                
                # 在对话框显示后异步刷新视频列表
                self.root.after(100, self.load_videos)
                
            except Exception as e:
                error_msg = str(e)
                log_message(f"错误: {error_msg}")
                self.root.after(0, lambda: messagebox.showerror("错误", f"智能媒体库更新时出错: {error_msg}"))
        
        # 在新线程中执行更新
        threading.Thread(target=comprehensive_update, daemon=True).start()
    
    def auto_tag_selected_videos(self):
        """为选中的视频自动打标签"""
        selected_items = self.video_tree.selection()
        if not selected_items:
            messagebox.showwarning("警告", "请先选择要打标签的视频")
            return
            
        # 获取选中视频的文件路径
        video_paths = []
        for item in selected_items:
            video_id = self.video_tree.item(item)['tags'][0]
            self.cursor.execute("SELECT file_path FROM videos WHERE id = ?", (video_id,))
            result = self.cursor.fetchone()
            if result and self.is_video_online(video_id):  # 只处理在线文件
                video_paths.append(result[0])
        
        if not video_paths:
            messagebox.showwarning("警告", "没有找到可处理的在线视频文件")
            return
            
        # 调用视频内容分析器
        self.run_video_content_analyzer(video_paths)
    
    def batch_auto_tag_all(self):
        """批量自动更新所有标签"""
        result = messagebox.askyesno("确认", "此操作将为数据库中所有视频重新生成标签，可能需要较长时间。\n\n是否继续？")
        if not result:
            return
            
        # 调用视频内容分析器的全部更新模式
        self.run_video_content_analyzer_mode("full_update")
    
    def batch_auto_tag_no_tags(self):
        """批量标注没有标签的文件"""
        # 调用视频内容分析器的无标签更新模式
        self.run_video_content_analyzer_mode("no_tags_update")
    
    def run_video_content_analyzer(self, video_paths):
        """运行视频内容分析器处理指定文件"""
        try:
            # 导入视频内容分析器
            import video_content_analyzer
            
            # 创建分析器实例，使用相同的数据库路径
            analyzer = video_content_analyzer.VideoContentAnalyzer(db_path="media_library.db")
            
            def analyze_videos():
                try:
                    processed = 0
                    failed = 0
                    
                    for i, video_path in enumerate(video_paths, 1):
                        try:
                            print(f"[{i}/{len(video_paths)}] 分析视频: {os.path.basename(video_path)}")
                            
                            if not os.path.exists(video_path):
                                print(f"   ✗ 文件不存在，跳过")
                                failed += 1
                                continue
                            
                            # 分析视频内容
                            analysis_result = analyzer.analyze_video_content(video_path, min_frames=100, max_interval=10, max_frames=300)
                            
                            if 'error' in analysis_result:
                                print(f"   ✗ 分析失败: {analysis_result['error']}")
                                failed += 1
                                continue
                            
                            generated_tags = analysis_result['generated_tags']
                            print(f"   ✓ 分析完成")
                            print(f"   生成标签：{', '.join(generated_tags) if generated_tags else '无'}")
                            
                            # 查找视频记录
                            self.cursor.execute("SELECT id, tags FROM videos WHERE file_path = ?", (video_path,))
                            video_record = self.cursor.fetchone()
                            
                            if not video_record:
                                print(f"   ⚠ 该视频不在数据库中，无法更新标签")
                                continue
                            
                            video_id, existing_tags = video_record
                            print(f"   现有标签：{existing_tags or '无'}")
                            
                            # 更新标签
                            if generated_tags:
                                # 获取现有标签
                                existing_set = set([tag.strip() for tag in (existing_tags or '').split(',') if tag.strip()])
                                new_set = set(generated_tags)
                                all_tags = existing_set.union(new_set)
                                
                                # 更新数据库
                                final_tags = ', '.join(sorted(all_tags))
                                self.cursor.execute(
                                    "UPDATE videos SET tags = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                                    (final_tags, video_id)
                                )
                                self.conn.commit()
                                
                                print(f"   ✓ 标签已更新: {final_tags}")
                                processed += 1
                            else:
                                print(f"   - 未生成新标签")
                                
                        except Exception as e:
                            print(f"   ✗ 处理失败: {str(e)}")
                            failed += 1
                    
                    # 刷新界面
                    self.root.after(0, self.load_videos)
                    result_msg = f"视频标签分析完成！\n\n成功处理: {processed} 个\n失败: {failed} 个"
                    self.root.after(0, lambda: messagebox.showinfo("完成", result_msg))
                    
                except Exception as e:
                    error_msg = str(e)
                    self.root.after(0, lambda: messagebox.showerror("错误", f"视频分析时出错: {error_msg}"))
            
            # 在新线程中运行分析
            threading.Thread(target=analyze_videos, daemon=True).start()
            
        except ImportError:
            messagebox.showerror("错误", "无法导入视频内容分析器模块")
        except Exception as e:
            messagebox.showerror("错误", f"启动视频分析时出错: {str(e)}")
    
    def run_video_content_analyzer_with_progress(self, video_paths):
        """运行视频内容分析器处理指定文件（带进度条）"""
        try:
            # 导入视频内容分析器
            import video_content_analyzer
            
            # 创建进度窗口
            progress_window = ProgressWindow(self.root, "批量自动标签", len(video_paths))
            
            # 创建分析器实例，使用相同的数据库路径
            analyzer = video_content_analyzer.VideoContentAnalyzer(db_path="media_library.db")
            
            def analyze_videos():
                try:
                    processed = 0
                    failed = 0
                    
                    for i, video_path in enumerate(video_paths):
                        # 检查是否取消
                        if progress_window.cancelled:
                            break
                        
                        try:
                            # 更新进度（在GUI线程中安全更新）
                            file_name = os.path.basename(video_path)
                            progress_num = i + 1
                            def update_progress(p=progress_num, f=file_name):
                                progress_window.update_progress(p, f"正在分析: {f}")
                            self.root.after(0, update_progress)
                            
                            if not os.path.exists(video_path):
                                print(f"[{i+1}/{len(video_paths)}] ✗ 文件不存在，跳过: {file_name}")
                                failed += 1
                                continue
                            
                            print(f"[{i+1}/{len(video_paths)}] 分析视频: {file_name}")
                            
                            # 分析视频内容
                            analysis_result = analyzer.analyze_video_content(video_path, min_frames=100, max_interval=10, max_frames=300)
                            
                            if 'error' in analysis_result:
                                print(f"   ✗ 分析失败: {analysis_result['error']}")
                                failed += 1
                                continue
                            
                            generated_tags = analysis_result['generated_tags']
                            print(f"   ✓ 分析完成")
                            print(f"   生成标签：{', '.join(generated_tags) if generated_tags else '无'}")
                            
                            # 查找视频记录
                            self.cursor.execute("SELECT id, tags FROM videos WHERE file_path = ?", (video_path,))
                            video_record = self.cursor.fetchone()
                            
                            if not video_record:
                                print(f"   ⚠ 该视频不在数据库中，无法更新标签")
                                continue
                            
                            video_id, existing_tags = video_record
                            print(f"   现有标签：{existing_tags or '无'}")
                            
                            # 更新标签
                            if generated_tags:
                                # 获取现有标签
                                existing_set = set([tag.strip() for tag in (existing_tags or '').split(',') if tag.strip()])
                                new_set = set(generated_tags)
                                all_tags = existing_set.union(new_set)
                                
                                # 更新数据库
                                final_tags = ', '.join(sorted(all_tags))
                                self.cursor.execute(
                                    "UPDATE videos SET tags = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                                    (final_tags, video_id)
                                )
                                self.conn.commit()
                                
                                print(f"   ✓ 标签已更新: {final_tags}")
                                processed += 1
                            else:
                                print(f"   - 未生成新标签")
                                
                        except Exception as e:
                            print(f"   ✗ 处理失败: {str(e)}")
                            failed += 1
                    
                    # 关闭进度窗口（在GUI线程中安全关闭）
                    self.root.after(0, progress_window.close)
                    
                    # 刷新界面和显示结果（在GUI线程中安全执行）
                    if not progress_window.cancelled:
                        self.root.after(0, self.load_videos)
                        result_msg = f"视频标签分析完成！\n\n成功处理: {processed} 个\n失败: {failed} 个"
                        self.root.after(0, lambda: messagebox.showinfo("完成", result_msg))
                    
                except Exception as e:
                    # 关闭进度窗口并显示错误（在GUI线程中安全执行）
                    self.root.after(0, progress_window.close)
                    error_msg = str(e)
                    self.root.after(0, lambda: messagebox.showerror("错误", f"视频分析时出错: {error_msg}"))
            
            # 在新线程中运行分析
            threading.Thread(target=analyze_videos, daemon=True).start()
            
        except ImportError:
            messagebox.showerror("错误", "无法导入视频内容分析器模块")
        except Exception as e:
            messagebox.showerror("错误", f"启动视频分析时出错: {str(e)}")
    
    def run_video_content_analyzer_mode(self, mode):
        """运行视频内容分析器的指定模式"""
        try:
            # 导入视频内容分析器
            import video_content_analyzer
            
            # 创建分析器实例，使用相同的数据库路径
            analyzer = video_content_analyzer.VideoContentAnalyzer(db_path="media_library.db")
            
            # 创建进度窗口
            if mode == "full_update":
                title = "批量更新所有标签"
            elif mode == "no_tags_update":
                title = "批量更新无标签文件"
            else:
                title = "批量处理进度"
                
            progress_window = ProgressWindow(self.root, title, 0)  # 初始化为0，稍后更新
            
            def progress_callback(current, total, message):
                """进度回调函数"""
                if not progress_window.is_cancelled():
                    progress_window.update_progress(current + 1, message)
            
            def analyze_videos():
                try:
                    if mode == "full_update":
                        # 获取所有视频
                        self.cursor.execute("SELECT id, file_path, title, tags FROM videos")
                        all_videos = self.cursor.fetchall()
                        # 过滤出文件存在的视频
                        videos = [(vid, path, title, tags) for vid, path, title, tags in all_videos 
                                if os.path.exists(path) and os.path.isfile(path)]
                    elif mode == "no_tags_update":
                        # 获取没有标签的视频
                        self.cursor.execute("SELECT id, file_path, title, tags FROM videos WHERE (tags IS NULL OR tags = '')")
                        all_videos = self.cursor.fetchall()
                        # 过滤出文件存在的视频
                        videos = [(vid, path, title, tags) for vid, path, title, tags in all_videos 
                                if os.path.exists(path) and os.path.isfile(path)]
                    else:
                        videos = []
                    
                    if not videos:
                        self.root.after(0, lambda: messagebox.showinfo("信息", "没有找到需要处理的视频"))
                        self.root.after(0, progress_window.close)
                        return
                    
                    # 更新进度窗口的总数
                    progress_window.total_items = len(videos)
                    progress_window.progress_text.config(text=f"0/{len(videos)} (0%)")
                    
                    processed = 0
                    failed = 0
                    updated = 0
                    
                    for i, (video_id, file_path, title, current_tags) in enumerate(videos, 1):
                        if progress_window.is_cancelled():
                            break
                            
                        current_file = os.path.basename(file_path)
                        progress_callback(i-1, len(videos), f"正在处理: {current_file}")
                        
                        if not os.path.exists(file_path):
                            print(f"文件不存在，跳过: {current_file}")
                            failed += 1
                            progress_window.update_progress(i, f"跳过: {current_file}", success=False)
                            continue
                        
                        try:
                            # 分析视频内容
                            analysis_result = analyzer.analyze_video_content(file_path, min_frames=100, max_interval=10, max_frames=300)
                            
                            if 'error' in analysis_result:
                                print(f"分析失败: {current_file} - {analysis_result['error']}")
                                failed += 1
                                progress_window.update_progress(i, f"失败: {current_file}", success=False)
                                continue
                            
                            processed += 1
                            generated_tags = analysis_result['generated_tags']
                            
                            if generated_tags:
                                # 合并现有标签和新标签
                                existing_tags = set(tag.strip() for tag in (current_tags or '').split(',') if tag.strip())
                                new_tags = set(generated_tags)
                                all_tags = existing_tags.union(new_tags)
                                
                                # 更新标签
                                tags_str = ', '.join(sorted(all_tags))
                                self.cursor.execute("UPDATE videos SET tags = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (tags_str, video_id))
                                self.conn.commit()
                                
                                print(f"已更新标签: {current_file} - {', '.join(generated_tags)}")
                                updated += 1
                                progress_window.update_progress(i, f"已完成: {current_file}", success=True)
                            else:
                                print(f"未生成标签: {current_file}")
                                progress_window.update_progress(i, f"已完成: {current_file}", success=True)
                                
                        except Exception as e:
                            print(f"处理失败: {current_file} - {str(e)}")
                            failed += 1
                            progress_window.update_progress(i, f"错误: {current_file}", success=False)
                    
                    # 等待一下让用户看到完成状态
                    time.sleep(1)
                    
                    # 刷新界面
                    if not progress_window.is_cancelled():
                        self.root.after(0, self.load_videos)
                        result_msg = f"批量视频标签分析完成！\n\n总数: {len(videos)}\n成功分析: {processed}\n更新标签: {updated}\n失败: {failed}"
                        self.root.after(0, lambda: messagebox.showinfo("完成", result_msg))
                    
                    # 关闭进度窗口
                    self.root.after(0, progress_window.close)
                    
                except Exception as e:
                    error_msg = str(e)
                    self.root.after(0, lambda: messagebox.showerror("错误", f"批量视频分析时出错: {error_msg}"))
                    self.root.after(0, progress_window.close)
            
            # 在新线程中运行分析
            threading.Thread(target=analyze_videos, daemon=True).start()
            
        except ImportError:
            messagebox.showerror("错误", "无法导入视频内容分析器模块")
        except Exception as e:
            messagebox.showerror("错误", f"启动批量视频分析时出错: {str(e)}")

    def save_javdb_info_to_db(self, video_id, javdb_info):
        """保存JAVDB信息到数据库"""
        try:
            # 读取本地图片文件并转换为二进制数据
            cover_image_data = None
            local_image_path = javdb_info.get('local_image_path', '')
            if local_image_path and os.path.exists(local_image_path):
                try:
                    with open(local_image_path, 'rb') as f:
                        cover_image_data = f.read()
                    print(f"Successfully read image data from: {local_image_path}")
                except Exception as e:
                    print(f"Failed to read image file {local_image_path}: {e}")
            
            # 检查是否已存在该video_id的JAVDB信息
            self.cursor.execute("SELECT id FROM javdb_info WHERE video_id = ?", (video_id,))
            existing_record = self.cursor.fetchone()
            
            if existing_record:
                # 更新已有记录
                javdb_info_id = existing_record[0]
                self.cursor.execute("""
                    UPDATE javdb_info SET 
                    javdb_code = ?, javdb_url = ?, javdb_title = ?, release_date = ?, duration = ?,
                    studio = ?, score = ?, cover_url = ?, local_cover_path = ?, cover_image_data = ?,
                    magnet_links = ?, updated_at = datetime('now')
                    WHERE video_id = ?
                """, (
                    javdb_info.get('video_id', ''),
                    javdb_info.get('detail_url', ''),
                    javdb_info.get('title', ''),
                    javdb_info.get('release_date', ''),
                    javdb_info.get('duration', ''),
                    javdb_info.get('studio', ''),
                    float(javdb_info.get('rating', 0)) if javdb_info.get('rating') and javdb_info.get('rating') != 'N/A' else None,
                    javdb_info.get('cover_image_url', ''),
                    javdb_info.get('local_image_path', ''),
                    cover_image_data,
                    json.dumps(javdb_info.get('magnet_links', []), ensure_ascii=False),
                    video_id
                ))
                
                # 清除旧的标签和演员关联
                self.cursor.execute("DELETE FROM javdb_info_tags WHERE javdb_info_id = ?", (javdb_info_id,))
                self.cursor.execute("DELETE FROM video_actors WHERE video_id = ?", (video_id,))
                print(f"Updated existing JAVDB record for video_id: {video_id}")
            else:
                # 插入新记录
                self.cursor.execute("""
                    INSERT INTO javdb_info 
                    (video_id, javdb_code, javdb_url, javdb_title, release_date, duration, 
                     studio, score, cover_url, local_cover_path, cover_image_data, magnet_links, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                """, (
                    video_id,
                    javdb_info.get('video_id', ''),
                    javdb_info.get('detail_url', ''),
                    javdb_info.get('title', ''),
                    javdb_info.get('release_date', ''),
                    javdb_info.get('duration', ''),
                    javdb_info.get('studio', ''),
                    float(javdb_info.get('rating', 0)) if javdb_info.get('rating') and javdb_info.get('rating') != 'N/A' else None,
                    javdb_info.get('cover_image_url', ''),
                    javdb_info.get('local_image_path', ''),
                    cover_image_data,
                    json.dumps(javdb_info.get('magnet_links', []), ensure_ascii=False)
                ))
                javdb_info_id = self.cursor.lastrowid
                print(f"Inserted new JAVDB record for video_id: {video_id}")
            
            # 获取javdb_info记录的ID
            
            # 保存标签信息
            tags = javdb_info.get('tags', [])
            if tags:
                for tag_name in tags:
                    if tag_name.strip():
                        # 先插入或获取标签
                        self.cursor.execute("""
                            INSERT OR IGNORE INTO javdb_tags (tag_name)
                            VALUES (?)
                        """, (tag_name.strip(),))
                        
                        # 获取标签ID
                        self.cursor.execute("SELECT id FROM javdb_tags WHERE tag_name = ?", (tag_name.strip(),))
                        tag_result = self.cursor.fetchone()
                        if tag_result:
                            tag_id = tag_result[0]
                            
                            # 建立javdb信息和标签的关联
                            self.cursor.execute("""
                                INSERT OR IGNORE INTO javdb_info_tags (javdb_info_id, tag_id)
                                VALUES (?, ?)
                            """, (javdb_info_id, tag_id))
            
            # 保存演员信息
            actors = javdb_info.get('actors', [])
            if actors:
                for actor in actors:
                    actor_name = actor.get('name', '').strip()
                    actor_link = actor.get('link', '')
                    
                    if actor_name:
                        # 先插入或更新演员信息
                        self.cursor.execute("""
                            INSERT OR IGNORE INTO actors (name, profile_url)
                            VALUES (?, ?)
                        """, (actor_name, actor_link))
                        
                        # 获取演员ID
                        self.cursor.execute("SELECT id FROM actors WHERE name = ?", (actor_name,))
                        actor_result = self.cursor.fetchone()
                        if actor_result:
                            actor_id = actor_result[0]
                            
                            # 建立视频和演员的关联
                            self.cursor.execute("""
                                INSERT OR IGNORE INTO video_actors (video_id, actor_id)
                                VALUES (?, ?)
                            """, (video_id, actor_id))
            
            self.conn.commit()
            print(f"已保存JAVDB信息到数据库: {javdb_info.get('title', 'Unknown')}")
            
        except Exception as e:
            print(f"保存JAVDB信息到数据库失败: {str(e)}")
            raise

    def fetch_current_javdb_info(self):
        """获取当前选中视频的JAVDB信息"""
        if not self.current_video:
            messagebox.showwarning("警告", "请先选择一个视频")
            return
        
        video_id = self.current_video[0]  # 视频ID是第一个字段
        self.fetch_javdb_info(video_id)
        
        # 获取完成后刷新详情显示
        self.root.after(2000, lambda: self.load_javdb_details(video_id))
        
    def fetch_javdb_info(self, video_id):
        """获取JAVDB信息"""
        try:
            # 获取视频文件信息
            self.cursor.execute("SELECT file_path, file_name FROM videos WHERE id = ?", (video_id,))
            result = self.cursor.fetchone()
            if not result:
                messagebox.showerror("错误", "未找到视频记录")
                return
                
            file_path, file_name = result
            
            # 导入番号提取器
            from code_extractor import CodeExtractor
            
            # 提取番号
            extractor = CodeExtractor()
            av_code = extractor.extract_code_from_filename(file_name)
            
            if not av_code:
                messagebox.showwarning("警告", f"无法从文件名 '{file_name}' 中提取番号")
                return
            
            # 确认对话框
            if not messagebox.askyesno("确认", f"检测到番号: {av_code}\n\n是否获取JAVDB信息？"):
                return
            
            # 创建进度窗口
            progress_window = tk.Toplevel(self.root)
            progress_window.title("JAVDB信息获取")
            progress_window.geometry("400x200")
            progress_window.transient(self.root)
            progress_window.grab_set()
            
            # 进度显示
            progress_label = ttk.Label(progress_window, text=f"正在获取 {av_code} 的信息...")
            progress_label.pack(pady=20)
            
            progress_bar = ttk.Progressbar(progress_window, length=300, mode='indeterminate')
            progress_bar.pack(pady=10)
            progress_bar.start()
            
            status_label = ttk.Label(progress_window, text="初始化...")
            status_label.pack(pady=10)
            
            def fetch_thread():
                try:
                    # 更新状态
                    self.root.after(0, lambda: status_label.config(text="正在搜索视频..."))
                    
                    # 调用javdb_crawler_single.py获取信息
                    import subprocess
                    import json
                    
                    # 执行javdb_crawler_single.py
                    cmd = ["python", "javdb_crawler_single.py", av_code]
                    process = subprocess.run(cmd, capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__)))
                    
                    if process.returncode == 0 and process.stdout:
                        try:
                            result = json.loads(process.stdout)
                            # 检查是否有错误
                            if "error" in result:
                                result = None
                        except json.JSONDecodeError:
                            result = None
                    else:
                        result = None
                    
                    if result:
                        self.root.after(0, lambda: status_label.config(text="正在保存到数据库..."))
                        
                        # 保存JAVDB信息到数据库
                        self.save_javdb_info_to_db(video_id, result)
                        
                        self.root.after(0, lambda: status_label.config(text="获取完成"))
                        time.sleep(1)
                        
                        # 关闭进度窗口并显示结果
                        self.root.after(0, progress_window.destroy)
                        self.root.after(100, lambda: messagebox.showinfo("完成", f"已成功获取并保存 {av_code} 的JAVDB信息\n\n标题: {result.get('title', 'N/A')}\n发行日期: {result.get('release_date', 'N/A')}\n评分: {result.get('rating', 'N/A')}"))
                        
                        # 刷新视频列表和详情显示
                        self.root.after(200, self.load_videos)
                        self.root.after(300, lambda: self.load_javdb_details(video_id))
                    else:
                        self.root.after(0, progress_window.destroy)
                        self.root.after(100, lambda: messagebox.showwarning("警告", f"未能获取到番号 {av_code} 的信息\n\n可能原因：\n1. 网络连接问题\n2. JAVDB上没有该番号\n3. 需要登录验证"))
                    
                except Exception as e:
                    error_msg = f"获取JAVDB信息失败: {str(e)}"
                    self.root.after(0, progress_window.destroy)
                    self.root.after(100, lambda: messagebox.showerror("错误", error_msg))
            
            # 在后台线程中执行获取
            thread = threading.Thread(target=fetch_thread, daemon=True)
            thread.start()
            
        except ImportError:
            messagebox.showerror("错误", "无法导入番号提取器模块")
        except Exception as e:
            messagebox.showerror("错误", f"获取JAVDB信息失败: {str(e)}")

    def import_videos(self):
        """导入视频文件功能"""
        try:
            # 创建导入对话框
            import_window = tk.Toplevel(self.root)
            import_window.title("导入视频文件")
            import_window.resizable(True, True)
            import_window.transient(self.root)
            import_window.grab_set()
            
            # 调整窗口大小以适应所有内容
            import_window.update_idletasks()
            x = (import_window.winfo_screenwidth() // 2) - (650 // 2)
            y = (import_window.winfo_screenheight() // 2) - (650 // 2)
            import_window.geometry(f"650x650+{x}+{y}")
            
            # 创建主框架和滚动条
            main_frame = ttk.Frame(import_window)
            main_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            # 源文件选择区域
            source_frame = ttk.LabelFrame(main_frame, text="选择源文件", padding=10)
            source_frame.pack(fill="both", expand=True, pady=(0, 10))
            
            self.selected_files = []
            self.selected_folders = []
            
            # 文件列表显示
            files_frame = ttk.Frame(source_frame)
            files_frame.pack(fill="both", expand=True)
            
            files_listbox = tk.Listbox(files_frame, height=8)
            files_scrollbar = ttk.Scrollbar(files_frame, orient="vertical", command=files_listbox.yview)
            files_listbox.configure(yscrollcommand=files_scrollbar.set)
            
            files_listbox.pack(side="left", fill="both", expand=True)
            files_scrollbar.pack(side="right", fill="y")
            
            # 按钮区域
            buttons_frame = ttk.Frame(source_frame)
            buttons_frame.pack(fill="x", pady=(10, 0))
            
            def add_files():
                files = filedialog.askopenfilenames(
                    title="选择视频文件",
                    filetypes=[("视频文件", "*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm *.m4v"), ("所有文件", "*.*")]
                )
                for file in files:
                    if file not in self.selected_files and os.path.exists(file):
                        self.selected_files.append(file)
                        files_listbox.insert(tk.END, f"文件: {os.path.basename(file)}")
            
            def add_folders():
                folder = filedialog.askdirectory(title="选择文件夹")
                if folder and folder not in self.selected_folders and os.path.exists(folder):
                    self.selected_folders.append(folder)
                    files_listbox.insert(tk.END, f"文件夹: {os.path.basename(folder)}")
            
            def clear_selection():
                self.selected_files.clear()
                self.selected_folders.clear()
                files_listbox.delete(0, tk.END)
            
            ttk.Button(buttons_frame, text="添加文件", command=add_files).pack(side="left", padx=(0, 5))
            ttk.Button(buttons_frame, text="添加文件夹", command=add_folders).pack(side="left", padx=5)
            ttk.Button(buttons_frame, text="清空", command=clear_selection).pack(side="left", padx=5)
            
            # 目标文件夹选择 - 改为下拉菜单
            dest_frame = ttk.LabelFrame(main_frame, text="选择目标文件夹", padding=10)
            dest_frame.pack(fill="x", pady=(0, 10))
            
            # 获取媒体库文件夹列表
            self.cursor.execute("SELECT DISTINCT folder_path FROM folders WHERE is_active = 1 ORDER BY folder_path")
            available_folders = [row[0] for row in self.cursor.fetchall()]
            
            self.target_folder = tk.StringVar()
            
            # 如果有可用文件夹，设置默认值为第一个
            if available_folders:
                self.target_folder.set(available_folders[0])
            
            dest_combobox = ttk.Combobox(dest_frame, textvariable=self.target_folder, values=available_folders, state="readonly")
            dest_combobox.pack(side="left", fill="x", expand=True, padx=(0, 5))
            
            def browse_custom_folder():
                folder = filedialog.askdirectory(title="选择自定义目标文件夹")
                if folder:
                    # 将自定义文件夹添加到下拉列表
                    current_values = list(dest_combobox['values'])
                    if folder not in current_values:
                        current_values.append(folder)
                        dest_combobox['values'] = current_values
                    self.target_folder.set(folder)
            
            ttk.Button(dest_frame, text="自定义", command=browse_custom_folder).pack(side="right")
            
            # 选项设置
            options_frame = ttk.LabelFrame(main_frame, text="导入选项", padding=10)
            options_frame.pack(fill="x", pady=(0, 10))
            
            self.check_playable = tk.BooleanVar(value=True)
            self.check_md5 = tk.BooleanVar(value=True)
            self.rename_files = tk.BooleanVar(value=True)
            
            ttk.Checkbutton(options_frame, text="检查视频完整性", variable=self.check_playable).pack(anchor="w")
            ttk.Checkbutton(options_frame, text="检查MD5冲突", variable=self.check_md5).pack(anchor="w")
            ttk.Checkbutton(options_frame, text="自动重命名文件", variable=self.rename_files).pack(anchor="w")
            
            # 操作按钮 - 调整布局，放在选项下方
            action_frame = ttk.Frame(main_frame)
            action_frame.pack(fill="x", pady=(10, 0))
            
            def start_import():
                if not (self.selected_files or self.selected_folders):
                    messagebox.showwarning("警告", "请选择要导入的文件或文件夹")
                    return
                
                if not self.target_folder.get():
                    messagebox.showwarning("警告", "请选择目标文件夹")
                    return
                
                import_window.destroy()
                self.process_video_import()
            
            # 按钮居中排列
            button_container = ttk.Frame(action_frame)
            button_container.pack(expand=True)
            
            ttk.Button(button_container, text="开始导入", command=start_import).pack(side="left", padx=5)
            ttk.Button(button_container, text="取消", command=import_window.destroy).pack(side="left", padx=5)
            
        except Exception as e:
            messagebox.showerror("错误", f"打开导入对话框失败: {str(e)}")
    
    def process_video_import(self):
        """处理视频导入"""
        try:
            # 收集所有要处理的视频文件
            all_video_files = []
            video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'}
            
            # 添加直接选择的文件
            for file_path in self.selected_files:
                if os.path.splitext(file_path.lower())[1] in video_extensions:
                    all_video_files.append(file_path)
            
            # 扫描选择的文件夹
            for folder_path in self.selected_folders:
                for root, dirs, files in os.walk(folder_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        if os.path.splitext(file.lower())[1] in video_extensions:
                            all_video_files.append(file_path)
            
            if not all_video_files:
                messagebox.showinfo("信息", "没有找到视频文件")
                return
            
            # 创建进度窗口
            progress_window = ProgressWindow(self.root, "导入视频文件", len(all_video_files))
            
            def import_thread():
                try:
                    imported_count = 0
                    skipped_count = 0
                    error_count = 0
                    
                    for i, file_path in enumerate(all_video_files):
                        if progress_window.is_cancelled():
                            break
                        
                        self.root.after(0, lambda f=file_path: progress_window.update_status(f"正在处理: {os.path.basename(f)}"))
                        
                        try:
                            # 检查视频完整性
                            if self.check_playable.get():
                                if not self.can_play_video(file_path):
                                    self.root.after(0, lambda f=file_path: progress_window.update_status(f"跳过不可播放文件: {os.path.basename(f)}"))
                                    skipped_count += 1
                                    continue
                            
                            # 计算MD5并检查冲突
                            if self.check_md5.get():
                                file_hash = self.calculate_file_hash(file_path)
                                if self.check_md5_conflict(file_hash):
                                    self.root.after(0, lambda f=file_path: progress_window.update_status(f"跳过MD5冲突文件: {os.path.basename(f)}"))
                                    skipped_count += 1
                                    continue
                            
                            # 处理文件名
                            filename = os.path.basename(file_path)
                            if self.rename_files.get():
                                filename = self.process_filename(filename)
                            
                            # 移动文件到目标位置
                            target_path = os.path.join(self.target_folder.get(), filename)
                            
                            # 如果目标文件已存在，添加序号
                            counter = 1
                            base_name, ext = os.path.splitext(filename)
                            while os.path.exists(target_path):
                                new_filename = f"{base_name}_{counter}{ext}"
                                target_path = os.path.join(self.target_folder.get(), new_filename)
                                counter += 1
                            
                            # 复制文件
                            shutil.copy2(file_path, target_path)
                            imported_count += 1
                            
                            self.root.after(0, lambda f=filename: progress_window.update_status(f"已导入: {f}"))
                            
                        except Exception as ex:
                            error_count += 1
                            self.root.after(0, lambda f=file_path, err=str(ex): progress_window.update_status(f"处理失败: {os.path.basename(f)} - {err}"))
                        
                        self.root.after(0, lambda: progress_window.update_progress(i + 1))
                        time.sleep(0.1)  # 避免界面卡顿
                    
                    # 显示结果
                    result_msg = f"导入完成\n\n成功导入: {imported_count} 个文件\n跳过文件: {skipped_count} 个\n错误文件: {error_count} 个"
                    self.root.after(0, progress_window.close)
                    self.root.after(100, lambda: messagebox.showinfo("导入完成", result_msg))
                    
                    # 刷新媒体库
                    if imported_count > 0:
                        self.root.after(200, self.load_videos)
                    
                except Exception as import_error:
                    error_msg = str(import_error)
                    self.root.after(0, progress_window.close)
                    self.root.after(100, lambda: messagebox.showerror("错误", f"导入过程中发生错误: {error_msg}"))
            
            # 在后台线程中执行导入
            thread = threading.Thread(target=import_thread, daemon=True)
            thread.start()
            
        except Exception as e:
            messagebox.showerror("错误", f"启动导入过程失败: {str(e)}")
    
    def can_play_video(self, file_path):
        """检查视频文件是否可以播放（从cfn4.py移植）"""
        try:
            import cv2
            cap = cv2.VideoCapture(file_path)
            if not cap.isOpened():
                return False
            
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.release()
            
            return frame_count > 0
        except Exception as e:
             return False
    
    def check_md5_conflict(self, file_hash):
        """检查MD5是否与数据库中的文件冲突"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM videos WHERE md5_hash = ?", (file_hash,))
            count = cursor.fetchone()[0]
            return count > 0
        except Exception as e:
             return False
    
    def process_filename(self, filename):
        """处理文件名（从cfn4.py移植）"""
        try:
            # 分离文件名和扩展名
            name, ext = os.path.splitext(filename)
            
            # 转换为大写，扩展名转为小写
            name = name.upper()
            ext = ext.lower()
            
            # 去除空格
            name = name.replace(' ', '')
            
            # 去除特定字符串
            name = name.replace('CHINESEHOMEMADEVIDEO', '')
            
            # 去除其他不需要的字符串（可以根据需要扩展）
            unwanted_strings = ['HD', 'UNCENSORED', 'LEAKED']
            for unwanted in unwanted_strings:
                name = name.replace(unwanted, '')
            
            return name + ext
        except Exception as e:
             return filename

    def run(self):
        """运行应用程序"""
        self.root.mainloop()
        
    def import_videos(self):
        """导入视频文件功能"""
        import_window = tk.Toplevel(self.root)
        import_window.title("导入视频文件")
        import_window.geometry("800x700")
        import_window.transient(self.root)
        import_window.grab_set()
        
        # 主框架
        main_frame = ttk.Frame(import_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 源选择框架
        source_frame = ttk.LabelFrame(main_frame, text="选择导入源")
        source_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 源路径列表
        source_listbox = tk.Listbox(source_frame, height=6)
        source_listbox.pack(fill=tk.X, padx=5, pady=5)
        
        # 源选择按钮
        source_button_frame = ttk.Frame(source_frame)
        source_button_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        
        def add_folders():
            folders = filedialog.askdirectory(title="选择文件夹", mustexist=True)
            if folders:
                source_listbox.insert(tk.END, f"[文件夹] {folders}")
        
        def add_files():
            files = filedialog.askopenfilenames(
                title="选择视频文件",
                filetypes=[("视频文件", "*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm *.m4v *.3gp *.ts *.mts *.m2ts")]
            )
            for file in files:
                if os.path.exists(file):
                    source_listbox.insert(tk.END, f"[文件] {file}")
                else:
                    log_message(f"文件不存在，跳过: {file}")
        
        def remove_selected():
            selection = source_listbox.curselection()
            for index in reversed(selection):
                source_listbox.delete(index)
        
        ttk.Button(source_button_frame, text="添加文件夹", command=add_folders).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(source_button_frame, text="添加文件", command=add_files).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(source_button_frame, text="移除选中", command=remove_selected).pack(side=tk.LEFT)
        
        # 目标文件夹选择 - 改为下拉菜单
        target_frame = ttk.LabelFrame(main_frame, text="选择目标文件夹")
        target_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 获取媒体库文件夹列表
        self.cursor.execute("SELECT DISTINCT folder_path FROM folders WHERE is_active = 1 ORDER BY folder_path")
        available_folders = [row[0] for row in self.cursor.fetchall()]
        
        target_var = tk.StringVar()
        
        # 如果有可用文件夹，设置默认值为第一个
        if available_folders:
            target_var.set(available_folders[0])
        
        target_combobox = ttk.Combobox(target_frame, textvariable=target_var, values=available_folders, state="readonly")
        target_combobox.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        
        def browse_custom_folder():
            folder = filedialog.askdirectory(title="选择自定义目标文件夹")
            if folder:
                # 将自定义文件夹添加到下拉列表
                current_values = list(target_combobox['values'])
                if folder not in current_values:
                    current_values.append(folder)
                    target_combobox['values'] = current_values
                target_var.set(folder)
        
        ttk.Button(target_frame, text="自定义", command=browse_custom_folder).pack(side=tk.RIGHT, padx=5, pady=5)
        
        # 选项框架
        options_frame = ttk.LabelFrame(main_frame, text="导入选项")
        options_frame.pack(fill=tk.X, pady=(0, 10))
        
        delete_invalid_var = tk.BooleanVar(value=True)
        delete_duplicate_var = tk.BooleanVar(value=True)
        rename_files_var = tk.BooleanVar(value=True)
        
        ttk.Checkbutton(options_frame, text="删除无法播放的文件", variable=delete_invalid_var).pack(anchor=tk.W, padx=5, pady=2)
        ttk.Checkbutton(options_frame, text="删除重复文件（基于MD5）", variable=delete_duplicate_var).pack(anchor=tk.W, padx=5, pady=2)
        ttk.Checkbutton(options_frame, text="自动重命名文件", variable=rename_files_var).pack(anchor=tk.W, padx=5, pady=2)
        
        # 按钮框架 - 移到进度上方
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 10))
        
        import_button = ttk.Button(button_frame, text="开始导入", command=lambda: self.start_import_process(
            source_listbox, target_var.get(), delete_invalid_var.get(), delete_duplicate_var.get(), 
            rename_files_var.get(), progress_var, status_var, log_message, import_button
        ))
        import_button.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(button_frame, text="关闭", command=import_window.destroy).pack(side=tk.RIGHT)
        
        # 进度显示
        progress_frame = ttk.LabelFrame(main_frame, text="导入进度")
        progress_frame.pack(fill=tk.BOTH, expand=True)
        
        # 进度条
        progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(progress_frame, variable=progress_var, maximum=100)
        progress_bar.pack(fill=tk.X, padx=5, pady=5)
        
        # 状态标签
        status_var = tk.StringVar(value="准备就绪")
        status_label = ttk.Label(progress_frame, textvariable=status_var)
        status_label.pack(padx=5, pady=2)
        
        # 日志文本框
        log_text = tk.Text(progress_frame, height=10, wrap=tk.WORD)
        log_scrollbar = ttk.Scrollbar(progress_frame, orient=tk.VERTICAL, command=log_text.yview)
        log_text.configure(yscrollcommand=log_scrollbar.set)
        log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0), pady=5)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 5), pady=5)
        
        def log_message(message):
            timestamp = datetime.now().strftime("%H:%M:%S")
            log_text.insert(tk.END, f"[{timestamp}] {message}\n")
            log_text.see(tk.END)
            import_window.update_idletasks()
    
    def start_import_process(self, source_listbox, target_folder, delete_invalid, delete_duplicate, 
                           rename_files, progress_var, status_var, log_message, import_button):
        """开始导入处理过程"""
        if not target_folder:
            messagebox.showerror("错误", "请选择目标文件夹")
            return
        
        if source_listbox.size() == 0:
            messagebox.showerror("错误", "请添加要导入的文件或文件夹")
            return
        
        # 禁用导入按钮
        import_button.config(state="disabled")
        
        def import_worker():
            try:
                # 收集所有视频文件
                all_files = []
                log_message("正在收集视频文件...")
                
                for i in range(source_listbox.size()):
                    item = source_listbox.get(i)
                    if item.startswith("[文件夹] "):
                        folder_path = item[5:].strip()  # 移除"[文件夹] "前缀并去除空格
                        files = self.collect_video_files_from_folder(folder_path)
                        all_files.extend(files)
                        log_message(f"从文件夹 {folder_path} 收集到 {len(files)} 个视频文件")
                    elif item.startswith("[文件] "):
                        file_path = item[4:].strip()  # 移除"[文件] "前缀并去除空格
                        log_message(f"检查文件路径: '{file_path}' (长度: {len(file_path)})")
                        
                        # 使用pathlib进行路径处理
                        try:
                            path_obj = Path(file_path)
                            normalized_path = str(path_obj.resolve())
                            log_message(f"标准化路径: '{normalized_path}'")
                            
                            if path_obj.exists():
                                all_files.append(str(path_obj))
                                log_message(f"文件存在，已添加: {str(path_obj)}")
                            else:
                                log_message(f"文件不存在: {file_path}")
                                # 尝试检查父目录是否存在
                                if path_obj.parent.exists():
                                    log_message(f"父目录存在: {path_obj.parent}")
                                    # 列出父目录中的文件
                                    try:
                                        files_in_dir = list(path_obj.parent.glob('*'))
                                        log_message(f"父目录中的文件数量: {len(files_in_dir)}")
                                        if len(files_in_dir) <= 10:  # 只显示少量文件
                                            for f in files_in_dir:
                                                log_message(f"  - {f.name}")
                                    except Exception as e:
                                        log_message(f"无法列出父目录文件: {e}")
                                else:
                                    log_message(f"父目录不存在: {path_obj.parent}")
                        except Exception as e:
                            log_message(f"路径处理错误: {e}")
                            # 回退到原始检查
                            if os.path.exists(file_path):
                                all_files.append(file_path)
                            else:
                                log_message(f"原始路径检查也失败: {file_path}")
                
                if not all_files:
                    log_message("没有找到视频文件")
                    self.root.after(0, lambda: messagebox.showinfo("信息", "没有找到视频文件"))
                    return
                
                log_message(f"总共找到 {len(all_files)} 个视频文件")
                
                # 第一阶段：预处理所有文件，计算MD5并进行去重
                log_message("开始预处理文件，计算MD5并检查重复...")
                
                # 存储文件信息的字典：{file_path: {hash, size, created_time, stars, valid}}
                file_info_map = {}
                
                # 计算所有文件的MD5
                for i, file_path in enumerate(all_files):
                    try:
                        progress = (i / len(all_files)) * 50  # 预处理占50%进度
                        progress_var.set(progress)
                        status_var.set(f"预处理文件 {i+1}/{len(all_files)}: {os.path.basename(file_path)}")
                        
                        # 检查视频是否可播放
                        if not self.can_play_video(file_path):
                            log_message(f"无法播放，标记为无效: {os.path.basename(file_path)}")
                            file_info_map[file_path] = {'valid': False}
                            continue
                        
                        # 计算MD5
                        file_hash = self.calculate_file_hash(file_path)
                        if not file_hash:
                            log_message(f"MD5计算失败，跳过: {os.path.basename(file_path)}")
                            file_info_map[file_path] = {'valid': False}
                            continue
                        
                        # 获取文件信息
                        file_stat = os.stat(file_path)
                        file_size = file_stat.st_size
                        created_time = datetime.fromtimestamp(file_stat.st_ctime)
                        
                        # 从文件名解析星级（叹号数量）
                        filename = os.path.basename(file_path)
                        stars = self.parse_stars_from_filename(filename)
                        
                        file_info_map[file_path] = {
                            'hash': file_hash,
                            'size': file_size,
                            'created_time': created_time,
                            'stars': stars,
                            'valid': True
                        }
                        
                    except Exception as e:
                        log_message(f"预处理文件失败: {os.path.basename(file_path)} - {str(e)}")
                        file_info_map[file_path] = {'valid': False}
                
                # 第二阶段：去重处理
                log_message("开始去重处理...")
                
                # 按MD5分组
                hash_groups = {}
                for file_path, info in file_info_map.items():
                    if info.get('valid') and info.get('hash'):
                        file_hash = info['hash']
                        if file_hash not in hash_groups:
                            hash_groups[file_hash] = []
                        hash_groups[file_hash].append(file_path)
                
                # 处理重复文件
                files_to_process = []  # 最终要处理的文件列表
                files_to_delete = []   # 要删除的重复文件列表
                
                for file_hash, file_paths in hash_groups.items():
                    # 检查数据库中是否已存在此MD5
                    if self.check_duplicate_by_hash(file_hash):
                        log_message(f"MD5 {file_hash[:8]}... 在数据库中已存在，跳过所有相关文件")
                        if delete_duplicate:
                            files_to_delete.extend(file_paths)
                        continue
                    
                    if len(file_paths) == 1:
                        # 没有重复，直接添加到处理列表
                        files_to_process.append(file_paths[0])
                    else:
                        # 有重复文件，需要选择保留哪个
                        log_message(f"发现 {len(file_paths)} 个重复文件 (MD5: {file_hash[:8]}...)")
                        
                        # 排序规则：1. 星级高的优先 2. 创建时间早的优先
                        def sort_key(path):
                            info = file_info_map[path]
                            return (-info['stars'], info['created_time'])  # 负号表示降序
                        
                        sorted_paths = sorted(file_paths, key=sort_key)
                        keep_file = sorted_paths[0]
                        duplicate_files = sorted_paths[1:]
                        
                        files_to_process.append(keep_file)
                        
                        log_message(f"保留文件: {os.path.basename(keep_file)} (星级: {file_info_map[keep_file]['stars']})")
                        for dup_file in duplicate_files:
                            log_message(f"标记为重复: {os.path.basename(dup_file)} (星级: {file_info_map[dup_file]['stars']})")
                        
                        if delete_duplicate:
                            files_to_delete.extend(duplicate_files)
                
                # 删除无效和重复文件
                invalid_count = 0
                duplicate_count = 0
                
                for file_path in file_info_map:
                    if not file_info_map[file_path].get('valid'):
                        if delete_invalid:
                            try:
                                send2trash(file_path)
                                log_message(f"已删除无效文件: {os.path.basename(file_path)}")
                                invalid_count += 1
                            except Exception as e:
                                log_message(f"删除无效文件失败: {os.path.basename(file_path)} - {str(e)}")
                
                for file_path in files_to_delete:
                    try:
                        send2trash(file_path)
                        log_message(f"已删除重复文件: {os.path.basename(file_path)}")
                        duplicate_count += 1
                    except Exception as e:
                        log_message(f"删除重复文件失败: {os.path.basename(file_path)} - {str(e)}")
                
                # 第三阶段：处理剩余的有效文件
                log_message(f"开始处理 {len(files_to_process)} 个有效文件...")
                
                processed_count = 0
                success_count = 0
                failed_count = 0
                
                for i, file_path in enumerate(files_to_process):
                    try:
                        progress = 50 + (i / len(files_to_process)) * 50  # 处理阶段占50%进度
                        progress_var.set(progress)
                        status_var.set(f"导入文件 {i+1}/{len(files_to_process)}: {os.path.basename(file_path)}")
                        
                        # 重命名文件
                        if rename_files:
                            new_filename = self.process_filename(os.path.basename(file_path))
                        else:
                            new_filename = os.path.basename(file_path)
                        
                        # 构建目标路径
                        target_path = os.path.join(target_folder, new_filename)
                        
                        # 处理文件名冲突
                        target_path = self.resolve_filename_conflict(target_path)
                        
                        # 移动文件
                        shutil.move(file_path, target_path)
                        
                        # 将文件添加到数据库
                        try:
                            # 确定文件夹类型
                            folder_type = "local"  # 默认为本地文件夹
                            
                            # 检查是否为NAS文件夹
                            cursor = self.conn.cursor()
                            cursor.execute("SELECT folder_type FROM folders WHERE folder_path = ?", (target_folder,))
                            folder_result = cursor.fetchone()
                            if folder_result:
                                folder_type = folder_result[0]
                            
                            # 添加到数据库
                            self.add_video_to_db(target_path, folder_type)
                            log_message(f"成功导入并添加到数据库: {os.path.basename(target_path)}")
                        except Exception as db_error:
                            log_message(f"文件移动成功但数据库插入失败: {os.path.basename(target_path)} - {str(db_error)}")
                        
                        success_count += 1
                        
                    except Exception as e:
                        log_message(f"处理文件失败: {os.path.basename(file_path)} - {str(e)}")
                        failed_count += 1
                    
                    processed_count += 1
                
                # 完成
                progress_var.set(100)
                status_var.set("导入完成")
                log_message(f"导入完成！成功: {success_count}, 失败: {failed_count}, 重复: {duplicate_count}, 无效: {invalid_count}")
                
                # 刷新媒体库显示
                if success_count > 0:
                    log_message("正在刷新媒体库...")
                    self.root.after(0, self.load_videos)
                
                self.root.after(0, lambda: messagebox.showinfo("完成", 
                    f"导入完成！\n\n成功导入: {success_count} 个文件\n失败: {failed_count} 个文件\n删除重复: {duplicate_count} 个文件\n删除无效: {invalid_count} 个文件"))
                
            except Exception as e:
                error_msg = str(e)
                log_message(f"导入过程发生错误: {error_msg}")
                self.root.after(0, lambda: messagebox.showerror("错误", f"导入过程发生错误: {error_msg}"))
            finally:
                # 重新启用导入按钮
                self.root.after(0, lambda: import_button.config(state="normal"))
        
        # 在新线程中执行导入
        threading.Thread(target=import_worker, daemon=True).start()
    
    def collect_video_files_from_folder(self, folder_path):
        """从文件夹收集所有视频文件"""
        video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.3gp', '.ts', '.mts', '.m2ts'}
        video_files = []
        
        if not os.path.exists(folder_path):
            print(f"文件夹不存在: {folder_path}")
            return video_files
            
        if not os.path.isdir(folder_path):
            print(f"路径不是文件夹: {folder_path}")
            return video_files
        
        try:
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    if any(file.lower().endswith(ext) for ext in video_extensions):
                        full_path = os.path.join(root, file)
                        if os.path.exists(full_path) and os.path.isfile(full_path):
                            video_files.append(full_path)
        except Exception as e:
            print(f"扫描文件夹失败 {folder_path}: {str(e)}")
        
        return video_files
    
    def can_play_video(self, file_path):
        """检查视频文件是否可以播放"""
        try:
            cap = cv2.VideoCapture(file_path)
            if not cap.isOpened():
                return False
            
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.release()
            
            return frame_count > 0
        except Exception:
            return False
    
    def check_duplicate_by_hash(self, file_hash):
        """检查文件哈希是否已存在于数据库中"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM videos WHERE md5_hash = ?", (file_hash,))
            count = cursor.fetchone()[0]
            return count > 0
        except Exception:
            return False
    
    def process_filename(self, filename):
        """使用cfn4.py中的逻辑处理文件名"""
        # 获取文件名和后缀
        filename_no_ext, ext = os.path.splitext(filename)
        
        # 将文件名转换为大写
        filename_upper = filename_no_ext.upper()
        
        # 将后缀转换为小写
        ext_lower = ext.lower()
        
        # 构建新的文件名
        new_filename = filename_upper + ext_lower
        
        # 去掉空格
        if " " in new_filename:
            new_filename = new_filename.replace(" ", "")
        
        # 去掉其他可能的变体
        if "CHINESEHOMEMADEVIDEO" in new_filename:
            new_filename = new_filename.replace("CHINESEHOMEMADEVIDEO", "")
        if "_CHINESE_HOMEMADE_VIDEO" in new_filename:
            new_filename = new_filename.replace("_CHINESE_HOMEMADE_VIDEO", "")
        
        # 去掉"hhd800.com@"
        if "HHD800.COM@" in new_filename:
            new_filename = new_filename.replace("HHD800.COM@", "")
        
        # 去掉"WoXav.Com@"
        if "WOXAV.COM@" in new_filename:
            new_filename = new_filename.replace("WOXAV.COM@", "")
        
        # 去掉"【"和"】"之间的内容
        pattern = r"(【.*?】)"
        if "【" in new_filename and "】" in new_filename:
            new_filename = re.sub(pattern, "", new_filename)
        
        # 去掉各种括号内容
        partern2 = r"[\[\【\(\（][^)）].*?[\）\)\】\]]"
        new_filename = re.sub(partern2, "", new_filename)
        
        # 去掉各种括号没有括回而是.
        partern3 = r"[\[\【\(\（][^)）].*?\."
        new_filename = re.sub(partern3, ".", new_filename)
        
        # 去掉直角单引号之间的内容
        if "「" in new_filename and "」" in new_filename:
            new_filename = re.sub(r"「.*?」", "", new_filename)
        
        # 去掉直角双引号之间的内容
        if "『" in new_filename and "』" in new_filename:
            new_filename = re.sub(r"『.*?』", "", new_filename)
        
        # 去掉网址名称格式
        url_pattern = r"(?:WWW\.)?[A-Z0-9]+\.(COM|NET|ORG|CN|CC|ME)"
        new_filename = re.sub(url_pattern, "", new_filename)
        
        # 去掉开头的叹号
        if new_filename.startswith("!"):
            new_filename = new_filename[1:]
        
        return new_filename
    
    def resolve_filename_conflict(self, target_path):
        """解决文件名冲突"""
        if not os.path.exists(target_path):
            return target_path
        
        base_path, ext = os.path.splitext(target_path)
        counter = 1
        
        while True:
            new_path = f"{base_path}_{counter}{ext}"
            if not os.path.exists(new_path):
                return new_path
            counter += 1
    
    def clean_filename_for_video(self, video_id):
        """为单个视频清理文件名"""
        try:
            # 获取视频信息
            cursor = self.conn.cursor()
            cursor.execute("SELECT file_path, title FROM videos WHERE id = ?", (video_id,))
            result = cursor.fetchone()
            if not result:
                print(f"未找到视频ID: {video_id}")
                return False
            
            old_file_path, old_title = result
            if not os.path.exists(old_file_path):
                print(f"文件不存在: {old_file_path}")
                return False
            
            # 获取文件目录和原始文件名
            file_dir = os.path.dirname(old_file_path)
            old_filename = os.path.basename(old_file_path)
            
            # 应用清理逻辑
            new_filename = self.process_single_filename(old_filename)
            
            # 如果文件名没有变化，直接返回
            if new_filename == old_filename:
                print(f"文件名无需清理: {old_filename}")
                return True
            
            # 构建新的完整路径
            new_file_path = os.path.join(file_dir, new_filename)
            
            # 处理文件名冲突
            if os.path.exists(new_file_path):
                new_file_path = self.handle_filename_conflict(new_file_path)
                new_filename = os.path.basename(new_file_path)
            
            # 重命名文件
            os.rename(old_file_path, new_file_path)
            
            # 生成新的标题（应用相同的清理逻辑）
            # 对数据库中的原始标题应用清理逻辑
            cleaned_title_with_ext = self.process_single_filename(old_title + ".tmp")  # 添加临时扩展名
            new_title = os.path.splitext(cleaned_title_with_ext)[0]  # 去掉临时扩展名
            
            # 更新数据库中的文件路径和标题
            cursor.execute("UPDATE videos SET file_path = ?, title = ? WHERE id = ?", (new_file_path, new_title, video_id))
            self.conn.commit()
            
            print(f"文件重命名成功: {old_filename} -> {new_filename}")
            print(f"标题更新: {old_title} -> {new_title}")
            return True
            
        except Exception as e:
            print(f"清理文件名失败: {str(e)}")
            return False
    
    def process_single_filename(self, filename):
        """处理单个文件名，基于cfn4.py的逻辑"""
        import re
        
        # 获取文件名和后缀
        filename_no_ext, ext = os.path.splitext(filename)
        
        # 去除开头的叹号（保留叹号用于星级评分）
        # 注意：这里不移除叹号，因为叹号用于星级评分
        
        # 去除开头和结尾的句号
        filename_no_ext = filename_no_ext.strip('.')
        
        # 将文件名转换为大写
        filename_upper = filename_no_ext.upper()
        
        # 将后缀转换为小写
        ext_lower = ext.lower()
        
        # 构建新的文件名
        new_filename = filename_upper + ext_lower
        
        # 去掉空格
        if " " in new_filename:
            new_filename = new_filename.replace(" ", "")
        
        # 去掉"Chinese homemade video"和"_CHINESE_HOMEMADE_VIDEO"
        if "CHINESEHOMEMADEVIDEO" in new_filename:
            new_filename = new_filename.replace("CHINESEHOMEMADEVIDEO", "")
        if "_CHINESE_HOMEMADE_VIDEO" in new_filename:
            new_filename = new_filename.replace("_CHINESE_HOMEMADE_VIDEO", "")
        
        # 去掉"hhd800.com@"
        if "HHD800.COM@" in new_filename:
            new_filename = new_filename.replace("HHD800.COM@", "")
        
        # 去掉"WoXav.Com@"
        if "WOXAV.COM@" in new_filename:
            new_filename = new_filename.replace("WOXAV.COM@", "")
        
        # 匹配"【"和"】"之间的内容
        pattern = r"(【.*?】)"
        if "【" in new_filename and "】" in new_filename:
            match = re.search(pattern, new_filename)
            if match:
                new_filename = re.sub(pattern, "", new_filename)
        
        # 第二轮匹配各种括号情形
        partern2 = r"[\[\【\(\（][^)）].*?[\）\)\】\]]"
        match = re.search(partern2, new_filename)
        if match:
            new_filename = re.sub(partern2, "", new_filename)
        
        # 第三轮匹配各种括号没有括回而是.
        partern3 = r"[\[\【\(\（][^)）].*?\."
        match = re.search(partern3, new_filename)
        if match:
            new_filename = re.sub(partern3, "", new_filename)
        
        # 去掉直角单引号之间的内容
        if "「" in new_filename and "」" in new_filename:
            new_filename = re.sub(r"「.*?」", "", new_filename)
        
        # 去掉直角双引号之间的内容
        if "『" in new_filename and "』" in new_filename:
            new_filename = re.sub(r"『.*?』", "", new_filename)
        
        # 去掉网址名称格式
        url_pattern = r"(?:WWW\.)?[A-Z0-9]+\.(COM|NET|ORG|CN|CC|ME)"
        new_filename = re.sub(url_pattern, "", new_filename)
        
        # 清理连续的句号，替换为空字符串
        new_filename = re.sub(r'\.{2,}', '', new_filename)
        
        # 最终清理：去除开头和结尾的句号
        filename_part, ext_part = os.path.splitext(new_filename)
        filename_part = filename_part.strip('.')
        new_filename = filename_part + ext_part
        
        return new_filename
    
    def handle_filename_conflict(self, file_path):
        """处理文件名冲突，添加数字后缀"""
        base_path, ext = os.path.splitext(file_path)
        counter = 1
        
        while True:
            new_path = f"{base_path}_{counter}{ext}"
            if not os.path.exists(new_path):
                return new_path
            counter += 1
    
    def batch_clean_filename_selected_videos(self):
        """批量清理选中视频的文件名"""
        selected_items = self.video_tree.selection()
        if not selected_items:
            messagebox.showwarning("警告", "请先选择要清理文件名的视频")
            return
        
        # 确认操作
        result = messagebox.askyesno("确认", f"确定要清理 {len(selected_items)} 个视频的文件名吗？")
        if not result:
            return
        
        success_count = 0
        failed_count = 0
        
        for item in selected_items:
            try:
                video_id = self.video_tree.item(item)['tags'][0]
                if self.clean_filename_for_video(video_id):
                    success_count += 1
                else:
                    failed_count += 1
            except (IndexError, TypeError):
                failed_count += 1
                continue
        
        # 刷新视频列表
        self.load_videos()
        
        # 显示结果
        messagebox.showinfo("完成", f"文件名清理完成\n成功: {success_count} 个\n失败: {failed_count} 个")
    
    def clean_filename_from_context(self, video_id):
        """从右键菜单清理单个视频文件名"""
        if self.clean_filename_for_video(video_id):
            # 刷新视频列表
            self.load_videos()
            messagebox.showinfo("成功", "文件名清理完成")
        else:
            messagebox.showerror("错误", "文件名清理失败")
    
    def import_nfo_from_context(self, video_id, video_path):
        """从右键菜单导入NFO文件"""
        try:
            # 获取视频文件所在目录
            video_dir = os.path.dirname(video_path)
            
            # 检查必需的文件是否存在
            fanart_path = os.path.join(video_dir, "fanart.jpg")
            poster_path = os.path.join(video_dir, "poster.jpg")
            nfo_path = os.path.join(video_dir, "movie.nfo")
            
            missing_files = []
            if not os.path.exists(fanart_path):
                missing_files.append("fanart.jpg")
            if not os.path.exists(poster_path):
                missing_files.append("poster.jpg")
            if not os.path.exists(nfo_path):
                missing_files.append("movie.nfo")
            
            if missing_files:
                messagebox.showwarning("文件缺失", f"以下文件不存在，无法导入NFO：\n{', '.join(missing_files)}")
                return
            
            # 读取NFO文件内容
            nfo_data = self.parse_nfo_file(nfo_path)
            if not nfo_data:
                messagebox.showerror("错误", "无法解析NFO文件")
                return
            
            # 读取fanart.jpg作为缩略图
            thumbnail_data = None
            try:
                with open(fanart_path, 'rb') as f:
                    thumbnail_data = f.read()
            except Exception as e:
                print(f"读取fanart.jpg失败: {e}")
            
            # 更新videos表的基本信息
            video_update_fields = []
            video_update_values = []
            
            # 使用JAVDB标题作为主标题，如果没有则使用完整标题
            if nfo_data.get('javdb_title'):
                video_update_fields.append("title = ?")
                video_update_values.append(nfo_data['javdb_title'])
            elif nfo_data.get('title'):
                video_update_fields.append("title = ?")
                video_update_values.append(nfo_data['title'])
            
            if nfo_data.get('plot'):
                video_update_fields.append("description = ?")
                video_update_values.append(nfo_data['plot'])
            
            if nfo_data.get('year'):
                video_update_fields.append("year = ?")
                video_update_values.append(nfo_data['year'])
            
            if nfo_data.get('genre'):
                video_update_fields.append("genre = ?")
                video_update_values.append(nfo_data['genre'])
            
            # 封面图片（fanart.jpg作为缩略图）
            if thumbnail_data:
                video_update_fields.append("thumbnail_data = ?")
                video_update_values.append(thumbnail_data)
            
            # 更新videos表
            if video_update_fields:
                video_update_values.append(video_id)
                sql = f"UPDATE videos SET {', '.join(video_update_fields)} WHERE id = ?"
                self.cursor.execute(sql, video_update_values)
            
            # 将NFO数据存储到javdb_info表
            javdb_code = nfo_data.get('uniqueid') or nfo_data.get('code')
            if javdb_code:
                # 检查是否已存在javdb_info记录
                self.cursor.execute("SELECT id FROM javdb_info WHERE video_id = ?", (video_id,))
                existing_record = self.cursor.fetchone()
                
                # 准备javdb_info数据
                javdb_title = nfo_data.get('javdb_title') or nfo_data.get('title')
                release_date = nfo_data.get('premiered')
                studio = nfo_data.get('studio')
                rating_text = nfo_data.get('rating')
                score = None
                
                # 转换评分
                if rating_text:
                    try:
                        score = float(rating_text)
                    except ValueError:
                        pass
                
                # 读取poster.jpg作为封面
                cover_image_data = None
                try:
                    with open(poster_path, 'rb') as f:
                        cover_image_data = f.read()
                except Exception as e:
                    print(f"读取poster.jpg失败: {e}")
                
                if existing_record:
                    # 更新现有记录
                    self.cursor.execute("""
                        UPDATE javdb_info SET 
                        javdb_code = ?, javdb_title = ?, release_date = ?, 
                        studio = ?, rating = ?, score = ?, cover_image_data = ?,
                        updated_at = CURRENT_TIMESTAMP
                        WHERE video_id = ?
                    """, (javdb_code, javdb_title, release_date, studio, rating_text, score, cover_image_data, video_id))
                else:
                    # 插入新记录
                    self.cursor.execute("""
                        INSERT INTO javdb_info 
                        (video_id, javdb_code, javdb_title, release_date, studio, rating, score, cover_image_data, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """, (video_id, javdb_code, javdb_title, release_date, studio, rating_text, score, cover_image_data))
                
                # 处理演员信息
                if nfo_data.get('actors'):
                    for actor_name in nfo_data['actors']:
                        # 插入或获取演员ID
                        self.cursor.execute("INSERT OR IGNORE INTO actors (name) VALUES (?)", (actor_name,))
                        self.cursor.execute("SELECT id FROM actors WHERE name = ?", (actor_name,))
                        actor_id = self.cursor.fetchone()[0]
                        
                        # 关联视频和演员
                        self.cursor.execute("""
                            INSERT OR IGNORE INTO video_actors (video_id, actor_id) 
                            VALUES (?, ?)
                        """, (video_id, actor_id))
                
                # 处理标签信息
                if nfo_data.get('tags'):
                    # 获取javdb_info记录ID
                    self.cursor.execute("SELECT id FROM javdb_info WHERE video_id = ?", (video_id,))
                    javdb_info_id = self.cursor.fetchone()[0]
                    
                    for tag_name in nfo_data['tags']:
                        # 插入或获取标签ID
                        self.cursor.execute("INSERT OR IGNORE INTO javdb_tags (tag_name) VALUES (?)", (tag_name,))
                        self.cursor.execute("SELECT id FROM javdb_tags WHERE tag_name = ?", (tag_name,))
                        tag_id = self.cursor.fetchone()[0]
                        
                        # 关联javdb_info和标签
                        self.cursor.execute("""
                            INSERT OR IGNORE INTO javdb_info_tags (javdb_info_id, tag_id) 
                            VALUES (?, ?)
                        """, (javdb_info_id, tag_id))
            
            self.conn.commit()
            
            # 刷新视频列表
            self.load_videos()
            
            imported_info = []
            if nfo_data.get('title'):
                imported_info.append(f"标题: {nfo_data['title']}")
            if nfo_data.get('year'):
                imported_info.append(f"年份: {nfo_data['year']}")
            if nfo_data.get('genre'):
                imported_info.append(f"类型: {nfo_data['genre']}")
            if nfo_data.get('rating'):
                imported_info.append(f"评分: {nfo_data['rating']}")
            if thumbnail_data:
                imported_info.append("缩略图: fanart.jpg")
            
            messagebox.showinfo("导入成功", f"NFO数据导入完成！\n\n导入的信息：\n{chr(10).join(imported_info)}")
            
        except Exception as e:
            messagebox.showerror("错误", f"导入NFO失败: {str(e)}")
    
    def parse_nfo_file(self, nfo_path):
        """解析NFO文件"""
        try:
            import xml.etree.ElementTree as ET
            
            tree = ET.parse(nfo_path)
            root = tree.getroot()
            
            nfo_data = {}
            
            # 提取标题（完整截取到</title>）
            title_elem = root.find('title')
            if title_elem is not None and title_elem.text:
                full_title = title_elem.text.strip()
                nfo_data['title'] = full_title
                
                # 从标题中提取番号和JAVDB标题
                # 第一个空格前面作为番号，后面作为javdb标题
                if ' ' in full_title:
                    parts = full_title.split(' ', 1)
                    nfo_data['code'] = parts[0]  # 番号
                    nfo_data['javdb_title'] = parts[1]  # JAVDB标题
                else:
                    nfo_data['code'] = full_title
                    nfo_data['javdb_title'] = full_title
            
            # 提取剧情描述
            plot_elem = root.find('plot')
            if plot_elem is not None and plot_elem.text:
                nfo_data['plot'] = plot_elem.text.strip()
            
            # 提取年份
            year_elem = root.find('year')
            if year_elem is not None and year_elem.text:
                nfo_data['year'] = year_elem.text.strip()
            
            # 提取发行日期
            premiered_elem = root.find('premiered')
            if premiered_elem is not None and premiered_elem.text:
                nfo_data['premiered'] = premiered_elem.text.strip()
            
            # 提取类型
            genre_elem = root.find('genre')
            if genre_elem is not None and genre_elem.text:
                nfo_data['genre'] = genre_elem.text.strip()
            
            # 提取JAVDB评分
            rating_elem = root.find('rating')
            if rating_elem is not None and rating_elem.text:
                nfo_data['rating'] = rating_elem.text.strip()
            
            # 提取发行商
            studio_elem = root.find('studio')
            if studio_elem is not None and studio_elem.text:
                nfo_data['studio'] = studio_elem.text.strip()
            
            # 提取番号（从uniqueid标签）
            uniqueid_elem = root.find('.//uniqueid[@type="num"][@default="true"]')
            if uniqueid_elem is not None and uniqueid_elem.text:
                nfo_data['uniqueid'] = uniqueid_elem.text.strip()
            
            # 提取标签
            tags = []
            for tag_elem in root.findall('tag'):
                if tag_elem.text:
                    tags.append(tag_elem.text.strip())
            if tags:
                nfo_data['tags'] = tags
            
            # 提取演员信息（从<actor><name>标签）
            actors = []
            for actor_elem in root.findall('actor'):
                name_elem = actor_elem.find('name')
                if name_elem is not None and name_elem.text:
                    actors.append(name_elem.text.strip())
            if actors:
                nfo_data['actors'] = actors
            
            return nfo_data
            
        except Exception as e:
            print(f"解析NFO文件失败: {e}")
            return None
    
    def batch_import_nfo_for_no_actors(self):
        """批量导入NFO信息 - 针对没有演员信息的视频"""
        try:
            # 获取当前选定的文件夹
            selected_folder_indices = self.folder_listbox.curselection()
            if not selected_folder_indices or not hasattr(self, 'folder_path_mapping'):
                messagebox.showwarning("警告", "请先选择一个文件夹")
                return
                
            selected_folder = self.folder_listbox.get(selected_folder_indices[0])
            if selected_folder == "全部":
                messagebox.showwarning("警告", "请选择具体的文件夹，不能选择'全部'")
                return
                
            if selected_folder not in self.folder_path_mapping:
                messagebox.showwarning("警告", "无法找到选定文件夹的路径")
                return
                
            folder_path = self.folder_path_mapping[selected_folder]
            
            # 查询该文件夹下没有演员信息的视频
            self.cursor.execute("""
                SELECT v.id, v.file_path, v.file_name 
                FROM videos v
                LEFT JOIN video_actors va ON v.id = va.video_id
                WHERE v.source_folder LIKE ? AND va.video_id IS NULL
            """, (f"{folder_path}%",))
            
            videos_without_actors = self.cursor.fetchall()
            
            if not videos_without_actors:
                messagebox.showinfo("信息", f"文件夹 '{selected_folder}' 中没有找到缺少演员信息的视频")
                return
                
            # 确认对话框
            if not messagebox.askyesno("确认", 
                f"找到 {len(videos_without_actors)} 个没有演员信息的视频\n\n是否开始批量导入NFO信息？"):
                return
                
            # 复用现有的进度窗口创建逻辑（类似batch_javdb_info_selected_videos）
            progress_window = tk.Toplevel(self.root)
            progress_window.title("批量导入NFO信息")
            progress_window.geometry("500x300")
            progress_window.transient(self.root)
            progress_window.grab_set()
            
            progress_label = ttk.Label(progress_window, text="准备导入...")
            progress_label.pack(pady=10)
            
            progress_bar = ttk.Progressbar(progress_window, length=400, maximum=len(videos_without_actors))
            progress_bar.pack(pady=10)
            
            log_frame = ttk.Frame(progress_window)
            log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            log_text = tk.Text(log_frame, height=10, width=60)
            scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=log_text.yview)
            log_text.configure(yscrollcommand=scrollbar.set)
            
            log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            def log_message(message):
                log_text.insert(tk.END, message + "\n")
                log_text.see(tk.END)
                progress_window.update()
                
            cancel_button = ttk.Button(progress_window, text="取消")
            cancel_button.pack(pady=5)
            
            self.cancel_import = False
            
            def cancel_import():
                self.cancel_import = True
                cancel_button.config(text="关闭", command=progress_window.destroy)
                
            cancel_button.config(command=cancel_import)
            
            def import_thread():
                try:
                    imported_count = 0
                    skipped_count = 0
                    
                    for i, (video_id, file_path, file_name) in enumerate(videos_without_actors):
                        if self.cancel_import:
                            break
                            
                        progress_bar.config(value=i + 1)
                        progress_label.config(text=f"处理: {file_name} ({i + 1}/{len(videos_without_actors)})")
                        
                        # 查找对应的NFO文件
                        nfo_path = os.path.splitext(file_path)[0] + '.nfo'
                        
                        if os.path.exists(nfo_path):
                            log_message(f"找到NFO文件: {os.path.basename(nfo_path)}")
                            
                            # 直接调用现有的parse_nfo_file方法
                            if self.parse_nfo_file(nfo_path):
                                imported_count += 1
                                log_message(f"✓ 成功导入: {file_name}")
                            else:
                                skipped_count += 1
                                log_message(f"✗ 导入失败: {file_name}")
                        else:
                            skipped_count += 1
                            log_message(f"- 未找到NFO文件: {file_name}")
                    
                    # 完成
                    progress_label.config(text="导入完成")
                    log_message(f"\n=== 导入完成 ===")
                    log_message(f"成功导入: {imported_count} 个")
                    log_message(f"跳过: {skipped_count} 个")
                    
                    cancel_button.config(text="关闭", command=progress_window.destroy)
                    
                    # 刷新视频列表
                    self.root.after(100, self.load_videos)
                    
                except Exception as e:
                    log_message(f"批量导入过程中发生错误: {str(e)}")
                    cancel_button.config(text="关闭", command=progress_window.destroy)
            
            # 在后台线程中执行导入
            thread = threading.Thread(target=import_thread, daemon=True)
            thread.start()
            
        except Exception as e:
            messagebox.showerror("错误", f"批量导入NFO信息失败: {str(e)}")
    
    def batch_import_javdb_for_no_title(self):
        """批量导入JAVDB信息 - 针对没有JAVDB标题的视频"""
        try:
            # 获取当前选定的文件夹
            selected_folder_indices = self.folder_listbox.curselection()
            if not selected_folder_indices or not hasattr(self, 'folder_path_mapping'):
                messagebox.showwarning("警告", "请先选择一个文件夹")
                return
                
            selected_folder = self.folder_listbox.get(selected_folder_indices[0])
            if selected_folder == "全部":
                messagebox.showwarning("警告", "请选择具体的文件夹，不能选择'全部'")
                return
                
            if selected_folder not in self.folder_path_mapping:
                messagebox.showwarning("警告", "无法找到选定文件夹的路径")
                return
                
            folder_path = self.folder_path_mapping[selected_folder]
            
            # 查询该文件夹下没有JAVDB标题的视频
            self.cursor.execute("""
                SELECT v.id, v.file_path, v.file_name 
                FROM videos v
                LEFT JOIN javdb_info j ON v.id = j.video_id
                WHERE v.source_folder LIKE ? AND (j.javdb_title IS NULL OR j.javdb_title = '')
            """, (f"{folder_path}%",))
            
            videos_without_javdb = self.cursor.fetchall()
            
            if not videos_without_javdb:
                messagebox.showinfo("信息", f"文件夹 '{selected_folder}' 中没有找到缺少JAVDB标题的视频")
                return
                
            # 确认对话框
            if not messagebox.askyesno("确认", 
                f"找到 {len(videos_without_javdb)} 个没有JAVDB标题的视频\n\n是否开始批量导入JAVDB信息？\n\n注意：此操作可能需要较长时间"):
                return
                
            # 复用现有的进度窗口创建逻辑（与batch_javdb_info_selected_videos相同）
            progress_window = tk.Toplevel(self.root)
            progress_window.title("批量导入JAVDB信息")
            progress_window.geometry("600x400")
            progress_window.transient(self.root)
            progress_window.grab_set()
            
            progress_label = ttk.Label(progress_window, text="准备导入...")
            progress_label.pack(pady=10)
            
            progress_bar = ttk.Progressbar(progress_window, length=500, maximum=len(videos_without_javdb))
            progress_bar.pack(pady=10)
            
            log_frame = ttk.Frame(progress_window)
            log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            log_text = tk.Text(log_frame, height=15, width=70)
            scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=log_text.yview)
            log_text.configure(yscrollcommand=scrollbar.set)
            
            log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            def log_message(message):
                log_text.insert(tk.END, message + "\n")
                log_text.see(tk.END)
                progress_window.update()
                
            cancel_button = ttk.Button(progress_window, text="取消")
            cancel_button.pack(pady=5)
            
            self.cancel_import = False
            
            def cancel_import():
                self.cancel_import = True
                cancel_button.config(text="关闭", command=progress_window.destroy)
                
            cancel_button.config(command=cancel_import)
            
            def import_thread():
                try:
                    from code_extractor import CodeExtractor
                    import subprocess
                    import json
                    
                    extractor = CodeExtractor()
                    imported_count = 0
                    skipped_count = 0
                    
                    for i, (video_id, file_path, file_name) in enumerate(videos_without_javdb):
                        if self.cancel_import:
                            break
                            
                        progress_bar.config(value=i + 1)
                        progress_label.config(text=f"处理: {file_name} ({i + 1}/{len(videos_without_javdb)})")
                        
                        # 直接调用现有的番号提取逻辑
                        av_code = extractor.extract_code_from_filename(file_name)
                        
                        if not av_code:
                            skipped_count += 1
                            log_message(f"- 无法提取番号: {file_name}")
                            continue
                            
                        log_message(f"提取番号: {av_code} <- {file_name}")
                        
                        try:
                            # 直接调用现有的JAVDB爬虫逻辑
                            cmd = ["python", "javdb_crawler_single.py", av_code]
                            process = subprocess.run(cmd, capture_output=True, text=True, 
                                                   cwd=os.path.dirname(os.path.abspath(__file__)), timeout=60)
                            
                            if process.returncode == 0 and process.stdout:
                                try:
                                    result = json.loads(process.stdout)
                                    if "error" not in result:
                                        # 直接调用现有的保存方法
                                        self.save_javdb_info_to_db(video_id, result)
                                        imported_count += 1
                                        log_message(f"✓ 成功导入: {av_code} - {result.get('title', 'N/A')}")
                                    else:
                                        skipped_count += 1
                                        log_message(f"✗ JAVDB返回错误: {av_code} - {result.get('error', 'Unknown error')}")
                                except json.JSONDecodeError:
                                    skipped_count += 1
                                    log_message(f"✗ 解析JAVDB响应失败: {av_code}")
                            else:
                                skipped_count += 1
                                log_message(f"✗ JAVDB获取失败: {av_code}")
                                
                        except subprocess.TimeoutExpired:
                            skipped_count += 1
                            log_message(f"✗ 获取超时: {av_code}")
                        except Exception as e:
                            skipped_count += 1
                            log_message(f"✗ 处理错误: {av_code} - {str(e)}")
                    
                    # 完成
                    progress_label.config(text="导入完成")
                    log_message(f"\n=== 导入完成 ===")
                    log_message(f"成功导入: {imported_count} 个")
                    log_message(f"跳过: {skipped_count} 个")
                    
                    cancel_button.config(text="关闭", command=progress_window.destroy)
                    
                    # 刷新视频列表
                    self.root.after(100, self.load_videos)
                    
                except ImportError:
                    log_message("错误: 无法导入番号提取器模块")
                    cancel_button.config(text="关闭", command=progress_window.destroy)
                except Exception as e:
                    log_message(f"批量导入过程中发生错误: {str(e)}")
                    cancel_button.config(text="关闭", command=progress_window.destroy)
            
            # 在后台线程中执行导入
            thread = threading.Thread(target=import_thread, daemon=True)
            thread.start()
            
        except Exception as e:
            messagebox.showerror("错误", f"批量导入JAVDB信息失败: {str(e)}")

    def get_actor_info_by_name(self, actor_name):
        """根据演员名称获取演员详细信息"""
        try:
            self.cursor.execute("""
                SELECT id, name, name_traditional, name_common, aliases, 
                       avatar_url, avatar_data, profile_url, movie_count,
                       birth_date, debut_date, height, measurements, description
                FROM actors 
                WHERE name = ? OR name_common = ? OR name_traditional = ?
                LIMIT 1
            """, (actor_name, actor_name, actor_name))
            return self.cursor.fetchone()
        except Exception as e:
            print(f"获取演员信息失败: {e}")
            return None
    
    def get_actor_movies_in_library(self, actor_name):
        """获取演员在媒体库中的影片"""
        try:
            self.cursor.execute("""
                SELECT DISTINCT v.id, v.file_name, v.file_path, j.javdb_title, 
                       j.javdb_code, j.release_date, j.cover_url
                FROM videos v
                JOIN video_actors va ON v.id = va.video_id
                JOIN actors a ON va.actor_id = a.id
                LEFT JOIN javdb_info j ON v.id = j.video_id
                WHERE a.name = ? OR a.name_common = ? OR a.name_traditional = ?
                ORDER BY j.release_date DESC
            """, (actor_name, actor_name, actor_name))
            return self.cursor.fetchall()
        except Exception as e:
            print(f"获取演员影片失败: {e}")
            return []
    
    def open_actor_detail(self, actor_name):
        """打开演员详情页面"""
        try:
            ActorDetailWindow(self.root, actor_name, self)
        except Exception as e:
            messagebox.showerror("错误", f"无法打开演员详情页面: {str(e)}")

    def select_video_by_id(self, video_id):
        """根据视频ID在主界面中选中对应的视频"""
        try:
            # 遍历树形控件中的所有项目
            for item in self.video_tree.get_children():
                # 获取项目的tags（包含video_id）
                tags = self.video_tree.item(item, 'tags')
                if tags and int(tags[0]) == video_id:
                    # 选中该项目
                    self.video_tree.selection_set(item)
                    self.video_tree.focus(item)
                    # 确保该项目可见
                    self.video_tree.see(item)
                    # 触发选择事件以更新详情面板
                    self.on_video_select(None)
                    return True
            
            # 如果在当前页面没找到，可能需要搜索或切换页面
            messagebox.showinfo("提示", "视频可能不在当前显示的列表中，请尝试搜索该视频")
            return False
            
        except Exception as e:
            print(f"选择视频失败: {e}")
            return False

    def __del__(self):
        """析构函数"""
        if hasattr(self, 'conn'):
            self.conn.close()


class ActorDetailWindow:
    """演员详情页面窗口"""
    
    def __init__(self, parent, actor_name, media_library):
        self.parent = parent
        self.actor_name = actor_name
        self.media_library = media_library
        
        # 获取演员信息
        self.actor_info = media_library.get_actor_info_by_name(actor_name)
        self.actor_movies = media_library.get_actor_movies_in_library(actor_name)
        
        self.create_window()
        
    def create_window(self):
        """创建演员详情窗口"""
        self.window = tk.Toplevel(self.parent)
        self.window.title(f"演员详情 - {self.actor_name}")
        self.window.geometry("800x600")
        self.window.transient(self.parent)
        self.window.grab_set()
        
        # 创建主框架
        main_frame = ttk.Frame(self.window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 创建演员信息区域
        self.create_actor_info_section(main_frame)
        
        # 创建分隔线
        separator = ttk.Separator(main_frame, orient='horizontal')
        separator.pack(fill=tk.X, pady=10)
        
        # 创建影片列表区域
        self.create_movies_section(main_frame)
        
        # 创建底部按钮
        self.create_bottom_buttons(main_frame)
    
    def create_actor_info_section(self, parent):
        """创建演员信息区域"""
        info_frame = ttk.Frame(parent)
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 左侧头像区域
        avatar_frame = ttk.Frame(info_frame)
        avatar_frame.pack(side=tk.LEFT, padx=(0, 20))
        
        # 头像标签
        self.avatar_label = ttk.Label(avatar_frame, text="头像")
        self.avatar_label.pack()
        
        # 加载头像
        self.load_avatar()
        
        # 右侧信息区域
        details_frame = ttk.Frame(info_frame)
        details_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        if self.actor_info:
            # 演员名称
            name_frame = ttk.Frame(details_frame)
            name_frame.pack(fill=tk.X, pady=2)
            ttk.Label(name_frame, text="姓名:", font=('Arial', 10, 'bold')).pack(side=tk.LEFT)
            ttk.Label(name_frame, text=self.actor_info[1] or "未知").pack(side=tk.LEFT, padx=(5, 0))
            
            # 繁体中文名
            if self.actor_info[2]:
                traditional_frame = ttk.Frame(details_frame)
                traditional_frame.pack(fill=tk.X, pady=2)
                ttk.Label(traditional_frame, text="繁体名:", font=('Arial', 10, 'bold')).pack(side=tk.LEFT)
                ttk.Label(traditional_frame, text=self.actor_info[2]).pack(side=tk.LEFT, padx=(5, 0))
            
            # 常用名
            if self.actor_info[3]:
                common_frame = ttk.Frame(details_frame)
                common_frame.pack(fill=tk.X, pady=2)
                ttk.Label(common_frame, text="常用名:", font=('Arial', 10, 'bold')).pack(side=tk.LEFT)
                ttk.Label(common_frame, text=self.actor_info[3]).pack(side=tk.LEFT, padx=(5, 0))
            
            # 别名
            if self.actor_info[4]:
                aliases_frame = ttk.Frame(details_frame)
                aliases_frame.pack(fill=tk.X, pady=2)
                ttk.Label(aliases_frame, text="别名:", font=('Arial', 10, 'bold')).pack(side=tk.LEFT)
                ttk.Label(aliases_frame, text=self.actor_info[4]).pack(side=tk.LEFT, padx=(5, 0))
            
            # 影片数量
            count_frame = ttk.Frame(details_frame)
            count_frame.pack(fill=tk.X, pady=2)
            ttk.Label(count_frame, text="媒体库影片:", font=('Arial', 10, 'bold')).pack(side=tk.LEFT)
            ttk.Label(count_frame, text=f"{len(self.actor_movies)} 部").pack(side=tk.LEFT, padx=(5, 0))
            
            # 其他信息
            if self.actor_info[10]:  # birth_date
                birth_frame = ttk.Frame(details_frame)
                birth_frame.pack(fill=tk.X, pady=2)
                ttk.Label(birth_frame, text="出生日期:", font=('Arial', 10, 'bold')).pack(side=tk.LEFT)
                ttk.Label(birth_frame, text=self.actor_info[10]).pack(side=tk.LEFT, padx=(5, 0))
            
            if self.actor_info[11]:  # debut_date
                debut_frame = ttk.Frame(details_frame)
                debut_frame.pack(fill=tk.X, pady=2)
                ttk.Label(debut_frame, text="出道日期:", font=('Arial', 10, 'bold')).pack(side=tk.LEFT)
                ttk.Label(debut_frame, text=self.actor_info[11]).pack(side=tk.LEFT, padx=(5, 0))
            
            if self.actor_info[12]:  # height
                height_frame = ttk.Frame(details_frame)
                height_frame.pack(fill=tk.X, pady=2)
                ttk.Label(height_frame, text="身高:", font=('Arial', 10, 'bold')).pack(side=tk.LEFT)
                ttk.Label(height_frame, text=self.actor_info[12]).pack(side=tk.LEFT, padx=(5, 0))
            
            if self.actor_info[13]:  # measurements
                measurements_frame = ttk.Frame(details_frame)
                measurements_frame.pack(fill=tk.X, pady=2)
                ttk.Label(measurements_frame, text="三围:", font=('Arial', 10, 'bold')).pack(side=tk.LEFT)
                ttk.Label(measurements_frame, text=self.actor_info[13]).pack(side=tk.LEFT, padx=(5, 0))
        else:
            ttk.Label(details_frame, text=f"未找到演员 '{self.actor_name}' 的详细信息", 
                     font=('Arial', 12)).pack(pady=20)
    
    def load_avatar(self):
        """加载演员头像"""
        try:
            if self.actor_info and self.actor_info[6] is not None:  # avatar_data
                # 从数据库加载头像
                import io
                from PIL import Image, ImageTk
                
                avatar_data = self.actor_info[6]
                if len(avatar_data) > 0:  # 确保头像数据不为空
                    image = Image.open(io.BytesIO(avatar_data))
                    # 兼容不同版本的PIL
                    try:
                        # 新版本PIL
                        image = image.resize((150, 200), Image.Resampling.LANCZOS)
                    except AttributeError:
                        # 旧版本PIL
                        image = image.resize((150, 200), Image.LANCZOS)
                    photo = ImageTk.PhotoImage(image)
                    
                    self.avatar_label.config(image=photo, text="")
                    self.avatar_label.image = photo  # 保持引用
                    return
            
            # 显示默认头像（没有头像数据或数据为空）
            self.avatar_label.config(text="暂无头像\n(150x200)", 
                                    width=20, height=10, 
                                    relief="solid", borderwidth=1,
                                    background="#f0f0f0")
        except Exception as e:
            print(f"加载头像失败: {e}")
            self.avatar_label.config(text="头像加载失败\n(150x200)", 
                                   width=20, height=10, 
                                   relief="solid", borderwidth=1,
                                   background="#ffeeee")
    
    def create_movies_section(self, parent):
        """创建影片列表区域"""
        movies_frame = ttk.LabelFrame(parent, text=f"在媒体库中的影片 ({len(self.actor_movies)} 部)")
        movies_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # 创建Treeview
        columns = ('title', 'code', 'release_date', 'file_name', 'online_status')
        self.movies_tree = ttk.Treeview(movies_frame, columns=columns, show='headings')
        
        # 设置列标题
        self.movies_tree.heading('title', text='标题')
        self.movies_tree.heading('code', text='番号')
        self.movies_tree.heading('release_date', text='发行日期')
        self.movies_tree.heading('file_name', text='文件名')
        self.movies_tree.heading('online_status', text='是否在线')
        
        # 设置列宽
        self.movies_tree.column('title', width=220)
        self.movies_tree.column('code', width=100)
        self.movies_tree.column('release_date', width=80)
        self.movies_tree.column('file_name', width=250)
        self.movies_tree.column('online_status', width=30)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(movies_frame, orient=tk.VERTICAL, command=self.movies_tree.yview)
        self.movies_tree.configure(yscrollcommand=scrollbar.set)
        
        # 布局
        self.movies_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 填充数据
        for movie in self.actor_movies:
            video_id, file_name, file_path, javdb_title, javdb_code, release_date, cover_url = movie
            
            # 检查视频是否在线
            is_online = self.media_library.is_video_online(int(video_id))
            online_status = "在线" if is_online else "离线"
            
            self.movies_tree.insert('', 'end', values=(
                javdb_title or file_name,
                javdb_code or "未知",
                release_date or "未知",
                file_name,
                online_status
            ), tags=(video_id,))
        
        # 绑定双击事件
        self.movies_tree.bind('<Double-1>', self.on_movie_double_click)
    
    def on_movie_double_click(self, event):
        """影片双击事件 - 直接播放视频"""
        selection = self.movies_tree.selection()
        if not selection:
            return  # 没有选中任何项目
        
        item = selection[0]
        video_id = self.movies_tree.item(item, 'tags')[0]
        
        # 直接播放视频
        try:
            import platform
            import subprocess
            import os
            
            # 从数据库获取视频信息
            cursor = self.media_library.cursor
            cursor.execute("SELECT file_path FROM videos WHERE id = ?", (video_id,))
            result = cursor.fetchone()
            if not result:
                messagebox.showerror("错误", "找不到视频信息")
                return
            
            file_path = result[0]
            is_nas_online = self.media_library.is_video_online(int(video_id))
            
            if not is_nas_online:
                messagebox.showwarning("警告", "文件离线，无法播放视频")
                return
                
            if not os.path.exists(file_path):
                messagebox.showerror("错误", "视频文件不存在")
                return
                
            # 跨平台播放
            system = platform.system()
            if system == "Darwin":  # macOS
                subprocess.run(["open", file_path])
            elif system == "Windows":
                os.startfile(file_path)
            elif system == "Linux":
                subprocess.run(["xdg-open", file_path])
            else:
                messagebox.showerror("错误", f"不支持的操作系统: {system}")
                
        except Exception as e:
            messagebox.showerror("错误", f"播放视频失败: {str(e)}")
    
    def create_bottom_buttons(self, parent):
        """创建底部按钮"""
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X)
        
        # 访问JAVDB页面按钮
        if self.actor_info and self.actor_info[7]:  # profile_url
            ttk.Button(button_frame, text="访问JAVDB页面", 
                      command=self.open_javdb_page).pack(side=tk.LEFT, padx=(0, 10))
        
        # 关闭按钮
        ttk.Button(button_frame, text="关闭", 
                  command=self.window.destroy).pack(side=tk.RIGHT)
    
    def open_javdb_page(self):
        """打开JAVDB页面"""
        try:
            import webbrowser
            webbrowser.open(self.actor_info[7])
        except Exception as e:
            messagebox.showerror("错误", f"无法打开链接: {str(e)}")


if __name__ == "__main__":
    app = MediaLibrary()
    app.run()