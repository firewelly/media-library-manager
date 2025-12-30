#!/usr/bin/env python3
"""JavSP爬虫系统使用示例"""
import logging
import sys
import os
from typing import List, Optional

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from javsp_crawler_manager import search_movie, batch_search, get_crawler_status
from javsp_datatype import MovieInfo
from javsp_config import config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('javsp_crawler.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

def print_movie_info(movie: MovieInfo, dvdid: str = None):
    """打印影片信息"""
    if not movie:
        print(f"❌ 未找到影片信息: {dvdid}")
        return
    
    print(f"✅ 影片信息: {movie.dvdid}")
    print(f"   标题: {movie.title or 'N/A'}")
    print(f"   演员: {', '.join(movie.actress) if movie.actress else 'N/A'}")
    print(f"   时长: {movie.duration}分钟" if movie.duration else "   时长: N/A")
    print(f"   类型: {', '.join(movie.genre) if movie.genre else 'N/A'}")
    print(f"   制作商: {movie.producer or 'N/A'}")
    print(f"   发行商: {movie.publisher or 'N/A'}")
    print(f"   发行日期: {movie.publish_date or 'N/A'}")
    print(f"   评分: {movie.score or 'N/A'}")
    print(f"   封面: {movie.cover or 'N/A'}")
    print(f"   URL: {movie.url or 'N/A'}")
    print()

def test_single_search():
    """测试单个影片搜索"""
    print("=== 单个影片搜索测试 ===")
    
    # 测试普通番号
    test_ids = [
        'IPX-177',
        'SSIS-001', 
        'PRED-100',
        'MIDE-500'
    ]
    
    for dvdid in test_ids:
        print(f"\n🔍 搜索: {dvdid}")
        try:
            movie = search_movie(dvdid)
            print_movie_info(movie, dvdid)
        except Exception as e:
            logger.error(f"搜索 {dvdid} 时出错: {e}")
            print(f"❌ 搜索出错: {e}")

def test_fc2_search():
    """测试FC2影片搜索"""
    print("=== FC2影片搜索测试 ===")
    
    # 测试FC2番号
    fc2_ids = [
        'FC2-718323',
        'FC2-1234567',  # 可能不存在的番号
    ]
    
    for dvdid in fc2_ids:
        print(f"\n🔍 搜索FC2: {dvdid}")
        try:
            movie = search_movie(dvdid)
            print_movie_info(movie, dvdid)
        except Exception as e:
            logger.error(f"搜索 {dvdid} 时出错: {e}")
            print(f"❌ 搜索出错: {e}")

def test_batch_search():
    """测试批量搜索"""
    print("=== 批量搜索测试 ===")
    
    batch_ids = [
        'IPX-177',
        'SSIS-001',
        'FC2-718323',
        'NONEXISTENT-123'  # 不存在的番号
    ]
    
    print(f"\n🔍 批量搜索: {', '.join(batch_ids)}")
    
    try:
        results = batch_search(batch_ids, use_parallel=True, max_workers=3)
        
        print(f"\n📊 批量搜索结果 ({len([r for r in results.values() if r])}/{len(batch_ids)} 成功):")
        
        for dvdid, movie in results.items():
            if movie:
                print(f"  ✅ {dvdid}: {movie.title}")
            else:
                print(f"  ❌ {dvdid}: 未找到")
        
        print("\n详细信息:")
        for dvdid, movie in results.items():
            if movie:
                print(f"\n--- {dvdid} ---")
                print_movie_info(movie)
                
    except Exception as e:
        logger.error(f"批量搜索时出错: {e}")
        print(f"❌ 批量搜索出错: {e}")

def test_parallel_vs_sequential():
    """测试并行搜索 vs 顺序搜索的性能"""
    print("=== 并行 vs 顺序搜索性能测试 ===")
    
    test_ids = ['IPX-177', 'SSIS-001']
    
    import time
    
    # 顺序搜索
    print("\n🔄 顺序搜索测试...")
    start_time = time.time()
    for dvdid in test_ids:
        movie = search_movie(dvdid, use_parallel=False)
        if movie:
            print(f"  ✅ {dvdid}: {movie.title}")
        else:
            print(f"  ❌ {dvdid}: 未找到")
    sequential_time = time.time() - start_time
    
    # 并行搜索
    print("\n⚡ 并行搜索测试...")
    start_time = time.time()
    for dvdid in test_ids:
        movie = search_movie(dvdid, use_parallel=True)
        if movie:
            print(f"  ✅ {dvdid}: {movie.title}")
        else:
            print(f"  ❌ {dvdid}: 未找到")
    parallel_time = time.time() - start_time
    
    print(f"\n📈 性能对比:")
    print(f"  顺序搜索: {sequential_time:.2f}秒")
    print(f"  并行搜索: {parallel_time:.2f}秒")
    if sequential_time > 0:
        speedup = sequential_time / parallel_time
        print(f"  加速比: {speedup:.2f}x")

def show_crawler_status():
    """显示爬虫状态"""
    print("=== 爬虫状态检查 ===")
    
    try:
        status = get_crawler_status()
        
        print("\n🕷️ 普通番号爬虫:")
        for name, info in status.get('normal_crawlers', {}).items():
            status_icon = "✅" if info.get('available') else "❌"
            print(f"  {status_icon} {name}: {info.get('base_url', 'Unknown')}")
            if 'error' in info:
                print(f"      错误: {info['error']}")
        
        print("\n🎬 FC2爬虫:")
        for name, info in status.get('fc2_crawlers', {}).items():
            status_icon = "✅" if info.get('available') else "❌"
            print(f"  {status_icon} {name}: {info.get('base_url', 'Unknown')}")
            if 'error' in info:
                print(f"      错误: {info['error']}")
                
    except Exception as e:
        logger.error(f"获取爬虫状态时出错: {e}")
        print(f"❌ 获取爬虫状态出错: {e}")

def show_config_info():
    """显示配置信息"""
    print("=== 配置信息 ===")
    
    print(f"\n🌐 网络配置:")
    print(f"  代理服务器: {config.network.proxy_server}")
    print(f"  免代理URL: {len(config.network.proxy_free)} 个站点")
    
    print(f"\n🕷️ 爬虫配置:")
    print(f"  普通番号爬虫: {', '.join(config.crawler.selection)}")
    print(f"  FC2爬虫: {', '.join(config.crawler.fc2_selection)}")
    print(f"  必需字段: {', '.join(config.crawler.required_keys)}")

def interactive_search():
    """交互式搜索"""
    print("=== 交互式搜索 ===")
    print("输入番号进行搜索，输入 'quit' 退出")
    
    while True:
        try:
            dvdid = input("\n🔍 请输入番号: ").strip()
            
            if dvdid.lower() in ['quit', 'exit', 'q']:
                print("👋 再见!")
                break
            
            if not dvdid:
                print("❌ 请输入有效的番号")
                continue
            
            print(f"\n正在搜索 {dvdid}...")
            movie = search_movie(dvdid)
            print_movie_info(movie, dvdid)
            
        except KeyboardInterrupt:
            print("\n\n👋 用户中断，再见!")
            break
        except Exception as e:
            logger.error(f"交互式搜索出错: {e}")
            print(f"❌ 搜索出错: {e}")

def main():
    """主函数"""
    print("🎬 JavSP爬虫系统测试")
    print("=" * 50)
    
    # 显示配置信息
    show_config_info()
    
    # 检查爬虫状态
    show_crawler_status()
    
    # 如果有命令行参数，执行对应的测试
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == 'single':
            test_single_search()
        elif command == 'fc2':
            test_fc2_search()
        elif command == 'batch':
            test_batch_search()
        elif command == 'performance':
            test_parallel_vs_sequential()
        elif command == 'interactive':
            interactive_search()
        elif command == 'status':
            pass  # 已经显示了状态
        else:
            print(f"\n❌ 未知命令: {command}")
            print("可用命令: single, fc2, batch, performance, interactive, status")
    else:
        # 默认执行所有测试
        test_single_search()
        test_fc2_search()
        test_batch_search()
        
        # 询问是否进入交互模式
        try:
            response = input("\n是否进入交互式搜索模式? (y/N): ").strip().lower()
            if response in ['y', 'yes']:
                interactive_search()
        except KeyboardInterrupt:
            print("\n\n👋 再见!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 用户中断，再见!")
    except Exception as e:
        logger.error(f"程序执行出错: {e}", exc_info=True)
        print(f"❌ 程序执行出错: {e}")
        sys.exit(1)