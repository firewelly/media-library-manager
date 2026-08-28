---
type: 参考
title: 人脸识别模块
description: 介绍 facereco/ 目录 — 人脸提取 API（包含 Haar 级联检测、质量评分、多人提取的 FaceExtractorAPI）及示例用法脚本。
openwiki:
  roles: [domain]
  source_paths: [facereco/face_extractor_api.py, facereco/multi_person_face_extractor.py]
  symbols: [FaceExtractorAPI]
---

# 人脸识别模块（`facereco/`）

`facereco/` 目录提供人脸检测和提取功能，主要由演员爬虫用于处理封面图片。

## `face_extractor_api.py` — `FaceExtractorAPI`

人脸提取的主 API 类：

**构造函数：**
```python
FaceExtractorAPI(output_dir="output")
```
- 初始化 OpenCV Haar 级联分类器，用于人脸和眼睛检测
- 如果输出目录不存在则创建

**核心方法：**
- `calculate_face_quality(face_img, face_rect, original_img)` — 使用以下指标对人脸进行评分：
  - 尺寸评分（人脸越大 = 越清晰）
  - 清晰度评分（拉普拉斯方差）
  - 眼睛检测数量（检测到眼睛的人脸得分更高）
- 从 URL 或本地文件提取人脸
- 检测到多个人脸时自动选择最佳人脸

**技术：**
- OpenCV Haar 级联分类器（`haarcascade_frontalface_default.xml`、`haarcascade_eye.xml`）
- 无深度学习依赖 — 轻量级，仅依赖 CPU

## `multi_person_face_extractor.py`

用于从包含多人的图像中提取人脸的扩展模块：
- 检测图像中的所有人脸
- 分别裁剪并保存每个人脸
- 适用于展示多位演员的演员封面图片

## 示例脚本

- `example_usage.py` — 单人提取演示
- `example_multi_person_usage.py` — 多人提取演示

## 另请参阅

- [演员爬虫](../crawlers/actor_crawlers.md) — 使用人脸提取的爬虫
- [其他目录概览](overview.md) — 所有辅助目录