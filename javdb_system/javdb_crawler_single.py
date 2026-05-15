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
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.edge.options import Options
from selenium.common.exceptions import TimeoutException, WebDriverException
import socks
import socket
import subprocess
from contextlib import suppress
from config import SOCKS5_PROXY_HOST, SOCKS5_PROXY_PORT, LOGIN_EMAIL, LOGIN_PASSWORD, MIN_DELAY, MAX_DELAY, get_javdb_base_url, USE_SOCKS5_PROXY, JAVDB_DIRECT_DOMAIN, JAVDB_ALTERNATE_DIRECT_DOMAINS
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

def get_dedicated_edge_user_data_dir():
    """Return and create a dedicated Edge user data dir to persist login state"""
    try:
        d = runtime_path('.edge_driver_user_data')
        os.makedirs(d, exist_ok=True)
        return d
    except Exception:
        return None

def is_login_page(driver):
    """Heuristically detect if the current page is a login page"""
    try:
        email_inputs = driver.find_elements(By.CSS_SELECTOR, 'input[type="email"], input[name="email"]')
        password_inputs = driver.find_elements(By.CSS_SELECTOR, 'input[type="password"], input[name="password"]')
        buttons = driver.find_elements(By.CSS_SELECTOR, 'button[type="submit"], input[type="submit"], .btn-primary')
        return (len(email_inputs) > 0 and len(password_inputs) > 0 and len(buttons) > 0)
    except Exception:
        return False

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

def is_cloudflare_challenge(driver) -> bool:
    try:
        return is_cloudflare_challenge_html(driver.page_source or "", driver.title or "")
    except Exception:
        return False

def wait_for_cloudflare_clear(driver, timeout_seconds=90) -> bool:
    start = time.time()
    while time.time() - start < timeout_seconds:
        if not is_cloudflare_challenge(driver):
            return True
        time.sleep(2)
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

def setup_socks5_proxy():
    """Setup SOCKS5 proxy for requests"""
    # Save original socket
    original_socket = socket.socket
    
    # Set up SOCKS5 proxy
    socks.set_default_proxy(socks.SOCKS5, SOCKS5_PROXY_HOST, SOCKS5_PROXY_PORT)
    socket.socket = socks.socksocket
    
    return original_socket

def restore_socket(original_socket):
    """Restore original socket"""
    socket.socket = original_socket

