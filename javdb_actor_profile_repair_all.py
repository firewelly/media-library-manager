#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JavDB演员档案全量重新爬取脚本

功能：
- 重新爬取所有已有JavDB链接的演员信息
- 清理之前爬取错误或者有更新的信息
- 基于原有javdb_actor_profile_repair.py，但修改了演员选择逻辑
- 查找等待爬取的演员时，选择所有有javdb链接的演员进行重新爬取

运行示例：
- 干跑预览（不写库）：
  python javdb_actor_profile_repair_all.py --db-path media_library.db --dry-run --limit 50
- 实际写库（小范围验证）：
  python javdb_actor_profile_repair_all.py --db-path media_library.db --execute --limit 20
- 重新爬取所有有JavDB链接的演员：
  python javdb_actor_profile_repair_all.py --db-path media_library.db --execute --all-javdb-actors

说明：
- 浏览器以 UI 模式运行并复用项目内统一的 Edge 用户数据目录，便于手工登录。
- 默认下载头像二进制数据并写入 avatar_data，同时更新 avatar_url；如需仅更新 URL 可加入 --no-download-avatar 禁用下载。
"""

import os
import sys
import re
import argparse
import sqlite3
import time
import random
from urllib.parse import urlparse, urlunparse
import urllib.request
import io
import cv2
import numpy as np

import platform
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver import ActionChains

# 兼容性导入配置
import config as _cfg
BASE_URL = getattr(_cfg, 'BASE_URL', 'https://javdb.com')
SOCKS5_PROXY_HOST = getattr(_cfg, 'SOCKS5_PROXY_HOST', '127.0.0.1')
SOCKS5_PROXY_PORT = getattr(_cfg, 'SOCKS5_PROXY_PORT', 1080)
MIN_DELAY = getattr(_cfg, 'MIN_DELAY', 2.0)
MAX_DELAY = getattr(_cfg, 'MAX_DELAY', 4.0)


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


def canonicalize_javdb_url(url: str) -> str:
    """将任何 javdbNNN.com 等替代域名改写为 https://javdb.com，保留路径与查询。"""
    try:
        if not url:
            return url
        parsed = urlparse(url)
        host = (parsed.netloc or '').lower()
        if 'javdb.com' in host:
            # 已是主域名
            return url
        # 匹配替代域（例如 javdb562.com）
        if re.match(r'^javdb\d+\.com$', host):
            new_netloc = 'javdb.com'
            return urlunparse((parsed.scheme or 'https', new_netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
        # 对其他域名不改写
        return url
    except Exception:
        return url


class JavdbActorRepair:
    def __init__(self, db_path: str, download_avatar: bool = True, use_proxy: bool = True, prefer_insert: bool = False, use_temp_profile: bool = False, use_cover_fallback: bool = True):
        self.db_path = db_path
        self.download_avatar = download_avatar
        self.use_proxy = use_proxy
        self.prefer_insert = prefer_insert
        self.driver = None
        self.use_temp_profile = use_temp_profile
        self.use_cover_fallback = use_cover_fallback
        # 基于是否使用代理，动态选择BASE_URL
        try:
            self.base_url = _cfg.get_javdb_base_url(use_proxy)
        except Exception:
            self.base_url = ('https://javdb.com' if use_proxy else 'https://javdb562.com')
        # URL规范化方法（浏览用）：将任意 javdb 域统一改为当前 base_url 域
        def _norm(url):
            try:
                if not url:
                    return url
                p = urlparse(url)
                host = (p.netloc or '').lower()
                if 'javdb' in host:
                    target_host = urlparse(self.base_url).netloc
                    p = p._replace(netloc=target_host)
                    return urlunparse(p)
                return url
            except Exception:
                # 退化：不改写，避免误伤
                return url
        self._normalize_url = _norm
        # 最终入库统一规范化为主域名 javdb.com
        def _norm_store(url):
            try:
                from urllib.parse import urlparse, urlunparse
                p = urlparse(url)
                host = (p.netloc or '').lower()
                if not host:
                    return url
                alternates = [
                    'javdb.com',
                    'www.javdb.com',
                ]
                try:
                    alternates.extend(getattr(_cfg, 'JAVDB_ALTERNATE_DIRECT_DOMAINS', []))
                except Exception:
                    pass
                # 可匹配 javdbNNN.com 或带 www 前缀
                import re as _re
                if host in [h.lower() for h in alternates] or _re.match(r'^(www\.)?javdb\d+\.com$', host):
                    p = p._replace(netloc='javdb.com')
                    return urlunparse(p)
                return url
            except Exception:
                return canonicalize_javdb_url(url)
        self._normalize_url_store = _norm_store
        # 干跑模式标记：在预览模式下缩短等待与动作以便快速验证
        self.dry_run_mode = False

    def random_delay(self, min_seconds=MIN_DELAY, max_seconds=MAX_DELAY):
        # 干跑/测试模式下将等待时间缩短到 0.5–2 秒，避免长时间阻塞
        if getattr(self, 'dry_run_mode', False):
            min_seconds = min(min_seconds, 0.5)
            max_seconds = min(max_seconds, 2.0)
        time.sleep(random.uniform(min_seconds, max_seconds))

    def setup_driver(self):
        # 在单链接测试模式下，使用临时独立的用户数据目录以避免被占用
        user_data_dir = None
        profile_directory = None
        try:
            if self.use_temp_profile:
                base = os.path.dirname(os.path.abspath(__file__))
                suffix = f".edge_driver_user_data_test_{int(time.time())}_{os.getpid()}"
                user_data_dir = os.path.join(base, suffix)
                os.makedirs(user_data_dir, exist_ok=True)
                # 临时目录下不强制指定 Default，避免并发占用
                profile_directory = None
            else:
                user_data_dir = get_dedicated_edge_user_data_dir()
                profile_directory = detect_default_edge_profile_directory(user_data_dir)
        except Exception:
            user_data_dir = get_dedicated_edge_user_data_dir()
            profile_directory = detect_default_edge_profile_directory(user_data_dir)

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
        if user_data_dir:
            opts.add_argument(f"--user-data-dir={user_data_dir}")
        if profile_directory:
            opts.add_argument(f"--profile-directory={profile_directory}")
        # 可选代理
        if self.use_proxy:
            opts.add_argument(f'--proxy-server=socks5://{SOCKS5_PROXY_HOST}:{SOCKS5_PROXY_PORT}')
            opts.add_argument('--proxy-bypass-list=<-loopback>')

        # 选择驱动路径
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

        try:
            if os.path.exists(driver_path):
                service = webdriver.edge.service.Service(driver_path)
                self.driver = webdriver.Edge(service=service, options=opts)
            else:
                self.driver = webdriver.Edge(options=opts)
            self.driver.set_page_load_timeout(60)
            self.driver.set_script_timeout(30)
            try:
                self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            except Exception:
                pass
            print("Edge驱动初始化成功（UI模式，复用登录态）")
        except Exception as e:
            print(f"Edge驱动初始化失败: {e}")
            self.driver = None

    def human_pause(self, min_seconds=3, max_seconds=6, do_actions=True):
        """执行随机等待并模拟一些人类操作（滚动与鼠标移动）。"""
        try:
            self.random_delay(min_seconds, max_seconds)
            # 干跑模式下跳过人类动作以加快验证速度
            if getattr(self, 'dry_run_mode', False):
                return
            if not do_actions or not self.driver:
                return
            try:
                total_h = self.driver.execute_script("return Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)")
                win_h = self.driver.execute_script("return window.innerHeight")
                if total_h and win_h:
                    max_y = max(0, int(total_h) - int(win_h))
                    y = random.randint(0, max_y) if max_y > 0 else 0
                    self.driver.execute_script("window.scrollTo(0, arguments[0]);", y)
            except Exception:
                pass
            try:
                ac = ActionChains(self.driver)
                ac.move_by_offset(random.randint(-30, 30), random.randint(-20, 20)).perform()
                ac.move_by_offset(random.randint(-30, 30), random.randint(-20, 20)).perform()
            except Exception:
                pass
        except Exception:
            pass

    def is_security_verification_page(self):
        """粗略检测安全验证/挑战页（如Cloudflare）。"""
        try:
            url = (self.driver.current_url or '').lower()
            if any(k in url for k in ['challenge', 'verify', 'security', 'captcha', 'cf-challenge']):
                return True
            if self.driver.find_elements(By.CSS_SELECTOR, '#cf-challenge, .cf-challenge, .challenge-container'):
                return True
            if self.driver.find_elements(By.XPATH, "//*[contains(text(),'验证') or contains(text(),'Challenge') or contains(text(),'安全验证')]"):
                return True
        except Exception:
            pass
        return False

    def is_login_page(self):
        try:
            url = (self.driver.current_url or '').lower()
            if 'login' in url or '/sign_in' in url:
                return True
            if self.driver.find_elements(By.CSS_SELECTOR, 'input[type="email"], input[name="email"]'):
                return True
            if self.driver.find_elements(By.CSS_SELECTOR, 'input[type="password"], input[name="password"]'):
                return True
            if self.driver.find_elements(By.CSS_SELECTOR, '[data-sitekey], .captcha, iframe[src*="captcha"]'):
                return True
        except Exception:
            pass
        return False

    def wait_for_manual_login(self, seconds=300, reopen_url=None):
        import select
        print(f"检测到登录页，请在 UI 中手工登录。按回车继续，或最多等待 {int(seconds)} 秒…")
        try:
            rlist, _, _ = select.select([sys.stdin], [], [], seconds)
            if rlist:
                _ = sys.stdin.readline()
                print("检测到回车，继续执行…")
            else:
                print("等待超时，继续执行…")
        except Exception:
            time.sleep(seconds)
        if reopen_url:
            try:
                print(f"登录后重新打开页面：{reopen_url}")
                self.driver.get(reopen_url)
                self.random_delay(2, 4)
            except Exception:
                pass

    def search_actor_on_javdb(self, actor_name: str) -> str:
        if not self.driver:
            self.setup_driver()
            if not self.driver:
                return None
        # 使用实例级的 base_url（跟随是否使用代理）
        search_url = f"{self.base_url}/search?q={actor_name}&f=actor"
        print(f"搜索演员: {actor_name} => {search_url}")
        try:
            self.driver.get(search_url)
            # 页面加载与人类行为模拟：搜索后 3-5 秒随机等待
            if self.is_login_page():
                self.wait_for_manual_login(seconds=300, reopen_url=search_url)
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.container, #content, body'))
            )
            # 检测安全验证页
            if self.is_security_verification_page():
                print("检测到安全验证页面，模拟人类行为并等待…")
                self.human_pause(min_seconds=3, max_seconds=5, do_actions=True)
            else:
                self.human_pause(min_seconds=3, max_seconds=5, do_actions=True)
            selectors = [
                '#actors .actor-box a[href*="/actors/"]',
                '.actors .box a[href*="/actors/"]',
                '.grid .item a[href*="/actors/"]',
                '.actors-grid .item a[href*="/actors/"]',
                '.movie-list .item a[href*="/actors/"]'
            ]
            for sel in selectors:
                results = self.driver.find_elements(By.CSS_SELECTOR, sel)
                if results:
                    for r in results:
                        href = r.get_attribute('href')
                        # 过滤掉导航栏中的 censored/uncensored 链接
                        if href and '/actors/censored' not in href and '/actors/uncensored' not in href:
                            return self._normalize_url(href)
            return None
        except Exception as e:
            print(f"搜索异常: {e}")
            return None

    def _normalize_name_token(self, s: str) -> str:
        """规范化单个名称token：去除包裹的括号与多余空白，过滤计数信息。"""
        if not s:
            return ''
        t = s.strip()
        # 去掉外层括号
        t = re.sub(r'^[\(（]\s*', '', t)
        t = re.sub(r'\s*[\)）]$', '', t)
        # 去掉尾随的"数字+部影片/部作品"等计数噪音（保留纯净艺名）
        t = re.sub(r'[\s\u3000]*\d+\s*部(?:影片|作品)\b.*$', '', t)
        # 去掉常见分隔符后的附加信息
        t = re.sub(r'\s*[-|｜].*$', '', t)
        return t.strip()

    def _classify_names(self, primary_names, alias_items):
        pass

    def fetch_actor_page(self, actor_url: str) -> dict:
        if not self.driver:
            self.setup_driver()
            if not self.driver:
                return None
        try:
            # 浏览用：将URL域名统一到当前base_url（无代理为javdb562.com，有代理为javdb.com）
            browse_url = self._normalize_url(actor_url)
            try:
                print(f"打开演员页: {browse_url}")
            except Exception:
                pass
            self.driver.get(browse_url)
            # 页面加载与人类行为模拟：打开演员页后 10-15 秒随机等待
            if self.is_login_page():
                self.wait_for_manual_login(seconds=300, reopen_url=browse_url)
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.container, #content, body'))
            )
            # 检测安全验证页
            if self.is_security_verification_page():
                print("检测到安全验证页面，模拟人类行为并等待…")
                self.human_pause(min_seconds=10, max_seconds=15, do_actions=True)
            else:
                self.human_pause(min_seconds=10, max_seconds=15, do_actions=True)
            # 规范化个人页URL（跟随是否使用代理）
            info = {'profile_url': self._normalize_url(actor_url)}

            # 解析主名称（常见于 actor-section-name 或 title）
            main_text = ''
            try:
                name_el = self.driver.find_element(By.CSS_SELECTOR, '.actor-section-name, .actor-info .title, .actor-box .title, h1.title, h2.title')
                main_text = (name_el.text or '').strip()
            except Exception:
                pass
            # 基于页面两行规则解析（第一行为中文名与common名，第二行全部为别名）
            lines_raw = [x.strip() for x in re.split(r"[\r\n]+", (main_text or '')) if x.strip()]
            def _strip_noise_line(x: str) -> str:
                x = re.sub(r"[\s\u3000]*\d+\s*部(?:影片|作品)\b.*$", "", x)
                x = re.sub(r"\s*[-|｜].*$", "", x)
                return x.strip()
            lines = [_strip_noise_line(l) for l in lines_raw]
            first_line = (lines[0] if lines else '')
            second_lines = (lines[1:] if len(lines) > 1 else [])
            comma_split = r"[,，、]\s*"
            tokens1 = [self._normalize_name_token(t) for t in (re.split(comma_split, first_line) if first_line else [])]
            tokens1 = [t for t in tokens1 if t]
            aliases_from_main = []
            if len(tokens1) >= 2:
                info['name_traditional'] = tokens1[0]
                info['name'] = tokens1[1]
                info['name_common'] = tokens1[1]
                for t in tokens1:
                    if t != info['name_common']:
                        aliases_from_main.append(t)
            elif len(tokens1) == 1:
                info['name'] = tokens1[0]
                info['name_common'] = tokens1[0]
                info['name_traditional'] = tokens1[0]
            for line_i in second_lines:
                for t in re.split(comma_split, line_i):
                    norm = self._normalize_name_token(t)
                    if norm:
                        aliases_from_main.append(norm)

            # 解析别名（常见于 section-meta 或副标题），与主标题解析的别名合并
            alias_items = []
            try:
                alias_el = self.driver.find_element(By.CSS_SELECTOR, '.section-meta, .actor-info .sub-title, .actor-box .sub-title, .actor-header .sub-title, .actor-section-name + small')
                alias_text = (alias_el.text or '').strip()
                raw_aliases = [self._normalize_name_token(a) for a in re.split(comma_split, alias_text)]
                alias_items = [a for a in raw_aliases if a]
            except Exception:
                pass

            try:
                m_paren = re.findall(r'[\(（]\s*([^\)）]+?)\s*[\)）]', main_text or '')
                for grp in m_paren:
                    for tok in re.split(r"[\,\u3001、，/｜\|・\s]+", grp):
                        t = self._normalize_name_token(tok)
                        if t:
                            alias_items.append(t)
            except Exception:
                pass

            # 合并别名来源并去重；策略：除了 common 名之外的所有名字都作为别名
            all_alias_candidates = []
            all_alias_candidates.extend(aliases_from_main)
            all_alias_candidates.extend(alias_items)
            excluded = {info.get('name_common')}
            dedup_aliases = []
            seen = set()
            for a in all_alias_candidates:
                if a and a not in excluded and a not in seen:
                    dedup_aliases.append(a)
                    seen.add(a)
            if dedup_aliases:
                info['aliases'] = ', '.join(dedup_aliases)

            # 头像
            avatar_url = None
            selectors = [
                '.actor-avatar img',
                '.actor-info img',
                '.actor-box img',
                '.actor-section img',
                'img[alt*="actor"], img[alt*="Actor"]',
                '.avatar img',
                'img[src*="/actors/"]'
            ]
            for sel in selectors:
                try:
                    img_el = self.driver.find_element(By.CSS_SELECTOR, sel)
                    src = (img_el.get_attribute('src') or '').strip()
                    if src and src.startswith('http'):
                        avatar_url = src
                        break
                except Exception:
                    continue
            info['avatar_url'] = avatar_url

            # 生日
            birthday = None
            try:
                # 常见格式：1990-01-01 或 1990年1月1日
                birthday_text = ''
                els = self.driver.find_elements(By.XPATH, "//*[contains(text(),'生日') or contains(text(),'Birthday') or contains(text(),'生年月日')]/following-sibling::*[1]")
                if els:
                    birthday_text = (els[0].text or '').strip()
                if not birthday_text:
                    els = self.driver.find_elements(By.CSS_SELECTOR, '.actor-birthday, .birthday, .birth-date')
                    if els:
                        birthday_text = (els[0].text or '').strip()
                if birthday_text:
                    # 提取日期
                    m = re.search(r'(\d{4})[年\-](\d{1,2})[月\-](\d{1,2})', birthday_text)
                    if m:
                        birthday = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
            except Exception:
                pass
            info['birth_date'] = birthday

            # 身高
            height = None
            try:
                height_text = ''
                els = self.driver.find_elements(By.XPATH, "//*[contains(text(),'身高') or contains(text(),'Height') or contains(text(),'身長')]/following-sibling::*[1]")
                if els:
                    height_text = (els[0].text or '').strip()
                if not height_text:
                    els = self.driver.find_elements(By.CSS_SELECTOR, '.actor-height, .height')
                    if els:
                        height_text = (els[0].text or '').strip()
                if height_text:
                    # 提取数字
                    m = re.search(r'(\d+)', height_text)
                    if m:
                        height = int(m.group(1))
            except Exception:
                pass
            info['height'] = height

            # 罩杯
            cup = None
            try:
                cup_text = ''
                els = self.driver.find_elements(By.XPATH, "//*[contains(text(),'罩杯') or contains(text(),'Cup') or contains(text(),'カップ')]/following-sibling::*[1]")
                if els:
                    cup_text = (els[0].text or '').strip()
                if not cup_text:
                    els = self.driver.find_elements(By.CSS_SELECTOR, '.actor-cup, .cup')
                    if els:
                        cup_text = (els[0].text or '').strip()
                if cup_text:
                    # 提取罩杯（A-Z）
                    m = re.search(r'([A-Z])', cup_text.upper())
                    if m:
                        cup = m.group(1)
            except Exception:
                pass
            # 注意：数据库中没有cup字段，跳过这个字段

            # 作品数量
            works_count = None
            try:
                count_text = ''
                els = self.driver.find_elements(By.XPATH, "//*[contains(text(),'部作品') or contains(text(),'部作品') or contains(text(),'works')]")
                if els:
                    count_text = (els[0].text or '').strip()
                if not count_text:
                    els = self.driver.find_elements(By.CSS_SELECTOR, '.actor-works-count, .works-count')
                    if els:
                        count_text = (els[0].text or '').strip()
                if count_text:
                    # 提取数字
                    m = re.search(r'(\d+)', count_text)
                    if m:
                        works_count = int(m.group(1))
            except Exception:
                pass
            info['movie_count'] = works_count

            return info
        except Exception as e:
            print(f"获取演员页异常: {e}")
            return None

    def download_avatar_data(self, avatar_url: str) -> bytes:
        if not avatar_url:
            return None
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'Referer': self.base_url
            }
            req = urllib.request.Request(avatar_url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
                # 验证是否为有效图片
                img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
                if img is not None and img.size > 0:
                    return data
        except Exception as e:
            print(f"下载头像失败: {e}")
        return None

    def get_actors_with_javdb_links(self, limit: int = None, min_actor_id: int = None):
        """获取所有有JavDB链接的演员 - 这是本脚本的核心修改"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        # 构建查询：选择所有profile_url包含javdb的演员
        # 使用实际的数据库字段名称
        query = """
            SELECT id, name, profile_url, avatar_url, avatar_data, last_crawled_at,
                   name_traditional, name_common, aliases, birth_date, height, movie_count
            FROM actors
            WHERE profile_url IS NOT NULL 
            AND profile_url != ''
            AND (
                profile_url LIKE '%javdb%'
                OR profile_url LIKE '%javdb562%'
                OR profile_url LIKE '%javdb561%'
                OR profile_url LIKE '%javdb563%'
                OR profile_url LIKE '%javdb564%'
            )
        """
        
        params = []
        if min_actor_id:
            query += " AND id >= ?"
            params.append(min_actor_id)
            
        query += " ORDER BY id ASC"
        
        if limit:
            query += " LIMIT ?"
            params.append(limit)
            
        try:
            cur.execute(query, params)
            rows = cur.fetchall()
            actors = []
            for row in rows:
                actors.append(dict(row))
            return actors
        except Exception as e:
            print(f"查询演员失败: {e}")
            return []
        finally:
            conn.close()

    def update_actor_info(self, actor_id: int, info: dict):
        """更新演员信息"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        try:
            # 更新基本信息 - 使用实际的数据库字段名称
            update_fields = []
            params = []
            
            if 'name' in info and info['name']:
                update_fields.append("name = ?")
                params.append(info['name'])
            if 'name_traditional' in info and info['name_traditional']:
                update_fields.append("name_traditional = ?")
                params.append(info['name_traditional'])
            if 'name_common' in info:
                update_fields.append("name_common = ?")
                params.append(info['name_common'])
            if 'aliases' in info:
                update_fields.append("aliases = ?")
                val = info['aliases']
                if isinstance(val, (list, tuple)):
                    params.append(', '.join([str(x).strip() for x in val if str(x).strip()]))
                else:
                    params.append(str(val) if val else '')
            if 'birth_date' in info:
                update_fields.append("birth_date = ?")
                params.append(info['birth_date'])
            if 'height' in info:
                update_fields.append("height = ?")
                params.append(info['height'])
            if 'movie_count' in info:
                update_fields.append("movie_count = ?")
                params.append(info['movie_count'])
            if 'avatar_url' in info:
                update_fields.append("avatar_url = ?")
                params.append(info['avatar_url'])
            if 'avatar_data' in info:
                update_fields.append("avatar_data = ?")
                params.append(info['avatar_data'])
                
            # 总是更新profile_url和last_crawled_at
            update_fields.append("profile_url = ?")
            params.append(self._normalize_url_store(info.get('profile_url', '')))
            
            update_fields.append("last_crawled_at = ?")
            params.append(int(time.time()))
            
            if update_fields:
                query = f"UPDATE actors SET {', '.join(update_fields)} WHERE id = ?"
                params.append(actor_id)
                cur.execute(query, params)
                conn.commit()
                print(f"更新演员 ID {actor_id} 信息成功")
                return True
        except Exception as e:
            print(f"更新演员 ID {actor_id} 失败: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def process_all_javdb_actors(self, limit: int = None, min_actor_id: int = None, dry_run: bool = False):
        """处理所有有JavDB链接的演员"""
        print("开始获取所有有JavDB链接的演员...")
        actors = self.get_actors_with_javdb_links(limit, min_actor_id)
        
        if not actors:
            print("没有找到有JavDB链接的演员")
            return
            
        print(f"找到 {len(actors)} 个有JavDB链接的演员")
        
        # 设置干跑模式
        self.dry_run_mode = dry_run
        
        processed = 0
        updated = 0
        
        for i, actor in enumerate(actors, 1):
            actor_id = actor['id']
            name = actor['name'] or f"演员{actor_id}"
            profile_url = actor['profile_url']
            
            print(f"\n[{i}/{len(actors)}] 处理演员: {name} (ID: {actor_id})")
            print(f"  现有profile_url: {profile_url}")
            
            if dry_run:
                print("  [干跑模式] 跳过实际爬取和更新")
                processed += 1
                continue
                
            try:
                # 重新爬取演员信息
                print(f"  重新爬取演员信息...")
                info = self.fetch_actor_page(profile_url)
                
                if not info:
                    print(f"  爬取失败，跳过")
                    continue
                    
                # 下载头像数据（如果需要）
                if self.download_avatar and info.get('avatar_url'):
                    print(f"  下载头像...")
                    avatar_data = self.download_avatar_data(info['avatar_url'])
                    if avatar_data:
                        info['avatar_data'] = avatar_data
                        print(f"  头像下载成功，大小: {len(avatar_data)} bytes")
                    else:
                        print(f"  头像下载失败")
                
                # 更新数据库
                if self.update_actor_info(actor_id, info):
                    updated += 1
                    print(f"  更新成功")
                else:
                    print(f"  更新失败")
                    
                processed += 1
                
                # 随机延迟，避免过于频繁
                self.random_delay(2, 4)
                
            except Exception as e:
                print(f"  处理异常: {e}")
                continue
        
        print(f"\n处理完成！总计处理: {processed}, 更新成功: {updated}")

    def merge_duplicates_for_aliases(self, max_actor_id: int = 660, dry_run: bool = True):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT profile_url
            FROM actors
            WHERE id < ? AND aliases IS NOT NULL AND aliases != '' AND profile_url IS NOT NULL AND profile_url != ''
            GROUP BY profile_url
            """,
            (max_actor_id,)
        )
        rows = cur.fetchall()
        urls = [r[0] for r in rows if r and r[0]]
        processed = 0
        for purl in urls:
            cur.execute(
                """
                SELECT id, name, name_common, name_traditional, aliases, last_crawled_at, updated_at
                FROM actors
                WHERE profile_url = ?
                ORDER BY
                    CASE WHEN last_crawled_at IS NULL THEN 0 ELSE last_crawled_at END DESC,
                    updated_at DESC
                """,
                (purl,)
            )
            group_rows = cur.fetchall()
            if not group_rows:
                continue
            target = group_rows[0]
            target_id = target[0]
            target_names = set()
            for idx in [1, 2, 3]:
                if target[idx]:
                    target_names.update([n.strip() for n in str(target[idx]).split(',') if n.strip() and len(n.strip()) >= 2])
            alias_set = set()
            for r in group_rows[1:]:
                for idx in [1, 2, 3]:
                    if r[idx]:
                        alias_set.update([n.strip() for n in str(r[idx]).split(',') if n.strip() and len(n.strip()) >= 2])
                if r[4]:
                    alias_set.update([a.strip() for a in str(r[4]).split(',') if a.strip() and len(a.strip()) >= 2])
            alias_set -= target_names
            existing_aliases = set()
            if target[4]:
                existing_aliases.update([a.strip() for a in str(target[4]).split(',') if a.strip() and len(a.strip()) >= 2])
            final_aliases = ', '.join(sorted(existing_aliases.union(alias_set))) if (existing_aliases or alias_set) else ''
            if dry_run:
                print(f"[DRY] 合并组 profile_url={purl}，保留 id={target_id}，删除 {len(group_rows)-1} 条；更新 aliases='{final_aliases}'")
            else:
                cur.execute(
                    "UPDATE actors SET aliases = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (final_aliases, target_id)
                )
                ids_to_delete = []
                for r in group_rows[1:]:
                    sid = r[0]
                    cur.execute("UPDATE video_actors SET actor_id = ? WHERE actor_id = ?", (target_id, sid))
                    ids_to_delete.append(sid)
                if ids_to_delete:
                    cur.executemany("DELETE FROM actors WHERE id = ?", [(i,) for i in ids_to_delete])
                conn.commit()
                print(f"合并完成：profile_url={purl}，保留 id={target_id}，删除 {len(ids_to_delete)} 条，aliases 已更新")
            processed += 1
        print("重复记录合并阶段完成")


def main():
    parser = argparse.ArgumentParser(description="JavDB演员档案全量重新爬取工具")
    parser.add_argument("--db-path", default="media_library.db", help="SQLite数据库路径")
    parser.add_argument("--execute", action="store_true", help="实际执行写库操作（默认干跑）")
    parser.add_argument("--dry-run", action="store_true", help="干跑模式，不实际写库")
    parser.add_argument("--limit", type=int, help="限制处理的演员数量")
    parser.add_argument("--min-actor-id", type=int, help="最小演员ID过滤")
    parser.add_argument("--all-javdb-actors", action="store_true", help="重新爬取所有有JavDB链接的演员（本脚本主要功能）")
    parser.add_argument("--merge-duplicates-for-aliases", action="store_true", help="按profile_url合并并重写aliases（过滤条件）")
    parser.add_argument("--max-actor-id", type=int, default=660, help="按ID上限过滤用于合并的组")
    parser.add_argument("--no-download-avatar", action="store_true", help="不下载头像二进制数据")
    parser.add_argument("--no-proxy", action="store_true", help="禁用SOCKS5代理")
    parser.add_argument("--test-isolate-profile", action="store_true", help="单链测试时使用临时Edge用户数据目录")
    parser.add_argument("--prefer-insert", action="store_true", help="优先插入新记录而非更新（本脚本中不常用）")
    parser.add_argument("--disable-cover-fallback", action="store_true", help="禁用封面头像兜底逻辑")
    
    args = parser.parse_args()
    
    # 参数验证
    if args.execute and args.dry_run:
        print("错误: --execute 与 --dry-run 不能同时使用")
        sys.exit(1)
        
    if not args.execute and not args.dry_run:
        print("提示: 未指定 --execute 或 --dry-run，默认进入干跑模式")
        args.dry_run = True
    
    # 创建修复器实例
    repairer = JavdbActorRepair(
        db_path=args.db_path,
        download_avatar=not args.no_download_avatar,
        use_proxy=not args.no_proxy,
        prefer_insert=args.prefer_insert,
        use_temp_profile=args.test_isolate_profile,
        use_cover_fallback=not args.disable_cover_fallback
    )
    
    if args.merge_duplicates_for_aliases:
        repairer.merge_duplicates_for_aliases(max_actor_id=args.max_actor_id, dry_run=args.dry_run)
    else:
        repairer.process_all_javdb_actors(
            limit=args.limit,
            min_actor_id=args.min_actor_id,
            dry_run=args.dry_run
        )


if __name__ == "__main__":
    main()
