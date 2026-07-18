# -*- coding: utf-8 -*-
"""
主窗口
布局：左侧导航 + 中间列表 + 右侧详情
集成数据库、搜索、筛选、排序、对话框
"""

import os
import logging
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QFrame, QStatusBar,
    QSizePolicy, QFileDialog, QMessageBox, QMenu
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QAction, QKeySequence

from ..widgets import Sidebar, VideoTable, DetailPanel, FilterBar, Pagination
from ..theme import get_main_qss
from ..core import Database, VideoRepository, ActorRepository, TagRepository
from ..workers import DataLoaderWorker, CoverLoaderWorker, TaskWorker
from ..dialogs import (
    ActorDialog, TagDialog, ScanDialog, SettingsDialog, TaskProgressDialog,
    FolderDialog, SmartUpdateDialog, DedupDialog
)

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("媒体库管理器 v4")
        self.setMinimumSize(1280, 800)
        self.resize(1600, 900)

        # 应用样式
        self.setStyleSheet(get_main_qss())

        # 初始化数据库
        self.db = Database()
        self.video_repo = VideoRepository(self.db) if self.db.is_connected else None
        self.actor_repo = ActorRepository(self.db) if self.db.is_connected else None
        self.tag_repo = TagRepository(self.db) if self.db.is_connected else None

        # 状态
        self._current_data = []
        self._total_count = 0
        self._search_text = ""
        self._filters = {}
        self._sort_by = "created_at"
        self._sort_order = "DESC"
        self._cover_workers = []

        # 搜索防抖
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._do_search)

        self._setup_ui()
        self._create_menus()
        self._create_shortcuts()
        self._load_initial_data()

    def _setup_ui(self):
        """初始化 UI"""
        # 中心部件
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 左侧导航
        self.sidebar = Sidebar()
        self.sidebar.nav_selected.connect(self._on_nav_selected)
        main_layout.addWidget(self.sidebar)

        # 中间主区
        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)

        # 顶部工具栏
        topbar = self._create_topbar()
        center_layout.addWidget(topbar)

        # 筛选条
        self.filterbar = FilterBar()
        self.filterbar.filter_changed.connect(self._on_filter_changed)
        center_layout.addWidget(self.filterbar)

        # 内容区（列表 + 详情）
        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # 视频列表
        self.video_table = VideoTable()
        self.video_table.item_selected.connect(self._on_item_selected)
        self.video_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.video_table.customContextMenuRequested.connect(self._show_context_menu)
        content_layout.addWidget(self.video_table, 1)

        # 右侧详情
        self.detail_panel = DetailPanel()
        self.detail_panel.save_clicked.connect(self._on_detail_save)
        self.detail_panel.set_star_clicked.connect(self._on_detail_set_star)
        self.detail_panel.add_tag_clicked.connect(self._on_detail_add_tag)
        self.detail_panel.fetch_javdb_clicked.connect(self._on_detail_fetch_javdb)
        self.detail_panel.generate_thumbnail_clicked.connect(self._on_detail_generate_thumbnail)
        self.detail_panel.delete_clicked.connect(self._on_detail_delete)
        content_layout.addWidget(self.detail_panel)

        center_layout.addWidget(content, 1)

        # 分页组件
        self.pagination = Pagination()
        self.pagination.page_changed.connect(self._on_page_changed)
        center_layout.addWidget(self.pagination)

        # 底部状态栏
        statusbar = self._create_statusbar()
        center_layout.addWidget(statusbar)

        main_layout.addWidget(center, 1)

    def _create_topbar(self) -> QWidget:
        """创建顶部工具栏"""
        topbar = QFrame()
        topbar.setObjectName("topbar")

        layout = QHBoxLayout(topbar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)

        # 搜索框
        search_box = QFrame()
        search_box.setObjectName("searchBox")
        search_layout = QHBoxLayout(search_box)
        search_layout.setContentsMargins(12, 0, 12, 0)
        search_layout.setSpacing(8)

        search_icon = QLabel("⌕")
        search_icon.setStyleSheet("color: #6b7382; font-size: 14px;")
        search_layout.addWidget(search_icon)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索标题 / 番号 / 演员 / 标签…")
        self.search_input.setStyleSheet("background: transparent; border: none; color: #f2f4f8;")
        self.search_input.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self.search_input)

        kbd = QLabel("⌘K")
        kbd.setStyleSheet("""
            color: #6b7382;
            font-size: 11px;
            border: 1px solid #1f232c;
            border-radius: 4px;
            padding: 1px 5px;
            font-family: monospace;
        """)
        search_layout.addWidget(kbd)

        layout.addWidget(search_box)

        # 筛选按钮
        btn_filter = QPushButton("筛选 ▾")
        layout.addWidget(btn_filter)

        # 星级筛选
        self.btn_stars = QPushButton("星级 ≥ 3")
        self.btn_stars.setProperty("active", "true")
        self.btn_stars.clicked.connect(self._toggle_star_filter)
        layout.addWidget(self.btn_stars)

        # 排序
        self.btn_sort = QPushButton("排序：创建时间 ▾")
        self.btn_sort.clicked.connect(self._cycle_sort)
        layout.addWidget(self.btn_sort)

        layout.addStretch()

        # 视图切换
        view_seg = QFrame()
        view_seg.setStyleSheet("""
            QFrame {
                background-color: #0a0c0f;
                border: 1px solid #1f232c;
                border-radius: 8px;
                padding: 2px;
            }
        """)
        view_layout = QHBoxLayout(view_seg)
        view_layout.setContentsMargins(2, 2, 2, 2)
        view_layout.setSpacing(2)

        self.btn_list_view = QPushButton("☰ 列表")
        self.btn_list_view.setProperty("active", "true")
        self.btn_list_view.setStyleSheet("""
            QPushButton {
                background-color: #2a2f3a;
                border: none;
                border-radius: 6px;
                color: #f2f4f8;
                font-weight: 600;
                padding: 0 12px;
                min-height: 26px;
            }
        """)
        view_layout.addWidget(self.btn_list_view)

        self.btn_grid_view = QPushButton("▦ 封面墙")
        self.btn_grid_view.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 6px;
                color: #6b7382;
                padding: 0 12px;
                min-height: 26px;
            }
            QPushButton:hover {
                color: #f2f4f8;
            }
        """)
        view_layout.addWidget(self.btn_grid_view)

        layout.addWidget(view_seg)

        # 扫描按钮
        btn_scan = QPushButton("⟳ 扫描媒体库")
        btn_scan.setProperty("primary", "true")
        btn_scan.clicked.connect(self._open_scan_dialog)
        layout.addWidget(btn_scan)

        return topbar

    def _create_statusbar(self) -> QWidget:
        """创建底部状态栏"""
        statusbar = QFrame()
        statusbar.setObjectName("statusbar")

        layout = QHBoxLayout(statusbar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(16)

        self.status_total = QLabel("共 0 条")
        layout.addWidget(self.status_total)

        self.status_loaded = QLabel("已加载 0 条")
        layout.addWidget(self.status_loaded)

        self.status_perf = QLabel("")
        self.status_perf.setStyleSheet("color: #3fb950; font-family: monospace; font-size: 11px;")
        layout.addWidget(self.status_perf)

        layout.addStretch()

        self.status_row_height = QLabel("行高：紧凑 ▾")
        layout.addWidget(self.status_row_height)

        self.status_columns = QLabel("18 列 · 已显示 9 列")
        layout.addWidget(self.status_columns)

        return statusbar

    def _load_initial_data(self):
        """加载初始数据"""
        if not self.video_repo:
            logger.warning("数据库未连接，无法加载数据")
            self.status_total.setText("数据库未连接")
            return

        # 加载统计
        try:
            total = self.video_repo.total_count()
            fav = self.video_repo.favorites_count()
            recent = self.video_repo.recent_count()
            no_tags = self.video_repo.no_tags_count()

            self.sidebar.all_videos.count_label.setText(f"{total:,}")
            self.sidebar.favorites.count_label.setText(f"{fav:,}")
            self.sidebar.recent.count_label.setText(f"{recent:,}")
            self.sidebar.no_tags.count_label.setText(f"{no_tags:,}")

            self.status_total.setText(f"共 {total:,} 条")
        except Exception as e:
            logger.error(f"加载统计失败: {e}")

        # 加载视频列表
        self._load_videos()

    def _load_videos(self):
        """异步加载视频列表"""
        if not self.video_repo:
            return

        page = self.pagination.get_current_page()
        page_size = self.pagination.get_page_size()
        offset = (page - 1) * page_size

        self._worker = DataLoaderWorker(
            repo=self.video_repo,
            offset=offset,
            limit=page_size,
            search=self._search_text,
            filters=self._filters,
            sort_by=self._sort_by,
            sort_order=self._sort_order,
        )
        self._worker.finished.connect(self._on_data_loaded)
        self._worker.error.connect(self._on_data_error)
        self._worker.start()

    def _on_data_loaded(self, rows: list, total: int, elapsed_ms: int):
        """数据加载完成"""
        self._current_data = rows
        self._total_count = total

        # 更新分页
        self.pagination.set_total(total)

        # 转换为表格格式
        table_data = []
        for row in rows:
            actors = row.get("_actors", [])
            actors_text = ", ".join([a.get("name", "") for a in actors[:2]])
            if len(actors) > 2:
                actors_text += f" +{len(actors) - 2}"

            file_size = row.get("file_size", 0) or 0
            if file_size >= 1024**3:
                size_str = f"{file_size / (1024**3):.2f} GB"
            elif file_size >= 1024**2:
                size_str = f"{file_size / (1024**2):.1f} MB"
            else:
                size_str = ""
            
            duration_sec = row.get("duration", 0)
            duration_str = f"{duration_sec // 3600}:{(duration_sec % 3600) // 60:02d}:{duration_sec % 60:02d}" if duration_sec else ""

            table_data.append({
                "id": row.get("id"),
                "title": row.get("title") or row.get("file_name", ""),
                "code": row.get("javdb_code", ""),
                "actors": actors_text,
                "stars": row.get("stars", 0),
                "tags": row.get("_tags_list", []),
                "size": size_str,
                "online": bool(row.get("is_nas_online", True)),
                "duration": duration_str,
                "date": (row.get("file_created_time") or row.get("created_at", ""))[:10],
                "release_date": row.get("release_date", ""),
                "resolution": row.get("resolution", ""),
                "device": self._guess_device(row.get("file_path", "")),
                "path": row.get("file_path", ""),
                "javdb_score": row.get("javdb_score"),
                "_cover_path": row.get("local_cover_path"),
                "_cover_data": row.get("cover_image_data"),
            })

        self.video_table.set_data(table_data)
        self.status_loaded.setText(f"已加载 {len(table_data)} 条")
        self.status_perf.setText(f"查询耗时 {elapsed_ms}ms")
        self.filterbar.set_match_count(total, elapsed_ms)

    def _on_data_error(self, error: str):
        """数据加载错误"""
        logger.error(f"数据加载失败: {error}")
        self.status_perf.setText(f"错误: {error}")

    def _guess_device(self, file_path: str) -> str:
        """猜测文件所在设备"""
        if file_path.startswith("/Volumes/app"):
            return "NAS · app"
        elif file_path.startswith("/Volumes/Video"):
            return "NAS · Video"
        elif file_path.startswith("/Users/firewell"):
            return "本地磁盘"
        else:
            return "未知"

    def _on_nav_selected(self, text: str):
        """导航选中处理"""
        nav_map = {
            "全部视频": lambda: self._apply_nav_filter({}),
            "收藏": lambda: self._apply_nav_filter({"stars_min": 4}),
            "最近添加": lambda: self._apply_nav_filter({"recent_days": 30}),
            "无标签": lambda: self._apply_nav_filter({"no_tags": True}),
            "本地磁盘": lambda: self._apply_nav_filter({"folder": "/Users/firewell"}),
            "NAS · app": lambda: self._apply_nav_filter({"folder": "/Volumes/app"}),
            "NAS · Video": lambda: self._apply_nav_filter({"folder": "/Volumes/Video"}),
            "演员库": self._open_actor_dialog,
            "标签管理": self._open_tag_dialog,
            "文件夹管理": self._on_manage_folders,
            "设置": self._open_settings_dialog,
        }

        handler = nav_map.get(text)
        if handler:
            handler()

    def _apply_nav_filter(self, filters: dict):
        """应用导航筛选"""
        self._filters = filters
        self._load_videos()

    def _on_item_selected(self, data: dict):
        """列表项选中处理"""
        self.detail_panel.set_data(data)

        # 异步加载封面
        cover_path = data.get("_cover_path")
        cover_data = data.get("_cover_data")
        if cover_path or cover_data:
            worker = CoverLoaderWorker(data.get("id", 0), cover_path, cover_data)
            worker.loaded.connect(self._on_cover_loaded)
            worker.error.connect(self._on_cover_error)
            self._cover_workers.append(worker)
            worker.start()

    def _on_cover_loaded(self, video_id: int, pixmap: QPixmap):
        """封面加载完成"""
        if self.detail_panel._data and self.detail_panel._data.get("id") == video_id:
            self.detail_panel.cover.setPixmap(pixmap)
            self.detail_panel.cover.setText("")

    def _on_cover_error(self, video_id: int, error: str):
        """封面加载错误"""
        logger.debug(f"封面加载失败: {error}")

    def _on_search_changed(self, text: str):
        """搜索框变化处理（防抖）"""
        self._search_text = text
        self._search_timer.start(300)  # 300ms 防抖

    def _do_search(self):
        """执行搜索"""
        self._load_videos()

    def _on_filter_changed(self, filters: list):
        """筛选条件变化处理"""
        # 解析筛选条中的筛选条件
        self._filters = {}
        for f in filters:
            if "星级" in f:
                self._filters["stars_min"] = 3
            elif "在线" in f:
                self._filters["online_only"] = True
            elif "标签" in f:
                # 提取标签名
                import re
                match = re.search(r'标签：(.+)', f)
                if match:
                    self._filters["tag"] = match.group(1)
        self._load_videos()

    def _on_page_changed(self, page: int, page_size: int):
        """分页变化处理"""
        self._load_videos()

    def _toggle_star_filter(self):
        """切换星级筛选"""
        active = self.btn_stars.property("active")
        if active:
            self.btn_stars.setProperty("active", "false")
            self._filters.pop("stars_min", None)
        else:
            self.btn_stars.setProperty("active", "true")
            self._filters["stars_min"] = 3

        self.btn_stars.style().unpolish(self.btn_stars)
        self.btn_stars.style().polish(self.btn_stars)
        self._load_videos()

    def _cycle_sort(self):
        """循环切换排序"""
        sort_options = [
            ("created_at", "DESC", "创建时间 ▾"),
            ("created_at", "ASC", "创建时间 ▴"),
            ("title", "ASC", "标题 ▴"),
            ("title", "DESC", "标题 ▾"),
            ("file_size", "DESC", "大小 ▾"),
            ("file_size", "ASC", "大小 ▴"),
            ("stars", "DESC", "星级 ▾"),
            ("stars", "ASC", "星级 ▴"),
        ]

        current = (self._sort_by, self._sort_order)
        idx = next((i for i, (s, o, _) in enumerate(sort_options) if (s, o) == current), 0)
        next_idx = (idx + 1) % len(sort_options)

        self._sort_by, self._sort_order, label = sort_options[next_idx]
        self.btn_sort.setText(f"排序：{label}")
        self._load_videos()

    def _open_actor_dialog(self):
        """打开演员库对话框"""
        if self.actor_repo:
            dialog = ActorDialog(self.db, self)
            dialog.exec()

    def _open_tag_dialog(self):
        """打开标签管理对话框"""
        if self.tag_repo:
            dialog = TagDialog(self.db, self)
            dialog.exec()

    def _open_scan_dialog(self):
        """打开扫描进度对话框"""
        dialog = ScanDialog(self)
        dialog.start_scan()
        dialog.exec()

    def _open_settings_dialog(self):
        """打开设置对话框"""
        dialog = SettingsDialog(self)
        dialog.exec()

    def _create_menus(self):
        """创建菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件(&F)")
        file_menu.addAction("扫描媒体文件", self._on_scan_media)
        file_menu.addAction("智能媒体库更新", self._on_comprehensive_update)
        file_menu.addSeparator()
        file_menu.addAction("导入 NFO 文件", self._on_import_nfo)
        file_menu.addAction("导入视频文件", self._on_import_videos)
        file_menu.addSeparator()
        file_menu.addAction("批量导入 NFO 信息", self._on_batch_import_nfo_for_no_actors)
        file_menu.addAction("批量导入 JAVDB 信息", self._on_batch_import_javdb_for_no_title)
        file_menu.addSeparator()
        file_menu.addAction("去重复", self._on_remove_duplicates)

        # 工具菜单
        tools_menu = menubar.addMenu("工具(&T)")
        tools_menu.addAction("标签管理", self._open_tag_dialog)
        tools_menu.addAction("文件夹管理", self._on_manage_folders)
        tools_menu.addSeparator()
        tools_menu.addAction("同步打分到文件", self._on_sync_stars)
        tools_menu.addSeparator()
        tools_menu.addAction("批量计算 MD5", self._on_batch_calculate_md5)
        tools_menu.addAction("智能去重", self._on_smart_dedup)
        tools_menu.addAction("文件移动管理", self._on_file_move)
        tools_menu.addSeparator()
        tools_menu.addAction("清理演员信息", self._on_clean_actor_data)
        tools_menu.addAction("重新导入元数据", self._on_reimport_metadata)
        tools_menu.addAction("完全重置数据库", self._on_full_database_reset)
        tools_menu.addSeparator()
        tools_menu.addAction("批量生成封面", self._on_batch_thumbnails)
        tools_menu.addAction("批量自动标签", self._on_batch_auto_tag)
        tools_menu.addAction("批量标注没有标签的文件", self._on_batch_auto_tag_no_tags)
        tools_menu.addAction("批量清理文件名", self._on_batch_clean_names)
        tools_menu.addSeparator()
        tools_menu.addAction("修正 JAVDB 错误信息", self._on_fix_javdb_error_titles)
        tools_menu.addSeparator()
        tools_menu.addAction("快速智能媒体库更新", self._on_quick_smart_media_update)
        tools_menu.addSeparator()
        tools_menu.addAction("JAV 信息面板", self._open_jav_info_dialog)

        # 界面菜单
        view_menu = menubar.addMenu("界面(&V)")
        view_menu.addAction("刷新", self._load_videos)
        view_menu.addAction("清空筛选", self._clear_filters)
        view_menu.addSeparator()
        view_menu.addAction("重置界面布局", self._on_reset_layout)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助(&H)")
        help_menu.addAction("关于", self._show_about)
        help_menu.addAction("快捷键", self._show_shortcuts)

    def _create_shortcuts(self):
        """创建快捷键"""
        # Ctrl+R 刷新
        refresh_action = QAction(self)
        refresh_action.setShortcut(QKeySequence("Ctrl+R"))
        refresh_action.triggered.connect(self._load_videos)
        self.addAction(refresh_action)

        # Ctrl+F 搜索
        search_action = QAction(self)
        search_action.setShortcut(QKeySequence("Ctrl+F"))
        search_action.triggered.connect(self._focus_search)
        self.addAction(search_action)

        # Space 播放
        play_action = QAction(self)
        play_action.setShortcut(QKeySequence("Space"))
        play_action.triggered.connect(self._play_selected)
        self.addAction(play_action)

        # Enter 生成封面
        thumbnail_action = QAction(self)
        thumbnail_action.setShortcut(QKeySequence("Return"))
        thumbnail_action.triggered.connect(self._generate_thumbnail_selected)
        self.addAction(thumbnail_action)

        # Ctrl+0-5 设置星级
        for i in range(6):
            star_action = QAction(self)
            star_action.setShortcut(QKeySequence(f"Ctrl+{i}"))
            star_action.triggered.connect(lambda checked, rating=i: self._set_star_rating(rating))
            self.addAction(star_action)

    def _focus_search(self):
        """聚焦搜索框"""
        self.search_input.setFocus()
        self.search_input.selectAll()

    def _clear_filters(self):
        """清空筛选"""
        self._filters = {}
        self._search_text = ""
        self.search_input.clear()
        self.filterbar.clear_all()
        self._load_videos()

    def _play_selected(self):
        """播放选中的视频"""
        item = self.video_table.get_selected_item()
        if item and item.get("path"):
            from ..actions.video_actions import VideoActions
            actions = VideoActions(self.db, self)
            actions.play_video(item["id"])

    def _set_star_rating(self, rating: int):
        """设置选中视频的星级"""
        item = self.video_table.get_selected_item()
        if item and self.video_repo:
            self.video_repo.update_stars(item["id"], rating)
            self._load_videos()

    def _on_scan_media(self):
        """扫描媒体文件"""
        self._open_scan_dialog()

    def _on_comprehensive_update(self):
        """智能媒体库更新"""
        dialog = SmartUpdateDialog(self.db, self)
        dialog.exec()

    def _on_import_nfo(self):
        """导入 NFO 文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择 NFO 文件", "", "NFO Files (*.nfo);;All Files (*)"
        )
        if not file_path:
            return
        
        def task(progress_callback=None, cancel_check=None):
            from utils.media_extensions import NFOImporter
            importer = NFOImporter(self.db.db_path)
            return importer.import_nfo(file_path, progress_callback=progress_callback, cancel_check=cancel_check)
        
        self.run_batch_task("导入 NFO", task)

    def _on_import_videos(self):
        """导入视频文件"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "选择视频文件", "", "Video Files (*.mp4 *.mkv *.avi *.wmv *.mov);;All Files (*)"
        )
        if not file_paths:
            return
        
        def task(progress_callback=None, cancel_check=None):
            success = 0
            failed = 0
            for i, file_path in enumerate(file_paths):
                if cancel_check and cancel_check():
                    break
                if progress_callback:
                    progress_callback(f"导入 {i+1}/{len(file_paths)}", int((i+1)/len(file_paths)*100))
                try:
                    if self.video_repo.add_video_to_db(file_path, "local"):
                        success += 1
                    else:
                        failed += 1
                except Exception:
                    failed += 1
            return {"success": success, "failed": failed}
        
        self.run_batch_task("导入视频", task)

    def _on_remove_duplicates(self):
        """去重复"""
        dialog = DedupDialog(self.db, self)
        dialog.exec()

    def _on_manage_folders(self):
        """文件夹管理"""
        dialog = FolderDialog(self.db, self)
        dialog.exec()

    def _on_sync_stars(self):
        """同步打分到文件"""
        reply = QMessageBox.question(
            self, "同步星级",
            "是否将星级同步到文件名（添加!前缀）？\n这会重命名文件。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            def task(progress_callback=None, cancel_check=None):
                from utils.maintenance import MaintenanceManager
                from utils.database import DatabaseManager
                db_manager = DatabaseManager(self.db.db_path)
                maintenance = MaintenanceManager(db_manager)
                return maintenance.sync_stars_to_filename(progress_callback=progress_callback, cancel_check=cancel_check)
            
            self.run_batch_task("同步星级", task)

    def _on_batch_calculate_md5(self):
        """批量计算 MD5"""
        reply = QMessageBox.question(
            self, "批量计算 MD5",
            "确定要重新计算所有视频的 MD5 吗？\n这可能需要很长时间。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            def task(progress_callback=None, cancel_check=None):
                from utils.batch_ops import BatchOperationManager
                from utils.database import DatabaseManager
                db_manager = DatabaseManager(self.db.db_path)
                batch_manager = BatchOperationManager(db_manager)
                videos = db_manager.get_videos()
                video_ids = [v['id'] for v in videos]
                return batch_manager.batch_calculate_md5(video_ids=video_ids, progress_callback=progress_callback, cancel_check=cancel_check)
            
            self.run_batch_task("批量计算 MD5", task)

    def _on_smart_dedup(self):
        """智能去重"""
        reply = QMessageBox.question(
            self, "智能去重",
            "是否自动删除重复文件（保留文件较大的版本）？\n删除操作不可恢复！",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            def task(progress_callback=None, cancel_check=None):
                from utils.maintenance import MaintenanceManager
                from utils.database import DatabaseManager
                db_manager = DatabaseManager(self.db.db_path)
                maintenance = MaintenanceManager(db_manager)
                return maintenance.duplicate_manager.remove_duplicates_by_criteria(
                    keep_criteria='largest',
                    progress_callback=progress_callback,
                    cancel_check=cancel_check
                )
            
            self.run_batch_task("智能去重", task)

    def _on_file_move(self):
        """文件移动管理"""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QTableWidget, QTableWidgetItem, QHeaderView
        from PySide6.QtCore import Qt
        
        dialog = QDialog(self)
        dialog.setWindowTitle("文件移动管理")
        dialog.setMinimumSize(600, 400)
        
        layout = QVBoxLayout(dialog)
        
        # 说明
        info = QLabel("选择要移动的文件和目标文件夹")
        layout.addWidget(info)
        
        # 目标文件夹选择
        target_layout = QHBoxLayout()
        target_layout.addWidget(QLabel("目标文件夹:"))
        target_combo = QComboBox()
        
        # 获取在线文件夹
        folders = self.db.execute("SELECT folder_path FROM folders WHERE is_active = 1")
        for folder in folders:
            target_combo.addItem(folder["folder_path"])
        target_layout.addWidget(target_combo, 1)
        layout.addLayout(target_layout)
        
        # 选中文件列表
        selected_items = self.video_table.get_selected_items()
        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["标题", "当前路径"])
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.setRowCount(len(selected_items))
        
        for i, item in enumerate(selected_items):
            table.setItem(i, 0, QTableWidgetItem(item.get("title", "")))
            table.setItem(i, 1, QTableWidgetItem(item.get("path", "")))
        
        layout.addWidget(table)
        
        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)
        
        move_btn = QPushButton("移动")
        
        def do_move():
            target_folder = target_combo.currentText()
            if not target_folder:
                QMessageBox.warning(dialog, "警告", "请选择目标文件夹")
                return
            
            def task(progress_callback=None, cancel_check=None):
                from ..actions.video_actions import VideoActions
                actions = VideoActions(self.db, self)
                success = 0
                failed = 0
                for i, item in enumerate(selected_items):
                    if cancel_check and cancel_check():
                        break
                    if progress_callback:
                        progress_callback(f"移动 {i+1}/{len(selected_items)}", int((i+1)/len(selected_items)*100))
                    if actions.move_video(item["id"], target_folder):
                        success += 1
                    else:
                        failed += 1
                return {"success": success, "failed": failed}
            
            dialog.accept()
            self.run_batch_task("移动文件", task)
        
        move_btn.clicked.connect(do_move)
        btn_layout.addWidget(move_btn)
        
        layout.addLayout(btn_layout)
        dialog.exec()

    def _on_batch_thumbnails(self):
        """批量生成封面"""
        selected_items = self.video_table.get_selected_items()
        if not selected_items:
            QMessageBox.warning(self, "警告", "请先选择要生成封面的视频")
            return
        
        def task(progress_callback=None, cancel_check=None):
            from ..actions.video_actions import VideoActions
            actions = VideoActions(self.db, self)
            success = 0
            failed = 0
            for i, item in enumerate(selected_items):
                if cancel_check and cancel_check():
                    break
                if progress_callback:
                    progress_callback(f"生成封面 {i+1}/{len(selected_items)}", int((i+1)/len(selected_items)*100))
                if actions.generate_thumbnail(item["id"]):
                    success += 1
                else:
                    failed += 1
            return {"success": success, "failed": failed}
        
        self.run_batch_task("批量生成封面", task)

    def _on_batch_auto_tag(self):
        """批量自动标签"""
        selected_items = self.video_table.get_selected_items()
        if not selected_items:
            QMessageBox.warning(self, "警告", "请先选择要标注标签的视频")
            return
        
        def task(progress_callback=None, cancel_check=None):
            from video_analyzer.adapter import VideoContentAnalyzer
            analyzer = VideoContentAnalyzer()
            success = 0
            failed = 0
            for i, item in enumerate(selected_items):
                if cancel_check and cancel_check():
                    break
                if progress_callback:
                    progress_callback(f"标注标签 {i+1}/{len(selected_items)}", int((i+1)/len(selected_items)*100))
                try:
                    row = self.db.execute_one("SELECT file_path FROM videos WHERE id = ?", (item["id"],))
                    if not row or not os.path.isfile(row["file_path"]):
                        failed += 1
                        continue
                    result = analyzer.analyze_video_content_with_retry(row["file_path"])
                    if result and result.get("tags"):
                        tags_str = ",".join(result["tags"])
                        self.db.execute_write("UPDATE videos SET tags = ? WHERE id = ?", (tags_str, item["id"]))
                        success += 1
                    else:
                        failed += 1
                except Exception:
                    failed += 1
            return {"success": success, "failed": failed}
        
        self.run_batch_task("批量自动标签", task)

    def _on_batch_clean_names(self):
        """批量清理文件名"""
        selected_items = self.video_table.get_selected_items()
        if not selected_items:
            QMessageBox.warning(self, "警告", "请先选择要清理文件名的视频")
            return
        
        def task(progress_callback=None, cancel_check=None):
            from ..actions.video_actions import VideoActions
            actions = VideoActions(self.db, self)
            success = 0
            failed = 0
            for i, item in enumerate(selected_items):
                if cancel_check and cancel_check():
                    break
                if progress_callback:
                    progress_callback(f"清理文件名 {i+1}/{len(selected_items)}", int((i+1)/len(selected_items)*100))
                try:
                    row = self.db.execute_one("SELECT file_path FROM videos WHERE id = ?", (item["id"],))
                    if not row:
                        failed += 1
                        continue
                    # 清理文件名逻辑
                    import os
                    import re
                    old_path = row["file_path"]
                    dirname = os.path.dirname(old_path)
                    filename = os.path.basename(old_path)
                    name, ext = os.path.splitext(filename)
                    # 清理逻辑：去除多余空格、特殊字符等
                    cleaned = re.sub(r'\s+', ' ', name).strip()
                    cleaned = re.sub(r'[^\w\s\-\.]', '', cleaned)
                    new_path = os.path.join(dirname, cleaned + ext)
                    if old_path != new_path and os.path.isfile(old_path):
                        os.rename(old_path, new_path)
                        self.db.execute_write("UPDATE videos SET file_path = ? WHERE id = ?", (new_path, item["id"]))
                        success += 1
                    else:
                        failed += 1
                except Exception:
                    failed += 1
            return {"success": success, "failed": failed}
        
        self.run_batch_task("批量清理文件名", task)

    def _on_reset_layout(self):
        """重置界面布局"""
        reply = QMessageBox.question(
            self, "重置布局",
            "确定要重置界面布局吗？\n这将恢复默认的列宽和顺序。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            # 重置列配置
            default_columns = {
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
            }
            import json
            config_path = os.path.join(os.path.dirname(self.db.db_path), 'gui_config.json')
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump({'columns': default_columns}, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "重置完成", "界面布局已重置，请重启应用以生效。")

    def _show_about(self):
        """显示关于对话框"""
        QMessageBox.about(
            self, "关于",
            "媒体库管理器 v4\n\n"
            "深色影院风界面\n"
            "琥珀金强调色 + 玻璃拟态面板\n\n"
            "基于 PySide6 构建"
        )

    def _show_context_menu(self, position):
        """显示右键菜单"""
        selected_items = self.video_table.get_selected_items()
        if not selected_items:
            return

        menu = QMenu(self)

        if len(selected_items) == 1:
            # 单文件菜单
            item = selected_items[0]
            menu.addAction("播放", lambda: self._play_video(item["id"]))
            menu.addAction("打开所在文件夹", lambda: self._open_folder(item["id"]))
            menu.addSeparator()
            menu.addAction("自动标签", lambda: self._auto_tag_video(item["id"]))
            menu.addSeparator()
            menu.addAction("获取 JAVDB 信息", lambda: self._fetch_javdb_info(item["id"]))
            menu.addSeparator()
            menu.addAction("生成封面", lambda: self._generate_thumbnail(item["id"]))
            menu.addSeparator()
            menu.addAction("删除", lambda: self._delete_video(item["id"]))
        else:
            # 多文件菜单
            count = len(selected_items)
            menu.addAction(f"批量自动标签 ({count} 个文件)", self._batch_auto_tag_selected)
            menu.addSeparator()
            menu.addAction(f"批量获取 JAVDB 信息 ({count} 个文件)", self._batch_fetch_javdb_selected)
            menu.addSeparator()
            menu.addAction(f"批量生成封面 ({count} 个文件)", self._batch_generate_thumbnails_selected)
            menu.addSeparator()
            menu.addAction(f"批量删除 ({count} 个文件)", self._batch_delete_selected)

        menu.exec(self.video_table.mapToGlobal(position))

    def _play_video(self, video_id: int):
        """播放视频"""
        from ..actions.video_actions import VideoActions
        actions = VideoActions(self.db, self)
        if not actions.play_video(video_id):
            QMessageBox.warning(self, "播放失败", "无法播放视频，文件可能不存在或离线")

    def _open_folder(self, video_id: int):
        """打开所在文件夹"""
        from ..actions.video_actions import VideoActions
        actions = VideoActions(self.db, self)
        if not actions.open_folder(video_id):
            QMessageBox.warning(self, "打开失败", "无法打开文件夹，文件可能不存在或离线")

    def _auto_tag_video(self, video_id: int):
        """自动标签单个视频"""
        def task(progress_callback=None, cancel_check=None):
            row = self.db.execute_one("SELECT file_path FROM videos WHERE id = ?", (video_id,))
            if not row:
                return {"success": 0, "failed": 1, "error": "视频不存在"}
            
            from video_analyzer.adapter import VideoContentAnalyzer
            analyzer = VideoContentAnalyzer()
            result = analyzer.analyze_video_content_with_retry(row["file_path"])
            
            if result and result.get("tags"):
                tags_str = ",".join(result["tags"])
                self.db.execute_write(
                    "UPDATE videos SET tags = ? WHERE id = ?",
                    (tags_str, video_id)
                )
                return {"success": 1, "failed": 0}
            return {"success": 0, "failed": 1}

        self.run_batch_task("自动标签", task)

    def _fetch_javdb_info(self, video_id: int):
        """获取 JAVDB 信息"""
        def task(progress_callback=None, cancel_check=None):
            try:
                row = self.db.execute_one("SELECT file_name FROM videos WHERE id = ?", (video_id,))
                if not row:
                    return {"success": 0, "failed": 1, "error": "视频不存在"}
                
                # 从文件名提取番号
                import re
                filename = row["file_name"]
                code_match = re.search(r'([A-Z]+-\d+)', filename, re.IGNORECASE)
                if not code_match:
                    return {"success": 0, "failed": 1, "error": "无法从文件名提取番号"}
                
                code = code_match.group(1).upper()
                
                # 使用 javdb_system 获取信息
                from javdb_system.crawler import JavDBCrawler
                crawler = JavDBCrawler()
                info = crawler.search_by_code(code)
                
                if info:
                    # 保存到数据库
                    self.db.execute_write("""
                        INSERT OR REPLACE INTO javdb_info 
                        (video_id, javdb_code, javdb_title, release_date, score, cover_url)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (video_id, code, info.get("title"), info.get("release_date"), 
                          info.get("score"), info.get("cover_url")))
                    return {"success": 1, "failed": 0}
                else:
                    return {"success": 0, "failed": 1, "error": "未找到 JAVDB 信息"}
            except Exception as e:
                return {"success": 0, "failed": 1, "error": str(e)}

        self.run_batch_task("获取 JAVDB 信息", task)

    def _generate_thumbnail(self, video_id: int):
        """生成封面"""
        def task(progress_callback=None, cancel_check=None):
            from ..actions.video_actions import VideoActions
            actions = VideoActions(self.db, self)
            if actions.generate_thumbnail(video_id):
                return {"success": 1, "failed": 0}
            return {"success": 0, "failed": 1}

        self.run_batch_task("生成封面", task)

    def _delete_video(self, video_id: int):
        """删除视频"""
        reply = QMessageBox.question(
            self, "删除确认",
            "确定要删除这个视频吗？\n此操作不可恢复！",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            from ..actions.video_actions import VideoActions
            actions = VideoActions(self.db, self)
            if actions.delete_video(video_id, delete_file=False):
                self._load_videos()
                QMessageBox.information(self, "删除成功", "视频已删除")
            else:
                QMessageBox.warning(self, "删除失败", "无法删除视频")

    def _batch_auto_tag_selected(self):
        """批量自动标签选中视频"""
        selected_items = self.video_table.get_selected_items()
        if not selected_items:
            return

        def task(progress_callback=None, cancel_check=None):
            success = 0
            failed = 0
            
            from video_analyzer.adapter import VideoContentAnalyzer
            analyzer = VideoContentAnalyzer()
            
            for i, item in enumerate(selected_items):
                if cancel_check and cancel_check():
                    break
                
                if progress_callback:
                    progress_callback(f"处理 {i+1}/{len(selected_items)}", int((i+1)/len(selected_items)*100))
                
                row = self.db.execute_one("SELECT file_path FROM videos WHERE id = ?", (item["id"],))
                if not row or not os.path.isfile(row["file_path"]):
                    failed += 1
                    continue
                
                try:
                    result = analyzer.analyze_video_content_with_retry(row["file_path"])
                    if result and result.get("tags"):
                        tags_str = ",".join(result["tags"])
                        self.db.execute_write(
                            "UPDATE videos SET tags = ? WHERE id = ?",
                            (tags_str, item["id"])
                        )
                        success += 1
                    else:
                        failed += 1
                except Exception:
                    failed += 1
            
            return {"success": success, "failed": failed}

        self.run_batch_task("批量自动标签", task)

    def _batch_fetch_javdb_selected(self):
        """批量获取 JAVDB 信息"""
        selected_items = self.video_table.get_selected_items()
        if not selected_items:
            QMessageBox.warning(self, "警告", "请先选择要获取 JAVDB 信息的视频")
            return
        
        def task(progress_callback=None, cancel_check=None):
            import re
            from javdb_system.crawler import JavDBCrawler
            crawler = JavDBCrawler()
            success = 0
            failed = 0
            for i, item in enumerate(selected_items):
                if cancel_check and cancel_check():
                    break
                if progress_callback:
                    progress_callback(f"获取 JAVDB 信息 {i+1}/{len(selected_items)}", int((i+1)/len(selected_items)*100))
                try:
                    row = self.db.execute_one("SELECT file_name FROM videos WHERE id = ?", (item["id"],))
                    if not row:
                        failed += 1
                        continue
                    filename = row["file_name"]
                    code_match = re.search(r'([A-Z]+-\d+)', filename, re.IGNORECASE)
                    if not code_match:
                        failed += 1
                        continue
                    code = code_match.group(1).upper()
                    info = crawler.search_by_code(code)
                    if info:
                        self.db.execute_write("""
                            INSERT OR REPLACE INTO javdb_info 
                            (video_id, javdb_code, javdb_title, release_date, score, cover_url)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (item["id"], code, info.get("title"), info.get("release_date"), 
                              info.get("score"), info.get("cover_url")))
                        success += 1
                    else:
                        failed += 1
                except Exception:
                    failed += 1
            return {"success": success, "failed": failed}
        
        self.run_batch_task("批量获取 JAVDB 信息", task)

    def _batch_generate_thumbnails_selected(self):
        """批量生成封面"""
        selected_items = self.video_table.get_selected_items()
        if not selected_items:
            return

        def task(progress_callback=None, cancel_check=None):
            from ..actions.video_actions import VideoActions
            actions = VideoActions(self.db, self)
            success = 0
            failed = 0
            
            for i, item in enumerate(selected_items):
                if cancel_check and cancel_check():
                    break
                
                if progress_callback:
                    progress_callback(f"处理 {i+1}/{len(selected_items)}", int((i+1)/len(selected_items)*100))
                
                if actions.generate_thumbnail(item["id"]):
                    success += 1
                else:
                    failed += 1
            
            return {"success": success, "failed": failed}

        self.run_batch_task("批量生成封面", task)

    def _batch_delete_selected(self):
        """批量删除选中视频"""
        selected_items = self.video_table.get_selected_items()
        if not selected_items:
            return

        reply = QMessageBox.question(
            self, "批量删除确认",
            f"确定要删除 {len(selected_items)} 个视频吗？\n此操作不可恢复！",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            from ..actions.video_actions import VideoActions
            actions = VideoActions(self.db, self)
            success = 0
            for item in selected_items:
                if actions.delete_video(item["id"], delete_file=False):
                    success += 1
            
            self._load_videos()
            QMessageBox.information(self, "删除完成", f"成功删除 {success} 个视频")

    def run_batch_task(self, title: str, task_func, **kwargs):
        """运行批量任务的通用方法"""
        progress = TaskProgressDialog(title, self)
        progress.show()

        worker = TaskWorker(task_func, **kwargs)
        worker.progress_signal.connect(progress.update_progress)
        progress.cancel_signal.connect(worker.cancel)

        def on_finished(result):
            progress.close()
            success = result.get("success", 0)
            failed = result.get("failed", 0)
            skipped = result.get("skipped", 0)

            msg = f"操作完成\n成功: {success}"
            if failed > 0:
                msg += f"\n失败: {failed}"
            if skipped > 0:
                msg += f"\n跳过: {skipped}"

            if result.get("error"):
                msg += f"\n错误: {result.get('error')}"

            QMessageBox.information(self, "完成", msg)
            self._load_videos()

        worker.finished_signal.connect(on_finished)
        worker.error_signal.connect(
            lambda err: (progress.close(), QMessageBox.critical(self, "错误", str(err)))
        )

        worker.start()
        self._current_worker = worker

    def _generate_thumbnail_selected(self):
        """为选中视频生成封面"""
        item = self.video_table.get_selected_item()
        if item:
            self._generate_thumbnail(item["id"])

    def _on_batch_import_nfo_for_no_actors(self):
        """批量导入 NFO 信息（为没有演员的视频）"""
        reply = QMessageBox.question(
            self, "批量导入 NFO",
            "是否为所有缺失演员信息的视频导入 NFO？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
        )
        if reply == QMessageBox.Yes:
            def task(progress_callback=None, cancel_check=None):
                from utils.batch_ops import BatchOperationManager
                from utils.database import DatabaseManager
                db_manager = DatabaseManager(self.db.db_path)
                batch_manager = BatchOperationManager(db_manager)
                videos = db_manager.get_videos()
                video_ids = [v['id'] for v in videos]
                return batch_manager.batch_import_nfo(
                    video_ids=video_ids,
                    filter_no_actors=True,
                    progress_callback=progress_callback,
                    cancel_check=cancel_check
                )
            
            self.run_batch_task("批量导入 NFO", task)

    def _on_batch_import_javdb_for_no_title(self):
        """批量导入 JAVDB 信息（为没有标题的视频）"""
        reply = QMessageBox.question(
            self, "确认操作",
            "此功能将为没有完整标题的视频批量导入 JAV 信息。\n"
            "这需要网络连接并且可能需要较长时间，确定要继续吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        def task(progress_callback=None, cancel_check=None):
            import re
            from utils import jav as utils_jav
            
            rows = self.db.execute("SELECT id, file_name FROM videos WHERE (title IS NULL OR title='')")
            if not rows:
                return {"success": 0, "failed": 0, "message": "没有需要导入的项目"}

            total = len(rows)
            success = 0
            for idx, row in enumerate(rows, 1):
                if cancel_check and cancel_check():
                    break
                if progress_callback:
                    progress_callback(f"导入 {idx}/{total}", int(idx/total*100))
                
                code = utils_jav.extract_code(row["file_name"])
                info = utils_jav.search_movie_info(code) if code else None
                if info and utils_jav.save_movie_info_to_db(self.db.conn, row["id"], info):
                    success += 1

            return {"success": success, "failed": total - success}

        self.run_batch_task("批量导入 JAVDB 信息", task)

    def _on_clean_actor_data(self):
        """清理演员信息"""
        def task(progress_callback=None, cancel_check=None):
            from utils.maintenance import MaintenanceManager
            from utils.database import DatabaseManager
            db_manager = DatabaseManager(self.db.db_path)
            maintenance = MaintenanceManager(db_manager)
            result = maintenance.clean_actor_data()
            return result

        self.run_batch_task("清理演员信息", task)

    def _on_reimport_metadata(self):
        """重新导入元数据"""
        def task(progress_callback=None, cancel_check=None):
            from utils.advanced_tools import AdvancedToolsManager
            from utils.database import DatabaseManager
            db_manager = DatabaseManager(self.db.db_path)
            advanced_tools = AdvancedToolsManager(db_manager)
            return advanced_tools.reimport_incomplete_metadata(
                progress_callback=progress_callback,
                cancel_check=cancel_check
            )

        self.run_batch_task("重新导入元数据", task)

    def _on_full_database_reset(self):
        """完全重置数据库"""
        reply = QMessageBox.question(
            self, "确认",
            "此操作将完全重置数据库（保留标签和评分信息）。\n"
            "所有视频需要重新扫描才能恢复元数据。\n\n"
            "确定要继续吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            def task(progress_callback=None, cancel_check=None):
                from utils.advanced_tools import AdvancedToolsManager
                from utils.database import DatabaseManager
                db_manager = DatabaseManager(self.db.db_path)
                advanced_tools = AdvancedToolsManager(db_manager)
                return advanced_tools.full_database_reset(
                    progress_callback=progress_callback,
                    cancel_check=cancel_check
                )

            self.run_batch_task("完全重置数据库", task)

    def _on_batch_auto_tag_no_tags(self):
        """批量标注没有标签的文件"""
        def task(progress_callback=None, cancel_check=None):
            from video_analyzer.adapter import VideoContentAnalyzer
            analyzer = VideoContentAnalyzer()
            
            rows = self.db.execute("""
                SELECT v.id, v.file_path, v.file_name FROM videos v
                WHERE (v.tags IS NULL OR v.tags = '')
            """)
            videos = [(row["id"], row["file_path"], row["file_name"]) for row in rows
                      if row["file_path"] and os.path.exists(row["file_path"]) and os.path.isfile(row["file_path"])]

            if not videos:
                return {"success": 0, "failed": 0, "message": "没有找到需要处理的无标签在线视频"}

            success = 0
            failed = 0
            for i, (vid, path, name) in enumerate(videos):
                if cancel_check and cancel_check():
                    break
                if progress_callback:
                    progress_callback(f"标注 {i+1}/{len(videos)}", int((i+1)/len(videos)*100))
                
                try:
                    result = analyzer.analyze_video_content_with_retry(path, use_retry=True)
                    if result and result.get("tags"):
                        tags_str = ",".join(result["tags"])
                        self.db.execute_write("UPDATE videos SET tags = ? WHERE id = ?", (tags_str, vid))
                        success += 1
                    else:
                        self.db.execute_write("UPDATE videos SET tags = ? WHERE id = ?", ("<无标签>", vid))
                        failed += 1
                except Exception:
                    failed += 1

            return {"success": success, "failed": failed}

        self.run_batch_task("批量标注没有标签的文件", task)

    def _on_fix_javdb_error_titles(self):
        """修正 JAVDB 错误信息"""
        def task(progress_callback=None, cancel_check=None):
            from utils.advanced_tools import AdvancedToolsManager
            from utils.database import DatabaseManager
            db_manager = DatabaseManager(self.db.db_path)
            advanced_tools = AdvancedToolsManager(db_manager)
            return advanced_tools.fix_javdb_error_titles(
                progress_callback=progress_callback,
                cancel_check=cancel_check
            )

        self.run_batch_task("修正 JAVDB 错误信息", task)

    def _on_quick_smart_media_update(self):
        """快速智能媒体库更新"""
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "选择要快速更新的文件夹",
            "",
            QFileDialog.Option.ShowDirsOnly
        )
        if folder_path:
            def task(progress_callback=None, cancel_check=None):
                from fast_smart_media_updater import run_fast_update
                return run_fast_update(
                    folder_path=folder_path,
                    progress_callback=progress_callback,
                    cancel_check=cancel_check
                )

            self.run_batch_task("快速智能媒体库更新", task)

    def _open_jav_info_dialog(self):
        """打开 JAV 信息面板"""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton
        dialog = QDialog(self)
        dialog.setWindowTitle("JAV 信息面板")
        dialog.setMinimumSize(600, 400)
        
        layout = QVBoxLayout(dialog)
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setHtml("<h2>JAV 信息面板</h2><p>此功能正在开发中...</p>")
        layout.addWidget(text_edit)
        
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        
        dialog.exec()

    def _show_shortcuts(self):
        """显示快捷键对话框"""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton
        shortcuts_text = """
        <h2>快捷键指南</h2>

        <h3>基础操作</h3>
        <table>
            <tr><td><b>Ctrl+R</b></td><td>刷新数据</td></tr>
            <tr><td><b>Ctrl+F</b></td><td>聚焦搜索框</td></tr>
        </table>

        <h3>视频操作</h3>
        <table>
            <tr><td><b>Space</b></td><td>播放选中的视频</td></tr>
            <tr><td><b>Enter</b></td><td>生成视频封面</td></tr>
        </table>

        <h3>星级设置</h3>
        <table>
            <tr><td><b>Ctrl+0</b></td><td>清除星级</td></tr>
            <tr><td><b>Ctrl+1</b></td><td>设置1星</td></tr>
            <tr><td><b>Ctrl+2</b></td><td>设置2星</td></tr>
            <tr><td><b>Ctrl+3</b></td><td>设置3星</td></tr>
            <tr><td><b>Ctrl+4</b></td><td>设置4星</td></tr>
            <tr><td><b>Ctrl+5</b></td><td>设置5星</td></tr>
        </table>

        <h3>鼠标操作</h3>
        <table>
            <tr><td><b>双击视频</b></td><td>播放视频</td></tr>
            <tr><td><b>双击星级列</b></td><td>快速设置星级</td></tr>
            <tr><td><b>右键菜单</b></td><td>显示操作选项</td></tr>
        </table>
        """

        dialog = QDialog(self)
        dialog.setWindowTitle("快捷键指南")
        dialog.setFixedSize(500, 600)
        dialog.setModal(True)

        layout = QVBoxLayout(dialog)
        text_edit = QTextEdit()
        text_edit.setHtml(shortcuts_text)
        text_edit.setReadOnly(True)
        layout.addWidget(text_edit)

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.exec()

    def _on_detail_save(self, data: dict):
        """详情面板保存"""
        if data and self.video_repo:
            self.video_repo.update_video(
                data["id"],
                description=data.get("description", ""),
                tags=data.get("tags", "")
            )
            QMessageBox.information(self, "保存成功", "视频信息已保存")
            self._load_videos()

    def _on_detail_set_star(self, rating: int):
        """详情面板设置星级"""
        item = self.video_table.get_selected_item()
        if item and self.video_repo:
            self.video_repo.update_stars(item["id"], rating)
            self._load_videos()

    def _on_detail_add_tag(self):
        """详情面板添加标签"""
        item = self.video_table.get_selected_item()
        if item:
            from PySide6.QtWidgets import QInputDialog
            tag, ok = QInputDialog.getText(self, "添加标签", "请输入标签:")
            if ok and tag:
                # 获取当前标签
                current_tags = item.get("tags", [])
                if isinstance(current_tags, str):
                    current_tags = [t.strip() for t in current_tags.split(",") if t.strip()]
                if tag not in current_tags:
                    current_tags.append(tag)
                    tags_str = ",".join(current_tags)
                    self.video_repo.update_tags(item["id"], tags_str)
                    self._load_videos()

    def _on_detail_fetch_javdb(self):
        """详情面板获取 JAVDB 信息"""
        item = self.video_table.get_selected_item()
        if item:
            self._fetch_javdb_info(item["id"])

    def _on_detail_generate_thumbnail(self):
        """详情面板生成封面"""
        item = self.video_table.get_selected_item()
        if item:
            self._generate_thumbnail(item["id"])

    def _on_detail_delete(self):
        """详情面板删除视频"""
        item = self.video_table.get_selected_item()
        if item:
            self._delete_video(item["id"])

    def closeEvent(self, event):
        """关闭事件"""
        # 等待所有后台线程完成
        if hasattr(self, '_worker') and self._worker and self._worker.isRunning():
            self._worker.quit()
            self._worker.wait(1000)
        
        if hasattr(self, '_cover_workers'):
            for worker in self._cover_workers:
                if worker and worker.isRunning():
                    worker.quit()
                    worker.wait(1000)
        
        if self.db:
            self.db.close()
        event.accept()
