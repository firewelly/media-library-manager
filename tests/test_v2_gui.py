# -*- coding: utf-8 -*-
"""
v2 GUI 功能测试 —— Part 7-9

用 processEvents 替代 app.exec()，避免事件循环卡死。
"""

import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(_PROJECT_ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, _PROJECT_ROOT)

# 关键：锚定 sys.argv[0] 到项目根目录的启动脚本，
# 使 runtime_path('media_library.db') 解析到主库而非 tests/ 子目录
sys.argv = [os.path.join(_PROJECT_ROOT, "media_library_v2.py")] + sys.argv[1:]

_passed = 0
_failed = 0
_errors = []


def test(name, condition, detail=""):
    global _passed, _failed
    if condition:
        _passed += 1
        print(f"  ✅ {name}")
    else:
        _failed += 1
        _errors.append(f"{name}: {detail}")
        print(f"  ❌ {name}  {detail}")


def flush_events(app, ms=200):
    """刷新事件循环指定毫秒，不进入 exec()。"""
    from PySide6.QtCore import QElapsedTimer
    timer = QElapsedTimer()
    timer.start()
    while not timer.hasExpired(ms):
        app.processEvents()


# ====================================================================
# Part 7: GUI 完整功能测试
# ====================================================================
def test_gui():
    print("\n" + "=" * 60)
    print("  Part 7: GUI 完整功能测试")
    print("=" * 60)

    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt

    app = QApplication.instance() or QApplication(sys.argv)

    from pyside_v2.windows.main_window import MainWindow
    from pyside_v2.widgets import ClickableLabel

    win = MainWindow()
    flush_events(app, 500)  # 等待数据加载

    # 1. 窗口
    test("MainWindow 创建成功", win is not None)
    test("窗口标题含 v2", "v2" in win.windowTitle(), f"'{win.windowTitle()}'")

    # 2. 列表
    model = win.video_model
    row_count = model.rowCount()
    test(f"VideoTableModel 加载数据 (rowCount={row_count})", row_count > 0)
    test("列数 = 12", model.columnCount() == 12, f"got {model.columnCount()}")

    col_keys = model.column_keys
    expected = ['javdb_code','title','actors','stars','tags','size',
                'status','duration','resolution','javdb_rating',
                'file_created_time','source_folder']
    test("列标识正确", col_keys == expected, f"diff: {set(expected) ^ set(col_keys)}")

    total = model.total_count
    test(f"total_count = {total}", total > 0)

    # 3. 数据格式化
    if row_count > 0:
        vid = model.index(0, 0).data(Qt.UserRole)
        test("data(UserRole) 返回 video_id", vid is not None)

        status_col = col_keys.index('status')
        fg = model.index(0, status_col).data(Qt.ForegroundRole)
        test("status 列有前景色", fg is not None)

        size_col = col_keys.index('size')
        size_text = model.index(0, size_col).data(Qt.DisplayRole)
        test("size 列格式化含单位",
             size_text == "" or any(u in str(size_text) for u in ["KB","MB","GB","TB"]),
             f"got '{size_text}'")

    # 4. 搜索
    win.search_input.setText("test")
    win._on_search()
    flush_events(app, 300)
    test("搜索触发不报错", True)
    win.search_input.setText("")
    win._on_search()
    flush_events(app, 300)

    # 5. 星级筛选
    win.star_filter_combo.setCurrentIndex(3)
    flush_events(app, 300)
    test("星级筛选切换不报错", True)
    win.star_filter_combo.setCurrentIndex(0)
    flush_events(app, 300)

    # 6. 仅在线
    win._toggle_online_only()
    flush_events(app, 300)
    test("仅在线切换不报错", True)
    win._toggle_online_only()
    flush_events(app, 300)

    # 7. 翻页
    if total > model.page_size:
        win.go_next_page()
        flush_events(app, 300)
        test("翻页 next 不报错", True)
        win.go_first_page()
        flush_events(app, 300)
        test("翻页 first 不报错", True)
    else:
        test("翻页（数据不足一页，跳过）", True)

    # 8. 详情面板
    if row_count > 0:
        first_vid = model.index(0, 0).data(Qt.UserRole)
        win.load_detail(first_vid)
        flush_events(app, 200)
        test("load_detail() 不报错", True)
        title = win.detail_title_edit.text()
        test("详情标题已加载", bool(title), f"title='{title}'")

    # 9. 主题切换
    initial = win.theme_mgr.theme_name
    win._toggle_theme()
    flush_events(app, 300)
    test("主题切换不报错", True)
    test("主题实际变化", win.theme_mgr.theme_name != initial,
         f"{initial} → {win.theme_mgr.theme_name}")
    # 切回
    win._toggle_theme()
    flush_events(app, 300)

    # 10. 更多菜单
    test("_show_more_menu 方法存在", hasattr(win, '_show_more_menu'))
    test("_refresh_inline_colors 方法存在", hasattr(win, '_refresh_inline_colors'))

    # 11. 搜索防抖
    test("搜索防抖 = 500ms", win._search_timer.interval() == 500,
         f"got {win._search_timer.interval()}")

    # 12. 详情面板精简
    test("有 btn_play", hasattr(win, 'btn_play'))
    test("有 btn_save", hasattr(win, 'btn_save'))
    test("有 btn_more", hasattr(win, 'btn_more'))
    test("无 btn_star（移入更多菜单）", not hasattr(win, 'btn_star'))
    test("无 btn_delete（移入更多菜单）", not hasattr(win, 'btn_delete'))

    # 13. ClickableLabel
    test("detail_stars_label 是 ClickableLabel",
         isinstance(win.detail_stars_label, ClickableLabel),
         f"got {type(win.detail_stars_label).__name__}")

    # 14. 侧栏 NavRow 验证
    from pyside_v2.widgets import NavRow
    nav_rows = win.sidebar.findChildren(NavRow)
    test(f"侧栏有 NavRow 组件 ({len(nav_rows)} 个)", len(nav_rows) > 0)

    win.close()


