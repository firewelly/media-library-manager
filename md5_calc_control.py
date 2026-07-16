#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NAS上计算md5的控制脚本
步骤：
1. 导出待处理任务到文件
2. 传到NAS
3. 在NAS上后台运行计算脚本
4. 传回结果
5. 导入结果到数据库

用法：
  python3 md5_calc_control.py --export      # 导出任务并上传到NAS
  python3 md5_calc_control.py --status      # 检查任务状态
  python3 md5_calc_control.py --download    # 下载结果
  python3 md5_calc_control.py --import      # 导入结果到数据库
"""

import sqlite3
import os
import subprocess
import sys
import json
import time

# 配置
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'media_library.db')
CREDENTIAL_FILE = '/Users/firewell/Library/CloudStorage/OneDrive-Personal/bioinfo/MacMgt/config/nas/dx4600/overview.json'
WORK_DIR = '/tmp/md5_calc'
NAS_WORK_DIR = '/tmp/md5_calc'

# 支持的NAS文件夹前缀（macOS挂载路径）
NAS_VOLUME_PREFIXES = [
    '/Volumes/国产_DX4600/',
    '/Volumes/app/usr/',
    '/Volumes/HC530_1/',
    '/Volumes/Jav_HDD4/',
]


def load_credential():
    """加载NAS连接信息"""
    with open(CREDENTIAL_FILE, 'r') as f:
        data = json.load(f)
    return {
        'host': data['ip'],
        'user': data['ssh']['users'][0]['username'],
        'password': data['ssh']['users'][0]['password']
    }


def ssh_cmd(cmd, cred, capture=False, timeout=120):
    """执行SSH命令，增加超时控制"""
    full_cmd = ['sshpass', '-p', cred['password'], 'ssh', '-o', 'StrictHostKeyChecking=no',
                f"{cred['user']}@{cred['host']}", cmd]
    try:
        if capture:
            result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=timeout)
            return result.stdout.strip()
        else:
            subprocess.run(full_cmd, timeout=timeout)
            return None
    except subprocess.TimeoutExpired:
        print(f"⚠️ SSH命令超时: {cmd[:80]}")
        return None if capture else None


def scp_file(local, remote, cred, to_remote=True):
    """传输文件（使用SSH+cat方式，兼容UGREEN NAS）"""
    if to_remote:
        with open(local, 'rb') as f:
            cmd = ['sshpass', '-p', cred['password'], 'ssh', '-o', 'StrictHostKeyChecking=no',
                   f"{cred['user']}@{cred['host']}", f'cat > {remote}']
            subprocess.run(cmd, stdin=f, check=True)
    else:
        cmd = ['sshpass', '-p', cred['password'], 'ssh', '-o', 'StrictHostKeyChecking=no',
               f"{cred['user']}@{cred['host']}", f'cat {remote}']
        with open(local, 'wb') as f:
            subprocess.run(cmd, stdout=f, check=True)


def export_tasks():
    """导出待处理任务"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 获取在线的NAS文件夹（从 folders 表）
    c.execute("SELECT folder_path FROM folders WHERE is_active = 1 AND folder_path LIKE '/Volumes/%'")
    active_nas_folders = [r[0] for r in c.fetchall()]

    if not active_nas_folders:
        print("没有活跃的NAS文件夹")
        conn.close()
        return None

    # 也检查 macOS 挂载点是否实际在线
    online_folders = [f for f in active_nas_folders if os.path.exists(f)]
    offline_folders = [f for f in active_nas_folders if not os.path.exists(f)]

    print(f"活跃NAS文件夹: {len(online_folders)} 个在线, {len(offline_folders)} 个离线")
    for f in online_folders:
        print(f"  ✅ {f}")
    for f in offline_folders:
        print(f"  ❌ {f}")

    if not online_folders:
        print("没有在线的NAS文件夹")
        conn.close()
        return None

    # 构建查询条件：按 source_folder 前缀匹配
    like_clauses = []
    for f in online_folders:
        # 确保前缀以 / 结尾
        prefix = f.rstrip('/') + '/'
        like_clauses.append(f"file_path LIKE '{prefix}%'")
    where_clause = f"({' OR '.join(like_clauses)})"

    c.execute(f"""
        SELECT id, file_path 
        FROM videos 
        WHERE {where_clause} 
          AND (md5_hash IS NULL OR md5_hash = '')
        ORDER BY id
    """)
    records = c.fetchall()
    conn.close()

    if not records:
        print("没有待处理的记录（所有在线NAS视频都已有MD5）")
        return None

    # 写入任务文件
    os.makedirs(WORK_DIR, exist_ok=True)
    tasks_file = os.path.join(WORK_DIR, 'tasks.txt')
    with open(tasks_file, 'w') as f:
        for vid, path in records:
            f.write(f"{vid},{path}\n")

    print(f"\n导出任务: {len(records)} 条 -> {tasks_file}")

    # 按文件夹统计分布
    folder_stats = {}
    for vid, path in records:
        # 提取 /Volumes/xxx/ 部分
        parts = path.split('/')
        if len(parts) >= 3:
            key = '/'.join(parts[:3])
        else:
            key = path
        folder_stats[key] = folder_stats.get(key, 0) + 1

    print("\n按文件夹分布:")
    for folder, count in sorted(folder_stats.items(), key=lambda x: -x[1]):
        print(f"  {folder}: {count} 条")

    return tasks_file


