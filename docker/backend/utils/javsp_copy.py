import os
import shutil
from .file_utils import FileUtils


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


def resolve_copy_conflict(cursor, dest_file_path, file_name, target_library_path):
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


def copy_single(cursor, conn, old_file_path, video_id, target_library_path, progress_callback=None):
    """复制单个JavSP文件到目标媒体库，不删除源文件
    
    参数:
        cursor: 数据库游标
        conn: 数据库连接
        old_file_path: 源文件路径
        video_id: 视频ID
        target_library_path: 目标媒体库路径
        progress_callback: 进度回调函数 callback(copied_bytes, total_bytes)
        
    返回:
        dict: 包含操作结果的字典
    """
    try:
        # 首先获取原始视频的完整信息
        cursor.execute("SELECT * FROM videos WHERE id = ?", (video_id,))
        original_video = cursor.fetchone()
        if not original_video:
            return {"ok": False, "error": "原始视频记录不存在"}
        
        # 获取videos表的列信息
        cursor.execute("PRAGMA table_info(videos)")
        video_columns_info = cursor.fetchall()
        video_column_names = [col[1] for col in video_columns_info]  # 获取列名
        
        # 获取原始视频的所有相关数据
        # 获取演员关联
        cursor.execute("SELECT actor_id FROM video_actors WHERE video_id = ?", (video_id,))
        original_actors = [row[0] for row in cursor.fetchall()]
        
        # 获取JAVDB信息
        cursor.execute("SELECT * FROM javdb_info WHERE video_id = ?", (video_id,))
        original_javdb_info = cursor.fetchone()
        
        # 获取JAVDB标签关联
        if original_javdb_info:
            javdb_info_id = original_javdb_info[0]  # ID是第一个字段
            cursor.execute("SELECT tag_id FROM javdb_info_tags WHERE javdb_info_id = ?", (javdb_info_id,))
            original_javdb_tags = [row[0] for row in cursor.fetchall()]
        else:
            original_javdb_tags = []
        
        video_dir = os.path.dirname(old_file_path)
        file_name = os.path.basename(old_file_path)
        base_num = os.path.splitext(file_name)[0]
        source_root = find_source_root_for_path(cursor, old_file_path)
        rel = compute_javsp_relative_subdir(source_root, video_dir)
        dest_dir = os.path.join(target_library_path, rel) if rel else target_library_path
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir, exist_ok=True)
        dest_file_path = os.path.join(dest_dir, file_name)
        
        final_path, existing_dir = resolve_copy_conflict(cursor, dest_file_path, file_name, target_library_path)
        
        side_files, side_dirs = collect_javsp_sidecar_files(video_dir, base_num)

        def copy_side_file(src, dst_dir):
            """复制附属文件，如果目标文件已存在则重命名"""
            name = os.path.basename(src)
            dst = os.path.join(dst_dir, name)
            if os.path.exists(dst):
                try:
                    if os.path.getsize(src) == os.path.getsize(dst):
                        return  # 文件相同，跳过
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
            shutil.copy2(src, dst)  # 使用copy2保留文件元数据

        def copy_side_dir(src_dir, dst_parent):
            """复制附属目录，如果目标目录已存在则重命名"""
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
            shutil.copytree(src_dir, dst_dir_path)

        if existing_dir:
            # 目标位置已存在同名文件，只复制附属文件
            for f in side_files:
                copy_side_file(f, existing_dir)
            for d in side_dirs:
                copy_side_dir(d, existing_dir)
            
            # 在数据库中创建新记录，复制原始数据
            new_file_path = os.path.join(existing_dir, file_name)
            new_file_size = os.path.getsize(old_file_path)
            
            # 构建插入语句，复制除id、file_path、source_folder外的所有字段
            values = list(original_video)
            
            # 更新file_path、file_size、source_folder
            file_path_idx = video_column_names.index('file_path')
            file_size_idx = video_column_names.index('file_size')
            source_folder_idx = video_column_names.index('source_folder')
            
            values[file_path_idx] = new_file_path
            values[file_size_idx] = new_file_size
            values[source_folder_idx] = existing_dir
            
            # 构建插入语句
            placeholders = ', '.join(['?' for _ in values[1:]])  # 跳过id列
            insert_sql = f"INSERT INTO videos ({', '.join(video_column_names[1:])}) VALUES ({placeholders})"
            cursor.execute(insert_sql, values[1:])
            new_video_id = cursor.lastrowid
            
            # 复制演员关联
            for actor_id in original_actors:
                cursor.execute("INSERT OR IGNORE INTO video_actors (video_id, actor_id) VALUES (?, ?)", 
                             (new_video_id, actor_id))
            
            # 复制JAVDB信息和标签
            if original_javdb_info:
                # 获取javdb_info表的列信息
                cursor.execute("PRAGMA table_info(javdb_info)")
                javdb_columns_info = cursor.fetchall()
                javdb_column_names = [col[1] for col in javdb_columns_info]
                
                javdb_values = list(original_javdb_info)
                video_id_idx = javdb_column_names.index('video_id')
                javdb_values[video_id_idx] = new_video_id
                
                javdb_placeholders = ', '.join(['?' for _ in javdb_values[1:]])
                javdb_insert_sql = f"INSERT INTO javdb_info ({', '.join(javdb_column_names[1:])}) VALUES ({javdb_placeholders})"
                cursor.execute(javdb_insert_sql, javdb_values[1:])
                new_javdb_info_id = cursor.lastrowid
                
                # 复制JAVDB标签关联
                for tag_id in original_javdb_tags:
                    cursor.execute("INSERT OR IGNORE INTO javdb_info_tags (javdb_info_id, tag_id) VALUES (?, ?)", 
                                 (new_javdb_info_id, tag_id))
            
            conn.commit()
            
            return {
                "ok": True,
                "merged": True,
                "final_path": new_file_path,
                "new_video_id": new_video_id,
                "message": "copied_to_existing"
            }

        # 复制主文件
        if not FileUtils.copy_file_with_progress(old_file_path, final_path, callback=progress_callback):
            return {"ok": False, "error": f"复制文件失败: {old_file_path}"}
        
        # 复制附属文件
        for f in side_files:
            copy_side_file(f, dest_dir)
        for d in side_dirs:
            copy_side_dir(d, dest_dir)
        
        # 在数据库中创建新记录，复制原始数据
        new_file_size = os.path.getsize(final_path)
        
        # 构建插入语句，复制除id、file_path、source_folder外的所有字段
        values = list(original_video)
        
        # 更新file_path、file_size、source_folder
        file_path_idx = video_column_names.index('file_path')
        file_size_idx = video_column_names.index('file_size')
        source_folder_idx = video_column_names.index('source_folder')
        
        values[file_path_idx] = final_path
        values[file_size_idx] = new_file_size
        values[source_folder_idx] = dest_dir
        
        # 构建插入语句
        placeholders = ', '.join(['?' for _ in values[1:]])  # 跳过id列
        insert_sql = f"INSERT INTO videos ({', '.join(video_column_names[1:])}) VALUES ({placeholders})"
        cursor.execute(insert_sql, values[1:])
        new_video_id = cursor.lastrowid
        
        # 复制演员关联
        for actor_id in original_actors:
            cursor.execute("INSERT OR IGNORE INTO video_actors (video_id, actor_id) VALUES (?, ?)", 
                         (new_video_id, actor_id))
        
        # 复制JAVDB信息和标签
        if original_javdb_info:
            # 获取javdb_info表的列信息
            cursor.execute("PRAGMA table_info(javdb_info)")
            javdb_columns_info = cursor.fetchall()
            javdb_column_names = [col[1] for col in javdb_columns_info]
            
            javdb_values = list(original_javdb_info)
            video_id_idx = javdb_column_names.index('video_id')
            javdb_values[video_id_idx] = new_video_id
            
            javdb_placeholders = ', '.join(['?' for _ in javdb_values[1:]])
            javdb_insert_sql = f"INSERT INTO javdb_info ({', '.join(javdb_column_names[1:])}) VALUES ({javdb_placeholders})"
            cursor.execute(javdb_insert_sql, javdb_values[1:])
            new_javdb_info_id = cursor.lastrowid
            
            # 复制JAVDB标签关联
            for tag_id in original_javdb_tags:
                cursor.execute("INSERT OR IGNORE INTO javdb_info_tags (javdb_info_id, tag_id) VALUES (?, ?)", 
                             (new_javdb_info_id, tag_id))
        
        conn.commit()
        
        return {
            "ok": True,
            "merged": False,
            "final_path": final_path,
            "new_video_id": new_video_id,
            "message": "copied"
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}