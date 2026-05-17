#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模型对比测试脚本
比较 Qwen3-VL-8B 和 Qwen3-VL-30B 的输出效果
支持不同帧数测试（8帧 vs 30帧）
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from video_analyzer_local_model_adult import VideoAnalyzerLocalModelAdult

def compare_models(video_path: str, num_frames: int = 8):
    """
    对比两个模型的分析效果
    
    Args:
        video_path: 视频文件路径
        num_frames: 提取帧数
    """
    if not os.path.exists(video_path):
        print(f"错误: 文件不存在 {video_path}")
        return
    
    print("=" * 60)
    print(f"视频文件: {os.path.basename(video_path)}")
    print(f"帧数设置: {num_frames}")
    print("=" * 60)
    
    models = [
        ("Qwen/Qwen3-VL-8B-Instruct", "8B模型"),
        ("Qwen/Qwen3-VL-30B-A3B-Instruct", "30B模型")
    ]
    
    results = []
    
    for model_name, model_label in models:
        print(f"\n{'='*40}")
        print(f"测试 {model_label}: {model_name}")
        print(f"{'='*40}")
        
        try:
            analyzer = VideoAnalyzerLocalModelAdult(
                api_base_url="https://api.siliconflow.cn",
                model_name=model_name,
                verbose=True
            )
            
            start_time = time.time()
            result = analyzer.analyze_video(video_path, num_frames=num_frames)
            elapsed_time = time.time() - start_time
            
            if result.get('success'):
                analysis_text = result.get('analysis', '')
                tags = analyzer.extract_tags_from_analysis(analysis_text)
                
                print(f"\n耗时: {elapsed_time:.2f}秒")
                print(f"帧数: {result.get('frames_extracted', 0)}")
                print(f"\n分析结果:")
                print(analysis_text)
                print(f"\n提取标签: {tags}")
                
                results.append({
                    'model': model_label,
                    'time': elapsed_time,
                    'tags': tags,
                    'analysis': analysis_text,
                    'frames': result.get('frames_extracted', 0)
                })
            else:
                print(f"分析失败: {result.get('error')}")
                results.append({
                    'model': model_label,
                    'error': result.get('error')
                })
                
        except Exception as e:
            print(f"异常: {e}")
            results.append({
                'model': model_label,
                'error': str(e)
            })
    
    # 对比结果
    print("\n" + "=" * 60)
    print("对比结果汇总")
    print("=" * 60)
    
    for r in results:
        if 'error' in r:
            print(f"\n{r['model']}: 失败 - {r['error']}")
        else:
            print(f"\n{r['model']}:")
            print(f"  耗时: {r['time']:.2f}秒")
            print(f"  标签: {r['tags']}")
            print(f"  标签数: {len(r['tags'])}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python compare_models.py <视频路径> [帧数]")
        print("\n示例:")
        print("python compare_models.py '/Users/firewell/影视/国产mac/测试视频.mp4'")
        print("python compare_models.py '/Users/firewell/影视/国产mac/测试视频.mp4' 30")
        sys.exit(1)
    
    video_path = sys.argv[1]
    num_frames = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    
    compare_models(video_path, num_frames)