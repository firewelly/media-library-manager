import os
import shutil


def find_source_root_for_path(cursor, file_path):
    try:
        cursor.execute("SELECT folder_path FROM folders WHERE is_active = 1")
        rows = cursor.fetchall()
        candidates = []
        for r in rows:
            fp = r[0]
            if file_path.startswith(fp.rstrip(os.sep) + os.sep) or file_path == fp:
                candidates.append(fp)
        if not candidates:
            return None
        candidates.sort(key=lambda p: len(p), reverse=True)
        return candidates[0]
    except Exception:
        return None


def compute_javsp_relative_subdir(source_root, video_dir):
    try:
        if source_root:
            rel = os.path.relpath(video_dir, source_root)
        else:
            rel = os.path.basename(video_dir)
        parts = rel.split(os.sep)
        if parts and parts[0] in ("#整理完成", "整理完成"):
            parts = parts[1:]
        return os.path.join(*parts) if parts else ""
    except Exception:
        return ""


def collect_javsp_sidecar_files(video_dir, base_num):
    files = []
    dirs = []
    cand = [
        os.path.join(video_dir, base_num + ".nfo"),
        os.path.join(video_dir, base_num + "-thumb.jpg"),
        os.path.join(video_dir, "poster.jpg"),
        os.path.join(video_dir, "fanart.jpg"),
    ]
    for p in cand:
        if os.path.exists(p) and os.path.isfile(p):
            files.append(p)
    ef = os.path.join(video_dir, "extrafanart")
    if os.path.exists(ef) and os.path.isdir(ef):
        dirs.append(ef)
    return files, dirs


def resolve_migration_conflict(cursor, dest_file_path, file_name, target_library_path):
    if not os.path.exists(dest_file_path):
        return dest_file_path, None
    try:
        cursor.execute(
            "SELECT id, file_path FROM videos WHERE file_name = ? AND file_path LIKE ?",
            (file_name, target_library_path.rstrip(os.sep) + os.sep + "%")
        )
        row = cursor.fetchone()
        if row and os.path.exists(row[1]):
            return None, os.path.dirname(row[1])
        base, ext = os.path.splitext(os.path.basename(dest_file_path))
        parent = os.path.dirname(dest_file_path)
        counter = 1
        new_path = dest_file_path
        while os.path.exists(new_path):
            new_name = f"{base}_{counter}{ext}"
            new_path = os.path.join(parent, new_name)
            counter += 1
        return new_path, None
    except Exception:
        base, ext = os.path.splitext(os.path.basename(dest_file_path))
        parent = os.path.dirname(dest_file_path)
        counter = 1
        new_path = dest_file_path
        while os.path.exists(new_path):
            new_name = f"{base}_{counter}{ext}"
            new_path = os.path.join(parent, new_name)
            counter += 1
        return new_path, None


def migrate_single(cursor, conn, old_file_path, video_id, target_library_path):
    try:
        video_dir = os.path.dirname(old_file_path)
        file_name = os.path.basename(old_file_path)
        base_num = os.path.splitext(file_name)[0]
        source_root = find_source_root_for_path(cursor, old_file_path)
        rel = compute_javsp_relative_subdir(source_root, video_dir)
        dest_dir = os.path.join(target_library_path, rel) if rel else target_library_path
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir, exist_ok=True)
        dest_file_path = os.path.join(dest_dir, file_name)
        final_path, existing_dir = resolve_migration_conflict(cursor, dest_file_path, file_name, target_library_path)
        side_files, side_dirs = collect_javsp_sidecar_files(video_dir, base_num)

        def move_side_file(src, dst_dir):
            name = os.path.basename(src)
            dst = os.path.join(dst_dir, name)
            if os.path.exists(dst):
                try:
                    if os.path.getsize(src) == os.path.getsize(dst):
                        return
                except Exception:
                    pass
                base, ext = os.path.splitext(name)
                c = 1
                new_name = name
                new_path = dst
                while os.path.exists(new_path):
                    new_name = f"{base}_{c}{ext}"
                    new_path = os.path.join(dst_dir, new_name)
                    c += 1
                dst = new_path
            shutil.move(src, dst)

        def move_side_dir(src_dir, dst_parent):
            name = os.path.basename(src_dir)
            dst_dir_path = os.path.join(dst_parent, name)
            if os.path.exists(dst_dir_path):
                c = 1
                new_name = name
                new_path = dst_dir_path
                while os.path.exists(new_path):
                    new_name = f"{name}_{c}"
                    new_path = os.path.join(dst_parent, new_name)
                    c += 1
                dst_dir_path = new_path
            shutil.move(src_dir, dst_dir_path)

        if existing_dir:
            for f in side_files:
                move_side_file(f, existing_dir)
            for d in side_dirs:
                move_side_dir(d, existing_dir)
            if os.path.exists(old_file_path):
                try:
                    os.remove(old_file_path)
                except Exception:
                    pass
            cursor.execute("DELETE FROM videos WHERE id = ?", (video_id,))
            conn.commit()
            return {
                "ok": True,
                "merged": True,
                "final_path": None,
                "dest_dir": existing_dir,
                "message": "merged"
            }

        shutil.move(old_file_path, final_path)
        for f in side_files:
            move_side_file(f, dest_dir)
        for d in side_dirs:
            move_side_dir(d, dest_dir)
        cursor.execute(
            "UPDATE videos SET file_path = ?, source_folder = ? WHERE id = ?",
            (final_path, dest_dir, video_id)
        )
        conn.commit()
        return {
            "ok": True,
            "merged": False,
            "final_path": final_path,
            "dest_dir": dest_dir,
            "message": "moved"
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

