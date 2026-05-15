#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JAVDB登录助手 - 使用专用的Edge用户数据目录持久化登录状态
"""

import os
import sys
import time
import platform
import subprocess
import json
from urllib.parse import urlparse

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.edge.options import Options
from selenium.common.exceptions import TimeoutException

# 配置信息
try:
    from config import SOCKS5_PROXY_HOST, SOCKS5_PROXY_PORT, get_javdb_base_url, USE_SOCKS5_PROXY
except ImportError:
    SOCKS5_PROXY_HOST = '127.0.0.1'
    SOCKS5_PROXY_PORT = 1080
    def get_javdb_base_url(use_proxy: bool) -> str:
        return 'https://javdb.com'
    USE_SOCKS5_PROXY = True

from utils.runtime import runtime_path

MIN_DELAY = 1
MAX_DELAY = 3

# ---------- 工具函数 ----------
def random_delay(min_seconds=MIN_DELAY, max_seconds=MAX_DELAY):
    """随机延迟，模拟人类操作间隔"""
    delay = random.uniform(min_seconds, max_seconds)
    time.sleep(delay)


def get_dedicated_edge_user_data_dir():
    """
    返回并创建一个专用于 EdgeDriver 的用户数据目录，以持久化登录态。
    该目录与系统 Edge 的用户数据隔离，可在 Edge 运行中使用而不冲突。
    """
    try:
        d = runtime_path('.edge_driver_user_data')
        os.makedirs(d, exist_ok=True)
        return d
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
    except Exception:
        pass
    return False


def find_edge_binary():
    try:
        candidates = []
        program_files = os.environ.get("ProgramFiles")
        program_files_x86 = os.environ.get("ProgramFiles(x86)")
        local_app_data = os.environ.get("LOCALAPPDATA")
        if program_files:
            candidates.append(os.path.join(program_files, "Microsoft", "Edge", "Application", "msedge.exe"))
        if program_files_x86:
            candidates.append(os.path.join(program_files_x86, "Microsoft", "Edge", "Application", "msedge.exe"))
        if local_app_data:
            candidates.append(os.path.join(local_app_data, "Microsoft", "Edge", "Application", "msedge.exe"))
        for p in candidates:
            if p and os.path.exists(p):
                return p
    except Exception:
        pass
    return None


def get_login_attempts(use_proxy: bool):
    attempts = []
    if use_proxy:
        attempts.append({"proxy": True, "use_service": True, "label": "ui+proxy+service"})
    attempts.extend(
        [
            {"proxy": False, "use_service": True, "label": "ui+no-proxy+service"},
            {"proxy": False, "use_service": False, "label": "ui+no-proxy+PATH"},
        ]
    )
    return attempts

def setup_driver(user_data_dir=None, profile_directory=None, use_proxy: bool = True):
    """设置MS Edge浏览器驱动，支持附加到现有Edge用户配置文件以帮助通过安全检查"""
    edge_binary = find_edge_binary()
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
        opts.add_argument('--no-first-run')
        opts.add_argument('--no-default-browser-check')
        opts.add_argument('--start-maximized')
        opts.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
        if edge_binary:
            try:
                opts.binary_location = edge_binary
            except Exception:
                pass
        
        # 附加到Edge用户配置文件以重用cookie和人类信号
        if user_data_dir:
            opts.add_argument(f"--user-data-dir={user_data_dir}")
        if profile_directory:
            opts.add_argument(f"--profile-directory={profile_directory}")
            
        # 设置代理
        if use_proxy:
            opts.add_argument(f'--proxy-server=socks5://{SOCKS5_PROXY_HOST}:{SOCKS5_PROXY_PORT}')
            opts.add_argument('--proxy-bypass-list=<-loopback>')
        
        return opts

    # 确定驱动路径
    system = platform.system().lower()
    if system == "darwin":
        machine = platform.machine().lower()
        default_driver_path = "/usr/local/bin/edgedriver_mac64_m1/msedgedriver" if machine in ['arm64', 'aarch64'] else "/usr/local/bin/edgedriver_mac64/msedgedriver"
    elif system == "windows":
        bundled_driver = runtime_path('tools', 'msedgedriver.exe')
        default_driver_path = bundled_driver if os.path.exists(bundled_driver) else r"C:\\bin\\edgedriver_win64\\msedgedriver.exe"
    elif system == "linux":
        default_driver_path = "/usr/local/bin/edgedriver_linux64/msedgedriver"
    else:
        default_driver_path = "/usr/local/bin/edgedriver_mac64/msedgedriver"

    user_driver_path = os.path.expanduser("~/bin/edgedriver_mac64_m1/msedgedriver")
    driver_path = user_driver_path if os.path.exists(user_driver_path) else default_driver_path

    last_error = None
    attempts = get_login_attempts(use_proxy)
    
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
            
            # 隐藏webdriver特征
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

    print(f"MS Edge driver启动失败: {last_error}")
    print("请确保已安装MS Edge浏览器和EdgeDriver")
    print("您可以运行update_msedge_driver.py来安装驱动")
    return None


def is_login_page(driver):
    """检测当前页面是否为登录页面"""
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
    """检测当前页面是否为安全验证页面"""
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


def wait_for_manual_login(driver, seconds=300, reopen_url=None):
    """
    等待用户手动登录，支持按回车立即继续，否则最长等待seconds秒
    :param driver: WebDriver实例
    :param seconds: 最长等待时间（秒），默认为300秒（5分钟）
    :param reopen_url: 登录后重新打开的URL
    """
    import select as _select
    print(f"检测到需要登录，请手工操作。按回车立即继续，或最多等待 {int(seconds)} 秒…")
    try:
        # 使用select监听标准输入，等待用户按键或超时
        rlist, _, _ = _select.select([sys.stdin], [], [], seconds)
        if rlist:
            _ = sys.stdin.readline()  # 读取回车符
            print("检测到回车，继续执行…")
        else:
            print("等待超时，继续执行…")
    except Exception:
        # 如果select不可用（如Windows某些环境），回退到简单的sleep
        time.sleep(seconds)
    
    # 如果提供了重新打开的URL，则在登录后访问该URL
    if reopen_url:
        try:
            print(f"登录处理完成，重新打开页面：{reopen_url}")
            driver.get(reopen_url)
            random_delay(2, 3)  # 给页面加载时间
        except Exception:
            pass


def main():
    """主函数"""
    print("===== JAVDB登录助手 =====")
    print("本工具使用专用的Edge用户数据目录来持久化登录状态")
    print(f"用户数据目录: {get_dedicated_edge_user_data_dir()}")
    import argparse
    parser = argparse.ArgumentParser(description="JAVDB登录助手")
    parser.add_argument("--no-proxy", dest="no_proxy", action="store_true", help="禁用SOCKS5代理直连")
    args = parser.parse_args()
    use_proxy = False if args.no_proxy else bool(USE_SOCKS5_PROXY)
    base_url = get_javdb_base_url(use_proxy)
    login_url = f"{base_url}/login"
    print(f"网络模式: {'代理' if use_proxy else '直连'}")
    
    # 启动Edge浏览器
    user_data_dir = get_dedicated_edge_user_data_dir()
    driver = setup_driver(user_data_dir=user_data_dir, use_proxy=use_proxy)
    
    if not driver:
        print("无法启动浏览器，程序退出")
        sys.exit(1)
    
    try:
        # 访问登录页面
        print(f"正在访问登录页面: {login_url}")
        driver.get(login_url)
        random_delay(3, 5)  # 等待页面加载
        
        # 检查是否需要登录或安全验证
        if is_security_verification_page(driver):
            print("检测到安全验证页面，请完成验证")
            wait_for_manual_login(driver, seconds=300, reopen_url=login_url)
        
        if is_login_page(driver):
            print("检测到登录页面，请手动登录您的JAVDB账号")
            wait_for_manual_login(driver, seconds=300, reopen_url=base_url)
        
        # 验证是否登录成功
        print("正在验证登录状态...")
        driver.get(base_url)
        random_delay(3, 5)
        
        # 简单的登录验证：检查是否存在用户相关元素或不再跳转登录页
        if not is_login_page(driver):
            print("\n登录状态已保存成功！")
            print("下次运行其他需要登录的脚本时，将自动使用此登录状态")
            print(f"用户数据存储在: {user_data_dir}")
        else:
            print("\n登录可能未成功，请检查并重新尝试")
            
        # 提示用户可以手动操作浏览器
        print("\n您现在可以在浏览器中进行任何操作，完成后请关闭浏览器窗口以结束程序")
        
        # 等待用户关闭浏览器
        while True:
            try:
                # 检查浏览器是否仍在运行
                driver.current_url  # 尝试访问浏览器，如果关闭会抛出异常
                time.sleep(1)
            except:
                print("浏览器已关闭，程序退出")
                break
        
    except Exception as e:
        print(f"发生错误: {e}")
    finally:
        try:
            driver.quit()
        except:
            pass


if __name__ == "__main__":
    # 导入random模块（只在main中使用，避免不必要的导入）
    import random
    main()
