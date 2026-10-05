# -*- coding: utf-8 -*-
"""
库统计面板 —— 总量卡片 + 星级/年份/标签/文件夹分布横条图。

纯查询 + 自绘 BarRow（paintEvent 画 accent 圆角条），无第三方依赖。
数据量大时标签统计在后台线程完成（拉 tags 单列 ~几 MB 可接受）。
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QScrollArea,
    QGridLayout, QPushButton,
)
from PySide6.QtCore import Qt, QRectF, QThread, Signal
from PySide6.QtGui import QPainter, QColor, QFont

from pyside_v2.theme import current, color_hex


def _fmt_size(size):
    if not size:
        return "0 B"
    try:
        s = float(size)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if s < 1024:
                return f"{s:.1f} {unit}"
            s /= 1024
        return f"{s:.1f} PB"
    except Exception:
        return str(size)


class BarRow(QWidget):
    """一行横条：标签 + 圆角条 + 数值。"""

    def __init__(self, label, value_text, ratio, parent=None):
        super().__init__(parent)
        self._label = str(label)
        self._value = str(value_text)
        self._ratio = max(0.0, min(1.0, float(ratio or 0)))
        self.setFixedHeight(22)
        self.setToolTip(f"{self._label}: {self._value}")

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        c = current()
        w, h = self.width(), self.height()
        label_w = min(150, int(w * 0.3))
        value_w = 64
        bar_rect = QRectF(label_w + 6, 6, w - label_w - value_w - 12, h - 12)

        # 底槽
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(c.bg_active))
        p.drawRoundedRect(bar_rect, 5, 5)
        # 数值条
        if self._ratio > 0:
            fill = QRectF(bar_rect.left(), bar_rect.top(),
                          max(bar_rect.width() * self._ratio, 6), bar_rect.height())
            p.setBrush(QColor(c.accent))
            p.drawRoundedRect(fill, 5, 5)
        # 文本
        p.setPen(QColor(c.text_2))
        f = QFont(); f.setPointSize(9)
        p.setFont(f)
        p.drawText(QRectF(0, 0, label_w, h), Qt.AlignRight | Qt.AlignVCenter, self._label)
        p.setPen(QColor(c.text_1))
        p.drawText(QRectF(w - value_w, 0, value_w, h), Qt.AlignLeft | Qt.AlignVCenter, self._value)
        p.end()


class StatsWorker(QThread):
    """后台统计查询（避免 49k 行标签扫描阻塞 UI）。"""

    # object 而非 dict：Signal(dict) 跨线程 emit 有 C++ 转换问题
    ready = Signal(object)
    failed = Signal(str)

    def __init__(self, core, parent=None):
        super().__init__(parent)
        self.core = core

    def run(self):
        try:
            cur = self.core.conn.cursor()
            out = {}
            cur.execute("SELECT COUNT(*), COALESCE(SUM(file_size),0), "
                        "COALESCE(SUM(is_nas_online),0) FROM videos")
            out["total"], out["size"], out["online"] = cur.fetchone()
            cur.execute("SELECT COUNT(*) FROM actors")
            out["actors"] = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM tags")
            out["tags"] = cur.fetchone()[0]

            cur.execute("SELECT stars, COUNT(*) FROM videos GROUP BY stars ORDER BY stars")
            out["stars"] = cur.fetchall()

            cur.execute("SELECT year, COUNT(*) FROM videos WHERE year IS NOT NULL "
                        "GROUP BY year ORDER BY COUNT(*) DESC LIMIT 10")
            out["years"] = cur.fetchall()

            # 标签：Python 端拆 CSV
            cur.execute("SELECT tags FROM videos WHERE tags IS NOT NULL AND tags != ''")
            tag_counter = {}
            for (csv,) in cur.fetchall():
                for t in csv.split(","):
                    t = t.strip()
                    if t:
                        tag_counter[t] = tag_counter.get(t, 0) + 1
            out["tags_top"] = sorted(tag_counter.items(), key=lambda kv: -kv[1])[:15]

            cur.execute("SELECT source_folder, COUNT(*), COALESCE(SUM(file_size),0) "
                        "FROM videos WHERE source_folder IS NOT NULL AND source_folder != '' "
                        "GROUP BY source_folder ORDER BY SUM(file_size) DESC LIMIT 8")
            out["folders"] = cur.fetchall()
            cur.close()
            self.ready.emit(out)
        except Exception as e:
            self.failed.emit(str(e))


class StatsDialog(QDialog):
    """库统计面板。"""

    def __init__(self, main_window, parent=None):
        super().__init__(parent or main_window)
        self.mw = main_window
        self.core = main_window.core
        self.setWindowTitle("库统计")
        self.resize(680, 640)
        self._setup_ui()
        self._worker = StatsWorker(self.core, self)
        self._worker.ready.connect(self._render)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    # ------------------------------------------------------------------
    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        self.body = QWidget()
        self.body_lay = QVBoxLayout(self.body)
        self.body_lay.setContentsMargins(4, 4, 4, 4)
        self.body_lay.setSpacing(14)
        scroll.setWidget(self.body)
        outer.addWidget(scroll, 1)

        # 等待提示
        self.waiting = QLabel("⏳ 统计中…")
        self.waiting.setAlignment(Qt.AlignCenter)
        self.body_lay.addWidget(self.waiting)
        self.body_lay.addStretch()

        close_row = QHBoxLayout()
        close_row.addStretch()
        btn = QPushButton("关闭")
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(self.accept)
        close_row.addWidget(btn)
        outer.addLayout(close_row)

    def _clear_body(self):
        while self.body_lay.count():
            item = self.body_lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _on_failed(self, msg):
        self.waiting.setText(f"❌ 统计失败: {msg}")

    # ------------------------------------------------------------------
    def _render(self, d):
        self._clear_body()

        # ---- 顶部卡片 ----
        cards = QWidget()
        grid = QGridLayout(cards)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(8)
        offline = d["total"] - d["online"]
        cells = [
            ("视频总数", f"{d['total']:,}"),
            ("库容量", _fmt_size(d["size"])),
            ("在线", f"{d['online']:,}"),
            ("离线", f"{offline:,}"),
            ("演员", f"{d['actors']:,}"),
            ("标签", f"{d['tags']:,}"),
        ]
        for i, (k, v) in enumerate(cells):
            cell = QLabel(f"<div style='font-size:17px; font-weight:700;'>{v}</div>"
                          f"<div style='font-size:11px;'>{k}</div>")
            cell.setAlignment(Qt.AlignCenter)
            cell.setStyleSheet(
                f"background: palette(base); border: 1px solid palette(midlight);"
                f"border-radius: 8px; padding: 10px 6px;")
            grid.addWidget(cell, i // 3, i % 3)
        self.body_lay.addWidget(cards)

        # ---- 分布区 ----
        def add_section(title, rows, fmt_label=lambda k: str(k), fmt_value=lambda c, extra=None: f"{c:,}"):
            if not rows:
                return
            head = QLabel(title)
            head.setStyleSheet("font-size: 13px; font-weight: 600; color: palette(text);")
            self.body_lay.addWidget(head)
            max_v = max((r[1] for r in rows), default=1) or 1
            for r in rows:
                key, count = r[0], r[1]
                extra = r[2] if len(r) > 2 else None
                ratio = count / max_v
                self.body_lay.addWidget(BarRow(
                    fmt_label(key), fmt_value(count, extra), ratio))

        add_section("星级分布", d["stars"],
                    fmt_label=lambda s: "未评分" if not s else "★" * int(s))
        add_section("年份 Top 10", d["years"])
        add_section("标签 Top 15", d["tags_top"])
        add_section("文件夹分布（按容量 Top 8）", d["folders"],
                    fmt_label=lambda p: p.rstrip("/").split("/")[-1] if p else "—",
                    fmt_value=lambda cnt, size: f"{cnt} 个 · {_fmt_size(size)}")

        self.body_lay.addStretch()
