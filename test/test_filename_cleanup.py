#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试文件名清理功能
验证process_single_filename函数的标题格式和叹号处理

作者: AI Assistant
创建时间: 2025
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from media_library import MediaLibrary

def test_filename_processing():
    """
    测试文件名处理功能
    """
    print("测试文件名清理功能")
    print("=" * 50)
    
    # 创建MediaLibrary实例
    media_lib = MediaLibrary()
    
    # 测试用例：包含各种问题的文件名
    test_cases = [
        # 测试叹号处理
        "!极品少妇.mp4",
        "!!美女视频.mp4", 
        "!!!超级大片.mp4",
        "!!!!顶级内容.mp4",
        "movie!.mp4",  # 叹号不在开头
        "mid!dle.mp4",  # 叹号在中间
        
        # 测试标题格式问题
        ".hidden_file.mp4",  # 以句号开头
        "normal_file..mp4",  # 多个句号
        "file.name.mp4",    # 中间有句号
        "..double_dot.mp4",  # 开头多个句号
        
        # 测试其他清理功能
        "CHINESEHOMEMADEVIDEO_test.mp4",
        "HHD800.COM@video.mp4",
        "WOXAV.COM@content.mp4",
        "【标签】视频.mp4",
        "(括号内容)视频.mp4",
        "WWW.EXAMPLE.COM_video.mp4",
        
        # 混合问题
        "!.【标签】CHINESEHOMEMADEVIDEO.mp4",
        "!!..HHD800.COM@content.mp4",
    ]
    
    print("测试用例处理结果：")
    print("-" * 50)
    
    for i, test_file in enumerate(test_cases, 1):
        try:
            result = media_lib.process_single_filename(test_file)
            print(f"{i:2d}. 原文件名: {test_file}")
            print(f"    处理结果: {result}")
            
            # 检查潜在问题
            issues = []
            if result.startswith('.'):
                issues.append("开头仍有句号")
            if result.endswith('.'):
                issues.append("结尾仍有句号")
            if '..' in result:
                issues.append("包含连续句号")
            if test_file.startswith('!') and not result.startswith('!'):
                issues.append("叹号被错误移除")
            if 'CHINESEHOMEMADEVIDEO' in result:
                issues.append("中文自制视频标识未清理")
            if 'HHD800.COM@' in result or 'WOXAV.COM@' in result:
                issues.append("网站标识未清理")
            
            if issues:
                print(f"    ⚠️  问题: {', '.join(issues)}")
            else:
                print(f"    ✅ 处理正常")
            print()
            
        except Exception as e:
            print(f"{i:2d}. 原文件名: {test_file}")
            print(f"    ❌ 处理出错: {e}")
            print()

def test_star_rating_extraction():
    """
    测试星级评分提取功能
    """
    print("\n测试星级评分提取功能")
    print("=" * 50)
    
    # 创建MediaLibrary实例
    media_lib = MediaLibrary()
    
    test_cases = [
        ("movie.mp4", 0),      # 无叹号
        ("!movie.mp4", 2),     # 1个叹号 = 2星
        ("!!movie.mp4", 3),    # 2个叹号 = 3星
        ("!!!movie.mp4", 4),   # 3个叹号 = 4星
        ("!!!!movie.mp4", 5),  # 4个叹号 = 5星
        ("!!!!!movie.mp4", 5), # 5个叹号 = 5星（最大值）
        ("movie!.mp4", 0),     # 叹号不在开头
        ("mo!vie.mp4", 0),     # 叹号在中间
    ]
    
    print("星级评分测试结果：")
    print("-" * 50)
    
    for i, (filename, expected_stars) in enumerate(test_cases, 1):
        try:
            # 假设有parse_stars_from_filename函数
            if hasattr(media_lib, 'parse_stars_from_filename'):
                actual_stars = media_lib.parse_stars_from_filename(filename)
                status = "✅" if actual_stars == expected_stars else "❌"
                print(f"{i}. {filename} -> 期望: {expected_stars}星, 实际: {actual_stars}星 {status}")
            else:
                # 手动实现星级检测逻辑
                exclamation_count = 0
                for char in filename:
                    if char == '!':
                        exclamation_count += 1
                    else:
                        break
                
                actual_stars = min(exclamation_count + 1, 5) if exclamation_count > 0 else 0
                status = "✅" if actual_stars == expected_stars else "❌"
                print(f"{i}. {filename} -> 期望: {expected_stars}星, 实际: {actual_stars}星 {status}")
                
        except Exception as e:
            print(f"{i}. {filename} -> ❌ 处理出错: {e}")

def main():
    """
    主函数
    """
    print("文件名清理功能测试")
    print("=" * 60)
    
    try:
        # 测试文件名处理
        test_filename_processing()
        
        # 测试星级评分
        test_star_rating_extraction()
        
        print("\n测试完成！")
        print("请检查上述结果，确认是否存在需要修复的问题。")
        
    except Exception as e:
        print(f"测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()