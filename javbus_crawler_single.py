#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Selenium测试JavBus爬虫
"""

import sys
import os
import time
import logging
import platform
import json
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

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

def crawl_single_video(av_code):
    """
    使用Selenium爬取JavBus单个视频信息
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
            'cover_image_url': result['cover_image_url'],
            'cover_image_path': result['cover_image_path'],
            'magnet_links': result['magnet_links']
        }
        print(json.dumps(json_result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"error": "Failed to crawl video information"}, ensure_ascii=False, indent=2))
        sys.exit(1)