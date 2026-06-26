#!/usr/bin/env python3
"""批量更新指定文件夹的 JAVDB 信息"""
import subprocess, sys, os

FOLDERS = {
    12: "/Volumes/app/usr",
    16: "/Volumes/HC530_1/JAV_H530",
    28: "/Volumes/Jav_HDD4",
}

script = os.path.join(os.path.dirname(__file__), "nas_javdb_updater.py")
env = os.environ.copy()
env["PYTHONUNBUFFERED"] = "1"

for fid, fpath in FOLDERS.items():
    print(f"\n{'='*60}")
    print(f"开始处理文件夹 ID={fid}: {fpath}")
    print(f"{'='*60}")
    result = subprocess.run(
        [sys.executable, script, "--no-proxy", "--test", "--test-folder", fpath],
        cwd=os.path.dirname(script),
        env=env,
    )
    if result.returncode != 0:
        print(f"⚠️  文件夹 {fid} 处理异常，退出码: {result.returncode}")
    print(f"文件夹 {fid} 处理完成\n")
