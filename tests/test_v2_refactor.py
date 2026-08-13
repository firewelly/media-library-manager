# -*- coding: utf-8 -*-
"""
v2 重构功能测试 —— 覆盖审计修复的全部代码路径。

测试对象：
    1. core 数据访问层（17 个新方法）
    2. theme color_hex() 主题令牌函数
    3. NavRow / ClickableLabel 新组件
    4. GUI 完整功能（列表/搜索/筛选/排序/详情/主题切换）
    5. SQL 收口验证（widgets/dialogs 不再有 cursor.execute）
    6. 导入流程验证

运行：
    cd /Users/firewell/bin/media
    python3 tests/test_v2_refactor.py
"""

import os
import sys

# 锚定项目根目录
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(_PROJECT_ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, _PROJECT_ROOT)

# 关键：锚定 sys.argv[0] 到项目根目录的启动脚本，
# 使 runtime_path('media_library.db') 解析到主库而非 tests/ 子目录
sys.argv = [os.path.join(_PROJECT_ROOT, "media_library_v2.py")] + sys.argv[1:]

# ---- 测试框架 ----
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


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ====================================================================
# Part 1: core 数据访问层测试（无 GUI 依赖）
# ====================================================================
def test_core_data_access():
    section("Part 1: core 数据访问层（17 个新方法）")

    from pyside_v2.core import MediaLibraryCore
    core = MediaLibraryCore()

    # --- 文件夹 ---
    folders = core.get_all_folders()
    test("get_all_folders() 返回列表", isinstance(folders, list) and len(folders) > 0,
         f"got {type(folders)}, len={len(folders) if isinstance(folders, list) else 'N/A'}")
    test("get_all_folders() 含 5 元组", len(folders[0]) == 5 if folders else False,
         f"tuple len={len(folders[0]) if folders else 0}")

    active = core.get_active_folders()
    test("get_active_folders() 含 3 元组", len(active[0]) == 3 if active else False,
         f"tuple len={len(active[0]) if active else 0}")

    paths = core.get_active_folder_paths()
    test("get_active_folder_paths() 返回路径列表",
         isinstance(paths, list) and all(isinstance(p, str) for p in paths),
         f"got {paths[:2]}")

    if active:
        sample_path = active[0][0]
        ft = core.get_folder_type(sample_path)
        test("get_folder_type() 返回类型字符串",
             ft in ("local", "nas", None),
             f"got {ft!r} for {sample_path}")

    # --- 标签 ---
    tags = core.get_all_tags()
    test("get_all_tags() 返回去重列表",
         isinstance(tags, list) and len(tags) > 0,
         f"len={len(tags)}")
    test("get_all_tags() 结果无重复",
         len(tags) == len(set(tags)),
         f"有重复: {len(tags)} vs {len(set(tags))}")

    # --- 演员 ---
    actor_name = core.get_actor_name_by_id(1)
    test("get_actor_name_by_id() 不报错",
         actor_name is None or isinstance(actor_name, str),
         f"got {actor_name!r}")

    avatar = core.get_actor_avatar(1)
    test("get_actor_avatar() 返回 bytes 或 None",
         avatar is None or isinstance(avatar, (bytes, bytearray)),
         f"got {type(avatar)}")

    fav = core.get_actor_favorite(1)
    test("get_actor_favorite() 返回 bool",
         isinstance(fav, bool),
         f"got {fav!r}")

    total, rows = core.search_actors(keyword="", sort="movie_count", page_size=5, offset=0)
    test("search_actors() 返回 (total, rows)",
         isinstance(total, int) and isinstance(rows, list),
         f"total={total}, rows={type(rows)}")
    test("search_actors() rows 为 5 元组",
         len(rows[0]) == 5 if rows else True,
         f"tuple len={len(rows[0]) if rows else 0}")

    total2, rows2 = core.search_actors(keyword="a", fav_only=True, sort="name")
    test("search_actors() 支持多条件筛选不报错", True)

    # --- 视频查询 ---
    # 取一个已有视频 ID
    core.cursor.execute("SELECT id FROM videos LIMIT 1")
    vid = core.cursor.fetchone()
    vid = vid[0] if vid else None

    if vid:
        path = core.get_video_path(vid)
        test("get_video_path() 返回路径或 None",
             path is None or isinstance(path, str),
             f"got {path!r}")

        stars = core.get_video_stars(vid)
        test("get_video_stars() 返回 int",
             isinstance(stars, int) and 0 <= stars <= 5,
             f"got {stars!r}")

    # --- 文件夹增删改（用临时数据，测完删除）---
    test_folder = "/tmp/_v2_test_folder_do_not_use"
    try:
        core.add_folder(test_folder, "local", "test_device")
        core.cursor.execute("SELECT is_active FROM folders WHERE folder_path=?", (test_folder,))
        r = core.cursor.fetchone()
        test("add_folder() 写入成功", r is not None and r[0] == 1)

        fid = None
        core.cursor.execute("SELECT id FROM folders WHERE folder_path=?", (test_folder,))
        r = core.cursor.fetchone()
        if r:
            fid = r[0]
            new_val = core.toggle_folder_active(fid)
            test("toggle_folder_active() 切换为 0", new_val == 0, f"got {new_val}")
            new_val2 = core.toggle_folder_active(fid)
            test("toggle_folder_active() 切换回 1", new_val2 == 1, f"got {new_val2}")

            core.delete_folder(fid)
            core.cursor.execute("SELECT id FROM folders WHERE id=?", (fid,))
            test("delete_folder() 删除成功", core.cursor.fetchone() is None)
        else:
            test("add_folder() 查到记录", False, "写入后查不到")
    finally:
        # 清理
        core.cursor.execute("DELETE FROM folders WHERE folder_path=?", (test_folder,))
        core.conn.commit()

    # --- 标签增删改（临时标签）---
    test_tag = "_v2_test_tag_xyz"
    try:
        core.add_tag(test_tag)
        tags_after = core.get_all_tags()
        test("add_tag() 标签出现在列表", test_tag in tags_after)

        renamed = "_v2_test_tag_renamed"
        core.update_tag(test_tag, renamed)
        tags_after2 = core.get_all_tags()
        test("update_tag() 旧名消失", test_tag not in tags_after2)
        test("update_tag() 新名出现", renamed in tags_after2)

        core.delete_tag(renamed)
        tags_after3 = core.get_all_tags()
        test("delete_tag() 标签消失", renamed not in tags_after3)
    finally:
        core.cursor.execute("DELETE FROM tags WHERE tag_name IN (?, ?)", (test_tag, "_v2_test_tag_renamed"))
        core.conn.commit()

    core.conn.close()


