#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
收藏演员作品爬虫 - 爬取JAVDB收藏演员的作品列表，对比本地数据库标注未下载作品
支持断点续爬、增量更新，输出 CSV 格式结果
默认使用续爬模式，CSV文件固定名称
"""

import time
import random
import re
import csv
import sqlite3
import os
import sys
import argparse
from urllib.parse import urljoin, urlparse
from datetime import datetime
from contextlib import suppress

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
except Exception:
    sync_playwright = None
    PlaywrightTimeoutError = Exception

from config import SOCKS5_PROXY_HOST, SOCKS5_PROXY_PORT, get_javdb_base_url, USE_SOCKS5_PROXY, JAVDB_ALTERNATE_DIRECT_DOMAINS, JAVDB_DIRECT_DOMAIN, JAVDB_PROXY_DOMAIN, MIN_DELAY, MAX_DELAY

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'media_library.db')
RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')
DEFAULT_CSV_PATH = os.path.join(RESULTS_DIR, 'favorite_actor_works.csv')
os.makedirs(RESULTS_DIR, exist_ok=True)

REQUEST_LANGUAGE = "zh-CN,zh;q=0.9,ja;q=0.8,en;q=0.7"
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"


def random_delay(min_seconds=1.0, max_seconds=3.0):
    delay = random.uniform(min_seconds, max_seconds)
    time.sleep(delay)


def simulate_human_behavior(page):
    try:
        viewport = page.viewport_size or {"width": 1280, "height": 800}
        scroll_y = random.randint(100, 300)
        page.evaluate(f"window.scrollBy(0, {scroll_y})")
        random_delay(0.5, 1.5)
        scroll_y2 = random.randint(-50, 150)
        page.evaluate(f"window.scrollBy(0, {scroll_y2})")
        random_delay(0.3, 0.8)
        x = random.randint(100, viewport["width"] - 100)
        y = random.randint(100, viewport["height"] - 100)
        page.mouse.move(x, y)
        random_delay(0.2, 0.5)
    except Exception:
        pass


def get_browser_preferences():
    return ["msedge", "firefox"]


def get_profile_modes():
    return ["persisted", "fresh"]


def normalize_actor_url(url_str: str, use_proxy: bool, direct_domain=None) -> str:
    if not url_str:
        return url_str
    target_direct = direct_domain or JAVDB_DIRECT_DOMAIN
    if use_proxy:
        # 使用代理时，将所有alternative域名替换为代理域名
        url_str = url_str.replace(target_direct, JAVDB_PROXY_DOMAIN).replace(f"www.{target_direct}", JAVDB_PROXY_DOMAIN)
        for alt in JAVDB_ALTERNATE_DIRECT_DOMAINS:
            url_str = url_str.replace(alt, JAVDB_PROXY_DOMAIN).replace(f"www.{alt}", JAVDB_PROXY_DOMAIN)
    else:
        # 不使用代理时，将所有javdb.com和alternative域名替换为目标direct域名
        url_str = url_str.replace("javdb.com", target_direct).replace("www.javdb.com", target_direct)
        for alt in JAVDB_ALTERNATE_DIRECT_DOMAINS:
            url_str = url_str.replace(alt, target_direct).replace(f"www.{alt}", target_direct)
    return url_str


def get_attempt_configs(use_socks5):
    configs = []
    if use_socks5:
        configs.append({"use_proxy": True, "headless": False})
    configs.append({"use_proxy": False, "headless": False})
    return configs


def is_age_confirmation_html(page_source: str) -> bool:
    if not page_source:
        return False
    s = page_source.lower()
    age_markers = [
        "您必須已達",
        "你必须已达",
        "法定年齡",
        "法定年龄",
        "you must be of legal age",
        "age verification",
        "18歲",
        "18岁",
        "years of age",
        "confirm you are of legal age",
    ]
    return sum(1 for m in age_markers if m in s) >= 2


def is_cloudflare_challenge_html(page_source: str, title: str = "") -> bool:
    if not page_source:
        return False
    if is_age_confirmation_html(page_source):
        return False
    t = (title or "").lower()
    s = page_source.lower()
    strong_markers = [
        "checking your browser before accessing",
        "attention required!",
        "cf-browser-verification",
    ]
    if any(marker in s for marker in strong_markers):
        return True
    secondary_markers = [
        "cf-challenge",
        "challenge-platform",
        "turnstile",
        "cf_chl_",
        "cf-chl-",
        "/cdn-cgi/challenge-platform/",
    ]
    if any(marker in s for marker in secondary_markers):
        cf_page_markers = ["checking your browser", "just a moment", "please stand by", "enable javascript", "ray id"]
        if any(m in s for m in cf_page_markers):
            return True
    title_markers = ["cloudflare", "just a moment", "checking your browser", "attention required!"]
    body_markers = ["just a moment", "checking your browser", "please stand by, while we are checking your browser"]
    if any(marker in t for marker in title_markers) and any(marker in s for marker in body_markers):
        return True
    
    # 检测Turnstile验证框
    turnstile_markers = [
        "turnstile",
        "cf-turnstile",
        "data-sitekey",
        "challenges.cloudflare.com",
    ]
    if any(marker in s for marker in turnstile_markers):
        return True
    
    return False


def is_cloudflare_challenge_pw(page):
    try:
        title = page.title() or ""
        html = page.content() or ""
        return is_cloudflare_challenge_html(html, title)
    except Exception:
        return False


def is_cloudflare_verification_failed(page):
    try:
        title = page.title() or ""
        html = page.content() or ""
        s = html.lower()
        t = title.lower()
        failed_markers = [
            "verification failed",
            "please refresh the page",
            "verify you are human",
            "error 1020",
            "access denied",
            "sorry, you have been blocked",
        ]
        if any(marker in s for marker in failed_markers):
            return True
        if any(marker in t for marker in failed_markers):
            return True
        return False
    except Exception:
        return False


def wait_for_cloudflare_pass(page, base_url=None, max_retries=3, retry_delay=300):
    """等待Cloudflare验证通过，支持刷新和重新导航
    
    Args:
        page: Playwright页面对象
        base_url: 基础URL，用于导航恢复
        max_retries: 最大重试次数
        retry_delay: 重试间隔（秒），默认300秒（5分钟）
    """
    for attempt in range(max_retries):
        if is_cloudflare_verification_failed(page):
            print(f"检测到Cloudflare验证失败，等待{retry_delay}秒后重试 (第{attempt+1}/{max_retries}次)...", file=sys.stderr)
            random_delay(retry_delay, retry_delay + 60)
            page.reload(wait_until="domcontentloaded", timeout=30000)
            random_delay(10, 20)
            if not is_cloudflare_challenge_pw(page):
                print("刷新后验证通过", file=sys.stderr)
                return True
        elif not is_cloudflare_challenge_pw(page):
            return True
        else:
            # 等待Cloudflare自动验证通过
            print(f"等待Cloudflare自动验证 (第{attempt+1}/{max_retries}次)...", file=sys.stderr)
            for _ in range(30):  # 最多等待90秒
                if not is_cloudflare_challenge_pw(page):
                    print("自动验证通过", file=sys.stderr)
                    return True
                time.sleep(3)
            
            # 如果验证仍未通过，等待更长时间后重试
            if is_cloudflare_challenge_pw(page):
                print(f"自动验证超时，等待{retry_delay}秒后重试...", file=sys.stderr)
                random_delay(retry_delay, retry_delay + 60)
                page.reload(wait_until="domcontentloaded", timeout=30000)
                random_delay(10, 20)
    
    # 所有重试都失败，尝试导航到首页重新获取cookie
    if base_url:
        print("尝试导航到首页重新获取cookie...", file=sys.stderr)
        try:
            page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
            random_delay(60, 120)  # 首页导航后等待1-2分钟
            if not is_cloudflare_challenge_pw(page):
                print("首页导航成功，验证通过", file=sys.stderr)
                return True
        except Exception as e:
            print(f"首页导航失败: {e}", file=sys.stderr)
    
    return False


def recover_from_cloudflare_block(page, base_url, context=None):
    """从Cloudflare阻断中恢复，清理cookie并重新获取"""
    print("\n=== Cloudflare阻断恢复 ===", file=sys.stderr)
    print("尝试清理Cloudflare相关cookie并重新获取...", file=sys.stderr)
    
    # 尝试清理cf_clearance cookie
    try:
        cookies = context.cookies() if context else []
        cf_cookies = [c for c in cookies if 'cf_' in c.get('name', '').lower() or 'cloudflare' in c.get('domain', '').lower()]
        if cf_cookies:
            print(f"发现 {len(cf_cookies)} 个Cloudflare相关cookie，尝试清理...", file=sys.stderr)
            for cookie in cf_cookies:
                try:
                    context.clear_cookies()
                    print(f"已清理cookie: {cookie.get('name')}", file=sys.stderr)
                except Exception:
                    pass
    except Exception as e:
        print(f"清理cookie时出错: {e}", file=sys.stderr)
    
    # 导航到首页重新获取cookie
    print("导航到首页重新获取验证...", file=sys.stderr)
    try:
        page.goto(base_url, wait_until="domcontentloaded", timeout=60000)
        random_delay(15, 25)
        
        # 等待Cloudflare验证通过
        if is_cloudflare_challenge_pw(page):
            print("首页仍有Cloudflare验证，等待通过...", file=sys.stderr)
            for _ in range(40):  # 最多等待2分钟
                if not is_cloudflare_challenge_pw(page):
                    print("首页验证通过", file=sys.stderr)
                    return True
                time.sleep(3)
        else:
            print("首页验证通过", file=sys.stderr)
            return True
    except Exception as e:
        print(f"首页导航失败: {e}", file=sys.stderr)
    
    return False


def is_age_confirmation_pw(page):
    try:
        html = page.content() or ""
        return is_age_confirmation_html(html)
    except Exception:
        return False


def dismiss_age_confirmation_pw(page, timeout_seconds=10):
    try:
        selectors = [
            "a.button.is-primary",
            "button.button.is-primary",
            "a.button.is-large",
            "button.button.is-large",
            "a.button.is-success",
            "button.button.is-success",
            "a.button:has-text('是')",
            "button.button:has-text('是')",
            "button.btn-primary",
            "a.btn-primary",
            "button:has-text('YES')",
            "button:has-text('Yes')",
            "a:has-text('YES')",
            "a:has-text('Yes')",
            ".confirm-age-btn",
            "#confirm-age",
        ]
        for sel in selectors:
            try:
                loc = page.locator(sel).first
                if loc.count() > 0 and loc.is_visible():
                    loc.click()
                    random_delay(1.5, 2.5)
                    if not is_age_confirmation_pw(page):
                        print(f"已自动点击年龄确认按钮: {sel}", file=sys.stderr)
                        return True
            except Exception:
                continue
        return False
    except Exception:
        return False


def setup_playwright_session(use_proxy=True, headless=False, browser_name="msedge", profile_mode="fresh", proxy_host=None, proxy_port=None):
    if sync_playwright is None:
        return None
    try:
        p = sync_playwright().start()
        launch_args = {
            "headless": headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                # Cloudflare Turnstile验证需要的特性
                "--enable-features=NetworkService,NetworkServiceInProcess",
                "--disable-features=AutomationControlled",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
                # GPU和硬件加速（让浏览器更真实）
                "--disable-gpu",  # headless模式下通常需要禁用GPU
                "--disable-software-rasterizer",
                # 其他反检测参数
                "--window-size=1280,800",
                "--lang=zh-CN",
                "--accept-lang=zh-CN,zh,ja,en",
            ],
        }
        if use_proxy:
            ph = proxy_host or SOCKS5_PROXY_HOST
            pp = proxy_port or SOCKS5_PROXY_PORT
            launch_args["proxy"] = {"server": f"socks5://{ph}:{pp}"}
        user_data_dir = os.path.join(os.path.dirname(__file__), '.playwright_user_data')
        os.makedirs(user_data_dir, exist_ok=True)
        context_args = {
            "user_agent": DEFAULT_USER_AGENT,
            "locale": "zh-CN",
            "viewport": {"width": 1280, "height": 800},
            # 启用JavaScript（默认启用，但显式声明）
            "java_script_enabled": True,
            # 其他反检测设置
            "bypass_csp": True,
        }
        if profile_mode == "persisted":
            context_args["user_data_dir"] = user_data_dir
            if browser_name == "msedge":
                try:
                    context = p.chromium.launch_persistent_context(**context_args, channel="msedge", **launch_args)
                except Exception:
                    context = p.chromium.launch_persistent_context(**context_args, **launch_args)
            elif browser_name == "firefox":
                context = p.firefox.launch_persistent_context(**context_args, **launch_args)
            else:
                context = p.chromium.launch_persistent_context(**context_args, **launch_args)
            page = context.pages[0] if context.pages else context.new_page()
            # 注入反检测脚本
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'ja', 'en']});
                window.chrome = {
                    runtime: {},
                    loadTimes: function() {},
                    csi: function() {},
                    app: {}
                };
            """)
            return {"playwright": p, "browser": None, "context": context, "page": page}
        else:
            if browser_name == "msedge":
                try:
                    browser = p.chromium.launch(**launch_args, channel="msedge")
                except Exception:
                    browser = p.chromium.launch(**launch_args)
            elif browser_name == "firefox":
                browser = p.firefox.launch(**launch_args)
            else:
                browser = p.chromium.launch(**launch_args)
            context = browser.new_context(**context_args)
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'ja', 'en']});
                window.chrome = {
                    runtime: {},
                    loadTimes: function() {},
                    csi: function() {},
                    app: {}
                };
            """)
            page = context.new_page()
            return {"playwright": p, "browser": browser, "context": context, "page": page}
    except Exception as e:
        print(f"Playwright启动失败: {e}", file=sys.stderr)
        return None


def close_playwright_session(session):
    try:
        if session:
            session["context"].close()
            session["browser"].close()
            session["playwright"].stop()
    except Exception:
        pass


def get_favorite_actors():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, profile_url FROM actors WHERE is_favorite = 1 AND profile_url IS NOT NULL")
    actors = cursor.fetchall()
    conn.close()
    return actors


def get_actor_by_javdb_code(javdb_code):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, profile_url FROM actors WHERE profile_url LIKE ? AND is_favorite = 1", (f"%/{javdb_code}%",))
    actor = cursor.fetchone()
    conn.close()
    return actor


def get_existing_codes():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT javdb_code FROM javdb_info WHERE javdb_code IS NOT NULL")
    codes = set(row[0] for row in cursor.fetchall())
    cursor.execute("SELECT file_name FROM videos WHERE file_name IS NOT NULL")
    for row in cursor.fetchall():
        from code_extractor import CodeExtractor
        extractor = CodeExtractor()
        code = extractor.extract_code_from_filename(row[0])
        if code:
            codes.add(code.upper())
    conn.close()
    return codes


def load_existing_csv(csv_path):
    if not os.path.exists(csv_path):
        return []
    results = []
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            results.append(row)
    return results


def save_csv(csv_path, results):
    fieldnames = ["actor_javdb_code", "actor_name", "code", "title", "url", "release_date", "in_database", "magnet_link", "categories", "added_date"]
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(results)


def extract_javdb_code_from_url(url):
    if not url:
        return ""
    match = re.search(r'/actors/([A-Za-z0-9]+)', url)
    if match:
        return match.group(1)
    match = re.search(r'/a/([A-Za-z0-9]+)', url)
    if match:
        return match.group(1)
    return ""


def get_video_detail_info(page, video_url, base_url):
    """获取视频详情页的磁力链接和类别信息"""
    magnet_link = ""
    categories = ""
    try:
        if not video_url.startswith("http"):
            video_url = urljoin(base_url, video_url)
        page.goto(video_url, wait_until="domcontentloaded", timeout=30000)
        random_delay(2, 4)
        simulate_human_behavior(page)
        if is_cloudflare_challenge_pw(page):
            print("详情页检测到 Cloudflare 验证页，等待通过...", file=sys.stderr)
            if not wait_for_cloudflare_pass(page, base_url=base_url, max_retries=2):
                print("详情页Cloudflare验证未通过", file=sys.stderr)
                return "", ""
        if is_age_confirmation_pw(page):
            dismiss_age_confirmation_pw(page)
            random_delay(1, 2)
        
        # 提取磁力链接
        magnet_selectors = [
            "a[href^='magnet:?']",
            ".magnet-link a",
            "#magnet-link",
            "a.button.is-primary[href^='magnet']",
            "a[href*='magnet:?xt=urn:btih:']",
        ]
        for sel in magnet_selectors:
            try:
                magnet_elem = page.locator(sel).first
                if magnet_elem.count() > 0:
                    href = magnet_elem.get_attribute("href") or ""
                    if href.startswith("magnet:"):
                        magnet_link = href
                        break
            except Exception:
                continue
        if not magnet_link:
            try:
                all_magnets = page.locator("a[href^='magnet:?']").all()
                if all_magnets:
                    magnet_link = all_magnets[0].get_attribute("href") or ""
            except Exception:
                pass
        
        # 提取类别信息
        try:
            # 方法1: 使用XPath查找"類別:"标签（与javdb_crawler_single.py一致）
            try:
                category_elements = page.locator("xpath=//strong[text()='類別:']/following-sibling::span[1]/a").all()
                if category_elements:
                    categories = ", ".join([elem.text_content().strip() for elem in category_elements])
            except Exception:
                pass
            
            # 方法2: 尝试"Tags:"标签
            if not categories:
                try:
                    category_elements = page.locator("xpath=//strong[text()='Tags:']/following-sibling::span[1]/a").all()
                    if category_elements:
                        categories = ", ".join([elem.text_content().strip() for elem in category_elements])
                except Exception:
                    pass
            
            # 方法3: 备用选择器
            if not categories:
                try:
                    category_elements = page.locator('.panel-info a[href*="/tags/"], .genres a, .tags a').all()
                    if category_elements:
                        cats = [elem.text_content().strip() for elem in category_elements if elem.text_content().strip()]
                        # 去重但保持顺序
                        seen = set()
                        unique_cats = []
                        for c in cats:
                            if c not in seen:
                                seen.add(c)
                                unique_cats.append(c)
                        categories = ", ".join(unique_cats)
                except Exception:
                    pass
        except Exception as e:
            print(f"提取类别信息失败: {e}", file=sys.stderr)
            
    except Exception as e:
        print(f"获取详情页信息失败: {e}", file=sys.stderr)
    return magnet_link, categories


def parse_actor_works_page(page, actor_url, base_url):
    works = []
    try:
        page.goto(actor_url, wait_until="domcontentloaded", timeout=60000)
        random_delay(2, 3)
        simulate_human_behavior(page)
        if is_cloudflare_challenge_pw(page):
            print("检测到 Cloudflare 验证页，等待通过...", file=sys.stderr)
            if not wait_for_cloudflare_pass(page, base_url=base_url, max_retries=3):
                print("Cloudflare验证未通过，跳过此页面", file=sys.stderr)
                return works
        if is_age_confirmation_pw(page):
            print("检测到年龄确认页，尝试自动点击...", file=sys.stderr)
            dismiss_age_confirmation_pw(page)
        page.wait_for_selector(".video-list, .grid-items, .videos, a[href*='/v/']", timeout=15000)
        video_items = page.locator("a[href*='/v/']").all()
        for item in video_items:
            try:
                href = item.get_attribute("href") or ""
                if not href:
                    continue
                if not href.startswith("http"):
                    href = urljoin(base_url, href)
                has_magnet = False
                try:
                    magnet_tag = item.locator("span.tag.is-success, span.tag.is-warning").first
                    if magnet_tag.count() > 0:
                        tag_text = (magnet_tag.text_content() or "").strip()
                        if "磁鏈" in tag_text or "磁链" in tag_text:
                            has_magnet = True
                except Exception:
                    pass
                if not has_magnet:
                    continue
                title_elem = item.locator(".title, .video-title, strong").first
                title = ""
                if title_elem.count() > 0:
                    title = (title_elem.text_content() or "").strip()
                    title = re.sub(r'\s+', ' ', title).strip()
                code_match = re.search(r'([A-Z]{2,10}[-_]?\d{2,5})', title, re.I)
                code = code_match.group(1).upper().replace('_', '-') if code_match else ""
                date_elem = item.locator(".date, .release-date, .meta").first
                release_date = ""
                if date_elem.count() > 0:
                    date_text = (date_elem.text_content() or "").strip()
                    date_match = re.search(r'(\d{4}[-/]\d{2}[-/]\d{2})', date_text)
                    if date_match:
                        release_date = date_match.group(1)
                if code:
                    works.append({
                        "code": code,
                        "title": title,
                        "url": href,
                        "release_date": release_date,
                        "has_magnet": has_magnet,
                    })
            except Exception:
                continue
        print(f"从演员页面获取到 {len(works)} 个有磁力链接的作品", file=sys.stderr)
    except Exception as e:
        print(f"解析演员作品页面失败: {e}", file=sys.stderr)
    return works


def crawl_actor_all_pages(page, actor_url, base_url, max_pages=10, skip_codes=None, on_work_found=None):
    all_works = []
    skip_codes = skip_codes or set()
    current_page = 1
    while current_page <= max_pages:
        print(f"正在爬取第 {current_page} 页...", file=sys.stderr)
        page_url = actor_url if current_page == 1 else f"{actor_url}?page={current_page}"
        works = parse_actor_works_page(page, page_url, base_url)
        if not works:
            print(f"第 {current_page} 页无有磁力链接的作品，停止翻页", file=sys.stderr)
            break
        for w in works:
            if w["code"] in skip_codes:
                continue
            print(f"获取详情页信息: {w['code']}...", file=sys.stderr)
            magnet_link, categories = get_video_detail_info(page, w["url"], base_url)
            if magnet_link:
                w["magnet_link"] = magnet_link
                w["categories"] = categories
                all_works.append(w)
                print(f"找到磁力链接: {w['code']}, 类别: {categories}", file=sys.stderr)
                # 每找到一个作品，立即调用回调保存
                if on_work_found:
                    on_work_found(w)
            else:
                print(f"详情页无磁力链接，跳过: {w['code']}", file=sys.stderr)
            # 每个详情页爬取后增加较长间隔，防止被ban
            random_delay(8, 15)
        skip_codes.update(w["code"] for w in works)
        has_next = False
        try:
            next_btn = page.locator("a.pagination-next, a.next, a[rel='next']").first
            if next_btn.count() > 0 and next_btn.is_visible():
                href = next_btn.get_attribute("href") or ""
                if href and ("page=" in href or "next" in href.lower()):
                    has_next = True
        except Exception:
            pass
        if not has_next:
            print("无下一页，停止翻页", file=sys.stderr)
            break
        current_page += 1
        random_delay(3, 6)
    return all_works


def main():
    parser = argparse.ArgumentParser(description="收藏演员作品爬虫 - 爬取JAVDB收藏演员的作品列表")
    parser.add_argument("--max-pages", type=int, default=10, help="每个演员最多爬取页数")
    parser.add_argument("--actor-code", type=str, default=None, help="指定演员JAVDB唯一码（如Julia的1KBW）")
    parser.add_argument("--proxy", type=str, default=None, help="指定SOCKS5代理地址（如127.0.0.1:1080），默认使用config.py中的配置")
    parser.add_argument("--no-proxy", action="store_true", help="不使用代理")
    parser.add_argument("--import-csv", type=str, nargs="+", default=None, help="导入已有CSV文件（支持多个文件）")
    parser.add_argument("--wait-login", type=int, default=60, help="等待登录时间（秒），0表示不等待")
    parser.add_argument("--direct-domain", type=str, default=None, help="指定直连域名（默认使用config.py中的JAVDB_DIRECT_DOMAIN）")
    args = parser.parse_args()

    use_proxy = not args.no_proxy
    proxy_host = SOCKS5_PROXY_HOST
    proxy_port = SOCKS5_PROXY_PORT
    if args.proxy:
        parts = args.proxy.split(":")
        if len(parts) == 2:
            proxy_host = parts[0]
            proxy_port = int(parts[1])
        else:
            print(f"代理地址格式错误: {args.proxy}，应为 host:port", file=sys.stderr)
            return

    direct_domain = args.direct_domain or JAVDB_DIRECT_DOMAIN
    if use_proxy:
        base_url = f"https://{JAVDB_PROXY_DOMAIN}"
    else:
        base_url = f"https://{direct_domain}"
    print(f"使用域名: {base_url} (代理: {use_proxy}, 代理地址: {proxy_host}:{proxy_port})", file=sys.stderr)

    existing_codes = get_existing_codes()
    print(f"本地数据库已有 {len(existing_codes)} 个番号", file=sys.stderr)

    csv_path = DEFAULT_CSV_PATH
    existing_csv_data = load_existing_csv(csv_path)
    existing_codes_in_csv = set()
    existing_actor_codes_in_csv = set()
    for row in existing_csv_data:
        code = row.get("code", "")
        actor_code = row.get("actor_javdb_code", "")
        if code:
            existing_codes_in_csv.add(code)
        if actor_code:
            existing_actor_codes_in_csv.add(actor_code)
    print(f"已有CSV文件 {csv_path} 包含 {len(existing_csv_data)} 条记录", file=sys.stderr)

    actors = []
    if args.actor_code:
        actor = get_actor_by_javdb_code(args.actor_code)
        if actor:
            actors = [actor]
            print(f"指定演员: {actor[1]} (JAVDB码: {args.actor_code})", file=sys.stderr)
        else:
            print(f"未找到JAVDB码为 {args.actor_code} 的收藏演员", file=sys.stderr)
            return
    else:
        actors = get_favorite_actors()
        actors = [a for a in actors if extract_javdb_code_from_url(a[2]) not in existing_actor_codes_in_csv]
        print(f"需要爬取的收藏演员数量: {len(actors)}", file=sys.stderr)

    if not actors and not args.import_csv:
        print("无需要爬取的演员", file=sys.stderr)
        if existing_csv_data:
            print(f"已有CSV数据保持不变: {csv_path}", file=sys.stderr)
        return

    added_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    all_results = existing_csv_data

    if args.import_csv:
        for csv_file in args.import_csv:
            print(f"导入已有CSV: {csv_file}", file=sys.stderr)
            imported_data = []
            with open(csv_file, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    title = row.get("title", "")
                    video_id = row.get("video_id", "")
                    detail_url = row.get("detail_url", "")
                    release_date = row.get("release_date", "")
                    actor_info = row.get("actor", "")
                    magnet_link = row.get("magnet_link", "")
                    if not magnet_link:
                        continue
                    actor_name = ""
                    if actor_info:
                        actor_name = actor_info.split("\n")[0].strip().split(",")[0].strip()
                    if not actor_name:
                        filename = os.path.basename(csv_file)
                        if "javdb_" in filename:
                            actor_name = filename.replace("javdb_", "").replace(".csv", "")
                        elif "actor_videos_" in filename:
                            match = re.search(r'actor_videos_([^_]+)_', filename)
                            if match:
                                actor_name = match.group(1)
                    code = video_id.upper() if video_id else ""
                    if not code:
                        code_match = re.search(r'([A-Z]{2,10}[-_]?\d{2,5})', title, re.I)
                        code = code_match.group(1).upper().replace('_', '-') if code_match else ""
                    in_database = code in existing_codes
                    if code and magnet_link:
                        imported_data.append({
                            "actor_javdb_code": "",
                            "actor_name": actor_name,
                            "code": code,
                            "title": title,
                            "url": detail_url,
                            "release_date": release_date,
                            "in_database": in_database,
                            "magnet_link": magnet_link,
                            "added_date": added_date
                        })
            print(f"从 {csv_file} 导入 {len(imported_data)} 条记录", file=sys.stderr)
            for r in imported_data:
                key = f"{r['actor_name']}|{r['code']}"
                existing_key = f"{r['actor_name']}|{r['code']}"
                if not any(f"{row.get('actor_name','')}|{row.get('code','')}" == existing_key for row in all_results):
                    all_results.append(r)
                    existing_codes_in_csv.add(r["code"])

    session = None
    for attempt in get_attempt_configs(use_proxy):
        for browser_name in get_browser_preferences():
            for profile_mode in get_profile_modes():
                print(f"尝试 Playwright - browser: {browser_name}, profile: {profile_mode}, proxy: {attempt['use_proxy']}", file=sys.stderr)
                session = setup_playwright_session(
                    use_proxy=attempt["use_proxy"],
                    headless=attempt["headless"],
                    browser_name=browser_name,
                    profile_mode=profile_mode,
                    proxy_host=proxy_host if attempt["use_proxy"] else None,
                    proxy_port=proxy_port if attempt["use_proxy"] else None
                )
                if session:
                    break
            if session:
                break
        if session:
            break

    if not session:
        print("Playwright启动失败", file=sys.stderr)
        if all_results:
            save_csv(csv_path, all_results)
            print(f"数据已保存到: {csv_path}", file=sys.stderr)
        return

    page = session["page"]
    try:
        page.goto(base_url, wait_until="domcontentloaded", timeout=60000)
        random_delay(2, 3)
        if is_cloudflare_challenge_pw(page):
            print("检测到 Cloudflare 验证页，等待通过...", file=sys.stderr)
            if not wait_for_cloudflare_pass(page, base_url=base_url, max_retries=3):
                print("Cloudflare验证未通过", file=sys.stderr)
                save_csv(csv_path, all_results)
                return
        if is_age_confirmation_pw(page):
            print("检测到年龄确认页，尝试自动点击...", file=sys.stderr)
            dismiss_age_confirmation_pw(page)

        if args.wait_login > 0:
            print(f"等待 {args.wait_login} 秒，请手动登录VIP账号...", file=sys.stderr)
            print("登录完成后脚本将自动继续...", file=sys.stderr)
            time.sleep(args.wait_login)
            print("等待结束，开始爬取...", file=sys.stderr)

        for actor_id, actor_name, actor_url in actors:
            print(f"\n爬取演员: {actor_name} ({actor_url})", file=sys.stderr)
            if not actor_url:
                continue
            if not actor_url.startswith("http"):
                actor_url = urljoin(base_url, actor_url)
            actor_url = normalize_actor_url(actor_url, use_proxy, direct_domain=direct_domain)
            actor_javdb_code = extract_javdb_code_from_url(actor_url)
            actor_processed_codes = set()
            for r in all_results:
                if r.get("actor_javdb_code") == actor_javdb_code or r.get("actor_name") == actor_name:
                    actor_processed_codes.add(r.get("code", ""))
            
            # 定义回调函数：每找到一个作品就立即保存
            def on_work_found(w):
                code = w["code"]
                in_database = code in existing_codes
                all_results.append({
                    "actor_javdb_code": actor_javdb_code,
                    "actor_name": actor_name,
                    "code": code,
                    "title": w["title"],
                    "url": w["url"],
                    "release_date": w.get("release_date", ""),
                    "in_database": in_database,
                    "magnet_link": w.get("magnet_link", ""),
                    "categories": w.get("categories", ""),
                    "added_date": added_date
                })
                # 每找到一个作品就立即保存CSV
                save_csv(csv_path, all_results)
                print(f"已保存CSV，当前总记录数: {len(all_results)}", file=sys.stderr)
            
            # 检查Cloudflare状态
            if is_cloudflare_challenge_pw(page):
                print("检测到Cloudflare验证，尝试恢复...", file=sys.stderr)
                if not wait_for_cloudflare_pass(page, base_url=base_url, max_retries=3):
                    print("Cloudflare验证未通过，尝试恢复...", file=sys.stderr)
                    if recover_from_cloudflare_block(page, base_url, session.get("context")):
                        print("恢复成功，继续爬取", file=sys.stderr)
                    else:
                        print("恢复失败，保存当前结果并跳过此演员", file=sys.stderr)
                        save_csv(csv_path, all_results)
                        continue
            
            javdb_works = crawl_actor_all_pages(page, actor_url, base_url, max_pages=args.max_pages, skip_codes=actor_processed_codes, on_work_found=on_work_found)
            print(f"JAVDB新获取 {len(javdb_works)} 个作品", file=sys.stderr)
            
            # 演员之间增加较长间隔，防止被ban
            random_delay(30, 60)

    except Exception as e:
        print(f"爬取失败: {e}", file=sys.stderr)
    finally:
        close_playwright_session(session)

    if not all_results:
        print("未能获取任何作品信息", file=sys.stderr)
        return

    dedup_results = []
    seen = set()
    for r in all_results:
        magnet_link = r.get("magnet_link", "")
        if not magnet_link:
            continue
        actor_javdb_code = r.get("actor_javdb_code", "")
        actor_name = r.get("actor_name", "")
        code = r.get("code", "")
        key = f"{actor_javdb_code}|{actor_name}|{code}"
        if key not in seen:
            seen.add(key)
            dedup_results.append(r)

    save_csv(csv_path, dedup_results)

    in_db_count = sum(1 for r in dedup_results if r.get("in_database"))
    not_in_db_count = len(dedup_results) - in_db_count
    print(f"\n结果已保存到: {csv_path}", file=sys.stderr)
    print(f"总作品数: {len(dedup_results)}", file=sys.stderr)
    print(f"已在数据库: {in_db_count}", file=sys.stderr)
    print(f"未在数据库: {not_in_db_count}", file=sys.stderr)


if __name__ == "__main__":
    main()