#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GUI适配层 - 用于将Tkinter的media_library功能适配到PySide6
通过适配器模式，最大程度复用原有代码而不需要修改
"""

import sys
import os
import threading
import tempfile
import sqlite3
from pathlib import Path
from datetime import datetime

# PySide6导入
from PySide6.QtWidgets import (
    QApplication, QMessageBox, QFileDialog, QInputDialog,
    QProgressDialog, QLabel, QPushButton, QVBoxLayout, QWidget
)
from PySide6.QtCore import QThread, Signal, QTimer
from PySide6.QtGui import QPixmap

class TkinterToQtAdapter:
    """Tkinter到PySide6的适配器类"""

    def __init__(self, qt_window):
        self.qt_window = qt_window
        self.core = qt_window.core

    # 文件对话框适配
    def askdirectory(self, title="选择文件夹", initialdir=None):
        """适配tkinter的askdirectory"""
        folder = QFileDialog.getExistingDirectory(
            self.qt_window, title, initialdir or ""
        )
        return folder

    def askopenfilename(self, title="选择文件", filetypes=None, initialdir=None):
        """适配tkinter的askopenfilename"""
        file_filter = ";;".join([f"{ft[1]} ({ft[0]})" for ft in filetypes]) if filetypes else "All Files (*)"
        file_path, _ = QFileDialog.getOpenFileName(
            self.qt_window, title, initialdir or "", file_filter
        )
        return file_path

    def askopenfilenames(self, title="选择文件", filetypes=None, initialdir=None):
        """适配tkinter的askopenfilenames"""
        file_filter = ";;".join([f"{ft[1]} ({ft[0]})" for ft in filetypes]) if filetypes else "All Files (*)"
        file_paths, _ = QFileDialog.getOpenFileNames(
            self.qt_window, title, initialdir or "", file_filter
        )
        return file_paths

    def asksaveasfilename(self, title="保存文件", defaultextension="", filetypes=None, initialdir=None):
        """适配tkinter的asksaveasfilename"""
        file_filter = ";;".join([f"{ft[1]} ({ft[0]})" for ft in filetypes]) if filetypes else "All Files (*)"
        file_path, _ = QFileDialog.getSaveFileName(
            self.qt_window, title, initialdir or "", file_filter
        )
        return file_path

    # 消息框适配
    def showinfo(self, title, message):
        """适配tkinter的showinfo"""
        QMessageBox.information(self.qt_window, title, str(message))

    def showwarning(self, title, message):
        """适配tkinter的showwarning"""
        QMessageBox.warning(self.qt_window, title, str(message))

    def showerror(self, title, message):
        """适配tkinter的showerror"""
        QMessageBox.critical(self.qt_window, title, str(message))

    def askyesno(self, title, message):
        """适配tkinter的askyesno"""
        reply = QMessageBox.question(
            self.qt_window, title, str(message),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        return reply == QMessageBox.Yes

    def askokcancel(self, title, message):
        """适配tkinter的askokcancel"""
        reply = QMessageBox.question(
            self.qt_window, title, str(message),
            QMessageBox.Ok | QMessageBox.Cancel,
            QMessageBox.Cancel
        )
        return reply == QMessageBox.Ok

    def askretrycancel(self, title, message):
        """适配tkinter的askretrycancel"""
        reply = QMessageBox.question(
            self.qt_window, title, str(message),
            QMessageBox.Retry | QMessageBox.Cancel,
            QMessageBox.Cancel
        )
        return reply == QMessageBox.Retry

    def askyesnocancel(self, title, message):
        """适配tkinter的askyesnocancel（三选一：是/否/取消）。返回 True/False/None。"""
        reply = QMessageBox.question(
            self.qt_window, title, str(message),
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            QMessageBox.Yes
        )
        if reply == QMessageBox.Yes:
            return True
        if reply == QMessageBox.No:
            return False
        return None  # Cancel

    # 输入对话框适配
    def askstring(self, title, prompt, initialvalue=None):
        """适配tkinter的askstring"""
        text, ok = QInputDialog.getText(
            self.qt_window, title, prompt, text=initialvalue or ""
        )
        return text if ok else None

    def askinteger(self, title, prompt, initialvalue=None, minvalue=None, maxvalue=None):
        """适配tkinter的askinteger"""
        text, ok = QInputDialog.getInt(
            self.qt_window, title, prompt,
            initialvalue or 0, minvalue or -2147483648, maxvalue or 2147483647
        )
        return text if ok else None

from PySide6.QtCore import Signal as QtSignal

class ProgressThread(QThread):
    """进度条线程，用于适配Tkinter的进度更新"""

    progress_update = QtSignal(int, int, str)  # current, total, message
    finished_signal = QtSignal()

    def __init__(self, target_func, *args, **kwargs):
        super().__init__()
        self.target_func = target_func
        self.args = args
        self.kwargs = kwargs
        self.progress_callback = None

    def run(self):
        """运行目标函数"""
        if self.progress_callback:
            # 将进度回调替换为Qt信号
            self.kwargs['progress_callback'] = self._emit_progress

        try:
            self.target_func(*self.args, **self.kwargs)
        except Exception as e:
            print(f"线程执行错误: {e}")
        finally:
            self.finished_signal.emit()

    def _emit_progress(self, current, total, message=""):
        """发送进度更新信号"""
        self.progress_update.emit(current, total, message)

class MediaLibraryFunctionAdapter:
    """媒体库功能适配器，用于无缝集成原有功能"""

    def __init__(self, qt_window):
        self.qt_window = qt_window
        self.core = qt_window.core
        self.tk_adapter = TkinterToQtAdapter(qt_window)

        # 创建兼容的messagebox模块
        self.messagebox = self.tk_adapter

        # 创建兼容的filedialog模块
        self.filedialog = self.tk_adapter

        # 创建兼容的simpledialog模块
        self.simpledialog = self.tk_adapter

    def create_threaded_function(self, func_name):
        """创建线程化版本的函数"""
        def threaded_wrapper(*args, **kwargs):
            # 检查是否有对应的原函数
            if not hasattr(self, func_name):
                self.qt_window.show_error("错误", f"功能 {func_name} 尚未适配")
                return

            original_func = getattr(self, func_name)

            # 创建进度对话框
            progress_dialog = QProgressDialog(
                self.qt_window
            )
            progress_dialog.setWindowTitle("处理中...")
            progress_dialog.setCancelButtonText("取消")
            progress_dialog.setRange(0, 0)  # 不确定进度
            progress_dialog.show()

            # 创建工作线程
            worker_thread = ProgressThread(original_func, *args, **kwargs)

            def on_progress(current, total, message):
                if total > 0:
                    progress_dialog.setRange(0, total)
                    progress_dialog.setValue(current)
                if message:
                    progress_dialog.setLabelText(message)
                QApplication.processEvents()

            def on_finished():
                progress_dialog.close()
                self.qt_window.refresh_data()

            worker_thread.progress_update.connect(on_progress)
            worker_thread.finished_signal.connect(on_finished)
            worker_thread.start()

        return threaded_wrapper

    def inject_dependencies(self):
        """向核心模块注入依赖"""
        import media_library

        # 替换messagebox模块
        media_library.messagebox = self.messagebox
        media_library.filedialog = self.filedialog
        media_library.simpledialog = self.simpledialog

        # 如果原模块需要root窗口，我们可以创建一个虚拟的root对象
        class DummyRoot:
            def __init__(self, qt_window):
                self.qt_window = qt_window

            def protocol(self, name, handler):
                """适配WM_DELETE_WINDOW事件"""
                if name == "WM_DELETE_WINDOW":
                    self.qt_window.closeEvent = lambda e: handler()

        # 这里我们选择不直接替换root，而是在具体方法中处理

class MediaLibraryIntegration:
    """媒体库功能集成器，负责将原有功能完整集成到PySide界面"""

    def __init__(self, qt_window):
        self.qt_window = qt_window
        self.core = qt_window.core
        self.adapter = MediaLibraryFunctionAdapter(qt_window)

        # 注入依赖
        self.adapter.inject_dependencies()

        # 绑定功能方法
        self.bind_functions()

    def bind_functions(self):
        """绑定原有功能到PySide界面"""
        # 将原有的功能方法绑定到新的GUI
        # 这里我们使用动态导入和适配的方式

        import importlib
        import media_library

        # 获取原有的MediaLibrary类
        original_class = media_library.MediaLibrary

        # 创建一个临时实例用于访问方法（但不初始化，避免关闭数据库连接）
        temp_instance = original_class.__new__(original_class)
        temp_instance.conn = self.core.conn
        temp_instance.cursor = self.core.cursor
        temp_instance.root = DummyTkinterRoot(self.qt_window)

        # 重写析构函数，防止关闭共享的数据库连接
        def dummy_del():
            pass
        temp_instance.__del__ = dummy_del

        # 获取所有方法（除了特殊方法）
        methods = [method for method in dir(temp_instance)
                  if not method.startswith('_') and callable(getattr(temp_instance, method))]

        # 绑定方法到新窗口
        for method_name in methods:
            if hasattr(self.qt_window, method_name):
                continue  # 避免覆盖已存在的方法

            method = getattr(temp_instance, method_name)
            if not hasattr(method, '__self__') or method.__self__ != temp_instance:
                continue

            # 创建适配版本的方法
            def create_adapted_method(original_method, method_name):
                def adapted_method(*args, **kwargs):
                    # 创建一个临时的self对象，动态回退到 core/qt_window/MediaLibrary 默认值。
                    # 用 __getattr__ 解决 Tk 方法依赖大量 self.xxx 属性的问题。
                    core = self.core
                    qt_window = self.qt_window
                    ml_class = media_library.MediaLibrary

                    class TempSelf:
                        """动态属性回退的临时 self。

                        访问属性顺序：显式设置 > core > qt_window > MediaLibrary 默认值。
                        Tk 的 GUI 控件（video_tree 等）返回 None 占位（不崩）。
                        """
                        def __getattr__(self, attr):
                            # 1. core 上有
                            if hasattr(core, attr):
                                return getattr(core, attr)
                            # 2. qt_window 上有
                            if hasattr(qt_window, attr):
                                return getattr(qt_window, attr)
                            # 3. Tk 类属性（方法/类变量）
                            if hasattr(ml_class, attr):
                                return getattr(ml_class, attr)
                            # 4. 已知的 Tk 实例属性默认值（避免 AttributeError）
                            _defaults = {
                                'db_path': getattr(core, 'db_path', ''),
                                'folder_online_cache': {},
                                'folder_cache_lock': __import__('threading').Lock(),
                                'cache_update_interval': 5,
                                'current_sort_column': None,
                                'current_sort_reverse': False,
                                'progress_window': None,
                                'import_window': None,
                                'cancel_import': False,
                                'cancel_sync': False,
                                'cancel_reset': False,
                                'cancel_thumbnail': False,
                                'generate_missing_only': False,
                                'status_var': None,
                                'progress_var': None,
                            }
                            if attr in _defaults:
                                return _defaults[attr]
                            # 5. Tk GUI 控件占位（video_tree/folder_listbox 等）
                            #    返回 None，让 Tk 方法自然失败而非 AttributeError
                            return None

                        def __setattr__(self, attr, value):
                            object.__setattr__(self, attr, value)

                    temp_self = TempSelf()
                    temp_self.conn = core.conn
                    temp_self.cursor = core.cursor
                    temp_self.root = DummyTkinterRoot(qt_window)

                    # 确保临时对象不会关闭数据库连接
                    temp_self._shared_connection = True
                    temp_self.column_config = core.column_config
                    temp_self.current_video = core.current_video
                    temp_self.sort_column_name = core.sort_column_name
                    temp_self.sort_reverse = core.sort_reverse
                    temp_self.gpu_acceleration = core.gpu_acceleration

                    # 注入适配器
                    temp_self.messagebox = self.adapter.messagebox
                    temp_self.filedialog = self.adapter.filedialog
                    temp_self.simpledialog = self.adapter.simpledialog

                    # 适配GUI更新方法
                    def gui_updater(log_message):
                        qt_window.status_bar.showMessage(log_message)

                    temp_self.log_info = lambda msg: media_library.log_info(msg, gui_updater)
                    temp_self.log_error = lambda msg: media_library.log_error(msg, gui_updater)
                    temp_self.log_warning = lambda msg: media_library.log_warning(msg, gui_updater)

                    # 如果方法需要更新视频列表，我们在调用后刷新
                    # 注：original_method 是绑定方法（getattr(temp_instance, name)），
                    # 其 __self__ 已是 temp_instance，所以这里用 __func__ 取未绑定函数，
                    # 让 temp_self 正确作为 self 参数（否则双 self 注入导致 TypeError）。
                    if method_name in ['scan_media', 'import_videos', 'import_nfo', 'remove_duplicates']:
                        try:
                            result = original_method.__func__(temp_self, *args, **kwargs)
                            self.qt_window.refresh_data()
                            return result
                        except Exception as e:
                            self.qt_window.show_error("错误", f"执行 {method_name} 失败: {str(e)}")
                            return None
                    else:
                        # 对于其他方法，直接调用
                        return original_method.__func__(temp_self, *args, **kwargs)

                return adapted_method

            # 绑定适配的方法
            adapted_method = create_adapted_method(method, method_name)
            setattr(self.qt_window, method_name, adapted_method)

class DummyTkinterRoot:
    """虚拟的Tkinter根窗口，用于适配原有代码"""

    def __init__(self, qt_window):
        self.qt_window = qt_window

    def protocol(self, name, handler):
        """适配WM_DELETE_WINDOW事件"""
        if name == "WM_DELETE_WINDOW":
            # 我们可以在这里处理窗口关闭事件
            pass

    def title(self, new_title=None):
        """获取或设置窗口标题"""
        if new_title:
            self.qt_window.setWindowTitle(new_title)
        return self.qt_window.windowTitle()

    def geometry(self, geometry_string=None):
        """获取或设置窗口几何"""
        if geometry_string:
            # 解析几何字符串并应用
            pass
        # 返回当前几何信息
        return f"{self.qt_window.width()}x{self.qt_window.height()}+{self.qt_window.x()}+{self.qt_window.y()}"

class GUIComponentAdapter:
    """GUI组件适配器，用于在PySide和Tkinter组件间转换"""

    @staticmethod
    def adapt_treeview_data(video_tree_widget):
        """将Tkinter Treeview数据适配到PySide TreeWidget"""
        # 这个方法可以在数据加载时使用
        pass

    @staticmethod
    def adapt_file_dialog_result(result):
        """适配文件对话框结果"""
        return result

    @staticmethod
    def adapt_progress_callback(progress_var, progress_bar, progress_label):
        """适配进度回调函数"""
        def callback(current, total, message=""):
            if total > 0:
                percentage = int((current / total) * 100)
                progress_bar.setValue(percentage)
            if message:
                progress_label.setText(message)

        return callback

def create_integration_layer(qt_window):
    """创建完整的集成层"""
    integration = MediaLibraryIntegration(qt_window)
    return integration

def setup_full_integration(qt_window):
    """设置完整的集成"""
    # 创建集成层
    integration = create_integration_layer(qt_window)

    # 绑定所有功能
    integration.bind_functions()

    return integration