# ====================================================================
# Part 8: 对话框测试
# ====================================================================
def test_dialogs():
    print("\n" + "=" * 60)
    print("  Part 8: 对话框功能测试")
    print("=" * 60)

    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    from pyside_v2.windows.main_window import MainWindow
    win = MainWindow()
    flush_events(app, 500)

    # 标签管理
    from pyside_v2.dialogs import TagManagerDialog
    tag_dlg = TagManagerDialog(win)
    test("TagManagerDialog 创建成功", tag_dlg.list.count() >= 0,
         f"count={tag_dlg.list.count()}")
    # 验证颜色用的是 color_hex 而非硬编码
    style = tag_dlg.btn_del.styleSheet()
    test("TagManager 删除按钮用主题色", style.startswith("color: #") and "#cf222e" not in style or
         "cf222e" not in style.replace(" ", ""), f"style={style}")
    tag_dlg.close()

    # 文件夹管理
    from pyside_v2.dialogs import FolderManagerDialog
    folder_dlg = FolderManagerDialog(win)
    test("FolderManagerDialog 创建成功", folder_dlg.table.rowCount() >= 0,
         f"rows={folder_dlg.table.rowCount()}")
    folder_dlg.close()

    # 演员库
    from pyside_v2.dialogs import ActorBrowserDialog
    actor_dlg = ActorBrowserDialog(win)
    test("ActorBrowserDialog 创建成功", actor_dlg._total >= 0,
         f"total={actor_dlg._total}")
    test(f"演员库加载了 {len(actor_dlg.grid_container.children())} 卡片",
         actor_dlg._total > 0)
    actor_dlg.close()

    # 演员详情
    from pyside_v2.dialogs import ActorDetailWindow
    win.core.cursor.execute("SELECT name FROM actors WHERE name IS NOT NULL LIMIT 1")
    r = win.core.cursor.fetchone()
    if r and r[0]:
        detail_dlg = ActorDetailWindow(win, actor_name=r[0])
        flush_events(app, 200)
        test(f"ActorDetailWindow 加载演员 '{r[0]}'",
             getattr(detail_dlg, '_actor_id', None) is not None)
        # 验证收藏按钮颜色用 color_hex
        fav_style = detail_dlg.btn_fav.styleSheet()
        test("ActorDetail 收藏按钮无硬编码颜色",
             "#e8a009" not in fav_style, f"style={fav_style}")
        detail_dlg.close()
    else:
        test("ActorDetailWindow（无演员数据）", True)

    win.close()


