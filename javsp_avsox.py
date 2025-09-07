"""Avsox爬虫模块 - 基于JavSP改编"""
import logging
import re
from typing import Optional
from urllib.parse import urljoin

from javsp_base import get_html, CrawlerError, MovieNotFoundError, sleep_after_request, is_url_accessible
from javsp_datatype import MovieInfo
from javsp_config import config

logger = logging.getLogger(__name__)

class AvsoxCrawler:
    """Avsox爬虫类"""
    
    def __init__(self):
        self.name = 'avsox'
        self.permanent_url = 'https://avsox.click'
        self.base_url = ''
        self._init_network_config()
        
        logger.info(f"Avsox crawler initialized with base_url: {self.base_url}")
    
    def _init_network_config(self):
        """初始化网络配置，选择最佳的访问URL"""
        # 候选URL列表
        urls = [
            config.network.proxy_free.get('avsox', self.permanent_url),
            self.permanent_url,
            'https://avsox.com',
            'https://avsox.website',
            'https://avsox.host'
        ]
        
        # 测试URL可用性
        for url in urls:
            if url and self._test_url_accessibility(url):
                self.base_url = url
                logger.info(f"Using Avsox URL: {url}")
                return
        
        # 如果都不可用，使用永久URL
        self.base_url = self.permanent_url
        logger.warning(f"All URLs failed, using permanent URL: {self.permanent_url}")
    
    def _test_url_accessibility(self, url: str) -> bool:
        """测试URL可访问性"""
        try:
            return is_url_accessible(url, timeout=5)
        except Exception as e:
            logger.debug(f"Failed to access {url}: {e}")
            return False
    
    def parse_data(self, movie: MovieInfo) -> None:
        """从Avsox抓取并解析指定番号的数据
        
        Args:
            movie (MovieInfo): 要解析的影片信息，解析后的信息直接更新到此变量内
        """
        if not movie.dvdid:
            raise ValueError("dvdid is required for Avsox crawler")
        
        # 如果base_url未初始化，重新初始化
        if not self.base_url:
            self._init_network_config()
        
        try:
            # 处理FC2番号格式
            full_id = movie.dvdid
            if full_id.startswith('FC2-') and not full_id.startswith('FC2-PPV-'):
                full_id = full_id.replace('FC2-', 'FC2-PPV-')
            
            # 搜索影片
            search_url = f'{self.base_url}/tw/search/{full_id}'
            logger.info(f"Searching for {full_id} at: {search_url}")
            
            html = get_html(search_url, encoding='utf-8')
            
            # 从搜索结果中找到目标影片URL
            movie_url = self._find_movie_url(html, full_id, movie.dvdid)
            
            # 获取影片详情页面
            logger.info(f"Fetching movie details from: {movie_url}")
            html = get_html(movie_url, encoding='utf-8')
            
            # 解析影片信息
            self._parse_movie_info(html, movie, movie_url, full_id)
            
            logger.info(f"Successfully parsed data for {movie.dvdid}")
            
        except Exception as e:
            logger.error(f"Failed to parse data for {movie.dvdid}: {e}")
            raise CrawlerError(f"Avsox parsing failed: {e}")
        
        finally:
            sleep_after_request()
    
    def _find_movie_url(self, html, full_id: str, original_dvdid: str) -> str:
        """从搜索结果中找到目标影片URL"""
        ids = html.xpath("//div[@class='photo-info']/span/date[1]/text()")
        urls = html.xpath("//a[contains(@class, 'movie-box')]/@href")
        
        if not ids or not urls:
            raise MovieNotFoundError(self.name, original_dvdid)
        
        # 查找匹配的ID
        ids_lower = [id_str.lower() for id_str in ids]
        target_id = full_id.lower()
        
        if target_id in ids_lower:
            index = ids_lower.index(target_id)
            url = urls[index]
            # 转换为中文页面
            url = url.replace('/tw/', '/cn/', 1)
            # 确保URL是完整的
            if url.startswith('/'):
                url = urljoin(self.base_url, url)
            return url
        else:
            raise MovieNotFoundError(self.name, original_dvdid, ids)
    
    def _parse_movie_info(self, html, movie: MovieInfo, movie_url: str, full_id: str) -> None:
        """解析影片信息"""
        try:
            container = html.xpath("/html/body/div[@class='container']")
            if not container:
                raise CrawlerError("Cannot find main container")
            
            container = container[0]
            
            # 解析标题
            title_elements = container.xpath("h3/text()")
            if title_elements:
                title = title_elements[0]
                movie.title = self._clean_title(title, movie.dvdid)
            
            # 解析封面
            cover_elements = container.xpath("//a[@class='bigImage']/@href")
            if cover_elements:
                movie.cover = cover_elements[0]
            
            # 解析详细信息
            info_container = container.xpath("div/div[@class='col-md-3 info']")
            if info_container:
                self._parse_info_section(info_container[0], movie, full_id)
            
            # 解析演员
            actress_elements = container.xpath("//a[@class='avatar-box']/span/text()")
            if actress_elements:
                movie.actress = [a.strip() for a in actress_elements if a.strip()]
            
            # 设置URL
            movie.url = movie_url.replace(self.base_url, self.permanent_url)
            
        except Exception as e:
            logger.error(f"Error parsing movie info: {e}")
            raise
    
    def _parse_info_section(self, info_element, movie: MovieInfo, full_id: str) -> None:
        """解析信息区域"""
        try:
            # 解析识别码
            dvdid_elements = info_element.xpath("p/span[@style]/text()")
            if dvdid_elements:
                dvdid = dvdid_elements[0]
                # 处理FC2格式
                if dvdid.startswith('FC2-PPV-'):
                    dvdid = dvdid.replace('FC2-PPV-', 'FC2-')
                movie.dvdid = dvdid
            
            # 解析发行日期
            date_elements = info_element.xpath("p/span[text()='发行时间:']")
            if date_elements and date_elements[0].tail:
                movie.publish_date = date_elements[0].tail.strip()
            
            # 解析时长
            duration_elements = info_element.xpath("p/span[text()='长度:']")
            if duration_elements and duration_elements[0].tail:
                duration = duration_elements[0].tail.replace('分钟', '').strip()
                # 只保留数字
                duration = re.sub(r'[^0-9]', '', duration)
                if duration.isdigit() and int(duration) > 0:
                    movie.duration = duration
            
            # 解析制作商
            producer_elements = info_element.xpath("p[text()='制作商: ']")
            producer = None
            if producer_elements:
                next_element = producer_elements[0].getnext()
                if next_element is not None:
                    producer_links = next_element.xpath("a")
                    if producer_links:
                        producer = producer_links[0].text_content().strip()
            
            # 解析系列
            serial_elements = info_element.xpath("p[text()='系列:']")
            serial = None
            if serial_elements:
                next_element = serial_elements[0].getnext()
                if next_element is not None:
                    serial_links = next_element.xpath("a/text()")
                    if serial_links:
                        serial = serial_links[0].strip()
            
            # 处理FC2作品的特殊情况
            if full_id.startswith('FC2-'):
                # avsox把FC2作品的拍摄者归类到'系列'而制作商固定为'FC2-PPV'
                # 这既不合理也与其他站点不兼容，因此进行调整
                movie.producer = serial
                movie.serial = None
            else:
                movie.producer = producer
                movie.serial = serial
            
            # 解析类型
            genre_elements = info_element.xpath("p/span[@class='genre']/a/text()")
            if genre_elements:
                movie.genre = [g.strip() for g in genre_elements if g.strip()]
            
        except Exception as e:
            logger.error(f"Error parsing info section: {e}")
    
    def _clean_title(self, title: str, dvdid: str = None) -> str:
        """清理标题"""
        if not title:
            return ''
        
        # 移除番号
        if dvdid:
            title = title.replace(dvdid, '').strip()
        
        # 移除常见的无用信息
        useless_patterns = [
            r'官方App下[載载]',
            r'Official App Download',
            r'アプリダウンロード',
            r'公式アプリ',
        ]
        
        cleaned_title = title
        for pattern in useless_patterns:
            cleaned_title = re.sub(pattern, '', cleaned_title, flags=re.IGNORECASE)
        
        # 清理多余的空格和标点
        cleaned_title = re.sub(r'\s+', ' ', cleaned_title).strip()
        cleaned_title = cleaned_title.strip('- ')
        
        return cleaned_title
    
    def search_movie(self, dvdid: str) -> Optional[MovieInfo]:
        """搜索影片信息"""
        try:
            movie = MovieInfo(dvdid=dvdid)
            self.parse_data(movie)
            return movie
        except Exception as e:
            logger.error(f"Failed to search movie {dvdid}: {e}")
            return None
    
    def is_available(self) -> bool:
        """检查爬虫是否可用"""
        try:
            return self._test_url_accessibility(self.base_url)
        except Exception as e:
            logger.error(f"Avsox crawler is not available: {e}")
            return False

# 创建全局实例
avsox_crawler = AvsoxCrawler()

def parse_data(movie: MovieInfo) -> None:
    """解析指定番号的影片数据（兼容接口）"""
    avsox_crawler.parse_data(movie)

def search_movie(dvdid: str) -> Optional[MovieInfo]:
    """搜索影片信息（便捷接口）"""
    return avsox_crawler.search_movie(dvdid)

if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)
    
    test_movie = MovieInfo(dvdid='082713-417')
    try:
        parse_data(test_movie)
        print(f"Title: {test_movie.title}")
        print(f"Actress: {test_movie.actress}")
        print(f"Duration: {test_movie.duration}")
        print(f"Genre: {test_movie.genre}")
        print(f"Producer: {test_movie.producer}")
    except Exception as e:
        logger.error(f"Test failed: {e}")