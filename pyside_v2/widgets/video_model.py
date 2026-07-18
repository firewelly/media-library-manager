# -*- coding: utf-8 -*-
"""
视频表格数据模型 - 分页 + 核心字段（性能版）。

性能架构（vs v1 的 QTreeWidget + 全量 JOIN）：
    1. 列表只查核心字段（10 列），不 SELECT *，不 JOIN 演员/标签
       → 49k 库首屏 300 行：1.7ms（v1 同查询 31s）
    2. 分页：每页 PAGE_SIZE 条，翻页/搜索重新查询
    3. 演员/标签/JAVDB 信息在选中行时按 video_id 子查询（0.2ms）
    4. 排序走索引字段（file_created_time / title / stars / ...）

列定义沿用 core.column_config 的 18 列标识，但模型按"显示列"组织，
数据行是 10 元组（核心字段），演员/标签等通过 row 的 source_folder 等
派生或留空（详情面板单独查）。
"""

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex


# 列表核心查询字段顺序（与 load_page 的 SELECT 严格一致）
# 0:id 1:file_path 2:file_name 3:title 4:stars 5:tags 6:file_size
# 7:is_nas_online 8:duration 9:resolution 10:file_created_time 11:source_folder 12:md5_hash
FIELD_INDEX = {
    'id': 0, 'file_path': 1, 'file_name': 2, 'title': 3, 'stars': 4,
    'tags': 5, 'file_size': 6, 'is_nas_online': 7, 'duration': 8,
    'resolution': 9, 'file_created_time': 10, 'source_folder': 11, 'md5_hash': 12,
}

# 显示列：列标识 → (显示名, 数据源字段名, 默认宽度, 对齐方式)
# 只含列表实际展示的列（详情面板另有完整字段）
DISPLAY_COLUMNS = [
    ('title',              '标题',      360, 'left'),
    ('stars',              '星级',      80,  'center'),
    ('tags',               '标签',      140, 'left'),
    ('size',               '大小',      85,  'center'),
    ('status',             '状态',      60,  'center'),
    ('duration',           '时长',      80,  'center'),
    ('resolution',         '分辨率',    110, 'center'),
    ('file_created_time',  '创建时间',  140, 'left'),
    ('source_folder',      '所在文件夹', 200, 'left'),
]

# 排序字段映射（列标识 → SQL 列名，确保走索引）
SORT_MAPPING = {
    'title': 'title',
    'stars': 'stars',
    'tags': 'tags',
    'size': 'file_size',
    'status': 'is_nas_online',
    'duration': 'duration',
    'resolution': 'resolution',
    'file_created_time': 'file_created_time',
    'source_folder': 'source_folder',
}

DEFAULT_PAGE_SIZE = 300


class VideoTableModel(QAbstractTableModel):
    """分页视频模型。

    数据由 set_page 注入（list[tuple]，顺序与 FIELD_INDEX 一致）。
    """

    def __init__(self, parent=None, page_size=DEFAULT_PAGE_SIZE):
        super().__init__(parent)
        self._page = []                 # 当前页 list[tuple]
        self._page_size = page_size
        self._total_count = 0           # 总行数（分页总数）
        self._current_page_no = 0       # 当前页码（0-based）

        # 列定义
        self._col_keys = [c[0] for c in DISPLAY_COLUMNS]
        self._col_titles = [c[1] for c in DISPLAY_COLUMNS]
        self._col_widths = {c[0]: c[2] for c in DISPLAY_COLUMNS}
        self._col_align = {c[0]: c[3] for c in DISPLAY_COLUMNS}

    # ---- QAbstractTableModel 必需 ----
    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._page)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self._col_keys)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self._page[index.row()]
        col_key = self._col_keys[index.column()]
        raw = self._field(row, col_key)

        if role == Qt.DisplayRole:
            return self._display_text(col_key, raw, row)
        if role == Qt.UserRole:
            return row[FIELD_INDEX['id']]
        if role == Qt.TextAlignmentRole:
            return int(Qt.AlignCenter) if self._col_align[col_key] == 'center' \
                else int(Qt.AlignLeft | Qt.AlignVCenter)
        if role == Qt.ForegroundRole:
            return self._foreground(col_key, raw)
        if role == Qt.ToolTipRole:
            if col_key == 'title':
                return row[FIELD_INDEX['file_path']] or row[FIELD_INDEX['file_name']]
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            if 0 <= section < len(self._col_titles):
                return self._col_titles[section]
        return None

    # ---- 数据注入 ----
    def set_page(self, page_rows, total_count, page_no):
        self.beginResetModel()
        self._page = list(page_rows)
        self._total_count = total_count
        self._current_page_no = page_no
        self.endResetModel()

    def clear(self):
        self.beginResetModel()
        self._page = []
        self._total_count = 0
        self._current_page_no = 0
        self.endResetModel()

    def row_at(self, row_index: int):
        if 0 <= row_index < len(self._page):
            return self._page[row_index]
        return None

    def video_id_at(self, row_index: int):
        row = self.row_at(row_index)
        return row[FIELD_INDEX['id']] if row else None

    # ---- 属性 ----
    @property
    def column_keys(self):
        return list(self._col_keys)

    @property
    def column_widths(self):
        return dict(self._col_widths)

    @property
    def page_size(self):
        return self._page_size

    @property
    def total_count(self):
        return self._total_count

    @property
    def current_page_no(self):
        return self._current_page_no

    # ---- 格式化 ----
    def _field(self, row, col_key):
        if col_key == 'size':
            return row[FIELD_INDEX['file_size']]
        if col_key == 'status':
            return row[FIELD_INDEX['is_nas_online']]
        if col_key == 'source_folder':
            return row[FIELD_INDEX['source_folder']]
        if col_key in FIELD_INDEX:
            return row[FIELD_INDEX[col_key]]
        return None

    def _display_text(self, col_key, raw, row):
        if col_key == 'title':
            return raw or row[FIELD_INDEX['file_name']] or ""
        if col_key == 'stars':
            return int(raw) if raw else 0
        if col_key == 'tags':
            return raw or ""
        if col_key == 'size':
            return self._fmt_size(raw)
        if col_key == 'status':
            return "在线" if raw else "离线"
        if col_key == 'duration':
            return self._fmt_duration(raw)
        if col_key == 'resolution':
            return raw or ""
        if col_key == 'file_created_time':
            return self._fmt_datetime(raw)
        if col_key == 'source_folder':
            return self._short_folder(raw)
        return str(raw) if raw is not None else ""

    def _fmt_size(self, size):
        if not size:
            return ""
        try:
            s = float(size)
            for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
                if s < 1024:
                    return f"{s:.1f} {unit}"
                s /= 1024
            return f"{s:.1f} PB"
        except Exception:
            return str(size)

    def _fmt_duration(self, seconds):
        if not seconds:
            return ""
        try:
            sec = int(seconds)
            h, rem = divmod(sec, 3600)
            m, s = divmod(rem, 60)
            return f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"
        except Exception:
            return str(seconds)

    def _fmt_datetime(self, dt):
        if not dt:
            return ""
        try:
            return str(dt)[:19].replace('T', ' ')
        except Exception:
            return str(dt)

    def _short_folder(self, folder):
        """文件夹路径简化：取最后 1-2 段，避免过长。"""
        if not folder:
            return ""
        parts = folder.rstrip('/').rstrip('\\').replace('\\', '/').split('/')
        if len(parts) >= 2:
            return '.../' + parts[-1]
        return folder

    def _foreground(self, col_key, raw):
        from pyside_v2.theme import current
        if col_key == 'status':
            c = current()
            return c.online if raw else c.offline
        return None
