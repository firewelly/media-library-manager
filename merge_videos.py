#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把两条视频记录合并成一条，自动判定「重复上传」还是「真分片」。

判定方式：两个文件各抽 1fps 灰度帧，在 ±60s 内搜索最佳时间偏移，取重合段平均像素差。
  - 平均像素差 <= 6/255 → 判为同一内容的两次上传（水印/时长不同）：
    不生成新文件——拼接只会得到重复画面；保留更长（更完整）的一条，
    标签取并集、星级取两者较高（--stars 覆盖），删除另一条记录并把文件移入废纸篓。
  - 平均像素差 > 阈值 → 判为分片：ffmpeg concat demuxer 无损拼接成一个新文件，
    写一条新记录（标签并集、星级、md5、时长、分辨率、缩略图），两条旧记录删除、源文件移入废纸篓。

用法：
  python3 merge_videos.py --ids 55609 54793 [--stars 3] [--name 输出名] [--dry-run] [--keep-sources]

删除前会先把被删记录导出到 .merge_backup_<时间戳>.json（不含缩略图 BLOB）。
"""
import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "media_library.db")
FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")

SAME_CONTENT_DIFF = 6.0      # 重合段平均像素差阈值（0-255），低于此判为同一内容
SAMPLE_W, SAMPLE_H = 120, 68
MAX_OFFSET = 60              # 偏移搜索范围（秒）
MIN_OVERLAP = 10             # 参与判定的最短重合秒数
DURATION_TOL = 2.0           # 拼接后时长允许误差（秒）
THUMB_SEEK = "00:00:10"      # 缩略图取帧位置，与 GUI 生成封面一致


def log(msg=""):
    print(msg, flush=True)


def die(msg):
    log(f"错误: {msg}")
    sys.exit(1)


# ---------------------------------------------------------------- 探测与比较
def probe(path):
    """返回 {duration, size, width, height, has_audio}。"""
    if not os.path.exists(path):
        die(f"文件不存在: {path}")
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration",
         "-show_entries", "stream=codec_type,width,height",
         "-of", "json", path],
        capture_output=True, text=True)
    if out.returncode != 0:
        die(f"ffprobe 失败: {path}\n{out.stderr.strip()}")
    info = json.loads(out.stdout)
    dur = float(info.get("format", {}).get("duration") or 0)
    w = h = 0
    has_audio = False
    for st in info.get("streams", []):
        if st.get("codec_type") == "video" and not w:
            w, h = st.get("width", 0), st.get("height", 0)
        if st.get("codec_type") == "audio":
            has_audio = True
    return {"duration": dur, "size": os.path.getsize(path), "width": w,
            "height": h, "has_audio": has_audio}


def frames(path):
    """抽 1fps 灰度帧，返回 (秒数, h, w) 的 int16 数组。"""
    import numpy as np
    res = subprocess.run(
        [FFMPEG, "-v", "error", "-i", path, "-vf", f"fps=1,scale={SAMPLE_W}:{SAMPLE_H}",
         "-f", "rawvideo", "-pix_fmt", "gray", "-"],
        capture_output=True)
    if res.returncode != 0:
        die(f"抽帧失败: {path}")
    data = np.frombuffer(res.stdout, dtype=np.uint8)
    n = len(data) // (SAMPLE_W * SAMPLE_H)
    return data[:n * SAMPLE_W * SAMPLE_H].reshape(n, SAMPLE_H, SAMPLE_W).astype(np.int16)


def align(fa, fb):
    """在 ±MAX_OFFSET 秒内找到最佳对齐；返回 (offset, mean_diff, overlap_secs)。

    offset > 0 表示 a 的内容从 b 的第 offset 秒开始（a 被 b 包含）。
    """
    import numpy as np
    best = None
    for k in range(-MAX_OFFSET, MAX_OFFSET + 1):
        if k >= 0:
            a, b = fa[:len(fa) - k], fb[k:]
        else:
            a, b = fa[-k:], fb[:len(fb) + k]
        n = min(len(a), len(b))
        if n < MIN_OVERLAP:
            continue
        d = float(np.abs(a[:n] - b[:n]).mean())
        if best is None or d < best[1]:
            best = (k, d, n)
    return best


def md5_of(path):
    import hashlib
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def make_thumbnail(path, out_jpg):
    res = subprocess.run(
        [FFMPEG, "-v", "error", "-y", "-ss", THUMB_SEEK, "-i", path,
         "-frames:v", "1", "-q:v", "6", out_jpg],
        capture_output=True, text=True)
    return res.returncode == 0 and os.path.exists(out_jpg)


# ---------------------------------------------------------------- 数据库
def connect():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def fetch_video(cur, vid):
    cur.execute("SELECT * FROM videos WHERE id = ?", (vid,))
    row = cur.fetchone()
    if row is None:
        die(f"数据库里没有 id={vid} 的记录")
    return row


def tag_list(tags):
    return [t.strip() for t in (tags or "").split(",") if t.strip()]


def merge_tags(first, second):
    """并集，保持 first 原有顺序，再追加 second 的新标签。"""
    out = []
    for t in tag_list(first) + tag_list(second):
        if t not in out:
            out.append(t)
    return ", ".join(out)


def folder_type(cur, folder_path):
    cur.execute("SELECT folder_type FROM folders WHERE folder_path = ?", (folder_path,))
    row = cur.fetchone()
    return row[0] if row else "local"


def row_to_dict(row, drop_blobs=True):
    d = {k: row[k] for k in row.keys()}
    if drop_blobs:
        for k, v in list(d.items()):
            if isinstance(v, (bytes, bytearray, memoryview)):
                d[k] = f"<blob {len(bytes(v))} bytes>"
    return d


def backup(records, plan, files_trashed):
    path = os.path.join(
        BASE_DIR, f".merge_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"时间": datetime.now().isoformat(timespec="seconds"),
                   "数据库": DB_PATH, "操作": plan,
                   "被删/被改记录": records,
                   "移入废纸篓的文件": files_trashed,
                   "恢复提示": "被删记录可从本文件重建：INSERT 回 videos 表；文件在 macOS 废纸篓中可还原"},
                  f, ensure_ascii=False, indent=2)
    return path


def move_related_rows(cur, drop_id, keep_id):
    """把被删记录的关联数据迁移到保留记录上（无关联时什么都不做）。"""
    moved = []
    cur.execute("UPDATE OR IGNORE video_actors SET video_id = ? WHERE video_id = ?",
                (keep_id, drop_id))
    cur.execute("DELETE FROM video_actors WHERE video_id = ?", (drop_id,))
    if cur.rowcount:
        moved.append(f"video_actors {cur.rowcount} 条并入")

    cur.execute("SELECT id FROM javdb_info WHERE video_id = ?", (keep_id,))
    keep_info = cur.fetchone()
    cur.execute("SELECT id FROM javdb_info WHERE video_id = ?", (drop_id,))
    drop_info = cur.fetchone()
    if drop_info:
        if keep_info:
            cur.execute("SELECT id FROM javdb_info_tags WHERE javdb_info_id = ?",
                        (drop_info[0],))
            ids = [r[0] for r in cur.fetchall()]
            for iid in ids:
                cur.execute("DELETE FROM javdb_info_tags WHERE id = ?", (iid,))
            cur.execute("DELETE FROM javdb_info WHERE id = ?", (drop_info[0],))
            moved.append("javdb_info 保留方已有，丢弃被删方")
        else:
            cur.execute("UPDATE javdb_info SET video_id = ? WHERE video_id = ?",
                        (keep_id, drop_id))
            moved.append("javdb_info 迁移到保留方")
    return moved


def trash_file(path, enabled):
    if not enabled:
        log(f"    --keep-sources：保留源文件 {os.path.basename(path)}")
        return False
    try:
        from send2trash import send2trash
        send2trash(path)
        log(f"    已移入废纸篓: {os.path.basename(path)}")
        return True
    except Exception as e:  # noqa: BLE001 - 回收站失败不该中断已完成的合并
        log(f"    警告: 移入废纸篓失败（{e}），文件仍在原位: {path}")
        return False


# ---------------------------------------------------------------- 两种合并
def do_duplicate_merge(conn, cur, rows, stats, args):
    """同一内容的两次上传：保留更完整的一条。"""
    first, second = rows
    keep, drop = (first, second) if stats["duration_a"] >= stats["duration_b"] \
        else (second, first)
    log(f"  判定: 同一内容重复上传（重合段平均像素差 {stats['diff']:.2f}/255，"
        f"重合 {stats['overlap']} 秒）")
    log(f"  保留: id={keep['id']} {keep['file_name']}（{int(stats['keep_dur'])} 秒）")
    log(f"  删除: id={drop['id']} {drop['file_name']}（{int(stats['drop_dur'])} 秒）")

    tags = merge_tags(keep["tags"], drop["tags"])
    stars = args.stars if args.stars is not None else max(keep["stars"] or 0,
                                                         drop["stars"] or 0)
    log(f"  标签: {drop['tags'] or '（空）'} + {keep['tags'] or '（空）'} → {tags}")
    log(f"  星级: {keep['stars']} / {drop['stars']} → {stars}")
    log(f"  描述: 沿用保留方（两段描述同场景，未拼接）")
    log(f"  文件: 保留原位，不生成新文件")

    if args.dry_run:
        return {"plan": "duplicate", "keep": keep["id"], "drop": drop["id"],
                "tags": tags, "stars": stars}

    related = move_related_rows(cur, drop["id"], keep["id"])
    for m in related:
        log(f"    关联数据: {m}")
    cur.execute("UPDATE videos SET tags = ?, stars = ?, updated_at = CURRENT_TIMESTAMP "
                "WHERE id = ?", (tags, stars, keep["id"]))
    cur.execute("DELETE FROM videos WHERE id = ?", (drop["id"],))
    cur.execute("SELECT * FROM videos WHERE id = ?", (keep["id"],))
    after = row_to_dict(cur.fetchone())
    conn.commit()

    trashed = []
    if trash_file(drop["file_path"], not args.keep_sources):
        trashed.append(drop["file_path"])
    bak = backup({"被删": row_to_dict(drop), "更新后": after,
                  "更新前": row_to_dict(keep)},
                 {"mode": "duplicate", "keep": keep["id"], "drop": drop["id"]}, trashed)
    return {"plan": "duplicate", "keep": keep["id"], "drop": drop["id"],
            "tags": tags, "stars": stars, "backup": bak}


def do_concat_merge(conn, cur, rows, args):
    """内容不同：无损拼成一个新文件。"""
    first, second = rows
    parts = [first["file_path"], second["file_path"]]
    ext = os.path.splitext(first["file_path"])[1] or ".mp4"
    if args.name:
        out_name = args.name if os.path.splitext(args.name)[1] else args.name + ext
    else:
        out_name = f"{first['title'] or os.path.splitext(first['file_name'])[0]}＋" \
                   f"{second['title'] or os.path.splitext(second['file_name'])[0]}{ext}"
    out_name = out_name[:200] + ext if len(out_name) > 200 and not args.name else out_name
    out_dir = os.path.dirname(first["file_path"])
    out_path = os.path.join(out_dir, out_name)
    tags = merge_tags(first["tags"], second["tags"])
    stars = args.stars if args.stars is not None else max(first["stars"] or 0,
                                                         second["stars"] or 0)

    log(f"  判定: 内容不同 → 无损拼接（concat demuxer -c copy）")
    for r, p in zip(rows, parts):
        log(f"    分片: id={r['id']} {os.path.basename(p)}")
    log(f"  输出: {out_path}")
    log(f"  标签: {first['tags'] or '（空）'} + {second['tags'] or '（空）'} → {tags}")
    log(f"  星级: {first['stars']} / {second['stars']} → {stars}")

    if os.path.exists(out_path):
        die(f"输出文件已存在，先改名或清理: {out_path}")
    cur.execute("SELECT id FROM videos WHERE file_path = ?", (out_path,))
    if cur.fetchone():
        die(f"输出路径已在数据库中: {out_path}")

    if args.dry_run:
        return {"plan": "concat", "output": out_path, "tags": tags, "stars": stars}

    # 1) 拼接
    list_file = os.path.join(tempfile.mkdtemp(prefix="merge_"), "concat.txt")
    with open(list_file, "w", encoding="utf-8") as f:
        for p in parts:
            f.write("file '%s'\n" % p.replace("'", "'\\''"))
    tmp_out = out_path + ".partial"
    res = subprocess.run(
        [FFMPEG, "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", list_file,
         "-c", "copy", "-movflags", "+faststart", tmp_out],
        capture_output=True, text=True)
    if res.returncode != 0 or not os.path.exists(tmp_out):
        die(f"ffmpeg 拼接失败:\n{res.stderr.strip()}")

    # 2) 校验：时长、流、大小
    sum_dur = sum(probe(p)["duration"] for p in parts)
    got = probe(tmp_out)
    log(f"    拼接结果: {got['duration']:.1f} 秒（分片合计 {sum_dur:.1f} 秒），"
        f"{got['width']}x{got['height']}，音频 {'有' if got['has_audio'] else '无'}")
    if abs(got["duration"] - sum_dur) > DURATION_TOL:
        os.unlink(tmp_out)
        die(f"拼接时长异常（差 {abs(got['duration'] - sum_dur):.1f} 秒），已丢弃输出")
    if not got["has_audio"]:
        log("    警告: 拼接结果没有音频流")

    os.replace(tmp_out, out_path)

    # 3) 元数据
    thumb = os.path.join(tempfile.mkdtemp(prefix="merge_thumb_"), "t.jpg")
    thumb_blob = None
    if make_thumbnail(out_path, thumb):
        with open(thumb, "rb") as f:
            thumb_blob = f.read()
    created = min([r["file_created_time"] for r in rows if r["file_created_time"]]
                  or [datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    ftype = folder_type(cur, out_dir)

    # 4) 写新记录 + 删旧记录
    cur.execute(
        """INSERT INTO videos
           (file_path, file_name, file_size, md5_hash, title, description, genre,
            stars, rating, tags, nas_path, is_nas_online, duration, resolution,
            file_created_time, source_folder, thumbnail_data)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (out_path, out_name, got["size"], md5_of(out_path),
         os.path.splitext(out_name)[0], first["description"], first["genre"],
         stars, first["rating"], tags,
         out_path if ftype == "nas" else None, 1,
         int(round(got["duration"])), f"{got['width']}x{got['height']}",
         created, out_dir, thumb_blob))
    new_id = cur.lastrowid
    for r in rows:
        move_related_rows(cur, r["id"], new_id)
        cur.execute("DELETE FROM videos WHERE id = ?", (r["id"],))
    cur.execute("SELECT * FROM videos WHERE id = ?", (new_id,))
    after = row_to_dict(cur.fetchone())
    conn.commit()
    log(f"    新记录 id={new_id}，已删除旧记录 {[r['id'] for r in rows]}")

    trashed = []
    for p in parts:
        if trash_file(p, not args.keep_sources):
            trashed.append(p)
    bak = backup({"新记录": after, "已删": [row_to_dict(r) for r in rows]},
                 {"mode": "concat", "new_id": new_id,
                  "deleted": [r["id"] for r in rows]}, trashed)
    return {"plan": "concat", "new_id": new_id, "output": out_path,
            "deleted": [r["id"] for r in rows], "tags": tags, "stars": stars,
            "duration": int(round(got["duration"])), "backup": bak}


