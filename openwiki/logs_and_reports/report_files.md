---
type: 参考
title: 报告文件
description: 记录 CSV 报告文件——分析结果、演员作品导出、磁力链接导出、文件夹重新关联预览以及 MD5 缓存索引。
openwiki:
  roles: [operations]
  source_paths: [reports/analysis_out.csv, reports/folder_reassociation_preview.csv, results/favorite_actor_works.csv, results/javdb_magnets.csv, md5_cache.json]
---

# 报告文件

## 分析报告

### `reports/analysis_out.csv` (~375KB)
视频内容分析的输出。包含每个视频的标签提取结果。

### `reports/folder_reassociation_preview.csv` (~10MB)
文件夹重新关联操作的预览。反映完整资料库的大型文件。用于在执行文件夹移动之前预览更改。

### `video_analyzer/production_analysis_*.csv`
每次运行的 AI 分析输出。以时间戳命名。每个文件包含：
- 视频文件路径
- 提取的标签（每个视频最多 7 个）
- 置信度得分
- 使用的模型（`Qwen3-VL-30B-A3B-Instruct`）

## 爬虫导出

### `results/favorite_actor_works.csv` (~981KB)
由 `favorite_actor_works_crawler.py` 和 `javdb_actor_all.py` 导出。包含：
- 演员姓名
- 影片番号
- 标题
- 磁力链接

### `results/javdb_magnets.csv` (~271KB)
JavDB 爬虫的磁力链接提取结果。包含备份文件（`.bak_*`）。

### `results/images/`
包含已下载的封面图片和演员头像的目录。

## 缓存文件

### `md5_cache.json` (~696KB)
JSON 索引，将 `(file_path, file_size, mtime)` 映射到 MD5 哈希值。由 `utils/file_utils.py` 使用，以避免对未更改的文件重新计算哈希值。其大小随资料库规模增长。

## 另请参阅

- [日志概述](overview.md) — 所有日志和报告
- [日志文件](log_files.md) — 详细日志文档
- [MD5 工具](../utilities/md5_tools.md) — MD5 缓存工作流