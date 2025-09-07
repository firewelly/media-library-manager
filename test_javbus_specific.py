#!/usr/bin/env python3
"""测试JavBus爬虫对特定番号的解析能力"""

import logging
import sys
from javsp_javbus import JavBusCrawler
from javsp_datatype import MovieInfo
from javsp_config import config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_javbus_crawler(dvd_id: str):
    """测试JavBus爬虫"""
    print(f"\n🔍 测试JavBus爬虫 ({dvd_id}):")
    
    try:
        # 初始化爬虫
        crawler = JavBusCrawler()
        print(f"   爬虫初始化成功")
        print(f"   基础URL: {crawler.base_url}")
        
        # 构造测试URL
        test_url = f"https://www.javbus.com/{dvd_id}"
        print(f"   测试URL: {test_url}")
        
        # 创建MovieInfo对象
        movie = MovieInfo()
        movie.dvdid = dvd_id
        
        # 测试爬取
        print(f"   开始爬取数据...")
        crawler.parse_data(movie)
        
        # 显示结果
        print(f"  ✅ 爬取成功")
        print(f"     标题: {movie.title or 'N/A'}")
        print(f"     工作室: {getattr(movie, 'studio', 'N/A') or getattr(movie, 'producer', 'N/A')}")
        print(f"     发布日期: {getattr(movie, 'release_date', 'N/A') or getattr(movie, 'publish_date', 'N/A')}")
        print(f"     演员: {', '.join(movie.actress) if movie.actress else 'N/A'}")
        print(f"     类型: {', '.join(movie.genre) if movie.genre else 'N/A'}")
        print(f"     时长: {movie.duration or 'N/A'}")
        print(f"     评分: {movie.score or 'N/A'}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ 爬取失败: {str(e)}")
        logger.exception(f"JavBus crawler failed for {dvd_id}")
        return False

def main():
    """主函数"""
    dvd_id = sys.argv[1] if len(sys.argv) > 1 else "CWPBD-89"
    
    print("="*60)
    print(f"JavBus爬虫专项测试")
    print(f"番号: {dvd_id}")
    print(f"代理配置: {config.network.proxy_server}")
    print("="*60)
    
    success = test_javbus_crawler(dvd_id)
    
    print("\n" + "="*60)
    print("测试完成！")
    print(f"结果: {'✅ 成功' if success else '❌ 失败'}")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())