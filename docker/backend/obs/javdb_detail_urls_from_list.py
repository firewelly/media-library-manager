import os
import re
import sys
import csv
import time
import random
import subprocess
from urllib.parse import urljoin, urlparse

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

from config import (
    SOCKS5_PROXY_HOST,
    SOCKS5_PROXY_PORT,
    MIN_DELAY,
    MAX_DELAY,
    LOGIN_EMAIL,
    LOGIN_PASSWORD,
    NO_PROXY_BYPASS_LIST,
    normalize_javdb_url,
    get_javdb_base_url,
)


# ---------- Utils ----------
def random_delay(min_seconds=MIN_DELAY, max_seconds=MAX_DELAY):
    delay = random.uniform(min_seconds, max_seconds)
    time.sleep(delay)

CRAWL_MIN_DELAY = MIN_DELAY
CRAWL_MAX_DELAY = MAX_DELAY
HUMAN_ACTIONS = True

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
    d = os.path.join(os.getcwd(), 'results')
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d

def detect_default_edge_user_data_dir():
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
        p = os.path.expanduser('~/.config/microsoft-edge')
        return p if os.path.isdir(p) else None
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

def is_edge_running():
    try:
        sysname = (platform.system() or '').lower()
        if 'darwin' in sysname or 'mac' in sysname:
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

def safe_filename(filename: str) -> str:
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    filename = filename.strip(' .')
    return filename[:200] if len(filename) > 200 else filename


