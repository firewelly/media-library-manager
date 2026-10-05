#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
在 DXP4800 上执行：把 U 盘(BLACK) 的视频复制到 Video 卷，校验 MD5 后删除源文件。

- 计划文件 /tmp/usb_copy_plan.tsv：源路径 <TAB> 目标路径 <TAB> 大小 <TAB> 期望MD5
- 先复制成 .part，算完目标 MD5 与期望一致才改名 + 删源；不一致保留两侧并报错
- 目标已存在且 MD5 一致 → 视为已完成（删源）
- 可反复运行续跑：已完成的条目自动跳过
- 保留源文件 mtime（供后续按 path|mtime|size 命中 MD5 缓存）

用法：python3 nas_copy_usb_videos.py [--workers 3]
"""
import argparse
import hashlib
import os
import shutil
import sys
import threading
import time

PLAN = '/tmp/usb_copy_plan.tsv'
LOG = '/tmp/usb_copy.log'
CHUNK = 4 * 1024 * 1024


def md5_of(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        while True:
            b = f.read(CHUNK)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def load_plan():
    items = []
    with open(PLAN, encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')
            if not line:
                continue
            src, target, size, expected = line.split('\t')
            items.append((src, target, int(size), expected))
    return items


def process(item, log, stats, lock):
    src, target, size, expected = item
    name = os.path.basename(target)
    t0 = time.time()
    try:
        # 目标已存在：校验后决定
        if os.path.exists(target):
            if md5_of(target) == expected:
                if os.path.exists(src):
                    os.remove(src)
                return '已存在且校验通过（删源）'
            return f'!! 目标已存在但 MD5 不符，未动: {target}'

        if not os.path.exists(src):
            return f'!! 源不存在: {src}'

        os.makedirs(os.path.dirname(target), exist_ok=True)
        st = os.stat(src)
        tmp = target + '.part'
        shutil.copyfile(src, tmp)
        os.utime(tmp, ns=(st.st_atime_ns, st.st_mtime_ns))

        got = md5_of(tmp)
        if got != expected:
            os.remove(tmp)
            return f'!! 复制后 MD5 不符（源或写入异常）got={got} want={expected}'
        os.rename(tmp, target)
        os.remove(src)
        return 'OK'
    except Exception as e:
        return f'!! 异常: {e}'
    finally:
        dt = time.time() - t0
        with lock:
            stats['done'] += 1
            stats['bytes'] += size
            stats['elapsed'] += dt
            speed = stats['bytes'] / stats['elapsed'] / 1024 ** 2 if stats['elapsed'] else 0
            remain = stats['total_bytes'] - stats['bytes']
            eta = remain / (stats['bytes'] / stats['elapsed']) if stats['bytes'] and stats['elapsed'] else 0
            log(f"[{stats['done']}/{stats['total']}] {name[:44]}  {size/1024**3:.2f}GB  "
                f"累计 {speed:.0f} MB/s  剩余 {eta/3600:.1f} 小时")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workers', type=int, default=3)
    args = ap.parse_args()

    items = load_plan()
    total_bytes = sum(i[2] for i in items)
    logf = open(LOG, 'a', encoding='utf-8', buffering=1)

    def log(msg):
        line = f"{time.strftime('%H:%M:%S')} {msg}"
        print(line, flush=True)
        logf.write(line + '\n')

    log(f"===== 开始/续跑：{len(items)} 个文件, {total_bytes/1024**3:.1f} GB, {args.workers} 并发 =====")
    stats = {'done': 0, 'bytes': 0, 'elapsed': 0.0, 'total': len(items), 'total_bytes': total_bytes}
    lock = threading.Lock()

    from concurrent.futures import ThreadPoolExecutor
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for r in pool.map(lambda it: process(it, log, stats, lock), items):
            results.append(r)

    ok = sum(1 for r in results if r == 'OK')
    existed = sum(1 for r in results if r.startswith('已存在'))
    errs = [r for r in results if r.startswith('!!')]
    log(f"===== 完成：新拷 {ok}，已存在 {existed}，异常 {len(errs)} =====")
    for e in errs:
        log("   " + e)
    logf.close()


if __name__ == '__main__':
    main()
