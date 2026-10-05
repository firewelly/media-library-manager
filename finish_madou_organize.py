#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
收尾整理：把 /av 里剩余的中文系列片按「演员」归档
====================================================

匹配顺序:
  1. **数据集番号匹配**（带后缀容错：PMS008-1 / NHAV013-1 / MD0338 之类）
  2. **标题相似度匹配**（对无番号、仅推广标题的文件，如「全身涂满萤光颜料…」）
  3. **JavDB 反查**：按番号搜索作品页 → 取演员/标题/片商
  4. 仍未匹配 → 报告（多为日系 AV 或纯广告）

归档目标:
  <root>/<片商名>/<演员[,演员...]>/<原条目名>     片商名如「麻豆傳媒映畫」「蜜桃传媒」

用法:
    python3 finish_madou_organize.py            # 干跑
    python3 finish_madou_organize.py --apply    # 执行
"""

import os
import re
import sys
import json
import time
import random
import shutil
import argparse
import subprocess
import difflib
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE_DIR, "results", "madou")
INDEX_PATH = os.path.join(OUT_DIR, "series_index.json")
REPORT_PATH = os.path.join(OUT_DIR, "series_report.json")
OVERRIDE_PATH = os.path.join(OUT_DIR, "download_actress_overrides.json")
LOG_PATH = os.path.join(OUT_DIR, "finish_organize_log.json")
UA = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
}
BASE = "https://javdb580.com"
SKIP = {".DS_Store", "System Volume Information", "$RECYCLE.BIN", ".Trashes"}

# 片商名归一（用于目录名）
MAKER_ALIAS = {
    "麻豆傳媒映畫": "麻豆傳媒映畫", "麻豆传媒映画": "麻豆傳媒映畫", "麻豆传媒": "麻豆傳媒映畫",
    "蜜桃影像": "蜜桃影像", "蜜桃传媒": "蜜桃影像", "蜜桃傳媒": "蜜桃影像",
    "大象传媒": "大象傳媒", "大象傳媒": "大象傳媒",
    "性视界": "性视界", "性視界": "性视界",
    "兔子先生": "兔子先生", "爱神尤物": "爱神尤物", "愛神尤物": "爱神尤物",
}
CN_EXT = {".mp4", ".mkv", ".avi", ".wmv", ".ts", ".rmvb", ".mov", ".m4v", ".iso", ".jpg", ".png"}


def nz(s):
    return re.sub(r"[\s\-_·]", "", str(s or "")).upper()


def cn_grams(s):
    """中文/日文字符 2-gram 集合，用于标题相似度"""
    chars = re.findall(r"[\u4e00-\u9fff\u3040-\u30ff]", str(s or ""))
    return {chars[i] + chars[i + 1] for i in range(len(chars) - 1)}


def similarity(a, b):
    ga, gb = cn_grams(a), cn_grams(b)
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / len(ga | gb)


def load_dataset():
    idx = json.load(open(INDEX_PATH, encoding="utf-8"))
    report = {r["code"]: r for r in json.load(open(REPORT_PATH, encoding="utf-8"))}
    ov = {}
    if os.path.exists(OVERRIDE_PATH):
        ov = json.load(open(OVERRIDE_PATH, encoding="utf-8"))
    ds = {}
    for code, it in idx.items():
        r = report.get(code) or {}
        acts = (r.get("actresses") or []) or (ov.get(code) or {}).get("actresses") or []
        ds[nz(code)] = {"code": code, "title": it.get("title", ""), "actresses": acts,
                        "studio": r.get("studio", ""), "ocr": r.get("ocr", "")}
    return ds


CODE_RE = re.compile(r"([A-Za-z]{2,8})[-_ ]?0*(\d{2,5})(?:[-_ ]?(\d{1,2}|CD\d))?(?!\d)")


def guess_codes(name, ds):
    out = []
    for m in CODE_RE.finditer(name):
        c = nz(f"{m.group(1)}-{m.group(2)}")
        if c in ds and c not in out:
            out.append(c)
    return out


def fetch_work_by_code(code, sess):
    """JavDB 搜索番号 → 返回 {title, actresses, maker} 或 None"""
    try:
        time.sleep(random.uniform(0.3, 0.7))
        r = sess.get(f"{BASE}/search?q={code}&f=all", headers=UA, timeout=25)
        m = re.search(r'<a href="/v/([A-Za-z0-9]+)" class="box" title="([^"]*)"', r.text)
        if not m:
            return None
        href, title = m.group(1), m.group(2)
        time.sleep(random.uniform(0.3, 0.7))
        d = sess.get(f"{BASE}/v/{href}", headers=UA, timeout=25).text
        h2 = re.search(r"<h2[^>]*>(.*?)</h2>", d, re.S)
        page_title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h2.group(1))).strip() if h2 else title
        acts = [a[1] for a in re.findall(r'href="/actors/([A-Za-z0-9]+)"[^>]*>([^<]{1,20})<', d)
                if a[0] not in ("censored", "uncensored", "western")]
        mk = re.search(r'href="/makers/([^"]+)"[^>]*>([^<]+)<', d)
        return {"title": page_title, "actresses": acts[:6], "maker": (mk.group(2) if mk else "")}
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser(description="收尾整理下载文件")
    ap.add_argument("--src", default="/Volumes/BLACK/av")
    ap.add_argument("--root", default="/Volumes/BLACK/JAV")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--title-threshold", type=float, default=0.5)
    args = ap.parse_args()

    ds = load_dataset()
    print(f"数据集: {len(ds)} 部")
    items = [x for x in sorted(os.listdir(args.src)) if x not in SKIP and not x.startswith("._")]
    print(f"扫描 {len(items)} 项")

    sess = requests.Session()
    sess.cookies.set("over18", "1", domain="javdb580.com")

    plans, need_lookup, unmatched = [], [], []
    for name in items:
        codes = guess_codes(name, ds)
        if codes:
            meta = ds[codes[0]]
            plans.append({"item": name, "code": meta["code"], "actresses": meta["actresses"],
                          "maker": meta.get("studio") or "麻豆傳媒映畫", "how": "code"})
            continue
        # 标题相似度（对比数据集标题与 OCR）
        best, score = None, 0.0
        for k, meta in ds.items():
            s = max(similarity(name, meta["title"]), similarity(name, meta["ocr"]))
            if s > score:
                best, score = meta, s
        if best and score >= args.title_threshold:
            plans.append({"item": name, "code": best["code"], "actresses": best["actresses"],
                          "maker": best.get("studio") or "麻豆傳媒映畫", "how": f"title({score:.2f})"})
            continue
        # 需要 JavDB 反查：取名称里的首个番号样式 token
        tok = CODE_RE.search(name)
        if tok:
            need_lookup.append((name, f"{tok.group(1)}-{tok.group(2)}"))
        else:
            unmatched.append(name)

    print(f"\n① 数据集直接命中(番号): {sum(1 for p in plans if p['how']=='code')} | "
          f"(标题相似度): {sum(1 for p in plans if p['how'].startswith('title'))} | "
          f"待 JavDB 反查: {len(need_lookup)} | 无法匹配: {len(unmatched)}")

    if need_lookup:
        print("\n② JavDB 反查中…")
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futs = {pool.submit(fetch_work_by_code, code, sess): (name, code) for name, code in need_lookup}
            for fut in as_completed(futs):
                name, code = futs[fut]
                info = fut.result()
                if info and info.get("actresses"):
                    plans.append({"item": name, "code": code, "actresses": info["actresses"],
                                  "maker": MAKER_ALIAS.get(info.get("maker", ""), info.get("maker") or ""),
                                  "how": "javdb", "title": info.get("title", "")})
                else:
                    unmatched.append(name)

    print(f"\n归档方案 {len(plans)} 项:")
    for p in plans[:40]:
        folder = ",".join(p["actresses"]) if p["actresses"] else "#未知演员"
        maker = p.get("maker") or "麻豆傳媒映畫"
        print(f"   {p['item'][:48]:<50} → {maker}/{folder}/   [{p['how']}]")
    if len(plans) > 40:
        print(f"   …共 {len(plans)} 项")

    if unmatched:
        print(f"\n未归档 {len(unmatched)} 项（日系/广告/无信息）:")
        for u in unmatched[:20]:
            print(f"   {u[:70]}")

    if args.apply and plans:
        moved, failed = 0, []
        for p in plans:
            src = os.path.join(args.src, p["item"])
            if not os.path.exists(src):
                continue
            maker = p.get("maker") or "麻豆傳媒映畫"
            folder = ",".join(p["actresses"]) if p["actresses"] else "#未知演员"
            dest_dir = os.path.join(args.root, maker, folder)
            dst = os.path.join(dest_dir, p["item"])
            if os.path.exists(dst):
                continue
            try:
                os.makedirs(dest_dir, exist_ok=True)
                time.sleep(0.2)                      # 缓解 NTFS/Tuxera 新建目录竞态
                rc = subprocess.call(["mv", src, dst])
                if rc != 0:
                    failed.append(p["item"])
                else:
                    moved += 1
            except Exception:
                failed.append(p["item"])
        print(f"\n已移动 {moved} 项 | 失败 {len(failed)}: {failed[:5]}")
        json.dump(plans, open(LOG_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"日志: {LOG_PATH}")
    elif not args.apply:
        print("\n(干跑，未移动；加 --apply 执行)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
