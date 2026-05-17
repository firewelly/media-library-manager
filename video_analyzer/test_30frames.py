#!/usr/bin/env python3
"""对比测试：8帧 vs 30帧（30B模型）"""
import time, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from video_analyzer_local_model_adult import VideoAnalyzerLocalModelAdult

video_paths = [
    '/Users/firewell/影视/AV/#整理完成/明里つむぎ/FNS-166 無愛想な美人同僚とお酒の勢いでホテルに行ったら睨まれながらもチ●ポとオマ●コの相性ピッタリ過ぎて残業の度に密会セックスする関係に…/FNS-166.mp4',
    '/Users/firewell/影视/AV/#整理完成/美乃すずめ,美ノ嶋めぐり/DLDSS-481 不良生徒から優等生を守るため…人妻女教師 放課後肉便器 美乃すずめ/美ノ嶋めぐり パンティと写真付き/DLDSS-481.mp4'
]

model_name = 'Qwen/Qwen3-VL-30B-A3B-Instruct'

for video_path in video_paths:
    basename = os.path.basename(video_path)
    for num_frames, label in [(8, "8帧"), (30, "30帧")]:
        print(f"\n{'='*50}")
        print(f"{basename} - 30B模型 - {label}")
        print(f"{'='*50}")
        
        analyzer = VideoAnalyzerLocalModelAdult(
            api_base_url='https://api.siliconflow.cn',
            model_name=model_name,
            verbose=False
        )
        if num_frames > 8:
            analyzer.max_frames = num_frames
        
        start = time.time()
        result = analyzer.analyze_video(video_path, num_frames=num_frames)
        elapsed = time.time() - start
        
        print(f"耗时: {elapsed:.2f}秒")
        if result.get('success'):
            print(result['analysis'])
            tags = analyzer.extract_tags_from_analysis(result['analysis'])
            print(f"\n标签 ({len(tags)}个): {tags}")
        else:
            print(f"失败: {result.get('error')}")
        
        time.sleep(2)  # 避免限流
