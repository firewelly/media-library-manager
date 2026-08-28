---
type: 概览
title: 日志与报告概览
description: 爬虫、导入器和视频分析器生成的日志文件、分析报告及 CSV 导出内容概览。
openwiki:
  roles: [operations]
  source_paths: [batch_analysis.log, pipeline_run.log, reprocess_failed.log, reports/analysis_out.csv, reports/folder_reassociation_preview.csv]
---

# 日志与报告概览

系统在批处理操作期间会生成多种日志文件，并生成 CSV 报告用于数据导出和分析。

## 日志文件

| 文件 | 生成来源 | 内容 |
|------|-------------|---------|
| `batch_analysis.log` | 批处理分析操作 | 逐视频分析进度与结果 |
| `pipeline_run.log` | 视频分析器流水线 | 帧提取与 API 调用日志 |
| `reprocess_failed.log` | 失败项目重处理 | 重试操作的错误详情 |
| `retag_run_*.log` | 自动打标签运行（`retag_local_videos.py`） | 逐视频打标签进度 |
| `retag_retry_*.log` | 重新打标签重试运行 | 30 帧采样重试详情 |
| `quick_import_from_csv.log` | 基于 CSV 的导入 | 导入进度（约 37MB，超大媒体库） |
| `batch_update.log` | 批量元数据更新 | 更新进度与错误 |
| `video_analyzer/analysis_log.txt` | 视频分析器 | 完整分析日志（约 14MB） |

## 报告文件

| 文件 | 生成来源 | 内容 |
|------|-------------|---------|
| `reports/analysis_out.csv` | 视频分析 | 标签提取结果 |
| `reports/folder_reassociation_preview.csv` | 文件夹重新关联 | 文件夹重新分配预览 |
| `video_analyzer/production_analysis_*.csv` | 制作分析器 | 每次运行的 AI 生成标签结果 |
| `results/favorite_actor_works.csv` | 演员作品爬虫 | 完整作品目录 |
| `results/javdb_magnets.csv` | JavDB 爬虫 | 磁力链接提取结果 |
| `md5_cache.json` | MD5 计算 | 缓存的文件哈希值 |

## 日志特征

- 日志文件名通常包含时间戳（`retag_run_20260625_222110.log`）
- 长时间运行的批处理操作（49k+ 个视频）会生成大型日志
- CSV 报告遵循一致的格式，其表头与数据库架构相匹配

## 另请参阅

- [日志文件详情](log_files.md) — 详细的日志文件文档
- [报告文件详情](report_files.md) — CSV 导出详情