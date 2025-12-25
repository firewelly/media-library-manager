#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
按番号复制并填充完整JAVDB字段（仅填充空值，支持可选覆盖），并在目标无演员关联时复制演员关系。

用法示例：
- 干跑预览：
  python copy_javdb_info_by_code.py --folder-index 11 --dry-run
- 正式入库（限制2条）：
  python copy_javdb_info_by_code.py --folder-index 11 --limit 2
- 覆盖已有值（非默认）：
  python copy_javdb_info_by_code.py --folder-index 11 --overwrite

说明：
- 根据选中文件夹中的视频，若其 `javdb_info` 缺失或存在空字段，则尝试按番号在数据库中查找有完整 `javdb_info` 的来源视频，
  将缺失的字段填充到目标（默认仅填充空字段）。
- 同步的字段范围：`javdb_info` 表的常见字段、`javdb_info_tags` 标签关联；此外，当目标视频当前没有任何演员关联时，会复制来源视频的 `video_actors` 关系（INSERT OR IGNORE）。
"""

import os
import re
import json
import sqlite3
import argparse
from urllib.parse import urlparse

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'media_library.db')


def get_domains():
    try:
        from config import get_javdb_base_url
        proxy_domain = urlparse(get_javdb_base_url(True)).netloc
        direct_domain = urlparse(get_javdb_base_url(False)).netloc
        domains = {proxy_domain, direct_domain}
    except Exception:
        domains = {'javdb.com'}
    return sorted([d for d in domains if d])


def list_management_folders(conn):
    """优先从 folders 表列出“管理文件夹”，若不存在则回退到 videos.source_folder。"""
    cursor = conn.cursor()
    # 优先使用 folders 表（仅活跃）
    try:
        cursor.execute("SELECT folder_path FROM folders WHERE is_active = 1 ORDER BY folder_path")
        rows = cursor.fetchall()
        if rows:
            return [ (row[0] or '').rstrip('/\\') for row in rows if (row[0] or '').strip() ]
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
    return [ (row[0] or '').rstrip('/\\') for row in rows if (row[0] or '').strip() ]


def clean_filename(name: str) -> str:
    name = (name or '').strip()
    # 去除常见噪声
    name = re.sub(r"[\[\]（）()]+", " ", name)
    name = re.sub(r"\s+", " ", name)
    return name


def fast_extract_code(text: str) -> str | None:
    t = clean_filename(text or '')
    # 常见番号：字母-数字或纯数字（如 FC2-PPV-123456, SNIS-886, TEAM-083, 259LUXU-123）
    patterns = [
        r"\b([A-Z]{2,5}-\d{2,6})\b",
        r"\b(FC2[- ]?PPV[- ]?\d{3,7})\b",
        r"\b(\d{3,6}[A-Z]{2,6}-\d{2,6})\b",
    ]
    for p in patterns:
        m = re.search(p, t, re.IGNORECASE)
        if m:
            return m.group(1).upper().replace(' ', '').replace('PPV-', 'PPV-')
    return None


def extract_code_for_video(file_path: str, title: str, code_in_db: str | None) -> str | None:
    c0 = (code_in_db or '').strip()
    if c0:
        return c0
    for src in [file_path, title]:
        c = fast_extract_code(src or '')
        if c:
            return c
    # 尝试增强/基础提取器（仅用文件名或标题，避免isfile路径检查）
    try:
        from enhanced_code_extractor import EnhancedCodeExtractor as PrimaryExtractor
    except Exception:
        PrimaryExtractor = None
    try:
        from code_extractor import CodeExtractor as FallbackExtractor
    except Exception:
        FallbackExtractor = None
    for src in [os.path.basename(file_path or ''), title or '']:
        t = (src or '').strip()
        if not t:
            continue
        if PrimaryExtractor:
            try:
                c = PrimaryExtractor.extract_code_from_filename(t)
                if c:
                    return c
            except Exception:
                pass
        if FallbackExtractor:
            try:
                c = FallbackExtractor.extract_code_from_filename(t)
                if c:
                    return c
            except Exception:
                pass
    return None


def build_source_index(conn) -> dict[str, list[int]]:
    """聚合所有拥有javdb_info的来源视频：code -> [video_id...]"""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT j.javdb_code, v.id
        FROM javdb_info j
        JOIN videos v ON v.id = j.video_id
        WHERE j.javdb_code IS NOT NULL AND j.javdb_code <> ''
        """
    )
    idx: dict[str, list[int]] = {}
    for code, vid in cursor.fetchall():
        c = (code or '').strip()
        if not c:
            continue
        idx.setdefault(c, []).append(vid)
    return idx


