# -*- coding: utf-8 -*-
"""
pyside_v4.core.logging — Qt 信号日志适配
直接 import utils/logger.py，重定向到 Qt Signal
"""

import sys
import os
from datetime import datetime

# 确保项目根目录在 sys.path 中
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from PySide6.QtCore import QObject, Signal


class LogEmitter(QObject):
    """Qt 信号日志发射器"""
    log_message = Signal(str, str)  # level, formatted_message


# 全局实例
_emitter = LogEmitter()


def get_emitter() -> LogEmitter:
    return _emitter


def format_log(level: str, message: str) -> str:
    timestamp = datetime.now().strftime('%H:%M:%S')
    return f"[{level}] {message}"


def log_debug(message: str):
    formatted = format_log("DEBUG", message)
    _emitter.log_message.emit("DEBUG", formatted)
    print(formatted)


def log_info(message: str):
    formatted = format_log("INFO", message)
    _emitter.log_message.emit("INFO", formatted)
    print(formatted)


def log_warning(message: str):
    formatted = format_log("WARNING", message)
    _emitter.log_message.emit("WARNING", formatted)
    print(formatted)


def log_error(message: str):
    formatted = format_log("ERROR", message)
    _emitter.log_message.emit("ERROR", formatted)
    print(formatted)


def log_critical(message: str):
    formatted = format_log("CRITICAL", message)
    _emitter.log_message.emit("CRITICAL", formatted)
    print(formatted)
