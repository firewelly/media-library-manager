---
type: 参考
title: JavSP 配置文件
description: 介绍 JavSP 爬虫配置 — javsp_config.py（包含 CrawlerID 枚举、NetworkConfig 和数据类设置的 Python 模块）和 javsp_config.yaml（包含启用的爬虫、优先级和并行搜索设置的 YAML 文件）。
openwiki:
  roles: [architecture]
  source_paths: [javsp_config.py, javsp_config.yaml]
  symbols: [CrawlerID, NetworkConfig]
---

# JavSP 配置文件

JavSP 框架使用两个配置文件：一个用于代码级设置的 Python 模块，以及一个用于运行时可调参数的 YAML 文件。

## `javsp_config.py`

定义配置数据模型：

### `CrawlerID` 枚举
所有支持的爬虫标识符：
```
airav, avsox, avwiki, fanza, fc2, fc2fan, fc2ppvdb,
jav321, javbus, javlib, javmenu, mgstage, njav,
prestige, arzon, arzon_iv
```

### `NetworkConfig` 数据类
- `proxy_server`：SOCKS5 代理 URL（平台相关默认值：macOS/Linux 上为 `127.0.0.1:1080`，Windows 上为 `127.0.0.1:8800`）
- `retry`：重试次数（默认值：3）
- `timeout`：请求超时时间（秒）（默认值：30）
- `proxy_free`：每个爬虫的免代理 URL（无需代理即可访问的站点）

### `config` 全局变量
在导入时从 `javsp_config.yaml` 加载。提供当前生效的配置单例。

## `javsp_config.yaml`

运行时可调设置：

**网络：**
```yaml
network:
  proxy:
    enabled: true
    host: "127.0.0.1"
    port: 1080
    type: "socks5"
  timeout: 30
  retry:
    max_attempts: 3
    delay: 1.0
```

**爬虫选择与优先级：**
```yaml
crawlers:
  enabled:
    - "javbus"     # Priority 1
    - "javlib"     # Priority 2
    - "avsox"      # Priority 3
    - "fc2"        # Priority 4
  parallel:
    enabled: true
    max_workers: 4
    timeout: 60
```

**数据处理：**
```yaml
data:
  title_cleaning:
    enabled: true
```

## 另请参阅

- [JavSP 爬虫](../crawlers/JavSP_crawlers.md) — 配置的使用方式
- [配置概览](overview.md) — 所有配置文件