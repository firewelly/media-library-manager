#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一次性批量导入封面到数据库脚本

功能：
- 扫描指定目录中的封面图片（默认扫描 results/images 和 covers）
- 从文件名中提取番号（如 ABW-265、ADN-347、SSIS-xxx、FC2-PPV-xxxxx 等）
- 基于番号匹配：
  1) 优先匹配已存在的 javdb_info.javdb_code，然后更新其 local_cover_path 与 cover_image_data（BLOB）
  2) 若不存在 javdb_info 记录，则在 videos 表中通过 file_name/title/file_path LIKE 番号查找视频，插入一条 javdb_info 记录并写入封面
- 同步更新 videos.thumbnail_path，增强 GUI 显示覆盖面

注意：
- 有些图片没有 .jpg 后缀但实际上是 JPEG，本脚本会用 imghdr 识别并正常导入
- 仅处理能识别为图片的文件；遇到无法识别或无匹配视频的记录会跳过并打印提示
"""

import os
import re
import sqlite3
import imghdr
from typing import List, Tuple, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'media_library.db')

DEFAULT_SCAN_DIRS = [
    os.path.join(BASE_DIR, 'results', 'images'),
    os.path.join(BASE_DIR, 'covers'),
]


def is_image_file(path: str) -> bool:
    """粗略判断是否为图片文件：扩展名或 imghdr 能识别。"""
    if not os.path.isfile(path):
        return False
    ext = os.path.splitext(path)[1].lower()
    if ext in {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp'}:
        return True
    # 无扩展或不常见扩展，尝试用 imghdr 检测
    try:
        kind = imghdr.what(path)
        return kind is not None
    except Exception:
        return False


def extract_code_from_filename(filename: str) -> Optional[str]:
    """从文件名中提取番号。

    兼容常见格式：
    - 标准：ABW-265、ADN-347、SSIS-123 等
    - FC2：FC2-PPV-123456
    - 其他品牌：大写字母+可选字母段-数字段
    """
    name = os.path.basename(filename)
    # 常见特例优先：FC2-PPV-xxxxx
    m = re.search(r"(FC2-PPV-\d{3,7})", name, re.IGNORECASE)
    if m:
        return m.group(1).upper()

    # 通用：字母段（2+）-数字段（2-5），支持中间再带字母
    m = re.search(r"([A-Za-z]{2,}[A-Za-z]*-\d{2,5})", name)
    if m:
        return m.group(1).upper()

    # 次选：字母段后直接数字（如极少数无连字符场景）
    m = re.search(r"([A-Za-z]{2,}\d{2,5})", name)
    if m:
        return m.group(1).upper()

    return None


def read_image_bytes(path: str) -> Optional[bytes]:
    try:
        with open(path, 'rb') as f:
            return f.read()
    except Exception as e:
        print(f"读取图片失败：{path} -> {e}")
        return None


def ensure_tables(cursor: sqlite3.Cursor) -> None:
    """确保 javdb_info 表存在（与现有结构一致）。"""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS javdb_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER NOT NULL,
            javdb_code TEXT NOT NULL,
            javdb_url TEXT,
            javdb_title TEXT,
            release_date TEXT,
            duration TEXT,
            studio TEXT,
            series TEXT,
            score REAL,
            cover_url TEXT,
            local_cover_path TEXT,
            cover_image_data BLOB,
            magnet_links TEXT,
            tags TEXT,
            actors TEXT,
            source TEXT DEFAULT 'manual-import',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (video_id) REFERENCES videos (id) ON DELETE CASCADE,
            UNIQUE(video_id)
        )
        """
    )


