#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
演员详细信息爬虫
使用Selenium + SOCKS5代理爬取JAVDB演员页面的详细信息
"""

import sqlite3
import os
import time
import json
import requests
import platform
import subprocess
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.edge.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException

class ActorDetailCrawler:
    def __init__(self, proxy_host="127.0.0.1", proxy_port="1080"):
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port
        self.driver = None
        self.db_path = os.path.join(os.path.dirname(__file__), 'media_library.db')
        
    def get_edge_driver_path(self):
        """获取Edge driver路径"""
        system = platform.system().lower()
        if system == "windows":
            return r"C:\bin\edgedriver_win64\msedgedriver.exe"
        elif system == "darwin":  # macOS
            machine = platform.machine().lower()
            if machine in ['arm64', 'aarch64']:
                # 优先检查用户目录
                user_path = os.path.expanduser("~/bin/edgedriver_mac64_m1/msedgedriver")
                if os.path.exists(user_path):
                    return user_path
                return "/usr/local/bin/edgedriver_mac64_m1/msedgedriver"
            else:
                user_path = os.path.expanduser("~/bin/edgedriver_mac64/msedgedriver")
                if os.path.exists(user_path):
                    return user_path
                return "/usr/local/bin/edgedriver_mac64/msedgedriver"
        elif system == "linux":
            return "/usr/local/bin/edgedriver_linux64/msedgedriver"
        else:
            return "/usr/local/bin/edgedriver_mac64/msedgedriver"
    
    def setup_driver(self):
        """设置Edge浏览器驱动，配置SOCKS5代理"""
        edge_options = Options()
        # edge_options.add_argument('--headless')  # 关闭无头模式以便调试
        edge_options.add_argument('--no-sandbox')
        edge_options.add_argument('--disable-dev-shm-usage')
        edge_options.add_argument('--disable-gpu')
        edge_options.add_argument('--window-size=1920,1080')
        edge_options.add_argument('--disable-blink-features=AutomationControlled')
        edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        edge_options.add_experimental_option('useAutomationExtension', False)
        
        # 配置SOCKS5代理
        edge_options.add_argument(f'--proxy-server=socks5://{self.proxy_host}:{self.proxy_port}')
        
        # 设置更真实的用户代理
        edge_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # 禁用图片加载以提高速度
        prefs = {
            "profile.managed_default_content_settings.images": 2,
            "profile.default_content_setting_values.notifications": 2
        }
        edge_options.add_experimental_option("prefs", prefs)
        
        try:
            # 获取Edge driver路径
            driver_path = self.get_edge_driver_path()
            
            # 检查driver是否存在
            if not os.path.exists(driver_path):
                print(f"Edge driver未找到: {driver_path}")
                print("请运行 python3 update_msedge_driver.py 来安装Edge driver")
                raise FileNotFoundError(f"Edge driver not found: {driver_path}")
            
            # 创建Edge service
            service = Service(executable_path=driver_path)
            self.driver = webdriver.Edge(service=service, options=edge_options)
            self.driver.set_page_load_timeout(30)
            
            # 执行反检测脚本
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")
            self.driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en']})")
            
            print("Edge驱动初始化成功，已配置SOCKS5代理")
            return True
        except Exception as e:
            print(f"Edge驱动初始化失败: {e}")
            return False
    
    def close_driver(self):
        """关闭浏览器驱动"""
        if self.driver:
            self.driver.quit()
            self.driver = None
    
    def crawl_actor_detail(self, actor_url):
        """爬取演员详细信息"""
        if not self.driver:
            if not self.setup_driver():
                return None
        
        try:
            # # 先测试访问JAVDB主页
            # print("测试访问JAVDB主页...")
            # self.driver.get("https://javdb.com")
            # time.sleep(3)
            # print(f"JAVDB主页标题: {self.driver.title}")
            
            print(f"正在爬取演员页面: {actor_url}")
            self.driver.get(actor_url)
            
            # 增加等待时间并添加调试信息
            print("等待页面加载...")
            wait = WebDriverWait(self.driver, 20)  # 增加到20秒
            
            # 先等待页面基本加载完成
            wait.until(lambda driver: driver.execute_script("return document.readyState") == "complete")
            print(f"页面加载完成，当前URL: {self.driver.current_url}")
            print(f"页面标题: {self.driver.title}")
            
            # 检查页面是否正常加载（通过标题判断）
            page_title = self.driver.title
            if "寶生莉莉" in page_title or "JavDB" in page_title:
                print("页面加载正常，继续解析")
            else:
                print(f"页面可能有问题，标题: {page_title}")
                # 检查是否有验证码或防护页面
                page_source = self.driver.page_source
                if "验证" in page_source or "captcha" in page_source.lower() or "cloudflare" in page_source.lower():
                    print("检测到验证码或防护页面，尝试等待...")
                    time.sleep(5)
                    # 刷新页面重试
                    self.driver.refresh()
                    time.sleep(3)
                    page_source = self.driver.page_source
                    if "验证" in page_source or "captcha" in page_source.lower() or "cloudflare" in page_source.lower():
                        print("仍然检测到防护页面，跳过此页面")
                        return None
                    else:
                        print("防护页面已通过")
                else:
                    print("未检测到明显的防护页面，继续尝试解析")
            
            # 等待演员信息区域出现
            try:
                # 增加页面稳定性检查
                time.sleep(2)
                
                # 检查浏览器是否还在运行
                try:
                    current_url = self.driver.current_url
                    print(f"当前页面URL确认: {current_url}")
                except Exception as e:
                    print(f"浏览器连接异常: {e}")
                    return None
                
                # 查找演员名称元素
                wait.until(EC.presence_of_element_located((By.CLASS_NAME, "actor-section-name")))
                print("找到演员名称元素")
            except TimeoutException:
                print("未找到演员名称元素，尝试查找其他元素...")
                try:
                    # 尝试查找其他可能的演员信息元素
                    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".actor-info, .profile, .actor-detail")))
                    print("找到演员信息元素")
                except TimeoutException:
                    print("页面中未找到任何演员相关元素")
                    return None
            except Exception as e:
                print(f"等待演员信息时发生异常: {e}")
                return None
            
            actor_info = {
                'name': '',
                'name_traditional': '',
                'name_common': '',
                'aliases': '',
                'avatar_url': '',
                'avatar_data': None
            }
            
            # 获取演员名称信息
            try:
                # 获取主要名称（从 actor-section-name 元素）
                 name_element = self.driver.find_element(By.CLASS_NAME, "actor-section-name")
                 main_names = name_element.text.strip() if name_element else ""
                 print(f"主要名称: {main_names}")
                 
                 # 获取别名（从 section-meta 元素）
                 aliases = []
                 try:
                     alias_element = self.driver.find_element(By.CLASS_NAME, "section-meta")
                     alias_text = alias_element.text.strip() if alias_element else ""
                     if alias_text:
                         aliases = [alias.strip() for alias in alias_text.split(',')]
                     print(f"别名: {aliases}")
                 except Exception as e:
                     print(f"获取别名时出错: {e}")
                 
                 # 解析主要名称（可能包含多个名称，用逗号分隔）
                 primary_names = [name.strip() for name in main_names.split(',') if name.strip()]
                 
                 # 合并所有名称
                 all_names = primary_names + aliases
                 
                 # 分类名称
                 japanese_name = None
                 traditional_name = None
                 other_aliases = []
                 
                 # 从所有名称中找到日文名和繁体中文名
                 for name in all_names:
                     if name:
                         # 检查是否包含日文假名（作为主名称和常用名）
                         if any('\u3040' <= char <= '\u309f' or '\u30a0' <= char <= '\u30ff' for char in name):
                             if not japanese_name:
                                 japanese_name = name
                             else:
                                 other_aliases.append(name)
                         # 检查是否包含中文字符（作为繁体中文名）
                         elif any('\u4e00' <= char <= '\u9fff' for char in name):
                             if not traditional_name:
                                 traditional_name = name
                             else:
                                 other_aliases.append(name)
                         else:
                             other_aliases.append(name)
                 
                 # 设置字段值
                 actor_info['name'] = japanese_name if japanese_name else (traditional_name if traditional_name else "未知")
                 actor_info['name_common'] = japanese_name if japanese_name else ""
                 actor_info['name_traditional'] = traditional_name if traditional_name else ""
                 
                 if other_aliases:
                     actor_info['aliases'] = ', '.join(other_aliases)
                 
                 print(f"分类结果:")
                 print(f"  主名称(name): {actor_info['name']}")
                 print(f"  常用名(name_common): {actor_info['name_common']}")
                 print(f"  繁体中文名(name_traditional): {actor_info['name_traditional']}")
                 print(f"  别名(aliases): {other_aliases}")
                
            except Exception as e:
                print(f"获取演员名称失败: {e}")
            
            # 获取头像
            try:
                avatar_element = self.driver.find_element(By.CSS_SELECTOR, ".actor-section .photo img")
                avatar_url = avatar_element.get_attribute('src')
                if avatar_url:
                    actor_info['avatar_url'] = avatar_url
                    # 下载头像数据
                    try:
                        response = requests.get(avatar_url, timeout=10)
                        if response.status_code == 200:
                            actor_info['avatar_data'] = response.content
                            print(f"头像下载成功，大小: {len(response.content)} bytes")
                    except Exception as e:
                        print(f"下载头像失败: {e}")
            except Exception as e:
                print(f"获取头像失败: {e}")
            
            print(f"演员信息爬取完成: {actor_info['name']}")
            print(f"  - 繁体中文名: {actor_info['name_traditional']}")
            print(f"  - 常用名: {actor_info['name_common']}")
            print(f"  - 别名: {actor_info['aliases']}")
            print(f"  - 头像URL: {actor_info['avatar_url']}")
            
            return actor_info
            
        except TimeoutException:
            print(f"页面加载超时: {actor_url}")
            return None
        except Exception as e:
            print(f"爬取演员详细信息失败: {e}")
            return None
    
    # def crawl_actor_filmography(self, actor_url, max_pages=None):
    #     """爬取演员参演影片列表"""
    #     if not self.driver:
    #         if not self.setup_driver():
    #             return []
    #     
    #     movies = []
    #     page = 1
    #     
    #     # 构建影片列表页面URL
    #     base_url = actor_url.rstrip('/')
    #     if '?' in base_url:
    #         filmography_url = f"{base_url}&t=d&sort_type=0"
    #     else:
    #         filmography_url = f"{base_url}?t=d&sort_type=0"
    #     
    #     try:
    #         while True:
    #             if max_pages and page > max_pages:
    #                 break
    #             
    #             # 构建当前页面URL
    #             if page == 1:
    #                 current_url = filmography_url
    #             else:
    #                 if '?' in filmography_url:
    #                     current_url = f"{filmography_url}&page={page}"
    #                 else:
    #                     current_url = f"{filmography_url}?page={page}"
    #             
    #             print(f"正在爬取第{page}页: {current_url}")
    #             self.driver.get(current_url)
    #             
    #             # 等待页面加载
    #             wait = WebDriverWait(self.driver, 10)
    #             try:
    #                 wait.until(EC.presence_of_element_located((By.CLASS_NAME, "movie-list")))
    #             except TimeoutException:
    #                 print(f"第{page}页加载超时或无内容")
    #                 break
    #             
    #             # 获取当前页面的影片
    #             page_movies = []
    #             try:
    #                 movie_items = self.driver.find_elements(By.CSS_SELECTOR, ".movie-list .item")
    #                 
    #                 for item in movie_items:
    #                     try:
    #                         movie_info = {
    #                             'title': '',
    #                             'url': '',
    #                             'javdb_code': '',
    #                             'release_date': '',
    #                             'has_magnet': False,
    #                             'magnet_links': ''
    #                         }
    #                         
    #                         # 获取影片标题和链接
    #                         title_link = item.find_element(By.CSS_SELECTOR, "a")
    #                         movie_info['title'] = title_link.get_attribute('title') or title_link.text.strip()
    #                         movie_info['url'] = title_link.get_attribute('href')
    #                         
    #                         # 从URL提取番号
    #                         if movie_info['url']:
    #                             url_parts = movie_info['url'].split('/')
    #                             if len(url_parts) > 0:
    #                                 movie_info['javdb_code'] = url_parts[-1]
    #                         
    #                         # 检查是否有磁链
    #                         try:
    #                             magnet_icon = item.find_element(By.CSS_SELECTOR, ".tags .tag.is-warning")
    #                             if magnet_icon and '磁' in magnet_icon.text:
    #                                 movie_info['has_magnet'] = True
    #                         except NoSuchElementException:
    #                             pass
    #                         
    #                         # 获取发布日期
    #                         try:
    #                             date_element = item.find_element(By.CSS_SELECTOR, ".meta")
    #                             date_text = date_element.text.strip()
    #                             if date_text:
    #                                 movie_info['release_date'] = date_text
    #                         except NoSuchElementException:
    #                             pass
    #                         
    #                         if movie_info['title'] and movie_info['url']:
    #                             page_movies.append(movie_info)
    #                             
    #                     except Exception as e:
    #                         print(f"解析影片信息失败: {e}")
    #                         continue
    #                 
    #                 print(f"第{page}页找到{len(page_movies)}部影片")
    #                 movies.extend(page_movies)
    #                 
    #                 # 检查是否有下一页
    #                 try:
    #                     next_button = self.driver.find_element(By.CSS_SELECTOR, ".pagination-next")
    #                     if next_button.get_attribute('disabled') or 'is-disabled' in next_button.get_attribute('class'):
    #                         print("已到达最后一页")
    #                         break
    #                 except NoSuchElementException:
    #                     print("未找到分页按钮，可能已到达最后一页")
    #                     break
    #                 
    #                 page += 1
    #                 time.sleep(2)  # 避免请求过快
    #                 
    #             except Exception as e:
    #                 print(f"解析第{page}页失败: {e}")
    #                 break
    #                 
    #     except Exception as e:
    #         print(f"爬取演员参演影片失败: {e}")
    #     
    #     print(f"总共爬取到{len(movies)}部影片")
    #     return movies
    
    def update_actor_in_database(self, actor_id, actor_info):
        """更新数据库中的演员信息"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 更新演员基本信息
            cursor.execute("""
                UPDATE actors SET 
                    name_traditional = ?,
                    name_common = ?,
                    aliases = ?,
                    avatar_url = ?,
                    avatar_data = ?,
                    last_crawled_at = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                actor_info.get('name_traditional', ''),
                actor_info.get('name_common', ''),
                actor_info.get('aliases', ''),
                actor_info.get('avatar_url', ''),
                actor_info.get('avatar_data'),
                datetime.now().isoformat(),
                actor_id
            ))
            
            conn.commit()
            print(f"演员信息已更新到数据库，ID: {actor_id}")
            return True
            
        except Exception as e:
            print(f"更新数据库失败: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def save_actor_movies_to_database(self, actor_id, movies):
        """保存演员参演影片到数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 清除该演员的旧影片记录
            cursor.execute("DELETE FROM actor_movies WHERE actor_id = ?", (actor_id,))
            
            # 插入新的影片记录
            for movie in movies:
                cursor.execute("""
                    INSERT OR IGNORE INTO actor_movies (
                        actor_id, movie_title, movie_url, javdb_code, 
                        release_date, has_magnet, magnet_links
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    actor_id,
                    movie['title'],
                    movie['url'],
                    movie['javdb_code'],
                    movie['release_date'],
                    movie['has_magnet'],
                    movie['magnet_links']
                ))
            
            # 更新演员的影片数量
            cursor.execute("""
                UPDATE actors SET movie_count = ? WHERE id = ?
            """, (len(movies), actor_id))
            
            conn.commit()
            print(f"已保存{len(movies)}部影片到数据库")
            return True
            
        except Exception as e:
            print(f"保存影片到数据库失败: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def crawl_actor_complete_info(self, actor_id, actor_url, max_pages=None):
        """爬取演员完整信息（基本信息+参演影片）"""
        print(f"开始爬取演员完整信息，ID: {actor_id}, URL: {actor_url}")
        
        # 爬取基本信息
        actor_info = self.crawl_actor_detail(actor_url)
        if actor_info:
            self.update_actor_in_database(actor_id, actor_info)
        
        # 爬取参演影片
        movies = self.crawl_actor_filmography(actor_url, max_pages)
        if movies:
            self.save_actor_movies_to_database(actor_id, movies)
        
        return actor_info, movies

# def test_proxy_connection():
#     """测试代理连接"""
#     crawler = ActorDetailCrawler()
#     
#     try:
#         if not crawler.setup_driver():
#             print("驱动初始化失败")
#             return False
#             
#         print("测试代理连接，访问 www.google.com...")
#         crawler.driver.get("https://www.google.com")
#         
#         # 等待页面加载
#         wait = WebDriverWait(crawler.driver, 10)
#         wait.until(lambda driver: driver.execute_script("return document.readyState") == "complete")
#         
#         title = crawler.driver.title
#         current_url = crawler.driver.current_url
#         
#         print(f"成功访问Google!")
#         print(f"页面标题: {title}")
#         print(f"当前URL: {current_url}")
#         
#         return True
#         
#     except Exception as e:
#         print(f"代理连接测试失败: {e}")
#         return False
#     finally:
#         crawler.close_driver()

def test_crawler():
    """测试爬虫功能"""
    # # 首先测试代理连接
    # if not test_proxy_connection():
    #     print("代理连接失败，无法继续测试爬虫功能")
    #     return
    
    print("\n" + "="*50)
    print("开始测试演员爬虫功能")
    print("="*50)
    
    crawler = ActorDetailCrawler()
    
    # 测试演员：宝生リリー
    test_url = "https://javdb.com/actors/Q0YG"
    
    try:
        # 爬取基本信息
        actor_info = crawler.crawl_actor_detail(test_url)
        if actor_info:
            print("\n=== 演员基本信息 ===")
            for key, value in actor_info.items():
                if key != 'avatar_data':
                    print(f"{key}: {value}")
                else:
                    print(f"{key}: {len(value) if value else 0} bytes")
        else:
            print("未能获取演员基本信息")
        
        # # 爬取参演影片（限制前2页）
        # movies = crawler.crawl_actor_filmography(test_url, max_pages=2)
        # if movies:
        #     print(f"\n=== 参演影片 (前{len(movies)}部) ===")
        #     for i, movie in enumerate(movies[:5], 1):
        #         print(f"{i}. {movie['title']} ({movie['javdb_code']})")
        #         print(f"   URL: {movie['url']}")
        #         print(f"   有磁链: {movie['has_magnet']}")
        #         print(f"   发布日期: {movie['release_date']}")
        #         print()
    
    finally:
        crawler.close_driver()

if __name__ == "__main__":
    test_crawler()