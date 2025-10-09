#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JAVDB信息更新器 - 合并登录助手和批量信息获取功能
支持列出用户定义的数据文件夹，选择文件夹后批量更新无演员信息的视频
"""

import os
import sys
import time
import platform
import subprocess
import json
import random
import re
import sqlite3
import argparse
from urllib.parse import urlparse, urljoin

# 从配置文件加载代理与域名设置
from config import (
    SOCKS5_PROXY_HOST,
    SOCKS5_PROXY_PORT,
    MIN_DELAY,
    MAX_DELAY,
    LOGIN_EMAIL,
    LOGIN_PASSWORD,
    get_javdb_base_url,
    normalize_javdb_url,
)

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.edge.options import Options
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.action_chains import ActionChains

# 配置信息（BASE_URL/LOGIN_URL 根据是否使用代理动态设置；默认使用代理）
USE_PROXY = True
BASE_URL = get_javdb_base_url(USE_PROXY)
LOGIN_URL = f'{BASE_URL}/login'
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'media_library.db')
# 统一封面缓存目录到 results/images（与其它脚本保持一致）
COVERS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results', 'images')

# ---------- 工具函数 ----------
def random_delay(min_seconds=MIN_DELAY, max_seconds=MAX_DELAY):
    """随机延迟，模拟人类操作间隔"""
    try:
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)
    except Exception:
        time.sleep(min_seconds)


def perform_human_actions(driver, scroll=True, mouse_move=True):
    """执行轻量的人类操作模拟：滚动与鼠标移动，提高反爬通过率"""
    try:
        # 轻量滚动以触发懒加载
        if scroll:
            total_steps = random.randint(3, 6)
            viewport_height = driver.execute_script("return window.innerHeight || 800;") or 800
            for _ in range(total_steps):
                delta = int(viewport_height * random.uniform(0.3, 0.7))
                driver.execute_script("window.scrollBy(0, arguments[0]);", delta)
                random_delay(0.5, 1.5)

        # 鼠标移动：随机小幅度移动到页面不同位置
        if mouse_move:
            try:
                actions = ActionChains(driver)
                actions.move_by_offset(random.randint(5, 25), random.randint(5, 25)).perform()
                random_delay(0.2, 0.6)
                actions.move_by_offset(random.randint(30, 80), random.randint(10, 60)).perform()
                random_delay(0.2, 0.6)
            except Exception:
                pass
    except Exception:
        pass


def get_dedicated_edge_user_data_dir():
    """
    返回并创建一个专用于 EdgeDriver 的用户数据目录，以持久化登录态。
    该目录与系统 Edge 的用户数据隔离，可在 Edge 运行中使用而不冲突。
    """
    try:
        base = os.path.dirname(os.path.abspath(__file__))
        d = os.path.join(base, '.edge_driver_user_data')
        os.makedirs(d, exist_ok=True)
        return d
    except Exception:
        # 回退到当前工作目录
        try:
            d = os.path.join(os.getcwd(), '.edge_driver_user_data')
            os.makedirs(d, exist_ok=True)
            return d
        except Exception:
            return None


def is_edge_running():
    """检测系统中是否有 Edge 正在运行，若在运行则返回 True"""
    try:
        sysname = (platform.system() or '').lower()
        if 'darwin' in sysname or 'mac' in sysname:
            # 优先使用 pgrep
            try:
                r = subprocess.run(['pgrep', '-f', 'Microsoft Edge'], capture_output=True)
                if r.returncode == 0:
                    return True
            except Exception:
                pass
            try:
                r = subprocess.run(['pgrep', '-f', 'msedge'], capture_output=True)
                if r.returncode == 0:
                    return True
            except Exception:
                pass
        elif 'windows' in sysname:
            try:
                r = subprocess.run(['tasklist'], capture_output=True, text=True)
                s = (r.stdout or '').lower()
                if 'msedge.exe' in s or 'microsoftedge.exe' in s:
                    return True
            except Exception:
                pass
        else:
            # linux 系统
            for pat in ['msedge', 'microsoft-edge', 'Microsoft Edge']:
                try:
                    r = subprocess.run(['pgrep', '-f', pat], capture_output=True)
                    if r.returncode == 0:
                        return True
                except Exception:
                    pass
    except Exception:
        pass
    return False


def setup_driver(user_data_dir=None, profile_directory=None, headless=False, use_proxy: bool = None):
    """设置MS Edge浏览器驱动，支持附加到现有Edge用户配置文件以帮助通过安全检查。

    :param use_proxy: 显式指定是否使用代理；为 None 时按既定尝试顺序（先代理后直连）。
    """
    def build_options(use_proxy=True):
        opts = Options()
        opts.page_load_strategy = 'eager'
        opts.add_argument('--no-sandbox')
        opts.add_argument('--disable-dev-shm-usage')
        opts.add_argument('--disable-blink-features=AutomationControlled')
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option('useAutomationExtension', False)
        opts.add_argument('--remote-allow-origins=*')
        opts.add_argument('--disable-gpu')
        opts.add_argument('--start-maximized')
        opts.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
        
        # 附加到Edge用户配置文件以重用cookie和人类信号
        if user_data_dir:
            opts.add_argument(f"--user-data-dir={user_data_dir}")
        if profile_directory:
            opts.add_argument(f"--profile-directory={profile_directory}")
            
        # 设置代理
        if use_proxy:
            opts.add_argument(f'--proxy-server=socks5://{SOCKS5_PROXY_HOST}:{SOCKS5_PROXY_PORT}')
            opts.add_argument('--proxy-bypass-list=<-loopback>')
        
        # 设置无头模式
        if headless:
            opts.add_argument('--headless')
        
        return opts

    # 确定驱动路径
    system = platform.system().lower()
    if system == "darwin":
        machine = platform.machine().lower()
        default_driver_path = "/usr/local/bin/edgedriver_mac64_m1/msedgedriver" if machine in ['arm64', 'aarch64'] else "/usr/local/bin/edgedriver_mac64/msedgedriver"
    elif system == "windows":
        default_driver_path = r"C:\\bin\\edgedriver_win64\\msedgedriver.exe"
    elif system == "linux":
        default_driver_path = "/usr/local/bin/edgedriver_linux64/msedgedriver"
    else:
        default_driver_path = "/usr/local/bin/edgedriver_mac64/msedgedriver"

    user_driver_path = os.path.expanduser("~/bin/edgedriver_mac64_m1/msedgedriver")
    driver_path = user_driver_path if os.path.exists(user_driver_path) else default_driver_path

    last_error = None
    if use_proxy is None:
        attempts = [
            {"proxy": True,  "use_service": True,  "label": "ui+proxy+service"},
            {"proxy": False, "use_service": True,  "label": "ui+no-proxy+service"},
            {"proxy": False, "use_service": False, "label": "ui+no-proxy+PATH"},
        ]
    elif use_proxy:
        attempts = [
            {"proxy": True,  "use_service": True,  "label": "ui+proxy+service"},
            {"proxy": True,  "use_service": False, "label": "ui+proxy+PATH"},
        ]
    else:
        attempts = [
            {"proxy": False, "use_service": True,  "label": "ui+no-proxy+service"},
            {"proxy": False, "use_service": False, "label": "ui+no-proxy+PATH"},
        ]
    
    for att in attempts:
        try:
            print(f"尝试启动Edge驱动（{att['label']}），路径: {driver_path}")
            opts = build_options(use_proxy=att["proxy"])
            if att["use_service"] and os.path.exists(driver_path):
                service = webdriver.edge.service.Service(driver_path)
                driver = webdriver.Edge(service=service, options=opts)
            else:
                driver = webdriver.Edge(options=opts)
            
            driver.set_page_load_timeout(60)
            driver.set_script_timeout(30)
            
            # 隐藏webdriver特征
            try:
                driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            except Exception:
                pass
            
            print("Edge驱动启动成功（UI模式）")
            return driver
        except Exception as e:
            last_error = e
            print(f"启动失败（{att['label']}）: {e}")
            time.sleep(1)

    print(f"MS Edge driver启动失败: {last_error}")
    print("请确保已安装MS Edge浏览器和EdgeDriver")
    print("您可以运行update_msedge_driver.py来安装驱动")
    return None


def is_login_page(driver):
    """检测当前页面是否为登录页面"""
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


def is_security_verification_page(driver):
    """检测当前页面是否为安全验证页面"""
    try:
        url = (driver.current_url or '').lower()
        # URL关键词命中
        if any(k in url for k in ['challenge', 'verify', 'security', 'captcha', 'cf-challenge']):
            return True
        # 常见Cloudflare/验证码痕迹
        if driver.find_elements(By.CSS_SELECTOR, '#cf-challenge, .cf-challenge, .challenge-container'):
            return True
        if driver.find_elements(By.CSS_SELECTOR, '[data-sitekey], .captcha, iframe[src*="captcha"]'):
            return True
        # 文本提示
        if driver.find_elements(By.XPATH, "//*[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'security verification')]"):
            return True
        if driver.find_elements(By.XPATH, "//*[contains(text(),'安全验证') or contains(text(),'请完成安全验证') or contains(text(),'驗證')]"):
            return True
        if driver.find_elements(By.XPATH, "//*[contains(text(),'Verify you are human') or contains(text(),'Just a moment')]"):
            return True
    except Exception:
        pass
    return False


def wait_for_manual_login(driver, seconds=300, reopen_url=None):
    """
    等待用户手动登录，支持按回车立即继续，否则最长等待seconds秒
    :param driver: WebDriver实例
    :param seconds: 最长等待时间（秒），默认为300秒（5分钟）
    :param reopen_url: 登录后重新打开的URL
    """
    import select as _select
    print(f"\n=== 请手动完成登录操作 ===")
    print(f"1. 在浏览器中完成JAVDB网站的登录")
    print(f"2. 登录成功后，请按回车键继续执行程序")
    print(f"3. 如果不操作，程序将在 {int(seconds)} 秒后自动继续")
    
    try:
        # 使用select监听标准输入，等待用户按键或超时
        rlist, _, _ = _select.select([sys.stdin], [], [], seconds)
        if rlist:
            _ = sys.stdin.readline()  # 读取回车符
            print("已检测到您的操作，正在继续执行...")
        else:
            print("等待超时，自动继续执行...")
    except Exception:
        # 如果select不可用（如Windows某些环境），回退到简单的sleep
        print(f"等待 {int(seconds)} 秒让您完成登录...")
        time.sleep(seconds)
        print("等待时间结束，继续执行...")
    
    # 如果提供了重新打开的URL，则在登录后访问该URL
    if reopen_url:
        try:
            print(f"登录处理完成，正在导航到指定页面：{reopen_url}")
            driver.get(reopen_url)
            random_delay(2, 3)  # 给页面加载时间
        except Exception:
            print("重新打开页面时发生错误，但不影响程序继续执行")


# ---------- 番号提取器 ----------
class CodeExtractor:
    """增强版番号提取器，整合了 javsp_mac 的先进识别逻辑"""
    
    def __init__(self):
        # 忽略模式配置
        self.ignore_pattern = re.compile(r'', re.I)  # 可以根据需要配置
        
        # 常见的无效匹配（需要过滤掉的）
        self.invalid_patterns = [
            r'^\d{4}$',  # 纯4位数字（可能是年份）
            r'^19\d{2}$|^20\d{2}$',  # 年份格式
            r'^\d{1,2}p$',  # 分辨率标识如720p, 1080p
            r'^[xX]\d+$',  # x264, x265等编码标识
            r'^\d{1,3}$',  # 过短的纯数字
        ]
        
        self.invalid_compiled = [re.compile(pattern, re.IGNORECASE) for pattern in self.invalid_patterns]
    
    def extract_code_from_filename(self, filename: str) -> str:
        """
        从文件名中提取番号（基于 javsp_mac 的 get_id 函数增强）
        """
        # 获取文件名并应用忽略模式
        basename = os.path.basename(filename)
        basename = self.ignore_pattern.sub('', basename)
        filename_lc = basename.lower()
        
        # FC2 格式处理
        if 'fc2' in filename_lc:
            match = re.search(r'fc2[^a-z\d]{0,5}(ppv[^a-z\d]{0,5})?(\d{5,7})', basename, re.I)
            if match:
                return 'FC2-' + match.group(2)
        
        # 一本道格式：1pondo-123456_789
        elif '1pondo' in filename_lc or 'pondo' in filename_lc:
            match = re.search(r'(1pondo|pondo)[-_]*(\d{6})[-_]*(\d{3})', basename, re.I)
            if match:
                return '1pondo-' + match.group(2) + '_' + match.group(3)
        
        # 加勒比格式：carib-123456-789, caribbeancom-123456-789
        elif 'carib' in filename_lc:
            match = re.search(r'(carib|caribbeancom)[-_]*(\d{6})[-_]*(\d{3})', basename, re.I)
            if match:
                return match.group(1) + '-' + match.group(2) + '-' + match.group(3)
        
        # 天然素人格式：10musume-123456_01
        elif '10musume' in filename_lc or 'musume' in filename_lc:
            match = re.search(r'(10musume|musume)[-_]*(\d{6})[-_]*(\d{2})', basename, re.I)
            if match:
                return '10musume-' + match.group(2) + '_' + match.group(3)
        
        # Heydouga 格式
        elif 'heydouga' in filename_lc:
            match = re.search(r'(heydouga)[-_]*(\d{4})[-_]0?(\d{3,5})', basename, re.I)
            if match:
                return '-'.join(match.groups())
        
        # 普通番号，优先尝试匹配带分隔符的（如ABC-123）
        match = re.search(r'([a-z]{2,10})[-_](\d{2,5})', basename, re.I)
        if match:
            return match.group(1) + '-' + match.group(2)
        
        # 东热的red, sky, ex三个不带-分隔符的系列
        match = re.search(r'(red[01]\d{2}|sky[0-3]\d{2}|ex00[01]\d)', basename, re.I)
        if match:
            return match.group(1)
        
        # 缺失了-分隔符的普通番号
        match = re.search(r'([a-z]{2,})([0-9]{2,5})', basename, re.I)
        if match:
            return match.group(1) + '-' + match.group(2)
        
        # TMA制作的影片（如'T28-557'）
        match = re.search(r'(T28[-_]\d{3})', basename)
        if match:
            return match.group(1)
        
        # 东热n, k系列
        match = re.search(r'(n\d{4}|k\d{4})', basename, re.I)
        if match:
            return match.group(1)
        
        # 纯数字番号（无码影片）
        match = re.search(r'(\d{6}[-_]\d{2,3})', basename)
        if match:
            return match.group(1)
        
        # 尝试将')('替换为'-'后再试
        if ')(' in filename:
            avid = self.extract_code_from_filename(filename.replace(')(', '-'))
            if avid:
                return avid
        
        # 如果仍然匹配不了，尝试使用文件所在文件夹的名字
        if os.path.isfile(filename):
            norm = os.path.normpath(filename)
            if os.sep in norm:
                folder = norm.split(os.sep)[-2]
                return self.extract_code_from_filename(folder)
        
        return None
    
    def _clean_filename(self, filename):
        """清理文件名，移除干扰字符"""
        # 移除常见的干扰字符
        filename = re.sub(r'[\[\]\(\)\{\}\s\-_\.\*]', '', filename)
        return filename
    
    def _format_code(self, match):
        """格式化提取到的番号"""
        if isinstance(match, tuple):
            if len(match) == 2 and match[0] and match[1]:
                return f"{match[0].upper()}-{match[1]}"
        return match
    
    def _is_valid_code(self, code):
        """检查提取的番号是否有效"""
        for pattern in self.invalid_compiled:
            if pattern.match(code):
                return False
        return True


# ---------- 数据库操作 ----------
def get_user_defined_folders():
    """获取用户定义的数据文件夹列表"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        # 查询所有活跃的文件夹
        cursor.execute("SELECT folder_path, folder_type FROM folders WHERE is_active = 1")
        folders = cursor.fetchall()
        conn.close()
        return [(folder[0], folder[1]) for folder in folders]
    except Exception as e:
        print(f"获取用户定义文件夹时出错: {e}")
        return []


