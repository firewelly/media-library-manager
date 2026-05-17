# 关键字/番号格式映射文档

## 通用格式（标准AV番号）

| 格式 | 示例 | 匹配正则 |
|------|------|----------|
| 字母-数字 | IPX-177, ABP-123 | `([A-Z]+-\d+)` |
| FC2 | FC2-1234567 | `FC2-\d{5,7}` |
| 一本道 | 1pondo-123456_789 | `1pondo-\d{6}_\d{3}` |
| 加勒比 | carib-123456-789 | `carib-\d{6}-\d{3}` |
| 10musume | 10musume-123456_01 | `10musume-\d{6}_\d{2}` |
| Heydouga | heydouga-4017-12345 | `heydouga-\d{4}-\d{3,5}` |

## JAVDB 域名配置 (config.py)

| 配置项 | 说明 |
|--------|------|
| `JAVDB_PROXY_DOMAIN` | 使用代理时域名（默认: javdb.com） |
| `JAVDB_DIRECT_DOMAIN` | 不使用代理时域名（默认: javdb572.com） |
| `JAVDB_ALTERNATE_DIRECT_DOMAINS` | 备用镜像域名列表 |
| `USE_SOCKS5_PROXY` | 是否使用SOCKS5代理 |

## SOCKS5 代理配置

| 配置项 | 默认值 |
|--------|--------|
| 主机 | 127.0.0.1 |
| 端口 | 1080 (macOS/Linux), 8800 (Windows) |

## 错误标题检测

爬虫检测到以下标题时视为被屏蔽/错误信息，会触发回退：
- `官方App下載`
- `官方App下载`
- `Official App Download`
- `アプリダウンロード`
- `公式アプリ`

## 人工干预检测

爬虫检测到以下关键词时提示用户需要人工验证：
- `cloudflare`
- `验证页`
- `just a moment`
- `checking your browser`
- `登录状态缺失`
- `访问详情页需要登录`
- `login`
