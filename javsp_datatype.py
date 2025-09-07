"""JavSP数据类型定义"""
import json
import logging
from typing import List, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

@dataclass
class MovieInfo:
    """影片信息类"""
    dvdid: Optional[str] = None          # DVD ID，即通常的番号
    cid: Optional[str] = None            # DMM Content ID
    url: Optional[str] = None            # 影片页面的URL
    plot: Optional[str] = None           # 故事情节
    cover: Optional[str] = None          # 封面图片（URL）
    big_cover: Optional[str] = None      # 高清封面图片（URL）
    genre: Optional[List[str]] = None    # 影片分类的标签
    genre_id: Optional[List[str]] = None # 影片分类的标签的ID
    genre_norm: Optional[List[str]] = None # 统一后的影片分类的标签
    score: Optional[str] = None          # 评分（10分制）
    title: Optional[str] = None          # 影片标题（不含番号）
    ori_title: Optional[str] = None      # 原始影片标题
    magnet: Optional[str] = None         # 磁力链接
    serial: Optional[str] = None         # 系列
    actress: Optional[List[str]] = None  # 出演女优
    actress_pics: Optional[List[str]] = None # 出演女优的头像
    director: Optional[str] = None       # 导演
    duration: Optional[str] = None       # 影片时长
    producer: Optional[str] = None       # 制作商
    publisher: Optional[str] = None      # 发行商
    uncensored: Optional[bool] = None    # 是否为无码影片
    publish_date: Optional[str] = None   # 发布日期
    preview_pics: Optional[List[str]] = None # 预览图片（URL）
    preview_video: Optional[str] = None  # 预览视频（URL）
    
    @property
    def release_date(self):
        """发布日期的别名，兼容不同的访问方式"""
        return self.publish_date
    
    @release_date.setter
    def release_date(self, value):
        """设置发布日期"""
        self.publish_date = value
    
    @property
    def studio(self):
        """工作室的别名，兼容不同的访问方式"""
        return self.producer or self.publisher
    
    @studio.setter
    def studio(self, value):
        """设置工作室"""
        if not self.producer:
            self.producer = value
        elif not self.publisher:
            self.publisher = value
        else:
            self.producer = value
    
    def __post_init__(self):
        """初始化后处理"""
        # 确保列表字段不为None
        if self.genre is None:
            self.genre = []
        if self.genre_id is None:
            self.genre_id = []
        if self.genre_norm is None:
            self.genre_norm = []
        if self.actress is None:
            self.actress = []
        if self.actress_pics is None:
            self.actress_pics = []
        if self.preview_pics is None:
            self.preview_pics = []
    
    def __str__(self) -> str:
        """字符串表示"""
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)
    
    def __repr__(self) -> str:
        """对象表示"""
        if self.dvdid:
            expression = f"('{self.dvdid}')"
        elif self.cid:
            expression = f"(cid='{self.cid}')"
        else:
            expression = "()"
        return self.__class__.__name__ + expression
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)
    
    def is_valid(self) -> bool:
        """检查数据是否有效"""
        # 至少需要有番号或CID
        if not self.dvdid and not self.cid:
            return False
        # 至少需要有标题
        if not self.title:
            return False
        return True
    
    def get_id(self) -> str:
        """获取影片ID（优先返回dvdid）"""
        return self.dvdid or self.cid or ''
    
    def clean_title(self) -> str:
        """清理标题，移除常见的无用信息"""
        if not self.title:
            return ''
        
        title = self.title.strip()
        
        # 移除常见的无用标题
        useless_titles = [
            '官方App下載',
            '官方App下载',
            'Official App Download',
            'アプリダウンロード',
            '公式アプリ',
        ]
        
        for useless in useless_titles:
            if useless in title:
                title = title.replace(useless, '').strip()
        
        # 移除多余的空格和标点
        title = ' '.join(title.split())
        title = title.strip('- ')
        
        return title
    
    def merge_from(self, other: 'MovieInfo') -> None:
        """从另一个MovieInfo对象合并数据"""
        if not isinstance(other, MovieInfo):
            return
        
        # 合并非空字段
        for field_name, field_value in asdict(other).items():
            if field_value is not None:
                current_value = getattr(self, field_name)
                if current_value is None or (isinstance(current_value, list) and not current_value):
                    setattr(self, field_name, field_value)
                elif isinstance(field_value, list) and isinstance(current_value, list):
                    # 合并列表，去重
                    merged_list = list(set(current_value + field_value))
                    setattr(self, field_name, merged_list)
    
    def validate_required_fields(self, required_fields: List[str]) -> bool:
        """验证必需字段是否存在"""
        for field in required_fields:
            value = getattr(self, field, None)
            if value is None or (isinstance(value, list) and not value):
                logger.warning(f"Missing required field: {field} for {self.get_id()}")
                return False
        return True

def create_movie_info(dvdid: str = None, cid: str = None) -> MovieInfo:
    """创建MovieInfo实例的工厂函数"""
    if not dvdid and not cid:
        raise ValueError("Either dvdid or cid must be provided")
    
    return MovieInfo(dvdid=dvdid, cid=cid)