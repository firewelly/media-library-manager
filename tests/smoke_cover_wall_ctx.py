# -*- coding: utf-8 -*-
"""封面墙交互冒烟截图 —— 右键菜单(单选/批量) + 文本时长修复 + 多选。

验证点：
    1. 封面墙单选右键菜单弹出（_build_single_menu 复用）
    2. 封面墙多选（ExtendedSelection）+ 批量右键菜单
    3. 详情面板时长："122 分鍾" 文本 → 02:02:00（不再整面板加载失败）
    4. _active_view_selected_ids 在封面墙视图下返回选中
"""

import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(_PROJECT_ROOT)
sys.argv = [os.path.join(_PROJECT_ROOT, "media_library_v2.py")]
sys.path.insert(0, _PROJECT_ROOT)

from PySide6.QtWidgets import QApplication, QMenu
from PySide6.QtCore import QTimer, QElapsedTimer, QPoint
from PySide6.QtGui import QGuiApplication

app = QApplication(sys.argv)

from pyside_v2.windows.main_window import MainWindow

win = MainWindow()
win.resize(1400, 900)
win.show()

_checks = {"pass": 0, "fail": 0}


def check(name, ok):
    _checks["pass" if ok else "fail"] += 1
    print(("  ✅ " if ok else "  ❌ ") + name)


def wait_for(condition, timeout_ms=30000):
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


def grab_screen(path):
    """整屏截图（QMenu 是独立顶层窗口，win.grab() 截不到）。"""
    app.processEvents()
    QGuiApplication.primaryScreen().grabWindow(0).save(path)
    print(f"  📷 {path} ({os.path.getsize(path)//1024}KB)")


# 找一个文本时长的视频 id（验证 "122 分鍾" → 02:02:00）
TEXT_DUR_VID = None
cur = win.core.conn.cursor()
cur.execute("SELECT id, duration FROM videos WHERE typeof(duration)='text' LIMIT 1")
r = cur.fetchone()
if r:
    TEXT_DUR_VID, TEXT_DUR_RAW = r
    print(f"文本时长样本: id={TEXT_DUR_VID} duration={TEXT_DUR_RAW!r}")


def step1():
    print("⏳ 等待首屏数据…")
    wait_for(lambda: win.video_model.rowCount() > 0)
    QTimer.singleShot(300, step2_single_menu)


def step2_single_menu():
    """封面墙单选右键菜单。"""
    print("📸 截图 1: 封面墙单选右键菜单")
    win._switch_view(1)
    wait_for(lambda: len(win.cover_model._pixmaps) > 0, 30000)
    app.processEvents()

    idx = win.cover_model.index(1, 0)
    win.cover_wall.setCurrentIndex(idx)
    vid = idx.data(0x0100)  # Qt.UserRole
    check("封面墙选中 video_id 有效", vid is not None)
    check("_active_view_selected_ids 封面墙视图生效",
          win._active_view_selected_ids() == [vid])

    global menu1
    menu1 = QMenu(win)
    win._build_single_menu(menu1, vid)
    pos = win.cover_wall.visualRect(idx).center()
    menu1.popup(win.cover_wall.viewport().mapToGlobal(pos + QPoint(30, 10)))
    QTimer.singleShot(700, step3_batch_menu)


def step3_batch_menu():
    grab_screen("/tmp/v2_ctx_cover_single.png")
    menu1.close()

    """封面墙多选 + 批量右键菜单。"""
    print("📸 截图 2: 封面墙多选 + 批量菜单")
    from PySide6.QtCore import QItemSelectionModel
    sm = win.cover_wall.selectionModel()
    sm.clearSelection()
    win.cover_wall.setCurrentIndex(win.cover_model.index(0, 0))
    # 注意顺序：先 setCurrentIndex 再 select——反过来会被 ClearAndSelect 冲掉
    for r in (0, 1, 2):
        sm.select(win.cover_model.index(r, 0), QItemSelectionModel.Select)
    app.processEvents()

    ids = win.cover_wall.selected_video_ids()
    check(f"封面墙多选 3 项（实得 {len(ids)}）", len(ids) == 3)

    global menu2
    menu2 = QMenu(win)
    win._build_batch_menu(menu2, ids, len(ids))
    pos = win.cover_wall.visualRect(win.cover_model.index(1, 0)).center()
    menu2.popup(win.cover_wall.viewport().mapToGlobal(pos + QPoint(30, 10)))
    QTimer.singleShot(700, step4_duration)


def step4_duration():
    grab_screen("/tmp/v2_ctx_cover_batch.png")
    menu2.close()

    """详情面板文本时长修复。"""
    print("📸 截图 3: 详情面板（文本时长 → HH:MM:SS）")
    if TEXT_DUR_VID is None:
        check("库中存在文本时长样本", False)
        QTimer.singleShot(100, finish)
        return
    win._switch_view(0)
    win.load_detail(TEXT_DUR_VID)
    app.processEvents()

    # 在详情区找时长值标签
    from PySide6.QtWidgets import QLabel
    dur_text = None
    for row_w in win.detail_kv_container.parentWidget().findChildren(QLabel):
        pass  # 结构嵌套，改用逐行扫描
    # 逐行扫描 kv 容器：key=时长 的同行 value
    lay = win.detail_kv_container
    for i in range(lay.count()):
        row = lay.itemAt(i).widget()
        if not row:
            continue
        labels = row.findChildren(QLabel)
        if len(labels) >= 2 and labels[0].text() == "时长":
            dur_text = labels[1].text()
            break
    import re
    check(f"时长显示为 HH:MM:SS（实得 {dur_text!r}）",
          bool(dur_text and re.fullmatch(r"\d{2}:\d{2}(:\d{2})?", dur_text)))

    # 状态栏回归：load_detail 后计数标签不应被重置（_clear_layout 已去掉重建状态栏）
    count_text = win.video_count_label.text()
    check(f"load_detail 后计数标签保留（实得 {count_text!r}）",
          count_text.endswith("个视频") and not count_text.startswith("0"))

    # 详情面板截图（截主窗口右侧即可，整窗截一张）
    QTimer.singleShot(400, finish)


def finish():
    win.grab().save("/tmp/v2_detail_text_duration.png")
    print(f"  📷 /tmp/v2_detail_text_duration.png")
    print(f"\n结果: ✅ {_checks['pass']} 通过  ❌ {_checks['fail']} 失败")
    app.exit(0 if _checks["fail"] == 0 else 1)


QTimer.singleShot(100, step1)
sys.exit(app.exec())
