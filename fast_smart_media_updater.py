#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速智能媒体库更新器

仅针对指定的源文件夹进行快速扫描与数据库同步：
- 新建文件：插入到数据库
- 已存在且未变化：跳过
- 发生移动：更新路径与来源文件夹
- 已删除：移除数据库记录（可关闭）

设计目标：
- 仅处理用户选择的在线文件夹，避免全库扫描
- 以 source_folder 作为查询范围，减少内存占用
- 支持按需MD5匹配识别移动（路径变更）
"""

import argparse
import os
import sqlite3
import sys
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Set, Tuple

DB_NAME = "media_library.db"

# 统一的视频扩展名集合（可根据需要调整）
VIDEO_EXTS = {
    ".mp4", ".mkv", ".avi", ".wmv", ".mov", ".flv", ".webm", ".ts", ".m2ts", ".mpg", ".mpeg"
}

# 额外过滤小文件：跳过 < 2MB 文件
SMALL_FILE_MIN_SIZE = 2 * 1024 * 1024


def db_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), DB_NAME)


def connect_db() -> sqlite3.Connection:
    path = db_path()
    if not os.path.exists(path):
        print(f"❌ 数据库文件不存在: {path}")
        sys.exit(1)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def is_video_file(file_name: str) -> bool:
    return os.path.splitext(file_name)[1].lower() in VIDEO_EXTS


def iter_folder_files(folder: str) -> List[Tuple[str, str, int]]:
    """遍历文件夹，返回 (path, name, size) 列表，跳过 <2MB 小文件。"""
    files: List[Tuple[str, str, int]] = []
    for root, _, names in os.walk(folder):
        for name in names:
            if not is_video_file(name):
                continue
            full = os.path.join(root, name)
            try:
                size = os.path.getsize(full)
            except OSError:
                continue
            if size < SMALL_FILE_MIN_SIZE:
                # 过滤过小文件，减少噪音与无效数据
                continue
            files.append((full, name, size))
    return files


def md5_of_file(path: str, chunk_size: int = 4 * 1024 * 1024) -> Optional[str]:
    """高效计算文件MD5（按需使用）。"""
    try:
        import hashlib
        h = hashlib.md5()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


# --- MD5 缓存：使用本地 md5_cache.json，键为 path + mtime + size ---
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "md5_cache.json")

def load_md5_cache() -> Dict[str, str]:
    try:
        import json
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return {str(k): str(v) for k, v in data.items()}
    except Exception:
        pass
    return {}


def save_md5_cache(cache: Dict[str, str]) -> None:
    try:
        import json
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def cache_key_for(path: str) -> Optional[str]:
    try:
        st = os.stat(path)
        return f"{path}|{int(st.st_mtime)}|{st.st_size}"
    except Exception:
        return None


def md5_with_cache(path: str, cache: Dict[str, str]) -> Optional[str]:
    key = cache_key_for(path)
    if not key:
        return md5_of_file(path)
    hit = cache.get(key)
    if hit:
        return hit
    value = md5_of_file(path)
    if value:
        cache[key] = value
    return value


@dataclass
class FolderStats:
    new_count: int = 0
    unchanged_count: int = 0
    updated_count: int = 0
    moved_count: int = 0
    deleted_count: int = 0


def load_active_folders(conn: sqlite3.Connection) -> List[str]:
    cur = conn.cursor()
    cur.execute("SELECT folder_path FROM folders WHERE is_active = 1")
    rows = [r[0] for r in cur.fetchall()]
    # 仅返回当前存在的路径（在线）
    return [p for p in rows if isinstance(p, str) and p.strip() and os.path.exists(p)]


def load_db_records_for_folder(conn: sqlite3.Connection, folder: str) -> List[sqlite3.Row]:
    """限定在该文件夹范围内的记录（按 source_folder 或路径前缀匹配）。"""
    cur = conn.cursor()
    prefix = folder.rstrip("/") + "/"
    # 使用两个条件保证兼容历史数据
    cur.execute(
        """
        SELECT id, file_path, file_name, file_size, md5_hash, source_folder
        FROM videos
        WHERE source_folder = ? OR file_path LIKE ?
        """,
        (folder, prefix + "%"),
    )
    return cur.fetchall()


def load_db_maps(conn: sqlite3.Connection) -> Tuple[Dict[str, List[sqlite3.Row]], Dict[str, List[sqlite3.Row]]]:
    """构建 DB 的辅助映射：md5 -> rows，filename -> rows（用于迁移检测）。"""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, file_path, file_name, file_size, md5_hash, source_folder
        FROM videos
        WHERE md5_hash IS NOT NULL AND md5_hash <> ''
        """
    )
    rows = cur.fetchall()
    md5_to_rows: Dict[str, List[sqlite3.Row]] = {}
    name_to_rows: Dict[str, List[sqlite3.Row]] = {}
    for r in rows:
        md5 = r["md5_hash"]
        fn = r["file_name"] or ""
        if md5:
            md5_to_rows.setdefault(md5, []).append(r)
        if fn:
            name_to_rows.setdefault(fn, []).append(r)
    return md5_to_rows, name_to_rows