def apply_stealth(driver):
    """注入隐藏自动化痕迹的脚本，进一步降低 Cloudflare 识别概率"""
    try:
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": """
                // 伪装 webdriver 痕迹
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                // 添加常见属性
                window.chrome = { runtime: {} };
                // 平台与硬件并发
                try { Object.defineProperty(navigator, 'platform', { get: () => 'MacIntel' }); } catch (e) {}
                try { Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 }); } catch (e) {}
                // 语言
                Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en-US', 'en'] });
                // 插件数量
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                // 权限查询返回合理值
                const originalQuery = window.navigator.permissions && window.navigator.permissions.query;
                if (originalQuery) {
                  window.navigator.permissions.query = (parameters) => (
                    parameters && parameters.name === 'notifications' ?
                      Promise.resolve({ state: Notification.permission }) :
                      originalQuery(parameters)
                  );
                }
                """,
            },
        )
    except Exception:
        pass


def setup_driver(user_data_dir: str = None, profile_directory: str = None, prefer_proxy: bool = True):
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
        opts.add_argument('--lang=zh-CN')
        # 使用真实 Edge UA，减少被 Cloudflare 判定为自动化的概率
        opts.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0')
        if user_data_dir:
            opts.add_argument(f"--user-data-dir={user_data_dir}")
        if profile_directory:
            opts.add_argument(f"--profile-directory={profile_directory}")
        if use_proxy:
            opts.add_argument(f'--proxy-server=socks5://{SOCKS5_PROXY_HOST}:{SOCKS5_PROXY_PORT}')
            opts.add_argument('--proxy-bypass-list=<-loopback>')
        else:
            try:
                if NO_PROXY_BYPASS_LIST:
                    opts.add_argument(f"--proxy-bypass-list={';'.join(NO_PROXY_BYPASS_LIST)}")
            except Exception:
                pass
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
    if prefer_proxy:
        attempts = [
            {"proxy": True,  "use_service": True,  "label": "ui+proxy+service"},
            {"proxy": False, "use_service": True,  "label": "ui+no-proxy+service"},
            {"proxy": False, "use_service": False, "label": "ui+no-proxy+PATH"},
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
            try:
                driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            except Exception:
                pass
            # 覆盖 UA、语言、平台为更真实的组合
            try:
                driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                    'userAgent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0',
                    'acceptLanguage': 'zh-CN,zh;q=0.9,en;q=0.8',
                    'platform': 'MacIntel'
                })
            except Exception:
                pass
            # 本地化与时区覆盖
            try:
                driver.execute_cdp_cmd('Emulation.setTimezoneOverride', {'timezoneId': 'Asia/Shanghai'})
            except Exception:
                pass
            try:
                driver.execute_cdp_cmd('Emulation.setLocaleOverride', {'locale': 'zh-CN'})
            except Exception:
                pass
            # 进一步隐身处理
            apply_stealth(driver)
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


def is_valid_record(info):
    try:
        t = (info.get('title') or '').strip()
        best = find_best_magnet_link(info.get('magnet_links', []))
        m = (best or '').strip()
        # title与magnet_link同时存在且非占位即有效
        if not t or t.upper() == 'N/A':
            return False
        if not m:
            return False
        return True
    except Exception:
        return False


def parse_detail(driver, detail_url, max_retries=2):
    for attempt in range(max_retries):
        try:
            driver.get(detail_url)
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.container, #content, body'))
            )
            human_pause(driver)

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
                            # 使用当前详情页作为基准来补全相对地址，避免对未定义常量的依赖
                            img_url = urljoin(detail_url, img_url)
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
                # 失败时不返回占位数据，主循环将跳过写入以便下次重试
                return None


def is_security_verification_page(driver):
    try:
        url = (driver.current_url or '').lower()
        if any(k in url for k in ['challenge', 'verify', 'security', 'captcha', 'cf-challenge']):
            return True
        if driver.find_elements(By.CSS_SELECTOR, '#cf-challenge, .cf-challenge, .challenge-container'):
            return True
        if driver.find_elements(By.CSS_SELECTOR, '[data-sitekey], .captcha, iframe[src*="captcha"]'):
            return True
        if driver.find_elements(By.XPATH, "//*[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'security verification')]"):
            return True
        if driver.find_elements(By.XPATH, "//*[contains(text(),'安全验证') or contains(text(),'请完成安全验证') or contains(text(),'驗證')]"):
            return True
        if driver.find_elements(By.XPATH, "//*[contains(text(),'Verify you are human') or contains(text(),'Just a moment')]"):
            return True
    except Exception:
        pass
    return False

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
    import sys as _sys
    import select as _select
    print(f"检测到登录/验证，请手工处理。按回车立即继续，或最多等待 {int(seconds)} 秒…")
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


def open_csv_stream(csv_path):
    is_new = not os.path.exists(csv_path)
    f = open(csv_path, 'a', newline='', encoding='utf-8')
    headers = ['title', 'release_date', 'video_id', 'detail_url', 'studio', 'rating', 'duration', 'magnet_link', 'all_magnet_links']
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
        print(f"读取已处理CSV失败（忽略）: {e}")
    return processed


def read_urls_file(path):
    urls = []
    if not path:
        return urls
    p = os.path.abspath(path)
    if not os.path.exists(p):
        print(f"输入文件不存在: {p}")
        return urls
    try:
        with open(p, 'r', encoding='utf-8') as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith('#'):
                    continue
                urls.append(s)
    except Exception as e:
        print(f"读取URL文件失败: {e}")
    # 去重保持顺序
    seen = set()
    uniq = []
    for u in urls:
        if u not in seen:
            uniq.append(u)
            seen.add(u)
    return uniq


def main():
    import argparse
    parser = argparse.ArgumentParser(description='JAVDB详情页列表批处理（基于 actor_all 逻辑，UI模式）')
    parser.add_argument('--urls-file', dest='urls_file', default='url.txt', help='包含详情页URL的一行一条文本文件，默认 url.txt')
    parser.add_argument('--csv', dest='csv_path', default='', help='输出CSV路径（可选，存在则启用断点续爬并追加写入）')
    parser.add_argument('--user-data-dir', dest='user_data_dir', default='', help='Edge用户数据目录（可选），如 ~/Library/Application Support/Microsoft Edge')
    parser.add_argument('--profile-directory', dest='profile_directory', default='', help='Edge配置目录名（可选），一般为 Default')
    parser.add_argument('--use-dedicated-profile', dest='use_dedicated_profile', action='store_true',
                        help='使用专用EdgeDriver用户数据目录（持久化登录态，避免与系统Edge冲突）')
    parser.add_argument('--min-delay', dest='min_delay', type=float, default=3.0, help='最小随机等待秒数，默认 3.0')
    parser.add_argument('--max-delay', dest='max_delay', type=float, default=7.0, help='最大随机等待秒数，默认 7.0')
    parser.add_argument('--no-human-actions', dest='no_human_actions', action='store_true', help='禁用随机滚动与鼠标移动')
    parser.add_argument('--no-proxy', dest='no_proxy', action='store_true', help='禁用 SOCKS5 代理直连访问')
    args = parser.parse_args()

    urls_file = args.urls_file.strip()

    global CRAWL_MIN_DELAY, CRAWL_MAX_DELAY, HUMAN_ACTIONS
    CRAWL_MIN_DELAY = max(0.5, float(args.min_delay or 3.0))
    CRAWL_MAX_DELAY = max(CRAWL_MIN_DELAY, float(args.max_delay or 7.0))
    HUMAN_ACTIONS = not bool(args.no_human_actions)

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

    use_proxy = not bool(args.no_proxy)
    driver = setup_driver(user_data_dir=ud, profile_directory=pd, prefer_proxy=use_proxy)
    if not driver:
        sys.exit(1)

    try:
        # 先访问首页，触发可能的登录/安全验证
        try:
            base_url = get_javdb_base_url(use_proxy)
            driver.get(base_url)
            human_pause(driver)
            if is_security_verification_page(driver):
                print("检测到安全验证页面，请完成认证后按回车继续…")
                wait_for_manual_login(driver, seconds=300, reopen_url=base_url)
            if is_login_page(driver):
                print("检测到登录页，尝试自动填充后手工验证…")
                handle_login(driver)
                wait_for_manual_login(driver, seconds=300, reopen_url=base_url)
        except Exception:
            pass

        links = read_urls_file(urls_file)
        if not links:
            print("未从输入文件获得任何URL，退出。")
            return
        # 域名归一：将可能的旧域名统一替换成当前配置中的直连/代理域名
        try:
            links = [normalize_javdb_url(u, use_proxy) for u in links]
        except Exception:
            pass
        print(f"读取到 {len(links)} 条详情页URL（已按代理模式归一域名）")

        resume_mode = False
        results_dir = get_results_dir()
        if args.csv_path:
            out_path = os.path.abspath(args.csv_path)
            resume_mode = os.path.exists(out_path)
        else:
            out_path = os.path.join(results_dir, 'javdb_magnets.csv')
            if os.path.exists(out_path):
                resume_mode = True
                print(f"检测到固定名CSV，启用断点续爬: {out_path}")

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
        for idx, durl in enumerate(remaining_links, start=1):
            print(f"解析详情({idx}/{len(remaining_links)}): {durl}")
            if durl in processed_urls:
                skipped += 1
                print("已在CSV中存在，跳过")
                continue
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

            # 仅当 title 与 magnet_link 同时有效时才写入
            if not is_valid_record(info):
                skipped += 1
                print("核心字段缺失（title或magnet_link），未写入CSV，跳过")
                continue

            row = {
                'title': info.get('title', 'N/A'),
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
