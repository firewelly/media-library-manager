"""JavSP爬虫管理器 - 统一管理所有爬虫模块"""
import logging
from typing import List, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from javsp_datatype import MovieInfo
from javsp_config import config
from javsp_base import CrawlerError, MovieNotFoundError, NetworkError

# 导入所有爬虫模块
try:
    from javsp_javbus import javbus_crawler
except ImportError as e:
    logging.warning(f"Failed to import JavBus crawler: {e}")
    javbus_crawler = None

try:
    from javsp_javlib import javlib_crawler
except ImportError as e:
    logging.warning(f"Failed to import JavLib crawler: {e}")
    javlib_crawler = None

try:
    from javsp_avsox import avsox_crawler
except ImportError as e:
    logging.warning(f"Failed to import Avsox crawler: {e}")
    avsox_crawler = None

try:
    from javsp_fc2 import fc2_crawler
except ImportError as e:
    logging.warning(f"Failed to import FC2 crawler: {e}")
    fc2_crawler = None

logger = logging.getLogger(__name__)

class CrawlerManager:
    """爬虫管理器类"""
    
    def __init__(self):
        self.crawlers = self._init_crawlers()
        self.fc2_crawlers = self._init_fc2_crawlers()
        
        logger.info(f"Crawler manager initialized with {len(self.crawlers)} normal crawlers and {len(self.fc2_crawlers)} FC2 crawlers")
    
    def _init_crawlers(self) -> Dict[str, Any]:
        """初始化普通番号爬虫"""
        crawlers = {}
        
        # 根据配置选择爬虫
        normal_crawlers = config.crawler.selection.get('normal', [])
        
        if 'javbus' in normal_crawlers and javbus_crawler:
            crawlers['javbus'] = javbus_crawler
            logger.info("JavBus crawler enabled")
        
        if 'javlib' in normal_crawlers and javlib_crawler:
            crawlers['javlib'] = javlib_crawler
            logger.info("JavLib crawler enabled")
        
        if 'avsox' in normal_crawlers and avsox_crawler:
            crawlers['avsox'] = avsox_crawler
            logger.info("Avsox crawler enabled")
        
        return crawlers
    
    def _init_fc2_crawlers(self) -> Dict[str, Any]:
        """初始化FC2爬虫"""
        fc2_crawlers = {}
        
        # FC2爬虫配置
        fc2_selection = config.crawler.fc2_selection
        
        if 'fc2' in fc2_selection and fc2_crawler:
            fc2_crawlers['fc2'] = fc2_crawler
            logger.info("FC2 crawler enabled")
        
        return fc2_crawlers
    
    def is_fc2_id(self, dvdid: str) -> bool:
        """判断是否为FC2番号"""
        return dvdid.upper().startswith('FC2-')
    
    def get_available_crawlers(self, dvdid: str) -> Dict[str, Any]:
        """获取可用的爬虫列表"""
        if self.is_fc2_id(dvdid):
            return self.fc2_crawlers
        else:
            return self.crawlers
    
    def search_movie_single(self, dvdid: str, crawler_name: str = None) -> Optional[MovieInfo]:
        """使用单个爬虫搜索影片信息
        
        Args:
            dvdid: 影片番号
            crawler_name: 指定爬虫名称，如果为None则自动选择
        
        Returns:
            MovieInfo对象或None
        """
        available_crawlers = self.get_available_crawlers(dvdid)
        
        if not available_crawlers:
            logger.warning(f"No available crawlers for {dvdid}")
            return None
        
        # 如果指定了爬虫名称
        if crawler_name:
            if crawler_name in available_crawlers:
                crawler = available_crawlers[crawler_name]
                try:
                    logger.info(f"Searching {dvdid} using {crawler_name}")
                    return crawler.search_movie(dvdid)
                except Exception as e:
                    logger.error(f"Failed to search {dvdid} using {crawler_name}: {e}")
                    return None
            else:
                logger.warning(f"Crawler {crawler_name} not available for {dvdid}")
                return None
        
        # 自动选择爬虫（按优先级顺序尝试）
        for name, crawler in available_crawlers.items():
            try:
                logger.info(f"Trying to search {dvdid} using {name}")
                result = crawler.search_movie(dvdid)
                if result and result.is_valid():
                    logger.info(f"Successfully found {dvdid} using {name}")
                    return result
            except Exception as e:
                logger.warning(f"Failed to search {dvdid} using {name}: {e}")
                continue
        
        logger.warning(f"All crawlers failed to find {dvdid}")
        return None
    
    def search_movie_parallel(self, dvdid: str, max_workers: int = 3, timeout: int = 30) -> Optional[MovieInfo]:
        """并行使用多个爬虫搜索影片信息
        
        Args:
            dvdid: 影片番号
            max_workers: 最大并发数
            timeout: 超时时间（秒）
        
        Returns:
            MovieInfo对象或None
        """
        available_crawlers = self.get_available_crawlers(dvdid)
        
        if not available_crawlers:
            logger.warning(f"No available crawlers for {dvdid}")
            return None
        
        logger.info(f"Parallel searching {dvdid} using {list(available_crawlers.keys())}")
        
        def search_with_crawler(crawler_info):
            name, crawler = crawler_info
            try:
                start_time = time.time()
                result = crawler.search_movie(dvdid)
                elapsed = time.time() - start_time
                
                if result and result.is_valid():
                    logger.info(f"Successfully found {dvdid} using {name} in {elapsed:.2f}s")
                    return result, name, elapsed
                else:
                    logger.warning(f"No valid result from {name} for {dvdid}")
                    return None, name, elapsed
            except Exception as e:
                elapsed = time.time() - start_time
                logger.warning(f"Failed to search {dvdid} using {name} in {elapsed:.2f}s: {e}")
                return None, name, elapsed
        
        # 并行执行搜索
        with ThreadPoolExecutor(max_workers=min(max_workers, len(available_crawlers))) as executor:
            future_to_crawler = {
                executor.submit(search_with_crawler, item): item[0] 
                for item in available_crawlers.items()
            }
            
            try:
                for future in as_completed(future_to_crawler, timeout=timeout):
                    result, crawler_name, elapsed = future.result()
                    if result:
                        # 取消其他未完成的任务
                        for f in future_to_crawler:
                            if f != future and not f.done():
                                f.cancel()
                        return result
            except Exception as e:
                logger.error(f"Parallel search failed for {dvdid}: {e}")
        
        logger.warning(f"All parallel searches failed for {dvdid}")
        return None
    
    def search_movie(self, dvdid: str, use_parallel: bool = False, **kwargs) -> Optional[MovieInfo]:
        """搜索影片信息（主要接口）
        
        Args:
            dvdid: 影片番号
            use_parallel: 是否使用并行搜索
            **kwargs: 其他参数
        
        Returns:
            MovieInfo对象或None
        """
        if not dvdid:
            logger.warning("Empty dvdid provided")
            return None
        
        dvdid = dvdid.strip().upper()
        logger.info(f"Searching movie: {dvdid}")
        
        try:
            if use_parallel:
                return self.search_movie_parallel(dvdid, **kwargs)
            else:
                return self.search_movie_single(dvdid, **kwargs)
        except Exception as e:
            logger.error(f"Failed to search movie {dvdid}: {e}")
            return None
    
    def batch_search(self, dvdids: List[str], use_parallel: bool = True, max_workers: int = 5) -> Dict[str, Optional[MovieInfo]]:
        """批量搜索影片信息
        
        Args:
            dvdids: 影片番号列表
            use_parallel: 是否使用并行搜索
            max_workers: 最大并发数
        
        Returns:
            字典，键为番号，值为MovieInfo对象或None
        """
        results = {}
        
        if not dvdids:
            return results
        
        logger.info(f"Batch searching {len(dvdids)} movies")
        
        def search_single_movie(dvdid):
            try:
                result = self.search_movie(dvdid, use_parallel=use_parallel)
                return dvdid, result
            except Exception as e:
                logger.error(f"Failed to search {dvdid}: {e}")
                return dvdid, None
        
        # 批量并行搜索
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_dvdid = {
                executor.submit(search_single_movie, dvdid): dvdid 
                for dvdid in dvdids
            }
            
            for future in as_completed(future_to_dvdid):
                dvdid, result = future.result()
                results[dvdid] = result
                
                if result:
                    logger.info(f"Batch search: Found {dvdid}")
                else:
                    logger.warning(f"Batch search: Failed to find {dvdid}")
        
        success_count = sum(1 for r in results.values() if r is not None)
        logger.info(f"Batch search completed: {success_count}/{len(dvdids)} successful")
        
        return results
    
    def get_crawler_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有爬虫的状态信息"""
        status = {
            'normal_crawlers': {},
            'fc2_crawlers': {}
        }
        
        # 检查普通爬虫状态
        for name, crawler in self.crawlers.items():
            try:
                is_available = crawler.is_available()
                status['normal_crawlers'][name] = {
                    'available': is_available,
                    'base_url': getattr(crawler, 'base_url', 'Unknown')
                }
            except Exception as e:
                status['normal_crawlers'][name] = {
                    'available': False,
                    'error': str(e)
                }
        
        # 检查FC2爬虫状态
        for name, crawler in self.fc2_crawlers.items():
            try:
                is_available = crawler.is_available()
                status['fc2_crawlers'][name] = {
                    'available': is_available,
                    'base_url': getattr(crawler, 'base_url', 'Unknown')
                }
            except Exception as e:
                status['fc2_crawlers'][name] = {
                    'available': False,
                    'error': str(e)
                }
        
        return status

# 创建全局实例
crawler_manager = CrawlerManager()

# 便捷函数
def search_movie(dvdid: str, **kwargs) -> Optional[MovieInfo]:
    """搜索影片信息（便捷接口）"""
    return crawler_manager.search_movie(dvdid, **kwargs)

def search_movie_info(dvdid: str, **kwargs) -> Optional[MovieInfo]:
    """搜索影片信息（便捷接口，与search_movie相同）"""
    return crawler_manager.search_movie(dvdid, **kwargs)

def batch_search(dvdids: List[str], **kwargs) -> Dict[str, Optional[MovieInfo]]:
    """批量搜索影片信息（便捷接口）"""
    return crawler_manager.batch_search(dvdids, **kwargs)

def get_crawler_status() -> Dict[str, Dict[str, Any]]:
    """获取爬虫状态（便捷接口）"""
    return crawler_manager.get_crawler_status()

if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)
    
    # 测试普通番号
    test_dvdids = ['IPX-177', 'SSIS-001']
    
    for dvdid in test_dvdids:
        print(f"\n=== Testing {dvdid} ===")
        result = search_movie(dvdid)
        if result:
            print(f"Title: {result.title}")
            print(f"Actress: {result.actress}")
            print(f"Duration: {result.duration}")
        else:
            print("Not found")
    
    # 测试FC2番号
    fc2_dvdid = 'FC2-718323'
    print(f"\n=== Testing {fc2_dvdid} ===")
    result = search_movie(fc2_dvdid)
    if result:
        print(f"Title: {result.title}")
        print(f"Producer: {result.producer}")
        print(f"Duration: {result.duration}")
    else:
        print("Not found")
    
    # 显示爬虫状态
    print("\n=== Crawler Status ===")
    status = get_crawler_status()
    for category, crawlers in status.items():
        print(f"\n{category}:")
        for name, info in crawlers.items():
            print(f"  {name}: {'Available' if info.get('available') else 'Unavailable'}")
            if 'error' in info:
                print(f"    Error: {info['error']}")