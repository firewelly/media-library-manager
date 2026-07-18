# -*- coding: utf-8 -*-
"""
封面图片异步加载
"""

import os
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QPixmap, QImage


class CoverLoaderWorker(QThread):
    """异步加载封面图片"""

    loaded = Signal(int, QPixmap)  # video_id, pixmap
    error = Signal(int, str)

    def __init__(self, video_id: int, cover_path: str = None, cover_data: bytes = None, parent=None):
        super().__init__(parent)
        self.video_id = video_id
        self.cover_path = cover_path
        self.cover_data = cover_data

    def run(self):
        try:
            pixmap = QPixmap()

            # 优先从二进制数据加载
            if self.cover_data:
                image = QImage.fromData(self.cover_data)
                if not image.isNull():
                    pixmap = QPixmap.fromImage(image)

            # 回退到文件路径
            elif self.cover_path and os.path.isfile(self.cover_path):
                pixmap.load(self.cover_path)

            if not pixmap.isNull():
                # 缩放到合适尺寸
                scaled = pixmap.scaled(
                    360, 540,  # 2:3 比例
                    aspectMode=1,  # Qt.AspectRatioMode.KeepAspectRatio
                    mode=1,  # Qt.TransformationMode.SmoothTransformation
                )
                self.loaded.emit(self.video_id, scaled)
            else:
                self.error.emit(self.video_id, "无法加载封面")

        except Exception as e:
            self.error.emit(self.video_id, str(e))
