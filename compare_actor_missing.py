#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
演员作品缺失比对工具
====================
将 javdb_actor_all.py 爬取的演员单体作品 CSV 与本地 media_library.db 比对，
找出本地缺失的作品，输出 CSV + Markdown 列表（含 JavDB 链接）。

用法:
    python3 compare_actor_missing.py results/javdb_彩美旬果_solo.csv
    python3 compare_actor_missing.py <csv> --actor-id 489
"""

import os
import re
import csv
import sqlite3
import argparse
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'media_library.db')


def normalize_code(code):
    if not code:
        return ''
    code = str(code).strip().upper()
    code = re.sub(r'\s+', '', code)
    # FC2 统一为 FC2-XXXX 格式比较
    code = re.sub(r'^FC2[-_]?PPV[-_]?(\d+)$', r'FC2-\1', code)
    return code


def load_owned_codes(db_path):
    """本地已拥有番号集合: javdb_info.javdb_code + videos.file_name 提取的番号"""
    owned = set()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT javdb_code FROM javdb_info WHERE javdb_code IS NOT NULL")
    for (c,) in cur.fetchall():
        n = normalize_code(c)
        if n:
            owned.add(n)
    cur.execute("SELECT file_name FROM videos WHERE file_name IS NOT NULL")
    rows = cur.fetchall()
    conn.close()
    try:
        from code_extractor import CodeExtractor
        extractor = CodeExtractor()
        for (fn,) in rows:
            c = extractor.extract_code_from_filename(fn or '')
            if c:
                n = normalize_code(c)
                if n:
                    owned.add(n)
    except Exception as e:
        print(f"警告: CodeExtractor 不可用({e})，仅使用 javdb_info 番号比对")
    return owned


def load_actor_tagged_codes(db_path, actor_id):
    """通过 video_actors 关联到该演员的本地视频番号（javdb_code 优先，其次文件名提取）"""
    codes = set()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT COALESCE(j.javdb_code, ''), v.file_name
        FROM video_actors va
        JOIN videos v ON v.id = va.video_id
        LEFT JOIN javdb_info j ON j.video_id = v.id
        WHERE va.actor_id = ?
    """, (actor_id,))
    rows = cur.fetchall()
    conn.close()
    extractor = None
    try:
        from code_extractor import CodeExtractor
        extractor = CodeExtractor()
    except Exception:
        pass
    for javdb_code, fn in rows:
        c = javdb_code
        if not c and extractor:
            c = extractor.extract_code_from_filename(fn or '')
        n = normalize_code(c)
        if n:
            codes.add(n)
    return codes


def load_crawl_csv(csv_path):
    works = []
    with open(csv_path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = normalize_code(row.get('video_id') or '')
            if not code or code == 'N/A':
                continue
            works.append({
                'code': code,
                'title': (row.get('title') or '').strip(),
                'release_date': (row.get('release_date') or '').strip(),
                'rating': (row.get('rating') or '').strip(),
                'detail_url': (row.get('detail_url') or '').strip(),
                'has_magnet': bool((row.get('magnet_link') or '').strip()),
            })
    # 按 code 去重（保留首条）
    seen = set()
    uniq = []
    for w in works:
        if w['code'] not in seen:
            seen.add(w['code'])
            uniq.append(w)
    return uniq


def main():
    parser = argparse.ArgumentParser(description='比对爬取的演员作品与本地数据库，输出缺失列表')
    parser.add_argument('csv_path', help='javdb_actor_all.py 生成的作品CSV')
    parser.add_argument('--actor-id', dest='actor_id', type=int, default=None,
                        help='actors 表中的演员ID（可选，用于附加统计）')
    parser.add_argument('--db', dest='db_path', default=DB_PATH, help='数据库路径')
    parser.add_argument('--outdir', dest='outdir', default='results', help='输出目录')
    parser.add_argument('--link-domain', dest='link_domain', default='',
                        help='将输出中的 JavDB 链接替换为该镜像域名，如 javdb571.com（JavDB 各镜像的 /v/ ID 通用）')
    args = parser.parse_args()

    works = load_crawl_csv(args.csv_path)
    if not works:
        print("爬取CSV中没有有效作品记录")
        return
    if args.link_domain:
        for w in works:
            w['detail_url'] = re.sub(r'://[^/]+/', f'://{args.link_domain}/', w['detail_url'])

    if args.link_domain:
        for w in works:
            w['detail_url'] = re.sub(r'://[^/]+/', f'://{args.link_domain}/', w['detail_url'])

    owned = load_owned_codes(args.db_path)
    actor_tagged = load_actor_tagged_codes(args.db_path, args.actor_id) if args.actor_id else set()

    missing = [w for w in works if w['code'] not in owned]
    have = [w for w in works if w['code'] in owned]

    os.makedirs(args.outdir, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    actor_name = os.path.basename(args.csv_path)
    actor_name = re.sub(r'^javdb_|\.csv$', '', actor_name)
    base = os.path.join(args.outdir, f"missing_{actor_name}_{stamp}")

    # CSV 输出
    csv_out = base + '.csv'
    with open(csv_out, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=['code', 'title', 'release_date', 'rating', 'has_magnet', 'detail_url'])
        w.writeheader()
        for item in sorted(missing, key=lambda x: x['release_date'] or '', reverse=True):
            w.writerow(item)

    # Markdown 输出
    md_out = base + '.md'
    with open(md_out, 'w', encoding='utf-8') as f:
        f.write(f"# 本地缺失的演员单体作品：{actor_name}\n\n")
        f.write(f"- 爬取来源: `{args.csv_path}`\n")
        f.write(f"- 比对时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"- 单体作品总数: **{len(works)}**\n")
        f.write(f"- 本地已拥有: **{len(have)}** ({len(have)*100//len(works)}%)\n")
        f.write(f"- 本地缺失: **{len(missing)}**\n")
        if actor_tagged:
            in_actor_tagged = sum(1 for w in missing if w['code'] in actor_tagged)
            f.write(f"- 缺失作品中已被标记为该演员但番号未入库的: {in_actor_tagged}\n")
        f.write(f"- 缺失作品中 JavDB 有磁力链接的: **{sum(1 for w in missing if w['has_magnet'])}**\n\n")

        f.write("## 缺失列表（按发行日期倒序）\n\n")
        f.write("| # | 番号 | 发行日期 | 评分 | 磁力 | 标题 | 链接 |\n")
        f.write("|---|------|----------|------|------|------|------|\n")
        for i, w_ in enumerate(sorted(missing, key=lambda x: x['release_date'] or '', reverse=True), 1):
            title = w_['title'][:60].replace('|', '/')
            magnet = '✅' if w_['has_magnet'] else '—'
            f.write(f"| {i} | {w_['code']} | {w_['release_date']} | {w_['rating']} | {magnet} | {title} | {w_['detail_url']} |\n")

    print(f"单体作品总数: {len(works)} | 本地已有: {len(have)} | 缺失: {len(missing)}")
    if actor_tagged:
        print(f"演员标记视频番号(本地): {len(actor_tagged)}")
    print(f"输出: {csv_out}")
    print(f"输出: {md_out}")


if __name__ == '__main__':
    main()
