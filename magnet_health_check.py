#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
磁力链接健康度检查（按番号）
============================
复用 collect_missing_magnets.py 的详情页解析(parse_detail)与优选评分(magnet_score)，
BASE 域名来自 compare_actor_filmography（javdb580.com，匿名可抓）。

健康度：对每个 info_hash 向多个公共 UDP tracker 发 BEP-15 scrape，
取各 tracker 返回的最大 seeder/leecher 数：
  seeder >= 3  → 健康
  seeder 1-2   → 可用（勉强）
  seeder 0     → 死链风险高

用法:
    python3 magnet_health_check.py PPT-032 IPVR-295 IPVR-256 LV-09
    python3 magnet_health_check.py SSIS-190 --tracker-timeout 8
"""

import base64
import random
import re
import socket
import struct
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from compare_actor_filmography import BASE
from collect_missing_magnets import parse_detail, magnet_score, UA

# 公共 UDP tracker（去重后并发查询，取最大值）
UDP_TRACKERS = [
    ("tracker.opentrackr.org", 1337),
    ("open.demonii.com", 1337),
    ("open.stealth.si", 80),
    ("tracker.torrent.eu.org", 451),
    ("exodus.desync.com", 6969),
    ("explodie.org", 6969),
    ("tracker.moeking.me", 6969),
]


def log(m):
    print(m, file=sys.stderr, flush=True)


def hash_to_bytes(h):
    """40位hex 或 32位base32 → 20字节"""
    h = h.strip().lower()
    if len(h) == 40:
        return bytes.fromhex(h)
    if len(h) == 32:
        return base64.b32decode(h.upper())
    return None


JAVBUS_BASE = "https://www.javbus.com"
JAVBUS_PROXIES = {"http": "socks5h://127.0.0.1:1080", "https": "socks5h://127.0.0.1:1080"}


def _size_to_mb(text):
    m = re.match(r"([\d.]+)\s*(GB|MB|TB|KB)", (text or "").strip(), re.I)
    if not m:
        return 0
    v, unit = float(m.group(1)), m.group(2).upper()
    return int(v * {"TB": 1024 * 1024, "GB": 1024, "MB": 1, "KB": 1 / 1024}[unit])


def javbus_magnets(code):
    """javbus 磁力（详情页表格由 AJAX 二次加载）：
    先取页面 var gid/uc/img，再请求 uncledatoolsbyajax.php，返回与 parse_detail 兼容的条目"""
    sess = requests.Session()
    out = []
    try:
        r = sess.get(f"{JAVBUS_BASE}/{code}", headers=UA, timeout=25, proxies=JAVBUS_PROXIES)
        if r.status_code != 200:
            return out
        gid = re.search(r"var\s+gid\s*=\s*['\"]?([0-9A-Za-z_-]+)", r.text)
        uc = re.search(r"var\s+uc\s*=\s*['\"]?([0-9A-Za-z_-]+)", r.text)
        img = re.search(r"var\s+img\s*=\s*['\"]([^'\"]+)", r.text)
        if not gid:
            return out
        url = (f"{JAVBUS_BASE}/ajax/uncledatoolsbyajax.php?gid={gid.group(1)}&lang=zh"
               f"&img={img.group(1) if img else ''}&uc={uc.group(1) if uc else 0}"
               f"&floor={random.randint(1, 999)}")
        h = dict(UA)
        h["Referer"] = f"{JAVBUS_BASE}/{code}"
        h["X-Requested-With"] = "XMLHttpRequest"
        r2 = sess.get(url, headers=h, timeout=25, proxies=JAVBUS_PROXIES)
        for blk in re.split(r"<tr\b", r2.text)[1:]:
            lm = re.search(r'href="(magnet:\?xt=urn:btih:[^"]+)"', blk, re.I)
            if not lm:
                continue
            link = lm.group(1).replace("&amp;", "&")
            nm = re.search(r"href=\"magnet:[^\"]+\">\s*([^<]+?)\s*</a>", blk, re.I)
            sizes = re.findall(r">\s*([\d.]+\s*(?:GB|MB|TB|KB))\s*<", blk, re.I)
            out.append({"link": link, "name": (nm.group(1).strip() if nm else code),
                        "tags": [], "size_mb": _size_to_mb(sizes[0]) if sizes else 0,
                        "source": "javbus"})
    except Exception as e:
        log(f"  javbus 抓取失败: {str(e)[:80]}")
    return out


def search_detail_url(sess, code):
    """javdb 搜索 → 番号精确匹配的第一个详情页 URL（番号在卡片内部 strong，不在 title 属性）"""
    r = sess.get(f"{BASE}/search?q={code}&f=all", headers=UA, timeout=25)
    target = code.replace("-", "").replace(" ", "").upper()
    for m in re.finditer(r'<a href="/v/([A-Za-z0-9]+)" class="box"[^>]*>(.*?)</a>', r.text, re.S):
        vid, block = m.group(1), m.group(2)
        # 去标签后整块文本匹配番号
        text = re.sub(r'<[^>]+>', ' ', block)
        norm = text.replace("-", "").replace(" ", "").upper()
        if target in norm:
            title_m = re.search(r'title="([^"]*)"', m.group(0))
            return f"{BASE}/v/{vid}", (title_m.group(1) if title_m else text.strip()[:60])
    return None, None


def _scrape_one_tracker(tracker, hashes, timeout):
    """单个 tracker 的 BEP-15 scrape，返回 {hash_hex: (seed, completed, leech)}"""
    host, port = tracker
    out = {}
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(timeout)
        try:
            tx = random.randint(0, 2 ** 31)
            s.sendto(struct.pack('>QII', 0x41727101980, 0, tx), (host, port))
            data, _ = s.recvfrom(2048)
            if len(data) < 16:
                return out
            # BEP15 应答: action(4) + transaction_id(4) + connection_id(8)
            conn_id = struct.unpack('>Q', data[8:16])[0]
            tx2 = random.randint(0, 2 ** 31)
            payload = struct.pack('>QII', conn_id, 2, tx2) + b''.join(hashes)
            s.sendto(payload, (host, port))
            data, _ = s.recvfrom(4096)
            if len(data) < 8 or struct.unpack('>I', data[:4])[0] != 2:
                return out
            n = (len(data) - 8) // 12
            for i in range(min(n, len(hashes))):
                seed, comp, leech = struct.unpack('>III', data[8 + i * 12: 20 + i * 12])
                out[hashes[i].hex()] = (seed, comp, leech)
        finally:
            s.close()
    except Exception:
        pass
    return out


def scrape_all(hashes, timeout=6, batch_size=30):
    """并发查询全部 tracker，每 hash 取最大 seeder/leecher。
    注意：UDP scrape 单包上限约 74 个 hash，超出会被静默截断（假 0 做种），必须分批。"""
    result = {h.hex(): (0, 0, 0) for h in hashes}
    batches = [hashes[i:i + batch_size] for i in range(0, len(hashes), batch_size)]
    for bi, bh in enumerate(batches, 1):
        if len(batches) > 1:
            log(f"  批次 {bi}/{len(batches)}（{len(bh)} hash）")
        with ThreadPoolExecutor(max_workers=len(UDP_TRACKERS)) as ex:
            futs = {ex.submit(_scrape_one_tracker, t, bh, timeout): t for t in UDP_TRACKERS}
            for fut in as_completed(futs):
                tr = fut.result()
                for h, (seed, comp, leech) in tr.items():
                    cur = result.get(h, (0, 0, 0))
                    result[h] = (max(cur[0], seed), max(cur[1], comp), max(cur[2], leech))
                if len(batches) == 1:
                    log(f"    tracker {futs[fut][0]}:{futs[fut][1]} 应答覆盖 {len(tr)}/{len(bh)} 个hash")
    return result


def health_label(seed):
    if seed >= 3:
        return "健康"
    if seed >= 1:
        return "可用"
    return "死链?"


def fmt_size(mb):
    if not mb:
        return "?"
    return f"{mb/1024:.1f}GB" if mb >= 1024 else f"{mb}MB"


def main():
    codes = [a for a in sys.argv[1:] if not a.startswith("--")]
    timeout = 6
    if "--tracker-timeout" in sys.argv:
        i = sys.argv.index("--tracker-timeout")
        if i + 1 < len(sys.argv):
            timeout = int(sys.argv[i + 1])
    do_copy = "--copy" in sys.argv
    available_only = "--available-only" in sys.argv
    do_check = "--check" in sys.argv or available_only
    codes = [c for c in codes if not c.isdigit()]
    if not codes:
        print(__doc__)
        sys.exit(1)

    sess = requests.Session()
    all_rows = []   # (code, title, magnet_dict, (seed,comp,leech))
    pending_hashes = {}
    for code in codes:
        log(f"=== {code} ===")
        title = ""
        magnets = []
        try:
            url, title = search_detail_url(sess, code)
        except Exception as e:
            log(f"  搜索失败: {str(e)[:80]}")
            url = None
        if url:
            log(f"  详情页: {url}")
            try:
                r = sess.get(url, headers=UA, timeout=25)
                solo, magnets = parse_detail(r.text)
                log(f"  javdb 磁力 {len(magnets)} 条" + ("（单体作品）" if solo else ""))
            except Exception as e:
                log(f"  详情页失败: {str(e)[:80]}")
        if not magnets:
            log(f"  javdb 无结果 → 回退 javbus")
            magnets = javbus_magnets(code)
            log(f"  javbus 磁力 {len(magnets)} 条")
            title = title or code
        for m in magnets:
            mm = re.search(r"btih:([a-fA-F0-9]{32,40})", m["link"])
            if not mm:
                continue
            h = mm.group(1).lower()
            hb = hash_to_bytes(h)
            if hb is None:
                continue
            pending_hashes[hb.hex()] = hb
            all_rows.append((code, title, m, h))
        time.sleep(1)

    if not all_rows:
        log("无磁力可检查")
        return

    stats = {}
    if do_check:
        log(f"\n=== 查询 {len(pending_hashes)} 个 info_hash 的种子健康度（{len(UDP_TRACKERS)} 个tracker）===")
        t0 = time.time()
        stats = scrape_all(list(pending_hashes.values()), timeout)
        log(f"tracker 查询完成，耗时 {time.time()-t0:.0f}s\n")

    # 输出报告（按番号分组，组内按 优选规则[+健康度] 排序）
    print("=" * 100)
    print(f"{'番号':<10} {'健康':<5} {'做种':>4} {'下栽':>4} {'体积':>8}  名称/标签")
    print("-" * 100)
    by_code = {}
    for row in all_rows:
        by_code.setdefault(row[0], []).append(row)
    for code, rows in by_code.items():
        def sort_key(r):
            seed = stats.get(r[3], (0, 0, 0))[0] if do_check else 0
            return (seed, magnet_score(r[2]))
        for code_, title, m, h in sorted(rows, key=sort_key, reverse=True):
            seed, comp, leech = stats.get(h, (0, 0, 0))
            tags = "/".join(m.get("tags") or [])[:30]
            name = (m.get("name") or "")[:45]
            hl = health_label(seed) if do_check else "-"
            print(f"{code_:<10} {hl:<5} {seed:>4} {leech:>4} {fmt_size(m.get('size_mb', 0)):>8}"
                  f"  {name}  [{tags}]")
        print("-" * 100)

    # 按用户偏好规则优选（每个番号一条）+ 复制到剪贴板
    if do_copy or available_only or True:
        picks = []
        for code, rows in by_code.items():
            cand = []
            for code_, title, m, h in rows:
                seed = stats.get(h, (0, 0, 0))[0] if do_check else 0
                if available_only and seed < 1:
                    continue
                cand.append((1 if seed >= 1 else 0, magnet_score(m), m, seed))
            if not cand:
                log(f"  [{code}] 无符合规则的磁力")
                continue
            cand.sort(key=lambda x: (x[0], x[1]), reverse=True)
            _, _, m, seed = cand[0]
            picks.append((code, m["link"], seed, m.get("name", ""), m.get("size_mb", 0), m.get("tags") or []))

        print()
        print("=" * 100)
        print(f"【按偏好规则优选】{len(picks)}/{len(by_code)} 个番号命中")
        print("规则: 中文字幕(-UC/-C/字幕标签) > 清晰度(1080p/FHD) > 体积(5-10GB最佳) > 无码/高清")
        print("-" * 100)
        for code, link, seed, name, sz, tags in picks:
            extra = f" 做种{seed}" if do_check else ""
            print(f"[{code}]{extra} {fmt_size(sz)} [{('/'.join(tags))[:20]}] {name[:40]}")
            print(f"  {link}")
        text = "\n".join(p[1] for p in picks)
        if do_copy:
            try:
                subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
                print()
                print(f"✅ 已复制 {len(picks)} 条链接到剪贴板")
            except Exception as e:
                log(f"[警告] 复制剪贴板失败: {e}")


if __name__ == "__main__":
    main()
