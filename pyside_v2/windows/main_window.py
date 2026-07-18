# -*- coding: utf-8 -*-
"""
主窗口 - Phase 1 + 2。

Phase 1: 菜单栏（文件/工具/界面/帮助，对齐 v1 全部菜单项）
Phase 2: 高性能视频列表（QTableView + QAbstractTableModel）+ load_videos 查询
"""

import os
import json
import platform

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QStatusBar,
    QSplitter, QScrollArea, QMenu, QMessageBox, QPushButton, QLineEdit,
    QApplication,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QKeySequence, QShortcut, QPixmap

from pyside_v2.core import MediaLibraryCore, qt_log_handler
from pyside_v2.theme import Tokens, init_theme, current
from pyside_v2.widgets import VideoTableModel, VideoTableView, Sidebar
from gui_adapter import setup_full_integration


class MainWindow(QMainWindow):
    """主窗口。"""

    def __init__(self):
        super().__init__()

        # 1. 后端 facade
        self.core = MediaLibraryCore()

        # 2. 高级工具管理器
        try:
            from utils.advanced_tools import AdvancedToolsManager
            self.advanced_tools_manager = AdvancedToolsManager(self.core.db_manager)
        except Exception as e:
            print(f"⚠️ AdvancedToolsManager 初始化失败: {e}")
            self.advanced_tools_manager = None

        # 筛选状态
        self.show_online_only = True
        self.is_filtering = False
        self._current_video_id = None
        self._nav_filter = 'all'          # 当前侧栏导航筛选
        self._search_text = ''            # 顶部搜索文本

        # 3. UI
        self.setup_ui()
        self.create_menus()
        self.create_shortcuts()

        # 主题管理器（初始化后应用持久化的主题）
        self.theme_mgr = init_theme(QApplication.instance())
        self._update_theme_button()

        # 侧栏加载存储位置
        self.sidebar.load_storage_locations(self.core)
        self.sidebar.select_all()

        # 4. 桥接后端
        bound = self.setup_function_integration()
        print(f"✅ 已桥接 {bound} 个后端方法")

        # 关键：桥接过程(gui_adapter.bind_functions)会创建临时 MediaLibrary 实例，
        # 其 __del__/GC 会关闭共享的 core.conn，导致后续 core.cursor 失效。
        # 这里重建 core 的 conn/cursor，确保数据加载可用。
        self._reconnect_core()

        # 5. 日志
        qt_log_handler.log_signal.connect(self.append_log)

        # 6. 首次加载数据
        self.load_videos()

    def _reconnect_core(self):
        """重建 core 的 SQLite 连接（修复桥接导致的连接关闭问题）。"""
        import sqlite3
        from utils.runtime import runtime_path
        try:
            db_path = runtime_path('media_library.db')
            self.core.conn = sqlite3.connect(db_path, check_same_thread=False)
            self.core.cursor = self.core.conn.cursor()
        except Exception as e:
            print(f"⚠️ 重建数据库连接失败: {e}")

    # ==================================================================
    # UI 骨架（对齐 ui_design：侧栏 + topbar + 列表 + 右详情卡片）
    # ==================================================================
    def setup_ui(self):
        self.setWindowTitle("媒体库管理器 v2")
        self.resize(1320, 860)

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- 左：侧栏导航 ----
        self.sidebar = Sidebar(self)
        self.sidebar.nav_changed.connect(self.on_nav_changed)
        root.addWidget(self.sidebar)

        # ---- 右：主区（topbar + 内容 + 状态栏）----
        main = QWidget()
        main_lay = QVBoxLayout(main)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)
        root.addWidget(main, 1)

        # -- 顶部工具栏 topbar --
        topbar = QWidget()
        topbar.setObjectName("topbar")
        topbar.setFixedHeight(Tokens.TOPBAR_H)
        tbar_lay = QHBoxLayout(topbar)
        tbar_lay.setContentsMargins(16, 0, 16, 0)
        tbar_lay.setSpacing(12)

        # 搜索框
        self.search_input = QLineEdit()
        self.search_input.setObjectName("searchBox")
        self.search_input.setPlaceholderText("搜索标题 / 番号 / 演员 / 标签…")
        self.search_input.setFixedWidth(340)
        self.search_input.returnPressed.connect(self._on_search)
        tbar_lay.addWidget(self.search_input)

        # 仅在线按钮
        self.btn_online = QPushButton("仅在线")
        self.btn_online.setProperty("role", "on")
        self.btn_online.setCheckable(True)
        self.btn_online.setChecked(self.show_online_only)
        self.btn_online.setCursor(Qt.PointingHandCursor)
        self.btn_online.clicked.connect(self._toggle_online_only)
        tbar_lay.addWidget(self.btn_online)

        tbar_lay.addStretch()

        # 主题切换
        self.btn_theme = QPushButton("◐")
        self.btn_theme.setProperty("role", "icon")
        self.btn_theme.setFixedWidth(32)
        self.btn_theme.setCursor(Qt.PointingHandCursor)
        self.btn_theme.setToolTip("切换深/浅色主题")
        self.btn_theme.clicked.connect(self._toggle_theme)
        tbar_lay.addWidget(self.btn_theme)

        # 导入视频文件按钮（主操作，对接桥接的 import_videos）
        self.btn_scan = QPushButton("＋ 导入视频文件")
        self.btn_scan.setProperty("role", "primary")
        self.btn_scan.setCursor(Qt.PointingHandCursor)
        self.btn_scan.clicked.connect(self.on_import_videos)
        tbar_lay.addWidget(self.btn_scan)

        main_lay.addWidget(topbar)

        # -- 内容区（列表 + 右详情）--
        content = QSplitter(Qt.Horizontal)
        content.setHandleWidth(1)
        content.setContentsMargins(0, 0, 0, 0)

        # 列表区（列表 + 翻页栏，垂直）
        list_area = QWidget()
        list_lay = QVBoxLayout(list_area)
        list_lay.setContentsMargins(12, 12, 6, 12)
        list_lay.setSpacing(0)

        # 列表（真实数据，分页）
        self.video_model = VideoTableModel(page_size=300)
        self.video_table = VideoTableView(self)
        self.video_table.set_model(self.video_model)
        self.video_table.selection_changed.connect(self.on_video_selected)
        self.video_table.double_clicked.connect(self.on_video_double_clicked)
        self.video_table.header_clicked.connect(self.on_header_clicked)
        self.video_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.video_table.customContextMenuRequested.connect(self.show_context_menu)
        list_lay.addWidget(self.video_table, 1)

        # 翻页栏
        page_bar = QWidget()
        page_bar.setObjectName("pageBar")
        pbl = QHBoxLayout(page_bar)
        pbl.setContentsMargins(12, 6, 12, 6)
        self.page_label = QLabel("0 / 0")
        self.page_label.setObjectName("pageLabel")
        pbl.addStretch()
        self.btn_first = QPushButton("⟨⟨"); self.btn_first.setFixedWidth(34)
        self.btn_prev = QPushButton("⟨"); self.btn_prev.setFixedWidth(34)
        self.btn_next = QPushButton("⟩"); self.btn_next.setFixedWidth(34)
        self.btn_last = QPushButton("⟩⟩"); self.btn_last.setFixedWidth(34)
        for b in (self.btn_first, self.btn_prev, self.btn_next, self.btn_last):
            b.setCursor(Qt.PointingHandCursor)
            b.setProperty("role", "icon")
        self.btn_first.clicked.connect(self.go_first_page)
        self.btn_prev.clicked.connect(self.go_prev_page)
        self.btn_next.clicked.connect(self.go_next_page)
        self.btn_last.clicked.connect(self.go_last_page)
        pbl.addWidget(self.btn_first)
        pbl.addWidget(self.btn_prev)
        pbl.addWidget(self.page_label)
        pbl.addWidget(self.btn_next)
        pbl.addWidget(self.btn_last)
        list_lay.addWidget(page_bar)

        content.addWidget(list_area)

        # 右详情面板（卡片式）
        self.detail_panel = self._build_detail_panel()
        detail_scroll = QScrollArea()
        detail_scroll.setWidgetResizable(True)
        detail_scroll.setFrameShape(QScrollArea.NoFrame)
        detail_scroll.setWidget(self.detail_panel)
        content.addWidget(detail_scroll)

        content.setSizes([860, 380])
        main_lay.addWidget(content, 1)

        # -- 状态栏 --
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")
        self.video_count_label = QLabel("0 个视频")
        self.video_count_label.setObjectName("videoCountLabel")
        self.status_bar.addPermanentWidget(self.video_count_label)

    def _build_detail_panel(self):
        """构建右侧详情卡片（对齐 ui_design .detail + v1 全部操作按钮）。"""
        from pyside_v2.theme import current
        panel = QWidget()
        panel.setObjectName("detailPanel")
        panel.setFixedWidth(Tokens.DETAIL_W)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # 封面
        self.cover_label = QLabel()
        self.cover_label.setObjectName("coverLabel")
        self.cover_label.setFixedHeight(int(Tokens.DETAIL_W * Tokens.COVER_RATIO))
        self.cover_label.setAlignment(Qt.AlignCenter)
        self.cover_label.setText("封面")
        lay.addWidget(self.cover_label)

        # 元数据区（可滚动）
        body = QWidget()
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(16, 16, 16, 16)
        body_lay.setSpacing(6)

        # 可编辑标题
        from PySide6.QtWidgets import QGroupBox as _GB
        self.detail_title_edit = QLineEdit()
        self.detail_title_edit.setPlaceholderText("标题（可编辑）")
        self.detail_title_edit.setStyleSheet("font-size:15px; font-weight:600;")
        body_lay.addWidget(self.detail_title_edit)

        self.detail_sub = QLabel("")
        self.detail_sub.setObjectName("detailSub")
        body_lay.addWidget(self.detail_sub)

        # 星级（可点）
        star_row = QHBoxLayout()
        star_row.setSpacing(6)
        star_row.addWidget(QLabel("星级"))
        self.detail_stars_label = QLabel("☆☆☆☆☆")
        self.detail_stars_label.setStyleSheet("font-size:16px; color: #e8a009;")
        self.detail_stars_label.setCursor(Qt.PointingHandCursor)
        self.detail_stars_label.setToolTip("点击设置星级（点同一星降级）")
        self.detail_stars_label.mousePressEvent = self._detail_star_clicked
        star_row.addWidget(self.detail_stars_label)
        star_row.addStretch()
        body_lay.addLayout(star_row)

        # 标签（可编辑）
        body_lay.addWidget(QLabel("标签"))
        self.detail_tags_edit = QLineEdit()
        self.detail_tags_edit.setPlaceholderText("标签，逗号分隔（可编辑）")
        body_lay.addWidget(self.detail_tags_edit)

        # 描述（可编辑）
        body_lay.addWidget(QLabel("描述"))
        from PySide6.QtWidgets import QPlainTextEdit as _PTE
        self.detail_desc_edit = _PTE()
        self.detail_desc_edit.setPlaceholderText("描述（可编辑）")
        self.detail_desc_edit.setFixedHeight(60)
        body_lay.addWidget(self.detail_desc_edit)

        body_lay.addSpacing(4)

        # kv 元数据（只读：演员/大小/时长/分辨率/路径等）
        self.detail_kv_container = QVBoxLayout()
        self.detail_kv_container.setSpacing(4)
        body_lay.addLayout(self.detail_kv_container)

        body_lay.addStretch()

        # 操作按钮组（对齐 v1：播放/保存/星级/标签/JAVDB/封面/删除）
        actions = QHBoxLayout()
        actions.setSpacing(6)
        self.btn_play = QPushButton("▶ 播放")
        self.btn_play.setProperty("role", "primary")
        self.btn_play.setCursor(Qt.PointingHandCursor)
        self.btn_play.clicked.connect(lambda: self._play_video(self._current_video_id))
        self.btn_save = QPushButton("💾 保存")
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.clicked.connect(self._save_video_info)
        actions.addWidget(self.btn_play)
        actions.addWidget(self.btn_save)
        body_lay.addLayout(actions)

        actions2 = QHBoxLayout()
        actions2.setSpacing(6)
        self.btn_star = QPushButton("★ 星级")
        self.btn_star.setCursor(Qt.PointingHandCursor)
        self.btn_star.clicked.connect(self._show_star_dialog)
        self.btn_addtag = QPushButton("# 标签")
        self.btn_addtag.setCursor(Qt.PointingHandCursor)
        self.btn_addtag.clicked.connect(self._add_tag_to_video)
        actions2.addWidget(self.btn_star)
        actions2.addWidget(self.btn_addtag)
        body_lay.addLayout(actions2)

        actions3 = QHBoxLayout()
        actions3.setSpacing(6)
        self.btn_javdb = QPushButton("🔎 JAVDB")
        self.btn_javdb.setCursor(Qt.PointingHandCursor)
        self.btn_javdb.clicked.connect(self._fetch_javdb_info)
        self.btn_thumb = QPushButton("🖼 封面")
        self.btn_thumb.setCursor(Qt.PointingHandCursor)
        self.btn_thumb.clicked.connect(lambda: self._refresh_thumbnail(self._current_video_id))
        actions3.addWidget(self.btn_javdb)
        actions3.addWidget(self.btn_thumb)
        body_lay.addLayout(actions3)

        actions4 = QHBoxLayout()
        actions4.setSpacing(6)
        self.btn_open_dir = QPushButton("📂 目录")
        self.btn_open_dir.setCursor(Qt.PointingHandCursor)
        self.btn_open_dir.clicked.connect(self._open_current_dir)
        self.btn_delete = QPushButton("🗑 删除")
        self.btn_delete.setCursor(Qt.PointingHandCursor)
        self.btn_delete.setStyleSheet("color: #cf222e;")
        self.btn_delete.clicked.connect(lambda: self._delete_videos([self._current_video_id]))
        actions4.addWidget(self.btn_open_dir)
        actions4.addWidget(self.btn_delete)
        body_lay.addLayout(actions4)

        lay.addWidget(body, 1)
        return panel

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")
        self.video_count_label = QLabel("0 个视频")
        self.status_bar.addPermanentWidget(self.video_count_label)

    # ==================================================================
    # 菜单（Phase 1 - 对齐 v1 全部菜单项）
    # ==================================================================
    def create_menus(self):
        mb = self.menuBar()

        # ---- 文件 ----
        file_menu = mb.addMenu("文件")
        file_menu.addAction("扫描媒体文件", self.on_scan_media)
        file_menu.addAction("智能媒体库更新", self.on_comprehensive_media_update)
        file_menu.addSeparator()
        file_menu.addAction("导入NFO文件", self.on_import_nfo)
        file_menu.addAction("导入视频文件", self.on_import_videos)
        file_menu.addSeparator()
        file_menu.addAction("批量导入NFO信息", self.on_batch_import_nfo_for_no_actors)
        file_menu.addAction("批量导入JAVDB信息", self.on_batch_import_javdb_for_no_title)
        file_menu.addSeparator()
        file_menu.addAction("去重复", self.on_remove_duplicates)

        # ---- 工具 ----
        tools_menu = mb.addMenu("工具")
        tools_menu.addAction("标签管理", self.on_manage_tags)
        tools_menu.addAction("文件夹管理", self.on_manage_folders)
        tools_menu.addSeparator()
        tools_menu.addAction("同步打分到文件", self.on_sync_stars_to_filename)
        tools_menu.addSeparator()
        tools_menu.addAction("批量计算MD5", self.on_batch_calculate_md5)
        tools_menu.addAction("智能去重", self.on_smart_remove_duplicates)
        tools_menu.addAction("文件移动管理", self.on_file_move_manager)
        tools_menu.addSeparator()
        tools_menu.addAction("清理演员信息", self.on_clean_actor_data)
        tools_menu.addAction("重新导入元数据", self.on_reimport_metadata)
        tools_menu.addAction("完全重置数据库", self.on_full_database_reset)
        tools_menu.addSeparator()
        tools_menu.addAction("批量生成封面", self.on_batch_generate_thumbnails)
        tools_menu.addAction("批量自动更新所有标签", self.on_batch_auto_tag_all)
        tools_menu.addAction("批量标注没有标签的文件", self.on_batch_auto_tag_no_tags)
        tools_menu.addAction("批量清理文件名", self.on_batch_clean_filenames)
        tools_menu.addSeparator()
        tools_menu.addAction("修正JAVDB错误信息", self.on_fix_javdb_error_titles)
        tools_menu.addSeparator()
        tools_menu.addAction("快速智能媒体库更新", self.on_quick_smart_media_update)
        tools_menu.addSeparator()
        tools_menu.addAction("JAV信息面板", self.open_jav_info_dialog)

        # ---- 界面 ----
        view_menu = mb.addMenu("界面")
        view_menu.addAction("刷新", self.refresh_data)
        view_menu.addAction("清空筛选", self.clear_filters)
        view_menu.addAction("重置界面布局", self.on_reset_gui_layout)

        # ---- 帮助 ----
        help_menu = mb.addMenu("帮助")
        help_menu.addAction("关于", self.show_about)
        help_menu.addAction("快捷键", self.show_shortcuts)

    # ==================================================================
    # 快捷键（对齐 v1）
    # ==================================================================
    def create_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+R"), self, activated=self.refresh_data)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self._focus_search)
        for i in range(6):
            QShortcut(QKeySequence(f"Ctrl+{i}"), self,
                      activated=lambda r=i: self._quick_set_star(r))
        QShortcut(QKeySequence(Qt.Key_Space), self, activated=self._play_current)
        QShortcut(QKeySequence(Qt.Key_Return), self, activated=self._gen_thumb_current)

        # 列表专属：当视频列表有焦点时，直接按 0-5 数字键打分（无需 Ctrl）
        # 用 WidgetShortcut 作用域，避免和搜索框输入冲突
        for i in range(6):
            sc = QShortcut(QKeySequence(str(i)), self.video_table,
                           activated=lambda r=i: self._quick_set_star(r))
            sc.setContext(Qt.WidgetShortcut)

    def _focus_search(self):
        """Ctrl+F：聚焦搜索框并全选。"""
        self.search_input.setFocus()
        self.search_input.selectAll()

    def _quick_set_star(self, rating):
        """快捷键设置星级：支持批量（多选时确认后批量设置）。"""
        ids = self.video_table.selected_video_ids()
        if not ids:
            # 兼容：无多选时用当前选中
            if self._current_video_id is not None:
                ids = [self._current_video_id]
            else:
                self.status_bar.showMessage("请先选择视频", 2000)
                return

        if len(ids) == 1:
            self._set_stars(ids, rating)
        else:
            star_text = f"{rating} 星" if rating > 0 else "清除星级"
            reply = QMessageBox.question(
                self, "确认批量设置",
                f"确定要将选中的 {len(ids)} 个视频设置为{star_text}吗？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
            )
            if reply == QMessageBox.Yes:
                self._set_stars(ids, rating)

    def _set_stars(self, video_ids, rating):
        """设置一批视频的星级并刷新（同步 DB + 视图局部刷新）。"""
        ok = 0
        for vid in video_ids:
            if self.core.update_video(vid, stars=rating):
                ok += 1
        star_text = f"{rating} 星" if rating > 0 else "清除星级"
        self.status_bar.showMessage(f"已将 {ok}/{len(video_ids)} 个视频设置为{star_text}", 3000)
        # 刷新当前页（星级列会重绘）
        self.load_videos()
        # 若当前详情是其中之一，刷新详情星级
        if self._current_video_id in video_ids:
            self.load_detail(self._current_video_id)

    def _play_current(self):
        if self._current_video_id is not None:
            self._play_video(self._current_video_id)

    def _gen_thumb_current(self):
        """Enter：为当前视频生成封面。"""
        if self._current_video_id is not None:
            self._refresh_thumbnail(self._current_video_id)

    # ==================================================================
    # 主题 / 导航 / 搜索
    # ==================================================================
    def _toggle_theme(self):
        self.theme_mgr.toggle()
        self._update_theme_button()

    def _update_theme_button(self):
        self.btn_theme.setText("☀" if self.theme_mgr.theme_name == "dark" else "☾")

    def _toggle_online_only(self):
        self.show_online_only = self.btn_online.isChecked()
        self.video_model._current_page_no = 0
        self.load_videos()

    def _on_search(self):
        self._search_text = self.search_input.text().strip()
        self.is_filtering = bool(self._search_text)
        self.video_model._current_page_no = 0
        self.load_videos()

    def on_nav_changed(self, key):
        """侧栏导航变化 → 设置筛选 → 重新加载。"""
        self._nav_filter = key
        # 管理类导航：打开对应对话框
        if key == 'tags':
            self.on_manage_tags(); return
        if key == 'folders':
            self.on_manage_folders(); return
        if key == 'actors':
            from pyside_v2.dialogs import ActorBrowserDialog
            ActorBrowserDialog(self).exec(); return
        if key == 'settings':
            self.status_bar.showMessage("设置（后续）", 3000); return
        # 筛选类导航：重新查询
        self.video_model._current_page_no = 0
        self.load_videos()

    def _open_current_dir(self):
        """在文件管理器中打开当前视频所在目录。"""
        if self._current_video_id is None:
            return
        try:
            self.core.cursor.execute("SELECT file_path FROM videos WHERE id = ?", (self._current_video_id,))
            result = self.core.cursor.fetchone()
            if not result or not result[0]:
                return
            import os, subprocess
            folder = os.path.dirname(result[0])
            if platform.system() == 'Darwin':
                subprocess.Popen(['open', folder])
            elif platform.system() == 'Windows':
                subprocess.Popen(['explorer', folder])
            else:
                subprocess.Popen(['xdg-open', folder])
        except Exception as e:
            self.show_error("打开目录失败", str(e))

    # ==================================================================
    # 右键菜单（单选/多选，对齐 v1）
    # ==================================================================
    def show_context_menu(self, position):
        """列表右键菜单。position 是 video_table viewport 相对坐标。"""
        from PySide6.QtWidgets import QApplication as _QApp
        index = self.video_table.indexAt(position)
        if not index.isValid():
            return
        # 确保点击项在选中集合里
        ids = self.video_table.selected_video_ids()
        vid_clicked = index.data(Qt.UserRole)
        if vid_clicked not in ids:
            self.video_table.selectRow(index.row())
            ids = [vid_clicked]

        menu = QMenu(self)
        count = len(ids)

        if count == 1:
            self._build_single_menu(menu, ids[0])
        else:
            self._build_batch_menu(menu, ids, count)

        menu.exec(self.video_table.viewport().mapToGlobal(position))

    def _build_single_menu(self, menu, video_id):
        """单选右键菜单。"""
        # 播放
        menu.addAction("▶ 播放", lambda: self._play_video(video_id))
        menu.addSeparator()
        # 在文件管理器显示 / 复制路径
        menu.addAction("在文件管理器中显示", lambda: self._show_in_finder(video_id))
        menu.addAction("复制文件路径", lambda: self._copy_path(video_id))
        menu.addSeparator()
        # 移动到...
        move_menu = menu.addMenu("移动到…")
        self._fill_move_menu(move_menu, lambda f: self._move_single(video_id, f))
        # 清理文件名 / 自动标签
        menu.addAction("清理文件名", lambda: self._clean_filename_single(video_id))
        menu.addAction("自动标签", lambda: self._auto_tag_single(video_id))
        menu.addSeparator()
        # 快速设置星级
        star_menu = menu.addMenu("快速设置星级")
        star_menu.addAction("清除星级", lambda: self._set_stars([video_id], 0))
        for i in range(1, 6):
            star_menu.addAction(f"{'★'*i} {i} 星", lambda r=i: self._set_stars([video_id], r))
        menu.addSeparator()
        # 刷新封面
        menu.addAction("刷新封面", lambda: self._refresh_thumbnail(video_id))
        # 视频旋转子菜单
        rotate_menu = menu.addMenu("顺时针旋转")
        rotate_menu.addAction("旋转 90°", lambda: self._rotate_video(video_id, 90))
        rotate_menu.addAction("旋转 180°", lambda: self._rotate_video(video_id, 180))
        rotate_menu.addAction("旋转 270°", lambda: self._rotate_video(video_id, 270))
        # 迁移/复制 JavSP（单个）
        migrate_menu = menu.addMenu("迁移 JavSP 到…")
        self._fill_move_menu(migrate_menu, lambda f: self._migrate_javsp([video_id], f, is_copy=False))
        copy_menu = menu.addMenu("复制 JavSP 到…")
        self._fill_move_menu(copy_menu, lambda f: self._migrate_javsp([video_id], f, is_copy=True))
        menu.addSeparator()
        # 删除
        del_action = menu.addAction("🗑 删除视频")
        del_action.triggered.connect(lambda: self._delete_videos([video_id]))

    def _build_batch_menu(self, menu, ids, count):
        """多选右键菜单（批量）。"""
        menu.addAction(f"已选择 {count} 个文件").setEnabled(False)
        menu.addSeparator()
        # 批量星级
        star_menu = menu.addMenu(f"批量设置星级 ({count})")
        star_menu.addAction("清除星级", lambda: self._set_stars(ids, 0))
        for i in range(1, 6):
            star_menu.addAction(f"{'★'*i} {i} 星", lambda r=i: self._set_stars(ids, r))
        menu.addSeparator()
        # 批量移动
        move_menu = menu.addMenu(f"批量移动到… ({count})")
        self._fill_move_menu(move_menu, lambda f: self._batch_move(ids, f))
        # 批量迁移 JavSP
        mig_menu = menu.addMenu(f"批量迁移 JavSP 到… ({count})")
        self._fill_move_menu(mig_menu, lambda f: self._migrate_javsp(ids, f, is_copy=False))
        # 批量复制 JavSP
        cp_menu = menu.addMenu(f"批量复制 JavSP 到… ({count})")
        self._fill_move_menu(cp_menu, lambda f: self._migrate_javsp(ids, f, is_copy=True))
        menu.addSeparator()
        # 批量清理文件名 / 删除
        menu.addAction(f"批量清理文件名 ({count})", lambda: self._batch_clean_filename(ids))
        del_action = menu.addAction(f"批量删除 ({count})")
        del_action.triggered.connect(lambda: self._delete_videos(ids))

    def _fill_move_menu(self, move_menu, handler):
        """填充"移动到"子菜单（在线文件夹列表）。"""
        online_folders = self.core.get_online_folders()
        if online_folders:
            for folder in online_folders:
                name = os.path.basename(folder) or folder
                move_menu.addAction(name, lambda checked=False, f=folder: handler(f))
        else:
            move_menu.addAction("（无在线文件夹）").setEnabled(False)

    # ---- 右键菜单调用的操作 ----
    def _show_in_finder(self, video_id):
        try:
            self.core.cursor.execute("SELECT file_path FROM videos WHERE id = ?", (video_id,))
            r = self.core.cursor.fetchone()
            if not r or not r[0]:
                return
            import subprocess
            fp = r[0]
            if platform.system() == 'Darwin':
                subprocess.Popen(['open', '-R', fp])
            elif platform.system() == 'Windows':
                subprocess.Popen(['explorer', '/select,', fp])
            else:
                subprocess.Popen(['xdg-open', os.path.dirname(fp)])
        except Exception as e:
            self.show_error("打开失败", str(e))

    def _copy_path(self, video_id):
        try:
            self.core.cursor.execute("SELECT file_path FROM videos WHERE id = ?", (video_id,))
            r = self.core.cursor.fetchone()
            if r and r[0]:
                QApplication.clipboard().setText(r[0])
                self.status_bar.showMessage("文件路径已复制", 2000)
        except Exception as e:
            self.show_error("复制失败", str(e))

    def _move_single(self, video_id, target_folder):
        """移动单个文件到目标文件夹。"""
        try:
            self.core.cursor.execute("SELECT file_path FROM videos WHERE id = ?", (video_id,))
            r = self.core.cursor.fetchone()
            if not r or not r[0]:
                return
            old_path = r[0]
            self.core.move_file(video_id, old_path, target_folder)
            self.status_bar.showMessage(f"已移动到 {os.path.basename(target_folder)}", 3000)
            self.load_videos()
        except FileExistsError as e:
            self.show_error("移动失败", str(e))
        except Exception as e:
            self.show_error("移动失败", str(e))

    def _batch_move(self, ids, target_folder):
        """批量移动。"""
        ok = 0
        for vid in ids:
            try:
                self.core.cursor.execute("SELECT file_path FROM videos WHERE id = ?", (vid,))
                r = self.core.cursor.fetchone()
                if r and r[0]:
                    self.core.move_file(vid, r[0], target_folder)
                    ok += 1
            except Exception:
                pass
        self.status_bar.showMessage(f"已移动 {ok}/{len(ids)} 到 {os.path.basename(target_folder)}", 4000)
        self.load_videos()

    def _clean_filename_single(self, video_id):
        ok, msg = self.core.clean_filename_for_video(video_id)
        self.status_bar.showMessage(msg, 3000)
        if ok:
            self.load_videos()

    def _batch_clean_filename(self, ids):
        ok = 0
        for vid in ids:
            success, _ = self.core.clean_filename_for_video(vid)
            if success:
                ok += 1
        self.status_bar.showMessage(f"已清理 {ok}/{len(ids)} 个文件名", 3000)
        self.load_videos()

    def _auto_tag_single(self, video_id):
        """自动标签单个视频（调用桥接的 auto_tag 逻辑）。"""
        self.status_bar.showMessage("自动标签中…（可能较慢）")
        try:
            self.core.cursor.execute("SELECT file_path FROM videos WHERE id = ?", (video_id,))
            r = self.core.cursor.fetchone()
            if r and r[0]:
                ok, msg = self.core.auto_tag_video(r[0], use_retry=False)
                self.status_bar.showMessage(msg, 4000)
                if ok:
                    self.load_detail(video_id)
        except Exception as e:
            self.status_bar.showMessage(f"自动标签失败: {e}", 4000)

    def _refresh_thumbnail(self, video_id):
        """刷新封面（生成缩略图）。"""
        self.status_bar.showMessage("生成封面中…")
        try:
            self.core.cursor.execute("SELECT file_path FROM videos WHERE id = ?", (video_id,))
            r = self.core.cursor.fetchone()
            if r and r[0]:
                ok, out = self.core.generate_thumbnail_for_video(r[0])
                if ok and out:
                    # 写入 thumbnail_data
                    with open(out, 'rb') as f:
                        data = f.read()
                    self.core.cursor.execute(
                        "UPDATE videos SET thumbnail_data=?, thumbnail_path=? WHERE id=?",
                        (data, out, video_id)
                    )
                    self.core.conn.commit()
                    self.status_bar.showMessage("封面已刷新", 3000)
                    if self._current_video_id == video_id:
                        self._load_cover(video_id)
                else:
                    self.status_bar.showMessage(out or "生成失败", 3000)
        except Exception as e:
            self.status_bar.showMessage(f"生成封面失败: {e}", 3000)

    def _delete_videos(self, ids):
        """删除视频（回收站 + 删库记录）。"""
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除选中的 {len(ids)} 个视频吗？\n（文件移至回收站，库记录删除）",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        ok = 0
        for vid in ids:
            try:
                self.core.cursor.execute("SELECT file_path FROM videos WHERE id = ?", (vid,))
                r = self.core.cursor.fetchone()
                if r and r[0] and os.path.exists(r[0]):
                    try:
                        from send2trash import send2trash
                        send2trash(r[0])
                    except Exception:
                        pass
                if self.core.delete_video(vid):
                    ok += 1
            except Exception:
                pass
        self.status_bar.showMessage(f"已删除 {ok}/{len(ids)} 个视频", 3000)
        self.load_videos()

    def _rotate_video(self, video_id, degrees):
        """顺时针旋转视频（对接 utils.video_rotate，后台线程）。"""
        try:
            self.core.cursor.execute("SELECT file_path FROM videos WHERE id=?", (video_id,))
            r = self.core.cursor.fetchone()
            if not r or not r[0]:
                return
            file_path = r[0]
            reply = QMessageBox.question(
                self, "确认旋转",
                f"确定要将视频顺时针旋转 {degrees}° 吗？\n此操作将重新编码并覆盖原文件，可能较慢。",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

            self.status_bar.showMessage(f"正在旋转 {degrees}°…（后台执行）")
            QApplication.processEvents()

            from utils import video_rotate
            from pyside_v2.core.bridge import GenericWorker

            def worker_func(progress_callback, cancel_check):
                def cb(percent, msg):
                    if cancel_check():
                        return
                    p = 50 if percent == -1 else percent
                    progress_callback(msg, p, {})
                success, msg = video_rotate.rotate_video(file_path, degrees, cb)
                return {'success': success, 'msg': msg}

            worker = GenericWorker(worker_func)
            def on_finished(result):
                success = result.get('success')
                msg = result.get('msg', '')
                if success:
                    self.status_bar.showMessage(f"已旋转 {degrees}°", 3000)
                    # 重新生成封面 + 刷新详情
                    self._refresh_thumbnail(video_id)
                    if self._current_video_id == video_id:
                        self.load_detail(video_id)
                else:
                    self.show_error("旋转失败", msg)
            def on_error(err):
                self.show_error("旋转出错", err)
            worker.finished_signal.connect(on_finished)
            worker.error_signal.connect(on_error)
            worker.start()
        except Exception as e:
            self.show_error("旋转失败", str(e))

    def _migrate_javsp(self, ids, target_folder, is_copy=False):
        """批量迁移/复制 JavSP 文件到目标文件夹（对接 core.migrate/copy_javsp_file）。"""
        action = "复制" if is_copy else "迁移"
        reply = QMessageBox.question(
            self, f"确认{action}",
            f"确定要{action} {len(ids)} 个视频的 JavSP 文件到\n{target_folder} 吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self.status_bar.showMessage(f"正在{action} JavSP…")
        ok = 0
        for i, vid in enumerate(ids):
            try:
                self.core.cursor.execute("SELECT file_path FROM videos WHERE id=?", (vid,))
                r = self.core.cursor.fetchone()
                if not r or not r[0]:
                    continue
                self.status_bar.showMessage(f"{action} {i+1}/{len(ids)}: {os.path.basename(r[0])}")
                QApplication.processEvents()
                if is_copy:
                    self.core.copy_javsp_file(vid, r[0], target_folder)
                else:
                    self.core.migrate_javsp_file(vid, r[0], target_folder)
                ok += 1
            except Exception as e:
                self.status_bar.showMessage(f"{action}失败 {vid}: {e}", 3000)
        self.status_bar.showMessage(f"已{action} {ok}/{len(ids)} 个 JavSP 文件", 4000)
        self.load_videos()

    # ==================================================================
    # 数据加载（Phase 2 核心 - 分页 + 核心字段，性能版）
    # ==================================================================
    def load_videos(self):
        """异步加载当前页视频列表。

        查询在后台线程执行（QueryWorker），UI 保持响应——冷查询（SQLite 大库
        首次磁盘读）可能 2-5s，热查询 0.1s。查询期间状态栏显示"加载中"。
        """
        if not self.core.ensure_connection():
            self.show_error("加载失败", "数据库连接失败")
            return

        # 构建 SQL（同步，纯字符串拼接，不查库）
        fields, where_clause, order_clause, params, offset, limit, page_size, page_no = \
            self._build_query()

        # 防止并发：若有旧 worker 在跑，等其结束（新查询覆盖）
        if hasattr(self, '_query_worker') and self._query_worker and self._query_worker.isRunning():
            self._query_worker.quit()
            self._query_worker.wait(500)

        self.status_bar.showMessage("⏳ 加载中…")
        self.video_count_label.setText("查询中…")

        # 闭包：在 worker 线程里执行 COUNT + 分页。
        # 用独立 cursor（共享 connection 但 SQLite 不支持并发游标，
        # 独立 cursor 避免和主线程/详情子查询的 cursor 冲突）。
        def do_query():
            cur = self.core.conn.cursor()
            count_sql = f"SELECT COUNT(*) FROM videos v {where_clause}"
            cur.execute(count_sql, params)
            total = cur.fetchone()[0]
            page_sql = f"SELECT {fields} FROM videos v {where_clause} {order_clause} LIMIT ? OFFSET ?"
            cur.execute(page_sql, params + [limit, offset])
            rows = cur.fetchall()
            cur.close()
            return rows, total

        from pyside_v2.workers import QueryWorker
        self._query_worker = QueryWorker(do_query, page_no, self)
        self._query_worker.finished_signal.connect(self._on_query_finished)
        self._query_worker.error_signal.connect(self._on_query_error)
        self._query_worker.start()

    def _build_query(self):
        """构建查询 SQL 各部分（同步，不执行）。"""
        fields = ('id, file_path, file_name, title, stars, tags, file_size, '
                  'is_nas_online, duration, resolution, file_created_time, '
                  'source_folder, md5_hash')

        conditions = []
        params = []

        if self.is_filtering and self._search_text:
            self._apply_search_filters(conditions, params)
        self._apply_nav_filter(conditions, params)

        if getattr(self, 'show_online_only', False):
            conditions.append("v.is_nas_online = 1")

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        # 排序
        from pyside_v2.widgets.video_model import SORT_MAPPING
        order_col = 'file_created_time'
        if getattr(self.core, 'sort_column_name', None):
            order_col = SORT_MAPPING.get(self.core.sort_column_name, 'file_created_time')
        direction = "DESC" if getattr(self.core, 'sort_reverse', False) else "ASC"
        if not getattr(self.core, 'sort_column_name', None):
            direction = "DESC"
        order_clause = f"ORDER BY {order_col} {direction}"

        # 有筛选时不排序（结果少；排序+is_nas_online 会退化全表扫）
        has_filter = bool(self._search_text) or self._nav_filter in (
            'favorites', 'recent', 'notag'
        ) or self._nav_filter.startswith('folder:')
        if has_filter and not getattr(self.core, 'sort_column_name', None):
            order_clause = ""

        page_size = self.video_model.page_size
        page_no = self.video_model.current_page_no
        offset = page_no * page_size
        limit = page_size
        return fields, where_clause, order_clause, params, offset, limit, page_size, page_no

    def _on_query_finished(self, rows, total, page_no):
        """查询完成（主线程）：更新模型 + 状态栏。"""
        page_size = self.video_model.page_size
        offset = page_no * page_size
        self.video_model.set_page(rows, total, page_no)
        start = offset + 1 if total > 0 else 0
        end = min(offset + len(rows), total)
        self.video_count_label.setText(f"{total} 个视频")
        self.status_bar.showMessage(
            f"显示 {start}-{end} / 共 {total}（第 {page_no+1} 页）", 3000)
        max_page = max(1, (total - 1) // page_size + 1) if total > 0 else 1
        self.page_label.setText(f"{page_no + 1} / {max_page}")

    def _on_query_error(self, msg):
        self.status_bar.showMessage(f"❌ 查询失败: {msg}", 5000)
        self.video_count_label.setText("查询失败")

    def go_first_page(self):
        self._goto_page(0)

    def go_prev_page(self):
        self._goto_page(max(0, self.video_model.current_page_no - 1))

    def go_next_page(self):
        page_size = self.video_model.page_size
        max_page = max(0, (self.video_model.total_count - 1) // page_size)
        self._goto_page(min(max_page, self.video_model.current_page_no + 1))

    def go_last_page(self):
        page_size = self.video_model.page_size
        max_page = max(0, (self.video_model.total_count - 1) // page_size)
        self._goto_page(max_page)

    def _goto_page(self, page_no):
        if page_no != self.video_model.current_page_no:
            # 直接改 model 内部字段，load_videos 会读取
            self.video_model._current_page_no = page_no
            self.load_videos()

    def _apply_search_filters(self, conditions, params):
        """顶部搜索框 → 标题/文件名/标签/演员 综合搜索。

        性能关键：用 id IN (子查询) 而非直接 OR LIKE。
        原因：当和 is_nas_online 等条件 AND 时，直接 OR LIKE 会强制全表扫描；
        用 IN 子查询让 SQLite 先在子查询里用 LIKE 缩小范围（~0.05s），
        再对外层少量结果过滤，整体 0.06s（直接 AND 要 3s）。
        """
        text = self._search_text
        if not text:
            return
        kw = f"%{text}%"
        # 子查询：title/file_name/tags LIKE + 演员名 LIKE
        conditions.append(
            "v.id IN ("
            "SELECT id FROM videos WHERE title LIKE ? OR file_name LIKE ? OR tags LIKE ? "
            "UNION "
            "SELECT va.video_id FROM video_actors va JOIN actors a ON va.actor_id=a.id "
            "WHERE a.name LIKE ?"
            ")"
        )
        params.extend([kw, kw, kw, kw])

    def _apply_nav_filter(self, conditions, params):
        """侧栏导航 → 筛选条件。"""
        key = self._nav_filter
        if key == 'all':
            return
        if key == 'favorites':
            conditions.append("v.stars >= 4")           # 高星视为收藏
        elif key == 'recent':
            conditions.append("v.file_created_time >= datetime('now', '-30 days')")
        elif key == 'notag':
            conditions.append("(v.tags IS NULL OR v.tags = '' OR v.tags = '<无标签>')")
        elif key.startswith('folder:'):
            folder_path = key[len('folder:'):]
            if platform.system() == 'Windows':
                conditions.append("REPLACE(v.source_folder, CHAR(92), '/') LIKE REPLACE(?, CHAR(92), '/') || '%'")
                params.append(folder_path)
            else:
                conditions.append("v.source_folder LIKE ?")
                params.append(f"{folder_path}%")

    # ==================================================================
    # 列表交互
    # ==================================================================
    def on_video_selected(self, video_id):
        self._current_video_id = video_id
        if video_id is not None:
            self.load_detail(video_id)

    def load_detail(self, video_id):
        """填充右侧详情卡片（按 video_id 子查询完整信息 + 演员）。"""
        try:
            # 主信息 + JAVDB
            self.core.cursor.execute(
                "SELECT v.title, v.file_name, v.file_size, v.duration, v.resolution, "
                "v.file_created_time, v.file_path, v.source_folder, v.stars, v.tags, "
                "j.javdb_code, j.javdb_title, j.score, j.release_date "
                "FROM videos v LEFT JOIN javdb_info j ON v.id = j.video_id "
                "WHERE v.id = ?", (video_id,)
            )
            row = self.core.cursor.fetchone()
            if not row:
                return
            (title, file_name, fsize, dur, res, fctime, fpath, sfolder,
             stars, tags, jcode, jtitle, jscore, jrelease) = row

            # 演员（子查询，按索引快）
            self.core.cursor.execute(
                "SELECT GROUP_CONCAT(a.name, ', ') FROM video_actors va "
                "JOIN actors a ON va.actor_id=a.id WHERE va.video_id=?", (video_id,)
            )
            actors = self.core.cursor.fetchone()[0] or "—"

            # 查 description 字段
            self.core.cursor.execute("SELECT description FROM videos WHERE id=?", (video_id,))
            desc_row = self.core.cursor.fetchone()
            description = desc_row[0] if desc_row and desc_row[0] else ""

            # 可编辑字段
            self.detail_title_edit.setText(title or "")
            self.detail_tags_edit.setText(tags or "")
            self.detail_desc_edit.setPlainText(description)

            # 星级标签（可点）
            self._current_stars = stars or 0
            self.detail_stars_label.setText(
                "★" * (stars or 0) + "☆" * (5 - (stars or 0))
            )

            sub_parts = []
            if jcode:
                sub_parts.append(jcode)
            if jrelease:
                sub_parts.append(f"{jrelease} 发行")
            self.detail_sub.setText(" · ".join(sub_parts) if sub_parts else file_name or "")

            # kv 元数据（只读）
            self._clear_layout(self.detail_kv_container)
            def _kv(k, v, mono=False):
                row_w = QWidget(); row_w.setStyleSheet("background:transparent;")
                rl = QHBoxLayout(row_w); rl.setContentsMargins(0,0,0,0); rl.setSpacing(0)
                kl = QLabel(k); kl.setObjectName("detailKey"); kl.setFixedWidth(76)
                vlbl = QLabel(str(v));
                vlbl.setObjectName("detailValueMono" if mono else "detailValue")
                vlbl.setWordWrap(not mono)
                rl.addWidget(kl); rl.addWidget(vlbl, 1)
                self.detail_kv_container.addWidget(row_w)

            import os
            _kv("演员", actors)
            _kv("大小", self._fmt_size(fsize))
            _kv("时长", self._fmt_duration(dur))
            _kv("分辨率", res or "—")
            _kv("创建时间", self._fmt_dt(fctime))
            if jscore:
                _kv("JAVDB评分", str(jscore))
            _kv("路径", fpath or "—", mono=True)

            # 封面缩略图（数据库里的 thumbnail_data BLOB）
            self._load_cover(video_id)
        except Exception as e:
            print(f"加载详情失败: {e}")

    def _load_cover(self, video_id):
        """加载封面缩略图（thumbnail_data BLOB 或 JAVDB 封面）。"""
        try:
            from PySide6.QtGui import QPixmap
            from PIL import Image
            import io
            self.core.cursor.execute("SELECT thumbnail_data FROM videos WHERE id=?", (video_id,))
            row = self.core.cursor.fetchone()
            if row and row[0]:
                pix = QPixmap()
                pix.loadFromData(row[0])
                if not pix.isNull():
                    self.cover_label.setPixmap(
                        pix.scaled(self.cover_label.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                    )
                    self.cover_label.setText("")
                    return
            # JAVDB 封面兜底
            self.core.cursor.execute("SELECT cover_image_data FROM javdb_info WHERE video_id=?", (video_id,))
            row = self.core.cursor.fetchone()
            if row and row[0]:
                pix = QPixmap()
                pix.loadFromData(row[0])
                if not pix.isNull():
                    self.cover_label.setPixmap(
                        pix.scaled(self.cover_label.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                    )
                    self.cover_label.setText("")
                    return
            self.cover_label.setText("无封面")
            self.cover_label.setPixmap(QPixmap())
        except Exception as e:
            self.cover_label.setText("无封面")

    # ---- 详情面板操作按钮 ----
    def _save_video_info(self):
        """保存详情面板的标题/标签/描述编辑。"""
        if self._current_video_id is None:
            return
        try:
            title = self.detail_title_edit.text().strip()
            tags = self.detail_tags_edit.text().strip()
            desc = self.detail_desc_edit.toPlainText().strip()
            self.core.cursor.execute(
                "UPDATE videos SET title=?, tags=?, description=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (title, tags, desc, self._current_video_id)
            )
            self.core.conn.commit()
            self.status_bar.showMessage("已保存", 2000)
            self.load_videos()
        except Exception as e:
            self.show_error("保存失败", str(e))

    def _show_star_dialog(self):
        """弹出星级设置对话框。"""
        if self._current_video_id is None:
            return
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QRadioButton, QButtonGroup, QDialogButtonBox
        dlg = QDialog(self)
        dlg.setWindowTitle("设置星级")
        dlg.setFixedSize(320, 130)
        lay = QVBoxLayout(dlg)
        row = QHBoxLayout()
        grp = QButtonGroup(dlg)
        for i in range(6):
            text = "清除" if i == 0 else f"{'★'*i} {i}星"
            rb = QRadioButton(text)
            grp.addButton(rb, i)
            row.addWidget(rb)
        cur = getattr(self, '_current_stars', 0) or 0
        btns = grp.buttons()
        if cur < len(btns):
            btns[cur].setChecked(True)
        lay.addLayout(row)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        if dlg.exec() == QDialog.Accepted:
            r = grp.checkedId()
            if r >= 0:
                self._set_stars([self._current_video_id], r)

    def _detail_star_clicked(self, event):
        """点击详情星级标签：根据点击位置算星级。"""
        if self._current_video_id is None:
            return
        lbl = self.detail_stars_label
        char_w = lbl.fontMetrics().horizontalAdvance('★')
        if char_w <= 0:
            return
        star = int(event.position().x() / char_w) + 1
        star = max(0, min(5, star))
        # 再点同一星降一级（0=清除）
        if star == getattr(self, '_current_stars', 0):
            star = star - 1 if star > 0 else 0
        self._set_stars([self._current_video_id], star)

    def _add_tag_to_video(self):
        """添加标签：弹出输入框，追加到标签字段。"""
        if self._current_video_id is None:
            return
        from PySide6.QtWidgets import QInputDialog
        text, ok = QInputDialog.getText(self, "添加标签", "输入标签（多个用逗号分隔）：")
        if ok and text.strip():
            current = self.detail_tags_edit.text().strip()
            new_tags = (current + ", " if current else "") + text.strip()
            self.detail_tags_edit.setText(new_tags)
            self.status_bar.showMessage("已添加，点「保存」生效", 3000)

    def _fetch_javdb_info(self):
        """抓取当前视频的 JAVDB 信息并入库（对接 utils.jav）。"""
        if self._current_video_id is None:
            return
        try:
            self.core.cursor.execute("SELECT file_name FROM videos WHERE id=?", (self._current_video_id,))
            r = self.core.cursor.fetchone()
            if not r or not r[0]:
                return
            from utils import jav as utils_jav
            code = utils_jav.extract_code(r[0])
            if not code:
                self.status_bar.showMessage("无法从文件名提取番号", 3000)
                return
            self.status_bar.showMessage(f"正在获取 JAVDB 信息：{code}…（可能较慢）")
            QApplication.processEvents()
            info = utils_jav.search_movie_info(code)
            if not info:
                self.status_bar.showMessage("未获取到 JAVDB 信息", 3000)
                return
            ok = utils_jav.save_movie_info_to_db(self.core.conn, self._current_video_id, info)
            if ok:
                self.status_bar.showMessage("JAVDB 信息已保存", 3000)
                self.load_detail(self._current_video_id)
                self.load_videos()
            else:
                self.status_bar.showMessage("保存 JAVDB 信息失败", 3000)
        except Exception as e:
            self.status_bar.showMessage(f"获取 JAVDB 失败: {e}", 4000)

    @staticmethod
    def _fmt_size(size):
        if not size: return "—"
        s = float(size)
        for u in ('B','KB','MB','GB','TB'):
            if s < 1024: return f"{s:.2f} {u}"
            s /= 1024
        return f"{s:.2f} PB"

    @staticmethod
    def _fmt_duration(sec):
        if not sec: return "—"
        s = int(sec); h, r = divmod(s, 3600); m, s = divmod(r, 60)
        return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

    @staticmethod
    def _fmt_dt(dt):
        if not dt: return "—"
        return str(dt)[:19].replace('T', ' ')

    def on_video_double_clicked(self, video_id):
        if video_id is not None:
            self._play_video(video_id)

    def on_header_clicked(self, col_key):
        """表头点击切换排序。"""
        if self.core.sort_column_name == col_key:
            self.core.sort_reverse = not self.core.sort_reverse
        else:
            self.core.sort_column_name = col_key
            self.core.sort_reverse = False
        self.load_videos()

    # 暴露给右键菜单（Phase 6）的信号占位
    context_menu_requested = Signal(object)

    # ==================================================================
    # adapter 契约方法
    # ==================================================================
    def show_error(self, title, message):
        QMessageBox.critical(self, title, str(message))

    def refresh_data(self):
        self.load_videos()

    def clear_filters(self):
        self.is_filtering = False
        self._search_text = ""
        self._nav_filter = 'all'
        self.core.sort_column_name = None
        self.core.sort_reverse = False
        self.video_model._current_page_no = 0
        # 清空搜索框 + 重置侧栏选中
        self.search_input.clear()
        self.sidebar.select_all()
        self.load_videos()

    def on_reset_gui_layout(self):
        """重置列布局（修复 v1 setup_table_columns 未定义 bug，改用 QHeaderView 原生）。"""
        # 重置为默认列宽
        for i, key in enumerate(self.video_model.column_keys):
            w = self.core.default_columns.get(key, {}).get('width', 100)
            self.video_table.setColumnWidth(i, w)
        self.status_bar.showMessage("界面布局已重置", 3000)

    def setup_function_integration(self):
        integration = setup_full_integration(self)
        import media_library
        original_class = media_library.MediaLibrary
        public_methods = [
            m for m in dir(original_class)
            if not m.startswith('_') and callable(getattr(original_class, m, None))
        ]
        bound = sum(1 for m in public_methods if hasattr(self, m) and callable(getattr(self, m)))
        return bound

    # ==================================================================
    # 菜单动作处理器（大部分走桥接，Phase 4/5/6 补充完整）
    # ==================================================================
    def _bridged(self, method_name, *args, **kwargs):
        """调用桥接来的后端方法。"""
        m = getattr(self, method_name, None)
        if m and callable(m):
            return m(*args, **kwargs)
        self.status_bar.showMessage(f"⚠️ {method_name} 暂未实现（见 Phase 4/5/6）", 4000)

    # 文件菜单
    def on_scan_media(self): self._bridged_bg("scan_media", "扫描媒体文件")
    def on_comprehensive_media_update(self): self._bridged("comprehensive_media_update")
    def on_import_nfo(self): self._bridged("import_nfo")
    def on_import_videos(self):
        """打开导入视频文件对话框（原生 PySide6，替代桥接失败的 import_videos）。"""
        from pyside_v2.dialogs import ImportVideosDialog
        dlg = ImportVideosDialog(self)
        dlg.exec()
    def on_batch_import_nfo_for_no_actors(self): self._bridged("batch_import_nfo_for_no_actors")
    def on_batch_import_javdb_for_no_title(self): self._bridged("batch_import_javdb_for_no_title")
    def on_remove_duplicates(self): self._bridged("remove_duplicates")

    # 工具菜单
    def on_manage_tags(self):
        from pyside_v2.dialogs.tag_manager import TagManagerDialog
        TagManagerDialog(self).exec()
    def on_manage_folders(self):
        from pyside_v2.dialogs.folder_manager import FolderManagerDialog
        FolderManagerDialog(self).exec()
    def on_sync_stars_to_filename(self): self._bridged("sync_stars_to_filename")
    def on_batch_calculate_md5(self): self._bridged_bg("batch_calculate_md5", "批量计算 MD5")
    def on_smart_remove_duplicates(self): self._bridged("smart_remove_duplicates")
    def on_file_move_manager(self): self._bridged("file_move_manager")
    def on_clean_actor_data(self): self._bridged_confirm("clean_actor_data", "清理演员信息", "确定要清理无效的演员信息吗？")
    def on_reimport_metadata(self): self._bridged_bg("reimport_incomplete_metadata", "重新导入元数据")
    def on_full_database_reset(self):
        reply = QMessageBox.critical(
            self, "⚠️ 危险操作",
            "完全重置数据库将清空所有视频记录并重新扫描！\n\n确定继续吗？此操作不可撤销。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._bridged_bg("full_database_reset", "重置数据库")
    def on_batch_generate_thumbnails(self): self._bridged_bg("batch_generate_thumbnails", "批量生成封面")
    def on_batch_auto_tag_all(self): self._bridged_bg("batch_auto_tag_all", "批量自动标签")
    def on_batch_auto_tag_no_tags(self): self._bridged_bg("batch_auto_tag_no_tags", "批量标注无标签文件")
    def on_batch_clean_filenames(self): self._bridged("batch_clean_filenames")
    def on_fix_javdb_error_titles(self): self._bridged_bg("fix_javdb_error_titles", "修正 JAVDB 错误信息")
    def on_quick_smart_media_update(self): self._bridged_bg("quick_smart_media_update", "快速智能更新")
    def open_jav_info_dialog(self):
        from pyside_v2.dialogs.jav_info_dialog import JavInfoDialog
        JavInfoDialog(self).exec()

    def _bridged_confirm(self, method_name, title, prompt):
        """带确认框的桥接调用。"""
        reply = QMessageBox.question(self, title, prompt, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self._bridged(method_name)

    def _bridged_bg(self, method_name, label):
        """桥接调用耗时操作：状态栏提示 + 调用后刷新。
        同步执行（会短暂阻塞 UI），但后端方法本身多为多线程或快操作。
        完整异步化在 Phase 4 异步任务系统统一处理。
        """
        m = getattr(self, method_name, None)
        if not (m and callable(m)):
            self.status_bar.showMessage(f"⚠️ {method_name} 不可用", 4000)
            return
        self.status_bar.showMessage(f"⏳ {label} 执行中…")
        QApplication.processEvents()
        try:
            result = m()
            self.status_bar.showMessage(f"✅ {label} 完成", 4000)
            self.refresh_data()
        except Exception as e:
            self.show_error(label + "失败", str(e))

    # 帮助
    def show_about(self):
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.about(self, "关于",
            "视频媒体库管理器 v2 (PySide6)\n\n"
            "性冷淡风 / Normcore 界面\n"
            "复用 media_library.py 全部后端能力\n\n"
            "Phase 0-2 已完成：脚手架 + 主题 + 高性能列表")

    def show_shortcuts(self):
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(self, "快捷键",
            "Ctrl+R  刷新\n"
            "Ctrl+F  聚焦搜索\n"
            "Ctrl+0..5  设置星级\n"
            "Space   播放\n"
            "Enter   生成封面")

    # ==================================================================
    # 播放（跨平台，移植自 v1）
    # ==================================================================
    def _play_video(self, video_id):
        try:
            self.core.cursor.execute("SELECT file_path FROM videos WHERE id = ?", (video_id,))
            result = self.core.cursor.fetchone()
            if not result or not result[0]:
                return
            file_path = result[0]
            if not os.path.exists(file_path):
                self.status_bar.showMessage(f"文件不存在: {file_path}", 4000)
                return
            if platform.system() == 'Darwin':
                import subprocess
                subprocess.Popen(['open', file_path])
            elif platform.system() == 'Windows':
                os.startfile(file_path)
            else:
                import subprocess
                subprocess.Popen(['xdg-open', file_path])
        except Exception as e:
            self.show_error("播放失败", str(e))

    # ==================================================================
    # 日志
    # ==================================================================
    def append_log(self, message: str):
        self.status_bar.showMessage(message, 5000)
