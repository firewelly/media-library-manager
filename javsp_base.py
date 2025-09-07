"""JavSP网络请求基础模块"""
import logging
import time
import requests
from typing import Optional, Dict, Any
from urllib.parse import urljoin, urlparse
from lxml import etree, html
import cloudscraper

from javsp_config import config, get_proxy_settings

logger = logging.getLogger(__name__)

class RequestSession:
    """请求会话类"""
    
    def __init__(self):
        self.session = None
        self.cloudscraper_session = None
        self._init_session()
    
    def _init_session(self):
        """初始化会话"""
        # 普通requests会话
        self.session = requests.Session()
        
        # 设置User-Agent
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.session.headers.update(headers)
        
        # 设置代理
        proxy_settings = get_proxy_settings()
        if proxy_settings:
            self.session.proxies.update(proxy_settings)
            logger.info(f"Using proxy: {config.network.proxy_server}")
            # 当使用SOCKS代理时，禁用SSL验证以避免连接问题
            if 'socks' in config.network.proxy_server.lower():
                self.session.verify = False
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                logger.info("SSL verification disabled for SOCKS proxy")
        
        # 设置超时
        self.session.timeout = config.network.timeout
        
        # CloudScraper会话（用于处理CloudFlare挑战）
        try:
            self.cloudscraper_session = cloudscraper.create_scraper(
                browser={
                    'browser': 'chrome',
                    'platform': 'windows',
                    'desktop': True
                }
            )
            
            if proxy_settings:
                self.cloudscraper_session.proxies.update(proxy_settings)
            
            self.cloudscraper_session.timeout = config.network.timeout
            
        except Exception as e:
            logger.warning(f"Failed to create CloudScraper session: {e}")
            self.cloudscraper_session = None
    
    def get(self, url: str, use_cloudscraper: bool = False, **kwargs) -> requests.Response:
        """GET请求"""
        session = self.cloudscraper_session if use_cloudscraper and self.cloudscraper_session else self.session
        
        for attempt in range(config.network.retry + 1):
            try:
                response = session.get(url, **kwargs)
                response.raise_for_status()
                return response
            except Exception as e:
                logger.warning(f"Request failed (attempt {attempt + 1}/{config.network.retry + 1}): {e}")
                if attempt < config.network.retry:
                    time.sleep(1)
                else:
                    raise
    
    def post(self, url: str, use_cloudscraper: bool = False, **kwargs) -> requests.Response:
        """POST请求"""
        session = self.cloudscraper_session if use_cloudscraper and self.cloudscraper_session else self.session
        
        for attempt in range(config.network.retry + 1):
            try:
                response = session.post(url, **kwargs)
                response.raise_for_status()
                return response
            except Exception as e:
                logger.warning(f"Request failed (attempt {attempt + 1}/{config.network.retry + 1}): {e}")
                if attempt < config.network.retry:
                    time.sleep(1)
                else:
                    raise

# 全局会话实例
_session = RequestSession()

def get_html(url: str, encoding: str = 'utf-8', use_cloudscraper: bool = False, **kwargs) -> etree._Element:
    """获取HTML并解析为lxml元素"""
    try:
        response = _session.get(url, use_cloudscraper=use_cloudscraper, **kwargs)
        
        # 设置编码
        if encoding:
            response.encoding = encoding
        
        # 解析HTML
        html_content = response.text
        if not html_content.strip():
            raise ValueError(f"Empty response from {url}")
        
        # 使用lxml解析
        try:
            tree = html.fromstring(html_content)
        except Exception as e:
            logger.warning(f"Failed to parse HTML with lxml: {e}, trying etree")
            tree = etree.HTML(html_content)
        
        return tree
        
    except Exception as e:
        logger.error(f"Failed to get HTML from {url}: {e}")
        raise

def post_html(url: str, data: Dict[str, Any] = None, encoding: str = 'utf-8', use_cloudscraper: bool = False, **kwargs) -> etree._Element:
    """POST请求并解析HTML"""
    try:
        response = _session.post(url, data=data, use_cloudscraper=use_cloudscraper, **kwargs)
        
        # 设置编码
        if encoding:
            response.encoding = encoding
        
        # 解析HTML
        html_content = response.text
        if not html_content.strip():
            raise ValueError(f"Empty response from {url}")
        
        # 使用lxml解析
        try:
            tree = html.fromstring(html_content)
        except Exception as e:
            logger.warning(f"Failed to parse HTML with lxml: {e}, trying etree")
            tree = etree.HTML(html_content)
        
        return tree
        
    except Exception as e:
        logger.error(f"Failed to post to {url}: {e}")
        raise

def get_response(url: str, use_cloudscraper: bool = False, **kwargs) -> requests.Response:
    """获取原始响应对象"""
    return _session.get(url, use_cloudscraper=use_cloudscraper, **kwargs)

def post_response(url: str, data: Dict[str, Any] = None, use_cloudscraper: bool = False, **kwargs) -> requests.Response:
    """POST请求获取原始响应对象"""
    return _session.post(url, data=data, use_cloudscraper=use_cloudscraper, **kwargs)

def is_url_accessible(url: str, timeout: int = 10) -> bool:
    """检查URL是否可访问"""
    try:
        response = _session.get(url, timeout=timeout)
        return response.status_code == 200
    except Exception:
        return False

def normalize_url(url: str, base_url: str = None) -> str:
    """标准化URL"""
    if not url:
        return ''
    
    # 如果是相对URL，转换为绝对URL
    if base_url and not url.startswith(('http://', 'https://')):
        url = urljoin(base_url, url)
    
    return url

def extract_domain(url: str) -> str:
    """提取域名"""
    try:
        parsed = urlparse(url)
        return parsed.netloc
    except Exception:
        return ''

def sleep_after_request():
    """请求后休眠"""
    if config.crawler.sleep_after_scraping > 0:
        time.sleep(config.crawler.sleep_after_scraping)

# 异常类定义
class CrawlerError(Exception):
    """爬虫基础异常"""
    pass

class MovieNotFoundError(CrawlerError):
    """影片未找到异常"""
    def __init__(self, crawler_name: str, movie_id: str, available_ids: list = None):
        self.crawler_name = crawler_name
        self.movie_id = movie_id
        self.available_ids = available_ids or []
        
        message = f"Movie '{movie_id}' not found in {crawler_name}"
        if self.available_ids:
            message += f". Available IDs: {self.available_ids[:10]}"  # 只显示前10个
        
        super().__init__(message)

class NetworkError(CrawlerError):
    """网络错误异常"""
    pass

class ParseError(CrawlerError):
    """解析错误异常"""
    pass