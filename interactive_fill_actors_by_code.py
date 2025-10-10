#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交互式一次性工具：按番号复制演员关联

状态：失效（待修复）
原因：当前脚本仅复制 javdb_info 部分基础字段（code/url/title/studio/release_date/rating），
缺少诸多JAVDB字段的处理与同步，包括但不限于：series、duration、tags、cover_image_url、
cover_image_data/local_cover_path、magnet_links 等。因此暂时标记为失效，待修复完善后再启用。

功能概述（历史参考，当前禁用）：
- 列出数据库中 `videos.source_folder` 的所有文件夹供用户选择；
- 针对选中文件夹下“没有JAVDB演员信息”的视频，按提取到的番号在数据库中查找其他已有演员关联的视频；
- 将这些演员关联（`video_actors`）复制到目标视频，避免重复（UNIQUE约束下INSERT OR IGNORE）。

可选（历史参考，当前禁用）：
- 支持复制基础的 `javdb_info` 字段到目标视频（如不存在该视频的javdb_info），通过 `--copy-javdb-info` 开启。
- 支持干跑模式，不落库，仅打印计划变更。
- 支持非交互模式：直接打印文件夹列表或指定文件夹索引。
"""

import os
import sys
import sqlite3
import argparse
from urllib.parse import urlparse

# 复用番号提取器（增强版优先，回退到基础版）
try:
    from enhanced_code_extractor import EnhancedCodeExtractor as PrimaryExtractor
except Exception:
    PrimaryExtractor = None
try:
    from code_extractor import CodeExtractor as FallbackExtractor
except Exception:
    FallbackExtractor = None

try:
    from config import get_javdb_base_url
except Exception:
    # 简单兜底：若无法加载配置，直接使用常见域名
    def get_javdb_base_url(use_proxy: bool = True):
        return 'https://www.javdb.com'


DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'media_library.db')

# 标记脚本失效（待修复）
SCRIPT_DEPRECATED = True
DEPRECATION_REASON = (
    "当前脚本仅复制 javdb_info 的部分字段（code/url/title/studio/release_date/rating），"
    "缺少 series、duration、tags、cover_image_url、cover_image_data/local_cover_path、magnet_links 等字段的处理。"
)


def get_domains():
    """返回可能的JAVDB域名（代理/直连两种）。"""
    try:
        proxy_domain = urlparse(get_javdb_base_url(True)).netloc
        direct_domain = urlparse(get_javdb_base_url(False)).netloc
        domains = {proxy_domain, direct_domain}
    except Exception:
        domains = {'javdb.com'}
    # 过滤空
    return sorted([d for d in domains if d])


def list_management_folders(conn):
    """优先从 folders 表列出“管理文件夹”，若不存在则回退到 videos.source_folder。"""
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT folder_path FROM folders WHERE is_active = 1 ORDER BY folder_path")
        rows = cursor.fetchall()
        if rows:
            return [row[0] for row in rows]
    except Exception:
        pass
    # 回退：distinct source_folder
    cursor.execute(
        """
        SELECT DISTINCT source_folder
        FROM videos
        WHERE source_folder IS NOT NULL AND TRIM(source_folder) <> ''
        ORDER BY source_folder
        """
    )
    rows = cursor.fetchall()
    return [row[0] for row in rows]


def build_missing_actors_query(selected_folder: str, only_javdb: bool, domains: list[str]):
    """构建查询：选中文件夹下缺少演员关联的视频。
    - 若 only_javdb=True，则仅认为“缺少JAVDB域名演员链接”的视频为目标；
    - 若 only_javdb=False，则认为“没有任何演员关联”的视频为目标。
    """
    # 在 file_path 上也做包含匹配，兼容部分记录未填 source_folder 的情况
    where_folder = "(v.source_folder = ? OR v.source_folder = ? OR v.source_folder LIKE ? OR v.file_path LIKE ?)"
    if only_javdb:
        domain_like = " OR ".join(["a.profile_url LIKE ?" for _ in domains])
        sql = f"""
            SELECT v.id, v.file_path, v.title, j.javdb_code
            FROM videos v
            LEFT JOIN javdb_info j ON v.id = j.video_id
            WHERE {where_folder}
            AND NOT EXISTS (
                SELECT 1 FROM video_actors va
                JOIN actors a ON va.actor_id = a.id
                WHERE va.video_id = v.id
                  AND ({domain_like})
            )
            ORDER BY v.id
        """
        params = [
            selected_folder.rstrip('/\\'),
            selected_folder.rstrip('/\\') + '/',
            selected_folder.rstrip('/\\') + '/%',
            selected_folder.rstrip('/\\') + '/%'
        ] + [f"%{d}%" for d in domains]
        return sql, params
    else:
        sql = f"""
            SELECT v.id, v.file_path, v.title, j.javdb_code
            FROM videos v
            LEFT JOIN javdb_info j ON v.id = j.video_id
            WHERE {where_folder}
            AND NOT EXISTS (
                SELECT 1 FROM video_actors va
                WHERE va.video_id = v.id
            )
            ORDER BY v.id
        """
        params = [
            selected_folder.rstrip('/\\'),
            selected_folder.rstrip('/\\') + '/',
            selected_folder.rstrip('/\\') + '/%',
            selected_folder.rstrip('/\\') + '/%'
        ]
        return sql, params


def extract_code_for_video(file_path: str, title: str | None, code_in_db: str | None):
    """提取视频番号：
    1) 优先使用数据库中的 `javdb_code`；
    2) 使用快速正则从文件名解析（避免慢磁盘I/O）；
    3) 回退到增强/基础提取器，仅使用文件名或标题，不对完整路径做 isfile 检查。
    """
    # 1) 数据库字段优先
    if code_in_db and str(code_in_db).strip():
        return str(code_in_db).strip()

    filename = os.path.basename(file_path or '')

    # 2) 快速正则提取（文件名）
    import re
    m = re.search(r"(FC2-PPV-\d{3,7})", filename, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    m = re.search(r"([A-Za-z]{2,}[A-Za-z]*-\d{2,5})", filename)
    if m:
        return m.group(1).upper()
    m = re.search(r"([A-Za-z]{2,}\d{2,5})", filename)
    if m:
        return m.group(1).upper()

    # 3) 增强版（仅文件名/标题）
    if PrimaryExtractor:
        try:
            e = PrimaryExtractor()
            code = e.extract_code_from_filename(filename)
            if code:
                return code
            if title:
                code = e.extract_code_from_filename(title)
                if code:
                    return code
        except Exception:
            pass

    # 4) 基础版（文件名/标题）
    if FallbackExtractor:
        try:
            c = FallbackExtractor()
            code = c.extract_code_from_filename(filename)
            if code:
                return code
            if title:
                code = c.extract_code_from_filename(title)
                if code:
                    return code
        except Exception:
            pass
    return None


def has_actor_associations(conn, video_id: int, only_javdb: bool, domains: list[str]) -> bool:
    """判断视频是否存在演员关联，支持仅限JAVDB域名或全部。"""
    cursor = conn.cursor()
    if only_javdb:
        domain_like = " OR ".join(["a.profile_url LIKE ?" for _ in domains])
        cursor.execute(
            f"""
            SELECT COUNT(*)
            FROM video_actors va
            JOIN actors a ON va.actor_id = a.id
            WHERE va.video_id = ? AND ({domain_like})
            """,
            [video_id] + [f"%{d}%" for d in domains]
        )
    else:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM video_actors va
            WHERE va.video_id = ?
            """,
            (video_id,)
        )
    return ((cursor.fetchone() or [0])[0] > 0)


