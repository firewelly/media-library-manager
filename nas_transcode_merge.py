#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
在 DXP4800 上把「同一番号的分卷文件」转码后合并成一个 MP4（HEVC/QSV）。

清单 /tmp/wmv_groups.txt 每行：目标mp4<TAB>分卷1|分卷2|...
流程：逐卷转成同参数 mp4（临时）→ concat demuxer 无损拼接 → 校验时长≈各卷之和
      → 分卷源移入隔离目录。幂等：目标已存在且时长有效则跳过。

用法：python3 nas_transcode_merge.py [--apply] [--workers 1]
"""
import os
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

QUARANTINE = '/volume1/Video/_转码原始_待确认'
TMPBASE = '/volume1/Video/_transcode_tmp'
LOG = '/tmp/transcode_merge.log'
ENCODE = ['-c:v', 'hevc_qsv', '-preset', 'veryfast', '-global_quality', '22', '-tag:v', 'hvc1',
          '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart']


def log(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    try:
        with open(LOG, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass


def dur_of(path):
    try:
        r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                            '-of', 'csv=p=0', path], capture_output=True, text=True, timeout=300)
        return float(r.stdout.strip() or 0)
    except Exception:
        return 0


def run_group(dst, parts, apply_):
    tmpdir = os.path.join(TMPBASE, f"mg_{os.getpid()}_{threading.get_ident()}_{int(time.time()*1000)}")
    os.makedirs(tmpdir, exist_ok=True)
    try:
        outs = []
        for i, p in enumerate(parts, 1):
            if not os.path.exists(p):
                log(f"  !! 分卷不存在: {p}")
                return False
            o = os.path.join(tmpdir, f"p{i}.mp4")
            log(f"  卷 {i}/{len(parts)}: {os.path.basename(p)}")
            r = subprocess.run(['ffmpeg', '-hide_banner', '-v', 'error', '-i', p] + ENCODE + ['-y', o],
                               capture_output=True, text=True, timeout=12 * 3600)
            if r.returncode != 0 or dur_of(o) <= 0:
                log(f"  !! 分卷转码失败: {r.stderr.strip()[:200]}")
                return False
            outs.append(o)
        # concat 无损拼接
        lst = os.path.join(tmpdir, 'list.txt')
        with open(lst, 'w', encoding='utf-8') as f:
            for o in outs:
                f.write(f"file '{o}'\n")
        r = subprocess.run(['ffmpeg', '-hide_banner', '-v', 'error', '-f', 'concat', '-safe', '0',
                            '-i', lst, '-c', 'copy', '-movflags', '+faststart', '-y', dst],
                           capture_output=True, text=True, timeout=6 * 3600)
        if r.returncode != 0:
            log(f"  !! 拼接失败: {r.stderr.strip()[:200]}")
            return False
        d_out = dur_of(dst)
        d_sum = sum(dur_of(o) for o in outs)
        if d_out <= 0 or abs(d_out - d_sum) > max(5, d_sum * 0.01):
            log(f"  !! 拼接后时长不符 各卷和={d_sum:.0f}s 输出={d_out:.0f}s")
            return False
        for p in parts:
            q = os.path.join(QUARANTINE, os.path.relpath(p, '/volume1/Video'))
            os.makedirs(os.path.dirname(q), exist_ok=True)
            shutil.move(p, q)
        log(f"  OK {d_out/60:.0f} 分钟，{os.path.getsize(dst)/1024**3:.2f} GB（{len(parts)} 卷已合并，源已隔离）")
        with open('/tmp/transcode_manifest.tsv', 'a', encoding='utf-8') as mf:
            mf.write(f"{dst}\t" + '|'.join(parts) + '\n')
        return True
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    apply_ = '--apply' in sys.argv
    workers = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 1
    groups = []
    for line in open('/tmp/wmv_groups.txt', encoding='utf-8'):
        line = line.rstrip('\n')
        if line.strip():
            dst, parts = line.split('\t')
            groups.append((dst, parts.split('|')))
    log(f"===== {'执行' if apply_ else '干跑'}：{len(groups)} 组，{workers} 并发 =====")
    ok = fail = skip = 0

    def work(it):
        dst, parts = it
        if os.path.exists(dst) and dur_of(dst) > 0:
            log(f"  跳过（目标已存在）: {os.path.basename(dst)}")
            return 'skip'
        log(f"  合并组: {os.path.basename(dst)} （{len(parts)} 卷）")
        if not apply_:
            return 'dry'
        return 'ok' if run_group(dst, parts, apply_) else 'fail'

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for r in pool.map(work, groups):
            ok += (r == 'ok'); fail += (r == 'fail'); skip += (r == 'skip')
    log(f"===== 结束：成功 {ok}，失败 {fail}，跳过 {skip}，用时 {(time.time()-t0)/60:.1f} 分钟 =====")


if __name__ == '__main__':
    main()