def setup_driver(use_proxy=True, headless=True):
    """Setup MS Edge browser driver with SOCKS5 proxy and persistent user data"""
    import platform

    edge_options = Options()
    edge_options.page_load_strategy = 'eager'

    # Simulate real users
    edge_options.add_argument('--no-sandbox')
    edge_options.add_argument('--disable-dev-shm-usage')
    edge_options.add_argument('--disable-blink-features=AutomationControlled')
    edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    edge_options.add_experimental_option('useAutomationExtension', False)
    edge_options.add_argument(f'--user-agent={DEFAULT_USER_AGENT}')
    edge_options.add_argument('--lang=zh-CN')
    edge_options.add_experimental_option('prefs', {'intl.accept_languages': REQUEST_LANGUAGE})

    if use_proxy:
        edge_options.add_argument(f'--proxy-server=socks5://{SOCKS5_PROXY_HOST}:{SOCKS5_PROXY_PORT}')

    # Persistent user data dir
    user_data_dir = get_dedicated_edge_user_data_dir()
    if user_data_dir:
        edge_options.add_argument(f'--user-data-dir={user_data_dir}')
        edge_options.add_argument('--profile-directory=Default')

    if headless:
        edge_options.add_argument('--headless')

    last_error = None
    try:
        # Determine EdgeDriver path based on system
        system = platform.system().lower()
        machine = platform.machine().lower()
        print(f"[DEBUG] System: {system}, Architecture: {machine}", file=sys.stderr)
        
        if system == "windows":
            bundled_driver = runtime_path('tools', 'msedgedriver.exe')
            driver_path = bundled_driver if os.path.exists(bundled_driver) else r"C:\bin\edgedriver_win64\msedgedriver.exe"
        elif system == "darwin":  # macOS
            if machine in ['arm64', 'aarch64']:
                driver_path = "/usr/local/bin/edgedriver_mac64_m1/msedgedriver"
            else:
                driver_path = "/usr/local/bin/edgedriver_mac64/msedgedriver"
        elif system == "linux":
            driver_path = "/usr/local/bin/edgedriver_linux64/msedgedriver"
        else:
            driver_path = "/usr/local/bin/edgedriver_mac64/msedgedriver"

        # Prefer user driver path if exists
        user_driver_path = os.path.expanduser("~/bin/edgedriver_mac64_m1/msedgedriver")
        if os.path.exists(user_driver_path):
            driver_path = user_driver_path

        print(f"[DEBUG] Attempting to use EdgeDriver at: {driver_path}", file=sys.stderr)
        print(f"[DEBUG] Driver exists: {os.path.exists(driver_path) if driver_path else 'No path'}", file=sys.stderr)
        
        if driver_path and os.path.exists(driver_path):
            try:
                # Check EdgeDriver version
                try:
                    result = subprocess.run([driver_path, '--version'], capture_output=True, text=True, timeout=5)
                    driver_version = result.stdout.strip()
                    print(f"[DEBUG] EdgeDriver version: {driver_version}", file=sys.stderr)
                except Exception as e:
                    print(f"[DEBUG] Failed to check EdgeDriver version: {e}", file=sys.stderr)
                
                # Check Edge browser version
                try:
                    if system == "darwin":
                        result = subprocess.run(['/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge', '--version'], capture_output=True, text=True, timeout=5)
                        edge_version = result.stdout.strip()
                        print(f"[DEBUG] Edge browser version: {edge_version}", file=sys.stderr)
                except Exception as e:
                    print(f"[DEBUG] Failed to check Edge browser version: {e}", file=sys.stderr)
                
                driver = webdriver.Edge(service=webdriver.edge.service.Service(driver_path), options=edge_options)
                driver.set_page_load_timeout(60)
                driver.set_script_timeout(30)
                try:
                    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                except Exception:
                    pass
                print(f"[DEBUG] EdgeDriver started successfully with explicit path", file=sys.stderr)
                return driver
            except Exception as e:
                last_error = e
                print(f"[DEBUG] Failed to start EdgeDriver with explicit path: {e}", file=sys.stderr)

        # Fallback to automatic driver
        print(f"[DEBUG] Attempting to start EdgeDriver with automatic detection", file=sys.stderr)
        driver = webdriver.Edge(options=edge_options)
        driver.set_page_load_timeout(60)
        driver.set_script_timeout(30)
        try:
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        except Exception:
            pass
        print(f"[DEBUG] EdgeDriver started successfully with automatic detection", file=sys.stderr)
        return driver
    except Exception as e:
        print(f"[ERROR] MS Edge driver startup failed: {e}", file=sys.stderr)
        if last_error and last_error is not e:
            print(f"[ERROR] MS Edge driver startup failed (with explicit driver_path): {last_error}", file=sys.stderr)
        print(f"[SOLUTION] Please make sure MS Edge browser and EdgeDriver are installed", file=sys.stderr)
        print(f"[SOLUTION] Run this command to update EdgeDriver: python update_msedge_driver.py", file=sys.stderr)
        return None

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

