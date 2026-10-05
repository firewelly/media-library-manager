#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
规划 BLACK(U盘) -> DXP4800 的视频分发：收藏演员 -> Video/usr，其余 -> Video/JAV。

规则（与 migrate_av_to_nas.py 一致）：
- 多演员文件夹：任一演员是收藏 -> usr，否则 JAV
- 单演员：按 actors 表判定；目标文件夹名优先用 usr/JAV 里已存在的同名/别名文件夹，
  其次 merge.conf 的规范名，最后沿用 U 盘上的文件夹名
- #未知女优 -> JAV/#未知女优

只做规划与冲突检测，不动任何文件。产出 plan JSON 供执行脚本使用。
"""
import json
import os
import sqlite3
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, 'media_library.db')
CONF = os.path.join(HERE, 'merge.conf')
INDEX = os.path.join(HERE, 'black_jav_md5_index.json')
NAS_RUN = os.path.join(HERE, 'nas_run.sh')

USB_BASE = '/mnt/@usb/sde2/JAV'
NAS_USR = '/volume1/Video/usr'
NAS_JAV = '/volume1/Video/JAV'


def nas(cmd):
    r = subprocess.run([NAS_RUN, cmd], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"[NAS 命令失败] {cmd}\n{r.stderr[:500]}", file=sys.stderr)
        sys.exit(1)
    return r.stdout


def load_alias_map():
    m = {}
    if not os.path.exists(CONF):
        return m
    with open(CONF, encoding='utf-8') as f:
        for line in f:
            cols = [c.strip() for c in line.rstrip('\n').split('\t') if c.strip()]
            if not cols:
                continue
            for c in cols:
                m[c] = cols[0]
    return m


def load_actor_index(alias_map):
    """name 变体 -> (actor_id, 规范名, is_favorite)。

    同时收录 merge.conf 规范名：文件夹名可能是规范形式（如 楓カレン（枫花恋）），
    直接按变体匹配不到，需要规范名反向映射。
    """
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    idx = {}
    for r in conn.execute("SELECT id,name,name_traditional,name_common,aliases,is_favorite FROM actors"):
        variants = [r['name'], r['name_traditional'], r['name_common']]
        variants += [a.strip() for a in (r['aliases'] or '').split(',')]
        forms = set(v.strip() for v in variants if v and v.strip())
        forms |= set(alias_map[f] for f in forms if f in alias_map)
        for v in forms:
            idx.setdefault(v, []).append((r['id'], r['name'], r['is_favorite']))
    conn.close()
    return idx


def match_actor(name, actor_idx, alias_map):
    """返回该名字命中的 actor 行列表。"""
    hits = actor_idx.get(name)
    if hits:
        return hits
    canon = alias_map.get(name)
    if canon:
        hits = actor_idx.get(canon)
        if hits:
            return hits
    return []


def folder_names(folder):
    """拆分文件夹名 -> 演员名列表，兼容 'A,B' 与 'A - B' 两种写法。"""
    parts = []
    for chunk in folder.split(','):
        for sub in chunk.split(' - '):
            sub = sub.strip()
            if sub:
                parts.append(sub)
    return parts


def main():
    alias_map = load_alias_map()
    actor_idx = load_actor_index(alias_map)
    index = json.load(open(INDEX, encoding='utf-8'))['entries']
    md5_by_key = {}
    for rel, v in index.items():
        md5_by_key[(v['name'], v['size'])] = (v['md5'], rel)

    usb_files = []
    for line in nas(f"find {USB_BASE} -type f \\( -iname '*.mp4' -o -iname '*.mkv' \\) -printf '%s\\t%p\\n'").splitlines():
        if not line.strip():
            continue
        size, path = line.split('\t', 1)
        usb_files.append((path, int(size)))

    usr_folders = set(nas(f"ls -1 {NAS_USR}").split('\n')) - {''}
    jav_folders = set(nas(f"ls -1 {NAS_JAV}").split('\n')) - {''}

    # 目标路径存在性检查（一次 ssh 批量）
    plan = []
    for path, size in usb_files:
        rel = os.path.relpath(path, USB_BASE)
        parts = rel.split('/')
        actor_folder = parts[0]
        name = os.path.basename(path)
        md5, idx_rel = md5_by_key.get((name, size), (None, None))
        if not md5:
            print(f"!! 无预算 MD5: {path}")
            continue

        if actor_folder == '#未知女优':
            parent, target_folder = 'JAV', '#未知女优'
            actors, is_fav, matched = [], False, []
        else:
            names = folder_names(actor_folder)
            matched = []
            for n in names:
                matched.append((n, match_actor(n, actor_idx, alias_map)))
            is_fav = any(h[2] == 1 for _, hits in matched for h in hits)
            actors = [n for n, _ in matched]
            parent = 'usr' if is_fav else 'JAV'
            pool = usr_folders if parent == 'usr' else jav_folders
            # 目标文件夹名：已有同名/别名文件夹 > merge.conf 规范名 > U盘原名
            target_folder = None
            if actor_folder in pool:
                target_folder = actor_folder
            else:
                for n, hits in matched:
                    for variant in ([n] + ([alias_map[n]] if n in alias_map else [])):
                        if variant in pool:
                            target_folder = variant
                            break
                    if target_folder:
                        break
            if not target_folder and len(names) == 1:
                target_folder = alias_map.get(names[0], names[0])
            if not target_folder:
                target_folder = actor_folder

        base = NAS_USR if parent == 'usr' else NAS_JAV
        sub = '/'.join(parts[1:-1])          # 番号 文件夹
        target_dir = f"{base}/{target_folder}" + (f"/{sub}" if sub else '')
        plan.append({
            'src': path,
            'size': size,
            'md5': md5,
            'actors': actors,
            'matched': [[n, [list(h) for h in hits]] for n, hits in matched],
            'is_favorite': is_fav,
            'parent': parent,
            'target_dir': target_dir,
            'target_path': f"{target_dir}/{name}",
            'mac_path': f"/Volumes/Video/{target_dir[len('/volume1/Video/'):]}/{name}",
            'src_rel': rel,
        })

    # 冲突检测（末尾 true 保证 ssh 退出码为 0）
    checks = '\n'.join(f"[ -e '{p['target_path']}' ] && echo 'EXIST:{p['target_path']}'" for p in plan)
    out = nas(checks + '\ntrue')
    existing = set(l.split('EXIST:', 1)[1] for l in out.splitlines() if l.startswith('EXIST:'))

    # JAV 中属于收藏演员的文件夹
    jav_move = []
    for f in sorted(jav_folders):
        if f.startswith('@') or f in ('#recycle', 'Thumbs.db'):
            continue
        names = folder_names(f)
        if not names:
            continue
        fav_hits = []
        for n in names:
            for h in match_actor(n, actor_idx, alias_map):
                if h[2] == 1:
                    fav_hits.append((n, h))
        if fav_hits:
            jav_move.append({'folder': f, 'fav_hits': [[n, list(h)] for n, h in fav_hits],
                             'in_usr': f in usr_folders})

    # usr 中已不是收藏演员的历史文件夹（本次不处理，仅提示）
    legacy_usr = []
    for f in sorted(usr_folders):
        if f.startswith(('@', '#')) or f in ('Thumbs.db',):
            continue
        names = folder_names(f)
        hits = [h for n in names for h in match_actor(n, actor_idx, alias_map)]
        if names and not any(h[2] == 1 for h in hits):
            legacy_usr.append(f)

    report = {
        'plan': plan,
        'existing_targets': sorted(existing),
        'jav_to_usr': jav_move,
        'legacy_usr_not_favorite': legacy_usr,
        'usr_folders': sorted(usr_folders),
        'jav_folder_count': len(jav_folders),
    }
    out_path = os.path.join(HERE, 'black_jav_migration_plan.json')
    json.dump(report, open(out_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    # 摘要
    print(f"待搬运文件: {len(plan)} 个, {sum(p['size'] for p in plan)/1024**3:.1f} GB")
    print(f"  收藏->usr: {sum(1 for p in plan if p['parent']=='usr')} 个文件, "
          f"{sum(p['size'] for p in plan if p['parent']=='usr')/1024**3:.1f} GB")
    print(f"  非收藏->JAV: {sum(1 for p in plan if p['parent']=='JAV')} 个文件, "
          f"{sum(p['size'] for p in plan if p['parent']=='JAV')/1024**3:.1f} GB")
    print(f"  目标已存在同名文件: {len(existing)} 个")
    for e in sorted(existing):
        print(f"     {e}")
    print(f"\n目标文件夹一览:")
    from collections import Counter
    c = Counter((p['parent'], p['target_dir']) for p in plan)
    for (parent, d), n in sorted(c.items()):
        mark = '  [已存在]' if d.split('/')[3] in (usr_folders if parent == 'usr' else jav_folders) else '  [新建]'
        print(f"   [{parent}] {d}  ({n} 个){mark}")
    print(f"\nJAV 中收藏演员的文件夹: {len(jav_move)} 个"
          f"（其中 {sum(1 for m in jav_move if m['in_usr'])} 个 usr 已有同名文件夹，需合并）")
    for m in jav_move:
        print(f"   {m['folder']}  <- 收藏: {', '.join(sorted({n for n,_ in m['fav_hits']}))}"
              + ('   [需合并到 usr 同名文件夹]' if m['in_usr'] else ''))
    print(f"\nusr 中已非收藏演员的历史文件夹: {len(legacy_usr)} 个（本次不动，仅提示）")
    for f in legacy_usr:
        print(f"   {f}")
    print(f"\n计划已写入 {out_path}")


if __name__ == '__main__':
    main()
