# -*- coding: utf-8 -*-
"""
通用任务进度对话框
参考 media_library_pyside.py 的 TaskProgressDialog
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QTextEdit, QGroupBox
)
from PySide6.QtCore import Qt, Signal


class TaskProgressDialog(QDialog):
    """通用任务进度对话框"""
    cancel_signal = Signal()

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(600, 450)
        self.setModal(True)
        self.setup_ui()
        self.cancelled = False

    def setup_ui(self):
        layout = QVBoxLayout()

        # 标题
        self.title_label = QLabel("正在处理...")
        self.title_label.setStyleSheet("font-size: 14px; font-weight: bold; margin: 10px;")
        layout.addWidget(self.title_label)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # 当前文件进度条
        self.file_progress_bar = QProgressBar()
        self.file_progress_bar.setRange(0, 100)
        self.file_progress_bar.setValue(0)
        self.file_progress_bar.setFormat("当前文件: %p%")
        layout.addWidget(self.file_progress_bar)

        # 速度标签
        self.speed_label = QLabel("")
        self.speed_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.speed_label)

        # 状态标签
        self.status_label = QLabel("准备开始...")
        layout.addWidget(self.status_label)

        # 统计信息区域
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("font-family: monospace; background-color: #1a1e26; padding: 5px; border: 1px solid #2d3340;")
        self.stats_label.hide()
        layout.addWidget(self.stats_label)

        # 日志区域
        log_group = QGroupBox("处理日志")
        log_group.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #2d3340; border-radius: 4px; margin-top: 8px; padding-top: 8px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px; }")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("background-color: #0f1115; border: none; font-family: monospace;")
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)

        # 按钮
        button_layout = QHBoxLayout()
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.cancel)
        self.cancel_button.setStyleSheet("background-color: #2d3340; border: none; padding: 6px 16px; border-radius: 4px;")
        button_layout.addWidget(self.cancel_button)
        button_layout.addStretch()
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def update_progress(self, value, message="", data=None):
        if value >= 0:
            self.progress_bar.setValue(value)
        if message:
            self.status_label.setText(message)
        
        if data and 'file_progress' in data:
            fp = data['file_progress']
            current = fp.get('current', 0)
            total = fp.get('total', 0)
            speed_str = fp.get('speed_str', '')
            
            if total > 0:
                pct = int((current / total) * 100)
                self.file_progress_bar.setValue(pct)
            
            if speed_str:
                self.speed_label.setText(speed_str)

    def set_stats(self, text):
        self.stats_label.setText(text)
        self.stats_label.show()

    def append_log(self, message):
        from datetime import datetime
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_text.append(f"[{timestamp}] {message}")
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def cancel(self):
        self.cancelled = True
        self.cancel_button.setText("正在取消...")
        self.cancel_button.setEnabled(False)
        self.cancel_signal.emit()
