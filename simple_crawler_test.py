#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化爬虫测试脚本
验证爬虫集成是否成功
"""

import sys
import json
import subprocess
import logging
from typing import Dict, Any, Optional
import time

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_javdb_crawler(dvdid: str) -> Dict[str, Any]:
    """测试JAVDB爬虫"""
    try:
        start_time = time.time()
        result = subprocess.run(
            [sys.executable, 'javdb_crawler_single.py', dvdid],
            capture_output=True,
            text=True,
            timeout=30
        )
        elapsed_time = time.time() - start_time
        
        if result.returncode == 0 and result.stdout.strip():
            try:
                data = json.loads(result.stdout.strip())
                return {
                    'success': True,
                    'data': data,
                    'time': elapsed_time,
                    'error': None
                }
            except json.JSONDecodeError as e:
                return {
                    'success': False,
                    'data': None,
                    'time': elapsed_time,
                    'error': f'JSON解析错误: {e}'
                }
        else:
            return {
                'success': False,
                'data': None,
                'time': elapsed_time,
                'error': f'命令执行失败: {result.stderr}'
            }
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'data': None,
            'time': 30.0,
            'error': '超时'
        }
    except Exception as e:
        return {
            'success': False,
            'data': None,
            'time': 0.0,
            'error': f'异常: {e}'
        }

def test_javsp_integration() -> Dict[str, Any]:
    """测试JavSP集成"""
    try:
        from javsp_crawler_manager import CrawlerManager
        from javsp_config import config
        
        # 检查配置
        logger.info(f"配置加载状态: {config is not None}")
        logger.info(f"爬虫配置: {config.crawler.selection if config else 'None'}")
        
        # 初始化管理器
        manager = CrawlerManager()
        
        # 检查可用爬虫
        test_id = 'SSIS-001'
        available_crawlers = manager.get_available_crawlers(test_id)
        
        return {
            'success': True,
            'config_loaded': config is not None,
            'crawler_selection': config.crawler.selection if config else None,
            'available_crawlers': list(available_crawlers.keys()),
            'crawler_count': len(available_crawlers),
            'error': None
        }
        
    except Exception as e:
        return {
            'success': False,
            'config_loaded': False,
            'crawler_selection': None,
            'available_crawlers': [],
            'crawler_count': 0,
            'error': str(e)
        }

def main():
    dvdid = sys.argv[1] if len(sys.argv) > 1 else 'SSIS-001'
    
    print("=" * 60)
    print("简化爬虫测试报告")
    print("=" * 60)
    
    # 测试JavSP集成
    print("\n🔧 JavSP集成测试:")
    integration_result = test_javsp_integration()
    if integration_result['success']:
        print(f"  ✅ 集成成功")
        print(f"     配置加载: {integration_result['config_loaded']}")
        print(f"     爬虫配置: {integration_result['crawler_selection']}")
        print(f"     可用爬虫: {integration_result['available_crawlers']}")
        print(f"     爬虫数量: {integration_result['crawler_count']}")
    else:
        print(f"  ❌ 集成失败: {integration_result['error']}")
    
    # 测试JAVDB爬虫
    print(f"\n📺 JAVDB爬虫测试 ({dvdid}):")
    javdb_result = test_javdb_crawler(dvdid)
    if javdb_result['success']:
        data = javdb_result['data']
        print(f"  ✅ 成功 ({javdb_result['time']:.2f}秒)")
        print(f"     标题: {data.get('title', 'N/A')}")
        print(f"     工作室: {data.get('studio', 'N/A')}")
        print(f"     发布日期: {data.get('release_date', 'N/A')}")
        if data.get('title') == '官方App下載':
            print("     ⚠️ 检测到'官方App下載'标题问题")
    else:
        print(f"  ❌ 失败 ({javdb_result['time']:.2f}秒): {javdb_result['error']}")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    
    # 总结
    print("\n📋 总结:")
    if integration_result['success']:
        print(f"  • JavSP集成: ✅ 成功 ({integration_result['crawler_count']}个爬虫可用)")
    else:
        print(f"  • JavSP集成: ❌ 失败")
    
    if javdb_result['success']:
        title_status = "有标题问题" if javdb_result['data'].get('title') == '官方App下載' else "正常"
        print(f"  • JAVDB爬虫: ✅ 成功 ({title_status})")
    else:
        print(f"  • JAVDB爬虫: ❌ 失败")

if __name__ == '__main__':
    main()