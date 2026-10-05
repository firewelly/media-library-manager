#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清洗演员简介（本地处理，不联网）
==================================

问题：简介(bio) 由网页片段拼装而来，混入了两类不该出现的内容：
  1. **键值式档案文案**：如「中文名:… 外文名:… 身高:165cm 三围:B88(E) W56 H88 罩杯:E
     星座:… 国籍:…」——这些与结构化字段（生日/身高/三围/罩杯等）重复，不属于"详细介绍"；
  2. **盘点/榜单类段落**：如「四大伪娘图鉴 1. 愛沢さら… 2. 池田マリナ…」——描写的是多位演员。

处理：
  - 删除 标签:值 片段、推广/水印/页码等噪音；
  - 按句子切分，丢弃「编号条目」「盘点类」且未提及本人的句子；
  - 去重后重拼；剩余过短（默认 <25 字）则置空，避免以数据垃圾充数。

用法:
    python3 clean_actor_bios.py                # 干跑，打印前后对比
    python3 clean_actor_bios.py --apply        # 写库
    python3 clean_actor_bios.py --apply --limit 20
"""

import os
import re
import sys
import sqlite3
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from enrich_profiles_baike import norm  # 繁简/标点归一，用于姓名判定

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "media_library.db")

LABELS = ("中文名", "外文名", "艺名", "藝名", "别名", "別名", "本名", "姓名", "昵称", "暱稱",
          "生日", "出生日期", "出生地", "出生", "身高", "身長", "三围", "三圍", "罩杯",
          "血型", "星座", "国籍", "國籍", "民族", "职业", "職業", "事务所", "事務所",
          "经纪公司", "經紀公司", "爱好", "興趣", "兴趣", "体重", "體重", "性别", "性別",
          "出道年份", "出道年", "活跃", "活躍", "职业状况", "作品数", "出生年月日")
# 有独立字段的标签（简介里出现即为重复，需丢弃）
DROP_LABELS = ("中文名", "外文名", "艺名", "藝名", "别名", "別名", "本名", "姓名", "生日",
               "出生日期", "出生年月日", "出生", "身高", "身長", "三围", "三圍", "罩杯",
               "星座", "性别", "性別", "职业", "職業", "作品数", "出道年份", "出道年", "活跃")
# 无独立字段、值得保留进"详细介绍"的标签
KEEP_LABELS = ("出生地", "血型", "事务所", "事務所", "经纪公司", "經紀公司", "爱好",
               "興趣", "兴趣", "民族", "国籍", "國籍", "体重", "體重", "昵称", "暱稱")
LABEL_RE = re.compile(r"(?:" + "|".join(LABELS) + r")\s*[:：]?\s*[^\s，,。;；、）)]{0,18}")
NOISE_RE = re.compile(r"(cv\d+|打开网易新闻|查看精彩图片|投稿详情\S*|详情薇\S*|薇\s*jap\d+|"
                      r"https?://\S+|www\.\S+|\b\d+\s*/\s*\d+\b|【[^】]{0,12}】)")
LISTICLE_RE = re.compile(r"图鉴|圖鑑|盘点|盤點|榜单|榜單|排行|合集|大赏|大賞|TOP|"
                         r"十大|四大|八大|系列第|合集作品|每日最优|每日分享|赏颜|賞顏")
ENUM_RE = re.compile(r"^\s*\d+\s*[、.．)）]")


def mentions(text, tokens):
    n = norm(text).lower()
    return any(norm(t).lower() in n for t in tokens if t)


DATA_RE = re.compile(r"\d+\s*cm|\d{2,3}\s*[-–—/]\s*\d{2,3}\s*[-–—/]\s*\d{2,3}|"
                     r"cup|カップ|罩杯|cm\b|kg\b|\d+\s*部作品")


def digit_ratio(text):
    if not text:
        return 0
    return sum(ch.isdigit() for ch in text) / len(text)


def sanitize(bio, tokens, min_len=25):
    """按语义单元丢弃数据型片段，仅保留叙述性文字"""
    if not bio:
        return None, "空"
    text = NOISE_RE.sub(" ", bio)
    # 先抽取"无对应字段"的补充信息（出生地/血型/事务所/爱好…）
    extras, seen_x = [], set()
    for chunk in re.split(r"\s{2,}|[\n。]", text):
        m = re.match(r"^\s*(" + "|".join(KEEP_LABELS) + r")\s*[:：]\s*(.{1,40})$", chunk.strip())
        if not m:
            continue
        label, value = m.group(1), m.group(2).strip(" 　·|,，、-—:：")
        if value and label not in seen_x and len(value) <= 40:
            seen_x.add(label)
            extras.append(f"{label}：{value}")
    for m in re.finditer(r"(" + "|".join(KEEP_LABELS) + r")\s*[:：]\s*([^\s，,。;；]{1,24})", text):
        label, value = m.group(1), m.group(2).strip(" 　·|,，、-—:：")
        if value and label not in seen_x:
            seen_x.add(label)
            extras.append(f"{label}：{value}")
    units, dropped = [], 0
    for raw in re.split(r"[\n。！？;；]|\s{2,}", text):
        u = raw.strip(" 　·|,，、-—:：")
        if len(u) < 10:
            dropped += 1
            continue
        keep_ok = True
        if LABEL_RE.search(u):                                   # 键值式档案文案
            keep_ok = False
        elif DATA_RE.search(u) and not mentions(u, tokens):       # 数值/尺寸罗列
            keep_ok = False
        elif ENUM_RE.match(u) and not mentions(u, tokens):        # 编号条目
            keep_ok = False
        elif LISTICLE_RE.search(u) and not mentions(u, tokens):   # 盘点/榜单
            keep_ok = False
        elif digit_ratio(u) > 0.25 and not mentions(u, tokens):   # 数字占比过高
            keep_ok = False
        if keep_ok:
            units.append(u)
        else:
            dropped += 1
    # 去重
    seen, uniq = set(), []
    for u in units:
        key = norm(u)[:30]
        if key in seen or len(key) < 8:
            continue
        seen.add(key)
        uniq.append(u)
    out = "。".join(uniq)
    out = re.sub(r"^[。\s]+|[。\s]+$", "", out)
    if extras:
        out = (out + "。" if out else "") + "；".join(extras[:6])
    if len(out) < min_len:
        return None, f"过短({len(out)}字)已清空"
    return out, f"{len(bio)}→{len(out)} 字，丢 {dropped} 段"


def main():
    ap = argparse.ArgumentParser(description="清洗演员简介")
    ap.add_argument("--db-path", default=DB_PATH)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--show", type=int, default=5, help="打印几条前后对比")
    args = ap.parse_args()

    conn = sqlite3.connect(args.db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""SELECT id, name, name_common, name_traditional, aliases, bio
                           FROM actors WHERE bio IS NOT NULL AND bio<>'' ORDER BY id""").fetchall()
    if args.limit:
        rows = rows[:args.limit]

    cleared = changed = kept = 0
    shown = 0
    for r in rows:
        tokens = [t.strip() for t in [r["name"], r["name_common"], r["name_traditional"]]
                  + (r["aliases"] or "").split(",") if t and t.strip()]
        new, note = sanitize(r["bio"], tokens)
        if new is None:
            cleared += 1
        elif new != r["bio"]:
            changed += 1
        else:
            kept += 1
        if shown < args.show and (new is None or new != r["bio"]):
            shown += 1
            print(f"\n--- DB#{r['id']} {r['name']} ({note}) ---")
            print("原:", (r["bio"] or "")[:200].replace("\n", " "))
            print("新:", (new or "（置空）")[:200].replace("\n", " "))
        if args.apply:
            conn.execute("UPDATE actors SET bio=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                         (new, r["id"]))
    if args.apply:
        conn.commit()
    print("\n" + "-" * 60)
    print(f"处理 {len(rows)} 条 | 内容更新 {changed} | 置空 {cleared} | 保持不变 {kept}")
    if not args.apply:
        print("(干跑模式，未写库；加 --apply 执行)")
    conn.close()


if __name__ == "__main__":
    main()
