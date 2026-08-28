---
type: 概览
title: 配置概述
description: 所有配置文件的概述——Python 配置模块 (config.py)、GUI 配置 (gui_config.json)、环境变量 (.env) 以及 JavSP 爬虫配置。
openwiki:
  roles: [architecture]
  source_paths: [config.py, config.example.py, gui_config.json, .env.example, javsp_config.py, javsp_config.yaml]
---

# 配置概述

系统使用多个配置源，每个配置源都有其特定的作用范围。

## 配置文件

| 文件 | 格式 | 作用范围 | 包含内容 |
|------|--------|-------|----------|
| `config.py` | Python 模块 | JavDB 爬虫 | 代理、域名、凭据（来自环境变量）、延迟 |
| `config.example.py` | Python 模块 | JavDB 爬虫 | 可安全提交的示例（无实际值） |
| `gui_config.json` | JSON | GUI 布局与主题 | 列宽/位置、主题选择、窗口状态 |
| `.env` | 键值对 | 全局密钥 | API 密钥、登录凭据（切勿提交） |
| `.env.example` | 键值对 | 全局密钥 | 包含占位符的模板 |
| `javsp_config.py` | Python 模块 | JavSP 框架 | 爬虫 ID、网络配置、代理设置 |
| `javsp_config.yaml` | YAML | JavSP 框架 | 启用的爬虫、优先级、并行设置 |
| `merge.conf` | 制表符分隔 | NAS 迁移 | 演员到文件夹名称的映射 |

## 配置加载顺序

1. 首先通过 `python-dotenv`（或手动解析器回退）加载 `.env` 文件
2. `config.py` 读取环境变量（`LOGIN_EMAIL`、`LOGIN_PASSWORD`、`SILICONFLOW_API_KEY`）
3. GUI 应用程序在启动时读取 `gui_config.json` 以获取列布局和主题
4. JavSP 框架通过 `javsp_config.py` 读取 `javsp_config.yaml`

## 另请参阅

- [主配置](main_configs.md) — 详细的 `config.py`、`gui_config.json`、`.env` 文档
- [JavSP 配置](JavSP_configs.md) — JavSP 框架配置
- [快速开始](../quickstart.md) — 环境变量设置