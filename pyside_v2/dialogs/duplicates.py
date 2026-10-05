# -*- coding: utf-8 -*-
"""
去重复管理界面 —— 补 v1 的交互式重复组浏览器（v2 原来只查不删）。

布局：
    左：重复组列表（组N · 文件数 · 总大小 · 类型[md5/file_hash]）
    右：当前组文件表（勾选 / 文件名 / 大小 / 星级 / 在线 / 路径）

操作：
    保留策略：保留最大 / 保留最高分 / 全选 / 全不选（反选组内其余）
    删除：☐ 同时删除磁盘文件（默认仅移除库记录）→ 二次确认 → 后台批量执行

数据源：core.maintenance_manager.find_duplicates()
    → [{type, hash, count, videos: [全字段 dict]}]
"""

import os

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox,
    QSplitter, QMessageBox,
)
from PySide6.QtCore import Qt, QThread, Signal

from pyside_v2.theme import color_hex


def _fmt_size(size):
    if not size:
        return ""
    try:
        s = float(size)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if s < 1024:
                return f"{s:.1f} {unit}"
            s /= 1024
        return f"{s:.1f} PB"
    except Exception:
        return str(size)


class DuplicatesWorker(QThread):
    """后台查找重复。"""

    # object 而非 list：Signal(list) 跨线程 emit 同样有 C++ 转换问题
    found = Signal(object)
    failed = Signal(str)

    def __init__(self, core, parent=None):
        super().__init__(parent)
        self.core = core

    def run(self):
        try:
            result = self.core.maintenance_manager.find_duplicates()
            self.found.emit(result or [])
        except Exception as e:
            self.failed.emit(str(e))


