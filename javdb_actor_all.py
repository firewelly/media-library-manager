import os
import re
import sys
import csv
import json
import time
import random
import subprocess
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
from selenium.webdriver import ActionChains

from config import SOCKS5_PROXY_HOST, SOCKS5_PROXY_PORT, BASE_URL, MIN_DELAY, MAX_DELAY, LOGIN_EMAIL, LOGIN_PASSWORD


# ---------- Utils ----------
def random_delay(min_seconds=MIN_DELAY, max_seconds=MAX_DELAY):
    delay = random.uniform(min_seconds, max_seconds)
    time.sleep(delay)

CRAWL_MIN_DELAY = MIN_DELAY
CRAWL_MAX_DELAY = MAX_DELAY
HUMAN_ACTIONS = True
USE_SINGLE_ONLY = True  # 默认仅抓取单体且有磁性链接（t=d,s）；可通过 --legacy-filter 关闭

def human_pause(driver, min_seconds=None, max_seconds=None, do_actions=None):
    ms = (min_seconds if min_seconds is not None else CRAWL_MIN_DELAY)
    mx = (max_seconds if max_seconds is not None else CRAWL_MAX_DELAY)
    random_delay(ms, mx)
    if do_actions is None:
        do_actions = HUMAN_ACTIONS
    if not do_actions:
        return
    try:
        total_h = driver.execute_script("return Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)")
        win_h = driver.execute_script("return window.innerHeight")
        if total_h and win_h:
            max_y = max(0, int(total_h) - int(win_h))
            y = random.randint(0, max_y) if max_y > 0 else 0
            driver.execute_script("window.scrollTo(0, arguments[0]);", y)
        try:
            ac = ActionChains(driver)
            ac.move_by_offset(random.randint(-30, 30), random.randint(-20, 20)).perform()
            ac.move_by_offset(random.randint(-30, 30), random.randint(-20, 20)).perform()
        except Exception:
            pass
    except Exception:
        pass

def get_results_dir():
    """返回并确保存在的 results 目录"""
    d = os.path.join(os.getcwd(), 'results')
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d

def detect_default_edge_user_data_dir():
    """自动检测本机 Edge 用户数据目录（优先 macOS），找不到则返回 None"""
    try:
        sysname = (platform.system() or '').lower()
        if 'darwin' in sysname or 'mac' in sysname:
            p = os.path.expanduser('~/Library/Application Support/Microsoft Edge')
            return p if os.path.isdir(p) else None
        if 'windows' in sysname:
            base = os.environ.get('LOCALAPPDATA', '')
            if base:
                p = os.path.join(base, 'Microsoft', 'Edge', 'User Data')
                return p if os.path.isdir(p) else None
        # linux
        p = os.path.expanduser('~/.config/microsoft-edge')
        return p if os.path.isdir(p) else None
    except Exception:
        return None

def detect_default_edge_profile_directory(user_data_dir):
    """优先返回 'Default' 配置目录，若不存在则返回 None"""
    try:
        if not user_data_dir:
            return None
        d = os.path.join(user_data_dir, 'Default')
        return 'Default' if os.path.isdir(d) else None
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
            # 回退到 ps aux
            try:
                r = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
                s = (r.stdout or '').lower()
                if 'microsoft edge' in s or 'msedge' in s:
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
            try:
                r = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
                s = (r.stdout or '').lower()
                if 'microsoft-edge' in s or 'msedge' in s:
                    return True
            except Exception:
                pass
    except Exception:
        pass
    return False

