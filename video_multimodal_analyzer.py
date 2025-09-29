#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频多模态分析器
基于给定的视频文件，抽取10帧影像，使用本地LM Studio的qwen2.5-vl-7b模型
进行女性人物形象描述和剧情推测，并与vocabulary_tags.txt中的标签进行匹配
"""

import cv2
import os
import sys
import json
import base64
import requests
from typing import List, Dict, Tuple
import argparse
from pathlib import Path
import numpy as np
from PIL import Image
import io

class VideoMultimodalAnalyzer:
    def __init__(self, lm_studio_url: str = "http://127.0.0.1:1234", vocabulary_file: str = "vocabulary_tags.txt"):
        """
        初始化视频多模态分析器
        
        Args:
            lm_studio_url: LM Studio服务器地址
            vocabulary_file: 词汇标签文件路径
        """
        self.lm_studio_url = self._detect_available_server(lm_studio_url)
        self.vocabulary_file = vocabulary_file
        self.vocabulary_tags = self._load_vocabulary_tags()
    
    def _detect_available_server(self, preferred_url: str = "http://127.0.0.1:1234") -> str:
        """
        检测可用的LM Studio服务器，优先使用localhost，如果不可用则使用备用服务器
        
        Args:
            preferred_url: 首选服务器地址
            
        Returns:
            可用的服务器地址
        """
        servers_to_try = [
            "http://127.0.0.1:1234",
            "http://192.168.110.213:1234"
        ]
        
        # 如果用户指定了特定的URL，优先尝试
        if preferred_url not in servers_to_try:
            servers_to_try.insert(0, preferred_url)
        
        for server_url in servers_to_try:
            try:
                print(f"正在测试服务器: {server_url}")
                response = requests.get(f"{server_url}/v1/models", timeout=5)
                if response.status_code == 200:
                    print(f"✓ 服务器可用: {server_url}")
                    return server_url
                else:
                    print(f"✗ 服务器响应异常: {server_url} (状态码: {response.status_code})")
            except requests.exceptions.RequestException as e:
                print(f"✗ 服务器不可用: {server_url} ({str(e)})")
        
        # 如果所有服务器都不可用，返回默认值并警告
        print("警告: 所有服务器都不可用，使用默认地址，可能会导致分析失败")
        return preferred_url
        
    def _load_vocabulary_tags(self) -> List[str]:
        """
        加载词汇标签文件
        
        Returns:
            标签列表
        """
        try:
            with open(self.vocabulary_file, 'r', encoding='utf-8') as f:
                tags = [line.strip() for line in f.readlines() if line.strip()]
            print(f"已加载 {len(tags)} 个词汇标签")
            return tags
        except FileNotFoundError:
            print(f"警告: 词汇标签文件 {self.vocabulary_file} 未找到")
            return []
    
    def extract_frames(self, video_path: str, num_frames: int = 10) -> List[np.ndarray]:
        """
        从视频中抽取指定数量的帧
        
        Args:
            video_path: 视频文件路径
            num_frames: 要抽取的帧数
            
        Returns:
            帧图像列表
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"视频文件不存在: {video_path}")
        
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"无法打开视频文件: {video_path}")
        
        # 获取视频总帧数
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        duration = total_frames / fps if fps > 0 else 0
        
        print(f"视频信息: 总帧数={total_frames}, FPS={fps:.2f}, 时长={duration:.2f}秒")
        
        # 计算要抽取的帧索引
        if total_frames <= num_frames:
            frame_indices = list(range(total_frames))
        else:
            # 均匀分布抽取帧
            frame_indices = np.linspace(0, total_frames - 1, num_frames, dtype=int)
        
        frames = []
        for frame_idx in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if ret:
                # 转换BGR到RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frames.append(frame_rgb)
            else:
                print(f"警告: 无法读取第 {frame_idx} 帧")
        
        cap.release()
        print(f"成功抽取 {len(frames)} 帧图像")
        return frames
    
    def frame_to_base64(self, frame: np.ndarray) -> str:
        """
        将帧图像转换为base64编码
        
        Args:
            frame: 帧图像数组
            
        Returns:
            base64编码的图像字符串
        """
        # 转换为PIL图像
        pil_image = Image.fromarray(frame)
        
        # 压缩图像以减少传输大小
        buffer = io.BytesIO()
        pil_image.save(buffer, format='JPEG', quality=85)
        
        # 转换为base64
        img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return img_base64
    
    def analyze_frame_with_llm(self, frame_base64: str, frame_index: int) -> Dict:
        """
        使用LM Studio的多模态模型分析单帧图像
        
        Args:
            frame_base64: base64编码的图像
            frame_index: 帧索引
            
        Returns:
            分析结果字典
        """
        prompt = """
请仔细观察这张图像，并进行以下分析：

1. 女性人物形象描述：
   - 外貌特征（年龄、身材、发型、妆容等）
   - 服装穿着（衣物、类型、颜色、风格等）
   - 整体气质和风格

2. 场景和剧情推测：
   - 女性职业
   - 场景环境描述
   - 可能的剧情情节
   - 人物关系和互动

3. 关键特征标签：
   - 提取能够描述人物和场景的关键词
   - 重点关注人物特征、服装、场景、动作等

请用中文回答，尽量详细和准确。
"""
        
        try:
            # 构建请求数据
            data = {
                "model": "qwen2.5-vl-7b-abliterated-caption-it",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{frame_base64}"
                                }
                            }
                        ]
                    }
                ],
                "temperature": 0.7,
                "max_tokens": 1000
            }
            
            # 发送请求到LM Studio
            response = requests.post(
                f"{self.lm_studio_url}/v1/chat/completions",
                json=data,
                headers={"Content-Type": "application/json"},
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                analysis_text = result['choices'][0]['message']['content']
                
                return {
                    "frame_index": frame_index,
                    "analysis": analysis_text,
                    "success": True
                }
            else:
                print(f"LM Studio请求失败: {response.status_code} - {response.text}")
                return {
                    "frame_index": frame_index,
                    "analysis": "",
                    "success": False,
                    "error": f"HTTP {response.status_code}"
                }
                
        except Exception as e:
            print(f"分析第 {frame_index} 帧时出错: {str(e)}")
            return {
                "frame_index": frame_index,
                "analysis": "",
                "success": False,
                "error": str(e)
            }
    
    def match_vocabulary_tags(self, analysis_text: str) -> List[str]:
        """
        将分析结果与词汇标签进行匹配
        
        Args:
            analysis_text: 分析文本
            
        Returns:
            匹配的标签列表
        """
        matched_tags = []
        analysis_lower = analysis_text.lower()
        
        for tag in self.vocabulary_tags:
            if tag in analysis_text or tag.lower() in analysis_lower:
                matched_tags.append(tag)
        
        return matched_tags
    
    def analyze_video(self, video_path: str, output_dir: str = "analysis_output", num_frames: int = 10) -> Dict:
        """
        分析整个视频文件
        
        Args:
            video_path: 视频文件路径
            output_dir: 输出目录
            num_frames: 要抽取的帧数，默认为10
            
        Returns:
            完整的分析结果
        """
        print(f"开始分析视频: {video_path}")
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 抽取帧
        frames = self.extract_frames(video_path, num_frames=num_frames)
        
        # 分析结果
        analysis_results = []
        all_matched_tags = set()
        
        print("开始逐帧分析...")
        for i, frame in enumerate(frames):
            print(f"分析第 {i+1}/{len(frames)} 帧...")
            
            # 转换为base64
            frame_base64 = self.frame_to_base64(frame)
            
            # 使用LLM分析
            analysis_result = self.analyze_frame_with_llm(frame_base64, i)
            
            if analysis_result['success']:
                # 匹配词汇标签
                matched_tags = self.match_vocabulary_tags(analysis_result['analysis'])
                analysis_result['matched_tags'] = matched_tags
                all_matched_tags.update(matched_tags)
                
                print(f"第 {i+1} 帧分析完成，匹配到 {len(matched_tags)} 个标签")
            else:
                analysis_result['matched_tags'] = []
                print(f"第 {i+1} 帧分析失败")
            
            analysis_results.append(analysis_result)
            
            # 保存帧图像
            frame_path = os.path.join(output_dir, f"frame_{i:03d}.jpg")
            Image.fromarray(frame).save(frame_path, quality=95)
        
        # 汇总结果
        summary_result = {
            "video_path": video_path,
            "total_frames_analyzed": len(frames),
            "successful_analyses": sum(1 for r in analysis_results if r['success']),
            "all_matched_tags": sorted(list(all_matched_tags)),
            "frame_analyses": analysis_results,
            "tag_frequency": self._calculate_tag_frequency(analysis_results)
        }
        
        # 保存结果到JSON文件
        result_file = os.path.join(output_dir, "analysis_result.json")
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(summary_result, f, ensure_ascii=False, indent=2)
        
        # 生成报告
        self._generate_report(summary_result, output_dir)
        
        print(f"\n分析完成！")
        print(f"总共分析了 {len(frames)} 帧")
        print(f"成功分析 {summary_result['successful_analyses']} 帧")
        print(f"匹配到 {len(all_matched_tags)} 个不同的标签")
        print(f"结果保存在: {output_dir}")
        
        return summary_result
    
    def _calculate_tag_frequency(self, analysis_results: List[Dict]) -> Dict[str, int]:
        """
        计算标签出现频率
        
        Args:
            analysis_results: 分析结果列表
            
        Returns:
            标签频率字典
        """
        tag_frequency = {}
        for result in analysis_results:
            if 'matched_tags' in result:
                for tag in result['matched_tags']:
                    tag_frequency[tag] = tag_frequency.get(tag, 0) + 1
        return dict(sorted(tag_frequency.items(), key=lambda x: x[1], reverse=True))
    
    def _generate_report(self, summary_result: Dict, output_dir: str):
        """
        生成分析报告
        
        Args:
            summary_result: 汇总结果
            output_dir: 输出目录
        """
        report_file = os.path.join(output_dir, "analysis_report.md")
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("# 视频多模态分析报告\n\n")
            f.write(f"**视频文件**: {summary_result['video_path']}\n\n")
            f.write(f"**分析帧数**: {summary_result['total_frames_analyzed']}\n\n")
            f.write(f"**成功分析**: {summary_result['successful_analyses']}\n\n")
            
            # 匹配的标签
            f.write("## 匹配的词汇标签\n\n")
            if summary_result['all_matched_tags']:
                for tag in summary_result['all_matched_tags']:
                    frequency = summary_result['tag_frequency'].get(tag, 0)
                    f.write(f"- {tag} (出现 {frequency} 次)\n")
            else:
                f.write("未匹配到任何标签\n")
            
            # 标签频率统计
            f.write("\n## 标签频率统计\n\n")
            if summary_result['tag_frequency']:
                f.write("| 标签 | 出现次数 |\n")
                f.write("|------|----------|\n")
                for tag, freq in summary_result['tag_frequency'].items():
                    f.write(f"| {tag} | {freq} |\n")
            
            # 逐帧分析详情
            f.write("\n## 逐帧分析详情\n\n")
            for i, result in enumerate(summary_result['frame_analyses']):
                f.write(f"### 第 {i+1} 帧\n\n")
                if result['success']:
                    f.write(f"**分析结果**:\n{result['analysis']}\n\n")
                    if result['matched_tags']:
                        f.write(f"**匹配标签**: {', '.join(result['matched_tags'])}\n\n")
                    else:
                        f.write("**匹配标签**: 无\n\n")
                else:
                    f.write(f"**分析失败**: {result.get('error', '未知错误')}\n\n")
                f.write("---\n\n")

def main():
    parser = argparse.ArgumentParser(description='视频多模态分析器')
    parser.add_argument('video_path', help='视频文件路径')
    parser.add_argument('--lm-studio-url', default='http://127.0.0.1:1234', help='LM Studio服务器地址')
    parser.add_argument('--vocabulary-file', default='vocabulary_tags.txt', help='词汇标签文件路径')
    parser.add_argument('--output-dir', default='analysis_output', help='输出目录')
    parser.add_argument('--num-frames', type=int, default=10, help='抽取的帧数')
    
    args = parser.parse_args()
    
    try:
        # 创建分析器
        analyzer = VideoMultimodalAnalyzer(
            lm_studio_url=args.lm_studio_url,
            vocabulary_file=args.vocabulary_file
        )
        
        # 分析视频
        result = analyzer.analyze_video(
            video_path=args.video_path,
            output_dir=args.output_dir,
            num_frames=args.num_frames
        )
        
        print("\n=== 分析摘要 ===")
        print(f"匹配的标签: {', '.join(result['all_matched_tags']) if result['all_matched_tags'] else '无'}")
        
    except Exception as e:
        print(f"错误: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()