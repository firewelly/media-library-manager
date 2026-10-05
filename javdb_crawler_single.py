import time
import random
import requests
import os
import re
import json
import sys
import tempfile
import shutil
from urllib.parse import urljoin, urlparse
import subprocess
from contextlib import suppress
from config import SOCKS5_PROXY_HOST, SOCKS5_PROXY_PORT, MIN_DELAY, MAX_DELAY, get_javdb_base_url, USE_SOCKS5_PROXY, JAVDB_DIRECT_DOMAIN, JAVDB_ALTERNATE_DIRECT_DOMAINS
from utils.runtime import runtime_dir, runtime_path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
except Exception:
    sync_playwright = None
    PlaywrightTimeoutError = Exception

RESULTS_DIR = runtime_path('results')
IMAGES_DIR = runtime_path('results', 'images')
os.makedirs(IMAGES_DIR, exist_ok=True)
COVERS_DIR = IMAGES_DIR
REQUEST_LANGUAGE = "zh-CN,zh;q=0.9,ja;q=0.8,en;q=0.7"
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

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
    return False

def get_base_url_candidates(use_proxy: bool) -> list[str]:
    if use_proxy:
        return [get_javdb_base_url(True)]
    domains = []
    if isinstance(JAVDB_DIRECT_DOMAIN, str) and JAVDB_DIRECT_DOMAIN.strip():
        domains.append(JAVDB_DIRECT_DOMAIN.strip())
    if isinstance(JAVDB_ALTERNATE_DIRECT_DOMAINS, list):
        for d in JAVDB_ALTERNATE_DIRECT_DOMAINS:
            if isinstance(d, str) and d.strip():
                domains.append(d.strip())
    seen = set()
    uniq = []
    for d in domains:
        low = d.lower()
        if low in seen:
            continue
        seen.add(low)
        uniq.append(d)
    return [f"https://{d}" for d in uniq]

def normalize_javdb_url_to_base(url: str, base_url: str) -> str:
    try:
        if not url:
            return url
        target_host = urlparse(base_url).netloc
        if not target_host:
            return url
        p = urlparse(url)
        host = (p.netloc or '').lower()
        if 'javdb' in host:
            p = p._replace(netloc=target_host)
            return p.geturl()
        return url
    except Exception:
        return url

def random_delay(min_seconds=MIN_DELAY, max_seconds=MAX_DELAY):
    """Random delay to simulate human behavior"""
    delay = random.uniform(min_seconds, max_seconds)
    time.sleep(delay)

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

def download_image(img_url, filename, use_proxy=True, base_url=None):
    """Download image to local and return absolute path with inferred extension"""
    try:
        proxies = None
        if use_proxy:
            proxies = {
                'http': f'socks5://{SOCKS5_PROXY_HOST}:{SOCKS5_PROXY_PORT}',
                'https': f'socks5://{SOCKS5_PROXY_HOST}:{SOCKS5_PROXY_PORT}'
            }

        headers = {
            'User-Agent': DEFAULT_USER_AGENT,
            'Accept-Language': REQUEST_LANGUAGE,
            'Referer': base_url or get_javdb_base_url(use_proxy)
        }

        try:
            if proxies:
                response = requests.get(img_url, headers=headers, proxies=proxies, timeout=30)
                response.raise_for_status()
            else:
                response = requests.get(img_url, headers=headers, timeout=30)
                response.raise_for_status()
        except Exception:
            # Fallback without proxy
            response = requests.get(img_url, headers=headers, timeout=30)
            response.raise_for_status()

        os.makedirs(COVERS_DIR, exist_ok=True)
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

        safe_name = safe_filename(filename)
        img_path = os.path.join(COVERS_DIR, f"{safe_name}{ext}")
        with open(img_path, 'wb') as f:
            f.write(response.content)
        return os.path.abspath(img_path)
    except Exception as e:
        print(f"Image download failed {img_url}: {e}", file=sys.stderr)
        return None

