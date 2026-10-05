#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
只整理用户点名的几个未归档条目（不动 /av 里其它文件）
=======================================================

作用域：脚本内 ITEMS 列表（默认 6 条中文片）。
流程：番号 → 数据集演员 → 同名分集演员沿用 → 文件名里的演员名 → JavDB 反查（需校验番号一致）；
      垃圾（<50MB 视频 / 广告后缀文件）隔离到既有 _清理_广告与垃圾/；
      条目整体 mv 到 麻豆傳媒映畫/<演员|#未知演员>/。
安全：默认干跑；不删除任何东西；目标已存在则整体跳过；不动 µTorrent 残留文件。

用法:
    python3 organize_av_selected.py            # 干跑
    python3 organize_av_selected.py --apply    # 执行
"""

import os
import re
import sys
import json
import time
import shutil
import argparse
import subprocess
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE_DIR, "results", "madou")
INDEX_PATH = os.path.join(OUT_DIR, "series_index.json")
REPORT_PATH = os.path.join(OUT_DIR, "series_report.json")
DONE_PATH = os.path.join(OUT_DIR, "downloaded_codes.json")
OVERRIDE_PATH = os.path.join(OUT_DIR, "download_actress_overrides.json")

SRC = "/Volumes/BLACK/av"
CN_ROOT = "/Volumes/BLACK/JAV/麻豆傳媒映畫"
SERIES_DIRNAME = "麻豆傳媒映畫"
QUARANTINE_DIRNAME = "_清理_广告与垃圾"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
      "Accept-Language": "zh-CN,zh;q=0.9"}
BASE = "https://javdb580.com"

VIDEO_EXT = {".mp4", ".mkv", ".avi", ".wmv", ".ts", ".rmvb", ".mov", ".m4v", ".iso"}
# BT 社区广告/残留（保留封面 .jpg 与 .torrent，保留 ~uTorrentPartFile*）
JUNK_EXT = {".url", ".lnk", ".html", ".htm", ".txt", ".bat", ".exe", ".db", ".ini",
            ".js", ".apk", ".rar", ".gif"}
AD_MAX_MB = 50

# 用户点名要整理的条目（不扩展到其它文件）
ITEMS = [
    "NHAV013-1 麻豆传媒 内涵甜蜜女友 足球宝贝上门破处 无套操爽啦啦队长",
    "MD0338 肉棒教训继母与阿姨",
    "MDSR0005-3 少妇白洁[第三章] 风情万种的少妇",
    "PMC069 没忍住竟和同学下药迷奸亲嫂子",
    "⚫️2025新品，推特52万粉名气女神【苏畅】最新付费，全身涂满萤光颜料，在密室内激情造爱",
    "蜜桃传媒 PMS008-1 年轻的继母上集_钟婉冰.mp4",
]

# 文件名里没番号、但按标题可确定的（记录用，便于 HTML 标注已下载）
CODE_HINT = {
    "⚫️2025新品，推特52万粉名气女神【苏畅】最新付费，全身涂满萤光颜料，在密室内激情造爱":
        ("CUS-2574", "标题与数据集 CUS-2574「全身涂满萤光颜料…」高度重合，且文件名自带【苏畅】"),
}

# 数据集外的条目：JavDB 反查结论（反查时无码页尚未上登录墙，已留证）
KNOWN_LOOKUP = {
    "PMC069 没忍住竟和同学下药迷奸亲嫂子":
        ("PMC-069", "JavDB v/96nyKR 标题「没忍住竟和同学下药迷奸亲嫂子 / 淫荡体质 立即见效」与文件名一致；无码页无演员字段"),
}

STOPWORDS = {"上集", "下集", "无码", "無碼", "中文", "字幕", "合集", "完整版", "高清",
             "第一部", "第二部", "第三部", "第四部", "全集", "特别版", "番外"}

# 番号：PREFIX + 数字(+可选 -分集)
CODE_PARSE = re.compile(r"^([A-Za-z]{2,8})[-_ ]?0*(\d{1,6})(?:[-_ ]?(\d{1,2}))?$")
TOKEN_RE = re.compile(r"([A-Za-z]{2,8})[-_ ]?(\d{1,6})(?:[-_ ]?(\d{1,2}))?(?!\d)")


def canon(code):
    """'NHAV013-1' → ('NHAV-13-1', 'NHAV-13')；保留分集后缀，去前导零"""
    m = CODE_PARSE.match(str(code or "").strip())
    if not m:
        return "", ""
    prefix, num, part = m.group(1).upper(), str(int(m.group(2))), m.group(3)
    base = f"{prefix}-{num}"
    return (f"{base}-{part}" if part else base), base


def load_dataset():
    idx = json.load(open(INDEX_PATH, encoding="utf-8"))
    report = {r["code"]: r for r in json.load(open(REPORT_PATH, encoding="utf-8"))}
    ov = json.load(open(OVERRIDE_PATH, encoding="utf-8")) if os.path.exists(OVERRIDE_PATH) else {}
    by_full, by_base, actresses = {}, {}, set()
    for code, it in idx.items():
        r = report.get(code) or {}
        acts = (r.get("actresses") or []) or (ov.get(code) or {}).get("actresses") or []
        meta = {"code": code, "title": it.get("title", "") or r.get("title", ""),
                "actresses": acts, "ocr": r.get("ocr", "")}
        full, base = canon(code)
        if not full:
            continue
        by_full[full] = meta
        by_base.setdefault(base, []).append(meta)
        actresses.update(acts)
    return by_full, by_base, actresses


def guess_code(name, by_full, by_base):
    """返回 (meta, 说明)"""
    for m in TOKEN_RE.finditer(name):
        full, base = canon(m.group(0))
        if not full:
            continue
        if full in by_full:
            return by_full[full], f"数据集精确命中 {full}"
        if base in by_base:
            metas = by_base[base]
            with_act = [x for x in metas if x["actresses"]]
            return (with_act[0] if with_act else metas[0]), f"数据集同番号 {base}（{len(metas)} 个分集）"
    return None, ""


def actress_from_filename(name, known):
    for m in re.finditer(r"【([^】]{2,12})】", name):
        cand = m.group(1).strip()
        if cand in known or (2 <= len(cand) <= 4 and cand not in STOPWORDS):
            return cand, f"文件名【{cand}】"
    m = re.search(r"[_\-]([\u4e00-\u9fff]{2,4})(?:\.(?:mp4|mkv|avi|wmv|ts|mov|iso))?$", name)
    if m:
        cand = m.group(1)
        if cand in known or cand not in STOPWORDS:
            return cand, f"文件名结尾 _{cand}"
    return "", ""


def javdb_lookup(code):
    """按番号反查 JavDB：依次尝试多种番号写法；详情页番号必须与查询一致才采用"""
    prefix_num = canon(code)[1]                      # 如 PMC-69
    if not prefix_num:
        return {"error": "番号无法解析"}
    p, n = prefix_num.split("-")
    pat = re.compile(rf"{p}[-_ ]?0*{n}(?!\d)", re.I)
    queries = [str(code).strip(), f"{p}-{n.zfill(3)}", prefix_num]
    seen = set()
    queries = [q for q in queries if q and not (q in seen or seen.add(q))]
    try:
        s = requests.Session()
        s.cookies.set("over18", "1", domain="javdb580.com")
        mismatches = []
        for q in queries:
            time.sleep(0.5)
            r = s.get(f"{BASE}/search", params={"q": q, "f": "all"}, headers=UA, timeout=25)
            m = re.search(r'<a href="/v/([A-Za-z0-9]+)" class="box" title="([^"]*)"', r.text)
            if not m:
                continue
            href, s_title = m.group(1), m.group(2)
            time.sleep(0.5)
            d = s.get(f"{BASE}/v/{href}", headers=UA, timeout=25).text
            h2 = re.search(r"<h2[^>]*>(.*?)</h2>", d, re.S)
            title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h2.group(1))).strip() if h2 else s_title
            if not pat.search(d):
                mismatches.append(f"{q}→{href}")
                continue
            acts = [a[1].strip() for a in re.findall(r'href="/actors/([A-Za-z0-9]+)"[^>]*>([^<]{1,24})<', d)
                    if a[0] not in ("censored", "uncensored", "western")]
            return {"href": href, "title": title, "actresses": acts[:6], "query": q}
        return {"mismatch": True, "detail": "; ".join(mismatches) or "无搜索结果"}
    except Exception as e:
        return {"error": str(e)[:80]}


def junk_scan(item_path):
    out = []
    if os.path.isfile(item_path):
        ext = os.path.splitext(item_path)[1].lower()
        mb = os.path.getsize(item_path) / 1024 / 1024
        if (ext in VIDEO_EXT and mb < AD_MAX_MB) or ext in JUNK_EXT:
            out.append((item_path, f"{mb:.1f}MB"))
        return out
    for root, _dirs, files in os.walk(item_path):
        for fn in files:
            fp = os.path.join(root, fn)
            if fn.startswith("~uTorrentPartFile") or fn.startswith("._"):
                continue                                  # BT 状态文件不动
            ext = os.path.splitext(fn)[1].lower()
            try:
                mb = os.path.getsize(fp) / 1024 / 1024
            except Exception:
                continue
            if ext in VIDEO_EXT and mb < AD_MAX_MB:
                out.append((fp, f"{mb:.1f}MB 广告"))
            elif ext in JUNK_EXT:
                out.append((fp, f"垃圾({ext})"))
    return out


def main():
    ap = argparse.ArgumentParser(description="整理点名条目")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--src", default=SRC)
    ap.add_argument("--root", default=CN_ROOT)
    args = ap.parse_args()

    by_full, by_base, known = load_dataset()
    print(f"数据集: {len(by_full)} 个番号键 / 演员名 {len(known)} 个")
    quarantine = os.path.join(args.root, QUARANTINE_DIRNAME)
    done = json.load(open(DONE_PATH, encoding="utf-8")) if os.path.exists(DONE_PATH) else {}
    plan = []

    for name in ITEMS:
        src = os.path.join(args.src, name)
        if not os.path.exists(src):
            plan.append({"item": name, "status": "源不存在（可能已整理）", "target": ""})
            continue
        meta, how = guess_code(name, by_full, by_base)
        acts, act_src = [], ""
        if meta and meta["actresses"]:
            acts, act_src = meta["actresses"], "数据集演员"
        if not acts and meta:                                   # 同名分集有演员 → 沿用
            _f, base = canon(meta["code"])
            sibs = [x for x in by_base.get(base, []) if x["actresses"] and x["code"] != meta["code"]]
            if sibs:
                acts, act_src = sibs[0]["actresses"], f"同番号分集 {sibs[0]['code']} 沿用"
        if not acts:
            cand, ev = actress_from_filename(name, known)
            if cand:
                acts, act_src = [cand], ev
        jd, jd_note = None, ""
        if not meta and name in KNOWN_LOOKUP:          # 已离线留证的反查结论
            jd_note = KNOWN_LOOKUP[name][1]
        elif not meta:
            tok = TOKEN_RE.search(name)
            code_q = canon(tok.group(0))[0] if tok else ""
            if code_q:
                jd = javdb_lookup(code_q)
                if jd.get("mismatch"):
                    jd_note = f"JavDB 番号校验不通过（{jd.get('detail','')}）→ 不采用"
                    jd = None
                elif jd and jd.get("actresses"):
                    acts, act_src = jd["actresses"][:1], "JavDB 反查"
                elif jd and jd.get("error"):
                    jd_note = f"JavDB 反查失败: {jd['error']}"
        code_out = (meta or {}).get("code", "")
        hint_note = ""
        if not code_out and name in KNOWN_LOOKUP:
            code_out, hint_note = KNOWN_LOOKUP[name]
        if not code_out and name in CODE_HINT:
            code_out, hint_note = CODE_HINT[name]
        folder = ",".join(acts) if acts else "#未知演员"
        dst = os.path.join(args.root, folder, name)
        exists = os.path.exists(dst)
        plan.append({"item": name, "code": code_out,
                     "how": how or (jd_note or (f"JavDB {jd.get('href')}" if jd else "未命中")),
                     "hint": hint_note,
                     "title": (meta or {}).get("title") or (jd or {}).get("title", ""),
                     "actresses": acts, "actress_src": act_src,
                     "target": dst, "exists": exists,
                     "junk": [(os.path.basename(p), r) for p, r in junk_scan(src)] if not exists else []})

    for p in plan:
        print(f"\n● {p['item'][:62]}")
        if p.get("status"):
            print(f"   {p['status']}")
            continue
        print(f"   番号/来源 : {p['code'] or '（未识别）'}   {p['how']}")
        if p.get("hint"):
            print(f"   番号依据  : {p['hint']}")
        print(f"   标题      : {p.get('title','')[:56]}")
        print(f"   演员      : {p['actresses'] or '（无）'}   ← {p['actress_src'] or '无依据'}")
        print(f"   目标      : {p['target'].replace(args.root, SERIES_DIRNAME)}"
              f"{'   [目标已存在 → 整条跳过]' if p.get('exists') else ''}")
        if p["junk"]:
            print(f"   待隔离    : " + "; ".join(f"{n}({r})" for n, r in p["junk"][:6])
                  + (" …" if len(p["junk"]) > 6 else ""))

    if args.apply:
        moved = 0
        for p in plan:
            if p.get("status") or not p["target"] or p.get("exists"):
                continue
            src = os.path.join(args.src, p["item"])
            if not os.path.exists(src):
                continue
            for fp, _r in junk_scan(src):
                try:
                    os.makedirs(quarantine, exist_ok=True)
                    tgt = os.path.join(quarantine, os.path.basename(fp))
                    if os.path.exists(tgt):
                        tgt = os.path.join(quarantine, f"{int(time.time())}_{os.path.basename(fp)}")
                    shutil.move(fp, tgt)
                except Exception as e:
                    print(f"   [隔离失败] {os.path.basename(fp)}: {str(e)[:50]}")
            try:
                os.makedirs(os.path.dirname(p["target"]), exist_ok=True)
                time.sleep(0.3)
                rc = subprocess.call(["mv", src, p["target"]])
                if rc != 0:
                    print(f"   [移动失败] {p['item'][:50]} (mv rc={rc})")
                    continue
                moved += 1
                if p["code"]:
                    done[p["code"]] = {"item": p["item"], "actresses": p["actresses"]}
            except Exception as e:
                print(f"   [失败] {p['item'][:50]}: {str(e)[:60]}")
        json.dump(done, open(DONE_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"\n已移动 {moved} 项 → {args.root}")
        print(f"已下载清单更新: {DONE_PATH}（{len(done)} 部）")
        json.dump(plan, open(os.path.join(OUT_DIR, "organize_selected_log.json"), "w",
                             encoding="utf-8"), ensure_ascii=False, indent=1)
    else:
        print("\n(干跑，未移动、未隔离；加 --apply 执行)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
