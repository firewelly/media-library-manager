# -*- coding: utf-8 -*-
"""
星级评分组件
"""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide6.QtCore import Qt, Signal


class StarRating(QWidget):
    """星级评分组件"""
    
    rating_changed = Signal(int)
    
    def __init__(self, rating: int = 0, readonly: bool = False, parent=None):
        super().__init__(parent)
        self._rating = rating
        self._readonly = readonly
        self._stars = []
        
        self._setup_ui()
        self._update_stars()
    
    def _setup_ui(self):
        """初始化 UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        for i in range(5):
            star = QLabel("★")
            star.setStyleSheet(f"font-size: 14px;")
            if not self._readonly:
                star.setCursor(Qt.CursorShape.PointingHandCursor)
                star.mousePressEvent = lambda e, idx=i: self._on_star_clicked(idx)
            layout.addWidget(star)
            self._stars.append(star)
        
        layout.addStretch()
    
    def _update_stars(self):
        """更新星星显示"""
        for i, star in enumerate(self._stars):
            if i < self._rating:
                star.setStyleSheet(f"font-size: 14px; color: #f0b429;")
            else:
                star.setStyleSheet(f"font-size: 14px; color: #2d3340;")
    
    def _on_star_clicked(self, index: int):
        """星星点击处理"""
        if self._readonly:
            return
        self._rating = index + 1
        self._update_stars()
        self.rating_changed.emit(self._rating)
    
    def get_rating(self) -> int:
        """获取当前评分"""
        return self._rating
    
    def set_rating(self, rating: int):
        """设置评分"""
        self._rating = max(0, min(5, rating))
        self._update_stars()
