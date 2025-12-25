"""FC2官网爬虫模块 - 基于JavSP改编"""
import logging
import re
from typing import Optional
from urllib.parse import urljoin

from javsp_base import get_html, get_response, CrawlerError, MovieNotFoundError, NetworkError, sleep_after_request, is_url_accessible
from javsp_datatype import MovieInfo
from javsp_config import config

logger = logging.getLogger(__name__)

class SiteBlocked(CrawlerError):
    """站点被阻止访问异常"""
    pass

class FC2Crawler:
    """FC2官网爬虫类"""
    
    def __init__(self):
        self.name = 'fc2'
        self.base_url = 'https://adult.contents.fc2.com'
        
        logger.info(f"FC2 crawler initialized with base_url: {self.base_url}")
    
    def _strftime_to_minutes(self, time_str: str) -> int:
        """将时间字符串转换为分钟数"""
        try:
            # 匹配各种时间格式
            patterns = [
                r'(\d+):(\d+):(\d+)',  # HH:MM:SS
                r'(\d+):(\d+)',        # MM:SS
                r'(\d+)分',            # X分
                r'(\d+)分钟',          # X分钟
            ]
            
            for pattern in patterns:
                match = re.search(pattern, time_str)
                if match:
                    groups = match.groups()
                    if len(groups) == 3:  # HH:MM:SS
                        hours, minutes, seconds = map(int, groups)
                        return hours * 60 + minutes + (1 if seconds > 0 else 0)
                    elif len(groups) == 2:  # MM:SS
                        minutes, seconds = map(int, groups)
                        return minutes + (1 if seconds > 0 else 0)
                    elif len(groups) == 1:  # X分 or X分钟
                        return int(groups[0])
            
            # 如果都不匹配，尝试提取数字
            numbers = re.findall(r'\d+', time_str)
            if numbers:
                return int(numbers[0])
            
            return 0
        except Exception as e:
            logger.warning(f"Failed to parse duration '{time_str}': {e}")
            return 0
    
    def get_movie_score(self, fc2_id: str) -> Optional[float]:
        """通过评论数据来计算FC2的影片评分（10分制）"""
        try:
            review_url = f'{self.base_url}/article/{fc2_id}/review'
            html = get_html(review_url, encoding='utf-8')
            
            review_tags = html.xpath("//ul[@class='items_comment_headerReviewInArea']/li")
            reviews = {}
            
            for tag in review_tags:
                score_elements = tag.xpath("div/span/text()")
                vote_elements = tag.xpath("span")
                
                if score_elements and vote_elements:
                    score = int(score_elements[0])
                    vote = int(vote_elements[0].text_content())
                    reviews[score] = vote
            
            total_votes = sum(reviews.values())
            if total_votes >= 2:  # 至少需要两个人评价
                summary = sum([k * v for k, v in reviews.items()])
                final_score = summary / total_votes * 2  # 乘以2转换为10分制
                return final_score
            
            return None
            
        except Exception as e:
            logger.warning(f"Failed to get movie score for {fc2_id}: {e}")
            return None
    
    def parse_data(self, movie: MovieInfo) -> None:
        """从FC2官网抓取并解析指定番号的数据
        
        Args:
            movie (MovieInfo): 要解析的影片信息，解析后的信息直接更新到此变量内
        """
        if not movie.dvdid:
            raise ValueError("dvdid is required for FC2 crawler")
        
        # 验证FC2番号格式
        id_uc = movie.dvdid.upper()
        if not id_uc.startswith('FC2-'):
            raise ValueError(f'Invalid FC2 number: {movie.dvdid}')
        
        fc2_id = id_uc.replace('FC2-', '')
        url = f'{self.base_url}/article/{fc2_id}/'
        
        logger.info(f"Fetching FC2 data for {movie.dvdid} from: {url}")
        
        try:
            # 获取影片页面
            resp = get_response(url)
            
            # 检查是否被重定向到登录页面
            if '/id.fc2.com/' in resp.url:
                raise SiteBlocked('FC2要求当前IP登录账号才可访问，请尝试更换为日本IP')
            
            html = resp.html
            
            # 查找主容器
            container = html.xpath("//div[@class='items_article_left']")
            if not container:
                raise MovieNotFoundError(self.name, movie.dvdid)
            
            container = container[0]
            
            # 解析影片信息
            self._parse_movie_info(container, movie, fc2_id, url)
            
            logger.info(f"Successfully parsed data for {movie.dvdid}")
            
        except Exception as e:
            logger.error(f"Failed to parse data for {movie.dvdid}: {e}")
            if isinstance(e, (SiteBlocked, MovieNotFoundError)):
                raise
            raise CrawlerError(f"FC2 parsing failed: {e}")
        
        finally:
            sleep_after_request()
    
    def _parse_movie_info(self, container, movie: MovieInfo, fc2_id: str, url: str) -> None:
        """解析影片信息"""
        try:
            # 解析标题 - FC2标题可能有反爬乱码，使用数组合并
            title_elements = container.xpath("//div[@class='items_article_headerInfo']/h3/text()")
            if title_elements:
                title = ''.join(title_elements)
                movie.title = self._clean_title(title)
            
            # 解析缩略图和时长信息
            thumb_container = container.xpath("//div[@class='items_article_MainitemThumb']")
            if thumb_container:
                thumb_container = thumb_container[0]
                
                # 解析缩略图
                thumb_elements = thumb_container.xpath("span/img/@src")
                if thumb_elements:
                    thumb_pic = thumb_elements[0]
                
                # 解析时长
                duration_elements = thumb_container.xpath("span/p[@class='items_article_info']/text()")
                if duration_elements:
                    duration_str = duration_elements[0]
                    duration_minutes = self._strftime_to_minutes(duration_str)
                    if duration_minutes > 0:
                        movie.duration = str(duration_minutes)
            
            # 解析制作商（FC2没有制作商和发行商的区分，'by'更接近于制作商）
            producer_elements = container.xpath("//li[text()='by ']/a/text()")
            if producer_elements:
                movie.producer = producer_elements[0].strip()
            
            # 解析类型
            genre_elements = container.xpath("//a[@class='tag tagTag']/text()")
            if genre_elements:
                movie.genre = [g.strip() for g in genre_elements if g.strip()]
            
            # 解析发行日期
            date_elements = container.xpath("//div[@class='items_article_Releasedate']/p/text()")
            if date_elements:
                date_str = date_elements[0]
                # 提取日期部分，格式如'販売日 : 2017/11/30'
                date_match = re.search(r'(\d{4})/(\d{1,2})/(\d{1,2})', date_str)
                if date_match:
                    year, month, day = date_match.groups()
                    movie.publish_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            
            # 解析预览图片
            preview_elements = container.xpath("//ul[@data-feed='sample-images']/li/a/@href")
            if preview_elements:
                movie.preview_pics = preview_elements
            
            # 解析评分（简单版本，从星级获取）
            score_elements = container.xpath("//a[@class='items_article_Stars']/p/span/@class")
            if score_elements:
                score_class = score_elements[0]
                # 类名如'items_article_Star5'表示5星
                score_match = re.search(r'Star(\d+)', score_class)
                if score_match:
                    star_score = int(score_match.group(1))
                    movie.score = f"{star_score * 2:.2f}"  # 转换为10分制
            
            # 设置基本信息
            movie.dvdid = movie.dvdid.upper()  # 确保大写
            movie.url = url
            
            # 设置封面 - FC2的缩略图是220x220的，如果有预览图片，使用第一张作为封面
            if movie.preview_pics:
                movie.cover = movie.preview_pics[0]
            elif 'thumb_pic' in locals():
                movie.cover = thumb_pic
            
        except Exception as e:
            logger.error(f"Error parsing movie info: {e}")
            raise
    
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
            return is_url_accessible(self.base_url, timeout=5)
        except Exception as e:
            logger.error(f"FC2 crawler is not available: {e}")
            return False

# 创建全局实例
fc2_crawler = FC2Crawler()

def parse_data(movie: MovieInfo) -> None:
    """解析指定番号的影片数据（兼容接口）"""
    fc2_crawler.parse_data(movie)

def search_movie(dvdid: str) -> Optional[MovieInfo]:
    """搜索影片信息（便捷接口）"""
    return fc2_crawler.search_movie(dvdid)

if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)
    
    test_movie = MovieInfo(dvdid='FC2-718323')
    try:
        parse_data(test_movie)
        print(f"Title: {test_movie.title}")
        print(f"Producer: {test_movie.producer}")
        print(f"Duration: {test_movie.duration}")
        print(f"Genre: {test_movie.genre}")
        print(f"Score: {test_movie.score}")
        print(f"Preview pics: {len(test_movie.preview_pics) if test_movie.preview_pics else 0}")
    except Exception as e:
        logger.error(f"Test failed: {e}")