# -*- coding: utf-8 -*-
"""
设置对话框
"""

import json
import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QTabWidget, QWidget,
    QCheckBox, QComboBox, QLineEdit, QSpinBox,
    QMessageBox
)
from PySide6.QtCore import Qt

from ..theme import get_main_qss


class SettingsDialog(QDialog):
    """设置对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumSize(600, 500)
        self.setStyleSheet(get_main_qss())

        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标题
        header = QFrame()
        header.setStyleSheet("background-color: #1a1e26; padding: 16px;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("设置")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        layout.addWidget(header)

        # 标签页
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: #0f1115;
            }
            QTabBar::tab {
                background-color: #14171d;
                color: #aab2c0;
                padding: 12px 24px;
                border: none;
                border-bottom: 2px solid transparent;
            }
            QTabBar::tab:selected {
                background-color: #1a1e26;
                color: #f0b429;
                border-bottom: 2px solid #f0b429;
            }
            QTabBar::tab:hover {
                background-color: #1f232c;
                color: #f2f4f8;
            }
        """)

        # 通用设置
        general_tab = self._create_general_tab()
        tabs.addTab(general_tab, "通用")

        # 界面设置
        appearance_tab = self._create_appearance_tab()
        tabs.addTab(appearance_tab, "界面")

        # 存储设置
        storage_tab = self._create_storage_tab()
        tabs.addTab(storage_tab, "存储")

        # 高级设置
        advanced_tab = self._create_advanced_tab()
        tabs.addTab(advanced_tab, "高级")

        layout.addWidget(tabs, 1)

        # 底部按钮
        footer = QFrame()
        footer.setStyleSheet("background-color: #1a1e26; padding: 16px;")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 16, 16, 16)

        footer_layout.addStretch()

        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        footer_layout.addWidget(btn_cancel)

        btn_save = QPushButton("保存")
        btn_save.setProperty("primary", "true")
        btn_save.clicked.connect(self._save_settings)
        footer_layout.addWidget(btn_save)

        layout.addWidget(footer)

    def _create_general_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # 启动选项
        startup_group = self._create_group("启动选项")
        startup_layout = QVBoxLayout(startup_group)

        self.chk_startup = QCheckBox("开机自动启动")
        startup_layout.addWidget(self.chk_startup)

        self.chk_minimize = QCheckBox("启动时最小化到托盘")
        startup_layout.addWidget(self.chk_minimize)

        self.chk_check_update = QCheckBox("启动时检查更新")
        self.chk_check_update.setChecked(True)
        startup_layout.addWidget(self.chk_check_update)

        layout.addWidget(startup_group)

        # 扫描选项
        scan_group = self._create_group("扫描选项")
        scan_layout = QVBoxLayout(scan_group)

        self.chk_auto_scan = QCheckBox("启动时自动扫描媒体库")
        scan_layout.addWidget(self.chk_auto_scan)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(QLabel("扫描间隔（分钟）："))
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(5, 1440)
        self.interval_spin.setValue(60)
        self.interval_spin.setStyleSheet("""
            QSpinBox {
                background-color: #0a0c0f;
                border: 1px solid #1f232c;
                border-radius: 4px;
                padding: 4px 8px;
                color: #f2f4f8;
                min-width: 80px;
            }
        """)
        row_layout.addWidget(self.interval_spin)
        row_layout.addStretch()
        scan_layout.addWidget(row)

        layout.addWidget(scan_group)

        layout.addStretch()

        return widget

    def _create_appearance_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # 主题
        theme_group = self._create_group("主题")
        theme_layout = QVBoxLayout(theme_group)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(QLabel("界面主题："))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["深色影院风", "浅色 Fluent 风", "跟随系统"])
        self.theme_combo.setStyleSheet("""
            QComboBox {
                background-color: #0a0c0f;
                border: 1px solid #1f232c;
                border-radius: 4px;
                padding: 4px 12px;
                color: #f2f4f8;
                min-width: 150px;
            }
        """)
        row_layout.addWidget(self.theme_combo)
        row_layout.addStretch()
        theme_layout.addWidget(row)

        layout.addWidget(theme_group)

        # 列表
        list_group = self._create_group("列表显示")
        list_layout = QVBoxLayout(list_group)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(QLabel("默认行高："))
        self.height_combo = QComboBox()
        self.height_combo.addItems(["紧凑 (36px)", "舒适 (44px)"])
        self.height_combo.setStyleSheet("""
            QComboBox {
                background-color: #0a0c0f;
                border: 1px solid #1f232c;
                border-radius: 4px;
                padding: 4px 12px;
                color: #f2f4f8;
                min-width: 150px;
            }
        """)
        row_layout.addWidget(self.height_combo)
        row_layout.addStretch()
        list_layout.addWidget(row)

        self.chk_show_cover = QCheckBox("显示封面缩略图")
        self.chk_show_cover.setChecked(True)
        list_layout.addWidget(self.chk_show_cover)

        layout.addWidget(list_group)

        layout.addStretch()

        return widget

    def _create_storage_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # 文件夹管理
        folder_group = self._create_group("监控文件夹")
        folder_layout = QVBoxLayout(folder_group)

        folders = [
            ("/Users/firewell/Movies", "本地磁盘", True),
            ("/Volumes/app", "NAS · app", True),
            ("/Volumes/Video", "NAS · Video", False),
        ]

        for path, name, active in folders:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)

            chk = QCheckBox()
            chk.setChecked(active)
            row_layout.addWidget(chk)

            info = QLabel(f"{name}\n{path}")
            info.setStyleSheet("color: #f2f4f8; font-size: 12px;")
            row_layout.addWidget(info, 1)

            btn_remove = QPushButton("移除")
            btn_remove.setFixedSize(60, 28)
            btn_remove.setStyleSheet("font-size: 11px; padding: 0;")
            row_layout.addWidget(btn_remove)

            folder_layout.addWidget(row)

        btn_add = QPushButton("+ 添加文件夹")
        btn_add.clicked.connect(lambda: None)
        folder_layout.addWidget(btn_add)

        layout.addWidget(folder_group)

        layout.addStretch()

        return widget

    def _create_advanced_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # 数据库
        db_group = self._create_group("数据库")
        db_layout = QVBoxLayout(db_group)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(QLabel("数据库路径："))
        path_label = QLabel("media_library.db")
        path_label.setStyleSheet("color: #6b7382; font-family: monospace;")
        row_layout.addWidget(path_label)
        row_layout.addStretch()
        db_layout.addWidget(row)

        btn_backup = QPushButton("备份数据库")
        db_layout.addWidget(btn_backup)

        layout.addWidget(db_group)

        # 缓存
        cache_group = self._create_group("缓存")
        cache_layout = QVBoxLayout(cache_group)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(QLabel("缓存大小："))
        cache_label = QLabel("64 MB")
        cache_label.setStyleSheet("color: #f2f4f8;")
        row_layout.addWidget(cache_label)
        row_layout.addStretch()
        cache_layout.addWidget(row)

        btn_clear = QPushButton("清除缓存")
        cache_layout.addWidget(btn_clear)

        layout.addWidget(cache_group)

        layout.addStretch()

        return widget

    def _create_group(self, title: str) -> QFrame:
        group = QFrame()
        group.setStyleSheet("background-color: #1a1e26; border-radius: 8px; padding: 16px;")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(16, 16, 16, 16)

        label = QLabel(title)
        label.setStyleSheet("font-size: 14px; font-weight: 600; margin-bottom: 8px;")
        layout.addWidget(label)

        return group

    def _load_settings(self):
        """加载设置"""
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'settings.json')
        config_path = os.path.abspath(config_path)
        
        if not os.path.exists(config_path):
            return
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            
            self.theme_combo.setCurrentText(settings.get("theme", "深色影院风"))
            self.height_combo.setCurrentText(settings.get("row_height", "紧凑 (36px)"))
            self.chk_show_cover.setChecked(settings.get("show_cover", True))
            self.chk_startup.setChecked(settings.get("startup", False))
            self.chk_minimize.setChecked(settings.get("minimize", False))
            self.chk_check_update.setChecked(settings.get("check_update", True))
            self.chk_auto_scan.setChecked(settings.get("auto_scan", False))
            self.interval_spin.setValue(settings.get("scan_interval", 60))
        except Exception:
            pass

    def _save_settings(self):
        """保存设置到配置文件"""
        settings = {
            "theme": self.theme_combo.currentText(),
            "row_height": self.height_combo.currentText(),
            "show_cover": self.chk_show_cover.isChecked(),
            "startup": self.chk_startup.isChecked(),
            "minimize": self.chk_minimize.isChecked(),
            "check_update": self.chk_check_update.isChecked(),
            "auto_scan": self.chk_auto_scan.isChecked(),
            "scan_interval": self.interval_spin.value(),
        }
        
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'settings.json')
        config_path = os.path.abspath(config_path)
        
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "保存成功", "设置已保存")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"无法保存设置：{str(e)}")