class DuplicatesDialog(QDialog):
    """重复组浏览器。"""

    def __init__(self, main_window, parent=None):
        super().__init__(parent or main_window)
        self.mw = main_window
        self.core = main_window.core
        self._groups = []          # find_duplicates 原始结果
        self._worker = None
        self.setWindowTitle("去重复管理")
        self.resize(960, 620)
        self._setup_ui()
        self._load_duplicates()

    # ------------------------------------------------------------------
    def _setup_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 12)
        lay.setSpacing(10)

        # 顶部说明 + 刷新
        top = QHBoxLayout()
        self.hint_label = QLabel("按 MD5 / 文件哈希查找内容相同的文件组。勾选要删除的重复项（每组至少保留一个）。")
        self.hint_label.setStyleSheet("color: palette(mid);")
        btn_refresh = QPushButton("⟳ 重新扫描")
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.clicked.connect(self._load_duplicates)
        top.addWidget(self.hint_label, 1)
        top.addWidget(btn_refresh)
        lay.addLayout(top)

        # 左右分栏
        split = QSplitter(Qt.Horizontal)
        self.group_list = QListWidget()
        self.group_list.setMinimumWidth(280)
        self.group_list.currentRowChanged.connect(self._on_group_changed)
        split.addWidget(self.group_list)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["删除", "文件名", "大小", "星级", "路径"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        split.addWidget(self.table)
        split.setSizes([320, 620])
        lay.addWidget(split, 1)

        # 策略行
        policy = QHBoxLayout()
        policy.addWidget(QLabel("选择策略："))
        for text, handler in [
            ("保留最大", self._keep_largest),
            ("保留最高分", self._keep_highest),
            ("全选本组", self._select_all_in_group),
            ("全不选", self._select_none_in_group),
        ]:
            btn = QPushButton(text)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(handler)
            policy.addWidget(btn)
        policy.addStretch()
        lay.addLayout(policy)

        # 删除行
        del_row = QHBoxLayout()
        self.chk_delete_files = QCheckBox("同时删除磁盘文件（危险，默认仅移除库记录）")
        self.chk_delete_files.setStyleSheet(f"color: {color_hex('danger')};")
        del_row.addWidget(self.chk_delete_files)
        del_row.addStretch()
        self.btn_delete = QPushButton("🗑 删除选中")
        self.btn_delete.setProperty("role", "primary")
        self.btn_delete.setCursor(Qt.PointingHandCursor)
        self.btn_delete.clicked.connect(self._delete_selected)
        del_row.addWidget(self.btn_delete)
        lay.addLayout(del_row)

        # 关闭
        close_row = QHBoxLayout()
        close_row.addStretch()
        btn_close = QPushButton("关闭")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.clicked.connect(self.accept)
        close_row.addWidget(btn_close)
        lay.addLayout(close_row)

    # ------------------------------------------------------------------
    def _load_duplicates(self):
        self.group_list.clear()
        self.table.setRowCount(0)
        self.hint_label.setText("⏳ 正在扫描重复文件…")
        self.btn_delete.setEnabled(False)
        self._worker = DuplicatesWorker(self.core, self)
        self._worker.found.connect(self._on_found)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_failed(self, msg):
        self.hint_label.setText(f"❌ 扫描失败: {msg}")

    def _on_found(self, groups):
        self._groups = groups
        self.group_list.clear()
        total_files = sum(g.get("count", 0) for g in groups)
        self.hint_label.setText(
            f"共 {len(groups)} 组重复 · 涉及 {total_files} 个文件"
            if groups else "✅ 未发现重复文件")
        self.btn_delete.setEnabled(bool(groups))
        for i, g in enumerate(groups):
            vids = g.get("videos", [])
            total_size = sum(v.get("file_size") or 0 for v in vids)
            item = QListWidgetItem(
                f"组 {i + 1} · {g.get('count', len(vids))} 个文件 · {_fmt_size(total_size)} · {g.get('type', '?')}")
            item.setData(Qt.UserRole, i)
            self.group_list.addItem(item)
        if groups:
            self.group_list.setCurrentRow(0)

    # ------------------------------------------------------------------
    def _current_group(self):
        row = self.group_list.currentRow()
        if 0 <= row < len(self._groups):
            return self._groups[row]
        return None

    def _on_group_changed(self, row):
        group = self._current_group()
        self.table.setRowCount(0)
        if not group:
            return
        vids = sorted(
            group.get("videos", []),
            key=lambda v: (v.get("file_size") or 0), reverse=True)
        self.table.setRowCount(len(vids))
        for r, v in enumerate(vids):
            # 勾选框（默认不勾 → 保留）
            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            chk_item.setCheckState(Qt.Unchecked)
            self.table.setItem(r, 0, chk_item)
            self.table.setItem(r, 1, QTableWidgetItem(v.get("file_name") or ""))
            size_item = QTableWidgetItem(_fmt_size(v.get("file_size")))
            size_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(r, 2, size_item)
            stars_item = QTableWidgetItem("★" * int(v.get("stars") or 0))
            stars_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(r, 3, stars_item)
            path_item = QTableWidgetItem(v.get("file_path") or "")
            self.table.setItem(r, 4, path_item)
            # 记录 video_id
            self.table.item(r, 0).setData(Qt.UserRole, v.get("id"))

    def _iter_rows(self):
        for r in range(self.table.rowCount()):
            yield r, self.table.item(r, 0)

    # ---- 保留策略 ----
    def _keep_by(self, key):
        """组内保留 key 最大者，勾选其余。key=lambda video_dict。"""
        group = self._current_group()
        if not group or not group.get("videos"):
            return
        vids = group["videos"]
        best = max(range(len(vids)), key=lambda i: key(vids[i]) or 0)
        best_id = vids[best].get("id")
        for r, chk in self._iter_rows():
            chk.setCheckState(
                Qt.Unchecked if chk.data(Qt.UserRole) == best_id else Qt.Checked)

    def _keep_largest(self):
        self._keep_by(lambda v: v.get("file_size"))

    def _keep_highest(self):
        self._keep_by(lambda v: (v.get("stars") or 0, v.get("file_size") or 0))

    def _select_all_in_group(self):
        for _, chk in self._iter_rows():
            chk.setCheckState(Qt.Checked)

    def _select_none_in_group(self):
        for _, chk in self._iter_rows():
            chk.setCheckState(Qt.Unchecked)

    # ------------------------------------------------------------------
    def _delete_selected(self):
        """删除所有组中勾选的项（跨组汇总）。"""
        targets = []   # (video_id, file_path, file_name)
        for r, chk in self._iter_rows():
            if chk.checkState() == Qt.Checked:
                targets.append((chk.data(Qt.UserRole),
                                self.table.item(r, 4).text(),
                                self.table.item(r, 1).text()))
        if not targets:
            self.mw.status_bar.showMessage("未勾选任何要删除的项", 3000)
            return

        delete_files = self.chk_delete_files.isChecked()
        mode = "库记录 + 磁盘文件" if delete_files else "仅库记录"
        reply = QMessageBox.question(
            self, "确认删除",
            f"将删除 {len(targets)} 个文件（{mode}）。\n\n确定继续吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return

        ok = 0
        for vid, fpath, fname in targets:
            try:
                if delete_files and fpath and os.path.exists(fpath):
                    os.remove(fpath)
                self.core.delete_video(vid)
                ok += 1
            except Exception as e:
                self.mw.status_bar.showMessage(f"删除失败 {fname}: {e}", 5000)
        self.mw.status_bar.showMessage(f"已删除 {ok}/{len(targets)} 个重复文件", 4000)
        self.mw.load_videos()
        self._load_duplicates()   # 重新扫描剩余重复
