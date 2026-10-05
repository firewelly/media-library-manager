#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 DXP4800 上的转码/合并结果回写到 media_library.db。

数据来源：NAS 上的 /tmp/transcode_manifest.tsv
  单文件行：  源路径<TAB>目标路径
  合并组行：  目标路径<TAB>分卷1|分卷2|...
流程：
  1. 取回 manifest，在 NAS 上批量算目标文件的 md5 与大小
  2. 单文件：把源路径那条记录改指到新 .mp4（更新 size/md5/resolution）
  3. 合并组：第一条分卷记录改指到合并后的 mp4，其余分卷记录删除（内容已并入）
  4. 找不到源记录的，打印出来供人工确认（不新增）
用法：python3 db_apply_transcodes.py [--dry-run|--apply]
"""
import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, 'media_library.db')


def nas(cmd):
    r = subprocess.run([os.path.join(HERE, 'nas_run.sh'), cmd], capture_output=True, text=True)
    return r.stdout


def nfd(s):
    return unicodedata.normalize('NFD', s)


def to_mac(p):
    """manifest 里是 NAS 路径，库里存的是 Mac 挂载路径，需转换后再比对。"""
    return p.replace('/volume1/Video/', '/Volumes/Video/')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    if not (args.dry_run or args.apply):
        print("请指定 --dry-run 或 --apply")
        return 1

    # 1) 取回 manifest
    local = os.path.join(HERE, 'transcode_manifest.tsv')
    with open(local, 'wb') as f:
        subprocess.run([sys.executable, os.path.join(HERE, 'nas_get.py'),
                        '/tmp/transcode_manifest.tsv', local], stdout=f)
    lines = [l.rstrip('\n') for l in open(local, encoding='utf-8') if l.strip()]
    singles, groups = [], []
    for l in lines:
        a, b = l.split('\t')
        (groups if '|' in b else singles).append((a, b if '|' not in b else b.split('|')))
    print(f"manifest: 单文件 {len(singles)} 条，合并组 {len(groups)} 组")

    # 2) 在 NAS 上批量算 md5/大小
    targets = [b for _, b in singles] + [a for a, _ in groups]
    info = {}
    if targets:
        lst = '/tmp/md5_targets.txt'
        payload = '\n'.join(targets) + '\n'
        with open('/tmp/_md5_payload.txt', 'w', encoding='utf-8') as f:
            f.write(payload)
        subprocess.run([sys.executable, os.path.join(HERE, 'nas_put.py'),
                        '/tmp/_md5_payload.txt', lst])
        out = nas(f"while IFS= read -r p; do [ -z \"$p\" ] && continue; "
                  f"if [ -f \"$p\" ]; then printf '%s\\t%s\\t%s\\n' \"$p\" \"$(stat -c%s \"$p\")\" \"$(md5sum \"$p\" | cut -d' ' -f1)\"; fi; done < {lst}; true")
        for line in out.splitlines():
            p = line.split('\t')
            if len(p) == 3:
                info[p[0]] = (int(p[1]), p[2])
    print(f"已取得 {len(info)} 个目标文件的 md5/大小")

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    by_nfd = {}
    for r in cur.execute("SELECT id, file_path, md5_hash FROM videos WHERE file_path LIKE '/Volumes/%'"):
        by_nfd.setdefault(nfd(r['file_path']), []).append(r['id'])

    path_updates, md5_updates, deletes, not_found, inserts = [], [], [], [], []
    stale = []
    for src, dst in singles:
        if dst not in info:            # 目标文件不存在（可能已被清理）→ 跳过，避免写入悬空路径
            stale.append(dst)
            continue
        ids = by_nfd.get(nfd(to_mac(src)), [])
        if not ids:
            # 源不在库（如镜像转出的新文件）：目标路径也空闲时新增一条记录
            if nfd(to_mac(dst)) in by_nfd:
                not_found.append(src + '  (目标已有记录，跳过)')
            else:
                inserts.append(dst)
            continue
        new_path = nfd(to_mac(dst))
        size, md5 = info.get(dst, (None, None))
        path_updates.append((new_path, ids[0]))
        if md5:
            md5_updates.append((md5, size, ids[0]))
        for extra in ids[1:]:
            deletes.append(extra)
    for dst, parts in groups:
        if dst not in info:
            stale.append(dst)
            continue
        ids = by_nfd.get(nfd(to_mac(parts[0])), [])
        if not ids:
            if nfd(to_mac(dst)) in by_nfd:
                not_found.append(parts[0] + '  (目标已有记录，跳过)')
            else:
                inserts.append(dst)
            continue
        new_path = nfd(to_mac(dst))
        size, md5 = info.get(dst, (None, None))
        path_updates.append((new_path, ids[0]))
        if md5:
            md5_updates.append((md5, size, ids[0]))
        for p in parts[1:]:
            for pid in by_nfd.get(nfd(to_mac(p)), []):
                deletes.append(pid)
        for extra in ids[1:]:
            deletes.append(extra)

    print(f"路径更新 {len(path_updates)} 条，size/md5 更新 {len(md5_updates)} 条，"
          f"删除合并掉的重复记录 {len(deletes)} 条，新增记录 {len(inserts)} 条")
    if stale:
        print(f"跳过（目标已不存在，可能被其它会话清理）{len(stale)} 条:")
        for d in stale[:10]:
            print("   ", d.replace('/volume1/Video/', ''))
    if not_found:
        print(f"库中找不到源记录的 {len(not_found)} 条（需人工确认）:")
        for p in not_found[:10]:
            print("   ", p.replace('/volume1/Video/', ''))

    if args.dry_run:
        print("\n[dry-run] 未写入")
        return 0

    backup_dir = os.path.join(HERE, 'db_backups')
    os.makedirs(backup_dir, exist_ok=True)
    bp = os.path.join(backup_dir, f"media_library_before_transcode_{time.strftime('%Y%m%d_%H%M%S')}.db")
    shutil.copy2(DB, bp)
    print(f"\n已备份 -> {bp}")

    cur.executemany("UPDATE videos SET file_path=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", path_updates)
    cur.executemany("UPDATE videos SET md5_hash=?, file_size=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", md5_updates)
    if deletes:
        cur.executemany("DELETE FROM video_actors WHERE video_id=?", [(i,) for i in deletes])
        cur.executemany("DELETE FROM videos WHERE id=?", [(i,) for i in deletes])
    if inserts:
        from datetime import datetime
        rows = []
        for dst in inserts:
            size, md5 = info.get(dst, (None, None))
            name = os.path.basename(dst)
            base = os.path.splitext(name)[0]
            n = base.count('!')
            title = base.replace('!', '').strip()
            stars = min(5, max(2, n + 1)) if n > 0 else 0
            rows.append((nfd(to_mac(dst)), name, title, stars, size, '/Volumes/Video/usr', md5))
        cur.executemany('''INSERT INTO videos (file_path, file_name, title, stars, file_size, source_folder,
                                                md5_hash, is_nas_online, created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)''', rows)
    conn.commit()
    print(f"已写入：路径 {len(path_updates)}，size/md5 {len(md5_updates)}，删除 {len(deletes)}，新增 {len(inserts)}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
