#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一次性快速导入脚本：从指定CSV读取MD5与文件信息，导入到媒体库数据库

特性：
 - 仅针对指定根路径下的文件（默认：/Volumes/Video/usr、/Volumes/Video/Video2、/Volumes/Video/JAV）
 - 路径映射：将CSV中的/volume1/映射为/Volumes/
 - 去重依据：文件路径精确匹配，辅以同目录中文件名匹配
 - 过滤：忽略隐藏文件（以.或._开头）、#recycle内文件、以及小于10MB的文件
 - MD5不做计算，直接使用CSV中的值

CSV列要求：文件名,文件路径,大小(字节),MD5值
CSV示例参见：/Users/firewell/Library/CloudStorage/OneDrive-个人/bioinfo/media/video_md5.csv
"""

import os
import csv
import sqlite3
from pathlib import Path
from datetime import datetime
import logging


# 可配置参数
DB_PATH = os.path.join(os.path.dirname(__file__), 'media_library.db')
CSV_PATH = os.path.join(os.path.dirname(__file__), 'video_md5.csv')
TARGET_ROOTS = ['/Volumes/Video/usr', '/Volumes/Video/Video2', '/Volumes/Video/JAV']  # 仅导入这些前缀下的文件
SIZE_LIMIT_BYTES = 10 * 1024 * 1024  # 10MB
LOG_PATH = os.path.join(os.path.dirname(__file__), 'quick_import_from_csv.log')
OUT_TXT_PATH = os.path.join(os.path.dirname(__file__), 'outside_root_paths.txt')


def map_csv_path_to_real(csv_path: str) -> str:
    """将CSV中的路径映射为本机实际路径。
    需求：/Volume1/ 或 /volume1/ 或 /Volume1/ 或 /volume1/ -> /Volumes/
    """
    if not csv_path:
        return csv_path
    # 统一分隔符与空格
    mapped = csv_path.strip()
    # 映射规则 - 修正所有可能的大小写变体
    for src in ('/Volume1/', '/volume1/', '/Volume1/', '/volume1/'):
        mapped = mapped.replace(src, '/Volumes/')
    return mapped


def is_hidden_path(path: str) -> bool:
    """判断是否为隐藏文件或路径（.或._开头，或任意路径段以.开头）。"""
    name = os.path.basename(path)
    if name.startswith('.') or name.startswith('._'):
        return True
    # 任意路径段以'.'开头
    parts = Path(path).parts
    return any(p.startswith('.') for p in parts)


def in_recycle(path: str) -> bool:
    """判断是否在回收站路径#recycle内。"""
    return '/#recycle/' in path or path.endswith('/#recycle') or '/@eaDir/' in path


def get_db_video_columns(conn) -> set:
    """获取videos表现有列名集合，兼容不同版本结构。"""
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(videos)")
    cols = {row[1] for row in cur.fetchall()}
    return cols


def ensure_db_exists(db_path: str):
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"数据库不存在：{db_path}")


def build_insert_values(file_path: str, file_name: str, file_size: int, md5_hash: str,
                        db_cols: set):
    """根据现有表结构构建可插入的列与值。只插入存在的列。"""
    values = {}

    # 基础字段
    if 'file_path' in db_cols:
        values['file_path'] = file_path
    if 'file_name' in db_cols:
        values['file_name'] = file_name
    if 'file_size' in db_cols:
        values['file_size'] = file_size
    if 'md5_hash' in db_cols:
        values['md5_hash'] = md5_hash

    # 其他可选字段
    title = os.path.splitext(file_name)[0]
    if 'title' in db_cols:
        values['title'] = title
    if 'tags' in db_cols:
        values['tags'] = ''
    if 'is_nas_online' in db_cols:
        values['is_nas_online'] = 1
    # 源文件夹：使用文件所在目录
    if 'source_folder' in db_cols:
        values['source_folder'] = os.path.dirname(file_path)
    # 文件创建时间（如果能读取到）
    if 'file_created_time' in db_cols:
        try:
            stat = os.stat(file_path)
            # 使用文件修改时间作为创建时间的近似
            values['file_created_time'] = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            # 读不到则不设置，让数据库默认或保持为NULL
            pass

    return values


