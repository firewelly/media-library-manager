#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JAVDB信息更新器卷测试脚本
专门用于测试/Volumes/Video/usr/路径下的文件
"""

import os
import sys
import glob

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 测试/Volumes/Video/usr/路径下的文件
def test_volumes_videos():
    """测试/Volumes/Video/usr/路径下的视频文件"""
    print("===== 测试/Volumes/Video/usr/路径下的视频文件 =====")
    
    # 尝试导入CodeExtractor类
    try:
        from javdb_information_updater import CodeExtractor
        print("成功导入CodeExtractor类")
    except ImportError as e:
        print(f"导入失败: {e}")
        return False
    
    # 初始化提取器
    extractor = CodeExtractor()
    
    # 定义测试路径
    test_path = '/Volumes/Video/usr/'
    if not os.path.exists(test_path):
        print(f"路径不存在: {test_path}")
        return False
    
    print(f"正在扫描路径: {test_path}")
    
    # 获取所有视频文件
    video_extensions = ['*.mp4', '*.mkv', '*.avi', '*.wmv', '*.mov', '*.flv', '*.webm']
    video_files = []
    
    # 遍历路径下的所有文件和子目录
    for root, dirs, files in os.walk(test_path):
        for ext in video_extensions:
            pattern = os.path.join(root, ext)
            video_files.extend(glob.glob(pattern))
        
        # 限制搜索深度，避免时间过长
        if len(video_files) > 100:  # 限制最多100个文件
            break
    
    if not video_files:
        print("没有找到视频文件")
        return False
    
    print(f"找到 {len(video_files)} 个视频文件")
    
    # 统计结果
    success_count = 0
    failure_count = 0
    
    # 测试前几个文件（最多20个）
    test_files = video_files[:20]
    print(f"\n测试前20个文件的番号提取：")
    
    for file_path in test_files:
        try:
            # 获取文件名（不包含路径）
            filename = os.path.basename(file_path)
            
            # 提取番号
            extracted_code = extractor.extract_code_from_filename(file_path)
            
            if extracted_code:
                success_count += 1
                print(f"✓ 成功: {filename[:50]}... -> {extracted_code}")
            else:
                failure_count += 1
                print(f"✗ 失败: {filename[:50]}... -> 无法提取番号")
        except Exception as e:
            failure_count += 1
            print(f"✗ 异常: {os.path.basename(file_path)[:50]}... -> {e}")
    
    # 打印统计结果
    print(f"\n测试结果: 成功 {success_count} 个, 失败 {failure_count} 个")
    
    # 返回测试结果
    return success_count > 0

# 测试特定演员文件夹
def test_specific_actor_folder():
    """测试特定演员文件夹下的视频文件"""
    print("\n===== 测试特定演员文件夹下的视频文件 =====")
    
    # 获取演员文件夹列表
    test_path = '/Volumes/Video/usr/'
    actor_folders = []
    
    try:
        # 获取所有目录
        for item in os.listdir(test_path):
            item_path = os.path.join(test_path, item)
            if os.path.isdir(item_path):
                actor_folders.append(item)
        
        if not actor_folders:
            print("没有找到演员文件夹")
            return False
        
        print(f"找到 {len(actor_folders)} 个演员文件夹")
        print("前10个演员文件夹:")
        for folder in actor_folders[:10]:
            print(f"  - {folder}")
        
        # 选择第一个演员文件夹进行测试
        if actor_folders:
            selected_folder = actor_folders[0]
            selected_path = os.path.join(test_path, selected_folder)
            
            print(f"\n测试演员文件夹: {selected_folder}")
            
            # 尝试导入CodeExtractor类
            from javdb_information_updater import CodeExtractor
            extractor = CodeExtractor()
            
            # 获取视频文件
            video_extensions = ['*.mp4', '*.mkv', '*.avi', '*.wmv', '*.mov', '*.flv', '*.webm']
            video_files = []
            
            for ext in video_extensions:
                pattern = os.path.join(selected_path, ext)
                video_files.extend(glob.glob(pattern))
            
            if not video_files:
                print(f"在 {selected_folder} 中没有找到视频文件")
                return False
            
            print(f"在 {selected_folder} 中找到 {len(video_files)} 个视频文件")
            
            # 测试前几个文件
            success_count = 0
            failure_count = 0
            
            for file_path in video_files[:10]:  # 最多测试10个文件
                try:
                    filename = os.path.basename(file_path)
                    extracted_code = extractor.extract_code_from_filename(file_path)
                    
                    if extracted_code:
                        success_count += 1
                        print(f"✓ 成功: {filename[:50]}... -> {extracted_code}")
                    else:
                        failure_count += 1
                        print(f"✗ 失败: {filename[:50]}... -> 无法提取番号")
                except Exception as e:
                    failure_count += 1
                    print(f"✗ 异常: {filename[:50]}... -> {e}")
            
            print(f"\n测试结果: 成功 {success_count} 个, 失败 {failure_count} 个")
            return success_count > 0
        else:
            return False
    except Exception as e:
        print(f"测试演员文件夹时出错: {e}")
        return False

# 主测试函数
def run_volumes_tests():
    """运行卷测试"""
    print("开始测试/Volumes/Video/usr/路径下的文件...\n")
    
    # 运行测试
    all_videos_result = test_volumes_videos()
    specific_actor_result = test_specific_actor_folder()
    
    # 汇总结果
    print("\n===== 测试汇总 =====")
    print(f"所有视频文件测试: {'通过' if all_videos_result else '失败'}")
    print(f"特定演员文件夹测试: {'通过' if specific_actor_result else '失败'}")
    
    any_tests_passed = all_videos_result or specific_actor_result
    
    if any_tests_passed:
        print("\n✅ 测试通过！JAVDB信息更新器能够处理/Volumes/Video/usr/路径下的文件。")
        print("\n您可以通过以下命令运行主程序：")
        print("python javdb_information_updater.py")
        print("运行后，选择相应的文件夹进行批量更新。")
    else:
        print("\n❌ 所有测试失败，请检查路径和文件权限。")
    
    return any_tests_passed

if __name__ == "__main__":
    run_volumes_tests()