#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从百度百科补全演员档案（生日 / 身高 / 三围 / 出道 / 简介 / 别名）
==================================================================

背景: av-wiki.net 未收录的演员（如長澤あずさ）以及部分只有部分字段的演员，
可尝试用百度百科补全。本脚本调用百度百科词条卡片 API 获取结构化档案：
    本名 / 外文名 / 别名 / 出生日期 / 身高 / 三围 / 血型 / 出生地 + 词条摘要

安全策略（重要）:
1. **只填空字段**，绝不覆盖库中已有数据。若库中已有值与百科值不一致，
   仅记录为「冲突」供人工判断（av-wiki 与百科对同一人常给出不同年份/尺寸的官方数据）。
2. **严格身份校验**，需同时满足:
   - 词条标题与搜索名一致，或 外文名/别名/本名 命中本地该演员的某个名称；
   - 且摘要显示其为成人影像/模特类词条（避免同名普通人）。
   繁简体差异通过 zhconv 归一后比较。

依赖: requests、zhconv（繁简转换）
用法:
    python3 enrich_profiles_baike.py              # 干跑
    python3 enrich_profiles_baike.py --apply      # 写库
"""

import os
import re
import sys
import time
import html
import random
import sqlite3
import argparse

import requests

try:
    from zhconv import convert as zh_convert
except Exception:  # 无 zhconv 时退化为不做繁简转换（匹配率下降）
    def zh_convert(s, *a):
        return s

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "media_library.db")
API = "https://baike.baidu.com/api/openapi/BaikeLemmaCardApi"
UA = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://baike.baidu.com/",
}
# 词条必须属于该类目，避免匹配到同名的普通人
ADULT_HINTS = ("AV", "av", "女優", "女优", "成人", "模特", "寫真", "写真", "性感", "影片")


def norm(s):
    """归一化名称：繁转简 + 去空格/标点/脚注数字"""
    if not s:
        return ""
    s = zh_convert(html.unescape(re.sub("<[^>]+>", "", str(s))), "zh-cn")
    s = re.sub(r"[\s·・,，.。、\-—_/()（）\[\]【】'\"\u3000]", "", s)
    return s


def clean_value(v):
    """清理百科字段值：去 HTML、去脚注数字"""
    if isinstance(v, list):
        v = v[0] if v else ""
    v = html.unescape(re.sub("<[^>]+>", "", str(v))).strip()
    v = re.sub(r"(?<=[日号型cm米歲岁])[\d]+", "", v)                    # "162 cm4" / "1993年8月16日4"
    v = re.sub(r"(?<=[\u4e00-\u9fff\u3040-\u30ff])[\d]+\s*(?=$|[、,，/])", "", v)  # "大槻佳奈1"
    v = re.sub(r"[\u200b\u200e\u200f]", "", v)
    return v.strip()


def alias_ok(a):
    """判断百科「别名」是否像个人名（过滤脚注残留与宣传语）"""
    a = a.strip()
    if not (2 <= len(a) <= 16):
        return False
    if re.search(r"\d", a):
        return False
    has_cjk = bool(re.search(r"[\u4e00-\u9fff\u3040-\u30ff]", a))
    has_latin = bool(re.search(r"[A-Za-z]", a))
    if has_latin and has_cjk:          # 如「人类最强Body」
        return False
    if has_latin and " " not in a:     # 单个拉丁词，非姓名写法
        return False
    return True


def trim_sentences(text, limit=480):
    """按句号截断，避免简介停在半句"""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    idx = max(cut.rfind("。"), cut.rfind("】"), cut.rfind("！"), cut.rfind("？"))
    return cut[:idx + 1] if idx > 60 else cut.rstrip() + "…"


def baike_lookup(name, session):
    """查询词条卡片，返回 {'key','abstract','card'} 或 None"""
    try:
        r = session.get(API, headers=UA, timeout=20, params={
            "scope": "103", "format": "json", "appid": "379020",
            "bk_key": name, "bk_length": "600"})
        d = r.json()
    except Exception:
        return None
    if not d.get("key"):
        return None
    card = {}
    for it in (d.get("card") or []):
        card[clean_value(it.get("name"))] = clean_value(it.get("value"))
    return {"key": d["key"], "abstract": clean_value(d.get("abstract") or ""), "card": card}


def parse_baike(info, tokens):
    """解析百科字段；返回 dict 或 None（身份校验不通过）"""
    card, abstract, key = info["card"], info["abstract"], info["key"]
    token_set = {norm(t) for t in tokens if t}

    # --- 身份校验 ---
    title_ok = norm(key) in token_set
    alias_fields = [card.get("外文名"), card.get("别名"), card.get("本名"), card.get("中文名")]
    alias_hit = any(norm(a) in token_set for a in alias_fields if a)
    adult_ok = any(h in abstract for h in ADULT_HINTS)
    if not ((title_ok or alias_hit) and adult_ok):
        return None

    out = {"key": key, "matched_by": ("title" if title_ok else "alias"),
           "birth_date": None, "height": None, "measurements": None,
           "debut_date": None, "description": None, "aliases": []}

    m = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", card.get("出生日期", ""))
    if m:
        out["birth_date"] = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.search(r"(\d{2,3})", card.get("身高", ""))
    if m and 120 <= int(m.group(1)) <= 210:
        out["height"] = m.group(1)
    m = re.search(r"(\d{2,3})\s*[/\-,，]\s*(\d{2,3})\s*[/\-,，]\s*(\d{2,3})", card.get("三围", ""))
    if m:
        out["measurements"] = f"B{m.group(1)}-W{m.group(2)}-H{m.group(3)}"
    md = re.search(r"(\d{4})\s*年\s*(\d{1,2})?\s*月?\s*(\d{1,2})?\s*日?\s*[^。]{0,24}?(?:正式)?出道", abstract)
    if md:
        y, mo, d = md.group(1), md.group(2), md.group(3)
        out["debut_date"] = f"{y}-{int(mo):02d}-{int(d):02d}" if mo and d else (f"{y}-{int(mo):02d}" if mo else y)
    if abstract and 10 <= len(abstract) <= 600:
        out["description"] = trim_sentences(abstract)
    for a in re.split(r"[、,，/]", card.get("别名") or ""):
        a = a.strip()
        if a and alias_ok(a) and norm(a) not in token_set:
            out["aliases"].append(a)
    return out


def search_names(row):
    """候选查询名：本地全部名称 + 其简体形式"""
    names = []
    for key in ("name", "name_common", "name_traditional"):
        v = (row[key] or "").strip()
        if v:
            names.append(v)
    for a in (row["aliases"] or "").split(","):
        a = a.strip()
        if a:
            names.append(a)
    out = []
    for n in names:
        for c in (n, zh_convert(n, "zh-cn")):
            if c and c not in out:
                out.append(c)
    return out


def main():
    ap = argparse.ArgumentParser(description="从百度百科补全演员档案")
    ap.add_argument("--db-path", default=DB_PATH)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--all", action="store_true",
                    help="对所有收藏演员查询（默认只查有缺失字段的）")
    args = ap.parse_args()

    conn = sqlite3.connect(args.db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, name, name_common, name_traditional, aliases, birth_date, debut_date, "
        "height, measurements, description FROM actors WHERE is_favorite=1 ORDER BY id"
    ).fetchall()
    if not args.all:
        rows = [r for r in rows if not (r["birth_date"] and r["height"] and r["measurements"]
                                        and r["debut_date"] and r["description"])]
    if args.limit:
        rows = rows[:args.limit]

    session = requests.Session()
    filled = {"birth_date": 0, "height": 0, "measurements": 0,
              "debut_date": 0, "description": 0, "aliases": 0}
    hits, misses, conflicts = [], [], []

    for row in rows:
        tokens = [t for t in [row["name"], row["name_common"], row["name_traditional"]]
                  + (row["aliases"] or "").split(",") if t and t.strip()]
        found = None
        for q in search_names(row):
            info = baike_lookup(q, session)
            time.sleep(random.uniform(0.5, 1.0))
            if not info:
                continue
            parsed = parse_baike(info, tokens)
            if parsed:
                found = parsed
                break
        if not found:
            misses.append((row["id"], row["name"]))
            print(f"[无词条] DB#{row['id']} {row['name']}")
            continue

        sets, vals, changed = [], [], []
        for field in ("birth_date", "height", "measurements", "debut_date", "description"):
            new = found.get(field)
            cur = (row[field] or "").strip()
            if not new:
                continue
            if not cur:
                sets.append(f"{field}=?"); vals.append(new); changed.append(f"{field}={str(new)[:24]}")
            elif cur != new and field in ("birth_date", "height", "measurements", "debut_date"):
                conflicts.append((row["id"], row["name"], field, cur, new))
        new_aliases = [a for a in found["aliases"]
                       if norm(a) not in {norm(t) for t in tokens}]
        if new_aliases:
            merged = ", ".join([x.strip() for x in (row["aliases"] or "").split(",") if x.strip()] + new_aliases)
            sets.append("aliases=?"); vals.append(merged); changed.append(f"别名+{new_aliases}")

        hits.append((row["id"], row["name"], found["key"], changed, found["matched_by"]))
        print(f"[命中] DB#{row['id']} {row['name']} (词条「{found['key']}」/{found['matched_by']}) -> "
              + ("; ".join(changed) if changed else "无新增字段"))

        if args.apply and changed:
            sets.append("updated_at=CURRENT_TIMESTAMP")
            conn.execute(f"UPDATE actors SET {', '.join(sets)} WHERE id=?", vals + [row["id"]])
            for f in ("birth_date", "height", "measurements", "debut_date", "description"):
                if any(s.startswith(f + "=") for s in sets):
                    filled[f] += 1
            if any(s.startswith("aliases=") for s in sets):
                filled["aliases"] += 1

    if args.apply:
        conn.commit()

    print("-" * 62)
    print(f"查询 {len(rows)} 人 | 百科命中 {len(hits)} 人 | 无词条 {len(misses)} 人")
    if args.apply:
        print("写入: " + " | ".join(f"{k} {v}" for k, v in filled.items()))
    else:
        print("(干跑模式，未写库；加 --apply 执行)")
    if conflicts:
        print(f"\n与库中已有数据冲突 {len(conflicts)} 处（已保留库中原值，未覆盖）:")
        for cid, cname, f, old, new in conflicts:
            print(f"  DB#{cid} {cname}: {f} 库内「{old}」vs 百科「{new}」")
    conn.close()


if __name__ == "__main__":
    main()
