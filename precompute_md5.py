#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
预计算指定目录下视频文件的 MD5，供后续迁移到 NAS 后直接入库使用。

算法与 media_library.py（tk 界面）的 calculate_md5_with_cache 完全一致：
整文件 hashlib.md5().hexdigest()。分块大小不影响摘要值，这里用 1MB 分块提速。

产物（默认写到脚本同目录）：
  <tag>_md5.csv        文件名,文件路径,大小(字节),MD5值
                       与 video_md5.csv 同格式，可被 smart_video_updater.py 的
                       MD5CSVIndex 直接索引
  <tag>_md5_index.json 以"相对路径"为键的完整索引，含 文件名/大小/mtime/md5，
                       迁移后路径前缀变化也能按 文件名+大小 反查
  --table 指定时另写一份简表（完整路径,文件名,MD5，UTF-8 BOM，Excel 可直接打开）
                       可放在被扫描卷的上一级，如 /Volumes/BLACK/JAV_md5.csv

特点：
  - 断点续跑：重跑时按 (大小, mtime) 校验已算条目，未变则跳过
  - 多线程：本盘为 Tuxera NTFS，单流约 300MB/s、4 线程聚合约 625MB/s
  - 增量落盘：每完成一个文件即更新产物，中断不丢已算结果

用法：
  python3 precompute_md5.py --root /Volumes/BLACK/JAV --tag black_jav --workers 4 \
                            --table /Volumes/BLACK/JAV_md5.csv
