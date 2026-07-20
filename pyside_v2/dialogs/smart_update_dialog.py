# -*- coding: utf-8 -*-
"""
快速智能媒体库更新对话框（原生 PySide6）。

替代 Tk 版 quick_smart_media_update（深度依赖 Tk GUI，桥接失败）。
复用底层 fast_smart_media_updater.run_fast_update（纯函数，不依赖 Tk）。

流程：选活跃文件夹（多选）→ 勾选选项 → 后台线程执行 → 进度+日志。
"""

import os

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QCheckBox, QProgressBar, QPlainTextEdit, QGroupBox,
    QMessageBox,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont

from pyside_v2.theme import Tokens


class SmartUpdateDialog(QDialog):
    """快速智能媒体库更新对话框。"""

    def __init__(self, main_window, parent=None):
        super().__init__(parent or main_window)
        self.mw = main_window
        self.core = main_window.core
        self._worker = None
        self._setup_ui()
        self._load_folders()

    def _setup_ui(self):
        self.setWindowTitle("快速智能媒体库更新")
        self.resize(620, 600)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(Tokens.SP_5, Tokens.SP_5, Tokens.SP_5, Tokens.SP_5)
        lay.setSpacing(Tokens.SP_3)

        # 文件夹选择
        box = QGroupBox("选择要更新的文件夹（可多选）")
        box_lay = QVBoxLayout(box)
        btn_row = QHBoxLayout()
        btn_all = QPushButton("全选"); btn_all.setCursor(Qt.PointingHandCursor)
        btn_none = QPushButton("取消全选"); btn_none.setCursor(Qt.PointingHandCursor)
        btn_all.clicked.connect(lambda: self._select_all(True))
        btn_none.clicked.connect(lambda: self._select_all(False))
        btn_row.addWidget(btn_all); btn_row.addWidget(btn_none); btn_row.addStretch()
        box_lay.addLayout(btn_row)

        self.folder_list = QListWidget()
        self.folder_list.setSelectionMode(QListWidget.MultiSelection)
        self.folder_list.setAlternatingRowColors(True)
        self.folder_list.setMinimumHeight(140)
        box_lay.addWidget(self.folder_list)
        lay.addWidget(box)

        # 选项
        opt_box = QGroupBox("更新选项")
        opt_lay = QVBoxLayout(opt_box)
        self.chk_md5 = QCheckBox("启用 MD5 校验（更精确检测移动，但较慢）")
        self.chk_delete = QCheckBox("删除库中已不存在的文件记录")
        self.chk_delete.setChecked(True)
        opt_lay.addWidget(self.chk_md5)
        opt_lay.addWidget(self.chk_delete)
        lay.addWidget(opt_box)

        # 按钮
        btn_row2 = QHBoxLayout()
        self.btn_run = QPushButton("开始更新")
        self.btn_run.setProperty("role", "primary")
        self.btn_run.setCursor(Qt.PointingHandCursor)
        self.btn_run.clicked.connect(self._start)
        btn_close = QPushButton("关闭")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.clicked.connect(self.reject)
        btn_row2.addStretch()
        btn_row2.addWidget(self.btn_run)
        btn_row2.addWidget(btn_close)
        lay.addLayout(btn_row2)

        # 进度 + 日志
        prog_box = QGroupBox("进度")
        prog_lay = QVBoxLayout(prog_box)
        self.progress = QProgressBar()
        self.progress.setValue(0)
        prog_lay.addWidget(self.progress)
        self.status_label = QLabel("准备就绪")
        self.status_label.setStyleSheet("color: palette(mid);")
        prog_lay.addWidget(self.status_label)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        mono = QFont("Menlo"); mono.setPointSize(10)
        self.log_view.setFont(mono)
        self.log_view.setMinimumHeight(160)
        prog_lay.addWidget(self.log_view)
        lay.addWidget(prog_box, 1)

    def _load_folders(self):
        """加载活跃且在线的文件夹。"""
        try:
            self.core.cursor.execute(
                "SELECT folder_path FROM folders WHERE is_active = 1 ORDER BY folder_path"
            )
            folders = [r[0] for r in self.core.cursor.fetchall() if r[0]]
        except Exception:
            folders = []
        self.folder_list.clear()
        for f in folders:
            online = os.path.exists(f)
            text = f"{f}  [{'在线' if online else '离线'}]"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, f)
            if not online:
                item.setForeground(Qt.gray)
            self.folder_list.addItem(item)
        # 默认全选在线的
        for i in range(self.folder_list.count()):
            item = self.folder_list.item(i)
            if os.path.exists(item.data(Qt.UserRole)):
                item.setSelected(True)

    def _select_all(self, selected):
        for i in range(self.folder_list.count()):
            self.folder_list.item(i).setSelected(selected)

    def _log(self, msg):
        self.log_view.appendPlainText(msg)

    def _start(self):
        selected = [
            self.folder_list.item(i).data(Qt.UserRole)
            for i in range(self.folder_list.count())
            if self.folder_list.item(i).isSelected()
        ]
        # 只保留在线的
        selected = [f for f in selected if os.path.exists(f)]
        if not selected:
            QMessageBox.warning(self, "提示", "请至少选择一个在线文件夹")
            return

        options = {
            'enable_md5': self.chk_md5.isChecked(),
            'delete_missing': self.chk_delete.isChecked(),
        }
        self.btn_run.setEnabled(False)
        self.progress.setValue(0)
        self._log(f"开始更新 {len(selected)} 个文件夹…")

        self._worker = SmartUpdateWorker(self.core, selected, options)
        self._worker.progress_signal.connect(self._on_progress)
        self._worker.log_signal.connect(self._log)
        self._worker.finished_signal.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, value, status):
        self.progress.setValue(value)
        self.status_label.setText(status)

    def _on_finished(self, summary):
        self.btn_run.setEnabled(True)
        self.progress.setValue(100)
        self.status_label.setText(summary)
        self._log(summary)
        if hasattr(self.mw, 'load_videos'):
            self.mw.load_videos()

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            self._worker.quit()
            self._worker.wait(3000)
        event.accept()

    def reject(self):
        if self._worker and self._worker.isRunning():
            self._worker.quit()
            self._worker.wait(3000)
        super().reject()