def search_video_by_code(driver, video_code, base_url):
    """Search video by code and return detail page URL"""
    try:
        # Navigate to search page
        search_url = f"{base_url}/search?q={video_code}&f=all"
        # print(f"Searching: {search_url}")
        driver.get(search_url)
        random_delay(2, 4)
        
        # Wait for search results to load
        wait = WebDriverWait(driver, 20)
        
        # Find the first search result
        try:
            # Look for video links in search results
            video_links = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'a[href*="/v/"]')))
            
            if video_links:
                detail_url = video_links[0].get_attribute('href')
                # print(f"Found detail page: {detail_url}")
                return detail_url
            else:
                # print(f"No search results found for {video_code}")
                return None
                
        except TimeoutException:
            # print(f"Search results loading timeout for {video_code}")
            return None
            
    except Exception as e:
        # print(f"Search error for {video_code}: {e}")
        return None

def parse_detail(driver, detail_url, base_url, use_proxy, max_retries=2):
    """Parse detail page"""
    for attempt in range(max_retries):
        try:
            # print(f"Visiting detail page: {detail_url} (Attempt {attempt + 1}/{max_retries})")
            driver.get(detail_url)
            
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
                    # Fallback: try rating-stars container attributes or generic score elements
                    try:
                        stars = driver.find_element(By.CSS_SELECTOR, '.rating-stars')
                        score_attr = (stars.get_attribute('data-score') or stars.get_attribute('aria-label') or '').strip()
                        m = re.search(r'(\d+(?:\.\d+)?)', score_attr)
                        if m:
                            rating = m.group(1)
                    except:
                        try:
                            score_elem = driver.find_element(By.CSS_SELECTOR, '.score, .rating .score, .rating .value')
                            txt = score_elem.text.strip()
                            m = re.search(r'(\d+(?:\.\d+)?)', txt)
                            if m:
                                rating = m.group(1)
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
                    # Fallback: look for tag links in common containers
                    try:
                        tag_elements = driver.find_elements(By.CSS_SELECTOR, '.panel-info a[href*="/tags/"], .genres a, .tags a')
                        tags = [t.text.strip() for t in tag_elements if t.text.strip()]
                        # Deduplicate while preserving order
                        seen = set()
                        tags = [x for x in tags if not (x in seen or seen.add(x))]
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

            # Get cover image (prefer high-res via srcset or data-src)
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
                            img_url = urljoin(base_url, img_url)
                        img_element_for_screenshot = img_element
                        break
                except:
                    continue
            
            # Get magnet links
            magnet_links = []
            try:
                magnet_elements = driver.find_elements(By.CSS_SELECTOR, '.magnet-links [data-clipboard-text^="magnet:?xt"]')
                magnet_links = [element.get_attribute('data-clipboard-text') for element in magnet_elements]
            except Exception:
                try:
                    copy_buttons = driver.find_elements(By.XPATH, "//a[contains(text(), 'Copy')]")
                    magnet_links = [button.get_attribute('data-clipboard-text') for button in copy_buttons]
                except Exception:
                    pass  # Allow magnet links to be empty

            # Download cover image (no screenshot fallback)
            local_img_path = None
            if img_url and title != 'N/A':
                filename = f"{video_id}_{title}" if video_id != 'N/A' else title
                try:
                    local_img_path = download_image(img_url, filename, use_proxy=use_proxy, base_url=base_url)
                except Exception as e:
                    print(f"Image download failed: {e}", file=sys.stderr)
            
            # print(f"Parse successful - Title: {title[:50]}..., ID: {video_id}")
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
                'local_image_path': local_img_path,
                'magnet_links': magnet_links
            }

        except Exception as e:
            print(f"Error parsing detail page (Attempt {attempt + 1}/{max_retries}): {e}", file=sys.stderr)
            if attempt < max_retries - 1:
                print("Waiting to retry...", file=sys.stderr)
                random_delay(3, 5)
                continue
            else:
                print("All retries failed. Recording as unable to parse.", file=sys.stderr)
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
                    'cover_image_url': '',
                    'local_image_path': None,
                    'magnet_links': []
                }


