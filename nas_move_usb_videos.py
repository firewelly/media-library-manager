#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
在 DXP4800 上执行：把 U 盘(BLACK) 的视频搬到 Video 卷，三段式，可反复续跑。

  1) copy   只读源、写目标（不碰 U 盘写入），完成后写入 ledger
  2) verify 读目标算 MD5 与期望值比对，通过的写入 ok ledger
  3) delete 只删除 ok ledger 里、且目标存在且大小正确的源文件

计划 /tmp/usb_copy_plan.tsv：源路径 <TAB> 目标路径 <TAB> 大小 <TAB> 期望MD5
账本 /tmp/usb_copy_ledger.tsv（copy 完成）、/tmp/usb_copy_ok.tsv（verify 通过）

用法：
  python3 nas_move_usb_videos.py copy    [--workers 1]
  python3 nas_move_usb_videos.py verify  [--workers 4]
  python3 nas_move_usb_videos.py delete
"""
import argparse
import hashlib
import os
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor

PLAN = '/tmp/usb_copy_plan.tsv'
LEDGER = '/tmp/usb_copy_ledger.tsv'
OKLEDGER = '/tmp/usb_copy_ok.tsv'
LOG = '/tmp/usb_move.log'
CHUNK = 4 * 1024 * 1024


def log(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


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
            if line:
                src, target, size, md5 = line.split('\t')
                items.append((src, target, int(size), md5))
    return items


def read_ledger(path):
    done = {}
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            for line in f:
                p = line.rstrip('\n').split('\t')
                if len(p) >= 4:
                    done[p[1]] = (p[0], int(p[2]), p[3])
    return done


def append_ledger(path, src, target, size, md5):
    with open(path, 'a', encoding='utf-8') as f:
        f.write(f"{src}\t{target}\t{size}\t{md5}\n")


def do_copy(items, workers):
    ledger = read_ledger(LEDGER)
    todo = [it for it in items if it[1] not in ledger]
    todo.sort(key=lambda x: -x[2])          # 大文件先做，避免长尾
    total_bytes = sum(i[2] for i in todo)
    log(f"[copy] 待复制 {len(todo)} 个 / {total_bytes/1024**3:.1f} GB（已完成 {len(ledger)}）")
    if not todo:
        return
    state = {'bytes': 0, 'n': 0, 't0': time.time()}

    def work(it):
        src, target, size, md5 = it
        name = os.path.basename(target)
        try:
            if os.path.exists(target) and os.path.getsize(target) == size:
                append_ledger(LEDGER, src, target, size, md5)
                return f"已存在，跳过: {name}"
            if not os.path.exists(src):
                # 先前那轮（边拷边删）已完成并删源的文件：目标在且大小对，补记账本，交给 verify 校验
                if os.path.exists(target) and os.path.getsize(target) == size:
                    append_ledger(LEDGER, src, target, size, md5)
                    return f"源已删（先前完成）: {name}"
                return f"!! 源不存在且目标缺失: {src}"
            os.makedirs(os.path.dirname(target), exist_ok=True)
            st = os.stat(src)
            tmp = target + '.part'
            shutil.copyfile(src, tmp)
            os.utime(tmp, ns=(st.st_atime_ns, st.st_mtime_ns))
            os.rename(tmp, target)
            append_ledger(LEDGER, src, target, size, md5)
            return None
        except Exception as e:
            return f"!! 复制失败 {name}: {e}"
        finally:
            state['bytes'] += size
            state['n'] += 1
            el = time.time() - state['t0']
            sp = state['bytes'] / el / 1024 ** 2 if el else 0
            eta = (total_bytes - state['bytes']) / (state['bytes'] / el) if state['bytes'] and el else 0
            if state['n'] % 5 == 0 or state['n'] == len(todo):
                log(f"[copy] {state['n']}/{len(todo)}  {state['bytes']/1024**3:.1f}/{total_bytes/1024**3:.1f} GB  "
                    f"{sp:.0f} MB/s  剩余 {eta/3600:.1f} 小时")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for r in pool.map(work, todo):
            if r:
                log("   " + r)
    log(f"[copy] 结束：ledger 共 {len(read_ledger(LEDGER))} 条")


def do_verify(items, workers):
    ledger = read_ledger(LEDGER)
    ok = read_ledger(OKLEDGER)
    todo = [it for it in items if it[1] in ledger and it[1] not in ok]
    total = sum(i[2] for i in todo)
    log(f"[verify] 待校验 {len(todo)} 个 / {total/1024**3:.1f} GB（已通过 {len(ok)}）")
    state = {'bytes': 0, 'n': 0, 'bad': 0, 't0': time.time()}

    def work(it):
        src, target, size, md5 = it
        try:
            if not os.path.exists(target):
                return f"!! 目标缺失: {target}"
            got = md5_of(target)
            if got == md5:
                append_ledger(OKLEDGER, src, target, size, md5)
                return None
            return f"!! MD5 不符 {os.path.basename(target)}: got={got} want={md5}"
        except Exception as e:
            return f"!! 校验异常 {os.path.basename(target)}: {e}"
        finally:
            state['bytes'] += size
            state['n'] += 1
            el = time.time() - state['t0']
            sp = state['bytes'] / el / 1024 ** 2 if el else 0
            eta = (total - state['bytes']) / (state['bytes'] / el) if state['bytes'] and el else 0
            if state['n'] % 20 == 0 or state['n'] == len(todo):
                log(f"[verify] {state['n']}/{len(todo)}  {sp:.0f} MB/s  剩余 {eta/60:.0f} 分钟")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for r in pool.map(work, todo):
            if r:
                log("   " + r)
                state['bad'] += 1
    log(f"[verify] 结束：通过 {len(read_ledger(OKLEDGER))}，异常 {state['bad']}")


def do_delete():
    ok = read_ledger(OKLEDGER)
    log(f"[delete] 校验通过可删源: {len(ok)} 个")
    deleted = kept = 0
    for target, (src, size, md5) in ok.items():
        try:
            if not os.path.exists(src):
                kept += 1
                continue
            if not (os.path.exists(target) and os.path.getsize(target) == size):
                log(f"   !! 目标异常，保留源: {src}")
                kept += 1
                continue
            os.remove(src)
            deleted += 1
        except Exception as e:
            log(f"   !! 删除失败 {src}: {e}")
            kept += 1
    log(f"[delete] 结束：删除 {deleted}，保留 {kept}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['copy', 'verify', 'delete'])
    ap.add_argument('--workers', type=int, default=None)
    args = ap.parse_args()
    items = load_plan()
    if args.mode == 'copy':
        do_copy(items, args.workers or 1)
    elif args.mode == 'verify':
        do_verify(items, args.workers or 4)
    else:
        do_delete()


if __name__ == '__main__':
    main()
