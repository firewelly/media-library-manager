---
type: 参考
title: 日志文件
description: 记录系统生成的所有日志文件——包括其生成者、内容格式以及大型媒体库操作时的大致文件大小。
openwiki:
  roles: [operations]
  source_paths: [batch_analysis.log, pipeline_run.log, reprocess_failed.log]
---

# 日志文件

## 操作日志

### `batch_analysis.log`（约 88KB）
在批量视频分析操作期间生成。包含带有状态指示器的逐视频进度行。

### `pipeline_run.log`（约 62KB）
由 `video_analyzer/video_analyzer_pipeline.py` 生成。记录内容：
- 每个视频的帧提取时间戳
- API 调用时长和响应代码
- 标签提取结果

### `reprocess_failed.log`（约 15KB）
记录在初始分析期间失败并正在重新处理的视频。包含错误信息和重试次数。

### `batch_update.log`（约 643 字节）
来自批量元数据更新操作的小型日志。

## 重新标记日志

匹配 `retag_run_YYYYMMDD_HHMMSS.log` 和 `retag_retry_YYYYMMDD_HHMMSS.log` 的文件：
- 由 `retag_local_videos.py` 和 `retag_scored_videos.py` 生成
- 根据媒体库大小，文件大小从约 1MB 到约 14MB 不等
- 包含每个视频的标记决策（旧标签 -> 新标签）

## 导入日志

### `quick_import_from_csv.log`（约 37MB）
来自基于 CSV 的批量导入的超大型日志。在从预先计算的 MD5 列表导入数万个视频时生成。

## 视频分析器日志

### `video_analyzer/analysis_log.txt`（约 14MB）
来自 AI 视频分析器的全面日志。记录整个媒体库的每一次帧提取、API 调用和标签确定。

## 另请参阅

- [日志概述](overview.md) — 所有日志和报告
- [报告文件](report_files.md) — CSV 导出