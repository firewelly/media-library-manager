# -*- coding: utf-8 -*-
"""
通用后台任务对话框（原生 PySide6）。

所有"批量/耗时操作"共用此对话框：提供任务函数 → 后台线程执行 → 进度+日志显示。
替代 Tk 版各方法里重复的 tk.Toplevel + Progressbar + Text 日志模式。

用法：
    TaskRunnerDialog.run(parent, title, task_func, on_done=callback)
    task_func(progress_cb, log_cb, cancel_cb) -> result_str
        progress_cb(percent, status)   报告进度
        log_cb(message)                写日志
        cancel_cb() -> bool            检查是否取消
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QProgressBar,
    QPlainTextEdit, QGroupBox, QHBoxLayout,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont

from pyside_v2.theme import Tokens


class _TaskWorker(QThread):
    """执行任务函数的后台线程。"""
    progress_signal = Signal(int, str)   # percent, status
    log_signal = Signal(str)             # message
    finished_signal = Signal(str)        # result summary
    error_signal = Signal(str)           # error message

    def __init__(self, task_func, parent=None):
        super().__init__(parent)
        self._task_func = task_func
        self._cancelled = False

    def run(self):
        def progress_cb(percent, status=""):
            self.progress_signal.emit(int(percent), status)

        def log_cb(msg):
            self.log_signal.emit(msg)

        def cancel_cb():
            return self._cancelled

        try:
            result = self._task_func(progress_cb, log_cb, cancel_cb)
            self.finished_signal.emit(result or "完成")
        except Exception as e:
            import traceback
            self.log_signal.emit(f"错误: {e}")
            self.error_signal.emit(str(e))

    def cancel(self):
        self._cancelled = True


class TaskRunnerDialog(QDialog):
    """通用任务执行对话框（进度条 + 日志 + 取消）。"""

    def __init__(self, title, task_func, parent=None, on_done=None):
        super().__init__(parent)
        self._on_done = on_done
        self._worker = None
        self._setup_ui(title)
        self._start(task_func)

    def _setup_ui(self, title):
        self.setWindowTitle(title)
        self.resize(560, 520)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(Tokens.SP_5, Tokens.SP_5, Tokens.SP_5, Tokens.SP_5)
        lay.setSpacing(Tokens.SP_3)

        # 进度
        prog_box = QGroupBox("进度")
        prog_lay = QVBoxLayout(prog_box)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        prog_lay.addWidget(self.progress)
        self.status_label = QLabel("准备中…")
        self.status_label.setStyleSheet("color: palette(mid);")
        prog_lay.addWidget(self.status_label)
        lay.addWidget(prog_box)

        # 日志
        log_box = QGroupBox("日志")
        log_lay = QVBoxLayout(log_box)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        mono = QFont("Menlo"); mono.setPointSize(10)
        self.log_view.setFont(mono)
        log_lay.addWidget(self.log_view)
        lay.addWidget(log_box, 1)

        # 按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.clicked.connect(self._cancel)
        self.btn_close = QPushButton("关闭")
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setEnabled(False)
        self.btn_close.clicked.connect(self.accept)
        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_close)
        lay.addLayout(btn_row)

    def _start(self, task_func):
        self._worker = _TaskWorker(task_func, self)
        self._worker.progress_signal.connect(self._on_progress)
        self._worker.log_signal.connect(self._log)
        self._worker.finished_signal.connect(self._on_finished)
        self._worker.error_signal.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, percent, status):
        self.progress.setValue(percent)
        if status:
            self.status_label.setText(status)

    def _log(self, msg):
        self.log_view.appendPlainText(msg)

    def _on_finished(self, summary):
        self.progress.setValue(100)
        self.status_label.setText(summary)
        self._log(f"\n{summary}")
        self.btn_cancel.setEnabled(False)
        self.btn_close.setEnabled(True)
        if self._on_done:
            try:
                self._on_done()
            except Exception:
                pass

    def _on_error(self, err):
        self.status_label.setText(f"错误: {err}")
        self.btn_cancel.setEnabled(False)
        self.btn_close.setEnabled(True)

    def _cancel(self):
        if self._worker:
            self._worker.cancel()
            self.status_label.setText("正在取消…")

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.quit()
            self._worker.wait(5000)
        event.accept()

    @staticmethod
    def run(parent, title, task_func, on_done=None):
        """便捷方法：创建并模态执行任务对话框。"""
        dlg = TaskRunnerDialog(title, task_func, parent, on_done)
        dlg.exec()
        return dlg
