#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复缺失的演员头像数据
从avatar_url重新下载头像并存储到avatar_data字段
"""

import sqlite3
import requests
import time
import re
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

class AvatarFixer:
    def __init__(self, db_path='media_library.db'):
        self.db_path = db_path
        self.proxy_host = '127.0.0.1'
        self.proxy_port = 7890
        self.driver = None
        
    def setup_driver(self):
        """设置Chrome浏览器驱动"""
        if self.driver is None:
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument(f'--proxy-server=socks5://{self.proxy_host}:{self.proxy_port}')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.set_page_load_timeout(30)
            
    def close_driver(self):
        """关闭浏览器驱动"""
        if self.driver:
            self.driver.quit()
            self.driver = None
        
    def get_actors_without_avatar_data(self):
        """获取没有avatar_data的演员"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, avatar_url, profile_url 
            FROM actors 
            WHERE avatar_data IS NULL
        """)
        
        actors = cursor.fetchall()
        conn.close()
        
        return actors
    
    def download_avatar(self, avatar_url):
        """下载头像数据"""
        try:
            # 配置代理设置
            proxies = {
                'http': f'socks5://{self.proxy_host}:{self.proxy_port}',
                'https': f'socks5://{self.proxy_host}:{self.proxy_port}'
            }
            
            # 设置请求头
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://javdb.com/'
            }
            
            response = requests.get(avatar_url, proxies=proxies, headers=headers, timeout=15)
            if response.status_code == 200:
                return response.content
            else:
                print(f"下载失败，状态码: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"下载头像失败: {e}")
            return None
    
    def update_avatar_data(self, actor_id, avatar_data):
        """更新演员的头像数据"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE actors 
                SET avatar_data = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (avatar_data, actor_id))
            
            conn.commit()
            return True
            
        except Exception as e:
            print(f"更新数据库失败: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def fix_missing_avatars(self):
        """修复缺失的头像数据"""
        actors = self.get_actors_without_avatar_data()
        
        if not actors:
            print("没有需要修复的演员头像")
            return
        
        print(f"找到 {len(actors)} 个演员需要重新下载头像")
        
        success_count = 0
        failed_count = 0
        
        for actor_id, name, avatar_url in actors:
            print(f"\n处理演员: {name} (ID: {actor_id})")
            print(f"头像URL: {avatar_url}")
            
            # 下载头像
            avatar_data = self.download_avatar(avatar_url)
            
            if avatar_data:
                # 更新数据库
                if self.update_avatar_data(actor_id, avatar_data):
                    print(f"✓ 头像下载成功，大小: {len(avatar_data)} bytes")
                    success_count += 1
                else:
                    print(f"✗ 头像下载成功但数据库更新失败")
                    failed_count += 1
            else:
                print(f"✗ 头像下载失败")
                failed_count += 1
            
            # 添加延迟避免请求过快
            time.sleep(1)
        
        print(f"\n=== 修复完成 ===")
        print(f"成功: {success_count} 个")
        print(f"失败: {failed_count} 个")
        print(f"总计: {len(actors)} 个")

def main():
    print("开始修复缺失的演员头像数据...")
    
    fixer = AvatarFixer()
    fixer.fix_missing_avatars()
    
    print("\n修复完成！")

if __name__ == "__main__":
    main()