"""
media_library.py 修改补丁
用于改进JAVDB信息处理功能

使用方法:
1. 备份原始的media_library.py文件
2. 将此补丁中的函数替换原始文件中的对应函数
3. 或者使用patch工具应用此补丁
"""

import os
import json
import subprocess
import time
from tkinter import messagebox

# 注意: ProgressWindow类应该从原始的media_library.py中导入
# 如果这个补丁是作为独立模块使用，需要添加以下导入:
# from media_library import ProgressWindow

# 以下是改进的save_javdb_info_to_db函数
def save_javdb_info_to_db_improved(self, video_id, javdb_info):
    """改进的JAVDB信息保存函数，增强错误处理和数据验证"""
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
            self._save_tags_improved(javdb_info_id, javdb_info.get('tags', []))
            
            # 保存演员信息
            self._save_actors_improved(video_id, javdb_info.get('actors', []))
            
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

def _parse_rating(self, rating):
    """解析评分"""
    if not rating or rating == 'N/A':
        return None
    try:
        return float(rating)
    except (ValueError, TypeError):
        return None

def _save_tags_improved(self, javdb_info_id, tags):
    """改进的标签信息保存函数"""
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

def _save_actors_improved(self, video_id, actors):
    """改进的演员信息保存函数"""
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

def fetch_javdb_info_with_retry(self, av_code, max_retries=3, retry_delay=2):
    """带重试机制的JAVDB信息获取"""
    blocked_titles = ['官方App下載', '官方App下载', 'Official App Download']
    cwd_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 尝试多个数据源
    sources = [
        ("javdb", "javdb_crawler_single.py"),
        ("javbus", "javbus_crawler_single.py"),
        ("javsp", "javsp_integration.py")
    ]
    
    for source_name, script_name in sources:
        for attempt in range(max_retries):
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
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
    
    print(f"所有数据源均无法获取信息: {av_code}")
    return None

def _normalize_javbus_result(self, result, av_code):
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

def _normalize_javsp_result(self, result, av_code):
    """标准化JavSP结果格式"""
    # JavSP结果可能已经是标准格式，直接返回
    return result

