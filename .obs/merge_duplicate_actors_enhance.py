#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import sys
import sqlite3
import argparse
import time
import random
from urllib.parse import urljoin, urlparse, parse_qsl, urlencode, urlunparse

import socks
import socket
import platform

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.edge.options import Options
from selenium.common.exceptions import TimeoutException

from config import SOCKS5_PROXY_HOST, SOCKS5_PROXY_PORT, BASE_URL, MIN_DELAY, MAX_DELAY, LOGIN_EMAIL, LOGIN_PASSWORD


class EnhancedActorProcessor:
    def __init__(self, db_path):
        self.db_path = db_path
        self.driver = None
        
    def setup_driver(self, prefer_headless=False):
        """Setup MS Edge browser driver with SOCKS5 proxy and fallbacks.
        prefer_headless: True to try headless first, False to try UI first.
        """
        # 统一挂载专用 Edge 用户数据目录
        def get_dedicated_edge_user_data_dir():
            try:
                base = os.path.dirname(os.path.abspath(__file__))
                d = os.path.join(base, '.edge_driver_user_data')
                os.makedirs(d, exist_ok=True)
                return d
            except Exception:
                try:
                    d = os.path.join(os.getcwd(), '.edge_driver_user_data')
                    os.makedirs(d, exist_ok=True)
                    return d
                except Exception:
                    return None

        def detect_default_edge_profile_directory(user_data_dir):
            try:
                if not user_data_dir:
                    return None
                d = os.path.join(user_data_dir, 'Default')
                return 'Default' if os.path.isdir(d) else None
            except Exception:
                return None

        user_data_dir = get_dedicated_edge_user_data_dir()
        profile_directory = detect_default_edge_profile_directory(user_data_dir)

        def build_options(headless=True, use_proxy=True):
            opts = Options()
            opts.page_load_strategy = 'eager'
            opts.add_argument('--no-sandbox')
            opts.add_argument('--disable-dev-shm-usage')
            opts.add_argument('--disable-blink-features=AutomationControlled')
            opts.add_experimental_option("excludeSwitches", ["enable-automation"])
            opts.add_experimental_option('useAutomationExtension', False)
            opts.add_argument('--remote-allow-origins=*')
            opts.add_argument('--disable-gpu')
            opts.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
            # 挂载用户数据目录与默认配置档，复用登录态
            if user_data_dir:
                opts.add_argument(f"--user-data-dir={user_data_dir}")
            if profile_directory:
                opts.add_argument(f"--profile-directory={profile_directory}")
            if use_proxy:
                opts.add_argument(f'--proxy-server=socks5://{SOCKS5_PROXY_HOST}:{SOCKS5_PROXY_PORT}')
                opts.add_argument('--proxy-bypass-list=<-loopback>')
            if headless:
                opts.add_argument('--headless')
            else:
                opts.add_argument('--start-maximized')
            return opts

        system = platform.system().lower()
        if system == "windows":
            default_driver_path = r"C:\\bin\\edgedriver_win64\\msedgedriver.exe"
        elif system == "darwin":
            machine = platform.machine().lower()
            default_driver_path = "/usr/local/bin/edgedriver_mac64_m1/msedgedriver" if machine in ['arm64', 'aarch64'] else "/usr/local/bin/edgedriver_mac64/msedgedriver"
        elif system == "linux":
            default_driver_path = "/usr/local/bin/edgedriver_linux64/msedgedriver"
        else:
            default_driver_path = "/usr/local/bin/edgedriver_mac64/msedgedriver"

        user_driver_path = os.path.expanduser("~/bin/edgedriver_mac64_m1/msedgedriver")
        driver_path = user_driver_path if os.path.exists(user_driver_path) else default_driver_path

        if prefer_headless:
            attempts = [
                {"headless": True,  "proxy": True,  "use_service": True,  "label": "headless+proxy+service"},
                {"headless": False, "proxy": True,  "use_service": True,  "label": "ui+proxy+service"},
                {"headless": False, "proxy": False, "use_service": True,  "label": "ui+no-proxy+service"},
                {"headless": False, "proxy": False, "use_service": False, "label": "ui+no-proxy+PATH"},
            ]
        else:
            attempts = [
                {"headless": False, "proxy": True,  "use_service": True,  "label": "ui+proxy+service"},
                {"headless": True,  "proxy": True,  "use_service": True,  "label": "headless+proxy+service"},
                {"headless": False, "proxy": False, "use_service": True,  "label": "ui+no-proxy+service"},
                {"headless": False, "proxy": False, "use_service": False, "label": "ui+no-proxy+PATH"},
            ]

        last_error = None
        for att in attempts:
            try:
                print(f"尝试启动Edge驱动（{att['label']}），路径: {driver_path}")
                opts = build_options(headless=att["headless"], use_proxy=att["proxy"])
                if att["use_service"] and os.path.exists(driver_path):
                    service = webdriver.edge.service.Service(driver_path)
                    driver = webdriver.Edge(service=service, options=opts)
                else:
                    driver = webdriver.Edge(options=opts)
                driver.set_page_load_timeout(60)
                driver.set_script_timeout(30)
                try:
                    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                except Exception:
                    pass
                print("Edge驱动启动成功")
                return driver
            except Exception as e:
                last_error = e
                print(f"启动失败（{att['label']}）: {e}")
                time.sleep(1)

        print(f"MS Edge driver startup failed: {last_error}")
        print("Please make sure MS Edge browser and EdgeDriver are installed")
        print("You can run update_msedge_driver.py to install the driver")
        return None

    def random_delay(self, min_seconds=MIN_DELAY, max_seconds=MAX_DELAY):
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)

    def is_login_page(self, driver):
        try:
            url = (driver.current_url or '').lower()
            if 'login' in url or '/sign_in' in url:
                return True
            if driver.find_elements(By.CSS_SELECTOR, 'input[type="email"], input[name="email"]'):
                return True
            if driver.find_elements(By.CSS_SELECTOR, 'input[type="password"], input[name="password"]'):
                return True
            if driver.find_elements(By.CSS_SELECTOR, '[data-sitekey], .captcha, iframe[src*="captcha"]'):
                return True
            if driver.find_elements(By.XPATH, "//*[contains(text(),'登录') or contains(text(),'Sign in') or contains(text(),'ログイン')]"):
                return True
        except Exception:
            pass
        return False

    def wait_for_manual_login(self, driver, seconds=300, reopen_url=None):
        # 支持按回车立即继续；否则最长等待seconds秒
        import sys
        import select
        print(f"检测到登录页，已切换到有头模式；请手工登录。按回车立即继续，或最多等待 {int(seconds)} 秒…")
        try:
            rlist, _, _ = select.select([sys.stdin], [], [], seconds)
            if rlist:
                _ = sys.stdin.readline()
                print("检测到回车，继续执行…")
            else:
                print("等待超时，继续执行…")
        except Exception:
            # 兜底：无法非阻塞监听时，直接睡眠
            time.sleep(seconds)
        if reopen_url:
            try:
                print(f"登录处理完成，重新打开页面：{reopen_url}")
                driver.get(reopen_url)
                self.random_delay(2, 4)
            except Exception:
                pass

    def search_actor_on_javdb(self, actor_name):
        """在JavDB上搜索演员并返回第一个结果的URL"""
        
        if not self.driver:
            print("启动浏览器驱动...")
            self.driver = self.setup_driver(prefer_headless=False)
            if not self.driver:
                print("无法启动浏览器驱动，跳过搜索")
                return None
        
        # 构建搜索URL
        search_url = f"{BASE_URL}/search?q={actor_name}&f=actor"
        print(f"搜索演员: {actor_name}, URL: {search_url}")
        
        try:
            self.driver.get(search_url)
            self.random_delay(2, 4)
            
            # 检查是否需要登录
            if self.is_login_page(self.driver):
                self.wait_for_manual_login(self.driver, seconds=300, reopen_url=search_url)
            
            # 等待搜索结果加载
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.container, #content, body'))
            )
            
            # 查找第一个演员结果
            first_result = None
            try:
                # 尝试不同的选择器来找到第一个演员结果
                selectors = [
                    '.grid .item a[href*="/actors/"]',
                    '.actors-grid .item a[href*="/actors/"]',
                    'a[href*="/actors/"]'
                ]
                
                for selector in selectors:
                    results = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if results and len(results) > 0:
                        first_result = results[0]
                        break
            except Exception as e:
                print(f"查找结果时出错: {e}")
                
            if first_result:
                actor_url = first_result.get_attribute('href')
                actor_display_name = first_result.text.strip()
                print(f"找到演员: {actor_display_name}, URL: {actor_url}")
                return actor_url
            else:
                print(f"未找到演员: {actor_name}")
                return None
                
        except Exception as e:
            print(f"搜索过程出错: {e}")
            return None

    def get_actor_details_from_javdb(self, actor_url):
        """从JavDB获取演员详细信息"""
        
        if not self.driver:
            print("浏览器驱动未初始化")
            return None
        
        try:
            self.driver.get(actor_url)
            self.random_delay(2, 4)
            
            # 检查是否需要登录
            if self.is_login_page(self.driver):
                self.wait_for_manual_login(self.driver, seconds=300, reopen_url=actor_url)
            
            # 等待页面加载
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.container, #content, body'))
            )
            
            # 提取演员信息
            actor_info = {}
            
            # 提取名称
            try:
                name_element = self.driver.find_element(By.CSS_SELECTOR, '.actor-info .title, .actor-box .title, h1.title, h2.title')
                actor_info['name'] = name_element.text.strip()
            except Exception:
                print("无法提取演员名称")
                
            # 提取其他信息如生日、身高、三围等
            try:
                info_items = self.driver.find_elements(By.CSS_SELECTOR, '.info-item')
                for item in info_items:
                    try:
                        label = item.find_element(By.CSS_SELECTOR, '.label').text.strip().lower()
                        value = item.find_element(By.CSS_SELECTOR, '.value').text.strip()
                        if label == '生日':
                            actor_info['birth_date'] = value
                        elif label == '身高':
                            actor_info['height'] = value
                        elif label == '三围':
                            actor_info['measurements'] = value
                        # 可以根据需要添加更多字段
                    except Exception:
                        continue
            except Exception:
                print("无法提取演员详细信息")
                
            # 提取头像URL
            try:
                avatar_element = self.driver.find_element(By.CSS_SELECTOR, '.actor-avatar img, .avatar img')
                avatar_url = avatar_element.get_attribute('src')
                if avatar_url and not avatar_url.startswith('http'):
                    avatar_url = urljoin(BASE_URL, avatar_url)
                actor_info['avatar_url'] = avatar_url
            except Exception:
                print("无法提取头像URL")
                
            # 添加profile_url
            actor_info['profile_url'] = actor_url
            
            print(f"成功提取演员信息: {actor_info.get('name', '未知')}")
            return actor_info
            
        except Exception as e:
            print(f"获取演员信息时出错: {e}")
            return None

    def get_all_actor_names_from_database(self):
        """从数据库中获取所有演员名称"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT id, name, name_common, name_traditional, aliases FROM actors")
            actors = cursor.fetchall()
            
            all_names = set()
            name_to_id = {}
            
            for actor in actors:
                actor_id, name, name_common, name_traditional, aliases = actor
                
                # 添加各种名称形式到集合中
                if name and name.strip():
                    all_names.add(name.strip())
                    name_to_id[name.strip()] = actor_id
                if name_common and name_common.strip():
                    all_names.add(name_common.strip())
                    name_to_id[name_common.strip()] = actor_id
                if name_traditional and name_traditional.strip():
                    all_names.add(name_traditional.strip())
                    name_to_id[name_traditional.strip()] = actor_id
                if aliases and aliases.strip():
                    # 处理别名列表
                    alias_list = [a.strip() for a in aliases.split(',') if a.strip()]
                    for alias in alias_list:
                        all_names.add(alias)
                        name_to_id[alias] = actor_id
            
            return all_names, name_to_id
            
        except Exception as e:
            print(f"获取演员名称时出错: {e}")
            return set(), {}
        finally:
            conn.close()

    def find_existing_actor_by_name(self, name):
        """查找是否已存在同名演员（在name、name_common、name_traditional或aliases中）"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT id, name, name_common, name_traditional, aliases, profile_url
                FROM actors 
                WHERE name = ? OR name_common = ? OR name_traditional = ? 
                   OR aliases LIKE ? OR aliases LIKE ? OR aliases LIKE ?
                LIMIT 1
            """, (name, name, name, f"%{name}%", f"{name},%", f"%, {name}%"))
            
            result = cursor.fetchone()
            return result
            
        except Exception as e:
            print(f"查找现有演员失败: {e}")
            return None
        finally:
            conn.close()

    def add_actor_to_database(self, actor_info):
        """将演员信息添加到数据库"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 检查是否已存在相同profile_url的演员
            if actor_info.get('profile_url'):
                cursor.execute("SELECT id FROM actors WHERE profile_url = ?", (actor_info['profile_url'],))
                existing = cursor.fetchone()
                if existing:
                    print(f"演员已存在于数据库中，ID: {existing[0]}")
                    return existing[0]
            
            # 插入新演员记录
            cursor.execute("""
                INSERT INTO actors (
                    name, name_common, name_traditional, aliases,
                    avatar_url, avatar_data, profile_url, birth_date, height, measurements,
                    created_at, updated_at, last_crawled_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (
                actor_info.get('name', ''),
                actor_info.get('name', ''),  # 默认为相同名称
                actor_info.get('name', ''),  # 默认为相同名称
                actor_info.get('aliases', ''),
                actor_info.get('avatar_url'),
                None,  # avatar_data
                actor_info.get('profile_url'),
                actor_info.get('birth_date'),
                actor_info.get('height'),
                actor_info.get('measurements')
            ))
            
            new_actor_id = cursor.lastrowid
            conn.commit()
            print(f"成功添加演员到数据库，ID: {new_actor_id}")
            return new_actor_id
            
        except Exception as e:
            print(f"添加演员到数据库失败: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()

    def process_actor_name(self, actor_name, dry_run=True):
        """处理单个演员名称，检查数据库、搜索JavDB并添加到数据库"""
        
        if not actor_name or not actor_name.strip():
            return None
            
        actor_name = actor_name.strip()
        print(f"\n处理演员名称: {actor_name}")
        
        # 检查数据库中是否已存在该演员
        existing_actor = self.find_existing_actor_by_name(actor_name)
        
        if existing_actor:
            actor_id, name, name_common, name_traditional, aliases, profile_url = existing_actor
            print(f"演员已存在于数据库中，ID: {actor_id}")
            
            # 如果没有profile_url，尝试搜索JavDB更新信息
            if not profile_url or not profile_url.strip():
                print(f"演员缺少profile_url，尝试搜索更新")
                if not dry_run:
                    actor_url = self.search_actor_on_javdb(actor_name)
                    if actor_url:
                        actor_info = self.get_actor_details_from_javdb(actor_url)
                        if actor_info:
                            # 更新现有演员记录
                            self.update_actor_in_database(actor_id, actor_info)
            
            return actor_id
        else:
            print(f"演员不存在于数据库中")
            
            if dry_run:
                print("[DRY RUN] 不执行实际搜索和添加操作")
                return None
            
            # 搜索JavDB
            actor_url = self.search_actor_on_javdb(actor_name)
            if not actor_url:
                print(f"无法在JavDB上找到演员: {actor_name}")
                # 创建一个没有profile_url的记录
                basic_info = {'name': actor_name}
                return self.add_actor_to_database(basic_info)
            
            # 获取详细信息
            actor_info = self.get_actor_details_from_javdb(actor_url)
            if not actor_info:
                print(f"无法获取演员详细信息: {actor_name}")
                # 创建一个只有URL的记录
                basic_info = {'name': actor_name, 'profile_url': actor_url}
                return self.add_actor_to_database(basic_info)
            
            # 添加到数据库
            return self.add_actor_to_database(actor_info)

    def update_actor_in_database(self, actor_id, actor_info):
        """更新数据库中的演员信息"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 构建更新字段
            update_fields = []
            update_params = []
            
            if actor_info.get('name'):
                update_fields.append("name = ?")
                update_params.append(actor_info['name'])
            if actor_info.get('name_common'):
                update_fields.append("name_common = ?")
                update_params.append(actor_info['name_common'])
            if actor_info.get('name_traditional'):
                update_fields.append("name_traditional = ?")
                update_params.append(actor_info['name_traditional'])
            if actor_info.get('aliases'):
                update_fields.append("aliases = ?")
                update_params.append(actor_info['aliases'])
            if actor_info.get('avatar_url'):
                update_fields.append("avatar_url = ?")
                update_params.append(actor_info['avatar_url'])
            if actor_info.get('profile_url'):
                update_fields.append("profile_url = ?")
                update_params.append(actor_info['profile_url'])
            if actor_info.get('birth_date'):
                update_fields.append("birth_date = ?")
                update_params.append(actor_info['birth_date'])
            if actor_info.get('height'):
                update_fields.append("height = ?")
                update_params.append(actor_info['height'])
            if actor_info.get('measurements'):
                update_fields.append("measurements = ?")
                update_params.append(actor_info['measurements'])
            
            # 添加更新时间
            update_fields.append("updated_at = CURRENT_TIMESTAMP")
            update_fields.append("last_crawled_at = CURRENT_TIMESTAMP")
            
            # 添加ID参数
            update_params.append(actor_id)
            
            # 执行更新
            if update_fields:
                query = f"UPDATE actors SET {', '.join(update_fields)} WHERE id = ?"
                cursor.execute(query, update_params)
                conn.commit()
                print(f"成功更新演员信息，ID: {actor_id}")
            
        except Exception as e:
            print(f"更新演员信息失败: {e}")
            conn.rollback()
        finally:
            conn.close()

    def extract_actor_names_from_text(self, text):
        """从文本中提取可能的演员名称（处理逗号分隔的情况）"""
        
        if not text or not text.strip():
            return []
            
        # 按逗号分割并去重
        names = [name.strip() for name in text.split(',') if name.strip()]
        return list(dict.fromkeys(names))  # 去重并保持顺序

    def process_actor_text(self, actor_text, dry_run=True):
        """处理可能包含多个演员的文本，提取并处理每个演员名称"""
        
        if not actor_text or not actor_text.strip():
            return []
            
        # 提取演员名称
        actor_names = self.extract_actor_names_from_text(actor_text)
        print(f"从文本中提取演员名称: {actor_names}")
        
        # 处理每个演员名称
        processed_actors = []
        for name in actor_names:
            actor_id = self.process_actor_name(name, dry_run=dry_run)
            if actor_id:
                processed_actors.append((actor_id, name))
            
        return processed_actors

    def show_statistics(self):
        """显示数据库统计信息"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_actors,
                    COUNT(DISTINCT profile_url) as unique_urls,
                    COUNT(CASE WHEN profile_url IS NOT NULL AND profile_url != '' THEN 1 END) as has_url
                FROM actors
            """)
            
            stats = cursor.fetchone()
            print(f"\n=== 数据库统计 ===")
            print(f"总演员数: {stats[0]}")
            print(f"唯一URL数: {stats[1]}")
            print(f"有URL的演员: {stats[2]}")
            
        except Exception as e:
            print(f"获取统计信息失败: {e}")
        finally:
            conn.close()

    def close_driver(self):
        """关闭浏览器驱动"""
        
        if self.driver:
            try:
                self.driver.quit()
                print("浏览器驱动已关闭")
            except Exception:
                pass
            finally:
                self.driver = None


