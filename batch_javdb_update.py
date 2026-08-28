#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量更新 JAVDB 演员/标签信息（无头后台版）
复刻 media_library.py 的 batch_process_javdb_info：
  CodeExtractor 提番号 -> javdb_crawler_single.py(Playwright优先) -> JavBus 回退 -> JavSP 回退 -> 写库
范围: AV 相关文件夹中 无javdb_info 或 无JavDB域名演员链接 的视频
断点: .batch_javdb_progress.txt 记录已成功番号，重跑自动跳过
用法: python3 batch_javdb_update.py [--limit N] [--online]
      --online  只处理当前已挂载（在线）的卷，并校验文件真实存在
"""
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, 'media_library.db')
PROGRESS_FILE = os.path.join(BASE, '.batch_javdb_progress.txt')
LOG_FILE = os.path.join(BASE, f'batch_javdb_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')

BLOCKED_TITLES = ['官方App下載', '官方App下载', 'Official App Download']
AV_FOLDERS = [
    '/Volumes/Video/JAV/%',
    '/Volumes/Video/usr/%',
    '/Volumes/Video/Video2/av%',
    '/Volumes/HC530_1/%',
    '/Volumes/app/usr/%',
    '/Volumes/Jav_HDD4/%',
    '/Volumes/Glowy2T/%',
]

MANUAL_MARKERS = ['cloudflare', '验证页', 'just a moment', 'checking your browser',
                  '登录状态缺失', '访问详情页需要登录', '登录仍未成功', 'login']


def online_av_folders():
    """只返回当前实际挂载（在线）的 AV 文件夹，避免对离线卷做无效爬取"""
    online = []
    for pattern in AV_FOLDERS:
        # pattern 形如 /Volumes/xxx/%  -> 卷路径 /Volumes/xxx
        vol = '/'.join(pattern.split('/')[:3])
        if os.path.ismount(vol):
            online.append(pattern)
    return online or AV_FOLDERS


def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)


def needs_manual_action(stderr_text):
    if not stderr_text:
        return False
    t = str(stderr_text).lower()
    return any(m in t for m in MANUAL_MARKERS)


def normalize_actors_from_names(names):
    if not isinstance(names, list):
        return []
    return [{'name': n, 'link': ''} for n in names if isinstance(n, str) and n.strip()]


def get_pending_videos(folders=None, require_exists=True):
    """AV 文件夹中 无javdb_info 或 无JavDB域名演员链接 的视频，按入库时间从新到旧排序

    folders: 指定文件夹范围，默认 AV_FOLDERS
    require_exists: 只返回文件实际存在的记录（在线校验）
    """
    folders = folders or AV_FOLDERS
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    folder_clause = ' OR '.join(['v.file_path LIKE ?'] * len(folders))
    c.execute(f"""
        SELECT v.id, v.file_name, v.file_path, v.created_at
        FROM videos v
        LEFT JOIN javdb_info j ON v.id = j.video_id
        WHERE (j.id IS NULL OR NOT EXISTS (
            SELECT 1 FROM video_actors va WHERE va.video_id = v.id
        )) AND ({folder_clause})
        ORDER BY v.created_at DESC
    """, folders)
    rows = c.fetchall()
    conn.close()
    out = [{'id': r[0], 'file_name': r[1] or '', 'file_path': r[2] or '', 'created_at': r[3] or ''} for r in rows]
    if require_exists:
        out = [v for v in out if v['file_path'] and os.path.exists(v['file_path'])]
    return out


def extract_code_smart(filename):
    """智能番号提取：对特殊格式尝试多种提取方式"""
    import sys
    sys.path.insert(0, BASE)
    from code_extractor import CodeExtractor
    extractor = CodeExtractor()
    
    # 先尝试标准提取
    code = extractor.extract_code_from_filename(filename)
    
    # 对加勒比番号，尝试去掉前缀（JavDB 可能只认数字部分）
    if code and code.lower().startswith('caribbeancom-'):
        # caribbeancom-123456-789 -> 123456-789
        parts = code.split('-')
        if len(parts) == 3:
            alt_code = f"{parts[1]}-{parts[2]}"
            return code, alt_code  # 返回两个候选
    
    if code:
        return code, None
    return None, None


def save_to_db(video_id, info):
    """复刻 media_library.save_javdb_info_to_db"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        cover_image_data = None
        local_image_path = info.get('local_image_path', '')
        if local_image_path and os.path.exists(local_image_path):
            try:
                with open(local_image_path, 'rb') as f:
                    cover_image_data = f.read()
            except Exception:
                pass

        c.execute("SELECT id FROM javdb_info WHERE video_id = ?", (video_id,))
        existing = c.fetchone()
        score = info.get('rating')
        score_val = float(score) if score and score != 'N/A' else None

        if existing:
            javdb_info_id = existing[0]
            c.execute("""UPDATE javdb_info SET
                javdb_code=?, javdb_url=?, javdb_title=?, release_date=?, duration=?,
                studio=?, score=?, cover_url=?, local_cover_path=?, cover_image_data=?,
                magnet_links=?, updated_at=datetime('now')
                WHERE video_id=?""", (
                info.get('video_id', ''), info.get('detail_url', ''), info.get('title', ''),
                info.get('release_date', ''), info.get('duration', ''), info.get('studio', ''),
                score_val, info.get('cover_image_url', ''), info.get('local_image_path', ''),
                cover_image_data, json.dumps(info.get('magnet_links', []), ensure_ascii=False),
                video_id))
            c.execute("DELETE FROM javdb_info_tags WHERE javdb_info_id=?", (javdb_info_id,))
            c.execute("DELETE FROM video_actors WHERE video_id=?", (video_id,))
        else:
            c.execute("""INSERT INTO javdb_info
                (video_id, javdb_code, javdb_url, javdb_title, release_date, duration,
                 studio, score, cover_url, local_cover_path, cover_image_data, magnet_links,
                 created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'),datetime('now'))""", (
                video_id, info.get('video_id', ''), info.get('detail_url', ''),
                info.get('title', ''), info.get('release_date', ''), info.get('duration', ''),
                info.get('studio', ''), score_val, info.get('cover_image_url', ''),
                info.get('local_image_path', ''), cover_image_data,
                json.dumps(info.get('magnet_links', []), ensure_ascii=False)))
            javdb_info_id = c.lastrowid

        for tag_name in (info.get('tags') or []):
            if isinstance(tag_name, str) and tag_name.strip():
                c.execute("INSERT OR IGNORE INTO javdb_tags (tag_name) VALUES (?)", (tag_name.strip(),))
                c.execute("SELECT id FROM javdb_tags WHERE tag_name=?", (tag_name.strip(),))
                tr = c.fetchone()
                if tr:
                    c.execute("INSERT OR IGNORE INTO javdb_info_tags (javdb_info_id, tag_id) VALUES (?,?)",
                              (javdb_info_id, tr[0]))

        for actor in (info.get('actors') or []):
            if isinstance(actor, dict):
                name = (actor.get('name') or '').strip()
                link = actor.get('link', '')
                if name:
                    c.execute("INSERT OR IGNORE INTO actors (name, profile_url) VALUES (?,?)", (name, link))
                    c.execute("SELECT id FROM actors WHERE name=?", (name,))
                    ar = c.fetchone()
                    if ar:
                        c.execute("INSERT OR IGNORE INTO video_actors (video_id, actor_id) VALUES (?,?)",
                                  (video_id, ar[0]))

        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        log(f"  写库失败 video_id={video_id}: {e}")
        return False
    finally:
        conn.close()