def handle_login(driver):
    """Handle login process"""
    try:
        # Find email input field
        email_input = driver.find_element(By.CSS_SELECTOR, 'input[type="email"], input[name="email"]')
        email_input.clear()
        email_input.send_keys(LOGIN_EMAIL)
        random_delay(1, 2)
        
        # Find password input field
        password_input = driver.find_element(By.CSS_SELECTOR, 'input[type="password"], input[name="password"]')
        password_input.clear()
        password_input.send_keys(LOGIN_PASSWORD)
        random_delay(1, 2)
        
        # Find and click login button
        login_button = driver.find_element(By.CSS_SELECTOR, 'button[type="submit"], input[type="submit"], .btn-primary')
        login_button.click()
        
        print("Login form submitted", file=sys.stderr)
        return True
        
    except Exception as e:
        print(f"Login error: {e}", file=sys.stderr)
        return False

def get_attempt_configs(use_proxy_default: bool):
    attempts = [
        {"use_proxy": False, "headless": False},
        {"use_proxy": False, "headless": True},
    ]
    if use_proxy_default:
        attempts.extend(
            [
                {"use_proxy": True, "headless": False},
                {"use_proxy": True, "headless": True},
            ]
        )
    return attempts

def get_browser_preferences():
    return ["msedge", "firefox"]


def get_profile_modes():
    return ["fresh", "persisted"]


def setup_playwright_session(use_proxy=True, headless=True, browser_name="msedge", profile_mode="persisted"):
    if sync_playwright is None:
        return None
    proxy = None
    if use_proxy:
        proxy = {"server": f"socks5://{SOCKS5_PROXY_HOST}:{SOCKS5_PROXY_PORT}"}
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
        link = page.locator('a[href*="/v/"]').first
        if link.count() == 0:
            return None
        href = link.get_attribute("href")
        if not href:
            return None
        if not href.startswith("http"):
            href = urljoin(base_url, href)
        return href
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
                        const anchors = Array.from(document.querySelectorAll('a[href*="/actors/"]'));
                        const raw = [];
                        for (const a of anchors) {
                            const name = (a.textContent || '').trim();
                            if (!name) continue;
                            let female = false;
                            let n = a.nextSibling;
                            let guard = 0;
                            while (n && guard < 4) {
                                const t = (n.textContent || '').trim();
                                if (t.includes('♀')) { female = true; break; }
                                if (n.nodeType === 1 && n.classList && n.classList.contains('female')) { female = true; break; }
                                n = n.nextSibling;
                                guard += 1;
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


def crawl_single_video_selenium(video_code):
    print(f"[INFO] Starting Selenium fallback crawl for video code: {video_code}", file=sys.stderr)
    for attempt in get_attempt_configs(USE_SOCKS5_PROXY):
        print(f"[INFO] Attempt config - use_proxy: {attempt['use_proxy']}, headless: {attempt['headless']}", file=sys.stderr)
        driver = setup_driver(use_proxy=attempt["use_proxy"], headless=attempt["headless"])
        if not driver:
            print(f"[ERROR] Failed to setup driver for config: {attempt}", file=sys.stderr)
            continue
        try:
            for base_url in get_base_url_candidates(attempt["use_proxy"]):
                driver.get(base_url)
                random_delay(2, 4)
                if is_cloudflare_challenge(driver):
                    if attempt["headless"]:
                        break
                    if not wait_for_cloudflare_clear(driver, timeout_seconds=120):
                        continue
                detail_url = search_video_by_code(driver, video_code, base_url)
                if not detail_url:
                    continue
                detail_url = normalize_javdb_url_to_base(detail_url, base_url)
                result = parse_detail(driver, detail_url, base_url, attempt["use_proxy"])
                if result:
                    return result
        except Exception:
            pass
        finally:
            driver.quit()
    return None


def crawl_single_video(video_code):
    result = crawl_single_video_playwright(video_code)
    if result:
        return result
    return crawl_single_video_selenium(video_code)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python javdb_crawler_single.py <video_code>")
        print("Example: python javdb_crawler_single.py CJOD-413")
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