def main():
    parser = argparse.ArgumentParser(description='增强版演员记录处理器 - 去重、匹配和从JavDB获取演员信息')
    parser.add_argument('--dry-run', action='store_true', default=True,
                       help='只显示将要执行的操作，不实际修改数据库（默认）')
    parser.add_argument('--execute', action='store_true',
                       help='实际执行操作')
    parser.add_argument('--db-path', default='media_library.db',
                       help='数据库文件路径')
    parser.add_argument('--actor', type=str,
                       help='处理单个演员名称')
    parser.add_argument('--process-existing', action='store_true',
                       help='处理数据库中所有缺少profile_url的演员')
    
    args = parser.parse_args()
    
    # 如果指定了--execute，则不是dry run
    dry_run = not args.execute
    
    if not os.path.exists(args.db_path):
        print(f"错误：找不到数据库文件 {args.db_path}")
        return
    
    processor = EnhancedActorProcessor(args.db_path)
    
    print(f"增强版演员记录处理器")
    print(f"数据库: {args.db_path}")
    print(f"模式: {'预览模式' if dry_run else '执行模式'}")
    
    if dry_run:
        print("\n注意：当前为预览模式，不会修改数据库")
        print("使用 --execute 参数来实际执行操作")
    
    # 显示当前统计
    processor.show_statistics()
    
    try:
        if args.actor:
            # 处理单个演员名称
            print(f"\n=== 处理单个演员: {args.actor} ===")
            processor.process_actor_name(args.actor, dry_run=dry_run)
        elif args.process_existing:
            # 处理数据库中所有缺少profile_url的演员
            print("\n=== 处理数据库中所有缺少profile_url的演员 ===")
            conn = sqlite3.connect(args.db_path)
            cursor = conn.cursor()
            
            try:
                cursor.execute("SELECT id, name FROM actors WHERE profile_url IS NULL OR profile_url = ''")
                actors_without_url = cursor.fetchall()
                print(f"找到 {len(actors_without_url)} 个缺少profile_url的演员")
                
                for i, (actor_id, actor_name) in enumerate(actors_without_url, 1):
                    print(f"\n处理第 {i}/{len(actors_without_url)} 个演员: {actor_name} (ID: {actor_id})")
                    if not dry_run:
                        # 搜索JavDB
                        actor_url = processor.search_actor_on_javdb(actor_name)
                        if actor_url:
                            actor_info = processor.get_actor_details_from_javdb(actor_url)
                            if actor_info:
                                processor.update_actor_in_database(actor_id, actor_info)
            except Exception as e:
                print(f"处理现有演员时出错: {e}")
            finally:
                conn.close()
        else:
            # 默认交互模式
            print("\n=== 交互模式 ===")
            print("输入演员名称（多个名称用逗号分隔，输入'exit'退出）：")
            
            while True:
                try:
                    user_input = input("演员名称: ").strip()
                    if user_input.lower() == 'exit':
                        break
                    
                    processor.process_actor_text(user_input, dry_run=dry_run)
                except KeyboardInterrupt:
                    break
        
        # 显示更新后的统计
        if not dry_run:
            processor.show_statistics()
            
    finally:
        # 确保关闭浏览器驱动
        processor.close_driver()


if __name__ == '__main__':
    main()