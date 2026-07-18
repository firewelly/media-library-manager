# -*- coding: utf-8 -*-
"""
视频列表 QTableView。

性能（vs v1 QTreeWidget）：
    - QAbstractTableModel 仅绘制可视行，49k 行流畅
    - 星级/状态用 delegate 直接绘制，无 widget 开销
    - 列宽持久化用 QHeaderView saveState/restoreState（修复 v1 setup_table_columns bug）
"""

from PySide6.QtWidgets import QTableView, QHeaderView, QAbstractItemView, QMenu
from PySide6.QtCore import Qt, Signal

from pyside_v2.widgets.video_model import VideoTableModel
from pyside_v2.widgets.star_delegate import StarDelegate


class VideoTableView(QTableView):
    """视频表格视图。

    向上发出信号供 MainWindow 接管：
        selection_changed(video_id)   单选变化
        double_clicked(video_id)      双击（默认播放）
        header_clicked(col_key)       表头点击（排序）
        context_menu_requested(pos)   右键菜单
    """

    selection_changed = Signal(object)   # video_id or None
    double_clicked = Signal(object)      # video_id or None
    header_clicked = Signal(str)         # 列标识
    context_menu_requested = Signal(object)  # QPoint（viewport 相对）

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent

        # 交互
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setShowGrid(False)
        self.setWordWrap(False)

        # 表头
        hh = self.horizontalHeader()
        hh.setSectionsMovable(True)
        hh.setSectionsClickable(True)
        hh.setStretchLastSection(False)
        hh.setHighlightSections(False)
        hh.sectionClicked.connect(self._on_header_clicked)

        vh = self.verticalHeader()
        vh.setVisible(False)
        vh.setDefaultSectionSize(34)

        # 右键
        self.setContextMenuPolicy(Qt.CustomContextMenu)

        # model/delegate 由 set_model 注入

    def set_model(self, model: VideoTableModel):
        self.setModel(model)
        # 应用列宽
        widths = model.column_widths
        for i, key in enumerate(model.column_keys):
            w = widths.get(key, 100)
            self.setColumnWidth(i, w)
        # 星级列用 delegate
        for i, key in enumerate(model.column_keys):
            if key == 'stars':
                self.setItemDelegateForColumn(i, StarDelegate(self))

    # ---- 信号转发 ----
    def currentChanged(self, current, previous):
        super().currentChanged(current, previous)
        vid = current.data(Qt.UserRole) if current.isValid() else None
        self.selection_changed.emit(vid)

    def mouseDoubleClickEvent(self, event):
        idx = self.indexAt(event.pos())
        if idx.isValid():
            vid = idx.data(Qt.UserRole)
            self.double_clicked.emit(vid)
        else:
            super().mouseDoubleClickEvent(event)

    def _on_header_clicked(self, section):
        model = self.model()
        if isinstance(model, VideoTableModel) and 0 <= section < len(model.column_keys):
            self.header_clicked.emit(model.column_keys[section])

    def save_header_state(self) -> bytes:
        """保存表头状态（列宽/顺序）供持久化。"""
        return self.horizontalHeader().saveState()

    def restore_header_state(self, state: bytes):
        if state:
            self.horizontalHeader().restoreState(state)

    def selected_video_ids(self):
        """返回当前选中行的 video_id 列表。"""
        ids = []
        for idx in self.selectionModel().selectedRows():
            vid = idx.data(Qt.UserRole)
            if vid is not None:
                ids.append(vid)
        return ids
