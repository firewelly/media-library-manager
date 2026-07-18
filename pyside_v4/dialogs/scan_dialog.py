# -*- coding: utf-8 -*-
"""
扫描进度对话框
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QFrame, QTextEdit,
    QWidget
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QTextCursor

from ..theme import get_main_qss


class ScanWorker(QThread):
    """扫描工作线程（模拟）"""

    progress = Signal(int, int, str)  # current, total, message
    finished = Signal(int, int, int)  # new_count, moved_count, deleted_count
    log = Signal(str, str)  # message, level

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = True

    def run(self):
        import time
        import random

        total = 48888
        new_count = 0
        moved_count = 0
        deleted_count = 0

        # 模拟扫描过程
        devices = [
            ("本地磁盘", "/Users/firewell/Movies", 21430),
            ("NAS · app", "/Volumes/app", 16885),
            ("NAS · Video", "/Volumes/Video", 10573),
        ]

        for device_name, device_path, device_total in devices:
            self.log.emit(f"开始扫描 {device_name} {device_path}", "info")

            for i in range(device_total):
                if not self._running:
                    return

                # 模拟进度
                if i % 100 == 0:
                    self.progress.emit(i, device_total, device_name)

                # 随机事件
                if random.random() < 0.001:
                    new_count += 1
                    self.log.emit(f"发现新增文件: {device_name}/video_{i}.mp4", "success")
                elif random.random() < 0.0005:
                    moved_count += 1
                    self.log.emit(f"文件移动检测: video_{i}.mp4", "warning")
                elif random.random() < 0.0001:
                    deleted_count += 1
                    self.log.emit(f"文件已删除: video_{i}.mp4", "error")

                time.sleep(0.001)  # 模拟扫描速度

            self.log.emit(f"{device_name} 扫描完成，共 {device_total} 个文件", "success")

        self.finished.emit(new_count, moved_count, deleted_count)

    def stop(self):
        self._running = False


class ScanDialog(QDialog):
    """扫描进度对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("扫描媒体库")
        self.setMinimumSize(700, 500)
        self.setStyleSheet(get_main_qss())

        self._worker = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # 标题
        title = QLabel("扫描媒体库")
        title.setStyleSheet("font-size: 20px; font-weight: 600;")
        layout.addWidget(title)

        subtitle = QLabel("正在扫描所有存储设备，检测新增、移动、删除的视频文件…")
        subtitle.setStyleSheet("color: #6b7382; font-size: 12px;")
        layout.addWidget(subtitle)

        # 总进度
        overall = QFrame()
        overall.setStyleSheet("background-color: #1f232c; border-radius: 8px; padding: 16px;")
        overall_layout = QVBoxLayout(overall)
        overall_layout.setContentsMargins(16, 16, 16, 16)
        overall_layout.setSpacing(8)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)

        self.progress_title = QLabel("总体进度")
        self.progress_title.setStyleSheet("font-size: 14px; font-weight: 600;")
        header_layout.addWidget(self.progress_title)

        header_layout.addStretch()

        self.progress_stats = QLabel("已扫描 0 / 48,888 个文件")
        self.progress_stats.setStyleSheet("color: #aab2c0; font-size: 12px;")
        header_layout.addWidget(self.progress_stats)

        overall_layout.addWidget(header)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #2a2f3a;
                border: none;
                border-radius: 4px;
                height: 8px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #f0b429;
                border-radius: 4px;
            }
        """)
        overall_layout.addWidget(self.progress_bar)

        meta = QWidget()
        meta_layout = QHBoxLayout(meta)
        meta_layout.setContentsMargins(0, 0, 0, 0)
        meta_layout.setSpacing(16)

        self.stat_new = QLabel("新增：0")
        self.stat_new.setStyleSheet("color: #6b7382; font-size: 12px;")
        meta_layout.addWidget(self.stat_new)

        self.stat_moved = QLabel("移动：0")
        self.stat_moved.setStyleSheet("color: #6b7382; font-size: 12px;")
        meta_layout.addWidget(self.stat_moved)

        self.stat_deleted = QLabel("删除：0")
        self.stat_deleted.setStyleSheet("color: #6b7382; font-size: 12px;")
        meta_layout.addWidget(self.stat_deleted)

        meta_layout.addStretch()

        self.stat_time = QLabel("耗时：00:00")
        self.stat_time.setStyleSheet("color: #6b7382; font-size: 12px;")
        meta_layout.addWidget(self.stat_time)

        overall_layout.addWidget(meta)

        layout.addWidget(overall)

        # 日志区
        log_title = QLabel("扫描日志")
        log_title.setStyleSheet("font-size: 14px; font-weight: 600;")
        layout.addWidget(log_title)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumHeight(200)
        self.log_box.setStyleSheet("""
            QTextEdit {
                background-color: #0f1115;
                border: 1px solid #1f232c;
                border-radius: 8px;
                padding: 12px;
                font-family: "SF Mono", "JetBrains Mono", monospace;
                font-size: 11px;
                color: #aab2c0;
            }
        """)
        layout.addWidget(self.log_box)

        # 底部按钮
        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(8)

        btn_layout.addStretch()

        self.btn_pause = QPushButton("暂停")
        self.btn_pause.clicked.connect(self._toggle_pause)
        btn_layout.addWidget(self.btn_pause)

        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_background = QPushButton("在后台运行")
        self.btn_background.setProperty("primary", "true")
        self.btn_background.clicked.connect(self._run_in_background)
        btn_layout.addWidget(self.btn_background)

        layout.addWidget(btn_row)

    def start_scan(self):
        """开始扫描"""
        self._worker = ScanWorker()
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.log.connect(self._on_log)
        self._worker.start()

        self._start_time = QThread.currentThread()
        import time
        self._start_timestamp = time.time()

    def _on_progress(self, current: int, total: int, device: str):
        percent = int(current / total * 100) if total > 0 else 0
        self.progress_bar.setValue(percent)
        self.progress_stats.setText(f"已扫描 {current:,} / {total:,} 个文件")

        import time
        elapsed = int(time.time() - self._start_timestamp)
        minutes = elapsed // 60
        seconds = elapsed % 60
        self.stat_time.setText(f"耗时：{minutes:02d}:{seconds:02d}")

    def _on_finished(self, new_count: int, moved_count: int, deleted_count: int):
        self.stat_new.setText(f"新增：{new_count}")
        self.stat_moved.setText(f"移动：{moved_count}")
        self.stat_deleted.setText(f"删除：{deleted_count}")

        self.progress_bar.setValue(100)
        self.progress_title.setText("扫描完成")

        self._on_log("扫描完成！", "success")

    def _on_log(self, message: str, level: str):
        import time
        timestamp = time.strftime("%H:%M:%S")

        color_map = {
            "info": "#aab2c0",
            "success": "#3fb950",
            "warning": "#d29922",
            "error": "#f47067",
        }
        color = color_map.get(level, "#aab2c0")

        html = f'<span style="color: #6b7382;">[{timestamp}]</span> <span style="color: {color};">{message}</span>'
        self.log_box.append(html)

        # 自动滚动到底部
        cursor = self.log_box.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_box.setTextCursor(cursor)

    def _toggle_pause(self):
        if self._worker:
            if self.btn_pause.text() == "暂停":
                self._worker.stop()
                self.btn_pause.setText("继续")
                self._on_log("扫描已暂停", "warning")
            else:
                self.start_scan()
                self.btn_pause.setText("暂停")
                self._on_log("扫描已恢复", "info")

    def _run_in_background(self):
        self._on_log("扫描将在后台继续运行", "info")
        self.accept()
