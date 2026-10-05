# -*- coding: utf-8 -*-
"""
封面墙视图 —— 2:3 竖版封面网格（对齐 ui_design/index.html 封面墙设计意图）。

结构：
    CoverModel(QAbstractListModel)   当前页行数据 + id→QPixmap 缩略图表
    CoverDelegate(QStyledItemDelegate)  绘制封面/番号条/五星/骨架占位
    CoverWallView(QListView)         网格布局 + 信号转发
    ThumbnailWorker(QThread)         后台批量取 thumbnail_data 并解码

数据流（MainWindow 驱动）：
    load_videos 完成 → cover_model.set_page(rows)
    → 视图可见时 load_thumbnails(ids) 后台解码 → pixmaps_ready → set_pixmaps
"""

from PySide6.QtCore import Qt, QAbstractListModel, QModelIndex, QRectF, QPointF, QThread, Signal
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QFontMetrics
from PySide6.QtWidgets import QListView, QStyledItemDelegate, QAbstractItemView, QStyle

from pyside_v2.theme import current, Tokens
from pyside_v2.widgets.star_delegate import draw_star

CARD_W = 160          # 卡片宽（封面显示宽）
CARD_H = int(160 / Tokens.COVER_RATIO) + 34   # 封面高 + 番号条高
THUMB_W = 320         # 解码目标宽（2x 供缩放平滑）


class CoverModel(QAbstractListModel):
    """封面墙数据模型。

    行数据为 VideoTableModel 同源的 16 元组（FIELD_INDEX 对齐），
    仅取 id/javdb_code/file_name/title/stars 渲染；缩略图按 id 懒注入。
    """

    ID = 0
    CODE = 14
    TITLE = 3
    FILE_NAME = 2
    STARS = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows = []
        self._pixmaps = {}   # video_id -> QPixmap

    # ---- QAbstractListModel ----
    def rowCount(self, parent=QModelIndex()):
        return len(self._rows)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._rows)):
            return None
        row = self._rows[index.row()]
        if role == Qt.UserRole:
            return row[self.ID]
        if role == Qt.DecorationRole:
            return self._pixmaps.get(row[self.ID])
        if role == Qt.DisplayRole:
            code = row[self.CODE] or ""
            title = row[self.TITLE] or row[self.FILE_NAME] or ""
            return f"{code}\n{title}"
        if role == Qt.UserRole + 1:
            return int(row[self.STARS] or 0)
        return None

    # ---- 数据注入 ----
    def set_page(self, rows):
        self.beginResetModel()
        self._rows = list(rows)
        # 保留仍在本页的缩略图，其余释放
        keep = {r[self.ID] for r in self._rows}
        self._pixmaps = {k: v for k, v in self._pixmaps.items() if k in keep}
        self.endResetModel()

    def set_pixmaps(self, pixmaps: dict):
        if not self._rows:
            return
        self._pixmaps.update(pixmaps)
        # 局部刷新（整列 DecorationRole 变化）
        self.dataChanged.emit(self.index(0, 0), self.index(len(self._rows) - 1, 0))

    def video_id_at(self, index):
        if index.isValid() and 0 <= index.row() < len(self._rows):
            return self._rows[index.row()][self.ID]
        return None


