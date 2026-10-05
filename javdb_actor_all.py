#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JAVDB演员作品信息爬虫工具（Playwright 版）
============================================

功能描述:
---------
从 JAVDB（主站或镜像域名）抓取指定演员的所有作品信息，包括：
- 作品标题、番号、发行日期、时长、评分
- 演员信息、制作商、标签分类
- 封面图片URL、磁力链接
- 支持断点续爬、增量更新
- 自动处理 Cloudflare 验证、年龄确认、登录检测
- 智能过滤（单体作品+磁力链接）

核心特性:
---------
1. **Playwright 驱动**: 使用 launch_persistent_context 持久化登录态，
   与 javdb_crawler_single.py 共用 `.playwright_user_data/<browser>` 配置目录
2. **固定登录态优先**: persisted 模式优先复用已保存的 cookie，fresh 模式为临时会话
3. **反检测**: 注入 webdriver 隐藏脚本、随机延迟、滚动与鼠标移动模拟
4. **Cloudflare 处理**: 自动等待验证通过，失败时可人工介入
5. **断点续爬**: CSV 文件存在时自动续爬，避免重复抓取
6. **灵活过滤**: 默认只抓取单体作品且有磁力链接（t=d,s），--filter 可自定义

CLI 兼容性说明:
---------
- 保留了原 Selenium 版的 actor_url / --from / --to / --name / --csv /
  --legacy-filter / --min-delay / --max-delay / --no-human-actions
- 移除了 Edge 专属参数（--user-data-dir / --profile-directory /
  --use-dedicated-profile），替换为 --browser / --profile-mode / --headless / --proxy
- CSV 字段与原版完全一致，旧 CSV 可直接续爬

依赖配置:
---------
- Python 3.8+
- playwright（pip install playwright && playwright install msedge 或 chromium）
- SOCKS5代理（可选，访问 javdb.com 主站时默认启用，镜像域名默认直连）

用法示例:
---------
    python javdb_actor_all.py "https://javdb571.com/actors/5Dya"                 # 全部单体+可下载
    python javdb_actor_all.py "https://javdb.com/actors/abc123" --filter s       # 仅单体作品（含无磁力）
    python javdb_actor_all.py "https://javdb.com/actors/abc123" --from 1 --to 5
    python javdb_actor_all.py "https://javdb.com/actors/abc123" --login          # 手动登录保存登录态
"""

import os
import re
import sys
import csv
import time
import random
import shutil
import tempfile
import argparse
from urllib.parse import urljoin, urlparse, parse_qsl, urlencode, urlunparse
from contextlib import suppress

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
except Exception:
    sync_playwright = None
    PlaywrightTimeoutError = Exception

from config import (
    SOCKS5_PROXY_HOST, SOCKS5_PROXY_PORT, MIN_DELAY, MAX_DELAY,
    LOGIN_EMAIL, LOGIN_PASSWORD, USE_SOCKS5_PROXY,
    JAVDB_PROXY_DOMAIN,
)
from utils.runtime import runtime_path

CRAWL_MIN_DELAY = MIN_DELAY
CRAWL_MAX_DELAY = MAX_DELAY
HUMAN_ACTIONS = True
DEFAULT_FILTER = "d,s"  # 默认单体且有磁力链接；--filter 可改为如 "s"、"d"、"a"
RUN_BASE_URL = None     # 本次运行的基础URL（取自输入演员链接的域名）

DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
REQUEST_LANGUAGE = "zh-CN,zh;q=0.9,ja;q=0.8,en;q=0.7"

ANTI_DETECT_SCRIPT = """
    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'ja', 'en-US', 'en']});
    Object.defineProperty(navigator, 'language', {get: () => 'zh-CN'});
    Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
    window.chrome = {runtime: {}, loadTimes: function() {}, csi: function() {}, app: {}};
