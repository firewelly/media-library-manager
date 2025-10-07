import os
import csv
import sqlite3
from typing import Optional, List


def normalize_path(p: str) -> str:
    if not p:
        return p
    p2 = p.replace('\\', '/')
    if len(p2) > 1 and p2.endswith('/'):
        p2 = p2[:-1]
    return p2


def best_folder_match(file_dir: str, active_folders: List[str]) -> Optional[str]:
    file_dir_n = normalize_path(file_dir)
    best = None
    best_len = -1
    for f in active_folders:
        f_n = normalize_path(f)
        if file_dir_n.startswith(f_n) and len(f_n) > best_len:
            best = f
            best_len = len(f_n)
    return best


def load_active_folders(cursor) -> List[str]:
    cursor.execute("SELECT folder_path FROM folders WHERE is_active = 1")
    rows = cursor.fetchall()
    return [row[0] for row in rows]


def main():
    base_dir = os.path.dirname(__file__)
    db_path = os.path.join(base_dir, 'media_library.db')
    out_dir = os.path.join(base_dir, 'reports')
    os.makedirs(out_dir, exist_ok=True)
    out_csv = os.path.join(out_dir, 'folder_reassociation_preview.csv')

    if not os.path.exists(db_path):
        print(f"未找到数据库: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    active_folders = load_active_folders(cursor)

    cursor.execute("SELECT id, file_path, file_name, source_folder FROM videos")
    rows = cursor.fetchall()

    matched = 0
    unmatched = 0
    will_update = 0

    with open(out_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'video_id',
            'file_path',
            'file_name',
            'current_source_folder',
            'proposed_source_folder',
            'matched_active_folder',
            'folder_match_found',
            'will_update_source_folder'
        ])

        for vid, file_path, file_name, source_folder in rows:
            file_dir = normalize_path(os.path.dirname(file_path or ''))
            match_folder = best_folder_match(file_dir, active_folders) if file_dir else None
            folder_match_found = 'yes' if match_folder else 'no'
            if match_folder:
                matched += 1
            else:
                unmatched += 1
            proposed_source = file_dir
            will_update_flag = 'yes' if (source_folder != proposed_source) else 'no'
            if will_update_flag == 'yes':
                will_update += 1

            writer.writerow([
                vid,
                file_path or '',
                file_name or '',
                normalize_path(source_folder or ''),
                proposed_source or '',
                normalize_path(match_folder or ''),
                folder_match_found,
                will_update_flag,
            ])

    conn.close()
    print(f"CSV已生成: {out_csv}")
    print(f"匹配到激活文件夹: {matched}, 未匹配: {unmatched}, 需要更新source_folder: {will_update}")


if __name__ == '__main__':
    main()