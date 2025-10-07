#!/usr/bin/env python3
"""
测试脚本：验证JAVDB信息更新器的修复效果
"""
import os
import sys

# 确保可以导入当前目录的模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from javdb_information_updater import login_and_update

if __name__ == "__main__":
    print("===== JAVDB信息更新器修复测试 ====\n")
    print("此测试将自动选择包含ADN-347视频的文件夹进行更新")
    print("文件夹路径: /Volumes/app/usr\n")
    
    # 调用login_and_update函数，启用测试模式并指定测试文件夹
    login_and_update(test_mode=True, test_folder_path="/Volumes/app/usr")