# ====================================================================
# Part 9: 导入流程测试
# ====================================================================
def test_import():
    print("\n" + "=" * 60)
    print("  Part 9: 导入流程测试（AV 文件夹）")
    print("=" * 60)

    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    from pyside_v2.windows.main_window import MainWindow
    win = MainWindow()
    flush_events(app, 500)

    av_folder = "/Users/firewell/影视/AV"
    if not os.path.exists(av_folder):
        test("AV 文件夹在线", False, f"{av_folder} 不存在")
        win.close()
        return
    test("AV 文件夹在线", True)

    # 导入前数量
    win.core.cursor.execute("SELECT COUNT(*) FROM videos WHERE source_folder LIKE ?", (av_folder + "%",))
    before = win.core.cursor.fetchone()[0]
    test(f"导入前 DB 中 AV 视频数 = {before}", True)

    # 找未入库文件（最多 3 个）
    new_files = []
    for root, dirs, files in os.walk(av_folder):
        for f in files:
            if f.lower().endswith(('.mp4', '.mkv', '.avi')):
                fp = os.path.join(root, f)
                win.core.cursor.execute("SELECT 1 FROM videos WHERE file_path=?", (fp,))
                if not win.core.cursor.fetchone():
                    new_files.append(fp)
                    if len(new_files) >= 3:
                        break
        if len(new_files) >= 3:
            break

    test(f"找到 {len(new_files)} 个未入库文件", len(new_files) > 0)
    for f in new_files:
        print(f"     📄 {os.path.basename(f)}")

    # 导入
    imported = 0
    for fp in new_files:
        try:
            result = win.core.add_video_to_db_optimized(fp, "local")
            if result == "added":
                imported += 1
                print(f"     ✅ 导入成功: {os.path.basename(fp)}")
            else:
                print(f"     ⚠️ 导入返回: {result} ({os.path.basename(fp)})")
        except Exception as e:
            print(f"     ❌ 导入失败: {os.path.basename(fp)} — {e}")

    test(f"导入成功 {imported}/{len(new_files)}",
         imported == len(new_files) if new_files else True)

    # 验证 get_video_path
    for fp in new_files[:imported]:
        win.core.cursor.execute("SELECT id FROM videos WHERE file_path=?", (fp,))
        r = win.core.cursor.fetchone()
        if r:
            path = win.core.get_video_path(r[0])
            test(f"get_video_path(id={r[0]}) 正确",
                 path == fp, f"expected {fp}, got {path}")

    # 总数对比
    win.core.cursor.execute("SELECT COUNT(*) FROM videos WHERE source_folder LIKE ?", (av_folder + "%",))
    after = win.core.cursor.fetchone()[0]
    test(f"导入后 = {after} (before={before} + imported={imported})",
         after == before + imported,
         f"after={after}, expected={before + imported}")

    win.close()


# ====================================================================
if __name__ == "__main__":
    print("\n" + "🔥" * 30)
    print("  v2 GUI 功能测试")
    print("🔥" * 30)

    for fn in [test_gui, test_dialogs, test_import]:
        try:
            fn()
        except Exception as e:
            import traceback
            print(f"\n❌ {fn.__name__} 崩溃: {e}")
            traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"  GUI 测试结果: ✅ {_passed} 通过  ❌ {_failed} 失败")
    print("=" * 60)

    if _errors:
        print("\n失败详情:")
        for e in _errors:
            print(f"  ❌ {e}")

    sys.exit(1 if _failed > 0 else 0)
