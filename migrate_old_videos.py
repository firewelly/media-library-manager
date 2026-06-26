#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
迁移"去年12月底之前 + 未打分"的本地非jav视频到 /Volumes/Essay2T/dhelper

复用项目现成的 utils.FileUtils 智能移动能力（同盘rename/跨盘copy+remove/文件名过长自动缩短），
并补充现成 GUI 迁移功能缺失的 md5 冲突去重逻辑。

源文件夹（数据库 folders 表 id=9, id=10）:
  - /Users/firewell/影视/国产mac
  - /Users/firewell/Downloads/mp42
目标文件夹（数据库 folders 表 id=14）:
  - /Volumes/Essay2T/dhelper

筛选条件:
  - file_created_time <= 2025-12-31 23:59:59（去年12月底之前）
  - stars IS NULL OR stars = 0（未打分）

冲突处理（目标已有同名文件）:
  - md5 相同 -> 删除源文件 + 删除该视频数据库记录（含关联表 video_actors / javdb_info / javdb_info_tags）
  - md5 不同 -> 源文件重命名（追加 _dupN）后迁移 + 更新数据库路径

用法:
  # 预览（默认，不改任何东西）
  python3 migrate_old_videos.py
  # 限制数量（调试）
  python3 migrate_old_videos.py --limit 20
  # 实际执行
  python3 migrate_old_videos.py --execute
  # 只迁移某个源
  python3 migrate_old_videos.py --folder /Users/firewell/Downloads/mp42