def find_video_id_by_code(cursor: sqlite3.Cursor, code: str) -> Optional[int]:
    """基于番号查找 video_id：优先通过 javdb_info，再通过 videos LIKE 匹配。"""
    # 1) 优先 javdb_info
    cursor.execute(
        "SELECT video_id FROM javdb_info WHERE UPPER(javdb_code) = ?",
        (code.upper(),)
    )
    row = cursor.fetchone()
    if row and row[0]:
        return int(row[0])

    # 2) 回退 videos 表，通过文件名/标题/路径模糊匹配
    like = f"%{code}%"
    cursor.execute(
        """
        SELECT id FROM videos
        WHERE file_name LIKE ? OR title LIKE ? OR file_path LIKE ?
        ORDER BY id DESC LIMIT 1
        """,
        (like, like, like)
    )
    row = cursor.fetchone()
    return int(row[0]) if row else None


def upsert_cover_for_code(cursor: sqlite3.Cursor, video_id: int, code: str, img_path: str, img_bytes: bytes) -> None:
    """插入或更新某个 video 的 javdb_info 封面；同时更新 videos.thumbnail_path。"""
    # 是否已有记录
    cursor.execute("SELECT id FROM javdb_info WHERE video_id = ?", (video_id,))
    exists = cursor.fetchone() is not None

    if exists:
        cursor.execute(
            """
            UPDATE javdb_info
            SET javdb_code = ?, local_cover_path = ?, cover_image_data = ?, source = 'manual-import',
                updated_at = datetime('now')
            WHERE video_id = ?
            """,
            (code.upper(), img_path, img_bytes, video_id)
        )
    else:
        cursor.execute(
            """
            INSERT OR REPLACE INTO javdb_info (
                video_id, javdb_code, local_cover_path, cover_image_data, source, updated_at
            ) VALUES (?, ?, ?, ?, 'manual-import', datetime('now'))
            """,
            (video_id, code.upper(), img_path, img_bytes)
        )

    # 同步 videos.thumbnail_path（若列存在则更新）
    cursor.execute("PRAGMA table_info(videos);")
    cols = {row[1] for row in cursor.fetchall()}
    if 'thumbnail_path' in cols:
        cursor.execute(
            "UPDATE videos SET thumbnail_path = ? WHERE id = ?",
            (img_path, video_id)
        )


def scan_image_files(dirs: List[str]) -> List[str]:
    files = []
    for d in dirs:
        if not os.path.isdir(d):
            continue
        for root, _, filenames in os.walk(d):
            for fn in filenames:
                path = os.path.join(root, fn)
                if is_image_file(path):
                    files.append(path)
    return files


def main(scan_dirs: Optional[List[str]] = None) -> None:
    dirs = scan_dirs or DEFAULT_SCAN_DIRS
    print("扫描目录：")
    for d in dirs:
        print(f"- {d}")

    img_paths = scan_image_files(dirs)
    print(f"共发现 {len(img_paths)} 个候选图片文件")

    if not os.path.exists(DB_PATH):
        print(f"错误：找不到数据库文件 {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    ensure_tables(cursor)

    updated, inserted, skipped, unmatched = 0, 0, 0, 0

    for p in img_paths:
        code = extract_code_from_filename(p)
        if not code:
            print(f"跳过（无法提取番号）：{p}")
            skipped += 1
            continue

        img_bytes = read_image_bytes(p)
        if not img_bytes:
            print(f"跳过（无法读取图片）：{p}")
            skipped += 1
            continue

        video_id = find_video_id_by_code(cursor, code)
        if not video_id:
            print(f"未匹配到视频（番号={code}）：{p}")
            unmatched += 1
            continue

        # 判断是否更新或插入
        cursor.execute("SELECT id FROM javdb_info WHERE video_id = ?", (video_id,))
        existed = cursor.fetchone() is not None
        upsert_cover_for_code(cursor, video_id, code, p, img_bytes)
        if existed:
            updated += 1
        else:
            inserted += 1

    conn.commit()
    conn.close()

    print("\n导入完成：")
    print(f"- 更新记录：{updated}")
    print(f"- 新增记录：{inserted}")
    print(f"- 跳过文件：{skipped}")
    print(f"- 未匹配视频：{unmatched}")


if __name__ == '__main__':
    # 可按需传入自定义目录：main(["/path/to/images"]) 
    main()