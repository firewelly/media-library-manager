#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
麻豆庫：垃圾清理 + 文件名规范化
================================

规则（元数据取自 results/madou/ 里已爬取整理的数据集）:
  1. **垃圾判定**
     - 文件级：广告/残留后缀（.js .apk .chm .mhtml .gif .url .exe .rar .zip .dat .html .txt …）、
       小于 50MB 的视频（广告）、0 字节文件、非封面图片（截图/宣传图）
     - 目录级：整个子目录里没有任何"保留物"（≥50MB 视频或本条目封面）→ 整目录隔离
     - 种子：每个条目只保留根目录的 `.magent_*.torrent`，成堆的种子包一律隔离
  2. **命名规范化**（统一为 `<番号> <标题>`）
     - 条目文件夹：`<番号> <标题>`（番号与标题取自数据集）
     - 内部视频：`<番号> <标题>.<原扩展名>`
     - 封面图  ：`<番号> <标题>.<原扩展名>`
     - 种子    ：`<番号>.torrent`
  3. **演员文件夹不动**（只报告与文件名冲突的情况）
  4. 只移动/重命名，**不删除**；全部动作写入日志，可回溯

用法:
    python3 clean_rename_madou_library.py                  # 干跑
    python3 clean_rename_madou_library.py --apply          # 执行
    python3 clean_rename_madou_library.py --apply --root /Volumes/BLACK/麻豆傳媒映畫
