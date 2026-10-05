#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JAVDB登录助手（Playwright 版）

登录状态现由 javdb_crawler_single.py 的 Playwright 持久化会话
（.playwright_user_data/）保存；本脚本只是该交互式登录流程的入口，
兼容旧的 `python javdb_login_helper.py` 用法。
旧的 Selenium/.edge_driver_user_data 方案已废弃。
"""

import os
import subprocess
import sys


def _runtime_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.argv[0]))
    return os.path.dirname(os.path.abspath(__file__))


def _build_crawler_cmd():
    """构建登录子进程命令（兼容 PyInstaller 打包）"""
    if getattr(sys, 'frozen', False):
        return [os.path.join(_runtime_dir(), 'javdb_crawler_single.exe'), '--login']
    return [sys.executable, 'javdb_crawler_single.py', '--login']


def main():
    """打开持久化会话浏览器，等待用户手动登录 javdb 并保存登录态"""
    print("===== JAVDB登录助手（Playwright） =====")
    print("登录态将保存到持久化会话目录 .playwright_user_data/，")
    print("供 javdb_crawler_single.py / 批量更新器 / GUI 等脚本复用。")
    print("网络模式跟随 config.py 的 USE_SOCKS5_PROXY 配置。")
    try:
        result = subprocess.run(_build_crawler_cmd(), cwd=_runtime_dir())
        return result.returncode
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        print(f"登录流程失败: {e}")
        print("也可以直接运行: python javdb_crawler_single.py --login")
        return 1


if __name__ == "__main__":
    sys.exit(main() or 0)
