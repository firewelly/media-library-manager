#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JavBus 单番号爬虫（Playwright 优先 + Selenium 回退）
Playwright 版使用固定持久会话(.playwright_user_data_javbus)保存年龄确认/语言等状态
输出 JSON 字段与历史版本一致: number/title/studio/release_date/actors/cover_image_url/cover_image_path/magnet_links
"""

import sys
import os
import time
import random
import logging
import platform
import json
from contextlib import suppress
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

try:
    from playwright.sync_api import sync_playwright
except Exception:
    sync_playwright = None

try:
    from config import SOCKS5_PROXY_HOST, SOCKS5_PROXY_PORT, USE_SOCKS5_PROXY
except Exception:
    SOCKS5_PROXY_HOST, SOCKS5_PROXY_PORT, USE_SOCKS5_PROXY = "127.0.0.1", 1080, True

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 统一封面保存目录到 results/images（与其它脚本保持一致）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COVERS_DIR = os.path.join(BASE_DIR, 'results', 'images')
os.makedirs(COVERS_DIR, exist_ok=True)

def save_cover_image_from_selenium(driver, img_element, av_code, download_dir=COVERS_DIR):
    """
    使用Selenium直接保存已加载的封面图片
    """
    try:
        if not img_element:
            logger.warning("封面图元素为空")
            return None
            
        # 创建下载目录
        os.makedirs(download_dir, exist_ok=True)
        
        # 生成本地文件名
        local_filename = f"{av_code}_cover.png"  # 使用PNG格式保存截图
        local_path = os.path.join(download_dir, local_filename)
        
        logger.info(f"开始保存封面图到: {local_path}")
        
        # 滚动到图片元素位置
        driver.execute_script("arguments[0].scrollIntoView();", img_element)
        time.sleep(0.5)  # 等待滚动完成
        
        # 获取图片元素的位置和大小
        location = img_element.location
        size = img_element.size
        
        # 截取整个页面
        driver.save_screenshot(local_path + ".temp")
        
        # 使用PIL裁剪出图片部分
        try:
            from PIL import Image
            
            # 打开截图
            screenshot = Image.open(local_path + ".temp")
            
            # 计算裁剪区域
            left = location['x']
            top = location['y']
            right = left + size['width']
            bottom = top + size['height']
            
            # 裁剪图片
            cover_image = screenshot.crop((left, top, right, bottom))
            
            # 保存裁剪后的图片
            cover_image.save(local_path)
            
            # 删除临时文件
            os.remove(local_path + ".temp")
            
            logger.info(f"封面图已保存到: {local_path} (尺寸: {size['width']}x{size['height']})")
            return local_path
            
        except ImportError:
            # 如果没有PIL，直接使用完整截图
            os.rename(local_path + ".temp", local_path)
            logger.info(f"封面图已保存到: {local_path} (完整截图)")
            return local_path
            
    except Exception as e:
        logger.error(f"保存封面图失败: {e}")
        # 清理临时文件
        try:
            if os.path.exists(local_path + ".temp"):
                os.remove(local_path + ".temp")
        except:
            pass
        return None

def get_edge_driver_path():
    """根据操作系统获取Edge WebDriver路径"""
    system = platform.system().lower()
    machine = platform.machine().lower()
    
    if system == 'windows':
        return 'C:\\bin\\edgedriver_win64\\msedgedriver.exe'
    elif system == 'darwin':  # macOS
        if machine in ['arm64', 'aarch64']:  # Apple Silicon
            return '/usr/local/bin/edgedriver_mac64_m1/msedgedriver'
        else:  # Intel Mac
            return '/usr/local/bin/edgedriver_mac64/msedgedriver'
    elif system == 'linux':
        return '/usr/local/bin/edgedriver_linux64/msedgedriver'
    else:
        # 默认使用macOS Intel路径
        return '/usr/local/bin/edgedriver_mac64/msedgedriver'

def setup_edge_driver():
    """设置Edge WebDriver"""
    options = Options()
    options.add_argument('--headless')  # 启用无头模式
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-web-security')
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--ignore-ssl-errors')
    options.add_argument('--allow-running-insecure-content')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.59')
    
    # 设置代理（如果需要）
    proxy_server = 'socks5://127.0.0.1:1080'
    if proxy_server:
        options.add_argument(f'--proxy-server={proxy_server}')
    
    driver_path = get_edge_driver_path()
    logger.info(f"使用Edge WebDriver路径: {driver_path}")
    
    try:
        if os.path.exists(driver_path):
            service = Service(driver_path)
            driver = webdriver.Edge(service=service, options=options)
        else:
            logger.warning(f"WebDriver路径不存在: {driver_path}，尝试使用系统PATH中的驱动")
            driver = webdriver.Edge(options=options)
        
        return driver
    except Exception as e:
        logger.error(f"创建WebDriver失败: {e}")
        return None

# ==================== Playwright 版（优先） ====================
JAVBUS_BASE_SITES = ["https://www.javbus.com"]
JAVBUS_PW_USER_DATA_DIR = os.path.join(BASE_DIR, '.playwright_user_data_javbus', 'msedge')


def _log(msg):
    print(msg, file=sys.stderr, flush=True)


def _random_delay(a, b):
    time.sleep(random.uniform(a, b))


def _setup_javbus_playwright(use_proxy=True, headless=False):
    """启动 JavBus 专用 Edge 持久会话（保存年龄确认/语言等 cookie 状态）"""
    if sync_playwright is None:
        return None
    proxy = None
    if use_proxy:
        proxy = {"server": f"socks5://{SOCKS5_PROXY_HOST}:{SOCKS5_PROXY_PORT}"}
    os.makedirs(JAVBUS_PW_USER_DATA_DIR, exist_ok=True)
    kwargs = {
        "headless": headless,
        "locale": "zh-CN",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "extra_http_headers": {"Accept-Language": "zh-CN,zh;q=0.9,ja;q=0.8,en;q=0.7"},
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--lang=zh-CN",
        ],
    }
    if proxy:
        kwargs["proxy"] = proxy
    pw = ctx = None
    try:
        pw = sync_playwright().start()
        ctx = pw.chromium.launch_persistent_context(JAVBUS_PW_USER_DATA_DIR, channel="msedge", **kwargs)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.add_init_script("""
            Object.defineProperty(navigator, 'language', { get: () => 'zh-CN' });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'ja', 'en'] });
        """)
        return {"pw": pw, "context": ctx, "page": page}
    except Exception as e:
        _log(f"[DEBUG] JavBus Playwright 启动失败: {e}")
        with suppress(Exception):
            if ctx:
                ctx.close()
        with suppress(Exception):
            if pw:
                pw.stop()
        return None


def _close_javbus_playwright(session):
    if not session:
        return
    with suppress(Exception):
        session["context"].close()
    with suppress(Exception):
        session["pw"].stop()


def _is_cloudflare_pw(page):
    try:
        title = (page.title() or "").lower()
        if "just a moment" in title or "attention required" in title:
            return True
        html = (page.content() or "").lower()
        return "cdn-cgi/challenge-platform" in html
    except Exception:
        return False


def _has_age_gate_pw(page):
    try:
        return page.locator("#enter-alert, #warning").count() > 0
    except Exception:
        return False


def _dismiss_age_gate_pw(page):
    for sel in ["#enter-alert a#enter", "a#enter", "#warning a", "a:has-text('是')", "a:has-text('Enter')"]:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0 and loc.is_visible():
                loc.click()
                _random_delay(1, 2)
                if not _has_age_gate_pw(page):
                    _log(f"已自动通过年龄确认: {sel}")
                    return True
        except Exception:
            continue
    return False


def _is_404_pw(page):
    try:
        title = (page.title() or "").lower()
        if "404" in title:
            return True
        html = (page.content() or "").lower()
        return "404 page not found" in html[:3000]
    except Exception:
        return False


def _parse_javbus_detail_pw(page, url, av_code, context):
    """解析 JavBus 详情页，返回与 Selenium 版同构的 dict（无有效标题返回 None）"""
    result = {
        "number": av_code,
        "title": "",
        "studio": "",
        "release_date": "",
        "actors": [],
        "cover_image_url": "",
        "cover_image_path": None,
        "magnet_links": [],
        "tags": [],
    }
    try:
        result["title"] = (page.locator("h3").first.text_content() or "").strip()
    except Exception:
        pass
    if not result["title"] or _is_404_pw(page):
        return None
    with suppress(Exception):
        result["studio"] = (page.locator("p:has(span:has-text('製作')) a").first.text_content() or "").strip()
    with suppress(Exception):
        t = page.locator("p:has(span:has-text('發行日期'))").first.text_content() or ""
        result["release_date"] = t.replace("發行日期:", "").replace("发行日期:", "").strip()
    with suppress(Exception):
        boxes = page.locator("#star-div .avatar-box")
        for i in range(boxes.count()):
            b = boxes.nth(i)
            name = ""
            with suppress(Exception):
                name = (b.locator("span").first.text_content() or "").strip()
            if not name:
                with suppress(Exception):
                    name = b.locator("img").first.get_attribute("title") or ""
            link = b.get_attribute("href") or ""
            if name:
                result["actors"].append({"name": name.strip(), "link": link})
    with suppress(Exception):
        src = page.locator("a.bigImage img").first.get_attribute("src") or ""
        if src:
            from urllib.parse import urljoin as _ujoin
            result["cover_image_url"] = _ujoin(url, src)
    if result["cover_image_url"]:
        with suppress(Exception):
            resp = context.request.get(result["cover_image_url"], headers={"Referer": url}, timeout=30000)
            if resp.ok:
                local_path = os.path.join(COVERS_DIR, f"{av_code}_cover.jpg")
                with open(local_path, "wb") as f:
                    f.write(resp.body())
                result["cover_image_path"] = local_path
    with suppress(Exception):
        magnets = page.eval_on_selector_all(
            '[data-clipboard-text^="magnet:?xt"]',
            "els => els.map(e => e.getAttribute('data-clipboard-text') || '').filter(Boolean)")
        for m in magnets:
            if m not in result["magnet_links"]:
                result["magnet_links"].append(m)
    with suppress(Exception):
        href_magnets = page.eval_on_selector_all(
            'a[href^="magnet:?xt"]',
            "els => els.map(e => e.getAttribute('href') || '').filter(Boolean)")
        for m in href_magnets:
            if m not in result["magnet_links"]:
                result["magnet_links"].append(m)
    with suppress(Exception):
        result["tags"] = page.eval_on_selector_all(
            "span.genre label",
            "els => els.map(e => (e.textContent || '').trim()).filter(Boolean)")
    return result


def _search_javbus_pw(page, site, av_code):
    """详情 URL 直连失败时走站内搜索，返回详情页 URL 或 None"""
    try:
        page.goto(f"{site}/search/{av_code}&type=0&parent=ce", wait_until="domcontentloaded", timeout=60000)
        _random_delay(1.5, 2.5)
        if _is_404_pw(page) or _is_cloudflare_pw(page):
            return None
        box = page.locator("a.movie-box").first
        if box.count() > 0:
            return box.get_attribute("href")
    except Exception:
        pass
    return None


def crawl_single_video_playwright(av_code):
    """Playwright 优先的 JavBus 爬虫（代理→直连，有界面→无头 逐级回退）"""
    if sync_playwright is None:
        _log("[WARN] Playwright 未安装，跳过 Playwright 流程")
        return None
    _log(f"[INFO] Starting Playwright crawl for JavBus code: {av_code}")
    for use_proxy in ([True, False] if USE_SOCKS5_PROXY else [False]):
        for headless in (False, True):
            session = _setup_javbus_playwright(use_proxy=use_proxy, headless=headless)
            if not session:
                continue
            page = session["page"]
            try:
                for site in JAVBUS_BASE_SITES:
                    url = f"{site}/{av_code}"
                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    except Exception:
                        continue
                    _random_delay(1.5, 2.5)
                    if _is_cloudflare_pw(page):
                        if headless:
                            break
                        _log("检测到 Cloudflare 验证页，等待通过（最多120秒）...")
                        cleared = False
                        for _ in range(60):
                            if not _is_cloudflare_pw(page):
                                cleared = True
                                break
                            time.sleep(2)
                        if not cleared:
                            continue
                    if _has_age_gate_pw(page) and not _dismiss_age_gate_pw(page):
                        if headless:
                            break
                        for _ in range(30):
                            if not _has_age_gate_pw(page):
                                break
                            time.sleep(2)
                    parsed = _parse_javbus_detail_pw(page, url, av_code, session["context"])
                    if parsed:
                        return parsed
                    found = _search_javbus_pw(page, site, av_code)
                    if found:
                        try:
                            page.goto(found, wait_until="domcontentloaded", timeout=60000)
                            _random_delay(1.5, 2.5)
                        except Exception:
                            continue
                        if _has_age_gate_pw(page):
                            _dismiss_age_gate_pw(page)
                        parsed = _parse_javbus_detail_pw(page, found, av_code, session["context"])
                        if parsed:
                            return parsed
            except Exception as e:
                _log(f"[WARN] JavBus Playwright 异常: {e}")
            finally:
                _close_javbus_playwright(session)
    return None


# ==================== Selenium 版（历史回退） ====================

def crawl_single_video_selenium(av_code):
    """
    使用Selenium爬取JavBus单个视频信息（msedgedriver 失效时的回退路径）
    """
    driver = None
    result = {
        'number': av_code,
        'title': '',
        'studio': '',
        'release_date': '',
        'actors': [],
        'cover_image_url': '',
        'cover_image_path': None,
        'magnet_links': [],
        'success': False,
        'error': ''
    }
    
    try:
        logger.info(f"开始测试番号: {av_code}")
        
        # 设置WebDriver
        driver = setup_edge_driver()
        if not driver:
            logger.error("无法创建WebDriver")
            result['error'] = "无法创建WebDriver"
            return result
        
        # 构造URL
        url = f"https://www.javbus.com/{av_code}"
        logger.info(f"访问URL: {url}")
        
        # 设置页面加载超时
        driver.set_page_load_timeout(30)
        
        # 访问页面
        driver.get(url)
        
        # 等待页面加载
        wait = WebDriverWait(driver, 10)
        
        # 尝试获取标题
        try:
            title_element = wait.until(
                EC.presence_of_element_located((By.TAG_NAME, "title"))
            )
            page_title = title_element.get_attribute("innerHTML")
            logger.info(f"页面标题: {page_title}")
        except TimeoutException:
            logger.warning("无法获取页面标题")
            page_title = "未知"
        
        # 尝试获取影片信息
        try:
            # 查找影片标题
            movie_title_element = driver.find_element(By.CSS_SELECTOR, "h3")
            result['title'] = movie_title_element.text if movie_title_element else "未找到"
            logger.info(f"影片标题: {result['title']}")
        except Exception as e:
            logger.warning(f"无法获取影片标题: {e}")
            result['title'] = "未找到"
        
        # 尝试获取工作室信息
        try:
            studio_elements = driver.find_elements(By.XPATH, "//span[contains(text(), '製作商:')]/following-sibling::a")
            result['studio'] = studio_elements[0].text if studio_elements else "未找到"
            logger.info(f"工作室: {result['studio']}")
        except Exception as e:
            logger.warning(f"无法获取工作室信息: {e}")
            result['studio'] = "未找到"
        
        # 尝试获取发布日期
        try:
            # 查找包含"發行日期:"的span元素的父级p元素，然后获取其文本内容
            date_elements = driver.find_elements(By.XPATH, "//span[contains(text(), '發行日期:')]/parent::p")
            if date_elements:
                full_text = date_elements[0].text
                # 从"發行日期: 2013-08-16"中提取日期部分
                result['release_date'] = full_text.replace('發行日期:', '').strip()
            else:
                result['release_date'] = "未找到"
            logger.info(f"发布日期: {result['release_date']}")
        except Exception as e:
            logger.warning(f"无法获取发布日期: {e}")
            result['release_date'] = "未找到"
        
        # 尝试获取演员信息
        try:
            # JavBus 演员信息在 star-div 下的 avatar-box 中
            actor_elements = driver.find_elements(By.CSS_SELECTOR, "#star-div .avatar-box")
            for actor_element in actor_elements:
                try:
                    # 获取演员姓名（从 span 标签或 img 的 title 属性）
                    actor_name = ""
                    span_element = actor_element.find_element(By.TAG_NAME, "span")
                    if span_element:
                        actor_name = span_element.text.strip()
                    
                    # 如果 span 没有文本，尝试从 img 的 title 属性获取
                    if not actor_name:
                        img_element = actor_element.find_element(By.TAG_NAME, "img")
                        if img_element:
                            actor_name = img_element.get_attribute('title')
                    
                    # 获取演员链接
                    actor_link = actor_element.get_attribute('href')
                    
                    if actor_name and actor_link:
                        result['actors'].append({
                            'name': actor_name,
                            'link': actor_link
                        })
                except Exception as e:
                    logger.warning(f"解析单个演员信息时出错: {e}")
                    continue
            
            # 如果上面没找到，尝试其他可能的选择器
            if not result['actors']:
                actor_elements = driver.find_elements(By.XPATH, "//span[contains(text(), '演員')]/following-sibling::a")
                for actor_element in actor_elements:
                    actor_name = actor_element.text.strip()
                    actor_link = actor_element.get_attribute('href')
                    if actor_name and actor_link:
                        result['actors'].append({
                            'name': actor_name,
                            'link': actor_link
                        })
            
            logger.info(f"找到 {len(result['actors'])} 个演员")
                
        except Exception as e:
            logger.warning(f"无法获取演员信息: {e}")
        
        # 尝试获取封面图
        try:
            # 查找封面图片
            img_selectors = [
                'a.bigImage img',  # JavBus 封面图片选择器
                '.screencap img',
                'img.video-cover', 
                'img[src*="cover"]', 
                'img[src*="thumb"]'
            ]
            for selector in img_selectors:
                try:
                    img_element = driver.find_element(By.CSS_SELECTOR, selector)
                    if img_element:
                        result['cover_image_url'] = img_element.get_attribute('src')
                        if result['cover_image_url']:
                            logger.info(f"找到封面图: {result['cover_image_url']}")
                            # 下载封面图
                            # 找到封面图元素
                            try:
                                img_element = driver.find_element(By.CSS_SELECTOR, "a.bigImage img")
                                result['cover_image_path'] = save_cover_image_from_selenium(driver, img_element, av_code)
                            except Exception as e:
                                logger.warning(f"无法找到封面图元素: {e}")
                                result['cover_image_path'] = None
                            break
                except:
                    continue
        except Exception as e:
            logger.warning(f"无法获取封面图: {e}")
        
        # 尝试获取磁力链接
        try:
            # JavBus 磁力链接通常在表格中
            magnet_elements = driver.find_elements(By.XPATH, "//a[starts-with(@href, 'magnet:')]")
            for element in magnet_elements:
                magnet_link = element.get_attribute('href')
                if magnet_link and magnet_link not in result['magnet_links']:
                    result['magnet_links'].append(magnet_link)
            
            # 也尝试查找复制按钮的data属性
            try:
                copy_buttons = driver.find_elements(By.XPATH, "//a[contains(@class, 'btn') and contains(text(), '複製')]")
                for button in copy_buttons:
                    magnet_data = button.get_attribute('data-clipboard-text')
                    if magnet_data and magnet_data.startswith('magnet:') and magnet_data not in result['magnet_links']:
                        result['magnet_links'].append(magnet_data)
            except:
                pass
            
            logger.info(f"找到 {len(result['magnet_links'])} 个磁力链接")
                
        except Exception as e:
            logger.warning(f"无法获取磁力链接: {e}")
        
        # 检查是否成功获取到基本信息
        if result['title'] != "未找到" or result['studio'] != "未找到":
            result['success'] = True
            logger.info("✅ 爬取成功")
            return result
        else:
            logger.error("❌ 未能获取到有效信息")
            result['error'] = "未能获取到有效信息"
            return result
            
    except TimeoutException:
        logger.error("❌ 页面加载超时")
        result['error'] = "页面加载超时"
        return result
    except WebDriverException as e:
        logger.error(f"❌ WebDriver错误: {e}")
        result['error'] = f"WebDriver错误: {e}"
        return result
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        result['error'] = f"测试失败: {e}"
        return result
    finally:
        if driver:
            driver.quit()
            logger.info("WebDriver已关闭")


def crawl_single_video(av_code):
    """统一入口：Playwright 优先，Selenium(msedgedriver) 回退"""
    result = crawl_single_video_playwright(av_code)
    if result:
        result["success"] = True
        return result
    return crawl_single_video_selenium(av_code)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python javbus_crawler_single.py <video_code>")
        print("Example: python javbus_crawler_single.py CWPBD-89")
        sys.exit(1)
    
    av_code = sys.argv[1]
    result = crawl_single_video(av_code)
    
    if result and result['success']:
        # JSON格式输出
        json_result = {
            'number': result['number'],
            'title': result['title'],
            'studio': result['studio'],
            'release_date': result['release_date'],
            'actors': result['actors'],
            'tags': result.get('tags', []),
            'cover_image_url': result['cover_image_url'],
            'cover_image_path': result['cover_image_path'],
            'magnet_links': result['magnet_links']
        }
        print(json.dumps(json_result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"error": "Failed to crawl video information"}, ensure_ascii=False, indent=2))
        sys.exit(1)