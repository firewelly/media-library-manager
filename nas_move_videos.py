#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
在 DXP4800 上按「番号目录 → 目标番号目录」搬运单个作品（文件连同附属封面/nfo），
搬完若源目录已空则删除。清单 /tmp/video_move_list.txt：源目录<TAB>目标目录（绝对路径）

用法：python3 nas_move_videos.py [--apply]
"""
import os
import shutil
import sys

LIST = '/tmp/video_move_list.txt'


def main():
    apply_ = '--apply' in sys.argv
    pairs = []
    for line in open(LIST, encoding='utf-8'):
        line = line.rstrip('\n')
        if line.strip():
            a, b = line.split('\t')
            pairs.append((a, b))
    print(f"{'执行' if apply_ else '干跑'}：{len(pairs)} 个作品目录", flush=True)

    for src, dst in pairs:
        if not os.path.isdir(src):
            print(f"  跳过（源不存在）: {src}", flush=True)
            continue
        print(f"  {src.replace('/volume1/Video/JAV/','')}  ->  usr/{dst.split('/usr/',1)[-1]}", flush=True)
        for name in sorted(os.listdir(src)):
            s, d = os.path.join(src, name), os.path.join(dst, name)
            if os.path.exists(d):
                print(f"    !! 目标已存在，跳过: {name}", flush=True)
                continue
            print(f"    移入: {name}", flush=True)
            if apply_:
                os.makedirs(dst, exist_ok=True)
                shutil.move(s, d)
        if apply_ and os.path.isdir(src) and not os.listdir(src):
            os.rmdir(src)
            print("    （源目录已空，删除）", flush=True)


if __name__ == '__main__':
    main()