"""

import os
import re
import sys
import json
import time
import shutil
import argparse
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE_DIR, "results", "madou")
REPORT_PATH = os.path.join(OUT_DIR, "series_report.json")
LLM_PATH = os.path.join(OUT_DIR, "llm_meta.json")
DONE_PATH = os.path.join(OUT_DIR, "downloaded_codes.json")
LOG_PATH = os.path.join(OUT_DIR, "library_clean_rename_log.json")

DEFAULT_ROOT = "/Volumes/BLACK/麻豆傳媒映畫"
QUARANTINE_DIRNAME = "_清理_广告与垃圾"

VIDEO_EXT = {".mp4", ".mkv", ".avi", ".wmv", ".ts", ".rmvb", ".mov", ".m4v", ".iso"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
JUNK_EXT = {".js", ".apk", ".chm", ".mhtml", ".gif", ".url", ".lnk", ".exe", ".rar",
            ".zip", ".dat", ".html", ".htm", ".txt", ".ini", ".db", ".bat", ".swf"}
AD_MAX_MB = 50
KEEP_TORRENT_MAX = 1          # 每个条目最多保留几个种子（其余视为种子包垃圾）

# 文件名里没有番号的条目 → 按标题/文件名证据补
CODE_HINT = {
    "⚫️2025新品，推特52万粉名气女神【苏畅】最新付费，全身涂满萤光颜料，在密室内激情造爱": "CUS-2574",
}
# 数据集外（JavDB 無碼侧，无演员无标题）但番号确定 → 仅规范化名字，不改标题
CODE_ONLY = {"PMC069 没忍住竟和同学下药迷奸亲嫂子": "PMC069"}

# 合集条目：一个文件夹里装多部作品
_PACK_SPEC = {
    "new_name": "PM091-PMS010 蜜桃影像传媒合集（6部）",
    "codes": ["PM091", "PM092", "PM093", "PM096", "PMS010-1", "PMS010-2"],
}
PACKS = {
    "精品国产AV【蜜桃影像传媒】合集【PM091—PMS010】高清1080原版【6部】合集【4.66GB】": _PACK_SPEC,
    "PM091-PMS010 蜜桃影像传媒合集（5部）": _PACK_SPEC,      # 已改过一次名
    "PM091-PMS010 蜜桃影像传媒合集（6部）": _PACK_SPEC,
}

CODE_PARSE = re.compile(r"^([A-Za-z]{2,8})[-_ ]?0*(\d{1,6})(?:[-_ ]?(\d{1,2}))?$")
TOKEN_RE = re.compile(r"([A-Za-z]{2,8})[-_ ]?(\d{1,6})(?:[-_ ]?(\d{1,2}))?(?!\d)")


def canon(code):
    m = CODE_PARSE.match(str(code or "").strip())
    if not m:
        return "", ""
    prefix, num, part = m.group(1).upper(), str(int(m.group(2))), m.group(3)
    base = f"{prefix}-{num}"
    return (f"{base}-{part}" if part else base), base


def safe_name(s, limit=95):
    """NTFS/macOS 安全文件名"""
    s = str(s or "")
    s = re.sub(r"[\r\n\t]+", " ", s)
    s = re.sub(r"\s*[/／]\s*", " ", s)      # 标题内的 “ / ” 分隔 → 空格
    s = s.replace("/", "、").replace("\\", "、").replace(":", "：")
    s = re.sub(r'[<>"|?*]', "_", s)
    s = re.sub(r"\s{2,}", " ", s).strip()
    s = s.rstrip(" .·-—")
    if len(s) > limit:
        s = s[:limit].rstrip(" .·-—")
    return s


STUDIO_PREFIX = ["麻豆傳媒映畫", "麻豆传媒映画", "麻豆傳媒", "麻豆传媒", "大象傳媒", "大象传媒",
                 "蜜桃影像傳媒", "蜜桃影像传媒", "蜜桃傳媒", "蜜桃传媒", "抖阴传媒", "抖陰傳媒",
                 "三只狼", "絕對領域", "绝对领域", "麻豆", "蜜桃"]
AD_PREFIX_RE = [
    re.compile(r"^\s*[A-Za-z0-9._-]{2,40}\.(?:com|net|cc|top|xyz|org|me|app|tv|vip)[@\s]*", re.I),
    re.compile(r"^\s*(?:第?[一1]會所新片|第一会所新片|SIS001|2048|1024)@?[A-Za-z0-9]*@?"),
    re.compile(r"^\s*\[[^\]]{1,24}\]\s*"),
    re.compile(r"^\s*\d{4}\s*年\s*\d{1,2}\s*月[^ ]{0,24}\s*"),
    re.compile(r"^\s*精品国产AV"),
    re.compile(r"^\s*avman\.app_", re.I),
]


def clean_title(t):
    t = str(t or "").strip()
    for pre in STUDIO_PREFIX:
        if t.startswith(pre):
            t = t[len(pre):].strip(" 　-—・·:：")
            break
    return re.sub(r"\s{2,}", " ", t).strip()


def strip_ad_prefix(name):
    n = str(name or "")
    for rx in AD_PREFIX_RE:
        n = rx.sub("", n)
    return re.sub(r"\s{2,}", " ", n).strip(" 　-—・·_")


def tidy_from_filename(fn, code):
    """从带广告装饰的原文件名里取标题：优先最长的【…】块，其次去掉装饰后的正文"""
    stem = os.path.splitext(os.path.basename(fn))[0]
    blocks = [b for b in re.findall(r"【([^】]{4,})】", stem)
              if not re.search(r"传媒|傳媒|影像|麻豆|蜜桃|大象|抖阴|抖陰|三只狼|絕對領域|绝对领域|1080|720|原版|首发", b)]
    if code:
        ck = re.sub(r"[-_\s]", "", code).upper()
        blocks = [b for b in blocks if ck not in re.sub(r"[-_\s]", "", b).upper()]
    if blocks:
        t = max(blocks, key=len)
    else:
        t = re.sub(r"【[^】]*】", " ", stem)
        t = re.sub(r"(?:高清|超清)?\s*(?:1080|720)[Pp]?|原版|首发|无水印", " ", t)
    t = t.replace("・", " ").replace("　", " ")
    t = re.sub(r"^[\s\-_，,、]+|[\s\-_，,、]+$", "", t)
    return re.sub(r"\s{2,}", " ", t).strip()


def load_dataset():
    report = {r["code"]: r for r in json.load(open(REPORT_PATH, encoding="utf-8"))}
    llm = json.load(open(LLM_PATH, encoding="utf-8")) if os.path.exists(LLM_PATH) else {}
    by_full, by_base = {}, {}
    for code, r in report.items():
        meta = {"code": code, "title": (r.get("title") or "").strip(),
                "actresses": r.get("actresses") or []}
        if not meta["title"]:
            meta["title"] = ((llm.get(code) or {}).get("title") or "").strip()
        full, base = canon(code)
        if not full:
            continue
        by_full[full] = meta
        by_base.setdefault(base, []).append(meta)
    return by_full, by_base


def find_code(name, by_full, by_base):
    for m in TOKEN_RE.finditer(name):
        full, base = canon(m.group(0))
        if not full:
            continue
        if full in by_full:
            return by_full[full], f"番号精确 {full}"
        if base in by_base:
            metas = by_base[base]
            with_act = [x for x in metas if x["actresses"]]
            return (with_act[0] if with_act else metas[0]), f"番号基号 {base}"
    if name in CODE_HINT:
        full, _b = canon(CODE_HINT[name])
        if full in by_full:
            return by_full[full], f"标题证据 → {full}"
    return None, ""


AD_IMG_HINT = ("http", ".com", ".top", ".cc", ".net", ".xyz", "91", "狼友", "永久地址",
               "发布", "發布", "扫码", "掃碼", "社区", "社區", "論壇", "论坛", "成人", "直播",
               "约炮", "約炮", "外围", "外圍", "hgame", "telegram", "qq", "二维码", "教程")


def classify(item_path, meta_code, by_full, codes=None):
    """把条目里的文件分成 保留 / 垃圾。返回 (keep_files, junk_files, junk_dirs, flags)"""
    keep, junk, junk_dirs, flags = [], [], [], []
    code_key = re.sub(r"[-_\s]", "", meta_code).upper() if meta_code else ""

    # 1) 收集所有文件
    all_files = []
    for r, _d, fs in os.walk(item_path):
        for f in fs:
            all_files.append(os.path.join(r, f))

    def is_video(p):
        return os.path.splitext(p)[1].lower() in VIDEO_EXT

    def is_bt_state(p):
        return os.path.basename(p).startswith("~uTorrentPartFile")   # 仅 BT 状态文件保留；._* 属 macOS 残留，按垃圾处理

    def mb(p):
        try:
            return os.path.getsize(p) / 1024 / 1024
        except Exception:
            return 0.0

    # 2) 先挑保留物：≥50MB 视频 / 封面 / 主种子
    all_vids = [p for p in all_files if is_video(p)]
    main_size = max([mb(p) for p in all_vids], default=0)
    videos = [p for p in all_vids
              if mb(p) >= AD_MAX_MB and not (main_size and mb(p) < 0.4 * main_size and mb(p) < 200)]
    # 封面：根目录下文件名含番号的图片；否则根目录最大的图片
    root_files = [p for p in all_files if os.path.dirname(p) == item_path]
    code_keys = {canon(c)[0] for c in (codes or ([meta_code] if meta_code else [])) if c}
    code_keys.discard("")

    def file_codes(fn):
        return {canon(m.group(0))[0] for m in TOKEN_RE.finditer(fn)} - {""}

    covers = [p for p in root_files if os.path.splitext(p)[1].lower() in IMAGE_EXT
              and (file_codes(os.path.basename(p)) & code_keys)]
    covers = [p for p in covers if mb(p) >= 0.005]       # 只丢掉空/损坏图（真封面可小到 ~45KB）
    # 种子：根目录 .magent_*.torrent，否则根目录最小的 torrent
    tor = [p for p in root_files if p.lower().endswith(".torrent")]
    magents = [p for p in tor if os.path.basename(p).startswith(".magent_")]
    torrents_keep = magents[:KEEP_TORRENT_MAX] or (sorted(tor, key=mb)[:1] if tor else [])

    bt_state = [p for p in all_files if is_bt_state(p)]
    keep_set = set(videos) | set(covers) | set(torrents_keep) | set(bt_state)

    # 3) 目录级：整目录里没有任何保留物 → 整目录垃圾
    dirs = []
    for r, ds, _fs in os.walk(item_path):
        for d in ds:
            dirs.append(os.path.join(r, d))
    dirs.sort(key=lambda p: -p.count(os.sep))          # 深的先判
    junk_dir_set = set()
    for d in dirs:
        inside = [p for p in all_files if p.startswith(d + os.sep)]
        if not inside:
            junk_dirs.append(d)
            junk_dir_set.add(d)
            continue
        if any(p in keep_set for p in inside):
            continue
        if any(any(p.startswith(jd + os.sep) for jd in junk_dir_set) for p in inside):
            continue                                    # 父目录已被判垃圾
        junk_dirs.append(d)
        junk_dir_set.add(d)

    # 4) 文件级
    for p in all_files:
        if any(p.startswith(d + os.sep) for d in junk_dir_set):
            continue                                    # 随目录一起走
        if p in keep_set:
            keep.append(p)
            continue
        ext = os.path.splitext(p)[1].lower()
        size = mb(p)
        if ext in VIDEO_EXT:
            if size == 0:
                junk.append((p, "空视频文件"))
            elif size < AD_MAX_MB:
                junk.append((p, f"广告视频 {size:.1f}MB"))
            else:
                junk.append((p, f"广告视频 {size:.1f}MB（远小于主视频 {main_size:.0f}MB）"))
        elif ext in JUNK_EXT:
            junk.append((p, f"垃圾({ext})"))
        elif size == 0:
            junk.append((p, "0 字节"))
        elif ext in IMAGE_EXT:
            junk.append((p, "截图/宣传图"))
        elif ext == ".torrent":
            junk.append((p, "种子包"))
        else:
            junk.append((p, f"未识别({ext or '无扩展名'})"))

    if not videos:
        flags.append("无有效视频（≥50MB）")
    return keep, junk, junk_dirs, flags


def main():
    ap = argparse.ArgumentParser(description="麻豆库清理与重命名")
    ap.add_argument("--root", default=DEFAULT_ROOT)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    root = args.root
    if not os.path.isdir(root):
        print(f"[错误] 目录不存在: {root}")
        return 1
    by_full, by_base = load_dataset()
    print(f"数据集: {len(by_full)} 个番号")
    quarantine = os.path.join(root, QUARANTINE_DIRNAME)
    log = {"root": root, "items": []}

    acts = [a for a in sorted(os.listdir(root))
            if os.path.isdir(os.path.join(root, a)) and a != QUARANTINE_DIRNAME]
    total_junk = total_keep = 0
    for act in acts:
        ap_ = os.path.join(root, act)
        for item in sorted(os.listdir(ap_)):
            ip = os.path.join(ap_, item)
            if not os.path.isdir(ip):
                continue
            meta, how = find_code(item, by_full, by_base)
            if not meta and item in CODE_ONLY:
                meta, how = {"code": CODE_ONLY[item], "title": "", "actresses": []}, "番号确定（JavDB 無碼侧）"
            pack = PACKS.get(item)
            new_folder = ""
            if pack:
                new_folder = safe_name(pack["new_name"])
            elif meta:
                title = clean_title(meta["title"])
                if not title:
                    title = strip_ad_prefix(item)
                    title = re.sub(r"^" + re.escape(meta["code"]) + r"[-_ ]*", "", title, flags=re.I)
                new_folder = safe_name(f"{meta['code']} {title}".strip())
            codes = (pack or {}).get("codes") or ([(meta or {}).get("code", "")] if meta else [])
            keep, junk, junk_dirs, flags = classify(ip, (meta or {}).get("code", ""), by_full, codes)
            if not keep and not junk and not junk_dirs:
                continue
            total_junk += len(junk) + len(junk_dirs)
            total_keep += len(keep)
            print(f"\n● {act}/{item[:56]}")
            print(f"   番号: {(meta or {}).get('code','（未识别）')}  {how or ''}")
            if new_folder and new_folder != item:
                print(f"   改名: {item[:60]}  →  {new_folder}")
            if flags:
                print(f"   ⚠ " + "；".join(flags))
            print(f"   保留 {len(keep)} 项: " + ", ".join(
                f"{os.path.relpath(p, ip)}({os.path.getsize(p)/1e6:.0f}MB)" for p in keep[:5]))
            if junk:
                print(f"   隔离文件 {len(junk)} 个（示例）: " + "; ".join(
                    f"{os.path.relpath(p, ip)}({r})" for p, r in junk[:4]))
            if junk_dirs:
                print(f"   隔离整目录 {len(junk_dirs)} 个: " + "; ".join(
                    os.path.relpath(d, ip)[:46] for d in junk_dirs[:4]))
            log["items"].append({
                "actress": act, "item": item, "code": (meta or {}).get("code", ""),
                "new_folder": new_folder, "flags": flags,
                "keep": [os.path.relpath(p, ip) for p in keep],
                "junk_files": [(os.path.relpath(p, ip), r) for p, r in junk],
                "junk_dirs": [os.path.relpath(d, ip) for d in junk_dirs]})

    print(f"\n合计: 保留 {total_keep} 个文件；隔离 {total_junk} 项（文件+目录）")
    if not args.apply:
        print("(干跑，未改动；加 --apply 执行)")
        return 0

    # ---------- 执行 ----------
    print("\n执行中…")
    for rec in log["items"]:
        ip = os.path.join(root, rec["actress"], rec["item"])
        if not os.path.isdir(ip):
            rec["status"] = "源不存在"
            continue
        qdir = os.path.join(quarantine, safe_name(rec["item"])[:60])
        moved = 0
        for rel in rec["junk_dirs"]:
            src = os.path.join(ip, rel)
            if not os.path.exists(src):
                continue
            os.makedirs(qdir, exist_ok=True)
            try:
                shutil.move(src, os.path.join(qdir, safe_name(os.path.basename(src))[:80]))
                moved += 1
            except Exception as e:
                rec.setdefault("errors", []).append(f"dir {rel}: {str(e)[:60]}")
        for rel, _r in rec["junk_files"]:
            src = os.path.join(ip, rel)
            if not os.path.exists(src):
                continue
            try:
                dst = os.path.join(qdir, safe_name(os.path.basename(src))[:80])
                if os.path.exists(dst):
                    dst = os.path.join(qdir, f"{int(time.time()*1000)%100000}_{safe_name(os.path.basename(src))[:70]}")
                os.makedirs(qdir, exist_ok=True)
                shutil.move(src, dst)
                moved += 1
            except Exception as e:
                rec.setdefault("errors", []).append(f"file {rel}: {str(e)[:60]}")
        rec["junk_moved"] = moved
        # 视频上提：条目根无视频，且某子目录只剩视频
        if rec["keep"]:
            root_vids = [r for r in rec["keep"] if os.path.dirname(r) == "" and
                         os.path.splitext(r)[1].lower() in VIDEO_EXT]
            if not root_vids:
                subdirs = {os.path.dirname(r) for r in rec["keep"]
                           if os.path.dirname(r) and os.path.splitext(r)[1].lower() in VIDEO_EXT}
                for sd in subdirs:
                    rest = [r for r in rec["keep"] if os.path.dirname(r) == sd
                            and os.path.splitext(r)[1].lower() not in VIDEO_EXT]
                    if rest:
                        continue
                    left = []
                    for r2, _d2, f2 in os.walk(os.path.join(ip, sd)):
                        left += [f for f in f2]
                    if len(left) > len([r for r in rec["keep"] if os.path.dirname(r) == sd]):
                        continue
                    for r in [r for r in rec["keep"] if os.path.dirname(r) == sd]:
                        src = os.path.join(ip, r)
                        dst = os.path.join(ip, os.path.basename(r))
                        if os.path.exists(src) and not os.path.exists(dst):
                            try:
                                shutil.move(src, dst)
                                rec["keep"][rec["keep"].index(r)] = os.path.basename(r)
                                rec.setdefault("moved_up", []).append(r)
                            except Exception as e:
                                rec.setdefault("errors", []).append(f"moveup {r}: {str(e)[:50]}")
        # 数据集封面兜底
        if rec["code"] and rec["new_folder"] and not any(
                os.path.splitext(r)[1].lower() in IMAGE_EXT for r in rec["keep"]):
            cov = os.path.join(OUT_DIR, "covers", f"{rec['code']}.jpg")
            if os.path.exists(cov):
                tgt = os.path.join(ip, safe_name(rec["new_folder"]) + ".jpg")
                if not os.path.exists(tgt):
                    try:
                        shutil.copy2(cov, tgt)
                        rec["keep"].append(os.path.basename(tgt))
                        rec.setdefault("cover_added", []).append(os.path.basename(tgt))
                    except Exception as e:
                        rec.setdefault("errors", []).append(f"cover: {str(e)[:50]}")
        # 重命名内部文件（逐文件按自身番号 → <番号> <标题>）
        newf = rec["new_folder"]
        item_base = newf or safe_name(strip_ad_prefix(rec["item"]))
        used = set()
        for rel in rec["keep"]:
            p = os.path.join(ip, rel)
            if not os.path.exists(p):
                continue
            ext = os.path.splitext(p)[1].lower()
            if ext not in VIDEO_EXT and ext not in IMAGE_EXT and ext != ".torrent":
                continue                                   # BT 状态等文件不改名
            m2, _h2 = find_code(os.path.basename(p), by_full, by_base)
            if m2 and m2.get("title"):
                stem = safe_name(f"{m2['code']} {clean_title(m2['title'])}")
            elif ext == ".torrent" and rec["code"]:
                stem = safe_name(rec["code"])
            else:
                stem = tidy_from_filename(os.path.basename(p), rec["code"]) or item_base
            if ext == ".torrent":
                tgt_name = safe_name(f"{rec['code'] or stem}.torrent")
            else:
                tgt_name = safe_name(f"{stem}{ext}")
            tgt = os.path.join(os.path.dirname(p), tgt_name)
            if os.path.abspath(tgt) == os.path.abspath(p):
                used.add(tgt_name)
                continue
            n = 2
            while os.path.exists(tgt) or tgt_name in used:
                tgt_name = safe_name(f"{stem}-{n}{ext}")
                tgt = os.path.join(os.path.dirname(p), tgt_name)
                n += 1
            try:
                os.rename(p, tgt)
                used.add(tgt_name)
                rec.setdefault("renamed", []).append([rel, os.path.relpath(tgt, ip)])
            except Exception as e:
                rec.setdefault("errors", []).append(f"rename {rel}: {str(e)[:60]}")
        # 重命名条目文件夹
        if newf and newf != rec["item"]:
            tgt = os.path.join(root, rec["actress"], newf)
            if os.path.exists(tgt):
                rec["status"] = f"目标已存在，未改名: {newf}"
            else:
                try:
                    time.sleep(0.2)
                    rc = subprocess.call(["mv", ip, tgt])
                    rec["status"] = "已改名" if rc == 0 else f"改名失败 rc={rc}"
                except Exception as e:
                    rec["status"] = f"改名异常 {str(e)[:50]}"

    json.dump(log, open(LOG_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"完成。日志: {LOG_PATH}")
    print(f"隔离区: {quarantine}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