def get_table_columns(conn: sqlite3.Connection, table_name: str) -> list[str]:
    cur = conn.cursor()
    try:
        cur.execute(f"PRAGMA table_info({table_name})")
        return [row[1] for row in cur.fetchall()]
    except Exception:
        return []


def get_available_javdb_cols(conn: sqlite3.Connection) -> list[str]:
    """返回脚本期望字段与数据库实际字段的交集，按稳定顺序。"""
    preferred = [
        'javdb_code','javdb_url','javdb_title','release_date','duration','studio','series',
        'rating','score','cover_url','local_cover_path','cover_image_data','magnet_links','preview_images'
    ]
    actual = set(get_table_columns(conn, 'javdb_info'))
    return [c for c in preferred if c in actual]


def get_javdb_info_row(cursor: sqlite3.Cursor, video_id: int, cols: list[str]):
    if not cols:
        return None
    sel = ', '.join(cols)
    cursor.execute(
        f"""
        SELECT id, {sel}
        FROM javdb_info WHERE video_id = ?
        """,
        (video_id,)
    )
    row = cursor.fetchone()
    if not row:
        return None
    return {'id': row[0], **dict(zip(cols, row[1:]))}


def get_tags_for_javdb_info(cursor, javdb_info_id: int) -> list[str]:
    cursor.execute(
        """
        SELECT t.tag_name
        FROM javdb_info_tags jt JOIN javdb_tags t ON jt.tag_id = t.id
        WHERE jt.javdb_info_id = ?
        """,
        (javdb_info_id,)
    )
    return [row[0] for row in cursor.fetchall()]


def has_any_actors(cursor: sqlite3.Cursor, video_id: int) -> bool:
    """判断目标视频是否已有任何演员关联。"""
    try:
        cursor.execute("SELECT COUNT(1) FROM video_actors WHERE video_id = ?", (video_id,))
        return ((cursor.fetchone() or [0])[0] > 0)
    except Exception:
        return False


def copy_actor_links(conn: sqlite3.Connection, source_video_id: int, target_video_id: int, dry_run: bool = False) -> int:
    """将来源视频的演员关联复制到目标视频（INSERT OR IGNORE）。返回新增尝试的数量。"""
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT DISTINCT actor_id FROM video_actors WHERE video_id = ?", (source_video_id,))
        actor_ids = [row[0] for row in cursor.fetchall()]
    except Exception:
        actor_ids = []
    added = 0
    for aid in actor_ids:
        if dry_run:
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
        added += 1
    return added