class SmartUpdateWorker(QThread):
    """快速智能更新工作线程（对接 fast_smart_media_updater）。"""

    progress_signal = Signal(int, str)
    log_signal = Signal(str)
    finished_signal = Signal(str)

    def __init__(self, core, folders, options):
        super().__init__()
        self.core = core
        self.folders = folders
        self.options = options

    def run(self):
        try:
            import fast_smart_media_updater as fsu
            total = len(self.folders)
            self.log_signal.emit(f"共 {total} 个文件夹")

            def progress_cb(msg):
                self.log_signal.emit(msg)

            stats = fsu.run_fast_update(
                folders=self.folders,
                enable_md5=self.options.get('enable_md5', False),
                dry_run=False,
                delete_missing=self.options.get('delete_missing', True),
                quiet=True,
                progress=progress_cb,
            )
            # 汇总
            added = sum(getattr(s, 'added', 0) for s in stats.values())
            updated = sum(getattr(s, 'updated', 0) for s in stats.values())
            skipped = sum(getattr(s, 'skipped', 0) for s in stats.values())
            removed = sum(getattr(s, 'removed', 0) for s in stats.values())
            summary = (f"完成：新增 {added}，更新 {updated}，"
                       f"跳过 {skipped}，删除 {removed}（{total} 个文件夹）")
            self.progress_signal.emit(100, summary)
            self.finished_signal.emit(summary)
        except Exception as e:
            self.log_signal.emit(f"错误: {e}")
            self.finished_signal.emit(f"更新出错: {e}")
