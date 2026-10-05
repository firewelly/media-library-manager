#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将 JavDB 网页上收藏的演员同步标记到本地数据库
================================================

数据来源: JavDB「收藏的演員」页面 (/users/collection_actors)，人工整理为
FAVORITED_ACTORS 列表（JavDB 演员 ID + 页面 title 中的全部名称）。

功能:
1. 匹配: 优先按 profile_url 中的 JavDB 演员 ID 精确匹配，
   其次按 name / name_traditional / name_common / aliases 匹配。
2. 标记: --apply 将匹配到的演员 is_favorite=1。
3. 补爬: --crawl-missing 对未入库的演员抓取 JavDB 演员详情页
   （名称、别名、头像、作品数），下载头像写入 avatar_data 后
   以 is_favorite=1 插入 actors 表。
4. 补全: --refresh-incomplete 对已匹配但缺少头像/作品数的演员补充爬取。

用法:
    python3 mark_javdb_favorite_actors.py                     # 干跑，仅打印匹配结果
    python3 mark_javdb_favorite_actors.py --apply             # 标记收藏
    python3 mark_javdb_favorite_actors.py --apply --crawl-missing --refresh-incomplete
"""

import os
import re
import sys
import time
import random
import sqlite3
import argparse
from datetime import datetime

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import JAVDB_DIRECT_DOMAIN, get_javdb_base_url

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "media_library.db")
BASE_URL = get_javdb_base_url(False)  # 直连镜像域名

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

# ---------------------------------------------------------------------------
# JavDB 收藏的演員（两页合计 58 条，采集于 2026-09-19）
# 格式: (JavDB 演员 ID, 页面 title 中的全部名称逗号分隔)
# ---------------------------------------------------------------------------
FAVORITED_ACTORS = [
    # ---- 第 2 页（较早收藏） ----
    ("M4Q7", "明裏紬, 明里つむぎ"),
    ("vd5z", "坂道美琉, 坂道みる, miru"),
    ("NO1N", "椎名空, 椎名そら, 浅野奈都紀"),
    ("5Dya", "彩美旬果, あやみ旬果"),
    ("A5yq", "葵司, 葵つかさ"),
    ("WE4e", "篠田優, 篠田ゆう, 篠崎ゆう子, 中山ユウ, 高木早希, 桧山彩音, 橋本真紀, 松島智子, 秋元優子, 城田優子, 白井ゆう"),
    ("96AR", "君島美緒, 君島みお, 市井沙織, 京本かえで, 伊勢谷まり, 河合紗奈, 瞳ゆら, 門倉沙希"),
    ("Av2e", "三上悠亜, 三上悠亞, 鬼头桃菜"),
    ("KxPb", "涼森玲夢, 涼森れむ, 傻梦"),
    ("R2Vg", "波多野結衣, 酒井愛美"),
    ("kzx6", "田中檸檬, 田中レモン, 楓カレン, 楓花戀, 枫花恋"),
    ("pDeZ", "沖田杏梨, 観月あかね"),
    ("me7mM", "歌野こころ, 浅野こころ"),
    # ---- 第 1 页（最新收藏） ----
    ("W1AaK", "役野満里奈"),
    ("B8gBr", "宮西ひかる, 宮西あゆみ, 藤井知花"),
    ("RdZnn", "柚木れんか"),
    ("RngD", "沙月芽衣, さつき芽衣"),
    ("rPrR", "吉高寧寧, 吉高寧々"),
    ("GMB1D", "坂井美桜"),
    ("Vw2v3", "上羽絢"),
    ("65PmD", "神喜ミア"),
    ("eKnME", "三佳詩"),
    ("EvkJ", "河北彩花"),
    ("1G09", "有栖花緋, 有栖花あか, 凪ひかる, 汐世"),
    ("8VOMx", "田野憂"),
    ("wzK1", "蜜美杏, 藤井蘭々"),
    ("wVVz", "奧田咲, 奥田咲"),
    ("d78g", "田中寧寧, 田中ねね, 前田音緒"),
    ("Ng03", "愛音麻里亞, 愛音まりあ"),
    ("XW5X4", "紗弥佳"),
    ("BKMM", "大槻響, 大槻ひびき, 浜田絵梨, 綿貫沙織, 牧野里穂, 安藤絵里, 本庄芹那"),
    ("5R56", "篠田步美, 篠田あゆみ, 池田美和子, インセクター篠田"),
    ("A840", "椎名由奈, 椎名ゆな"),
    ("pRMq", "深田詠美, 深田えいみ, 天海こころ"),
    ("9D8vE", "福原みな"),
    ("YnwDp", "愛花未滿, 愛花あゆみ, 赤崎理奈, 柏木あゆみ, 相田亜由美, 五日市芽依"),
    ("XWm94", "兒玉七海"),
    ("RdZe8", "金松季歩"),
    ("p3Wye", "仁藤さや香"),
    ("VwvaX", "五条恋, 雛田真依羽, 結城ちか, 髙橋央"),
    ("658kM", "明日葉みつは"),
    ("yrRx0", "木村愛心"),
    # ---- 2026-10-02 新增（用户指定收藏；库内同人共 3 行：宝生リリー / 朝日しずく / 芽森しずく）----
    ("Q0YG", "宝生リリー, 寶生莉莉, 一花琴音, 芽森しずく, 芽森雫, 朝比奈るみな, 朝日奈るみな, 朝日しずく, 菊池凛, 仲里絵里子, 室生リリー"),
    ("J2Eb3", "滝川すみれ"),
    ("0Bw3", "吉根柚莉愛, 吉根ゆりあ, 吉永由梨"),
    ("Ewa2", "七森莉莉, 七ツ森りり, 松本鈴香, 葉月乃愛"),
    ("p392w", "葉月保奈美"),
    ("8BDW", "山岸逢花, 山岸あや花"),
    ("1KBW", "JULIA, 京香じゅりあ"),
    ("N0yx", "篠田優, 篠田ゆう, 篠崎ゆう子, 中山ユウ, 高木早希, 桧山彩音, 橋本真紀"),
    ("AzyRw", "水乃なのは"),
    ("mvmM", "齋藤亞美里, 斎藤あみり, あみり, 斉藤あみり"),
    ("zvK7", "小野六花"),
    ("bvWB", "櫻空桃, 桜空もも"),
    ("yERr", "美乃雀, 美乃すずめ"),
    ("PO5v", "佐山愛, 両津勘吉"),
    ("yAW", "武藤彩香, 武藤あやか, 武藤あやね, 神咲あやか"),
    ("A0Qy", "森澤佳奈, 森沢かな, 飯岡かなこ, 飯岡かな子, 沖田梨乃, 藤原遼子, 飯島恭子, 浅倉彩菜, かな子"),
    ("rmVrz", "宮本留衣"),
]


def load_db_actors(conn):
    """读取全部演员行，返回 list[dict]"""
    cur = conn.execute(
        "SELECT id, name, name_traditional, name_common, aliases, profile_url, "
        "is_favorite, avatar_url, avatar_data IS NOT NULL AND length(avatar_data)>0 AS has_avatar, "
        "movie_count FROM actors"
    )
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def title_names(title):
    return [n.strip() for n in title.split(",") if n.strip()]


def actor_javdb_id(profile_url):
    m = re.search(r"/actors/([A-Za-z0-9]+)/?$", profile_url or "")
    return m.group(1) if m else None


def alias_tokens(actor):
    tokens = set()
    for key in ("name", "name_traditional", "name_common"):
        if actor.get(key):
            tokens.add(actor[key].strip())
    for alias in (actor.get("aliases") or "").split(","):
        alias = alias.strip()
        if alias:
            tokens.add(alias)
    return tokens


def match_actors(db_actors):
    """对每个 JavDB 收藏演员进行匹配，返回 result 列表"""
    by_id = {}
    by_token = {}
    for a in db_actors:
        jid = actor_javdb_id(a.get("profile_url"))
        if jid:
            by_id.setdefault(jid, []).append(a)
        for tok in alias_tokens(a):
            by_token.setdefault(tok, []).append(a)

    results = []
    for jid, title in FAVORITED_ACTORS:
        names = title_names(title)
        hit = None
        match_type = None
        if jid in by_id:
            hit, match_type = by_id[jid], "profile_url"
        else:
            seen = {}
            for n in names:
                for a in by_token.get(n, []):
                    seen[a["id"]] = a
            if seen:
                hit, match_type = list(seen.values()), "name"
        results.append({
            "javdb_id": jid, "title": title, "names": names,
            "actors": hit, "match_type": match_type,
        })
    return results


def mark_favorite(conn, actor_ids):
    cur = conn.cursor()
    changed = 0
    for aid in actor_ids:
        cur.execute(
            "UPDATE actors SET is_favorite=1, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (aid,),
        )
        changed += cur.rowcount
    conn.commit()
    return changed


# ---------------------------------------------------------------------------
# 网络爬取（补全缺失演员）
# ---------------------------------------------------------------------------

def fetch_actor_page(actor_id, session=None):
    """抓取 JavDB 演员详情页 HTML，失败返回 None"""
    url = f"{BASE_URL}/actors/{actor_id}"
    sess = session or requests
    try:
        resp = sess.get(url, headers=REQUEST_HEADERS, timeout=30)
        resp.raise_for_status()
        if "actor-section-name" not in resp.text:
            print(f"  [WARN] {actor_id} 页面无演员区块（可能被验证拦截）")
            return None
        return resp.text
    except Exception as e:
        print(f"  [ERROR] 抓取 {url} 失败: {e}")
        return None


def parse_actor_page(html):
    """解析演员页: 名称列表 / 头像URL / 作品数 / 额外别名

    注意: 页面可能有多个 .section-meta（有别名时为「别名」span + 「N 部影片」span），
    作品数需在全部 section-meta 中匹配。
    """
    soup = BeautifulSoup(html, "html.parser")
    info = {"names": [], "avatar_url": "", "movie_count": None, "extra_aliases": []}
    el = soup.select_one(".actor-section-name")
    if el:
        info["names"] = [n.strip() for n in el.get_text().split(",") if n.strip()]
    for meta in soup.select(".section-meta"):
        text = meta.get_text().strip()
        m = re.search(r"(\d+)\s*部影片", text)
        if m:
            info["movie_count"] = int(m.group(1))
        elif text and text not in info["names"]:
            info["extra_aliases"].append(text)
    avatar = soup.select_one("span.avatar")
    if avatar and avatar.get("style"):
        m = re.search(r"url\(([^)]+)\)", avatar["style"])
        if m:
            info["avatar_url"] = m.group(1).strip("\"' ")
    return info


def download_avatar(avatar_url, session=None):
    """下载头像二进制，失败返回 None"""
    if not avatar_url:
        return None
    sess = session or requests
    headers = dict(REQUEST_HEADERS)
    headers["Referer"] = BASE_URL
    try:
        resp = sess.get(avatar_url, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.content
    except Exception as e:
        print(f"  [WARN] 头像下载失败 {avatar_url}: {e}")
        return None


def split_names(names):
    """按现有约定拆分: name/name_common 取日文原名, name_traditional 取繁体显示名"""
    if not names:
        return "未知", "未知", "未知", ""
    if len(names) == 1:
        n = names[0]
        return n, n, n, ""
    traditional = names[0]
    common = names[1]
    aliases = ", ".join(names[2:])
    return common, traditional, common, aliases


def upsert_missing_actor(conn, javdb_id, fallback_title, page_info, avatar_data, commit=True):
    """将缺失演员插入 actors 表（is_favorite=1），返回新行 id"""
    name, traditional, common, aliases = split_names(page_info.get("names") or title_names(fallback_title))
    extra = [a for a in page_info.get("extra_aliases", []) if a and a not in aliases.split(", ")]
    if extra:
        aliases = ", ".join(filter(None, [aliases] + extra))
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO actors (name, name_traditional, name_common, aliases, profile_url, "
        "avatar_url, avatar_data, movie_count, is_favorite, last_crawled_at, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
        (
            name, traditional, common, aliases,
            f"https://javdb.com/actors/{javdb_id}",
            page_info.get("avatar_url") or None,
            avatar_data,
            page_info.get("movie_count"),
            datetime.now().isoformat(),
        ),
    )
    if commit:
        conn.commit()
    return cur.lastrowid


def refresh_incomplete_actor(conn, actor, page_info, avatar_data, javdb_id=None, known_names=None):
    """补充缺失字段；返回更新的字段名列表（空列表表示无变化）"""
    cur = conn.cursor()
    sets, vals, changed_fields = [], [], []

    def add(field, expr, value):
        if expr not in sets:
            sets.append(expr)
            vals.append(value)
            changed_fields.append(field)

    if page_info.get("movie_count") and not actor.get("movie_count"):
        add("movie_count", "movie_count=?", page_info["movie_count"])
    if not actor.get("has_avatar"):
        if page_info.get("avatar_url"):
            add("avatar_url", "avatar_url=?", page_info["avatar_url"])
        if avatar_data:
            add("avatar_data", "avatar_data=?", avatar_data)
    elif javdb_id and actor.get("avatar_url"):
        # 修正历史合并脚本遗留的错误头像：头像 URL 指向其他演员档案，
        # 且本行演员名属于当前档案（页面名称或收藏清单中的别名）
        m = re.search(r"/avatars/[a-z0-9]{2}/([A-Za-z0-9]+)\.(?:jpg|png|webp)", actor["avatar_url"])
        names_ok = set((page_info.get("names") or []) + (known_names or []) + [actor["name"]])
        if m and m.group(1) != javdb_id and actor["name"] in names_ok:
            if page_info.get("avatar_url"):
                add("avatar_url", "avatar_url=?", page_info["avatar_url"])
            if avatar_data:
                add("avatar_data", "avatar_data=?", avatar_data)

    if not sets:
        return []
    sets.append("last_crawled_at=?")
    vals.append(datetime.now().isoformat())
    sets.append("updated_at=CURRENT_TIMESTAMP")
    vals.append(actor["id"])
    cur.execute(f"UPDATE actors SET {', '.join(sets)} WHERE id=?", vals)
    conn.commit()
    return changed_fields


def polite_sleep():
    time.sleep(random.uniform(1.0, 2.5))


def main():
    parser = argparse.ArgumentParser(description="同步 JavDB 收藏演员到本地数据库")
    parser.add_argument("--db-path", default=DB_PATH)
    parser.add_argument("--apply", action="store_true", help="实际写入 is_favorite=1")
    parser.add_argument("--crawl-missing", action="store_true", help="对未入库演员抓取详情并插入(is_favorite=1)")
    parser.add_argument("--refresh-incomplete", action="store_true", help="对已匹配但缺头像/作品数的演员补充爬取")
    args = parser.parse_args()

    conn = sqlite3.connect(args.db_path, timeout=30)
    db_actors = load_db_actors(conn)
    results = match_actors(db_actors)

    matched_ids, already, missing = [], [], []
    for r in results:
        if r["actors"]:
            for a in r["actors"]:
                if a["is_favorite"]:
                    already.append(a["id"])
                else:
                    matched_ids.append(a["id"])
            names = " / ".join(a["name"] for a in r["actors"])
            print(f"[匹配-{r['match_type']}] {r['javdb_id']:>6} {r['names'][0]:<10} -> DB#{r['actors'][0]['id']} {names}"
                  + ("  [已是收藏]" if all(a["is_favorite"] for a in r["actors"]) else ""))
        else:
            missing.append(r)
            print(f"[缺失]     {r['javdb_id']:>6} {r['names'][0]}")

    print("-" * 60)
    print(f"JavDB 收藏 {len(results)} 人 | 已在收藏 {len(set(already))} 人 | "
          f"待标记 {len(set(matched_ids))} 人 | 缺失 {len(missing)} 人")

    if args.apply and matched_ids:
        n = mark_favorite(conn, sorted(set(matched_ids)))
        print(f"已标记 {n} 名演员为收藏")
    elif not args.apply:
        print("(干跑模式，未写库；加 --apply 执行标记)")

    if missing and args.crawl_missing:
        print("-" * 60)
        http = requests.Session()
        for r in missing:
            print(f"[补爬] {r['javdb_id']} {r['names'][0]} ...")
            html = fetch_actor_page(r["javdb_id"], http)
            if not html:
                continue
            info = parse_actor_page(html)
            if not info["names"]:
                info["names"] = r["names"]
            avatar_data = download_avatar(info["avatar_url"], http)
            if avatar_data:
                print(f"  名称: {', '.join(info['names'])} | 作品数: {info['movie_count']} | 头像: {len(avatar_data)} 字节")
            else:
                print(f"  名称: {', '.join(info['names'])} | 作品数: {info['movie_count']} | 头像: 无")
            new_id = upsert_missing_actor(conn, r["javdb_id"], r["title"], info, avatar_data)
            print(f"  -> 已插入 DB#{new_id} (is_favorite=1)")
            polite_sleep()

    if args.refresh_incomplete:
        print("-" * 60)
        need = []
        seen_ids = set()
        for r in results:
            for a in (r["actors"] or []):
                if a["id"] in seen_ids:
                    continue
                seen_ids.add(a["id"])
                # 缺头像/作品数，或 JavDB 头像 URL 指向了其他演员档案
                m = re.search(r"/avatars/[a-z0-9]{2}/([A-Za-z0-9]+)\.(?:jpg|png|webp)", a.get("avatar_url") or "")
                wrong_avatar = bool(m and m.group(1) != r["javdb_id"] and a["name"] in r["names"])
                if not a["has_avatar"] or not a["movie_count"] or wrong_avatar:
                    need.append((r, a))
        print(f"缺少头像或作品数的已匹配演员: {len(need)} 人")
        http = requests.Session()
        for r, a in need:
            print(f"[补全] {r['javdb_id']} -> DB#{a['id']} {a['name']} ...")
            html = fetch_actor_page(r["javdb_id"], http)
            if not html:
                continue
            info = parse_actor_page(html)
            avatar_data = download_avatar(info["avatar_url"], http)
            changed = refresh_incomplete_actor(conn, a, info, avatar_data, r["javdb_id"], r["names"])
            print(f"  {'已更新: ' + ', '.join(changed)}" if changed else "  无需更新")
            polite_sleep()

    conn.close()
    print("完成。")


if __name__ == "__main__":
    main()
