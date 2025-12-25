#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JavSP配置管理模块
JavSP Configuration Manager Module

用于加载和管理JavSP爬虫系统的配置文件
For loading and managing JavSP crawler system configuration files
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

class ConfigManager:
    """配置管理器类"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径，如果为None则使用默认路径
        """
        if config_path is None:
            # 默认配置文件路径
            current_dir = Path(__file__).parent
            config_path = current_dir / "javsp_config.yaml"
        
        self.config_path = Path(config_path)
        self._config = None
        self._load_config()
    
    def _load_config(self) -> None:
        """加载配置文件"""
        try:
            if not self.config_path.exists():
                logger.warning(f"配置文件不存在: {self.config_path}，使用默认配置")
                self._config = self._get_default_config()
                return
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f)
            
            logger.info(f"成功加载配置文件: {self.config_path}")
            
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}，使用默认配置")
            self._config = self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            'network': {
                'proxy': {
                    'enabled': True,
                    'host': '127.0.0.1',
                    'port': 1080,
                    'type': 'socks5'
                },
                'timeout': 30,
                'retry': {
                    'max_attempts': 3,
                    'delay': 1.0
                },
                'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            },
            'crawlers': {
                'enabled': ['javbus', 'javlib', 'avsox', 'fc2'],
                'priority': {
                    'javbus': 1,
                    'javlib': 2,
                    'avsox': 3,
                    'fc2': 4
                },
                'parallel': {
                    'enabled': True,
                    'max_workers': 4,
                    'timeout': 60
                }
            },
            'data': {
                'title_cleaning': {
                    'enabled': True,
                    'remove_keywords': [
                        '官方App下載', '官方App下载', '官方APP下载',
                        '官方应用下载', 'Download Official App', 'Official App Download'
                    ]
                },
                'validation': {
                    'require_title': True,
                    'require_number': True,
                    'require_cover': False
                }
            },
            'logging': {
                'level': 'INFO',
                'colored': True,
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            },
            'performance': {
                'request_delay': 0.5,
                'connection_pool_size': 10,
                'max_connections': 20
            }
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值，支持点号分隔的嵌套键
        
        Args:
            key: 配置键，支持 'network.proxy.host' 格式
            default: 默认值
        
        Returns:
            配置值
        """
        keys = key.split('.')
        value = self._config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value: Any) -> None:
        """
        设置配置值
        
        Args:
            key: 配置键，支持 'network.proxy.host' 格式
            value: 配置值
        """
        keys = key.split('.')
        config = self._config
        
        # 导航到最后一级的父级
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        # 设置值
        config[keys[-1]] = value
    
    def save(self, path: Optional[str] = None) -> None:
        """
        保存配置到文件
        
        Args:
            path: 保存路径，如果为None则使用原路径
        """
        save_path = Path(path) if path else self.config_path
        
        try:
            with open(save_path, 'w', encoding='utf-8') as f:
                yaml.dump(self._config, f, default_flow_style=False, 
                         allow_unicode=True, indent=2)
            logger.info(f"配置已保存到: {save_path}")
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
    
    def reload(self) -> None:
        """重新加载配置文件"""
        self._load_config()
    
    # 便捷方法
    def get_proxy_config(self) -> Dict[str, Any]:
        """获取代理配置"""
        return self.get('network.proxy', {})
    
    def get_crawler_config(self) -> Dict[str, Any]:
        """获取爬虫配置"""
        return self.get('crawlers', {})
    
    def get_enabled_crawlers(self) -> List[str]:
        """获取启用的爬虫列表"""
        return self.get('crawlers.enabled', [])
    
    def get_crawler_priority(self) -> Dict[str, int]:
        """获取爬虫优先级"""
        return self.get('crawlers.priority', {})
    
    def get_title_cleaning_keywords(self) -> List[str]:
        """获取标题清理关键词"""
        return self.get('data.title_cleaning.remove_keywords', [])
    
    def is_proxy_enabled(self) -> bool:
        """检查是否启用代理"""
        return self.get('network.proxy.enabled', False)
    
    def is_parallel_enabled(self) -> bool:
        """检查是否启用并行搜索"""
        return self.get('crawlers.parallel.enabled', True)
    
    def get_max_workers(self) -> int:
        """获取最大并发数"""
        return self.get('crawlers.parallel.max_workers', 4)
    
    def get_request_timeout(self) -> int:
        """获取请求超时时间"""
        return self.get('network.timeout', 30)
    
    def get_user_agent(self) -> str:
        """获取User-Agent"""
        return self.get('network.user_agent', 
                       'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36')
    
    def get_log_level(self) -> str:
        """获取日志级别"""
        return self.get('logging.level', 'INFO')
    
    def is_colored_logging_enabled(self) -> bool:
        """检查是否启用彩色日志"""
        return self.get('logging.colored', True)
    
    def __str__(self) -> str:
        """返回配置的字符串表示"""
        return f"ConfigManager(config_path={self.config_path})"
    
    def __repr__(self) -> str:
        """返回配置的详细表示"""
        return f"ConfigManager(config_path={self.config_path}, config={self._config})"

# 全局配置实例
_global_config = None

def get_config(config_path: Optional[str] = None) -> ConfigManager:
    """
    获取全局配置实例
    
    Args:
        config_path: 配置文件路径
    
    Returns:
        ConfigManager实例
    """
    global _global_config
    if _global_config is None or config_path is not None:
        _global_config = ConfigManager(config_path)
    return _global_config

def reload_config() -> None:
    """重新加载全局配置"""
    global _global_config
    if _global_config:
        _global_config.reload()

# 创建全局配置管理器实例
config_manager = ConfigManager()

if __name__ == "__main__":
    # 测试代码
    config = ConfigManager()

    print("=== 配置管理器测试 ===")
    print(f"代理配置: {config.get_proxy_config()}")
    print(f"启用的爬虫: {config.get_enabled_crawlers()}")
    print(f"爬虫优先级: {config.get_crawler_priority()}")
    print(f"标题清理关键词: {config.get_title_cleaning_keywords()}")
    print(f"是否启用代理: {config.is_proxy_enabled()}")
    print(f"是否启用并行: {config.is_parallel_enabled()}")
    print(f"最大并发数: {config.get_max_workers()}")
    print(f"请求超时: {config.get_request_timeout()}")
    print(f"User-Agent: {config.get_user_agent()}")
    print(f"日志级别: {config.get_log_level()}")