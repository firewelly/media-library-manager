# -*- coding: utf-8 -*-
"""
智能更新对话框
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QGroupBox
)
from PySide6.QtCore import Qt

from ..core import Database
from ..workers import TaskWorker
from .task_progress_dialog import TaskProgressDialog


class SmartUpdateDialog(QDialog):
    """智能更新对话框"""

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.setWindowTitle("智能媒体库更新")
        self.setMinimumSize(500, 400)
        self.db = db

        self._setup_ui()

    def _setup_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("智能媒体库更新")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(title)

        desc = QLabel("扫描所有启用的文件夹，检测新增、移动、删除的视频文件")
        desc.setStyleSheet("color: #aab2c0;")
        layout.addWidget(desc)

        # 选项
        options_group = QGroupBox("选项")
        options_layout = QVBoxLayout()

        self.enable_md5 = QCheckBox("启用 MD5 匹配（更准确，但较慢）")
        self.enable_md5.setChecked(True)
        options_layout.addWidget(self.enable_md5)

        self.delete_missing = QCheckBox("删除数据库中缺失的记录")
        self.delete_missing.setChecked(False)
        options_layout.addWidget(self.delete_missing)

        options_group.setLayout(options_layout)
        layout.addWidget(options_group)

        # 按钮
        buttons = QHBoxLayout()
        buttons.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)

        start_btn = QPushButton("开始更新")
        start_btn.setProperty("primary", "true")
        start_btn.clicked.connect(self._start_update)
        buttons.addWidget(start_btn)

        layout.addLayout(buttons)

    def _start_update(self):
        """开始更新"""
        enable_md5 = self.enable_md5.isChecked()
        delete_missing = self.delete_missing.isChecked()

        def task(progress_callback=None, cancel_check=None):
            # 调用 fast_smart_media_updater
            from fast_smart_media_updater import run_fast_update
            
            result = run_fast_update(
                enable_md5=enable_md5,
                delete_missing=delete_missing,
                progress_callback=progress_callback,
                cancel_check=cancel_check
            )
            return result

        # 显示进度对话框
        progress = TaskProgressDialog("智能媒体库更新", self)
        progress.show()

        worker = TaskWorker(task)
        worker.progress_signal.connect(progress.update_progress)
        progress.cancel_signal.connect(worker.cancel)

        def on_finished(result):
            progress.close()
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, "完成",
                f"智能更新完成\n\n"
                f"新增: {result.get('new_files', 0)}\n"
                f"更新: {result.get('updated_files', 0)}\n"
                f"删除: {result.get('removed_files', 0)}\n"
                f"MD5更新: {result.get('md5_updated', 0)}"
            )
            self.accept()

        worker.finished_signal.connect(on_finished)
        worker.error_signal.connect(
            lambda err: (progress.close(), 
                        QMessageBox.critical(self, "错误", str(err)))
        )

        worker.start()
        self._worker = worker
