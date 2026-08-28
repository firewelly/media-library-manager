---
type: 参考
title: 演员爬虫
description: 详细记录所有与演员相关的爬虫脚本——资料抓取、无头变体、演员作品枚举以及收藏演员批量抓取。
openwiki:
  roles: [integration]
  source_paths: [actor_crawler_with_db.py, actor_crawler_headless_db.py, actor_detail_crawler.py, javdb_actor_all.py, javdb_actor_profile_repair.py, favorite_actor_works_crawler.py]
---

# 演员爬虫

专门用于从 JavDB 抓取演员资料、头像、作品列表和磁力链接的脚本。

## 核心演员爬虫

### `actor_crawler_with_db.py`（约 480 行）
全功能演员资料爬虫。针对每位演员：
- 抓取资料页（姓名、头像、简介、三围、生日）
- 下载头像图片并保存至 `covers/` 目录
- 通过 `utils/db.py` 将演员记录插入或更新到 `actors` 表中
- 将演员与现有视频记录关联

### `actor_crawler_headless_db.py`（约 550 行）
演员爬虫的无头变体。使用无头浏览器模式进行批量操作，无需显示浏览器窗口。数据提取逻辑与 `actor_crawler_with_db.py` 相同，但针对无人值守运行进行了优化。

### `actor_detail_crawler.py`（约 630 行）
深度提取演员详细信息。获取扩展资料信息，包括：
- 详细简介
- 作品完整度检查
- 相关演员链接
- 血型、身高、三围

## 演员作品爬虫

### `javdb_actor_all.py`（约 1,200 行）
全面的演员作品爬虫：
- 抓取指定演员的所有作品
- 提取每个视频的磁力链接
- 支持**断点续爬**（中断后基于检查点继续）
- 将结果写入 `results/favorite_actor_works.csv`

### `favorite_actor_works_crawler.py`（约 960 行）
批量抓取所有收藏演员（`actors` 表中 `is_favorite=1`）的完整作品。结合演员枚举与逐演员作品提取功能。

### `javdb_actor_profile_repair.py`（约 1,400 行） / `javdb_actor_profile_repair_all.py`（约 910 行）
用于修复不完整或损坏的演员记录的脚本。重新抓取资料以补全缺失的头像 URL、姓名或传记数据。

## 登录基础设施

所有演员爬虫均依赖 `javdb_login_helper.py` 来维持持久登录状态。登录助手的功能如下：
1. 使用专用的 Edge 浏览器用户数据目录（`~/.javdb_scraper/user_data`）
2. 登录 JavDB 一次（凭据来自 `.env` 文件：`LOGIN_EMAIL`、`LOGIN_PASSWORD`）
3. 持久化 Cookie，以便后续爬虫运行跳过登录步骤
4. 通过 `config.py` 设置配置 SOCKS5 代理

## 涉及的数据库表

| 表名 | 写入者 | 用途 |
|-------|-----------|---------|
| `actors` | 所有演员爬虫 | 演员资料（姓名、头像、简介） |
| `video_actors` | 所有演员爬虫 | 视频与演员的多对多关联 |
| `videos` | 作品爬虫 | 发现作品的元数据更新 |

## 另请参阅

- [爬虫系统概述](overview.md) — 三层回退架构
- [视频爬虫](video_crawlers.md) — 视频元数据爬虫
- [配置](../configuration/main_configs.md) — 代理与凭据设置
- [数据库概述](../database/overview.md) — 表结构参考