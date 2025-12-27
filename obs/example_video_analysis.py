#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频多模态分析器使用示例
"""

import os
from video_multimodal_analyzer import VideoMultimodalAnalyzer

def test_specific_video():
    """
    测试指定的视频文件
    """
    # 用户指定的测试视频路径
    video_path = "/Volumes/Data/影视/JAV/饭冈加奈子/MYBA-052 人妻の花びらめくり 森沢かな/MYBA-052.mp4"
    
    # 如果找不到指定路径，尝试查找目录下的mp4文件
    if not os.path.exists(video_path):
        base_dir = "/Volumes/Data/影视/JAV/饭冈加奈子/MYBA-052 人妻の花びらめくり 森沢かな"
        if os.path.exists(base_dir):
            mp4_files = [f for f in os.listdir(base_dir) if f.lower().endswith('.mp4')]
            if mp4_files:
                video_path = os.path.join(base_dir, mp4_files[0])
                print(f"找到视频文件: {video_path}")
            else:
                print(f"在目录 {base_dir} 中未找到mp4文件")
                return
        else:
            print(f"目录不存在: {base_dir}")
            return
    
    lm_studio_url = "http://127.0.0.1:1234"  # LM Studio服务器地址
    vocabulary_file = "vocabulary_tags.txt"  # 词汇标签文件
    output_dir = "MYBA-052_analysis_results"  # 输出目录
    
    print(f"开始分析视频: {os.path.basename(video_path)}")
    print(f"完整路径: {video_path}")
    
    try:
        # 创建分析器实例
        print("初始化视频多模态分析器...")
        analyzer = VideoMultimodalAnalyzer(
            lm_studio_url=lm_studio_url,
            vocabulary_file=vocabulary_file
        )
        
        # 执行视频分析
        result = analyzer.analyze_video(
            video_path=video_path,
            output_dir=output_dir
        )
        
        # 显示结果摘要
        print("\n" + "="*50)
        print("MYBA-052 分析结果摘要")
        print("="*50)
        print(f"视频文件: {result['video_path']}")
        print(f"分析帧数: {result['total_frames_analyzed']}")
        print(f"成功分析: {result['successful_analyses']}")
        print(f"匹配标签数: {len(result['all_matched_tags'])}")
        
        if result['all_matched_tags']:
            print("\n匹配的标签:")
            for tag in result['all_matched_tags']:
                frequency = result['tag_frequency'].get(tag, 0)
                print(f"  - {tag} (出现 {frequency} 次)")
        else:
            print("\n未匹配到任何标签")
        
        print(f"\n详细结果保存在: {output_dir}/")
        print("  - analysis_result.json: 完整的JSON格式结果")
        print("  - analysis_report.md: Markdown格式报告")
        print("  - frame_*.jpg: 抽取的视频帧图像")
        
    except Exception as e:
        print(f"分析过程中出现错误: {str(e)}")
        print("\n请检查:")
        print("1. LM Studio是否正在运行并加载了qwen2.5-vl-7b-abliterated-caption-it模型")
        print("2. 视频文件路径是否正确")
        print("3. vocabulary_tags.txt文件是否存在")
        print("4. 网络连接是否正常")

def example_usage():
    """
    通用使用示例
    """
    # 配置参数
    video_path = "your_video_file.mp4"  # 替换为实际的视频文件路径
    lm_studio_url = "http://127.0.0.1:1234"  # LM Studio服务器地址
    vocabulary_file = "vocabulary_tags.txt"  # 词汇标签文件
    output_dir = "video_analysis_results"  # 输出目录
    
    # 检查视频文件是否存在
    if not os.path.exists(video_path):
        print(f"错误: 视频文件不存在: {video_path}")
        print("请将 video_path 变量设置为实际的视频文件路径")
        return
    
    try:
        # 创建分析器实例
        print("初始化视频多模态分析器...")
        analyzer = VideoMultimodalAnalyzer(
            lm_studio_url=lm_studio_url,
            vocabulary_file=vocabulary_file
        )
        
        # 执行视频分析
        print(f"开始分析视频: {video_path}")
        result = analyzer.analyze_video(
            video_path=video_path,
            output_dir=output_dir
        )
        
        # 显示结果摘要
        print("\n" + "="*50)
        print("分析结果摘要")
        print("="*50)
        print(f"视频文件: {result['video_path']}")
        print(f"分析帧数: {result['total_frames_analyzed']}")
        print(f"成功分析: {result['successful_analyses']}")
        print(f"匹配标签数: {len(result['all_matched_tags'])}")
        
        if result['all_matched_tags']:
            print("\n匹配的标签:")
            for tag in result['all_matched_tags']:
                frequency = result['tag_frequency'].get(tag, 0)
                print(f"  - {tag} (出现 {frequency} 次)")
        else:
            print("\n未匹配到任何标签")
        
        print(f"\n详细结果保存在: {output_dir}/")
        print("  - analysis_result.json: 完整的JSON格式结果")
        print("  - analysis_report.md: Markdown格式报告")
        print("  - frame_*.jpg: 抽取的视频帧图像")
        
    except Exception as e:
        print(f"分析过程中出现错误: {str(e)}")
        print("\n请检查:")
        print("1. LM Studio是否正在运行并加载了qwen2.5-vl-7b-abliterated-caption-it模型")
        print("2. 视频文件路径是否正确")
        print("3. vocabulary_tags.txt文件是否存在")
        print("4. 网络连接是否正常")

def batch_analysis_example():
    """
    批量分析示例
    """
    # 视频文件列表
    video_files = [
        "video1.mp4",
        "video2.mp4",
        "video3.mp4"
    ]
    
    # 创建分析器
    analyzer = VideoMultimodalAnalyzer()
    
    # 批量分析
    for i, video_file in enumerate(video_files):
        if os.path.exists(video_file):
            print(f"\n分析第 {i+1}/{len(video_files)} 个视频: {video_file}")
            output_dir = f"analysis_batch_{i+1}"
            
            try:
                result = analyzer.analyze_video(video_file, output_dir)
                print(f"视频 {video_file} 分析完成，匹配到 {len(result['all_matched_tags'])} 个标签")
            except Exception as e:
                print(f"视频 {video_file} 分析失败: {str(e)}")
        else:
            print(f"跳过不存在的文件: {video_file}")

if __name__ == "__main__":
    print("视频多模态分析器使用示例")
    print("\n选择运行模式:")
    print("1. 测试指定视频 (MYBA-052)")
    print("2. 通用视频分析示例")
    print("3. 批量视频分析示例")
    
    choice = input("\n请输入选择 (1, 2 或 3): ").strip()
    
    if choice == "1":
        test_specific_video()
    elif choice == "2":
        example_usage()
    elif choice == "3":
        batch_analysis_example()
    else:
        print("无效选择，运行指定视频测试")
        test_specific_video()