# -*- coding: utf-8 -*-
"""
标签管理对话框
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QFrame, QTreeWidget,
    QTreeWidgetItem, QWidget
)
from PySide6.QtCore import Qt

from ..core import Database, TagRepository
from ..theme import get_main_qss


class TagDialog(QDialog):
    """标签管理对话框"""

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.setWindowTitle("标签管理")
        self.setMinimumSize(900, 600)
        self.setStyleSheet(get_main_qss())

        self.db = db
        self.repo = TagRepository(db)

        self._setup_ui()
        self._load_tags()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标题栏
        header = QFrame()
        header.setStyleSheet("background-color: #1a1e26; padding: 16px;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("标签管理")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        btn_import = QPushButton("导入")
        header_layout.addWidget(btn_import)

        btn_export = QPushButton("导出")
        header_layout.addWidget(btn_export)

        btn_new = QPushButton("+ 新建标签")
        btn_new.setProperty("primary", "true")
        header_layout.addWidget(btn_new)

        layout.addWidget(header)

        # 内容区
        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # 左侧分类树
        self.tree = QTreeWidget()
        self.tree.setFixedWidth(240)
        self.tree.setHeaderHidden(True)
        self.tree.setStyleSheet("""
            QTreeWidget {
                background-color: #14171d;
                border: none;
                border-right: 1px solid #1f232c;
            }
            QTreeWidget::item {
                padding: 8px 12px;
                color: #aab2c0;
            }
            QTreeWidget::item:hover {
                background-color: #1f232c;
                color: #f2f4f8;
            }
            QTreeWidget::item:selected {
                background-color: #2a2210;
                color: #f0b429;
            }
        """)
        self.tree.currentItemChanged.connect(self._on_category_selected)

        # 添加分类
        root = QTreeWidgetItem(self.tree, ["全部标签"])
        root.setData(0, Qt.ItemDataRole.UserRole, "all")

        common = QTreeWidgetItem(root, ["常用标签"])
        common.setData(0, Qt.ItemDataRole.UserRole, "common")

        uncategorized = QTreeWidgetItem(root, ["未分类"])
        uncategorized.setData(0, Qt.ItemDataRole.UserRole, "uncategorized")

        self.tree.expandAll()

        content_layout.addWidget(self.tree)

        # 右侧标签列表
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(12)

        # 工具栏
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索标签…")
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #0a0c0f;
                border: 1px solid #1f232c;
                border-radius: 8px;
                padding: 0 12px;
                min-height: 32px;
                color: #f2f4f8;
                min-width: 200px;
            }
        """)
        self.search_input.textChanged.connect(self._filter_tags)
        toolbar_layout.addWidget(self.search_input)

        toolbar_layout.addStretch()

        self.count_label = QLabel("已选 0 个")
        self.count_label.setStyleSheet("color: #6b7382;")
        toolbar_layout.addWidget(self.count_label)

        btn_merge = QPushButton("批量合并")
        toolbar_layout.addWidget(btn_merge)

        btn_delete = QPushButton("批量删除")
        toolbar_layout.addWidget(btn_delete)

        right_layout.addWidget(toolbar)

        # 标签表格
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["标签名称", "分类", "使用次数", "创建时间", "操作"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setColumnWidth(0, 200)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 100)
        self.table.setColumnWidth(3, 120)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._update_count)

        right_layout.addWidget(self.table)

        content_layout.addWidget(right, 1)

        layout.addWidget(content, 1)

    def _load_tags(self):
        tag_stats = self.repo.get_video_tag_stats()
        self._all_tags = tag_stats

        self.table.setRowCount(len(tag_stats))

        for row, (tag_name, count) in enumerate(tag_stats):
            # 标签名称
            name_item = QTableWidgetItem(tag_name)
            self.table.setItem(row, 0, name_item)

            # 分类
            category = self._guess_category(tag_name)
            cat_item = QTableWidgetItem(category)
            cat_item.setForeground(Qt.GlobalColor.darkGray)
            self.table.setItem(row, 1, cat_item)

            # 使用次数
            count_item = QTableWidgetItem(str(count))
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 2, count_item)

            # 创建时间
            date_item = QTableWidgetItem("—")
            date_item.setForeground(Qt.GlobalColor.darkGray)
            self.table.setItem(row, 3, date_item)

            # 操作
            op_widget = QWidget()
            op_layout = QHBoxLayout(op_widget)
            op_layout.setContentsMargins(4, 0, 4, 0)
            op_layout.setSpacing(4)

            btn_edit = QPushButton("编辑")
            btn_edit.setFixedSize(50, 24)
            btn_edit.setStyleSheet("font-size: 11px; padding: 0;")
            op_layout.addWidget(btn_edit)

            btn_rename = QPushButton("重命名")
            btn_rename.setFixedSize(60, 24)
            btn_rename.setStyleSheet("font-size: 11px; padding: 0;")
            op_layout.addWidget(btn_rename)

            btn_del = QPushButton("删除")
            btn_del.setFixedSize(50, 24)
            btn_del.setStyleSheet("font-size: 11px; padding: 0; color: #f47067;")
            op_layout.addWidget(btn_del)

            self.table.setCellWidget(row, 4, op_widget)

    def _guess_category(self, tag_name: str) -> str:
        """猜测标签分类"""
        if tag_name in ["高清", "4K", "VR"]:
            return "画质"
        elif tag_name in ["中文字幕"]:
            return "字幕"
        elif tag_name in ["收藏", "流出"]:
            return "常用标签"
        elif tag_name in ["单体作品", "合集"]:
            return "系列"
        else:
            return "内容"

    def _on_category_selected(self, current, previous):
        if current:
            category = current.data(0, Qt.ItemDataRole.UserRole)
            self._filter_by_category(category)

    def _filter_by_category(self, category: str):
        if category == "all":
            self._load_tags()
        else:
            filtered = [(name, count) for name, count in self._all_tags if self._guess_category(name) == category]
            self._display_tags(filtered)

    def _filter_tags(self, text: str):
        if not text:
            self._load_tags()
        else:
            filtered = [(name, count) for name, count in self._all_tags if text.lower() in name.lower()]
            self._display_tags(filtered)

    def _display_tags(self, tags: list):
        self.table.setRowCount(len(tags))
        for row, (tag_name, count) in enumerate(tags):
            name_item = QTableWidgetItem(tag_name)
            self.table.setItem(row, 0, name_item)

            category = self._guess_category(tag_name)
            cat_item = QTableWidgetItem(category)
            cat_item.setForeground(Qt.GlobalColor.darkGray)
            self.table.setItem(row, 1, cat_item)

            count_item = QTableWidgetItem(str(count))
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 2, count_item)

            date_item = QTableWidgetItem("—")
            date_item.setForeground(Qt.GlobalColor.darkGray)
            self.table.setItem(row, 3, date_item)

    def _update_count(self):
        selected = len(self.table.selectedItems()) // self.table.columnCount()
        self.count_label.setText(f"已选 {selected} 个")