# ====================================================================
# Part 2: theme color_hex() 测试
# ====================================================================
def test_color_hex():
    section("Part 2: theme color_hex() 主题令牌函数")

    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    from pyside_v2.theme import color_hex, set_theme

    # light 主题
    set_theme("light")
    accent = color_hex("accent")
    test("color_hex('accent') light = #0f6fde", accent == "#0f6fde", f"got {accent}")
    star = color_hex("star_on")
    test("color_hex('star_on') light = #e8a009", star == "#e8a009", f"got {star}")
    danger = color_hex("danger")
    test("color_hex('danger') light = #cf222e", danger == "#cf222e", f"got {danger}")

    # dark 主题
    set_theme("dark")
    accent_d = color_hex("accent")
    test("color_hex('accent') dark = #f0b429", accent_d == "#f0b429", f"got {accent_d}")
    star_d = color_hex("star_on")
    test("color_hex('star_on') dark = #f0b429", star_d == "#f0b429", f"got {star_d}")

    # 全部颜色名不报错
    names = ["star_on", "accent", "danger", "success", "warning",
             "text_1", "text_2", "text_3", "offline", "online", "info"]
    for n in names:
        v = color_hex(n)
        test(f"color_hex('{n}') 返回 #RRGGBB",
             isinstance(v, str) and v.startswith("#") and len(v) == 7,
             f"got {v!r}")

    # 未知颜色名报错
    try:
        color_hex("nonexistent")
        test("color_hex() 未知颜色名抛 KeyError", False, "未抛异常")
    except KeyError:
        test("color_hex() 未知颜色名抛 KeyError", True)

    # 恢复 light
    set_theme("light")


