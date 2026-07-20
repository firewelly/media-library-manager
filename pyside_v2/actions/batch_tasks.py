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

            if (i + 1) % 200 == 0 or i == total - 1:
                pct = int((i + 1) / total * 100)
                progress_cb(pct, f"扫描 {i+1}/{total}: 新增{added} 跳过{skipped}")
                core.conn.commit()
                # 日志降频：每 200 条记一次汇总，不逐条记
                log_cb(f"  [{i+1}/{total}] 新增:{added} 跳过:{skipped}")

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
# 同步打分到文件名（优化版）
# =====================================================================
def sync_stars_to_filename(main_window):
    """把星级（!数量）同步写入文件名。

    优化点（vs Tk 版）：
    1. 先查在线文件夹，只处理这些文件夹下的视频（不浪费在离线文件上）
    2. 只查 stars>0 的视频（无星级的不需要同步）
    3. 批量 commit（每 200 条一次，而非每条一次）
    4. 日志精简：只记录实际重命名的 + 错误；跳过的不逐条记录
    5. 进度更新降频（每 200 条更新一次 UI，避免重绘开销）
    6. 演员规则：有演员信息的不加叹号（对齐 Tk 业务逻辑）
    """
    core = main_window.core

    def task(progress_cb, log_cb, cancel_cb):
        # ---- 第 1 步：确定在线文件夹 ----
        log_cb("检查在线文件夹…")
        cur = core.conn.cursor()
        cur.execute("SELECT folder_path FROM folders WHERE is_active = 1")
        all_folders = [r[0] for r in cur.fetchall()]
        online_folders = [f for f in all_folders if f and os.path.exists(f)]
        log_cb(f"在线文件夹：{len(online_folders)} / {len(all_folders)}")
        if not online_folders:
            return "没有在线文件夹"

        # ---- 第 2 步：查询有星级评分的在线视频（带演员信息）----
        log_cb("查询有星级评分的视频…")
        # 用 source_folder LIKE 筛选在线文件夹下的视频 + stars>0
        # 只查需要的字段，避免取回全行
        folder_conds = " OR ".join(["source_folder LIKE ?"] * len(online_folders))
        folder_params = [f"{f}%{os.sep if not f.endswith(os.sep) else ''}" for f in online_folders]

        cur.execute(
            f"""SELECT v.id, v.file_path, v.file_name, v.stars,
                       (SELECT GROUP_CONCAT(a.name, ', ') FROM video_actors va
                        JOIN actors a ON va.actor_id = a.id
                        WHERE va.video_id = v.id) AS actors
                FROM videos v
                WHERE v.stars > 0 AND ({folder_conds})""",
            folder_params
        )
        videos = cur.fetchall()
        total = len(videos)
        log_cb(f"有星级评分的在线视频：{total} 个")
        if total == 0:
            return "没有需要同步的视频（无星级评分）"

        # ---- 第 3 步：逐个处理 ----
        renamed = skipped_no_change = skipped_offline = skipped_has_actor = error = 0
        batch_size = 200

        for i, (vid, fpath, fname, stars, actors) in enumerate(videos):
            if cancel_cb():
                log_cb("用户取消")
                break

            try:
                # 检查文件是否在线（快速判断）
                if not os.path.exists(fpath):
                    skipped_offline += 1
                    continue

                # 演员规则：有演员信息的不加叹号（对齐 Tk）
                has_actors = actors is not None and actors.strip() != ''
                if has_actors:
                    required_bangs = 0  # 有演员 → 不加叹号
                else:
                    required_bangs = max(0, stars - 1)  # stars-1 个叹号（1星=0, 2星=1...）

                # 计算当前叹号数
                name, ext = os.path.splitext(fname)
                current_bangs = 0
                clean_name = name
                while clean_name.startswith('!'):
                    current_bangs += 1
                    clean_name = clean_name[1:]

                # 叹号数已正确 → 跳过（不记日志，减少噪音）
                if current_bangs == required_bangs:
                    skipped_no_change += 1
                    continue

                # 生成新文件名
                new_fname = ('!' * required_bangs) + clean_name + ext
                new_path = os.path.join(os.path.dirname(fpath), new_fname)

                # 冲突处理（加序号）
                if os.path.exists(new_path) and new_path != fpath:
                    base, e = os.path.splitext(new_path)
                    n = 1
                    while os.path.exists(new_path):
                        new_path = f"{base}_{n}{e}"
                        n += 1
                    new_fname = os.path.basename(new_path)

                if new_path == fpath:
                    skipped_no_change += 1
                    continue

                # 重命名
                os.rename(fpath, new_path)
                cur.execute(
                    "UPDATE videos SET file_path=?, file_name=? WHERE id=?",
                    (new_path, new_fname, vid)
                )
                renamed += 1
                # 只记录实际重命名的（精简日志）
                log_cb(f"  重命名: {fname} → {new_fname}")

            except Exception as e:
                error += 1
                log_cb(f"  ⚠️ 错误: {fname} - {e}")

            # 批量 commit + 进度更新（降频）
            if (i + 1) % batch_size == 0 or i == total - 1:
                pct = int((i + 1) / total * 100)
                progress_cb(pct, f"处理 {i+1}/{total}（重命名 {renamed}）")
                core.conn.commit()

        core.conn.commit()
        cur.close()

        # 汇总（精简，只有关键数字）
        return (f"同步完成：重命名 {renamed}，跳过 {skipped_no_change + skipped_offline + skipped_has_actor}"
                f"（其中文件不存在 {skipped_offline}，叹号已正确 {skipped_no_change}），"
                f"错误 {error}（共 {total}）")

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
                if (i + 1) % 20 == 0 or i == total - 1:
                    pct = int((i + 1) / total * 100)
                    progress_cb(pct, f"计算 {i+1}/{total}（成功 {ok}）")
                    core.conn.commit()
                    # 日志降频：每 20 条记一次进度，不逐条记
                    if (i + 1) % 100 == 0:
                        log_cb(f"  [{i+1}/{total}] 已计算 {ok} 个，失败 {fail}")
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
                if (i + 1) % 10 == 0 or i == total - 1:
                    pct = int((i + 1) / total * 100)
                    progress_cb(pct, f"生成 {i+1}/{total}（成功 {ok}）")
                    core.conn.commit()
                    # 日志降频：每 50 条记一次进度
                    if (i + 1) % 50 == 0:
                        log_cb(f"  [{i+1}/{total}] 已生成 {ok} 个，失败 {fail}")
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
                    else:
                        fail += 1
                else:
                    fail += 1
                # 进度+日志降频
                if (i + 1) % 50 == 0 or i == total - 1:
                    pct = int((i + 1) / total * 100)
                    progress_cb(pct, f"导入 {i+1}/{total}（成功 {ok}）")
                    log_cb(f"  [{i+1}/{total}] 成功 {ok}，失败 {fail}")
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