def get_videos_to_update(folder_path=None, refresh_all=False, filter_by_code=None):
    """获取需要更新JAVDB信息的视频列表"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 基础查询条件
        base_conditions = []
        params = []
        
        # 文件夹过滤（兼容尾部斜杠，并包含子目录）；同时兼容基于 file_path 的前缀匹配
        if folder_path:
            norm_path = folder_path.rstrip('/\\')
            base_conditions.append("((v.source_folder = ? OR v.source_folder = ? OR v.source_folder LIKE ?) OR v.file_path LIKE ?)")
            params.extend([norm_path, norm_path + '/', norm_path + '/%', norm_path + '/%'])
        
        # 番号过滤
        if filter_by_code:
            base_conditions.append("j.javdb_code = ?")
            params.append(filter_by_code)
        
        # 主查询语句构建
        if refresh_all:
            # 刷新所有视频，包括那些已经有JAVDB信息的视频
            base_query = """
                SELECT v.id, v.file_path, v.title, j.javdb_code 
                FROM videos v
                LEFT JOIN javdb_info j ON v.id = j.video_id
            """
            
            if base_conditions:
                where_clause = " WHERE " + " AND ".join(base_conditions)
            else:
                where_clause = ""
                
            if not filter_by_code and not folder_path:
                # 如果没有过滤条件，只查询最近100个视频
                order_clause = " ORDER BY v.id DESC LIMIT 100"
            else:
                order_clause = ""
                
            query = base_query + where_clause + order_clause
        else:
            # 仅查询需要更新的视频（没有JAVDB信息或没有完整演员信息）
            base_query = """
                SELECT v.id, v.file_path, v.title, j.javdb_code 
                FROM videos v
                LEFT JOIN javdb_info j ON v.id = j.video_id
            """
            
            if base_conditions:
                where_clause = " WHERE " + " AND ".join(base_conditions) + " AND ("
            else:
                where_clause = " WHERE ("
                
            update_conditions = ""
            update_conditions += "j.id IS NULL -- 没有JAVDB信息\n"
            update_conditions += "OR NOT EXISTS (\n"
            update_conditions += "    SELECT 1 FROM video_actors va \n"
            update_conditions += "    JOIN actors a ON va.actor_id = a.id \n"
            update_conditions += "    WHERE va.video_id = v.id \n"
            # 根据当前 BASE_URL 的域名进行匹配（支持代理/直连两种主域名）
            domain = urlparse(BASE_URL).netloc
            update_conditions += f"    AND a.profile_url LIKE '%{domain}%'\n"
            update_conditions += ") -- 没有JAVDB女演员链接\n"
            
            query = base_query + where_clause + update_conditions + ")"
        
        cursor.execute(query, params)
        videos = cursor.fetchall()
        conn.close()
        
        return [{
            'id': video[0],
            'file_path': video[1],
            'title': video[2],
            'av_code': video[3] if len(video) > 3 and video[3] is not None else None
        } for video in videos]
    except Exception as e:
        print(f"获取需要更新的视频时出错: {e}")
        return []

# 兼容旧版API
def get_videos_without_actors(folder_path=None):
    """获取指定文件夹下需要更新JAVDB信息的视频列表（兼容旧版）"""
    return get_videos_to_update(folder_path)


def update_video_info(
    video_id,
    title=None,
    actors=None,
    tags=None,
    studio=None,
    series=None,
    release_date=None,
    duration=None,
    rating=None,
    cover_image_path=None,
    javdb_code=None,
    javdb_url=None,
    cover_image_url=None,
    magnet_links=None,
):
    """更新视频信息到数据库，并将封面以BLOB写入数据库。

    - 更新 `videos` 表：标题、标签、时长、评分、`thumbnail_path`，如存在则同时更新 `thumbnail_data`。
    - Upsert `javdb_info`：按 `video_id` 写入/更新 `cover_image_data`（BLOB）与 `local_cover_path`。
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 查询 videos 表的可用列，避免写入不存在的列造成错误
        cursor.execute("PRAGMA table_info(videos);")
        available_cols = {row[1] for row in cursor.fetchall()}  # 第二列是列名

        update_fields = []
        params = []

        if title and 'title' in available_cols:
            update_fields.append("title = ?")
            params.append(title)

        # actors 信息不直接写入 videos 表；演员链接关系应通过 video_actors/actors 维护

        if tags and 'tags' in available_cols:
            # tags 统一存储为逗号分隔字符串
            update_fields.append("tags = ?")
            params.append(','.join(tags) if isinstance(tags, (list, tuple)) else str(tags))

        # studio 和 release_date 在当前表结构中不存在，跳过

        if duration is not None and 'duration' in available_cols:
            update_fields.append("duration = ?")
            params.append(duration)

        if rating is not None and 'rating' in available_cols:
            update_fields.append("rating = ?")
            params.append(rating)

        # 将封面路径映射到 thumbnail_path（若存在）；并尝试读取字节以更新 thumbnail_data（若存在）
        cover_image_data = None
        if cover_image_path:
            try:
                # 直接读取绝对路径；相对路径则以脚本目录为基准
                p = cover_image_path
                if not os.path.isabs(p):
                    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), p)
                if os.path.exists(p):
                    with open(p, 'rb') as f:
                        cover_image_data = f.read()
            except Exception:
                cover_image_data = None

            if 'thumbnail_path' in available_cols:
                update_fields.append("thumbnail_path = ?")
                params.append(cover_image_path)

            if cover_image_data is not None and 'thumbnail_data' in available_cols:
                update_fields.append("thumbnail_data = ?")
                params.append(cover_image_data)

        # 若没有任何可更新字段，直接返回成功
        if not update_fields:
            conn.close()
            return True

        # 添加视频ID作为最后一个参数
        params.append(video_id)

        query = f"UPDATE videos SET {', '.join(update_fields)} WHERE id = ?"
        cursor.execute(query, params)
        conn.commit()

        # 将封面以BLOB写入/更新到 javdb_info 表，并补充其它JAVDB字段
        try:
            if cover_image_path and cover_image_data is None:
                # 若上面未能读取，重试一次读取
                p = cover_image_path
                if not os.path.isabs(p):
                    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), p)
                if os.path.exists(p):
                    with open(p, 'rb') as f:
                        cover_image_data = f.read()

            # 确保 javdb_info / javdb_tags / javdb_info_tags 表存在
            cursor.execute(
                """
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
                    score TEXT,
                    cover_url TEXT,
                    local_cover_path TEXT,
                    cover_image_data BLOB,
                    magnet_links TEXT,
                    preview_images TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (video_id) REFERENCES videos (id) ON DELETE CASCADE
                )
                """
            )
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

            # 解析评分为数值分值（score）
            score_val = None
            try:
                if isinstance(rating, (int, float)):
                    score_val = float(rating)
                elif isinstance(rating, str):
                    cleaned = rating.strip()
                    if cleaned:
                        score_val = float(cleaned)
            except Exception:
                score_val = None

            # 统一序列化列表字段（仅磁力链接保留JSON；标签与演员使用关系表写入）
            magnet_json = None
            try:
                import json as _json
                if magnet_links:
                    magnet_json = _json.dumps(magnet_links, ensure_ascii=False)
            except Exception:
                pass

            cursor.execute("SELECT id FROM javdb_info WHERE video_id = ?", (video_id,))
            row = cursor.fetchone()
            if row is None:
                cursor.execute(
                    """
                    INSERT INTO javdb_info (
                        video_id, javdb_code, javdb_url, javdb_title, release_date, duration, studio, series,
                        rating, score, cover_url, local_cover_path, cover_image_data, magnet_links,
                        created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                    """,
                    (
                        video_id,
                        javdb_code or '',
                        javdb_url or '',
                        title or None,
                        release_date or None,
                        duration if (duration is not None) else None,
                        studio or None,
                        series or None,
                        None,
                        score_val,
                        cover_image_url or None,
                        cover_image_path or '',
                        cover_image_data,
                        magnet_json,
                    )
                )
                javdb_info_id = cursor.lastrowid
            else:
                cursor.execute(
                    """
                    UPDATE javdb_info
                    SET javdb_code = COALESCE(?, javdb_code),
                        javdb_url = COALESCE(?, javdb_url),
                        javdb_title = COALESCE(?, javdb_title),
                        release_date = COALESCE(?, release_date),
                        duration = COALESCE(?, duration),
                        studio = COALESCE(?, studio),
                        series = COALESCE(?, series),
                        rating = COALESCE(?, rating),
                        score = COALESCE(?, score),
                        cover_url = COALESCE(?, cover_url),
                        local_cover_path = COALESCE(?, local_cover_path),
                        cover_image_data = COALESCE(?, cover_image_data),
                        magnet_links = COALESCE(?, magnet_links),
                        updated_at = datetime('now')
                    WHERE video_id = ?
                    """,
                    (
                        javdb_code or None,
                        javdb_url or None,
                        title or None,
                        release_date or None,
                        duration if (duration is not None) else None,
                        studio or None,
                        series or None,
                        None,
                        score_val,
                        cover_image_url or None,
                        cover_image_path or '',
                        cover_image_data,
                        magnet_json,
                        video_id,
                    )
                )
                javdb_info_id = row[0]
            conn.commit()

            # 同步写入标签关联（javdb_tags / javdb_info_tags）
            try:
                if tags and javdb_info_id:
                    for t in tags:
                        tag_name = (t or '').strip()
                        if not tag_name:
                            continue
                        cursor.execute(
                            "INSERT OR IGNORE INTO javdb_tags (tag_name) VALUES (?)",
                            (tag_name,)
                        )
                        cursor.execute("SELECT id FROM javdb_tags WHERE tag_name = ?", (tag_name,))
                        tag_row = cursor.fetchone()
                        if tag_row:
                            tag_id = tag_row[0]
                            cursor.execute(
                                "INSERT OR IGNORE INTO javdb_info_tags (javdb_info_id, tag_id) VALUES (?, ?)",
                                (javdb_info_id, tag_id)
                            )
                    conn.commit()
            except Exception as _e:
                # 标签关联失败不阻断主流程
                print(f"写入JAVDB标签关联失败: {_e}")
        except Exception as e:
            # 不影响主更新流程，打印日志即可
            print(f"更新javdb_info封面BLOB失败: {e}")

        # 若提供了演员信息，则写入 actors 与 video_actors 关联
        try:
            if actors and isinstance(actors, (list, tuple)):
                for actor in actors:
                    try:
                        actor_name = (actor.get('name') or '').strip()
                        actor_link = (actor.get('link') or '').strip()

                        if not actor_name:
                            continue

                        # 规范化链接为绝对URL（可能为/actors/xxx形式）
                        if actor_link and actor_link.startswith('/'):
                            actor_link = urljoin(BASE_URL, actor_link)

                        # 查找现有演员（优先按profile_url匹配，其次按name匹配）
                        cursor.execute("SELECT id, profile_url FROM actors WHERE profile_url = ?", (actor_link,))
                        row = cursor.fetchone()
                        actor_id = None

                        if row:
                            actor_id = row[0]
                            # 如名称为空或不同，可适度更新名称（不强制覆盖已有非空）
                            cursor.execute("UPDATE actors SET updated_at = datetime('now') WHERE id = ?", (actor_id,))
                        else:
                            # 尝试按名称匹配已存在记录
                            cursor.execute("SELECT id, profile_url FROM actors WHERE name = ?", (actor_name,))
                            row = cursor.fetchone()
                            if row:
                                actor_id = row[0]
                                # 若该记录没有profile_url，则补充
                                existing_profile = row[1] or ''
                                if actor_link and (not existing_profile.strip()):
                                    cursor.execute(
                                        "UPDATE actors SET profile_url = ?, updated_at = datetime('now') WHERE id = ?",
                                        (actor_link, actor_id)
                                    )
                            else:
                                # 插入新演员
                                cursor.execute(
                                    """
                                    INSERT INTO actors (name, profile_url, created_at, updated_at)
                                    VALUES (?, ?, datetime('now'), datetime('now'))
                                    """,
                                    (actor_name, actor_link)
                                )
                                actor_id = cursor.lastrowid

                        # 建立视频-演员关联（唯一约束防重复）
                        if actor_id:
                            cursor.execute(
                                """
                                INSERT OR IGNORE INTO video_actors (video_id, actor_id, created_at)
                                VALUES (?, ?, datetime('now'))
                                """,
                                (video_id, actor_id)
                            )
                    except Exception as _e:
                        # 单个演员写入失败不影响整体，打印日志继续
                        print(f"写入演员信息失败: {_e}")

                conn.commit()
        except Exception as e:
            print(f"批量写入演员信息时出错: {e}")

        conn.close()
        return True
    except Exception as e:
        print(f"更新视频信息时出错: {e}")
        return False


