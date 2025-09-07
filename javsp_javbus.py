"""JavBus爬虫模块 - 基于JavSP改编"""
import logging
import re
from typing import Optional
from urllib.parse import urljoin

from javsp_base import get_html, CrawlerError, MovieNotFoundError, sleep_after_request
from javsp_datatype import MovieInfo
from javsp_config import config

logger = logging.getLogger(__name__)

class JavBusCrawler:
    """JavBus爬虫类"""
    
    def __init__(self):
        self.name = 'javbus'
        self.permanent_url = 'https://www.javbus.com'
        # 根据是否使用代理选择base_url
        if config.network.proxy_server:
            self.base_url = self.permanent_url
        else:
            self.base_url = config.network.proxy_free.get('javbus', self.permanent_url)
        
        logger.info(f"JavBus crawler initialized with base_url: {self.base_url}")
    
    def parse_data(self, movie: MovieInfo) -> None:
        """从JavBus抓取并解析指定番号的数据
        
        Args:
            movie (MovieInfo): 要解析的影片信息，解析后的信息直接更新到此变量内
        """
        if not movie.dvdid:
            raise ValueError("dvdid is required for JavBus crawler")
        
        url = f'{self.base_url}/{movie.dvdid}'
        logger.info(f"Fetching data from: {url}")
        
        try:
            # 获取HTML页面
            html = get_html(url, encoding='utf-8')
            
            # 检查是否为404页面
            page_title = html.xpath('/html/head/title/text()')
            if page_title and page_title[0].startswith('404 Page Not Found!'):
                raise MovieNotFoundError(self.name, movie.dvdid)
            
            # 解析页面内容
            self._parse_movie_info(html, movie)
            
            # 设置URL
            movie.url = f'{self.permanent_url}/{movie.dvdid}'
            
            logger.info(f"Successfully parsed data for {movie.dvdid}")
            
        except Exception as e:
            logger.error(f"Failed to parse data for {movie.dvdid}: {e}")
            raise CrawlerError(f"JavBus parsing failed: {e}")
        
        finally:
            sleep_after_request()
    
    def _parse_movie_info(self, html, movie: MovieInfo) -> None:
        """解析影片信息"""
        try:
            container = html.xpath("//div[@class='container']")[0]
            
            # 解析标题
            title_elements = container.xpath("h3/text()")
            if title_elements:
                title = title_elements[0]
                # 移除番号，清理标题
                if movie.dvdid:
                    title = title.replace(movie.dvdid, '').strip()
                movie.title = self._clean_title(title)
            
            # 解析封面
            cover_elements = container.xpath("//a[@class='bigImage']/img/@src")
            if cover_elements:
                movie.cover = cover_elements[0]
            
            # 解析预览图片
            preview_pics = container.xpath("//div[@id='sample-waterfall']/a/@href")
            if preview_pics:
                movie.preview_pics = preview_pics
            
            # 解析详细信息
            info_container = container.xpath("//div[@class='col-md-3 info']")
            if info_container:
                self._parse_info_section(info_container[0], movie)
            
            # 解析演员信息
            self._parse_actress_info(html, movie)
            
        except Exception as e:
            logger.error(f"Error parsing movie info: {e}")
            raise
    
    def _parse_info_section(self, info_element, movie: MovieInfo) -> None:
        """解析信息区域"""
        try:
            # 解析识别码
            dvdid_elements = info_element.xpath("p/span[text()='識別碼:']")
            if dvdid_elements:
                dvdid = dvdid_elements[0].getnext().text
                if dvdid:
                    movie.dvdid = dvdid.strip()
            
            # 解析发行日期
            date_elements = info_element.xpath("p/span[text()='發行日期:']")
            if date_elements:
                date_text = date_elements[0].tail
                if date_text and date_text.strip() != '0000-00-00':
                    movie.publish_date = date_text.strip()
            
            # 解析时长
            duration_elements = info_element.xpath("p/span[text()='長度:']")
            if duration_elements:
                duration_text = duration_elements[0].tail
                if duration_text:
                    duration = duration_text.replace('分鐘', '').strip()
                    if duration.isdigit() and int(duration) > 0:
                        movie.duration = duration
            
            # 解析导演
            director_elements = info_element.xpath("p/span[text()='導演:']")
            if director_elements:
                director_element = director_elements[0].getnext()
                if director_element is not None and director_element.text:
                    movie.director = director_element.text.strip()
            
            # 解析制作商
            producer_elements = info_element.xpath("p/span[text()='製作商:']")
            if producer_elements:
                producer_element = producer_elements[0].getnext()
                if producer_element is not None and producer_element.text:
                    movie.producer = producer_element.text.strip()
            
            # 解析发行商
            publisher_elements = info_element.xpath("p/span[text()='發行商:']")
            if publisher_elements:
                publisher_element = publisher_elements[0].getnext()
                if publisher_element is not None and publisher_element.text:
                    movie.publisher = publisher_element.text.strip()
            
            # 解析系列
            serial_elements = info_element.xpath("p/span[text()='系列:']")
            if serial_elements:
                serial_element = serial_elements[0].getnext()
                if serial_element is not None and serial_element.text:
                    movie.serial = serial_element.text.strip()
            
            # 解析类型标签
            self._parse_genre_info(info_element, movie)
            
        except Exception as e:
            logger.error(f"Error parsing info section: {e}")
    
    def _parse_genre_info(self, info_element, movie: MovieInfo) -> None:
        """解析类型信息"""
        try:
            genre_tags = info_element.xpath("//span[@class='genre']/label/a")
            genre_list = []
            genre_id_list = []
            
            for tag in genre_tags:
                genre_text = tag.text
                if genre_text:
                    genre_list.append(genre_text.strip())
                
                # 解析genre_id
                tag_url = tag.get('href', '')
                if tag_url:
                    pre_id = tag_url.split('/')[-1]
                    if 'uncensored' in tag_url:
                        movie.uncensored = True
                        genre_id_list.append('uncensored-' + pre_id)
                    else:
                        movie.uncensored = False
                        genre_id_list.append(pre_id)
            
            if genre_list:
                movie.genre = genre_list
            if genre_id_list:
                movie.genre_id = genre_id_list
                
        except Exception as e:
            logger.error(f"Error parsing genre info: {e}")
    
    def _parse_actress_info(self, html, movie: MovieInfo) -> None:
        """解析演员信息"""
        try:
            actress_tags = html.xpath("//a[@class='avatar-box']/div/img")
            actress_list = []
            actress_pics_dict = {}
            
            for tag in actress_tags:
                name = tag.get('title')
                pic_url = tag.get('src')
                
                if name:
                    actress_list.append(name.strip())
                    
                    # 保存头像URL（跳过默认头像）
                    if pic_url and not pic_url.endswith('nowprinting.gif'):
                        actress_pics_dict[name.strip()] = pic_url
            
            if actress_list:
                movie.actress = actress_list
            if actress_pics_dict:
                movie.actress_pics = list(actress_pics_dict.values())
                
        except Exception as e:
            logger.error(f"Error parsing actress info: {e}")
    
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
        """检查爬虫是否可用"""
        try:
            test_url = f"{self.base_url}"
            html = get_html(test_url, encoding='utf-8')
            return html is not None
        except Exception as e:
            logger.error(f"JavBus crawler is not available: {e}")
            return False

# 创建全局实例
javbus_crawler = JavBusCrawler()

def parse_data(movie: MovieInfo) -> None:
    """解析指定番号的影片数据（兼容接口）"""
    javbus_crawler.parse_data(movie)

def search_movie(dvdid: str) -> Optional[MovieInfo]:
    """搜索影片信息（便捷接口）"""
    return javbus_crawler.search_movie(dvdid)

# 创建全局爬虫实例
javbus_crawler = JavBusCrawler()

# 为了兼容JavSP原始接口，提供parse_data函数
def parse_data(movie: MovieInfo) -> None:
    """解析数据的便捷函数"""
    javbus_crawler.parse_data(movie)

if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)
    
    test_movie = MovieInfo(dvdid='NANP-030')
    try:
        parse_data(test_movie)
        print(f"Title: {test_movie.title}")
        print(f"Actress: {test_movie.actress}")
        print(f"Duration: {test_movie.duration}")
        print(f"Genre: {test_movie.genre}")
    except Exception as e:
        logger.error(f"Test failed: {e}")