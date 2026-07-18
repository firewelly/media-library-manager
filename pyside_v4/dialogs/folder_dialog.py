# -*- coding: utf-8 -*-
"""
文件夹管理对话框
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QMessageBox, QCheckBox
)
from PySide6.QtCore import Qt

from ..core import Database


class FolderDialog(QDialog):
    """文件夹管理对话框"""

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.setWindowTitle("文件夹管理")
        self.setMinimumSize(700, 500)
        self.db = db

        self._setup_ui()
        self._load_folders()

    def _setup_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("文件夹管理")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(title)

        # 工具栏
        toolbar = QHBoxLayout()
        
        add_btn = QPushButton("+ 添加文件夹")
        add_btn.clicked.connect(self._add_folder)
        toolbar.addWidget(add_btn)

        remove_btn = QPushButton("移除")
        remove_btn.clicked.connect(self._remove_folder)
        toolbar.addWidget(remove_btn)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # 文件夹列表
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["启用", "路径", "类型", "设备"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 60)
        self.table.setColumnWidth(2, 80)
        self.table.setColumnWidth(3, 120)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        # 按钮
        buttons = QHBoxLayout()
        buttons.addStretch()
        
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        buttons.addWidget(close_btn)
        
        layout.addLayout(buttons)

    def _load_folders(self):
        """加载文件夹列表"""
        rows = self.db.execute(
            "SELECT id, folder_path, folder_type, is_active, device_name FROM folders ORDER BY folder_path"
        )
        
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            # 启用复选框
            checkbox = QCheckBox()
            checkbox.setChecked(bool(row["is_active"]))
            checkbox.stateChanged.connect(
                lambda state, fid=row["id"]: self._toggle_folder(fid, state)
            )
            self.table.setCellWidget(i, 0, checkbox)

            # 路径
            self.table.setItem(i, 1, QTableWidgetItem(row["folder_path"]))

            # 类型
            self.table.setItem(i, 2, QTableWidgetItem(row["folder_type"] or "local"))

            # 设备
            self.table.setItem(i, 3, QTableWidgetItem(row["device_name"] or ""))

    def _add_folder(self):
        """添加文件夹"""
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if not folder:
            return

        # 检查是否已存在
        existing = self.db.execute_one(
            "SELECT id FROM folders WHERE folder_path = ?", (folder,)
        )
        if existing:
            QMessageBox.warning(self, "警告", "该文件夹已存在")
            return

        # 添加
        import platform
        device_name = platform.node() or "Unknown"
        self.db.execute_write(
            "INSERT INTO folders (folder_path, folder_type, is_active, device_name) VALUES (?, 'local', 1, ?)",
            (folder, device_name)
        )
        self._load_folders()

    def _remove_folder(self):
        """移除文件夹"""
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "警告", "请先选择要移除的文件夹")
            return

        row = selected[0].row()
        path_item = self.table.item(row, 1)
        if not path_item:
            return

        folder_path = path_item.text()
        
        reply = QMessageBox.question(
            self, "确认",
            f"确定要移除文件夹吗？\n{folder_path}\n\n注意：这不会删除文件，只是从监控列表中移除。",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.db.execute_write("DELETE FROM folders WHERE folder_path = ?", (folder_path,))
            self._load_folders()

    def _toggle_folder(self, folder_id: int, state: int):
        """切换文件夹启用状态"""
        is_active = 1 if state == Qt.CheckState.Checked.value else 0
        self.db.execute_write(
            "UPDATE folders SET is_active = ? WHERE id = ?",
            (is_active, folder_id)
        )