# ---------- JAVDB信息爬取 ----------
def search_video_by_code(driver, video_code):
    """Search video by code and return detail page URL"""
    try:
        # Navigate to search page
        search_url = f"{BASE_URL}/search?q={video_code}&f=all"
        print(f"正在搜索番号: {video_code}")
        driver.get(search_url)
        # 执行人类操作，以触发懒加载与规避检测
        perform_human_actions(driver)
        random_delay(2, 4)
        
        # Wait for search results to load
        wait = WebDriverWait(driver, 20)
        
        # Find the first search result
        try:
            # Look for video links in search results
            video_links = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'a[href*="/v/"]')))
            
            if video_links:
                detail_url = video_links[0].get_attribute('href')
                print(f"找到详情页: {detail_url}")
                return detail_url
            else:
                print(f"未找到{video_code}的搜索结果")
                return None
                
        except TimeoutException:
            print(f"搜索结果加载超时: {video_code}")
            return None
            
    except Exception as e:
        print(f"搜索错误: {video_code} - {e}")
        return None


def safe_filename(filename):
    """Convert filename to safe format"""
    # Remove or replace unsafe characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Remove leading and trailing spaces and dots
    filename = filename.strip(' .')
    # Limit filename length
    if len(filename) > 200:
        filename = filename[:200]
    return filename


