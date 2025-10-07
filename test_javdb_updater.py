#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JAVDB信息更新器测试脚本
用于验证核心功能是否正常工作，而不需要实际运行完整的登录和爬取流程
"""

import os
import sys

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 测试番号提取器功能
def test_code_extractor():
    """测试番号提取器是否能正确从文件名中提取番号"""
    print("===== 测试番号提取器 =====")
    
    # 尝试导入CodeExtractor类
    try:
        from javdb_information_updater import CodeExtractor
        print("成功导入CodeExtractor类")
    except ImportError as e:
        print(f"导入失败: {e}")
        return False
    
    # 初始化提取器
    extractor = CodeExtractor()
    
    # 测试用例
    test_cases = [
        ("ABC-123.mp4", "ABC-123"),
        ("[1pondo-001234_567]测试视频.mp4", "1pondo-001234_567"),
        ("FC2-PPV-123456.mp4", "FC2-123456"),
        ("加勒比Carib-123456-789.mkv", "carib-123456-789"),
        ("10musume-123456_01.avi", "10musume-123456_01"),
        ("Heydouga-1234-0567.mp4", "heydouga-1234-0567"),
        ("无分隔符ABC123视频.mp4", "ABC-123"),
        ("red0123测试.mp4", "red0123"),
        ("SKY00123测试.mp4", "SKY00123"),
        ("ex00123测试.mp4", "ex00123"),
        ("普通视频文件.mp4", None),  # 无法提取
    ]
    
    success_count = 0
    for filename, expected_code in test_cases:
        try:
            extracted_code = extractor.extract_code_from_filename(filename)
            if extracted_code == expected_code:
                success_count += 1
                print(f"✓ 成功: {filename} -> {extracted_code}")
            else:
                print(f"✗ 失败: {filename} -> 实际: {extracted_code}, 期望: {expected_code}")
        except Exception as e:
            print(f"✗ 异常: {filename} -> {e}")
    
    print(f"\n测试结果: {success_count}/{len(test_cases)} 通过")
    return success_count == len(test_cases)

# 测试数据库连接功能
def test_database_connection():
    """测试数据库连接功能"""
    print("\n===== 测试数据库连接 =====")
    
    # 尝试导入数据库相关函数
    try:
        from javdb_information_updater import DB_PATH, get_user_defined_folders
        print(f"成功导入数据库相关函数，数据库路径: {DB_PATH}")
    except ImportError as e:
        print(f"导入失败: {e}")
        return False
    
    # 检查数据库文件是否存在
    if not os.path.exists(DB_PATH):
        print(f"数据库文件不存在: {DB_PATH}")
        return False
    
    print("数据库文件存在，尝试获取用户定义的文件夹...")
    try:
        folders = get_user_defined_folders()
        print(f"成功获取 {len(folders)} 个用户定义的文件夹")
        if folders:
            print("前3个文件夹示例:")
            for folder_path, folder_type in folders[:3]:
                print(f"  - {folder_path} ({folder_type})")
        return True
    except Exception as e:
        print(f"获取文件夹失败: {e}")
        return False

# 测试其他核心功能
def test_core_components():
    """测试其他核心组件"""
    print("\n===== 测试其他核心组件 =====")
    
    # 检查必要的目录是否存在
    try:
        from javdb_information_updater import COVERS_DIR, get_dedicated_edge_user_data_dir
        
        # 检查封面目录
        print(f"封面目录: {COVERS_DIR}")
        if not os.path.exists(COVERS_DIR):
            print("封面目录不存在，将尝试创建")
            os.makedirs(COVERS_DIR, exist_ok=True)
            print("封面目录创建成功")
        else:
            print("封面目录已存在")
        
        # 检查Edge用户数据目录
        user_data_dir = get_dedicated_edge_user_data_dir()
        print(f"Edge用户数据目录: {user_data_dir}")
        if not os.path.exists(user_data_dir):
            print("Edge用户数据目录不存在，将尝试创建")
            os.makedirs(user_data_dir, exist_ok=True)
            print("Edge用户数据目录创建成功")
        else:
            print("Edge用户数据目录已存在")
        
        return True
    except Exception as e:
        print(f"测试核心组件失败: {e}")
        return False

# 运行所有测试
def run_all_tests():
    """运行所有测试"""
    print("开始测试JAVDB信息更新器...\n")
    
    # 运行测试
    code_extractor_result = test_code_extractor()
    database_result = test_database_connection()
    core_components_result = test_core_components()
    
    # 汇总结果
    print("\n===== 测试汇总 =====")
    print(f"番号提取器: {'通过' if code_extractor_result else '失败'}")
    print(f"数据库连接: {'通过' if database_result else '失败'}")
    print(f"核心组件: {'通过' if core_components_result else '失败'}")
    
    all_tests_passed = code_extractor_result and database_result and core_components_result
    
    if all_tests_passed:
        print("\n✅ 所有测试通过！JAVDB信息更新器的核心功能正常。")
        print("\n您可以通过以下命令运行主程序：")
        print("python javdb_information_updater.py")
    else:
        print("\n❌ 部分测试失败，请检查输出信息并修复问题。")
    
    return all_tests_passed

if __name__ == "__main__":
    run_all_tests()