"""


# ---------- Utils ----------
def random_delay(min_seconds=None, max_seconds=None):
    lo = min_seconds if min_seconds is not None else CRAWL_MIN_DELAY
    hi = max_seconds if max_seconds is not None else CRAWL_MAX_DELAY
    time.sleep(random.uniform(lo, hi))


def human_pause(page, min_seconds=None, max_seconds=None, do_actions=None):
    """页面停留 + 随机滚动/鼠标移动，模拟人类浏览行为"""
    do = HUMAN_ACTIONS if do_actions is None else do_actions
    random_delay(min_seconds, max_seconds)
    if not do or page is None:
        return
    try:
        viewport = page.viewport_size or {"width": 1280, "height": 800}
        scroll_y = random.randint(100, 400)
        page.evaluate(f"window.scrollBy(0, {scroll_y})")
        random_delay(0.5, 1.2)
        scroll_y2 = random.randint(-80, 150)
        page.evaluate(f"window.scrollBy(0, {scroll_y2})")
        x = random.randint(100, max(101, viewport["width"] - 100))
        y = random.randint(100, max(101, viewport["height"] - 100))
        page.mouse.move(x, y)
    except Exception:
        pass


def get_results_dir():
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')
    os.makedirs(d, exist_ok=True)
    return d


def safe_filename(filename: str) -> str:
    return re.sub(r'[\\/:*?"<>|\s]+', '_', str(filename)).strip('._') or 'actor'


def extract_actor_id_from_url(url: str):
    m = re.search(r'/actors/([A-Za-z0-9]+)', url or '')
    return m.group(1) if m else None


def url_origin(url: str) -> str:
    try:
        p = urlparse(url)
        return f"{p.scheme or 'https'}://{p.netloc}"
    except Exception:
        return url


def guess_use_proxy(actor_url: str) -> bool:
    """javdb.com 主站默认走代理，镜像域名（javdbNNN.com 等）默认直连"""
    host = (urlparse(actor_url).netloc or '').lower()
    if host.startswith('www.'):
        host = host[4:]
    return host == JAVDB_PROXY_DOMAIN


def find_best_magnet_link(magnet_links):
    if not magnet_links:
        return None
    for link in magnet_links:
        if re.search(r'-UC\b', link, re.IGNORECASE):
            return link
    for link in magnet_links:
        if re.search(r'-C\b', link, re.IGNORECASE):
            return link
    return magnet_links[0] if magnet_links else None


# ---------- Playwright session ----------
def setup_playwright_session(use_proxy=True, headless=False, browser_name="msedge", profile_mode="persisted"):
    """启动 Playwright 持久化会话（登录态保存在 .playwright_user_data/<browser>）"""
    if sync_playwright is None:
        print("Playwright 未安装，请先: pip install playwright && playwright install msedge", file=sys.stderr)
        return None
    proxy = {"server": f"socks5://{SOCKS5_PROXY_HOST}:{SOCKS5_PROXY_PORT}"} if use_proxy else None
    if profile_mode == "fresh":
        parent = runtime_path(".playwright_user_data_fresh", browser_name)
        os.makedirs(parent, exist_ok=True)
        user_data_dir = tempfile.mkdtemp(prefix="pw_", dir=parent)
        cleanup_user_data_dir = user_data_dir
    else:
        user_data_dir = runtime_path(".playwright_user_data", browser_name)
        os.makedirs(user_data_dir, exist_ok=True)
        cleanup_user_data_dir = None
    launch_kwargs = {
        "headless": headless,
        "proxy": proxy,
        "locale": "zh-CN",
        "user_agent": DEFAULT_USER_AGENT,
        "extra_http_headers": {"Accept-Language": REQUEST_LANGUAGE},
        "viewport": {"width": 1280, "height": 800},
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--lang=zh-CN",
        ],
    }
    pw = None
    context = None
    try:
        pw = sync_playwright().start()
        if browser_name == "msedge":
            try:
                context = pw.chromium.launch_persistent_context(user_data_dir, channel="msedge", **launch_kwargs)
            except Exception:
                context = pw.chromium.launch_persistent_context(user_data_dir, **launch_kwargs)
        elif browser_name == "firefox":
            ff_kwargs = dict(launch_kwargs)
            ff_kwargs.pop("viewport", None)
            ff_kwargs["firefox_user_prefs"] = {"intl.accept_languages": "zh-CN,zh,ja,en-US,en"}
            context = pw.firefox.launch_persistent_context(user_data_dir, **ff_kwargs)
        else:
            context = pw.chromium.launch_persistent_context(user_data_dir, **launch_kwargs)
        page = context.pages[0] if context.pages else context.new_page()
        page.set_default_timeout(30000)
        page.add_init_script(ANTI_DETECT_SCRIPT)
        return {
            "pw": pw,
            "context": context,
            "page": page,
            "browser_name": browser_name,
            "profile_mode": profile_mode,
            "cleanup_user_data_dir": cleanup_user_data_dir,
        }
    except Exception as e:
        print(f"Playwright 启动失败({browser_name}): {e}", file=sys.stderr)
        with suppress(Exception):
            if context:
                context.close()
        with suppress(Exception):
            if pw:
                pw.stop()
        return None


def close_playwright_session(session):
    if not session:
        return
    with suppress(Exception):
        session["context"].close()
    with suppress(Exception):
        session["pw"].stop()
    cleanup_path = session.get("cleanup_user_data_dir")
    if cleanup_path:
        with suppress(Exception):
            shutil.rmtree(cleanup_path, ignore_errors=True)


# ---------- 页面状态检测（Cloudflare / 年龄确认 / 登录） ----------
def is_age_confirmation_html(page_source: str) -> bool:
    if not page_source:
        return False
    s = page_source.lower()
    age_markers = [
        "您必須已達", "你必须已达", "法定年齡", "法定年龄",
        "you must be of legal age", "age verification",
        "18歲", "18岁", "years of age", "confirm you are of legal age",
    ]
    return sum(1 for m in age_markers if m in s) >= 2


def is_age_confirmation_pw(page):
    try:
        return is_age_confirmation_html(page.content() or "")
    except Exception:
        return False


def dismiss_age_confirmation_pw(page, timeout_seconds=10):
    selectors = [
        "a.button.is-primary", "button.button.is-primary",
        "a.button.is-large", "button.button.is-large",
        "a.button.is-success", "button.button.is-success",
        "a.button:has-text('是')", "button.button:has-text('是')",
        "button.btn-primary", "a.btn-primary",
        "button:has-text('YES')", "button:has-text('Yes')",
        "a:has-text('YES')", "a:has-text('Yes')",
        ".confirm-age-btn", "#confirm-age",
    ]
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0 and loc.is_visible():
                loc.click()
                random_delay(1.5, 2.5)
                if not is_age_confirmation_pw(page):
                    print(f"已自动点击年龄确认按钮: {sel}")
                    return True
        except Exception:
            continue
    return False


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
    secondary_markers = ["cf-challenge", "challenge-platform", "turnstile", "cf_chl_", "cf-chl-", "/cdn-cgi/challenge-platform/"]
    if any(marker in s for marker in secondary_markers):
        cf_page_markers = ["checking your browser", "just a moment", "please stand by", "enable javascript", "ray id"]
        if any(m in s for m in cf_page_markers):
            return True
    title_markers = ["cloudflare", "just a moment", "checking your browser", "attention required!"]
    body_markers = ["just a moment", "checking your browser", "please stand by, while we are checking your browser"]
    if any(marker in t for marker in title_markers) and any(marker in s for marker in body_markers):
        return True
    turnstile_markers = ["turnstile", "cf-turnstile", "data-sitekey", "challenges.cloudflare.com"]
    if any(marker in s for marker in turnstile_markers):
        return True
    return False


def is_cloudflare_challenge_pw(page):
    try:
        return is_cloudflare_challenge_html(page.content() or "", page.title() or "")
    except Exception:
        return False


def is_cloudflare_verification_failed(page):
    try:
        title = (page.title() or "").lower()
        s = (page.content() or "").lower()
        failed_markers = [
            "verification failed", "please refresh the page", "verify you are human",
            "error 1020", "access denied", "sorry, you have been blocked",
        ]
        return any(m in s or m in title for m in failed_markers)
    except Exception:
        return False


def wait_for_cloudflare_pass(page, base_url=None, max_retries=3, retry_delay=300):
    """等待 Cloudflare 验证通过（自动轮询 + 刷新 + 首页恢复）"""
    for attempt in range(max_retries):
        if is_cloudflare_verification_failed(page):
            print(f"检测到Cloudflare验证失败，等待{retry_delay}秒后重试 (第{attempt+1}/{max_retries}次)...", file=sys.stderr)
            random_delay(retry_delay, retry_delay + 60)
            with suppress(Exception):
                page.reload(wait_until="domcontentloaded", timeout=30000)
            random_delay(10, 20)
            if not is_cloudflare_challenge_pw(page):
                print("刷新后验证通过", file=sys.stderr)
                return True
        elif not is_cloudflare_challenge_pw(page):
            return True
        else:
            print(f"等待Cloudflare自动验证 (第{attempt+1}/{max_retries}次)...", file=sys.stderr)
            for _ in range(30):  # 最多等90秒
                if not is_cloudflare_challenge_pw(page):
                    print("自动验证通过", file=sys.stderr)
                    return True
                time.sleep(3)
            if is_cloudflare_challenge_pw(page):
                print(f"自动验证超时，等待{retry_delay}秒后重试...", file=sys.stderr)
                random_delay(retry_delay, retry_delay + 60)
                with suppress(Exception):
                    page.reload(wait_until="domcontentloaded", timeout=30000)
                random_delay(10, 20)
    if base_url:
        print("尝试导航到首页重新获取cookie...", file=sys.stderr)
        try:
            page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
            random_delay(60, 120)
            if not is_cloudflare_challenge_pw(page):
                print("首页导航成功，验证通过", file=sys.stderr)
                return True
        except Exception as e:
            print(f"首页导航失败: {e}", file=sys.stderr)
    return False


def is_logged_in_pw(page):
    """导航栏出现登出/用户入口视为已登录"""
    try:
        if page.locator("a[href*='sign_out']").count() > 0:
            return True
        for text in ["登出", "ログアウト", "Sign Out"]:
            if page.locator(f"a:has-text('{text}')").count() > 0:
                return True
        if page.locator(".navbar-item.has-dropdown .navbar-link img.avatar, a[href*='/users/']").count() > 0:
            return True
        return False
    except Exception:
        return False


def is_login_page_pw(page):
    try:
        url = (page.url or '').lower()
        if 'login' in url or '/sign_in' in url:
            return True
        has_email = page.locator('input[type="email"], input[name="email"]').count() > 0
        has_pwd = page.locator('input[type="password"], input[name="password"]').count() > 0
        return has_email and has_pwd
    except Exception:
        return False


def handle_login_pw(page):
    """尝试用 config.py 中的账号自动填充登录表单"""
    if not (LOGIN_EMAIL and LOGIN_PASSWORD):
        print("未配置 LOGIN_EMAIL/LOGIN_PASSWORD，跳过自动填充，请手工登录")
        return False
    try:
        email = page.locator('input[type="email"], input[name="email"]').first
        if email.count() == 0:
            return False
        email.fill(LOGIN_EMAIL)
        random_delay(1, 2)
        page.locator('input[type="password"], input[name="password"]').first.fill(LOGIN_PASSWORD)
        random_delay(1, 2)
        page.locator('button[type="submit"], input[type="submit"], .btn-primary').first.click()
        print("已提交登录表单，等待跳转/人工验证…")
        random_delay(3, 5)
        return True
    except Exception as e:
        print(f"登录处理异常: {e}")
        return False


def wait_for_manual_login(page, seconds=300, reopen_url=None):
    """等待人工完成登录/验证：按回车立即继续，否则最多等待 seconds 秒"""
    import select
    print(f"需要人工介入（登录/验证）。按回车立即继续，或最多等待 {int(seconds)} 秒…")
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
            print(f"人工处理完成，重新打开页面：{reopen_url}")
            page.goto(reopen_url, wait_until="domcontentloaded", timeout=45000)
            human_pause(page, 2, 4)
        except Exception:
            pass


def goto_ready(page, url, timeout_ms=45000):
    """导航到 URL 并依次处理超时/年龄确认/Cloudflare/登录，返回页面是否可用"""
    for attempt in range(2):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        except PlaywrightTimeoutError:
            print(f"页面加载超时(第{attempt+1}次): {url}")
        except Exception as e:
            print(f"导航失败: {e}")
        human_pause(page)
        if is_age_confirmation_pw(page):
            dismiss_age_confirmation_pw(page)
        if is_cloudflare_challenge_pw(page):
            print("检测到 Cloudflare 验证页，等待通过…")
            if not wait_for_cloudflare_pass(page, base_url=RUN_BASE_URL):
                return False
        if is_cloudflare_challenge_pw(page):
            continue
        if is_login_page_pw(page) and not is_logged_in_pw(page):
            print("检测到登录页，尝试自动填充后等待人工验证…")
            handle_login_pw(page)
            wait_for_manual_login(page, seconds=300, reopen_url=url)
            if is_login_page_pw(page):
                print("提示：仍未登录，将以游客身份继续（部分内容可能不可见）")
        return True
    return False


def do_manual_login(base_url):
    """打开持久会话浏览器，等待用户手动登录；登录态保存到 persisted 配置目录"""
    session = setup_playwright_session(use_proxy=guess_use_proxy(base_url), headless=False,
                                       browser_name="msedge", profile_mode="persisted")
    if not session:
        print("无法启动持久会话浏览器", file=sys.stderr)
        return False
    page = session["page"]
    try:
        page.goto(base_url, wait_until="domcontentloaded", timeout=60000)
        if is_age_confirmation_pw(page):
            dismiss_age_confirmation_pw(page)
        if is_logged_in_pw(page):
            print("当前持久会话已是登录状态，无需重新登录")
            return True
        print(f"请在打开的浏览器窗口中登录 {base_url}，完成后按回车继续…")
        try:
            input()
        except EOFError:
            time.sleep(300)
        if is_logged_in_pw(page):
            print("登录成功，登录态已保存到持久会话目录（.playwright_user_data/msedge）")
            return True
        print("未检测到登录态，请检查是否登录成功")
        return False
    finally:
        close_playwright_session(session)


# ---------- URL 构造 ----------
def build_page_url(actor_url, page_num, filter_val=DEFAULT_FILTER):
    """构造分页URL：第1页强制加入 t=<filter> 与 sort_type=0，后续页追加 page=N"""
    if page_num <= 1:
        try:
            parsed = urlparse(actor_url)
            query_pairs = dict(parse_qsl(parsed.query, keep_blank_values=True))
            query_pairs['t'] = filter_val
            query_pairs['sort_type'] = '0'
            new_query = urlencode(query_pairs)
            return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
        except Exception:
            sep = '&' if '?' in actor_url else '?'
            return f"{actor_url}{sep}t={filter_val}&sort_type=0"
    if '?' in actor_url:
        return f"{actor_url}&page={page_num}&sort_type=0&t={filter_val}"
    return f"{actor_url}?page={page_num}&sort_type=0&t={filter_val}"


# ---------- 列表页解析 ----------
def extract_page_video_links(page):
    """从当前列表页提取视频详情链接"""
    selectors = [
        'div.item a.box[href*="/v/"]',
        'div.item a[href*="/v/"]',
        '.movie-list .item a[href*="/v/"]',
        'a[href*="/v/"]',
    ]
    for sel in selectors:
        try:
            hrefs = page.eval_on_selector_all(sel, "els => els.map(e => e.href)")
            hrefs = [h for h in hrefs if h and '/v/' in h]
            if hrefs:
                return hrefs
        except Exception:
            continue
    return []


def collect_actor_video_links(page, actor_url, start_page=1, end_page=None, filter_val=DEFAULT_FILTER):
    """
    流式爬取演员所有视频链接（Playwright版）

    1. 构建分页URL，支持 t=<filter> 过滤（默认单体+可下载）
    2. 逐页解析视频列表，提取详情页链接
    3. 连续两页无新链接视为末页
    """
    links = []
    seen = set()
    empty_streak = 0
    page_num = start_page
    while True:
        url = build_page_url(actor_url, page_num, filter_val)
        print(f"访问第{page_num}页: {url}")
        if not goto_ready(page, url):
            print("页面不可用，结束翻页")
            break
        try:
            page.wait_for_selector('div.item a[href*="/v/"], a[href*="/v/"]', timeout=20000)
        except PlaywrightTimeoutError:
            pass
        except Exception:
            pass
        hrefs = extract_page_video_links(page)
        new_links = [h for h in hrefs if h not in seen]
        if not new_links:
            empty_streak += 1
            print(f"第{page_num}页无新增链接（连续{empty_streak}次）")
            if empty_streak >= 2:
                print("已到末页，结束翻页")
                break
            page_num += 1
            continue
        empty_streak = 0
        seen.update(new_links)
        links.extend(new_links)
        print(f"第{page_num}页新增{len(new_links)}个视频链接，总计{len(links)}")
        if end_page is not None and page_num >= end_page:
            break
        page_num += 1
    return links


# ---------- 详情页解析 ----------
def _text_first(page, css_list, xpath_list=()):
    for sel in list(css_list) + [f"xpath={xp}" for xp in xpath_list]:
        try:
            loc = page.locator(sel)
            if loc.count() > 0:
                txt = loc.first.inner_text().strip()
                if txt:
                    return txt
        except Exception:
            continue
    return 'N/A'


def _texts_by_xpath(page, xpaths):
    for xp in xpaths:
        try:
            loc = page.locator(f"xpath={xp}")
            if loc.count() > 0:
                txt = loc.first.inner_text().strip()
                if txt:
                    return txt
        except Exception:
            continue
    return 'N/A'


def _parse_actors(page):
    """提取演员（优先识别新版 actor-female 标记，兼容旧版 ♀ 符号）"""
    actors = []
    sec_xpaths = [
        "//strong[text()='演員:']/following-sibling::span[1]",
        "//strong[text()='演員']/following-sibling::span[1]",
        "//strong[text()='Actors:']/following-sibling::span[1]",
    ]
    for xp in sec_xpaths:
        try:
            sec = page.locator(f"xpath={xp}")
            if sec.count() == 0:
                continue
            links = sec.first.locator("a")
            for i in range(links.count()):
                a = links.nth(i)
                nm = (a.inner_text() or '').strip()
                lk = a.get_attribute('href') or ''
                try:
                    # 新版结构: 演员链接自身或其父元素带 actor-female class
                    is_female = 'actor-female' in (a.get_attribute('class') or '').split()
                    if not is_female:
                        try:
                            pcl = a.locator("xpath=..").get_attribute('class') or ''
                            is_female = 'actor-female' in pcl.split()
                        except Exception:
                            pass
                    if not is_female:
                        # 旧版结构: 链接后跟 <strong class="symbol female">♀</strong>
                        fem = a.locator("xpath=./following-sibling::strong[contains(@class,'female')][1]")
                        if fem.count() == 0 or '♀' not in (fem.first.inner_text() or ''):
                            continue
                except Exception:
                    continue
                if nm:
                    actors.append({'name': nm, 'link': urljoin(RUN_BASE_URL or '', lk)})
            if actors:
                break
        except Exception:
            continue
    return actors


def _parse_magnets(page):
    magnets = []
    try:
        loc = page.locator(".magnet-links [data-clipboard-text^='magnet:?xt']")
        for i in range(loc.count()):
            v = loc.nth(i).get_attribute('data-clipboard-text')
            if v:
                magnets.append(v)
    except Exception:
        pass
    if not magnets:
        try:
            hrefs = page.eval_on_selector_all("a[href^='magnet:?']", "els => els.map(e => e.href)")
            magnets = [h for h in hrefs if h]
        except Exception:
            pass
    if not magnets:
        try:
            loc = page.locator("xpath=//a[contains(text(),'Copy')][@data-clipboard-text]")
            for i in range(loc.count()):
                v = loc.nth(i).get_attribute('data-clipboard-text')
                if v:
                    magnets.append(v)
        except Exception:
            pass
    # 去重并保持顺序
    seen = set()
    uniq = []
    for m in magnets:
        if m not in seen:
            seen.add(m)
            uniq.append(m)
    return uniq


def parse_detail(page, detail_url, max_retries=2):
    """解析单个视频详情页，返回字段字典；安全验证/不可用时返回 None"""
    for attempt in range(max_retries):
        try:
            if not goto_ready(page, detail_url):
                return None
            try:
                page.wait_for_selector('.container, #content, .panel, h2.title', timeout=15000)
            except Exception:
                pass
            human_pause(page)

            title = _text_first(page, ['h2.title', 'h1.title', '.current-title', 'h2', 'h1', '.title'])
            if title == 'N/A':
                raise ValueError("Could not parse title")

            video_id = _texts_by_xpath(page, [
                "//strong[text()='番號:']/following-sibling::span[1]",
                "//strong[text()='識別碼:']/following-sibling::span[1]",
                "//strong[text()='ID:']/following-sibling::span[1]",
                "//p[contains(@class,'video-id')]/strong[1]",
                "//span[contains(@class,'video-id')][1]",
            ])

            release_date = _texts_by_xpath(page, [
                "//strong[text()='日期:']/following-sibling::span[1]",
                "//strong[text()='發行日期:']/following-sibling::span[1]",
                "//strong[text()='Date:']/following-sibling::span[1]",
                "//span[@class='release-date'][1]",
            ])

            duration = _texts_by_xpath(page, [
                "//strong[text()='時長:']/following-sibling::span[1]",
                "//strong[text()='Duration:']/following-sibling::span[1]",
                "//span[@class='video-duration'][1]",
            ])

            rating = 'N/A'
            rating_txt = _texts_by_xpath(page, [
                "//strong[text()='評分:']/following-sibling::span[1]",
                "//strong[text()='Rating:']/following-sibling::span[1]",
                "//span[contains(@class,'score')][1]",
            ])
            if rating_txt != 'N/A':
                m = re.search(r'(\d+(?:\.\d+)?)', rating_txt)
                rating = m.group(1) if m else rating_txt

            tags = []
            try:
                loc = page.locator("xpath=//strong[text()='類別:']/following-sibling::span[1]/a | //strong[text()='Tags:']/following-sibling::span[1]/a")
                for i in range(loc.count()):
                    t = (loc.nth(i).inner_text() or '').strip()
                    if t:
                        tags.append(t)
            except Exception:
                pass

            actors = _parse_actors(page)

            studio = _texts_by_xpath(page, [
                "//strong[text()='片商:']/following-sibling::span[1]",
                "//strong[text()='製作商:']/following-sibling::span[1]",
                "//strong[text()='Studio:']/following-sibling::span[1]",
            ])

            img_url = ''
            for sel in ['div.cover img', '.cover img', 'img.video-cover', 'img[src*="cover"]', 'img[src*="thumb"]', '.movie-panel img']:
                try:
                    loc = page.locator(sel)
                    if loc.count() > 0:
                        img_url = loc.first.get_attribute('src') or ''
                        if img_url:
                            if not img_url.startswith('http'):
                                img_url = urljoin(RUN_BASE_URL or detail_url, img_url)
                            break
                except Exception:
                    continue

            magnet_links = _parse_magnets(page)

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
                'cover_image_url': img_url,
                'magnet_links': magnet_links,
            }
        except Exception as e:
            print(f"解析详情失败({attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                random_delay(3, 5)
                continue
            return {
                'title': 'N/A', 'video_id': 'N/A', 'detail_url': detail_url,
                'release_date': 'N/A', 'duration': 'N/A', 'rating': 'N/A',
                'tags': [], 'actors': [], 'studio': 'N/A',
                'cover_image_url': '', 'magnet_links': [],
            }


# ---------- CSV ----------
CSV_HEADERS = ['title', 'actor', 'release_date', 'video_id', 'detail_url', 'studio',
               'rating', 'duration', 'magnet_link', 'all_magnet_links']


def open_csv_stream(csv_path):
    is_new = not os.path.exists(csv_path)
    f = open(csv_path, 'a', newline='', encoding='utf-8')
    writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
    if is_new:
        writer.writeheader()
    return f, writer


def load_processed_urls_from_csv(csv_path):
    processed = set()
    if not os.path.exists(csv_path):
        return processed
    try:
        with open(csv_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            use_detail = 'detail_url' in (reader.fieldnames or [])
            use_vid = 'video_id' in (reader.fieldnames or [])
            for row in reader:
                if not row:
                    continue
                key = None
                if use_detail:
                    key = (row.get('detail_url') or '').strip()
                if not key and use_vid:
                    key = (row.get('video_id') or '').strip()
                if key:
                    processed.add(key)
    except Exception as e:
        print(f"读取已处理CSV失败（忽略，视为无已处理项）: {e}")
    return processed


def find_existing_actor_csv(actor_name, search_dir=None):
    """在 results 目录（其次当前目录）中寻找该演员的既有CSV，返回最新修改的一个"""
    try:
        short_actor = actor_name.strip()
        try:
            short_actor = re.split(r"[，,\s]+", short_actor, maxsplit=1)[0]
        except Exception:
            pass
        base = safe_filename(short_actor)
        primary_dir = search_dir or get_results_dir()
        dirs_to_check = [primary_dir]
        cwd_dir = os.getcwd()
        if primary_dir != cwd_dir:
            dirs_to_check.append(cwd_dir)
        candidates = []
        for directory in dirs_to_check:
            try:
                for fn in os.listdir(directory):
                    if not fn.lower().endswith('.csv'):
                        continue
                    if fn.startswith(f"javdb_{base}_") or fn == f"javdb_{base}.csv":
                        full = os.path.join(directory, fn)
                        try:
                            mtime = os.path.getmtime(full)
                        except Exception:
                            mtime = 0
                        candidates.append((mtime, full))
            except Exception:
                pass
        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            return candidates[0][1]
    except Exception:
        pass
    return None


# ---------- main ----------
def main():
    parser = argparse.ArgumentParser(
        description='JAVDB演员作品信息爬虫（Playwright版）- 支持断点续爬、智能过滤、Cloudflare处理',
        epilog='示例: python javdb_actor_all.py "https://javdb571.com/actors/5Dya" --filter s --csv output.csv',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('actor_url', nargs='?', default='', help='演员首页链接，如 https://javdb571.com/actors/5Dya')
    parser.add_argument('actor_name_pos', nargs='?', default='',
                        help='演员名（位置参数，等价于 --name，兼容 README 旧用法）')
    parser.add_argument('max_pages_pos', nargs='?', type=int, default=None,
                        help='最大页数（位置参数，等价于 --to，兼容 README 旧用法）')
    parser.add_argument('--from', dest='from_page', type=int, default=1, help='起始页，默认 1')
    parser.add_argument('--to', dest='to_page', type=int, default=None, help='结束页，默认自动翻到末页')
    parser.add_argument('--name', dest='actor_name', default='', help='演员名（可选），不提供则自动提取或使用ID')
    parser.add_argument('--csv', dest='csv_path', default='', help='输出CSV路径（可选，存在则启用断点续爬并追加写入）')
    parser.add_argument('--filter', dest='filter_val', default=DEFAULT_FILTER,
                        help="列表过滤参数 t 的值，默认 'd,s'（单体+可下载）；'s'=全部单体作品，'d'=仅可下载，'a'=全部")
    parser.add_argument('--legacy-filter', dest='legacy_filter', action='store_true',
                        help="与旧版一致：仅使用 t=d（不限定单体）；等价于 --filter d")
    parser.add_argument('--browser', dest='browser', default='msedge', choices=['msedge', 'chromium', 'firefox'],
                        help='Playwright 浏览器内核，默认 msedge')
    parser.add_argument('--profile-mode', dest='profile_mode', default='persisted', choices=['persisted', 'fresh'],
                        help='persisted=复用固定登录态（默认，登录态存于 .playwright_user_data/<browser>）；fresh=临时会话')
    parser.add_argument('--headless', dest='headless', action='store_true', help='无头模式运行（默认有头，便于人工过验证）')
    parser.add_argument('--proxy', dest='proxy', action='store_true', default=None,
                        help='强制使用 SOCKS5 代理（javdb.com 主站默认开启）')
    parser.add_argument('--no-proxy', dest='proxy', action='store_false',
                        help='强制直连（镜像域名 javdbNNN.com 默认直连）')
    parser.add_argument('--min-delay', dest='min_delay', type=float, default=3.0, help='最小随机等待秒数，默认 3.0')
    parser.add_argument('--max-delay', dest='max_delay', type=float, default=7.0, help='最大随机等待秒数，默认 7.0')
    parser.add_argument('--no-human-actions', dest='no_human_actions', action='store_true', help='禁用随机滚动与鼠标移动')
    parser.add_argument('--login', dest='do_login', action='store_true',
                        help='打开持久会话浏览器进行手动登录，登录态保存后退出（无需演员链接）')
    args = parser.parse_args()

    global CRAWL_MIN_DELAY, CRAWL_MAX_DELAY, HUMAN_ACTIONS, RUN_BASE_URL
    CRAWL_MIN_DELAY = max(0.5, float(args.min_delay or 3.0))
    CRAWL_MAX_DELAY = max(CRAWL_MIN_DELAY, float(args.max_delay or 7.0))
    HUMAN_ACTIONS = not bool(args.no_human_actions)
    filter_val = 'd' if args.legacy_filter else (args.filter_val or DEFAULT_FILTER).strip()

    if args.do_login:
        base = args.actor_url.strip() or f"https://{JAVDB_PROXY_DOMAIN}"
        RUN_BASE_URL = url_origin(base)
        ok = do_manual_login(RUN_BASE_URL)
        sys.exit(0 if ok else 1)

    actor_url = args.actor_url.strip()
    if not actor_url:
        parser.error("请提供演员首页链接，或使用 --login 进入手动登录流程")
    if '/actors/' not in actor_url:
        print("警告：输入链接似乎不是演员页（未包含 /actors/），仍将尝试抓取")

    from_page = max(1, int(args.from_page or 1))
    to_page = args.to_page if args.to_page and args.to_page >= from_page else None
    if to_page is None and args.max_pages_pos:
        to_page = max(from_page, int(args.max_pages_pos))
    actor_name = args.actor_name.strip() or (args.actor_name_pos or '').strip()
    RUN_BASE_URL = url_origin(actor_url)
    use_proxy = guess_use_proxy(actor_url) if args.proxy is None else bool(args.proxy)
    print(f"目标域名: {RUN_BASE_URL} | 代理: {'socks5://%s:%s' % (SOCKS5_PROXY_HOST, SOCKS5_PROXY_PORT) if use_proxy else '直连'}"
          f" | 过滤: t={filter_val} | 会话: {args.profile_mode}/{args.browser}")

    session = setup_playwright_session(use_proxy=use_proxy, headless=args.headless,
                                       browser_name=args.browser, profile_mode=args.profile_mode)
    if not session:
        sys.exit(1)
    page = session["page"]

    try:
        first_page_url = build_page_url(actor_url, from_page, filter_val)
        if not goto_ready(page, first_page_url):
            print("首页不可用（可能是验证未通过），退出")
            sys.exit(1)

        # 提取演员名
        if not actor_name:
            for sel in ['strong.current-title', 'h2.title', 'h1.title', '.title']:
                try:
                    loc = page.locator(sel)
                    if loc.count() > 0:
                        txt = (loc.first.inner_text() or '').strip()
                        if txt:
                            actor_name = re.sub(r"\s*[-|｜].*$", "", txt.splitlines()[0]).strip()
                            break
                except Exception:
                    continue
        if not actor_name:
            actor_name = extract_actor_id_from_url(actor_url) or 'actor'
        print(f"演员: {actor_name}")

        if to_page is None:
            print("未指定结束页，将自动翻页直至末页")

        print(f"准备收集详情链接，页范围: {from_page} → {'末页' if to_page is None else to_page}")
        links = collect_actor_video_links(page, actor_url, start_page=from_page, end_page=to_page, filter_val=filter_val)
        print(f"共收集到 {len(links)} 条详情链接")

        # CSV 输出与断点续爬（与旧版逻辑一致）
        results_dir = get_results_dir()
        if args.csv_path:
            out_path = os.path.abspath(args.csv_path)
        else:
            existing = find_existing_actor_csv(actor_name, search_dir=results_dir)
            if existing:
                out_path = existing
                print(f"检测到已有CSV，启用断点续爬: {out_path}")
            else:
                short_actor = actor_name.strip()
                try:
                    short_actor = re.split(r"[，,\s]+", short_actor, maxsplit=1)[0]
                except Exception:
                    pass
                out_path = os.path.join(results_dir, safe_filename(f"javdb_{short_actor}.csv"))
        resume_mode = os.path.exists(out_path)
        processed_urls = load_processed_urls_from_csv(out_path) if resume_mode else set()
        f_csv, writer = open_csv_stream(out_path)
        print(f"CSV输出: {out_path}")
        if resume_mode:
            print(f"断点续爬启用：已存在 {len(processed_urls)} 条记录，将跳过这些详情链接")

        remaining_links = [l for l in links if l not in processed_urls] if processed_urls else links
        pre_skipped = len(links) - len(remaining_links)
        if pre_skipped > 0:
            print(f"根据已爬取 detail_url 预过滤，跳过 {pre_skipped} 条，剩余 {len(remaining_links)} 条待解析")

        skipped = 0
        written = 0
        try:
            for idx, durl in enumerate(remaining_links, start=1):
                print(f"解析详情({idx}/{len(remaining_links)}): {durl}")
                if durl in processed_urls:
                    skipped += 1
                    print("已在CSV中存在，跳过")
                    continue
                info = parse_detail(page, durl, max_retries=2)
                if info is None:
                    skipped += 1
                    print("安全验证或页面不可用，未写入CSV，跳过")
                    continue
                best = find_best_magnet_link(info.get('magnet_links', []))
                all_links = info.get('magnet_links', [])
                row = {
                    'title': info.get('title', 'N/A'),
                    'actor': actor_name,
                    'release_date': info.get('release_date', 'N/A'),
                    'video_id': info.get('video_id', 'N/A'),
                    'detail_url': durl,
                    'studio': info.get('studio', 'N/A'),
                    'rating': info.get('rating', 'N/A'),
                    'duration': info.get('duration', 'N/A'),
                    'magnet_link': best or '',
                    'all_magnet_links': '; '.join(all_links) if all_links else '',
                }
                try:
                    writer.writerow(row)
                    f_csv.flush()
                    processed_urls.add(durl)
                    written += 1
                except Exception as e:
                    print(f"写入CSV失败: {e}")
        finally:
            with suppress(Exception):
                f_csv.close()

        print(f"全部详情解析完成，CSV已写入。新增 {written} 条，跳过 {skipped} 条。")

    finally:
        close_playwright_session(session)


if __name__ == "__main__":
    main()