def upload_and_run(tasks_file, cred):
    """上传任务并在NAS上运行"""
    # 清理旧的任务产物
    print("清理旧的任务产物...")
    ssh_cmd(f'rm -f {NAS_WORK_DIR}/results.txt {NAS_WORK_DIR}/results.txt.progress {NAS_WORK_DIR}/results.txt.fail_log {NAS_WORK_DIR}/calc.log 2>/dev/null', cred)

    # 创建工作目录
    print("创建远程工作目录...")
    ssh_cmd(f'mkdir -p {NAS_WORK_DIR}', cred)
    time.sleep(1)

    # 上传任务文件
    print("上传任务文件...")
    scp_file(tasks_file, f'{NAS_WORK_DIR}/tasks.txt', cred)

    # 上传计算脚本
    script_local = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'md5_calc_nas.sh')
    print("上传计算脚本...")
    scp_file(script_local, f'{NAS_WORK_DIR}/md5_calc_nas.sh', cred)

    # 在NAS上后台运行（nohup 确保SSH断开后继续运行）
    print("在NAS上启动后台任务...")
    cmd = f'cd {NAS_WORK_DIR} && nohup bash md5_calc_nas.sh tasks.txt results.txt > calc.log 2>&1 &'
    ssh_cmd(cmd, cred)

    print(f"\n✅ 任务已启动（后台运行，SSH断开不影响）")
    print(f"\n查看进度:")
    print(f"  python3 {os.path.basename(__file__)} --status")
    print(f"\n任务完成后下载结果:")
    print(f"  python3 {os.path.basename(__file__)} --download")


def download_results(cred):
    """下载结果文件"""
    os.makedirs(WORK_DIR, exist_ok=True)

    # 同时下载结果、进度和失败日志
    results_file = os.path.join(WORK_DIR, 'results.txt')
    fail_log_file = os.path.join(WORK_DIR, 'fail_log.txt')

    print("下载结果文件...")
    scp_file(f'{NAS_WORK_DIR}/results.txt', results_file, cred, to_remote=False)

    print("下载失败日志...")
    ssh_cmd(f'cat {NAS_WORK_DIR}/results.txt.fail_log 2>/dev/null || echo "无失败日志"', cred, capture=True)
    fail_log = ssh_cmd(f'cat {NAS_WORK_DIR}/results.txt.fail_log 2>/dev/null', cred, capture=True)
    if fail_log:
        with open(fail_log_file, 'w') as f:
            f.write(fail_log)
        print(f"失败日志: {fail_log_file}")

    # 统计结果
    if os.path.exists(results_file):
        with open(results_file, 'r') as f:
            lines = f.readlines()
        ok = sum(1 for l in lines if l.strip() and len(l.strip().split(',')[-1]) == 32)
        fail = len(lines) - ok
        print(f"\n结果统计: {ok} 条成功, {fail} 条失败, 共 {len(lines)} 条")

    print(f"\n结果已下载: {results_file}")
    return results_file