def get_dedicated_edge_user_data_dir():
    """返回并创建一个专用于 EdgeDriver 的用户数据目录，以持久化登录态。
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

def safe_filename(filename: str) -> str:
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    filename = filename.strip(' .')
    return filename[:200] if len(filename) > 200 else filename


def extract_actor_id_from_url(url: str):
    try:
        path = urlparse(url).path or ""
        m = re.search(r"/actors/([^/\?&#]+)", path)
        return m.group(1) if m else None
    except Exception:
        return None


def setup_driver(user_data_dir: str = None, profile_directory: str = None):
    """Setup MS Edge browser driver and FORCE UI mode (non-headless).
    Optionally attach to an existing Edge user profile to help pass security checks.
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
        # Attach to real Edge user profile to reuse cookies and human signals
        if user_data_dir:
            opts.add_argument(f"--user-data-dir={user_data_dir}")
        if profile_directory:
            opts.add_argument(f"--profile-directory={profile_directory}")
        if use_proxy:
            opts.add_argument(f'--proxy-server=socks5://{SOCKS5_PROXY_HOST}:{SOCKS5_PROXY_PORT}')
            opts.add_argument('--proxy-bypass-list=<-loopback>')
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

    last_error = None
    attempts = [
        {"proxy": True,  "use_service": True,  "label": "ui+proxy+service"},
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

    print(f"MS Edge driver startup failed: {last_error}")
    print("Please make sure MS Edge browser and EdgeDriver are installed")
    print("You can run update_msedge_driver.py to install the driver")
    return None


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


def parse_detail(driver, detail_url, max_retries=2):
    for attempt in range(max_retries):
        try:
            driver.get(detail_url)
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.container, #content, body'))
            )
            human_pause(driver)

            # 如果仍是安全验证页面，则不返回数据以避免写入CSV
            try:
                if is_security_verification_page(driver):
                    print("仍为安全验证页面，跳过该详情")
                    return None
            except Exception:
                pass

            title = 'N/A'
            for selector in ['h2.title', 'h1.title', 'h2', 'h1', '.title']:
                try:
                    el = driver.find_element(By.CSS_SELECTOR, selector)
                    if el and el.text:
                        title = el.text.strip()
                        break
                except:
                    continue
            if title == 'N/A':
                raise ValueError("Could not parse title")

            video_id = 'N/A'
            for xp in [
                "//strong[text()='番號:']/following-sibling::span[1]",
                "//strong[text()='識別碼:']/following-sibling::span[1]",
                "//strong[text()='ID:']/following-sibling::span[1]",
            ]:
                try:
                    el = driver.find_element(By.XPATH, xp)
                    video_id = el.text.strip()
                    break
                except:
                    continue

            release_date = 'N/A'
            for xp in [
                "//strong[text()='日期:']/following-sibling::span[1]",
                "//strong[text()='發行日期:']/following-sibling::span[1]",
                "//strong[text()='Date:']/following-sibling::span[1]",
            ]:
                try:
                    el = driver.find_element(By.XPATH, xp)
                    release_date = el.text.strip()
                    break
                except:
                    continue

            duration = 'N/A'
            for xp in [
                "//strong[text()='時長:']/following-sibling::span[1]",
                "//strong[text()='Duration:']/following-sibling::span[1]",
            ]:
                try:
                    el = driver.find_element(By.XPATH, xp)
                    duration = el.text.strip()
                    break
                except:
                    continue

            rating = 'N/A'
            for xp in [
                "//strong[text()='評分:']/following-sibling::span[1]",
                "//strong[text()='Rating:']/following-sibling::span[1]",
            ]:
                try:
                    el = driver.find_element(By.XPATH, xp)
                    txt = el.text.strip()
                    m = re.search(r'(\d+\.\d+)', txt)
                    rating = m.group(1) if m else txt
                    break
                except:
                    continue

            tags = []
            for xp in [
                "//strong[text()='類別:']/following-sibling::span[1]/a",
                "//strong[text()='Tags:']/following-sibling::span[1]/a",
            ]:
                try:
                    els = driver.find_elements(By.XPATH, xp)
                    tags = [e.text.strip() for e in els]
                    if tags:
                        break
                except:
                    continue

            actors = []
            try:
                sec = driver.find_element(By.XPATH, "//strong[text()='演員:']/following-sibling::span[1]")
                links = sec.find_elements(By.TAG_NAME, "a")
                for a in links:
                    nm = a.text.strip()
                    lk = a.get_attribute('href')
                    try:
                        fem = a.find_element(By.XPATH, "./following-sibling::strong[@class='symbol female'][1]")
                        if fem and '♀' in fem.text:
                            actors.append({'name': nm, 'link': lk})
                    except:
                        continue
            except:
                try:
                    links = driver.find_elements(By.XPATH, "//strong[text()='Actors:']/following-sibling::span[1]//a")
                    for a in links:
                        nm = a.text.strip()
                        lk = a.get_attribute('href')
                        try:
                            fem = a.find_element(By.XPATH, "./following-sibling::strong[@class='symbol female'][1]")
                            if fem and '♀' in fem.text:
                                actors.append({'name': nm, 'link': lk})
                        except:
                            continue
                except:
                    pass

            studio = 'N/A'
            for xp in [
                "//strong[text()='片商:']/following-sibling::span[1]",
                "//strong[text()='製作商:']/following-sibling::span[1]",
                "//strong[text()='Studio:']/following-sibling::span[1]",
            ]:
                try:
                    el = driver.find_element(By.XPATH, xp)
                    studio = el.text.strip()
                    break
                except:
                    continue

            img_url = ''
            for selector in ['div.cover img', '.cover img', 'img.video-cover', 'img[src*="cover"]', 'img[src*="thumb"]', '.movie-panel img']:
                try:
                    img_element = driver.find_element(By.CSS_SELECTOR, selector)
                    if img_element:
                        img_url = img_element.get_attribute('src')
                        if img_url and not img_url.startswith('http'):
                            img_url = urljoin(BASE_URL, img_url)
                        break
                except:
                    continue

            magnet_links = []
            try:
                els = driver.find_elements(By.CSS_SELECTOR, '.magnet-links [data-clipboard-text^="magnet:?xt"]')
                magnet_links = [e.get_attribute('data-clipboard-text') for e in els]
            except Exception:
                try:
                    copy_buttons = driver.find_elements(By.XPATH, "//a[contains(text(), 'Copy')]")
                    magnet_links = [b.get_attribute('data-clipboard-text') for b in copy_buttons]
                except Exception:
                    pass

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
            else:
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
                    'cover_image_url': '',
                    'magnet_links': [],
                }


