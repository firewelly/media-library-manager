---
type: 参考
title: 重新打标工具
description: 介绍自动打标系统——基于词库的标签生成（video_tagging.py）、重新打标脚本、30帧随机抽样重试机制，以及 vocabulary_tags.txt 标签字典。
openwiki:
  roles: [delivery]
  source_paths: [video_tagging.py, retag_local_videos.py, retag_retry_20260626_152132.log, retag_scored_videos.py, vocabulary_tags.txt]
---

# 重新打标工具

自动打标系统通过词库匹配、标题/关键词分析，以及（可选）通过 `video_analyzer/` 模块进行基于 AI 的分析，为视频生成内容标签。

## 基于词库的打标

### `video_tagging.py`
核心自动打标引擎：
- 从 `vocabulary_tags.txt`（122 个标签）加载标签词库
- 使用 `jieba` 中文分词从视频标题和文件名中提取关键词
- 将提取的关键词与词库进行匹配以生成标签
- 将标签写回 `videos.tags` 列

**标签优先级层次结构**（`video_tagging.py` 和 `video_analyzer/` 均使用）：
```
Special features (highest) → Body type, physical state
Clothing features          → Apparel, accessories
Plot features              → Story, relationship
Character features         → Identity, age, physique
Behavior features (lowest) → Actions, interaction
```

### `vocabulary_tags.txt`
标签字典。包含 122 个按类别组织的预定义标签。自动打标器和 AI 分析器均引用此文件，以确保标签输出的一致性。

## 重新打标脚本

### `retag_local_videos.py`
为之前使用不同词库或匹配规则打标的本地（非 NAS）视频重新打标。读取当前标签，重新应用最新的词库匹配规则，并更新数据库。

### `retag_scored_videos.py`
为已评分的视频重新打标。将更新后的标签词库应用于 stars > 0 的视频。

## 30 帧随机抽样

近期增强（提交 `3e129b7`）：自动打标现包含 30 帧随机抽样重试机制：
- 如果初始标签生成未产生任何标签，则通过抽样 30 个随机帧进行重试
- 通过 OpenCV 分析帧的视觉特征，以补充基于文本的匹配
- 重试后仍无标签的视频将被标记为 `<无标签>`，以便于筛选

## 自动标签模式

提交 `ff97f69` 将自动打标更改为“重建模式”：
- 完全清除旧标签
- 将 JavDB 标签与新生成的标签合并
- 确保标签反映当前的词库和 JavDB 数据

## 另请参阅

- [Video Analyzer](../other_directories/video_analyzer.md) — 通过 SiliconFlow API 进行基于 AI 的打标
- [Utilities Overview](overview.md) — 共享后端工具
- [Database Overview](../database/overview.md) — `videos.tags` 列