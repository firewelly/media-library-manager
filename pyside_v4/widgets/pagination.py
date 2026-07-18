# -*- coding: utf-8 -*-
"""
分页组件
"""

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QLabel, QComboBox
)
from PySide6.QtCore import Qt, Signal


class Pagination(QWidget):
    """分页组件"""
    
    page_changed = Signal(int, int)  # page, page_size
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_page = 1
        self._page_size = 200
        self._total_count = 0
        self._total_pages = 1
        
        self._setup_ui()
    
    def _setup_ui(self):
        """初始化 UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(8)
        
        # 每页显示数量
        layout.addWidget(QLabel("每页显示:"))
        
        self.page_size_combo = QComboBox()
        self.page_size_combo.addItems(["100", "200", "500", "1000"])
        self.page_size_combo.setCurrentText("200")
        self.page_size_combo.currentTextChanged.connect(self._on_page_size_changed)
        self.page_size_combo.setFixedWidth(80)
        layout.addWidget(self.page_size_combo)
        
        layout.addStretch()
        
        # 分页按钮
        self.first_btn = QPushButton("首页")
        self.first_btn.clicked.connect(lambda: self._go_to_page(1))
        layout.addWidget(self.first_btn)
        
        self.prev_btn = QPushButton("上一页")
        self.prev_btn.clicked.connect(lambda: self._go_to_page(self._current_page - 1))
        layout.addWidget(self.prev_btn)
        
        # 页码显示
        self.page_label = QLabel("第 1 页 / 共 1 页")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_label.setMinimumWidth(120)
        layout.addWidget(self.page_label)
        
        self.next_btn = QPushButton("下一页")
        self.next_btn.clicked.connect(lambda: self._go_to_page(self._current_page + 1))
        layout.addWidget(self.next_btn)
        
        self.last_btn = QPushButton("末页")
        self.last_btn.clicked.connect(lambda: self._go_to_page(self._total_pages))
        layout.addWidget(self.last_btn)
        
        layout.addStretch()
        
        # 总数显示
        self.total_label = QLabel("共 0 条")
        layout.addWidget(self.total_label)
        
        self._update_buttons()
    
    def set_total(self, total: int):
        """设置总数"""
        self._total_count = total
        self._total_pages = max(1, (total + self._page_size - 1) // self._page_size)
        
        if self._current_page > self._total_pages:
            self._current_page = self._total_pages
        
        self._update_display()
    
    def _on_page_size_changed(self, text: str):
        """每页显示数量变化"""
        self._page_size = int(text)
        self._current_page = 1
        self.set_total(self._total_count)
        self.page_changed.emit(self._current_page, self._page_size)
    
    def _go_to_page(self, page: int):
        """跳转到指定页"""
        if 1 <= page <= self._total_pages:
            self._current_page = page
            self._update_display()
            self.page_changed.emit(self._current_page, self._page_size)
    
    def _update_display(self):
        """更新显示"""
        self.page_label.setText(f"第 {self._current_page} 页 / 共 {self._total_pages} 页")
        self.total_label.setText(f"共 {self._total_count} 条")
        self._update_buttons()
    
    def _update_buttons(self):
        """更新按钮状态"""
        self.first_btn.setEnabled(self._current_page > 1)
        self.prev_btn.setEnabled(self._current_page > 1)
        self.next_btn.setEnabled(self._current_page < self._total_pages)
        self.last_btn.setEnabled(self._current_page < self._total_pages)
    
    def get_current_page(self) -> int:
        """获取当前页"""
        return self._current_page
    
    def get_page_size(self) -> int:
        """获取每页大小"""
        return self._page_size
