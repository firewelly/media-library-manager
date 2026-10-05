#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在 DXP4800 上生成可安全删除的 U 盘源文件清单：
只收录「目标存在且大小一致」的源文件（防止删掉还没拷好的）。"""
import os

OK = '/tmp/usb_copy_ok.tsv'
OUT = '/tmp/delete_list.txt'

safe, missing_target, size_mismatch, src_gone = [], 0, 0, 0
for line in open(OK, encoding='utf-8'):
    p = line.rstrip('\n').split('\t')
    if len(p) < 4:
        continue
    src, target, size = p[0], p[1], int(p[2])
    if not os.path.exists(src):
        src_gone += 1
        continue
    if not os.path.exists(target):
        missing_target += 1
        continue
    if os.path.getsize(target) != size:
        size_mismatch += 1
        continue
    safe.append(src)

with open(OUT, 'w', encoding='utf-8') as f:
    for s in safe:
        f.write(s + '\n')

print(f"可删 {len(safe)} 个；目标缺失 {missing_target}，大小不符 {size_mismatch}，源已不存在 {src_gone}")
print(f"清单: {OUT}")