def crawl_javdb(code):
    """Playwright 优先的 javdb 爬虫，返回 (result_dict|None, stderr)"""
    try:
        r = subprocess.run([sys.executable, 'javdb_crawler_single.py', code],
                           capture_output=True, text=True, cwd=BASE, timeout=300)
        if r.returncode == 0 and r.stdout:
            try:
                parsed = json.loads(r.stdout)
                if parsed and not parsed.get('error') and parsed.get('title') \
                        and parsed.get('title') not in BLOCKED_TITLES:
                    return parsed, r.stderr
                else:
                    # 详细错误信息
                    err_msg = f"rc={r.returncode}, stdout={r.stdout[:100] if r.stdout else 'empty'}, stderr={r.stderr[:100] if r.stderr else 'empty'}"
                    return None, err_msg
            except json.JSONDecodeError as e:
                # JSON 解析失败
                err_msg = f"JSON解析失败: {e}, stdout={r.stdout[:100] if r.stdout else 'empty'}"
                return None, err_msg
        else:
            # returncode 非 0 或 stdout 为空
            err_msg = f"rc={r.returncode}, stdout={r.stdout[:100] if r.stdout else 'empty'}, stderr={r.stderr[:100] if r.stderr else 'empty'}"
            return None, err_msg
    except subprocess.TimeoutExpired:
        return None, 'TIMEOUT'
    except Exception as e:
        return None, str(e)


def crawl_javbus(code):
    try:
        r = subprocess.run([sys.executable, 'javbus_crawler_single.py', code],
                           capture_output=True, text=True, cwd=BASE, timeout=90)
        if r.returncode == 0 and r.stdout:
            try:
                p = json.loads(r.stdout)
                if p and not p.get('error'):
                    return {
                        'title': p.get('title'),
                        'video_id': p.get('number') or code,
                        'detail_url': None,
                        'release_date': p.get('release_date'),
                        'duration': None,
                        'rating': None,
                        'tags': p.get('tags') or [],
                        'actors': normalize_actors_from_names(p.get('actors', [])),
                        'studio': p.get('studio'),
                        'cover_image_url': p.get('cover_image_url'),
                        'local_image_path': p.get('cover_image_path'),
                        'magnet_links': p.get('magnet_links', []),
                    }
            except json.JSONDecodeError:
                pass
        return None
    except Exception:
        return None


