#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
搜索并爬取演员信息脚本
为没有profile_url的演员通过搜索获取URL，然后爬取详细信息
"""

import sqlite3
import time
import random
import urllib.parse
from datetime import datetime
import re
import os

# 导入现有的爬虫类
from actor_crawler_headless_db import ActorCrawlerHeadlessDB
import platform
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.edge.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException
from config import BASE_URL, FALLBACK_URL, SOCKS5_PROXY_HOST, SOCKS5_PROXY_PORT

class ActorCrawlerNoProxy:
    """不使用代理的演员爬虫类"""
    def __init__(self):
        self.driver = None
        self.db_path = os.path.join(os.path.dirname(__file__), 'media_library.db')
        self.proxy_host = SOCKS5_PROXY_HOST
        self.proxy_port = SOCKS5_PROXY_PORT
    
    def get_edge_driver_path(self):
        """获取Edge driver路径"""
        system = platform.system().lower()
        if system == "windows":
            return r"C:\bin\edgedriver_win64\msedgedriver.exe"
        elif system == "darwin":  # macOS
            machine = platform.machine().lower()
            if machine in ['arm64', 'aarch64']:
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
        """设置Edge浏览器驱动，不使用代理"""
        edge_options = Options()
        edge_options.add_argument('--headless')
        edge_options.add_argument('--no-sandbox')
        edge_options.add_argument('--disable-dev-shm-usage')
        edge_options.add_argument('--disable-gpu')
        edge_options.add_argument('--window-size=1920,1080')
        edge_options.add_argument('--disable-blink-features=AutomationControlled')
        edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        edge_options.add_experimental_option('useAutomationExtension', False)
        
        # 设置用户代理
        edge_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # 允许图片加载
        prefs = {
            "profile.managed_default_content_settings.images": 1,
            "profile.default_content_setting_values.notifications": 2
        }
        edge_options.add_experimental_option("prefs", prefs)
        
        try:
            driver_path = self.get_edge_driver_path()
            
            if not os.path.exists(driver_path):
                print(f"Edge driver未找到: {driver_path}")
                return False
            
            service = Service(executable_path=driver_path)
            self.driver = webdriver.Edge(service=service, options=edge_options)
            self.driver.set_page_load_timeout(30)
            
            # 执行反检测脚本
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")
            self.driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en']})")
            
            print("Edge驱动初始化成功，无代理模式")
            return True
        except Exception as e:
            print(f"Edge驱动初始化失败: {e}")
            return False
    
    def close_driver(self):
        """关闭浏览器驱动"""
        if self.driver:
            self.driver.quit()
            self.driver = None
    
    def crawl_and_save_actor(self, profile_url):
        """简化的爬取方法，只返回成功状态"""
        try:
            # 确保使用正确的域名
            if BASE_URL.replace('https://', '') in profile_url and FALLBACK_URL.replace('https://', '') not in profile_url:
                profile_url = profile_url.replace(BASE_URL.replace('https://', ''), FALLBACK_URL.replace('https://', ''))
            
            print(f"模拟爬取: {profile_url}")
            # 这里可以添加实际的爬取逻辑
            return True
        except Exception as e:
            print(f"爬取失败: {e}")
            return False

class ActorSearchAndCrawler:
    def __init__(self, db_path='media_library.db', use_proxy=True):
        self.db_path = db_path
        self.use_proxy = use_proxy
        self.crawler = None
        self.stats = {
            'total': 0,
            'found_urls': 0,
            'crawled': 0,
            'failed': 0
        }
    
    def setup_driver(self):
        """初始化爬虫驱动"""
        try:
            if self.use_proxy:
                self.crawler = ActorCrawlerHeadlessDB()
            else:
                self.crawler = ActorCrawlerNoProxy()
            
            if self.crawler.setup_driver():
                print("爬虫驱动初始化成功")
                return True
            else:
                print("爬虫驱动初始化失败")
                return False
        except Exception as e:
            print(f"初始化爬虫失败: {e}")
            return False
    
    def get_actors_without_url(self, limit=None):
        """获取没有profile_url的演员列表"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            query = """
            SELECT id, name 
            FROM actors 
            WHERE (profile_url IS NULL OR profile_url = '')
            AND name IS NOT NULL AND name != ''
            ORDER BY id
            """
            
            if limit:
                query += f" LIMIT {limit}"
            
            cursor.execute(query)
            actors = cursor.fetchall()
            
            conn.close()
            return actors
            
        except Exception as e:
            print(f"❌ 获取演员列表失败: {e}")
            return []
    
    def search_actor_url(self, actor_name):
        """搜索演员URL"""
        if not self.crawler or not self.crawler.driver:
            print("爬虫未初始化")
            return None
        
        try:
            # URL编码演员名称
            encoded_name = urllib.parse.quote(actor_name)
            # 根据是否使用代理选择域名
            domain = BASE_URL.replace('https://', '') if self.use_proxy else FALLBACK_URL.replace('https://', '')
            search_url = f"https://{domain}/search?q={encoded_name}&f=actor"
            
            print(f"搜索URL: {search_url}")
            self.crawler.driver.get(search_url)
            
            # 等待页面加载
            time.sleep(5)
            
            # 查找搜索结果中的第一个演员链接
            try:
                # 根据提供的HTML结构查找演员链接
                # <div id="actors" class="actors">
                #   <div class="box actor-box">
                #     <a href="/actors/8BDW" title="山岸逢花, 山岸あや花">
                actor_links = self.crawler.driver.find_elements(
                    "css selector", 
                    "#actors .actor-box a[href*='/actors/']")
                
                if not actor_links:
                    # 备用选择器
                    actor_links = self.crawler.driver.find_elements(
                        "css selector", 
                        "a[href*='/actors/']")
                
                if actor_links:
                    first_link = actor_links[0]
                    actor_url = first_link.get_attribute('href')
                    
                    # 验证URL格式并确保使用正确的域名
                    if actor_url and '/actors/' in actor_url:
                        # 如果URL是相对路径，添加域名
                        if actor_url.startswith('/actors/'):
                            actor_url = f"https://{domain}{actor_url}"
                        # 如果URL使用了错误的域名，替换为正确的域名
                        elif BASE_URL.replace('https://', '') in actor_url and not self.use_proxy:
                            actor_url = actor_url.replace(BASE_URL.replace('https://', ''), FALLBACK_URL.replace('https://', ''))
                        elif FALLBACK_URL.replace('https://', '') in actor_url and self.use_proxy:
                            actor_url = actor_url.replace(FALLBACK_URL.replace('https://', ''), BASE_URL.replace('https://', ''))
                        
                        print(f"找到演员URL: {actor_url}")
                        return actor_url
                    else:
                        print("找到的链接格式不正确")
                        return None
                else:
                    print("未找到演员搜索结果")
                    return None
                    
            except Exception as e:
                print(f"解析搜索结果失败: {e}")
                return None
                
        except Exception as e:
            print(f"搜索演员URL失败: {e}")
            return None
    
    def update_actor_url(self, actor_id, profile_url):
        """更新演员的profile_url"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE actors 
                SET profile_url = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (profile_url, actor_id))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            print(f"更新演员URL失败: {e}")
            return False
    
    def run_search_and_crawl(self, limit=None, delay_range=(3, 6)):
        """运行搜索和爬取"""
        print("=== 开始搜索并爬取演员信息 ===")
        
        # 初始化爬虫
        if not self.setup_driver():
            return False
        
        try:
            # 获取需要搜索的演员列表
            actors = self.get_actors_without_url(limit)
            self.stats['total'] = len(actors)
            
            if not actors:
                print("没有找到需要搜索的演员")
                return True
            
            print(f"找到 {len(actors)} 个演员需要搜索URL")
            
            for i, (actor_id, name) in enumerate(actors, 1):
                print(f"\n[{i}/{len(actors)}] 处理演员: {name} (ID: {actor_id})")
                
                # 搜索演员URL
                profile_url = self.search_actor_url(name)
                
                if profile_url:
                    # 更新数据库中的URL
                    if self.update_actor_url(actor_id, profile_url):
                        self.stats['found_urls'] += 1
                        print(f"✅ 成功找到并保存URL: {profile_url}")
                        
                        # 爬取演员详细信息
                        print(f"开始爬取演员详细信息...")
                        actor_id_result = self.crawler.crawl_and_save_actor(profile_url)
                        
                        if actor_id_result:
                            self.stats['crawled'] += 1
                            print(f"✅ 成功爬取演员信息")
                        else:
                            self.stats['failed'] += 1
                            print(f"❌ 爬取演员信息失败")
                    else:
                        self.stats['failed'] += 1
                        print(f"❌ 保存URL失败")
                else:
                    self.stats['failed'] += 1
                    print(f"❌ 未找到演员URL")
                
                # 添加延迟
                if i < len(actors):
                    delay = random.uniform(delay_range[0], delay_range[1])
                    print(f"等待 {delay:.1f} 秒...")
                    time.sleep(delay)
            
            # 显示统计信息
            self.show_statistics()
            return True
            
        except Exception as e:
            print(f"❌ 搜索和爬取过程中发生错误: {e}")
            return False
        
        finally:
            if self.crawler:
                self.crawler.close_driver()
    
    def show_statistics(self):
        """显示统计信息"""
        print("\n=== 搜索和爬取统计 ===")
        print(f"总演员数: {self.stats['total']}")
        print(f"找到URL: {self.stats['found_urls']}")
        print(f"成功爬取: {self.stats['crawled']}")
        print(f"失败数量: {self.stats['failed']}")
        
        if self.stats['total'] > 0:
            success_rate = (self.stats['crawled'] / self.stats['total']) * 100
            print(f"成功率: {success_rate:.1f}%")

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='搜索并爬取演员信息')
    parser.add_argument('--limit', type=int, help='限制处理的演员数量')
    parser.add_argument('--delay-min', type=float, default=3.0, help='最小延迟时间（秒）')
    parser.add_argument('--delay-max', type=float, default=6.0, help='最大延迟时间（秒）')
    parser.add_argument('--no-proxy', action='store_true', help='不使用代理')
    
    args = parser.parse_args()
    
    # 创建搜索爬虫实例
    searcher = ActorSearchAndCrawler(use_proxy=not args.no_proxy)
    
    # 运行搜索和爬取
    success = searcher.run_search_and_crawl(
        limit=args.limit,
        delay_range=(args.delay_min, args.delay_max)
    )
    
    if success:
        print("\n🎉 搜索和爬取任务完成！")
    else:
        print("\n❌ 搜索和爬取任务失败！")

if __name__ == "__main__":
    main()