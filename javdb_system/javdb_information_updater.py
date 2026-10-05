#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JAVDB信息更新器 - 批量信息获取功能（Playwright 版）
通过 subprocess 调用同目录的 javdb_crawler_single.py（Playwright 优先）爬取信息，
登录与反爬验证由子爬虫的持久化会话负责。支持列出用户定义的数据文件夹，
选择文件夹后批量更新无演员信息的视频。
"""

import os
import sys
import time
import platform
import subprocess
import json
import random
import re
import sqlite3
import argparse
from urllib.parse import urlparse, urljoin

# 从配置文件加载代理与域名设置
from config import (
    MIN_DELAY,
    MAX_DELAY,
    get_javdb_base_url,
)

# 配置信息（BASE_URL/LOGIN_URL 根据是否使用代理动态设置；默认使用代理）
USE_PROXY = True
BASE_URL = get_javdb_base_url(USE_PROXY)
LOGIN_URL = f'{BASE_URL}/login'
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'media_library.db')
# 统一封面缓存目录到 results/images（与其它脚本保持一致）
COVERS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results', 'images')

# ---------- 工具函数 ----------
def random_delay(min_seconds=MIN_DELAY, max_seconds=MAX_DELAY):
    """随机延迟，模拟人类操作间隔"""
    try:
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)
    except Exception:
        time.sleep(min_seconds)


# ---------- 番号提取器 ----------
class CodeExtractor:
    """增强版番号提取器，整合了 javsp_mac 的先进识别逻辑"""
    
    def __init__(self):
        # 忽略模式配置
        self.ignore_pattern = re.compile(r'', re.I)  # 可以根据需要配置
        
        # 常见的无效匹配（需要过滤掉的）
        self.invalid_patterns = [
            r'^\d{4}$',  # 纯4位数字（可能是年份）
            r'^19\d{2}$|^20\d{2}$',  # 年份格式
            r'^\d{1,2}p$',  # 分辨率标识如720p, 1080p
            r'^[xX]\d+$',  # x264, x265等编码标识
            r'^\d{1,3}$',  # 过短的纯数字
        ]
        
        self.invalid_compiled = [re.compile(pattern, re.IGNORECASE) for pattern in self.invalid_patterns]
    
    def extract_code_from_filename(self, filename: str) -> str:
        """
        从文件名中提取番号（基于 javsp_mac 的 get_id 函数增强）
        """
        # 获取文件名并应用忽略模式
        basename = os.path.basename(filename)
        basename = self.ignore_pattern.sub('', basename)
        filename_lc = basename.lower()
        
        # FC2 格式处理
        if 'fc2' in filename_lc:
            match = re.search(r'fc2[^a-z\d]{0,5}(ppv[^a-z\d]{0,5})?(\d{5,7})', basename, re.I)
            if match:
                return 'FC2-' + match.group(2)
        
        # 一本道格式：1pondo-123456_789
        elif '1pondo' in filename_lc or 'pondo' in filename_lc:
            match = re.search(r'(1pondo|pondo)[-_]*(\d{6})[-_]*(\d{3})', basename, re.I)
            if match:
                return '1pondo-' + match.group(2) + '_' + match.group(3)
        
        # 加勒比格式：carib-123456-789, caribbeancom-123456-789
        elif 'carib' in filename_lc:
            match = re.search(r'(carib|caribbeancom)[-_]*(\d{6})[-_]*(\d{3})', basename, re.I)
            if match:
                return match.group(1) + '-' + match.group(2) + '-' + match.group(3)
        
        # 天然素人格式：10musume-123456_01
        elif '10musume' in filename_lc or 'musume' in filename_lc:
            match = re.search(r'(10musume|musume)[-_]*(\d{6})[-_]*(\d{2})', basename, re.I)
            if match:
                return '10musume-' + match.group(2) + '_' + match.group(3)
        
        # Heydouga 格式
        elif 'heydouga' in filename_lc:
            match = re.search(r'(heydouga)[-_]*(\d{4})[-_]0?(\d{3,5})', basename, re.I)
            if match:
                return '-'.join(match.groups())
        
        # 普通番号，优先尝试匹配带分隔符的（如ABC-123）
        match = re.search(r'([a-z]{2,10})[-_](\d{2,5})', basename, re.I)
        if match:
            return match.group(1) + '-' + match.group(2)
        
        # 东热的red, sky, ex三个不带-分隔符的系列
        match = re.search(r'(red[01]\d{2}|sky[0-3]\d{2}|ex00[01]\d)', basename, re.I)
        if match:
            return match.group(1)
        
        # 缺失了-分隔符的普通番号
        match = re.search(r'([a-z]{2,})([0-9]{2,5})', basename, re.I)
        if match:
            return match.group(1) + '-' + match.group(2)
        
        # TMA制作的影片（如'T28-557'）
        match = re.search(r'(T28[-_]\d{3})', basename)
        if match:
            return match.group(1)
        
        # 东热n, k系列
        match = re.search(r'(n\d{4}|k\d{4})', basename, re.I)
        if match:
            return match.group(1)
        
        # 纯数字番号（无码影片）
        match = re.search(r'(\d{6}[-_]\d{2,3})', basename)
        if match:
            return match.group(1)
        
        # 尝试将')('替换为'-'后再试
        if ')(' in filename:
            avid = self.extract_code_from_filename(filename.replace(')(', '-'))
            if avid:
                return avid
        
        # 如果仍然匹配不了，尝试使用文件所在文件夹的名字
        if os.path.isfile(filename):
            norm = os.path.normpath(filename)
            if os.sep in norm:
                folder = norm.split(os.sep)[-2]
                return self.extract_code_from_filename(folder)
        
        return None
    
    def _clean_filename(self, filename):
        """清理文件名，移除干扰字符"""
        # 移除常见的干扰字符
        filename = re.sub(r'[\[\]\(\)\{\}\s\-_\.\*]', '', filename)
        return filename
    
    def _format_code(self, match):
        """格式化提取到的番号"""
        if isinstance(match, tuple):
            if len(match) == 2 and match[0] and match[1]:
                return f"{match[0].upper()}-{match[1]}"
        return match
    
    def _is_valid_code(self, code):
        """检查提取的番号是否有效"""
        for pattern in self.invalid_compiled:
            if pattern.match(code):
                return False
        return True


# ---------- 数据库操作 ----------
def get_user_defined_folders():
    """获取用户定义的数据文件夹列表"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        # 查询所有活跃的文件夹
        cursor.execute("SELECT folder_path, folder_type FROM folders WHERE is_active = 1")
        folders = cursor.fetchall()
        conn.close()
        return [(folder[0], folder[1]) for folder in folders]
    except Exception as e:
        print(f"获取用户定义文件夹时出错: {e}")
        return []


