#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
流水线视频分析器
- 帧提取串行（CPU密集型）
- API调用并行（IO密集型）
最大化资源利用率

作者: AI Assistant
创建时间: 2026-05-15
"""

import os
import time
import threading
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime

try:
    from .video_analyzer_local_model_adult import VideoAnalyzerLocalModelAdult
except ImportError:
    from video_analyzer_local_model_adult import VideoAnalyzerLocalModelAdult


@dataclass
class VideoTask:
    """视频分析任务"""
    video_id: int
    video_path: str
    title: str = ""
    frames_base64: List[str] = field(default_factory=list)
    frames_extracted: bool = False
    frames_error: str = ""
    api_result: Dict[str, Any] = field(default_factory=dict)
    api_completed: bool = False
    api_error: str = ""
    final_tags: List[str] = field(default_factory=list)
    final_description: str = ""
    start_time: float = 0.0
    end_time: float = 0.0


class PipelineVideoAnalyzer:
    def __init__(self,
                 api_base_url: str = "https://api.siliconflow.cn",
                 model_name: str = "Qwen/Qwen3-VL-8B-Instruct",
                 api_key: str = None,
                 num_frames: int = 8,
                 max_api_workers: int = 3,
                 verbose: bool = True,
                 progress_callback: Callable = None):
        """
        初始化流水线分析器
        
        Args:
            api_base_url: API地址
            model_name: 模型名称
            api_key: API密钥
            num_frames: 每个视频提取的帧数
            max_api_workers: 最大并行API调用数
            verbose: 是否显示详细输出
            progress_callback: 进度回调函数
        """
        self.api_base_url = api_base_url
        self.model_name = model_name
        self.api_key = api_key or os.getenv("SILICONFLOW_API_KEY")
        if not self.api_key:
            raise ValueError("API密钥未设置")
        
        self.num_frames = num_frames
        self.max_api_workers = max_api_workers
        self.verbose = verbose
        self.progress_callback = progress_callback
        
        self.base_analyzer = VideoAnalyzerLocalModelAdult(
            api_base_url=api_base_url,
            model_name=model_name,
            api_key=api_key,
            verbose=False
        )
        
        self.task_queue = queue.Queue()
        self.api_executor = None
        self.frame_extractor_thread = None
        
        self.stats = {
            'total_videos': 0,
            'frames_extracted': 0,
            'api_calls': 0,
            'success_count': 0,
            'error_count': 0,
            'total_time': 0.0
        }
        
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
    
    def log(self, message: str):
        """记录日志"""
        if self.verbose:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] {message}")
    
    def _extract_frames_worker(self):
        """帧提取工作线程（串行）"""
        while not self._stop_event.is_set():
            try:
                task = self.task_queue.get(timeout=1)
                if task is None:
                    break
                
                task.start_time = time.time()
                self.log(f"提取帧: {os.path.basename(task.video_path)}")
                
                try:
                    frames = self.base_analyzer.extract_frames(
                        task.video_path, 
                        num_frames=self.num_frames
                    )
                    
                    with self._lock:
                        task.frames_base64 = frames
                        task.frames_extracted = True
                        self.stats['frames_extracted'] += 1
                    
                    self.log(f"帧提取完成: {len(frames)}帧 -> {task.video_id}")
                    
                    if self.progress_callback:
                        self.progress_callback('frame_extracted', task)
                    
                except Exception as e:
                    with self._lock:
                        task.frames_error = str(e)
                        task.frames_extracted = True
                    self.log(f"帧提取失败: {task.video_id} - {e}")
                
                self.task_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                self.log(f"帧提取线程异常: {e}")
                break
    
    def _call_api(self, task: VideoTask) -> VideoTask:
        """API调用（并行执行）"""
        if task.frames_error:
            task.api_error = task.frames_error
            task.api_completed = True
            return task
        
        self.log(f"API调用: {task.video_id}")
        
        try:
            prompt = self.base_analyzer._generate_analysis_prompt_adult(task.video_path)
            result = self.base_analyzer.analyze_frames_with_local_model(
                task.frames_base64, prompt
            )
            
            with self._lock:
                task.api_result = result
                task.api_completed = True
                self.stats['api_calls'] += 1
                
                if result.get('success'):
                    self.stats['success_count'] += 1
                    analysis_text = result.get('analysis', '')
                    task.final_tags = self.base_analyzer.extract_tags_from_analysis(analysis_text)
                    task.final_description = self._extract_description(analysis_text)
                else:
                    self.stats['error_count'] += 1
                    task.api_error = result.get('error', 'Unknown error')
            
            self.log(f"API完成: {task.video_id} - 标签: {task.final_tags[:3]}...")
            
            if self.progress_callback:
                self.progress_callback('api_completed', task)
            
        except Exception as e:
            with self._lock:
                task.api_error = str(e)
                task.api_completed = True
                self.stats['error_count'] += 1
            self.log(f"API异常: {task.video_id} - {e}")
        
        task.end_time = time.time()
        return task
    
    def _extract_description(self, analysis_text: str) -> str:
        """提取描述"""
        if not analysis_text:
            return ""
        
        patterns = [
            r'【女性主角】[^\n]*',
            r'【服装穿着】[^\n]*',
            r'【场景环境】[^\n]*',
        ]
        
        parts = []
        for p in patterns:
            import re
            match = re.search(p, analysis_text)
            if match:
                parts.append(match.group(0))
        
        return ' '.join(parts) if parts else analysis_text[:100]
    
    def analyze_videos(self, videos: List[Dict[str, Any]]) -> List[VideoTask]:
        """
        流水线分析多个视频
        
        Args:
            videos: 视频列表，每个元素包含 id, path, title
            
        Returns:
            完成的任务列表
        """
        if not videos:
            return []
        
        self.log(f"开始流水线分析，共 {len(videos)} 个视频")
        self.log(f"配置: 帧数={self.num_frames}, API并行数={self.max_api_workers}")
        
        start_time = time.time()
        
        tasks = []
        for v in videos:
            task = VideoTask(
                video_id=v.get('id', 0),
                video_path=v.get('path', ''),
                title=v.get('title', '')
            )
            tasks.append(task)
            self.task_queue.put(task)
        
        with self._lock:
            self.stats['total_videos'] = len(videos)
        
        self.frame_extractor_thread = threading.Thread(
            target=self._extract_frames_worker,
            name="FrameExtractor"
        )
        self.frame_extractor_thread.start()
        
        completed_tasks = []
        pending_api_tasks = []
        
        while True:
            with self._lock:
                ready_tasks = [t for t in tasks if t.frames_extracted and not t.api_completed]
            
            for task in ready_tasks:
                if task not in pending_api_tasks:
                    pending_api_tasks.append(task)
            
            if pending_api_tasks:
                batch_size = min(len(pending_api_tasks), self.max_api_workers)
                batch = pending_api_tasks[:batch_size]
                pending_api_tasks = pending_api_tasks[batch_size:]
                
                with ThreadPoolExecutor(max_workers=batch_size) as executor:
                    futures = {executor.submit(self._call_api, t): t for t in batch}
                    
                    for future in as_completed(futures):
                        try:
                            completed_task = future.result()
                            completed_tasks.append(completed_task)
                        except Exception as e:
                            self.log(f"Future异常: {e}")
            
            with self._lock:
                all_done = all(t.api_completed for t in tasks)
            
            if all_done:
                break
            
            if not self.frame_extractor_thread.is_alive() and self.task_queue.empty():
                for task in tasks:
                    if not task.frames_extracted:
                        task.frames_extracted = True
                        task.frames_error = "帧提取线程已结束"
            
            time.sleep(0.1)
        
        self._stop_event.set()
        if self.frame_extractor_thread.is_alive():
            self.frame_extractor_thread.join(timeout=2)
        
        total_time = time.time() - start_time
        with self._lock:
            self.stats['total_time'] = total_time
        
        self.log("=" * 50)
        self.log("流水线分析完成")
        self.log(f"总耗时: {total_time:.2f}秒")
        self.log(f"成功: {self.stats['success_count']}, 失败: {self.stats['error_count']}")
        self.log(f"平均每视频: {total_time/len(videos):.2f}秒")
        self.log("=" * 50)
        
        return completed_tasks
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            return self.stats.copy()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='流水线视频分析器')
    parser.add_argument('videos', nargs='*', help='视频文件路径')
    parser.add_argument('--workers', type=int, default=3, help='API并行数')
    parser.add_argument('--frames', type=int, default=8, help='每视频帧数')
    
    args = parser.parse_args()
    
    if args.videos:
        videos = [{'id': i, 'path': p, 'title': os.path.basename(p)} 
                  for i, p in enumerate(args.videos)]
        
        analyzer = PipelineVideoAnalyzer(
            max_api_workers=args.workers,
            num_frames=args.frames,
            verbose=True
        )
        
        results = analyzer.analyze_videos(videos)
        
        for task in results:
            print(f"\n{task.video_id}: {task.final_tags}")