def fill_empty_javdb_info(conn, source_video_id: int, target_video_id: int, dry_run: bool = False, overwrite: bool = False) -> bool:
    """将来源视频的javdb_info字段复制到目标：默认仅填充空值；支持覆盖。并复制标签关联（目标无标签时）。

    返回值仅在发生实际变更时为 True：插入新记录、更新了至少一个字段，或复制了至少一个标签。
    """
    cursor = conn.cursor()
    cols = get_available_javdb_cols(conn)
    s = get_javdb_info_row(cursor, source_video_id, cols)
    if not s:
        return False
    t = get_javdb_info_row(cursor, target_video_id, cols)

    # 便于输出
    cursor.execute("SELECT file_path FROM videos WHERE id = ?", (target_video_id,))
    tpath = (cursor.fetchone() or [""])[0] or ""

    sdict = s
    tdict = t if t else None

    # 插入或更新
    if not tdict:
        if dry_run:
            print(f"  [DRY-RUN] 插入完整javdb_info到: {tpath or ('视频ID=' + str(target_video_id))}")
            return True
        cursor.execute(
            f"""
            INSERT INTO javdb_info (
                video_id, {', '.join(cols)}, created_at, updated_at
            ) VALUES (
                ?, {', '.join(['?']*len(cols))}, datetime('now'), datetime('now')
            )
            """,
            (target_video_id,) + tuple(sdict.get(c) for c in cols)
        )
        return True

    # 已存在记录：决定更新内容
    updates = {}
    if overwrite:
        for c in cols:
            updates[c] = sdict.get(c)
    else:
        for c in cols:
            tv = tdict.get(c) if tdict else None
            sv = sdict.get(c)
            # 空判断：None 或 空字符串；BLOB与JSON文本也按空字符串视为空
            is_empty = (tv is None) or (isinstance(tv, str) and tv.strip() == '')
            if c == 'score':
                # 数值评分：仅当目标为None时填充
                is_empty = (tv is None)
            if is_empty and sv not in (None, ''):
                updates[c] = sv

    did_update = False
    if not updates:
        # 标签填充仍可进行
        pass
    else:
        if dry_run:
            filled = ", ".join(sorted(updates.keys()))
            print(f"  [DRY-RUN] 填充javdb_info空字段到: {tpath or ('视频ID=' + str(target_video_id))} | fields=<{filled}>")
            did_update = True
        else:
            set_clause = ", ".join([f"{k} = ?" for k in updates.keys()]) + ", updated_at = datetime('now')"
            params = list(updates.values()) + [target_video_id]
            cursor.execute(f"UPDATE javdb_info SET {set_clause} WHERE video_id = ?", params)
            did_update = True

    # 复制标签：仅当目标无任何标签关联时复制来源标签集合（标签表可能缺失，需容错）
    did_copy_tags = False
    try:
        cursor.execute("SELECT id FROM javdb_info WHERE video_id = ?", (target_video_id,))
        tinfo_row = cursor.fetchone()
        cursor.execute("SELECT id FROM javdb_info WHERE video_id = ?", (source_video_id,))
        sinfo_row = cursor.fetchone()
        if not (tinfo_row and sinfo_row):
            return did_update
        tinfo_id = tinfo_row[0]
        sinfo_id = sinfo_row[0]

        cursor.execute("SELECT COUNT(1) FROM javdb_info_tags WHERE javdb_info_id = ?", (tinfo_id,))
        has_target_tags = (cursor.fetchone() or [0])[0] > 0
        if not has_target_tags:
            src_tag_names = get_tags_for_javdb_info(cursor, sinfo_id)
            if src_tag_names:
                if dry_run:
                    print(f"  [DRY-RUN] 复制JAVDB标签到目标，共 {len(src_tag_names)} 个")
                    did_copy_tags = True
                else:
                    # 写入标签并建立关联
                    for tag_name in src_tag_names:
                        tn = (tag_name or '').strip()
                        if not tn:
                            continue
                        cursor.execute("INSERT OR IGNORE INTO javdb_tags (tag_name) VALUES (?)", (tn,))
                        cursor.execute("SELECT id FROM javdb_tags WHERE tag_name = ?", (tn,))
                        row = cursor.fetchone()
                        if not row:
                            continue
                        tag_id = row[0]
                        cursor.execute(
                            "INSERT OR IGNORE INTO javdb_info_tags (javdb_info_id, tag_id) VALUES (?, ?)",
                            (tinfo_id, tag_id)
                        )
                    did_copy_tags = True
    except Exception:
        pass

    return did_update or did_copy_tags

def score_javdb_info(cursor: sqlite3.Cursor, video_id: int, cols: list[str]) -> tuple[int, str]:
    """计算来源视频的javdb_info完整度与更新时间，用于来源优先级排序。
    - 完整度：非空字段数量（None或空字符串视为空）；
    - 更新时间：`updated_at`文本，作为同分时的降序次序。
    """
    try:
        cursor.execute(
            f"SELECT {', '.join(cols)}, updated_at FROM javdb_info WHERE video_id = ?",
            (video_id,)
        )
        row = cursor.fetchone()
        if not row:
            return (0, '')
        values = row[:-1]
        updated_at = row[-1] or ''
        score = 0
        for v in values:
            if v is None:
                continue
            if isinstance(v, str) and v.strip() == '':
                continue
            score += 1
        return (score, updated_at)
    except Exception:
        return (0, '')