def main():
    ap = argparse.ArgumentParser(description="把两条视频记录合并成一条（自动判定重复/分片）")
    ap.add_argument("--ids", nargs=2, type=int, required=True, metavar=("ID1", "ID2"),
                    help="要合并的两条视频记录 id")
    ap.add_argument("--stars", type=int, default=None, help="合并后的星级（默认取两者较高）")
    ap.add_argument("--name", default=None, help="拼接模式下的输出文件名（默认两标题相加）")
    ap.add_argument("--dry-run", action="store_true", help="只打印计划，不改文件与数据库")
    ap.add_argument("--keep-sources", action="store_true", help="保留源文件（不移入废纸篓）")
    args = ap.parse_args()

    for tool in (FFMPEG, FFPROBE):
        if not tool:
            die("找不到 ffmpeg/ffprobe")
    if not os.path.exists(DB_PATH):
        die(f"找不到数据库 {DB_PATH}")

    conn = connect()
    cur = conn.cursor()
    rows = [fetch_video(cur, vid) for vid in args.ids]
    for r in rows:
        if not r["file_path"] or not os.path.exists(r["file_path"]):
            die(f"文件缺失，无法合并: id={r['id']} {r['file_path']}")

    log(f"合并 {' + '.join(str(v) for v in args.ids)}"
        f"{'（dry-run，不做任何改动）' if args.dry_run else ''}")
    for r in rows:
        p = probe(r["file_path"])
        log(f"  id={r['id']} {r['file_name']}\n"
            f"      {p['duration']:.1f} 秒 / {p['size'] / 1048576:.1f} MB / "
            f"{p['width']}x{p['height']} / 星级 {r['stars']} / 标签 {r['tags'] or '（空）'}")

    log("  抽帧比较中…")
    fa, fb = frames(rows[0]["file_path"]), frames(rows[1]["file_path"])
    best = align(fa, fb)
    if best is None:
        die("两段太短或无法对齐，放弃判定")
    offset, diff, overlap = best
    dur_a, dur_b = (len(fa), len(fb))
    log(f"  对齐: 偏移 {offset} 秒，重合 {overlap} 秒，平均像素差 {diff:.2f}/255 "
        f"（同一内容阈值 ≤ {SAME_CONTENT_DIFF}）")

    if diff <= SAME_CONTENT_DIFF:
        result = do_duplicate_merge(conn, cur, rows, {
            "diff": diff, "overlap": overlap,
            "duration_a": dur_a, "duration_b": dur_b,
            "keep_dur": max(dur_a, dur_b), "drop_dur": min(dur_a, dur_b)}, args)
    else:
        result = do_concat_merge(conn, cur, rows, args)

    if args.dry_run:
        log("\n[dry-run] 未改动数据库与文件。")
    else:
        log(f"\n完成。备份: {result.get('backup')}")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