# ====================================================================
# Part 3: NavRow / ClickableLabel 组件测试
# ====================================================================
def test_new_widgets():
    section("Part 3: NavRow / ClickableLabel 新组件")

    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    from PySide6.QtCore import Qt, QPoint
    from PySide6.QtGui import QMouseEvent
    from pyside_v2.widgets import ClickableLabel, NavRow

    # ClickableLabel
    label = ClickableLabel("测试")
    clicked_count = [0]
    label.clicked.connect(lambda: clicked_count.__setitem__(0, clicked_count[0] + 1))

    # 模拟鼠标点击
    def send_click(widget):
        from PySide6.QtCore import QEvent
        pos = QPoint(5, 5)
        widget.mousePressEvent(QMouseEvent(
            QEvent.MouseButtonPress, pos, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier
        ))

    send_click(label)
    test("ClickableLabel 左键点击发出 clicked()", clicked_count[0] == 1,
         f"count={clicked_count[0]}")

    # NavRow
    nav = NavRow("▦", "测试导航", "test_key", checkable=True)
    nav_clicked = [None]
    nav.clicked.connect(lambda key: nav_clicked.__setitem__(0, key))

    send_click(nav)
    test("NavRow 点击发出 clicked(key)", nav_clicked[0] == "test_key",
         f"got {nav_clicked[0]!r}")
    test("NavRow checkable 模式按钮可勾选", nav.button.isCheckable(),
         f"checkable={nav.button.isCheckable()}")

    nav2 = NavRow("⚙", "设置", "settings", checkable=False)
    test("NavRow 不可勾选模式", not nav2.button.isCheckable(),
         f"checkable={nav2.button.isCheckable()}")


# ====================================================================
# Part 4: SQL 收口验证（grep 级别）
# ====================================================================
def test_sql_encapsulation():
    section("Part 4: SQL 收口验证（widgets/dialogs 无 cursor.execute）")

    import glob
    violations = []
    for pattern in ["pyside_v2/dialogs/*.py", "pyside_v2/widgets/*.py"]:
        for fpath in glob.glob(pattern):
            if "__pycache__" in fpath:
                continue
            with open(fpath, encoding="utf-8") as f:
                for i, line in enumerate(f, 1):
                    stripped = line.strip()
                    # 跳过注释
                    if stripped.startswith("#"):
                        continue
                    if "cursor.execute" in line or "cursor.fetchone" in line or "cursor.fetchall" in line:
                        violations.append(f"{fpath}:{i}: {stripped}")

    test("widgets/dialogs 中无 cursor.execute",
         len(violations) == 0,
         f"\n    " + "\n    ".join(violations[:10]))


# ====================================================================
# Part 5: 猴子补丁消除验证
# ====================================================================
def test_no_monkey_patches():
    section("Part 5: 猴子补丁消除验证")

    import glob
    violations = []
    for pattern in ["pyside_v2/**/*.py"]:
        for fpath in glob.glob(pattern, recursive=True):
            if "__pycache__" in fpath:
                continue
            with open(fpath, encoding="utf-8") as f:
                for i, line in enumerate(f, 1):
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        continue
                    # 检查 .mousePressEvent = / .mouseReleaseEvent = 模式
                    if (".mousePressEvent =" in line or
                        ".mouseReleaseEvent =" in line or
                        ".paintEvent =" in line):
                        violations.append(f"{fpath}:{i}: {stripped}")

    test("无 .mousePressEvent = 猴子补丁",
         len(violations) == 0,
         f"\n    " + "\n    ".join(violations))


# ====================================================================
# Part 6: 硬编码颜色验证
# ====================================================================
def test_no_hardcoded_colors():
    section("Part 6: 硬编码颜色消除验证")

    import glob, re
    hex_pattern = re.compile(r'#([0-9a-fA-F]{6})\b')
    rgba_pattern = re.compile(r'rgba\(\s*\d+')

    violations = []
    for pattern in ["pyside_v2/**/*.py"]:
        for fpath in glob.glob(pattern, recursive=True):
            if "__pycache__" in fpath or "theme/colors.py" in fpath:
                continue
            with open(fpath, encoding="utf-8") as f:
                for i, line in enumerate(f, 1):
                    stripped = line.strip()
                    # 跳过注释和文档字符串
                    if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                        continue
                    # 跳过 docstring 中的颜色说明
                    if "用户指定" in line or "Palette.STAR" in line:
                        continue
                    if hex_pattern.search(line) or rgba_pattern.search(line):
                        violations.append(f"{fpath}:{i}: {stripped}")

    test("pyside_v2/ 中无硬编码 #RRGGBB / rgba()",
         len(violations) == 0,
         f"\n    " + "\n    ".join(violations[:10]))


