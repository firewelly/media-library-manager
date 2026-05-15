#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JAVDB系统 - 数据持久化模块
从 media_library.py 第 8873-8999 行、第 3424-3480 行提取

函数说明:
  - save_javdb_info_to_db(video_id, javdb_info): 保存JAVDB信息到数据库
  - load_javdb_details(video_id): 加载JAVDB详情信息显示在界面

字段映射 (Json Key → DB Column):
  video_id          → javdb_info.javdb_code
  detail_url        → javdb_info.javdb_url
  title             → javdb_info.javdb_title
  release_date      → javdb_info.release_date
  duration          → javdb_info.duration
  studio            → javdb_info.studio
  rating/score      → javdb_info.score (float, "N/A"=NULL)
  cover_image_url   → javdb_info.cover_url
  local_image_path  → javdb_info.local_cover_path
  cover_image_data  → javdb_info.cover_image_data (BLOB)
  magnet_links      → javdb_info.magnet_links (JSON序列化)
  tags (list[str])  → javdb_tags + javdb_info_tags (多对多)
  actors (list[dict]) → actors + video_actors (多对多)
"""

import json
import os


def save_javdb_info_to_db(self, video_id, javdb_info):
    """
    保存JAVDB信息到数据库
    
    Args:
        video_id: 视频ID (videos表主键)
        javdb_info: 爬虫返回的字典数据
    
    数据库操作:
        1. 读取本地封面图片 → BLOB
        2. 如果已存在记录则UPDATE，否则INSERT
        3. 保存标签到 javdb_tags + javdb_info_tags
        4. 保存演员到 actors + video_actors
    """
    try:
        # 读取本地图片文件并转换为二进制数据
        cover_image_data = None
        local_image_path = javdb_info.get('local_image_path', '')
        if local_image_path and os.path.exists(local_image_path):
            try:
                with open(local_image_path, 'rb') as f:
                    cover_image_data = f.read()
            except Exception as e:
                print(f"Failed to read image file {local_image_path}: {e}")
        
        # 检查是否已存在该video_id的JAVDB信息
        self.cursor.execute("SELECT id FROM javdb_info WHERE video_id = ?", (video_id,))
        existing_record = self.cursor.fetchone()
        
        if existing_record:
            # 更新已有记录
            javdb_info_id = existing_record[0]
            self.cursor.execute("""
                UPDATE javdb_info SET 
                javdb_code = ?, javdb_url = ?, javdb_title = ?, release_date = ?, duration = ?,
                studio = ?, score = ?, cover_url = ?, local_cover_path = ?, cover_image_data = ?,
                magnet_links = ?, updated_at = datetime('now')
                WHERE video_id = ?
            """, (
                javdb_info.get('video_id', ''),
                javdb_info.get('detail_url', ''),
                javdb_info.get('title', ''),
                javdb_info.get('release_date', ''),
                javdb_info.get('duration', ''),
                javdb_info.get('studio', ''),
                float(javdb_info.get('rating', 0)) if javdb_info.get('rating') and javdb_info.get('rating') != 'N/A' else None,
                javdb_info.get('cover_image_url', ''),
                javdb_info.get('local_image_path', ''),
                cover_image_data,
                json.dumps(javdb_info.get('magnet_links', []), ensure_ascii=False),
                video_id
            ))
            
            # 清除旧的标签和演员关联
            self.cursor.execute("DELETE FROM javdb_info_tags WHERE javdb_info_id = ?", (javdb_info_id,))
            self.cursor.execute("DELETE FROM video_actors WHERE video_id = ?", (video_id,))
        else:
            # 插入新记录
            self.cursor.execute("""
                INSERT INTO javdb_info 
                (video_id, javdb_code, javdb_url, javdb_title, release_date, duration, 
                 studio, score, cover_url, local_cover_path, cover_image_data, magnet_links, 
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """, (
                video_id,
                javdb_info.get('video_id', ''),
                javdb_info.get('detail_url', ''),
                javdb_info.get('title', ''),
                javdb_info.get('release_date', ''),
                javdb_info.get('duration', ''),
                javdb_info.get('studio', ''),
                float(javdb_info.get('rating', 0)) if javdb_info.get('rating') and javdb_info.get('rating') != 'N/A' else None,
                javdb_info.get('cover_image_url', ''),
                javdb_info.get('local_image_path', ''),
                cover_image_data,
                json.dumps(javdb_info.get('magnet_links', []), ensure_ascii=False)
            ))
            javdb_info_id = self.cursor.lastrowid
        
        # 保存标签信息
        tags = javdb_info.get('tags', [])
        if tags:
            for tag_name in tags:
                if tag_name.strip():
                    self.cursor.execute(
                        "INSERT OR IGNORE INTO javdb_tags (tag_name) VALUES (?)",
                        (tag_name.strip(),)
                    )
                    self.cursor.execute(
                        "SELECT id FROM javdb_tags WHERE tag_name = ?",
                        (tag_name.strip(),)
                    )
                    tag_result = self.cursor.fetchone()
                    if tag_result:
                        self.cursor.execute(
                            "INSERT OR IGNORE INTO javdb_info_tags (javdb_info_id, tag_id) VALUES (?, ?)",
                            (javdb_info_id, tag_result[0])
                        )
        
        # 保存演员信息
        actors = javdb_info.get('actors', [])
        if actors:
            for actor in actors:
                actor_name = actor.get('name', '').strip()
                actor_link = actor.get('link', '')
                
                if actor_name:
                    self.cursor.execute(
                        "INSERT OR IGNORE INTO actors (name, profile_url) VALUES (?, ?)",
                        (actor_name, actor_link)
                    )
                    self.cursor.execute(
                        "SELECT id FROM actors WHERE name = ?",
                        (actor_name,)
                    )
                    actor_result = self.cursor.fetchone()
                    if actor_result:
                        self.cursor.execute(
                            "INSERT OR IGNORE INTO video_actors (video_id, actor_id) VALUES (?, ?)",
                            (video_id, actor_result[0])
                        )
        
        self.conn.commit()
        print(f"已保存JAVDB信息到数据库: {javdb_info.get('title', 'Unknown')}")
        
    except Exception as e:
        print(f"保存JAVDB信息到数据库失败: {str(e)}")
        raise


def load_javdb_details(self, video_id):
    """
    加载JAVDB详情信息并显示在界面上
    
    Args:
        video_id: 视频ID
    
    更新以下界面变量:
        - javdb_code_var: 番号
        - javdb_title_var: JAVDB标题
        - release_date_var: 发行日期
        - javdb_score_var: 评分
        - javdb_tags_var: 标签
    """
    try:
        self.cursor.execute("""
            SELECT javdb_code, javdb_title, release_date, score, studio, 
                   cover_url, local_cover_path, cover_image_data, magnet_links
            FROM javdb_info 
            WHERE video_id = ?
        """, (video_id,))
        
        javdb_row = self.cursor.fetchone()
        
        if javdb_row:
            self.javdb_code_var.set(javdb_row[0] or '')
            self.javdb_title_var.set(javdb_row[1] or '')
            self.release_date_var.set(javdb_row[2] or '')
            
            score = javdb_row[3]
            if score:
                self.javdb_score_var.set(f"{score:.1f}")
            else:
                self.javdb_score_var.set('')
            
            # 查询标签
            self.cursor.execute("""
                SELECT GROUP_CONCAT(jt.tag_name, ', ') 
                FROM javdb_info ji
                JOIN javdb_info_tags jit ON ji.id = jit.javdb_info_id
                JOIN javdb_tags jt ON jit.tag_id = jt.id
                WHERE ji.video_id = ?
            """, (video_id,))
            tags_result = self.cursor.fetchone()
            self.javdb_tags_var.set(tags_result[0] if tags_result and tags_result[0] else '')
        
    except Exception as e:
        print(f"加载JAVDB详情失败: {e}")