def download_image(img_url, filename):
    """Download image to local and return absolute path"""
    try:
        import requests
        # Setup proxy for image download
        proxies = {
            'http': f'socks5://{SOCKS5_PROXY_HOST}:{SOCKS5_PROXY_PORT}',
            'https': f'socks5://{SOCKS5_PROXY_HOST}:{SOCKS5_PROXY_PORT}'
        }

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Referer': BASE_URL
        }

        try:
            response = requests.get(img_url, headers=headers, proxies=proxies, timeout=30)
            response.raise_for_status()
        except Exception:
            # 代理失败时，尝试直连
            response = requests.get(img_url, headers=headers, timeout=30)
            response.raise_for_status()

        # Ensure covers directory exists
        os.makedirs(COVERS_DIR, exist_ok=True)

        # Determine extension from Content-Type or URL path
        content_type = (response.headers.get('Content-Type') or '').lower()
        if 'image/jpeg' in content_type or 'image/jpg' in content_type:
            ext = '.jpg'
        elif 'image/png' in content_type:
            ext = '.png'
        elif 'image/webp' in content_type:
            ext = '.webp'
        else:
            parsed_path = urlparse(img_url).path
            ext = os.path.splitext(parsed_path)[1] or '.jpg'

        # Sanitize filename
        safe_name = safe_filename(filename)

        # Save image to file with extension
        img_path = os.path.join(COVERS_DIR, f"{safe_name}{ext}")
        with open(img_path, 'wb') as f:
            f.write(response.content)

        # Return absolute path
        return img_path

    except Exception as e:
        print(f"封面下载失败 {img_url}: {e}")
        return None


