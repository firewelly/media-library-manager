# -*- coding: utf-8 -*-
"""
日志系统 - 从 media_library_pyside.py (73-177行) 原样移入。

通过 monkey-patching media_library._output_log，将 Tkinter 版后端的日志
重定向到 Qt 信号 qt_log_handler.log_signal，供主窗口状态栏/日志区接收。
"""

from datetime import datetime
from PySide6.QtCore import QObject, Signal


class LogLevel:
    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3
    CRITICAL = 4


CURRENT_LOG_LEVEL = LogLevel.INFO
LOG_TO_CONSOLE = True
LOG_TO_GUI = True


def set_log_level(level):
    global CURRENT_LOG_LEVEL
    CURRENT_LOG_LEVEL = level


def log_debug(message, gui_log_func=None):
    if CURRENT_LOG_LEVEL <= LogLevel.DEBUG:
        _output_log_qt("DEBUG", message, gui_log_func)


def log_info(message, gui_log_func=None):
    if CURRENT_LOG_LEVEL <= LogLevel.INFO:
        _output_log_qt("INFO", message, gui_log_func)


def log_warning(message, gui_log_func=None):
    if CURRENT_LOG_LEVEL <= LogLevel.WARNING:
        _output_log_qt("WARNING", message, gui_log_func)


def log_error(message, gui_log_func=None):
    if CURRENT_LOG_LEVEL <= LogLevel.ERROR:
        _output_log_qt("ERROR", message, gui_log_func)


def log_critical(message, gui_log_func=None):
    if CURRENT_LOG_LEVEL <= LogLevel.CRITICAL:
        _output_log_qt("CRITICAL", message, gui_log_func)


class ProgressUpdateManager:
    """进度更新节流器（原样移入）"""

    def __init__(self, update_interval=10):
        self.update_interval = update_interval
        self.last_update_count = 0

    def should_update(self, current_count, total_count=None, force_update=False):
        if force_update:
            return True
        if total_count and current_count >= total_count:
            return True
        if current_count - self.last_update_count >= self.update_interval:
            self.last_update_count = current_count
            return True
        return False

    def update_progress(self, progress_var, status_var, current_count, total_count, status_text, progress_window=None, update_stats_func=None, *args):
        if self.should_update(current_count, total_count):
            if progress_var is not None:
                progress = (current_count / total_count) * 100 if total_count and total_count > 0 else 0
                try:
                    progress_var(progress)
                except Exception:
                    pass
            if status_var is not None:
                try:
                    status_var(status_text)
                except Exception:
                    pass
            if update_stats_func:
                try:
                    update_stats_func(*args)
                except Exception:
                    pass
            if progress_window is not None:
                try:
                    progress_window.update()
                except Exception:
                    pass


class ProgressWindow:
    """占位类，兼容后端部分方法签名"""

    def destroy(self):
        try:
            pass
        except Exception:
            pass


class QtLogHandler(QObject):
    """将日志通过 Qt 信号发送到 GUI 的处理器"""
    log_signal = Signal(str)


# 全局日志处理器实例（与 v1 同名，保证 monkey-patch 后日志路由一致）
qt_log_handler = QtLogHandler()


def _output_log_qt(level, message, gui_log_func=None):
    """输出日志的内部函数，兼容 Qt 信号"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    formatted_message = f"[{level}] {message}"

    if LOG_TO_CONSOLE:
        print(f"{timestamp} - {formatted_message}")
    if LOG_TO_GUI:
        qt_log_handler.log_signal.emit(formatted_message)


def init_qt_logging():
    """初始化 Qt 日志系统：把 Tkinter 版后端的 _output_log 替换为 Qt 版本。

    这是复用后端的关键一步——后端(media_library.py)内部调用的是
    media_library._output_log，替换后所有日志都会走 qt_log_handler.log_signal。
    """
    import media_library
    media_library._output_log = _output_log_qt


# 模块级别名，兼容后端可能直接 import 的场景
global _output_log
_output_log = _output_log_qt
