#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成「麻豆傳媒映畫」演员浏览页（单文件 HTML，可离线打开）
=========================================================

数据来源:
  results/madou/series_report.json    每部影片（演员/标题/封面/体积/磁链数）
  results/madou/series_details.json   磁链（hash/dn/体积）

功能:
  · 按演员浏览（封面墙 + 作品数/可下载数）
  · 展开查看她的作品：番号、标题、日期、体积、磁链（点击复制 / 直接打开）
  · 勾选作品 → 底部汇总，可「复制选中磁链」「导出 txt」
  · 搜索、排序、只看可下载

用法:
    python3 make_madou_actors_html.py            # 生成 results/madou/actresses.html
"""

import os
import re
import sys
import json
import html
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE_DIR, "results", "madou")
REPORT = os.path.join(OUT_DIR, "series_report.json")
DETAILS = os.path.join(OUT_DIR, "series_details.json")
OUT_HTML = os.path.join(OUT_DIR, "actresses.html")


def score_magnet(m):
    """与项目其它脚本一致：中文字幕(UC>C) > 无码(U) > 体积(5-10GB 最佳) > 分辨率(≤4K)"""
    name = (m.get("dn") or "")
    up = name.upper()
    tags = " ".join(m.get("tags") or [])
    is_uc = bool(re.search(r"[-_.]UC\b|UC\.", up))
    has_sub = bool(is_uc or re.search(r"[-_.]C\b|C\.", up) or "字幕" in tags or "中字" in name)
    mb = m.get("size_mb") or 0
    gb = mb / 1024.0
    st = 3 if 5 <= gb <= 10 else (2 if 3 <= gb < 5 or 10 < gb <= 15 else (1 if gb <= 20 else 0))
    rt = 0 if "8K" in up else (3 if ("1080" in up or "FHD" in up) else 2)
    return (1 if has_sub else 0, 1 if is_uc else 0, st, rt, -(abs(mb - 7 * 1024)))


def build_payload():
    report = json.load(open(REPORT, encoding="utf-8"))
    details = json.load(open(DETAILS, encoding="utf-8"))
    # 已下载清单（由 organize_madou_downloads.py --apply 生成）
    downloaded = {}
    dl_path = os.path.join(OUT_DIR, "downloaded_codes.json")
    if os.path.exists(dl_path):
        try:
            downloaded = {re.sub(r"[-_\s]", "", k).upper(): v for k, v in
                          json.load(open(dl_path, encoding="utf-8")).items()}
        except Exception:
            downloaded = {}
    acts = {}
    works = []
    for r in report:
        code = r["code"]
        det = details.get(code) or {}
        mags = [m for m in (det.get("magnets") or []) if m.get("dn")]
        best = sorted(mags, key=score_magnet, reverse=True)[0] if mags else None
        cover = f"covers/{code}.jpg"
        w = {
            "downloaded": bool(downloaded.get(re.sub(r"[-_\s]", "", code).upper())),
            "code": code, "title": r.get("title", ""), "date": r.get("date", ""),
            "sizes": r.get("sizes_gb") or [], "cover": cover,
            "magnet": (f"magnet:?xt=urn:btih:{best['hash']}&dn={best['dn']}" if best else ""),
            "n": len(mags),
        }
        works.append(w)
        for a in (r.get("actresses") or []):
            acts.setdefault(a, []).append(code)
    # 演员 → 作品索引（作品按番号排序）
    by_code = {w["code"]: w for w in works}
    actresses = []
    for name, codes in acts.items():
        codes = sorted(set(codes))
        items = [by_code[c] for c in codes if c in by_code]
        actresses.append({
            "name": name, "total": len(items),
            "dl": sum(1 for x in items if x["magnet"]),
            "have": sum(1 for x in items if x["downloaded"]),
            "codes": codes,
        })
    # 已下载但未识别演员的作品 → 单独一组，便于在页面上看到
    orphans = [w["code"] for w in works if w["downloaded"] and not any(w["code"] in a["codes"] for a in actresses)]
    if orphans:
        actresses.insert(0, {"name": "『已下载·未识别演员』", "total": len(orphans),
                             "dl": sum(1 for c in orphans if by_code[c]["magnet"]),
                             "have": len(orphans), "codes": sorted(orphans)})
    actresses.sort(key=lambda a: (-a["dl"], -a["total"], a["name"]))
    return {"actresses": actresses, "works": by_code}


HTML_TMPL = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>麻豆傳媒映畫 · 演员浏览（决定下载）</title>
<style>
  :root{{--bg:#14161a;--card:#1d2026;--line:#2c313a;--fg:#e8eaed;--dim:#9aa3af;--acc:#ffb454;--ok:#4ade80;}}
  *{{box-sizing:border-box}}
  body{{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 -apple-system,"PingFang SC",Helvetica,Arial,sans-serif}}
  header{{position:sticky;top:0;z-index:9;background:#171a1f;border-bottom:1px solid var(--line);padding:10px 16px;display:flex;gap:10px;flex-wrap:wrap;align-items:center}}
  h1{{font-size:16px;margin:0 12px 0 0;font-weight:600}}
  input[type=search],select,button{{background:#22262e;color:var(--fg);border:1px solid var(--line);border-radius:8px;padding:6px 10px;font-size:13px}}
  button{{cursor:pointer}} button:hover{{border-color:var(--acc);color:var(--acc)}}
  .stat{{color:var(--dim);font-size:12px}}
  main{{padding:16px;display:grid;gap:14px;grid-template-columns:repeat(auto-fill,minmax(300px,1fr))}}
  .card{{background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden}}
  .h{{display:flex;justify-content:space-between;align-items:center;padding:10px 12px;cursor:pointer;gap:8px}}
  .name{{font-weight:600}} .badge{{font-size:11px;color:var(--dim)}}
  .badge b{{color:var(--ok)}}
  .wall{{display:grid;grid-template-columns:repeat(4,1fr);gap:2px;background:#000}}
  .wall img{{width:100%;aspect-ratio:3/4;object-fit:cover;display:block}}
  .works{{display:none;padding:8px 10px 12px;max-height:46vh;overflow:auto}}
  .card.open .works{{display:block}}
  .w{{display:flex;gap:8px;align-items:flex-start;padding:6px 0;border-top:1px solid #262b33}}
  .w img{{width:48px;aspect-ratio:3/4;object-fit:cover;border-radius:4px;flex:none;background:#000}}
  .w .meta{{flex:1;min-width:0}}
  .w .code{{font-weight:600;color:var(--acc);font-size:12px}}
  .w .t{{font-size:12px;color:#cfd6df;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
  .w .s{{font-size:11px;color:var(--dim)}}
  .w a.mag{{color:var(--ok);text-decoration:none;font-size:11px}}
  .w.disabled{{opacity:.45}}
  footer{{position:sticky;bottom:0;background:#171a1f;border-top:1px solid var(--line);padding:10px 16px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}}
  .pill{{background:#22262e;border:1px solid var(--line);border-radius:999px;padding:4px 10px;font-size:12px}}
</style></head><body>
<header>
  <h1>麻豆傳媒映畫 · 演员浏览</h1>
  <span class="stat" id="stat"></span>
  <input type="search" id="q" placeholder="搜索演员 / 番号 / 标题…" style="min-width:220px">
  <select id="sort">
    <option value="dl">按可下载数</option>
    <option value="total">按作品数</option>
    <option value="name">按名字</option>
  </select>
  <label class="stat"><input type="checkbox" id="onlydl"> 只看有磁链的</label>
  <label class="stat"><input type="checkbox" id="hidedl"> 隐藏已下载作品</label>
  <label class="stat"><input type="checkbox" id="onlyhave"> 只看已下载</label>
</header>
<main id="grid"></main>
<footer>
  <span class="pill" id="sel"></span>
  <button id="copysel">复制选中磁链</button>
  <button id="dlsel">导出选中 txt</button>
  <button id="clear">清空</button>
  <span class="stat">点击演员卡片展开作品；勾选＝决定下载</span>
</footer>
<script>
const DATA = {data};
const WORKS = DATA.works, ACTRESSES = DATA.actresses;
const sel = new Set();
const $ = s => document.querySelector(s);
function card(a) {{
  const hidedl = $('#hidedl').checked, onlyhave = $('#onlyhave').checked;
  const ws = a.codes.map(c => WORKS[c]).filter(Boolean)
      .filter(w => onlyhave ? w.downloaded : true)
      .filter(w => hidedl ? !w.downloaded : true);
  const covers = ws.slice(0, 4).map(w => `<img loading="lazy" src="${{w.cover}}" title="${{w.code}} ${{w.title}}" onerror="this.style.visibility='hidden'">`).join("");
  const rows = ws.map(w => {{
    const s = w.sizes && w.sizes.length ? w.sizes.map(x=>x+'GB').join(' / ') : '—';
    const mag = w.magnet ? `<a class="mag" href="${{w.magnet}}">磁链↗</a> <a class="mag" href="#" data-copy="${{w.magnet}}">复制</a>` : `<span class="s">无磁链</span>`;
    const done = w.downloaded ? `<span class="pill" style="background:#1e3a5f;border-color:#2563eb;color:#93c5fd">已下载</span>` : '';
    return `<div class="w ${{w.magnet&&!w.downloaded?'':'disabled'}}">
      <img loading="lazy" src="${{w.cover}}" onerror="this.style.visibility='hidden'">
      <div class="meta">
        <div class="code">${{w.code}} <span class="s">${{w.date||''}}</span> ${{done}}</div>
        <div class="t" title="${{esc(w.title)}}">${{esc(w.title)}}</div>
        <div class="s">体积: ${{s}} · 磁链 ${{w.n}} 条 · ${{w.downloaded?'（本地已有，无需重复下载）':mag}}</div>
      </div>
      ${{w.downloaded?'':`<input type="checkbox" data-code="${{w.code}}" ${{sel.has(w.code)?'checked':''}}>`}}
    </div>`;
  }}).join("");
  return `<div class="card" id="c_${{encodeURIComponent(a.name)}}">
    <div class="h"><span class="name">${{esc(a.name)}}</span>
      <span class="badge">作品 <b>${{a.total}}</b> · 可下载 <b>${{a.dl}}</b>${{a.have?` · <span style="color:#60a5fa">已有 ${{a.have}}</span>`:''}}</span></div>
    <div class="wall">${{covers}}</div>
    <div class="works">${{rows}}</div>
  </div>`;
}}
function esc(s){{return (s||'').replace(/[<>&"]/g, c=>({{'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;'}})[c]);}}
function render() {{
  const q = $('#q').value.trim().toLowerCase(), sort = $('#sort').value, onlydl = $('#onlydl').checked;
  const hidedl = $('#hidedl').checked, onlyhave = $('#onlyhave').checked;
  let list = ACTRESSES.filter(a => {{
    if (onlydl && !a.dl) return false;
    if (onlyhave && !a.have) return false;
    if (!q) return true;
    if (a.name.toLowerCase().includes(q)) return true;
    return a.codes.some(c => {{ const w = WORKS[c]; return w && ((w.code||'').toLowerCase().includes(q) || (w.title||'').toLowerCase().includes(q)); }});
  }});
  list.sort((x,y)=> sort==='name' ? x.name.localeCompare(y.name,'zh') : (sort==='total' ? y.total-x.total : y.dl-x.dl));
  $('#grid').innerHTML = list.map(card).join("");
  $('#stat').textContent = `演员 ${{list.length}} / ${{ACTRESSES.length}} 位`;
  updateSel();
}}
function updateSel() {{
  const codes = [...sel].filter(c => WORKS[c] && WORKS[c].magnet);
  const names = new Set(codes.map(c => (ACTRESSES.find(a=>a.codes.includes(c))||{{}}).name).filter(Boolean));
  $('#sel').textContent = `已选 ${{codes.length}} 部（${{names.size}} 位演员）`;
}}
function onToggle(el) {{
  const c = el.dataset.code, w = WORKS[c];
  if (el.checked && w && w.magnet) sel.add(c); else sel.delete(c);
  updateSel();
}}
document.addEventListener('change', e => {{
  if (e.target.matches('input[type=checkbox][data-code]')) onToggle(e.target);
}});
document.addEventListener('click', e => {{
  const copy = e.target.closest('[data-copy]');
  if (copy) {{ e.preventDefault(); navigator.clipboard.writeText(copy.dataset.copy); copy.textContent='已复制'; setTimeout(()=>copy.textContent='复制',1200); return; }}
  if (e.target.matches('input[type=checkbox][data-code]')) {{ onToggle(e.target); return; }}
  const h = e.target.closest('.h');
  if (h) h.parentElement.classList.toggle('open');
}});
document.addEventListener('keydown', e => {{
  if (e.key === 'Escape') {{ sel.clear(); render(); }}
}});
$('#q').addEventListener('input', render);
$('#sort').addEventListener('change', render);
$('#onlydl').addEventListener('change', render);
$('#hidedl').addEventListener('change', render);
$('#onlyhave').addEventListener('change', render);
$('#clear').addEventListener('click', ()=>{{ sel.clear(); render(); }});
function payload() {{
  const pick = [...sel].filter(c => WORKS[c] && WORKS[c].magnet).sort();
  return pick.map(c => `# ${{c}} ${{WORKS[c].title.slice(0,60)}}\\n${{WORKS[c].magnet}}`).join('\\n');
}}
$('#copysel').addEventListener('click', ()=> navigator.clipboard.writeText(payload()));
$('#dlsel').addEventListener('click', ()=>{{
  const blob = new Blob([payload()], {{type:'text/plain;charset=utf-8'}});
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
  a.download = 'madou_selected_magnets.txt'; a.click();
}});
render();
</script></body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT_HTML)
    args = ap.parse_args()
    payload = build_payload()
    html_out = HTML_TMPL.format(data=json.dumps(payload, ensure_ascii=False))
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html_out)
    n_a = len(payload["actresses"])
    n_w = len(payload["works"])
    n_dl = sum(1 for w in payload["works"].values() if w["magnet"])
    print(f"已生成: {args.out}")
    print(f"  演员 {n_a} 位 | 作品 {n_w} 部 | 其中有磁链 {n_dl} 部")
    print(f"  （封面使用相对路径 covers/，请保持该 HTML 与 covers/ 在同一目录）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
