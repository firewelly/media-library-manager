# -*- coding: utf-8 -*-
"""
批量任务动作（原生 PySide6，替代 Tk 桥接）。

所有深度依赖 Tk GUI 的菜单功能在此用底层 manager + TaskRunnerDialog 重写。
不走 gui_adapter 桥接，直接调 utils.* 的 manager。
"""

import os
import sqlite3
from datetime import datetime

from pyside_v2.dialogs.task_runner import TaskRunnerDialog


# =====================================================================
# 辅助：获取在线活跃文件夹
# =====================================================================
def _get_online_folders(core):
    """返回活跃且在线的文件夹列表。"""
    core.cursor.execute("SELECT folder_path, folder_type FROM folders WHERE is_active = 1")
    rows = core.cursor.fetchall()
    return [(fp, ft) for fp, ft in rows if fp and os.path.exists(fp)]


# =====================================================================
# 扫描媒体文件
# =====================================================================
def scan_media(main_window):
    """扫描活跃文件夹，导入新视频。"""
    core = main_window.core
    folders = _get_online_folders(core)
    if not folders:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(main_window, "提示", "没有在线的活跃文件夹")
        return

    video_exts = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v',
                  '.3gp', '.ts', '.mts', '.m2ts'}

    def task(progress_cb, log_cb, cancel_cb):
        # 收集所有视频
        log_cb("收集视频文件…")
        all_files = []
        for fp, ft in folders:
            if cancel_cb():
                return "已取消"
            for root, dirs, files in os.walk(fp):
                for f in files:
                    if any(f.lower().endswith(e) for e in video_exts):
                        all_files.append((os.path.join(root, f), ft))
        log_cb(f"共 {len(all_files)} 个视频文件")

        if not all_files:
            return "未找到视频文件"

        added = skipped = updated = 0
        total = len(all_files)
        for i, (fpath, ft) in enumerate(all_files):
            if cancel_cb():
                log_cb("用户取消")
                break
            try:
                r = core.add_video_to_db_optimized(fpath, ft)
                if r == 'added':
                    added += 1
                elif r == 'updated':
                    updated += 1
                else:
                    skipped += 1
            except Exception:
                skipped += 1

            if i % 50 == 0 or i == total - 1:
                pct = int((i + 1) / total * 100)
                progress_cb(pct, f"扫描 {i+1}/{total}: 新增{added} 跳过{skipped}")
                if i % 200 == 0:
                    core.conn.commit()
                    log_cb(f"[{i+1}/{total}] 新增:{added} 更新:{updated} 跳过:{skipped}")

        core.conn.commit()
        return f"扫描完成：新增 {added}，更新 {updated}，跳过 {skipped}（共 {total}）"

    TaskRunnerDialog.run(main_window, "扫描媒体文件", task,
                         on_done=main_window.load_videos)


# =====================================================================
# 综合媒体库更新
# =====================================================================
def comprehensive_update(main_window):
    """全量更新：新增 + 删失踪 + 更新MD5。"""
    core = main_window.core
    folders = _get_online_folders(core)
    if not folders:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(main_window, "提示", "没有在线的活跃文件夹")
        return

    def task(progress_cb, log_cb, cancel_cb):
        # 用 fast_smart_media_updater（纯函数，已在 SmartUpdateDialog 验证）
        import fast_smart_media_updater as fsu
        folder_paths = [fp for fp, _ in folders]

        def fsu_progress(msg):
            log_cb(msg)

        log_cb(f"开始综合更新 {len(folder_paths)} 个文件夹…")
        stats = fsu.run_fast_update(
            folders=folder_paths, enable_md5=True, dry_run=False,
            delete_missing=True, quiet=True, progress=fsu_progress,
        )
        added = sum(getattr(s, 'added', 0) for s in stats.values())
        updated = sum(getattr(s, 'updated', 0) for s in stats.values())
        removed = sum(getattr(s, 'removed', 0) for s in stats.values())
        progress_cb(100, "完成")
        return f"综合更新完成：新增 {added}，更新 {updated}，删除 {removed}"

    TaskRunnerDialog.run(main_window, "智能媒体库更新", task,
                         on_done=main_window.load_videos)