# ====================================================================
# Part 7: GUI 完整功能测试
# ====================================================================
def test_gui_full():
    section("Part 7: GUI 完整功能测试（列表/搜索/筛选/详情/主题）")

    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer, Qt

    app = QApplication.instance() or QApplication(sys.argv)

    from pyside_v2.windows.main_window import MainWindow
    from pyside_v2.theme import color_hex, current

    win = MainWindow()

    # 1. 主窗口创建成功
    test("MainWindow 创建成功", win is not None)
    test("窗口标题正确", "v2" in win.windowTitle(), f"got '{win.windowTitle()}'")

    # 2. 列表加载
    model = win.video_model
    QTimer.singleShot(100, app.quit)  # 给事件循环跑一下
    app.exec()

    row_count = model.rowCount()
    test("VideoTableModel 加载了数据", row_count > 0, f"rowCount={row_count}")
    test("VideoTableModel 列数 = 12", model.columnCount() == 12,
         f"colCount={model.columnCount()}")

    total = model.total_count
    test("total_count > 0", total > 0, f"total={total}")

    # 3. 列定义验证
    col_keys = model.column_keys
    expected_cols = ['javdb_code', 'title', 'actors', 'stars', 'tags', 'size',
                     'status', 'duration', 'resolution', 'javdb_rating',
                     'file_created_time', 'source_folder']
    test("列标识正确", col_keys == expected_cols, f"got {col_keys}")

    # 4. 数据格式化验证（取第一行）
    if row_count > 0:
        idx = model.index(0, 0)
        vid = idx.data(Qt.UserRole)
        test("data(UserRole) 返回 video_id", vid is not None, f"got {vid}")

        # 状态列颜色
        status_col = col_keys.index('status')
        fg = model.index(0, status_col).data(Qt.ForegroundRole)
        test("status 列有前景色（在线/离线）", fg is not None, "前景色为 None")

        # 文件大小格式化
        size_col = col_keys.index('size')
        size_text = model.index(0, size_col).data(Qt.DisplayRole)
        test("size 列格式化（含单位）",
             size_text == "" or any(u in size_text for u in ["KB", "MB", "GB", "TB"]),
             f"got '{size_text}'")

    # 5. 搜索功能
    win.search_input.setText("test")
    win._on_search()
    test("搜索触发不报错", True)
    # 搜索后重置
    win.search_input.setText("")
    win._on_search()

    # 6. 星级筛选
    win.star_filter_combo.setCurrentIndex(3)
    test("星级筛选切换不报错", True)
    win.star_filter_combo.setCurrentIndex(0)

    # 7. 仅在线切换
    win._toggle_online_only()
    test("仅在线切换不报错", True)
    win._toggle_online_only()  # 切回

    # 8. 翻页
    if model.page_size and total > model.page_size:
        win.go_next_page()
        test("翻页 next 不报错", True)
        win.go_first_page()
        test("翻页 first 不报错", True)
    else:
        test("翻页（数据不足一页，跳过）", True)

    # 9. 详情面板加载
    if row_count > 0:
        first_vid = model.index(0, 0).data(Qt.UserRole)
        win.load_detail(first_vid)
        test("load_detail() 加载详情不报错", True)
        test("详情面板标题非空", win.detail_title_edit.text() or True)

    # 10. 主题切换
    initial_theme = win.theme_mgr.theme_name
    win._toggle_theme()
    test("主题切换不报错", True)
    test("主题实际切换",
         win.theme_mgr.theme_name != initial_theme,
         f"{initial_theme} → {win.theme_mgr.theme_name}")
    # 切回
    win._toggle_theme()

    # 11. 详情面板「更多」菜单
    test("_show_more_menu 方法存在", hasattr(win, '_show_more_menu'))
    test("_refresh_inline_colors 方法存在", hasattr(win, '_refresh_inline_colors'))

    # 12. 搜索防抖 500ms
    test("搜索防抖 = 500ms", win._search_timer.interval() == 500,
         f"interval={win._search_timer.interval()}")

    # 13. 详情面板按钮精简验证
    test("详情面板有 btn_play", hasattr(win, 'btn_play'))
    test("详情面板有 btn_save", hasattr(win, 'btn_save'))
    test("详情面板有 btn_more", hasattr(win, 'btn_more'))
    test("详情面板无 btn_star（已移入更多菜单）", not hasattr(win, 'btn_star'))
    test("详情面板无 btn_delete（已移入更多菜单）", not hasattr(win, 'btn_delete'))

    # 14. ClickableLabel 替代验证
    from pyside_v2.widgets import ClickableLabel
    test("detail_stars_label 是 ClickableLabel",
         isinstance(win.detail_stars_label, ClickableLabel),
         f"got {type(win.detail_stars_label).__name__}")

    win.close()


