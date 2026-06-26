#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JavDB演员档案修复脚本

功能：
- 规范化 actors.profile_url 的域名为 https://javdb.com（例如 javdb573.com 改写为 javdb.com）
- 对非 JavDB 链接或空 profile_url 的记录，按演员名搜索 JavDB 并更新 profile_url 与基础信息
 - 对已是 JavDB 链接但头像二进制为空的记录，基于 profile_url 重新爬取头像（更新 avatar_url 并下载 avatar_data）
- 合并重复演员记录（按 profile_url）：
  - 以最近爬取过的记录为准（last_crawled_at 最新的作为主记录）
  - 将其他记录的名称合并到主记录的 aliases 字段中
  - 更新关联（video_actors），删除重复记录，仅保留主记录

运行示例：
- 干跑预览（不写库）：
  python javdb_actor_profile_repair.py --db-path media_library.db --dry-run --limit 50
- 实际写库（小范围验证）：
  python javdb_actor_profile_repair.py --db-path media_library.db --execute --limit 20

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
            proxy_domain = getattr(_cfg, 'JAVDB_PROXY_DOMAIN', 'javdb.com')
            direct_domain = getattr(_cfg, 'JAVDB_DIRECT_DOMAIN', 'javdb573.com')
            self.base_url = f"https://{proxy_domain if use_proxy else direct_domain}"
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
        # 去掉尾随的“数字+部影片/部作品”等计数噪音（保留纯净艺名）
        t = re.sub(r'[\s\u3000]*\d+\s*部(?:影片|作品)\b.*$', '', t)
        # 去掉常见分隔符后的附加信息
        t = re.sub(r'\s*[-|｜].*$', '', t)
        return t.strip()

    def _clean_actor_name(self, s: str) -> str:
        """提取纯净艺名：优先选取不含“部影片/部作品”的行，并移除尾随计数/附加信息。"""
        if not s:
            return ''
        lines = [x.strip() for x in re.split(r'[\r\n]+', s) if x.strip()]
        if not lines:
            return ''
        def _strip_noise(x: str) -> str:
            x = re.sub(r'[\s\u3000]*\d+\s*部(?:影片|作品)\b.*$', '', x)
            x = re.sub(r'\s*[-|｜].*$', '', x)
            return x.strip()
        # 先挑不含计数词的行
        for l in lines:
            if (('部影片' not in l) and ('部作品' not in l)):
                cleaned = _strip_noise(l)
                if cleaned:
                    return cleaned
        # 若全部为统计信息，返回空，不采集名称
        return ''

    def _classify_names(self, primary_names, alias_items):
        """根据字符类别分类名称：首个包含假名的为常用名，首个含中文的为繁体名，其余为别名。"""
        japanese_name = None
        traditional_name = None
        other_aliases = []
        # 用户规则：若存在第二行（别名列表），第一个通常是繁体名，剩下作为别名
        if alias_items:
            first_alias = alias_items[0]
            if first_alias:
                traditional_name = first_alias
            if len(alias_items) > 1:
                other_aliases.extend(alias_items[1:])
        # 合并所有候选名
        all_names = list(primary_names)
        # 若已设繁体名，避免重复加入到all_names
        for a in alias_items:
            if not traditional_name or a != traditional_name:
                all_names.append(a)

        for name in all_names:
            if not name:
                continue
            # 假名判定（平假名+片假名）
            if any('\u3040' <= ch <= '\u309f' or '\u30a0' <= ch <= '\u30ff' for ch in name):
                if not japanese_name:
                    japanese_name = name
                else:
                    other_aliases.append(name)
            # 中文判定（汉字范围）
            elif any('\u4e00' <= ch <= '\u9fff' for ch in name):
                if (not traditional_name) and (name not in (japanese_name or '')):
                    traditional_name = name
                else:
                    other_aliases.append(name)
            else:
                other_aliases.append(name)

        return japanese_name, traditional_name, other_aliases

    def fetch_actor_page(self, actor_url: str) -> dict:
        if not self.driver:
            self.setup_driver()
            if not self.driver:
                return None
        try:
            # 浏览用：将 URL 域名统一到当前 base_url（无代理为配置中的直连域名，有代理为 javdb.com）
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
                split_pattern = r"[,，、]\s*"
                raw_aliases = [self._normalize_name_token(a) for a in re.split(split_pattern, alias_text)]
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

            # 头像（增强版选择器与懒加载/srcset/背景图解析）
            try:
                def _pick_best_from_srcset(srcset: str) -> str:
                    if not srcset:
                        return ''
                    # 选择最后一个条目（通常为最高分辨率/2x）
                    parts = [p.strip() for p in srcset.split(',') if p.strip()]
                    if not parts:
                        return ''
                    last = parts[-1]
                    # 去掉尺寸或倍数标记（如 " 2x"、" 480w"）
                    url = last.split(' ')[0].strip()
                    return url

                def _complete_url(u: str) -> str:
                    try:
                        from urllib.parse import urljoin
                        if u and not str(u).startswith('http'):
                            return urljoin(self.base_url, u)
                        return u
                    except Exception:
                        return u

                avatar_url = ''

                # 优先等待常见 img 出现
                try:
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, '.actor-avatar img, .avatar img, .actor-info .avatar img, picture source[srcset], picture img'))
                    )
                except Exception:
                    pass

                # 依次尝试图片元素
                candidates = []
                try:
                    candidates.extend(self.driver.find_elements(By.CSS_SELECTOR, '.actor-avatar img, .avatar img, .actor-info .avatar img, .actor-section .photo img'))
                except Exception:
                    pass
                try:
                    # picture/source 结构
                    candidates.extend(self.driver.find_elements(By.CSS_SELECTOR, 'picture source[srcset], picture img'))
                except Exception:
                    pass

                # 懒加载属性与 src/srcset 解析
                for el in candidates:
                    try:
                        tag = (el.tag_name or '').lower()
                        src = el.get_attribute('src') or ''
                        srcset = el.get_attribute('srcset') or ''
                        data_src = el.get_attribute('data-src') or ''
                        data_original = el.get_attribute('data-original') or ''
                        data_lazy = el.get_attribute('data-lazy') or ''
                        lazy_src = el.get_attribute('lazy-src') or ''

                        # 如果 src 为空，尝试等待其填充
                        if tag == 'img' and not src:
                            try:
                                WebDriverWait(self.driver, 5).until(lambda d: (el.get_attribute('src') or el.get_attribute('data-src') or el.get_attribute('data-original')))
                                src = el.get_attribute('src') or ''
                                data_src = el.get_attribute('data-src') or data_src
                                data_original = el.get_attribute('data-original') or data_original
                            except Exception:
                                pass

                        chosen = ''
                        if srcset:
                            chosen = _pick_best_from_srcset(srcset)
                        if not chosen:
                            chosen = src or data_src or data_original or data_lazy or lazy_src
                        if chosen:
                            avatar_url = _complete_url(chosen)
                            if avatar_url:
                                break
                    except Exception:
                        continue

                # 背景图样式作为回退方案
                if not avatar_url:
                    bg_candidates = []
                    try:
                        bg_candidates.extend(self.driver.find_elements(By.CSS_SELECTOR, '.actor-avatar, .avatar, .actor-cover, .actor-profile .avatar'))
                    except Exception:
                        pass
                    for el in bg_candidates:
                        try:
                            style = el.get_attribute('style') or ''
                            if style and 'background' in style:
                                import re as _re
                                m = _re.search(r'url\((\"|\'|)(.+?)(\1)\)', style)
                                if m:
                                    avatar_url = _complete_url(m.group(2))
                                    break
                            # 计算样式
                            try:
                                bg = self.driver.execute_script('return window.getComputedStyle(arguments[0]).getPropertyValue("background-image")', el)
                                if bg and 'url(' in bg:
                                    import re as _re
                                    m = _re.search(r'url\((\"|\'|)(.+?)(\1)\)', bg)
                                    if m:
                                        avatar_url = _complete_url(m.group(2))
                                        break
                            except Exception:
                                pass
                        except Exception:
                            continue

                if avatar_url:
                    info['avatar_url'] = avatar_url
                else:
                    print('未能提取头像：未匹配到 img/srcset/懒加载或背景图样式')
            except Exception as _e:
                print(f'提取头像异常：{_e}')
                pass
            return info
        except Exception as e:
            print(f"抓取演员页面异常: {e}")
            return None

    def fetch_actor_page_http(self, actor_url: str) -> dict:
        """无需浏览器的快速HTTP解析，用于测试回退：尝试从HTML中解析头像与名称。"""
        try:
            url = self._normalize_url(actor_url)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,ja;q=0.7',
                'Referer': self.base_url,
                'Connection': 'keep-alive'
            }
            html = ''
            last_err = None
            for _ in range(2):
                try:
                    req = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        html = resp.read().decode('utf-8', 'ignore')
                    break
                except Exception as _e:
                    last_err = _e
                    time.sleep(random.uniform(0.8, 1.5))
            if not html:
                raise last_err or Exception('Empty HTML')
            info = {'profile_url': url}
            # 头像URL提取（正则匹配 jdbstatic avatars）
            try:
                import re as _re
                # 尝试 srcset 中的最高分辨率
                m = _re.search(r'srcset\s*=\s*"([^"]*jdbstatic\.com[^"]+)"', html, flags=_re.IGNORECASE)
                chosen = None
                if m:
                    parts = [p.strip() for p in m.group(1).split(',') if p.strip()]
                    if parts:
                        chosen = parts[-1].split(' ')[0].strip()
                if not chosen:
                    m2 = _re.search(r'src\s*=\s*"(https?://[^"]*jdbstatic\.com[^"]+)"', html, flags=_re.IGNORECASE)
                    if m2:
                        chosen = m2.group(1)
                if not chosen:
                    m3 = _re.search(r'url\((\"|\'|)(https?://[^\)\"\']*jdbstatic\.com[^\)\"\']*)(\1)\)', html, flags=_re.IGNORECASE)
                    if m3:
                        chosen = m3.group(2)
                if chosen:
                    info['avatar_url'] = chosen
            except Exception:
                pass
            # 名称与别名粗略提取（按两行规则：第一行中文+common，第二行全部别名）
            try:
                import re as _re
                name_block = ''
                m0 = _re.search(r'<div[^>]*class=["\']?actor-section-name["\']?[^>]*>(.*?)</div>', html, flags=_re.IGNORECASE|_re.DOTALL)
                if m0:
                    name_block = m0.group(1)
                else:
                    m1 = _re.search(r'<h1[^>]*class=["\']?title["\']?[^>]*>(.*?)</h1>', html, flags=_re.IGNORECASE|_re.DOTALL)
                    if m1:
                        name_block = m1.group(1)
                if name_block:
                    # 保留换行用于两行规则
                    text = _re.sub(r'<br\s*/?>', '\n', name_block, flags=_re.IGNORECASE)
                    text = _re.sub(r'<[^>]+>', '', text).strip()
                    lines = [l.strip() for l in re.split(r"[\r\n]+", text) if l.strip()]
                    def _strip_noise_line(x: str) -> str:
                        x = re.sub(r"[\s\u3000]*\d+\s*部(?:影片|作品)\b.*$", "", x)
                        x = re.sub(r"\s*[-|｜].*$", "", x)
                        return x.strip()
                    lines = [_strip_noise_line(l) for l in lines]
                    first = lines[0] if lines else ''
                    others = lines[1:] if len(lines) > 1 else []
                    comma_split = r"[,，、]\s*"
                    tokens1 = [self._normalize_name_token(t) for t in (re.split(comma_split, first) if first else [])]
                    tokens1 = [t for t in tokens1 if t]
                    alias_list = []
                    if len(tokens1) >= 2:
                        info['name_traditional'] = tokens1[0]
                        info['name'] = tokens1[1]
                        info['name_common'] = tokens1[1]
                        for t in tokens1:
                            if t != info['name_common']:
                                alias_list.append(t)
                    elif len(tokens1) == 1:
                        info['name'] = tokens1[0]
                        info['name_common'] = tokens1[0]
                        info['name_traditional'] = tokens1[0]
                    for line_i in others:
                        for t in re.split(comma_split, line_i):
                            norm = self._normalize_name_token(t)
                            if norm:
                                alias_list.append(norm)
                    if alias_list:
                        excluded = {info.get('name_common')}
                        dedup = []
                        seen = set()
                        for a in alias_list:
                            if a and a not in excluded and a not in seen:
                                dedup.append(a)
                                seen.add(a)
                        if dedup:
                            info['aliases'] = ', '.join(dedup)
            except Exception:
                pass
            try:
                import re as _re
                m2 = _re.search(r'<(div|span)[^>]*class=["\']?(section-meta|sub-title)["\']?[^>]*>(.*?)</\1>', html, flags=_re.IGNORECASE|_re.DOTALL)
                if m2:
                    txt = _re.sub(r'<[^>]+>', '', m2.group(3)).strip()
                    raw_aliases = [self._normalize_name_token(a) for a in re.split(r"[,，、]\s*", txt)]
                    raw_aliases = [a for a in raw_aliases if a]
                    if raw_aliases:
                        excluded = {info.get('name_common')}
                        dedup = []
                        seen = set()
                        for a in raw_aliases:
                            if a and a not in excluded and a not in seen:
                                dedup.append(a)
                                seen.add(a)
                        if dedup:
                            info['aliases'] = ', '.join(dedup)
            except Exception:
                pass
            return info
        except Exception as _e:
            print(f"HTTP解析失败: {_e}")
            return None

    def update_profile_url(self, actor_id: int, new_url: str, cursor, conn, dry_run: bool):
        # 入库前将URL统一归一到 javdb.com 主域名
        new_url = self._normalize_url_store(new_url)
        if dry_run:
            print(f"[DRY] 更新 profile_url: id={actor_id} => {new_url}")
            return True
        cursor.execute("UPDATE actors SET profile_url = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_url, actor_id))
        conn.commit()
        return True

    def update_avatar_url(self, actor_id: int, avatar_url: str, cursor, conn, dry_run: bool):
        if dry_run:
            print(f"[DRY] 更新 avatar_url: id={actor_id} => {avatar_url}")
            return True
        cursor.execute("UPDATE actors SET avatar_url = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (avatar_url, actor_id))
        conn.commit()
        return True

    def update_avatar_data(self, actor_id: int, avatar_bytes: bytes, cursor, conn, dry_run: bool):
        if avatar_bytes is None:
            return False
        if dry_run:
            print(f"[DRY] 更新 avatar_data: id={actor_id} => {len(avatar_bytes)} bytes")
            return True
        cursor.execute("UPDATE actors SET avatar_data = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (sqlite3.Binary(avatar_bytes), actor_id))
        conn.commit()
        return True

    def touch_last_crawled(self, actor_id: int, cursor, conn, dry_run: bool):
        """在抓取尝试后更新 last_crawled_at 时间戳，无论头像是否成功下载。"""
        if dry_run:
            print(f"[DRY] 更新 last_crawled_at: id={actor_id} => NOW")
            return True
        cursor.execute("UPDATE actors SET last_crawled_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (actor_id,))
        conn.commit()
        return True

    def download_avatar_bytes(self, url: str) -> bytes:
        try:
            if not url:
                return None
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
                'Referer': self.base_url,
                'Connection': 'keep-alive'
            }
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read()
        except Exception:
            return None

    def process(self, limit: int = None, dry_run: bool = True, select_not_crawled: bool = False, min_actor_id: int = None):
        """
        核心修复流程
        【区别】分阶段处理：
        1. 规范化替代域名 (javdbNNN -> javdb.com)
        2. 搜索并修复无效/缺失的 profile_url (repair_all 脚本跳过此步骤)
        """
        # 记录干跑模式，用于缩短等待与跳过动作
        self.dry_run_mode = bool(dry_run)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Phase A: 规范化替代域名
        if min_actor_id is not None:
            cursor.execute("SELECT id, name, profile_url FROM actors WHERE id >= ? AND profile_url LIKE '%javdb%' AND profile_url NOT LIKE '%javdb.com%'", (min_actor_id,))
        else:
            cursor.execute("SELECT id, name, profile_url FROM actors WHERE profile_url LIKE '%javdb%' AND profile_url NOT LIKE '%javdb.com%'")
        rows_alt = cursor.fetchall()
        print(f"发现替代域名的 JavDB 链接: {len(rows_alt)} 条")
        total_alt_display = (min(len(rows_alt), limit) if limit else len(rows_alt))
        count = 0
        for actor_id, name, purl in rows_alt:
            if limit and count >= limit:
                break
            progress_index = count + 1
            try:
                print(f"[{progress_index}/{total_alt_display}] 处理替代域名: {name} (id={actor_id})")
            except Exception:
                pass
            new_url = canonicalize_javdb_url(purl)
            if new_url != purl:
                print(f"规范化: {name} (id={actor_id}) {purl} => {new_url}")
                self.update_profile_url(actor_id, new_url, cursor, conn, dry_run)
            count += 1

        # Phase B: 非 JavDB 或空 profile_url => 搜索并更新（可选插入）
        if min_actor_id is not None:
            cursor.execute("SELECT id, name, profile_url FROM actors WHERE id >= ? AND (profile_url IS NULL OR profile_url = '' OR profile_url NOT LIKE '%javdb%')", (min_actor_id,))
        else:
            cursor.execute("SELECT id, name, profile_url FROM actors WHERE profile_url IS NULL OR profile_url = '' OR profile_url NOT LIKE '%javdb%'")
        rows_non = cursor.fetchall()
        print(f"非 JavDB 链接或空 profile_url 的记录: {len(rows_non)} 条")
        total_non_display = (min(len(rows_non), limit) if limit else len(rows_non))
        count = 0
        for actor_id, name, purl in rows_non:
            if limit and count >= limit:
                break
            progress_index = count + 1
            try:
                print(f"[{progress_index}/{total_non_display}] 搜索并更新: {name} (id={actor_id})")
            except Exception:
                pass
            if not name:
                continue
            actor_url = self.search_actor_on_javdb(name)
            if actor_url:
                info = self.fetch_actor_page(actor_url) or {}
                new_url_fetch = info.get('profile_url') or actor_url
                # 存储统一规范化到 javdb.com
                new_url_store = self._normalize_url_store(new_url_fetch)
                # 若开启prefer_insert且库内不存在该profile_url，插入新记录
                cursor.execute("SELECT id FROM actors WHERE profile_url = ?", (new_url_store,))
                existing = cursor.fetchone()
                if self.prefer_insert and (not existing):
                    # 准备插入信息（确保使用存储规范化URL）
                    info_to_insert = dict(info)
                    info_to_insert['profile_url'] = new_url_store
                    if dry_run:
                        print(f"[DRY] 插入新演员记录（prefer_insert启用）: name={info_to_insert.get('name')} url={info_to_insert.get('profile_url')}")
                    else:
                        self.add_actor_to_database(info_to_insert)
                else:
                    # 默认行为：更新当前记录的profile_url
                    self.update_profile_url(actor_id, new_url_store, cursor, conn, dry_run)
                avatar_url = info.get('avatar_url')
                if avatar_url:
                    self.update_avatar_url(actor_id, avatar_url, cursor, conn, dry_run)
                    if self.download_avatar:
                        data = self.download_avatar_bytes(avatar_url)
                        self.update_avatar_data(actor_id, data, cursor, conn, dry_run)
                # 更新名称与别名（若有）
                update_fields = []
                update_params = []
                if info.get('name_common'):
                    update_fields.append("name_common = ?")
                    update_params.append(info['name_common'])
                if info.get('name_traditional'):
                    update_fields.append("name_traditional = ?")
                    update_params.append(info['name_traditional'])
                if info.get('aliases'):
                    update_fields.append("aliases = ?")
                    update_params.append(info['aliases'])
                if update_fields:
                    if dry_run:
                        print(f"[DRY] 更新名称/别名: id={actor_id} => {', '.join(update_fields)}")
                    else:
                        cursor.execute(f"UPDATE actors SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", update_params + [actor_id])
                        conn.commit()
                # 抓取尝试后更新 last_crawled_at
                self.touch_last_crawled(actor_id, cursor, conn, dry_run)
            else:
                print(f"未在 JavDB 找到演员：{name} (id={actor_id})")
            count += 1

        # Phase C: 选择待抓取的 JavDB 演员
        if select_not_crawled:
            if min_actor_id is not None:
                cursor.execute("SELECT id, name, profile_url, avatar_url FROM actors WHERE id >= ? AND profile_url LIKE '%javdb%' AND (last_crawled_at IS NULL OR TRIM(last_crawled_at)='')", (min_actor_id,))
            else:
                cursor.execute("SELECT id, name, profile_url, avatar_url FROM actors WHERE profile_url LIKE '%javdb%' AND (last_crawled_at IS NULL OR TRIM(last_crawled_at)='')")
            rows_empty_avatar = cursor.fetchall()
            print(f"JavDB 链接但未抓取过的记录: {len(rows_empty_avatar)} 条")
        else:
            if min_actor_id is not None:
                cursor.execute("SELECT id, name, profile_url, avatar_url FROM actors WHERE id >= ? AND profile_url LIKE '%javdb%' AND (avatar_data IS NULL OR length(avatar_data)=0)", (min_actor_id,))
            else:
                cursor.execute("SELECT id, name, profile_url, avatar_url FROM actors WHERE profile_url LIKE '%javdb%' AND (avatar_data IS NULL OR length(avatar_data)=0)")
            rows_empty_avatar = cursor.fetchall()
            print(f"JavDB 链接但头像二进制为空的记录: {len(rows_empty_avatar)} 条")
        total_c_display = (min(len(rows_empty_avatar), limit) if limit else len(rows_empty_avatar))
        count = 0
        for actor_id, name, purl, aurl in rows_empty_avatar:
            if limit and count >= limit:
                break
            progress_index = count + 1
            try:
                print(f"[{progress_index}/{total_c_display}] 头像处理: {name} (id={actor_id})")
            except Exception:
                pass
            if not purl:
                continue
            info = self.fetch_actor_page(purl) or {}
            # 优先使用页面解析的新头像 URL；若未解析到则回退使用数据库中的现有 URL 进行二进制回填
            avatar_url_new = info.get('avatar_url')
            avatar_url_existing = aurl
            if avatar_url_new:
                self.update_avatar_url(actor_id, avatar_url_new, cursor, conn, dry_run)
                if self.download_avatar:
                    data = self.download_avatar_bytes(avatar_url_new)
                    if not data and avatar_url_existing:
                        data = self.download_avatar_bytes(avatar_url_existing)
                    self.update_avatar_data(actor_id, data, cursor, conn, dry_run)
            else:
                # 未能解析到新 URL，尝试用现有 URL 下载二进制
                fallback_needed = True
                if avatar_url_existing and self.download_avatar:
                    data = self.download_avatar_bytes(avatar_url_existing)
                    if data:
                        self.update_avatar_data(actor_id, data, cursor, conn, dry_run)
                        fallback_needed = False
                    else:
                        print(f"未能下载头像二进制：{name} (id={actor_id})")
                else:
                    print(f"未能提取头像 URL：{name} (id={actor_id})")

                # 封面兜底：从含“單體作品”标签的视频封面提取正面头像
                if fallback_needed and self.use_cover_fallback and not dry_run:
                    try:
                        cover_face_bytes = self.extract_avatar_from_covers_for_actor(actor_id)
                        if cover_face_bytes:
                            ok = self.update_avatar_data(actor_id, cover_face_bytes, cursor, conn, dry_run)
                            if ok:
                                print(f"✓ 已从封面提取头像并写入：{name} (id={actor_id})")
                            else:
                                print(f"✗ 从封面提取头像失败（写库失败）：{name} (id={actor_id})")
                        else:
                            print(f"✗ 从封面未能提取有效人脸：{name} (id={actor_id})")
                    except Exception as _fe:
                        print(f"封面兜底提取异常：{name} (id={actor_id}) => {_fe}")
            # 抓取尝试后更新 last_crawled_at
            self.touch_last_crawled(actor_id, cursor, conn, dry_run)
            # 同步名称与别名（若页面有提供）
            update_fields = []
            update_params = []
            if info.get('name_common'):
                update_fields.append("name_common = ?")
                update_params.append(info['name_common'])
            if info.get('name_traditional'):
                update_fields.append("name_traditional = ?")
                update_params.append(info['name_traditional'])
            if info.get('aliases'):
                update_fields.append("aliases = ?")
                update_params.append(info['aliases'])
            if update_fields:
                if dry_run:
                    print(f"[DRY] 更新名称/别名: id={actor_id} => {', '.join(update_fields)}")
                else:
                    cursor.execute(f"UPDATE actors SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", update_params + [actor_id])
                    conn.commit()
            count += 1

        # Phase D: 合并具有相同 profile_url 的重复演员记录
        try:
            self.merge_duplicates_by_profile_url(cursor, conn, limit=limit, dry_run=dry_run)
        except Exception as e:
            print(f"合并重复记录阶段异常: {e}")
        finally:
            conn.close()
        print("\n🎉 修复流程完成！")

    # === 封面头像兜底逻辑 ===
    def _init_face_detectors(self):
        if not hasattr(self, '_face_cascade'):
            self._face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        if not hasattr(self, '_eye_cascade'):
            self._eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')

    def _calculate_face_quality(self, face_img, face_rect, original_img):
        x, y, w, h = face_rect
        size_score = w * h
        gray_face = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY) if len(face_img.shape) == 3 else face_img
        laplacian_var = cv2.Laplacian(gray_face, cv2.CV_64F).var()
        eyes = self._eye_cascade.detectMultiScale(gray_face, 1.1, 5)
        frontal_score = len(eyes) * 100
        img_center_x = original_img.shape[1] // 2
        img_center_y = original_img.shape[0] // 2
        face_center_x = x + w // 2
        face_center_y = y + h // 2
        distance_from_center = np.sqrt((face_center_x - img_center_x)**2 + (face_center_y - img_center_y)**2)
        position_score = 1000 / (1 + distance_from_center)
        total_score = size_score * 0.3 + laplacian_var * 0.4 + frontal_score * 0.2 + position_score * 0.1
        return total_score, {
            'size': size_score,
            'clarity': laplacian_var,
            'frontal': frontal_score,
            'position': position_score,
            'total': total_score,
        }

    def _compare_faces(self, face1, face2):
        face1_resized = cv2.resize(face1, (128, 128))
        face2_resized = cv2.resize(face2, (128, 128))
        face1_gray = cv2.cvtColor(face1_resized, cv2.COLOR_BGR2GRAY)
        face2_gray = cv2.cvtColor(face2_resized, cv2.COLOR_BGR2GRAY)
        hist1 = cv2.calcHist([face1_gray], [0], None, [256], [0, 256])
        hist2 = cv2.calcHist([face2_gray], [0], None, [256], [0, 256])
        hist1 = cv2.normalize(hist1, hist1).flatten()
        hist2 = cv2.normalize(hist2, hist2).flatten()
        similarity = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)
        return similarity

    def _cluster_faces(self, faces_with_info, similarity_threshold=0.6):
        clusters = []
        for face_info in faces_with_info:
            face_img, score_info, original_meta, face_rect = face_info
            added_to_cluster = False
            for i, cluster in enumerate(clusters):
                best_face_in_cluster = cluster["face_img"]
                similarity = self._compare_faces(face_img, best_face_in_cluster)
                if similarity > similarity_threshold:
                    if score_info['total'] > cluster["score_info"]['total']:
                        clusters[i] = {
                            "face_img": face_img,
                            "score_info": score_info,
                            "original_meta": original_meta,
                            "face_rect": face_rect,
                            "cluster_id": i
                        }
                    added_to_cluster = True
                    break
            if not added_to_cluster:
                clusters.append({
                    "face_img": face_img,
                    "score_info": score_info,
                    "original_meta": original_meta,
                    "face_rect": face_rect,
                    "cluster_id": len(clusters)
                })
        return clusters

    def _detect_faces_in_image(self, img, origin_meta):
        self._init_face_detectors()
        faces_with_info = []
        try:
            if img is None:
                return faces_with_info
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            faces = self._face_cascade.detectMultiScale(
                gray, 
                scaleFactor=1.1, 
                minNeighbors=5, 
                minSize=(50, 50),
                flags=cv2.CASCADE_SCALE_IMAGE
            )
            for face_rect in faces:
                x, y, w, h = face_rect
                face_img_cropped = img[y:y+h, x:x+w]
                score, score_info = self._calculate_face_quality(face_img_cropped, face_rect, img)
                # 只保留正面（至少检测到一只眼睛）
                if score_info['frontal'] > 0:
                    # 扩展边界以获得更好的头像效果
                    padding = int(min(w, h) * 0.3)
                    x1 = max(0, x - padding)
                    y1 = max(0, y - padding)
                    x2 = min(img.shape[1], x + w + padding)
                    y2 = min(img.shape[0], y + h + padding)
                    face_img = img[y1:y2, x1:x2]
                    faces_with_info.append((face_img, score_info, origin_meta, face_rect))
        except Exception:
            pass
        return faces_with_info

    def _decode_image_bytes(self, blob_bytes):
        try:
            nparr = np.frombuffer(blob_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            return img
        except Exception:
            return None

    def _read_image_from_path(self, path):
        try:
            if path and os.path.exists(path):
                return cv2.imread(path)
        except Exception:
            pass
        return None

    def _find_local_poster(self, video_file_path):
        # 简易回退：查找同目录下 poster.jpg/png
        try:
            if not video_file_path:
                return None
            folder = os.path.dirname(video_file_path)
            for name in ["poster.jpg", "poster.png", "cover.jpg", "cover.png"]:
                candidate = os.path.join(folder, name)
                if os.path.exists(candidate):
                    return candidate
        except Exception:
            pass
        return None

    def _get_actor_single_work_cover_images(self, actor_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        images = []
        try:
            cursor.execute(
                """
                SELECT j.cover_image_data, j.local_cover_path, v.file_path
                FROM video_actors va
                JOIN videos v ON v.id = va.video_id
                JOIN javdb_info j ON j.video_id = v.id
                JOIN javdb_info_tags jit ON jit.javdb_info_id = j.id
                JOIN javdb_tags t ON t.id = jit.tag_id
                WHERE va.actor_id = ? AND (t.tag_name = '單體作品' OR t.tag_name LIKE '%單體作品%')
                """,
                (actor_id,)
            )
            rows = cursor.fetchall()
            for cover_blob, local_path, video_path in rows:
                img = None
                if cover_blob:
                    img = self._decode_image_bytes(cover_blob)
                if img is None and local_path:
                    img = self._read_image_from_path(local_path)
                if img is None:
                    poster = self._find_local_poster(video_path)
                    if poster:
                        img = self._read_image_from_path(poster)
                if img is not None:
                    images.append((img, {"source": local_path or "blob", "video_path": video_path}))
        except Exception:
            pass
        finally:
            conn.close()
        return images

    def extract_avatar_from_covers_for_actor(self, actor_id):
        # 汇总封面人脸并聚类选择最佳头像
        images_meta = self._get_actor_single_work_cover_images(actor_id)
        if not images_meta:
            return None
        all_faces = []
        for img, meta in images_meta:
            faces = self._detect_faces_in_image(img, meta)
            if faces:
                all_faces.extend(faces)
        if not all_faces:
            return None
        clusters = self._cluster_faces(all_faces, similarity_threshold=0.6)
        if not clusters:
            return None
        # 选择最具代表性的聚类：按最佳人脸的总分排序
        clusters_sorted = sorted(clusters, key=lambda c: c['score_info']['total'], reverse=True)
        best_cluster = clusters_sorted[0]
        face_img = best_cluster['face_img']
        face_resized = cv2.resize(face_img, (128, 128), interpolation=cv2.INTER_LANCZOS4)
        success, encoded = cv2.imencode('.jpg', face_resized)
        if success:
            return encoded.tobytes()
        return None

    def add_actor_to_database(self, actor_info):
        """插入新演员记录（统一存储profile_url为javdb.com域名）。
        actor_info: dict 包含至少 name 与 profile_url；可选 name_common、name_traditional、aliases、avatar_url
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            purl = self._normalize_url_store(actor_info.get('profile_url') or '')
            # 若已有相同profile_url则直接返回该ID
            if purl:
                cursor.execute("SELECT id FROM actors WHERE profile_url = ?", (purl,))
                row = cursor.fetchone()
                if row:
                    print(f"演员已存在，ID={row[0]}，跳过插入")
                    return row[0]

            avatar_data_val = None
            if self.download_avatar and actor_info.get('avatar_url'):
                avatar_data_val = self.download_avatar_bytes(actor_info.get('avatar_url'))

            cursor.execute(
                """
                INSERT INTO actors (
                    name, name_common, name_traditional, aliases,
                    avatar_url, avatar_data, profile_url,
                    created_at, updated_at, last_crawled_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (
                    actor_info.get('name', '') or '',
                    actor_info.get('name_common', actor_info.get('name', '') or ''),
                    actor_info.get('name_traditional', actor_info.get('name', '') or ''),
                    actor_info.get('aliases', '') or '',
                    actor_info.get('avatar_url'),
                    sqlite3.Binary(avatar_data_val) if avatar_data_val is not None else None,
                    purl or actor_info.get('profile_url'),
                )
            )
            new_id = cursor.lastrowid
            conn.commit()
            print(f"成功插入新演员记录，ID={new_id}")
            return new_id
        except Exception as e:
            print(f"插入新演员失败: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()

    def merge_duplicates_by_profile_url(self, cursor, conn, limit: int = None, dry_run: bool = True):
        """按 profile_url 合并重复演员记录：
        - 选择 last_crawled_at 最新的作为主记录
        - 将其他记录的名称并入主记录的 aliases 字段
        - 更新 video_actors 关联并删除重复记录
        """
        cursor.execute("""
            SELECT profile_url
            FROM actors
            WHERE profile_url IS NOT NULL AND TRIM(profile_url) != ''
            GROUP BY profile_url
            HAVING COUNT(*) > 1
        """)
        groups = cursor.fetchall()
        print(f"需要合并的重复组: {len(groups)}")
        processed = 0
        for (purl,) in groups:
            if limit and processed >= limit:
                break
            # 选主记录：last_crawled_at 最新，其次 updated_at 最新
            cursor.execute(
                """
                SELECT id, name, name_common, name_traditional, aliases, last_crawled_at, updated_at
                FROM actors
                WHERE profile_url = ?
                ORDER BY 
                    CASE WHEN last_crawled_at IS NULL THEN 1 ELSE 0 END,
                    last_crawled_at DESC,
                    updated_at DESC
                """,
                (purl,)
            )
            rows = cursor.fetchall()
            if not rows or len(rows) < 2:
                continue
            target = rows[0]
            target_id = target[0]
            # 主记录已有名称集合
            target_names = set()
            for idx in [1, 2, 3]:
                if target[idx]:
                    target_names.update([n.strip() for n in str(target[idx]).split(',') if n.strip()])

            # 收集重复记录的名称与别名
            alias_set = set()
            for r in rows[1:]:
                for idx in [1, 2, 3]:
                    if r[idx]:
                        alias_set.update([n.strip() for n in str(r[idx]).split(',') if n.strip()])
                if r[4]:
                    alias_set.update([a.strip() for a in str(r[4]).split(',') if a.strip()])

            # 去除与主名称重复
            alias_set -= target_names

            # 合并到主记录的 aliases（保留现有 aliases）
            existing_aliases = set()
            if target[4]:
                existing_aliases.update([a.strip() for a in str(target[4]).split(',') if a.strip()])
            final_aliases = ', '.join(sorted(existing_aliases.union(alias_set))) if (existing_aliases or alias_set) else ''

            if dry_run:
                print(f"[DRY] 合并组 profile_url={purl}，保留 id={target_id}，删除 {len(rows)-1} 条；更新 aliases='{final_aliases}'")
            else:
                # 更新主记录的别名
                cursor.execute(
                    "UPDATE actors SET aliases = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (final_aliases, target_id)
                )
                # 更新关联并删除重复记录
                ids_to_delete = []
                for r in rows[1:]:
                    sid = r[0]
                    cursor.execute("UPDATE video_actors SET actor_id = ? WHERE actor_id = ?", (target_id, sid))
                    ids_to_delete.append(sid)
                cursor.executemany("DELETE FROM actors WHERE id = ?", [(i,) for i in ids_to_delete])
                conn.commit()
                print(f"合并完成：profile_url={purl}，保留 id={target_id}，删除 {len(ids_to_delete)} 条，aliases 已更新")
            processed += 1
        print("重复记录合并阶段完成")


def main():
    parser = argparse.ArgumentParser(description="JavDB演员档案修复：规范化域名、别名解析与补抓空头像")
    parser.add_argument("--db-path", default="media_library.db", help="数据库路径")
    parser.add_argument("--dry-run", action="store_true", help="仅预览不写库")
    parser.add_argument("--execute", action="store_true", help="执行写库（与 --dry-run 互斥）")
    parser.add_argument("--limit", type=int, default=None, help="每阶段最多处理条数（避免一次处理过多）")
    parser.add_argument("--min-actor-id", type=int, default=None, help="演员ID最小值过滤：忽略 id 小于该值的记录")
    parser.add_argument("--no-download-avatar", action="store_true", help="禁用头像二进制下载，仅更新 avatar_url")
    parser.add_argument("--select-not-crawled", action="store_true", help="阶段C改为按 last_crawled_at 为空选择需要抓取的演员，而非按缺头像")
    parser.add_argument("--no-proxy", action="store_true", help="禁用SOCKS5代理，直接无代理访问")
    parser.add_argument("--prefer-insert", action="store_true", help="当搜索到新profile且库中不存在时插入新记录（默认更新现有记录）")
    parser.add_argument("--test-actor-url", dest="test_actor_url", default="", help="测试单演员个人页链接（如 https://javdb573.com/actors/V2z2），解析并打印头像/名称后退出")
    parser.add_argument("--test-isolate-profile", action="store_true", help="单链测试时使用临时独立的Edge用户数据目录（避免并发占用）")
    parser.add_argument("--disable-cover-fallback", action="store_true", help="禁用封面头像兜底逻辑（默认启用）")
    args = parser.parse_args()

    if args.execute and args.dry_run:
        print("参数冲突：--execute 与 --dry-run 不能同时使用")
        sys.exit(1)
    dry_run = not args.execute

    print("JavDB演员档案修复脚本")
    print(f"数据库: {args.db_path}")
    print("模式: 预览模式" if dry_run else "模式: 执行写库")

    # 单链接测试是否启用临时Profile由参数控制，默认复用统一目录以提高登录成功率
    use_temp_profile = True if args.test_isolate_profile else False
    repair = JavdbActorRepair(db_path=args.db_path, download_avatar=(not args.no_download_avatar), use_proxy=not args.no_proxy, prefer_insert=args.prefer_insert, use_temp_profile=use_temp_profile, use_cover_fallback=(not args.disable_cover_fallback))
    try:
        # 单链接测试模式：仅抓取并打印该演员页信息
        if args.test_actor_url:
            # 启用干跑/测试模式以缩短等待与跳过人类动作
            repair.dry_run_mode = True
            url = args.test_actor_url.strip()
            print(f"单链接测试: {url}")
            info = repair.fetch_actor_page(url) or {}
            if not (info.get('avatar_url') or info.get('name')):
                print("Selenium解析未获得头像或名称，尝试HTTP回退解析…")
                info = repair.fetch_actor_page_http(url) or info
            print("测试结果：")
            print(f"  profile_url: {info.get('profile_url')}")
            print(f"  name: {info.get('name')}")
            print(f"  name_common: {info.get('name_common')}")
            print(f"  name_traditional: {info.get('name_traditional')}")
            print(f"  aliases: {info.get('aliases')}")
            print(f"  avatar_url: {info.get('avatar_url')}")
            return
        
        repair.process(limit=args.limit, dry_run=dry_run, select_not_crawled=args.select_not_crawled, min_actor_id=args.min_actor_id)
    finally:
        try:
            if hasattr(repair, 'driver') and repair.driver:
                repair.driver.quit()
                print("WebDriver 已关闭")
        except Exception:
            pass


if __name__ == "__main__":
    main()