# =====================================================================
# 同步打分到文件名
# =====================================================================
def sync_stars_to_filename(main_window):
    """把星级（!数量）同步写入文件名。"""
    core = main_window.core

    def task(progress_cb, log_cb, cancel_cb):
        core.cursor.execute("SELECT id, file_path, file_name, stars FROM videos WHERE is_nas_online = 1")
        videos = core.cursor.fetchall()
        total = len(videos)
        log_cb(f"共 {total} 个在线视频")
        ok = fail = 0
        for i, (vid, fpath, fname, stars) in enumerate(videos):
            if cancel_cb():
                break
            try:
                stars = stars or 0
                # 去掉开头的 ! 再加回
                clean = fname.lstrip('!')
                prefix = '!' * stars if stars > 0 else ''
                new_name = prefix + clean
                if new_name != fname:
                    new_path = os.path.join(os.path.dirname(fpath), new_name)
                    if not os.path.exists(new_path):
                        os.rename(fpath, new_path)
                        core.cursor.execute(
                            "UPDATE videos SET file_path=?, file_name=? WHERE id=?",
                            (new_path, new_name, vid))
                        ok += 1
                if i % 100 == 0:
                    progress_cb(int(i/total*100), f"同步 {i+1}/{total}")
                    core.conn.commit()
                    log_cb(f"[{i+1}/{total}] 已同步 {ok}")
            except Exception as e:
                fail += 1
        core.conn.commit()
        return f"打分同步完成：成功 {ok}，失败 {fail}"

    TaskRunnerDialog.run(main_window, "同步打分到文件名", task,
                         on_done=main_window.load_videos)


# =====================================================================
# 批量计算 MD5
# =====================================================================
def batch_calculate_md5(main_window):
    """批量计算缺失的 MD5。"""
    core = main_window.core

    def task(progress_cb, log_cb, cancel_cb):
        core.cursor.execute(
            "SELECT id, file_path FROM videos WHERE (md5_hash IS NULL OR md5_hash = '') AND is_nas_online = 1"
        )
        videos = core.cursor.fetchall()
        total = len(videos)
        log_cb(f"共 {total} 个视频需要计算 MD5")
        if total == 0:
            return "所有视频已有 MD5"
        ok = fail = 0
        for i, (vid, fpath) in enumerate(videos):
            if cancel_cb():
                break
            try:
                md5 = core.calculate_md5_hash(fpath)
                if md5:
                    core.cursor.execute("UPDATE videos SET md5_hash=? WHERE id=?", (md5, vid))
                    ok += 1
                else:
                    fail += 1
                if i % 20 == 0:
                    progress_cb(int(i/total*100), f"计算 {i+1}/{total}")
                    core.conn.commit()
                    log_cb(f"[{i+1}/{total}] {os.path.basename(fpath)[:30]}: {md5[:8] if md5 else '失败'}")
            except Exception:
                fail += 1
        core.conn.commit()
        return f"MD5 计算完成：成功 {ok}，失败 {fail}（共 {total}）"

    TaskRunnerDialog.run(main_window, "批量计算 MD5", task,
                         on_done=main_window.load_videos)


# =====================================================================
# 智能去重
# =====================================================================
def smart_remove_duplicates(main_window):
    """智能去重（调 MaintenanceManager）。"""
    core = main_window.core

    def task(progress_cb, log_cb, cancel_cb):
        progress_cb(50, "正在查找重复…")
        log_cb("开始智能去重…")
        try:
            result = core.maintenance_manager.find_duplicates()
            log_cb(f"找到 {len(result) if result else 0} 组重复")
            # maintenance_manager 有 find_duplicates，去重逻辑较复杂
            # 这里先报告，实际删除需用户确认（对齐 Tk）
            progress_cb(100, "完成")
            dup_count = len(result) if result else 0
            return f"找到 {dup_count} 组重复文件（详见日志）"
        except Exception as e:
            return f"去重出错: {e}"

    TaskRunnerDialog.run(main_window, "智能去重", task,
                         on_done=main_window.load_videos)