class CoverDelegate(QStyledItemDelegate):
    """封面卡片绘制：2:3 封面 + 底部番号条 + 星级。"""

    def paint(self, painter: QPainter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        c = current()
        rect = option.rect

        cover_h = int(rect.width() / Tokens.COVER_RATIO)
        cover_rect = QRectF(rect.left(), rect.top(), rect.width(), cover_h)

        selected = bool(option.state & QStyle.State_Selected)
        hovered = bool(option.state & QStyle.State_MouseOver)

        # 封面底（骨架色）
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(c.bg_skeleton))
        painter.drawRoundedRect(cover_rect, 8, 8)

        # 封面图
        pix = index.data(Qt.DecorationRole)
        if pix and not pix.isNull():
            # KeepAspectRatioByExpanding 裁剪填充
            scaled = pix.scaled(
                int(cover_rect.width()), int(cover_rect.height()),
                Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            sx = max(0, (scaled.width() - cover_rect.width()) / 2)
            sy = max(0, (scaled.height() - cover_rect.height()) / 2)
            painter.setClipRect(cover_rect)
            painter.drawPixmap(
                int(cover_rect.left() - sx), int(cover_rect.top() - sy), scaled)
            painter.setClipping(False)
        else:
            # 无封面占位
            painter.setPen(QColor(c.text_3))
            f = QFont(); f.setPointSize(11)
            painter.setFont(f)
            painter.drawText(cover_rect, Qt.AlignCenter, "无封面")

        # 选中/悬浮边框
        if selected or hovered:
            pen = painter.pen()
            pen.setColor(QColor(c.accent if selected else c.border_strong))
            pen.setWidthF(2.0 if selected else 1.0)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(cover_rect.adjusted(1, 1, -1, -1), 8, 8)

        # 底部信息条：番号 + 星级
        text = index.data(Qt.DisplayRole) or ""
        code, _, title = text.partition("\n")
        stars = index.data(Qt.UserRole + 1) or 0
        info_rect = QRectF(rect.left(), cover_rect.bottom() + 4,
                           rect.width(), rect.bottom() - cover_rect.bottom() - 4)
        painter.setPen(QColor(c.text_1 if code else c.text_3))
        f = QFont(); f.setPointSize(9); f.setBold(bool(code))
        painter.setFont(f)
        fm = QFontMetrics(f)
        code_text = code if code else "（无番号）"
        painter.drawText(info_rect, Qt.AlignLeft | Qt.AlignTop,
                         fm.elidedText(code_text, Qt.ElideRight, int(rect.width() - 46)))
        # 右侧星级（小尺寸，实心）
        if stars > 0:
            star_size = 5.0
            for i in range(stars):
                cx = rect.right() - 6 - (stars - 1 - i) * (star_size * 2.4)
                cy = info_rect.top() + 7
                draw_star(painter, cx, cy, star_size, QColor(c.star_on), filled=True)
        # 标题第二行（弱色）
        if title:
            painter.setPen(QColor(c.text_3))
            f2 = QFont(); f2.setPointSize(8)
            painter.setFont(f2)
            fm2 = QFontMetrics(f2)
            title_rect = QRectF(rect.left(), info_rect.top() + 13,
                                rect.width(), info_rect.height() - 13)
            painter.drawText(title_rect, Qt.AlignLeft | Qt.AlignTop,
                             fm2.elidedText(title, Qt.ElideRight, int(rect.width())))

        painter.restore()

    def sizeHint(self, option, index):
        from PySide6.QtCore import QSize
        return QSize(CARD_W + 8, CARD_H + 8)


class ThumbnailWorker(QThread):
    """后台批量加载缩略图：ids → {id: QPixmap}。"""

    # 注意：用 object 而非 dict——PySide6 的 Signal(dict) 跨线程 emit 时会
    # "Cannot copy-convert dict to C++"，接收槽收不到数据。
    pixmaps_ready = Signal(object)

    def __init__(self, core, ids, parent=None):
        super().__init__(parent)
        self.core = core
        self.ids = list(ids)

    def run(self):
        out = {}
        if not self.ids:
            self.pixmaps_ready.emit(out)
            return
        try:
            cur = self.core.conn.cursor()
            placeholders = ",".join("?" * len(self.ids))
            cur.execute(
                f"SELECT id, thumbnail_data FROM videos WHERE id IN ({placeholders})",
                self.ids)
            for vid, blob in cur.fetchall():
                if blob:
                    pix = QPixmap()
                    if pix.loadFromData(blob):
                        out[vid] = pix.scaled(
                            THUMB_W, int(THUMB_W / Tokens.COVER_RATIO),
                            Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            cur.close()
        except Exception:
            pass
        self.pixmaps_ready.emit(out)


class CoverWallView(QListView):
    """封面墙网格视图。

    向上信号（与 VideoTableView 对齐）：
        selection_changed(video_id) / double_clicked(video_id)
    """

    selection_changed = Signal(object)
    double_clicked = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QListView.IconMode)
        self.setResizeMode(QListView.Adjust)
        self.setMovement(QListView.Static)
        # ExtendedSelection：Ctrl/Shift 多选，与表格视图行为对齐（批量右键菜单依赖）
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setUniformItemSizes(True)
        self.setSpacing(12)
        self.setWordWrap(False)
        self.setStyleSheet("QListView { background: transparent; border: none; }")
        # 右键菜单（customContextMenuRequested 由 MainWindow 接管）
        self.setContextMenuPolicy(Qt.CustomContextMenu)

    def set_model(self, model: CoverModel):
        self.setModel(model)
        self.setItemDelegate(CoverDelegate(self))

    def currentChanged(self, current, previous):
        super().currentChanged(current, previous)
        vid = current.data(Qt.UserRole) if current.isValid() else None
        self.selection_changed.emit(vid)

    def mouseDoubleClickEvent(self, event):
        idx = self.indexAt(event.pos())
        if idx.isValid():
            self.double_clicked.emit(idx.data(Qt.UserRole))
        else:
            super().mouseDoubleClickEvent(event)

    def select_video_by_id(self, video_id):
        """在封面墙中定位选中（找不到返回 False）。"""
        model = self.model()
        if not model:
            return False
        for r in range(model.rowCount()):
            if model.index(r, 0).data(Qt.UserRole) == video_id:
                self.setCurrentIndex(model.index(r, 0))
                self.scrollTo(model.index(r, 0), QAbstractItemView.PositionAtCenter)
                return True
        return False

    def selected_video_ids(self):
        """当前选中卡片的 video_id 列表（与 VideoTableView 对齐）。"""
        sm = self.selectionModel()
        if not sm:
            return []
        ids = []
        for idx in sm.selectedIndexes():
            vid = idx.data(Qt.UserRole)
            if vid is not None:
                ids.append(vid)
        return ids
