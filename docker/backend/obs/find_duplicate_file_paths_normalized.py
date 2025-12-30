import sqlite3
import unicodedata
from collections import defaultdict

DB_PATH = "media_library.db"

def normalize_path(path: str) -> str:
    # Trim whitespace, normalize Unicode to NFC, and case-fold for robust comparison
    if path is None:
        return ""
    p = path.strip()
    # Normalize to NFC to combine any decomposed characters (e.g., す + ゙ -> ず)
    p = unicodedata.normalize("NFC", p)
    # Case-fold to avoid case differences (mostly useful on case-insensitive filesystems)
    p = p.casefold()
    return p

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT id, file_path FROM videos WHERE file_path IS NOT NULL")
    rows = cur.fetchall()

    groups = defaultdict(list)
    for r in rows:
        fid = r["id"]
        fp = r["file_path"]
        norm = normalize_path(fp)
        groups[norm].append((fid, fp))

    # Collect duplicates
    duplicates = {norm: items for norm, items in groups.items() if len(items) > 1}

    print(f"Total records: {len(rows)}")
    print(f"Duplicate normalized file_path groups: {len(duplicates)}")

    # Show up to 50 groups with their members
    count = 0
    for norm, items in sorted(duplicates.items(), key=lambda kv: len(kv[1]), reverse=True):
        print("\n=== Duplicate Group ===")
        print(f"Normalized path: {norm}")
        print(f"Count: {len(items)}")
        for fid, fp in items:
            print(f"- id={fid} | file_path={fp}")
        count += 1
        if count >= 50:
            break

    # Specifically check the path user mentioned
    target = "/Volumes/app/usr/美乃すずめ/DLDSS-173 與絕對不能沉迷的上司最棒愛人沈溺在融化般不倫性愛 美乃雀/DLDSS-173.mp4"
    norm_target = normalize_path(target)
    print("\n=== Specific Path Check ===")
    print(f"Target: {target}")
    print(f"Normalized: {norm_target}")
    matches = groups.get(norm_target, [])
    print(f"Matched records: {len(matches)}")
    for fid, fp in matches:
        print(f"- id={fid} | file_path={fp}")

if __name__ == "__main__":
    main()