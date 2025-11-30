import os
import sqlite3
from typing import Dict, Any, List, Optional, Tuple

DB_FILENAME = 'media_library.db'

def get_connection(base_dir: str) -> sqlite3.Connection:
    db_path = os.path.join(base_dir, DB_FILENAME)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def upsert_actors(conn: sqlite3.Connection, actors: List[Dict[str, Any]]) -> List[int]:
    cur = conn.cursor()
    actor_ids = []
    for actor in actors:
        name = actor.get('name') or actor.get('name_common') or actor.get('name_traditional')
        if not name:
            continue
        cur.execute("SELECT id FROM actors WHERE name = ?", (name,))
        row = cur.fetchone()
        if row:
            actor_ids.append(row['id'])
        else:
            cur.execute("INSERT INTO actors(name) VALUES (?)", (name,))
            actor_ids.append(cur.lastrowid)
    conn.commit()
    return actor_ids

def link_video_actor(conn: sqlite3.Connection, video_id: int, actor_id: int, actor_name: str):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO video_actors(video_id, actor_id, actor_name) VALUES (?, ?, ?)",
        (video_id, actor_id, actor_name)
    )
    conn.commit()

def upsert_tags(conn: sqlite3.Connection, tags: List[str]) -> List[int]:
    cur = conn.cursor()
    tag_ids = []
    for tag in tags:
        cur.execute("SELECT id FROM javdb_tags WHERE tag_name = ?", (tag,))
        row = cur.fetchone()
        if row:
            tag_ids.append(row['id'])
        else:
            cur.execute("INSERT INTO javdb_tags(tag_name) VALUES (?)", (tag,))
            tag_ids.append(cur.lastrowid)
    conn.commit()
    return tag_ids

def upsert_jav_info(
    conn: sqlite3.Connection,
    video_id: int,
    info: Dict[str, Any]
) -> int:
    cur = conn.cursor()
    cur.execute("SELECT id FROM javdb_info WHERE video_id = ?", (video_id,))
    row = cur.fetchone()
    fields = {
        'javdb_code': info.get('javdb_code') or info.get('code'),
        'javdb_title': info.get('javdb_title') or info.get('title'),
        'javdb_description': info.get('javdb_description') or info.get('description'),
        'javdb_rating': info.get('rating'),
        'javdb_cover_url': info.get('cover_image_url') or info.get('cover_url'),
        'release_date': info.get('release_date')
    }
    if row:
        cur.execute(
            "UPDATE javdb_info SET javdb_code=?, javdb_title=?, javdb_description=?, javdb_rating=?, javdb_cover_url=?, release_date=?, updated_at=CURRENT_TIMESTAMP WHERE video_id=?",
            (
                fields['javdb_code'], fields['javdb_title'], fields['javdb_description'],
                fields['javdb_rating'], fields['javdb_cover_url'], fields['release_date'], video_id
            )
        )
        info_id = row['id']
    else:
        cur.execute(
            "INSERT INTO javdb_info(video_id, javdb_code, javdb_title, javdb_description, javdb_rating, javdb_cover_url, release_date) VALUES (?,?,?,?,?,?,?)",
            (
                video_id,
                fields['javdb_code'], fields['javdb_title'], fields['javdb_description'],
                fields['javdb_rating'], fields['javdb_cover_url'], fields['release_date']
            )
        )
        info_id = cur.lastrowid
    conn.commit()
    # 处理标签关联
    tags = info.get('tags') or []
    tag_ids = upsert_tags(conn, tags)
    for tid in tag_ids:
        cur.execute("INSERT INTO javdb_info_tags(javdb_info_id, tag_id) VALUES (?,?)", (info_id, tid))
    conn.commit()
    # 处理演员关联
    actors = info.get('actors') or []
    actor_ids = upsert_actors(conn, [{'name': a} for a in actors])
    for aid, name in zip(actor_ids, actors):
        link_video_actor(conn, video_id, aid, name)
    return info_id

