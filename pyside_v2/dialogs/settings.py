# -*- coding: utf-8 -*-
"""
设置对话框 —— v2 全局设置（对齐 v1 缺失的偏好配置能力）。

设置项：
    主题 / 每页条数 / 搜索防抖 / 默认仅在线 / 播放器路径 / 列布局重置

持久化：core/settings.SettingsManager → gui_config_v2.json
确定后回调 on_apply(settings_dict)，由 MainWindow 应用（无需重启）。
"""

import os

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QCheckBox, QLineEdit, QFileDialog, QGroupBox,
    QMessageBox,
)
from PySide6.QtCore import Qt

from pyside_v2.core.settings import SettingsManager


class SettingsDialog(QDialog):
    """全局设置对话框。"""

    def __init__(self, main_window, parent=None):
        super().__init__(parent or main_window)
        self.mw = main_window
        self.settings: SettingsManager = main_window.core_settings
        self.setWindowTitle("设置")
        self.resize(460, 380)
        self._setup_ui()
        self._load_values()

    def _setup_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 16)
        lay.setSpacing(12)

        # ---- 外观与列表 ----
        box = QGroupBox("外观与列表")
        form = QFormLayout(box)
        form.setSpacing(10)

        self.theme_combo = QComboBox()
        self.theme_combo.addItem("亮色（Fluent）", "light")
        self.theme_combo.addItem("暗色（影院）", "dark")
        form.addRow("主题：", self.theme_combo)

        self.page_size_spin = QSpinBox()
        self.page_size_spin.setRange(100, 1000)
        self.page_size_spin.setSingleStep(50)
        self.page_size_spin.setToolTip("列表/封面墙每页加载条数")
        form.addRow("每页条数：", self.page_size_spin)

        self.debounce_spin = QSpinBox()
        self.debounce_spin.setRange(200, 2000)
        self.debounce_spin.setSingleStep(100)
        self.debounce_spin.setSuffix(" ms")
        self.debounce_spin.setToolTip("输入停止后多久触发搜索")
        form.addRow("搜索防抖：", self.debounce_spin)

        self.online_chk = QCheckBox("启动时默认勾选「仅在线」")
        form.addRow("", self.online_chk)
        lay.addWidget(box)

        # ---- 播放 ----
        play_box = QGroupBox("播放")
        play_form = QFormLayout(play_box)
        path_row = QHBoxLayout()
        self.player_edit = QLineEdit()
        self.player_edit.setPlaceholderText("留空 = 系统默认播放器")
        browse = QPushButton("浏览…")
        browse.setCursor(Qt.PointingHandCursor)
        browse.clicked.connect(self._browse_player)
        path_row.addWidget(self.player_edit, 1)
        path_row.addWidget(browse)
        play_form.addRow("播放器路径：", path_row)
        lay.addWidget(play_box)

        # ---- 列布局 ----
        col_box = QGroupBox("列布局")
        col_lay = QHBoxLayout(col_box)
        col_hint = QLabel("表格列宽/顺序在关闭窗口时自动保存。")
        col_hint.setStyleSheet("color: palette(mid);")
        btn_reset_cols = QPushButton("恢复默认列宽")
        btn_reset_cols.setCursor(Qt.PointingHandCursor)
        btn_reset_cols.clicked.connect(self._reset_columns)
        col_lay.addWidget(col_hint, 1)
        col_lay.addWidget(btn_reset_cols)
        lay.addWidget(col_box)

        lay.addStretch()

        # ---- 确定/取消 ----
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_save = QPushButton("确定")
        self.btn_save.setProperty("role", "primary")
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.clicked.connect(self._on_save)
        btn_cancel = QPushButton("取消")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_save)
        btn_row.addWidget(btn_cancel)
        lay.addLayout(btn_row)

    def _load_values(self):
        self.theme_combo.setCurrentIndex(
            0 if self.settings.get("theme") == "light" else 1)
        self.page_size_spin.setValue(int(self.settings.get("page_size") or 300))
        self.debounce_spin.setValue(int(self.settings.get("search_debounce_ms") or 500))
        self.online_chk.setChecked(bool(self.settings.get("show_online_only")))
        self.player_edit.setText(self.settings.get("player_path") or "")

    def _browse_player(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择播放器", "",
            "应用程序 (*.app *.exe);;所有文件 (*)" if os.name != "nt"
            else "应用程序 (*.exe);;所有文件 (*)")
        if path:
            self.player_edit.setText(path)

    def _reset_columns(self):
        self.settings.set("header_state", "")
        video_table = getattr(self.mw, "video_table", None)
        if video_table:
            video_table.restore_header_state(b"")
            # 恢复默认列宽
            widths = self.mw.video_model.column_widths
            for i, key in enumerate(self.mw.video_model.column_keys):
                video_table.setColumnWidth(i, widths.get(key, 100))
        QMessageBox.information(self, "已重置", "列布局已恢复默认（保存后生效持久化）。")

    def _on_save(self):
        self.settings.update(
            theme=self.theme_combo.currentData(),
            page_size=self.page_size_spin.value(),
            search_debounce_ms=self.debounce_spin.value(),
            show_online_only=self.online_chk.isChecked(),
            player_path=self.player_edit.text().strip(),
        )
        # 同步旧主题文件（ThemeManager 持久化兼容）
        try:
            import json
            from pyside_v2.theme.theme_manager import _THEME_FILE
            _THEME_FILE.write_text(
                json.dumps({"theme": self.theme_combo.currentData()}),
                encoding="utf-8")
        except Exception:
            pass
        self.accept()