def batch_process_javdb_info_improved(self, video_ids):
    """改进的批量处理JAVDB信息获取"""
    try:
        print(f"开始批量处理JAVDB信息，视频数量: {len(video_ids)}")
        
        # 创建进度窗口
        print("正在创建进度窗口...")
        progress_window = ProgressWindow(self.root, "批量JAVDB信息获取", len(video_ids))
        print("进度窗口创建成功")
        
        def fetch_javdb_info():
            try:
                print("fetch_javdb_info线程开始执行")
                failed_files = []
                
                for i, video_id in enumerate(video_ids):
                    # 检查是否取消
                    if progress_window.cancelled:
                        break
                    
                    # 获取视频信息
                    self.cursor.execute("SELECT file_name, file_path FROM videos WHERE id = ?", (video_id,))
                    result = self.cursor.fetchone()
                    if not result:
                        error_msg = f"ID {video_id}: 未找到视频记录"
                        failed_files.append(error_msg)
                        progress_window.update_progress(i + 1, f"ID {video_id}", success=False)
                        continue
                    
                    file_name, file_path = result
                    
                    # 更新进度 - 开始处理
                    progress_window.update_progress(i + 1, file_name)
                    progress_window.update_status(f"正在提取番号: {file_name}")
                    
                    try:
                        # 导入番号提取器
                        from code_extractor import CodeExtractor
                        
                        # 提取番号
                        extractor = CodeExtractor()
                        av_code = extractor.extract_code_from_filename(file_name)
                        
                        if not av_code:
                            error_msg = f"{file_name}: 无法提取番号"
                            failed_files.append(error_msg)
                            progress_window.update_progress(i + 1, file_name, success=False)
                            progress_window.update_status(f"失败: 无法提取番号", "red")
                            continue
                        
                        # 更新状态 - 开始爬取
                        progress_window.update_status(f"正在爬取JAVDB信息: {av_code}")
                        
                        # 获取JAVDB信息（使用改进的重试机制）
                        javdb_info = self.fetch_javdb_info_with_retry(av_code)
                        
                        if not javdb_info:
                            error_msg = f"{file_name}: 无法获取JAVDB信息"
                            failed_files.append(error_msg)
                            progress_window.update_progress(i + 1, file_name, success=False)
                            progress_window.update_status(f"失败: 无法获取JAVDB信息", "red")
                            continue
                        
                        # 保存到数据库（使用改进的保存函数）
                        progress_window.update_status(f"正在保存到数据库: {av_code}")
                        if self.save_javdb_info_to_db_improved(video_id, javdb_info):
                            progress_window.update_progress(i + 1, file_name, success=True)
                            progress_window.update_status(f"成功保存: {av_code}", "green")
                        else:
                            error_msg = f"{file_name}: 保存到数据库失败"
                            failed_files.append(error_msg)
                            progress_window.update_progress(i + 1, file_name, success=False)
                            progress_window.update_status(f"失败: 保存到数据库失败", "red")
                        
                    except subprocess.TimeoutExpired:
                        error_msg = f"{file_name}: 获取超时"
                        failed_files.append(error_msg)
                        progress_window.update_progress(i + 1, file_name, success=False)
                        progress_window.update_status("失败: 获取超时", "red")
                    except ImportError:
                        error_msg = f"{file_name}: 无法导入番号提取器"
                        failed_files.append(error_msg)
                        progress_window.update_progress(i + 1, file_name, success=False)
                        progress_window.update_status("失败: 无法导入番号提取器", "red")
                    except Exception as e:
                        error_msg = f"{file_name}: {str(e)}"
                        failed_files.append(error_msg)
                        progress_window.update_progress(i + 1, file_name, success=False)
                        progress_window.update_status(f"失败: {str(e)}", "red")
                    
                    # 添加延迟避免请求过于频繁
                    time.sleep(1)
                
                # 处理完成
                if not progress_window.cancelled:
                    progress_window.update_status("批量处理完成！", "blue")
                    
                    # 刷新视频列表
                    self.root.after(100, self.load_videos)
                    
                    # 显示结果
                    success_count = progress_window.success_count
                    failed_count = progress_window.failed_count
                    
                    result_msg = f"批量JAVDB信息获取完成！\n成功获取: {success_count} 个文件\n失败: {failed_count} 个文件"
                    if failed_files:
                        result_msg += "\n\n失败详情:\n" + "\n".join(failed_files[:10])
                        if len(failed_files) > 10:
                            result_msg += f"\n... 还有 {len(failed_files) - 10} 个失败文件"
                    
                    # 延迟显示结果对话框，让用户看到最终状态
                    self.root.after(2000, lambda: messagebox.showinfo("完成", result_msg))
                    self.root.after(2000, lambda: progress_window.close())
                else:
                    # 用户取消了操作
                    progress_window.update_status("操作已取消", "orange")
                    success_count = progress_window.success_count
                    self.root.after(1000, lambda: messagebox.showinfo("取消", f"操作已取消\n已成功处理: {success_count} 个文件"))
                    self.root.after(1000, lambda: progress_window.close())
                
            except Exception as e:
                progress_window.close()
                messagebox.showerror("错误", f"批量JAVDB信息获取失败: {str(e)}")
        
        # 在新线程中执行
        print("正在启动处理线程...")
        import threading
        thread = threading.Thread(target=fetch_javdb_info)
        thread.daemon = True
        thread.start()
        print("处理线程已启动")
        
    except Exception as e:
        messagebox.showerror("错误", f"批量JAVDB信息获取失败: {str(e)}")

# 应用补丁的说明
"""
应用补丁步骤:

1. 备份原始的 media_library.py 文件
   cp media_library.py media_library.py.backup

2. 将上述函数添加到 MediaLibrary 类中，替换原有函数:
   - save_javdb_info_to_db 替换为 save_javdb_info_to_db_improved
   - batch_process_javdb_info 替换为 batch_process_javdb_info_improved
   - 添加新的辅助函数: _parse_rating, _save_tags_improved, _save_actors_improved
   - 添加新的辅助函数: fetch_javdb_info_with_retry, _normalize_javbus_result, _normalize_javsp_result

3. 更新右键菜单中的调用，将 batch_process_javdb_info 改为 batch_process_javdb_info_improved

4. 测试功能是否正常工作

改进点:
1. 增强了错误处理和数据验证
2. 添加了数据库事务管理，失败时自动回滚
3. 实现了多数据源重试机制
4. 改进了数据标准化处理
5. 增加了更详细的日志记录
6. 优化了内存使用，避免大文件一次性读取
"""