# =====================================================================
# 清理演员信息
# =====================================================================
def clean_actor_data(main_window):
    """清理无效演员数据（调 MaintenanceManager）。"""
    core = main_window.core

    def task(progress_cb, log_cb, cancel_cb):
        progress_cb(30, "正在清理演员…")
        log_cb("开始清理无效演员…")
        try:
            if hasattr(core.maintenance_manager, 'clean_actor_data'):
                result = core.maintenance_manager.clean_actor_data()
                log_cb(f"清理结果: {result}")
                progress_cb(100, "完成")
                return f"演员清理完成: {result}"
            else:
                # 手动清理：删除无关联的演员
                core.cursor.execute(
                    "DELETE FROM actors WHERE id NOT IN (SELECT DISTINCT actor_id FROM video_actors)"
                )
                deleted = core.cursor.rowcount
                core.conn.commit()
                log_cb(f"删除无关联演员: {deleted}")
                progress_cb(100, "完成")
                return f"清理完成：删除 {deleted} 个无关联演员"
        except Exception as e:
            return f"清理出错: {e}"

    TaskRunnerDialog.run(main_window, "清理演员信息", task)


# =====================================================================
# 完全重置数据库
# =====================================================================
def full_database_reset(main_window):
    """完全重置数据库（高危，需确认）。"""
    from PySide6.QtWidgets import QMessageBox
    reply = QMessageBox.critical(
        main_window, "⚠️ 危险操作",
        "完全重置数据库将清空所有视频记录并重新扫描！\n\n确定继续吗？此操作不可撤销。",
        QMessageBox.Yes | QMessageBox.No, QMessageBox.No
    )
    if reply != QMessageBox.Yes:
        return

    core = main_window.core
    folders = _get_online_folders(core)

    def task(progress_cb, log_cb, cancel_cb):
        log_cb("清空 videos 表…")
        progress_cb(10, "清空中…")
        core.cursor.execute("DELETE FROM videos")
        core.conn.commit()
        log_cb("已清空，开始重新扫描…")
        progress_cb(20, "重新扫描…")

        # 复用 scan 逻辑
        video_exts = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'}
        all_files = []
        for fp, ft in folders:
            for root, dirs, files in os.walk(fp):
                for f in files:
                    if any(f.lower().endswith(e) for e in video_exts):
                        all_files.append((os.path.join(root, f), ft))
        total = len(all_files)
        log_cb(f"共 {total} 个视频")
        added = 0
        for i, (fpath, ft) in enumerate(all_files):
            if cancel_cb():
                break
            try:
                core.add_video_to_db_optimized(fpath, ft)
                added += 1
            except Exception:
                pass
            if i % 100 == 0:
                pct = 20 + int(i / total * 80)
                progress_cb(pct, f"重新扫描 {i+1}/{total}")
                core.conn.commit()
        core.conn.commit()
        return f"重置完成：重新导入 {added} 个视频"

    TaskRunnerDialog.run(main_window, "完全重置数据库", task,
                         on_done=main_window.load_videos)


# =====================================================================
# 批量生成封面
# =====================================================================
def batch_generate_thumbnails(main_window):
    """批量生成封面（调 core.generate_thumbnail_for_video）。"""
    core = main_window.core

    def task(progress_cb, log_cb, cancel_cb):
        core.cursor.execute(
            "SELECT id, file_path FROM videos WHERE is_nas_online = 1 AND thumbnail_data IS NULL"
        )
        videos = core.cursor.fetchall()
        total = len(videos)
        log_cb(f"共 {total} 个视频需要生成封面")
        if total == 0:
            return "所有视频已有封面"
        ok = fail = 0
        for i, (vid, fpath) in enumerate(videos):
            if cancel_cb():
                break
            try:
                success, out = core.generate_thumbnail_for_video(fpath)
                if success and out:
                    with open(out, 'rb') as f:
                        data = f.read()
                    core.cursor.execute(
                        "UPDATE videos SET thumbnail_data=?, thumbnail_path=? WHERE id=?",
                        (data, out, vid))
                    ok += 1
                else:
                    fail += 1
                if i % 10 == 0:
                    progress_cb(int(i/total*100), f"生成 {i+1}/{total}")
                    core.conn.commit()
                    log_cb(f"[{i+1}/{total}] {os.path.basename(fpath)[:30]}: {'OK' if success else '失败'}")
            except Exception:
                fail += 1
        core.conn.commit()
        return f"封面生成完成：成功 {ok}，失败 {fail}（共 {total}）"

    TaskRunnerDialog.run(main_window, "批量生成封面", task,
                         on_done=main_window.load_videos)


