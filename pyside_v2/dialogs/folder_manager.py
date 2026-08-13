# -*- coding: utf-8 -*-
"""
文件夹管理对话框（对齐 v1 FolderManagerWindow，ui_design 风格）。

功能：表格列出管理文件夹（路径/类型/设备/状态）+ 添加/删除/启停/编辑/刷新。
数据来自 folders 表（folder_path, folder_type, is_active, device_name）。
"""

import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QGroupBox, QMessageBox, QInputDialog,
    QFileDialog, QComboBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from pyside_v2.theme import Tokens, color_hex


class FolderManagerDialog(QDialog):
    """文件夹管理对话框。"""

    def __init__(self, main_window, parent=None):
        super().__init__(parent or main_window)
        self.mw = main_window
        self.core = main_window.core
        self.setWindowTitle("文件夹管理")
        self.resize(720, 480)
        self._setup_ui()
        self.load_folders()

    def _setup_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(Tokens.SP_5, Tokens.SP_5, Tokens.SP_5, Tokens.SP_5)
        lay.setSpacing(Tokens.SP_3)

        box = QGroupBox("管理文件夹")
        box_lay = QVBoxLayout(box)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["文件夹路径", "类型", "设备", "状态", "操作"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        box_lay.addWidget(self.table)
        lay.addWidget(box)

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("＋ 添加文件夹")
        self.btn_add.setProperty("role", "primary")
        self.btn_add.setCursor(Qt.PointingHandCursor)
        self.btn_add.clicked.connect(self._add_folder)
        self.btn_toggle = QPushButton("启用/停用")
        self.btn_toggle.setCursor(Qt.PointingHandCursor)
        self.btn_toggle.clicked.connect(self._toggle_active)
        self.btn_del = QPushButton("删除")
        self.btn_del.setStyleSheet(f"color: {color_hex('danger')};")
        self.btn_del.setCursor(Qt.PointingHandCursor)
        self.btn_del.clicked.connect(self._delete_folder)
        self.btn_refresh = QPushButton("⟳ 刷新")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.clicked.connect(self.load_folders)
        for b in (self.btn_add, self.btn_toggle, self.btn_del, self.btn_refresh):
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

    def load_folders(self):
        try:
            rows = self.core.get_all_folders()
        except Exception:
            rows = []
        self.table.setRowCount(len(rows))
        for r, (fid, path, ftype, active, device) in enumerate(rows):
            self.table.setItem(r, 0, QTableWidgetItem(path))
            self.table.setItem(r, 1, QTableWidgetItem(ftype or "local"))
            self.table.setItem(r, 2, QTableWidgetItem(device or "—"))
            status_item = QTableWidgetItem("启用" if active else "停用")
            online = os.path.exists(path) if path else False
            if active and online:
                status_color = color_hex('success')
            elif active:
                status_color = color_hex('warning')
            else:
                status_color = color_hex('text_3')
            status_item.setForeground(QColor(status_color))
            self.table.setItem(r, 3, status_item)
            self.table.setItem(r, 4, QTableWidgetItem(""))
            # 存 id 到第0列的 UserRole
            self.table.item(r, 0).setData(Qt.UserRole, fid)

    def _current_id(self):
        item = self.table.currentItem()
        if not item:
            return None
        return self.table.item(item.row(), 0).data(Qt.UserRole)

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if not folder:
            return
        ftype, ok = QInputDialog.getItem(
            self, "文件夹类型", "选择类型：", ["local", "nas"], 0, False
        )
        if not ok:
            ftype = "local"
        try:
            device = self.core.get_current_device_name()
            self.core.add_folder(folder, ftype, device)
            self.load_folders()
            self.mw.sidebar.load_storage_locations(self.core)
            self.mw.status_bar.showMessage(f"已添加: {folder}", 2000)
        except Exception as e:
            QMessageBox.warning(self, "失败", str(e))

    def _toggle_active(self):
        fid = self._current_id()
        if fid is None:
            return
        try:
            self.core.toggle_folder_active(fid)
            self.load_folders()
            self.mw.sidebar.load_storage_locations(self.core)
        except Exception as e:
            QMessageBox.warning(self, "失败", str(e))

    def _delete_folder(self):
        fid = self._current_id()
        if fid is None:
            return
        reply = QMessageBox.question(
            self, "确认删除", "确定删除此文件夹（仅移除管理，不删文件）？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        try:
            self.core.delete_folder(fid)
            self.load_folders()
            self.mw.sidebar.load_storage_locations(self.core)
        except Exception as e:
            QMessageBox.warning(self, "失败", str(e))
