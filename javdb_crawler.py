#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JavDB 爬虫（Playwright 版）

浏览器层委托同目录的 javdb_crawler_single.py（Playwright 优先，含
Cloudflare/年龄确认/登录等待与持久化会话回退），本文件只负责批量编排与结果落盘。

用法:
    python javdb_crawler.py <video_code>   # 单番号, 输出 JSON
    python javdb_crawler.py                # 批量: 存在 av_codes_list.txt 时按番号
                                           # 批量, 否则爬取首页列表
结果保存到 ./results/ (JSON + Excel)
"""

import json
import os
import random
import re
import sys
import time

import pandas as pd

from config import MAX_PAGES, MIN_DELAY, MAX_DELAY
from javdb_crawler_single import (
    USE_SOCKS5_PROXY,
    crawl_single_video_playwright,
    get_attempt_configs,
    get_browser_preferences,
    get_profile_modes,
    get_base_url_candidates,
    setup_playwright_session,
    close_playwright_session,
    is_cloudflare_challenge_pw,
    wait_for_cloudflare_clear_pw,
    is_age_confirmation_pw,
    dismiss_age_confirmation_pw,
    is_login_page_pw,
    wait_for_manual_login_pw,
    ensure_preferred_language_pw,
    parse_detail_pw,
)

# Create results directory
if not os.path.exists('results'):
    os.makedirs('results')

# Create images directory
if not os.path.exists('results/images'):
    os.makedirs('results/images')

def random_delay(min_seconds=MIN_DELAY, max_seconds=MAX_DELAY):
    """Random delay to simulate human behavior"""
    time.sleep(random.uniform(min_seconds, max_seconds))

def safe_filename(filename):
    """Generate safe filename"""
    # Remove or replace unsafe characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Replace spaces with underscores
    filename = filename.replace(' ', '_')
    # Limit length
    if len(filename) > 100:
        filename = filename[:100]
    return filename

def _map_result(raw):
    """Map javdb_crawler_single's field names to the legacy result dict"""
    return {
        'title': raw.get('title'),
        'video_id': raw.get('video_id'),
        'detail_url': raw.get('detail_url'),
        'release_date': raw.get('release_date'),
        'duration': raw.get('duration'),
        'rating': raw.get('rating'),
        'tags': raw.get('tags') or [],
        'actors': raw.get('actors') or [],
        'studio': raw.get('studio'),
        'img_url': raw.get('cover_image_url') or '',
        'local_img_path': raw.get('local_image_path'),
        'magnet_links': raw.get('magnet_links') or [],
    }

def _failed_result(video_code, title):
    return {
        'title': title,
        'video_id': video_code,
        'detail_url': 'N/A',
        'release_date': 'N/A',
        'duration': 'N/A',
        'rating': 'N/A',
        'tags': [],
        'actors': [],
        'studio': 'N/A',
        'img_url': '',
        'local_img_path': None,
        'magnet_links': []
    }

def crawl_single_video(video_code):
    """Crawl information for a single video code via the Playwright pipeline

    Args:
        video_code (str): Video code, e.g. 'ABF-255'

    Returns:
        dict: Dictionary containing video information, returns None if failed
    """
    raw = crawl_single_video_playwright(video_code)
    if not raw or raw.get('title') in (None, 'N/A'):
        print(f"Failed to parse detail page for video code {video_code}")
        return None
    print(f"Successfully obtained information for video code {video_code}")
    return _map_result(raw)

