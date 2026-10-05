#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
汇总「库外作品磁链」到一个文件（有码 + 无码）
================================================

把两组结果合并为**一个文件**，格式保持可直接粘贴下载：

    # 演员名
    magnet:?xt=...
    magnet:?xt=...

来源:
  - 有码侧: results/magnets/favorites_censored_v3.txt（collect_missing_magnets.py 产出）
  - 无码侧: results/magnets/uncensored_works_<日期>.txt（crawl_uncensored_works.py --magnets 产出）

输出:
  - 更新 results/magnets/javdb_missing_magnets_ALL_<日期>.txt（默认沿用既有的 ALL 文件路径）

用法:
    python3 build_all_magnets_file.py                 # 合并并写出
    python3 build_all_magnets_file.py --sec-headers   # 在无码段前加一行注释分隔
"""

import os
import re
import sys
import glob
import argparse
import collections

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MG = os.path.join(BASE_DIR, "results", "magnets")


def clean_name(name):
    """去掉名称后的括注（如「（無碼：库外 108 部 / 共 118）」）"""
    return re.sub(r"（[^）]*）\s*$", "", name).strip()


def parse(path, strip_unc=False):
    """解析「# 演员 + 链接」格式的文件

    仅行首为「# 空格 + 非空格」的才算演员标题；
    「#   注释」（# 后跟两个以上空格）视为注释行，忽略。
    """
    out, cur = collections.OrderedDict(), None
    if not os.path.exists(path):
        return out
    for line in open(path, encoding="utf-8"):
        s = line.rstrip("\n")
        m = re.match(r"^#\s([^#].*)$", s)          # 标题：# 后仅一个空格
        if m and not re.match(r"^#\s{2,}", s):
            cur = clean_name(m.group(1)) if strip_unc else m.group(1).strip()
            out.setdefault(cur, [])
        elif s.strip().startswith("magnet:") and cur:
            out[cur].append(s.strip())
    return out


def main():
    ap = argparse.ArgumentParser(description="汇总库外磁链到一个文件")
    ap.add_argument("--censored", default=os.path.join(MG, "favorites_censored_v3.txt"))
    ap.add_argument("--uncensored", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--sec-headers", action="store_true", help="无码段前加注释分隔行")
    args = ap.parse_args()

    if not args.uncensored:
        cands = sorted(glob.glob(os.path.join(MG, "uncensored_works_*.txt")))
        args.uncensored = cands[-1] if cands else ""
    if not args.out:
        # 沿用用户既有的 ALL 文件（存在则更新它）
        existing = sorted(glob.glob(os.path.join(MG, "javdb_missing_magnets_ALL_*.txt")))
        args.out = existing[-1] if existing else os.path.join(MG, "javdb_missing_magnets_ALL.txt")

    censored = parse(args.censored)
    uncensored = parse(args.uncensored, strip_unc=True)

    # 合并（同名演员：有码在前，无码在后；链接去重）
    merged = collections.OrderedDict()
    for name, links in censored.items():
        merged.setdefault(name, {"c": [], "u": []})["c"].extend(links)
    for name, links in uncensored.items():
        merged.setdefault(name, {"c": [], "u": []})["u"].extend(links)

    lines, stat = [], []
    for name, groups in merged.items():
        c_links = [l for l in dict.fromkeys(groups["c"])]
        u_links = [l for l in dict.fromkeys(groups["u"]) if l not in c_links]
        if not (c_links or u_links):
            continue
        lines.append(f"# {name}")
        lines.extend(c_links)
        if u_links:
            if args.sec_headers:
                lines.append(f"#   —— 以下为无码作品 ——")
            lines.extend(u_links)
        lines.append("")
        stat.append((name, len(c_links), len(u_links)))

    payload = "\n".join(lines).rstrip() + "\n"
    open(args.out, "w", encoding="utf-8").write(payload)

    total_c = sum(s[1] for s in stat)
    total_u = sum(s[2] for s in stat)
    print(f"已写出: {args.out}")
    print(f"演员 {len(stat)} 位 | 有码 {total_c} 条 + 无码 {total_u} 条 = {total_c + total_u} 条")
    print("\n条数 TOP 15:")
    for name, c, u in sorted(stat, key=lambda x: -(x[1] + x[2]))[:15]:
        print(f"   {name:<12} 有码 {c:>4} | 无码 {u:>4}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