"""
import argparse
import csv
import hashlib
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

# 与 media_library.py:VIDEO_EXTENSIONS 保持一致。
# 该列表缺项会导致扫描时把"不在扫描范围"误判成"文件已消失"，勿随意裁剪。
VIDEO_EXTENSIONS = (
    '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v',
    '.ts', '.m2ts', '.mts', '.mpg', '.mpeg', '.3gp',
)

SKIP_TOKENS = (
    '/#recycle/', '/.@__thumb/', '/@eaDir/', '/.Trashes/', '/.Trash-',
    '/System Volume Information/', '/$RECYCLE.BIN/',
)

CHUNK = 1024 * 1024


def md5_of_file(path):
    h = hashlib.md5()
    n = 0
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(CHUNK), b''):
            h.update(chunk)
            n += len(chunk)
    return h.hexdigest(), n


def collect(root):
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith('.')]
        for name in filenames:
            if name.startswith('.'):
                continue
            if os.path.splitext(name)[1].lower() not in VIDEO_EXTENSIONS:
                continue
            full = os.path.join(dirpath, name)
            if any(t in full for t in SKIP_TOKENS):
                continue
            try:
                st = os.stat(full)
            except OSError as e:
                print(f"[跳过] stat 失败 {full}: {e}", flush=True)
                continue
            files.append((full, st.st_size, st.st_mtime))
    # 大文件优先，避免结尾被单个大文件拖长
    files.sort(key=lambda x: -x[1])
    return files


def load_index(path):
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[警告] 索引损坏，将重新开始: {e}", flush=True)
    return {}


def save_outputs(root, tag, entries, out_dir, table_path=None):
    """写 CSV + JSON。entries: rel_path -> {name,size,mtime,md5}"""
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, f"{tag}_md5.csv")
    json_path = os.path.join(out_dir, f"{tag}_md5_index.json")

    rows = []
    for rel, info in sorted(entries.items()):
        if not info.get('md5'):
            continue
        rows.append([info['name'], os.path.join(root, rel), info['size'], info['md5']])
    tmp = csv_path + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['文件名', '文件路径', '大小(字节)', 'MD5值'])
        w.writerows(rows)
    os.replace(tmp, csv_path)

    if table_path:
        # 供人看/交给 Excel 的简表：完整路径, 文件名, MD5。用 utf-8-sig 带 BOM，Excel 直接双击不乱码。
        os.makedirs(os.path.dirname(os.path.abspath(table_path)), exist_ok=True)
        tmp = table_path + '.tmp'
        with open(tmp, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.writer(f)
            w.writerow(['完整路径', '文件名', 'MD5'])
            for rel, info in sorted(entries.items()):
                if info.get('md5'):
                    w.writerow([os.path.join(root, rel), info['name'], info['md5']])
        os.replace(tmp, table_path)

    payload = {
        'root': root,
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'count': len(entries),
        'entries': entries,
    }
    tmp = json_path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    os.replace(tmp, json_path)
    return csv_path, json_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='/Volumes/BLACK/JAV')
    ap.add_argument('--tag', default='black_jav', help='产物文件名前缀')
    ap.add_argument('--out-dir', default=os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--table', help='额外输出简表（完整路径,文件名,MD5），如 /Volumes/BLACK/JAV_md5.csv')
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        print(f"目录不存在: {root}")
        return 1
    out_dir = os.path.abspath(args.out_dir)
    if out_dir == root or out_dir.startswith(root + os.sep):
        print(f"产物目录不能位于被扫描的卷内: {out_dir}")
        return 1
    json_path = os.path.join(out_dir, f"{args.tag}_md5_index.json")

    print(f"扫描 {root} ...", flush=True)
    files = collect(root)
    total_bytes = sum(s for _, s, _ in files)
    print(f"视频文件 {len(files)} 个，合计 {total_bytes/1024**3:.1f} GB", flush=True)
    if not files:
        return 0

    index = load_index(json_path)
    entries = index.get('entries', {}) if isinstance(index, dict) else {}

    todo = []
    skipped = 0
    for full, size, mtime in files:
        rel = os.path.relpath(full, root)
        old = entries.get(rel)
        if old and old.get('md5') and old.get('size') == size and abs(old.get('mtime', 0) - mtime) < 1:
            skipped += 1
            continue
        todo.append((full, rel, size, mtime))

    done_bytes = total_bytes - sum(s for _, _, s, _ in todo)
    print(f"已缓存 {skipped} 个（{done_bytes/1024**3:.1f} GB），待计算 {len(todo)} 个"
          f"（{(total_bytes-done_bytes)/1024**3:.1f} GB）", flush=True)
    if not todo:
        csv_path, json_path = save_outputs(root, args.tag, entries, out_dir, args.table)
        print(f"全部已完成，产物: {csv_path}"
              + (f"\n简表: {args.table}" if args.table else ""))
        return 0

    lock = threading.Lock()
    state = {'bytes': 0, 'files': 0, 'errors': 0, 't0': time.time(), 'last_save': 0.0}
    pending_bytes = sum(s for _, _, s, _ in todo)

    def flush(force=False):
        with lock:
            if not force and time.time() - state['last_save'] < 5:
                return
            state['last_save'] = time.time()
            snapshot = dict(entries)
        # 落盘放到锁外，避免阻塞其它线程
        try:
            save_outputs(root, args.tag, snapshot, out_dir, args.table)
        except Exception as e:
            print(f"[警告] 保存产物失败: {e}", flush=True)

    def work(item):
        full, rel, size, mtime = item
        try:
            md5, n = md5_of_file(full)
        except Exception as e:
            with lock:
                state['errors'] += 1
            print(f"[失败] {rel}: {e}", flush=True)
            return
        with lock:
            entries[rel] = {
                'name': os.path.basename(full),
                'size': size,
                'mtime': mtime,
                'md5': md5,
                'computed_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            }
            state['bytes'] += n
            state['files'] += 1
            elapsed = time.time() - state['t0']
            speed = state['bytes'] / elapsed / 1024**2 if elapsed else 0
            remain = pending_bytes - state['bytes']
            eta = remain / (state['bytes'] / elapsed) if state['bytes'] and elapsed else 0
            print(f"[{state['files']}/{len(todo)}] {rel}  {size/1024**3:.2f}GB  "
                  f"{speed:.0f} MB/s  剩余 {eta/60:.0f} 分钟", flush=True)
        flush()

    try:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            list(pool.map(work, todo))
    except KeyboardInterrupt:
        print("\n中断，正在保存已算结果 ...", flush=True)
        flush(force=True)
        raise

    flush(force=True)
    csv_path, json_path = save_outputs(root, args.tag, entries, out_dir, args.table)
    ok = sum(1 for e in entries.values() if e.get('md5'))
    total = time.time() - state['t0']
    print(f"\n完成：{ok} 个条目，本次 {state['files']} 个 / {state['bytes']/1024**3:.1f} GB "
          f"/ {total/60:.1f} 分钟 / {state['bytes']/total/1024**2:.0f} MB/s，失败 {state['errors']} 个", flush=True)
    print(f"产物：{csv_path}")
    print(f"      {json_path}")
    if args.table:
        print(f"简表：{args.table}", flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