def get_attempt_configs(use_proxy_default: bool):
    if use_proxy_default:
        # 代理优先：避免无代理尝试遍历大量备用域名浪费时间
        return [
            {"use_proxy": True, "headless": False},
            {"use_proxy": True, "headless": True},
            {"use_proxy": False, "headless": False},
            {"use_proxy": False, "headless": True},
        ]
    return [
        {"use_proxy": False, "headless": False},
        {"use_proxy": False, "headless": True},
    ]

def get_browser_preferences():
    return ["msedge", "firefox"]


def get_profile_modes():
    # persisted(固定用户cookie/登录态) 优先，fresh(每次新建临时状态) 保留作为回退
    return ["persisted", "fresh"]



def _persistent_profile_root(kind=".playwright_user_data"):
    """返回持久化浏览器 profile 的根目录。

    固定放在**项目目录**下（而非 sys.argv[0] 所在目录）：
    先前若从 /tmp 下运行脚本，profile 会落到 /tmp，被系统定期清理后登录态就"失效"了。
    可用环境变量 JAVDB_USER_DATA_DIR 覆盖。
    """
    env = os.getenv("JAVDB_USER_DATA_DIR")
    if env:
        return env
    if getattr(sys, "frozen", False):          # PyInstaller 打包后跟随可执行文件目录
        return runtime_path(kind)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), kind)


