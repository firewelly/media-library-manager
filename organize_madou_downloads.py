#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 BLACK/av 里下载好的「麻豆傳媒映畫」系列片整理入库
======================================================

流程:
  1. 用已采集的 1970 部数据集（results/madou/series_index.json）建立番号索引；
  2. 扫描下载目录（默认 /Volumes/BLACK/av）里的每个条目，尝试从名称中识别番号；
  3. 命中数据集 → 取该片的演员，规划移动到
       <目标根>/麻豆傳媒映畫/<演员（多人用逗号连接）>/<原条目名>
  4. 输出方案（--dry-run 默认）与已下载清单（供 HTML 标注）

用法:
    python3 organize_madou_downloads.py                  # 干跑，列方案
    python3 organize_madou_downloads.py --apply          # 实际移动
    python3 organize_madou_downloads.py --src /Volumes/BLACK/av --root /Volumes/BLACK/JAV
"""

import os
import re
import sys
import json
import shutil
import argparse
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE_DIR, "results", "madou")
INDEX_PATH = os.path.join(OUT_DIR, "series_index.json")
REPORT_PATH = os.path.join(OUT_DIR, "series_report.json")
DONE_PATH = os.path.join(OUT_DIR, "downloaded_codes.json")
OVERRIDE_PATH = os.path.join(OUT_DIR, "download_actress_overrides.json")
SERIES_DIRNAME = "麻豆傳媒映畫"
QUARANTINE_DIRNAME = "_清理_广告与垃圾"
VIDEO_EXT = {".mp4", ".mkv", ".avi", ".wmv", ".ts", ".rmvb", ".mov", ".m4v", ".iso"}
JUNK_EXT = {".url", ".lnk", ".html", ".htm", ".txt", ".bat", ".exe", ".db", ".ini"}
AD_MAX_MB = 50          # 视频 <50MB 视为广告


def scan_and_clean(item_path, quarantine_root, apply=False):
    """清理单个条目内的垃圾：返回 (隔离列表, 其它剧集文件列表, 报告)

    · 视频 < AD_MAX_MB → 判为广告，隔离
    · .url/.lnk/.html/.txt 等 → 隔离
    · 非本番号的视频文件 → 仅报告（可能是别的剧集）
    """
    quarantined, others = [], []
    if not os.path.isdir(item_path):
        # 单文件：也检查大小
        try:
            if os.path.splitext(item_path)[1].lower() in VIDEO_EXT:
                mb = os.path.getsize(item_path) / 1024 / 1024
                if mb < AD_MAX_MB:
                    if apply:
                        os.makedirs(quarantine_root, exist_ok=True)
                        shutil.move(item_path, os.path.join(quarantine_root, os.path.basename(item_path)))
                    quarantined.append((os.path.basename(item_path), f"{mb:.1f}MB"))
        except Exception:
            pass
        return quarantined, others
    for root, dirs, files in os.walk(item_path):
        for fn in files:
            fp = os.path.join(root, fn)
            ext = os.path.splitext(fn)[1].lower()
            try:
                mb = os.path.getsize(fp) / 1024 / 1024
            except Exception:
                continue
            if ext in VIDEO_EXT and mb < AD_MAX_MB:
                if apply:
                    os.makedirs(quarantine_root, exist_ok=True)
                    try:
                        shutil.move(fp, os.path.join(quarantine_root, fn))
                    except Exception:
                        pass
                quarantined.append((os.path.relpath(fp, item_path), f"{mb:.1f}MB"))
            elif ext in JUNK_EXT:
                if apply:
                    os.makedirs(quarantine_root, exist_ok=True)
                    try:
                        shutil.move(fp, os.path.join(quarantine_root, fn))
                    except Exception:
                        pass
                quarantined.append((os.path.relpath(fp, item_path), "垃圾文件"))
    return quarantined, others
SKIP_NAMES = {".DS_Store", "System Volume Information", "$RECYCLE.BIN", ".Trashes", "._.DS_Store"}


def norm_code(c):
    """归一：去分隔/前导零 → PREFIX-N"""
    c = re.sub(r"[-_\s]", "", str(c or "").upper())
    m = re.match(r"^([A-Z]+)0*(\d+)$", c)
    return f"{m.group(1)}-{m.group(2)}" if m else c


def build_code_index():
    idx = json.load(open(INDEX_PATH, encoding="utf-8"))
    report = {r["code"]: r for r in json.load(open(REPORT_PATH, encoding="utf-8"))}
    code2meta = {}
    for code in idx:
        code2meta[norm_code(code)] = {
            "code": code,
            "title": (report.get(code) or {}).get("title", idx[code].get("title", "")),
            "actresses": (report.get(code) or {}).get("actresses", []) or [],
        }
    return code2meta


TOKEN_RE = re.compile(r"([A-Za-z]{2,7})[-_ ]?0*(\d{2,5})(?!\d)")


def guess_codes(name, code2meta):
    """从条目名里找出属于数据集的番号（可能有多个候选）"""
    hits = []
    for m in TOKEN_RE.finditer(name):
        cand = norm_code(f"{m.group(1)}-{m.group(2)}")
        if cand in code2meta:
            hits.append(cand)
    # 去重保序
    out = []
    for c in hits:
        if c not in out:
            out.append(c)
    return out


def main():
    ap = argparse.ArgumentParser(description="整理麻豆系列下载文件")
    ap.add_argument("--src", default="/Volumes/BLACK/av")
    ap.add_argument("--root", default="/Volumes/BLACK/JAV", help="已整理库根目录（其下建 麻豆傳媒映畫）")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    code2meta = build_code_index()
    # 用「下载文件名」补出的演员覆盖数据集缺失值
    if os.path.exists(OVERRIDE_PATH):
        ov = json.load(open(OVERRIDE_PATH, encoding="utf-8"))
        for c, v in ov.items():
            k = norm_code(c)
            if k in code2meta and (v.get("actresses") or []):
                code2meta[k]["actresses"] = v["actresses"]
    print(f"数据集番号索引: {len(code2meta)} 个（含文件名补全）")

    if not os.path.isdir(args.src):
        print(f"[错误] 源目录不存在: {args.src}")
        return 1
    items = [x for x in sorted(os.listdir(args.src)) if x not in SKIP_NAMES and not x.startswith("._")]
    matched, unmatched = [], []
    for name in items:
        codes = guess_codes(name, code2meta)
        if codes:
            meta = code2meta[codes[0]]
            matched.append({"item": name, "code": meta["code"],
                            "actresses": meta["actresses"], "title": meta["title"]})
        else:
            unmatched.append(name)

    print(f"\n扫描 {len(items)} 项 | 命中麻豆系列 {len(matched)} 项 | 未命中 {len(unmatched)} 项")
    plan, done_codes = [], {}
    for m in matched:
        acts = m["actresses"]
        folder = ",".join(acts) if acts else "#未知演员"
        dest_dir = os.path.join(args.root, SERIES_DIRNAME, folder)
        plan.append({"src": os.path.join(args.src, m["item"]), "dst": os.path.join(dest_dir, m["item"]),
                     "code": m["code"], "actresses": acts})
        done_codes[m["code"]] = {"item": m["item"], "actresses": acts}

    # 清理扫描（干跑只统计）
    quarantine_root = os.path.join(args.root, SERIES_DIRNAME, QUARANTINE_DIRNAME) if args.apply is False else os.path.join(args.root, SERIES_DIRNAME, QUARANTINE_DIRNAME)
    clean_stat, other_files = [], []
    for p in plan:
        q, o = scan_and_clean(p["src"], quarantine_root, apply=False)
        if q:
            clean_stat.append((p["code"], q))
    total_q = sum(len(x[1]) for x in clean_stat)
    print(f"\n清理预检: {len(clean_stat)} 个条目含垃圾，共 {total_q} 个文件将隔离到 {QUARANTINE_DIRNAME}/")
    for code, q in clean_stat[:12]:
        print(f"   {code:<12} " + "; ".join(f"{n}({r})" for n, r in q[:4]) + (" …" if len(q) > 4 else ""))

    print("\n移动方案（前 25 条）:")
    for p in plan[:25]:
        folder = os.path.basename(os.path.dirname(p["dst"]))
        print(f"   {os.path.basename(p['src'])[:52]:<54} → {SERIES_DIRNAME}/{folder}/")
    if len(plan) > 25:
        print(f"   …共 {len(plan)} 条")

    print(f"\n未命中的 {len(unmatched)} 项（未列入移动）:")
    for u in unmatched[:15]:
        print(f"   {u[:70]}")
    if len(unmatched) > 15:
        print(f"   …共 {len(unmatched)} 项")

    if args.apply and plan:
        moved = 0
        for p in plan:
            if not os.path.exists(p["src"]):
                continue                      # 已移动过
            try:
                scan_and_clean(p["src"], quarantine_root, apply=True)
            except Exception:
                pass                          # 清理失败不影响移动
            try:
                os.makedirs(os.path.dirname(p["dst"]), exist_ok=True)
                if os.path.exists(p["dst"]):
                    print(f"   [跳过] 目标已存在: {p['dst'][:80]}")
                    continue
                # NTFS 卷上个别文件名含非法字节，shutil 会报 EINVAL；改用系统 mv
                rc = subprocess.call(["mv", p["src"], p["dst"]])
                if rc != 0:
                    shutil.move(p["src"], p["dst"])
                moved += 1
            except Exception as e:
                print(f"   [失败] {os.path.basename(p['src'])[:50]}: {str(e)[:70]}")
        print(f"\n已移动 {moved} 项 → {os.path.join(args.root, SERIES_DIRNAME)}")
        # 记录已下载清单（供 HTML 标注）
        prev = {}
        if os.path.exists(DONE_PATH):
            try:
                prev = json.load(open(DONE_PATH, encoding="utf-8"))
            except Exception:
                prev = {}
        prev.update(done_codes)
        json.dump(prev, open(DONE_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"已下载清单: {DONE_PATH}（{len(prev)} 部）")
    elif not args.apply:
        print("\n(干跑，未移动；加 --apply 执行)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
