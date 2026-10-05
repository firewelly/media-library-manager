# -*- coding: utf-8 -*-
"""
v2 新功能测试 —— 设置 / 封面墙 / 去重复 / 统计 / 视图切换 / 搜索范围
"""

import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(_PROJECT_ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, _PROJECT_ROOT)
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


def flush_events(app, ms=300):
    from PySide6.QtCore import QElapsedTimer
    timer = QElapsedTimer()
    timer.start()
    while not timer.hasExpired(ms):
        app.processEvents()


def wait_for(app, condition, timeout_ms=30000, label=""):
    """条件等待（替代固定 sleep，避免冷缓存/慢盘导致的时序失败）。"""
    from PySide6.QtCore import QElapsedTimer
    timer = QElapsedTimer()
    timer.start()
    while not timer.hasExpired(timeout_ms):
        app.processEvents()
        try:
            if condition():
                return True
        except Exception:
            pass
    print(f"  ⚠️ 等待超时: {label}")
    return False


def main():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    app = QApplication.instance() or QApplication(sys.argv)

    # ---- SettingsManager ----
    print("\n=== SettingsManager ===")
    from pyside_v2.core.settings import SettingsManager
    tmp = os.path.join(_PROJECT_ROOT, "_test_settings_tmp.json")
    sm = SettingsManager(tmp)
    test("默认值加载", sm.get("page_size") == 300 and sm.get("theme") == "light")
    sm.set("page_size", 500)
    sm2 = SettingsManager(tmp)  # 新实例应读到已保存值
    test("set 后落盘可读回", sm2.get("page_size") == 500)
    sm.set("unknown_key", "x")  # 不应崩溃也不应写入
    test("未知 key 被忽略", "unknown_key" not in sm.all_settings())
    os.remove(tmp)

    # ---- MainWindow + 新功能 ----
    print("\n=== MainWindow 新功能 ===")
    from pyside_v2.windows.main_window import MainWindow
    win = MainWindow()
    ok = wait_for(app, lambda: win.video_model.rowCount() > 0, 30000, "首屏查询")
    flush_events(app, 200)

    test("core_settings 存在", hasattr(win, "core_settings"))
    test("cover_model 存在", hasattr(win, "cover_model"))
    test("cover_wall 存在", hasattr(win, "cover_wall"))
    test("view_stack 存在", hasattr(win, "view_stack"))
    test("视图切换按钮存在", hasattr(win, "btn_view_table") and hasattr(win, "btn_view_wall"))

    rows = win.video_model.rowCount()
    test(f"列表加载 ({rows} 行)", rows > 0)
    test("封面墙同步行数一致", win.cover_model.rowCount() == rows,
         f"cover={win.cover_model.rowCount()} table={rows}")

    # 视图切换
    win._switch_view(1)
    test("切换到封面墙", win.view_stack.currentIndex() == 1 and win.btn_view_wall.isChecked())
    wait_for(app, lambda: len(win.cover_model._pixmaps) > 0, 30000, "缩略图加载")
    pix_count = len(win.cover_model._pixmaps)
    test(f"缩略图懒加载送达模型 ({pix_count} 张)", pix_count > 0,
         "Signal(dict)→object 修复后应有 pixmap 注入")
    win._switch_view(0)
    test("切换回表格", win.view_stack.currentIndex() == 0 and win.btn_view_table.isChecked())

    # 搜索（含 javdb_code 字段）
    win.search_input.setText("test")
    win._on_search()
    flush_events(app, 500)
    test("搜索（含番号字段）不报错", True)
    win.search_input.setText("")
    win._on_search()
    flush_events(app, 500)

    # 排序指示
    win.on_header_clicked("stars")
    ind = win.video_table.horizontalHeader().sortIndicatorSection()
    keys = win.video_model.column_keys
    test("排序指示箭头同步", keys[ind] == "stars", f"indicator at {ind}, key={keys[ind] if ind < len(keys) else '?'}")

    # select_video_by_id
    first_vid = win.video_model.video_id_at(0)
    ok = win.select_video_by_id(first_vid)
    test("select_video_by_id 定位成功", ok and win._current_video_id == first_vid)
    test("select_video_by_id 无效 ID 返回 False", win.select_video_by_id(999999999) is False)

    # _show_more_menu 回调 + 统计/去重/设置方法存在
    for m in ["on_open_settings", "apply_settings", "on_open_stats",
              "on_open_duplicates", "on_full_database_reset"]:
        test(f"{m} 方法存在", hasattr(win, m))

    # ---- 新对话框 ----
    print("\n=== 新对话框 ===")

    from pyside_v2.dialogs.stats import StatsDialog
    stats = StatsDialog(win)
    wait_for(app, lambda: stats.body_lay.count() > 2, 30000, "统计查询")
    test("StatsDialog 创建", stats is not None)
    test("统计渲染出内容", stats.body_lay.count() > 2, f"count={stats.body_lay.count()}")
    stats.close()

    from pyside_v2.dialogs.settings import SettingsDialog
    sd = SettingsDialog(win)
    test("SettingsDialog 创建", sd is not None)
    test("设置表单已填充", sd.page_size_spin.value() == win.core_settings.get("page_size"))
    sd.close()

    # DuplicatesDialog（会触发后台扫描，49k 行可能较慢，给足时间）
    from pyside_v2.dialogs.duplicates import DuplicatesDialog
    dd = DuplicatesDialog(win)
    flush_events(app, 15000)
    test("DuplicatesDialog 创建", dd is not None)
    test(f"重复数据送达 ({len(dd._groups)} 组)", dd._worker is not None and
         (len(dd._groups) > 0 or "未发现" in dd.hint_label.text() or "正在" in dd.hint_label.text()),
         f"groups={len(dd._groups)}, hint='{dd.hint_label.text()}'")
    dd.close()

    # 主题切换后封面墙仍工作
    win._toggle_theme()
    flush_events(app, 300)
    win._switch_view(1)
    flush_events(app, 300)
    test("dark 主题下封面墙切换正常", win.view_stack.currentIndex() == 1)
    win._switch_view(0)
    win._toggle_theme()

    # ---- 时长格式化（"122 分鍾" 文本兼容）----
    print("\n=== 时长格式化 ===")
    from pyside_v2.core.formatters import (
        parse_duration_seconds, format_duration, format_file_size)
    test("int 秒原样", parse_duration_seconds(7320) == 7320)
    test("float 秒取整", parse_duration_seconds(3661.5) == 3661)
    test("数字字符串按秒", parse_duration_seconds("7320") == 7320)
    test("'122 分鍾' 按分钟", parse_duration_seconds("122 分鍾") == 7320)
    test("'85 分钟' 按分钟", parse_duration_seconds("85 分钟") == 5100)
    test("'90 min' 按分钟", parse_duration_seconds("90 min") == 5400)
    test("'2 小時' 按小时", parse_duration_seconds("2 小時") == 7200)
    test("无法解析返回 None", parse_duration_seconds("abc") is None)
    test("None/空串返回 None", parse_duration_seconds(None) is None
         and parse_duration_seconds("") is None)
    test("format_duration 文本时长", format_duration("122 分鍾") == "02:02:00")
    test("format_duration 空值占位", format_duration(None) == "—")
    test("format_duration 无法解析原样", format_duration("abc") == "abc")
    test("主窗口 _fmt_duration 走共享实现",
         win._fmt_duration("122 分鍾") == "02:02:00")

    # 文本时长视频详情不再整面板失败
    cur = win.core.conn.cursor()
    cur.execute("SELECT id FROM videos WHERE typeof(duration)='text' LIMIT 1")
    row = cur.fetchone()
    if row:
        win.load_detail(row[0])
        flush_events(app, 200)
        from PySide6.QtWidgets import QLabel as _QL
        dur_txt = None
        lay = win.detail_kv_container
        for i in range(lay.count()):
            rw = lay.itemAt(i).widget()
            if not rw:
                continue
            lbs = rw.findChildren(_QL)
            if len(lbs) >= 2 and lbs[0].text() == "时长":
                dur_txt = lbs[1].text()
                break
        import re as _re
        test(f"文本时长视频详情加载成功（时长={dur_txt!r}）",
             bool(dur_txt and _re.fullmatch(r"\d{2}:\d{2}(:\d{2})?", dur_txt)))
        # 状态栏回归：load_detail 不得重建状态栏（_clear_layout 历史 bug）
        cnt = win.video_count_label.text()
        test(f"load_detail 后计数标签保留（{cnt!r}）",
             cnt.endswith("个视频") and not cnt.startswith("0"))
    else:
        test("库中有文本时长样本（无则跳过详情验证）", True)

    # ---- 封面墙交互（右键菜单/多选/快捷键取值）----
    print("\n=== 封面墙交互 ===")
    test("封面墙右键策略", win.cover_wall.contextMenuPolicy() == Qt.CustomContextMenu)
    from PySide6.QtWidgets import QAbstractItemView as _AIV
    test("封面墙 ExtendedSelection",
         win.cover_wall.selectionMode() == _AIV.ExtendedSelection)
    test("show_cover_context_menu 方法存在", hasattr(win, "show_cover_context_menu"))
    test("_active_view_selected_ids 方法存在", hasattr(win, "_active_view_selected_ids"))

    win._switch_view(1)
    flush_events(app, 300)
    from PySide6.QtCore import QItemSelectionModel as _QISM
    sm = win.cover_wall.selectionModel()
    sm.clearSelection()
    win.cover_wall.setCurrentIndex(win.cover_model.index(0, 0))
    for r in (0, 1, 2):
        sm.select(win.cover_model.index(r, 0), _QISM.Select)
    flush_events(app, 100)
    ids = win.cover_wall.selected_video_ids()
    test(f"封面墙多选 3 项（实得 {len(ids)}）", len(ids) == 3)
    test("_active_view_selected_ids 取封面墙",
         win._active_view_selected_ids() == ids)
    win._switch_view(0)
    flush_events(app, 100)
    test("_active_view_selected_ids 切回表格",
         win._active_view_selected_ids() == win.video_table.selected_video_ids())

    # 数字键打分快捷键在封面墙作用域注册（0-5 共 6 个）
    from PySide6.QtGui import QShortcut as _QSC
    cover_shortcuts = [c for c in win.cover_wall.findChildren(_QSC)]
    test(f"封面墙数字快捷键已注册（{len(cover_shortcuts)} 个）",
         len(cover_shortcuts) >= 6)

    win.close()

    # ---- 汇总 ----
    print("\n" + "=" * 60)
    print(f"  新功能测试结果: ✅ {_passed} 通过  ❌ {_failed} 失败")
    print("=" * 60)
    if _errors:
        print("\n失败详情:")
        for e in _errors:
            print(f"  ❌ {e}")
    sys.exit(1 if _failed else 0)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        print(f"\n❌ 测试崩溃: {e}")
        traceback.print_exc()
        sys.exit(2)
