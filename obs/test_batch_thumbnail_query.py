import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)
sys.argv[0] = os.path.join(parent_dir, "media_library.py")

from media_library import MediaLibrary


def has_table(cursor, table_name):
    cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    return cursor.fetchone() is not None


def build_candidates(app, only_missing):
    has_javdb_info = has_table(app.cursor, "javdb_info")
    has_javdb_tags = has_table(app.cursor, "javdb_tags")
    has_tags = has_table(app.cursor, "tags")
    has_video_actors = has_table(app.cursor, "video_actors")
    has_actors = has_table(app.cursor, "actors")

    conditions = []
    params = []

    if getattr(app, 'is_filtering', False):
        title_search_text = app.title_search_var.get().strip()
        if title_search_text:
            if has_javdb_info:
                conditions.append("(v.title LIKE ? OR v.file_name LIKE ? OR j.javdb_title LIKE ?)")
                title_search_param = f"%{title_search_text}%"
                params.extend([title_search_param, title_search_param, title_search_param])
            else:
                conditions.append("(v.title LIKE ? OR v.file_name LIKE ?)")
                title_search_param = f"%{title_search_text}%"
                params.extend([title_search_param, title_search_param])

        tag_search_text = app.tag_search_var.get().strip()
        if tag_search_text:
            tag_search_param = f"%{tag_search_text}%"
            if has_javdb_tags and has_tags:
                conditions.append("(v.tags LIKE ? OR EXISTS (SELECT 1 FROM javdb_tags jt JOIN tags t ON jt.tag_id = t.id WHERE jt.video_id = v.id AND t.name LIKE ?))")
                params.extend([tag_search_param, tag_search_param])
            else:
                conditions.append("v.tags LIKE ?")
                params.append(tag_search_param)

        actor_search_text = app.actor_search_var.get().strip()
        if actor_search_text:
            if has_video_actors and has_actors:
                conditions.append("EXISTS (SELECT 1 FROM video_actors va JOIN actors a ON va.actor_id = a.id WHERE va.video_id = v.id AND a.name LIKE ?)")
                actor_search_param = f"%{actor_search_text}%"
                params.append(actor_search_param)

        star_filter = app.star_filter.get()
        if star_filter > 0:
            conditions.append("v.stars = ?")
            params.append(star_filter)

        nas_filter = app.nas_filter.get()
        if nas_filter == "online":
            app.cursor.execute("SELECT DISTINCT source_folder FROM videos WHERE source_folder IS NOT NULL")
            all_video_folders = [row[0] for row in app.cursor.fetchall()]

            online_video_folders = []
            if os.name == "nt":
                app.refresh_folder_online_cache_async()
                with app.folder_cache_lock:
                    cached_status = dict(app.folder_online_cache)
                if cached_status:
                    for folder_path in all_video_folders:
                        if folder_path and cached_status.get(folder_path):
                            online_video_folders.append(folder_path)
                else:
                    online_video_folders = [p for p in all_video_folders if p]
            else:
                for folder_path in all_video_folders:
                    if os.path.exists(folder_path) and os.path.isdir(folder_path):
                        online_video_folders.append(folder_path)

            if online_video_folders:
                folder_conditions = []
                for folder_path in online_video_folders:
                    if os.name == "nt":
                        folder_conditions.append("REPLACE(v.source_folder, CHAR(92), '/') LIKE ?")
                        params.append(f"{folder_path.replace('\\\\', '/')}%")
                    else:
                        folder_conditions.append("v.source_folder LIKE ?")
                        params.append(f"{folder_path}%")
                conditions.append(f"({' OR '.join(folder_conditions)})")
            else:
                conditions.append("1 = 0")
        elif nas_filter == "offline":
            app.cursor.execute("SELECT DISTINCT source_folder FROM videos WHERE source_folder IS NOT NULL")
            all_video_folders = [row[0] for row in app.cursor.fetchall()]

            offline_video_folders = []
            for folder_path in all_video_folders:
                if not app.get_folder_online_status(folder_path):
                    offline_video_folders.append(folder_path)

            if offline_video_folders:
                folder_conditions = []
                for folder_path in offline_video_folders:
                    if os.name == "nt":
                        folder_conditions.append("REPLACE(v.source_folder, CHAR(92), '/') LIKE ?")
                        params.append(f"{folder_path.replace('\\\\', '/')}%")
                    else:
                        folder_conditions.append("v.source_folder LIKE ?")
                        params.append(f"{folder_path}%")
                conditions.append(f"({' OR '.join(folder_conditions)})")
            else:
                conditions.append("1 = 0")

        selected_folder_indices = app.folder_listbox.curselection()
        print(f"DEBUG: selected_folder_indices: {selected_folder_indices}")
        print(f"DEBUG: hasattr(app, 'folder_path_mapping'): {hasattr(app, 'folder_path_mapping')}")
        if hasattr(app, 'folder_path_mapping'):
            print(f"DEBUG: folder_path_mapping keys: {list(app.folder_path_mapping.keys())}")
        if selected_folder_indices and hasattr(app, 'folder_path_mapping'):
            selected_folder = app.folder_listbox.get(selected_folder_indices[0])
            if selected_folder != "全部" and selected_folder in app.folder_path_mapping:
                folder_path = app.folder_path_mapping[selected_folder]
                if folder_path:
                    if os.name == "nt":
                        conditions.append("(REPLACE(v.source_folder, CHAR(92), '/') LIKE ? OR REPLACE(v.file_path, CHAR(92), '/') LIKE ?)")
                        normalized_folder = folder_path.replace("\\", "/")
                        params.append(f"{normalized_folder}%")
                        params.append(f"{normalized_folder}%")
                    else:
                        conditions.append("(v.source_folder LIKE ? OR v.file_path LIKE ?)")
                        params.append(f"{folder_path}%")
                        params.append(f"{folder_path}%")

    conditions.append("(v.is_nas_online = 1 OR v.is_nas_online IS NULL)")
    ext_clause = """(
        (LOWER(COALESCE(v.file_path, '')) LIKE '%.mp4' AND LOWER(COALESCE(v.file_path, '')) NOT LIKE '/%.mp4') OR
        (LOWER(COALESCE(v.file_name, '')) LIKE '%.mp4' AND LENGTH(v.file_name) > 5) OR
        (LOWER(COALESCE(v.file_path, '')) LIKE '%.avi' AND LOWER(COALESCE(v.file_path, '')) NOT LIKE '/%.avi') OR
        (LOWER(COALESCE(v.file_name, '')) LIKE '%.avi' AND LENGTH(v.file_name) > 5) OR
        (LOWER(COALESCE(v.file_path, '')) LIKE '%.mkv' AND LOWER(COALESCE(v.file_path, '')) NOT LIKE '/%.mkv') OR
        (LOWER(COALESCE(v.file_name, '')) LIKE '%.mkv' AND LENGTH(v.file_name) > 5) OR
        (LOWER(COALESCE(v.file_path, '')) LIKE '%.rmvb' AND LOWER(COALESCE(v.file_path, '')) NOT LIKE '/%.rmvb') OR
        (LOWER(COALESCE(v.file_name, '')) LIKE '%.rmvb' AND LENGTH(v.file_name) > 6) OR
        (LOWER(COALESCE(v.file_path, '')) LIKE '%.mov' AND LOWER(COALESCE(v.file_path, '')) NOT LIKE '/%.mov') OR
        (LOWER(COALESCE(v.file_name, '')) LIKE '%.mov' AND LENGTH(v.file_name) > 5) OR
        (LOWER(COALESCE(v.file_path, '')) LIKE '%.wmv' AND LOWER(COALESCE(v.file_path, '')) NOT LIKE '/%.wmv') OR
        (LOWER(COALESCE(v.file_name, '')) LIKE '%.wmv' AND LENGTH(v.file_name) > 5) OR
        (LOWER(COALESCE(v.file_path, '')) LIKE '%.flv' AND LOWER(COALESCE(v.file_path, '')) NOT LIKE '/%.flv') OR
        (LOWER(COALESCE(v.file_name, '')) LIKE '%.flv' AND LENGTH(v.file_name) > 5) OR
        (LOWER(COALESCE(v.file_path, '')) LIKE '%.webm' AND LOWER(COALESCE(v.file_path, '')) NOT LIKE '/%.webm') OR
        (LOWER(COALESCE(v.file_name, '')) LIKE '%.webm' AND LENGTH(v.file_name) > 6) OR
        (LOWER(COALESCE(v.file_path, '')) LIKE '%.m4v' AND LOWER(COALESCE(v.file_path, '')) NOT LIKE '/%.m4v') OR
        (LOWER(COALESCE(v.file_name, '')) LIKE '%.m4v' AND LENGTH(v.file_name) > 5) OR
        (LOWER(COALESCE(v.file_path, '')) LIKE '%.ts' AND LOWER(COALESCE(v.file_path, '')) NOT LIKE '/%.ts') OR
        (LOWER(COALESCE(v.file_name, '')) LIKE '%.ts' AND LENGTH(v.file_name) > 4) OR
        (LOWER(COALESCE(v.file_path, '')) LIKE '%.m2ts' AND LOWER(COALESCE(v.file_path, '')) NOT LIKE '/%.m2ts') OR
        (LOWER(COALESCE(v.file_name, '')) LIKE '%.m2ts' AND LENGTH(v.file_name) > 6) OR
        (LOWER(COALESCE(v.file_path, '')) LIKE '%.mpg' AND LOWER(COALESCE(v.file_path, '')) NOT LIKE '/%.mpg') OR
        (LOWER(COALESCE(v.file_name, '')) LIKE '%.mpg' AND LENGTH(v.file_name) > 5) OR
        (LOWER(COALESCE(v.file_path, '')) LIKE '%.mpeg' AND LOWER(COALESCE(v.file_path, '')) NOT LIKE '/%.mpeg') OR
        (LOWER(COALESCE(v.file_name, '')) LIKE '%.mpeg' AND LENGTH(v.file_name) > 6)
    )"""
    conditions.append(ext_clause.strip())

    if hasattr(app, 'show_online_only') and app.show_online_only.get():
        app.cursor.execute("SELECT folder_path FROM folders WHERE is_active = 1")
        all_folders = [row[0] for row in app.cursor.fetchall()]

        online_folders = []
        if os.name == "nt":
            app.refresh_folder_online_cache_async()
            with app.folder_cache_lock:
                cached_status = dict(app.folder_online_cache)
            if cached_status:
                for folder_path in all_folders:
                    if folder_path and cached_status.get(folder_path):
                        online_folders.append(folder_path)
            else:
                online_folders = [p for p in all_folders if p]
        else:
            for folder_path in all_folders:
                if os.path.exists(folder_path) and os.path.isdir(folder_path):
                    online_folders.append(folder_path)

        if online_folders:
            folder_conditions = []
            for folder_path in online_folders:
                if os.name == "nt":
                    normalized_folder = folder_path.replace("\\", "/")
                    folder_conditions.append("(REPLACE(v.source_folder, CHAR(92), '/') LIKE ? OR REPLACE(v.file_path, CHAR(92), '/') LIKE ?)")
                    params.append(f"{normalized_folder}%")
                    params.append(f"{normalized_folder}%")
                else:
                    folder_conditions.append("(v.source_folder LIKE ? OR v.file_path LIKE ?)")
                    params.append(f"{folder_path}%")
                    params.append(f"{folder_path}%")
            conditions.append(f"({' OR '.join(folder_conditions)})")
        else:
            if os.name != "nt":
                return [], params, []
    else:
        if os.name == "nt":
            conditions.append("EXISTS (SELECT 1 FROM folders f WHERE f.is_active = 1 AND (REPLACE(v.source_folder, CHAR(92), '/') LIKE REPLACE(f.folder_path, CHAR(92), '/') || '%' OR REPLACE(v.file_path, CHAR(92), '/') LIKE REPLACE(f.folder_path, CHAR(92), '/') || '%'))")
        else:
            conditions.append("EXISTS (SELECT 1 FROM folders f WHERE f.is_active = 1 AND (v.source_folder LIKE f.folder_path || '%' OR v.file_path LIKE f.folder_path || '%'))")

    if only_missing:
        conditions.append("(v.thumbnail_data IS NULL OR v.thumbnail_data = '' OR length(v.thumbnail_data) = 0)")

    where_clause = f"WHERE {' AND '.join(conditions)}"
    if has_javdb_info:
        query = f"SELECT v.id, v.file_path, v.file_name, v.is_nas_online, v.thumbnail_data FROM videos v LEFT JOIN javdb_info j ON v.id = j.video_id {where_clause} ORDER BY v.file_name"
    else:
        query = f"SELECT v.id, v.file_path, v.file_name, v.is_nas_online, v.thumbnail_data FROM videos v {where_clause} ORDER BY v.file_name"
    app.cursor.execute(query, params)
    results = app.cursor.fetchall()
    return query, params, results


