# -*- coding: utf-8 -*-
"""
视频列表组件 - 虚拟滚动表格
支持 18 列配置，展示常用 9 列
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QCheckBox, QHBoxLayout,
    QLabel, QFrame
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from .star_rating import StarRating


class VideoTable(QWidget):
    """视频列表组件"""
    
    item_selected = Signal(dict)  # 选中项信号
    item_double_clicked = Signal(dict)  # 双击信号
    
    # 列定义
    COLUMNS = [
        ("check", "", 32),
        ("title", "标题", None),  # flex
        ("actors", "演员", None),
        ("stars", "星级", 90),
        ("tags", "标签", None),
        ("size", "大小", 76),
        ("status", "状态", 56),
        ("duration", "时长", 70),
        ("date", "创建时间", 100),
    ]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = []
        self._selected_row = -1
        
        self._setup_ui()
    
    def _setup_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 表格
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels([c[1] for c in self.COLUMNS])
        
        # 表格样式
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        
        # 表头样式
        self.table.horizontalHeader().setStyleSheet("""
            QHeaderView::section {
                background-color: #1a1e26;
                color: #f2f4f8;
                padding: 8px;
                border: none;
                border-bottom: 1px solid #1f232c;
                border-right: 1px solid #1f232c;
                font-weight: 600;
            }
            QHeaderView::section:last {
                border-right: none;
            }
        """)
        
        # 列宽设置
        header_view = self.table.horizontalHeader()
        for i, (key, name, width) in enumerate(self.COLUMNS):
            if width:
                self.table.setColumnWidth(i, width)
            elif key == "title":
                header_view.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                header_view.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
                self.table.setColumnWidth(i, 120)
        
        # 信号
        self.table.currentCellChanged.connect(self._on_row_changed)
        self.table.cellDoubleClicked.connect(self._on_double_click)
        
        layout.addWidget(self.table)
    
    def _create_header(self) -> QWidget:
        """创建自定义表头"""
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background-color: #1a1e26;
                border-bottom: 1px solid #1f232c;
            }
        """)
        header.setFixedHeight(34)
        
        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(0)
        
        for key, name, width in self.COLUMNS:
            label = QLabel(name)
            label.setStyleSheet("""
                color: #6b7382;
                font-size: 12px;
                padding: 0 12px;
            """)
            if width:
                label.setFixedWidth(width)
            else:
                label.setMinimumWidth(80)
            layout.addWidget(label)
        
        layout.addStretch()
        
        return header
    
    def set_data(self, data: list):
        """设置表格数据"""
        self._data = data
        self.table.setRowCount(len(data))
        
        for row, item in enumerate(data):
            self._populate_row(row, item)
    
    def _populate_row(self, row: int, item: dict):
        """填充一行数据"""
        # 复选框
        check_widget = QWidget()
        check_layout = QHBoxLayout(check_widget)
        check_layout.setContentsMargins(8, 0, 0, 0)
        check_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        checkbox = QCheckBox()
        check_layout.addWidget(checkbox)
        self.table.setCellWidget(row, 0, check_widget)
        
        # 标题
        title_item = QTableWidgetItem(item.get("title", ""))
        title_item.setForeground(QColor("#f2f4f8"))
        self.table.setItem(row, 1, title_item)
        
        # 演员
        actors_item = QTableWidgetItem(item.get("actors", ""))
        actors_item.setForeground(QColor("#aab2c0"))
        self.table.setItem(row, 2, actors_item)
        
        # 星级
        stars = item.get("stars", 0)
        star_widget = StarRating(stars, readonly=True)
        self.table.setCellWidget(row, 3, star_widget)
        
        # 标签
        tags = item.get("tags", [])
        tags_text = " ".join([f"[{t}]" for t in tags[:3]])
        tags_item = QTableWidgetItem(tags_text)
        tags_item.setForeground(QColor("#aab2c0"))
        self.table.setItem(row, 4, tags_item)
        
        # 大小
        size_item = QTableWidgetItem(item.get("size", ""))
        size_item.setForeground(QColor("#aab2c0"))
        size_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.table.setItem(row, 5, size_item)
        
        # 状态
        online = item.get("online", True)
        status_widget = self._create_status_widget(online)
        self.table.setCellWidget(row, 6, status_widget)
        
        # 时长
        duration_item = QTableWidgetItem(item.get("duration", ""))
        duration_item.setForeground(QColor("#aab2c0"))
        duration_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.table.setItem(row, 7, duration_item)
        
        # 日期
        date_item = QTableWidgetItem(item.get("date", ""))
        date_item.setForeground(QColor("#aab2c0"))
        self.table.setItem(row, 8, date_item)
        
        # 设置行高
        self.table.setRowHeight(row, 44)
    
    def _create_status_widget(self, online: bool) -> QWidget:
        """创建状态组件"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        color = "#3fb950" if online else "#8b949e"
        text = "在线" if online else "离线"
        
        dot = QLabel()
        dot.setFixedSize(7, 7)
        dot.setStyleSheet(f"""
            background-color: {color};
            border-radius: 3px;
        """)
        layout.addWidget(dot)
        
        label = QLabel(text)
        label.setStyleSheet(f"color: {color}; font-size: 12px;")
        layout.addWidget(label)
        
        layout.addStretch()
        
        return widget
    
    def _on_row_changed(self, row, col, prev_row, prev_col):
        """行选中变化"""
        if 0 <= row < len(self._data):
            self._selected_row = row
            self.item_selected.emit(self._data[row])
    
    def _on_double_click(self, row, col):
        """双击处理"""
        if 0 <= row < len(self._data):
            self.item_double_clicked.emit(self._data[row])
    
    def get_selected_item(self) -> dict:
        """获取选中项"""
        if 0 <= self._selected_row < len(self._data):
            return self._data[self._selected_row]
        return None

    def get_selected_items(self) -> list:
        """获取所有选中项（支持多选）"""
        selected_rows = set()
        for item in self.table.selectedItems():
            selected_rows.add(item.row())
        
        return [self._data[row] for row in sorted(selected_rows) if 0 <= row < len(self._data)]
