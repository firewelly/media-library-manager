---
type: 概述
title: 部署概述
description: 部署选项概述 — Docker Compose（FastAPI 后端 + Vue 3 前端）、特定平台的启动脚本以及 macOS .app 捆绑包。
openwiki:
  roles: [运维]
  source_paths: [docker/docker-compose.yml, docker/README.md, start_media_library.sh, start_media_library_v2.sh, start_media_library_v2.bat]
---

# 部署概述

本系统支持多种部署模式：本地桌面、Docker 容器化以及 macOS 应用程序捆绑包。

## 部署选项

| 模式 | 平台 | 启动方式 | 描述 |
|------|----------|-------|-------------|
| 本地桌面 (Tk) | macOS/Linux | `python media_library.py` | 经典单文件 GUI |
| 本地桌面 (v2) | macOS/Linux/Windows | `python media_library_v2.py` | 推荐的模块化 GUI |
| Docker Compose | NAS/服务器 | `docker-compose up -d` | FastAPI 后端 + Vue 3 前端 |
| macOS .app 捆绑包 | macOS | 双击 `Media Library.app` | 支持 Spotlight 搜索启动 |

## 平台启动脚本

| 脚本 | 平台 | 版本 | 特性 |
|--------|----------|---------|----------|
| `start_media_library.sh` | macOS/Linux | Tk 经典版 | 检查 Python，启动 Tk |
| `start_media_library_v2.sh` | macOS/Linux | v2 | 检查 Python，按需安装 PySide6 |
| `start_media_library_v2.bat` | Windows | v2 | 检查 Python，按需安装 PySide6 |

## Docker 部署

Docker 采用双服务架构：
- **后端**：运行于端口 8000 的 FastAPI — 用于视频浏览、搜索和元数据管理的 REST API
- **前端**：运行于端口 80 的 Vue 3 — 通过 nginx 提供服务

## 另请参阅

- [Docker 脚本](docker_scripts.md) — Dockerfile 和 compose 详情
- [部署脚本](deployment_scripts.md) — 启动脚本详情
- [快速入门](../quickstart.md) — 基本用法