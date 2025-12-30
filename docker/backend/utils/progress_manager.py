#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
进度管理模块
从media_library.py提取的进度显示和更新功能
"""

import threading
import time
from typing import Optional, Callable, Any

class ProgressUpdateManager:
    """进度更新管理器，用于控制GUI更新频率"""
    def __init__(self, update_interval: int = 10):
        self.update_interval = update_interval  # 每N个项目更新一次
        self.last_update_count = 0

    def should_update(self, current_count: int, total_count: Optional[int] = None, force_update: bool = False) -> bool:
        """判断是否应该更新进度"""
        if force_update:
            return True
        if total_count and current_count >= total_count:
            return True  # 最后一个项目总是更新
        if current_count - self.last_update_count >= self.update_interval:
            self.last_update_count = current_count
            return True
        return False

    def update_progress(self, progress_var=None, status_var=None, current_count: int = 0,
                       total_count: Optional[int] = None, status_text: str = "",
                       progress_window=None, update_stats_func: Optional[Callable] = None,
                       *args) -> None:
        """统一的进度更新函数"""
        if self.should_update(current_count, total_count):
            if progress_var:
                progress = (current_count / total_count) * 100 if total_count and total_count > 0 else 0
                try:
                    progress_var.set(progress)
                except AttributeError:
                    pass  # 支持不同类型的进度条
            if status_var:
                try:
                    status_var.set(status_text)
                except AttributeError:
                    pass
            if update_stats_func:
                update_stats_func(*args)
            if progress_window:
                try:
                    progress_window.update()
                except AttributeError:
                    pass

class ProgressTracker:
    """通用进度跟踪器，不依赖特定的GUI框架"""

    def __init__(self, total: int, description: str = "处理中", update_callback: Optional[Callable] = None):
        self.total = total
        self.current = 0
        self.description = description
        self.update_callback = update_callback
        self.start_time = time.time()
        self.last_update_time = 0
        self.cancelled = False

    def update(self, current: int, message: str = "") -> None:
        """更新进度"""
        if self.cancelled:
            return

        self.current = current
        current_time = time.time()

        # 限制更新频率（最多每0.1秒更新一次）
        if current_time - self.last_update_time < 0.1 and current < self.total:
            return

        self.last_update_time = current_time

        if self.update_callback:
            percentage = (current / self.total) * 100 if self.total > 0 else 0
            elapsed = current_time - self.start_time

            if current > 0:
                eta = (elapsed / current) * (self.total - current)
                eta_str = f"剩余 {eta:.1f}s"
            else:
                eta_str = "计算中..."

            status_message = f"{self.description}: {current}/{self.total} ({percentage:.1f}%) - {eta_str}"
            if message:
                status_message += f" - {message}"

            try:
                self.update_callback(current, self.total, status_message, percentage)
            except Exception as e:
                print(f"进度更新回调错误: {e}")

    def cancel(self) -> None:
        """取消进度跟踪"""
        self.cancelled = True

    def is_cancelled(self) -> bool:
        """检查是否已取消"""
        return self.cancelled

class ThreadedProgress:
    """支持线程的进度管理器"""

    def __init__(self, total: int, description: str = "处理中"):
        self.total = total
        self.description = description
        self.current = 0
        self.lock = threading.Lock()
        self.callbacks = []
        self.cancelled = False
        self.start_time = time.time()

    def add_callback(self, callback: Callable) -> None:
        """添加进度更新回调函数"""
        self.callbacks.append(callback)

    def update(self, increment: int = 1, message: str = "") -> None:
        """更新进度（线程安全）"""
        with self.lock:
            if self.cancelled:
                return

            self.current = min(self.current + increment, self.total)
            current_time = time.time()

            if self.current > 0:
                elapsed = current_time - self.start_time
                eta = (elapsed / self.current) * (self.total - self.current)
                percentage = (self.current / self.total) * 100
            else:
                eta = 0
                percentage = 0

            progress_info = {
                'current': self.current,
                'total': self.total,
                'percentage': percentage,
                'message': message,
                'elapsed': current_time - self.start_time,
                'eta': eta,
                'description': self.description
            }

            # 调用所有回调函数
            for callback in self.callbacks:
                try:
                    callback(progress_info)
                except Exception as e:
                    print(f"进度回调错误: {e}")

    def set_current(self, current: int, message: str = "") -> None:
        """设置当前进度值"""
        with self.lock:
            if self.cancelled:
                return
            increment = current - self.current
            if increment > 0:
                self.update(increment, message)

    def cancel(self) -> None:
        """取消进度"""
        with self.lock:
            self.cancelled = True

    def is_cancelled(self) -> bool:
        """检查是否已取消"""
        with self.lock:
            return self.cancelled

    def is_finished(self) -> bool:
        """检查是否已完成"""
        with self.lock:
            return self.current >= self.total

def create_simple_tracker(total: int, description: str = "处理中") -> ProgressTracker:
    """创建简单的进度跟踪器"""
    return ProgressTracker(total, description)

def create_threaded_tracker(total: int, description: str = "处理中") -> ThreadedProgress:
    """创建线程安全的进度跟踪器"""
    return ThreadedProgress(total, description)