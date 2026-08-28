---
type: 参考
title: 视频爬虫 (JavDB)
description: 介绍 JavDB 的主要视频爬虫——批量页面爬虫、单视频提取器、批量信息更新器以及 NAS 专用更新器。
openwiki:
  roles: [integration]
  source_paths: [javdb_crawler.py, javdb_crawler_single.py, javdb_information_updater.py, nas_javdb_updater.py, javdb_login_helper.py]
---

# 视频爬虫 (JavDB)

JavDB 是主要的元数据源。这些脚本从 JavDB 页面提取视频信息（番号、标题、演员、标签、封面、评分、发行日期、磁力链接）。

## 核心爬虫

### `javdb_crawler_single.py`（约 1,300 行）
核心单视频提取器。由 GUI（通过子进程调用）和批量更新器使用。

**主要功能：**
- 给定视频番号，从 JavDB 视频页面提取元数据
- 通过重试逻辑（`is_cloudflare_challenge_html`）处理 CloudFlare 挑战
- 针对不同的访问模式提供多种尝试配置（`get_attempt_configs`）
- 返回结构化数据：番号、标题、描述、演员、标签、评分、封面 URL、发行日期
- 属于三级回退机制的一部分：在 JavBus/JavSP 之前被优先调用

### `javdb_crawler.py`（约 800 行）
批量逐页爬虫。遍历 JavDB 列表页（由 `config.py` 中的 `MAX_PAGES` 控制）并提取找到的每个视频的元数据。

**用法：**
```bash
python javdb_crawler.py
```

### `javdb_information_updater.py`（约 900 行）
带有文件夹选择功能的批量元数据更新器：
- 列出数据库中用户定义的数据文件夹
- 识别缺少元数据的视频（无演员、无标签等）
- 对于每个视频，从文件名中提取番号，并通过子进程调用 `javdb_crawler_single.py`
- 三级回退机制：JavDB -> JavBus -> JavSP（通过 `javsp_integration.py`）
- 支持按番号刷新和全库刷新

### `nas_javdb_updater.py`（约 700 行）
面向 NAS 的更新器，使用带有持久化用户数据的 Playwright：
- 强制使用“持久化”模式——登录一次，cookie 保持有效
- 直接调用 `javdb_crawler_single.py`（非子进程）以提升性能
- 专为在网络拓扑不同的 NAS 或远程机器上运行而设计
- 使用 `config.normalize_javdb_url()` 将 URL 重写为当前活动的镜像域名

## 登录辅助工具

### `javdb_login_helper.py`（约 370 行）
所有 JavDB 爬虫使用的基础组件：
- 使用专用的用户数据目录启动 Edge 浏览器（`~/.javdb_scraper/user_data` 或本地的 `.edge_driver_user_data`）
- 使用 `.env` 中的凭据执行 JavDB 登录
- 持久化登录状态，以便后续爬虫运行跳过身份验证
- 从 `config.py` 配置 SOCKS5 代理（`USE_SOCKS5_PROXY`、`SOCKS5_PROXY_HOST`、`SOCKS5_PROXY_PORT`）
- 实现随机延迟（`MIN_DELAY` 到 `MAX_DELAY`）以模拟人类行为

## 域名管理

JavDB 经常更改其可访问域名。`config.py` 负责管理此问题：
- `JAVDB_PROXY_DOMAIN`：与代理一起使用的域名（`javdb.com`）
- `JAVDB_DIRECT_DOMAIN`：用于直接访问的镜像域名（例如 `javdb574.com`）
- `JAVDB_ALTERNATE_DIRECT_DOMAINS`：已知镜像的列表，用于回退
- `normalize_javdb_url(url, use_proxy)`：将 URL 中任何已知的 JavDB 域名重写为当前活动的域名

## 另请参阅

- [爬虫系统概述](overview.md) — 架构与回退链
- [演员爬虫](actor_crawlers.md) — 针对演员的爬虫
- [JavSP 系统](JavSP_crawlers.md) — 多源回退
- [配置](../configuration/main_configs.md) — 代理与域名设置