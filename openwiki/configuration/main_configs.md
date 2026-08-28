---
type: 参考
title: 主要配置文件
description: 记录 config.py（JavDB 代理/域名设置）、gui_config.json（GUI 列布局和主题）、.env（密钥模板）和 merge.conf（NAS 迁移文件夹映射）。
openwiki:
  roles: [architecture]
  source_paths: [config.py, config.example.py, gui_config.json, .env.example, merge.conf]
---

# 主要配置文件

## `config.py` — JavDB 爬虫配置

所有 JavDB 爬虫的主要配置模块。包含：

**代理设置：**
- `SOCKS5_PROXY_HOST`（默认值：`127.0.0.1`）
- `SOCKS5_PROXY_PORT`（默认值：`1080`）
- `USE_SOCKS5_PROXY`（默认值：`True`）

**域名设置：**
- `JAVDB_PROXY_DOMAIN`：代理激活时使用的域名（`javdb.com`）
- `JAVDB_DIRECT_DOMAIN`：用于直接访问的镜像域名（例如 `javdb574.com`）
- `JAVDB_ALTERNATE_DIRECT_DOMAINS`：用于回退的已知镜像列表
- `get_javdb_base_url(use_proxy)`：返回当前激活的基础 URL
- `normalize_javdb_url(url, use_proxy)`：将 URL 重写为当前激活的域名
- `NO_PROXY_BYPASS_LIST`：即使配置了代理也直接访问的主机列表

**爬取行为：**
- `MAX_PAGES`：要爬取的页数（默认值：3）
- `MIN_DELAY` / `MAX_DELAY`：随机延迟范围（秒）（默认值：1-3）

**凭证：** 仅从环境变量中读取：
- `LOGIN_EMAIL = os.getenv("LOGIN_EMAIL")`
- `LOGIN_PASSWORD = os.getenv("LOGIN_PASSWORD")`

`config.example.py` 是一个可安全提交的变体，包含较旧的镜像域名值。

## `gui_config.json` — GUI 布局和主题

由两个 GUI 版本持久化保存。包含：

```json
{
  "columns": {
    "title":  { "width": 400, "position": 0, "text": "标题" },
    "actors": { "width": 86,  "position": 1, "text": "演员" },
    "stars":  { "width": 75,  "position": 2, "text": "星级" },
    ...
  },
  "theme": "dark"
}
```

- **columns**：各列的列宽、显示顺序（position）和显示文本
- **theme**：`"dark"` 或 `"light"` — 在 v2 中用户切换主题时持久化保存

## `.env` — 环境变量

切勿提交。`.env.example` 显示了预期的键：

```
# SiliconFlow API (video content analysis)
SILICONFLOW_API_KEY=your_api_key_here

# JavDB credentials (crawlers)
LOGIN_EMAIL=your_email
LOGIN_PASSWORD=your_password
```

在应用启动时由 `python-dotenv` 加载。如果未安装 `python-dotenv`，则回退到手动解析器。

## `merge.conf` — NAS 迁移文件夹映射

由 `migrate_av_to_nas.py` 使用的制表符分隔文件：

```
FolderName	Alias1	Alias2	Alias3
```

- 第 1 列：标准 NAS 文件夹名称
- 其余列：演员名称别名及拼写变体

迁移脚本使用此文件根据演员名称确定视频应放入哪个 NAS 文件夹。

## 另请参阅

- [JavSP 配置](JavSP_configs.md) — JavSP 特定配置
- [配置概览](overview.md) — 所有配置文件
- [快速入门](../quickstart.md) — 安装说明