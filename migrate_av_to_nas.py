#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
迁移本机 AV 库视频到 NAS
- 收藏演员 (is_favorite=1) -> /Volumes/app/usr/<规范文件夹名>/
- 普通演员               -> /Volumes/HC530_1/JAV_H530/<规范文件夹名>/
- 演员名 -> 文件夹名 的映射以 merge.conf 为权威依据
  （每行 tab 分隔：第1列 = NAS 文件夹名，后续列 = 别名/异体字）

注意：本脚本不做挂载。请先确保 /Volumes/app 和 /Volumes/HC530_1 已挂载。
"""

import sqlite3
import os
import shutil
import subprocess
import sys

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'media_library.db')
PROGRESS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.migration_av_progress.txt')
CONF_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'merge.conf')

# DXP4800 NAS 挂载路径
USR_BASE = '/Volumes/Video/usr'
JAV_BASE = '/Volumes/Video/JAV'

# 挂载点（仅用于前置检查，不含任何凭证）
REQUIRED_MOUNTS = ['/Volumes/Video']


def load_alias_map(conf_path):
    """解析 merge.conf -> {任意别名: 第1列规范名}"""
    alias_map = {}
    if not os.path.exists(conf_path):
        print(f"警告: 未找到 {conf_path}，将直接使用数据库演员名作为文件夹名")
        return alias_map
    with open(conf_path, encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')
            if not line.strip():
                continue
            cols = [c.strip() for c in line.split('\t') if c.strip()]
            if not cols:
                continue
            canonical = cols[0]
            for c in cols:
                alias_map[c] = canonical
    return alias_map


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            return set(int(line.strip()) for line in f if line.strip())
    return set()


def save_progress(vid):
    with open(PROGRESS_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{vid}\n")


def clear_progress():
    if os.path.exists(PROGRESS_FILE):
        os.remove(PROGRESS_FILE)


def check_mounts():
    missing = [m for m in REQUIRED_MOUNTS if not os.path.exists(m)]
    if missing:
        print("错误: 以下挂载点不存在，请先挂载 NAS：")
        for m in missing:
            print(f"  - {m}")
        sys.exit(1)


def migrate_video(video_id, source_path, target_path, conn):
    """迁移视频：先移动文件，确认成功后再更新DB"""
    target_dir = os.path.dirname(target_path)
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)

    # 1. 用系统 mv 命令移动视频（更快）
    if os.path.exists(source_path):
        result = subprocess.run(['mv', source_path, target_path], capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"mv 失败: {result.stderr}")
        
        # 确认文件已移动
        if not os.path.exists(target_path):
            raise Exception(f"文件移动后目标不存在: {target_path}")
        if os.path.exists(source_path):
            raise Exception(f"源文件仍存在: {source_path}")

    # 2. 移动刮削文件
    source_dir = os.path.dirname(source_path)
    source_base = os.path.splitext(os.path.basename(source_path))[0]
    for ext in ['.nfo', '-fanart.jpg', '-poster.jpg', '.jpg', '.png']:
        sf = os.path.join(source_dir, source_base + ext)
        if os.path.exists(sf):
            tf = os.path.join(target_dir, source_base + ext)
            subprocess.run(['mv', sf, tf], capture_output=True)

    # 3. 文件移动成功后才更新DB
    c = conn.cursor()
    c.execute(
        "UPDATE videos SET file_path = ?, source_folder = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (target_path, target_dir, video_id)
    )
    conn.commit()


def main():
    if not os.path.exists(DB_PATH):
        print(f"数据库不存在: {DB_PATH}")
        sys.exit(1)

    check_mounts()

    alias_map = load_alias_map(CONF_PATH)
    print(f"merge.conf 映射条目: {len(alias_map)}")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 本机 AV 库所有视频 + 演员 + 收藏标记
    c.execute("""
        SELECT v.id, v.file_path, v.file_name,
               GROUP_CONCAT(a.name) as actors,
               GROUP_CONCAT(a.is_favorite) as fav_flags
        FROM videos v
        LEFT JOIN video_actors va ON va.video_id = v.id
        LEFT JOIN actors a ON a.id = va.actor_id
        WHERE v.source_folder LIKE '/Users/firewell/影视/AV%'
        GROUP BY v.id
        ORDER BY v.id
    """)
    videos = c.fetchall()

    processed = load_progress()
    print(f"\n本机 AV 库视频总数: {len(videos)}")
    print(f"已处理: {len(processed)}")
    print(f"待处理: {len(videos) - len(processed)}")

    if len(processed) == len(videos):
        print("\n所有视频已处理完成！")
        clear_progress()
        conn.close()
        return

    migrated = 0
    failed = 0
    skipped = 0
    created_folders = set()

    try:
        for vid, path, name, actors, fav_flags in videos:
            if vid in processed:
                continue

            if not actors:
                # 无演员 -> JAV/#未知女优
                target_base = f"{JAV_BASE}/#未知女优"
                video_folder = os.path.basename(os.path.dirname(path))
                target_path = f"{target_base}/{video_folder}/{name}"
                primary = "#未知女优"
                canonical = "#未知女优"
            else:
                alist = [a.strip() for a in actors.split(',')]
                flist = [f for f in fav_flags.split(',')]
                primary = None
                is_fav = False
                for a, f in zip(alist, flist):
                    if f == '1':
                        primary = a
                        is_fav = True
                        break
                if not primary:
                    primary = alist[0]
                canonical = alias_map.get(primary, primary)
                target_base = USR_BASE if is_fav else JAV_BASE

            if not os.path.exists(path):
                print(f"  文件不存在，跳过: {path}")
                skipped += 1
                save_progress(vid)
                continue

            if not actors:
                target_base = f"{JAV_BASE}/#未知女优"
            video_folder = os.path.basename(os.path.dirname(path))
            target_path = f"{target_base}/{canonical}/{video_folder}/{name}"

            # 记录需要新建的文件夹
            if not os.path.exists(os.path.dirname(target_path)):
                created_folders.add(f"{'usr' if target_base == USR_BASE else 'JAV'}/{canonical}")

            try:
                migrate_video(vid, path, target_path, conn)
                migrated += 1
                tag = 'usr' if target_base == USR_BASE else 'JAV'
                print(f"  [{tag}] {name[:36]} -> {canonical}")
            except Exception as e:
                print(f"  ✗ 迁移失败 {name}: {e}")
                failed += 1

            save_progress(vid)

    except KeyboardInterrupt:
        print("\n用户中断，已保存进度。下次运行将继续。")
        conn.close()
        return

    conn.close()
    print(f"\n=== 完成 ===")
    print(f"已迁移: {migrated} 个")
    print(f"失败: {failed} 个")
    print(f"跳过(文件不存在): {skipped} 个")
    if created_folders:
        print(f"\n新建文件夹 {len(created_folders)} 个:")
        for f in sorted(created_folders):
            print(f"  {f}")

    clear_progress()


if __name__ == '__main__':
    main()
