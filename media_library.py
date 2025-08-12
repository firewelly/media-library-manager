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
            'stars': {'width': 60, 'position': 1, 'text': '星级'},
            'tags': {'width': 120, 'position': 2, 'text': '标签'},
            'size': {'width': 80, 'position': 3, 'text': '大小'},
            'status': {'width': 60, 'position': 4, 'text': '状态'},
            'duration': {'width': 120, 'position': 5, 'text': '时长'},
            'resolution': {'width': 150, 'position': 6, 'text': '分辨率'},
            'file_created_time': {'width': 120, 'position': 7, 'text': '创建时间'},
            'top_folder': {'width': 120, 'position': 8, 'text': '顶层文件夹'},
            'full_path': {'width': 200, 'position': 9, 'text': '完整路径'},
            'year': {'width': 60, 'position': 10, 'text': '年份'}
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
                        self.column_config[col]['width'] = self.video_tree.column(col, 'width')
            
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
        
        # 销毁当前表格
        list_frame = self.video_tree.master
        self.video_tree.destroy()
        
        # 清理滚动条
        for widget in list_frame.winfo_children():
            widget.destroy()
        
        # 重新创建表格
        sorted_columns = sorted(self.column_config.items(), key=lambda x: x[1]['position'])
        columns = [col[0] for col in sorted_columns]
        
        self.video_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)
        
        # 设置列标题和宽度
        for col_name in columns:
            config = self.column_config[col_name]
            self.video_tree.heading(col_name, text=config['text'])
            self.video_tree.column(col_name, width=config['width'], minwidth=50)
        
        # 初始化排序状态
        self.sort_column_name = None
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
        self.video_tree.bind('<Double-1>', self.play_video)
        self.video_tree.bind('<Button-1>', self.on_tree_click)
        self.video_tree.bind('<Double-Button-1>', self.on_header_double_click)
        
        # 重新加载数据
        self.load_videos()
        
        # 恢复滚动位置
        self.root.after(100, lambda: self.video_tree.yview_moveto(scroll_top))
    
    def on_column_resize(self, event):
        """列宽度变化时保存配置"""
        # 延迟保存，避免频繁写入
        if hasattr(self, '_resize_timer'):
            self.root.after_cancel(self._resize_timer)
        self._resize_timer = self.root.after(1000, self.save_column_config)
    
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
            # 检查是否需要添加新字段
            self.cursor.execute("PRAGMA table_info(videos)")
            columns = [column[1] for column in self.cursor.fetchall()]
            
            # 添加缺失的字段
            if 'thumbnail_data' not in columns:
                self.cursor.execute('ALTER TABLE videos ADD COLUMN thumbnail_data BLOB')
                print("添加字段: thumbnail_data")
                
            if 'thumbnail_path' not in columns:
                self.cursor.execute('ALTER TABLE videos ADD COLUMN thumbnail_path TEXT')
                print("添加字段: thumbnail_path")
                
            if 'duration' not in columns:
                self.cursor.execute('ALTER TABLE videos ADD COLUMN duration INTEGER')
                print("添加字段: duration")
                
            if 'resolution' not in columns:
                self.cursor.execute('ALTER TABLE videos ADD COLUMN resolution TEXT')
                print("添加字段: resolution")
                
            if 'file_created_time' not in columns:
                self.cursor.execute('ALTER TABLE videos ADD COLUMN file_created_time TIMESTAMP')
                print("添加字段: file_created_time")
                
            if 'source_folder' not in columns:
                self.cursor.execute('ALTER TABLE videos ADD COLUMN source_folder TEXT')
                print("添加字段: source_folder")
                
            if 'md5_hash' not in columns:
                self.cursor.execute('ALTER TABLE videos ADD COLUMN md5_hash TEXT')
                print("添加字段: md5_hash")
                
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
        tools_menu.add_command(label="重新导入元数据", command=self.reimport_incomplete_metadata)
        tools_menu.add_command(label="完全重置数据库", command=self.full_database_reset)
        tools_menu.add_separator()
        tools_menu.add_command(label="批量生成封面", command=self.batch_generate_thumbnails)
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
        
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        search_entry.pack(fill=tk.X, padx=5, pady=5)
        search_entry.bind('<KeyRelease>', self.on_search)
        
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
        self.video_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)
        
        # 设置列标题和宽度，添加排序功能
        for col_name in columns:
            config = self.column_config[col_name]
            self.video_tree.heading(col_name, text=config['text'], 
                                  command=lambda c=col_name: self.sort_column(c))
            self.video_tree.column(col_name, width=config['width'], minwidth=50)
        
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
        
        # 绑定选择事件
        self.video_tree.bind('<<TreeviewSelect>>', self.on_video_select)
        self.video_tree.bind('<Double-1>', self.play_video)
        self.video_tree.bind('<Button-1>', self.on_tree_click)
        self.video_tree.bind('<Double-Button-1>', self.on_header_double_click)
        
        # 绑定拖拽事件
        self.video_tree.bind('<ButtonPress-1>', self.on_drag_start)
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
        
        # 详情内容
        detail_content = ttk.Frame(detail_frame)
        detail_content.pack(fill=tk.X, padx=5, pady=5)
        
        # 封面显示
        thumbnail_frame = ttk.Frame(detail_content)
        thumbnail_frame.pack(side=tk.LEFT, padx=(0, 10))
        
        self.thumbnail_label = ttk.Label(thumbnail_frame, text="无封面")
        self.thumbnail_label.pack()
        
        # 左侧详情
        detail_left = ttk.Frame(detail_content)
        detail_left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        ttk.Label(detail_left, text="标题:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.title_var = tk.StringVar()
        ttk.Entry(detail_left, textvariable=self.title_var, width=40).grid(row=0, column=1, sticky=tk.W, pady=2)
        
        # 星级显示和编辑
        ttk.Label(detail_left, text="星级:").grid(row=1, column=0, sticky=tk.W, pady=2)
        star_frame = ttk.Frame(detail_left)
        star_frame.grid(row=1, column=1, sticky=tk.W, pady=2)
        
        self.star_labels = []
        for i in range(5):
            star_label = ttk.Label(star_frame, text="☆", font=('Arial', 16))
            star_label.pack(side=tk.LEFT)
            star_label.bind("<Button-1>", lambda e, star=i+1: self.set_star_rating(star))
            star_label.bind("<Enter>", lambda e, star=i+1: self.highlight_stars(star))
            star_label.bind("<Leave>", lambda e: self.update_star_display())
            self.star_labels.append(star_label)
        
        ttk.Label(detail_left, text="描述:").grid(row=2, column=0, sticky=tk.NW, pady=2)
        self.desc_text = tk.Text(detail_left, height=3, width=40)
        self.desc_text.grid(row=2, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(detail_left, text="标签:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.tags_var = tk.StringVar()
        ttk.Entry(detail_left, textvariable=self.tags_var, width=40).grid(row=3, column=1, sticky=tk.W, pady=2)
        
        # 添加更多metadata显示
        ttk.Label(detail_left, text="年份:").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.year_var = tk.StringVar()
        ttk.Entry(detail_left, textvariable=self.year_var, width=40).grid(row=4, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(detail_left, text="类型:").grid(row=5, column=0, sticky=tk.W, pady=2)
        self.genre_var = tk.StringVar()
        ttk.Entry(detail_left, textvariable=self.genre_var, width=40).grid(row=5, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(detail_left, text="文件大小:").grid(row=6, column=0, sticky=tk.W, pady=2)
        self.filesize_var = tk.StringVar()
        ttk.Label(detail_left, textvariable=self.filesize_var).grid(row=6, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(detail_left, text="时长:").grid(row=7, column=0, sticky=tk.W, pady=2)
        self.duration_var = tk.StringVar()
        ttk.Label(detail_left, textvariable=self.duration_var).grid(row=7, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(detail_left, text="分辨率:").grid(row=8, column=0, sticky=tk.W, pady=2)
        self.resolution_var = tk.StringVar()
        ttk.Label(detail_left, textvariable=self.resolution_var).grid(row=8, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(detail_left, text="文件路径:").grid(row=9, column=0, sticky=tk.W, pady=2)
        self.filepath_var = tk.StringVar()
        ttk.Label(detail_left, textvariable=self.filepath_var, wraplength=300).grid(row=9, column=1, sticky=tk.W, pady=2)
        
        # 右侧操作按钮
        detail_right = ttk.Frame(detail_content)
        detail_right.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        
        ttk.Button(detail_right, text="播放", command=self.play_video).pack(fill=tk.X, pady=2)
        ttk.Button(detail_right, text="保存修改", command=self.save_video_info).pack(fill=tk.X, pady=2)
        ttk.Button(detail_right, text="设置星级", command=self.set_stars).pack(fill=tk.X, pady=2)
        ttk.Button(detail_right, text="添加标签", command=self.add_tag_to_video).pack(fill=tk.X, pady=2)
        ttk.Button(detail_right, text="生成封面", command=self.generate_thumbnail).pack(fill=tk.X, pady=2)
        ttk.Button(detail_right, text="删除视频", command=self.delete_video).pack(fill=tk.X, pady=2)
        
        # 状态栏
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 加载数据
        self.load_tags()
        self.load_videos()
        
    def add_folder(self):
        """添加文件夹"""
        folder_path = filedialog.askdirectory(title="选择要添加的文件夹")
        if folder_path:
            try:
                # 检查是否为NAS路径
                folder_type = "nas" if folder_path.startswith(("/Volumes", "//", "smb://")) else "local"
                
                self.cursor.execute(
                    "INSERT OR REPLACE INTO folders (folder_path, folder_type) VALUES (?, ?)",
                    (folder_path, folder_type)
                )
                self.conn.commit()
                
                self.status_var.set(f"已添加文件夹: {folder_path}")
                messagebox.showinfo("成功", f"文件夹已添加: {folder_path}")
            except Exception as e:
                messagebox.showerror("错误", f"添加文件夹失败: {str(e)}")
                
    def scan_media(self):
        """扫描媒体文件"""
        def scan_thread():
            try:
                self.status_var.set("正在扫描媒体文件...")
                
                # 获取所有活跃的文件夹
                self.cursor.execute("SELECT folder_path, folder_type FROM folders WHERE is_active = 1")
                folders = self.cursor.fetchall()
                
                video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'}
                scanned_count = 0
                
                for folder_path, folder_type in folders:
                    if not os.path.exists(folder_path):
                        continue
                        
                    for root, dirs, files in os.walk(folder_path):
                        for file in files:
                            if any(file.lower().endswith(ext) for ext in video_extensions):
                                file_path = os.path.join(root, file)
                                self.add_video_to_db(file_path, folder_type)
                                scanned_count += 1
                                
                                # 更新状态
                                if scanned_count % 10 == 0:
                                    self.status_var.set(f"已扫描 {scanned_count} 个文件...")
                                    self.root.update_idletasks()
                                
                self.status_var.set(f"扫描完成，共处理 {scanned_count} 个视频文件")
                self.root.after(0, self.load_videos)
                
            except Exception as e:
                self.status_var.set(f"扫描失败: {str(e)}")
                
        threading.Thread(target=scan_thread, daemon=True).start()
        
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
            is_nas_online = self.check_nas_status(file_path) if folder_type == "nas" else True
            
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
                
            # 生成缩略图（从视频的10%位置截取）
            cmd = [
                ffmpeg_cmd, "-i", file_path, "-ss", "00:00:10", "-vframes", "1",
                "-vf", "scale=200:150", "-y", temp_path
            ]
            
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
                # 调整大小
                image = image.resize((150, 112), Image.Resampling.LANCZOS)
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
            # 构建排序查询
            order_clause = "ORDER BY title"  # 默认排序
            if hasattr(self, 'sort_column_name') and self.sort_column_name:
                # 映射显示列名到数据库列名
                column_mapping = {
                    'title': 'title',
                    'stars': 'stars',
                    'tags': 'tags',
                    'size': 'file_size',
                    'status': 'is_nas_online',
                    'duration': 'duration',
                    'resolution': 'resolution',
                    'file_created_time': 'file_created_time',
                    'top_folder': 'source_folder',
                    'full_path': 'source_folder',
                    'year': 'year'
                }
                
                db_column = column_mapping.get(self.sort_column_name, 'title')
                direction = "DESC" if self.sort_reverse else "ASC"
                order_clause = f"ORDER BY {db_column} {direction}"
            
            query = f"SELECT * FROM videos {order_clause}"
            self.cursor.execute(query)
            videos = self.cursor.fetchall()
            
            for video in videos:
                video_id, file_path, file_name, file_size, file_hash, title, description, genre, year, rating, stars, tags, nas_path, is_nas_online, created_at, updated_at, thumbnail_data, thumbnail_path, duration, resolution, file_created_time, source_folder, md5_hash = video
                
                # 格式化星级显示（实心/空心星星组合）
                star_display = self.format_stars_display(stars)
                size_display = self.format_file_size(file_size) if file_size else ""
                status_display = "在线" if is_nas_online else "离线"
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
                
                # 根据列配置的位置顺序插入数据
                sorted_columns = sorted(self.column_config.items(), key=lambda x: x[1]['position'])
                values = []
                
                # 构建数据字典
                data_dict = {
                    'title': title or file_name,
                    'stars': star_display,
                    'tags': tags_display,
                    'size': size_display,
                    'status': status_display,
                    'duration': duration_display,
                    'resolution': resolution_display,
                    'file_created_time': file_created_display,
                    'top_folder': top_folder_display,
                    'full_path': full_path_display,
                    'year': year_display
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
            # 从folders表获取自定义文件库的顶层文件夹
            self.cursor.execute("SELECT DISTINCT folder_path FROM folders WHERE is_active = 1 ORDER BY folder_path")
            folders = self.cursor.fetchall()
            
            self.folder_listbox.delete(0, tk.END)
            self.folder_listbox.insert(0, "全部")
            
            # 存储文件夹路径映射，用于筛选
            self.folder_path_mapping = {"全部": None}
            
            for folder in folders:
                folder_path = folder[0]
                folder_name = os.path.basename(folder_path)
                self.folder_listbox.insert(tk.END, folder_name)
                self.folder_path_mapping[folder_name] = folder_path
                
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
    
    def on_tree_click(self, event):
        """处理Treeview点击事件，特别是星级列的点击"""
        # 如果正在拖拽，不处理其他点击事件
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
                video_id, file_path, file_name, file_size, file_hash, title, description, genre, year, rating, stars, tags, nas_path, is_nas_online, created_at, updated_at, thumbnail_data, thumbnail_path, duration, resolution, file_created_time, source_folder, md5_hash = video
                
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
                
        except Exception as e:
            messagebox.showerror("错误", f"加载视频详情失败: {str(e)}")
            
    def play_video(self, event=None):
        """播放视频（跨平台）"""
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
                    
            messagebox.showinfo("导入完成", f"成功导入 {imported_count} 个NFO文件")
            self.load_videos()
            
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
        """批量计算MD5"""
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
                self.cursor.execute("SELECT id, file_path FROM videos WHERE file_hash IS NULL OR file_hash = ''")
            else:  # 重新计算所有
                self.cursor.execute("SELECT id, file_path FROM videos")
                
            videos = self.cursor.fetchall()
            
            if not videos:
                messagebox.showinfo("信息", "没有需要计算MD5的文件")
                return
                
            # 创建进度窗口
            progress_window = tk.Toplevel(self.root)
            progress_window.title("计算MD5进度")
            progress_window.geometry("400x150")
            progress_window.transient(self.root)
            progress_window.grab_set()
            
            progress_label = ttk.Label(progress_window, text="准备计算...")
            progress_label.pack(pady=10)
            
            progress_bar = ttk.Progressbar(progress_window, length=300, mode='determinate')
            progress_bar.pack(pady=10)
            progress_bar['maximum'] = len(videos)
            
            cancel_button = ttk.Button(progress_window, text="取消")
            cancel_button.pack(pady=5)
            
            self.cancel_md5_calculation = False
            cancel_button.config(command=lambda: setattr(self, 'cancel_md5_calculation', True))
            
            def calculate_thread():
                calculated_count = 0
                for i, (video_id, file_path) in enumerate(videos):
                    if self.cancel_md5_calculation:
                        break
                        
                    progress_label.config(text=f"计算中: {os.path.basename(file_path)}")
                    progress_bar['value'] = i + 1
                    progress_window.update()
                    
                    if os.path.exists(file_path):
                        file_hash = self.calculate_file_hash(file_path)
                        if file_hash:
                            self.cursor.execute(
                                "UPDATE videos SET file_hash = ? WHERE id = ?",
                                (file_hash, video_id)
                            )
                            calculated_count += 1
                            
                self.conn.commit()
                progress_window.destroy()
                
                if not self.cancel_md5_calculation:
                    messagebox.showinfo("完成", f"已计算 {calculated_count} 个文件的MD5")
                    self.load_videos()
                    
            threading.Thread(target=calculate_thread, daemon=True).start()
            
        except Exception as e:
            messagebox.showerror("错误", f"批量计算MD5失败: {str(e)}")
            
    def smart_remove_duplicates(self):
        """智能去重"""
        try:
            # 查找重复的文件（基于哈希值）
            self.cursor.execute("""
                SELECT file_hash, COUNT(*) as count, 
                       GROUP_CONCAT(id) as ids, 
                       GROUP_CONCAT(file_path) as paths,
                       GROUP_CONCAT(file_created_time) as created_times,
                       GROUP_CONCAT(source_folder) as source_folders
                FROM videos 
                WHERE file_hash IS NOT NULL AND file_hash != ''
                GROUP BY file_hash 
                HAVING count > 1
            """)
            
            duplicates = self.cursor.fetchall()
            
            if not duplicates:
                messagebox.showinfo("信息", "没有发现重复文件")
                return
                
            # 创建去重选择窗口
            dup_window = tk.Toplevel(self.root)
            dup_window.title("智能去重")
            dup_window.geometry("600x500")
            dup_window.transient(self.root)
            dup_window.grab_set()
            
            ttk.Label(dup_window, text=f"发现 {len(duplicates)} 组重复文件，请选择保留策略：").pack(pady=10)
            
            strategy_var = tk.StringVar(value="oldest")
            ttk.Radiobutton(dup_window, text="保留最老的文件", variable=strategy_var, value="oldest").pack(anchor=tk.W, padx=20)
            ttk.Radiobutton(dup_window, text="保留最新的文件", variable=strategy_var, value="newest").pack(anchor=tk.W, padx=20)
            ttk.Radiobutton(dup_window, text="基于位置优先级保留", variable=strategy_var, value="location").pack(anchor=tk.W, padx=20)
            ttk.Radiobutton(dup_window, text="手动选择", variable=strategy_var, value="manual").pack(anchor=tk.W, padx=20)
            
            # 位置优先级设置
            priority_frame = ttk.LabelFrame(dup_window, text="位置优先级（从高到低）")
            priority_frame.pack(fill=tk.X, padx=20, pady=10)
            
            priority_text = tk.Text(priority_frame, height=4, width=50)
            priority_text.pack(padx=5, pady=5)
            priority_text.insert(tk.END, "本地硬盘\nNAS\n移动硬盘")
            
            def execute_dedup():
                strategy = strategy_var.get()
                removed_count = 0
                
                for file_hash, count, ids, paths, created_times, source_folders in duplicates:
                    id_list = ids.split(',')
                    path_list = paths.split(',')
                    time_list = created_times.split(',') if created_times else []
                    folder_list = source_folders.split(',') if source_folders else []
                    
                    keep_index = 0  # 默认保留第一个
                    
                    if strategy == "oldest" and time_list:
                        # 保留最老的
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
                        # 保留最新的
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
                        # 基于位置优先级
                        priorities = priority_text.get(1.0, tk.END).strip().split('\n')
                        best_priority = len(priorities)
                        
                        for i, folder in enumerate(folder_list):
                            for j, priority_location in enumerate(priorities):
                                if priority_location.lower() in folder.lower():
                                    if j < best_priority:
                                        best_priority = j
                                        keep_index = i
                                    break
                    
                    # 删除除了保留文件外的其他文件
                    for i, video_id in enumerate(id_list):
                        if i != keep_index:
                            self.cursor.execute("DELETE FROM videos WHERE id = ?", (video_id,))
                            removed_count += 1
                            
                self.conn.commit()
                dup_window.destroy()
                self.load_videos()
                messagebox.showinfo("完成", f"已删除 {removed_count} 个重复文件记录")
                
            ttk.Button(dup_window, text="执行去重", command=execute_dedup).pack(pady=20)
            
        except Exception as e:
            messagebox.showerror("错误", f"智能去重失败: {str(e)}")
            
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
                
            # 清空列表
            for item in file_tree.get_children():
                file_tree.delete(item)
                
            # 扫描文件
            video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'}
            for root, dirs, files in os.walk(source_path):
                for file in files:
                    if any(file.lower().endswith(ext) for ext in video_extensions):
                        file_path = os.path.join(root, file)
                        file_size = os.path.getsize(file_path)
                        size_str = self.format_file_size(file_size)
                        
                        # 检查是否在数据库中
                        self.cursor.execute("SELECT id FROM videos WHERE file_path = ?", (file_path,))
                        status = "数据库中" if self.cursor.fetchone() else "未入库"
                        
                        file_tree.insert('', 'end', text=file, values=(size_str, status), tags=(file_path,))
                        
        def execute_move():
            source_path = source_var.get()
            target_path = target_var.get()
            
            if not source_path or not target_path:
                messagebox.showerror("错误", "请选择源文件夹和目标文件夹")
                return
                
            if not os.path.exists(target_path):
                os.makedirs(target_path)
                
            moved_count = 0
            for item in file_tree.get_children():
                old_path = file_tree.item(item)['tags'][0]
                file_name = os.path.basename(old_path)
                new_path = os.path.join(target_path, file_name)
                
                try:
                    if copy_mode.get():
                        shutil.copy2(old_path, new_path)
                    else:
                        shutil.move(old_path, new_path)
                        
                    # 更新数据库
                    if update_db.get():
                        self.cursor.execute(
                            "UPDATE videos SET file_path = ?, source_folder = ? WHERE file_path = ?",
                            (new_path, target_path, old_path)
                        )
                        
                    moved_count += 1
                    
                except Exception as e:
                    print(f"移动文件失败 {old_path}: {str(e)}")
                    
            self.conn.commit()
            messagebox.showinfo("完成", f"已移动 {moved_count} 个文件")
            self.load_videos()
            
        ttk.Button(button_frame, text="扫描文件", command=scan_files).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="执行移动", command=execute_move).pack(side=tk.LEFT)
        
    def reimport_incomplete_metadata(self):
        """重新导入元数据不完整的视频"""
        def reimport_thread():
            try:
                self.status_var.set("正在检查元数据不完整的视频...")
                
                # 查找元数据不完整的视频
                self.cursor.execute("""
                    SELECT id, file_path, file_name FROM videos 
                    WHERE (duration IS NULL OR duration = 0) 
                       OR (resolution IS NULL OR resolution = '') 
                       OR (file_created_time IS NULL)
                       OR (source_folder IS NULL or source_folder = '')
                """)
                incomplete_videos = self.cursor.fetchall()
                
                if not incomplete_videos:
                    self.status_var.set("所有视频的元数据都已完整")
                    messagebox.showinfo("完成", "所有视频的元数据都已完整，无需重新导入")
                    return
                
                total_count = len(incomplete_videos)
                self.status_var.set(f"发现 {total_count} 个元数据不完整的视频，开始重新导入...")
                
                updated_count = 0
                for i, (video_id, file_path, file_name) in enumerate(incomplete_videos):
                    try:
                        # 检查文件是否存在
                        if not os.path.exists(file_path):
                            continue
                            
                        # 获取视频信息
                        duration, resolution = self.get_video_info(file_path)
                        
                        # 获取文件创建时间
                        file_created_time = None
                        try:
                            stat = os.stat(file_path)
                            file_created_time = datetime.fromtimestamp(
                                stat.st_birthtime if hasattr(stat, 'st_birthtime') else stat.st_ctime
                            )
                        except:
                            pass
                        
                        # 获取来源文件夹
                        source_folder = os.path.dirname(file_path)
                        
                        # 更新数据库
                        update_fields = []
                        update_values = []
                        
                        if duration is not None:
                            update_fields.append("duration = ?")
                            update_values.append(duration)
                            
                        if resolution is not None:
                            update_fields.append("resolution = ?")
                            update_values.append(resolution)
                            
                        if file_created_time is not None:
                            update_fields.append("file_created_time = ?")
                            update_values.append(file_created_time)
                            
                        if source_folder:
                            update_fields.append("source_folder = ?")
                            update_values.append(source_folder)
                        
                        if update_fields:
                            update_values.append(video_id)
                            sql = f"UPDATE videos SET {', '.join(update_fields)} WHERE id = ?"
                            self.cursor.execute(sql, update_values)
                            updated_count += 1
                        
                        # 更新进度
                        progress = int((i + 1) / total_count * 100)
                        self.status_var.set(f"重新导入进度: {progress}% ({i + 1}/{total_count})")
                        self.root.update_idletasks()
                        
                    except Exception as e:
                        print(f"重新导入视频元数据失败 {file_path}: {str(e)}")
                        continue
                
                self.conn.commit()
                self.status_var.set(f"重新导入完成，共更新 {updated_count} 个视频的元数据")
                
                # 刷新视频列表
                self.root.after(0, self.load_videos)
                
                messagebox.showinfo("完成", f"重新导入完成！\n\n检查到 {total_count} 个元数据不完整的视频\n成功更新 {updated_count} 个视频的元数据")
                
            except Exception as e:
                self.status_var.set(f"重新导入失败: {str(e)}")
                messagebox.showerror("错误", f"重新导入元数据失败: {str(e)}")
        
        # 确认对话框
        if messagebox.askyesno("确认", "是否重新导入所有元数据不完整的视频？\n\n这可能需要一些时间，特别是对于大量视频文件。"):
            threading.Thread(target=reimport_thread, daemon=True).start()
        

            
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
                        messagebox.showinfo("完成", f"数据库重置完成！\n\n恢复文件: {restored_files}\n新增文件: {new_files}\n总计: {total_files}")
                    else:
                        log_message("重置已取消")
                        cancel_button.config(text="关闭", command=progress_window.destroy)
                        
                except Exception as e:
                    progress_bar.stop()
                    log_message(f"重置失败: {str(e)}")
                    cancel_button.config(text="关闭", command=progress_window.destroy)
                    messagebox.showerror("错误", f"重置失败: {str(e)}")
                    
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
                stats_text.insert(tk.END, f"进度: {processed}/{total} ({processed/total*100:.1f}%)\n")
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
                            WHERE is_nas_online = 1 AND (thumbnail_data IS NULL OR thumbnail_data = '')
                            ORDER BY file_name
                        """
                        log_message("模式：仅生成缺失封面")
                    else:  # 重新生成所有封面
                        query = """
                            SELECT id, file_path, file_name, is_nas_online, thumbnail_data 
                            FROM videos 
                            WHERE is_nas_online = 1
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
                                
                            # 生成缩略图（从视频的10%位置截取）
                            cmd = [
                                ffmpeg_cmd, "-i", file_path, 
                                "-ss", "00:00:10", 
                                "-vframes", "1",
                                "-vf", "scale=200:150", 
                                "-y", temp_path
                            ]
                            
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
                        
                        messagebox.showinfo(
                            "完成", 
                            f"批量生成封面完成！\n\n" +
                            f"成功: {success_count}\n" +
                            f"失败: {failed_count}\n" +
                            f"跳过: {skipped_count}\n" +
                            f"总计: {processed}"
                        )
                    else:
                        log_message("批量生成已取消")
                        cancel_button.config(text="关闭", command=progress_window.destroy)
                        pause_button.config(state="disabled")
                        
                except Exception as e:
                    log_message(f"批量生成失败: {str(e)}")
                    cancel_button.config(text="关闭", command=progress_window.destroy)
                    pause_button.config(state="disabled")
                    messagebox.showerror("错误", f"批量生成失败: {str(e)}")
                    
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
                    # 获取所有有星级评分的视频
                    cursor = self.conn.cursor()
                    cursor.execute("""
                         SELECT id, file_path, stars, title 
                         FROM videos 
                         WHERE stars > 0 AND file_path IS NOT NULL AND file_path != ''
                         ORDER BY stars DESC, title
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
                    
                    for video_id, file_path, stars, title in videos:
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
                        
                        # 刷新视频列表
                        self.load_videos()
                        
                        cancel_button.config(text="关闭", command=progress_window.destroy)
                        
                        if renamed_count > 0:
                            messagebox.showinfo("同步完成", 
                                f"同步完成！\n\n" +
                                f"成功重命名: {renamed_count} 个文件\n" +
                                f"跳过: {skipped_count} 个文件\n" +
                                f"错误: {error_count} 个文件")
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
        columns = ('path', 'type', 'status')
        folder_tree = ttk.Treeview(folder_window, columns=columns, show='headings')
        
        folder_tree.heading('path', text='路径')
        folder_tree.heading('type', text='类型')
        folder_tree.heading('status', text='状态')
        
        folder_tree.column('path', width=400)
        folder_tree.column('type', width=80)
        folder_tree.column('status', width=80)
        
        folder_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 按钮
        button_frame = ttk.Frame(folder_window)
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        def add_folder_to_management():
            """在文件夹管理窗口中添加文件夹"""
            folder_path = filedialog.askdirectory(title="选择要添加的文件夹")
            if folder_path:
                try:
                    # 检查是否为NAS路径
                    folder_type = "nas" if folder_path.startswith(("/Volumes", "//", "smb://")) else "local"
                    
                    self.cursor.execute(
                        "INSERT OR REPLACE INTO folders (folder_path, folder_type) VALUES (?, ?)",
                        (folder_path, folder_type)
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
            
            for folder in folders:
                folder_id, folder_path, folder_type, is_active, created_at = folder
                status = "活跃" if is_active else "禁用"
                folder_tree.insert('', 'end', values=(folder_path, folder_type, status), tags=(folder_id,))
                
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
        # 清空现有数据
        for item in self.video_tree.get_children():
            self.video_tree.delete(item)
            
        try:
            # 构建查询条件
            conditions = []
            params = []
            
            # 搜索条件
            search_text = self.search_var.get().strip()
            if search_text:
                conditions.append("(title LIKE ? OR file_name LIKE ? OR tags LIKE ?)")
                search_param = f"%{search_text}%"
                params.extend([search_param, search_param, search_param])
                
            # 星级筛选
            star_filter = self.star_filter.get()
            if star_filter > 0:
                conditions.append("stars = ?")
                params.append(star_filter)
                
            # 标签筛选
            selected_tags = [self.tags_listbox.get(i) for i in self.tags_listbox.curselection()]
            if selected_tags:
                tag_conditions = []
                for tag in selected_tags:
                    tag_conditions.append("tags LIKE ?")
                    params.append(f"%{tag}%")
                if tag_conditions:
                    conditions.append(f"({' OR '.join(tag_conditions)})")
                    
            # NAS状态筛选
            nas_filter = self.nas_filter.get()
            if nas_filter == "online":
                conditions.append("is_nas_online = 1")
            elif nas_filter == "offline":
                conditions.append("is_nas_online = 0")
                
            # 仅显示在线内容筛选
            if hasattr(self, 'show_online_only') and self.show_online_only.get():
                conditions.append("is_nas_online = 1")
                
            # 文件夹来源筛选
            selected_folder_indices = self.folder_listbox.curselection()
            if selected_folder_indices and hasattr(self, 'folder_path_mapping'):
                selected_folder = self.folder_listbox.get(selected_folder_indices[0])
                if selected_folder != "全部" and selected_folder in self.folder_path_mapping:
                    folder_path = self.folder_path_mapping[selected_folder]
                    conditions.append("source_folder LIKE ?")
                    params.append(f"{folder_path}%")
                
            # 构建最终查询
            query = "SELECT * FROM videos"
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY title"
            
            self.cursor.execute(query, params)
            videos = self.cursor.fetchall()
            
            # 显示结果
            for video in videos:
                video_id, file_path, file_name, file_size, file_hash, title, description, genre, year, rating, stars, tags, nas_path, is_nas_online, created_at, updated_at, thumbnail_data, thumbnail_path, duration, resolution, file_created_time, source_folder = video
                
                star_display = "★" * stars if stars > 0 else ""
                size_display = self.format_file_size(file_size) if file_size else ""
                status_display = "在线" if is_nas_online else "离线"
                tags_display = tags if tags else ""
                year_display = str(year) if year else ""
                
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
                source_folder_display = ""
                if source_folder:
                    source_folder_display = os.path.basename(source_folder) or source_folder
                
                self.video_tree.insert('', 'end', values=(
                    title or file_name,
                    star_display,
                    tags_display,
                    size_display,
                    status_display,
                    duration_display,
                    resolution_display,
                    file_created_display,
                    source_folder_display,
                    year_display
                ), tags=(video_id,))
                
        except Exception as e:
            messagebox.showerror("错误", f"筛选失败: {str(e)}")
    
    def show_context_menu(self, event):
        """显示右键菜单"""
        # 获取点击的项目
        item = self.video_tree.identify_row(event.y)
        if not item:
            return
            
        # 选中该项目
        self.video_tree.selection_set(item)
        
        # 获取视频信息
        video_id = self.video_tree.item(item)['tags'][0]
        self.cursor.execute("SELECT file_path, is_nas_online FROM videos WHERE id = ?", (video_id,))
        result = self.cursor.fetchone()
        
        if not result:
            return
            
        file_path, is_nas_online = result
        
        # 只为在线文件显示右键菜单
        if not is_nas_online:
            return
            
        # 创建右键菜单
        context_menu = tk.Menu(self.root, tearoff=0)
        context_menu.add_command(label="删除文件", command=lambda: self.delete_file_from_context(video_id, file_path))
        
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
                                command=lambda fp=folder_path: self.move_file_to_folder(video_id, file_path, fp))
        
        # 显示菜单
        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.grab_release()
    
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
            
    def comprehensive_media_update(self):
        """智能媒体库更新 - 合并扫描新文件和更新移动文件的功能"""
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
                
                # 第一阶段：检查现有文件并处理移动/删除
                log_message("第一阶段：检查现有文件状态...")
                self.cursor.execute("SELECT id, file_path, source_folder, md5_hash FROM videos")
                existing_videos = self.cursor.fetchall()
                
                total_existing = len(existing_videos)
                log_message(f"数据库中共有 {total_existing} 个文件记录")
                
                # 获取所有活跃文件夹
                self.cursor.execute("SELECT folder_path FROM folders WHERE is_active = 1")
                active_folders = [row[0] for row in self.cursor.fetchall()]
                
                for i, (video_id, file_path, source_folder, md5_hash) in enumerate(existing_videos):
                    progress = (i / (total_existing + 1)) * 50  # 前50%进度用于检查现有文件
                    progress_var.set(progress)
                    status_var.set(f"检查现有文件 {i+1}/{total_existing}")
                    update_stats(scanned_count, new_files_count, updated_files_count, removed_files_count, md5_updated_count)
                    
                    if os.path.exists(file_path):
                        # 文件存在，检查是否需要更新MD5
                        if not md5_hash:
                            try:
                                new_md5 = self.calculate_file_hash(file_path)
                                self.cursor.execute("UPDATE videos SET md5_hash = ? WHERE id = ?", (new_md5, video_id))
                                md5_updated_count += 1
                                log_message(f"更新MD5: {os.path.basename(file_path)}")
                            except Exception as e:
                                log_message(f"计算MD5失败: {os.path.basename(file_path)} - {str(e)}")
                    else:
                        # 文件不存在，尝试通过MD5查找移动的文件
                        if md5_hash:
                            found_path = None
                            for folder_path in active_folders:
                                for root, dirs, files in os.walk(folder_path):
                                    for file in files:
                                        if file.lower().endswith(('.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v')):
                                            potential_path = os.path.join(root, file)
                                            try:
                                                if self.calculate_file_hash(potential_path) == md5_hash:
                                                    found_path = potential_path
                                                    break
                                            except:
                                                continue
                                    if found_path:
                                        break
                                if found_path:
                                    break
                            
                            if found_path:
                                # 检查新路径是否已存在于数据库中
                                self.cursor.execute("SELECT id FROM videos WHERE file_path = ? AND id != ?", (found_path, video_id))
                                existing = self.cursor.fetchone()
                                
                                if existing:
                                    # 删除当前记录（避免重复）
                                    self.cursor.execute("DELETE FROM videos WHERE id = ?", (video_id,))
                                    removed_files_count += 1
                                    log_message(f"删除重复记录: {os.path.basename(file_path)}")
                                else:
                                    # 更新路径
                                    new_source_folder = os.path.dirname(found_path)
                                    self.cursor.execute(
                                        "UPDATE videos SET file_path = ?, source_folder = ? WHERE id = ?",
                                        (found_path, new_source_folder, video_id)
                                    )
                                    updated_files_count += 1
                                    log_message(f"文件移动更新: {os.path.basename(file_path)} -> {found_path}")
                            else:
                                # 删除不存在的文件记录
                                self.cursor.execute("DELETE FROM videos WHERE id = ?", (video_id,))
                                removed_files_count += 1
                                log_message(f"删除无效记录: {os.path.basename(file_path)}")
                        else:
                            # 没有MD5，尝试按文件名和大小查找
                            file_name = os.path.basename(file_path)
                            found_path = None
                            
                            for folder_path in active_folders:
                                for root, dirs, files in os.walk(folder_path):
                                    if file_name in files:
                                        potential_path = os.path.join(root, file_name)
                                        if os.path.exists(potential_path):
                                            found_path = potential_path
                                            break
                                if found_path:
                                    break
                            
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
                                    # 更新路径
                                    new_source_folder = os.path.dirname(found_path)
                                    self.cursor.execute(
                                        "UPDATE videos SET file_path = ?, source_folder = ? WHERE id = ?",
                                        (found_path, new_source_folder, video_id)
                                    )
                                    updated_files_count += 1
                                    log_message(f"文件移动更新: {file_name} -> {found_path}")
                            else:
                                # 删除不存在的文件记录
                                self.cursor.execute("DELETE FROM videos WHERE id = ?", (video_id,))
                                removed_files_count += 1
                                log_message(f"删除无效记录: {file_name}")
                    
                    # 每处理100个文件提交一次
                    if i % 100 == 0:
                        self.conn.commit()
                
                # 第二阶段：扫描新文件
                log_message("\n第二阶段：扫描新文件...")
                
                # 获取数据库中已有的文件路径
                self.cursor.execute("SELECT file_path FROM videos")
                existing_paths = set(row[0] for row in self.cursor.fetchall())
                
                total_files_to_scan = 0
                for folder_path in active_folders:
                    for root, dirs, files in os.walk(folder_path):
                        for file in files:
                            if file.lower().endswith(('.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v')):
                                total_files_to_scan += 1
                
                log_message(f"发现 {total_files_to_scan} 个视频文件需要检查")
                
                for folder_path in active_folders:
                    log_message(f"扫描文件夹: {folder_path}")
                    
                    for root, dirs, files in os.walk(folder_path):
                        for file in files:
                            if file.lower().endswith(('.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v')):
                                file_path = os.path.join(root, file)
                                scanned_count += 1
                                
                                progress = 50 + (scanned_count / total_files_to_scan) * 50  # 后50%进度用于扫描新文件
                                progress_var.set(progress)
                                status_var.set(f"扫描新文件 {scanned_count}/{total_files_to_scan}")
                                update_stats(scanned_count, new_files_count, updated_files_count, removed_files_count, md5_updated_count)
                                
                                if file_path not in existing_paths:
                                    # 这是新文件，添加到数据库
                                    try:
                                        # 解析文件名获取标题和星级
                                        title = self.parse_title_from_filename(file)
                                        stars = self.parse_stars_from_filename(file)
                                        
                                        # 获取文件信息
                                        file_size = os.path.getsize(file_path)
                                        
                                        # 计算MD5
                                        md5_hash = self.calculate_file_hash(file_path)
                                        
                                        # 插入数据库
                                        self.cursor.execute("""
                                            INSERT INTO videos (file_path, title, stars, file_size, source_folder, md5_hash)
                                            VALUES (?, ?, ?, ?, ?, ?)
                                        """, (file_path, title, stars, file_size, root, md5_hash))
                                        
                                        new_files_count += 1
                                        existing_paths.add(file_path)
                                        log_message(f"新增文件: {file}")
                                        
                                    except Exception as e:
                                        log_message(f"添加文件失败: {file} - {str(e)}")
                                
                                # 每处理100个文件提交一次
                                if scanned_count % 100 == 0:
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
                
                # 刷新视频列表
                self.load_videos()
                
                messagebox.showinfo("完成", 
                    f"智能媒体库更新完成！\n\n"
                    f"总扫描文件: {scanned_count}\n"
                    f"新增文件: {new_files_count}\n"
                    f"路径更新: {updated_files_count}\n"
                    f"删除无效记录: {removed_files_count}\n"
                    f"MD5更新: {md5_updated_count}")
                
            except Exception as e:
                log_message(f"错误: {str(e)}")
                messagebox.showerror("错误", f"智能媒体库更新时出错: {str(e)}")
        
        # 在新线程中执行更新
        threading.Thread(target=comprehensive_update, daemon=True).start()
    

    
    def run(self):
        """运行应用程序"""
        self.root.mainloop()
        
    def __del__(self):
        """析构函数"""
        if hasattr(self, 'conn'):
            self.conn.close()

if __name__ == "__main__":
    app = MediaLibrary()
    app.run()