#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
智能文件夹更新脚本（NAS优先使用预计算MD5）

功能概述：
- 扫描指定文件夹或数据库中已启用的文件夹
- 对于 NAS 挂载路径 `/Volumes/Video/` 下的文件，优先从 `video_md5.csv` 获取 MD5
  （CSV 路径前缀为 `/volume1/Video/`，自动进行路径前缀映射）
- 未命中 CSV 或非 NAS 路径，则回退到本地 MD5 计算（带缓存）
- 复用 ResumableSmartImporter 的“智能媒体库更新”逻辑

用法示例：
  python smart_video_updater.py --db media_library.db --md5-csv video_md5.csv --use-active-folders
  python smart_video_updater.py --db media_library.db --md5-csv video_md5.csv --folder "/Volumes/Video/Movies"

说明：
- 为提升性能，CSV 会被索引为 路径→(MD5, 大小) 的映射；对于大文件集建议本地运行。
"""

import os
import csv
from pathlib import Path
from typing import Optional, Dict, Tuple, List

from resumable_smart_importer import ResumableSmartImporter


NAS_LOCAL_PREFIX = "/Volumes/Video"
NAS_REMOTE_PREFIX = "/volume1/Video"


class MD5CSVIndex:
    """将 video_md5.csv 索引为 路径→(md5, size) 的映射。

    CSV格式示例（含表头）：
    文件名,文件路径,大小(字节),MD5值
    ...
    """

    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self._index: Dict[str, Tuple[str, int]] = {}
        self._loaded = False

    def load(self) -> int:
        if not os.path.exists(self.csv_path):
            return 0
        count = 0
        try:
            with open(self.csv_path, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f)
                # 跳过表头（中文表头）
                header = next(reader, None)
                # 容错：如果首行不是4列，认为无表头
                if header and len(header) != 4:
                    # 可能没有表头，将首行作为数据处理
                    f.seek(0)
                    reader = csv.reader(f)

                for row in reader:
                    if len(row) < 4:
                        continue
                    _, file_path, size_str, md5_val = row[0], row[1], row[2], row[3]
                    if not file_path or not md5_val:
                        continue
                    try:
                        size_int = int(size_str)
                    except Exception:
                        size_int = 0

                    # 采用原始 CSV 路径（/volume1/Video/...）作为 key
                    key = file_path.strip()
                    self._index[key] = (md5_val.strip(), size_int)
                    count += 1
            self._loaded = True
        except Exception as e:
            print(f"加载 MD5 CSV 失败: {e}")
        return count

    def get_by_remote_path(self, remote_path: str) -> Optional[Tuple[str, int]]:
        if not self._loaded:
            self.load()
        return self._index.get(remote_path)

    def get_for_local_path(self, local_path: str) -> Optional[Tuple[str, int]]:
        """将本地挂载路径转换为远端CSV路径并查询。
        本地：/Volumes/Video[/...] → 远端：/volume1/Video[/...]
        """
        if not local_path.startswith(NAS_LOCAL_PREFIX):
            return None
        # 映射：去掉本地前缀，拼接远端前缀，兼容是否带尾随斜杠
        suffix = local_path[len(NAS_LOCAL_PREFIX):]
        remote_path = NAS_REMOTE_PREFIX + suffix
        return self.get_by_remote_path(remote_path)


def attach_md5_csv_override(importer: ResumableSmartImporter, csv_index: Optional[MD5CSVIndex]):
    """为导入器实例注入 MD5 计算的 CSV 优先逻辑，并记录统计信息。"""
    original_fn = importer.calculate_md5_with_cache

    # 统计信息挂到实例上，便于外部读取
    importer._csv_md5_stats = {
        "hit": 0,
        "miss": 0,
        "fallback_size_mismatch": 0,
        "non_nas": 0
    }

    def _override(file_path: str) -> Optional[str]:
        try:
            # 仅对 NAS 路径优先查 CSV（兼容不带尾随斜杠）
            if csv_index and file_path.startswith(NAS_LOCAL_PREFIX):
                hit = csv_index.get_for_local_path(file_path)
                if hit:
                    md5_val, csv_size = hit
                    try:
                        actual_size = os.path.getsize(file_path)
                    except Exception:
                        actual_size = None

                    # 严格比对文件大小以避免错误匹配
                    if actual_size is not None and csv_size == actual_size:
                        importer._csv_md5_stats["hit"] += 1
                        print(f"CSV MD5 命中: {file_path} -> {md5_val}")
                        # 同步写入导入器的 md5_cache，提高后续命中率
                        file_key = str(Path(file_path).absolute())
                        if "md5_cache" not in importer.cache_data:
                            importer.cache_data["md5_cache"] = {}
                        try:
                            stat = os.stat(file_path)
                            importer.cache_data["md5_cache"][file_key] = {
                                "md5_hash": md5_val,
                                "file_size": stat.st_size,
                                "mtime": stat.st_mtime,
                                "calculated_at": None,
                                "source": "csv"
                            }
                        except Exception:
                            # 如果 stat 失败，仍返回 md5
                            pass
                        return md5_val
                    else:
                        importer._csv_md5_stats["fallback_size_mismatch"] += 1
                        print(f"CSV 大小不匹配，回退计算: {file_path} (csv={csv_size}, actual={actual_size})")
                        return original_fn(file_path)
                else:
                    importer._csv_md5_stats["miss"] += 1
            else:
                importer._csv_md5_stats["non_nas"] += 1

            # 未命中 CSV 或非 NAS，回退原始计算
            return original_fn(file_path)
        except Exception as e:
            print(f"MD5计算覆盖逻辑失败 {file_path}: {e}")
            return original_fn(file_path)

    importer.calculate_md5_with_cache = _override  # 注入覆盖逻辑

def apply_csv_md5_only(importer: ResumableSmartImporter, csv_index: Optional[MD5CSVIndex], folders: Optional[List[str]], dry_run: bool = False) -> Dict:
    """仅应用 CSV 中已有的 MD5 到数据库，不做全量扫描。

    - 将 CSV 中的远端路径 `/volume1/Video/...` 映射为本地挂载 `/Volumes/Video/...`
    - 仅在本地文件存在且大小匹配时更新数据库对应记录的 `md5_hash`
    - 若提供 `folders`，仅处理这些范围内的本地路径
    - 遵循回收站/缩略图等目录跳过规则
    """
    stats = {
        "csv_total": 0,
        "local_checked": 0,
        "updated": 0,
        "updated_by_file_path": 0,
        "updated_by_nas_path": 0,
        "updated_by_name_size": 0,
        "size_mismatch": 0,
        "missing_local": 0,
        "missing_db": 0,
        "skipped_special": 0
    }

    if not csv_index:
        print("未加载 CSV，无法执行 CSV MD5 仅合并模式")
        return stats

    skip_tokens = [
        '/#recycle/', '/.@__thumb/', '/@eaDir/', '/.Trashes/', '/.Trash-'
    ]

    stats["csv_total"] = len(csv_index._index)

    to_update = []  # (md5, local_path)

    for remote_path, (md5_val, csv_size) in csv_index._index.items():
        # 仅处理远端NAS路径
        if not remote_path.startswith(NAS_REMOTE_PREFIX):
            continue

        # 映射为本地路径（兼容是否带尾随斜杠）
        local_path = NAS_LOCAL_PREFIX + remote_path[len(NAS_REMOTE_PREFIX):]

        # 路径范围过滤
        if folders and not any(local_path.startswith(folder) for folder in folders):
            continue

        # 跳过特殊目录与隐藏文件
        if local_path.endswith('/#recycle') or any(tok in local_path for tok in skip_tokens) or os.path.basename(local_path).startswith('._'):
            stats["skipped_special"] += 1
            continue

        # 检查本地文件存在与大小匹配
        if os.path.exists(local_path):
            stats["local_checked"] += 1
            try:
                actual_size = os.path.getsize(local_path)
            except Exception:
                actual_size = None

            if actual_size is not None and actual_size == csv_size:
                updated_here = False
                # 1) 按 file_path 精确更新
                importer.cursor.execute("SELECT id FROM videos WHERE file_path = ?", (local_path,))
                row = importer.cursor.fetchone()
                if row:
                    if not dry_run:
                        importer.cursor.execute("UPDATE videos SET md5_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (md5_val, row[0]))
                    to_update.append((md5_val, local_path))
                    stats["updated"] += 1
                    stats["updated_by_file_path"] += 1
                    updated_here = True
                else:
                    # 2) 按 nas_path（远端路径）尝试更新
                    importer.cursor.execute("SELECT id FROM videos WHERE nas_path = ?", (remote_path,))
                    row2 = importer.cursor.fetchone()
                    if row2:
                        if not dry_run:
                            importer.cursor.execute("UPDATE videos SET md5_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (md5_val, row2[0]))
                        to_update.append((md5_val, local_path))
                        stats["updated"] += 1
                        stats["updated_by_nas_path"] += 1
                        updated_here = True
                    else:
                        # 3) 按 文件名 + 文件大小 尝试更新（降低碰撞概率）
                        basename = os.path.basename(local_path)
                        importer.cursor.execute("SELECT id FROM videos WHERE file_name = ? AND file_size = ?", (basename, csv_size))
                        row3 = importer.cursor.fetchone()
                        if row3:
                            if not dry_run:
                                importer.cursor.execute("UPDATE videos SET md5_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (md5_val, row3[0]))
                            to_update.append((md5_val, local_path))
                            stats["updated"] += 1
                            stats["updated_by_name_size"] += 1
                            updated_here = True

                if not updated_here:
                    stats["missing_db"] += 1
            else:
                stats["size_mismatch"] += 1
        else:
            stats["missing_local"] += 1

    if not dry_run and stats["updated"] > 0:
        importer.conn.commit()

    # 反馈示例清单（限制输出数量）
    if to_update:
        print("\nCSV 应用MD5示例（最多显示10条）：")
        for md5_val, lp in to_update[:10]:
            print(f"  {md5_val} <- {lp}")

    return stats


def main():
    import argparse

    parser = argparse.ArgumentParser(description="智能文件夹更新（NAS优先使用MD5 CSV）")
    parser.add_argument("--db", default="media_library.db", help="数据库路径，默认 media_library.db")
    parser.add_argument("--md5-csv", default="video_md5.csv", help="MD5 CSV 文件路径，默认 video_md5.csv")
    parser.add_argument("--folder", dest="folders", action="append", help="要扫描的文件夹，可重复传入")
    parser.add_argument("--use-active-folders", action="store_true", help="使用数据库中已启用的文件夹")
    parser.add_argument("--dry-run", action="store_true", help="仅打印统计信息，不输出详细日志")
    parser.add_argument("--csv-md5-only", action="store_true", help="仅应用 CSV 中已有 MD5，不进行全量扫描更新")

    args = parser.parse_args()

    print("初始化导入器...")
    importer = ResumableSmartImporter(db_path=args.db)

    csv_index = None
    if args.md5_csv and os.path.exists(args.md5_csv):
        print(f"加载 MD5 CSV: {args.md5_csv}")
        csv_index = MD5CSVIndex(args.md5_csv)
        count = csv_index.load()
        print(f"MD5 CSV 索引完成，记录数: {count}")
    else:
        print("未提供或找不到 MD5 CSV，MD5 将走本地计算（带缓存）")

    # 注入覆盖逻辑
    attach_md5_csv_override(importer, csv_index)

    # 选择扫描文件夹来源
    folders: Optional[List[str]] = None
    if args.use_active_folders:
        folders = importer.get_active_folders()
        print(f"使用数据库活跃文件夹: {folders}")
    elif args.folders:
        folders = args.folders
        print(f"使用指定文件夹: {folders}")
    else:
        print("未指定文件夹，将使用数据库活跃文件夹。")
        folders = importer.get_active_folders()

    # 执行智能更新或仅应用 CSV MD5
    if args.csv_md5_only:
        print("运行 CSV MD5 仅合并模式...")
        stats = apply_csv_md5_only(importer, csv_index, folders, dry_run=args.dry_run)
    else:
        stats = importer.comprehensive_media_update(folders=folders)

    # 输出结果
    print("\n=== 更新完成统计 ===")
    if isinstance(stats, dict):
        for k, v in stats.items():
            print(f"{k}: {v}")
    else:
        print(stats)

    # 输出 CSV 命中统计
    if hasattr(importer, "_csv_md5_stats"):
        s = importer._csv_md5_stats
        print("\n=== CSV MD5 命中统计 ===")
        print(f"命中(hit): {s['hit']}")
        print(f"未命中(miss): {s['miss']}")
        print(f"大小不匹配回退(fallback_size_mismatch): {s['fallback_size_mismatch']}")
        print(f"非NAS路径(non_nas): {s['non_nas']}")


if __name__ == "__main__":
    main()