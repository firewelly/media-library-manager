#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
在 DXP4800 上把 DVD/BD 镜像(.iso)转成 MP4（HEVC/QSV，保持原分辨率）。

DVD 镜像：7z 解出 VIDEO_TS/*.VOB → 取最大的标题组(VTS_NN，排除 _0 菜单) →
         按序号 cat 成单个 MPEG-PS → yadif 去隔行 → hevc_qsv
BD 镜像：7z 解出 BDMV/STREAM/*.m2ts → 取最大者 → hevc_qsv
成功后源 ISO 移入隔离目录（不删）。幂等：输出已存在且时长有效则跳过。

用法：python3 nas_transcode_iso.py [--apply] [--workers 1]
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

QUARANTINE = '/volume1/Video/_转码原始_待确认'
TMPBASE = '/volume1/Video/_transcode_tmp'
LOG = '/tmp/transcode_iso.log'
ENCODE = ['-c:v', 'hevc_qsv', '-global_quality', '22', '-tag:v', 'hvc1',
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


def extract_iso(iso, tmpdir):
    """解出镜像内容，返回待转码的输入文件（DVD: 拼接后的 mpg；BD: 最大 m2ts）"""
    subprocess.run(['7z', 'x', '-y', f'-o{tmpdir}', iso, 'VIDEO_TS/*.VOB', 'BDMV/STREAM/*'],
                   capture_output=True, text=True, timeout=7200)

    # BD
    m2ts = []
    vob_groups = defaultdict(list)
    for root, _, files in os.walk(tmpdir):
        for f in files:
            p = os.path.join(root, f)
            if f.lower().endswith(('.m2ts', '.mts')):
                m2ts.append((os.path.getsize(p), p))
            m = re.match(r'VTS_(\d+)_(\d+)\.VOB$', f, re.I)
            if m:
                vob_groups[m.group(1)].append((int(m.group(2)), p))

    if m2ts:
        m2ts.sort(reverse=True)
        return m2ts[0][1], 'BD'

    if vob_groups:
        # 取总体积最大的标题组
        best = max(vob_groups.items(), key=lambda kv: sum(os.path.getsize(p) for _, p in kv[1]))
        parts = sorted((n, p) for n, p in best[1] if n >= 1)   # 排除 _0 菜单
        joined = os.path.join(tmpdir, 'feature.mpg')
        with open(joined, 'wb') as out:
            for _, p in parts:
                with open(p, 'rb') as f:
                    shutil.copyfileobj(f, out, 8 * 1024 * 1024)
        return joined, 'DVD'
    return None, None


def transcode(iso, dst, apply_):
    tmpdir = os.path.join(TMPBASE, f"iso_{os.getpid()}_{threading.get_ident()}_{int(time.time()*1000)}")
    os.makedirs(tmpdir, exist_ok=True)
    try:
        log(f"  解包: {os.path.basename(iso)}")
        src, kind = extract_iso(iso, tmpdir)
        if not src:
            log("  !! 解包后找不到可用视频（VOB/m2ts）")
            return False
        log(f"  {kind} 主片: {os.path.basename(src)} ({os.path.getsize(src)/1024**3:.2f} GB)")
        d_src = dur_of(src)
        cmd = ['ffmpeg', '-hide_banner', '-v', 'error', '-i', src]
        if kind == 'DVD':
            cmd += ['-vf', 'yadif=0:-1:0']
        cmd += ENCODE + ['-y', dst]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=24 * 3600)
        if r.returncode != 0:
            log(f"  !! ffmpeg 失败: {r.stderr.strip()[:300]}")
            return False
        d_out = dur_of(dst)
        if d_out <= 0 or (d_src and abs(d_out - d_src) > max(5, d_src * 0.01)):
            log(f"  !! 时长不符 源={d_src:.0f}s 输出={d_out:.0f}s")
            return False
        q = os.path.join(QUARANTINE, os.path.relpath(iso, '/volume1/Video'))
        os.makedirs(os.path.dirname(q), exist_ok=True)
        shutil.move(iso, q)
        log(f"  OK {d_out/60:.0f} 分钟，{os.path.getsize(dst)/1024**3:.2f} GB（源已隔离）")
        return True
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    apply_ = '--apply' in sys.argv
    workers = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 1
    targets = []
    for line in open('/tmp/iso_list.txt', encoding='utf-8'):
        line = line.rstrip('\n')
        if line.strip():
            a, b = line.split('\t')
            targets.append((a, b))
    log(f"===== {'执行' if apply_ else '干跑'}：{len(targets)} 个镜像，{workers} 并发 =====")
    ok = fail = skip = 0

    def work(it):
        iso, dst = it
        if os.path.exists(dst) and dur_of(dst) > 0:
            log(f"  跳过（输出已存在）: {os.path.basename(dst)}")
            return 'skip'
        log(f"  转码: {os.path.basename(iso)}")
        if not apply_:
            return 'dry'
        return 'ok' if transcode(iso, dst, apply_) else 'fail'

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for r in pool.map(work, targets):
            ok += (r == 'ok'); fail += (r == 'fail'); skip += (r == 'skip')
    log(f"===== 结束：成功 {ok}，失败 {fail}，跳过 {skip}，用时 {(time.time()-t0)/60:.1f} 分钟 =====")


if __name__ == '__main__':
    main()