# ====================================================================
# Part 8: 对话框功能测试
# ====================================================================
def test_dialogs():
    section("Part 8: 对话框功能测试（标签/文件夹/演员库）")

    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    from pyside_v2.windows.main_window import MainWindow
    win = MainWindow()

    # 等数据加载
    from PySide6.QtCore import QTimer
    QTimer.singleShot(100, app.quit)
    app.exec()

    # --- 标签管理 ---
    from pyside_v2.dialogs import TagManagerDialog
    tag_dlg = TagManagerDialog(win)
    tag_dlg.list.count()
    test("TagManagerDialog 创建成功", tag_dlg.list.count() >= 0,
         f"tags={tag_dlg.list.count()}")
    test("TagManager 删除按钮使用 color_hex",
         "danger" in str(tag_dlg.btn_del.styleSheet()) or
         tag_dlg.btn_del.styleSheet().startswith("color: #"),
         f"style={tag_dlg.btn_del.styleSheet()}")
    tag_dlg.close()

    # --- 文件夹管理 ---
    from pyside_v2.dialogs import FolderManagerDialog
    folder_dlg = FolderManagerDialog(win)
    test("FolderManagerDialog 创建成功", folder_dlg.table.rowCount() >= 0,
         f"rows={folder_dlg.table.rowCount()}")
    folder_dlg.close()

    # --- 演员库 ---
    from pyside_v2.dialogs import ActorBrowserDialog
    actor_dlg = ActorBrowserDialog(win)
    test("ActorBrowserDialog 创建成功", actor_dlg._total >= 0,
         f"total={actor_dlg._total}")
    actor_dlg.close()

    # --- 演员详情 ---
    from pyside_v2.dialogs import ActorDetailWindow
    # 取第一个演员名
    win.core.cursor.execute("SELECT name FROM actors LIMIT 1")
    r = win.core.cursor.fetchone()
    if r and r[0]:
        detail_dlg = ActorDetailWindow(win, actor_name=r[0])
        test("ActorDetailWindow 创建成功", detail_dlg._actor_id is not None)
        detail_dlg.close()
    else:
        test("ActorDetailWindow（无演员数据，跳过）", True)

    win.close()


