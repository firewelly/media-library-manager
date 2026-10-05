#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
在 DXP4800 上把特殊格式转成 MP4（HEVC / QSV 硬编，保持原分辨率）。

- DVD 镜像(.iso, MPEG-2 混合隔行)：ffmpeg 直接读，yadif 去隔行
- BD 镜像(.iso, UDF)：7z 解出最大 m2ts 再转
- wmv / rmvb：直接转
- 输出与源同目录、同名换 .mp4；成功后把源移入隔离目录（默认不删）
- 幂等：输出已存在且时长相符则跳过

用法：python3 nas_transcode.py <清单文件> [--apply] [--workers 2]
清单文件每行：源路径<TAB>输出路径
"""
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

QUARANTINE = '/volume1/Video/_转码原始_待确认'
LOG = '/tmp/transcode.log'
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


def probe(path):
    """返回 (时长秒, 宽, 高, 是否可解析)"""
    try:
        r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                            'format=duration:stream=width,height',
                            '-select_streams', 'v:0', '-of', 'json', path],
                           capture_output=True, text=True, timeout=180)
        d = json.loads(r.stdout or '{}')
        dur = float((d.get('format') or {}).get('duration') or 0)
        st = (d.get('streams') or [{}])[0]
        return dur, st.get('width'), st.get('height'), r.returncode == 0
    except Exception:
        return 0, None, None, False


def transcode(src, dst, apply_):
    ext = os.path.splitext(src)[1].lower()
    tmpdir = None
    input_path = src

    if ext == '.iso':
        dur, w, h, ok = probe(src)
        if not ok:
            # UDF/BD 镜像：解包取最大 m2ts
            tmpdir = f"/tmp/iso_{os.getpid()}_{int(time.time())}"
            os.makedirs(tmpdir, exist_ok=True)
            r = subprocess.run(['7z', 'x', '-y', f'-o{tmpdir}', src, 'BDMV/STREAM/*'],
                               capture_output=True, text=True, timeout=3600)
            cands = []
            for root, _, files in os.walk(tmpdir):
                for f in files:
                    if f.lower().endswith(('.m2ts', '.mts')):
                        p = os.path.join(root, f)
                        cands.append((os.path.getsize(p), p))
            if not cands:
                log(f"  !! 解包后没有 m2ts: {src}")
                shutil.rmtree(tmpdir, ignore_errors=True)
                return False
            cands.sort(reverse=True)
            input_path = cands[0][1]
            log(f"  BD 镜像 → 主 m2ts: {os.path.basename(input_path)} ({cands[0][0]/1024**3:.1f} GB)")
        else:
            log(f"  DVD 镜像（直读）: {w}x{h} {dur/60:.0f} 分钟")

    cmd = ['ffmpeg', '-hide_banner', '-v', 'error', '-i', input_path]
    if ext == '.iso' and input_path == src:
        cmd += ['-vf', 'yadif=0:-1:0']        # DVD 隔行
    cmd += ENCODE + ['-y', dst]

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=12 * 3600)
        if r.returncode != 0:
            log(f"  !! ffmpeg 失败: {r.stderr.strip()[:300]}")
            return False
    finally:
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)

    # 校验：输出可解析且时长与源接近
    d_out, w_out, h_out, ok_out = probe(dst)
    d_src, _, _, _ = probe(input_path if input_path != src else src)
    if not ok_out or d_out <= 0:
        log(f"  !! 输出无法解析: {dst}")
        return False
    if d_src and abs(d_out - d_src) > max(5, d_src * 0.01):
        log(f"  !! 时长不符 源={d_src:.0f}s 输出={d_out:.0f}s")
        return False

    # 源移入隔离目录
    rel = os.path.relpath(src, '/volume1/Video')
    q = os.path.join(QUARANTINE, rel)
    os.makedirs(os.path.dirname(q), exist_ok=True)
    shutil.move(src, q)
    log(f"  OK {os.path.getsize(dst)/1024**3:.2f} GB（源已移入隔离目录）")
    with open('/tmp/transcode_manifest.tsv', 'a', encoding='utf-8') as mf:
        mf.write(f"{src}\t{dst}\n")
    return True


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    apply_ = '--apply' in sys.argv
    workers = 2
    if '--workers' in sys.argv:
        workers = int(sys.argv[sys.argv.index('--workers') + 1])
    pairs = []
    for line in open(args[0], encoding='utf-8'):
        line = line.rstrip('\n')
        if line.strip():
            a, b = line.split('\t')
            pairs.append((a, b))
    log(f"===== {'执行' if apply_ else '干跑'}：{len(pairs)} 个文件，{workers} 并发 =====")

    done = fail = skip = 0
    t0 = time.time()

    def work(it):
        src, dst = it
        if os.path.exists(dst):
            d_out, _, _, ok = probe(dst)
            if ok and d_out > 0:
                return 'skip'
        if not os.path.exists(src):
            log(f"  !! 源不存在: {src}")
            return 'fail'
        log(f"  转码: {os.path.basename(src)}")
        if not apply_:
            return 'dry'
        return 'ok' if transcode(src, dst, apply_) else 'fail'

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for r in pool.map(work, pairs):
            if r == 'ok':
                done += 1
            elif r == 'fail':
                fail += 1
            elif r == 'skip':
                skip += 1
    log(f"===== 结束：成功 {done}，失败 {fail}，跳过 {skip}，用时 {(time.time()-t0)/60:.1f} 分钟 =====")


if __name__ == '__main__':
    main()
