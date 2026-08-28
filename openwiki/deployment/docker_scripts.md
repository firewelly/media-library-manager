---
type: 参考
title: Docker 脚本
description: 介绍 Docker 部署 — docker-compose.yml（FastAPI 后端 + Vue 3 前端）、包含 FastAPI/SQLAlchemy 的后端 Dockerfile，以及包含 nginx 的前端 Dockerfile。
openwiki:
  roles: [operations]
  source_paths: [docker/docker-compose.yml, docker/backend/Dockerfile, docker/backend/main.py, docker/frontend/Dockerfile, docker/frontend/nginx.conf]
---

# Docker 脚本

## `docker-compose.yml`

双服务编排：

```yaml
services:
  backend:
    build: ./backend
    container_name: media-library-backend
    ports: ["8000:8000"]
    volumes:
      - ./data:/app/data
    restart: always

  frontend:
    build: ./frontend
    container_name: media-library-frontend
    ports: ["80:80"]
    depends_on: [backend]
    restart: always
```

**卷映射**：将 NAS 媒体文件夹挂载到后端容器中。内部路径必须与数据库路径匹配，或者需要更新路径。

## 后端（`docker/backend/`）

### `Dockerfile`
使用 Python 3.11 slim 镜像。安装 `requirements.txt`，复制 FastAPI 应用程序代码。

### `main.py` — FastAPI 应用程序
REST API 端点：
- `GET /videos/` — 列出视频，支持分页和搜索（标题、文件名、标签）
- 为所有来源启用 CORS

### `models.py` — SQLAlchemy 模型
映射到 SQLite 数据库表（`videos`、`actors` 等）的 ORM 模型。

### `schemas.py` — Pydantic 模式
请求/响应验证模式。

### `database.py`
SQLAlchemy 引擎和会话配置，指向 `data/media_library.db`。

### `fast_smart_media_updater.py`
文件夹扫描器的容器化版本（来自根目录的 `fast_smart_media_updater.py`）。

**在容器内运行扫描器：**
```bash
docker exec -it media-library-backend python fast_smart_media_updater.py --path /media/folder
```

## 前端（`docker/frontend/`）

### `Dockerfile`
构建使用 Node 18 Alpine，服务使用 nginx。运行 `npm install && npm run build`，将输出复制到 nginx。

### `nginx.conf`
提供 Vue 3 SPA 服务。将 API 调用代理到后端容器。

### `src/`
Web 前端的 Vue 3 源代码。

## 部署步骤

1. 将 `docker/` 复制到 NAS/服务器
2. （可选）将 `media_library.db` 复制到 `docker/data/`
3. 编辑 `docker-compose.yml` 以挂载媒体文件夹
4. 运行 `docker-compose up -d --build`
5. 访问 `http://<nas-ip>`

## 另请参阅

- [部署概述](overview.md) — 所有部署模式
- [部署脚本](deployment_scripts.md) — 桌面启动脚本