def build_targets_query(conn: sqlite3.Connection, selected_folder: str):
    """选中文件夹中的目标视频：无javdb_info，或核心字段缺失（javdb_title为空且无演员关联）。"""
    where_folder = "(v.source_folder = ? OR v.source_folder = ? OR v.source_folder LIKE ? OR v.file_path LIKE ?)"
    sql = f"""
        SELECT v.id, v.file_path, v.title, j.javdb_code
        FROM videos v
        LEFT JOIN javdb_info j ON v.id = j.video_id
        WHERE {where_folder}
          AND (
              j.video_id IS NULL
              OR (
                  (j.javdb_title IS NULL OR j.javdb_title = '')
                  AND NOT EXISTS (
                      SELECT 1 FROM video_actors va WHERE va.video_id = v.id
                  )
              )
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


def main():
    parser = argparse.ArgumentParser(description="按番号填充完整JAVDB字段（仅填充空值，支持覆盖）")
    parser.add_argument('--db-path', default=DB_PATH, help='SQLite数据库路径，默认当前目录下media_library.db')
    parser.add_argument('--list-folders', action='store_true', help='仅打印文件夹列表并退出')
    parser.add_argument('--folder-index', type=int, help='非交互模式选择文件夹索引（从1开始）')
    parser.add_argument('--dry-run', action='store_true', help='干跑模式，仅打印计划变更，不写入数据库')
    parser.add_argument('--overwrite', action='store_true', help='覆盖已有非空字段（默认不覆盖）')
    parser.add_argument('--limit', type=int, help='仅处理成功落库的目标数量上限（默认不限制）')

    args = parser.parse_args()

    conn = sqlite3.connect(args.db_path)
    try:
        folders = list_management_folders(conn)
        print("可选管理文件夹（folders 或 source_folder）：")
        for idx, folder in enumerate(folders, start=1):
            print(f"  {idx}. {folder}")
        if args.list_folders:
            return

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

        # 查询目标
        sql, params = build_targets_query(conn, selected_folder)
        cursor = conn.cursor()
        cursor.execute(sql, params)
        targets = cursor.fetchall()
        if not targets:
            print("选中文件夹下没有需要填充javdb字段的视频。")
            return
        print(f"需处理视频数：{len(targets)}")

        print("正在构建来源索引（按番号聚合有javdb_info的视频）...")
        source_index = build_source_index(conn)
        print(f"来源编号数：{len(source_index)}")

        total = len(targets)
        success = 0
        failed = 0

        for i, (video_id, file_path, title, code_in_db) in enumerate(targets, start=1):
            print(f"[{i}/{total}] 处理: {file_path or '(无路径记录)'} (ID={video_id})")
            av_code = extract_code_for_video(file_path, title, code_in_db)
            if not av_code:
                print("  无法提取番号，跳过。")
                failed += 1
                continue
            print(f"  番号: {av_code}")

            source_ids = [sid for sid in source_index.get(av_code, []) if sid != video_id]
            if not source_ids:
                print("  未找到同番号来源视频（已排除自身），跳过。")
                failed += 1
                continue

            # 对来源进行优先级排序：完整度优先，其次更新时间（降序）
            cols = get_available_javdb_cols(conn)
            scored_sources = []
            for sid in source_ids:
                s_score, s_updated = score_javdb_info(cursor, sid, cols)
                scored_sources.append((sid, s_score, s_updated))
            scored_sources.sort(key=lambda x: (x[1], x[2]), reverse=True)
            ordered_source_ids = [sid for sid, _, _ in scored_sources]

            # 提示最高优先来源
            if scored_sources:
                top_sid, top_score, top_updated = scored_sources[0]
                try:
                    cursor.execute("SELECT file_path FROM videos WHERE id = ?", (top_sid,))
                    top_fp = (cursor.fetchone() or [""])[0] or ""
                except Exception:
                    top_fp = ""
                print(f"  优先来源: {top_fp or '(无路径记录)'} (ID={top_sid}) | 完整度={top_score}, 更新时间={top_updated}")

            updated_any = False
            actors_added_total = 0
            target_has_actors = has_any_actors(cursor, video_id)
            for sid in ordered_source_ids:
                try:
                    cursor.execute("SELECT file_path FROM videos WHERE id = ?", (sid,))
                    src_fp = (cursor.fetchone() or [""])[0] or ""
                except Exception:
                    src_fp = ""
                print(f"  来源: {src_fp or '(无路径记录)'} (ID={sid})")

                changed = fill_empty_javdb_info(conn, sid, video_id, dry_run=args.dry_run, overwrite=args.overwrite)
                if changed:
                    updated_any = True
                    # 若目标无演员关联，尝试复制来源演员关系
                    if not target_has_actors:
                        added = copy_actor_links(conn, sid, video_id, dry_run=args.dry_run)
                        actors_added_total += added
                        if added > 0:
                            target_has_actors = True
                    # 一旦成功填充/更新（且已尝试演员复制），通常无需继续其他来源
                    break

                # 即使未发生字段更新，若目标无演员关联，也可以尝试仅复制演员关系
                if not target_has_actors:
                    added = copy_actor_links(conn, sid, video_id, dry_run=args.dry_run)
                    actors_added_total += added
                    if added > 0:
                        target_has_actors = True
                        updated_any = True
                        # 已完成演员复制，无需继续其他来源
                        break

            if not args.dry_run:
                conn.commit()

            if updated_any:
                success += 1
                if actors_added_total > 0:
                    print(f"  完成：填充/更新javdb_info及标签关联，并复制演员 {actors_added_total} 条")
                else:
                    print("  完成：填充/更新javdb_info及标签关联")
                if args.limit and success >= args.limit:
                    print(f"\n达到处理上限：{args.limit} 条，提前结束。")
                    break
            else:
                failed += 1
                print("  跳过：无空字段或已有标签，无实际变更。")

        print("\n处理完成：")
        print(f"  成功视频数：{success}")
        print(f"  失败视频数：{failed}")

    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == '__main__':
    main()