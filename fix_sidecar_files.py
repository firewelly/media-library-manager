#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复上次迁移遗漏的刮削文件
- 把本机AV库残留的刮削文件移动到NAS对应位置
- 清理空文件夹
"""

import sqlite3
import os
import shutil
import sys

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'media_library.db')
AV_DIR = '/Users/firewell/影视/AV'
NAS_BASE = '/Volumes/Video'

# 刮削文件扩展名
SIDECAR_EXTS = ('.nfo', '-thumb.jpg', '-poster.jpg', '-fanart.jpg')
SIDECAR_NAMES = ('poster.jpg', 'fanart.jpg', 'movie.nfo')


def find_nas_target_dir(cursor, local_dir):
    """根据本地目录路径，找到NAS上对应的目标目录"""
    # 提取演员文件夹和番号文件夹
    # 例如: /Users/firewell/影视/AV/#整理完成/桜空もも/IPZZ-719-C ...
    # 需要找到: /Volumes/Video/usr/桜空もも/ 或 /Volumes/Video/JAV/桜空もも/
    
    parts = local_dir.split('/')
    # 找到 #整理完成 之后的部分
    try:
        idx = parts.index('#整理完成')
        actor_folder = parts[idx + 1] if idx + 1 < len(parts) else None
        video_folder = parts[idx + 2] if idx + 2 < len(parts) else None
    except ValueError:
        # 没有 #整理完成
        actor_folder = None
        video_folder = None
    
    if not actor_folder:
        return None
    
    # 在NAS上查找匹配的演员文件夹
    for base in ['usr', 'JAV']:
        base_path = os.path.join(NAS_BASE, base)
        if not os.path.exists(base_path):
            continue
        
        # 精确匹配
        actor_path = os.path.join(base_path, actor_folder)
        if os.path.exists(actor_path):
            if video_folder:
                video_path = os.path.join(actor_path, video_folder)
                if os.path.exists(video_path):
                    return video_path
            return actor_path
        
        # 模糊匹配（处理繁简体差异）
        for d in os.listdir(base_path):
            if actor_folder in d or d in actor_folder:
                actor_path = os.path.join(base_path, d)
                if video_folder:
                    # 查找匹配的视频文件夹
                    for vd in os.listdir(actor_path):
                        if video_folder in vd or vd in video_folder:
                            return os.path.join(actor_path, vd)
                return actor_path
    
    return None


def collect_sidecar_files(directory):
    """收集目录下的刮削文件"""
    files = []
    if not os.path.exists(directory):
        return files
    
    for f in os.listdir(directory):
        full_path = os.path.join(directory, f)
        if not os.path.isfile(full_path):
            continue
        
        # 检查是否是刮削文件
        if f in SIDECAR_NAMES:
            files.append(full_path)
        elif f.endswith('.nfo') or f.endswith('-thumb.jpg') or f.endswith('-poster.jpg') or f.endswith('-fanart.jpg'):
            files.append(full_path)
    
    return files


def move_sidecar_file(src, dst_dir):
    """移动刮削文件到目标目录"""
    if not os.path.exists(dst_dir):
        os.makedirs(dst_dir, exist_ok=True)
    
    filename = os.path.basename(src)
    dst = os.path.join(dst_dir, filename)
    
    # 如果目标已存在，检查大小
    if os.path.exists(dst):
        try:
            if os.path.getsize(src) == os.path.getsize(dst):
                return True, "already_exists"
        except Exception:
            pass
        # 大小不同，重命名
        base, ext = os.path.splitext(filename)
        counter = 1
        while os.path.exists(dst):
            dst = os.path.join(dst_dir, f"{base}_{counter}{ext}")
            counter += 1
    
    try:
        shutil.move(src, dst)
        return True, "moved"
    except Exception as e:
        return False, str(e)


def is_dir_empty(directory):
    """检查目录是否为空"""
    if not os.path.exists(directory):
        return True
    return len(os.listdir(directory)) == 0


def remove_empty_dirs(root_dir):
    """递归删除空目录"""
    removed = 0
    for dirpath, dirnames, filenames in os.walk(root_dir, topdown=False):
        if not filenames and not dirnames:
            try:
                os.rmdir(dirpath)
                removed += 1
            except Exception:
                pass
    return removed


def main():
    if not os.path.exists(DB_PATH):
        print(f"数据库不存在: {DB_PATH}")
        sys.exit(1)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 扫描本机AV库的刮削文件
    print(f"扫描 {AV_DIR} ...")
    sidecar_dirs = []
    
    for root, dirs, files in os.walk(AV_DIR):
        # 检查是否有刮削文件
        has_sidecar = False
        for f in files:
            if f in SIDECAR_NAMES or f.endswith('.nfo') or f.endswith('-thumb.jpg') or f.endswith('-poster.jpg') or f.endswith('-fanart.jpg'):
                has_sidecar = True
                break
        
        if has_sidecar:
            # 检查是否还有视频文件
            has_video = False
            for f in files:
                if f.lower().endswith(('.mp4', '.mkv', '.avi', '.wmv', '.mov', '.flv', '.iso')):
                    has_video = True
                    break
            
            if not has_video:
                sidecar_dirs.append(root)
    
    print(f"找到 {len(sidecar_dirs)} 个只有刮削文件的目录")
    
    if not sidecar_dirs:
        print("没有需要处理的目录")
        conn.close()
        return
    
    # 处理每个目录
    moved_files = 0
    moved_dirs = 0
    failed = 0
    
    for local_dir in sidecar_dirs:
        # 找到NAS目标目录
        nas_target = find_nas_target_dir(cursor, local_dir)
        
        if not nas_target:
            print(f"  ✗ 未找到NAS目标: {local_dir}")
            failed += 1
            continue
        
        # 移动刮削文件
        sidecar_files = collect_sidecar_files(local_dir)
        for src in sidecar_files:
            ok, msg = move_sidecar_file(src, nas_target)
            if ok:
                moved_files += 1
                if msg == "moved":
                    print(f"  ✓ {os.path.basename(src)} -> {os.path.basename(nas_target)}")
            else:
                print(f"  ✗ 移动失败: {src} - {msg}")
                failed += 1
        
        # 检查目录是否为空，删除空目录
        if is_dir_empty(local_dir):
            try:
                os.rmdir(local_dir)
                moved_dirs += 1
            except Exception as e:
                print(f"  ✗ 删除目录失败: {local_dir} - {e}")
    
    # 清理AV目录下的空文件夹
    print(f"\n清理空文件夹...")
    removed = remove_empty_dirs(AV_DIR)
    print(f"删除空目录: {removed} 个")
    
    conn.close()
    
    print(f"\n=== 完成 ===")
    print(f"移动刮削文件: {moved_files} 个")
    print(f"删除空目录: {moved_dirs} 个")
    print(f"清理空文件夹: {removed} 个")
    print(f"失败: {failed} 个")


if __name__ == '__main__':
    main()
