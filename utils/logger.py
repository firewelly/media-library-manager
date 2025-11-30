#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志系统模块
从media_library.py提取的日志功能，支持GUI和控制台输出
"""

from datetime import datetime
import sys

class LogLevel:
    """日志级别枚举"""
    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3
    CRITICAL = 4

# 全局日志配置
CURRENT_LOG_LEVEL = LogLevel.INFO  # 默认日志级别
LOG_TO_CONSOLE = True  # 是否输出到控制台
LOG_TO_GUI = True  # 是否输出到GUI

def set_log_level(level):
    """设置全局日志级别"""
    global CURRENT_LOG_LEVEL
    CURRENT_LOG_LEVEL = level

def log_debug(message, gui_log_func=None):
    """调试级别日志"""
    if CURRENT_LOG_LEVEL <= LogLevel.DEBUG:
        _output_log("DEBUG", message, gui_log_func)

def log_info(message, gui_log_func=None):
    """信息级别日志"""
    if CURRENT_LOG_LEVEL <= LogLevel.INFO:
        _output_log("INFO", message, gui_log_func)

def log_warning(message, gui_log_func=None):
    """警告级别日志"""
    if CURRENT_LOG_LEVEL <= LogLevel.WARNING:
        _output_log("WARNING", message, gui_log_func)

def log_error(message, gui_log_func=None):
    """错误级别日志"""
    if CURRENT_LOG_LEVEL <= LogLevel.ERROR:
        _output_log("ERROR", message, gui_log_func)

def log_critical(message, gui_log_func=None):
    """严重错误级别日志"""
    if CURRENT_LOG_LEVEL <= LogLevel.CRITICAL:
        _output_log("CRITICAL", message, gui_log_func)

def _output_log(level, message, gui_log_func=None):
    """输出日志的内部函数"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    formatted_message = f"[{level}] {message}"

    # 输出到控制台
    if LOG_TO_CONSOLE:
        print(f"{timestamp} - {formatted_message}")

    # 输出到GUI（如果提供了GUI日志函数）
    if LOG_TO_GUI and gui_log_func:
        try:
            gui_log_func(formatted_message)
        except Exception as e:
            # 如果GUI日志输出失败，回退到控制台
            print(f"{timestamp} - GUI_LOG_ERROR: {e}")
            print(f"{timestamp} - {formatted_message}")

class Logger:
    """日志器类，支持面向对象的日志记录"""

    def __init__(self, name, gui_log_func=None):
        self.name = name
        self.gui_log_func = gui_log_func

    def debug(self, message):
        """记录调试信息"""
        log_debug(f"[{self.name}] {message}", self.gui_log_func)

    def info(self, message):
        """记录信息"""
        log_info(f"[{self.name}] {message}", self.gui_log_func)

    def warning(self, message):
        """记录警告"""
        log_warning(f"[{self.name}] {message}", self.gui_log_func)

    def error(self, message):
        """记录错误"""
        log_error(f"[{self.name}] {message}", self.gui_log_func)

    def critical(self, message):
        """记录严重错误"""
        log_critical(f"[{self.name}] {message}", self.gui_log_func)

def get_logger(name, gui_log_func=None):
    """获取一个日志器实例"""
    return Logger(name, gui_log_func)