def setup_playwright_session(use_proxy=True, headless=True, browser_name="msedge", profile_mode="persisted"):
    if sync_playwright is None:
        return None
    proxy = None
    if use_proxy:
        proxy = {"server": f"socks5://{SOCKS5_PROXY_HOST}:{SOCKS5_PROXY_PORT}"}
    if profile_mode == "fresh":
        parent = _persistent_profile_root(".playwright_user_data_fresh")
        parent = os.path.join(parent, browser_name) if not parent.endswith(browser_name) else parent
        os.makedirs(parent, exist_ok=True)
        user_data_dir = tempfile.mkdtemp(prefix="pw_", dir=parent)
        cleanup_user_data_dir = user_data_dir
    else:
        user_data_dir = os.path.join(_persistent_profile_root(".playwright_user_data"), browser_name)
        os.makedirs(user_data_dir, exist_ok=True)
        cleanup_user_data_dir = None
    launch_kwargs = {
        "headless": headless,
        "proxy": proxy,
        "locale": "zh-CN",
        "user_agent": DEFAULT_USER_AGENT,
        "extra_http_headers": {"Accept-Language": REQUEST_LANGUAGE},
        "args": [
            "--disable-blink-features=AutomationControlled",
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
            context = pw.chromium.launch_persistent_context(user_data_dir, channel="msedge", **launch_kwargs)
        elif browser_name == "firefox":
            firefox_kwargs = dict(launch_kwargs)
            firefox_kwargs["firefox_user_prefs"] = {
                "intl.accept_languages": "zh-CN,zh,ja,en-US,en"
            }
            context = pw.firefox.launch_persistent_context(user_data_dir, **firefox_kwargs)
        else:
            context = pw.chromium.launch_persistent_context(user_data_dir, **launch_kwargs)
        page = context.pages[0] if context.pages else context.new_page()
        page.add_init_script("""
            Object.defineProperty(navigator, 'language', { get: () => 'zh-CN' });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'ja', 'en-US', 'en'] });
        """)
        return {
            "pw": pw,
            "context": context,
            "page": page,
            "browser_name": browser_name,
            "profile_mode": profile_mode,
            "cleanup_user_data_dir": cleanup_user_data_dir
        }
    except Exception as e:
        print(f"[DEBUG] Playwright启动失败({browser_name}): {e}", file=sys.stderr)
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


def is_logged_in_pw(page):
    """检测 javdb 页面是否处于已登录状态（导航栏出现登出/用户入口）"""
    try:
        if page.locator("a[href*='sign_out']").count() > 0:
            return True
        for text in ["登出", "ログアウト", "Sign Out", "登出"]:
            if page.locator(f"a:has-text('{text}')").count() > 0:
                return True
        if page.locator(".navbar-item.has-dropdown .navbar-link img.avatar, a[href*='/users/']").count() > 0:
            return True
        return False
    except Exception:
        return False


def do_manual_login():
    """打开持久会话(persisted profile)浏览器，等待用户手动登录 javdb。
    登录态(cookie)会保存在 .playwright_user_data/<browser> 中，供后续爬虫复用。
    用法: python3 javdb_crawler_single.py --login
    """
    if sync_playwright is None:
        print("[ERROR] Playwright 未安装，无法执行登录流程", file=sys.stderr)
        return False
    attempt = get_attempt_configs(USE_SOCKS5_PROXY)[0]
    session = setup_playwright_session(
        use_proxy=attempt["use_proxy"], headless=False,
        browser_name="msedge", profile_mode="persisted")
    if not session:
        print("[ERROR] 无法启动持久会话浏览器", file=sys.stderr)
        return False
    page = session["page"]
    try:
        base_url = get_base_url_candidates(attempt["use_proxy"])[0]
        page.goto(base_url, wait_until="domcontentloaded", timeout=60000)
        random_delay(1.5, 3.0)
        if is_cloudflare_challenge_pw(page):
            print("检测到 Cloudflare 验证页，请在浏览器中完成验证...", file=sys.stderr)
            if not wait_for_cloudflare_clear_pw(page, timeout_seconds=180):
                print("[ERROR] Cloudflare 验证未通过", file=sys.stderr)
                return False
        if is_age_confirmation_pw(page):
            dismiss_age_confirmation_pw(page)
        if is_logged_in_pw(page):
            print("[INFO] 持久会话已处于登录状态，无需重新登录", file=sys.stderr)
            return True
        print("[INFO] 请在打开的浏览器窗口中登录 javdb（5 分钟内完成）...", file=sys.stderr)
        login_url = base_url.rstrip("/") + "/users/sign_in?locale=zh"
        with suppress(Exception):
            page.goto(login_url, wait_until="domcontentloaded", timeout=60000)
        for _ in range(150):
            if is_logged_in_pw(page):
                random_delay(2, 3)
                with suppress(Exception):
                    page.goto(base_url, wait_until="domcontentloaded", timeout=60000)
                    random_delay(1, 2)
                if is_logged_in_pw(page):
                    print("[INFO] 登录成功，登录态已保存到持久会话，后续爬虫将自动复用", file=sys.stderr)
                    return True
            time.sleep(2)
        print("[ERROR] 等待登录超时", file=sys.stderr)
        return False
    finally:
        close_playwright_session(session)


def is_login_page_pw(page):
    try:
        email_count = page.locator('input[type="email"], input[name="email"]').count()
        password_count = page.locator('input[type="password"], input[name="password"]').count()
        submit_count = page.locator('button[type="submit"], input[type="submit"], .btn-primary').count()
        return email_count > 0 and password_count > 0 and submit_count > 0
    except Exception:
        return False


def is_cloudflare_challenge_pw(page):
    try:
        title = page.title() or ""
        html = page.content() or ""
        return is_cloudflare_challenge_html(html, title)
    except Exception:
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


def wait_for_cloudflare_clear_pw(page, timeout_seconds=120):
    start = time.time()
    while time.time() - start < timeout_seconds:
        if not is_cloudflare_challenge_pw(page):
            return True
        time.sleep(2)
    return False


def wait_for_manual_login_pw(page, timeout_seconds=180):
    start = time.time()
    while time.time() - start < timeout_seconds:
        if not is_login_page_pw(page) and not is_cloudflare_challenge_pw(page):
            return True
        time.sleep(2)
    return False


def detect_ui_language_pw(page):
    try:
        nav_text = (page.locator("#navbar-menu-hero").first.text_content() or "").lower()
    except Exception:
        nav_text = ""
    if any(k in nav_text for k in ["類別", "排行榜", "演員", "片商", "無碼", "有碼"]):
        return "zh"
    if any(k in nav_text for k in ["ジャンル", "ランキング", "女優", "メーカー", "無修正"]):
        return "ja"
    if any(k in nav_text for k in ["categories", "rankings", "actors", "makers", "uncensored", "censored"]):
        return "en"
    return "unknown"


def ensure_preferred_language_pw(page, context, base_url):
    preferred_order = ["zh", "ja", "en"]
    current = detect_ui_language_pw(page)
    print(f"[DEBUG] 当前页面语言: {current}", file=sys.stderr)
    if current == "zh":
        return True
    domain = urlparse(base_url).hostname or ""
    cookie_candidates = [
        ("locale", "zh"),
        ("lang", "zh"),
        ("language", "zh"),
        ("i18n_redirected", "zh"),
    ]
    with suppress(Exception):
        context.add_cookies([
            {"name": k, "value": v, "domain": domain, "path": "/", "secure": True, "httpOnly": False}
            for k, v in cookie_candidates
        ])
    switch_urls = [
        f"{base_url}/?locale=zh",
        f"{base_url}/?lang=zh",
        f"{base_url}/?hl=zh-CN",
        f"{base_url}/?locale=zh-TW",
        f"{base_url}/?locale=zh-CN",
    ]
    for u in switch_urls:
        try:
            page.goto(u, wait_until="domcontentloaded", timeout=45000)
            random_delay(0.5, 1.0)
            current = detect_ui_language_pw(page)
            if current == "zh":
                print("[INFO] 已切换为中文界面", file=sys.stderr)
                return True
        except Exception:
            pass
    selectors = [
        "a[href*='locale=zh']",
        "a[href*='lang=zh']",
        "a[href*='hl=zh']",
        "a:has-text('中文')",
        "a:has-text('繁體中文')",
        "a:has-text('简体中文')",
    ]
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0:
                loc.click(timeout=5000)
                random_delay(0.8, 1.2)
                current = detect_ui_language_pw(page)
                if current == "zh":
                    print("[INFO] 已通过页面入口切换为中文", file=sys.stderr)
                    return True
        except Exception:
            pass
    current = detect_ui_language_pw(page)
    print(f"[WARN] 语言未成功切换为中文，当前: {current}，回退优先级: {preferred_order}", file=sys.stderr)
    return current in preferred_order


def search_video_by_code_pw(page, video_code, base_url):
    try:
        search_url = f"{base_url}/search?q={video_code}&f=all"
        page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
        random_delay(1, 2)
        # 遍历搜索结果，只接受番号精确匹配的条目（javdb 无结果时会返回模糊匹配，避免张冠李戴）
        cards = page.locator("a[href*='/v/']")
        try:
            n = min(cards.count(), 10)
        except Exception:
            n = 0
        target = (video_code or "").replace(" ", "").replace("-", "").upper()
        for i in range(n):
            try:
                card = cards.nth(i)
                href = card.get_attribute("href") or ""
                if "/v/" not in href:
                    continue
                title_text = ""
                with suppress(Exception):
                    title_text = card.locator(".video-title").first.text_content() or ""
                if not title_text:
                    with suppress(Exception):
                        title_text = card.text_content() or ""
                norm = (title_text or "").replace(" ", "").replace("-", "").upper()
                if target and target in norm:
                    if not href.startswith("http"):
                        href = urljoin(base_url, href)
                    return href
            except Exception:
                continue
        return None
    except Exception:
        return None


def _first_xpath_text_pw(page, xpath_candidates):
    for xp in xpath_candidates:
        try:
            loc = page.locator(f"xpath={xp}").first
            if loc.count() > 0:
                txt = (loc.text_content() or "").strip()
                if txt:
                    return txt
        except Exception:
            continue
    return "N/A"


def parse_detail_pw(page, detail_url, base_url, use_proxy, max_retries=2):
    default_result = {
        'title': 'N/A',
        'video_id': 'N/A',
        'detail_url': detail_url,
        'release_date': 'N/A',
        'duration': 'N/A',
        'rating': 'N/A',
        'tags': [],
        'actors': [],
        'studio': 'N/A',
        'cover_image_url': '',
        'local_image_path': None,
        'magnet_links': []
    }
    for attempt in range(max_retries):
        try:
            page.goto(detail_url, wait_until="domcontentloaded", timeout=60000)
            random_delay(1, 2)
            title = "N/A"
            for sel in ["h2.title", "h1.title", "h2", "h1", ".title"]:
                try:
                    loc = page.locator(sel).first
                    if loc.count() > 0:
                        t = (loc.text_content() or "").strip()
                        if t:
                            title = t
                            break
                except Exception:
                    continue
            if title == "N/A":
                raise ValueError("title not found")
            title = re.sub(r'\s+', ' ', title).strip()
            video_id = _first_xpath_text_pw(page, [
                "//strong[text()='番號:']/following-sibling::span[1]",
                "//strong[text()='識別碼:']/following-sibling::span[1]",
                "//strong[text()='ID:']/following-sibling::span[1]",
            ])
            release_date = _first_xpath_text_pw(page, [
                "//strong[text()='日期:']/following-sibling::span[1]",
                "//strong[text()='發行日期:']/following-sibling::span[1]",
                "//strong[text()='Date:']/following-sibling::span[1]",
            ])
            duration = _first_xpath_text_pw(page, [
                "//strong[text()='時長:']/following-sibling::span[1]",
                "//strong[text()='Duration:']/following-sibling::span[1]",
            ])
            rating_text = _first_xpath_text_pw(page, [
                "//strong[text()='評分:']/following-sibling::span[1]",
                "//strong[text()='Rating:']/following-sibling::span[1]",
            ])
            rating_match = re.search(r'(\d+(?:\.\d+)?)', rating_text)
            rating = rating_match.group(1) if rating_match else (rating_text if rating_text != "N/A" else "N/A")
            tags = []
            for xp in [
                "//strong[text()='類別:']/following-sibling::span[1]/a",
                "//strong[text()='Tags:']/following-sibling::span[1]/a",
            ]:
                try:
                    nodes = page.locator(f"xpath={xp}")
                    if nodes.count() > 0:
                        vals = []
                        for i in range(nodes.count()):
                            txt = (nodes.nth(i).text_content() or "").strip()
                            if txt:
                                vals.append(txt)
                        if vals:
                            tags = vals
                            break
                except Exception:
                    continue
            if not tags:
                with suppress(Exception):
                    vals = page.eval_on_selector_all(
                        '.panel-info a[href*="/tags/"], .genres a, .tags a',
                        "els => els.map(e => (e.textContent || '').trim()).filter(Boolean)"
                    )
                    seen = set()
                    tags = [x for x in vals if not (x in seen or seen.add(x))]
            actors = []
            with suppress(Exception):
                actors = page.evaluate("""
                    () => {
                        // 限定在详情信息面板内，避免抓到导航栏的演员分类入口(censored/uncensored等)
                        const anchors = Array.from(document.querySelectorAll('.panel-block a[href*="/actors/"], .movie-panel-info a[href*="/actors/"]'));
                        const raw = [];
                        for (const a of anchors) {
                            const name = (a.textContent || '').trim();
                            if (!name) continue;
                            let female = false;
                            // 新版结构: 链接自身或其父元素带 actor-female class
                            if ((a.classList && a.classList.contains('actor-female')) ||
                                (a.parentElement && a.parentElement.classList && a.parentElement.classList.contains('actor-female'))) {
                                female = true;
                            } else {
                                // 旧版结构: 链接后跟含 ♀ 或 female class 的兄弟节点
                                let n = a.nextSibling;
                                let guard = 0;
                                while (n && guard < 4) {
                                    const t = (n.textContent || '').trim();
                                    if (t.includes('♀')) { female = true; break; }
                                    if (n.nodeType === 1 && n.classList && (n.classList.contains('female') || n.classList.contains('actor-female'))) { female = true; break; }
                                    n = n.nextSibling;
                                    guard += 1;
                                }
                            }
                            raw.push({name, link: a.href || '', female});
                        }
                        const list = raw.some(x => x.female) ? raw.filter(x => x.female) : raw;
                        const dedup = [];
                        const seen = new Set();
                        for (const x of list) {
                            const k = `${x.name}|${x.link}`;
                            if (!seen.has(k)) {
                                seen.add(k);
                                dedup.push({name: x.name, link: x.link});
                            }
                        }
                        return dedup;
                    }
                """)
            studio = _first_xpath_text_pw(page, [
                "//strong[text()='片商:']/following-sibling::span[1]",
                "//strong[text()='製作商:']/following-sibling::span[1]",
                "//strong[text()='Studio:']/following-sibling::span[1]",
            ])
            img_url = ''
            with suppress(Exception):
                img_url = page.evaluate("""
                    () => {
                        const sels = ['div.cover img', '.cover img', 'img.video-cover', 'img[src*="cover"]', 'img[src*="thumb"]', '.movie-panel img'];
                        for (const sel of sels) {
                            const img = document.querySelector(sel);
                            if (!img) continue;
                            const srcset = img.getAttribute('srcset');
                            if (srcset) {
                                const parts = srcset.split(',').map(x => x.trim()).filter(Boolean);
                                if (parts.length) {
                                    const candidate = parts[parts.length - 1].split(' ')[0];
                                    if (candidate) return candidate;
                                }
                            }
                            const src = img.getAttribute('src') || img.getAttribute('data-src') || '';
                            if (src) return src;
                        }
                        return '';
                    }
                """)
            if img_url and not img_url.startswith("http"):
                img_url = urljoin(base_url, img_url)
            magnet_links = []
            with suppress(Exception):
                magnet_links = page.eval_on_selector_all(
                    '.magnet-links [data-clipboard-text^="magnet:?xt"]',
                    "els => els.map(e => e.getAttribute('data-clipboard-text') || '').filter(Boolean)"
                )
            local_img_path = None
            if img_url and title != 'N/A':
                filename = f"{video_id}_{title}" if video_id != 'N/A' else title
                local_img_path = download_image(img_url, filename, use_proxy=use_proxy, base_url=base_url)
            return {
                'title': title,
                'video_id': video_id,
                'detail_url': detail_url,
                'release_date': release_date,
                'duration': duration,
                'rating': rating,
                'tags': tags,
                'actors': actors or [],
                'studio': studio,
                'cover_image_url': img_url,
                'local_image_path': local_img_path,
                'magnet_links': magnet_links or []
            }
        except Exception as e:
            print(f"Playwright解析失败 (Attempt {attempt + 1}/{max_retries}): {e}", file=sys.stderr)
            if attempt < max_retries - 1:
                random_delay(2, 3)
                continue
            return default_result


def crawl_single_video_playwright(video_code):
    if sync_playwright is None:
        print("[WARN] Playwright未安装，跳过Playwright流程", file=sys.stderr)
        return None
    print(f"[INFO] Starting Playwright crawl for video code: {video_code}", file=sys.stderr)
    for attempt in get_attempt_configs(USE_SOCKS5_PROXY):
        for browser_name in get_browser_preferences():
            for profile_mode in get_profile_modes():
                print(f"[INFO] Playwright attempt - browser: {browser_name}, profile: {profile_mode}, use_proxy: {attempt['use_proxy']}, headless: {attempt['headless']}", file=sys.stderr)
                session = setup_playwright_session(
                    use_proxy=attempt["use_proxy"],
                    headless=attempt["headless"],
                    browser_name=browser_name,
                    profile_mode=profile_mode
                )
                if not session:
                    continue
                page = session["page"]
                try:
                    for base_url in get_base_url_candidates(attempt["use_proxy"]):
                        page.goto(base_url, wait_until="domcontentloaded", timeout=60000)
                        random_delay(1.5, 3.0)
                        if is_cloudflare_challenge_pw(page):
                            print("检测到 Cloudflare 验证页，等待通过...", file=sys.stderr)
                            if attempt["headless"]:
                                print("当前为无头模式，无法人工验证，切换到有界面模式重试。", file=sys.stderr)
                                break
                            if not wait_for_cloudflare_clear_pw(page, timeout_seconds=180):
                                if profile_mode == "persisted":
                                    print("持久会话验证未通过，切换到临时会话重试。", file=sys.stderr)
                                continue
                        if is_age_confirmation_pw(page):
                            print("检测到年龄确认页，尝试自动点击...", file=sys.stderr)
                            if not dismiss_age_confirmation_pw(page):
                                print("未能自动通过年龄确认，请手动点击...", file=sys.stderr)
                                if attempt["headless"]:
                                    break
                                for _ in range(30):
                                    if not is_age_confirmation_pw(page):
                                        break
                                    time.sleep(2)
                        if is_login_page_pw(page):
                            print("检测到登录页，请在浏览器中完成登录...", file=sys.stderr)
                            if attempt["headless"]:
                                break
                            if not wait_for_manual_login_pw(page, timeout_seconds=240):
                                continue
                        ensure_preferred_language_pw(page, session["context"], base_url)
                        detail_url = search_video_by_code_pw(page, video_code, base_url)
                        if not detail_url:
                            continue
                        detail_url = normalize_javdb_url_to_base(detail_url, base_url)
                        page.goto(detail_url, wait_until="domcontentloaded", timeout=60000)
                        random_delay(1.5, 3.0)
                        if is_cloudflare_challenge_pw(page):
                            print("检测到 Cloudflare 验证页，等待通过...", file=sys.stderr)
                            if attempt["headless"]:
                                break
                            if not wait_for_cloudflare_clear_pw(page, timeout_seconds=180):
                                continue
                        if is_age_confirmation_pw(page):
                            print("详情页年龄确认，尝试自动点击...", file=sys.stderr)
                            if not dismiss_age_confirmation_pw(page):
                                print("未能自动通过年龄确认，请手动点击...", file=sys.stderr)
                                if attempt["headless"]:
                                    break
                                for _ in range(30):
                                    if not is_age_confirmation_pw(page):
                                        break
                                    time.sleep(2)
                        if is_login_page_pw(page):
                            print("访问详情页需要登录，请在浏览器中完成登录...", file=sys.stderr)
                            if attempt["headless"]:
                                break
                            if not wait_for_manual_login_pw(page, timeout_seconds=240):
                                continue
                        result = parse_detail_pw(page, detail_url, base_url, attempt["use_proxy"])
                        if result and result.get("title") != "N/A":
                            return result
                except PlaywrightTimeoutError:
                    pass
                except Exception:
                    pass
                finally:
                    close_playwright_session(session)
    return None


def crawl_single_video(video_code):
    return crawl_single_video_playwright(video_code)

if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--login":
        sys.exit(0 if do_manual_login() else 1)
    if len(sys.argv) != 2:
        print("Usage: python javdb_crawler_single.py <video_code> | --login")
        print("Example: python javdb_crawler_single.py CJOD-413")
        print("         python javdb_crawler_single.py --login  # 手动登录并保存固定用户cookie到持久会话")
        sys.exit(1)
    
    video_code = sys.argv[1]
    result = crawl_single_video(video_code)
    
    if result:
        # Output as JSON
        json_result = {
            'title': result['title'],
            'video_id': result['video_id'],
            'detail_url': result['detail_url'],
            'release_date': result['release_date'],
            'duration': result['duration'],
            'rating': result['rating'],
            'studio': result['studio'],
            'tags': result['tags'],
            'actors': result['actors'],
            'cover_image_url': result['cover_image_url'],
            'local_image_path': result['local_image_path'],
            'magnet_links': result['magnet_links']
        }
        print(json.dumps(json_result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"error": "Failed to crawl video information"}, ensure_ascii=False, indent=2))
        sys.exit(1)
