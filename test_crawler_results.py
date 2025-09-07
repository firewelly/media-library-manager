#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试各个爬虫对特定番号的搜索结果
Test crawler results for specific movie codes
"""

import sys
import os
import json
import time
from typing import Dict, Any, Optional
import logging

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_javdb_crawler(code: str) -> Optional[Dict[str, Any]]:
    """测试JAVDB爬虫"""
    try:
        import subprocess
        import json
        
        logger.info(f"测试JAVDB爬虫搜索: {code}")
        
        # 运行javdb_crawler_single.py
        result = subprocess.run(
            [sys.executable, 'javdb_crawler_single.py', code],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            try:
                # 尝试解析JSON输出
                output_lines = result.stdout.strip().split('\n')
                for line in output_lines:
                    if line.strip().startswith('{'):
                        return json.loads(line)
                return {"status": "success", "message": "找到结果但无法解析JSON", "raw_output": result.stdout}
            except json.JSONDecodeError:
                return {"status": "success", "message": "找到结果但无法解析JSON", "raw_output": result.stdout}
        else:
            return {"status": "error", "message": result.stderr or "未知错误", "raw_output": result.stdout}
            
    except Exception as e:
        logger.error(f"JAVDB爬虫测试失败: {e}")
        return {"status": "error", "message": str(e)}

def test_javsp_crawlers(code: str) -> Dict[str, Any]:
    """测试JavSP爬虫"""
    results = {}
    
    try:
        from javsp_crawler_manager import CrawlerManager
        
        manager = CrawlerManager()
        logger.info(f"测试JavSP爬虫搜索: {code}")
        
        # 获取可用的爬虫
        available_crawlers = manager.get_available_crawlers(code)
        logger.info(f"可用爬虫: {list(available_crawlers.keys())}")
        
        # 测试每个爬虫
        for crawler_name in available_crawlers.keys():
            try:
                logger.info(f"测试爬虫: {crawler_name}")
                start_time = time.time()
                
                movie_info = manager.search_movie_single(code, crawler_name)
                
                end_time = time.time()
                
                if movie_info:
                    results[crawler_name] = {
                        "status": "success",
                        "title": getattr(movie_info, 'title', 'N/A'),
                        "code": getattr(movie_info, 'dvdid', 'N/A'),
                        "actress": getattr(movie_info, 'actress', []),
                        "genre": getattr(movie_info, 'genre', []),
                        "release_date": getattr(movie_info, 'release', 'N/A'),
                        "duration": getattr(movie_info, 'duration', 'N/A'),
                        "director": getattr(movie_info, 'director', 'N/A'),
                        "studio": getattr(movie_info, 'studio', 'N/A'),
                        "series": getattr(movie_info, 'series', 'N/A'),
                        "cover_url": getattr(movie_info, 'cover', 'N/A'),
                        "search_time": f"{end_time - start_time:.2f}秒"
                    }
                else:
                    results[crawler_name] = {
                        "status": "not_found",
                        "message": "未找到相关信息",
                        "search_time": f"{end_time - start_time:.2f}秒"
                    }
                    
            except Exception as e:
                logger.error(f"爬虫 {crawler_name} 测试失败: {e}")
                results[crawler_name] = {
                    "status": "error",
                    "message": str(e)
                }
                
    except Exception as e:
        logger.error(f"JavSP爬虫测试失败: {e}")
        results["error"] = {"status": "error", "message": str(e)}
        
    return results

def main():
    """主函数"""
    # 测试的番号
    test_codes = ["CWPBD-89"]
    
    if len(sys.argv) > 1:
        test_codes = sys.argv[1:]
    
    print("=" * 80)
    print("爬虫测试结果对比")
    print("=" * 80)
    
    for code in test_codes:
        print(f"\n🔍 测试番号: {code}")
        print("-" * 60)
        
        # 测试JAVDB爬虫
        print("\n📺 JAVDB爬虫测试:")
        javdb_result = test_javdb_crawler(code)
        if javdb_result:
            if javdb_result["status"] == "success":
                print("  ✅ 成功")
                if "title" in javdb_result:
                    print(f"  标题: {javdb_result.get('title', 'N/A')}")
                if "raw_output" in javdb_result:
                    print(f"  原始输出: {javdb_result['raw_output'][:200]}...")
            else:
                print(f"  ❌ 失败: {javdb_result['message']}")
        else:
            print("  ❌ 无结果")
        
        # 测试JavSP爬虫
        print("\n🕷️ JavSP爬虫测试:")
        javsp_results = test_javsp_crawlers(code)
        
        if javsp_results:
            for crawler_name, result in javsp_results.items():
                if result["status"] == "success":
                    print(f"  ✅ {crawler_name}: {result['title']} ({result['search_time']})")
                    print(f"     演员: {', '.join(result.get('actress', []))}")
                    print(f"     发行日期: {result.get('release_date', 'N/A')}")
                    print(f"     制作商: {result.get('studio', 'N/A')}")
                elif result["status"] == "not_found":
                    print(f"  ⚠️ {crawler_name}: 未找到 ({result.get('search_time', 'N/A')})")
                else:
                    print(f"  ❌ {crawler_name}: {result['message']}")
        else:
            print("  ❌ 无可用爬虫")
        
        print("\n" + "=" * 60)
    
    print("\n测试完成！")

if __name__ == "__main__":
    main()