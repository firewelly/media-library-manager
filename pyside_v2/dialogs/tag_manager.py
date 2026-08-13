# -*- coding: utf-8 -*-
"""
标签管理对话框（对齐 v1 TagManagerWindow，ui_design 风格）。

功能：搜索 / 列表 / 添加 / 删除 / 编辑 / 刷新。
标签来自 tags 表（tag_name, tag_color）+ javdb_tags。
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QLineEdit, QGroupBox, QMessageBox, QInputDialog,
)
from PySide6.QtCore import Qt

from pyside_v2.theme import Tokens, color_hex


class TagManagerDialog(QDialog):
    """标签管理对话框。"""

    def __init__(self, main_window, parent=None):
        super().__init__(parent or main_window)
        self.mw = main_window
        self.core = main_window.core
        self.setWindowTitle("标签管理")
        self.resize(480, 460)
        self._setup_ui()
        self.load_tags()

    def _setup_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(Tokens.SP_5, Tokens.SP_5, Tokens.SP_5, Tokens.SP_5)
        lay.setSpacing(Tokens.SP_3)

        box = QGroupBox("标签列表")
        box_lay = QVBoxLayout(box)
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索标签…")
        self.search.textChanged.connect(self._filter)
        box_lay.addWidget(self.search)

        self.list = QListWidget()
        self.list.setAlternatingRowColors(True)
        self.list.setSelectionMode(QListWidget.ExtendedSelection)
        box_lay.addWidget(self.list)

        self.count_label = QLabel("共 0 个标签")
        self.count_label.setStyleSheet("color: palette(mid);")
        box_lay.addWidget(self.count_label)
        lay.addWidget(box)

        # 按钮行
        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("＋ 添加")
        self.btn_add.setProperty("role", "primary")
        self.btn_add.setCursor(Qt.PointingHandCursor)
        self.btn_add.clicked.connect(self._add_tag)
        self.btn_edit = QPushButton("编辑")
        self.btn_edit.setCursor(Qt.PointingHandCursor)
        self.btn_edit.clicked.connect(self._edit_tag)
        self.btn_del = QPushButton("删除")
        self.btn_del.setStyleSheet(f"color: {color_hex('danger')};")
        self.btn_del.setCursor(Qt.PointingHandCursor)
        self.btn_del.clicked.connect(self._delete_tag)
        self.btn_refresh = QPushButton("⟳ 刷新")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.clicked.connect(self.load_tags)
        for b in (self.btn_add, self.btn_edit, self.btn_del, self.btn_refresh):
            btn_row.addWidget(b)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        btn_close = QPushButton("关闭")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.clicked.connect(self.accept)
        row2 = QHBoxLayout()
        row2.addStretch()
        row2.addWidget(btn_close)
        lay.addLayout(row2)

    def load_tags(self):
        """从 tags + javdb_tags 表加载。"""
        self.list.clear()
        tags = self.core.get_all_tags()
        self._all_tags = tags
        self._render(tags)

    def _render(self, tags):
        self.list.clear()
        for t in tags:
            self.list.addItem(QListWidgetItem(t))
        self.count_label.setText(f"共 {len(tags)} 个标签")

    def _filter(self, text):
        text = self.search.text().strip().lower()
        if not text:
            self._render(self._all_tags)
        else:
            self._render([t for t in self._all_tags if text in t.lower()])

    def _add_tag(self):
        name, ok = QInputDialog.getText(self, "添加标签", "标签名称：")
        if ok and name.strip():
            try:
                self.core.add_tag(name.strip())
                self.load_tags()
                self.mw.status_bar.showMessage(f"已添加标签: {name.strip()}", 2000)
            except Exception as e:
                QMessageBox.warning(self, "失败", str(e))

    def _edit_tag(self):
        item = self.list.currentItem()
        if not item:
            return
        old = item.text()
        new, ok = QInputDialog.getText(self, "编辑标签", "新名称：", text=old)
        if ok and new.strip() and new.strip() != old:
            try:
                self.core.update_tag(old, new.strip())
                self.load_tags()
            except Exception as e:
                QMessageBox.warning(self, "失败", str(e))

    def _delete_tag(self):
        items = self.list.selectedItems()
        if not items:
            return
        names = [i.text() for i in items]
        reply = QMessageBox.question(
            self, "确认删除", f"确定删除 {len(names)} 个标签吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        for n in names:
            try:
                self.core.delete_tag(n)
            except Exception:
                pass
        self.load_tags()
