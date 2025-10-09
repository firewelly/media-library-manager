#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
演员一次性处理管道

功能：按顺序执行
1) 搜索并爬取演员信息（更新 profile_url、基础档案、入库）
2) 修复缺失头像（从 avatar_url 下载并写入 avatar_data）
3) 去重合并与档案补全（增强版处理器，默认预览模式）

使用示例：
- 预览全流程（不实际修改合并）：
  python actors_one_off_pipeline.py --limit 100 --delay-min 2 --delay-max 5 --dry-run-merge

- 实际执行合并（处理所有缺少 profile_url 的记录）：
  python actors_one_off_pipeline.py --execute-merge --merge-mode existing

主要参数：
- --limit            搜索与爬取阶段的最大演员数（None 表示自动）
- --delay-min/max    搜索与爬取阶段的随机延迟区间（秒）
- --skip-avatars     跳过头像修复阶段
- --dry-run-merge    合并阶段仅预览（默认行为）
- --execute-merge    合并阶段实际执行（与 --dry-run-merge 互斥）
- --merge-mode       合并模式：existing 或 interactive（默认 existing）
- --db-path          数据库路径，默认为 media_library.db
- --log-file         可选，保存管道输出到文件

注意：
- 本脚本通过调用项目内现有脚本：
  - search_and_crawl_actors.py（支持 --limit/--delay-min/--delay-max/--no-proxy）
  - fix_missing_avatars.py（无参数，直接修复 avatar_data）
  - merge_duplicate_actors_enhance.py（支持 --dry-run/--execute/--process-existing/--db-path）
- 为保证安全，合并阶段默认以预览模式运行。如需真正写库，请加 --execute-merge。
"""

import argparse
import subprocess
import sys
import os
from datetime import datetime


def run_step(cmd, cwd=None, log_file=None, title=None):
    """运行单个步骤命令并打印输出，可选写入日志。"""
    if title:
        print(f"\n=== {title} ===")
    else:
        print("\n=== 运行步骤 ===")

    print("命令:", " ".join(cmd))
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        all_output = []
        for line in proc.stdout:
            line = line.rstrip("\n")
            print(line)
            all_output.append(line)
        code = proc.wait()

        if log_file:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"\n\n[{datetime.now().isoformat()}] {' '.join(cmd)}\n")
                f.write("\n".join(all_output))

        if code != 0:
            raise RuntimeError(f"命令执行失败，退出码 {code}")
        return True
    except Exception as e:
        print(f"步骤失败: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="演员一次性处理管道：批量抓取入库 -> 补头像 -> 去重合并")
    parser.add_argument("--limit", type=int, default=None, help="搜索与爬取阶段的最大演员数")
    parser.add_argument("--delay-min", type=float, default=3.0, help="最小延迟时间（秒）")
    parser.add_argument("--delay-max", type=float, default=6.0, help="最大延迟时间（秒）")
    parser.add_argument("--no-proxy", action="store_true", help="搜索爬取阶段不使用代理")

    parser.add_argument("--skip-avatars", action="store_true", help="跳过头像修复阶段")
    parser.add_argument("--dry-run-merge", action="store_true", help="合并阶段仅预览（默认）")
    parser.add_argument("--execute-merge", action="store_true", help="实际执行合并（与 --dry-run-merge 互斥）")
    parser.add_argument("--merge-mode", choices=["existing", "interactive"], default="existing", help="合并模式")
    parser.add_argument("--db-path", default="media_library.db", help="数据库路径")
    parser.add_argument("--log-file", default=None, help="保存管道输出到指定日志文件")

    args = parser.parse_args()

    repo_root = os.path.dirname(os.path.abspath(__file__))

    # 1) 搜索并爬取演员信息
    crawl_cmd = [
        sys.executable,
        os.path.join(repo_root, "search_and_crawl_actors.py"),
        "--delay-min", str(args.delay_min),
        "--delay-max", str(args.delay_max),
    ]
    if args.limit is not None:
        crawl_cmd += ["--limit", str(args.limit)]
    if args.no_proxy:
        crawl_cmd += ["--no-proxy"]

    ok = run_step(crawl_cmd, cwd=repo_root, log_file=args.log_file, title="步骤1：搜索并爬取演员信息")
    if not ok:
        print("搜索与爬取阶段失败，终止管道。")
        sys.exit(1)

    # 2) 修复缺失头像
    if not args.skip_avatars:
        fix_cmd = [
            sys.executable,
            os.path.join(repo_root, "fix_missing_avatars.py"),
        ]
        ok = run_step(fix_cmd, cwd=repo_root, log_file=args.log_file, title="步骤2：修复缺失头像")
        if not ok:
            print("修复头像阶段失败，继续后续步骤前请检查网络与代理设置。")
    else:
        print("跳过步骤2：头像修复")

    # 3) 增强版处理器（去重与补全）
    merge_cmd = [
        sys.executable,
        os.path.join(repo_root, "merge_duplicate_actors_enhance.py"),
        "--db-path", args.db_path,
    ]

    # 合并模式
    if args.merge_mode == "existing":
        merge_cmd += ["--process-existing"]

    # 执行模式 vs 预览模式
    if args.execute_merge and not args.dry_run_merge:
        merge_cmd += ["--execute"]
    else:
        merge_cmd += ["--dry-run"]

    ok = run_step(merge_cmd, cwd=repo_root, log_file=args.log_file, title="步骤3：去重合并与档案补全（增强版）")
    if not ok:
        print("去重合并阶段执行失败，请先以 --dry-run-merge 预览诊断具体问题。")
        sys.exit(1)

    print("\n🎉 管道执行完成！")


if __name__ == "__main__":
    main()