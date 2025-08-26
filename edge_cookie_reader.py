#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Edge浏览器Cookie读取器
用于从MS Edge浏览器读取cookie并在Selenium中使用
"""

import os
import sqlite3
import json
import base64
import shutil
from datetime import datetime, timedelta
import platform
from pathlib import Path

def get_edge_user_data_path():
    """
    获取Edge浏览器用户数据目录路径
    """
    system = platform.system().lower()
    
    if system == "windows":
        # Windows路径
        user_data_path = os.path.expanduser(r"~\AppData\Local\Microsoft\Edge\User Data")
    elif system == "darwin":  # macOS
        # macOS路径
        user_data_path = os.path.expanduser("~/Library/Application Support/Microsoft Edge")
    elif system == "linux":
        # Linux路径
        user_data_path = os.path.expanduser("~/.config/microsoft-edge")
    else:
        raise OSError(f"不支持的操作系统: {system}")
    
    return user_data_path

def get_edge_cookies_db_path(profile="Default"):
    """
    获取Edge浏览器Cookies数据库文件路径
    """
    user_data_path = get_edge_user_data_path()
    cookies_db_path = os.path.join(user_data_path, profile, "Network", "Cookies")
    
    # 如果Network目录不存在，尝试旧版本路径
    if not os.path.exists(cookies_db_path):
        cookies_db_path = os.path.join(user_data_path, profile, "Cookies")
    
    return cookies_db_path

def copy_cookies_db(cookies_db_path):
    """
    复制Cookies数据库文件到临时位置（因为Edge可能正在使用该文件）
    """
    temp_cookies_path = cookies_db_path + "_temp"
    try:
        shutil.copy2(cookies_db_path, temp_cookies_path)
        return temp_cookies_path
    except Exception as e:
        print(f"复制Cookies数据库失败: {e}")
        return None

def read_edge_cookies(domain_filter=None, profile="Default"):
    """
    从Edge浏览器读取cookies
    
    Args:
        domain_filter (str): 域名过滤器，如 'javdb.com'
        profile (str): Edge配置文件名，默认为 'Default'
    
    Returns:
        list: cookie字典列表
    """
    cookies_db_path = get_edge_cookies_db_path(profile)
    
    if not os.path.exists(cookies_db_path):
        print(f"Cookies数据库文件不存在: {cookies_db_path}")
        return []
    
    # 复制数据库文件
    temp_db_path = copy_cookies_db(cookies_db_path)
    if not temp_db_path:
        return []
    
    cookies = []
    
    try:
        # 连接到SQLite数据库
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        
        # 构建查询语句
        if domain_filter:
            query = """
            SELECT host_key, name, value, path, expires_utc, is_secure, is_httponly, samesite
            FROM cookies 
            WHERE host_key LIKE ?
            """
            cursor.execute(query, (f"%{domain_filter}%",))
        else:
            query = """
            SELECT host_key, name, value, path, expires_utc, is_secure, is_httponly, samesite
            FROM cookies
            """
            cursor.execute(query)
        
        rows = cursor.fetchall()
        
        for row in rows:
            host_key, name, value, path, expires_utc, is_secure, is_httponly, samesite = row
            
            # 转换过期时间（Chrome/Edge使用微秒时间戳）
            if expires_utc:
                # Chrome时间戳是从1601年1月1日开始的微秒数
                chrome_epoch = datetime(1601, 1, 1)
                expires = chrome_epoch + timedelta(microseconds=expires_utc)
                expires_timestamp = int(expires.timestamp())
            else:
                expires_timestamp = None
            
            cookie = {
                'name': name,
                'value': value,
                'domain': host_key,
                'path': path or '/',
                'secure': bool(is_secure),
                'httpOnly': bool(is_httponly)
            }
            
            # 只有在cookie未过期时才添加过期时间
            if expires_timestamp and expires_timestamp > datetime.now().timestamp():
                cookie['expiry'] = expires_timestamp
            
            cookies.append(cookie)
        
        conn.close()
        
    except Exception as e:
        print(f"读取cookies失败: {e}")
    finally:
        # 清理临时文件
        try:
            os.remove(temp_db_path)
        except:
            pass
    
    return cookies

def load_cookies_to_selenium(driver, domain_filter=None, profile="Default"):
    """
    将Edge浏览器的cookies加载到Selenium WebDriver中
    
    Args:
        driver: Selenium WebDriver实例
        domain_filter (str): 域名过滤器，如 'javdb.com'
        profile (str): Edge配置文件名，默认为 'Default'
    
    Returns:
        int: 成功加载的cookie数量
    """
    cookies = read_edge_cookies(domain_filter, profile)
    
    if not cookies:
        print("未找到任何cookies")
        return 0
    
    loaded_count = 0
    
    for cookie in cookies:
        try:
            # 确保域名匹配当前页面
            current_url = driver.current_url
            if domain_filter and domain_filter not in current_url:
                continue
            
            # 添加cookie到Selenium
            driver.add_cookie(cookie)
            loaded_count += 1
            
        except Exception as e:
            print(f"添加cookie失败 {cookie['name']}: {e}")
    
    print(f"成功加载 {loaded_count} 个cookies")
    return loaded_count

def save_cookies_to_file(cookies, filename):
    """
    将cookies保存到JSON文件
    
    Args:
        cookies (list): cookie列表
        filename (str): 文件名
    """
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(cookies, f, indent=2, ensure_ascii=False)
        print(f"Cookies已保存到: {filename}")
    except Exception as e:
        print(f"保存cookies失败: {e}")

def load_cookies_from_file(filename):
    """
    从JSON文件加载cookies
    
    Args:
        filename (str): 文件名
    
    Returns:
        list: cookie列表
    """
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            cookies = json.load(f)
        print(f"从文件加载了 {len(cookies)} 个cookies")
        return cookies
    except Exception as e:
        print(f"加载cookies文件失败: {e}")
        return []

class EdgeCookieReader:
    """Edge浏览器Cookie读取器类"""
    
    def __init__(self, profile="Default"):
        self.profile = profile
    
    def get_cookies_for_domain(self, domain):
        """获取指定域名的cookies"""
        return read_edge_cookies(domain, self.profile)
    
    def load_cookies_to_driver(self, driver, domain=None):
        """将cookies加载到Selenium WebDriver"""
        return load_cookies_to_selenium(driver, domain, self.profile)
    
    def save_cookies(self, cookies, filename):
        """保存cookies到文件"""
        return save_cookies_to_file(cookies, filename)
    
    def load_cookies(self, filename):
        """从文件加载cookies"""
        return load_cookies_from_file(filename)

if __name__ == "__main__":
    # 测试代码
    print("Edge浏览器Cookie读取器测试")
    print(f"Edge用户数据路径: {get_edge_user_data_path()}")
    print(f"Cookies数据库路径: {get_edge_cookies_db_path()}")
    
    # 读取JAVDB相关的cookies
    javdb_cookies = read_edge_cookies("javdb.com")
    print(f"找到 {len(javdb_cookies)} 个JAVDB相关的cookies")
    
    if javdb_cookies:
        # 保存cookies到文件
        save_cookies_to_file(javdb_cookies, "javdb_cookies.json")
        print("Cookies已保存到 javdb_cookies.json")
        
        for cookie in javdb_cookies:
            print(f"Cookie: {cookie['name']} = {cookie['value'][:50]}...")