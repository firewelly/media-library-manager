# Example configuration for JavDB crawler (safe to commit)
import os

# SOCKS5 proxy settings
SOCKS5_PROXY_HOST = "127.0.0.1"
SOCKS5_PROXY_PORT = 1080

# JavDB 域名设置（按是否使用代理选择不同域名）
JAVDB_PROXY_DOMAIN = "javdb.com"           # 使用代理时的主域名
JAVDB_DIRECT_DOMAIN = "javdb562.com"       # 不使用代理时的镜像域名（可按需修改）

# 历史或备用镜像域名（不使用代理时常变化，统一在此维护）
JAVDB_ALTERNATE_DIRECT_DOMAINS = [
    "javdb561.com",
    "javdb562.com",
    "www.javdb561.com",
    "www.javdb562.com",
]

def get_javdb_base_url(use_proxy: bool) -> str:
    domain = JAVDB_PROXY_DOMAIN if use_proxy else JAVDB_DIRECT_DOMAIN
    return f"https://{domain}"

# 不使用代理时的 bypass 列表（直连这些主机）
NO_PROXY_BYPASS_LIST = [
    "localhost",
    "127.0.0.1",
    "<-loopback>",
    JAVDB_DIRECT_DOMAIN,
]

def normalize_javdb_url(url: str, use_proxy: bool) -> str:
    """将 url 中的 JavDB 域名归一为当前主域名（根据是否使用代理选择）。"""
    try:
        from urllib.parse import urlparse, urlunparse
        p = urlparse(url)
        host = (p.netloc or '').lower()
        if not host:
            return url
        target = JAVDB_PROXY_DOMAIN if use_proxy else JAVDB_DIRECT_DOMAIN
        alternates = [
            JAVDB_PROXY_DOMAIN,
            f"www.{JAVDB_PROXY_DOMAIN}",
            *JAVDB_ALTERNATE_DIRECT_DOMAINS,
        ]
        if host in [d.lower() for d in alternates]:
            p = p._replace(netloc=target)
            return urlunparse(p)
        return url
    except Exception:
        return url

# Login credentials (read from environment; do NOT hardcode)
LOGIN_EMAIL = os.getenv("LOGIN_EMAIL") or ""
LOGIN_PASSWORD = os.getenv("LOGIN_PASSWORD") or ""

# Number of pages to crawl (for general crawling)
MAX_PAGES = 3

# Delay settings (in seconds)
MIN_DELAY = 1
MAX_DELAY = 3

# Whether to use SOCKS5 proxy when accessing JavDB
USE_SOCKS5_PROXY = True

# Base URL for JavDB, derived from domain configuration and proxy usage
BASE_URL = get_javdb_base_url(USE_SOCKS5_PROXY)