# -*- coding: utf-8 -*-
"""
v2 GUI 可视化冒烟测试 —— 启动真实窗口，截图验证界面渲染。

截图内容：
    1. 主窗口 light 主题（列表 + 侧栏 + 详情面板）
    2. 主窗口 dark 主题
    3. 详情面板「更多」菜单展开
"""

import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(_PROJECT_ROOT)
sys.argv = [os.path.join(_PROJECT_ROOT, "media_library_v2.py")]
sys.path.insert(0, _PROJECT_ROOT)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, Qt

app = QApplication(sys.argv)

from pyside_v2.windows.main_window import MainWindow

win = MainWindow()
win.resize(1400, 900)
win.show()

# 等待数据加载
def step1_load():
    """截图 1：light 主题主界面"""
    print("📸 截图 1: light 主题主界面")
    win.grab().save("/tmp/v2_smoke_light.png")
    # 选中第一行触发详情面板加载
    if win.video_model.rowCount() > 0:
        win.video_table.selectRow(0)
    QTimer.singleShot(500, step2_detail)

def step2_detail():
    """截图 2：详情面板已加载"""
    print("📸 截图 2: 详情面板已加载")
    win.grab().save("/tmp/v2_smoke_detail.png")
    # 切换 dark 主题
    win._toggle_theme()
    QTimer.singleShot(500, step3_dark)

def step3_dark():
    """截图 3：dark 主题"""
    print("📸 截图 3: dark 主题")
    win.grab().save("/tmp/v2_smoke_dark.png")
    # 打开「更多」菜单
    QTimer.singleShot(300, step4_more_menu)

def step4_more_menu():
    """截图 4：更多菜单"""
    print("📸 截图 4: 更多菜单展开")
    # 模拟点击更多按钮
    btn = win.btn_more
    from PySide6.QtCore import QPoint
    QMenu = __import__("PySide6.QtWidgets", fromlist=["QMenu"]).QMenu
    # 直接调用 _show_more_menu
    win._show_more_menu()
    QTimer.singleShot(500, step5_actor_browser)

def step5_actor_browser():
    """截图 5：演员库对话框"""
    print("📸 截图 5: 演员库对话框")
    from pyside_v2.dialogs import ActorBrowserDialog
    dlg = ActorBrowserDialog(win)
    dlg.resize(900, 600)
    dlg.show()
    QTimer.singleShot(800, lambda: (dlg.grab().save("/tmp/v2_smoke_actors.png"), dlg.close(),
                                     QTimer.singleShot(300, step6_tag_manager)))

def step6_tag_manager():
    """截图 6：标签管理对话框"""
    print("📸 截图 6: 标签管理对话框")
    from pyside_v2.dialogs import TagManagerDialog
    dlg = TagManagerDialog(win)
    dlg.show()
    QTimer.singleShot(500, lambda: (dlg.grab().save("/tmp/v2_smoke_tags.png"), dlg.close(),
                                     QTimer.singleShot(300, finish)))

def finish():
    print("✅ 冒烟测试截图完成")
    print("截图保存到:")
    for name in ["light", "detail", "dark", "actors", "tags"]:
        path = f"/tmp/v2_smoke_{name}.png"
        if os.path.exists(path):
            size = os.path.getsize(path)
            print(f"  📷 /tmp/v2_smoke_{name}.png ({size//1024}KB)")
    win.close()
    app.quit()

# 启动
QTimer.singleShot(1000, step1_load)
app.exec()