def build_page_url(actor_url, page_num):
    # 计算筛选参数：默认 t=d,s（单体且有磁性链接）；legacy 模式使用 t=d（旧行为）
    t_val = 'd,s' if USE_SINGLE_ONLY else 'd'
    # 第1页：在输入URL基础上强制加入 t=... 和 sort_type=0
    if page_num <= 1:
        try:
            parsed = urlparse(actor_url)
            query_pairs = dict(parse_qsl(parsed.query, keep_blank_values=True))
            query_pairs['t'] = t_val
            query_pairs['sort_type'] = '0'
            new_query = urlencode(query_pairs)
            return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
        except Exception:
            sep = '&' if '?' in actor_url else '?'
            return f"{actor_url}{sep}t={t_val}&sort_type=0"
    # 后续页：沿用原逻辑追加 page=N，并确保包含 t=... 与 sort_type=0
    if '?' in actor_url:
        return f"{actor_url}&page={page_num}&sort_type=0&t={t_val}"
    return f"{actor_url}?page={page_num}&sort_type=0&t={t_val}"


def is_login_page(driver):
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

def handle_login(driver):
    try:
        email_input = driver.find_element(By.CSS_SELECTOR, 'input[type="email"], input[name="email"]')
        email_input.clear()
        email_input.send_keys(LOGIN_EMAIL)
        random_delay(1, 2)

        password_input = driver.find_element(By.CSS_SELECTOR, 'input[type="password"], input[name="password"]')
        password_input.clear()
        password_input.send_keys(LOGIN_PASSWORD)
        random_delay(1, 2)

        login_button = driver.find_element(By.CSS_SELECTOR, 'button[type="submit"], input[type="submit"], .btn-primary')
        login_button.click()
        print("已提交登录表单，等待人工验证/跳转…")
        return True
    except Exception as e:
        print(f"登录处理异常: {e}")
        return False


def wait_for_manual_login(driver, seconds=300, reopen_url=None):
    # 支持按回车立即继续；否则最长等待seconds秒
    import sys as _sys
    import select as _select
    print(f"检测到登录页，请手工登录。按回车立即继续，或最多等待 {int(seconds)} 秒…")
    try:
        rlist, _, _ = _select.select([_sys.stdin], [], [], seconds)
        if rlist:
            _ = _sys.stdin.readline()
            print("检测到回车，继续执行…")
        else:
            print("等待超时，继续执行…")
    except Exception:
        time.sleep(seconds)
    if reopen_url:
        try:
            print(f"登录处理完成，重新打开页面：{reopen_url}")
            driver.get(reopen_url)
            human_pause(driver)
        except Exception:
            pass


