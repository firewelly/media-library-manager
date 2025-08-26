#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试Edge Cookie读取功能
"""

from edge_cookie_reader import EdgeCookieReader

def test_edge_cookies():
    """测试Edge cookie读取功能"""
    try:
        print("=== Edge Cookie读取测试 ===")
        
        # 创建cookie读取器
        cookie_reader = EdgeCookieReader()
        
        # 读取JAVDB相关的cookies
        print("正在读取JAVDB相关的cookies...")
        javdb_cookies = cookie_reader.get_cookies_for_domain('javdb.com')
        
        print(f"找到 {len(javdb_cookies)} 个JAVDB相关的cookies")
        
        if javdb_cookies:
            print("\n=== Cookie详情 ===")
            for i, cookie in enumerate(javdb_cookies, 1):
                print(f"{i}. Cookie名称: {cookie['name']}")
                print(f"   域名: {cookie.get('domain', 'N/A')}")
                print(f"   路径: {cookie.get('path', 'N/A')}")
                print(f"   值: {cookie['value'][:50]}{'...' if len(cookie['value']) > 50 else ''}")
                print(f"   安全: {cookie.get('secure', False)}")
                print(f"   HttpOnly: {cookie.get('http_only', False)}")
                if 'expires_utc' in cookie and cookie['expires_utc']:
                    print(f"   过期时间: {cookie['expires_utc']}")
                print()
            
            # 保存cookies到文件
            cookie_reader.save_cookies(javdb_cookies, "test_javdb_cookies.json")
            print("Cookies已保存到 test_javdb_cookies.json")
            
        else:
            print("未找到JAVDB相关的cookies")
            print("请确保：")
            print("1. 已在Edge浏览器中登录过JAVDB")
            print("2. Edge浏览器已关闭（避免数据库锁定）")
            print("3. 用户有权限访问Edge的用户数据目录")
        
        return len(javdb_cookies) > 0
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_edge_cookies()
    if success:
        print("\n✅ Edge Cookie读取测试成功！")
    else:
        print("\n❌ Edge Cookie读取测试失败！")