"""

import sqlite3
import os
import sys
import re
import json
import time
import shutil
import argparse
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# 复用项目现成的文件工具
from utils.file_utils import FileUtils

DB_PATH = os.path.join(BASE_DIR, 'media_library.db')
DST_DIR = '/Volumes/Essay2T/dhelper'
LOG_PATH = os.path.join(BASE_DIR, 'migration_old_videos.jsonl')

SOURCE_FOLDERS = [
    '/Users/firewell/影视/国产mac',
    '/Users/firewell/Downloads/mp42',
]
CUTOFF = datetime(2025, 12, 31, 23, 59, 59)


def log(msg):
    print(f'[{datetime.now().strftime("%H:%M:%S")}] {msg}', flush=True)


def parse_time(s):
    """解析 file_created_time，兼容日期字符串和 unix 时间戳"""
    if not s:
        return None
    s = str(s).strip()
    if re.fullmatch(r'\d{9,11}', s):
        try:
            return datetime.fromtimestamp(float(s))
        except Exception:
            return None
    for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(s[:26] if '.' in s else s[:19], fmt)
        except Exception:
            pass
    return None


def select_migrate_targets(conn, only_folder=None, limit=None):
    """筛选符合迁移条件的视频，返回 list[(id, file_path, file_name, file_size, md5_hash, file_created_time)]"""
    cur = conn.cursor()
    folders = [only_folder] if only_folder else SOURCE_FOLDERS
    out = []
    for f in folders:
        cur.execute(
            'SELECT id, file_path, file_name, file_size, md5_hash, file_created_time '
            'FROM videos WHERE file_path LIKE ? ORDER BY id',
            (f + '/%',),
        )
        for vid, fp, fn, sz, mh, fct in cur.fetchall():
            t = parse_time(fct)
            if t is None or t > CUTOFF:
                continue
            out.append((vid, fp, fn, sz, mh, fct))
    if limit:
        out = out[:limit]
    return out


def unique_dst_path(dst):
    """目标同名冲突且md5不同时，生成 _dup1/_dup2 ... 的唯一路径"""
    base, ext = os.path.splitext(dst)
    i = 1
    while True:
        cand = f'{base}_dup{i}{ext}'
        if not os.path.exists(cand):
            return cand
        i += 1


def load_done_ids():
    """读取日志中已处理过的 video_id，支持断点续传"""
    done = set()
    if not os.path.exists(LOG_PATH):
        return done
    with open(LOG_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                vid = rec.get('video_id')
                status = rec.get('status')
                if vid is not None and status in ('moved', 'renamed', 'dedup_deleted', 'skipped_exists', 'error'):
                    done.add(int(vid))
            except Exception:
                continue
    return done


def delete_video_record(conn, video_id):
    """删除 video 及其关联记录（video_actors, javdb_info 级联 javdb_info_tags）"""
    cur = conn.cursor()
    cur.execute('SELECT id FROM javdb_info WHERE video_id = ?', (video_id,))
    jids = [r[0] for r in cur.fetchall()]
    if jids:
        placeholders = ','.join('?' * len(jids))
        cur.execute(f'DELETE FROM javdb_info_tags WHERE javdb_info_id IN ({placeholders})', jids)
        cur.execute('DELETE FROM javdb_info WHERE video_id = ?', (video_id,))
    cur.execute('DELETE FROM video_actors WHERE video_id = ?', (video_id,))
    cur.execute('DELETE FROM videos WHERE id = ?', (video_id,))


def append_log(rec):
    with open(LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')


def process_one(conn, item, execute, dup_cache):
    """处理单个视频，返回记录 dict
    status: moved / renamed / dedup_deleted / error
    复用 FileUtils.move_file_smart（同盘rename/跨盘copy+remove/文件名过长自动缩短）
    """
    vid, src, fname, sz, src_md5, fct = item
    dst = os.path.join(DST_DIR, os.path.basename(src))

    if not os.path.exists(src):
        return {'video_id': vid, 'status': 'error', 'reason': 'src_not_found', 'src': src}

    # 目标不存在 -> 直接智能移动
    if not os.path.exists(dst):
        if execute:
            ok, final_path, err = FileUtils.move_file_smart(src, dst)
            if not ok:
                return {'video_id': vid, 'status': 'error', 'reason': f'move_fail:{err}', 'src': src, 'dst': dst}
            cur = conn.cursor()
            cur.execute(
                'UPDATE videos SET file_path=?, file_name=?, source_folder=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
                (final_path, os.path.basename(final_path), DST_DIR, vid),
            )
            conn.commit()
        return {'video_id': vid, 'status': 'moved', 'src': src, 'dst': dst, 'size': sz}

    # 目标已存在同名 -> 比对 md5
    dst_md5 = dup_cache.get(dst)
    if dst_md5 is None:
        dst_md5 = FileUtils.calculate_md5(dst)
        dup_cache[dst] = dst_md5

    if src_md5 and dst_md5 and src_md5 == dst_md5:
        # md5 相同 -> 删源文件 + 删DB记录
        if execute:
            try:
                FileUtils.delete_file(src, use_trash=False)
            except Exception as e:
                return {'video_id': vid, 'status': 'error', 'reason': f'remove_dup_fail:{e}', 'src': src}
            delete_video_record(conn, vid)
            conn.commit()
        return {'video_id': vid, 'status': 'dedup_deleted', 'src': src, 'dst': dst, 'md5': src_md5}

    # md5 不同 -> 重命名后智能移动
    new_dst = unique_dst_path(dst)
    if execute:
        ok, final_path, err = FileUtils.move_file_smart(src, new_dst)
        if not ok:
            return {'video_id': vid, 'status': 'error', 'reason': f'move_rename_fail:{err}', 'src': src, 'dst': new_dst}
        cur = conn.cursor()
        cur.execute(
            'UPDATE videos SET file_path=?, file_name=?, source_folder=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
            (final_path, os.path.basename(final_path), DST_DIR, vid),
        )
        conn.commit()
    return {'video_id': vid, 'status': 'renamed', 'src': src, 'dst': new_dst, 'md5': src_md5}


def backup_db():
    if not os.path.exists(DB_PATH):
        return None
    bak = f"{DB_PATH}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(DB_PATH, bak)
    return bak


def main():
    ap = argparse.ArgumentParser(description='迁移去年12月底前未打分的本地非jav视频到 Essay2T/dhelper')
    ap.add_argument('--execute', action='store_true', help='实际执行（默认仅预览）')
    ap.add_argument('--limit', type=int, help='限制处理数量（调试）')
    ap.add_argument('--folder', type=str, help='只处理指定源文件夹')
    ap.add_argument('--no-backup', action='store_true', help='跳过数据库备份（默认会备份）')
    ap.add_argument('--restart', action='store_true', help='忽略已有日志，从头开始（会清空日志）')
    args = ap.parse_args()

    if not os.path.isdir(DST_DIR):
        log(f'错误: 目标文件夹不存在或盘未挂载: {DST_DIR}')
        sys.exit(1)
    df = shutil.disk_usage(DST_DIR)
    log(f'目标盘 {DST_DIR} 可用空间: {df.free/1024/1024/1024:.1f} GB')

    if args.folder and args.folder not in SOURCE_FOLDERS:
        log(f'错误: --folder 必须是 {SOURCE_FOLDERS} 之一')
        sys.exit(1)

    if args.restart and os.path.exists(LOG_PATH):
        os.remove(LOG_PATH)
        log('已清空旧日志（--restart）')

    if args.execute and not args.no_backup:
        bak = backup_db()
        log(f'已备份数据库: {bak}')

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    targets = select_migrate_targets(conn, only_folder=args.folder, limit=args.limit)
    total = len(targets)
    total_size = sum((t[3] or 0) for t in targets)
    log(f'符合迁移条件: {total} 个, 合计 {total_size/1024/1024/1024:.2f} GB')
    if total == 0:
        log('没有符合条件的视频')
        conn.close()
        return

    done_ids = load_done_ids() if not args.restart else set()
    if done_ids:
        log(f'日志中已处理 {len(done_ids)} 个，将跳过（如需重跑加 --restart）')

    if not args.execute:
        log('=== 预览模式（不改动任何文件/数据库）===')
        conflict = sum(1 for t in targets if t[0] not in done_ids and os.path.exists(os.path.join(DST_DIR, os.path.basename(t[1]))))
        log(f'其中目标已存在同名文件(需md5比对): {conflict} 个')
        log(f'待处理(扣除已迁移): {sum(1 for t in targets if t[0] not in done_ids)} 个')
        log('前10条预览:')
        for t in targets[:10]:
            log(f'  id={t[0]} {t[2][:50]}')
        log('\n加 --execute 参数实际执行')
        conn.close()
        return

    # ===== 实际执行 =====
    log('=== 实际执行模式（复用 FileUtils.move_file_smart）===')
    dup_cache = {}
    counters = {'moved': 0, 'renamed': 0, 'dedup_deleted': 0, 'skipped': 0, 'error': 0}
    start = time.time()
    processed = 0
    for item in targets:
        vid = item[0]
        if vid in done_ids:
            counters['skipped'] += 1
            continue
        processed += 1
        rec = process_one(conn, item, execute=True, dup_cache=dup_cache)
        append_log(rec)
        counters[rec['status']] = counters.get(rec['status'], 0) + 1
        if processed % 20 == 0 or processed <= 5:
            log(f'[{processed}/{total}] {rec["status"]} id={vid} {item[2][:40]}')
        if rec['status'] == 'error':
            log(f'  ! 错误: {rec.get("reason")}')

    elapsed = time.time() - start
    log('=' * 50)
    log('迁移完成')
    log(f'  已迁移(moved):       {counters.get("moved",0)}')
    log(f'  重命名迁移(renamed): {counters.get("renamed",0)}')
    log(f'  去重删除(dedup):     {counters.get("dedup_deleted",0)}')
    log(f'  跳过(已处理):        {counters.get("skipped",0)}')
    log(f'  错误:                {counters.get("error",0)}')
    log(f'  耗时: {elapsed:.0f}秒 ({elapsed/60:.1f}分钟)')
    log(f'  日志: {LOG_PATH}')
    log('=' * 50)
    conn.close()


if __name__ == '__main__':
    main()
