#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
在 DXP4800 上批量探测视频时长/分辨率（供入库用）。
输入 /tmp/probe_list.txt（每行一个目标路径），输出 /tmp/probe_result.tsv：
  路径 <TAB> 时长秒 <TAB> 宽x高
用 ffprobe，取不到则输出空值。
"""
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

LIST = '/tmp/probe_list.txt'
OUT = '/tmp/probe_result.tsv'


def probe(path):
    try:
        r = subprocess.run(
            ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
             '-show_entries', 'format=duration:stream=width,height',
             '-of', 'json', path],
            capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            return path, '', ''
        d = json.loads(r.stdout or '{}')
        dur = (d.get('format') or {}).get('duration') or ''
        st = (d.get('streams') or [{}])[0]
        w, h = st.get('width'), st.get('height')
        res = f"{w}x{h}" if w and h else ''
        if dur:
            dur = str(int(float(dur))) if float(dur).is_integer() else f"{float(dur):.2f}"
        return path, dur, res
    except Exception:
        return path, '', ''


def main():
    paths = [l.rstrip('\n') for l in open(LIST, encoding='utf-8') if l.strip()]
    print(f"待探测 {len(paths)} 个", flush=True)
    t0 = time.time()
    done = 0
    with open(OUT, 'w', encoding='utf-8') as f, ThreadPoolExecutor(max_workers=4) as pool:
        for path, dur, res in pool.map(probe, paths):
            f.write(f"{path}\t{dur}\t{res}\n")
            f.flush()
            done += 1
            if done % 20 == 0 or done == len(paths):
                print(f"[{done}/{len(paths)}] {(time.time()-t0):.0f}s", flush=True)
    print("完成", flush=True)


if __name__ == '__main__':
    main()
