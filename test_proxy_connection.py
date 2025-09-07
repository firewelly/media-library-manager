#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
代理连接测试脚本
测试socks5代理是否正常工作，以及各个爬虫网站的连接性
"""

import requests
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import socket

def test_socks_proxy():
    """测试socks5代理连接"""
    print("=== 测试SOCKS5代理连接 ===")
    
    # 测试代理是否可用
    proxy_host = '127.0.0.1'
    proxy_port = 1080
    
    try:
        # 尝试连接代理端口
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((proxy_host, proxy_port))
        sock.close()
        
        if result == 0:
            print(f"✓ SOCKS5代理 {proxy_host}:{proxy_port} 端口可达")
            return True
        else:
            print(f"✗ SOCKS5代理 {proxy_host}:{proxy_port} 端口不可达")
            return False
    except Exception as e:
        print(f"✗ 代理连接测试失败: {e}")
        return False

def test_website_connection(url, use_proxy=True, timeout=10):
    """测试网站连接"""
    session = requests.Session()
    
    # 设置重试策略
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    # 设置代理
    if use_proxy:
        proxies = {
            'http': 'socks5://127.0.0.1:1080',
            'https': 'socks5://127.0.0.1:1080'
        }
        session.proxies.update(proxies)
    
    # 设置请求头
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    try:
        print(f"测试 {url} {'(使用代理)' if use_proxy else '(直连)'}...")
        start_time = time.time()
        
        response = session.get(url, headers=headers, timeout=timeout, verify=False)
        
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            print(f"  ✓ 连接成功 - 状态码: {response.status_code}, 耗时: {elapsed:.2f}s")
            print(f"  ✓ 响应大小: {len(response.content)} bytes")
            return True
        else:
            print(f"  ✗ 连接失败 - 状态码: {response.status_code}, 耗时: {elapsed:.2f}s")
            return False
            
    except requests.exceptions.SSLError as e:
        print(f"  ✗ SSL错误: {e}")
        return False
    except requests.exceptions.ProxyError as e:
        print(f"  ✗ 代理错误: {e}")
        return False
    except requests.exceptions.ConnectTimeout as e:
        print(f"  ✗ 连接超时: {e}")
        return False
    except requests.exceptions.ReadTimeout as e:
        print(f"  ✗ 读取超时: {e}")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"  ✗ 连接错误: {e}")
        return False
    except Exception as e:
        print(f"  ✗ 其他错误: {e}")
        return False
    finally:
        session.close()

def main():
    """主测试函数"""
    print("开始网络连接测试...\n")
    
    # 1. 测试代理连接
    proxy_available = test_socks_proxy()
    print()
    
    # 2. 测试网站列表
    test_sites = [
        'https://www.javlibrary.com',
        'https://avsox.website',
        'https://www.javbus.com',
        'https://javdb.com',
        'https://www.google.com',  # 作为对照组
        'https://www.baidu.com',   # 作为对照组
    ]
    
    print("=== 测试网站连接性 ===")
    
    results = {}
    
    for site in test_sites:
        print(f"\n--- 测试 {site} ---")
        
        # 如果代理可用，先测试代理连接
        if proxy_available:
            proxy_result = test_website_connection(site, use_proxy=True)
            results[f"{site} (代理)"] = proxy_result
        
        # 测试直连
        direct_result = test_website_connection(site, use_proxy=False)
        results[f"{site} (直连)"] = direct_result
    
    # 3. 输出测试总结
    print("\n=== 测试结果总结 ===")
    print(f"SOCKS5代理状态: {'可用' if proxy_available else '不可用'}")
    print("\n网站连接测试结果:")
    
    for site, result in results.items():
        status = "✓ 成功" if result else "✗ 失败"
        print(f"  {site}: {status}")
    
    # 4. 给出建议
    print("\n=== 建议 ===")
    if not proxy_available:
        print("- 请检查SOCKS5代理是否正在运行 (127.0.0.1:1080)")
        print("- 可能需要启动代理软件 (如Clash、V2Ray等)")
    
    # 检查是否有网站完全无法访问
    failed_sites = []
    for site in test_sites:
        proxy_key = f"{site} (代理)"
        direct_key = f"{site} (直连)"
        
        proxy_ok = results.get(proxy_key, False)
        direct_ok = results.get(direct_key, False)
        
        if not proxy_ok and not direct_ok:
            failed_sites.append(site)
    
    if failed_sites:
        print("\n完全无法访问的网站:")
        for site in failed_sites:
            print(f"  - {site}")
        print("这些网站可能被封锁或服务器有问题")
    
    print("\n测试完成!")

if __name__ == "__main__":
    main()