def find_source_video_ids_by_code(conn, av_code: str, only_javdb: bool, domains: list[str]):
    """查找同番号的源视频ID列表，优先使用 javdb_info；无匹配时回退扫描 videos。"""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT v.id
        FROM javdb_info j
        JOIN videos v ON v.id = j.video_id
        WHERE j.javdb_code = ?
        ORDER BY v.id
        """,
        (av_code,)
    )
    candidate_ids = [row[0] for row in cursor.fetchall()]
    sources = [vid for vid in candidate_ids if has_actor_associations(conn, vid, only_javdb, domains)]
    if sources:
        return sources

    # 回退：扫描 videos，提取番号后匹配
    cursor.execute("SELECT id, file_path, title FROM videos")
    rows = cursor.fetchall()
    matched = []
    for vid, fp, tt in rows:
        code2 = extract_code_for_video(fp or '', tt or '', None)
        if code2 and code2 == av_code and has_actor_associations(conn, vid, only_javdb, domains):
            matched.append(vid)
    return matched


def build_source_index(conn, only_javdb: bool, domains: list[str]) -> dict:
    """构建来源索引：编号 -> 已有演员关联的视频ID列表。
    1) 优先使用 javdb_info 的编号；
    2) 对无 javdb_info 的视频，按文件名/标题解析编号加入索引；
    """
    idx: dict[str, list[int]] = {}
    cursor = conn.cursor()
    # 1) 先从 javdb_info 聚合
    if only_javdb:
        domain_like = " OR ".join(["a.profile_url LIKE ?" for _ in domains])
        cursor.execute(
            f"""
            SELECT j.javdb_code, v.id
            FROM javdb_info j
            JOIN videos v ON v.id = j.video_id
            WHERE EXISTS (
                SELECT 1 FROM video_actors va
                JOIN actors a ON va.actor_id = a.id
                WHERE va.video_id = v.id AND ({domain_like})
            )
            """,
            [f"%{d}%" for d in domains]
        )
    else:
        cursor.execute(
            """
            SELECT j.javdb_code, v.id
            FROM javdb_info j
            JOIN videos v ON v.id = j.video_id
            WHERE EXISTS (
                SELECT 1 FROM video_actors va
                WHERE va.video_id = v.id
            )
            """
        )
    for code, vid in cursor.fetchall():
        c = (code or '').strip()
        if not c:
            continue
        idx.setdefault(c, []).append(vid)

    # 2) 仅针对“有演员关联但缺失 javdb_info”的视频做补充提取（减少扫描量）
    if only_javdb:
        domain_like = " OR ".join(["a.profile_url LIKE ?" for _ in domains])
        cursor.execute(
            f"""
            SELECT v.id, v.file_path, v.title
            FROM videos v
            WHERE NOT EXISTS (SELECT 1 FROM javdb_info j WHERE j.video_id = v.id)
              AND EXISTS (
                SELECT 1 FROM video_actors va JOIN actors a ON va.actor_id=a.id
                WHERE va.video_id=v.id AND ({domain_like})
              )
            """,
            [f"%{d}%" for d in domains]
        )
    else:
        cursor.execute(
            """
            SELECT v.id, v.file_path, v.title
            FROM videos v
            WHERE NOT EXISTS (SELECT 1 FROM javdb_info j WHERE j.video_id = v.id)
              AND EXISTS (SELECT 1 FROM video_actors va WHERE va.video_id=v.id)
            """
        )
    for vid, fp, tt in cursor.fetchall():
        av_code = extract_code_for_video(fp or '', tt or '', None)
        if av_code:
            idx.setdefault(av_code, []).append(vid)
    return idx


def get_actor_ids_for_video(conn, video_id: int, only_javdb: bool, domains: list[str]):
    """获取视频的演员ID，支持仅限JAVDB域名或全部。"""
    cursor = conn.cursor()
    if only_javdb:
        domain_like = " OR ".join(["a.profile_url LIKE ?" for _ in domains])
        cursor.execute(
            f"""
            SELECT DISTINCT a.id
            FROM video_actors va
            JOIN actors a ON va.actor_id = a.id
            WHERE va.video_id = ? AND ({domain_like})
            """,
            [video_id] + [f"%{d}%" for d in domains]
        )
    else:
        cursor.execute(
            """
            SELECT DISTINCT actor_id
            FROM video_actors
            WHERE video_id = ?
            """,
            (video_id,)
        )
    return [row[0] for row in cursor.fetchall()]


def maybe_copy_javdb_info(conn, source_video_id: int, target_video_id: int, dry_run: bool = False, overwrite: bool = False):
    """复制/更新目标视频的 `javdb_info`。
    - 默认行为（overwrite=False）：若目标存在记录，仅填充空字段；若不存在则插入整条记录。
    - overwrite=True：目标存在记录时覆盖基础字段（code/url/title/studio/release_date/rating）。
    """
    cursor = conn.cursor()

    # 源记录
    cursor.execute(
        """
        SELECT javdb_code, javdb_url, javdb_title, studio, release_date, rating
        FROM javdb_info WHERE video_id = ?
        """,
        (source_video_id,)
    )
    srow = cursor.fetchone()
    if not srow:
        return False
    (s_code, s_url, s_title, s_studio, s_release, s_rating) = srow

    # 目标记录（含id与字段）
    cursor.execute(
        """
        SELECT id, javdb_code, javdb_url, javdb_title, studio, release_date, rating
        FROM javdb_info WHERE video_id = ?
        """,
        (target_video_id,)
    )
    trow = cursor.fetchone()

    # 获取目标视频路径用于输出
    try:
        cursor.execute("SELECT file_path FROM videos WHERE id = ?", (target_video_id,))
        tpath = (cursor.fetchone() or [""])[0] or ""
    except Exception:
        tpath = ""

    if not trow:
        # 插入新记录
        if dry_run:
            print(f"  [DRY-RUN] 插入javdb_info到: {tpath or ('视频ID=' + str(target_video_id))} | code={s_code}, rating={s_rating}")
            return True
        cursor.execute(
            """
            INSERT INTO javdb_info (
                video_id, javdb_code, javdb_url, javdb_title, studio, release_date, rating,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """,
            (target_video_id, s_code, s_url, s_title, s_studio, s_release, s_rating)
        )
        return True

    # 已存在记录：根据 overwrite 决定填充策略
    (t_id, t_code, t_url, t_title, t_studio, t_release, t_rating) = trow

    if overwrite:
        if dry_run:
            print(f"  [DRY-RUN] 覆盖更新javdb_info到: {tpath or ('视频ID=' + str(target_video_id))} | code={s_code}, rating={s_rating}")
            return True
        cursor.execute(
            """
            UPDATE javdb_info
            SET javdb_code = ?, javdb_url = ?, javdb_title = ?, studio = ?, release_date = ?, rating = ?,
                updated_at = datetime('now')
            WHERE video_id = ?
            """,
            (s_code, s_url, s_title, s_studio, s_release, s_rating, target_video_id)
        )
        return True

    # 非覆盖：仅填充空字段（不改动已有非空值）
    # 空的定义：None 或 空字符串（数字字段仅判断 None）
    updates = {}
    if (t_code is None or (isinstance(t_code, str) and t_code.strip() == "")) and s_code:
        updates['javdb_code'] = s_code
    if (t_url is None or (isinstance(t_url, str) and t_url.strip() == "")) and s_url:
        updates['javdb_url'] = s_url
    if (t_title is None or (isinstance(t_title, str) and t_title.strip() == "")) and s_title:
        updates['javdb_title'] = s_title
    if (t_studio is None or (isinstance(t_studio, str) and t_studio.strip() == "")) and s_studio:
        updates['studio'] = s_studio
    if (t_release is None or (isinstance(t_release, str) and t_release.strip() == "")) and s_release:
        updates['release_date'] = s_release
    if (t_rating is None) and (s_rating is not None):
        updates['rating'] = s_rating

    if not updates:
        return False

    if dry_run:
        filled = ", ".join(sorted(updates.keys()))
        print(f"  [DRY-RUN] 填充javdb_info空字段到: {tpath or ('视频ID=' + str(target_video_id))} | fields=<{filled}>")
        return True

    set_clause = ", ".join([f"{k} = ?" for k in updates.keys()]) + ", updated_at = datetime('now')"
    params = list(updates.values()) + [target_video_id]
    cursor.execute(f"UPDATE javdb_info SET {set_clause} WHERE video_id = ?", params)
    return True


def copy_actor_links(conn, source_video_id: int, target_video_id: int, dry_run: bool = False):
    """将源视频的演员关联复制到目标视频（INSERT OR IGNORE）。返回新增的数量。"""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT DISTINCT actor_id FROM video_actors WHERE video_id = ?
        """,
        (source_video_id,)
    )
    actor_ids = [row[0] for row in cursor.fetchall()]
    added = 0
    for aid in actor_ids:
        if dry_run:
            # 打印目标文件路径以提升可读性
            try:
                cursor.execute("SELECT file_path FROM videos WHERE id = ?", (target_video_id,))
                tpath = (cursor.fetchone() or [""])[0] or ""
            except Exception:
                tpath = ""
            print(f"  [DRY-RUN] 关联演员 {aid} -> {tpath or ('视频ID=' + str(target_video_id))}")
            added += 1
            continue
        cursor.execute(
            """
            INSERT OR IGNORE INTO video_actors (video_id, actor_id, created_at)
            VALUES (?, ?, datetime('now'))
            """,
            (target_video_id, aid)
        )
        # 统计实际新增（IGNORE不抛错但可能未新增）
        added += 1
    return added