def crawl_javsp(code):
    try:
        sys.path.insert(0, BASE)
        sys.path.insert(0, os.path.join(BASE, 'javdb_system'))
        from javsp_integration import search_javdb_info
        return search_javdb_info(code)
    except Exception:
        return None


def mark_done(code):
    with open(PROGRESS_FILE, 'a', encoding='utf-8') as f:
        f.write(code + '\n')


def main():
    limit = None
    if '--limit' in sys.argv:
        i = sys.argv.index('--limit')
        limit = int(sys.argv[i + 1]) if i + 1 < len(sys.argv) else None

    online_only = '--online' in sys.argv
    folders = online_av_folders() if online_only else AV_FOLDERS
    if online_only:
        log(f"在线模式，使用卷: {sorted(set(f.split('/')[2] for f in folders))}")

    sys.path.insert(0, BASE)
    from code_extractor import CodeExtractor
    extractor = CodeExtractor()

    videos = get_pending_videos(folders=folders)
    log(f"待更新视频: {len(videos)} 个")

    done = set()
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, encoding='utf-8') as f:
            done = set(l.strip() for l in f if l.strip())
    log(f"断点已成功番号: {len(done)} 个")

    # 提番号分组（使用智能提取，对特殊格式尝试多种候选）
    code_map = {}  # code -> [videos]
    alt_code_map = {}  # alt_code -> [videos]  备用候选
    no_code = []
    for v in videos:
        code, alt_code = extract_code_smart(v['file_name'])
        if not code:
            code, alt_code = extract_code_smart(v['file_path'])
        if not code:
            no_code.append(v)
        else:
            code_map.setdefault(code, []).append(v)
            if alt_code:
                alt_code_map.setdefault(alt_code, []).append(v)
    log(f"去重后番号: {len(code_map)} 个, 备用候选: {len(alt_code_map)} 个, 无法提番号: {len(no_code)} 个")

    # 加载失败记录
    failed_file = os.path.join(BASE, '.batch_javdb_failed.txt')
    failed_codes = set()
    if os.path.exists(failed_file):
        with open(failed_file, encoding='utf-8') as f:
            failed_codes = set(l.strip() for l in f if l.strip())
    log(f"已记录失败番号: {len(failed_codes)} 个")

    pending_codes = [c for c in code_map if c not in done and c not in failed_codes]
    if limit:
        pending_codes = pending_codes[:limit]
    log(f"本次将处理: {len(pending_codes)} 个番号（跳过已失败 {len(failed_codes)} 个）")

    ok = fail = 0
    manual_warned = False
    t0 = time.time()
    for idx, code in enumerate(pending_codes, 1):
        group = code_map[code]
        log(f"[{idx}/{len(pending_codes)}] {code} ({len(group)}视频)")
        
        # 尝试主番号
        result, stderr = crawl_javdb(code)
        source = 'javdb'
        tried_alt = False
        
        # 如果主番号失败，尝试备用番号（如加勒比去前缀）
        if result is None and code in alt_code_map:
            alt_code = list(alt_code_map.keys())[0] if alt_code_map else None
            if alt_code:
                log(f"  主番号失败，尝试备用: {alt_code}")
                result, stderr = crawl_javdb(alt_code)
                if result:
                    code = alt_code  # 切换到备用番号
                    tried_alt = True
        
        if result is not None:
            has_actors = isinstance(result.get('actors'), list) and len(result['actors']) > 0
            if not has_actors:
                log("  javdb 无演员，尝试 JavBus")
                bus = crawl_javbus(code)
                if bus and bus.get('actors'):
                    result, source = bus, 'javbus'
        else:
            if not manual_warned and needs_manual_action(stderr):
                manual_warned = True
                log("  ⚠ 检测到需要人工验证(Cloudflare/登录)，后续同类错误不再提示")
            log(f"  javdb 失败({str(stderr)[:80]})，尝试 JavBus")
            bus = crawl_javbus(code)
            if bus:
                result, source = bus, 'javbus'
        if result is None or result.get('title') in BLOCKED_TITLES:
            sp = crawl_javsp(code)
            if sp:
                result, source = sp, 'javsp'
        if result is None or not result.get('title') or result.get('title') in BLOCKED_TITLES:
            fail += len(group)
            log(f"  ✗ 全部来源失败")
            # 记录失败
            with open(failed_file, 'a', encoding='utf-8') as f:
                f.write(code + '\n')
            time.sleep(1)
            continue

        saved = 0
        for v in group:
            if save_to_db(v['id'], result):
                saved += 1
        if saved > 0:
            ok += saved
            mark_done(code)
            actors = result.get('actors') or []
            log(f"  ✓ {source} 保存 {saved}/{len(group)} ({result.get('title', '')[:30]} 演员:{len(actors)})")
        else:
            fail += len(group)
        time.sleep(2)

    elapsed = time.time() - t0
    log(f"=== 完成: 成功 {ok}, 失败 {fail}, 无法提番号 {len(no_code)}, 耗时 {elapsed/60:.0f} 分钟 ===")


if __name__ == '__main__':
    main()
