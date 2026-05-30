#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
双向匹配 + metadata 同步
1. 文件名/番号匹配：在线文件 ↔ DB记录
2. 元数据补充：在线记录缺失metadata时，从离线记录同番号复制
3. 无文件记录删除，无记录文件报告
"""

import os, sys, sqlite3, re, argparse
from typing import Optional
from collections import defaultdict

VIDEO_EXTS = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.3gp', '.ts', '.mts', '.m2ts'}

def extract_code(filename: str) -> Optional[str]:
    name = os.path.splitext(os.path.basename(filename))[0]
    name = re.sub(r'[\[\(（].*?[\]\)）]|\d{3,4}[pP]|[hH][dD]|[uU][hH][dD]|[bB][dD]|[rR][iI][pP]|[wW][eE][bB][-_]?[dD][lL]', '', name)
    m = re.search(r'fc2[^a-z\d]{0,5}(ppv[^a-z\d]{0,5})?(\d{5,7})', name, re.I)
    if m: return f'FC2-{m.group(2)}'
    m = re.search(r'(?:heydouga|hey)[-_]*(\d{4})[-_]0?(\d{3,5})', name, re.I)
    if m: return f'heydouga-{m.group(1)}-{m.group(2)}'
    m = re.search(r'([a-z]{2,10})[-_](\d{2,5})', name, re.I)
    if m: return f'{m.group(1).upper()}-{m.group(2)}'
    m = re.search(r'([a-z]{2,})(\d{2,5})', name, re.I)
    if m: return f'{m.group(1).upper()}-{m.group(2)}'
    return None

def scan_folders(folders):
    by_name, by_code, name_conflicts, total = {}, defaultdict(list), [], 0
    for folder in folders:
        if not os.path.isdir(folder): continue
        for root, _, files in os.walk(folder):
            for f in files:
                if os.path.splitext(f)[1].lower() not in VIDEO_EXTS: continue
                fp = os.path.join(root, f); total += 1
                key = f.lower()
                if key in by_name: name_conflicts.append((key, fp, by_name[key]))
                else: by_name[key] = fp
                code = extract_code(f)
                if code: by_code[code.lower()].append(fp)
    return by_name, dict(by_code), name_conflicts, total

def in_any(path, folders):
    return any(path.startswith(f) for f in folders) if path else False

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--dry-run', action='store_true', help='干跑预览')
    p.add_argument('--sync-meta', action='store_true', help='补充元数据（从离线同番号复制）')
    p.add_argument('--skip-folder', action='append', dest='skip_folders', default=[], 
                   help='跳过该文件夹（不扫描、不处理），可重复指定')
    args = p.parse_args()

    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'media_library.db')
    if not os.path.exists(db_path): print(f"❌ 数据库不存在: {db_path}"); sys.exit(1)
    conn = sqlite3.connect(db_path); c = conn.cursor()

    c.execute("SELECT folder_path FROM folders WHERE is_active = 1")
    all_folders = [r[0] for r in c.fetchall()]
    skip_set = set(args.skip_folders)
    online = [f for f in all_folders if os.path.isdir(f) and f not in skip_set]
    offline = [f for f in all_folders if not os.path.isdir(f)]

    if skip_set:
        skipped = [f for f in all_folders if f in skip_set]
        for f in skipped: print(f"   ⏭ 跳过(用户指定): {f}")

    print(f"📁 在线 {len(online)} 个, 离线 {len(offline)} 个")
    for f in offline: print(f"   ⏭ 离线: {f}")

    print("\n🔍 扫描在线文件夹...")
    name_idx, code_idx, name_cf, nfiles = scan_folders(online)
    print(f"   {nfiles} 文件, {len(name_idx)} 唯一名, {len(code_idx)} 唯一番号")
    if name_cf: print(f"   ⚠ 同名 {len(name_cf)} 组 (如 {name_cf[0][0]})")

    c.execute("SELECT id, file_path, file_name FROM videos ORDER BY id")
    all_recs = c.fetchall()
    print(f"\n📊 数据库共 {len(all_recs)} 条")
    recs_online = [r for r in all_recs if in_any(r[1], online)]
    recs_offline = [r for r in all_recs if r[1] and in_any(r[1], offline)]
    recs_nopath = [r for r in all_recs if not r[1]]
    print(f"   在线: {len(recs_online)} | 离线: {len(recs_offline)} | 无路径: {len(recs_nopath)}")

    # === Step 1: 文件名/番号匹配 ===
    updated = []      # (id, old_path, new_path, reason)
    matched_ids = set()
    unmatched_recs = []
    used_files = set()

    for rid, fp, fn in recs_online:
        if os.path.exists(fp):
            matched_ids.add(rid)
            continue
        key = (fn or '').lower()
        if key in name_idx:
            np = name_idx[key]
            if np != fp: updated.append((rid, fp, np, "文件名匹配"))
            used_files.add(np); matched_ids.add(rid)
        else:
            unmatched_recs.append((rid, fp, fn))

    # 番号匹配（未配对的记录 ↔ 未配对的磁盘文件）
    unmatched_file_by_code = defaultdict(list)
    for fp in name_idx.values():
        if fp in used_files: continue
        code = extract_code(os.path.basename(fp))
        if code: unmatched_file_by_code[code.lower()].append(fp)

    still_unmatched = []
    for rid, fp, fn in unmatched_recs:
        code = extract_code(fn or '')
        if not code: still_unmatched.append((rid, fp, fn, "无番号")); continue
        cl = code.lower()
        if cl not in unmatched_file_by_code:
            still_unmatched.append((rid, fp, fn, f"番号{code}无文件")); continue
        cands = unmatched_file_by_code[cl]
        if len(cands) == 1:
            updated.append((rid, fp, cands[0], f"番号匹配 {code}"))
            used_files.add(cands[0]); matched_ids.add(rid)
            del unmatched_file_by_code[cl]
        else:
            # 多候选取路径相似度最高的
            bn = (fn or '').lower()
            chosen = sorted(cands, key=lambda p: abs(len(p) - len(bn)))[0]
            updated.append((rid, fp, chosen, f"多番号配对 {code}({len(cands)}候选)"))
            used_files.add(chosen); matched_ids.add(rid)
            unmatched_file_by_code[cl] = [p for p in cands if p != chosen]
            if not unmatched_file_by_code[cl]: del unmatched_file_by_code[cl]

    unmatched_files = [fp for fp in name_idx.values() if fp not in used_files]

    # === Step 2: metadata 同步（仅 --sync-meta 时执行）===
    meta_synced = []  # (online_video_id, code, 从离线 video_id 复制)
    if args.sync_meta and recs_offline:
        # 构建离线索引: javdb_code → (video_id, file_path)
        c2 = conn.cursor()
        c2.execute("""
            SELECT j.javdb_code, j.video_id, v.file_path
            FROM javdb_info j
            JOIN videos v ON v.id = j.video_id
            WHERE v.file_path IS NOT NULL
        """)
        offline_by_code = defaultdict(list)
        for code, vid, fpath in c2.fetchall():
            if in_any(fpath, offline):
                offline_by_code[code.upper()].append((vid, fpath))

        # 遍历 online 中已有匹配（matched_ids）、但缺失 metadata 的记录
        meta_missing_ids = set()
        # videos 表关键字段为空
        c2.execute(f"""
            SELECT v.id, v.file_name FROM videos v
            WHERE v.id IN ({','.join(map(str, matched_ids)) if matched_ids else '0'})
              AND (v.title IS NULL OR v.title = '')
        """)
        for vid, fn in c2.fetchall():
            code = extract_code(fn or '')
            if code and code.upper() in offline_by_code:
                meta_missing_ids.add((vid, code.upper(), 'title'))

        # javdb_info 不存在或空
        c2.execute(f"""
            SELECT v.id, v.file_name FROM videos v
            LEFT JOIN javdb_info j ON j.video_id = v.id
            WHERE v.id IN ({','.join(map(str, matched_ids)) if matched_ids else '0'})
              AND j.id IS NULL
        """)
        for vid, fn in c2.fetchall():
            code = extract_code(fn or '')
            if code and code.upper() in offline_by_code:
                meta_missing_ids.add((vid, code.upper(), 'javdb_info'))

        # 对每条缺失记录，找到离线记录并复制
        seen_pairs = set()
        for vid, code, miss_type in meta_missing_ids:
            pair = (vid, code)
            if pair in seen_pairs: continue
            seen_pairs.add(pair)
            off_records = offline_by_code.get(code, [])
            if not off_records: continue
            # 取离线中信息最完整的一条
            best_off = None
            for off_vid, off_path in off_records:
                c2.execute("SELECT javdb_title, score, release_date, duration, studio, series FROM javdb_info WHERE video_id = ?", (off_vid,))
                row = c2.fetchone()
                if row:
                    filled = sum(1 for v in row if v)
                    if best_off is None or filled > best_off[1]:
                        best_off = (off_vid, off_path, filled)
            if best_off:
                meta_synced.append((vid, code, best_off[0], best_off[1]))

    # === 报告 ===
    in_place = sum(1 for r in recs_online if os.path.exists(r[1]))
    print(f"\n{'='*55}")
    print(f"  匹配结果:")
    print(f"  ✅ 文件在原处: {in_place}")
    print(f"  🔄 路径匹配更新: {len(updated)}")
    print(f"  🗑 待删除(无文件): {len(still_unmatched)}")
    print(f"  ➕ 待导入(无记录): {len(unmatched_files)}")
    print(f"  ⏭ 离线目录跳过: {len(recs_offline)}")
    if args.sync_meta:
        print(f"  📋 元数据待补充:  {len(meta_synced)}")
    print(f"{'='*55}")

    if updated:
        print(f"\n📌 路径更新 (前5):")
        for rid, old, new, why in updated[:5]:
            print(f"  [{why}] id={rid}: {os.path.basename(old)} → {os.path.dirname(new)}/")
        print(f"  总计 {len(updated)} 条")

    if still_unmatched:
        print(f"\n🗑 待删除 (前10):")
        for rid, fp, fn, reason in still_unmatched[:10]:
            print(f"  id={rid} [{reason}]: {fn or os.path.basename(fp)} → {fp[:60]}")

    if unmatched_files:
        print(f"\n➕ 无记录文件 (前10):")
        for fp in unmatched_files[:10]:
            print(f"   {fp}")
        print(f"  总计 {len(unmatched_files)} 个")

    if args.sync_meta and meta_synced:
        print(f"\n📋 元数据待补充 (前10):")
        for vid, code, off_vid, off_path in meta_synced[:10]:
            print(f"  id={vid} ({code}) ← 离线id={off_vid} {os.path.basename(off_path)}")
        print(f"  总计 {len(meta_synced)} 条")

    if args.dry_run:
        print("\n✅ 干跑模式，未修改数据库"); conn.close(); return

    if not updated and not still_unmatched and not meta_synced:
        print("\n✅ 无需变更"); conn.close(); return

    ret = input(f"\n确认执行？更新路径 {len(updated)} 条，删除 {len(still_unmatched)} 条"
                + (f"，补充元数据 {len(meta_synced)} 条" if meta_synced else "")
                + " (yes/no): ").strip().lower()
    if ret != 'yes': print("已取消"); conn.close(); return

    print("\n执行中...")
    for rid, _, new_path, _ in updated:
        c.execute("UPDATE videos SET file_path = ?, updated_at = datetime('now') WHERE id = ?", (new_path, rid))
    for rid, _, _, _ in still_unmatched:
        for tbl in ['javdb_info', 'video_actors', 'javdb_info_tags', 'movies', 'tags']:
            c.execute(f"DELETE FROM {tbl} WHERE video_id = ?", (rid,))
        c.execute("DELETE FROM videos WHERE id = ?", (rid,))
    if args.sync_meta and meta_synced:
        META_COPY_FIELDS = ['javdb_code', 'javdb_url', 'javdb_title', 'release_date',
                            'duration', 'studio', 'series', 'rating', 'score']

        for vid, code, off_vid, off_path in meta_synced:
            c.execute(f"SELECT {', '.join(META_COPY_FIELDS)} FROM javdb_info WHERE video_id = ?", (off_vid,))
            src = c.fetchone()
            if not src or not any(v for v in src): continue
            c.execute(f"SELECT id FROM javdb_info WHERE video_id = ?", (vid,))
            existing = c.fetchone()
            if existing:
                updates = {k: v for k, v in zip(META_COPY_FIELDS, src) if v}
                if updates:
                    set_clause = ', '.join(f"{k}=?" for k in updates)
                    vals = list(updates.values()) + [vid]
                    c.execute(f"UPDATE javdb_info SET {set_clause}, updated_at=datetime('now') WHERE video_id=?", vals)
            else:
                cols = META_COPY_FIELDS
                vals = [vid] + list(src)
                c.execute(f"INSERT INTO javdb_info (video_id, {', '.join(cols)}) VALUES ({','.join('?' for _ in range(len(cols)+1))})", vals)
            # 复制 video_actors
            c.execute("SELECT actor_id FROM video_actors WHERE video_id = ?", (off_vid,))
            for (aid,) in c.fetchall():
                c.execute("INSERT OR IGNORE INTO video_actors (video_id, actor_id) VALUES (?, ?)", (vid, aid))
        print(f"  📋 补充元数据 {len(meta_synced)} 条")
    conn.commit()
    print(f"✅ 完成")
    conn.close()

if __name__ == '__main__':
    main()