# =====================================================================
# 修正 JAVDB 错误标题
# =====================================================================
def fix_javdb_error_titles(main_window):
    """修正 JAVDB 错误标题（调 AdvancedToolsManager）。"""
    core = main_window.core

    def task(progress_cb, log_cb, cancel_cb):
        log_cb("开始修正 JAVDB 错误标题…")
        progress_cb(50, "修正中…")
        try:
            if main_window.advanced_tools_manager:
                result = main_window.advanced_tools_manager.fix_javdb_error_titles()
                log_cb(f"结果: {result}")
                progress_cb(100, "完成")
                return f"JAVDB 标题修正完成: {result}"
            else:
                return "AdvancedToolsManager 不可用"
        except Exception as e:
            return f"修正出错: {e}"

    TaskRunnerDialog.run(main_window, "修正 JAVDB 错误信息", task,
                         on_done=main_window.load_videos)


# =====================================================================
# 批量导入 NFO（为无演员的视频）
# =====================================================================
def batch_import_nfo(main_window):
    """为没有演员的视频批量导入 NFO（调 BatchOperationManager）。"""
    core = main_window.core

    def task(progress_cb, log_cb, cancel_cb):
        log_cb("查找需要导入 NFO 的视频…")
        core.cursor.execute(
            "SELECT id, file_path FROM videos WHERE is_nas_online = 1 AND id NOT IN "
            "(SELECT DISTINCT video_id FROM video_actors)"
        )
        videos = core.cursor.fetchall()
        total = len(videos)
        log_cb(f"共 {total} 个视频无演员，尝试导入 NFO")
        if total == 0:
            return "所有视频已有演员信息"
        ok = fail = 0
        for i, (vid, fpath) in enumerate(videos):
            if cancel_cb():
                break
            try:
                # 找同目录的 .nfo 文件
                nfo = os.path.splitext(fpath)[0] + '.nfo'
                if os.path.exists(nfo):
                    success, msg = core.import_nfo_file(nfo, video_id=vid)
                    if success:
                        ok += 1
                        log_cb(f"[{i+1}/{total}] 导入成功: {os.path.basename(nfo)}")
                    else:
                        fail += 1
                else:
                    fail += 1
                if i % 20 == 0:
                    progress_cb(int(i/total*100), f"导入 {i+1}/{total}")
            except Exception:
                fail += 1
        core.conn.commit()
        return f"NFO 导入完成：成功 {ok}，失败 {fail}（共 {total}）"

    TaskRunnerDialog.run(main_window, "批量导入 NFO 信息", task,
                         on_done=main_window.load_videos)


# =====================================================================
# 批量导入 JAVDB（为无标题的视频）
# =====================================================================
def batch_import_javdb(main_window):
    """为没有 JAVDB 标题的视频批量抓取（调 utils.jav）。"""
    core = main_window.core

    def task(progress_cb, log_cb, cancel_cb):
        from utils import jav as utils_jav
        log_cb("查找需要抓取 JAVDB 的视频…")
        core.cursor.execute(
            "SELECT v.id, v.file_name FROM videos v "
            "LEFT JOIN javdb_info j ON v.id = j.video_id "
            "WHERE j.javdb_title IS NULL AND v.is_nas_online = 1"
        )
        videos = core.cursor.fetchall()
        total = len(videos)
        log_cb(f"共 {total} 个视频需要抓取 JAVDB")
        if total == 0:
            return "所有视频已有 JAVDB 信息"
        ok = fail = 0
        for i, (vid, fname) in enumerate(videos):
            if cancel_cb():
                break
            try:
                code = utils_jav.extract_code(fname)
                if not code:
                    fail += 1
                    continue
                log_cb(f"[{i+1}/{total}] 搜索: {code}")
                info = utils_jav.search_movie_info(code)
                if info:
                    if utils_jav.save_movie_info_to_db(core.conn, vid, info):
                        ok += 1
                        log_cb(f"  ✅ 保存成功: {code}")
                    else:
                        fail += 1
                else:
                    fail += 1
                    log_cb(f"  ⚠️ 未找到: {code}")
                progress_cb(int((i+1)/total*100), f"抓取 {i+1}/{total}")
            except Exception as e:
                fail += 1
                log_cb(f"  ❌ 错误: {e}")
        return f"JAVDB 抓取完成：成功 {ok}，失败 {fail}（共 {total}）"

    TaskRunnerDialog.run(main_window, "批量导入 JAVDB 信息", task,
                         on_done=main_window.load_videos)