def read_video_codes_from_file(filename):
    """Read video codes from a text file"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            codes = [line.strip() for line in f.readlines() if line.strip()]
        return codes
    except Exception as e:
        print(f"Error reading video codes from file {filename}: {e}")
        return []

def crawl_by_video_codes(video_codes):
    """Crawl videos by their codes (each code runs the full Playwright fallback pipeline)"""
    results = []

    for i, code in enumerate(video_codes, 1):
        print(f"\nProcessing video {i}/{len(video_codes)}: {code}")
        try:
            result = crawl_single_video(code)
            if result:
                results.append(result)
                print(f"Successfully parsed: {result['title']}")
            else:
                print(f"Video not found: {code}")
                results.append(_failed_result(code, 'Not Found'))
        except Exception as e:
            print(f"Error processing video {code}: {e}")
            results.append(_failed_result(code, 'Parse Error'))

        if i < len(video_codes):
            wait_time = random.uniform(3, 6)
            print(f"Waiting {wait_time:.1f} seconds...")
            time.sleep(wait_time)

    return results

def _pass_page_gates_pw(page, attempt):
    """Handle Cloudflare / age confirmation / login gates. Returns True if passed."""
    if is_cloudflare_challenge_pw(page):
        print("检测到 Cloudflare 验证页，等待通过...", file=sys.stderr)
        if attempt["headless"]:
            print("当前为无头模式，无法人工验证，切换到有界面模式重试。", file=sys.stderr)
            return False
        if not wait_for_cloudflare_clear_pw(page, timeout_seconds=180):
            return False
    if is_age_confirmation_pw(page):
        print("检测到年龄确认页，尝试自动点击...", file=sys.stderr)
        if not dismiss_age_confirmation_pw(page):
            print("未能自动通过年龄确认，请手动点击...", file=sys.stderr)
            if attempt["headless"]:
                return False
            for _ in range(30):
                if not is_age_confirmation_pw(page):
                    break
                time.sleep(2)
    if is_login_page_pw(page):
        print("检测到登录页，请在浏览器中完成登录...", file=sys.stderr)
        if attempt["headless"]:
            return False
        if not wait_for_manual_login_pw(page, timeout_seconds=240):
            return False
    return True

def get_video_detail_links_pw(page, base_url, max_pages=MAX_PAGES):
    """Get video detail links from the homepage listing via Playwright"""
    all_links = []
    seen = set()
    for page_num in range(1, max_pages + 1):
        url = base_url if page_num == 1 else f"{base_url}?page={page_num}"
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        random_delay(1.5, 3.0)
        if is_cloudflare_challenge_pw(page) or is_login_page_pw(page):
            break
        found = page.evaluate("""
            () => Array.from(document.querySelectorAll('a[href*="/v/"]'))
                .map(a => a.href)
                .filter(h => /\\/v\\/[A-Za-z0-9]+$/.test(h))
        """)
        if not found:
            break
        for link in found:
            if link not in seen:
                seen.add(link)
                all_links.append(link)
        print(f"Page {page_num}: collected {len(all_links)} links so far")
    return all_links

def crawl_homepage_videos(max_pages=MAX_PAGES):
    """Crawl videos from homepage"""
    for attempt in get_attempt_configs(USE_SOCKS5_PROXY):
        for browser_name in get_browser_preferences():
            for profile_mode in get_profile_modes():
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
                        if not _pass_page_gates_pw(page, attempt):
                            continue
                        ensure_preferred_language_pw(page, session["context"], base_url)
                        links = get_video_detail_links_pw(page, base_url, max_pages)
                        if not links:
                            continue

                        print(f"Obtained {len(links)} detail page links, starting to parse...")
                        results = []
                        for i, url in enumerate(links, 1):
                            print(f"\nProcessing item {i}/{len(links)}...")
                            try:
                                raw = parse_detail_pw(page, url, base_url, attempt["use_proxy"])
                                if raw and raw.get('title') not in (None, 'N/A'):
                                    results.append(_map_result(raw))
                                    print(f"Successfully parsed: {raw['title']}")
                                else:
                                    print(f"Parse failed: {url}")
                            except Exception as e:
                                print(f"Parse error {url}: {e}")
                            if i < len(links):
                                wait_time = random.uniform(3, 6)
                                print(f"Waiting {wait_time:.1f} seconds...")
                                time.sleep(wait_time)
                        if results:
                            return results
                except Exception:
                    pass
                finally:
                    close_playwright_session(session)
    return []

def save_results_to_json(results, filename):
    """Save results to JSON file"""
    json_path = os.path.join('results', filename)
    print(f"\nStarting to save results to {json_path}...")

    # Convert results to JSON-serializable format
    json_results = []
    for result in results:
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
            'cover_image_url': result['img_url'],
            'local_image_path': result['local_img_path'],
            'magnet_links': result['magnet_links']
        }
        json_results.append(json_result)

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_results, f, ensure_ascii=False, indent=2)

    print(f"Results saved to {json_path}")

def save_results_to_excel(results, filename):
    """Save results to Excel file"""
    excel_path = os.path.join('results', filename)
    print(f"Generating Excel file to: {excel_path}")

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
                '片商': result['studio'],
                '标签': '; '.join(result['tags']),
                '演员': '; '.join([f"{actor['name']} ({actor['link']})" for actor in result['actors']]),
                '在线图片地址': result['img_url'],
                '本地图片路径': result['local_img_path'] or '',
                '下载链接': '; '.join(result['magnet_links'])
            })

        df = pd.DataFrame(excel_data)
        df.to_excel(excel_path, index=False, engine='openpyxl')
        print("Excel file generated successfully!")
    except Exception as e:
        print(f"Failed to generate Excel file: {e}")

if __name__ == '__main__':
    # Check if a video code is provided as command line argument
    if len(sys.argv) > 1:
        video_code = sys.argv[1]
        print(f"Getting information for video: {video_code}")
        result = crawl_single_video(video_code)
        if result:
            # Convert to JSON format
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
                'cover_image_url': result['img_url'],
                'local_image_path': result['local_img_path'],
                'magnet_links': result['magnet_links']
            }
            print(json.dumps(json_result, ensure_ascii=False, indent=2))
        else:
            print(json.dumps({"error": "Failed to crawl video information"}, ensure_ascii=False, indent=2))
            sys.exit(1)
        sys.exit(0)

    # Batch processing
    if os.path.exists('av_codes_list.txt'):
        print("Found av_codes_list.txt, crawling videos by codes...")
        video_codes = read_video_codes_from_file('av_codes_list.txt')
        if video_codes:
            results = crawl_by_video_codes(video_codes)
        else:
            print("No video codes found in av_codes_list.txt")
            results = []
    else:
        print("av_codes_list.txt not found, crawling homepage videos...")
        results = crawl_homepage_videos(MAX_PAGES)

    if results:
        # Save results
        save_results_to_json(results, 'javdb_results.json')
        save_results_to_excel(results, 'javdb_results.xlsx')
        print(f"Crawling completed! Processed {len(results)} items in total.\nAll files saved to ./results/ directory")
    else:
        print("No results to save.")
