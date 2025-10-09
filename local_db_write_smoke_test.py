import os
import sqlite3
import json

# 为了导入更新器模块并复用其持久化函数
import javdb_information_updater as updater


def ensure_videos_table(conn):
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY,
            title TEXT,
            tags TEXT,
            duration TEXT,
            rating REAL,
            thumbnail_path TEXT,
            thumbnail_data BLOB
        )
        """
    )
    # 最小化创建演员与关联表，便于验证关系型写入
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS actors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            profile_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS video_actors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER NOT NULL,
            actor_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(video_id, actor_id)
        )
        """
    )
    conn.commit()


def run_smoke_test(db_path):
    # 重定向更新器的数据库路径到临时文件
    updater.DB_PATH = db_path

    # 准备数据库与基础表
    conn = sqlite3.connect(db_path)
    ensure_videos_table(conn)
    cursor = conn.cursor()

    # 插入一个测试视频记录
    cursor.execute(
        "INSERT OR REPLACE INTO videos (id, title, tags, duration, rating) VALUES (?, ?, ?, ?, ?)",
        (1, '占位标题', '占位标签', '90', 3.2)
    )
    conn.commit()
    conn.close()

    # 构造更新数据（模拟爬虫返回的数据）
    result = {
        'title': 'ADN-347 测试标题',
        'video_id': 'ADN-347',
        'detail_url': 'https://javdb.com/v/xxxx',
        'release_date': '2023-10-01',
        'duration': '120',
        'rating': '4.5',
        'tags': ['剧情', '已婚'],
        'actors': [
            {'name': '女演员A', 'link': 'https://javdb.com/actors/aaa'},
            {'name': '女演员B', 'link': 'https://javdb.com/actors/bbb'},
        ],
        'studio': 'Attackers',
        'cover_image_url': 'https://example.com/cover.jpg',
        'local_image_path': None,
        'magnet_links': [
            'magnet:?xt=urn:btih:ABC123&dn=ADN-347',
            'magnet:?xt=urn:btih:DEF456&dn=ADN-347'
        ]
    }

    # 调用持久化函数
    ok = updater.update_video_info(
        1,
        title=result['title'],
        actors=result['actors'],
        tags=result['tags'],
        studio=result['studio'],
        release_date=result['release_date'],
        duration=result['duration'],
        rating=result['rating'],
        cover_image_path=result.get('local_image_path'),
        javdb_code=result.get('video_id'),
        javdb_url=result.get('detail_url'),
        cover_image_url=result.get('cover_image_url'),
        magnet_links=result.get('magnet_links'),
    )

    # 验证写入效果
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT video_id, javdb_code, javdb_url, javdb_title, release_date, duration, studio, rating, score, cover_url, local_cover_path, magnet_links FROM javdb_info WHERE video_id = ?", (1,))
    row = cursor.fetchone()
    conn.close()

    print("写入成功?", ok)
    if not row:
        print("未找到 javdb_info 记录，写入失败")
        return

    video_id, code, url, jtitle, rdate, dur, studio, rating, score, c_url, local_path, magnets = row
    print("javdb_info 字段预览:")
    print("- video_id:", video_id)
    print("- javdb_code:", code)
    print("- javdb_url:", url)
    print("- javdb_title:", jtitle)
    print("- release_date:", rdate)
    print("- duration:", dur)
    print("- studio:", studio)
    print("- rating:", rating)
    print("- score:", score)
    print("- cover_url:", c_url)
    print("- local_cover_path:", local_path)
    print("- magnet_links:", magnets)

    # 验证关系型标签与演员写入
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM javdb_info WHERE video_id = ?", (1,))
    info_row = cursor.fetchone()
    if info_row:
        info_id = info_row[0]
        cursor.execute("""
            SELECT t.tag_name FROM javdb_info_tags it
            JOIN javdb_tags t ON it.tag_id = t.id
            WHERE it.javdb_info_id = ?
        """, (info_id,))
        tag_rows = cursor.fetchall()
        print("JAVDB 标签:", [r[0] for r in tag_rows])

    cursor.execute("""
        SELECT a.name, a.profile_url FROM video_actors va
        JOIN actors a ON va.actor_id = a.id
        WHERE va.video_id = ?
    """, (1,))
    actor_rows = cursor.fetchall()
    print("演员关联:", actor_rows)
    conn.close()


if __name__ == '__main__':
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, 'tmp_smoke.db')
    # 清理旧文件
    try:
        if os.path.exists(db_path):
            os.remove(db_path)
    except Exception:
        pass

    run_smoke_test(db_path)