def import_results(results_file):
    """导入结果到数据库"""
    if not os.path.exists(results_file):
        print(f"结果文件不存在: {results_file}")
        return

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    updated = 0
    failed = 0
    skipped = 0

    with open(results_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(',', 1)  # 只分割第一个逗号（md5值中不含逗号）
            if len(parts) != 2:
                skipped += 1
                continue
            vid, md5 = parts
            if not md5 or len(md5) != 32:  # MD5应该是32位十六进制
                failed += 1
                continue

            c.execute("UPDATE videos SET md5_hash = ? WHERE id = ?", (md5, vid))
            updated += 1

    conn.commit()

    # 验证
    c.execute("SELECT COUNT(*) FROM videos WHERE md5_hash IS NOT NULL AND md5_hash != ''")
    total_with_md5 = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM videos")
    total_videos = c.fetchone()[0]
    conn.close()

    print(f"\n导入完成:")
    print(f"  更新: {updated} 条")
    print(f"  失败(空/无效MD5): {failed} 条")
    print(f"  跳过(格式错误): {skipped} 条")
    print(f"\n数据库MD5覆盖率: {total_with_md5}/{total_videos} ({total_with_md5*100//total_videos}%)")


def check_status(cred):
    """检查NAS上的任务状态"""
    print("检查任务状态...\n")

    # 检查进程
    result = ssh_cmd('ps aux | grep md5_calc_nas | grep -v grep', cred, capture=True)
    if result:
        print("✅ 任务正在运行:")
        print(f"  {result}")
    else:
        print("⏹️ 任务已结束（或未启动）")

    # 检查进度（calc.log 最后几行）
    result = ssh_cmd(f'tail -10 {NAS_WORK_DIR}/calc.log 2>/dev/null || echo "日志文件不存在"', cred, capture=True)
    print(f"\n最近日志:")
    print(result)

    # 检查结果文件行数
    result = ssh_cmd(f'wc -l {NAS_WORK_DIR}/results.txt 2>/dev/null || echo "结果文件不存在"', cred, capture=True)
    print(f"\n结果文件: {result}")

    # 检查任务总数
    result = ssh_cmd(f'wc -l {NAS_WORK_DIR}/tasks.txt 2>/dev/null || echo "任务文件不存在"', cred, capture=True)
    print(f"任务文件: {result}")

    # 检查失败日志
    result = ssh_cmd(f'wc -l {NAS_WORK_DIR}/results.txt.fail_log 2>/dev/null || echo "无失败日志"', cred, capture=True)
    print(f"失败日志: {result}")


def main():
    if len(sys.argv) < 2:
        print("用法:")
        print(f"  python3 {sys.argv[0]} --export      # 导出任务并上传到NAS")
        print(f"  python3 {sys.argv[0]} --status      # 检查任务状态")
        print(f"  python3 {sys.argv[0]} --download    # 下载结果")
        print(f"  python3 {sys.argv[0]} --import      # 导入结果到数据库")
        return

    action = sys.argv[1]

    if action == '--export':
        cred = load_credential()
        tasks_file = export_tasks()
        if tasks_file:
            upload_and_run(tasks_file, cred)

    elif action == '--status':
        cred = load_credential()
        check_status(cred)

    elif action == '--download':
        cred = load_credential()
        download_results(cred)

    elif action == '--import':
        results_file = os.path.join(WORK_DIR, 'results.txt')
        import_results(results_file)

    else:
        print(f"未知操作: {action}")


if __name__ == '__main__':
    main()
