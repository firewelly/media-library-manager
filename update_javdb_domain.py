#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量更新 JavDB 镜像域名配置脚本

javdb 镜像域名经常变化（javdbNNN.com），本脚本自动扫描项目中所有配置文件，
将旧的镜像域名替换为新域名。

注意：javdb.com（代理主域名）不会被替换，只替换 javdbNNN.com（3位数字镜像域名）。

用法:
  # 查看当前项目配置的所有 javdb 域名
  python3 update_javdb_domain.py --show

  # 将旧镜像域名替换为新域名（默认预览模式）
  python3 update_javdb_domain.py --new-domain 574             # 预览模式
  python3 update_javdb_domain.py --new-domain 574 --backup    # 备份+执行

  # 一步到位
  python3 update_javdb_domain.py --new-domain 575 --force --backup
"""

import argparse
import os
import re
import shutil
import sys
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# 要扫描的文件类型
CONFIG_EXTENSIONS = {'.py', '.yml', '.yaml', '.toml', '.cfg', '.ini', '.md'}

# 排除目录
EXCLUDE_DIRS = {
    '__pycache__', '.git', '.codebuddy', '.vscode', '.idea',
    'venv', 'env', '.env', '.edge_driver_user_data',
    '__pycache__', '.pytest_cache', '.github',
    'build', 'dist', 'node_modules',
}

# javdbNNN.com 正则（3位数字镜像域名，不含 javdb.com）
MIRROR_DOMAIN_RE = re.compile(r'javdb(\d{3})\.com')


def make_alternates_block(domain):
    """生成 JAVDB_ALTERNATE_DIRECT_DOMAINS 列表内容"""
    domain_num = domain.replace('.com', '').replace('javdb', '')
    alt_nums = list(range(571, int(domain_num) + 1))
    lines = ['    "javdb{n}.com",'.format(n=n) for n in alt_nums]
    lines += ['    "www.javdb{n}.com",'.format(n=n) for n in alt_nums]
    return '\n'.join(lines)


# ========== 替换规则 ==========
# (file_glob_regex, search_pattern, replace_func(match, new_domain_full))

def repl_direct_domain(m, d):
    return m.group(1) + d + m.group(2)

def repl_alternates(m, d):
    return m.group(1) + '\n' + make_alternates_block(d) + '\n' + m.group(2)

def repl_config_yml(m, d):
    return m.group(1) + d + m.group(2)

def repl_getattr_default(m, d):
    return m.group(1) + d + m.group(2)

def repl_help_text(m, d):
    return m.group(1) + d + m.group(2)

def repl_sql_like(m, d):
    return m.group(1) + d + m.group(2)

REPLACE_RULES = [
    # config.py / config.example.py: JAVDB_DIRECT_DOMAIN
    (r'.*config(\.example)?\.py$',
     r'(JAVDB_DIRECT_DOMAIN\s*=\s*["\'])javdb\d{3}(\.com["\'])',
     repl_direct_domain),

    # config.py / config.example.py: JAVDB_ALTERNATE_DIRECT_DOMAINS 列表
    (r'.*config(\.example)?\.py$',
     r'(JAVDB_ALTERNATE_DIRECT_DOMAINS\s*=\s*\[).*?(\])',
     repl_alternates),

    # JavSP config.yml: proxy_free.javdb
    (r'.*config\.yml$',
     r'(javdb:\s*["\']https?://)javdb\d{3}(\.com["\'])',
     repl_config_yml),

    # 脚本中 getattr 回退默认值
    (r'.*\.py$',
     r'(["\']JAVDB_DIRECT_DOMAIN["\'],\s*["\'])javdb\d{3}(\.com["\'])',
     repl_getattr_default),

    # 帮助文本中的示例域名
    (r'.*\.py$',
     r'(https?://)javdb\d{3}(\.com/[a-zA-Z0-9/]*)',
     repl_help_text),

    # SQL LIKE 模式
    (r'.*\.py$',
     r'(LIKE\s*["\']%?)javdb\d{3}(%?["\'])',
     repl_sql_like),
]


# ========== 工具函数 ==========

def find_config_files(root_dir):
    """扫描项目中所有配置文件（跳过 unittest 测试数据）"""
    files = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS
                       and not d.startswith('.')
                       and d != 'unittest']
        for f in filenames:
            ext = os.path.splitext(f)[1].lower()
            if ext in CONFIG_EXTENSIONS:
                files.append(os.path.join(dirpath, f))
    return sorted(files)


def scan_mirror_domains(files):
    """扫描所有引用的 javdbNNN.com 镜像域名"""
    domains = set()
    for fp in files:
        try:
            with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
                for m in MIRROR_DOMAIN_RE.finditer(f.read()):
                    domains.add(m.group(0))
        except Exception:
            pass
    return sorted(domains)


# ========== 展示 ==========

def show_config(files):
    """展示当前项目所有 javdb 域名配置"""
    print("=" * 60)
    print("JavDB 域名配置扫描")
    print("=" * 60)

    # 核心配置（config.py 中的 *_DOMAIN 声明）
    core_configs = []
    for fp in files:
        rel = os.path.relpath(fp, PROJECT_ROOT)
        with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        for line in content.split('\n'):
            if MIRROR_DOMAIN_RE.search(line) and not line.strip().startswith('#'):
                if any(k in line for k in ['_DIRECT_DOMAIN', '_ALTERNATE',
                                           "javdb:", "getattr"]):
                    core_configs.append((rel, line.strip()))

    print("\n--- 核心镜像域名配置 ---")
    for rel, line in core_configs:
        print("  {rel}".format(rel=rel))
        print("    {line}".format(line=line))

    # 所有引用的镜像域名
    domains = scan_mirror_domains(files)
    print("\n--- 所有引用的镜像域名（共 {n} 个）---".format(n=len(domains)))
    for d in domains:
        print("  {d}".format(d=d))

    # 其他文件中的硬编码引用
    print("\n--- 其他文件中的硬编码 javdbNNN 引用 ---")
    shown = set()
    for fp in files:
        rel = os.path.relpath(fp, PROJECT_ROOT)
        if rel in shown:
            continue
        try:
            with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            for i, line in enumerate(lines, 1):
                m = MIRROR_DOMAIN_RE.search(line)
                if m and '_DIRECT_DOMAIN' not in line and '_ALTERNATE' not in line \
                   and "javdb:" not in line and "getattr" not in line \
                   and not line.strip().startswith('#'):
                    print("  {rel}:{i}  {d}  ({line})".format(
                        rel=rel, i=i, d=m.group(0), line=line.strip()[:80]))
                    shown.add(rel)
                    break
        except Exception:
            pass

    print("\n提示：javdb.com 不会被替换（代理主域名）。")
    print("脚本: {script}".format(script=os.path.basename(__file__)))


def update_domain(files, new_domain, dry_run=True):
    """批量替换镜像域名"""
    new_domain_full = "javdb{n}.com".format(n=new_domain)
    updated = []

    for fp in files:
        rel = os.path.relpath(fp, PROJECT_ROOT)
        try:
            with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
                original = f.read()
        except Exception:
            continue

        content = original
        fname = os.path.basename(fp)

        # 按规则替换
        for file_pat, search_pat, repl_fn in REPLACE_RULES:
            if not re.match(file_pat, fname):
                continue
            content = re.sub(
                search_pat,
                lambda m, d=new_domain_full, fn=repl_fn: fn(m, d),
                content,
                flags=re.DOTALL,
            )

        # 通用兜底：替换剩余独立的 javdbNNN.com
        # 但 javdb.com（无数字后缀）不会被匹配
        content = re.sub(
            r'(?<![-\w"\'])(?:https?://)?javdb(\d{3})\.com(?!["\'\w])',
            new_domain_full,
            content,
        )

        if content != original:
            updated.append(rel)
            if dry_run:
                print("  [预览] {rel}".format(rel=rel))
            else:
                with open(fp, 'w', encoding='utf-8') as f:
                    f.write(content)
                print("  [已更新] {rel}".format(rel=rel))

    if dry_run:
        print("\n预览完成，共 {n} 个文件需要更新".format(n=len(updated)))
        print("确认后运行:")
        print("  python3 {script} --new-domain {d} --backup".format(
            script=sys.argv[0], d=new_domain))
    else:
        print("\n共更新 {n} 个文件".format(n=len(updated)))


def backup_configs(files):
    """备份所有配置文件"""
    backup_dir = os.path.join(
        PROJECT_ROOT,
        'domain_backup_{ts}'.format(
            ts=datetime.now().strftime("%Y%m%d_%H%M%S")),
    )
    os.makedirs(backup_dir, exist_ok=True)
    count = 0
    for fp in files:
        rel = os.path.relpath(fp, PROJECT_ROOT)
        bak_path = os.path.join(backup_dir, rel)
        os.makedirs(os.path.dirname(bak_path), exist_ok=True)
        try:
            shutil.copy2(fp, bak_path)
            count += 1
        except Exception as e:
            print("  备份失败 {rel}: {e}".format(rel=rel, e=e))
    print("备份 {n} 个文件到 {d}".format(n=count, d=backup_dir))
    return backup_dir


def main():
    parser = argparse.ArgumentParser(
        description="批量更新 JavDB 镜像域名配置",
        epilog="示例: python3 %(prog)s --new-domain 574 --backup",
    )
    parser.add_argument('--show', action='store_true',
                        help='显示当前所有域名配置')
    parser.add_argument('--new-domain', type=str, default='',
                        help='新域名后缀数字（如 574、575）')
    parser.add_argument('--backup', action='store_true',
                        help='更新前先备份配置文件')
    parser.add_argument('--force', action='store_true',
                        help='跳过预览直接执行')

    args = parser.parse_args()
    files = find_config_files(PROJECT_ROOT)
    print("扫描到 {n} 个配置文件\n".format(n=len(files)))

    if args.show or not args.new_domain:
        show_config(files)
        if not args.new_domain:
            return

    dry_run = not args.force
    print("\n{label}更新镜像域名到 javdb{n}.com...".format(
        label='预览: ' if dry_run else '', n=args.new_domain))

    if args.backup and not dry_run:
        backup_configs(files)

    update_domain(files, args.new_domain, dry_run=dry_run)

    if not dry_run and not args.backup:
        print("\n建议: 下次加 --backup 自动备份")


if __name__ == '__main__':
    main()
