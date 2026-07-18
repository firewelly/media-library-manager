# -*- coding: utf-8 -*-
"""
筛选条组件
显示已选筛选条件，支持单独移除
"""

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QScrollArea, QFrame
)
from PySide6.QtCore import Qt, Signal


class FilterChip(QWidget):
    """筛选条件标签"""
    
    removed = Signal(str)
    
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self._text = text
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 6, 0)
        layout.setSpacing(6)
        
        self.setStyleSheet("""
            FilterChip {
                background-color: #2a2210;
                border-radius: 999px;
                min-height: 24px;
            }
        """)
        
        label = QLabel(text)
        label.setStyleSheet("color: #f0b429; font-size: 12px; background: transparent;")
        layout.addWidget(label)
        
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(16, 16)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: #f0b429;
                font-size: 10px;
                border-radius: 8px;
                padding: 0;
            }
            QPushButton:hover {
                background-color: rgba(0, 0, 0, 0.15);
            }
        """)
        close_btn.clicked.connect(lambda: self.removed.emit(self._text))
        layout.addWidget(close_btn)
    
    def get_text(self) -> str:
        return self._text


class FilterBar(QWidget):
    """筛选条"""
    
    filter_changed = Signal(list)  # 筛选条件变化信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("filterbar")
        self.setFixedHeight(40)
        
        self._filters = []
        self._chips = []
        
        self._setup_ui()
    
    def _setup_ui(self):
        """初始化 UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(8)
        
        # 标签
        self.label = QLabel("筛选：")
        self.label.setStyleSheet("color: #6b7382; font-size: 12px;")
        layout.addWidget(self.label)
        
        # 筛选条件容器（可滚动）
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet("background: transparent;")
        
        self.chips_container = QWidget()
        self.chips_container.setStyleSheet("background: transparent;")
        self.chips_layout = QHBoxLayout(self.chips_container)
        self.chips_layout.setContentsMargins(0, 0, 0, 0)
        self.chips_layout.setSpacing(8)
        
        scroll.setWidget(self.chips_container)
        layout.addWidget(scroll)
        
        # 清空按钮
        self.clear_btn = QPushButton("清空全部")
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px dashed #2d3340;
                border-radius: 999px;
                color: #6b7382;
                font-size: 12px;
                padding: 0 12px;
                min-height: 24px;
            }
            QPushButton:hover {
                color: #f47067;
                border-color: #f47067;
            }
        """)
        self.clear_btn.clicked.connect(self.clear_all)
        layout.addWidget(self.clear_btn)
        
        # 匹配数
        self.match_label = QLabel("")
        self.match_label.setStyleSheet("color: #6b7382; font-size: 12px;")
        layout.addWidget(self.match_label)
    
    def add_filter(self, text: str):
        """添加筛选条件"""
        if text in self._filters:
            return
        
        self._filters.append(text)
        
        chip = FilterChip(text)
        chip.removed.connect(self._on_chip_removed)
        self.chips_layout.addWidget(chip)
        self._chips.append(chip)
        
        self._update_visibility()
        self.filter_changed.emit(self._filters.copy())
    
    def _on_chip_removed(self, text: str):
        """移除筛选条件"""
        if text in self._filters:
            self._filters.remove(text)
        
        for chip in self._chips:
            if chip.get_text() == text:
                self.chips_layout.removeWidget(chip)
                chip.deleteLater()
                self._chips.remove(chip)
                break
        
        self._update_visibility()
        self.filter_changed.emit(self._filters.copy())
    
    def clear_all(self):
        """清空所有筛选条件"""
        self._filters.clear()
        
        for chip in self._chips:
            self.chips_layout.removeWidget(chip)
            chip.deleteLater()
        self._chips.clear()
        
        self._update_visibility()
        self.filter_changed.emit(self._filters.copy())
    
    def set_match_count(self, count: int, time_ms: int = None):
        """设置匹配数量"""
        if time_ms is not None:
            self.match_label.setText(f"匹配 {count:,} 条 · 耗时 {time_ms}ms")
        else:
            self.match_label.setText(f"匹配 {count:,} 条")
    
    def _update_visibility(self):
        """更新组件可见性"""
        has_filters = len(self._filters) > 0
        self.label.setVisible(has_filters)
        self.clear_btn.setVisible(has_filters)