def main():
    app = MediaLibrary()
    app.root.withdraw()
    try:
        print("db_path:", app.db_path)
        if os.path.exists(app.db_path):
            print("db_size:", os.path.getsize(app.db_path))
        print("is_filtering:", getattr(app, 'is_filtering', None))
        if hasattr(app, 'show_online_only'):
            print("show_online_only:", app.show_online_only.get())
        if hasattr(app, 'nas_filter'):
            print("nas_filter:", app.nas_filter.get())

        app.cursor.execute("SELECT COUNT(*) FROM videos")
        total = app.cursor.fetchone()[0]
        app.cursor.execute("SELECT COUNT(*) FROM videos WHERE thumbnail_data IS NULL OR thumbnail_data = '' OR length(thumbnail_data) = 0")
        missing = app.cursor.fetchone()[0]
        app.cursor.execute("SELECT COUNT(*) FROM videos WHERE is_nas_online = 1 OR is_nas_online IS NULL")
        online_or_null = app.cursor.fetchone()[0]

        print("videos_total:", total)
        print("missing_thumbnail:", missing)
        print("online_or_null:", online_or_null)

        app.cursor.execute("SELECT folder_path FROM folders WHERE is_active = 1")
        active_folders = [row[0] for row in app.cursor.fetchall()]
        print("active_folders_count:", len(active_folders))
        print("active_folders:", active_folders[:10])
        
        if os.name == "nt":
            app.refresh_folder_online_cache_async()
            with app.folder_cache_lock:
                cached_status = dict(app.folder_online_cache)
            print("folder_online_cache_count:", len(cached_status))
            if cached_status:
                online_folders = [f for f in active_folders if cached_status.get(f)]
                print("online_folders_count:", len(online_folders))
                print("online_folders:", online_folders)

        app.cursor.execute("SELECT file_path, source_folder FROM videos WHERE thumbnail_data IS NULL OR thumbnail_data = '' OR length(thumbnail_data) = 0")
        missing_rows = app.cursor.fetchall()
        missing_paths = [(r[0] or "", r[1] or "") for r in missing_rows]
        exts = {".mp4", ".avi", ".mkv", ".rmvb", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".ts", ".m2ts", ".mpg", ".mpeg"}

        norm_folders = []
        for p in active_folders:
            if not p:
                continue
            norm_folders.append(p.replace("\\", "/"))

        matched = 0
        unmatched_samples = []
        ext_matched = 0
        ext_unmatched_samples = []
        for file_path, source_folder in missing_paths:
            norm_file_path = (file_path or "").replace("\\", "/")
            norm_source = (source_folder or "").replace("\\", "/")
            if any(norm_file_path.startswith(f) or norm_source.startswith(f) for f in norm_folders):
                matched += 1
            elif len(unmatched_samples) < 10:
                unmatched_samples.append((file_path, source_folder))
            ext = os.path.splitext(file_path)[1].lower()
            if ext in exts:
                ext_matched += 1
            elif len(ext_unmatched_samples) < 10:
                ext_unmatched_samples.append((file_path, ext))

        print("missing_paths_matched_active_folders:", matched)
        print("missing_paths_unmatched:", len(missing_paths) - matched)
        print("missing_paths_ext_matched:", ext_matched)
        print("missing_paths_ext_unmatched:", len(missing_paths) - ext_matched)
        if unmatched_samples:
            print("unmatched_samples:")
            for fp, sf in unmatched_samples:
                print("  -", fp, "|", sf)
        if ext_unmatched_samples:
            print("ext_unmatched_samples:")
            for fp, ext in ext_unmatched_samples:
                print("  -", fp, "| ext:", ext)

        ext_clause = """
            (
                LOWER(COALESCE(file_path, '')) LIKE '%.mp4' OR LOWER(COALESCE(file_name, '')) LIKE '%.mp4' OR
                LOWER(COALESCE(file_path, '')) LIKE '%.avi' OR LOWER(COALESCE(file_name, '')) LIKE '%.avi' OR
                LOWER(COALESCE(file_path, '')) LIKE '%.mkv' OR LOWER(COALESCE(file_name, '')) LIKE '%.mkv' OR
                LOWER(COALESCE(file_path, '')) LIKE '%.rmvb' OR LOWER(COALESCE(file_name, '')) LIKE '%.rmvb' OR
                LOWER(COALESCE(file_path, '')) LIKE '%.mov' OR LOWER(COALESCE(file_name, '')) LIKE '%.mov' OR
                LOWER(COALESCE(file_path, '')) LIKE '%.wmv' OR LOWER(COALESCE(file_name, '')) LIKE '%.wmv' OR
                LOWER(COALESCE(file_path, '')) LIKE '%.flv' OR LOWER(COALESCE(file_name, '')) LIKE '%.flv' OR
                LOWER(COALESCE(file_path, '')) LIKE '%.webm' OR LOWER(COALESCE(file_name, '')) LIKE '%.webm' OR
                LOWER(COALESCE(file_path, '')) LIKE '%.m4v' OR LOWER(COALESCE(file_name, '')) LIKE '%.m4v' OR
                LOWER(COALESCE(file_path, '')) LIKE '%.ts' OR LOWER(COALESCE(file_name, '')) LIKE '%.ts' OR
                LOWER(COALESCE(file_path, '')) LIKE '%.m2ts' OR LOWER(COALESCE(file_name, '')) LIKE '%.m2ts' OR
                LOWER(COALESCE(file_path, '')) LIKE '%.mpg' OR LOWER(COALESCE(file_name, '')) LIKE '%.mpg' OR
                LOWER(COALESCE(file_path, '')) LIKE '%.mpeg' OR LOWER(COALESCE(file_name, '')) LIKE '%.mpeg'
            )
        """
        app.cursor.execute(f"SELECT COUNT(*) FROM videos WHERE (thumbnail_data IS NULL OR thumbnail_data = '' OR length(thumbnail_data) = 0) AND {ext_clause}")
        missing_ext_sql = app.cursor.fetchone()[0]
        print("missing_ext_sql:", missing_ext_sql)

        query, params, videos = build_candidates(app, True)
        print("candidates:", len(videos))
        print("query_params:", params)
        print("query:", query)

        for row in videos[:20]:
            video_id, file_path, file_name, is_nas_online, thumbnail_data = row
            thumb_len = len(thumbnail_data) if thumbnail_data else 0
            print(video_id, file_path, file_name, is_nas_online, thumb_len)
    finally:
        app.root.destroy()


if __name__ == "__main__":
    main()
