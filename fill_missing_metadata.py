#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
补齐 AV 视频缺失的演员/元数据信息

目标范围: jav/av/usr 相关文件夹中 无演员关联 的视频
三个阶段:
  rename  番号来自父文件夹、文件名本身无番号的 -> 文件重命名为番号格式 + 更新DB路径
  link    无番号但路径含演员名的 -> 直接关联 video_actors（匹配现有 actors 表，不新建演员）
  crawl   有番号的 -> javdb_crawler_single(登录态) -> javbus -> javsp -> 写库

用法:
  python3 fill_missing_metadata.py --dry-run            # 只预览所有动作
  python3 fill_missing_metadata.py --phase rename       # 执行重命名
  python3 fill_missing_metadata.py --phase link         # 执行演员关联
  python3 fill_missing_metadata.py --phase crawl --limit 5
  python3 fill_missing_metadata.py --phase all

断点:
  .fill_missing_renamed.txt   已重命名的 video_id
  .fill_missing_linked.txt    已关联演员的 video_id
  .batch_javdb_progress.txt   已成功爬取的番号（与 batch_javdb_update.py 共用）
"""
import argparse
import json
import os
import re
import sqlite3
import sys
import time
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

DB_PATH = os.path.join(BASE, 'media_library.db')
RENAMED_FILE = os.path.join(BASE, '.fill_missing_renamed.txt')
LINKED_FILE = os.path.join(BASE, '.fill_missing_linked.txt')

# 与 batch_javdb_update.py 一致的目标文件夹（jav/av/usr 相关）
FOLDER_CLAUSE = """(
    lower(v.source_folder) LIKE '%jav%' OR lower(v.source_folder) LIKE '%/av%'
    OR lower(v.source_folder) LIKE '%av_buffer%' OR lower(v.source_folder) LIKE '%usr%'
)"""

# 侧车文件模式（与 fix_sidecar_files.py 一致）
SIDECAR_SUFFIXES = ('.nfo', '-thumb.jpg', '-poster.jpg', '-fanart.jpg')

FAKE_CODE_PREFIXES = ('bhd-1080', 'bhd1080', 'zymzyp')


def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)


# ---------------------------------------------------------------- 分类

def load_actor_index(conn):
    """演员名 -> actor_id，名字归一化（去空白、小写），按长度降序优先匹配长名"""
    rows = conn.execute(
        'SELECT id, name, name_en, name_traditional, name_common, aliases FROM actors'
    ).fetchall()
    entries = []  # (normalized, actor_id, display_name)
    seen = set()
    
    # 过滤掉的词（不是演员名）
    FILTER_WORDS = {'無碼', '无码', 'uncensored'}
    
    for aid, name, ne, nt, nc, al in rows:
        # 清理 name 字段里的 (無碼) 后缀
        clean_name = re.sub(r'[\(（](無碼|无码)[\)）]', '', name).strip()
        
        candidates = [clean_name, ne, nt, nc]
        if al:
            # aliases 里也过滤掉 無碼
            candidates += [a.strip() for a in al.split(',') if a.strip() and a.strip() not in FILTER_WORDS]
        
        for n in candidates:
            if not n or len(n) < 2 or n in FILTER_WORDS:
                continue
            norm = re.sub(r'\s+', '', n.lower())
            if norm in seen or norm in FILTER_WORDS:
                continue
            seen.add(norm)
            entries.append((norm, aid, n))
    entries.sort(key=lambda x: -len(x[0]))
    return entries


def extract_code_deep(path):
    """从文件名和最多3级父目录名提取番号，返回 (code, source)"""
    from code_extractor import CodeExtractor
    ext = CodeExtractor()

    def valid(code):
        return bool(code) and not code.lower().startswith(FAKE_CODE_PREFIXES)

    code = ext.extract_code_from_filename(os.path.basename(path))
    if valid(code):
        return code, 'filename'
    d = os.path.dirname(path)
    for _ in range(3):
        if not d or d == '/':
            break
        code = ext.extract_code_from_filename(os.path.basename(d))
        if valid(code):
            return code, 'folder'
        d = os.path.dirname(d)
    return None, None


def match_actors_in_text(text, actor_index, max_actors=5):
    """在归一化文本中匹配演员名，去掉被更长名字包含的短名误匹配"""
    norm = re.sub(r'\s+', '', (text or '').lower())
    matched = []  # (actor_id, display_name, normalized)
    for anorm, aid, display in actor_index:
        if anorm in norm:
            # 跳过已被更长匹配包含的短名（如 'そら' ⊂ '蒼井そら'）
            if any(anorm in m[2] for m in matched):
                continue
            matched.append((aid, display, anorm))
            if len(matched) >= max_actors:
                break
    return matched


def get_targets(conn):
    """jav/av/usr 目录下无演员关联的视频；排除临时测试文件"""
    rows = conn.execute(f"""
        SELECT v.id, v.file_name, v.file_path
        FROM videos v
        WHERE {FOLDER_CLAUSE}
        AND NOT EXISTS (SELECT 1 FROM video_actors va WHERE va.video_id = v.id)
        ORDER BY v.file_path
    """).fetchall()
    return [r for r in rows if not (r[2] or '').startswith('/var/folders')]


def classify(videos, actor_index):
    """返回 {code_filename: [], code_folder: [], name_only: [], none: []}"""
    buckets = {'code_filename': [], 'code_folder': [], 'name_only': [], 'none': []}
    for vid, fn, fp in videos:
        code, src = extract_code_deep(fp or fn or '')
        if code:
            buckets[f'code_{src}'].append((vid, fn, fp, code))
            continue
        if match_actors_in_text(f'{fn} {fp}', actor_index):
            buckets['name_only'].append((vid, fn, fp, None))
        else:
            buckets['none'].append((vid, fn, fp, None))
    return buckets


# ---------------------------------------------------------------- rename

def load_done_set(path):
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            return set(l.strip() for l in f if l.strip())
    return set()


def append_done(path, key):
    with open(path, 'a', encoding='utf-8') as f:
        f.write(str(key) + '\n')


def candidate_names(folder, code, ext):
    """生成候选文件名: CODE.ext, CODE-CD2.ext ..."""
    yield code + ext
    n = 2
    while True:
        yield f'{code}-CD{n}{ext}'
        n += 1


def rename_one(conn, vid, fn, fp, code, dry_run):
    """重命名文件+侧车+缩略图，更新DB。返回 (status, detail)"""
    if not os.path.exists(fp):
        return 'offline', f'{code}: 文件不在线 {fp}'
    folder = os.path.dirname(fp)
    ext = os.path.splitext(fp)[1]
    old_base = os.path.splitext(os.path.basename(fp))[0]

    taken = set()
    for name in candidate_names(folder, code, ext):
        new_path = os.path.join(folder, name)
        if name not in taken and not os.path.exists(new_path) \
                and not conn.execute('SELECT 1 FROM videos WHERE file_path=?', (new_path,)).fetchone():
            break
        taken.add(name)
    else:
        return 'skip', '无可用候选文件名'
    new_base = os.path.splitext(name)[0]

    moves = [(fp, new_path)]
    # 侧车文件
    for suf in SIDECAR_SUFFIXES:
        side = fp[:-len(ext)] + suf if ext and fp.endswith(ext) else None
        if side and os.path.exists(side):
            moves.append((side, new_path[:-len(ext)] + suf))
    # 逐个检查同名其他扩展名的侧车 (CODE.nfo 等)
    for suf in ('.nfo',):
        side = old_base + suf
        sp = os.path.join(folder, side)
        if os.path.exists(sp) and (sp, new_path[:-len(ext)] + suf) not in moves:
            moves.append((sp, new_path[:-len(ext)] + suf))

    thumb = conn.execute('SELECT thumbnail_path FROM videos WHERE id=?', (vid,)).fetchone()[0]
    new_thumb = None
    if thumb and os.path.exists(thumb):
        text = os.path.splitext(thumb)[1]
        new_thumb = os.path.join(os.path.dirname(thumb), new_base + text)
        if (thumb, new_thumb) not in moves:
            moves.append((thumb, new_thumb))

    if dry_run:
        detail = ' | '.join(f'{os.path.basename(a)} -> {os.path.basename(b)}' for a, b in moves)
        return 'dry', f'{code}: {detail}'

    for src, dst in moves:
        try:
            os.rename(src, dst)
        except OSError as e:
            return 'fail', f'重命名失败 {src}: {e}'

    conn.execute('UPDATE videos SET file_path=?, file_name=?, thumbnail_path=?, '
                 'updated_at=datetime(\'now\') WHERE id=?',
                 (new_path, name, new_thumb, vid))
    conn.commit()
    detail = f'{code}: {os.path.basename(fp)} -> {name}'
    if len(moves) > 1:
        detail += f' (+{len(moves)-1}个附属文件)'
    return 'ok', detail


def phase_rename(buckets, conn, dry_run):
    done = load_done_set(RENAMED_FILE)
    items = [t for t in buckets['code_folder'] if str(t[0]) not in done]
    log(f"[rename] 待重命名: {len(items)} 个（已完成 {len(done)} 个）")
    ok = fail = skip = offline = 0
    for vid, fn, fp, code in items:
        if dry_run:
            status, detail = rename_one(conn, vid, fn, fp, code, True)
            print(f"  [{status}] {detail}", flush=True)
            if status == 'offline':
                offline += 1
            else:
                ok += 1
            continue
        status, detail = rename_one(conn, vid, fn, fp, code, False)
        if status == 'ok':
            append_done(RENAMED_FILE, vid)
            ok += 1
            log(f"  {detail}")
        elif status == 'offline':
            offline += 1
            log(f"  [离线跳过] video_id={vid} {detail}")
        else:
            fail += 1
            log(f"  [失败] video_id={vid} {detail}")
    log(f"[rename] 完成: 成功 {ok}, 离线跳过 {offline}, 失败 {fail}")
    return ok, fail


# ---------------------------------------------------------------- link

def phase_link(buckets, conn, dry_run):
    done = load_done_set(LINKED_FILE)
    items = [t for t in buckets['name_only'] if str(t[0]) not in done]
    log(f"[link] 待关联演员: {len(items)} 个（已完成 {len(done)} 个）")
    actor_index = load_actor_index(conn)
    ok = fail = 0
    for vid, fn, fp, _ in items:
        matched = match_actors_in_text(f'{fn} {fp}', actor_index)
        if not matched:
            log(f"  [跳过] 无匹配 video_id={vid}")
            continue
        if dry_run:
            names = [m[1] for m in matched]
            print(f"  {os.path.basename(fp or fn)[:60]} -> {names}", flush=True)
            ok += 1
            continue
        try:
            for aid, display, _ in matched:
                conn.execute('INSERT OR IGNORE INTO video_actors (video_id, actor_id) VALUES (?,?)',
                             (vid, aid))
            conn.commit()
            append_done(LINKED_FILE, vid)
            ok += 1
            log(f"  video_id={vid} <- {[m[1] for m in matched]}")
        except sqlite3.Error as e:
            conn.rollback()
            fail += 1
            log(f"  [失败] video_id={vid}: {e}")
    log(f"[link] 完成: 成功/预览 {ok}, 失败 {fail}")
    return ok, fail


# ---------------------------------------------------------------- crawl

def phase_crawl(buckets, dry_run, limit=None):
    from batch_javdb_update import (crawl_javdb, crawl_javbus, crawl_javsp, save_to_db,
                                    PROGRESS_FILE, MANUAL_MARKERS)
    # 番号 -> 视频列表（code_filename 优先，code_folder 已重命名后 file_name 也含番号）
    code_map = {}
    for t in buckets['code_filename'] + buckets['code_folder']:
        vid, fn, fp, code = t
        code_map.setdefault(code, []).append({'id': vid, 'file_name': fn or '', 'file_path': fp or ''})

    done = load_done_set(PROGRESS_FILE)
    failed_file = os.path.join(BASE, '.batch_javdb_failed.txt')
    failed = load_done_set(failed_file)
    pending = [c for c in code_map if c not in done and c not in failed]
    if limit:
        pending = pending[:limit]
    log(f"[crawl] 番号共 {len(code_map)}, 已成功 {len(done)}, 已失败 {len(failed)}, 本次 {len(pending)}")

    ok = fail = manual = 0
    for i, code in enumerate(pending, 1):
        group = code_map[code]
        log(f"[{i}/{len(pending)}] {code} ({len(group)}视频)")
        if dry_run:
            for v in group:
                print(f"  将爬取: {v['file_name'][:60]}", flush=True)
            ok += 1
            continue

        result, stderr = crawl_javdb(code)
        source = 'javdb'
        if result is None:
            result = crawl_javbus(code)
            source = 'javbus'
        if result is None:
            result = crawl_javsp(code)
            source = 'javsp'

        if result is None:
            err = (stderr or '').lower()
            if any(m in err for m in MANUAL_MARKERS):
                manual += 1
                log(f"  [需登录] {code}: {stderr[:120]}")
                if manual >= 3:
                    log("连续出现需人工处理的错误，请先运行 python3 javdb_crawler_single.py --login 登录后重跑")
                    break
            else:
                fail += 1
                with open(failed_file, 'a', encoding='utf-8') as f:
                    f.write(code + '\n')
                log(f"  [失败] {code}: {(stderr or '')[:120]}")
            continue

        all_ok = True
        for v in group:
            info = dict(result)
            info['video_id'] = code
            if not save_to_db(v['id'], info):
                all_ok = False
        if all_ok:
            from batch_javdb_update import mark_done
            mark_done(code)
            ok += 1
            log(f"  [成功/{source}] {result.get('title', '')[:60]}")
        else:
            fail += 1
        time.sleep(1)

    log(f"[crawl] 完成: 成功 {ok}, 失败 {fail}, 需人工 {manual}")
    return ok, fail


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--phase', choices=['rename', 'link', 'crawl', 'report', 'all'], default='report')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--limit', type=int, default=None)
    args = ap.parse_args()

    conn = sqlite3.connect(DB_PATH)
    videos = get_targets(conn)
    actor_index = load_actor_index(conn)
    buckets = classify(videos, actor_index)

    log(f"目标视频共 {len(videos)}: "
        f"文件名含番号 {len(buckets['code_filename'])}, "
        f"仅文件夹含番号 {len(buckets['code_folder'])}, "
        f"仅演员名 {len(buckets['name_only'])}, "
        f"无法处理 {len(buckets['none'])}")

    if args.phase == 'report':
        if buckets['none']:
            print("\n=== 无法自动处理的视频 ===")
            for vid, fn, fp, _ in buckets['none']:
                print(f"  {fp or fn}")
        if args.dry_run:
            print("\n--- rename 预览 ---")
            phase_rename(buckets, conn, True)
            print("\n--- link 预览 ---")
            phase_link(buckets, conn, True)
            print("\n--- crawl 预览 ---")
            phase_crawl(buckets, True, args.limit)
    elif args.phase in ('rename', 'all'):
        phase_rename(buckets, conn, args.dry_run)
        if args.phase != 'all':
            return
        buckets = classify(get_targets(conn), load_actor_index(conn))
        phase_link(buckets, conn, args.dry_run)
        buckets = classify(get_targets(conn), load_actor_index(conn))
        phase_crawl(buckets, args.dry_run, args.limit)
    elif args.phase == 'link':
        phase_link(buckets, conn, args.dry_run)
    elif args.phase == 'crawl':
        phase_crawl(buckets, args.dry_run, args.limit)

    conn.close()


if __name__ == '__main__':
    main()
