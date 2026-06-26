#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NAS JAVDB 信息更新器 — 固定使用 Playwright 持久化用户目录
直接从 javdb_crawler_single.py 调用爬虫（跳过 subprocess），
强制使用 "persisted" 模式，登录一次永久有效。
"""

import os
import sys
import time
import platform
import subprocess
import json
import re
import sqlite3
import argparse
from urllib.parse import urlparse, urlunparse, urljoin

from config import (
    SOCKS5_PROXY_HOST,
    SOCKS5_PROXY_PORT,
    MIN_DELAY,
    MAX_DELAY,
    get_javdb_base_url,
    normalize_javdb_url,
    JAVDB_ALTERNATE_DIRECT_DOMAINS,
    JAVDB_PROXY_DOMAIN,
)
from utils.runtime import runtime_dir

USE_PROXY = True
BASE_URL = get_javdb_base_url(USE_PROXY)
JAVDB_MAIN_DOMAIN = JAVDB_PROXY_DOMAIN
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'media_library.db')
COVERS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results', 'images')


# ---------- 工具函数 ----------
def normalize_to_main_javdb(url: str) -> str:
    try:
        p = urlparse(url)
        host = (p.netloc or '').lower()
        if not host:
            return url
        alternates = [
            JAVDB_PROXY_DOMAIN,
            f"www.{JAVDB_PROXY_DOMAIN}",
            *JAVDB_ALTERNATE_DIRECT_DOMAINS,
        ]
        if host in [d.lower() for d in alternates]:
            p = p._replace(netloc=JAVDB_MAIN_DOMAIN)
            return urlunparse(p)
        return url
    except Exception:
        return url


def random_delay(min_seconds=MIN_DELAY, max_seconds=MAX_DELAY):
    try:
        delay = min_seconds + (max_seconds - min_seconds) * __import__('random').random()
        time.sleep(delay)
    except Exception:
        time.sleep(min_seconds)


BLOCKED_TITLES = ['官方App下載', '官方App下载', 'Official App Download']


def _normalize_actors(maybe_list):
    normalized = []
    if isinstance(maybe_list, list):
        for item in maybe_list:
            if isinstance(item, dict):
                name = (item.get('name') or '').strip()
                link = item.get('link') or ''
                if name:
                    normalized.append({'name': name, 'link': link})
            elif isinstance(item, str):
                name = item.strip()
                if name:
                    normalized.append({'name': name, 'link': ''})
    return normalized


# ---------- 直接调用爬虫（强制 persisted 模式） ----------
def crawl_with_persisted_profile(av_code, timeout=180):
    """
    直接调用 javdb_crawler_single 的爬虫函数，
    强制使用 "persisted" Playwright 用户目录（不创建临时 fresh 目录）。
    需要登录时会打开有界面浏览器窗口，手工登录后自动持久化。
    """
    # 动态导入并强制 persisted 模式
    import importlib
    crawler = importlib.import_module('javdb_crawler_single')

    # 强制：仅持久化目录、仅 msedge、不使用代理、只试配置的主域名
    from config import JAVDB_DIRECT_DOMAIN
    original_get_profile_modes = crawler.get_profile_modes
    original_get_browser_prefs = crawler.get_browser_preferences
    original_get_url_candidates = crawler.get_base_url_candidates
    original_use_socks = getattr(crawler, 'USE_SOCKS5_PROXY', None)
    crawler.get_profile_modes = lambda: ["persisted"]
    crawler.get_browser_preferences = lambda: ["msedge"]
    crawler.get_base_url_candidates = lambda use_proxy: [f"https://{JAVDB_DIRECT_DOMAIN}"]
    if original_use_socks is not None:
        crawler.USE_SOCKS5_PROXY = False

    try:
        # 仅调用 Playwright，完全绕过 Selenium 降级
        result = crawler.crawl_single_video_playwright(av_code)
    finally:
        crawler.get_profile_modes = original_get_profile_modes
        crawler.get_browser_preferences = original_get_browser_prefs
        crawler.get_base_url_candidates = original_get_url_candidates
        if original_use_socks is not None:
            crawler.USE_SOCKS5_PROXY = original_use_socks

    if result:
        json_result = {
            'title': result.get('title'),
            'video_id': result.get('video_id'),
            'detail_url': result.get('detail_url'),
            'release_date': result.get('release_date'),
            'duration': result.get('duration'),
            'rating': result.get('rating'),
            'studio': result.get('studio'),
            'tags': result.get('tags', []),
            'actors': result.get('actors', []),
            'cover_image_url': result.get('cover_image_url'),
            'local_image_path': result.get('local_image_path'),
            'magnet_links': result.get('magnet_links', [])
        }
        return json_result
    return None


def fetch_video_info_with_fallback(av_code, timeout=180):
    """三级回退：JavDB(persisted) → JavBus → JavSP"""
    result_data = None

    # ---- 一级：JavDB 持久化模式 ----
    try:
        parsed = crawl_with_persisted_profile(av_code, timeout)
        if (parsed and not parsed.get('error')
                and parsed.get('title')
                and parsed.get('title') not in BLOCKED_TITLES):
            result_data = parsed
            has_actors = isinstance(parsed.get('actors'), list) and len(parsed.get('actors')) > 0
            print(f"  JavDB成功" + ("（演员缺失，尝试回退）" if not has_actors else ""))
        else:
            print("  JavDB信息不完整，尝试回退")
    except Exception as e:
        print(f"  JavDB异常: {e}，尝试回退")

    # ---- 二级/三级回退 ----
    need_fallback = not result_data or not (
        isinstance(result_data.get('actors'), list) and len(result_data.get('actors')) > 0
    )

    if need_fallback:
        cwd_dir = runtime_dir()
        used_source = None

        # JavBus
        try:
            if getattr(sys, 'frozen', False):
                cmd_bus = [os.path.join(runtime_dir(), "javbus_crawler_single.exe"), av_code]
            else:
                cmd_bus = [sys.executable, "javbus_crawler_single.py", av_code]
            p_bus = subprocess.run(cmd_bus, capture_output=True, text=True, cwd=cwd_dir, timeout=60)
            if p_bus.returncode == 0 and p_bus.stdout:
                bus_parsed = json.loads(p_bus.stdout)
                if bus_parsed and not bus_parsed.get('error'):
                    result_data = {
                        'title': bus_parsed.get('title'),
                        'video_id': bus_parsed.get('number') or av_code,
                        'detail_url': None,
                        'release_date': bus_parsed.get('release_date'),
                        'duration': None, 'rating': None,
                        'tags': bus_parsed.get('tags') or [],
                        'actors': _normalize_actors(bus_parsed.get('actors', [])),
                        'studio': bus_parsed.get('studio'),
                        'cover_image_url': bus_parsed.get('cover_image_url'),
                        'local_image_path': bus_parsed.get('cover_image_path'),
                        'magnet_links': bus_parsed.get('magnet_links', [])
                    }
                    used_source = 'javbus'
                    print("  已切换到 JavBus 数据")
        except Exception:
            pass

        # JavSP
        if not used_source:
            try:
                from javsp_integration import search_javdb_info as javsp_search
                sp_result = javsp_search(av_code)
                if sp_result:
                    result_data = sp_result
                    print("  已切换到 JavSP 数据")
            except Exception:
                print("  JavSP异常，回退结束")

    return result_data


# ---------- 番号提取器 ----------
class CodeExtractor:
    """番号提取器，基于 javsp 的 get_id 逻辑"""
    def __init__(self):
        self.ignore_pattern = re.compile(r'', re.I)

    def extract_code_from_filename(self, filename: str) -> str:
        from pathlib import Path
        filepath = Path(str(filename))
        norm = self.ignore_pattern.sub('', filepath.stem).upper()

        if 'FC2' in norm:
            match = re.search(r'FC2[^A-Z\d]{0,5}(PPV[^A-Z\d]{0,5})?(\d{5,7})', norm)
            if match:
                return 'FC2-' + match.group(2)
        elif 'HEYDOUGA' in norm:
            match = re.search(r'(HEYDOUGA)[-_]*(\d{4})[-_]0?(\d{3,5})', norm)
            if match:
                return '-'.join(match.groups())
        elif 'GETCHU' in norm:
            match = re.search(r'GETCHU[-_]*(\d+)', norm)
            if match:
                return 'GETCHU-' + match.group(1)
        elif 'GYUTTO' in norm:
            match = re.search(r'GYUTTO-(\d+)', norm)
            if match:
                return 'GYUTTO-' + match.group(1)
        elif '259LUXU' in norm:
            match = re.search(r'259LUXU-(\d+)', norm)
            if match:
                return '259LUXU-' + match.group(1)
        elif '1PONDO' in norm or 'PONDO' in norm:
            match = re.search(r'(1PONDO|PONDO)[-_]*(\d{6})[-_]*(\d{3})', norm)
            if match:
                return '1pondo-' + match.group(2) + '_' + match.group(3)
        elif 'CARIB' in norm:
            match = re.search(r'(CARIB|CARIBBEANCOM)[-_]*(\d{6})[-_]*(\d{3})', norm)
            if match:
                return match.group(1).lower() + '-' + match.group(2) + '-' + match.group(3)
        elif '10MUSUME' in norm or 'MUSUME' in norm:
            match = re.search(r'(10MUSUME|MUSUME)[-_]*(\d{6})[-_]*(\d{2})', norm)
            if match:
                return '10musume-' + match.group(2) + '_' + match.group(3)
        else:
            no_domain = re.sub(r'\w{3,10}\.(COM|NET|APP|XYZ)', '', norm)
            if no_domain != norm:
                avid = self.extract_code_from_filename(no_domain)
                if avid:
                    return avid
            match = re.search(r'(?:HEY)[-_]*(\d{4})[-_]0?(\d{3,5})', norm)
            if match:
                return 'heydouga-' + '-'.join(match.groups())
            match = re.search(r'(MKB?D)[-_]*(S\d{2,3})|(MK3D2DBD|S2M|S2MBD)[-_]*(\d{2,3})', norm)
            if match:
                if match.group(1) is not None:
                    return match.group(1) + '-' + match.group(2)
                else:
                    return match.group(3) + '-' + match.group(4)
            match = re.search(r'(IBW)[-_](\d{2,5}z)', norm)
            if match:
                return match.group(1) + '-' + match.group(2)
            match = re.search(r'([A-Z]{2,10})[-_](\d{2,5})', norm)
            if match:
                return match.group(1) + '-' + match.group(2)
            match = re.search(r'(RED[01]\d\d|SKY[0-3]\d\d|EX00[01]\d)', norm)
            if match:
                return match.group(1)
            match = re.search(r'([A-Z]{2,})(\d{2,5})', norm)
            if match:
                return match.group(1) + '-' + match.group(2)
        match = re.search(r'(T[23]8[-_]\d{3})', norm)
        if match:
            return match.group(1)
        match = re.search(r'(N\d{4}|K\d{4})', norm)
        if match:
            return match.group(1)
        match = re.search(r'R18-?\d{3}', norm)
        if match:
            return match.group(0)
        match = re.search(r'(\d{6}[-_]\d{2,3})', norm)
        if match:
            return match.group(1)
        if ')(' in str(filepath):
            avid = self.extract_code_from_filename(str(filepath).replace(')(', '-'))
            if avid:
                return avid
        parent = filepath.parent
        if parent and parent.name:
            avid = self.extract_code_from_filename(parent.name)
            if avid:
                return avid
        return None


# ---------- 数据库操作 ----------
def _get_db():
    """创建 WAL 模式数据库连接，避免与 GUI 长连接锁冲突"""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn

def get_user_defined_folders():
    try:
        conn = _get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT folder_path, folder_type FROM folders WHERE is_active = 1")
        folders = cursor.fetchall()
        conn.close()
        return [(folder[0], folder[1]) for folder in folders]
    except Exception as e:
        print(f"获取用户定义文件夹时出错: {e}")
        return []


def get_videos_to_update(folder_path=None, refresh_all=False, filter_by_code=None):
    try:
        conn = _get_db()
        cursor = conn.cursor()
        base_conditions = []
        params = []

        if folder_path:
            norm_path = folder_path.rstrip('/\\')
            if platform.system() == "Windows":
                base_conditions.append("((REPLACE(v.source_folder, CHAR(92), '/') = REPLACE(?, CHAR(92), '/') OR REPLACE(v.source_folder, CHAR(92), '/') = REPLACE(?, CHAR(92), '/') || '/' OR REPLACE(v.source_folder, CHAR(92), '/') LIKE REPLACE(?, CHAR(92), '/') || '%') OR REPLACE(v.file_path, CHAR(92), '/') LIKE REPLACE(?, CHAR(92), '/') || '%')")
                params.extend([norm_path, norm_path, norm_path, norm_path])
            else:
                base_conditions.append("((v.source_folder = ? OR v.source_folder = ? OR v.source_folder LIKE ?) OR v.file_path LIKE ?)")
                params.extend([norm_path, norm_path + '/', norm_path + '/%', norm_path + '/%'])

        if filter_by_code:
            base_conditions.append("j.javdb_code = ?")
            params.append(filter_by_code)

        if refresh_all:
            base_query = """SELECT v.id, v.file_path, v.title, j.javdb_code FROM videos v LEFT JOIN javdb_info j ON v.id = j.video_id"""
            if base_conditions:
                where_clause = " WHERE " + " AND ".join(base_conditions)
            else:
                where_clause = ""
            if not filter_by_code and not folder_path:
                order_clause = " ORDER BY v.id DESC LIMIT 100"
            else:
                order_clause = ""
            query = base_query + where_clause + order_clause
        else:
            base_query = """SELECT v.id, v.file_path, v.title, j.javdb_code FROM videos v LEFT JOIN javdb_info j ON v.id = j.video_id"""
            if base_conditions:
                where_clause = " WHERE " + " AND ".join(base_conditions) + " AND ("
            else:
                where_clause = " WHERE ("
            update_conditions = ""
            update_conditions += "j.id IS NULL\n"
            update_conditions += "OR NOT EXISTS (\n"
            update_conditions += "    SELECT 1 FROM video_actors va \n"
            update_conditions += "    JOIN actors a ON va.actor_id = a.id \n"
            update_conditions += "    WHERE va.video_id = v.id \n"
            update_conditions += f"    AND a.profile_url LIKE '%{JAVDB_MAIN_DOMAIN}%'\n"
            update_conditions += ")\n"
            query = base_query + where_clause + update_conditions + ")"

        cursor.execute(query, params)
        videos = cursor.fetchall()
        conn.close()
        return [{
            'id': video[0], 'file_path': video[1],
            'title': video[2],
            'av_code': video[3] if len(video) > 3 and video[3] is not None else None
        } for video in videos]
    except Exception as e:
        print(f"获取需要更新的视频时出错: {e}")
        return []


def get_videos_without_actors(folder_path=None):
    return get_videos_to_update(folder_path)


def _find_local_poster(file_path):
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


# ---------- 数据库保存 ----------
def save_javdb_info_to_db_standalone(video_id, javdb_info):
    try:
        conn = _get_db()
        cursor = conn.cursor()

        for field in ('detail_url', 'cover_image_url'):
            val = javdb_info.get(field)
            if val:
                javdb_info[field] = normalize_to_main_javdb(val)

        cover_image_data = None
        local_image_path = javdb_info.get('local_image_path', '')
        if local_image_path:
            abs_path = local_image_path if os.path.isabs(local_image_path) else os.path.join(os.path.dirname(os.path.abspath(__file__)), local_image_path)
            if os.path.exists(abs_path):
                try:
                    with open(abs_path, 'rb') as f:
                        cover_image_data = f.read()
                except Exception:
                    pass

        cursor.execute("SELECT id FROM javdb_info WHERE video_id = ?", (video_id,))
        existing_record = cursor.fetchone()

        score_val = None
        try:
            rating = javdb_info.get('rating')
            if isinstance(rating, (int, float)):
                score_val = float(rating)
            elif isinstance(rating, str):
                cleaned = rating.strip()
                if cleaned and cleaned != 'N/A':
                    score_val = float(cleaned)
        except Exception:
            pass

        magnet_json = None
        try:
            magnet_links = javdb_info.get('magnet_links', [])
            if magnet_links:
                magnet_json = json.dumps(magnet_links, ensure_ascii=False)
        except Exception:
            pass

        if existing_record:
            javdb_info_id = existing_record[0]
            cursor.execute("""
                UPDATE javdb_info SET 
                javdb_code = COALESCE(?, javdb_code), javdb_url = COALESCE(?, javdb_url),
                javdb_title = COALESCE(?, javdb_title), release_date = COALESCE(?, release_date),
                duration = COALESCE(?, duration), studio = COALESCE(?, studio),
                score = COALESCE(?, score), cover_url = COALESCE(?, cover_url),
                local_cover_path = COALESCE(?, local_cover_path), cover_image_data = COALESCE(?, cover_image_data),
                magnet_links = COALESCE(?, magnet_links), updated_at = datetime('now')
                WHERE video_id = ?
            """, (
                javdb_info.get('video_id') or None, javdb_info.get('detail_url') or None,
                javdb_info.get('title') or None, javdb_info.get('release_date') or None,
                javdb_info.get('duration') or None, javdb_info.get('studio') or None,
                score_val, javdb_info.get('cover_image_url') or None,
                local_image_path or None, cover_image_data, magnet_json, video_id
            ))
            cursor.execute("DELETE FROM javdb_info_tags WHERE javdb_info_id = ?", (javdb_info_id,))
            cursor.execute("DELETE FROM video_actors WHERE video_id = ?", (video_id,))
        else:
            cursor.execute("""
                INSERT INTO javdb_info (video_id, javdb_code, javdb_url, javdb_title, release_date,
                duration, studio, score, cover_url, local_cover_path, cover_image_data, magnet_links,
                created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """, (
                video_id, javdb_info.get('video_id') or '', javdb_info.get('detail_url') or '',
                javdb_info.get('title') or None, javdb_info.get('release_date') or None,
                javdb_info.get('duration') or None, javdb_info.get('studio') or None,
                score_val, javdb_info.get('cover_image_url') or None,
                local_image_path or '', cover_image_data, magnet_json
            ))
            javdb_info_id = cursor.lastrowid

        tags = javdb_info.get('tags', [])
        if tags:
            for tag_name in tags:
                tag_name = (tag_name or '').strip()
                if not tag_name:
                    continue
                cursor.execute("INSERT OR IGNORE INTO javdb_tags (tag_name) VALUES (?)", (tag_name,))
                cursor.execute("SELECT id FROM javdb_tags WHERE tag_name = ?", (tag_name,))
                tag_result = cursor.fetchone()
                if tag_result:
                    cursor.execute("INSERT OR IGNORE INTO javdb_info_tags (javdb_info_id, tag_id) VALUES (?, ?)",
                                   (javdb_info_id, tag_result[0]))

        actors = javdb_info.get('actors', [])
        if actors:
            for actor in actors:
                actor_name = (actor.get('name') or '').strip()
                actor_link = (actor.get('link') or '').strip()
                if not actor_name:
                    continue
                if actor_link:
                    if actor_link.startswith('/'):
                        actor_link = urljoin(BASE_URL, actor_link)
                    actor_link = normalize_to_main_javdb(actor_link)
                cursor.execute("SELECT id, profile_url FROM actors WHERE profile_url = ?", (actor_link,))
                row = cursor.fetchone()
                actor_id = None
                if row:
                    actor_id = row[0]
                else:
                    cursor.execute("SELECT id, profile_url FROM actors WHERE name = ?", (actor_name,))
                    row = cursor.fetchone()
                    if row:
                        actor_id = row[0]
                        existing_profile = row[1] or ''
                        if actor_link and not existing_profile.strip():
                            cursor.execute("UPDATE actors SET profile_url = ?, updated_at = datetime('now') WHERE id = ?",
                                           (actor_link, actor_id))
                    else:
                        cursor.execute("INSERT INTO actors (name, profile_url, created_at, updated_at) VALUES (?, ?, datetime('now'), datetime('now'))",
                                       (actor_name, actor_link))
                        actor_id = cursor.lastrowid
                if actor_id:
                    cursor.execute("INSERT OR IGNORE INTO video_actors (video_id, actor_id, created_at) VALUES (?, ?, datetime('now'))",
                                   (video_id, actor_id))

        try:
            cursor.execute("PRAGMA table_info(videos);")
            available_cols = {row[1] for row in cursor.fetchall()}
            update_fields = []
            update_params = []
            title = javdb_info.get('title')
            if title and title not in BLOCKED_TITLES and 'title' in available_cols:
                update_fields.append("title = ?")
                update_params.append(title)
            if local_image_path and 'thumbnail_path' in available_cols:
                update_fields.append("thumbnail_path = ?")
                update_params.append(local_image_path)
            if cover_image_data is not None and 'thumbnail_data' in available_cols:
                update_fields.append("thumbnail_data = ?")
                update_params.append(cover_image_data)
            if score_val is not None and 'rating' in available_cols:
                update_fields.append("rating = ?")
                update_params.append(score_val)
            if update_fields:
                update_params.append(video_id)
                cursor.execute(f"UPDATE videos SET {', '.join(update_fields)} WHERE id = ?", update_params)
        except Exception:
            pass

        conn.commit()
        conn.close()
        print(f"  已保存到数据库: {javdb_info.get('title', 'Unknown')}")
        return True
    except Exception as e:
        print(f"保存JAVDB信息到数据库失败: {e}")
        return False


# ---------- 主功能 ----------
def update_videos_batch(folder_path=None, refresh_all=False, filter_by_code=None):
    videos = get_videos_to_update(folder_path, refresh_all=refresh_all, filter_by_code=filter_by_code)
    if not videos:
        print("没有找到需要更新的视频")
        return
    print(f"找到 {len(videos)} 个需要更新的视频")
    code_extractor = CodeExtractor()
    code_map = {}
    for video in videos:
        av_code = video.get('av_code')
        if not av_code:
            av_code = code_extractor.extract_code_from_filename(video.get('file_path') or '')
            if not av_code:
                av_code = code_extractor.extract_code_from_filename(video.get('title') or '')
        code_map.setdefault(av_code, []).append(video)
    invalid_group = code_map.pop(None, [])
    unique_codes = list(code_map.keys())
    print(f"去重后需要处理的番号数: {len(unique_codes)}")
    success_count = 0
    failed_count = 0
    failed_videos = []
    for v in invalid_group:
        failed_count += 1
        failed_videos.append((v.get('title') or v.get('file_path') or '未知', "无法提取番号"))

    for idx, code in enumerate(unique_codes):
        group = code_map.get(code, [])
        sample_title = (group[0].get('title') or '')
        print(f"\n正在处理番号 {idx + 1}/{len(unique_codes)}: {code}（关联视频数 {len(group)}）")
        result = fetch_video_info_with_fallback(code)
        if not result or result.get('title') in BLOCKED_TITLES:
            error_msg = '爬取失败' if not result else '信息被屏蔽'
            failed_count += len(group)
            for v in group:
                failed_videos.append((v.get('title') or v.get('file_path') or '未知', error_msg))
            random_delay(MIN_DELAY, MAX_DELAY)
            continue
        tags_cnt = len(result.get('tags') or [])
        actors_cnt = len(result.get('actors') or [])
        magnets_cnt = len(result.get('magnet_links') or [])
        studio_str = result.get('studio') or 'N/A'
        print(f"  摘要：标签 {tags_cnt} 个，演员 {actors_cnt} 名，片商 {studio_str}，下载链接 {magnets_cnt} 条")
        for v in group:
            cover_path = result.get('local_image_path')
            if not cover_path:
                cover_path = _find_local_poster(v.get('file_path'))
            save_data = dict(result)
            if cover_path and not save_data.get('local_image_path'):
                save_data['local_image_path'] = cover_path
            save_result = save_javdb_info_to_db_standalone(v['id'], save_data)
            if save_result:
                success_count += 1
            else:
                failed_count += 1
                failed_videos.append((v.get('title') or v.get('file_path') or '未知', "更新数据库失败"))
        random_delay(MIN_DELAY, MAX_DELAY)

    print(f"\n=== 更新完成 ===")
    print(f"总视频数: {len(videos)}")
    print(f"去重后番号数: {len(unique_codes)}")
    print(f"成功更新: {success_count}")
    print(f"更新失败: {failed_count}")
    if failed_videos:
        print("\n失败的视频列表:")
        for title, reason in failed_videos[:10]:
            print(f"- {title[:50]}...: {reason}")


def select_folder(test_mode=False, test_folder_path=None):
    folders = get_user_defined_folders()
    if not folders:
        print("没有找到用户定义的数据文件夹")
        return None
    if test_mode and test_folder_path:
        print(f"测试模式：自动选择文件夹: {test_folder_path}")
        return test_folder_path
    print("请选择要更新的文件夹:")
    for i, (folder_path, folder_type) in enumerate(folders):
        print(f"{i + 1}. {folder_path} ({folder_type})")
    try:
        choice = int(input("请输入文件夹编号 (0表示全部): "))
        if choice == 0:
            return None
        elif 1 <= choice <= len(folders):
            return folders[choice - 1][0]
        else:
            print("无效的选择")
            return None
    except ValueError:
        print("请输入有效的数字")
        return None


def main(test_mode=False, test_folder_path=None, refresh_all=False, filter_by_code=None):
    if filter_by_code:
        print(f"正在刷新番号为 {filter_by_code} 的视频")
        result = fetch_video_info_with_fallback(filter_by_code)
        if result:
            conn = _get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT v.id, v.file_path FROM videos v WHERE v.id IN (SELECT video_id FROM javdb_info WHERE javdb_code = ?)", (filter_by_code,))
            row = cursor.fetchone()
            conn.close()
            if row:
                cover_path = result.get('local_image_path')
                if not cover_path:
                    cover_path = _find_local_poster(row[1])
                save_data = dict(result)
                if cover_path and not save_data.get('local_image_path'):
                    save_data['local_image_path'] = cover_path
                save_javdb_info_to_db_standalone(row[0], save_data)
            else:
                print(f"数据库中未找到番号为 {filter_by_code} 的视频")
        else:
            print(f"爬取番号为 {filter_by_code} 的视频信息失败")
    else:
        folder_path = select_folder(test_mode, test_folder_path)
        if folder_path is not None or (not folder_path and (test_mode or input("确定要更新所有文件夹的视频吗？(y/n): ").lower() == 'y')):
            update_videos_batch(folder_path, refresh_all=refresh_all)
        else:
            print("已取消更新操作")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='NAS JAVDB视频信息更新器')
    parser.add_argument('--refresh-all', action='store_true')
    parser.add_argument('--code', type=str)
    parser.add_argument('--test', action='store_true')
    parser.add_argument('--test-folder', type=str)
    parser.add_argument('--db-path', type=str)
    parser.add_argument('--min-delay', type=float)
    parser.add_argument('--max-delay', type=float)
    parser.add_argument('--no-proxy', dest='no_proxy', action='store_true')
    args = parser.parse_args()

    if args.db_path:
        new_db_path = args.db_path
        try:
            if os.path.isdir(new_db_path):
                new_db_path = os.path.join(new_db_path, 'media_library.db')
            os.makedirs(os.path.dirname(new_db_path), exist_ok=True)
            DB_PATH = new_db_path
            print(f"使用数据库路径: {DB_PATH}")
        except Exception:
            pass

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

    try:
        USE_PROXY = not getattr(args, 'no_proxy', False)
        BASE_URL = get_javdb_base_url(USE_PROXY)
        mode_str = '代理模式' if USE_PROXY else '直连模式'
        print(f"访问域名切换为：{BASE_URL}（{mode_str}）")
    except Exception as e:
        print(f"设置访问域名失败，仍使用默认：{BASE_URL}。错误：{e}")

    main(test_mode=args.test, test_folder_path=args.test_folder,
         refresh_all=args.refresh_all, filter_by_code=args.code)