def insert_video(conn, values: dict):
    cols = list(values.keys())
    placeholders = ','.join(['?'] * len(cols))
    sql = f"INSERT INTO videos ({','.join(cols)}) VALUES ({placeholders})"
    cur = conn.cursor()
    cur.execute(sql, [values[c] for c in cols])
    conn.commit()


def exists_duplicate(conn, file_path: str, file_name: str, directory: str) -> bool:
    """按要求进行重复性检查：
    - 文件路径精确匹配
    - 同目录下文件名匹配
    """
    cur = conn.cursor()
    # 路径精确匹配
    cur.execute("SELECT id FROM videos WHERE file_path = ?", (file_path,))
    if cur.fetchone():
        return True
    # 同目录中文件名匹配
    like_prefix = directory.rstrip('/') + '/%'
    cur.execute("SELECT id FROM videos WHERE file_name = ? AND file_path LIKE ?", (file_name, like_prefix))
    return cur.fetchone() is not None


def run_import():
    # 设置日志：输出到文件与控制台
    logger = logging.getLogger('quick_import')
    logger.setLevel(logging.INFO)
    logger.handlers = []
    fmt = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    fh = logging.FileHandler(LOG_PATH, encoding='utf-8')
    fh.setLevel(logging.INFO)
    fh.setFormatter(fmt)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(ch)

    ensure_db_exists(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    db_cols = get_db_video_columns(conn)

    # 建立目标根目录的文件名索引，便于按文件名查找
    def build_filename_index(root: str):
        idx = {}
        counted = 0
        for dirpath, dirnames, filenames in os.walk(root):
            # 跳过隐藏与回收站目录
            if in_recycle(dirpath) or is_hidden_path(dirpath):
                continue
            for name in filenames:
                if name.startswith('.') or name.startswith('._'):
                    continue
                full = os.path.join(dirpath, name)
                try:
                    size = os.path.getsize(full)
                except Exception:
                    size = 0
                if size < SIZE_LIMIT_BYTES:
                    continue
                idx.setdefault(name, []).append(full)
                counted += 1
        return idx, counted

    # 多根索引与根路径判断
    def is_in_target_roots(path: str, roots: list) -> bool:
        normalized = path.rstrip('/') + '/'
        for r in roots:
            rr = r.rstrip('/') + '/'
            if normalized.startswith(rr):
                return True
        return False

    def build_filename_index_multi(roots: list):
        idx = {}
        total = 0
        for r in roots:
            sub_idx, counted = build_filename_index(r)
            for name, paths in sub_idx.items():
                idx.setdefault(name, []).extend(paths)
            total += counted
            logger.info("索引完成 | 根=%s | 文件数=%s", r, counted)
        return idx, total

    filename_index, indexed_count = build_filename_index_multi(TARGET_ROOTS)
    logger.info("已建立目标根索引 | 根集合=%s | 总可用文件数=%s", ', '.join(TARGET_ROOTS), indexed_count)

    total_rows = 0
    skipped_hidden = 0
    skipped_recycle = 0
    skipped_small = 0
    skipped_outside_root = 0
    fallback_by_name = 0
    fallback_name_not_found = 0
    fallback_name_multiple = 0
    outside_root_records = []  # 记录未在目标根的原始CSV路径
    missing_files = 0
    duplicates = 0
    inserted = 0

    logger.info("开始快速导入: CSV=%s, 目标根目录=%s", CSV_PATH, ', '.join(TARGET_ROOTS))
    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_rows += 1

            csv_name = row.get('文件名', '')
            csv_path = row.get('文件路径', '')
            csv_size = row.get('大小(字节)', '0')
            csv_md5 = row.get('MD5值', '')

            # 路径映射
            mapped_path = map_csv_path_to_real(csv_path)

            # 过滤：隐藏文件
            if is_hidden_path(mapped_path) or (csv_name.startswith('.') or csv_name.startswith('._')):
                skipped_hidden += 1
                logger.info("SKIP-HIDDEN | name=%s | csv_path=%s | mapped_path=%s", csv_name, csv_path, mapped_path)
                continue

            # 过滤：回收站
            if in_recycle(mapped_path):
                skipped_recycle += 1
                logger.info("SKIP-RECYCLE | name=%s | mapped_path=%s", csv_name, mapped_path)
                continue

            # 过滤：大小
            try:
                size_int = int(csv_size)
            except ValueError:
                size_int = 0
            if size_int < SIZE_LIMIT_BYTES:
                skipped_small += 1
                logger.info("SKIP-SMALL | name=%s | size=%s | mapped_path=%s", csv_name, size_int, mapped_path)
                continue

            # 仅导入指定根目录（多个）
            if not is_in_target_roots(mapped_path, TARGET_ROOTS):
                # 尝试按文件名在目标根内查找
                candidates = filename_index.get(csv_name) or filename_index.get(os.path.basename(mapped_path))
                if candidates and len(candidates) == 1:
                    chosen = candidates[0]
                    logger.info("FOUND-BY-NAME | name=%s | csv_path=%s | mapped_path=%s | chosen=%s", csv_name, csv_path, mapped_path, chosen)
                    mapped_path = chosen
                    fallback_by_name += 1
                elif candidates and len(candidates) > 1:
                    fallback_name_multiple += 1
                    skipped_outside_root += 1
                    logger.info("NAME-MULTIPLE | name=%s | candidates_count=%s | mapped_path=%s", csv_name, len(candidates), mapped_path)
                    outside_root_records.append(f"{csv_name}\t{csv_path}\t{mapped_path}\tMULTIPLE")
                    continue
                else:
                    fallback_name_not_found += 1
                    skipped_outside_root += 1
                    logger.info("SKIP-OUTSIDE-ROOT | NAME-NOT-FOUND | name=%s | csv_path=%s | mapped_path=%s", csv_name, csv_path, mapped_path)
                    outside_root_records.append(f"{csv_name}\t{csv_path}\t{mapped_path}\tNOT_FOUND")
                    continue

            # 文件存在性检查（谨慎）：不存在也可选择跳过，避免脏记录
            if not os.path.exists(mapped_path):
                missing_files += 1
                logger.info("SKIP-MISSING | name=%s | mapped_path=%s", csv_name, mapped_path)
                continue

            directory = os.path.dirname(mapped_path)
            file_name = os.path.basename(mapped_path)

            # 去重
            if exists_duplicate(conn, mapped_path, file_name, directory):
                duplicates += 1
                logger.info("SKIP-DUPLICATE | name=%s | path=%s", file_name, mapped_path)
                continue

            # 构建插入
            values = build_insert_values(mapped_path, file_name, size_int, csv_md5, db_cols)
            try:
                insert_video(conn, values)
                inserted += 1
                logger.info("INSERTED | name=%s | path=%s | size=%s | md5=%s", file_name, mapped_path, size_int, csv_md5)
            except Exception as e:
                logger.error("INSERT-FAILED | path=%s | error=%s", mapped_path, e)

    conn.close()

    # 写出不在目标根路径的条目到txt
    try:
        with open(OUT_TXT_PATH, 'w', encoding='utf-8') as outf:
            outf.write("文件名\tCSV原始路径\t映射后路径\t原因\n")
            for line in outside_root_records:
                outf.write(line + "\n")
        logger.info("导出不在目标根路径的条目: %s | 总计=%s", OUT_TXT_PATH, len(outside_root_records))
    except Exception as e:
        logger.error("导出outside_root_paths失败: %s", e)

    summary = (
        "=== 导入完成 ===\n"
        f"总行数: {total_rows}\n"
        f"已插入: {inserted}\n"
        f"重复跳过: {duplicates}\n"
        f"隐藏文件跳过: {skipped_hidden}\n"
        f"回收站跳过: {skipped_recycle}\n"
        f"小于10MB跳过: {skipped_small}\n"
        f"不在目标根路径跳过: {skipped_outside_root}\n"
        f"按文件名找到并修正路径: {fallback_by_name}\n"
        f"按文件名未找到: {fallback_name_not_found}\n"
        f"按文件名命中多个候选: {fallback_name_multiple}\n"
        f"文件不存在跳过: {missing_files}\n"
        f"日志文件: {LOG_PATH}\n"
        f"不在根路径条目导出: {OUT_TXT_PATH}"
    )
    print(summary)
    logging.getLogger('quick_import').info(summary.replace('\n', ' | '))


if __name__ == '__main__':
    run_import()