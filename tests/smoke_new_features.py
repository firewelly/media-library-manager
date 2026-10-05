# -*- coding: utf-8 -*-
"""v2 新功能冒烟截图 —— 封面墙(亮/暗)/设置/统计面板。"""

import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(_PROJECT_ROOT)
sys.argv = [os.path.join(_PROJECT_ROOT, "media_library_v2.py")]
sys.path.insert(0, _PROJECT_ROOT)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, QElapsedTimer

app = QApplication(sys.argv)

from pyside_v2.windows.main_window import MainWindow

win = MainWindow()
win.resize(1400, 900)
win.show()


def wait_for(app, condition, timeout_ms=30000):
    t = QElapsedTimer()
    t.start()
    while not t.hasExpired(timeout_ms):
        app.processEvents()
        try:
            if condition():
                return True
        except Exception:
            pass
    return False


def step1():
    print("⏳ 等待首屏数据…")
    wait_for(app, lambda: win.video_model.rowCount() > 0)
    # 等详情面板封面
    wait_for(app, lambda: win._current_video_id is not None, 5000)
    QTimer.singleShot(500, step2_cover)


def step2_cover():
    print("📸 截图 1: 封面墙（亮色）")
    win._switch_view(1)
    wait_for(app, lambda: len(win.cover_model._pixmaps) > 0, 30000)
    QTimer.singleShot(600, step3_dark_cover)


def step3_dark_cover():
    win.grab().save("/tmp/v2_new_cover_light.png")
    print("📸 截图 2: 封面墙（暗色）")
    win._toggle_theme()
    QTimer.singleShot(600, step4_stats)


def step4_stats():
    win.grab().save("/tmp/v2_new_cover_dark.png")
    print("📸 截图 3: 统计面板")
    win._toggle_theme()  # 切回亮色
    from pyside_v2.dialogs.stats import StatsDialog
    global stats
    stats = StatsDialog(win)
    stats.resize(680, 640)
    stats.show()
    wait_for(app, lambda: stats.body_lay.count() > 2, 30000)
    QTimer.singleShot(500, step5_settings)


def step5_settings():
    stats.grab().save("/tmp/v2_new_stats.png")
    stats.close()
    print("📸 截图 4: 设置对话框")
    from pyside_v2.dialogs.settings import SettingsDialog
    dlg = SettingsDialog(win)
    dlg.show()
    QTimer.singleShot(500, finish)


def finish():
    from PySide6.QtWidgets import QApplication as QA
    for w in QA.allWidgets():
        if isinstance(w, SettingsDialogCompat):
            w.grab().save("/tmp/v2_new_settings.png")
            w.close()
    print("✅ 完成")
    for name in ["cover_light", "cover_dark", "stats", "settings"]:
        p = f"/tmp/v2_new_{name}.png"
        if os.path.exists(p):
            print(f"  📷 {p} ({os.path.getsize(p)//1024}KB)")
    win.close()
    app.quit()


class SettingsDialogCompat:
    pass


from pyside_v2.dialogs.settings import SettingsDialog as _SD
SettingsDialogCompat = _SD

QTimer.singleShot(800, step1)
app.exec()