def batch_update_md5(conn: sqlite3.Connection, md5_updates: List[Tuple[str, int]]) -> None:
    if not md5_updates:
        return
    cur = conn.cursor()
    cur.executemany(
        "UPDATE videos SET md5_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        md5_updates,
    )
    conn.commit()


def get_video_info(path: str) -> Tuple[Optional[float], Optional[str]]:
    """获取视频时长和分辨率，失败则返回 (None, None)。"""
    duration = None
    resolution = None
    try:
        import cv2  # type: ignore
        cap = cv2.VideoCapture(path)
        if cap.isOpened():
            fps = cap.get(cv2.CAP_PROP_FPS) or 0
            frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
            if fps > 0 and frames > 0:
                duration = frames / fps
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
            if w > 0 and h > 0:
                resolution = f"{w}x{h}"
        cap.release()
    except Exception:
        pass
    return duration, resolution


def parse_title_and_stars(file_name: str) -> Tuple[str, int]:
    """从文件名解析标题与星级：! 数量映射到 2-5 星。"""
    base = os.path.splitext(file_name)[0]
    exclamations = base.count("!")
    stars = 0
    if exclamations > 0:
        stars = min(5, max(2, exclamations + 1))
    title = base.replace("!", "").strip()
    return title, stars


def process_folder(
    conn: sqlite3.Connection,
    folder: str,
    enable_md5: bool = False,
    dry_run: bool = False,
    delete_missing: bool = True,
    cache: Optional[Dict[str, str]] = None,
    md5_to_rows: Optional[Dict[str, List[sqlite3.Row]]] = None,
    name_to_rows: Optional[Dict[str, List[sqlite3.Row]]] = None,
    progress: Optional[Callable[[str], None]] = None,
) -> FolderStats:
    stats = FolderStats()

    # 读取磁盘文件（该文件夹范围内）
    disk_files = iter_folder_files(folder)
    disk_by_path: Dict[str, Tuple[str, int]] = {p: (n, s) for p, n, s in disk_files}

    # 读取DB记录（限定在该文件夹范围内）
    db_rows = load_db_records_for_folder(conn, folder)
    db_by_path: Dict[str, sqlite3.Row] = {row["file_path"]: row for row in db_rows if row["file_path"]}

    cur = conn.cursor()

    # 0) 预先填充MD5缓存：将数据库中已有MD5的记录预填到缓存，避免重复计算
    if enable_md5 and cache is not None:
        for row in db_rows:
            md5 = row["md5_hash"] or ""
            if not md5:
                continue
            p = row["file_path"]
            if not p:
                continue
            try:
                st = os.stat(p)
                key = f"{p}|{int(st.st_mtime)}|{st.st_size}"
                if key not in cache:
                    cache[key] = md5
            except OSError:
                pass

    # 0) 预先补齐该文件夹范围内缺失的MD5（串行计算，支持进度显示）
    if enable_md5:
        md5_updates: List[Tuple[str, int]] = []  # (md5, id)
        for row in db_rows:
            if not row["file_path"]:
                continue
            md5_existing = row["md5_hash"] or ""
            if md5_existing:
                continue
            p = row["file_path"]
            try:
                if not os.path.exists(p):
                    continue
                size = os.path.getsize(p)
                if size < SMALL_FILE_MIN_SIZE:
                    continue
            except Exception:
                continue
            md5 = md5_with_cache(p, cache or {})
            if progress:
                progress(f"补齐MD5: {os.path.basename(p)} -> {md5 or '计算失败'}")
            if md5:
                md5_updates.append((md5, row["id"]))
                # 更新映射以便后续迁移检测更全面
                if md5_to_rows is not None:
                    md5_to_rows.setdefault(md5, []).append(row)
        if md5_updates and not dry_run:
            batch_update_md5(conn, md5_updates)

    # 1) 处理磁盘上的文件：新增/未变/更新大小/移动
    for path, (name, size) in disk_by_path.items():
        row = db_by_path.get(path)
        if row:
            # 在库中存在该路径
            db_size = row["file_size"] or 0
            if db_size == size:
                stats.unchanged_count += 1
            else:
                stats.updated_count += 1
                if not dry_run:
                    cur.execute(
                        "UPDATE videos SET file_size = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (size, row["id"]),
                    )
            # 将已有记录的MD5预填到缓存，下次即使记录被误删也可跳过文件读取
            if enable_md5 and cache is not None:
                md5_existing = row["md5_hash"] or ""
                if md5_existing:
                    try:
                        ck = cache_key_for(path)
                        if ck and ck not in cache:
                            cache[ck] = md5_existing
                    except Exception:
                        pass
            continue

        # 不在该路径：可能是新建或移动
        moved = False
        match_row: Optional[sqlite3.Row] = None
        if enable_md5:
            # 复用缓存或串行计算
            md5 = md5_with_cache(path, cache or {})
            if progress:
                progress(f"MD5: {name} -> {md5 or '计算失败'}")
            if md5:
                # 一级策略：MD5匹配（最精准），处理多命中时优先同名
                candidates = []
                if md5_to_rows is not None:
                    candidates = md5_to_rows.get(md5, [])
                else:
                    # 回退到查询数据库
                    cur.execute("SELECT id, file_path, file_name, source_folder FROM videos WHERE md5_hash = ?", (md5,))
                    candidates = cur.fetchall()
                # 仅考虑当前文件夹内的候选项
                folder_prefix = folder.rstrip("/") + "/"
                candidates = [r for r in candidates if (r["source_folder"] == folder) or ((r["file_path"] or "").startswith(folder_prefix))]
                if candidates:
                    # 优先同名
                    same_name = [r for r in candidates if (r["file_name"] or "") == name]
                    match_row = (same_name[0] if same_name else candidates[0])
        if match_row is None and enable_md5:
            # 二级回退：文件名匹配，必要时再比对MD5以消歧
            candidates = []
            if name_to_rows is not None:
                candidates = name_to_rows.get(name, [])
            else:
                cur.execute("SELECT id, file_path, file_name, source_folder, md5_hash FROM videos WHERE file_name = ?", (name,))
                candidates = cur.fetchall()
            # 仅考虑当前文件夹内的候选项
            folder_prefix = folder.rstrip("/") + "/"
            candidates = [r for r in candidates if (r["source_folder"] == folder) or ((r["file_path"] or "").startswith(folder_prefix))]
            if candidates:
                if len(candidates) == 1:
                    match_row = candidates[0]
                else:
                    # 多命中时，如果已算MD5则用MD5消歧
                    md5 = md5_with_cache(path, cache or {})
                    if md5:
                        md5_filtered = [r for r in candidates if (r["md5_hash"] or "") == md5]
                        if md5_filtered:
                            match_row = md5_filtered[0]
                        else:
                            match_row = candidates[0]

        if match_row:
            moved = True
            stats.moved_count += 1
            if not dry_run:
                # 避免重复：若新路径已有记录则合并/删除重复ID
                existing_new = db_by_path.get(path)
                if existing_new and existing_new["id"] != match_row["id"]:
                    cur.execute("DELETE FROM videos WHERE id = ?", (existing_new["id"],))
                cur.execute(
                    "UPDATE videos SET file_path = ?, source_folder = ?, file_size = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (path, folder, size, match_row["id"]),
                )
        else:
            # 作为新文件插入
            stats.new_count += 1
            if not dry_run:
                # 插入包含丰富元数据，并同步抽取视频信息
                duration, resolution = get_video_info(path)
                title, stars = parse_title_and_stars(name)
                # 新建记录强制计算MD5（去重基础字段），不受enable_md5控制
                md5_val = md5_with_cache(path, cache or {})
                cur.execute(
                    """
                    INSERT OR IGNORE INTO videos (
                        file_path, file_name, title, stars, file_size, source_folder,
                        md5_hash, duration, resolution, file_created_time, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    (
                        path,
                        name,
                        title,
                        stars,
                        size,
                        folder,
                        md5_val or None,
                        duration,
                        resolution,
                        int(os.path.getctime(path)) if os.path.exists(path) else None,
                    ),
                )

    # 2) 处理数据库中记录：磁盘不存在的视为删除
    # 注意：os.walk 可能因 NAS 延迟/权限问题跳过部分文件
    # 此处二次确认文件确实不存在再删除，避免误删后下次重新扫描
    if delete_missing:
        for row in db_rows:
            p = row["file_path"]
            if not p:
                continue
            if p not in disk_by_path:
                if os.path.exists(p):
                    continue
                stats.deleted_count += 1
                if not dry_run:
                    cur.execute("DELETE FROM videos WHERE id = ?", (row["id"],))

    if not dry_run:
        conn.commit()

    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="快速智能媒体库更新器（按选定文件夹）")
    parser.add_argument("--folders", nargs="*", help="要更新的源文件夹路径（可多个）")
    parser.add_argument("--all-active", action="store_true", help="使用数据库中处于激活且在线的所有文件夹")
    parser.add_argument("--enable-md5", action="store_true", help="为未知文件计算MD5以检测移动（较慢但更准确）")
    parser.add_argument("--quiet", action="store_true", help="减少日志输出")
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不实际写入数据库")
    parser.add_argument("--no-delete", action="store_true", help="不删除数据库中缺失的文件记录")
    return parser.parse_args()


def run_fast_update(
    folders: List[str],
    enable_md5: bool = False,
    dry_run: bool = False,
    delete_missing: bool = True,
    quiet: bool = False,
    progress: Optional[Callable[[str], None]] = None,
) -> Dict[str, FolderStats]:
    conn = connect_db()
    # 去重并过滤不存在的路径
    target_folders = [os.path.abspath(f) for f in folders if isinstance(f, str) and f.strip() and os.path.exists(f)]
    seen: Set[str] = set()
    target_folders = [f for f in target_folders if not (f in seen or seen.add(f))]

    if not target_folders:
        if progress and not quiet:
            progress("未选择有效文件夹，任务结束。")
        return {}

    cache = load_md5_cache() if enable_md5 else {}
    md5_to_rows, name_to_rows = load_db_maps(conn) if enable_md5 else ({}, {})

    results: Dict[str, FolderStats] = {}
    for folder in target_folders:
        if progress and not quiet:
            progress(f"处理文件夹: {folder}")
        stats = process_folder(
            conn,
            folder,
            enable_md5=enable_md5,
            dry_run=dry_run,
            delete_missing=delete_missing,
            cache=cache,
            md5_to_rows=md5_to_rows,
            name_to_rows=name_to_rows,
            progress=progress,
        )
        results[folder] = stats

    # 保存缓存（仅在开启MD5时）
    if enable_md5 and not dry_run:
        save_md5_cache(cache)

    if progress and not quiet:
        total_new = sum(s.new_count for s in results.values())
        total_move = sum(s.moved_count for s in results.values())
        total_update = sum(s.updated_count for s in results.values())
        total_delete = sum(s.deleted_count for s in results.values())
        progress(f"汇总: 新增 {total_new}, 移动 {total_move}, 更新 {total_update}, 删除 {total_delete}")

    return results


def main():
    args = parse_args()
    conn = connect_db()

    target_folders: List[str] = []

    if args.all_active:
        active = load_active_folders(conn)
        target_folders.extend(active)
    if args.folders:
        target_folders.extend(args.folders)

    # 规范化 & 去重
    norm: List[str] = []
    seen: Set[str] = set()
    for p in target_folders:
        if not isinstance(p, str):
            continue
        q = os.path.abspath(p)
        if q in seen:
            continue
        seen.add(q)
        # 仅处理在线文件夹
        if os.path.exists(q) and os.path.isdir(q):
            norm.append(q)
        else:
            print(f"⚠️ 跳过不存在或非目录的路径: {q}")

    if not norm:
        print("❌ 没有可处理的在线文件夹。请使用 --folders 或 --all-active。")
        return

    print("快速智能更新开始")
    print("=" * 30)
    print(f"目标文件夹数: {len(norm)}")
    print(f"预览模式: {'是' if args.dry_run else '否'}；删除缺失: {'否' if args.no_delete else '是'}；MD5匹配: {'是' if args.enable_md5 else '否'}")

    total = FolderStats()
    t0 = time.time()

    for folder in norm:
        print(f"\n>>> 处理文件夹: {folder}")
        stats = process_folder(
            conn,
            folder,
            enable_md5=args.enable_md5,
            dry_run=args.dry_run,
            delete_missing=not args.no_delete,
        )
        print(
            f"新增 {stats.new_count}，未变 {stats.unchanged_count}，更新 {stats.updated_count}，移动 {stats.moved_count}，删除 {stats.deleted_count}"
        )

        # 汇总
        total.new_count += stats.new_count
        total.unchanged_count += stats.unchanged_count
        total.updated_count += stats.updated_count
        total.moved_count += stats.moved_count
        total.deleted_count += stats.deleted_count

    t1 = time.time()
    print("\n=== 总结 ===")
    print(
        f"新增 {total.new_count}，未变 {total.unchanged_count}，更新 {total.updated_count}，移动 {total.moved_count}，删除 {total.deleted_count}"
    )
    print(f"耗时: {t1 - t0:.1f}s")


if __name__ == "__main__":
    main()