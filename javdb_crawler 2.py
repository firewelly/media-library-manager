import time
import random
import requests
import os
import re
from urllib.parse import urljoin, urlparse
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, WebDriverException
import socks
import socket
from config import SOCKS5_PROXY_HOST, SOCKS5_PROXY_PORT, BASE_URL, LOGIN_EMAIL, LOGIN_PASSWORD, MAX_PAGES, MIN_DELAY, MAX_DELAY

# Create results directory
if not os.path.exists('results'):
    os.makedirs('results')

# Create images directory
if not os.path.exists('results/images'):
    os.makedirs('results/images')

def setup_socks5_proxy():
    \"\"\"Setup SOCKS5 proxy for requests\"\"\"
    # Save original socket
    original_socket = socket.socket
    
    # Set up SOCKS5 proxy
    socks.set_default_proxy(socks.SOCKS5, SOCKS5_PROXY_HOST, SOCKS5_PROXY_PORT)
    socket.socket = socks.socksocket
    
    return original_socket

def restore_socket(original_socket):
    \"\"\"Restore original socket\"\"\"
    socket.socket = original_socket

def setup_driver():
    \"\"\"Setup Chrome browser driver with SOCKS5 proxy\"\"\"
    chrome_options = Options()
    
    # Set page load strategy to \"eager\", not waiting for images and other resources
    chrome_options.page_load_strategy = 'eager'

    # Add various options to simulate real users
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option(\"excludeSwitches\", [\"enable-automation\"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
    
    # Set up SOCKS5 proxy for Chrome
    chrome_options.add_argument(f'--proxy-server=socks5://{SOCKS5_PROXY_HOST}:{SOCKS5_PROXY_PORT}')
    
    # If you don't want to show the browser window, uncomment the next line
    # chrome_options.add_argument('--headless')
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        # Set page load timeout and script timeout
        driver.set_page_load_timeout(60)
        driver.set_script_timeout(30)
        # Hide webdriver features
        driver.execute_script(\"Object.defineProperty(navigator, 'webdriver', {get: () => undefined})\")
        return driver
    except Exception as e:
        print(f\"Chrome driver startup failed: {e}\")
        print(\"Please make sure Chrome browser and ChromeDriver are installed\")
        return None

def random_delay(min_seconds=MIN_DELAY, max_seconds=MAX_DELAY):
    \"\"\"Random delay to simulate human behavior\"\"\"
    time.sleep(random.uniform(min_seconds, max_seconds))

def safe_filename(filename):
    \"\"\"Generate safe filename\"\"\"
    # Remove or replace unsafe characters
    filename = re.sub(r'[<>:\"/\\|?*]', '_', filename)
    # Replace spaces with underscores
    filename = filename.replace(' ', '_')
    # Limit length
    if len(filename) > 100:
        filename = filename[:100]
    return filename

def download_image(img_url, filename):
    \"\"\"Download image to local\"\"\"
    try:
        # Setup SOCKS5 proxy for requests
        original_socket = setup_socks5_proxy()
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Referer': BASE_URL
        }
        
        response = requests.get(img_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Get file extension
        parsed_url = urlparse(img_url)
        ext = os.path.splitext(parsed_url.path)[1]
        if not ext:
            ext = '.jpg'  # Default extension
        
        safe_name = safe_filename(filename)
        filepath = os.path.join('results/images', f\"{safe_name}{ext}\")
        
        with open(filepath, 'wb') as f:
            f.write(response.content)
        
        print(f\"Image downloaded successfully: {filepath}\")
        # Restore original socket
        restore_socket(original_socket)
        return filepath
    
    except Exception as e:
        print(f\"Image download failed {img_url}: {e}\")
        # Restore original socket
        restore_socket(original_socket)
        return None

def search_video_by_code(driver, video_code):
    \"\"\"Search for a video by its code\"\"\"
    try:
        search_url = f\"{BASE_URL}/search?q={video_code}&f=all\"
        print(f\"Searching for video: {video_code}\")
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
            print(f\"No search results found for {video_code}: {e}\")
            return None
            
    except Exception as e:
        print(f\"Error searching for video {video_code}: {e}\")
        return None
    
    return None

def get_video_detail_links(driver, max_pages=MAX_PAGES):
    \"\"\"Get all video detail links from the homepage\"\"\"
    all_links = []
    
    for page in range(1, max_pages + 1):
        url = f\"{BASE_URL}?page={page}\"
        print(f\"Visiting page {page}: {url}\")
        driver.get(url)
        
        random_delay(2, 4)
        
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div.item a, .movie-list .item'))
            )
        except TimeoutException:
            print(f\"Page {page} content loading timeout or no items found.\")
            continue
        
        # Get only detail page links
        page_links = []
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, 'div.item a')
            for element in elements:
                href = element.get_attribute('href')
                if href and '/v/' in href:
                    if href not in all_links:
                        page_links.append(href)
        except Exception as e:
            print(f\"Failed to get detail links: {e}\")
        
        if page_links:
            all_links.extend(page_links)
            print(f\"Page {page} got {len(page_links)} links, total {len(all_links)}\")
        else:
            print(f\"No links found on page {page}\")
    
    print(f\"Total {len(all_links)} detail page links obtained\")
    return all_links

def parse_detail(driver, detail_url, max_retries=2):
    \"\"\"Parse detail page\"\"\"
    for attempt in range(max_retries):
        try:
            print(f\"Visiting detail page: {detail_url} (Attempt {attempt + 1}/{max_retries})\")
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
                raise ValueError(\"Could not parse title, page may not have loaded correctly.\")

            # Get番号(ID)
            video_id = 'N/A'
            try:
                video_id_element = driver.find_element(By.XPATH, \"//strong[text()='識別碼:']/following-sibling::span[1]\")
                video_id = video_id_element.text.strip()
            except:
                try:
                    video_id_element = driver.find_element(By.XPATH, \"//strong[text()='ID:']/following-sibling::span[1]\")
                    video_id = video_id_element.text.strip()
                except:
                    pass

            # Get date
            release_date = 'N/A'
            try:
                date_element = driver.find_element(By.XPATH, \"//strong[text()='發行日期:']/following-sibling::span[1]\")
                release_date = date_element.text.strip()
            except:
                try:
                    date_element = driver.find_element(By.XPATH, \"//strong[text()='Date:']/following-sibling::span[1]\")
                    release_date = date_element.text.strip()
                except:
                    pass

            # Get duration
            duration = 'N/A'
            try:
                duration_element = driver.find_element(By.XPATH, \"//strong[text()='時長:']/following-sibling::span[1]\")
                duration = duration_element.text.strip()
            except:
                try:
                    duration_element = driver.find_element(By.XPATH, \"//strong[text()='Duration:']/following-sibling::span[1]\")
                    duration = duration_element.text.strip()
                except:
                    pass

            # Get rating
            rating = 'N/A'
            try:
                rating_element = driver.find_element(By.XPATH, \"//strong[text()='評分:']/following-sibling::span[1]\")
                rating = rating_element.text.strip()
            except:
                try:
                    rating_element = driver.find_element(By.XPATH, \"//strong[text()='Rating:']/following-sibling::span[1]\")
                    rating = rating_element.text.strip()
                except:
                    pass

            # Get tags
            tags = []
            try:
                tag_elements = driver.find_elements(By.XPATH, \"//strong[text()='類別:']/following-sibling::span[1]/a\")
                tags = [tag.text.strip() for tag in tag_elements]
            except:
                try:
                    tag_elements = driver.find_elements(By.XPATH, \"//strong[text()='Tags:']/following-sibling::span[1]/a\")
                    tags = [tag.text.strip() for tag in tag_elements]
                except:
                    pass

            # Get actors
            actors = []
            try:
                actor_elements = driver.find_elements(By.XPATH, \"//strong[text()='演員:']/following-sibling::span[1]//a\")
                for actor_element in actor_elements:
                    actor_name = actor_element.text.strip()
                    actor_link = actor_element.get_attribute('href')
                    actors.append({
                        'name': actor_name,
                        'link': actor_link
                    })
            except:
                try:
                    actor_elements = driver.find_elements(By.XPATH, \"//strong[text()='Actors:']/following-sibling::span[1]//a\")
                    for actor_element in actor_elements:
                        actor_name = actor_element.text.strip()
                        actor_link = actor_element.get_attribute('href')
                        actors.append({
                            'name': actor_name,
                            'link': actor_link
                        })
                except:
                    pass

            # Get cover image
            img_url = ''
            img_selectors = [
                'div.cover img', '.cover img', 'img.video-cover', 'img[src*=\"cover\"]', 
                'img[src*=\"thumb\"]', '.movie-panel img'
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
                magnet_elements = driver.find_elements(By.CSS_SELECTOR, '.magnet-links [data-clipboard-text^=\"magnet:?xt\"]')
                magnet_links = [element.get_attribute('data-clipboard-text') for element in magnet_elements]
            except Exception:
                try:
                    copy_buttons = driver.find_elements(By.XPATH, \"//a[contains(text(), 'Copy')]\")
                    magnet_links = [button.get_attribute('data-clipboard-text') for button in copy_buttons]
                except Exception:
                    pass  # Allow magnet links to be empty

            # Download cover image
            local_img_path = None
            if img_url and title != 'N/A':
                filename = f\"{video_id}_{title}\" if video_id != 'N/A' else title
                local_img_path = download_image(img_url, filename)
            
            print(f\"Parse successful - Title: {title[:50]}..., ID: {video_id}\")
            return {
                'title': title,
                'video_id': video_id,
                'detail_url': detail_url,
                'release_date': release_date,
                'duration': duration,
                'rating': rating,
                'tags': tags,
                'actors': actors,
                'img_url': img_url,
                'local_img_path': local_img_path,
                'magnet_links': magnet_links
            }

        except Exception as e:
            print(f\"Error parsing detail page (Attempt {attempt + 1}/{max_retries}): {e}\")
            if attempt < max_retries - 1:
                print(\"Waiting to retry...\")
                random_delay(3, 5)
                continue
            else:
                print(\"All retries failed. Recording as unable to parse.\")
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
                    'img_url': '',
                    'local_img_path': None,
                    'magnet_links': []
                }

def handle_login(driver):
    try:
        # Wait for login window to appear
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type=\"email\"], input[name=\"email\"]'))
        )
        # Fill email
        email_input = driver.find_element(By.CSS_SELECTOR, 'input[type=\"email\"], input[name=\"email\"]')
        email_input.clear()
        email_input.send_keys(LOGIN_EMAIL)
        # Fill password
        pwd_input = driver.find_element(By.CSS_SELECTOR, 'input[type=\"password\"], input[name=\"password\"]')
        pwd_input.clear()
        pwd_input.send_keys(LOGIN_PASSWORD)
        # Wait for you to manually enter the captcha
        captcha_input = driver.find_element(By.CSS_SELECTOR, 'input[name=\"captcha\"], input[type=\"text\"][autocomplete=\"off\"]')
        print(\"Please view the captcha image in the browser, then enter the captcha here:\")
        captcha_code = input(\"Captcha: \").strip()
        captcha_input.clear()
        captcha_input.send_keys(captcha_code)
        # Submit
        captcha_input.send_keys(u'\\ue007')  # Enter key
        print(\"Login form submitted automatically\")
        time.sleep(2)
    except Exception as e:
        print(f\"Automatic login failed: {e}\")

def read_video_codes_from_file(filename):
    \"\"\"Read video codes from a text file\"\"\"
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            codes = [line.strip() for line in f.readlines() if line.strip()]
        return codes
    except Exception as e:
        print(f\"Error reading video codes from file {filename}: {e}\")
        return []

def crawl_by_video_codes(driver, video_codes):
    \"\"\"Crawl videos by their codes\"\"\"
    results = []
    
    for i, code in enumerate(video_codes, 1):
        print(f\"\\nProcessing video {i}/{len(video_codes)}: {code}\")
        try:
            # Search for the video
            detail_url = search_video_by_code(driver, code)
            
            if detail_url:
                # Parse the video details
                result = parse_detail(driver, detail_url)
                results.append(result)
                print(f\"Successfully parsed: {result['title']}\")
            else:
                print(f\"Video not found: {code}\")
                results.append({
                    'title': 'Not Found',
                    'video_id': code,
                    'detail_url': 'N/A',
                    'release_date': 'N/A',
                    'duration': 'N/A',
                    'rating': 'N/A',
                    'tags': [],
                    'actors': [],
                    'img_url': '',
                    'local_img_path': None,
                    'magnet_links': []
                })
            
            if i < len(video_codes):
                wait_time = random.uniform(3, 6)
                print(f\"Waiting {wait_time:.1f} seconds...\")
                time.sleep(wait_time)
                
        except Exception as e:
            print(f\"Error processing video {code}: {e}\")
            results.append({
                'title': 'Parse Error',
                'video_id': code,
                'detail_url': 'N/A',
                'release_date': 'N/A',
                'duration': 'N/A',
                'rating': 'N/A',
                'tags': [],
                'actors': [],
                'img_url': '',
                'local_img_path': None,
                'magnet_links': []
            })
    
    return results

def crawl_homepage_videos(driver, max_pages=MAX_PAGES):
    \"\"\"Crawl videos from homepage\"\"\"
    print(f\"Starting to crawl homepage: {BASE_URL}\")
    links = get_video_detail_links(driver, max_pages)
    if not links:
        print(\"No detail page links obtained, exiting program\")
        return []
    
    print(f\"Obtained {len(links)} detail page links, starting to parse...\")
    results = []
    
    for i, url in enumerate(links, 1):
        print(f\"\\nProcessing item {i}/{len(links)}...\")
        try:
            result = parse_detail(driver, url)
            results.append(result)
            print(f\"Successfully parsed: {result['title']}\")
            if i < len(links):
                wait_time = random.uniform(3, 6)
                print(f\"Waiting {wait_time:.1f} seconds...\")
                time.sleep(wait_time)
        except Exception as e:
            print(f\"Parse error {url}: {e}\")
            results.append({
                'title': 'Parse failed',
                'video_id': 'N/A',
                'detail_url': url,
                'release_date': 'N/A',
                'duration': 'N/A',
                'rating': 'N/A',
                'tags': [],
                'actors': [],
                'img_url': '',
                'local_img_path': None,
                'magnet_links': []
            })
    
    return results

def save_results_to_markdown(results, filename):
    \"\"\"Save results to Markdown file\"\"\"
    md_path = os.path.join('results', filename)
    print(f\"\\nStarting to save results to {md_path}...\")
    
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(f\"# JavDB Crawler Results\\n\\n\")
        for i, result in enumerate(results, 1):
            f.write(f\"## {i}. {result['title']}\\n\\n\")
            f.write(f\"**番号**: {result['video_id']}\\n\\n\")
            f.write(f\"**详情页链接**: {result['detail_url']}\\n\\n\")
            f.write(f\"**发行日期**: {result['release_date']}\\n\\n\")
            f.write(f\"**时长**: {result['duration']}\\n\\n\")
            f.write(f\"**评分**: {result['rating']}\\n\\n\")
            
            # Tags
            if result['tags']:
                f.write(f\"**标签**: {', '.join(result['tags'])}\\n\\n\")
            else:
                f.write(\"**标签**: N/A\\n\\n\")
            
            # Actors
            if result['actors']:
                actors_str = ', '.join([f\"[{actor['name']}]({actor['link']})\" for actor in result['actors']])
                f.write(f\"**演员**: {actors_str}\\n\\n\")
            else:
                f.write(\"**演员**: N/A\\n\\n\")
            
            # Images
            if result['local_img_path']:
                relative_path = os.path.relpath(result['local_img_path'], 'results').replace('\\\\', '/')
                f.write(f\"![Cover Image]({relative_path})\\n\\n\")
                f.write(f\"**在线图片地址**: {result['img_url']}\\n\\n\")
            elif result['img_url']:
                f.write(f\"![Cover Image]({result['img_url']})\\n\\n\")
                f.write(f\"**在线图片地址**: {result['img_url']}\\n\\n\")
            else:
                f.write(\"**图片**: 无法获取\\n\\n\")
            
            # Magnet links
            if result['magnet_links']:
                f.write(\"**下载链接**:\\n\")
                for j, magnet in enumerate(result['magnet_links'], 1):
                    f.write(f\"{j}. `{magnet}`\\n\")
                f.write(\"\\n\")
            else:
                f.write(\"**下载链接**: 无\\n\\n\")
            
            f.write(\"---\\n\\n\")
    
    print(f\"Results saved to {md_path}\")

def save_results_to_excel(results, filename):
    \"\"\"Save results to Excel file\"\"\"
    excel_path = os.path.join('results', filename)
    print(f\"Generating Excel file to: {excel_path}\")
    
    try:
        # Flatten the data for Excel
        excel_data = []
        for result in results:
            excel_data.append({
                '标题': result['title'],
                '番号': result['video_id'],
                '详情页链接': result['detail_url'],
                '发行日期': result['release_date'],
                '时长': result['duration'],
                '评分': result['rating'],
                '标签': ', '.join(result['tags']),
                '演员': ', '.join([actor['name'] for actor in result['actors']]),
                '图片链接': result['img_url'],
                '本地图片路径': result['local_img_path'] or '',
                '下载链接': '; '.join(result['magnet_links'])
            })
        
        df = pd.DataFrame(excel_data)
        df.to_excel(excel_path, index=False, engine='openpyxl')
        print(\"Excel file generated successfully!\")
    except Exception as e:
        print(f\"Failed to generate Excel file: {e}\")

if __name__ == '__main__':
    driver = setup_driver()
    if not driver:
        exit(1)
    
    # Check for login window
    try:
        if driver.find_elements(By.CSS_SELECTOR, 'input[type=\"email\"], input[name=\"email\"]'):
            print(\"Login window detected, logging in automatically...\")
            handle_login(driver)
            print(\"Waiting 30 seconds, please complete captcha input and login...\")
            time.sleep(30)
            random_delay(2, 4)
    except Exception as e:
        print(f\"Login process exception: {e}\")
    
    try:
        # Check if av_codes_list.txt exists
        if os.path.exists('av_codes_list.txt'):
            print(\"Found av_codes_list.txt, crawling videos by codes...\")
            video_codes = read_video_codes_from_file('av_codes_list.txt')
            if video_codes:
                results = crawl_by_video_codes(driver, video_codes)
            else:
                print(\"No video codes found in av_codes_list.txt\")
                results = []
        else:
            print(\"av_codes_list.txt not found, crawling homepage videos...\")
            results = crawl_homepage_videos(driver, MAX_PAGES)
        
        if results:
            # Save results
            save_results_to_markdown(results, 'javdb_results.md')
            save_results_to_excel(results, 'javdb_results.xlsx')
            print(f\"Crawling completed! Processed {len(results)} items in total.\\nAll files saved to ./results/ directory\")
        else:
            print(\"No results to save.\")
            
    finally:
        driver.quit()
        print(\"Browser closed\")