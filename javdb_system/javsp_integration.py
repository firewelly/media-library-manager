#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JavSP爬虫系统与媒体库集成模块

这个模块提供了将JavSP爬虫系统集成到现有媒体库的接口，
替换原有的单独JAVDB爬虫调用，提供更强大和稳定的数据获取能力。
"""

import os
import sys
import json
import logging
import sqlite3
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# 添加当前目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

try:
    from javsp_crawler_manager import CrawlerManager, search_movie_info, get_crawler_status
    from javsp_config_manager import config_manager
    from javsp_datatype import MovieInfo
except ImportError as e:
    print(f"警告: 无法导入JavSP模块: {e}")
    print("请确保JavSP相关文件存在于当前目录")


class JavSPIntegration:
    """
    JavSP爬虫系统与媒体库的集成类
    """
    
    def __init__(self, db_path: str = "media_library.db"):
        """
        初始化集成模块
        
        Args:
            db_path: 媒体库数据库路径
        """
        self.db_path = db_path
        self.logger = self._setup_logging()
        self.crawler_manager = None
        
        # 初始化爬虫管理器
        try:
            self.crawler_manager = CrawlerManager()
            self.logger.info("JavSP爬虫管理器初始化成功")
        except Exception as e:
            self.logger.error(f"JavSP爬虫管理器初始化失败: {e}")
    
    def _setup_logging(self) -> logging.Logger:
        """
        设置日志记录
        
        Returns:
            配置好的日志记录器
        """
        logger = logging.getLogger('javsp_integration')
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
    
    def is_available(self) -> bool:
        """
        检查JavSP爬虫系统是否可用
        
        Returns:
            True如果可用，False否则
        """
        return self.crawler_manager is not None
    
    def extract_code_from_filename(self, filename: str) -> Optional[str]:
        """
        从文件名中提取番号
        
        Args:
            filename: 文件名
            
        Returns:
            提取的番号，如果无法提取则返回None
        """
        if not filename:
            return None
            
        # 移除文件扩展名
        name_without_ext = os.path.splitext(filename)[0]
        
        # 常见的番号模式
        import re
        
        # 标准番号模式 (如: ABC-123, ABCD-123)
        patterns = [
            r'([A-Z]{2,6}-\d{3,5})',  # ABC-123, ABCD-1234
            r'(FC2-\d+)',              # FC2-1234567
            r'([A-Z]+\d{3,5})',        # ABC123, ABCD1234
            r'(\d{6}_\d{3})',          # 123456_789
        ]
        
        for pattern in patterns:
            match = re.search(pattern, name_without_ext.upper())
            if match:
                code = match.group(1)
                self.logger.debug(f"从文件名 '{filename}' 提取番号: {code}")
                return code
        
        self.logger.debug(f"无法从文件名 '{filename}' 提取番号")
        return None
    
    def search_movie_info(self, code: str, use_parallel: bool = True) -> Optional[Dict]:
        """
        搜索影片信息
        
        Args:
            code: 影片番号
            use_parallel: 是否使用并行搜索
            
        Returns:
            影片信息字典，如果未找到则返回None
        """
        if not self.is_available():
            self.logger.error("JavSP爬虫系统不可用")
            return None
            
        if not code:
            self.logger.warning("番号为空")
            return None
        
        try:
            self.logger.info(f"开始搜索影片信息: {code}")
            
            if use_parallel:
                movie_info = self.crawler_manager.search_movie(code, use_parallel=True)
            else:
                movie_info = self.crawler_manager.search_movie(code)
            
            if movie_info:
                self.logger.info(f"成功获取影片信息: {code} - {movie_info.title}")
                return self._convert_movie_info_to_dict(movie_info)
            else:
                self.logger.warning(f"未找到影片信息: {code}")
                return None
                
        except Exception as e:
            self.logger.error(f"搜索影片信息时发生错误 ({code}): {e}")
            return None
    
    def _convert_movie_info_to_dict(self, movie_info: 'MovieInfo') -> Dict:
        """
        将MovieInfo对象转换为字典格式
        
        Args:
            movie_info: MovieInfo对象
            
        Returns:
            转换后的字典
        """
        try:
            # 清理标题
            title = movie_info.clean_title() if hasattr(movie_info, 'clean_title') else movie_info.title
            
            # 转换演员列表
            actors = []
            if movie_info.actress:
                for actress in movie_info.actress:
                    if isinstance(actress, str):
                        actors.append({'name': actress})
                    elif isinstance(actress, dict):
                        actors.append(actress)
            
            # 转换类型列表
            tags = []
            if movie_info.genre:
                if isinstance(movie_info.genre, list):
                    tags = movie_info.genre
                elif isinstance(movie_info.genre, str):
                    tags = [movie_info.genre]
            
            # 处理评分
            rating = None
            if movie_info.score:
                try:
                    rating = float(movie_info.score)
                except (ValueError, TypeError):
                    rating = None
            
            # 处理时长
            duration = None
            if movie_info.duration:
                try:
                    # 如果是字符串，尝试提取数字
                    if isinstance(movie_info.duration, str):
                        import re
                        match = re.search(r'(\d+)', movie_info.duration)
                        if match:
                            duration = int(match.group(1))
                    else:
                        duration = int(movie_info.duration)
                except (ValueError, TypeError):
                    duration = None
            
            result = {
                'video_id': movie_info.dvdid or movie_info.cid,
                'detail_url': movie_info.url,
                'title': title,
                'release_date': movie_info.publish_date,
                'duration': f"{duration}分钟" if duration else None,
                'studio': movie_info.producer or movie_info.publisher,
                'series': movie_info.serial,
                'rating': rating,
                'cover_image_url': movie_info.cover,
                'local_image_path': None,  # 将在后续处理中设置
                'magnet_links': movie_info.magnet if isinstance(movie_info.magnet, list) else ([movie_info.magnet] if movie_info.magnet else []),
                'tags': tags,
                'actors': actors,
                'source': 'javsp',  # 标识数据来源
                'crawled_at': datetime.now().isoformat()
            }
            
            return result
            
        except Exception as e:
            self.logger.error(f"转换MovieInfo对象时发生错误: {e}")
            return None
    
    def batch_search_movies(self, codes: List[str], use_parallel: bool = True) -> Dict[str, Dict]:
        """
        批量搜索影片信息
        
        Args:
            codes: 番号列表
            use_parallel: 是否使用并行搜索
            
        Returns:
            番号到影片信息的映射字典
        """
        if not self.is_available():
            self.logger.error("JavSP爬虫系统不可用")
            return {}
            
        if not codes:
            return {}
        
        try:
            self.logger.info(f"开始批量搜索 {len(codes)} 个影片")
            
            if use_parallel:
                movie_infos = self.crawler_manager.batch_search(codes, use_parallel=True)
            else:
                movie_infos = {}
                for code in codes:
                    movie_info = self.crawler_manager.search_movie(code)
                    if movie_info:
                        movie_infos[code] = movie_info
            
            # 转换结果
            results = {}
            for code, movie_info in movie_infos.items():
                if movie_info:
                    converted = self._convert_movie_info_to_dict(movie_info)
                    if converted:
                        results[code] = converted
            
            self.logger.info(f"批量搜索完成，成功获取 {len(results)} 个影片信息")
            return results
            
        except Exception as e:
            self.logger.error(f"批量搜索影片信息时发生错误: {e}")
            return {}
    
    def get_crawler_status(self) -> Dict:
        """
        获取爬虫状态信息
        
        Returns:
            爬虫状态字典
        """
        if not self.is_available():
            return {'available': False, 'error': 'JavSP爬虫系统不可用'}
        
        try:
            status = get_crawler_status()
            status['available'] = True
            return status
        except Exception as e:
            return {'available': False, 'error': str(e)}
    
    def save_movie_info_to_db(self, video_id: int, movie_info: Dict) -> bool:
        """
        将影片信息保存到数据库
        
        Args:
            video_id: 视频ID
            movie_info: 影片信息字典
            
        Returns:
            True如果保存成功，False否则
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 检查并创建javdb_info表（移除tags/actors/source；新增rating/preview_images）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS javdb_info (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id INTEGER NOT NULL,
                    javdb_code TEXT NOT NULL,
                    javdb_url TEXT,
                    javdb_title TEXT,
                    release_date TEXT,
                    duration TEXT,
                    studio TEXT,
                    series TEXT,
                    rating TEXT,
                    score REAL,
                    cover_url TEXT,
                    local_cover_path TEXT,
                    cover_image_data BLOB,
                    magnet_links TEXT,
                    preview_images TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (video_id) REFERENCES videos (id) ON DELETE CASCADE,
                    UNIQUE(video_id)
                )
            """)

            # 关系型表：JAVDB标签与关联、演员与视频-演员关联
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS javdb_tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tag_name TEXT UNIQUE NOT NULL,
                    tag_type TEXT DEFAULT 'general',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS javdb_info_tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    javdb_info_id INTEGER NOT NULL,
                    tag_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (javdb_info_id) REFERENCES javdb_info (id) ON DELETE CASCADE,
                    FOREIGN KEY (tag_id) REFERENCES javdb_tags (id) ON DELETE CASCADE,
                    UNIQUE(javdb_info_id, tag_id)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS actors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    profile_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS video_actors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id INTEGER NOT NULL,
                    actor_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (video_id) REFERENCES videos (id) ON DELETE CASCADE,
                    FOREIGN KEY (actor_id) REFERENCES actors (id) ON DELETE CASCADE,
                    UNIQUE(video_id, actor_id)
                )
                """
            )
            
            # 处理评分
            score = None
            if movie_info.get('rating'):
                try:
                    score = float(movie_info['rating'])
                except (ValueError, TypeError):
                    score = None

            # 读取本地封面为二进制数据
            cover_image_data = None
            local_image_path = movie_info.get('local_image_path', '')

            def _read_image(path: str):
                try:
                    with open(path, 'rb') as f:
                        return f.read()
                except Exception as e:
                    self.logger.warning(f"读取封面文件失败 {path}: {e}")
                    return None

            if local_image_path:
                try:
                    if not os.path.isabs(local_image_path):
                        base_dir = os.path.dirname(os.path.abspath(__file__))
                        candidate = os.path.join(base_dir, local_image_path)
                        if os.path.exists(candidate):
                            cover_image_data = _read_image(candidate)
                        elif os.path.exists(local_image_path):
                            cover_image_data = _read_image(local_image_path)
                    else:
                        if os.path.exists(local_image_path):
                            cover_image_data = _read_image(local_image_path)
                except Exception:
                    pass
            
            # 插入或更新记录（仅写入基础字段与JSON磁链；标签与演员用关系表维护）
            cursor.execute(
                """
                INSERT OR REPLACE INTO javdb_info 
                (video_id, javdb_code, javdb_url, javdb_title, release_date, duration,
                 studio, series, rating, score, cover_url, local_cover_path, cover_image_data, magnet_links,
                 updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (
                    video_id,
                    movie_info.get('video_id', ''),
                    movie_info.get('detail_url', ''),
                    movie_info.get('title', ''),
                    movie_info.get('release_date', ''),
                    movie_info.get('duration', ''),
                    movie_info.get('studio', ''),
                    movie_info.get('series', ''),
                    movie_info.get('rating', ''),
                    score,
                    movie_info.get('cover_image_url', ''),
                    movie_info.get('local_image_path', ''),
                    cover_image_data,
                    json.dumps(movie_info.get('magnet_links', []), ensure_ascii=False),
                )
            )

            # 获取当前javdb_info记录ID用于关系写入
            cursor.execute("SELECT id FROM javdb_info WHERE video_id = ?", (video_id,))
            row = cursor.fetchone()
            javdb_info_id = row[0] if row else None

            # 写入JAVDB标签关系
            try:
                if javdb_info_id and movie_info.get('tags'):
                    for t in movie_info.get('tags'):
                        tag_name = (t or '').strip()
                        if not tag_name:
                            continue
                        cursor.execute(
                            "INSERT OR IGNORE INTO javdb_tags (tag_name) VALUES (?)",
                            (tag_name,),
                        )
                        cursor.execute("SELECT id FROM javdb_tags WHERE tag_name = ?", (tag_name,))
                        tag_row = cursor.fetchone()
                        if tag_row:
                            tag_id = tag_row[0]
                            cursor.execute(
                                "INSERT OR IGNORE INTO javdb_info_tags (javdb_info_id, tag_id) VALUES (?, ?)",
                                (javdb_info_id, tag_id),
                            )
            except Exception as _e:
                self.logger.warning(f"写入JAVDB标签关联失败: {_e}")

            # 写入演员与视频-演员关系
            try:
                actors = movie_info.get('actors') or []
                for a in actors:
                    name = None
                    profile_url = None
                    if isinstance(a, dict):
                        name = (a.get('name') or '').strip() if a.get('name') else None
                        profile_url = (
                            a.get('profile_url')
                            or a.get('link')
                            or a.get('url')
                        )
                    elif isinstance(a, str):
                        name = a.strip()
                    if not name:
                        continue

                    # 插入或获取演员ID
                    cursor.execute("SELECT id, profile_url FROM actors WHERE name = ?", (name,))
                    ar = cursor.fetchone()
                    if ar:
                        actor_id = ar[0]
                        # 更新缺失的个人链接
                        if profile_url and not (ar[1] or '').strip():
                            cursor.execute(
                                "UPDATE actors SET profile_url = ?, updated_at = datetime('now') WHERE id = ?",
                                (profile_url, actor_id),
                            )
                    else:
                        cursor.execute(
                            """
                            INSERT INTO actors (name, profile_url, created_at, updated_at)
                            VALUES (?, ?, datetime('now'), datetime('now'))
                            """,
                            (name, profile_url),
                        )
                        actor_id = cursor.lastrowid

                    # 建立视频-演员关联
                    if actor_id:
                        cursor.execute(
                            """
                            INSERT OR IGNORE INTO video_actors (video_id, actor_id, created_at)
                            VALUES (?, ?, datetime('now'))
                            """,
                            (video_id, actor_id),
                        )
            except Exception as _e:
                self.logger.warning(f"写入演员关联失败: {_e}")
            
            conn.commit()
            conn.close()
            
            self.logger.info(f"成功保存影片信息到数据库: video_id={video_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"保存影片信息到数据库时发生错误: {e}")
            return False


# 全局集成实例
_integration_instance = None

def get_integration_instance(db_path: str = "media_library.db") -> JavSPIntegration:
    """
    获取全局集成实例
    
    Args:
        db_path: 数据库路径
        
    Returns:
        JavSP集成实例
    """
    global _integration_instance
    if _integration_instance is None:
        _integration_instance = JavSPIntegration(db_path)
    return _integration_instance


# 兼容性函数，用于替换原有的JAVDB爬虫调用
def search_javdb_info(code: str) -> Optional[Dict]:
    """
    搜索JAVDB信息的兼容性函数
    
    Args:
        code: 影片番号
        
    Returns:
        影片信息字典
    """
    integration = get_integration_instance()
    return integration.search_movie_info(code)


def extract_code_from_filename(filename: str) -> Optional[str]:
    """
    从文件名提取番号的兼容性函数
    
    Args:
        filename: 文件名
        
    Returns:
        提取的番号
    """
    integration = get_integration_instance()
    return integration.extract_code_from_filename(filename)


if __name__ == "__main__":
    # 测试代码
    integration = JavSPIntegration()
    
    print("=== JavSP集成模块测试 ===")
    print(f"系统可用性: {integration.is_available()}")
    
    if integration.is_available():
        # 测试番号提取
        test_filename = "IPZZ-565.mp4"
        code = integration.extract_code_from_filename(test_filename)
        print(f"从文件名 '{test_filename}' 提取番号: {code}")
        
        # 测试搜索
        if code:
            print(f"\n搜索影片信息: {code}")
            movie_info = integration.search_movie_info(code)
            if movie_info:
                print(f"标题: {movie_info.get('title', 'N/A')}")
                print(f"发布日期: {movie_info.get('release_date', 'N/A')}")
                print(f"制作商: {movie_info.get('studio', 'N/A')}")
                print(f"评分: {movie_info.get('rating', 'N/A')}")
            else:
                print("未找到影片信息")
        
        # 测试爬虫状态
        print(f"\n爬虫状态: {integration.get_crawler_status()}")
    else:
        print("JavSP爬虫系统不可用")