def collect_actor_video_links(driver, actor_url, start_page=1, end_page=None):
    links = []
    page = start_page
    while True:
        url = build_page_url(actor_url, page)
        print(f"访问第{page}页: {url}")
        try:
            driver.get(url)
            human_pause(driver)
            if is_security_verification_page(driver):
                print("检测到安全验证页面，请完成认证后按回车继续…")
                wait_for_manual_login(driver, seconds=300, reopen_url=url)
            if is_login_page(driver):
                print("检测到登录页，等待手工登录（最长5分钟，可按回车立即继续）…")
                wait_for_manual_login(driver, seconds=300, reopen_url=url)
            wait = WebDriverWait(driver, 25)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div.item, .movie-list .item, a[href*="/v/"]')))
            elems = []
            try:
                elems = driver.find_elements(By.CSS_SELECTOR, 'div.item a[href*="/v/"]')
            except Exception:
                pass
            if not elems:
                try:
                    elems = driver.find_elements(By.CSS_SELECTOR, '.movie-list .item a[href*="/v/"]')
                except Exception:
                    pass
            if not elems:
                elems = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/v/"]')
            page_links = []
            for e in elems:
                href = e.get_attribute('href')
                if href and '/v/' in href and href not in links:
                    page_links.append(href)
            if not page_links:
                print("本页未找到更多视频链接，可能已到末页")
                break
            links.extend(page_links)
            print(f"第{page}页新增{len(page_links)}个视频链接，总计{len(links)}")
            # 若指定了结束页，到达后停止；否则继续到下一页直到无链接
            if end_page is not None and page >= end_page:
                break
            page += 1
        except TimeoutException:
            print(f"第{page}页加载超时，尝试直接解析链接")
            try:
                elems = driver.find_elements(By.CSS_SELECTOR, 'div.item a[href*="/v/"], .movie-list .item a[href*="/v/"], a[href*="/v/"]')
                page_links = []
                for e in elems:
                    href = e.get_attribute('href')
                    if href and '/v/' in href and href not in links:
                        page_links.append(href)
                if not page_links:
                    print("解析失败，结束翻页")
                    break
                links.extend(page_links)
                print(f"超时但解析到{len(page_links)}个链接，总计{len(links)}")
                # 若指定了结束页，到达后停止；否则继续到下一页直到无链接
                if end_page is not None and page >= end_page:
                    break
                page += 1
            except Exception:
                print("解析失败，结束翻页")
                break
        except Exception as e:
            print(f"解析第{page}页出错: {e}")
            break
    return links


def open_csv_stream(csv_path):
    is_new = not os.path.exists(csv_path)
    f = open(csv_path, 'a', newline='', encoding='utf-8')
    headers = ['title', 'actor', 'release_date', 'video_id', 'detail_url', 'studio', 'rating', 'duration', 'magnet_link', 'all_magnet_links']
    writer = csv.DictWriter(f, fieldnames=headers)
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
            # 优先使用 detail_url，其次回退到 video_id
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
    """在指定目录中寻找该演员的既有CSV文件，返回最新修改的一个路径"""
    try:
        # 使用短演员名：取第一个逗号或空白前片段
        short_actor = actor_name.strip()
        try:
            short_actor = re.split(r"[，,\s]+", short_actor, maxsplit=1)[0]
        except Exception:
            pass
        base = safe_filename(short_actor)
        # 优先在 results 目录查找，其次回退到当前目录，避免丢失历史文件
        primary_dir = search_dir or get_results_dir()
        dirs_to_check = []
        if primary_dir:
            dirs_to_check.append(primary_dir)
        cwd_dir = os.getcwd()
        if not primary_dir or primary_dir != cwd_dir:
            dirs_to_check.append(cwd_dir)
        candidates = []
        for directory in dirs_to_check:
            try:
                for fn in os.listdir(directory):
                    if not fn.lower().endswith('.csv'):
                        continue
                    # 兼容两种命名：带时间戳的 javdb_<actor>_YYYYmmdd_HHMMSS.csv 与固定名 javdb_<actor>.csv
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


def detect_max_pages_from_current(driver):
    try:
        # 收集所有分页链接中的最大页码
        anchors = driver.find_elements(By.CSS_SELECTOR, 'a[href*="page="]')
        nums = []
        for a in anchors:
            href = a.get_attribute('href') or ''
            m = re.search(r'[?&]page=(\d+)', href)
            if m:
                try:
                    nums.append(int(m.group(1)))
                except Exception:
                    pass
        if nums:
            return max(nums)
        # 备用：分页组件中的数字文本
        candidates = driver.find_elements(By.CSS_SELECTOR, '.pagination li, .pagination a, .page-item, .pages a')
        for el in candidates:
            txt = (el.text or '').strip()
            if txt.isdigit():
                nums.append(int(txt))
        return max(nums) if nums else 10
    except Exception:
        return 10


