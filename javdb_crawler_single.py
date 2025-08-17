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
from config import SOCKS5_PROXY_HOST, SOCKS5_PROXY_PORT, BASE_URL, LOGIN_EMAIL, LOGIN_PASSWORD, MIN_DELAY, MAX_DELAY

# Create results directory
if not os.path.exists('results'):
    os.makedirs('results')

# Create images directory
if not os.path.exists('results/images'):
    os.makedirs('results/images')

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

def setup_driver():
    """Setup MS Edge browser driver with SOCKS5 proxy"""
    import platform
    
    edge_options = Options()
    
    # Set page load strategy to "eager", not waiting for images and other resources
    edge_options.page_load_strategy = 'eager'

    # Add various options to simulate real users
    edge_options.add_argument('--no-sandbox')
    edge_options.add_argument('--disable-dev-shm-usage')
    edge_options.add_argument('--disable-blink-features=AutomationControlled')
    edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    edge_options.add_experimental_option('useAutomationExtension', False)
    edge_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
    
    # Set up SOCKS5 proxy for Edge
    edge_options.add_argument(f'--proxy-server=socks5://{SOCKS5_PROXY_HOST}:{SOCKS5_PROXY_PORT}')
    
    # Add headless mode
    edge_options.add_argument('--headless')
    
    try:
        # Determine EdgeDriver path based on system
        system = platform.system().lower()
        if system == "windows":
            driver_path = r"C:\bin\edgedriver_win64\msedgedriver.exe"
        elif system == "darwin":  # macOS
            machine = platform.machine().lower()
            if machine in ['arm64', 'aarch64']:
                driver_path = "/usr/local/bin/edgedriver_mac64_m1/msedgedriver"
            else:
                driver_path = "/usr/local/bin/edgedriver_mac64/msedgedriver"
        elif system == "linux":
            driver_path = "/usr/local/bin/edgedriver_linux64/msedgedriver"
        else:
            driver_path = "/usr/local/bin/edgedriver_mac64/msedgedriver"
        
        # Check if user directory driver exists
        import os
        user_driver_path = os.path.expanduser("~/bin/edgedriver_mac64_m1/msedgedriver")
        if os.path.exists(user_driver_path):
            driver_path = user_driver_path
        
        driver = webdriver.Edge(service=webdriver.edge.service.Service(driver_path), options=edge_options)
        # Set page load timeout and script timeout
        driver.set_page_load_timeout(60)
        driver.set_script_timeout(30)
        # Hide webdriver features
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver
    except Exception as e:
        print(f"MS Edge driver startup failed: {e}")
        print("Please make sure MS Edge browser and EdgeDriver are installed")
        print("You can run update_msedge_driver.py to install the driver")
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

def download_image(img_url, filename):
    """Download image to local and return path"""
    try:
        # Setup proxy for image download
        proxies = {
            'http': f'socks5://{SOCKS5_PROXY_HOST}:{SOCKS5_PROXY_PORT}',
            'https': f'socks5://{SOCKS5_PROXY_HOST}:{SOCKS5_PROXY_PORT}'
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Referer': BASE_URL
        }
        
        response = requests.get(img_url, headers=headers, proxies=proxies, timeout=30)
        response.raise_for_status()
        
        # Ensure images directory exists
        os.makedirs('results/images', exist_ok=True)
        
        # Save image to file
        img_path = os.path.join('results/images', filename)
        with open(img_path, 'wb') as f:
            f.write(response.content)
        
        return img_path
        
    except Exception as e:
        print(f"Image download failed {img_url}: {e}")
        return None

def search_video_by_code(driver, video_code):
    """Search video by code and return detail page URL"""
    try:
        # Navigate to search page
        search_url = f"{BASE_URL}/search?q={video_code}&f=all"
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

def parse_detail(driver, detail_url, max_retries=2):
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

            # Get cover image
            img_url = ''
            img_selectors = [
                'div.cover img', '.cover img', 'img.video-cover', 'img[src*="cover"]', 
                'img[src*="thumb"]', '.movie-panel img'
            ]
            for selector in img_selectors:
                try:
                    img_element = driver.find_element(By.CSS_SELECTOR, selector)
                    if img_element:
                        img_url = img_element.get_attribute('src')
                        if img_url and not img_url.startswith('http'):
                            img_url = urljoin(BASE_URL, img_url)
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

            # Download cover image
            local_img_path = None
            if img_url and title != 'N/A':
                filename = f"{video_id}_{title}" if video_id != 'N/A' else title
                local_img_path = download_image(img_url, filename)
            
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
            print(f"Error parsing detail page (Attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                print("Waiting to retry...")
                random_delay(3, 5)
                continue
            else:
                print("All retries failed. Recording as unable to parse.")
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


def search_video_by_code(driver, video_code):
    """Search for a video by its code"""
    try:
        search_url = f"{BASE_URL}/search?q={video_code}&f=all"
        # print(f"Searching for video: {video_code}")
        driver.get(search_url)
        
        # Wait for search results to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div.item, .movie-list .item'))
        )
        
        # Find the first result link
        try:
            first_result = driver.find_element(By.CSS_SELECTOR, 'div.item a')
            detail_url = first_result.get_attribute('href')
            if detail_url and '/v/' in detail_url:
                return detail_url
        except Exception as e:
            # print(f"No search results found for {video_code}: {e}")
            return None
            
    except Exception as e:
        # print(f"Error searching for video {video_code}: {e}")
        return None
    
    return None

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
        
        print("Login form submitted")
        return True
        
    except Exception as e:
        print(f"Login error: {e}")
        return False

def crawl_single_video(video_code):
    """Crawl single video by code"""
    driver = setup_driver()
    if not driver:
        return None
        
    try:
        # Handle login
        driver.get(BASE_URL)
        random_delay(2, 4)
        
        try:
            if driver.find_elements(By.CSS_SELECTOR, 'input[type="email"], input[name="email"]'):
                # print("Login window detected, manual login required...")
                handle_login(driver)
                # print("Waiting 30 seconds, please complete captcha input and login...")
                time.sleep(30)
                random_delay(2, 4)
        except Exception as e:
            # print(f"Login process exception: {e}")
            pass
        
        # Search video
        detail_url = search_video_by_code(driver, video_code)
        if not detail_url:
            # print(f"Detail page not found for video code {video_code}")
            return None
            
        # Parse detail page
        result = parse_detail(driver, detail_url)
        if result:
            # print(f"Successfully obtained information for video code {video_code}")
            return result
        else:
            # print(f"Failed to parse detail page for video code {video_code}")
            return None
            
    except Exception as e:
        # print(f"Error occurred while crawling video code {video_code}: {e}")
        return None
    finally:
        driver.quit()

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