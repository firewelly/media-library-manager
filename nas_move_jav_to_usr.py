#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
在 DXP4800 上执行：把 JAV 下属于收藏演员的文件夹搬到 usr。

- 目标不存在：同卷 rename（瞬时）
- 目标已存在：逐子项合并；同名文件先比大小再比 MD5，
  完全一致视为冗余副本（删源侧），不一致则保留源侧并加 .fromJAV 后缀
- .DS_Store / Thumbs.db 直接清理，不参与合并
- 空目录在搬完后清理

默认干跑，--apply 才真正执行。用法：python3 nas_move_jav_to_usr.py [--apply]
"""
import hashlib
import os
import shutil
import sys

JAV = '/volume1/Video/JAV'
USR = '/volume1/Video/usr'
LIST = '/tmp/jav_move_folders.txt'
JUNK = {'.DS_Store', 'Thumbs.db', 'desktop.ini'}


def md5_of(path, chunk=4 * 1024 * 1024):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def unique_name(dst_dir, name):
    base, ext = os.path.splitext(name)
    i = 1
    while True:
        cand = os.path.join(dst_dir, f"{base}.fromJAV-{i}{ext}")
        if not os.path.exists(cand):
            return cand
        i += 1


def merge(src, dst, log, apply_):
    for child in sorted(os.listdir(src)):
        s = os.path.join(src, child)
        d = os.path.join(dst, child)
        if child in JUNK:
            log(f"    清理垃圾: {child}")
            if apply_:
                os.remove(s)
            continue
        if not os.path.exists(d):
            log(f"    移入: {child}")
            if apply_:
                os.rename(s, d)
            continue
        if os.path.isdir(s) and os.path.isdir(d):
            log(f"    合并子目录: {child}")
            merge(s, d, log, apply_)
            if apply_:
                try:
                    os.rmdir(s)
                except OSError:
                    pass
            continue
        if os.path.isfile(s) and os.path.isfile(d):
            ss, ds = os.path.getsize(s), os.path.getsize(d)
            if ss == ds:
                if apply_:
                    same = md5_of(s) == md5_of(d)
                else:
                    same = True  # 干跑假定同大小即同内容，真正执行时会核对
                if same:
                    log(f"    冗余副本，删源侧: {child} ({ss} 字节)")
                    if apply_:
                        os.remove(s)
                    continue
            target = unique_name(dst, child) if apply_ else d + ' [将重命名保留]'
            log(f"    同名但内容不同，保留源侧为: {os.path.basename(target)}")
            if apply_:
                os.rename(s, target)
            continue
        # 类型不同（文件 vs 目录）
        target = unique_name(dst, child) if apply_ else d + ' [将重命名保留]'
        log(f"    类型冲突，保留源侧为: {os.path.basename(target)}")
        if apply_:
            os.rename(s, target)


def main():
    apply_ = '--apply' in sys.argv
    from_usr = '--from-usr' in sys.argv      # 合并 usr 内部的异体目录时用
    base = USR if from_usr else JAV
    with open(LIST, encoding='utf-8') as f:
        # 每行：源目录名  或  源目录名<TAB>目标目录名（异体名并入规范目录时用）
        pairs = []
        for l in f:
            l = l.rstrip('\n')
            if not l.strip():
                continue
            parts = l.split('\t')
            pairs.append((parts[0], parts[1] if len(parts) > 1 and parts[1] else parts[0]))
    print(f"{'执行' if apply_ else '干跑'}：{len(pairs)} 个文件夹", flush=True)

    moved = merged = skipped = 0
    for i, (f, dst_name) in enumerate(pairs, 1):
        src, dst = os.path.join(base, f), os.path.join(USR, dst_name)
        tag = f" -> {dst_name}" if dst_name != f else ""
        if not os.path.isdir(src):
            print(f"[{i}/{len(pairs)}] 跳过（源不存在）: {f}", flush=True)
            skipped += 1
            continue
        print(f"[{i}/{len(pairs)}] {f}{tag}", flush=True)
        if not os.path.exists(dst):
            if apply_:
                os.rename(src, dst)
            print("    -> usr（整目录搬移）", flush=True)
            moved += 1
        else:
            merge(src, dst, lambda m: print(m, flush=True), apply_)
            if apply_ and os.path.isdir(src) and not os.listdir(src):
                os.rmdir(src)
            merged += 1
    print(f"\n完成：整目录搬移 {moved}，合并 {merged}，跳过 {skipped}", flush=True)


if __name__ == '__main__':
    main()