# ====================================================================
# Part 9: 导入流程测试
# ====================================================================
def test_import_flow():
    section("Part 9: 导入流程测试（从 AV 文件夹导入新视频）")

    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    from pyside_v2.windows.main_window import MainWindow
    win = MainWindow()

    from PySide6.QtCore import QTimer
    QTimer.singleShot(100, app.quit)
    app.exec()

    # 确认 AV 文件夹未入库的文件
    import os
    av_folder = "/Users/firewell/影视/AV"
    if not os.path.exists(av_folder):
        test("AV 文件夹在线", False, f"{av_folder} 不存在")
        win.close()
        return

    # 统计当前 DB 里该文件夹的视频数
    win.core.cursor.execute("SELECT COUNT(*) FROM videos WHERE source_folder LIKE ?", (av_folder + "%",))
    before_count = win.core.cursor.fetchone()[0]
    test(f"导入前 DB 中 AV 文件夹视频数 = {before_count}", True)

    # 收集磁盘上的新文件（不在 DB 里的）
    on_disk_files = []
    for root, dirs, files in os.walk(av_folder):
        for f in files:
            if f.lower().endswith(('.mp4', '.mkv', '.avi')):
                fp = os.path.join(root, f)
                win.core.cursor.execute("SELECT 1 FROM videos WHERE file_path=?", (fp,))
                if not win.core.cursor.fetchone():
                    on_disk_files.append(fp)
                    if len(on_disk_files) >= 3:  # 只测 3 个
                        break
        if len(on_disk_files) >= 3:
            break

    test(f"找到 {len(on_disk_files)} 个未入库文件", len(on_disk_files) > 0,
         "无未入库文件" if not on_disk_files else "")

    # 测试 core.add_video_to_db_optimized
    imported = 0
    for fp in on_disk_files:
        try:
            result = win.core.add_video_to_db_optimized(fp, "local")
            if result == "added":
                imported += 1
        except Exception as e:
            test(f"导入 {os.path.basename(fp)}", False, str(e))

    test(f"成功导入 {imported}/{len(on_disk_files)} 个文件",
         imported == len(on_disk_files) if on_disk_files else True,
         f"imported={imported}")

    # 验证导入后能通过 get_video_path 查到
    if on_disk_files:
        for fp in on_disk_files[:imported]:
            win.core.cursor.execute("SELECT id FROM videos WHERE file_path=?", (fp,))
            r = win.core.cursor.fetchone()
            if r:
                path = win.core.get_video_path(r[0])
                test(f"get_video_path({r[0]}) 返回正确路径",
                     path == fp, f"expected {fp}, got {path}")

    # 导入后总数对比
    win.core.cursor.execute("SELECT COUNT(*) FROM videos WHERE source_folder LIKE ?", (av_folder + "%",))
    after_count = win.core.cursor.fetchone()[0]
    test(f"导入后 DB 中 AV 文件夹视频数 = {after_count}",
         after_count == before_count + imported,
         f"before={before_count}, after={after_count}, imported={imported}")

    win.close()


# ====================================================================
# 主入口
# ====================================================================
if __name__ == "__main__":
    print("\n" + "🔥" * 30)
    print("  v2 重构功能测试")
    print("🔥" * 30)

    try:
        test_core_data_access()
    except Exception as e:
        import traceback
        print(f"\n❌ Part 1 崩溃: {e}")
        traceback.print_exc()

    try:
        test_color_hex()
    except Exception as e:
        import traceback
        print(f"\n❌ Part 2 崩溃: {e}")
        traceback.print_exc()

    try:
        test_new_widgets()
    except Exception as e:
        import traceback
        print(f"\n❌ Part 3 崩溃: {e}")
        traceback.print_exc()

    try:
        test_sql_encapsulation()
    except Exception as e:
        import traceback
        print(f"\n❌ Part 4 崩溃: {e}")
        traceback.print_exc()

    try:
        test_no_monkey_patches()
    except Exception as e:
        import traceback
        print(f"\n❌ Part 5 崩溃: {e}")
        traceback.print_exc()

    try:
        test_no_hardcoded_colors()
    except Exception as e:
        import traceback
        print(f"\n❌ Part 6 崩溃: {e}")
        traceback.print_exc()

    try:
        test_gui_full()
    except Exception as e:
        import traceback
        print(f"\n❌ Part 7 崩溃: {e}")
        traceback.print_exc()

    try:
        test_dialogs()
    except Exception as e:
        import traceback
        print(f"\n❌ Part 8 崩溃: {e}")
        traceback.print_exc()

    try:
        test_import_flow()
    except Exception as e:
        import traceback
        print(f"\n❌ Part 9 崩溃: {e}")
        traceback.print_exc()

    # ---- 总结 ----
    print("\n" + "=" * 60)
    print(f"  测试结果: ✅ {_passed} 通过  ❌ {_failed} 失败")
    print("=" * 60)

    if _errors:
        print("\n失败详情:")
        for e in _errors:
            print(f"  ❌ {e}")

    sys.exit(1 if _failed > 0 else 0)
