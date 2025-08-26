#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
演员详细信息爬虫 - 数据库版本
使用Selenium + SOCKS5代理爬取JAVDB演员页面的详细信息并保存到数据库
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

class ActorCrawlerWithDB:
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
            if "JavDB" in page_title:
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
                'avatar_data': None,
                'javdb_url': actor_url
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
    
    def save_actor_to_database(self, actor_info):
        """将演员信息保存到数据库"""
        if not actor_info:
            print("演员信息为空，跳过保存")
            return False
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 检查演员是否已存在
            cursor.execute("""
                SELECT id FROM actors WHERE name = ? OR name_common = ? OR name_traditional = ?
            """, (actor_info['name'], actor_info['name_common'], actor_info['name_traditional']))
            
            existing_actor = cursor.fetchone()
            
            if existing_actor:
                # 更新现有演员信息
                actor_id = existing_actor[0]
                cursor.execute("""
                    UPDATE actors SET 
                        name_traditional = ?,
                        name_common = ?,
                        aliases = ?,
                        avatar_url = ?,
                        avatar_data = ?,
                        javdb_url = ?,
                        last_crawled_at = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (
                    actor_info.get('name_traditional', ''),
                    actor_info.get('name_common', ''),
                    actor_info.get('aliases', ''),
                    actor_info.get('avatar_url', ''),
                    actor_info.get('avatar_data'),
                    actor_info.get('javdb_url', ''),
                    datetime.now().isoformat(),
                    actor_id
                ))
                print(f"更新演员信息: {actor_info['name']} (ID: {actor_id})")
            else:
                # 插入新演员
                cursor.execute("""
                    INSERT INTO actors (
                        name, name_traditional, name_common, aliases, 
                        avatar_url, avatar_data, javdb_url, 
                        last_crawled_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, (
                    actor_info['name'],
                    actor_info.get('name_traditional', ''),
                    actor_info.get('name_common', ''),
                    actor_info.get('aliases', ''),
                    actor_info.get('avatar_url', ''),
                    actor_info.get('avatar_data'),
                    actor_info.get('javdb_url', ''),
                    datetime.now().isoformat()
                ))
                actor_id = cursor.lastrowid
                print(f"新增演员信息: {actor_info['name']} (ID: {actor_id})")
            
            conn.commit()
            return True
            
        except Exception as e:
            print(f"保存演员信息到数据库失败: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def crawl_and_save_actor(self, actor_url):
        """爬取演员信息并保存到数据库"""
        print(f"开始处理演员: {actor_url}")
        
        # 爬取演员信息
        actor_info = self.crawl_actor_detail(actor_url)
        
        if actor_info:
            # 保存到数据库
            success = self.save_actor_to_database(actor_info)
            if success:
                print(f"演员 {actor_info['name']} 信息已成功保存到数据库")
                return True
            else:
                print(f"演员 {actor_info['name']} 信息保存失败")
                return False
        else:
            print("演员信息爬取失败")
            return False
    
    def batch_crawl_actors(self, actor_urls):
        """批量爬取演员信息"""
        if not actor_urls:
            print("演员URL列表为空")
            return
        
        print(f"开始批量爬取 {len(actor_urls)} 个演员的信息")
        
        success_count = 0
        failed_count = 0
        
        for i, actor_url in enumerate(actor_urls, 1):
            print(f"\n进度: {i}/{len(actor_urls)}")
            
            try:
                if self.crawl_and_save_actor(actor_url):
                    success_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                print(f"处理演员 {actor_url} 时发生异常: {e}")
                failed_count += 1
            
            # 添加延迟避免请求过快
            if i < len(actor_urls):
                time.sleep(3)
        
        print(f"\n批量爬取完成:")
        print(f"  成功: {success_count}")
        print(f"  失败: {failed_count}")
        print(f"  总计: {len(actor_urls)}")

def test_single_actor():
    """测试单个演员爬取"""
    crawler = ActorCrawlerWithDB()
    
    try:
        # 测试演员URL
        test_url = "https://javdb.com/actors/Q0YG"
        
        print("开始测试单个演员爬取...")
        success = crawler.crawl_and_save_actor(test_url)
        
        if success:
            print("测试成功！")
        else:
            print("测试失败！")
            
    finally:
        crawler.close_driver()

def test_batch_actors():
    """测试批量演员爬取"""
    crawler = ActorCrawlerWithDB()
    
    try:
        # 测试演员URL列表
        test_urls = [
            "https://javdb.com/actors/2Rqe",  # 宝生リリー
            "https://javdb.com/actors/gqVA",  # 其他演员
        ]
        
        print("开始测试批量演员爬取...")
        crawler.batch_crawl_actors(test_urls)
        
    finally:
        crawler.close_driver()

if __name__ == "__main__":
    # 可以选择测试单个演员或批量演员
    test_single_actor()
    # test_batch_actors()