def main():
    import argparse
    parser = argparse.ArgumentParser(description='JAVDB演员详情流式爬取（UI模式）')
    parser.add_argument('actor_url', help='演员首页链接，如 https://javdb.com/actors/yAW')
    parser.add_argument('--from', dest='from_page', type=int, default=1, help='起始页，默认 1')
    parser.add_argument('--to', dest='to_page', type=int, default=None, help='结束页，默认自动探测最大页')
    parser.add_argument('--name', dest='actor_name', default='', help='演员名（可选），不提供则自动提取或使用ID')
    parser.add_argument('--csv', dest='csv_path', default='', help='输出CSV路径（可选，存在则启用断点续爬并追加写入）')
    parser.add_argument('--user-data-dir', dest='user_data_dir', default='', help='Edge用户数据目录（可选），如 ~/Library/Application Support/Microsoft Edge')
    parser.add_argument('--profile-directory', dest='profile_directory', default='', help='Edge配置目录名（可选），一般为 Default')
    parser.add_argument('--use-dedicated-profile', dest='use_dedicated_profile', action='store_true',
                        help='使用专用EdgeDriver用户数据目录（持久化登录态，避免与系统Edge冲突）')
    parser.add_argument('--legacy-filter', dest='legacy_filter', action='store_true',
                        help='与旧版一致：仅使用 t=d（不限定单体）；默认使用 t=d,s（单体且有磁性链接）')
    parser.add_argument('--min-delay', dest='min_delay', type=float, default=3.0, help='最小随机等待秒数，默认 3.0')
    parser.add_argument('--max-delay', dest='max_delay', type=float, default=7.0, help='最大随机等待秒数，默认 7.0')
    parser.add_argument('--no-human-actions', dest='no_human_actions', action='store_true', help='禁用随机滚动与鼠标移动')
    args = parser.parse_args()

    actor_url = args.actor_url.strip()
    from_page = max(1, int(args.from_page or 1))
    to_page = args.to_page if args.to_page and args.to_page >= from_page else None
    actor_name = args.actor_name.strip()

    # 设置全局节奏参数
    global CRAWL_MIN_DELAY, CRAWL_MAX_DELAY, HUMAN_ACTIONS, USE_SINGLE_ONLY
    CRAWL_MIN_DELAY = max(0.5, float(args.min_delay or 3.0))
    CRAWL_MAX_DELAY = max(CRAWL_MIN_DELAY, float(args.max_delay or 7.0))
    HUMAN_ACTIONS = not bool(args.no_human_actions)
    # 筛选模式：默认单体且有磁性链接；legacy 模式还原旧行为
    USE_SINGLE_ONLY = not bool(args.legacy_filter)

    # 用户数据目录选择逻辑：
    # 1) 若显式提供 --user-data-dir，则优先使用用户提供值
    # 2) 若指定 --use-dedicated-profile，则使用专用目录（与系统 Edge 隔离）
    # 3) 若检测到 Edge 正在运行，则使用专用目录以避免锁冲突并持久化登录态
    # 4) 否则，默认复用系统 Edge 用户数据以提升通过验证概率
    ud_arg = (args.user_data_dir or '').strip()
    pd_arg = (args.profile_directory or '').strip()
    use_dedicated = bool(args.use_dedicated_profile)

    ud = None
    pd = None
    if ud_arg:
        ud = ud_arg
        pd = pd_arg or (detect_default_edge_profile_directory(ud) or 'Default')
        print(f"使用用户提供的 Edge 用户数据目录: {ud}，配置: {pd}")
    elif use_dedicated or is_edge_running():
        if is_edge_running() and not use_dedicated:
            print("检测到 Edge 正在运行，改用专用 EdgeDriver 会话目录以避免冲突并持久化登录态")
        ud = get_dedicated_edge_user_data_dir()
        pd = 'Default'
        if ud:
            print(f"使用专用 EdgeDriver 用户数据目录: {ud}，配置: {pd}")
        else:
            print("无法创建专用用户数据目录，回退到不复用登录态")
            ud, pd = None, None
    else:
        ud = detect_default_edge_user_data_dir() or None
        pd = detect_default_edge_profile_directory(ud) or None
        if ud:
            print(f"复用系统 Edge 用户数据目录: {ud}，配置: {pd or 'Default'}")
        else:
            print("未检测到系统 Edge 用户数据目录，使用临时会话（不复用登录态）")

    # 强制UI模式
    driver = setup_driver(user_data_dir=ud, profile_directory=pd)
    if not driver:
        sys.exit(1)

    try:
        # 统一以第一页URL开始（强制 t=d & sort_type=0）
        first_page_url = build_page_url(actor_url, 1)
        driver.get(first_page_url)
        human_pause(driver)
        if is_security_verification_page(driver):
            print("检测到安全验证页面，请完成认证后按回车继续…")
            wait_for_manual_login(driver, seconds=300, reopen_url=first_page_url)
        if is_login_page(driver):
            print("检测到登录页，尝试自动填充后手工验证…")
            handle_login(driver)
            wait_for_manual_login(driver, seconds=300, reopen_url=first_page_url)

        # 若未提供演员名，则尝试从页面提取
        if not actor_name:
            try:
                # 常见选择器尝试
                for sel in ['h2.title', 'h1.title', '.title', 'title']:
                    els = driver.find_elements(By.CSS_SELECTOR, sel)
                    if els:
                        txt = els[0].text.strip() if hasattr(els[0], 'text') else els[0].get_attribute('innerText')
                        if txt:
                            actor_name = re.sub(r"\s*[-|｜].*$", "", txt).strip()
                            break
            except Exception:
                pass
        # 兜底：使用URL中的actor_id
        if not actor_name:
            actor_name = extract_actor_id_from_url(actor_url) or 'actor'

        # 未指定 --to 时不再首页估计最大页，改为动态遍历到末页
        if to_page is None:
            print("未指定结束页，将自动翻页直至末页")

        # 先翻页收集所有详情链接（支持起止页范围）
        print(f"准备收集详情链接，页范围: {from_page} → {'末页' if to_page is None else to_page}")
        links = collect_actor_video_links(driver, actor_url, start_page=from_page, end_page=to_page)
        print(f"共收集到 {len(links)} 条详情链接")

        # 准备CSV流式输出文件（支持断点续爬）
        resume_mode = False
        results_dir = get_results_dir()
        if args.csv_path:
            out_path = os.path.abspath(args.csv_path)
            resume_mode = os.path.exists(out_path)
        else:
            # 优先在 results 目录检测是否已有该演员的CSV，若有则启用续爬并在其后追加
            existing = find_existing_actor_csv(actor_name, search_dir=results_dir)
            if existing:
                out_path = existing
                resume_mode = True
                print(f"检测到已有CSV，启用断点续爬: {out_path}")
            else:
                # 生成短文件名：取第一个逗号或空白前的片段，默认放入 results 目录
                short_actor = actor_name.strip()
                try:
                    short_actor = re.split(r"[，,\s]+", short_actor, maxsplit=1)[0]
                except Exception:
                    pass
                out_name = safe_filename(f"javdb_{short_actor}.csv")
                out_path = os.path.join(results_dir, out_name)
                # 若固定名已存在，也视为断点续爬
                if os.path.exists(out_path):
                    resume_mode = True
                    print(f"检测到固定名CSV，启用断点续爬: {out_path}")
        # 加载已处理链接集合
        processed_urls = load_processed_urls_from_csv(out_path) if resume_mode else set()
        f_csv, writer = open_csv_stream(out_path)
        print(f"CSV输出: {out_path}")
        if resume_mode:
            print(f"断点续爬启用：已存在 {len(processed_urls)} 条记录，将跳过这些详情链接")

        # 根据已处理的 detail_url 预过滤待解析链接
        remaining_links = [l for l in links if l not in processed_urls] if processed_urls else links
        pre_skipped = len(links) - len(remaining_links)
        if pre_skipped > 0:
            print(f"根据已爬取 detail_url 预过滤，跳过 {pre_skipped} 条，剩余 {len(remaining_links)} 条待解析")

        # 逐详情页解析并即时写入一行
        skipped = 0
        written = 0
        for idx, durl in enumerate(remaining_links, start=1):
            print(f"解析详情({idx}/{len(remaining_links)}): {durl}")
            # 跳过已处理的链接（detail_url 或 video_id）
            if durl in processed_urls:
                skipped += 1
                print("已在CSV中存在，跳过")
                continue
            # 进入详情页前也检测安全验证
            try:
                driver.get(durl)
                human_pause(driver)
                if is_security_verification_page(driver):
                    print("检测到安全验证页面，请完成认证后按回车继续…")
                    wait_for_manual_login(driver, seconds=300, reopen_url=durl)
            except Exception:
                pass
            info = parse_detail(driver, durl, max_retries=2)
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

        print(f"全部详情解析完成，CSV已写入。新增 {written} 条，跳过 {skipped} 条。")

    finally:
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == '__main__':
    main()