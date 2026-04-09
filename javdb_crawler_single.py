import time
import random
import requests
import os
import re
import json
import sys
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
from config import SOCKS5_PROXY_HOST, SOCKS5_PROXY_PORT, LOGIN_EMAIL, LOGIN_PASSWORD, MIN_DELAY, MAX_DELAY, get_javdb_base_url, USE_SOCKS5_PROXY, JAVDB_DIRECT_DOMAIN, JAVDB_ALTERNATE_DIRECT_DOMAINS
from utils.runtime import runtime_dir, runtime_path

RESULTS_DIR = runtime_path('results')
IMAGES_DIR = runtime_path('results', 'images')
os.makedirs(IMAGES_DIR, exist_ok=True)
COVERS_DIR = IMAGES_DIR

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

def is_cloudflare_challenge_html(page_source: str, title: str = "") -> bool:
    if not page_source:
        return False
    t = (title or "").lower()
    s = page_source.lower()
    strong_markers = [
        "checking your browser before accessing",
        "attention required!",
        "cf-challenge",
        "cf-browser-verification",
        "challenge-platform",
        "turnstile",
        "cf_chl_",
        "cf-chl-",
        "/cdn-cgi/challenge-platform/",
    ]
    if any(marker in s for marker in strong_markers):
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
    edge_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')

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
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
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

def crawl_single_video(video_code):
    """Crawl single video by code"""
    print(f"[INFO] Starting crawl for video code: {video_code}", file=sys.stderr)
    
    for attempt in get_attempt_configs(USE_SOCKS5_PROXY):
        print(f"[INFO] Attempt config - use_proxy: {attempt['use_proxy']}, headless: {attempt['headless']}", file=sys.stderr)
        driver = setup_driver(use_proxy=attempt["use_proxy"], headless=attempt["headless"])
        if not driver:
            print(f"[ERROR] Failed to setup driver for config: {attempt}", file=sys.stderr)
            continue
        print(f"[INFO] Driver setup successful", file=sys.stderr)
        try:
            for base_url in get_base_url_candidates(attempt["use_proxy"]):
                driver.get(base_url)
                random_delay(2, 4)
                if is_cloudflare_challenge(driver):
                    print("检测到 Cloudflare 验证页，等待通过...", file=sys.stderr)
                    if attempt["headless"]:
                        print("当前为无头模式，无法人工验证，切换到有界面模式重试。", file=sys.stderr)
                        break
                    if not wait_for_cloudflare_clear(driver, timeout_seconds=120):
                        continue
                
                try:
                    if is_login_page(driver):
                        print("登录状态缺失，调用登录助手以持久化登录态...", file=sys.stderr)
                        cwd_dir = runtime_dir()
                        try:
                            if getattr(sys, 'frozen', False):
                                subprocess.run([runtime_path('javdb_login_helper.exe')], cwd=cwd_dir, check=True)
                            else:
                                subprocess.run([sys.executable, 'javdb_login_helper.py'], cwd=cwd_dir, check=True)
                        except Exception as e:
                            print(f"登录助手运行失败: {e}", file=sys.stderr)
                            continue
                        driver.get(base_url)
                        random_delay(1, 2)
                        if is_cloudflare_challenge(driver):
                            print("检测到 Cloudflare 验证页，等待通过...", file=sys.stderr)
                            if attempt["headless"]:
                                print("当前为无头模式，无法人工验证，切换到有界面模式重试。", file=sys.stderr)
                                break
                            if not wait_for_cloudflare_clear(driver, timeout_seconds=120):
                                continue
                except Exception:
                    pass
                
                detail_url = search_video_by_code(driver, video_code, base_url)
                if not detail_url:
                    continue
                
                detail_url = normalize_javdb_url_to_base(detail_url, base_url)
                
                driver.get(detail_url)
                random_delay(1, 2)
                if is_cloudflare_challenge(driver):
                    print("检测到 Cloudflare 验证页，等待通过...", file=sys.stderr)
                    if attempt["headless"]:
                        print("当前为无头模式，无法人工验证，切换到有界面模式重试。", file=sys.stderr)
                        break
                    if not wait_for_cloudflare_clear(driver, timeout_seconds=120):
                        continue
                if is_login_page(driver):
                    print("访问详情页需要登录，启动登录助手后重试...", file=sys.stderr)
                    cwd_dir = runtime_dir()
                    try:
                        if getattr(sys, 'frozen', False):
                            subprocess.run([runtime_path('javdb_login_helper.exe')], cwd=cwd_dir, check=True)
                        else:
                            subprocess.run([sys.executable, 'javdb_login_helper.py'], cwd=cwd_dir, check=True)
                    except Exception as e:
                        print(f"登录助手运行失败: {e}", file=sys.stderr)
                        continue
                    driver.get(detail_url)
                    random_delay(1, 2)
                    if is_cloudflare_challenge(driver):
                        print("检测到 Cloudflare 验证页，等待通过...", file=sys.stderr)
                        if attempt["headless"]:
                            print("当前为无头模式，无法人工验证，切换到有界面模式重试。", file=sys.stderr)
                            break
                        if not wait_for_cloudflare_clear(driver, timeout_seconds=120):
                            continue
                    if is_login_page(driver):
                        print("登录仍未成功，请手动登录后重试。", file=sys.stderr)
                        continue
                
                result = parse_detail(driver, detail_url, base_url, attempt["use_proxy"])
                if result:
                    return result
        except Exception:
            pass
        finally:
            driver.quit()
    return None

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
