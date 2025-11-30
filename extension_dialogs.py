#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
扩展功能对话框
为PySide6界面添加重复文件检测、NFO导入、批量操作等功能
"""

import os
from typing import List, Dict, Any, Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar,
    QTextEdit, QTableWidget, QTableWidgetItem, QCheckBox, QComboBox,
    QSpinBox, QFileDialog, QMessageBox, QGroupBox, QRadioButton,
    QButtonGroup, QLineEdit, QTabWidget, QSplitter, QHeaderView,
    QAbstractItemView, QFrame
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont

from utils import (
    DatabaseManager, NFOImporter, DuplicateManager, BatchOperations,
    MediaScanner, ThreadedProgress, get_logger
)

logger = get_logger("ExtensionDialogs")

class WorkerThread(QThread):
    """工作线程基类"""
    progress_update = Signal(int, int, str)  # current, total, message
    finished = Signal(dict)  # result
    error = Signal(str)  # error message

    def __init__(self):
        super().__init__()
        self._cancelled = False

    def cancel(self):
        """取消操作"""
        self._cancelled = True

    def is_cancelled(self):
        """检查是否已取消"""
        return self._cancelled

class DuplicateFinderThread(WorkerThread):
    """重复文件查找线程"""
    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db_manager = db_manager

    def run(self):
        try:
            duplicate_manager = DuplicateManager(self.db_manager)
            duplicates = duplicate_manager.find_duplicate_files()

            if self.is_cancelled():
                return

            self.finished.emit({'duplicates': duplicates})
        except Exception as e:
            self.error.emit(str(e))

class NFODialog(QDialog):
    """NFO导入对话框"""
    def __init__(self, parent=None, db_manager: DatabaseManager = None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.nfo_importer = NFOImporter(db_manager)
        self.init_ui()

    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("NFO文件导入")
        self.setGeometry(200, 200, 600, 400)

        layout = QVBoxLayout()

        # 说明
        info_label = QLabel("导入视频文件夹中的NFO文件信息到数据库")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # 操作模式
        mode_group = QGroupBox("操作模式")
        mode_layout = QVBoxLayout()

        self.current_video_radio = QRadioButton("仅处理当前选中的视频")
        self.current_video_radio.setChecked(True)

        self.all_missing_radio = QRadioButton("处理所有缺少信息的视频")
        self.all_missing_radio.setChecked(False)

        self.folder_scan_radio = QRadioButton("扫描文件夹并导入NFO")
        self.folder_scan_radio.setChecked(False)

        mode_layout.addWidget(self.current_video_radio)
        mode_layout.addWidget(self.all_missing_radio)
        mode_layout.addWidget(self.folder_scan_radio)
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        # 文件夹选择（仅在扫描文件夹模式时显示）
        self.folder_frame = QFrame()
        folder_layout = QHBoxLayout()
        self.folder_edit = QLineEdit()
        self.folder_browse_btn = QPushButton("浏览...")
        self.folder_browse_btn.clicked.connect(self.browse_folder)
        folder_layout.addWidget(QLabel("目标文件夹:"))
        folder_layout.addWidget(self.folder_edit)
        folder_layout.addWidget(self.folder_browse_btn)
        self.folder_frame.setLayout(folder_layout)
        self.folder_frame.setVisible(False)
        layout.addWidget(self.folder_frame)

        # 进度条
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        # 状态标签
        self.status_label = QLabel("准备就绪")
        layout.addWidget(self.status_label)

        # 日志
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(100)
        layout.addWidget(self.log_text)

        # 按钮
        button_layout = QHBoxLayout()
        self.import_btn = QPushButton("开始导入")
        self.import_btn.clicked.connect(self.start_import)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.import_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)

        self.setLayout(layout)

        # 连接信号
        self.current_video_radio.toggled.connect(self.on_mode_changed)
        self.all_missing_radio.toggled.connect(self.on_mode_changed)
        self.folder_scan_radio.toggled.connect(self.on_mode_changed)

    def on_mode_changed(self):
        """模式改变时更新界面"""
        self.folder_frame.setVisible(self.folder_scan_radio.isChecked())

    def browse_folder(self):
        """浏览文件夹"""
        folder = QFileDialog.getExistingDirectory(self, "选择包含视频的文件夹")
        if folder:
            self.folder_edit.setText(folder)

    def log_message(self, message: str):
        """添加日志消息"""
        self.log_text.append(message)
        self.status_label.setText(message)

    def start_import(self):
        """开始导入"""
        # TODO: 实现NFO导入逻辑
        self.log_message("NFO导入功能正在开发中...")
        self.accept()

class DuplicateManagerDialog(QDialog):
    """重复文件管理对话框"""
    def __init__(self, parent=None, db_manager: DatabaseManager = None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.duplicate_manager = DuplicateManager(db_manager)
        self.worker_thread = None
        self.init_ui()

    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("重复文件管理")
        self.setGeometry(100, 100, 900, 600)

        layout = QVBoxLayout()

        # 工具栏
        toolbar_layout = QHBoxLayout()
        self.scan_btn = QPushButton("扫描重复文件")
        self.scan_btn.clicked.connect(self.scan_duplicates)
        self.remove_btn = QPushButton("删除重复项")
        self.remove_btn.clicked.connect(self.remove_duplicates)
        self.remove_btn.setEnabled(False)
        toolbar_layout.addWidget(self.scan_btn)
        toolbar_layout.addWidget(self.remove_btn)
        toolbar_layout.addStretch()
        layout.addLayout(toolbar_layout)

        # 删除策略
        strategy_group = QGroupBox("删除策略")
        strategy_layout = QHBoxLayout()
        self.strategy_combo = QComboBox()
        self.strategy_combo.addItems([
            "保留最大的文件",
            "保留最新的文件",
            "保留路径最短的文件",
            "保留第一个文件"
        ])
        strategy_layout.addWidget(QLabel("策略:"))
        strategy_layout.addWidget(self.strategy_combo)
        strategy_group.setLayout(strategy_layout)
        layout.addWidget(strategy_group)

        # 分割器
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # 重复文件列表
        self.duplicate_table = QTableWidget()
        self.duplicate_table.setColumnCount(4)
        self.duplicate_table.setHorizontalHeaderLabels(["哈希值", "重复数量", "类型", "总大小"])
        self.duplicate_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.duplicate_table.itemSelectionChanged.connect(self.on_duplicate_selected)
        splitter.addWidget(self.duplicate_table)

        # 文件详情列表
        self.detail_table = QTableWidget()
        self.detail_table.setColumnCount(6)
        self.detail_table.setHorizontalHeaderLabels([
            "文件名", "路径", "大小", "创建时间", "星级", "操作"
        ])
        splitter.addWidget(self.detail_table)

        # 设置列宽
        self.duplicate_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.detail_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)  # 路径列自适应

        splitter.setSizes([300, 600])

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # 状态标签
        self.status_label = QLabel("准备就绪")
        layout.addWidget(self.status_label)

        self.setLayout(layout)

    def scan_duplicates(self):
        """扫描重复文件"""
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # 不确定进度
        self.scan_btn.setEnabled(False)
        self.status_label.setText("正在扫描重复文件...")

        # 启动工作线程
        self.worker_thread = DuplicateFinderThread(self.db_manager)
        self.worker_thread.finished.connect(self.on_scan_finished)
        self.worker_thread.error.connect(self.on_scan_error)
        self.worker_thread.start()

    def on_scan_finished(self, result: Dict):
        """扫描完成"""
        self.progress_bar.setVisible(False)
        self.scan_btn.setEnabled(True)

        duplicates = result.get('duplicates', [])
        self.duplicate_table.setRowCount(len(duplicates))

        for i, duplicate in enumerate(duplicates):
            hash_item = QTableWidgetItem(duplicate['hash'])
            count_item = QTableWidgetItem(str(duplicate['count']))
            type_item = QTableWidgetItem(duplicate['type'])

            # 计算总大小
            total_size = sum(v.get('file_size', 0) or 0 for v in duplicate['videos'])
            size_str = self.format_size(total_size)
            size_item = QTableWidgetItem(size_str)

            self.duplicate_table.setItem(i, 0, hash_item)
            self.duplicate_table.setItem(i, 1, count_item)
            self.duplicate_table.setItem(i, 2, type_item)
            self.duplicate_table.setItem(i, 3, size_item)

        if duplicates:
            self.remove_btn.setEnabled(True)
            self.status_label.setText(f"找到 {len(duplicates)} 组重复文件")
        else:
            self.status_label.setText("未找到重复文件")

    def on_scan_error(self, error_msg: str):
        """扫描错误"""
        self.progress_bar.setVisible(False)
        self.scan_btn.setEnabled(True)
        self.status_label.setText(f"扫描失败: {error_msg}")
        QMessageBox.critical(self, "错误", f"扫描重复文件失败:\n{error_msg}")

    def on_duplicate_selected(self):
        """重复文件组选择改变"""
        current_row = self.duplicate_table.currentRow()
        if current_row < 0:
            return

        # 获取选中的重复文件组数据
        # TODO: 从数据中获取详细信息并显示在detail_table中

    def remove_duplicates(self):
        """删除重复文件"""
        if self.duplicate_table.currentRow() < 0:
            QMessageBox.warning(self, "警告", "请先选择要删除的重复文件组")
            return

        strategy = self.strategy_combo.currentIndex()
        strategy_map = {
            0: 'largest',    # 保留最大的
            1: 'newest',     # 保留最新的
            2: 'shortest_path',  # 保留路径最短的
            3: 'first'       # 保留第一个
        }

        strategy_name = strategy_map[strategy]

        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要根据策略'{self.strategy_combo.currentText()}'删除重复文件吗？\n"
            "此操作不可撤销！",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # TODO: 实现删除逻辑
            self.status_label.setText("删除功能正在开发中...")

    def format_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        if size_bytes == 0:
            return "0 B"

        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        size = float(size_bytes)

        while size >= 1024.0 and i < len(size_names) - 1:
            size /= 1024.0
            i += 1

        return f"{size:.1f} {size_names[i]}"

class BatchOperationsDialog(QDialog):
    """批量操作对话框"""
    def __init__(self, parent=None, db_manager: DatabaseManager = None, selected_video_ids: List[int] = None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.batch_ops = BatchOperations(db_manager)
        self.selected_video_ids = selected_video_ids or []
        self.init_ui()

    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("批量操作")
        self.setGeometry(200, 200, 500, 400)

        layout = QVBoxLayout()

        # 选项卡
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # 批量更新星级标签页
        self.create_stars_tab()

        # 批量添加标签标签页
        self.create_tags_tab()

        # 批量移动文件标签页
        self.create_move_tab()

        # 批量重新计算哈希标签页
        self.create_hash_tab()

        # 按钮
        button_layout = QHBoxLayout()
        self.execute_btn = QPushButton("执行操作")
        self.execute_btn.clicked.connect(self.execute_operation)
        self.cancel_btn = QPushButton("关闭")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.execute_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def create_stars_tab(self):
        """创建星级更新标签页"""
        widget = QWidget()
        layout = QVBoxLayout()

        # 选择视频数量
        video_count = len(self.selected_video_ids)
        info_label = QLabel(f"选中的视频数量: {video_count}")
        layout.addWidget(info_label)

        # 星级选择
        stars_layout = QHBoxLayout()
        stars_layout.addWidget(QLabel("设置星级:"))
        self.stars_spinbox = QSpinBox()
        self.stars_spinbox.setRange(0, 5)
        self.stars_spinbox.setValue(3)
        stars_layout.addWidget(self.stars_spinbox)
        stars_layout.addStretch()
        layout.addLayout(stars_layout)

        widget.setLayout(layout)
        self.tab_widget.addTab(widget, "更新星级")

    def create_tags_tab(self):
        """创建标签管理标签页"""
        widget = QWidget()
        layout = QVBoxLayout()

        # 标签输入
        tags_layout = QVBoxLayout()
        tags_layout.addWidget(QLabel("要添加的标签 (用逗号分隔):"))
        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("例如: 动作,科幻,2023")
        tags_layout.addWidget(self.tags_edit)
        layout.addLayout(tags_layout)

        widget.setLayout(layout)
        self.tab_widget.addTab(widget, "添加标签")

    def create_move_tab(self):
        """创建文件移动标签页"""
        widget = QWidget()
        layout = QVBoxLayout()

        # 目标文件夹
        folder_layout = QVBoxLayout()
        folder_layout.addWidget(QLabel("目标文件夹:"))
        path_layout = QHBoxLayout()
        self.target_folder_edit = QLineEdit()
        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.clicked.connect(self.browse_target_folder)
        path_layout.addWidget(self.target_folder_edit)
        path_layout.addWidget(self.browse_btn)
        folder_layout.addLayout(path_layout)
        layout.addLayout(folder_layout)

        widget.setLayout(layout)
        self.tab_widget.addTab(widget, "移动文件")

    def create_hash_tab(self):
        """创建哈希重计算标签页"""
        widget = QWidget()
        layout = QVBoxLayout()

        # 说明
        info_label = QLabel("重新计算选中视频文件的MD5和文件哈希值")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # 范围选择
        range_layout = QVBoxLayout()
        self.selected_radio = QRadioButton("仅处理选中的视频")
        self.selected_radio.setChecked(True)
        self.all_radio = QRadioButton("处理所有视频")
        range_layout.addWidget(self.selected_radio)
        range_layout.addWidget(self.all_radio)
        layout.addLayout(range_layout)

        widget.setLayout(layout)
        self.tab_widget.addTab(widget, "重新计算哈希")

    def browse_target_folder(self):
        """浏览目标文件夹"""
        folder = QFileDialog.getExistingDirectory(self, "选择目标文件夹")
        if folder:
            self.target_folder_edit.setText(folder)

    def execute_operation(self):
        """执行批量操作"""
        current_tab = self.tab_widget.currentIndex()

        try:
            if current_tab == 0:  # 更新星级
                stars = self.stars_spinbox.value()
                if self.selected_video_ids:
                    count = self.batch_ops.batch_update_stars(self.selected_video_ids, stars)
                    QMessageBox.information(self, "完成", f"已更新 {count} 个视频的星级")
                else:
                    QMessageBox.warning(self, "警告", "没有选中的视频")

            elif current_tab == 1:  # 添加标签
                tags_text = self.tags_edit.text().strip()
                if tags_text:
                    tags = [tag.strip() for tag in tags_text.split(',') if tag.strip()]
                    if self.selected_video_ids:
                        count = self.batch_ops.batch_add_tags(self.selected_video_ids, tags)
                        QMessageBox.information(self, "完成", f"已为 {count} 个视频添加标签")
                    else:
                        QMessageBox.warning(self, "警告", "没有选中的视频")
                else:
                    QMessageBox.warning(self, "警告", "请输入要添加的标签")

            elif current_tab == 2:  # 移动文件
                target_folder = self.target_folder_edit.text().strip()
                if target_folder and self.selected_video_ids:
                    result = self.batch_ops.batch_move_files(self.selected_video_ids, target_folder)
                    QMessageBox.information(
                        self, "完成",
                        f"移动完成:\n成功: {result['moved']}\n失败: {result['failed']}"
                    )
                else:
                    QMessageBox.warning(self, "警告", "请选择目标文件夹和视频")

            elif current_tab == 3:  # 重新计算哈希
                if self.all_radio.isChecked():
                    video_ids = None
                else:
                    video_ids = self.selected_video_ids

                if video_ids or self.all_radio.isChecked():
                    # TODO: 实现进度对话框
                    result = self.batch_ops.batch_recalculate_hash(video_ids)
                    QMessageBox.information(
                        self, "完成",
                        f"哈希计算完成:\n更新: {result['updated']}\n失败: {result['failed']}"
                    )
                else:
                    QMessageBox.warning(self, "警告", "没有选中的视频")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"批量操作失败:\n{str(e)}")
            logger.error(f"批量操作失败: {e}")