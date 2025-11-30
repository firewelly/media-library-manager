"""JavLibrary爬虫模块 - 基于JavSP改编"""
import logging
import re
from typing import Optional
from urllib.parse import urlsplit, urljoin

from javsp_base import get_html, CrawlerError, MovieNotFoundError, sleep_after_request, is_url_accessible
from javsp_config import get_proxy_settings
from javsp_datatype import MovieInfo
from javsp_config import config

logger = logging.getLogger(__name__)

class MovieDuplicateError(CrawlerError):
    """影片重复异常"""
    def __init__(self, crawler_name: str, movie_id: str, count: int, urls: list):
        self.crawler_name = crawler_name
        self.movie_id = movie_id
        self.count = count
        self.urls = urls
        
        message = f"Found {count} duplicate movies for '{movie_id}' in {crawler_name}: {urls}"
        super().__init__(message)

class JavLibCrawler:
    """JavLibrary爬虫类"""
    
    def __init__(self):
        self.name = 'javlib'
        self.permanent_url = 'https://www.javlibrary.com'
        self.base_url = ''
        logger.info("JavLib crawler initialized (lazy network config)")
    
    def _init_network_config(self):
        if getattr(config.crawler, 'probe_on_first_use', False):
            urls = [
                config.network.proxy_free.get('javlib', self.permanent_url),
                self.permanent_url
            ]
            for url in urls:
                try:
                    if is_url_accessible(url, timeout=5):
                        self.base_url = url
                        logger.info(f"Using JavLib URL: {url}")
                        return
                except Exception as e:
                    logger.debug(f"Failed to access {url}: {e}")
            self.base_url = self.permanent_url
            logger.warning(f"All URLs failed, using permanent URL: {self.permanent_url}")
        else:
            self.base_url = self.permanent_url
            logger.info(f"Using JavLib URL with proxy: {self.base_url}")
    
    def _test_url_accessibility(self, url: str) -> bool:
        """测试URL可访问性"""
        try:
            return is_url_accessible(url, timeout=5)
        except Exception as e:
            logger.debug(f"Failed to access {url}: {e}")
            return False
    
    def parse_data(self, movie: MovieInfo) -> None:
        """从JavLibrary抓取并解析指定番号的数据
        
        Args:
            movie (MovieInfo): 要解析的影片信息，解析后的信息直接更新到此变量内
        """
        if not movie.dvdid:
            raise ValueError("dvdid is required for JavLib crawler")
        
        # 如果base_url未初始化，重新初始化
        if not self.base_url:
            self._init_network_config()
        
        search_url = f'{self.base_url}/cn/vl_searchbyid.php?keyword={movie.dvdid}'
        logger.info(f"Searching for {movie.dvdid} at: {search_url}")
        
        try:
            # 获取搜索页面
            html = get_html(search_url, encoding='utf-8', use_cloudscraper=True)
            
            # 处理搜索结果
            movie_url = self._process_search_results(html, movie, search_url)
            
            # 获取影片详情页面
            if movie_url != search_url:
                html = get_html(movie_url, encoding='utf-8', use_cloudscraper=True)
            
            # 解析影片信息
            self._parse_movie_info(html, movie, movie_url)
            
            logger.info(f"Successfully parsed data for {movie.dvdid}")
            
        except Exception as e:
            logger.error(f"Failed to parse data for {movie.dvdid}: {e}")
            raise CrawlerError(f"JavLib parsing failed: {e}")
        
        finally:
            sleep_after_request()
    
    def _process_search_results(self, html, movie: MovieInfo, search_url: str) -> str:
        """处理搜索结果，返回影片详情页URL"""
        # 检查是否直接跳转到了影片页面（只有一个搜索结果时会自动跳转）
        page_title = html.xpath('//title/text()')
        if page_title and not any(keyword in page_title[0].lower() for keyword in ['search', '搜索']):
            # 直接跳转到了影片页面
            return search_url
        
        # 处理多个搜索结果
        video_tags = html.xpath("//div[@class='video'][@id]/a")
        if not video_tags:
            raise MovieNotFoundError(self.name, movie.dvdid)
        
        # 查找匹配的影片
        matching_videos = []
        for tag in video_tags:
            tag_dvdid_elements = tag.xpath("div[@class='id']/text()")
            if tag_dvdid_elements:
                tag_dvdid = tag_dvdid_elements[0]
                if tag_dvdid.upper() == movie.dvdid.upper():
                    matching_videos.append(tag)
        
        if not matching_videos:
            raise MovieNotFoundError(self.name, movie.dvdid)
        
        # 选择最佳匹配
        selected_video = self._select_best_match(matching_videos, movie.dvdid)
        movie_url = selected_video.get('href')
        
        # 确保URL是完整的
        if movie_url.startswith('/'):
            movie_url = urljoin(self.base_url, movie_url)
        
        return movie_url
    
    def _select_best_match(self, matching_videos: list, dvdid: str):
        """从多个匹配结果中选择最佳的"""
        if len(matching_videos) == 1:
            return matching_videos[0]
        
        # 如果有多个结果，优先选择非蓝光版本
        non_bluray_videos = []
        for video in matching_videos:
            title = video.get('title', '')
            if 'ブルーレイディスク' not in title and 'Blu-ray' not in title:
                non_bluray_videos.append(video)
        
        if len(non_bluray_videos) == 1:
            logger.debug(f"'{dvdid}': Found {len(matching_videos)} matches, selected non-Blu-ray version")
            return non_bluray_videos[0]
        
        # 如果仍有多个结果，抛出异常
        urls = [v.get('href', '') for v in matching_videos]
        raise MovieDuplicateError(self.name, dvdid, len(matching_videos), urls)
    
    def _parse_movie_info(self, html, movie: MovieInfo, movie_url: str) -> None:
        """解析影片信息"""
        try:
            container = html.xpath("/html/body/div/div[@id='rightcolumn']")
            if not container:
                raise ParseError("Cannot find main container")
            
            container = container[0]
            
            # 解析标题
            title_elements = container.xpath("div/h3/a/text()")
            if title_elements:
                title = title_elements[0]
                # 移除番号，清理标题
                if movie.dvdid:
                    title = title.replace(movie.dvdid, '').strip()
                movie.title = self._clean_title(title)
            
            # 解析封面
            cover_elements = container.xpath("//img[@id='video_jacket_img']/@src")
            if cover_elements:
                cover = cover_elements[0]
                # 补全URL协议
                if cover.startswith('//'):
                    cover = 'https:' + cover
                movie.cover = cover
            
            # 解析详细信息
            info_container = container.xpath("//div[@id='video_info']")
            if info_container:
                self._parse_info_section(info_container[0], movie)
            
            # 设置URL
            movie.url = movie_url.replace(self.base_url, self.permanent_url)
            
        except Exception as e:
            logger.error(f"Error parsing movie info: {e}")
            raise
    
    def _parse_info_section(self, info_element, movie: MovieInfo) -> None:
        """解析信息区域"""
        try:
            # 解析识别码
            dvdid_elements = info_element.xpath("div[@id='video_id']//td[@class='text']/text()")
            if dvdid_elements:
                movie.dvdid = dvdid_elements[0].strip()
            
            # 解析发行日期
            date_elements = info_element.xpath("div[@id='video_date']//td[@class='text']/text()")
            if date_elements:
                movie.publish_date = date_elements[0].strip()
            
            # 解析时长
            duration_elements = info_element.xpath("div[@id='video_length']//span[@class='text']/text()")
            if duration_elements:
                duration = duration_elements[0].strip()
                # 移除单位，只保留数字
                duration = re.sub(r'[^0-9]', '', duration)
                if duration.isdigit() and int(duration) > 0:
                    movie.duration = duration
            
            # 解析导演
            director_elements = info_element.xpath("//span[@class='director']/a/text()")
            if director_elements:
                movie.director = director_elements[0].strip()
            
            # 解析制作商
            producer_elements = info_element.xpath("//span[@class='maker']/a/text()")
            if producer_elements:
                movie.producer = producer_elements[0].strip()
            
            # 解析发行商
            publisher_elements = info_element.xpath("//span[@class='label']/a/text()")
            if publisher_elements:
                movie.publisher = publisher_elements[0].strip()
            
            # 解析评分
            score_elements = info_element.xpath("//span[@class='score']/text()")
            if score_elements:
                score = score_elements[0].strip('()')
                if score and score != '-':
                    movie.score = score
            
            # 解析类型
            genre_elements = info_element.xpath("//span[@class='genre']/a/text()")
            if genre_elements:
                movie.genre = [g.strip() for g in genre_elements]
            
            # 解析演员
            actress_elements = info_element.xpath("//span[@class='star']/a/text()")
            if actress_elements:
                movie.actress = [a.strip() for a in actress_elements]
            
        except Exception as e:
            logger.error(f"Error parsing info section: {e}")
    
    def _clean_title(self, title: str) -> str:
        """清理标题"""
        if not title:
            return ''
        
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
        """检查爬虫是否可用（不触发网络访问，要求已配置代理）"""
        try:
            return bool(get_proxy_settings())
        except Exception:
            return False

class ParseError(CrawlerError):
    """解析错误异常"""
    pass

# 创建全局实例
javlib_crawler = JavLibCrawler()

def parse_data(movie: MovieInfo) -> None:
    """解析指定番号的影片数据（兼容接口）"""
    javlib_crawler.parse_data(movie)

def search_movie(dvdid: str) -> Optional[MovieInfo]:
    """搜索影片信息（便捷接口）"""
    return javlib_crawler.search_movie(dvdid)

if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)
    
    test_movie = MovieInfo(dvdid='IPX-177')
    try:
        parse_data(test_movie)
        print(f"Title: {test_movie.title}")
        print(f"Actress: {test_movie.actress}")
        print(f"Duration: {test_movie.duration}")
        print(f"Genre: {test_movie.genre}")
        print(f"Score: {test_movie.score}")
    except Exception as e:
        logger.error(f"Test failed: {e}")
