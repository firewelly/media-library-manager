# -*- coding: utf-8 -*-
"""
左侧导航组件
包含：媒体库分类、存储位置、管理入口
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QScrollArea, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, Signal


class NavItem(QFrame):
    """导航项组件"""
    
    clicked = Signal(str)
    
    def __init__(self, icon: str, text: str, count: int = None, parent=None):
        super().__init__(parent)
        self.setProperty("class", "navItem")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # 图标
        self.icon_label = QLabel(icon)
        self.icon_label.setFixedWidth(18)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.icon_label)
        
        # 文字
        self.text_label = QLabel(text)
        layout.addWidget(self.text_label)
        
        layout.addStretch()
        
        # 计数
        if count is not None:
            self.count_label = QLabel(str(count))
            self.count_label.setProperty("class", "count")
            layout.addWidget(self.count_label)
        
        self._active = False
    
    def set_active(self, active: bool):
        """设置激活状态"""
        self._active = active
        self.setProperty("active", "true" if active else "false")
        self.style().unpolish(self)
        self.style().polish(self)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.text_label.text())
        super().mousePressEvent(event)


class Sidebar(QWidget):
    """左侧导航栏"""
    
    nav_selected = Signal(str)  # 导航项选中信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(220)
        
        self._items = []
        self._setup_ui()
    
    def _setup_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 品牌区
        brand = self._create_brand()
        layout.addWidget(brand)
        
        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        scroll_content = QWidget()
        self.nav_layout = QVBoxLayout(scroll_content)
        self.nav_layout.setContentsMargins(0, 8, 0, 8)
        self.nav_layout.setSpacing(0)
        
        # 媒体库分类
        self._add_section("媒体库")
        self.all_videos = self._add_nav_item("▦", "全部视频", 48888)
        self.favorites = self._add_nav_item("★", "收藏", 312)
        self.recent = self._add_nav_item("◷", "最近添加", 86)
        self.no_tags = self._add_nav_item("⌀", "无标签", 9204)
        
        # 存储位置
        self._add_section("存储位置")
        self.local_disk = self._add_nav_item("▣", "本地磁盘", 21430)
        self.nas_app = self._add_nav_item("☁", "NAS · app", 16885)
        self.nas_video = self._add_nav_item("☁", "NAS · Video", 10573)
        
        # 管理
        self._add_section("管理")
        self.actors = self._add_nav_item("◉", "演员库")
        self.tags = self._add_nav_item("#", "标签管理")
        self.folders = self._add_nav_item("▸", "文件夹管理")
        self.settings = self._add_nav_item("⚙", "设置")
        
        self.nav_layout.addStretch()
        
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        # 存储状态区
        storage = self._create_storage_status()
        layout.addWidget(storage)
        
        # 默认选中"全部视频"
        self.all_videos.set_active(True)
    
    def _create_brand(self) -> QWidget:
        """创建品牌区"""
        brand = QWidget()
        brand.setObjectName("sidebarBrand")
        layout = QHBoxLayout(brand)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)
        
        logo = QLabel("M")
        logo.setObjectName("sidebarBrandLogo")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo)
        
        title = QLabel("媒体库")
        title.setStyleSheet(f"font-size: 16px; font-weight: 700;")
        layout.addWidget(title)
        
        layout.addStretch()
        
        return brand
    
    def _create_storage_status(self) -> QWidget:
        """创建存储状态区"""
        storage = QFrame()
        storage.setFrameShape(QFrame.Shape.StyledPanel)
        storage.setStyleSheet(f"""
            QFrame {{
                background-color: {self._get_sidebar_bg()};
                border-top: 1px solid #1f232c;
                padding: 12px;
            }}
        """)
        
        layout = QVBoxLayout(storage)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(4)
        
        # 本地磁盘
        local = self._create_status_line("本地磁盘", True)
        layout.addWidget(local)
        
        # NAS app
        nas_app = self._create_status_line("NAS /Volumes/app", True)
        layout.addWidget(nas_app)
        
        # NAS Video
        nas_video = self._create_status_line("NAS /Volumes/Video", False)
        layout.addWidget(nas_video)
        
        return storage
    
    def _create_status_line(self, text: str, online: bool) -> QWidget:
        """创建状态行"""
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        dot = QLabel()
        dot.setFixedSize(8, 8)
        color = "#3fb950" if online else "#8b949e"
        dot.setStyleSheet(f"""
            background-color: {color};
            border-radius: 4px;
        """)
        layout.addWidget(dot)
        
        label = QLabel(text)
        label.setStyleSheet(f"""
            font-size: 12px;
            color: #aab2c0;
        """)
        layout.addWidget(label)
        
        layout.addStretch()
        
        return row
    
    def _add_section(self, title: str):
        """添加分区标题"""
        label = QLabel(title)
        label.setProperty("class", "navSection")
        self.nav_layout.addWidget(label)
    
    def _add_nav_item(self, icon: str, text: str, count: int = None) -> NavItem:
        """添加导航项"""
        item = NavItem(icon, text, count)
        item.clicked.connect(self._on_item_clicked)
        self.nav_layout.addWidget(item)
        self._items.append(item)
        return item
    
    def _on_item_clicked(self, text: str):
        """导航项点击处理"""
        # 取消所有激活状态
        for item in self._items:
            item.set_active(False)
        
        # 激活当前项
        for item in self._items:
            if item.text_label.text() == text:
                item.set_active(True)
                break
        
        self.nav_selected.emit(text)
    
    def _get_sidebar_bg(self) -> str:
        """获取侧栏背景色"""
        return "#14171d"
