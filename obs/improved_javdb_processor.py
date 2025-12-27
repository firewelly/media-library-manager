"""
改进的JAVDB信息处理模块
包含改进的批量处理和数据库保存函数
"""

import os
import json
import subprocess
import threading
import time
import sqlite3
from typing import List, Dict, Any, Optional, Tuple

class ImprovedJavdbProcessor:
    """改进的JAVDB信息处理器"""
    
    def __init__(self, db_path: str, max_retries: int = 3, retry_delay: int = 2):
        """
        初始化处理器
        
        Args:
            db_path: 数据库路径
            max_retries: 最大重试次数
            retry_delay: 重试延迟(秒)
        """
        self.db_path = db_path
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.conn = None
        self.cursor = None
        self._connect_db()
    
    def _connect_db(self):
        """连接数据库"""
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.execute("PRAGMA foreign_keys = ON")
            self.cursor = self.conn.cursor()
        except Exception as e:
            raise Exception(f"数据库连接失败: {str(e)}")
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None
            self.cursor = None
    
    def save_javdb_info_to_db_improved(self, video_id: int, javdb_info: Dict[str, Any]) -> bool:
        """
        改进的JAVDB信息保存函数
        
        Args:
            video_id: 视频ID
            javdb_info: JAVDB信息字典
            
        Returns:
            bool: 保存是否成功
        """
        try:
            # 验证输入参数
            if not video_id or not javdb_info:
                print("错误: 无效的输入参数")
                return False
            
            # 验证必要字段
            if not javdb_info.get('title'):
                print("错误: 缺少标题信息")
                return False
            
            # 读取本地图片文件并转换为二进制数据
            cover_image_data = None
            local_image_path = javdb_info.get('local_image_path', '')
            if local_image_path and os.path.exists(local_image_path):
                try:
                    with open(local_image_path, 'rb') as f:
                        cover_image_data = f.read()
                    print(f"成功读取图片数据: {local_image_path}")
                except Exception as e:
                    print(f"读取图片文件失败 {local_image_path}: {e}")
            
            # 开始数据库事务
            try:
                # 检查是否已存在该video_id的JAVDB信息
                self.cursor.execute("SELECT id FROM javdb_info WHERE video_id = ?", (video_id,))
                existing_record = self.cursor.fetchone()
                
                if existing_record:
                    # 更新已有记录
                    javdb_info_id = existing_record[0]
                    self.cursor.execute("""
                        UPDATE javdb_info SET 
                        javdb_code = ?, javdb_url = ?, javdb_title = ?, release_date = ?, duration = ?,
                        studio = ?, score = ?, cover_url = ?, local_cover_path = ?, cover_image_data = ?,
                        magnet_links = ?, updated_at = datetime('now')
                        WHERE video_id = ?
                    """, (
                        javdb_info.get('video_id', ''),
                        javdb_info.get('detail_url', ''),
                        javdb_info.get('title', ''),
                        javdb_info.get('release_date', ''),
                        javdb_info.get('duration', ''),
                        javdb_info.get('studio', ''),
                        self._parse_rating(javdb_info.get('rating')),
                        javdb_info.get('cover_image_url', ''),
                        javdb_info.get('local_image_path', ''),
                        cover_image_data,
                        json.dumps(javdb_info.get('magnet_links', []), ensure_ascii=False),
                        video_id
                    ))
                    
                    # 清除旧的标签和演员关联
                    self.cursor.execute("DELETE FROM javdb_info_tags WHERE javdb_info_id = ?", (javdb_info_id,))
                    self.cursor.execute("DELETE FROM video_actors WHERE video_id = ?", (video_id,))
                    print(f"更新现有JAVDB记录: video_id={video_id}")
                else:
                    # 插入新记录
                    self.cursor.execute("""
                        INSERT INTO javdb_info 
                        (video_id, javdb_code, javdb_url, javdb_title, release_date, duration, 
                         studio, score, cover_url, local_cover_path, cover_image_data, magnet_links, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                    """, (
                        video_id,
                        javdb_info.get('video_id', ''),
                        javdb_info.get('detail_url', ''),
                        javdb_info.get('title', ''),
                        javdb_info.get('release_date', ''),
                        javdb_info.get('duration', ''),
                        javdb_info.get('studio', ''),
                        self._parse_rating(javdb_info.get('rating')),
                        javdb_info.get('cover_image_url', ''),
                        javdb_info.get('local_image_path', ''),
                        cover_image_data,
                        json.dumps(javdb_info.get('magnet_links', []), ensure_ascii=False)
                    ))
                    javdb_info_id = self.cursor.lastrowid
                    print(f"插入新JAVDB记录: video_id={video_id}")
                
                # 保存标签信息
                self._save_tags(javdb_info_id, javdb_info.get('tags', []))
                
                # 保存演员信息
                self._save_actors(video_id, javdb_info.get('actors', []))
                
                # 提交事务
                self.conn.commit()
                print(f"成功保存JAVDB信息: {javdb_info.get('title', 'Unknown')}")
                return True
                
            except Exception as e:
                # 回滚事务
                self.conn.rollback()
                print(f"保存JAVDB信息失败，事务已回滚: {str(e)}")
                return False
                
        except Exception as e:
            print(f"保存JAVDB信息到数据库失败: {str(e)}")
            return False
    
    def _parse_rating(self, rating: Any) -> Optional[float]:
        """解析评分"""
        if not rating or rating == 'N/A':
            return None
        try:
            return float(rating)
        except (ValueError, TypeError):
            return None
    
    def _save_tags(self, javdb_info_id: int, tags: List[str]) -> None:
        """保存标签信息"""
        if not tags:
            return
            
        for tag_name in tags:
            tag_name = tag_name.strip()
            if not tag_name:
                continue
                
            # 插入或获取标签
            self.cursor.execute("""
                INSERT OR IGNORE INTO javdb_tags (tag_name)
                VALUES (?)
            """, (tag_name,))
            
            # 获取标签ID
            self.cursor.execute("SELECT id FROM javdb_tags WHERE tag_name = ?", (tag_name,))
            tag_result = self.cursor.fetchone()
            if tag_result:
                tag_id = tag_result[0]
                
                # 建立javdb信息和标签的关联
                self.cursor.execute("""
                    INSERT OR IGNORE INTO javdb_info_tags (javdb_info_id, tag_id)
                    VALUES (?, ?)
                """, (javdb_info_id, tag_id))
    
    def _save_actors(self, video_id: int, actors: List[Dict[str, str]]) -> None:
        """保存演员信息"""
        if not actors:
            return
            
        for actor in actors:
            actor_name = actor.get('name', '').strip()
            actor_link = actor.get('link', '')
            
            if not actor_name:
                continue
                
            # 插入或获取演员信息
            self.cursor.execute("""
                INSERT OR IGNORE INTO actors (name, profile_url)
                VALUES (?, ?)
            """, (actor_name, actor_link))
            
            # 获取演员ID
            self.cursor.execute("SELECT id FROM actors WHERE name = ?", (actor_name,))
            actor_result = self.cursor.fetchone()
            if actor_result:
                actor_id = actor_result[0]
                
                # 建立视频和演员的关联
                self.cursor.execute("""
                    INSERT OR IGNORE INTO video_actors (video_id, actor_id)
                    VALUES (?, ?)
                """, (video_id, actor_id))
    
    def fetch_javdb_info_with_retry(self, av_code: str) -> Optional[Dict[str, Any]]:
        """
        带重试机制的JAVDB信息获取
        
        Args:
            av_code: 番号
            
        Returns:
            Dict or None: JAVDB信息字典或None
        """
        blocked_titles = ['官方App下載', '官方App下载', 'Official App Download']
        cwd_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 尝试多个数据源
        sources = [
            ("javdb", "javdb_crawler_single.py"),
            ("javbus", "javbus_crawler_single.py"),
            ("javsp", "javsp_integration.py")
        ]
        
        for source_name, script_name in sources:
            for attempt in range(self.max_retries):
                try:
                    print(f"尝试从 {source_name} 获取信息 (第 {attempt + 1} 次): {av_code}")
                    
                    if source_name == "javsp":
                        # JavSP 使用模块导入方式
                        from javsp_integration import search_javdb_info as javsp_search
                        result = javsp_search(av_code)
                    else:
                        # JavDB 和 JavBus 使用子进程方式
                        cmd = ["python", script_name, av_code]
                        process = subprocess.run(
                            cmd, 
                            capture_output=True, 
                            text=True, 
                            cwd=cwd_dir, 
                            timeout=60
                        )
                        
                        if process.returncode != 0 or not process.stdout:
                            raise Exception(f"脚本执行失败: {process.stderr}")
                            
                        result = json.loads(process.stdout)
                    
                    # 验证结果
                    if not result or result.get('error'):
                        raise Exception("返回结果为空或包含错误")
                        
                    if result.get('title') in blocked_titles:
                        raise Exception("标题被屏蔽")
                    
                    # 标准化结果格式
                    if source_name == "javbus":
                        result = self._normalize_javbus_result(result, av_code)
                    elif source_name == "javsp":
                        result = self._normalize_javsp_result(result, av_code)
                    
                    print(f"成功从 {source_name} 获取信息: {result.get('title')}")
                    return result
                    
                except subprocess.TimeoutExpired:
                    print(f"{source_name} 请求超时 (第 {attempt + 1} 次)")
                except json.JSONDecodeError as e:
                    print(f"{source_name} JSON解析失败 (第 {attempt + 1} 次): {e}")
                except Exception as e:
                    print(f"{source_name} 获取信息失败 (第 {attempt + 1} 次): {e}")
                
                # 如果不是最后一次尝试，等待后重试
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
        
        print(f"所有数据源均无法获取信息: {av_code}")
        return None
    
    def _normalize_javbus_result(self, result: Dict[str, Any], av_code: str) -> Dict[str, Any]:
        """标准化JavBus结果格式"""
        def normalize_actors_from_names(names):
            if not isinstance(names, list):
                return []
            return [{"name": n, "link": ""} for n in names if isinstance(n, str) and n.strip()]
        
        return {
            'title': result.get('title'),
            'video_id': result.get('number') or av_code,
            'detail_url': None,
            'release_date': result.get('release_date'),
            'duration': None,
            'rating': None,
            'tags': result.get('tags') or [],
            'actors': normalize_actors_from_names(result.get('actors', [])),
            'studio': result.get('studio'),
            'cover_image_url': result.get('cover_image_url'),
            'local_image_path': result.get('cover_image_path'),
            'magnet_links': result.get('magnet_links', [])
        }
    
    def _normalize_javsp_result(self, result: Dict[str, Any], av_code: str) -> Dict[str, Any]:
        """标准化JavSP结果格式"""
        # JavSP结果可能已经是标准格式，直接返回
        return result
    
    def batch_process_javdb_info_improved(
        self, 
        video_ids: List[int], 
        progress_callback=None,
        status_callback=None,
        cancel_event=None
    ) -> Tuple[int, int, List[str]]:
        """
        改进的批量处理JAVDB信息获取
        
        Args:
            video_ids: 视频ID列表
            progress_callback: 进度回调函数 (current, total, video_name, success)
            status_callback: 状态回调函数 (status_message, color)
            cancel_event: 取消事件对象
            
        Returns:
            Tuple[int, int, List[str]]: (成功数量, 失败数量, 失败详情列表)
        """
        success_count = 0
        failed_count = 0
        failed_files = []
        
        for i, video_id in enumerate(video_ids):
            # 检查是否取消
            if cancel_event and cancel_event.is_set():
                print("批量处理已取消")
                break
            
            # 获取视频信息
            self.cursor.execute("SELECT file_name, file_path FROM videos WHERE id = ?", (video_id,))
            result = self.cursor.fetchone()
            if not result:
                error_msg = f"ID {video_id}: 未找到视频记录"
                failed_files.append(error_msg)
                failed_count += 1
                if progress_callback:
                    progress_callback(i + 1, len(video_ids), f"ID {video_id}", False)
                continue
            
            file_name, file_path = result
            
            # 更新状态 - 开始处理
            if status_callback:
                status_callback(f"正在提取番号: {file_name}", None)
            
            try:
                # 提取番号
                from code_extractor import CodeExtractor
                extractor = CodeExtractor()
                av_code = extractor.extract_code_from_filename(file_name)
                
                if not av_code:
                    error_msg = f"{file_name}: 无法提取番号"
                    failed_files.append(error_msg)
                    failed_count += 1
                    if progress_callback:
                        progress_callback(i + 1, len(video_ids), file_name, False)
                    if status_callback:
                        status_callback(f"失败: 无法提取番号", "red")
                    continue
                
                # 更新状态 - 开始爬取
                if status_callback:
                    status_callback(f"正在爬取JAVDB信息: {av_code}", None)
                
                # 获取JAVDB信息
                javdb_info = self.fetch_javdb_info_with_retry(av_code)
                
                if not javdb_info:
                    error_msg = f"{file_name}: 无法获取JAVDB信息"
                    failed_files.append(error_msg)
                    failed_count += 1
                    if progress_callback:
                        progress_callback(i + 1, len(video_ids), file_name, False)
                    if status_callback:
                        status_callback(f"失败: 无法获取JAVDB信息", "red")
                    continue
                
                # 保存到数据库
                if status_callback:
                    status_callback(f"正在保存到数据库: {av_code}", None)
                
                if self.save_javdb_info_to_db_improved(video_id, javdb_info):
                    success_count += 1
                    if progress_callback:
                        progress_callback(i + 1, len(video_ids), file_name, True)
                    if status_callback:
                        status_callback(f"成功保存: {av_code}", "green")
                else:
                    error_msg = f"{file_name}: 保存到数据库失败"
                    failed_files.append(error_msg)
                    failed_count += 1
                    if progress_callback:
                        progress_callback(i + 1, len(video_ids), file_name, False)
                    if status_callback:
                        status_callback(f"失败: 保存到数据库失败", "red")
                
            except Exception as e:
                error_msg = f"{file_name}: {str(e)}"
                failed_files.append(error_msg)
                failed_count += 1
                if progress_callback:
                    progress_callback(i + 1, len(video_ids), file_name, False)
                if status_callback:
                    status_callback(f"失败: {str(e)}", "red")
            
            # 添加延迟避免请求过于频繁
            time.sleep(1)
        
        return success_count, failed_count, failed_files


# 使用示例
if __name__ == "__main__":
    # 创建处理器实例
    processor = ImprovedJavdbProcessor("media_library.db")
    
    # 测试单个视频的JAVDB信息保存
    test_video_id = 1
    test_javdb_info = {
        'title': '测试标题',
        'video_id': 'TEST-001',
        'detail_url': 'https://example.com',
        'release_date': '2023-01-01',
        'duration': '120',
        'studio': '测试工作室',
        'rating': '8.5',
        'tags': ['标签1', '标签2'],
        'actors': [{'name': '演员1', 'link': 'https://example.com/actor1'}],
        'cover_image_url': 'https://example.com/cover.jpg',
        'local_image_path': '/path/to/local/cover.jpg',
        'magnet_links': [{'link': 'magnet:?xt=urn:btih:example', 'title': '测试磁力链接'}]
    }
    
    # 保存测试数据
    success = processor.save_javdb_info_to_db_improved(test_video_id, test_javdb_info)
    print(f"保存结果: {'成功' if success else '失败'}")
    
    # 关闭处理器
    processor.close()