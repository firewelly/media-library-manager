# -*- coding: utf-8 -*-
"""
右侧详情面板
显示选中视频的详细信息
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QFrame, QLineEdit, QTextEdit,
    QGridLayout, QSizePolicy
)
from PySide6.QtCore import Qt, Signal

from .star_rating import StarRating


class DetailPanel(QWidget):
    """右侧详情面板"""
    
    # 信号
    save_clicked = Signal(dict)
    set_star_clicked = Signal(int)
    add_tag_clicked = Signal()
    fetch_javdb_clicked = Signal()
    generate_thumbnail_clicked = Signal()
    delete_clicked = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("detailPanel")
        self.setFixedWidth(360)
        
        self._data = None
        self._setup_ui()
    
    def _setup_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        
        # 封面区
        self.cover = QLabel()
        self.cover.setObjectName("detailCover")
        self.cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover.setText("封面")
        self.cover.setStyleSheet("""
            background-color: #1e2229;
            color: #6b7382;
            font-size: 24px;
            min-height: 270px;
        """)
        self.content_layout.addWidget(self.cover)
        
        # 分辨率徽章
        self.res_badge = QLabel("1920×1080")
        self.res_badge.setStyleSheet("""
            background-color: rgba(0, 0, 0, 0.72);
            color: white;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-family: monospace;
        """)
        self.content_layout.addWidget(self.res_badge)
        
        # 内容区
        body = QWidget()
        body.setObjectName("detailBody")
        body.setStyleSheet("padding: 16px;")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(16, 16, 16, 16)
        body_layout.setSpacing(8)
        
        # 标题
        self.title = QLabel("选择视频查看详情")
        self.title.setObjectName("detailTitle")
        self.title.setWordWrap(True)
        body_layout.addWidget(self.title)
        
        # 副标题
        self.subtitle = QLabel("")
        self.subtitle.setObjectName("detailSubtitle")
        body_layout.addWidget(self.subtitle)
        
        # 评分行
        rating_row = QWidget()
        rating_layout = QHBoxLayout(rating_row)
        rating_layout.setContentsMargins(0, 0, 0, 0)
        rating_layout.setSpacing(12)
        
        self.stars = StarRating(0, readonly=False)
        self.stars.rating_changed.connect(self._on_star_changed)
        rating_layout.addWidget(self.stars)
        
        self.javdb_score = QLabel("")
        self.javdb_score.setStyleSheet("color: #d29922; font-size: 12px;")
        rating_layout.addWidget(self.javdb_score)
        
        rating_layout.addStretch()
        body_layout.addWidget(rating_row)
        
        # 描述编辑框
        desc_label = QLabel("描述:")
        desc_label.setStyleSheet("color: #6b7382; font-size: 12px;")
        body_layout.addWidget(desc_label)
        
        self.desc_edit = QTextEdit()
        self.desc_edit.setMaximumHeight(80)
        self.desc_edit.setStyleSheet("""
            QTextEdit {
                background-color: #0a0c0f;
                border: 1px solid #1f232c;
                border-radius: 4px;
                padding: 4px;
                color: #f2f4f8;
                font-size: 12px;
            }
        """)
        body_layout.addWidget(self.desc_edit)
        
        # 标签编辑框
        tags_label = QLabel("标签:")
        tags_label.setStyleSheet("color: #6b7382; font-size: 12px;")
        body_layout.addWidget(tags_label)
        
        self.tags_edit = QLineEdit()
        self.tags_edit.setStyleSheet("""
            QLineEdit {
                background-color: #0a0c0f;
                border: 1px solid #1f232c;
                border-radius: 4px;
                padding: 4px;
                color: #f2f4f8;
                font-size: 12px;
            }
        """)
        body_layout.addWidget(self.tags_edit)
        
        # 信息行
        self.info_rows = {}
        for key, label in [
            ("actors", "演员"),
            ("filename", "文件名"),
            ("size", "大小"),
            ("duration", "时长"),
            ("resolution", "分辨率"),
            ("device", "设备"),
            ("date", "创建时间"),
            ("modified", "修改时间"),
            ("javdb_title", "JAVDB标题"),
            ("release_date", "发行日期"),
            ("path", "路径"),
        ]:
            row = self._create_kv_row(label, "")
            body_layout.addWidget(row)
            self.info_rows[key] = row.findChild(QLabel, "value")
        
        # 标签显示区
        body_layout.addSpacing(16)
        tags_title = QLabel("标签列表")
        tags_title.setStyleSheet("color: #6b7382; font-size: 12px;")
        body_layout.addWidget(tags_title)
        
        self.tags_container = QWidget()
        self.tags_layout = QHBoxLayout(self.tags_container)
        self.tags_layout.setContentsMargins(0, 0, 0, 0)
        self.tags_layout.setSpacing(4)
        body_layout.addWidget(self.tags_container)
        
        # 操作按钮
        body_layout.addSpacing(16)
        
        # 主要操作按钮
        self.btn_play = QPushButton("▶ 播放视频")
        self.btn_play.setProperty("primary", "true")
        body_layout.addWidget(self.btn_play)
        
        self.btn_save = QPushButton("💾 保存修改")
        self.btn_save.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
        self.btn_save.clicked.connect(self._on_save_clicked)
        body_layout.addWidget(self.btn_save)
        
        # 星级和标签操作
        btn_row1 = QHBoxLayout()
        self.btn_set_star = QPushButton("设置星级")
        self.btn_set_star.clicked.connect(self._on_set_star_clicked)
        btn_row1.addWidget(self.btn_set_star)
        
        self.btn_add_tag = QPushButton("添加标签")
        self.btn_add_tag.clicked.connect(self._on_add_tag_clicked)
        btn_row1.addWidget(self.btn_add_tag)
        body_layout.addLayout(btn_row1)
        
        # 信息获取操作
        self.btn_fetch_javdb = QPushButton("获取 JAVDB 信息")
        self.btn_fetch_javdb.setStyleSheet("background-color: #FF9800; color: white;")
        self.btn_fetch_javdb.clicked.connect(self._on_fetch_javdb_clicked)
        body_layout.addWidget(self.btn_fetch_javdb)
        
        self.btn_generate_thumbnail = QPushButton("生成封面")
        self.btn_generate_thumbnail.clicked.connect(self._on_generate_thumbnail_clicked)
        body_layout.addWidget(self.btn_generate_thumbnail)
        
        # 危险操作
        self.btn_delete = QPushButton("删除视频")
        self.btn_delete.setStyleSheet("background-color: #F44336; color: white;")
        self.btn_delete.clicked.connect(self._on_delete_clicked)
        body_layout.addWidget(self.btn_delete)
        
        body_layout.addStretch()
        
        self.content_layout.addWidget(body)
        
        scroll.setWidget(content)
        layout.addWidget(scroll)
    
    def _create_kv_row(self, key: str, value: str) -> QWidget:
        """创建键值对行"""
        row = QWidget()
        row.setProperty("class", "kvRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        k = QLabel(key)
        k.setProperty("class", "key")
        k.setFixedWidth(76)
        k.setStyleSheet("color: #6b7382; font-size: 12px;")
        layout.addWidget(k)
        
        v = QLabel(value)
        v.setObjectName("value")
        v.setProperty("class", "value")
        v.setStyleSheet("color: #f2f4f8; font-size: 12px;")
        v.setWordWrap(True)
        layout.addWidget(v)
        
        layout.addStretch()
        
        return row
    
    def set_data(self, data: dict):
        """设置详情数据"""
        self._data = data
        
        self.title.setText(data.get("title", ""))
        self.subtitle.setText(f"{data.get('code', '')} · {data.get('release_date', '')}")
        
        self.stars.set_rating(data.get("stars", 0))
        
        score = data.get("javdb_score")
        if score:
            self.javdb_score.setText(f"JAVDB {score}")
        else:
            self.javdb_score.setText("")
        
        # 更新描述
        self.desc_edit.setPlainText(data.get("description", ""))
        
        # 更新标签编辑框
        tags = data.get("tags", [])
        if isinstance(tags, list):
            self.tags_edit.setText(", ".join(tags))
        else:
            self.tags_edit.setText(str(tags))
        
        # 更新信息行
        self.info_rows["actors"].setText(data.get("actors", ""))
        self.info_rows["filename"].setText(data.get("filename", data.get("file_name", "")))
        self.info_rows["size"].setText(data.get("size", ""))
        self.info_rows["duration"].setText(data.get("duration", ""))
        self.info_rows["resolution"].setText(data.get("resolution", ""))
        self.info_rows["device"].setText(data.get("device", ""))
        self.info_rows["date"].setText(data.get("date", ""))
        self.info_rows["modified"].setText(data.get("modified", data.get("updated_at", "")))
        self.info_rows["javdb_title"].setText(data.get("javdb_title", ""))
        self.info_rows["release_date"].setText(data.get("release_date", ""))
        self.info_rows["path"].setText(data.get("path", ""))
        
        # 更新标签显示
        self._update_tags(tags if isinstance(tags, list) else [])
    
    def _update_tags(self, tags: list):
        """更新标签显示"""
        # 清空现有标签
        while self.tags_layout.count():
            item = self.tags_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 添加新标签
        for tag in tags:
            label = QLabel(tag)
            label.setProperty("class", "tag")
            label.setStyleSheet("""
                background-color: #2a2f3a;
                border-radius: 999px;
                padding: 1px 7px;
                font-size: 11px;
                color: #aab2c0;
            """)
            self.tags_layout.addWidget(label)
        
        self.tags_layout.addStretch()
    
    def clear(self):
        """清空详情"""
        self.title.setText("选择视频查看详情")
        self.subtitle.setText("")
        self.stars.set_rating(0)
        self.javdb_score.setText("")
        self.desc_edit.clear()
        self.tags_edit.clear()
        for row in self.info_rows.values():
            row.setText("")
        self._update_tags([])
    
    def _on_star_changed(self, rating: int):
        """星级变化"""
        self.set_star_clicked.emit(rating)
    
    def _on_save_clicked(self):
        """保存按钮点击"""
        if self._data:
            self._data["description"] = self.desc_edit.toPlainText()
            self._data["tags"] = self.tags_edit.text()
            self.save_clicked.emit(self._data)
    
    def _on_set_star_clicked(self):
        """设置星级按钮点击"""
        self.set_star_clicked.emit(self.stars.get_rating())
    
    def _on_add_tag_clicked(self):
        """添加标签按钮点击"""
        self.add_tag_clicked.emit()
    
    def _on_fetch_javdb_clicked(self):
        """获取 JAVDB 信息按钮点击"""
        self.fetch_javdb_clicked.emit()
    
    def _on_generate_thumbnail_clicked(self):
        """生成封面按钮点击"""
        self.generate_thumbnail_clicked.emit()
    
    def _on_delete_clicked(self):
        """删除按钮点击"""
        self.delete_clicked.emit()