def find_local_poster(file_path):
    """当网络封面下载失败时，尝试使用视频同目录下的poster.jpg作为封面。
    优先使用网络爬取的封面；仅在其不可用时使用本地poster.jpg。
    """
    try:
        if not file_path:
            return None
        dir_path = os.path.dirname(file_path)
        poster_path = os.path.join(dir_path, 'poster.jpg')
        if os.path.isfile(poster_path):
            return poster_path
    except Exception:
        pass
    return None


def parse_detail(driver, detail_url, max_retries=3):
    """解析详情页，提取视频信息"""
    for attempt in range(max_retries):
        try:
            print(f"正在访问详情页: {detail_url} (尝试 {attempt + 1}/{max_retries})")
            driver.get(detail_url)
            # 人类操作模拟：滚动与轻微鼠标移动
            perform_human_actions(driver)
            
            # Wait for core page content to load
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.container, #content, body'))
            )
            random_delay(1, 2)

            # Get title
            title = 'N/A'
            title_selectors = ['h2.title', 'h1.title', 'h2', 'h1', '.title']
            for selector in title_selectors:
                try:
                    title_element = driver.find_element(By.CSS_SELECTOR, selector)
                    if title_element and title_element.text:
                        title = title_element.text.strip()
                        break
                except:
                    continue
            
            # If title not found, page has issues, retry
            if title == 'N/A':
                raise ValueError("Could not parse title, page may not have loaded correctly.")

            # Get番号(ID)
            video_id = 'N/A'
            try:
                video_id_element = driver.find_element(By.XPATH, "//strong[text()='番號:']/following-sibling::span[1]")
                video_id = video_id_element.text.strip()
            except:
                try:
                    video_id_element = driver.find_element(By.XPATH, "//strong[text()='識別碼:']/following-sibling::span[1]")
                    video_id = video_id_element.text.strip()
                except:
                    try:
                        video_id_element = driver.find_element(By.XPATH, "//strong[text()='ID:']/following-sibling::span[1]")
                        video_id = video_id_element.text.strip()
                    except:
                        pass

            # Get date
            release_date = 'N/A'
            try:
                date_element = driver.find_element(By.XPATH, "//strong[text()='日期:']/following-sibling::span[1]")
                release_date = date_element.text.strip()
            except:
                try:
                    date_element = driver.find_element(By.XPATH, "//strong[text()='發行日期:']/following-sibling::span[1]")
                    release_date = date_element.text.strip()
                except:
                    try:
                        date_element = driver.find_element(By.XPATH, "//strong[text()='Date:']/following-sibling::span[1]")
                        release_date = date_element.text.strip()
                    except:
                        pass

            # Get duration
            duration = 'N/A'
            try:
                duration_element = driver.find_element(By.XPATH, "//strong[text()='時長:']/following-sibling::span[1]")
                duration = duration_element.text.strip()
            except:
                try:
                    duration_element = driver.find_element(By.XPATH, "//strong[text()='Duration:']/following-sibling::span[1]")
                    duration = duration_element.text.strip()
                except:
                    pass

            # Get rating
            rating = 'N/A'
            try:
                rating_element = driver.find_element(By.XPATH, "//strong[text()='評分:']/following-sibling::span[1]")
                rating_text = rating_element.text.strip()
                # Extract only the numeric rating (e.g., "3.97" from "3.97分, 由420人評價")
                rating_match = re.search(r'(\d+\.\d+)', rating_text)
                rating = rating_match.group(1) if rating_match else rating_text
            except:
                try:
                    rating_element = driver.find_element(By.XPATH, "//strong[text()='Rating:']/following-sibling::span[1]")
                    rating_text = rating_element.text.strip()
                    # Extract only the numeric rating (e.g., "3.97" from "3.97分, 由420人評價")
                    rating_match = re.search(r'(\d+\.\d+)', rating_text)
                    rating = rating_match.group(1) if rating_match else rating_text
                except:
                    pass

            # Get tags
            tags = []
            try:
                tag_elements = driver.find_elements(By.XPATH, "//strong[text()='類別:']/following-sibling::span[1]/a")
                tags = [tag.text.strip() for tag in tag_elements]
            except:
                try:
                    tag_elements = driver.find_elements(By.XPATH, "//strong[text()='Tags:']/following-sibling::span[1]/a")
                    tags = [tag.text.strip() for tag in tag_elements]
                except:
                    pass

            # Get actors (only female actors)
            actors = []
            try:
                # Find the actor section
                actor_section = driver.find_element(By.XPATH, "//strong[text()='演員:']/following-sibling::span[1]")
                # Get all actor links and their following gender symbols
                actor_links = actor_section.find_elements(By.TAG_NAME, "a")
                
                for actor_link in actor_links:
                    actor_name = actor_link.text.strip()
                    actor_href = actor_link.get_attribute('href')
                    
                    # Check if there's a female symbol after this actor link
                    try:
                        # Look for female symbol immediately following the actor link
                        parent_element = actor_link.find_element(By.XPATH, "./following-sibling::strong[@class='symbol female'][1]")
                        if parent_element and '♀' in parent_element.text:
                            actors.append({
                                'name': actor_name,
                                'link': actor_href
                            })
                    except:
                        # If no female symbol found, skip this actor
                        continue
            except:
                try:
                    actor_elements = driver.find_elements(By.XPATH, "//strong[text()='Actors:']/following-sibling::span[1]//a")
                    for actor_element in actor_elements:
                        actor_name = actor_element.text.strip()
                        actor_link = actor_element.get_attribute('href')
                        
                        # Check for female symbol
                        try:
                            parent_element = actor_element.find_element(By.XPATH, "./following-sibling::strong[@class='symbol female'][1]")
                            if parent_element and '♀' in parent_element.text:
                                actors.append({
                                    'name': actor_name,
                                    'link': actor_link
                                })
                        except:
                            continue
                except:
                    pass

            # Get studio/maker (片商)
            studio = 'N/A'
            try:
                studio_element = driver.find_element(By.XPATH, "//strong[text()='片商:']/following-sibling::span[1]")
                studio = studio_element.text.strip()
            except:
                try:
                    studio_element = driver.find_element(By.XPATH, "//strong[text()='製作商:']/following-sibling::span[1]")
                    studio = studio_element.text.strip()
                except:
                    try:
                        studio_element = driver.find_element(By.XPATH, "//strong[text()='Studio:']/following-sibling::span[1]")
                        studio = studio_element.text.strip()
                    except:
                        pass

            # Get series (系列)
            series = 'N/A'
            try:
                series_element = driver.find_element(By.XPATH, "//strong[text()='系列:']/following-sibling::span[1]")
                series = series_element.text.strip()
            except:
                try:
                    series_element = driver.find_element(By.XPATH, "//strong[text()='Series:']/following-sibling::span[1]")
                    series = series_element.text.strip()
                except:
                    pass

            # Get cover image
            img_url = ''
            img_selectors = [
                'div.cover img', '.cover img', 'img.video-cover', 'img[src*="cover"]', 
                'img[src*="thumb"]', '.movie-panel img'
            ]
            img_element_for_screenshot = None
            for selector in img_selectors:
                try:
                    img_element = driver.find_element(By.CSS_SELECTOR, selector)
                    if img_element:
                        # 优先读取 srcset / data-src 获取更高清封面
                        srcset = img_element.get_attribute('srcset')
                        data_src = img_element.get_attribute('data-src')
                        src = img_element.get_attribute('src')
                        if srcset:
                            try:
                                parts = [p.strip() for p in srcset.split(',') if p.strip()]
                                last = parts[-1]
                                candidate = last.split(' ')[0]
                                img_url = candidate
                            except Exception:
                                img_url = src or data_src or ''
                        else:
                            img_url = src or data_src or ''
                        if img_url and not img_url.startswith('http'):
                            img_url = urljoin(BASE_URL, img_url)
                        # 记录元素以便截图回退
                        img_element_for_screenshot = img_element
                        break
                except:
                    continue
            
            # Download cover image
            local_img_path = None
            if img_url and title != 'N/A':
                filename = f"{video_id}_{title}" if video_id != 'N/A' else title
                try:
                    local_img_path = download_image(img_url, filename)
                except Exception as e:
                    print(f"封面下载失败，尝试截图回退: {e}")
                
                # 下载失败或文件不存在时，回退为元素截图
                try:
                    if (not local_img_path) or (not os.path.exists(local_img_path)):
                        if img_element_for_screenshot is not None:
                            os.makedirs(COVERS_DIR, exist_ok=True)
                            screenshot_path = os.path.join(COVERS_DIR, f"{filename}.png")
                            img_element_for_screenshot.screenshot(screenshot_path)
                            if os.path.exists(screenshot_path):
                                local_img_path = os.path.abspath(screenshot_path)
                                print("封面回退截图成功")
                except Exception as e:
                    print(f"封面截图回退失败: {e}")

            # Get magnet links (下载链接)
            magnet_links = []
            try:
                # 首选：页面内包含 data-clipboard-text 的磁力链接复制按钮
                elements = driver.find_elements(By.CSS_SELECTOR, '.magnet-links [data-clipboard-text^="magnet:?xt"]')
                for el in elements:
                    data = el.get_attribute('data-clipboard-text')
                    if data and data.startswith('magnet:?'):
                        magnet_links.append(data)

                # 兜底：常见复制按钮选择器
                if not magnet_links:
                    copy_buttons = driver.find_elements(By.CSS_SELECTOR, 'button[data-clipboard-text^="magnet:?xt"], .copy-to-clipboard')
                    for b in copy_buttons:
                        data = b.get_attribute('data-clipboard-text')
                        if data and data.startswith('magnet:?'):
                            magnet_links.append(data)

                # 最后兜底：直接抓取 a[href^="magnet:"]
                if not magnet_links:
                    anchors = driver.find_elements(By.CSS_SELECTOR, 'a[href^="magnet:?xt"]')
                    for a in anchors:
                        href = a.get_attribute('href')
                        if href and href.startswith('magnet:?'):
                            magnet_links.append(href)

                # 去重
                magnet_links = list(dict.fromkeys(magnet_links))
            except Exception:
                pass
            
            print(f"解析成功 - 标题: {title[:50]}..., ID: {video_id}")
            return {
                'title': title,
                'video_id': video_id,
                'detail_url': detail_url,
                'release_date': release_date,
                'duration': duration,
                'rating': rating,
                'tags': tags,
                'actors': actors,
                'studio': studio,
                'series': series,
                'cover_image_url': img_url,
                'local_image_path': local_img_path,
                'magnet_links': magnet_links
            }

        except Exception as e:
            print(f"解析详情页错误 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                print("等待重试...")
                random_delay(15, 30)
                continue
            else:
                print("所有重试均失败，记录为无法解析。")
                # Return default failure object
                return {
                    'title': 'N/A',
                    'video_id': 'N/A',
                    'detail_url': detail_url,
                    'release_date': 'N/A',
                    'duration': 'N/A',
                    'rating': 'N/A',
                    'tags': [],
                    'actors': [],
                    'studio': 'N/A',
                    'series': 'N/A',
                    'cover_image_url': '',
                    'local_image_path': None,
                    'magnet_links': []
                }


# ---------- 主功能函数 ----------
def crawl_single_video(driver, video_code):
    """Crawl single video by code"""
    try:
        # Search video
        detail_url = search_video_by_code(driver, video_code)
        if not detail_url:
            print(f"未找到番号 {video_code} 的详情页")
            return None
            
        # Parse detail page
        result = parse_detail(driver, detail_url)
        if result:
            print(f"成功获取番号 {video_code} 的信息")
            return result
        else:
            print(f"解析番号 {video_code} 的详情页失败")
            return None
            
    except Exception as e:
        print(f"爬取番号 {video_code} 时发生错误: {e}")
        return None


def update_videos_without_actors(driver, folder_path=None):
    """批量更新没有演员信息的视频"""
    # 获取没有演员信息的视频列表
    videos = get_videos_without_actors(folder_path)
    if not videos:
        print("没有找到需要更新的视频")
        return

    print(f"找到 {len(videos)} 个需要更新演员信息的视频")

    # 初始化番号提取器
    code_extractor = CodeExtractor()

    # 先按番号分组去重，确保每个番号只爬取一次
    code_map = {}
    for video in videos:
        av_code = video.get('av_code')
        if not av_code:
            av_code = code_extractor.extract_code_from_filename(video.get('file_path') or '')
            if not av_code:
                av_code = code_extractor.extract_code_from_filename(video.get('title') or '')
        if not av_code:
            # 无法提取番号的记录，留到失败统计阶段
            av_code = None
        code_map.setdefault(av_code, []).append(video)

    # 去掉无效番号键
    if None in code_map:
        invalid_group = code_map.pop(None)
    else:
        invalid_group = []

    unique_codes = list(code_map.keys())
    print(f"去重后需要处理的番号数: {len(unique_codes)}")

    # 成功和失败计数
    success_count = 0
    failed_count = 0
    failed_videos = []
    # 批量摘要累计
    total_tags = 0
    total_actors = 0
    total_magnet_links = 0
    unique_studios = set()
    unique_series = set()

    # 先记录无法提取番号的失败项
    for v in invalid_group:
        failed_count += 1
        failed_videos.append((v.get('title') or v.get('file_path') or '未知', "无法提取番号"))

    # 按唯一番号进行爬取并批量更新同番号的所有视频
    for idx, code in enumerate(unique_codes):
        group = code_map.get(code, [])
        sample_title = (group[0].get('title') or '')
        print(f"\n正在处理番号 {idx + 1}/{len(unique_codes)}: {code}（关联视频数 {len(group)}）")

        # 爬取一次
        result = crawl_single_video(driver, code)
        if not result:
            failed_count += len(group)
            for v in group:
                failed_videos.append(((v.get('title') or v.get('file_path') or '未知'), "爬取失败"))
            # 下一个番号前仍保持延迟
            random_delay(MIN_DELAY, MAX_DELAY)
            continue

        # 打印该番号的摘要
        tags_cnt = len(result.get('tags') or [])
        actors_cnt = len(result.get('actors') or [])
        magnets_cnt = len(result.get('magnet_links') or [])
        studio_str = result.get('studio') or 'N/A'
        series_str = result.get('series') or 'N/A'
        print(f"摘要：标签 {tags_cnt} 个，演员 {actors_cnt} 名，片商 {studio_str}，下载链接 {magnets_cnt} 条" + (f"，系列 {series_str}" if series_str and series_str != 'N/A' else ""))

        # 累计批量摘要
        total_tags += tags_cnt
        total_actors += actors_cnt
        total_magnet_links += magnets_cnt
        if studio_str and studio_str != 'N/A':
            unique_studios.add(studio_str)
        if series_str and series_str != 'N/A':
            unique_series.add(series_str)

        # 将结果应用到所有关联视频
        for v in group:
            # 优先使用网络下载的封面；如无则回退到同目录poster.jpg
            cover_path = result.get('local_image_path')
            if not cover_path:
                cover_path = find_local_poster(v.get('file_path'))
            update_result = update_video_info(
                v['id'],
                title=result['title'],
                actors=result['actors'],
                tags=result['tags'],
                studio=result['studio'],
                series=result.get('series'),
                release_date=result['release_date'],
                duration=result['duration'],
                rating=result['rating'],
                cover_image_path=cover_path,
                javdb_code=result.get('video_id'),
                javdb_url=result.get('detail_url'),
                cover_image_url=result.get('cover_image_url'),
                magnet_links=result.get('magnet_links')
            )
            if update_result:
                success_count += 1
            else:
                failed_count += 1
                failed_videos.append((v.get('title') or v.get('file_path') or '未知', "更新数据库失败"))

        # 番号间随机延迟，避免被反爬（默认3-7秒，可配置）
        random_delay(MIN_DELAY, MAX_DELAY)

    # 打印统计结果
    print(f"\n=== 更新完成 ===")
    print(f"总视频数: {len(videos)}")
    print(f"去重后番号数: {len(unique_codes)}")
    print(f"成功更新: {success_count}")
    print(f"更新失败: {failed_count}")
    print(f"汇总：标签 {total_tags} 个，演员 {total_actors} 名，下载链接 {total_magnet_links} 条")
    if unique_studios:
        print(f"片商数: {len(unique_studios)}（例如：{list(unique_studios)[:3]}）")
    if unique_series:
        print(f"系列数: {len(unique_series)}（例如：{list(unique_series)[:3]}）")

    if failed_videos:
        print("\n失败的视频列表:")
        for title, reason in failed_videos[:10]:  # 只显示前10个
            print(f"- {title[:50]}...: {reason}")
        if len(failed_videos) > 10:
            print(f"... 还有 {len(failed_videos) - 10} 个失败视频未显示")


def select_folder(test_mode=False, test_folder_path=None):
    """列出用户定义的文件夹，让用户通过编号选择"""
    folders = get_user_defined_folders()
    if not folders:
        print("没有找到用户定义的数据文件夹")
        return None
    
    # 测试模式：自动选择指定的文件夹
    if test_mode and test_folder_path:
        print(f"测试模式：自动选择文件夹: {test_folder_path}")
        return test_folder_path
    
    print("请选择要更新的文件夹:")
    for i, (folder_path, folder_type) in enumerate(folders):
        print(f"{i + 1}. {folder_path} ({folder_type})")
    
    try:
        choice = int(input("请输入文件夹编号 (0表示全部): "))
        if choice == 0:
            return None  # 返回None表示选择全部文件夹
        elif 1 <= choice <= len(folders):
            return folders[choice - 1][0]  # 返回选择的文件夹路径
        else:
            print("无效的选择")
            return None
    except ValueError:
        print("请输入有效的数字")
        return None


def login_and_update(test_mode=False, test_folder_path=None, refresh_all=False, filter_by_code=None):
    """登录JAVDB并更新指定文件夹下需要更新的视频信息
    
    参数:
        test_mode: 测试模式，自动选择测试文件夹
        test_folder_path: 测试文件夹路径
        refresh_all: 是否刷新所有视频，包括已更新的视频
        filter_by_code: 按番号筛选特定视频，如 'ADN-347'
    """
    # 设置用户数据目录，用于保存登录状态
    user_data_dir = os.path.join(os.path.expanduser('~'), '.javdb_scraper', 'user_data')
    os.makedirs(user_data_dir, exist_ok=True)
    
    # 启动浏览器（根据是否使用代理决定网络模式）
    driver = setup_driver(user_data_dir=user_data_dir, headless=False, use_proxy=USE_PROXY)  # 使用有头模式
    
    if not driver:
        print("无法启动浏览器，程序退出")
        sys.exit(1)
    
    try:
        # 先尝试直接访问主页，检查是否已经登录
        print(f"正在访问主页: {BASE_URL}")
        driver.get(BASE_URL)
        random_delay(3, 5)  # 等待页面加载
        
        # 检查是否需要登录或安全验证
        if is_security_verification_page(driver):
            print("检测到安全验证页面，请完成验证")
            wait_for_manual_login(driver, seconds=300, reopen_url=BASE_URL)
        
        # 如果直接访问主页后仍需要登录，则访问登录页面
        if is_login_page(driver):
            print("检测到需要登录，正在访问登录页面...")
            driver.get(LOGIN_URL)
            random_delay(3, 5)
            
            # 再次检查是否需要安全验证
            if is_security_verification_page(driver):
                print("检测到安全验证页面，请完成验证")
                wait_for_manual_login(driver, seconds=300, reopen_url=LOGIN_URL)
                
                # 验证安全验证是否成功
                if is_security_verification_page(driver):
                    print("安全验证可能未成功，请重新尝试")
                    return
            
            print("请手动登录您的JAVDB账号")
            wait_for_manual_login(driver, seconds=300, reopen_url=None)  # 不重新打开URL，保持当前页面
        
        # 验证是否登录成功
        print("正在验证登录状态...")
        driver.get(BASE_URL)
        random_delay(3, 5)
        
        # 简单的登录验证：检查是否存在用户相关元素或不再跳转登录页
        if not is_login_page(driver):
            print("\n登录成功！")
            
            if filter_by_code:
                # 按番号刷新特定视频
                print(f"正在刷新番号为 {filter_by_code} 的视频")
                # 直接爬取并更新该视频
                result = crawl_single_video(driver, filter_by_code)
                if result:
                    # 查询数据库中是否有该番号的视频
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute("SELECT v.id, v.file_path FROM videos v WHERE v.id IN (SELECT video_id FROM javdb_info WHERE javdb_code = ?)", (filter_by_code,))
                    row = cursor.fetchone()
                    conn.close()
                    
                    if row:
                        # 优先使用网络下载的封面；如无则回退到同目录poster.jpg
                        cover_path = result.get('local_image_path')
                        if not cover_path:
                            cover_path = find_local_poster(row[1])
                        update_result = update_video_info(
                            row[0],
                            title=result['title'],
                            actors=result['actors'],
                            tags=result['tags'],
                            studio=result['studio'],
                            series=result.get('series'),
                            release_date=result['release_date'],
                            duration=result['duration'],
                            rating=result['rating'],
                            cover_image_path=cover_path,
                            javdb_code=result.get('video_id'),
                            javdb_url=result.get('detail_url'),
                            cover_image_url=result.get('cover_image_url'),
                            magnet_links=result.get('magnet_links')
                        )
                        if update_result:
                            print(f"成功更新番号为 {filter_by_code} 的视频信息")
                        else:
                            print(f"更新番号为 {filter_by_code} 的视频信息失败")
                    else:
                        print(f"数据库中未找到番号为 {filter_by_code} 的视频")
                else:
                    print(f"爬取番号为 {filter_by_code} 的视频信息失败")
            else:
                # 选择要更新的文件夹
                folder_path = select_folder(test_mode, test_folder_path)
                if folder_path is not None or (not folder_path and (test_mode or input("确定要更新所有文件夹的视频吗？(y/n): ").lower() == 'y')):
                    if refresh_all:
                        # 刷新所有视频
                        print("正在刷新所有视频信息...")
                        videos = get_videos_to_update(folder_path, refresh_all=True)
                        if videos:
                            print(f"找到 {len(videos)} 个视频")
                            # 初始化番号提取器
                            code_extractor = CodeExtractor()

                            # 先按番号分组去重，确保每个番号只爬取一次
                            code_map = {}
                            for v in videos:
                                av_code = v.get('av_code')
                                if not av_code:
                                    av_code = code_extractor.extract_code_from_filename(v.get('file_path') or '')
                                    if not av_code:
                                        av_code = code_extractor.extract_code_from_filename(v.get('title') or '')
                                if not av_code:
                                    av_code = None
                                code_map.setdefault(av_code, []).append(v)

                            invalid_group = code_map.pop(None, []) if None in code_map else []
                            unique_codes = list(code_map.keys())
                            print(f"去重后需要处理的番号数: {len(unique_codes)}")

                            # 成功和失败计数
                            success_count = 0
                            failed_count = 0
                            failed_videos = []

                            # 记录无法提取番号的失败项
                            for v in invalid_group:
                                failed_count += 1
                                failed_videos.append((v.get('title') or v.get('file_path') or '未知', "无法提取番号"))

                            # 按唯一番号进行爬取并批量更新同番号的所有视频
                            for idx, code in enumerate(unique_codes):
                                group = code_map.get(code, [])
                                print(f"\n正在处理番号 {idx + 1}/{len(unique_codes)}: {code}（关联视频数 {len(group)}）")

                                # 爬取一次
                                result = crawl_single_video(driver, code)
                                if not result:
                                    failed_count += len(group)
                                    for v in group:
                                        failed_videos.append((v.get('title') or v.get('file_path') or '未知', "爬取失败"))
                                    random_delay(MIN_DELAY, MAX_DELAY)
                                    continue

                                # 将结果应用到所有关联视频
                                for v in group:
                                    # 优先使用网络下载的封面；如无则回退到同目录poster.jpg
                                    cover_path = result.get('local_image_path')
                                    if not cover_path:
                                        cover_path = find_local_poster(v.get('file_path'))
                                    update_result = update_video_info(
                                        v['id'],
                                        title=result['title'],
                                        actors=result['actors'],
                                        tags=result['tags'],
                                        studio=result['studio'],
                                        series=result.get('series'),
                                        release_date=result['release_date'],
                                        duration=result['duration'],
                                        rating=result['rating'],
                                        cover_image_path=cover_path,
                                        javdb_code=result.get('video_id'),
                                        javdb_url=result.get('detail_url'),
                                        cover_image_url=result.get('cover_image_url'),
                                        magnet_links=result.get('magnet_links')
                                    )
                                    if update_result:
                                        success_count += 1
                                    else:
                                        failed_count += 1
                                        failed_videos.append((v.get('title') or v.get('file_path') or '未知', "更新数据库失败"))

                                # 番号间随机延迟，避免被反爬（默认3-7秒，可配置）
                                random_delay(MIN_DELAY, MAX_DELAY)

                            # 打印统计结果
                            print(f"\n=== 更新完成 ===")
                            print(f"总视频数: {len(videos)}")
                            print(f"去重后番号数: {len(unique_codes)}")
                            print(f"成功更新: {success_count}")
                            print(f"更新失败: {failed_count}")
                        else:
                            print("没有找到视频")
                    else:
                        # 批量更新没有完整信息的视频
                        update_videos_without_actors(driver, folder_path)
                else:
                    print("已取消更新操作")
        else:
            print("\n登录可能未成功，请检查并重新尝试")
            
    except Exception as e:
        print(f"发生错误: {e}")
    finally:
        try:
            # 优化关闭逻辑：只有在命令行模式下才自动关闭浏览器
            # 交互式使用时，让用户决定是否关闭
            if not test_mode and not filter_by_code and not refresh_all:
                # 全自动模式：自动关闭
                print("关闭浏览器...")
                driver.quit()
            else:
                # 交互模式：询问用户是否关闭
                user_input = input("任务已完成。按回车键关闭浏览器，输入'n'保留浏览器打开状态：")
                if user_input.lower() != 'n':
                    print("关闭浏览器...")
                    driver.quit()
                else:
                    print("浏览器保持打开状态，您可以继续使用")
        except:
            pass


if __name__ == "__main__":
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description='JAVDB视频信息更新工具')
    parser.add_argument('--refresh-all', action='store_true', help='刷新所有视频信息，包括已更新的视频')
    parser.add_argument('--code', type=str, help='按番号刷新特定视频，如 --code ADN-347')
    parser.add_argument('--test', action='store_true', help='测试模式')
    parser.add_argument('--test-folder', type=str, help='测试文件夹路径')
    parser.add_argument('--db-path', type=str, help='指定数据库文件路径或目录（目录将自动追加media_library.db）')
    parser.add_argument('--min-delay', type=float, help='最小操作间隔秒，默认3')
    parser.add_argument('--max-delay', type=float, help='最大操作间隔秒，默认7')
    parser.add_argument('--no-proxy', dest='no_proxy', action='store_true', help='不使用代理（使用直连域名）')
    
    # 解析命令行参数
    args = parser.parse_args()

    # 覆盖默认数据库路径（支持传入目录）
    if args.db_path:
        new_db_path = args.db_path
        try:
            if os.path.isdir(new_db_path):
                new_db_path = os.path.join(new_db_path, 'media_library.db')
            # 确保父目录存在
            os.makedirs(os.path.dirname(new_db_path), exist_ok=True)
            DB_PATH = new_db_path
            print(f"使用数据库路径: {DB_PATH}")
        except Exception as e:
            print(f"设置数据库路径失败: {e}")
            print(f"回退到默认数据库路径: {DB_PATH}")

    # 根据命令行参数调整默认随机延迟范围
    try:
        if args.min_delay is not None:
            MIN_DELAY = float(args.min_delay)
        if args.max_delay is not None:
            MAX_DELAY = float(args.max_delay)
        if MIN_DELAY > MAX_DELAY:
            MIN_DELAY, MAX_DELAY = MAX_DELAY, MIN_DELAY
        print(f"操作间隔：最小 {MIN_DELAY:.1f}s，最大 {MAX_DELAY:.1f}s")
    except Exception:
        pass

    # 设置是否使用代理，并根据模式更新 BASE_URL / LOGIN_URL
    try:
        USE_PROXY = not getattr(args, 'no_proxy', False)
        BASE_URL = get_javdb_base_url(USE_PROXY)
        LOGIN_URL = f"{BASE_URL}/login"
        mode_str = '代理模式' if USE_PROXY else '直连模式'
        print(f"访问域名切换为：{BASE_URL}（{mode_str}）")
    except Exception as e:
        print(f"设置访问域名失败，仍使用默认：{BASE_URL}。错误：{e}")

    # 执行登录和更新
    login_and_update(
        test_mode=args.test,
        test_folder_path=args.test_folder,
        refresh_all=args.refresh_all,
        filter_by_code=args.code
    )