#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用 DeepSeek 从已有文本中识别演员罩杯（LLM 辅助提取）
======================================================

背景: 罩杯常见于「作品标题」（如 G罩杯新人女社員 / Fカップ / Iカップ）与简介正文，
但写法繁多（カップ/罩杯/杯/灯/乳），且合辑作品的罩杯可能属于他人，纯正则难以判定。

做法:
  1. 取该演员在库内的作品标题（含番号）+ 简介/摘要文本，交给 DeepSeek 判断；
  2. **要求模型返回证据原文**，脚本校验该证据确实存在于提供的文本中（防幻觉）；
  3. 仅当模型判定「明确指向她本人」且证据校验通过时才写入 cup。

密钥: 从 OneDrive MacMgt/config 读取 DEEPSEEK_API_KEY（项目内不保存密钥）。

用法:
    python3 extract_cup_llm.py --limit 20                # 干跑试算
    python3 extract_cup_llm.py --apply --workers 4       # 写库
"""

import os
import re
import sys
import json
import time
import sqlite3
import argparse
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils.secrets import get_key, load_keys
from enrich_profiles_baike import norm

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "media_library.db")
API_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-chat"

PROMPT = """你是资料核对助手。下面给出日本 AV 女演员「{name}」的资料片段（她的作品标题、简介）。
请判断资料中是否**明确写出她本人**的罩杯（cup，字母 A-L）。

严格要求：
1. 只依据给定原文，禁止推测、禁止常识推断（例如"巨乳"不等于具体罩杯）。
2. 合辑/多演员作品的标题里出现的罩杯（如"全員Fカップ以上"、"＃A ＃B ＃C"多人群演）不能算作她的罩杯。
3. 必须能引用原文片段作为证据，evidence 必须是给定资料中的原样文字。
4. 不确定就返回 null，宁可漏报不可错报。

只输出 JSON：{{"cup": "字母或 null", "evidence": "原文片段或空", "reason": "一句话"}}

资料：
{context}"""


def fetch_actors(conn, limit=0, ids=None):
    sql = """SELECT DISTINCT a.id, a.name, a.name_common, a.name_traditional, a.aliases,
                    a.bio, a.description
             FROM actors a JOIN video_actors va ON va.actor_id = a.id
             WHERE (a.cup IS NULL OR a.cup = '')"""
    if ids:
        sql += f" AND a.id IN ({','.join(str(i) for i in ids)})"
    rows = conn.execute(sql).fetchall()
    return rows[:limit] if limit else rows


def build_context(conn, actor):
    titles = [r[0] for r in conn.execute(
        """SELECT DISTINCT v.title FROM videos v JOIN video_actors va ON va.video_id = v.id
           WHERE va.actor_id = ? AND v.title IS NOT NULL
           ORDER BY v.id DESC LIMIT 20""", (actor["id"],)).fetchall()]
    titles = [t[:120] for t in titles if t]
    descs = [r[0] for r in conn.execute(
        """SELECT DISTINCT v.description FROM videos v JOIN video_actors va ON va.video_id = v.id
           WHERE va.actor_id = ? AND v.description IS NOT NULL AND length(v.description) > 10
           LIMIT 10""", (actor["id"],)).fetchall()]
    descs = [d[:300] for d in descs if d]
    bio = (actor["bio"] or actor["description"] or "")[:400]
    parts = ["【作品标题】"] + [f"- {t}" for t in titles]
    if descs:
        parts += ["【作品描述】"] + [f"- {d}" for d in descs]
    if bio:
        parts += ["【简介】", bio]
    return "\n".join(parts), titles + descs + [bio]


def ask_deepseek(context, name, key, retries=3):
    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": PROMPT.format(name=name, context=context)}],
        "temperature": 0,
        "max_tokens": 300,
        "response_format": {"type": "json_object"},
    }
    for i in range(retries):
        try:
            r = requests.post(API_URL, json=body, timeout=60,
                              headers={"Authorization": f"Bearer {key}",
                                       "Content-Type": "application/json"})
            if r.status_code in (429, 500, 502, 503):
                time.sleep(1.5 * (i + 1))
                continue
            r.raise_for_status()
            data = r.json()
            content = data["choices"][0]["message"]["content"]
            return json.loads(content), data.get("usage", {})
        except Exception as e:
            if i == retries - 1:
                return {"error": str(e)[:80]}, {}
            time.sleep(1.2 * (i + 1))
    return {"error": "retries exhausted"}, {}


def evidence_ok(evidence, sources):
    """校验模型给的证据确实来自我们提供的文本（防幻觉）"""
    if not evidence or len(evidence) < 4:
        return False
    ne = norm(evidence).lower()
    for s in sources:
        if not s:
            continue
        ns = norm(s).lower()
        if ne and (ne in ns or ns in ne):
            return True
    return False


def main():
    ap = argparse.ArgumentParser(description="DeepSeek 识别罩杯")
    ap.add_argument("--db-path", default=DB_PATH)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--ids", default="")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--min-titles", type=int, default=1, help="至少有多少条作品标题才送审")
    args = ap.parse_args()

    load_keys()
    key = get_key("DEEPSEEK_API_KEY")
    if not key:
        print("未找到 DEEPSEEK_API_KEY（OneDrive MacMgt/config/skills-api-keys.env）", file=sys.stderr)
        return 2

    conn = sqlite3.connect(args.db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    ids = {int(x) for x in args.ids.split(",") if x.strip()} if args.ids else None
    actors = fetch_actors(conn, args.limit, ids)
    print(f"待识别 {len(actors)} 人（并发 {args.workers}）")

    jobs, tasks = {}, {}
    for a in actors:
        ctx, sources = build_context(conn, a)
        if ctx.count("- ") < args.min_titles:
            continue
        jobs[a["id"]] = (a, sources)
        tasks[a["id"]] = None

    found, checked, tokens_in = [], 0, 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {}
        for aid, (a, sources) in jobs.items():
            ctx, _ = build_context(conn, a)
            futs[pool.submit(ask_deepseek, ctx, a["name"], key)] = aid
        for i, fut in enumerate(as_completed(futs), 1):
            aid = futs[fut]
            a, sources = jobs[aid]
            res, usage = fut.result()
            checked += 1
            tokens_in += usage.get("prompt_tokens", 0)
            cup = (res or {}).get("cup")
            ev = (res or {}).get("evidence") or ""
            if cup and re.fullmatch(r"[A-La-l]", str(cup)) and evidence_ok(ev, sources):
                found.append((aid, a["name"], cup.upper(), ev[:70]))
                if args.apply:
                    conn.execute("""UPDATE actors SET cup=?, updated_at=CURRENT_TIMESTAMP
                                    WHERE id=? AND (cup IS NULL OR cup='')""", (cup.upper(), aid))
            if i % 25 == 0 or i == len(futs):
                conn.commit() if args.apply else None
                print(f"  进度 {i}/{len(futs)} | 命中 {len(found)} | 累计输入 {tokens_in} tokens",
                      flush=True)

    if args.apply:
        conn.commit()
    print("\n" + "-" * 60)
    print(f"送审 {checked} 人 | 命中 {len(found)} 人 | 输入 tokens ≈ {tokens_in}")
    for f in found[:20]:
        print(f"   DB#{f[0]} {f[1]} -> {f[2]}  ← {f[3]}")
    if not args.apply:
        print("(干跑模式，未写库；加 --apply 执行)")
    conn.close()


if __name__ == "__main__":
    main()
