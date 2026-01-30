"""JavSP爬虫配置文件"""
import os
import platform
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

class CrawlerID(str, Enum):
    """爬虫ID枚举"""
    airav = 'airav'
    avsox = 'avsox'
    avwiki = 'avwiki'
    fanza = 'fanza'
    fc2 = 'fc2'
    fc2fan = 'fc2fan'
    fc2ppvdb = 'fc2ppvdb'
    jav321 = 'jav321'
    javbus = 'javbus'
    javlib = 'javlib'
    javmenu = 'javmenu'
    mgstage = 'mgstage'
    njav = 'njav'
    prestige = 'prestige'
    arzon = 'arzon'
    arzon_iv = 'arzon_iv'

@dataclass
class NetworkConfig:
    """网络配置"""
    proxy_server: Optional[str] = None
    retry: int = 3
    timeout: int = 30
    proxy_free: Dict[str, str] = None
    
    def __post_init__(self):
        if self.proxy_server is None:
            if platform.system().lower() == 'windows':
                self.proxy_server = "socks5://127.0.0.1:8800"
            else:
                self.proxy_server = "socks5://127.0.0.1:1080"
        if self.proxy_free is None:
            # 为某些站点配置免代理URL
            self.proxy_free = {
                CrawlerID.avsox: "https://avsox.website",
                CrawlerID.javbus: "https://www.javbus.com",
                CrawlerID.javlib: "https://www.javlibrary.com",
                CrawlerID.fanza: "https://www.dmm.co.jp",
                CrawlerID.mgstage: "https://www.mgstage.com",
                CrawlerID.fc2: "https://adult.contents.fc2.com",
                CrawlerID.prestige: "https://www.prestige-av.com",
            }

@dataclass
class CrawlerConfig:
    """爬虫配置"""
    # 普通番号爬虫选择（跳过javdb）
    normal_crawlers: List[str] = None
    # FC2番号爬虫选择
    fc2_crawlers: List[str] = None
    # 必需字段
    required_keys: List[str] = None
    # 是否努力工作模式
    hardworking: bool = True
    # 爬取后休眠时间（秒）
    sleep_after_scraping: float = 1.0
    # 爬虫选择字典（兼容JavSP原始接口）
    selection: Dict[str, List[str]] = None
    # FC2爬虫选择（兼容JavSP原始接口）
    fc2_selection: List[str] = None
    # 是否在首次调用时做可用性探测（启动阶段不探测）
    probe_on_first_use: bool = True
    
    def __post_init__(self):
        if self.normal_crawlers is None:
            # 只使用现有的爬虫文件
            self.normal_crawlers = [
                'javbus',
                'javlib',
                'avsox',
            ]
        
        if self.fc2_crawlers is None:
            self.fc2_crawlers = [
                'fc2',
                'fc2fan',
                'fc2ppvdb',
            ]
        
        if self.required_keys is None:
            self.required_keys = [
                'title',
                'actress',
                'publish_date',
                'duration',
                'genre',
                'cover'
            ]
        
        # 设置selection字典以兼容JavSP原始接口
        if self.selection is None:
            self.selection = {
                'normal': self.normal_crawlers,
                'fc2': self.fc2_crawlers,
                'cid': self.normal_crawlers  # 通用ID爬虫
            }
        
        # 设置fc2_selection以兼容JavSP原始接口
        if self.fc2_selection is None:
            self.fc2_selection = self.fc2_crawlers

@dataclass
class JavSPConfig:
    """JavSP配置类"""
    network: NetworkConfig
    crawler: CrawlerConfig
    
    def __init__(self):
        self.network = NetworkConfig()
        self.crawler = CrawlerConfig()

# 全局配置实例
config = JavSPConfig()

def get_proxy_settings():
    """获取代理设置"""
    if config.network.proxy_server:
        return {
            'http': config.network.proxy_server,
            'https': config.network.proxy_server
        }
    return None

def get_crawler_list(data_type='normal'):
    """获取爬虫列表"""
    if data_type == 'fc2':
        return config.crawler.fc2_crawlers
    else:
        return config.crawler.normal_crawlers

def is_crawler_enabled(crawler_id: str) -> bool:
    """检查爬虫是否启用"""
    all_crawlers = config.crawler.normal_crawlers + config.crawler.fc2_crawlers
    return crawler_id in all_crawlers
