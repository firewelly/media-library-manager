#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
综合爬虫测试脚本
测试多个番号在不同爬虫中的搜索结果
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
            timeout=60
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
            'time': 60.0,
            'error': '超时'
        }
    except Exception as e:
        return {
            'success': False,
            'data': None,
            'time': 0.0,
            'error': f'异常: {e}'
        }

def test_javsp_crawlers(dvdid: str) -> Dict[str, Any]:
    """测试JavSP爬虫"""
    try:
        from javsp_crawler_manager import CrawlerManager
        
        start_time = time.time()
        manager = CrawlerManager()
        available_crawlers = manager.get_available_crawlers(dvdid)
        
        logger.info(f"可用爬虫: {list(available_crawlers.keys())}")
        
        results = {}
        for crawler_name in available_crawlers.keys():
            try:
                crawler_start = time.time()
                movie_info = manager.search_movie_single(dvdid, crawler_name)
                crawler_time = time.time() - crawler_start
                
                if movie_info:
                    results[crawler_name] = {
                        'success': True,
                        'data': {
                            'title': movie_info.title,
                            'video_id': movie_info.dvdid,
                            'release_date': movie_info.release_date,
                            'duration': movie_info.duration,
                            'studio': movie_info.studio,
                            'actors': [actor.name for actor in movie_info.actress] if movie_info.actress else [],
                            'tags': movie_info.genre if movie_info.genre else [],
                            'cover_image_url': movie_info.cover
                        },
                        'time': crawler_time,
                        'error': None
                    }
                else:
                    results[crawler_name] = {
                        'success': False,
                        'data': None,
                        'time': crawler_time,
                        'error': '未找到'
                    }
            except Exception as e:
                crawler_time = time.time() - crawler_start
                results[crawler_name] = {
                    'success': False,
                    'data': None,
                    'time': crawler_time,
                    'error': str(e)
                }
        
        total_time = time.time() - start_time
        return {
            'success': len(results) > 0,
            'crawlers': results,
            'total_time': total_time,
            'available_count': len(available_crawlers)
        }
        
    except Exception as e:
        return {
            'success': False,
            'crawlers': {},
            'total_time': 0.0,
            'available_count': 0,
            'error': str(e)
        }

def main():
    # 测试的番号列表
    test_dvdids = [
        'CWPBD-89',
        'SSIS-001',
        'MIDE-001',
        'PRED-001'
    ]
    
    if len(sys.argv) > 1:
        test_dvdids = [sys.argv[1]]
    
    print("=" * 80)
    print("综合爬虫测试报告")
    print("=" * 80)
    
    for dvdid in test_dvdids:
        print(f"\n🔍 测试番号: {dvdid}")
        print("-" * 60)
        
        # 测试JAVDB爬虫
        print("\n📺 JAVDB爬虫测试:")
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
        
        # 测试JavSP爬虫
        print("\n🕷️ JavSP爬虫测试:")
        javsp_result = test_javsp_crawlers(dvdid)
        if javsp_result['success']:
            print(f"  可用爬虫数量: {javsp_result['available_count']}")
            for crawler_name, result in javsp_result['crawlers'].items():
                if result['success']:
                    data = result['data']
                    print(f"  ✅ {crawler_name} 成功 ({result['time']:.2f}秒)")
                    print(f"     标题: {data.get('title', 'N/A')}")
                    print(f"     工作室: {data.get('studio', 'N/A')}")
                    print(f"     发布日期: {data.get('release_date', 'N/A')}")
                else:
                    print(f"  ❌ {crawler_name} 失败 ({result['time']:.2f}秒): {result['error']}")
        else:
            print(f"  ❌ JavSP初始化失败: {javsp_result.get('error', '未知错误')}")
    
    print("\n" + "=" * 80)
    print("测试完成！")

if __name__ == '__main__':
    main()