def get_videos_to_update(folder_path=None, refresh_all=False, filter_by_code=None):
    """获取需要更新JAVDB信息的视频列表"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 基础查询条件
        base_conditions = []
        params = []
        
        # 文件夹过滤（兼容尾部斜杠，并包含子目录）；同时兼容基于 file_path 的前缀匹配
        if folder_path:
            norm_path = folder_path.rstrip('/\\')
            if platform.system() == "Windows":
                base_conditions.append("((REPLACE(v.source_folder, CHAR(92), '/') = REPLACE(?, CHAR(92), '/') OR REPLACE(v.source_folder, CHAR(92), '/') = REPLACE(?, CHAR(92), '/') || '/' OR REPLACE(v.source_folder, CHAR(92), '/') LIKE REPLACE(?, CHAR(92), '/') || '%') OR REPLACE(v.file_path, CHAR(92), '/') LIKE REPLACE(?, CHAR(92), '/') || '%')")
                params.extend([norm_path, norm_path, norm_path, norm_path])
            else:
                base_conditions.append("((v.source_folder = ? OR v.source_folder = ? OR v.source_folder LIKE ?) OR v.file_path LIKE ?)")
                params.extend([norm_path, norm_path + '/', norm_path + '/%', norm_path + '/%'])
        
        # 番号过滤
        if filter_by_code:
            base_conditions.append("j.javdb_code = ?")
            params.append(filter_by_code)
        
        # 主查询语句构建
        if refresh_all:
            # 刷新所有视频，包括那些已经有JAVDB信息的视频
            base_query = """
                SELECT v.id, v.file_path, v.title, j.javdb_code 
                FROM videos v
                LEFT JOIN javdb_info j ON v.id = j.video_id
            """
            
            if base_conditions:
                where_clause = " WHERE " + " AND ".join(base_conditions)
            else:
                where_clause = ""
                
            if not filter_by_code and not folder_path:
                # 如果没有过滤条件，只查询最近100个视频
                order_clause = " ORDER BY v.id DESC LIMIT 100"
            else:
                order_clause = ""
                
            query = base_query + where_clause + order_clause
        else:
            # 仅查询需要更新的视频（没有JAVDB信息或没有完整演员信息）
            base_query = """
                SELECT v.id, v.file_path, v.title, j.javdb_code 
                FROM videos v
                LEFT JOIN javdb_info j ON v.id = j.video_id
            """
            
            if base_conditions:
                where_clause = " WHERE " + " AND ".join(base_conditions) + " AND ("
            else:
                where_clause = " WHERE ("
                
            update_conditions = ""
            update_conditions += "j.id IS NULL -- 没有JAVDB信息\n"
            update_conditions += "OR NOT EXISTS (\n"
            update_conditions += "    SELECT 1 FROM video_actors va \n"
            update_conditions += "    JOIN actors a ON va.actor_id = a.id \n"
            update_conditions += "    WHERE va.video_id = v.id \n"
            # 根据当前 BASE_URL 的域名进行匹配（支持代理/直连两种主域名）
            domain = urlparse(BASE_URL).netloc
            update_conditions += f"    AND a.profile_url LIKE '%{domain}%'\n"
            update_conditions += ") -- 没有JAVDB女演员链接\n"
            
            query = base_query + where_clause + update_conditions + ")"
        
        cursor.execute(query, params)
        videos = cursor.fetchall()
        conn.close()
        
        return [{
            'id': video[0],
            'file_path': video[1],
            'title': video[2],
            'av_code': video[3] if len(video) > 3 and video[3] is not None else None
        } for video in videos]
    except Exception as e:
        print(f"获取需要更新的视频时出错: {e}")
        return []

# 兼容旧版API
def get_videos_without_actors(folder_path=None):
    """获取指定文件夹下需要更新JAVDB信息的视频列表（兼容旧版）"""
    return get_videos_to_update(folder_path)


def update_video_info(
    video_id,
    title=None,
    actors=None,
    tags=None,
    studio=None,
    series=None,
    release_date=None,
    duration=None,
    rating=None,
    cover_image_path=None,
    javdb_code=None,
    javdb_url=None,
    cover_image_url=None,
    magnet_links=None,
):
    """更新视频信息到数据库，并将封面以BLOB写入数据库。

    - 更新 `videos` 表：标题、标签、时长、评分、`thumbnail_path`，如存在则同时更新 `thumbnail_data`。
    - Upsert `javdb_info`：按 `video_id` 写入/更新 `cover_image_data`（BLOB）与 `local_cover_path`。
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 查询 videos 表的可用列，避免写入不存在的列造成错误
        cursor.execute("PRAGMA table_info(videos);")
        available_cols = {row[1] for row in cursor.fetchall()}  # 第二列是列名

        update_fields = []
        params = []

        if title and 'title' in available_cols:
            update_fields.append("title = ?")
            params.append(title)

        # actors 信息不直接写入 videos 表；演员链接关系应通过 video_actors/actors 维护

        if tags and 'tags' in available_cols:
            # tags 统一存储为逗号分隔字符串
            update_fields.append("tags = ?")
            params.append(','.join(tags) if isinstance(tags, (list, tuple)) else str(tags))

        # studio 和 release_date 在当前表结构中不存在，跳过

        if duration is not None and 'duration' in available_cols:
            update_fields.append("duration = ?")
            params.append(duration)

        if rating is not None and 'rating' in available_cols:
            update_fields.append("rating = ?")
            params.append(rating)

        # 将封面路径映射到 thumbnail_path（若存在）；并尝试读取字节以更新 thumbnail_data（若存在）
        cover_image_data = None
        if cover_image_path:
            try:
                # 直接读取绝对路径；相对路径则以脚本目录为基准
                p = cover_image_path
                if not os.path.isabs(p):
                    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), p)
                if os.path.exists(p):
                    with open(p, 'rb') as f:
                        cover_image_data = f.read()
            except Exception:
                cover_image_data = None

            if 'thumbnail_path' in available_cols:
                update_fields.append("thumbnail_path = ?")
                params.append(cover_image_path)

            if cover_image_data is not None and 'thumbnail_data' in available_cols:
                update_fields.append("thumbnail_data = ?")
                params.append(cover_image_data)

        # 若没有任何可更新字段，直接返回成功
        if not update_fields:
            conn.close()
            return True

        # 添加视频ID作为最后一个参数
        params.append(video_id)

        query = f"UPDATE videos SET {', '.join(update_fields)} WHERE id = ?"
        cursor.execute(query, params)
        conn.commit()

        # 将封面以BLOB写入/更新到 javdb_info 表，并补充其它JAVDB字段
        try:
            if cover_image_path and cover_image_data is None:
                # 若上面未能读取，重试一次读取
                p = cover_image_path
                if not os.path.isabs(p):
                    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), p)
                if os.path.exists(p):
                    with open(p, 'rb') as f:
                        cover_image_data = f.read()

            # 确保 javdb_info / javdb_tags / javdb_info_tags 表存在
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
                    rating TEXT,
                    score TEXT,
                    cover_url TEXT,
                    local_cover_path TEXT,
                    cover_image_data BLOB,
                    magnet_links TEXT,
                    preview_images TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (video_id) REFERENCES videos (id) ON DELETE CASCADE
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS javdb_tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tag_name TEXT UNIQUE NOT NULL,
                    tag_type TEXT DEFAULT 'general',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS javdb_info_tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    javdb_info_id INTEGER NOT NULL,
                    tag_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (javdb_info_id) REFERENCES javdb_info (id) ON DELETE CASCADE,
                    FOREIGN KEY (tag_id) REFERENCES javdb_tags (id) ON DELETE CASCADE,
                    UNIQUE(javdb_info_id, tag_id)
                )
                """
            )

            # 解析评分为数值分值（score）
            score_val = None
            try:
                if isinstance(rating, (int, float)):
                    score_val = float(rating)
                elif isinstance(rating, str):
                    cleaned = rating.strip()
                    if cleaned:
                        score_val = float(cleaned)
            except Exception:
                score_val = None

            # 统一序列化列表字段（仅磁力链接保留JSON；标签与演员使用关系表写入）
            magnet_json = None
            try:
                import json as _json
                if magnet_links:
                    magnet_json = _json.dumps(magnet_links, ensure_ascii=False)
            except Exception:
                pass

            cursor.execute("SELECT id FROM javdb_info WHERE video_id = ?", (video_id,))
            row = cursor.fetchone()
            if row is None:
                cursor.execute(
                    """
                    INSERT INTO javdb_info (
                        video_id, javdb_code, javdb_url, javdb_title, release_date, duration, studio, series,
                        rating, score, cover_url, local_cover_path, cover_image_data, magnet_links,
                        created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                    """,
                    (
                        video_id,
                        javdb_code or '',
                        javdb_url or '',
                        title or None,
                        release_date or None,
                        duration if (duration is not None) else None,
                        studio or None,
                        series or None,
                        None,
                        score_val,
                        cover_image_url or None,
                        cover_image_path or '',
                        cover_image_data,
                        magnet_json,
                    )
                )
                javdb_info_id = cursor.lastrowid
            else:
                cursor.execute(
                    """
                    UPDATE javdb_info
                    SET javdb_code = COALESCE(?, javdb_code),
                        javdb_url = COALESCE(?, javdb_url),
                        javdb_title = COALESCE(?, javdb_title),
                        release_date = COALESCE(?, release_date),
                        duration = COALESCE(?, duration),
                        studio = COALESCE(?, studio),
                        series = COALESCE(?, series),
                        rating = COALESCE(?, rating),
                        score = COALESCE(?, score),
                        cover_url = COALESCE(?, cover_url),
                        local_cover_path = COALESCE(?, local_cover_path),
                        cover_image_data = COALESCE(?, cover_image_data),
                        magnet_links = COALESCE(?, magnet_links),
                        updated_at = datetime('now')
                    WHERE video_id = ?
                    """,
                    (
                        javdb_code or None,
                        javdb_url or None,
                        title or None,
                        release_date or None,
                        duration if (duration is not None) else None,
                        studio or None,
                        series or None,
                        None,
                        score_val,
                        cover_image_url or None,
                        cover_image_path or '',
                        cover_image_data,
                        magnet_json,
                        video_id,
                    )
                )
                javdb_info_id = row[0]
            conn.commit()

            # 同步写入标签关联（javdb_tags / javdb_info_tags）
            try:
                if tags and javdb_info_id:
                    for t in tags:
                        tag_name = (t or '').strip()
                        if not tag_name:
                            continue
                        cursor.execute(
                            "INSERT OR IGNORE INTO javdb_tags (tag_name) VALUES (?)",
                            (tag_name,)
                        )
                        cursor.execute("SELECT id FROM javdb_tags WHERE tag_name = ?", (tag_name,))
                        tag_row = cursor.fetchone()
                        if tag_row:
                            tag_id = tag_row[0]
                            cursor.execute(
                                "INSERT OR IGNORE INTO javdb_info_tags (javdb_info_id, tag_id) VALUES (?, ?)",
                                (javdb_info_id, tag_id)
                            )
                    conn.commit()
            except Exception as _e:
                # 标签关联失败不阻断主流程
                print(f"写入JAVDB标签关联失败: {_e}")
        except Exception as e:
            # 不影响主更新流程，打印日志即可
            print(f"更新javdb_info封面BLOB失败: {e}")

        # 若提供了演员信息，则写入 actors 与 video_actors 关联
        try:
            if actors and isinstance(actors, (list, tuple)):
                for actor in actors:
                    try:
                        actor_name = (actor.get('name') or '').strip()
                        actor_link = (actor.get('link') or '').strip()

                        if not actor_name:
                            continue

                        # 规范化链接为绝对URL（可能为/actors/xxx形式）
                        if actor_link and actor_link.startswith('/'):
                            actor_link = urljoin(BASE_URL, actor_link)

                        # 查找现有演员（优先按profile_url匹配，其次按name匹配）
                        cursor.execute("SELECT id, profile_url FROM actors WHERE profile_url = ?", (actor_link,))
                        row = cursor.fetchone()
                        actor_id = None

                        if row:
                            actor_id = row[0]
                            # 如名称为空或不同，可适度更新名称（不强制覆盖已有非空）
                            cursor.execute("UPDATE actors SET updated_at = datetime('now') WHERE id = ?", (actor_id,))
                        else:
                            # 尝试按名称匹配已存在记录
                            cursor.execute("SELECT id, profile_url FROM actors WHERE name = ?", (actor_name,))
                            row = cursor.fetchone()
                            if row:
                                actor_id = row[0]
                                # 若该记录没有profile_url，则补充
                                existing_profile = row[1] or ''
                                if actor_link and (not existing_profile.strip()):
                                    cursor.execute(
                                        "UPDATE actors SET profile_url = ?, updated_at = datetime('now') WHERE id = ?",
                                        (actor_link, actor_id)
                                    )
                            else:
                                # 插入新演员
                                cursor.execute(
                                    """
                                    INSERT INTO actors (name, profile_url, created_at, updated_at)
                                    VALUES (?, ?, datetime('now'), datetime('now'))
                                    """,
                                    (actor_name, actor_link)
                                )
                                actor_id = cursor.lastrowid

                        # 建立视频-演员关联（唯一约束防重复）
                        if actor_id:
                            cursor.execute(
                                """
                                INSERT OR IGNORE INTO video_actors (video_id, actor_id, created_at)
                                VALUES (?, ?, datetime('now'))
                                """,
                                (video_id, actor_id)
                            )
                    except Exception as _e:
                        # 单个演员写入失败不影响整体，打印日志继续
                        print(f"写入演员信息失败: {_e}")

                conn.commit()
        except Exception as e:
            print(f"批量写入演员信息时出错: {e}")

        conn.close()
        return True
    except Exception as e:
        print(f"更新视频信息时出错: {e}")
        return False


# ---------- JAVDB信息爬取（委托 javdb_crawler_single.py 的 Playwright 管线） ----------
def _build_crawler_cmd(script_name, av_code):
    """构建爬虫子进程命令（兼容 PyInstaller 打包）"""
    if getattr(sys, 'frozen', False):
        exe_name = script_name.replace('.py', '.exe')
        return [os.path.join(os.path.dirname(os.path.abspath(__file__)), exe_name), av_code]
    return [sys.executable, script_name, av_code]


def crawl_single_video(video_code):
    """通过 javdb_crawler_single.py（Playwright 优先）爬取单个番号。

    登录/Cloudflare/年龄确认等拦截由子爬虫的持久化会话自行处理；
    返回与旧版 parse_detail 同构的 dict，失败返回 None。
    """
    cwd_dir = os.path.dirname(os.path.abspath(__file__))
    cmd = _build_crawler_cmd('javdb_crawler_single.py', video_code)
    try:
        process = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd_dir, timeout=240)
    except subprocess.TimeoutExpired:
        print(f"爬取番号 {video_code} 超时")
        return None
    except Exception as e:
        print(f"爬取番号 {video_code} 时发生错误: {e}")
        return None

    if process.returncode != 0 or not process.stdout:
        print(f"未找到番号 {video_code} 的详情页")
        return None
    try:
        data = json.loads(process.stdout)
    except json.JSONDecodeError:
        print(f"番号 {video_code} 的返回数据解析失败")
        return None
    if not isinstance(data, dict) or data.get('error') or not data.get('title') or data.get('title') == 'N/A':
        print(f"未找到番号 {video_code} 的详情页")
        return None

    print(f"成功获取番号 {video_code} 的信息")
    actors = []
    for item in (data.get('actors') or []):
        if isinstance(item, dict):
            name = (item.get('name') or '').strip()
            if name:
                actors.append({'name': name, 'link': item.get('link') or ''})
        elif isinstance(item, str) and item.strip():
            actors.append({'name': item.strip(), 'link': ''})

    return {
        'title': data.get('title'),
        'video_id': data.get('video_id') or video_code,
        'detail_url': data.get('detail_url'),
        'release_date': data.get('release_date'),
        'duration': data.get('duration'),
        'rating': data.get('rating'),
        'tags': data.get('tags') or [],
        'actors': actors,
        'studio': data.get('studio'),
        'series': None,
        'cover_image_url': data.get('cover_image_url'),
        'local_image_path': data.get('local_image_path'),
        'magnet_links': data.get('magnet_links') or [],
    }


def safe_filename(filename):
    """Convert filename to safe format"""
    # Remove or replace unsafe characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Remove leading and trailing spaces and dots
    filename = filename.strip(' .')
    # Limit filename length
    if len(filename) > 200:
        filename = filename[:200]
    return filename


def find_local_poster(file_path):
    """当网络封面下载失败时，尝试使用视频同目录下的poster.jpg作为封面。
    优先使用网络爬取的封面；仅在其不可用时使用本地poster.jpg。
    """
    try:
        if not file_path:
            return None
        dir_path = os.path.dirname(file_path)
        poster_path = os.path.join(dir_path, 'poster.jpg')
        if os.path.isfile(poster_path):
            return poster_path
    except Exception:
        pass
    return None


def update_videos_without_actors(folder_path=None):
    """批量更新没有演员信息的视频"""
    # 获取没有演员信息的视频列表
    videos = get_videos_without_actors(folder_path)
    if not videos:
        print("没有找到需要更新的视频")
        return

    print(f"找到 {len(videos)} 个需要更新演员信息的视频")
    _update_videos_batch(videos)


def _update_videos_batch(videos):
    """按番号分组爬取并批量更新同番号的所有视频（各更新入口共用）"""

    # 初始化番号提取器
    code_extractor = CodeExtractor()

    # 先按番号分组去重，确保每个番号只爬取一次
    code_map = {}
    for video in videos:
        av_code = video.get('av_code')
        if not av_code:
            av_code = code_extractor.extract_code_from_filename(video.get('file_path') or '')
            if not av_code:
                av_code = code_extractor.extract_code_from_filename(video.get('title') or '')
        if not av_code:
            # 无法提取番号的记录，留到失败统计阶段
            av_code = None
        code_map.setdefault(av_code, []).append(video)

    # 去掉无效番号键
    if None in code_map:
        invalid_group = code_map.pop(None)
    else:
        invalid_group = []

    unique_codes = list(code_map.keys())
    print(f"去重后需要处理的番号数: {len(unique_codes)}")

    # 成功和失败计数
    success_count = 0
    failed_count = 0
    failed_videos = []
    # 批量摘要累计
    total_tags = 0
    total_actors = 0
    total_magnet_links = 0
    unique_studios = set()
    unique_series = set()

    # 先记录无法提取番号的失败项
    for v in invalid_group:
        failed_count += 1
        failed_videos.append((v.get('title') or v.get('file_path') or '未知', "无法提取番号"))

    # 按唯一番号进行爬取并批量更新同番号的所有视频
    for idx, code in enumerate(unique_codes):
        group = code_map.get(code, [])
        sample_title = (group[0].get('title') or '')
        print(f"\n正在处理番号 {idx + 1}/{len(unique_codes)}: {code}（关联视频数 {len(group)}）")

        # 爬取一次
        result = crawl_single_video(code)
        if not result:
            failed_count += len(group)
            for v in group:
                failed_videos.append(((v.get('title') or v.get('file_path') or '未知'), "爬取失败"))
            # 下一个番号前仍保持延迟
            random_delay(MIN_DELAY, MAX_DELAY)
            continue

        # 打印该番号的摘要
        tags_cnt = len(result.get('tags') or [])
        actors_cnt = len(result.get('actors') or [])
        magnets_cnt = len(result.get('magnet_links') or [])
        studio_str = result.get('studio') or 'N/A'
        series_str = result.get('series') or 'N/A'
        print(f"摘要：标签 {tags_cnt} 个，演员 {actors_cnt} 名，片商 {studio_str}，下载链接 {magnets_cnt} 条" + (f"，系列 {series_str}" if series_str and series_str != 'N/A' else ""))

        # 累计批量摘要
        total_tags += tags_cnt
        total_actors += actors_cnt
        total_magnet_links += magnets_cnt
        if studio_str and studio_str != 'N/A':
            unique_studios.add(studio_str)
        if series_str and series_str != 'N/A':
            unique_series.add(series_str)

        # 将结果应用到所有关联视频
        for v in group:
            # 优先使用网络下载的封面；如无则回退到同目录poster.jpg
            cover_path = result.get('local_image_path')
            if not cover_path:
                cover_path = find_local_poster(v.get('file_path'))
            update_result = update_video_info(
                v['id'],
                title=result['title'],
                actors=result['actors'],
                tags=result['tags'],
                studio=result['studio'],
                series=result.get('series'),
                release_date=result['release_date'],
                duration=result['duration'],
                rating=result['rating'],
                cover_image_path=cover_path,
                javdb_code=result.get('video_id'),
                javdb_url=result.get('detail_url'),
                cover_image_url=result.get('cover_image_url'),
                magnet_links=result.get('magnet_links')
            )
            if update_result:
                success_count += 1
            else:
                failed_count += 1
                failed_videos.append((v.get('title') or v.get('file_path') or '未知', "更新数据库失败"))

        # 番号间随机延迟，避免被反爬（默认3-7秒，可配置）
        random_delay(MIN_DELAY, MAX_DELAY)

    # 打印统计结果
    print(f"\n=== 更新完成 ===")
    print(f"总视频数: {len(videos)}")
    print(f"去重后番号数: {len(unique_codes)}")
    print(f"成功更新: {success_count}")
    print(f"更新失败: {failed_count}")
    print(f"汇总：标签 {total_tags} 个，演员 {total_actors} 名，下载链接 {total_magnet_links} 条")
    if unique_studios:
        print(f"片商数: {len(unique_studios)}（例如：{list(unique_studios)[:3]}）")
    if unique_series:
        print(f"系列数: {len(unique_series)}（例如：{list(unique_series)[:3]}）")

    if failed_videos:
        print("\n失败的视频列表:")
        for title, reason in failed_videos[:10]:  # 只显示前10个
            print(f"- {title[:50]}...: {reason}")
        if len(failed_videos) > 10:
            print(f"... 还有 {len(failed_videos) - 10} 个失败视频未显示")


def select_folder(test_mode=False, test_folder_path=None):
    """列出用户定义的文件夹，让用户通过编号选择"""
    folders = get_user_defined_folders()
    if not folders:
        print("没有找到用户定义的数据文件夹")
        return None
    
    # 测试模式：自动选择指定的文件夹
    if test_mode and test_folder_path:
        print(f"测试模式：自动选择文件夹: {test_folder_path}")
        return test_folder_path
    
    print("请选择要更新的文件夹:")
    for i, (folder_path, folder_type) in enumerate(folders):
        print(f"{i + 1}. {folder_path} ({folder_type})")
    
    try:
        choice = int(input("请输入文件夹编号 (0表示全部): "))
        if choice == 0:
            return None  # 返回None表示选择全部文件夹
        elif 1 <= choice <= len(folders):
            return folders[choice - 1][0]  # 返回选择的文件夹路径
        else:
            print("无效的选择")
            return None
    except ValueError:
        print("请输入有效的数字")
        return None


def login_and_update(test_mode=False, test_folder_path=None, refresh_all=False, filter_by_code=None):
    """更新指定文件夹下需要更新的视频信息。

    登录与反爬验证由 javdb_crawler_single.py 的 Playwright 持久化会话负责：
    检测到登录页时会打开有界面浏览器等待人工登录，登录态保存在
    .playwright_user_data/ 供后续爬取复用（也可先执行
    `python javdb_crawler_single.py --login` 预先完成登录）。
    """
    if filter_by_code:
        # 按番号刷新特定视频
        print(f"正在刷新番号为 {filter_by_code} 的视频")
        result = crawl_single_video(filter_by_code)
        if not result:
            print(f"爬取番号为 {filter_by_code} 的视频信息失败")
            return

        # 查询数据库中是否有该番号的视频
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT v.id, v.file_path FROM videos v WHERE v.id IN (SELECT video_id FROM javdb_info WHERE javdb_code = ?)", (filter_by_code,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            print(f"数据库中未找到番号为 {filter_by_code} 的视频")
            return

        # 优先使用网络下载的封面；如无则回退到同目录poster.jpg
        cover_path = result.get('local_image_path')
        if not cover_path:
            cover_path = find_local_poster(row[1])
        if update_video_info(
            row[0],
            title=result['title'],
            actors=result['actors'],
            tags=result['tags'],
            studio=result['studio'],
            series=result.get('series'),
            release_date=result['release_date'],
            duration=result['duration'],
            rating=result['rating'],
            cover_image_path=cover_path,
            javdb_code=result.get('video_id'),
            javdb_url=result.get('detail_url'),
            cover_image_url=result.get('cover_image_url'),
            magnet_links=result.get('magnet_links')
        ):
            print(f"成功更新番号为 {filter_by_code} 的视频信息")
        else:
            print(f"更新番号为 {filter_by_code} 的视频信息失败")
        return

    # 选择要更新的文件夹
    folder_path = select_folder(test_mode, test_folder_path)
    if folder_path is not None or (not folder_path and (test_mode or input("确定要更新所有文件夹的视频吗？(y/n): ").lower() == 'y')):
        if refresh_all:
            # 刷新所有视频
            print("正在刷新所有视频信息...")
            videos = get_videos_to_update(folder_path, refresh_all=True)
            if videos:
                print(f"找到 {len(videos)} 个视频")
                _update_videos_batch(videos)
            else:
                print("没有找到视频")
        else:
            # 批量更新没有完整信息的视频
            update_videos_without_actors(folder_path)
    else:
        print("已取消更新操作")


if __name__ == "__main__":
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description='JAVDB视频信息更新工具')
    parser.add_argument('--refresh-all', action='store_true', help='刷新所有视频信息，包括已更新的视频')
    parser.add_argument('--code', type=str, help='按番号刷新特定视频，如 --code ADN-347')
    parser.add_argument('--test', action='store_true', help='测试模式')
    parser.add_argument('--test-folder', type=str, help='测试文件夹路径')
    parser.add_argument('--db-path', type=str, help='指定数据库文件路径或目录（目录将自动追加media_library.db）')
    parser.add_argument('--min-delay', type=float, help='最小操作间隔秒，默认3')
    parser.add_argument('--max-delay', type=float, help='最大操作间隔秒，默认7')
    parser.add_argument('--no-proxy', dest='no_proxy', action='store_true', help='不使用代理（使用直连域名）')
    
    # 解析命令行参数
    args = parser.parse_args()

    # 覆盖默认数据库路径（支持传入目录）
    if args.db_path:
        new_db_path = args.db_path
        try:
            if os.path.isdir(new_db_path):
                new_db_path = os.path.join(new_db_path, 'media_library.db')
            # 确保父目录存在
            os.makedirs(os.path.dirname(new_db_path), exist_ok=True)
            DB_PATH = new_db_path
            print(f"使用数据库路径: {DB_PATH}")
        except Exception as e:
            print(f"设置数据库路径失败: {e}")
            print(f"回退到默认数据库路径: {DB_PATH}")

    # 根据命令行参数调整默认随机延迟范围
    try:
        if args.min_delay is not None:
            MIN_DELAY = float(args.min_delay)
        if args.max_delay is not None:
            MAX_DELAY = float(args.max_delay)
        if MIN_DELAY > MAX_DELAY:
            MIN_DELAY, MAX_DELAY = MAX_DELAY, MIN_DELAY
        print(f"操作间隔：最小 {MIN_DELAY:.1f}s，最大 {MAX_DELAY:.1f}s")
    except Exception:
        pass

    # 设置是否使用代理，并根据模式更新 BASE_URL / LOGIN_URL
    try:
        USE_PROXY = not getattr(args, 'no_proxy', False)
        BASE_URL = get_javdb_base_url(USE_PROXY)
        LOGIN_URL = f"{BASE_URL}/login"
        mode_str = '代理模式' if USE_PROXY else '直连模式'
        print(f"访问域名切换为：{BASE_URL}（{mode_str}）")
    except Exception as e:
        print(f"设置访问域名失败，仍使用默认：{BASE_URL}。错误：{e}")

    # 执行登录和更新
    login_and_update(
        test_mode=args.test,
        test_folder_path=args.test_folder,
        refresh_all=args.refresh_all,
        filter_by_code=args.code
    )