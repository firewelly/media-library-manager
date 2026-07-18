# -*- coding: utf-8 -*-
"""
星级 delegate - 用浅色金黄色绘制 5 星（实心/空心）。

用户指定：星级用浅色金黄色（Palette.STAR = #C5A572 哑光香槟金）。
这是 Normcore 框架内唯一的小破例暖色，仅用于星级符号。
"""

from PySide6.QtWidgets import QStyledItemDelegate
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QColor, QPolygonF
from PySide6.QtCore import QPointF

from pyside_v2.theme import current


def draw_star(painter: QPainter, cx: float, cy: float, size: float, color: QColor, filled: bool):
    """画一颗五角星（cx,cy 中心；size 外接圆半径）。"""
    # 五角星 10 个顶点（外圆/内圆交替），顶点朝上
    import math
    points = []
    for i in range(10):
        angle = math.radians(-90 + i * 36)
        r = size if i % 2 == 0 else size * 0.42
        points.append(QPointF(cx + r * math.cos(angle), cy + r * math.sin(angle)))
    poly = QPolygonF(points)
    if filled:
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        painter.drawPolygon(poly)
    else:
        painter.setBrush(Qt.NoBrush)
        pen = painter.pen()
        pen.setColor(color)
        pen.setWidthF(1.0)
        painter.setPen(pen)
        painter.drawPolygon(poly)


class StarDelegate(QStyledItemDelegate):
    """星级列 delegate：单元格 data 返回 0-5 的整数（DisplayRole）。"""

    def paint(self, painter, option, index):
        rating = index.data(Qt.DisplayRole)
        try:
            rating = int(rating) if rating is not None else 0
        except (TypeError, ValueError):
            rating = 0

        painter.save()
        c = current()
        rect = option.rect
        star_size = min(rect.height() * 0.35, 7)   # 星半径
        gap = star_size * 2.4
        total_w = 5 * gap - (gap - star_size * 2)
        start_x = rect.center().x() - total_w / 2 + star_size
        cy = rect.center().y()

        for i in range(5):
            cx = start_x + i * gap
            if i < rating:
                draw_star(painter, cx, cy, star_size, c.star_on, filled=True)
            else:
                draw_star(painter, cx, cy, star_size, c.star_off, filled=True)

        painter.restore()

    def sizeHint(self, option, index):
        return option.rect.size() if option.rect.isValid() else self.parent().sizeHintForIndex(index)
