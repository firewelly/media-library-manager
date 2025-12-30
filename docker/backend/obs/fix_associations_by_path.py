import os
import sqlite3
from typing import Optional, Tuple

# 尝试导入项目中的番号提取器
try:
    from enhanced_code_extractor import EnhancedCodeExtractor
except Exception:
    EnhancedCodeExtractor = None

try:
    from code_extractor import CodeExtractor
except Exception:
    CodeExtractor = None


def normalize_path(p: str) -> str:
    if not p:
        return p
    # 统一分隔符与去除尾部斜杠
    p2 = p.replace('\\', '/')
    if len(p2) > 1 and p2.endswith('/'):
        p2 = p2[:-1]
    return p2


def best_folder_match(file_dir: str, active_folders: list[str]) -> Optional[str]:
    """在激活的文件夹中查找最长前缀匹配的目录路径。"""
    file_dir_n = normalize_path(file_dir)
    best = None
    best_len = -1
    for f in active_folders:
        f_n = normalize_path(f)
        if file_dir_n.startswith(f_n) and len(f_n) > best_len:
            best = f
            best_len = len(f_n)
    return best


def extract_code(filename: str, filepath: str) -> Optional[str]:
    """从文件名/路径中提取番号，优先使用增强版提取器（仅用文件名以避免慢文件检查）。"""
    # 优先只用文件名（避免对完整路径进行 isfile 等慢操作）
    if EnhancedCodeExtractor:
        try:
            e = EnhancedCodeExtractor()
            code = e.extract_code_from_filename(filename or '')
            if code:
                return code
        except Exception:
            pass
    # 回退到基础提取器，允许用完整路径
    if CodeExtractor:
        try:
            c = CodeExtractor()
            code = c.extract_code_from_filename(filename or filepath)
            if code:
                return code
            code = c.extract_code_from_filename(filepath)
            if code:
                return code
        except Exception:
            pass
    return None


def load_active_folders(cursor) -> list[str]:
    cursor.execute("SELECT folder_path FROM folders WHERE is_active = 1")
    rows = cursor.fetchall()
    return [row[0] for row in rows]


def reassociate_videos_by_path(db_path: str) -> Tuple[int, int, int]:
    """
    基于路径为视频重建文件夹关联，并补齐缺失的source_folder。

    返回: (更新source_folder数量, 已有关联匹配数量, 无匹配数量)
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    active_folders = load_active_folders(cursor)

    cursor.execute("SELECT id, file_path, file_name, source_folder FROM videos")
    rows = cursor.fetchall()

    updated = 0
    matched = 0
    unmatched = 0

    for vid, file_path, file_name, source_folder in rows:
        if not file_path:
            continue
        file_dir = os.path.dirname(file_path)
        file_dir_n = normalize_path(file_dir)
        best_match = best_folder_match(file_dir_n, active_folders)
        if best_match:
            matched += 1
        else:
            unmatched += 1
        # source_folder 统一为文件所在目录（保证与导入逻辑一致）
        if source_folder != file_dir_n:
            cursor.execute(
                "UPDATE videos SET source_folder = ? WHERE id = ?",
                (file_dir_n, vid),
            )
            updated += 1

    conn.commit()
    conn.close()
    return updated, matched, unmatched


def upsert_missing_javdb_code(db_path: str) -> Tuple[int, int]:
    """为缺失 javdb_code 的视频进行番号提取并插入/更新到 javdb_info。返回 (插入数量, 更新数量)。"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 找出没有 javdb_info 或者 javdb_code 为空的记录
    cursor.execute(
        """
        SELECT v.id, v.file_name, v.file_path, j.id, j.javdb_code
        FROM videos v
        LEFT JOIN javdb_info j ON j.video_id = v.id
        WHERE j.id IS NULL OR j.javdb_code IS NULL OR j.javdb_code = ''
        """
    )
    rows = cursor.fetchall()

    inserted = 0
    updated = 0

    batch = 0
    for video_id, file_name, file_path, j_id, j_code in rows:
        code = extract_code(file_name or '', file_path or '')
        if not code:
            continue
        code_norm = code.strip().upper()
        if j_id is None:
            # 插入新记录，尽量只填必要字段，其余置空
            cursor.execute(
                """
                INSERT INTO javdb_info (video_id, javdb_code, created_at, updated_at)
                VALUES (?, ?, datetime('now'), datetime('now'))
                """,
                (video_id, code_norm),
            )
            inserted += 1
        else:
            # 仅更新 javdb_code
            cursor.execute(
                "UPDATE javdb_info SET javdb_code = ?, updated_at = datetime('now') WHERE id = ?",
                (code_norm, j_id),
            )
            updated += 1

        batch += 1
        if batch % 500 == 0:
            conn.commit()

    conn.commit()
    conn.close()
    return inserted, updated


def main():
    db_path = os.path.join(os.path.dirname(__file__), 'media_library.db')
    if not os.path.exists(db_path):
        print(f"未找到数据库文件: {db_path}")
        return

    print("开始基于路径重建视频的文件夹关联 ...")
    upd, ok, no = reassociate_videos_by_path(db_path)
    print(f"source_folder更新: {upd}, 匹配到激活文件夹: {ok}, 未匹配: {no}")

    print("开始补全缺失的javdb_code关联 ...")
    ins, upd2 = upsert_missing_javdb_code(db_path)
    print(f"javdb_info插入: {ins}, javdb_code更新: {upd2}")

    print("处理完成。")


if __name__ == '__main__':
    main()