def main():
    # 入口处直接阻止运行
    if SCRIPT_DEPRECATED:
        print("[已失效/待修复] interactive_fill_actors_by_code.py 当前不可用。")
        print("原因：" + DEPRECATION_REASON)
        print("建议：请使用 `javdb_information_updater.py` 或后续修复版脚本进行完整的JAVDB字段同步。")
        sys.exit(1)
    parser = argparse.ArgumentParser(description="按番号复制演员关联（交互式）")
    parser.add_argument('--db-path', default=DB_PATH, help='SQLite数据库路径，默认当前目录下media_library.db')
    parser.add_argument('--list-folders', dest='list_folders', action='store_true', help='仅打印文件夹列表并退出')
    parser.add_argument('--folder-index', type=int, help='非交互模式选择文件夹索引（从1开始）')
    parser.add_argument('--dry-run', action='store_true', help='干跑模式，仅打印计划变更，不写入数据库')
    parser.add_argument('--copy-javdb-info', action='store_true', help='如目标视频不存在javdb_info，复制基础字段')
    parser.add_argument('--only-javdb-actors', action='store_true', help='仅复制含JAVDB域名链接的演员关联（默认复制全部演员关联）')
    parser.add_argument('--overwrite-javdb-info', action='store_true', help='如目标已存在javdb_info则覆盖更新字段')
    parser.add_argument('--limit', type=int, help='仅处理成功落库的目标数量上限（默认不限制）')

    args = parser.parse_args()

    conn = sqlite3.connect(args.db_path)
    try:
        folders = list_management_folders(conn)
        if not folders:
            print("数据库中未找到任何 source_folder 记录。")
            return

        # 打印文件夹列表
        print("可选管理文件夹（folders 或 source_folder）：")
        for idx, folder in enumerate(folders, start=1):
            print(f"  {idx}. {folder}")

        if args.list_folders:
            return

        # 选择文件夹索引
        if args.folder_index and 1 <= args.folder_index <= len(folders):
            selected_folder = folders[args.folder_index - 1]
            print(f"\n选择文件夹：{selected_folder}")
        else:
            raw = input("\n请输入要处理的文件夹编号（例如 1）：").strip()
            try:
                idx = int(raw)
                assert 1 <= idx <= len(folders)
                selected_folder = folders[idx - 1]
            except Exception:
                print("输入无效，退出。")
                return

        domains = get_domains()
        if args.only_javdb_actors:
            print(f"匹配JAVDB域名：{', '.join(domains)}")
        else:
            print("匹配任何演员关联（不限制域名）")

        # 查询需要处理的视频
        sql, params = build_missing_actors_query(selected_folder, args.only_javdb_actors, domains)
        cursor = conn.cursor()
        cursor.execute(sql, params)
        targets = cursor.fetchall()
        if not targets:
            print("选中文件夹下没有需要补全演员信息的视频。")
            return
        print(f"需处理视频数：{len(targets)}")

        # 构建一次来源索引，避免每个目标都做全表扫描
        print("正在构建来源索引（按番号聚合已有演员的来源视频）...")
        source_index = build_source_index(conn, args.only_javdb_actors, domains)
        print(f"来源编号数：{len(source_index)}")

        # 开始处理
        total = len(targets)
        success = 0
        failed = 0
        copied_links = 0
        copied_info = 0

        for i, (video_id, file_path, title, code_in_db) in enumerate(targets, start=1):
            print(f"[{i}/{total}] 处理: {file_path or '(无路径记录)'} (ID={video_id})")
            av_code = extract_code_for_video(file_path, title, code_in_db)
            if not av_code:
                print("  无法提取番号，跳过。")
                failed += 1
                continue
            print(f"  番号: {av_code}")

            source_ids = source_index.get(av_code, [])
            if not source_ids:
                print("  未找到同番号来源视频（已有演员关联），跳过。")
                failed += 1
                continue

            # 选择第一个作为来源（也可遍历全部来源合并）
            added_total_for_video = 0
            info_copied_for_video = False
            for sid in source_ids:
                try:
                    cursor.execute("SELECT file_path, title FROM videos WHERE id = ?", (sid,))
                    src_fp, src_title = (cursor.fetchone() or ["", ""])[:2]
                except Exception:
                    src_fp, src_title = "", ""
                print(f"  来源: {src_fp or '(无路径记录)'} (ID={sid})")
                # 复制演员关联
                added = copy_actor_links(conn, sid, video_id, dry_run=args.dry_run)
                added_total_for_video += added

                # 可选复制javdb_info
                if args.copy_javdb_info:
                    if maybe_copy_javdb_info(conn, sid, video_id, dry_run=args.dry_run, overwrite=args.overwrite_javdb_info):
                        info_copied_for_video = True

            if not args.dry_run:
                conn.commit()

            if added_total_for_video > 0 or info_copied_for_video:
                success += 1
                copied_links += added_total_for_video
                copied_info += (1 if info_copied_for_video else 0)
                print(f"  完成：新增演员关联 {added_total_for_video} 条" + ("，复制javdb_info" if info_copied_for_video else ""))
                # 若设置了处理上限，则在达到上限后提前结束
                if args.limit and success >= args.limit:
                    print(f"\n达到处理上限：{args.limit} 条，提前结束。")
                    break
            else:
                failed += 1
                print("  未新增任何关联或信息，可能已存在或来源为空。")

        print("\n处理完成：")
        print(f"  成功视频数：{success}")
        print(f"  失败视频数：{failed}")
        print(f"  新增演员关联总数：{copied_links}")
        if args.copy_javdb_info:
            print(f"  复制javdb_info的目标视频数：{copied_info}")

    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == '__main__':
    main()