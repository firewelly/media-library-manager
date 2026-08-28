---
type: 概览
title: 其他目录概览
description: 支持性目录概览 — facereco（人脸提取 API）、video_analyzer（AI 视频内容分析）和 utils（提供数据库、文件操作、批量操作等功能的共享工具模块）。
openwiki:
  roles: [architecture]
  source_paths: [facereco/, video_analyzer/, utils/]
---

# 其他目录概览

本节涵盖提供支持功能的目录，这些目录提供主应用程序之外的特定功能。

## 目录汇总

| 目录 | 用途 | 关键文件 |
|-----------|---------|-----------|
| `facereco/` | 从图像/视频中提取人脸 | `face_extractor_api.py`, `multi_person_face_extractor.py` |
| `video_analyzer/` | AI 视频内容分析 | `production_video_analyzer_fixed.py`, `video_analyzer_pipeline.py`, `adapter.py` |
| `utils/` | 共享工具模块 | `database.py`, `file_utils.py`, `batch_ops.py`, `media_extensions.py`, `thumbnails.py` |

## 相互关系

- **主应用程序**从 `utils/` 导入所有数据库、文件和批量操作相关功能
- `video_analyzer/adapter.py` 为 Tk 版本提供了一个 GUI 桥接，用于调用 AI 分析
- `facereco/` 供 actor 爬虫使用，用于从视频封面中提取人脸图像并进行质量评分
- `utils/runtime.py` 提供运行时目录解析，供两个 GUI 版本和所有爬虫使用

## 另请参阅

- [人脸识别](facereco.md) — 人脸提取 API 详情
- [视频分析器](video_analyzer.md) — AI 分析管道详情
- [Utils 模块](utils.md) — 工具模块 API 参考