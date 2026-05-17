import os
from typing import List, Dict, Any
from .video_analyzer_local_model_adult import VideoAnalyzerLocalModelAdult
from .video_analyzer_pipeline import PipelineVideoAnalyzer

class VideoContentAnalyzer:
    def __init__(self, db_path="media_library.db", use_pipeline=False, max_workers=3):
        self.db_path = db_path
        self.use_pipeline = use_pipeline
        self.max_workers = max_workers
        
        self.analyzer = VideoAnalyzerLocalModelAdult(
            api_base_url="https://api.siliconflow.cn",
            model_name="Qwen/Qwen3-VL-30B-A3B-Instruct",
            verbose=True
        )
        
        if use_pipeline:
            self.pipeline_analyzer = PipelineVideoAnalyzer(
                api_base_url="https://api.siliconflow.cn",
                model_name="Qwen/Qwen3-VL-30B-A3B-Instruct",
                max_api_workers=max_workers,
                verbose=True
            )

    def analyze_video_content(self, video_path, min_frames=100, max_interval=10, max_frames=300):
        """
        Analyze video content and return tags.
        Arguments min_frames, max_interval, max_frames are kept for compatibility 
        but are largely ignored in favor of the new model's optimal settings (5-8 frames).
        """
        try:
            result = self.analyzer.analyze_video(video_path)
            
            if not result.get('success', False):
                return {'error': result.get('error', 'Unknown error')}
            
            analysis_text = result.get('analysis', '')
            generated_tags = self.analyzer.extract_tags_from_analysis(analysis_text)
            
            return {
                'generated_tags': generated_tags,
                'frames_analyzed': result.get('frames_extracted', 0),
                'analysis_text': analysis_text,
                'summary': {'generated_tags': generated_tags}
            }
        except Exception as e:
            return {'error': str(e)}

    def analyze_video_content_with_retry(self, video_path):
        """
        带重试的视频内容分析：
        1. 先用默认方式（均匀采样5-8帧）分析
        2. 如果没有生成标签，用30帧随机采样重试
        3. 如果仍然没有标签，返回特殊标记 'no_tag'
        
        Returns:
            dict: 包含 generated_tags, frames_analyzed, retry_used, analysis_text
        """
        try:
            result = self.analyzer.analyze_video(video_path)
            
            if not result.get('success', False):
                error = result.get('error', 'Unknown error')
                return {'error': error, 'generated_tags': [], 'retry_used': False}
            
            analysis_text = result.get('analysis', '')
            generated_tags = self.analyzer.extract_tags_from_analysis(analysis_text)
            
            if generated_tags:
                return {
                    'generated_tags': generated_tags,
                    'frames_analyzed': result.get('frames_extracted', 0),
                    'analysis_text': analysis_text,
                    'retry_used': False,
                    'summary': {'generated_tags': generated_tags}
                }
            
            print(f"   首次分析未生成标签，尝试30帧随机采样重试...")
            
            frames_base64 = self.analyzer.extract_frames_random(video_path, num_frames=30)
            
            if not frames_base64:
                return {
                    'generated_tags': [],
                    'frames_analyzed': 0,
                    'retry_used': True,
                    'analysis_text': '',
                    'no_tag': True
                }
            
            prompt = self.analyzer._generate_analysis_prompt_adult(video_path)
            retry_result = self.analyzer.analyze_frames_with_local_model(frames_base64, prompt)
            
            if retry_result.get('success', False):
                retry_analysis = retry_result.get('analysis', '')
                retry_tags = self.analyzer.extract_tags_from_analysis(retry_analysis)
                
                if retry_tags:
                    print(f"   30帧随机重试成功，获得标签: {', '.join(retry_tags)}")
                    return {
                        'generated_tags': retry_tags,
                        'frames_analyzed': len(frames_base64),
                        'analysis_text': retry_analysis,
                        'retry_used': True,
                        'summary': {'generated_tags': retry_tags}
                    }
            
            print(f"   30帧随机重试仍未生成标签，标记为<无标签>")
            return {
                'generated_tags': [],
                'frames_analyzed': len(frames_base64),
                'retry_used': True,
                'analysis_text': retry_result.get('analysis', ''),
                'no_tag': True
            }
            
        except Exception as e:
            return {'error': str(e), 'generated_tags': [], 'retry_used': False}
    
    def analyze_videos_batch(self, video_paths: List[str], progress_callback=None) -> List[Dict[str, Any]]:
        """
        Batch analyze multiple videos using pipeline mode.
        
        Args:
            video_paths: List of video file paths
            progress_callback: Optional callback function for progress updates
            
        Returns:
            List of analysis results for each video
        """
        if not self.use_pipeline or not hasattr(self, 'pipeline_analyzer'):
            results = []
            for i, path in enumerate(video_paths):
                result = self.analyze_video_content(path)
                results.append({'path': path, 'result': result})
                if progress_callback:
                    progress_callback(i, len(video_paths), path, result)
            return results
        
        videos = [{'id': i, 'path': p, 'title': os.path.basename(p)} 
                  for i, p in enumerate(video_paths)]
        
        def pipeline_progress(stage, task):
            if progress_callback:
                idx = task.video_id
                if stage == 'api_completed':
                    result = {
                        'generated_tags': task.final_tags,
                        'frames_analyzed': len(task.frames_base64),
                        'analysis_text': task.api_result.get('analysis', ''),
                        'error': task.api_error if task.api_error else None
                    }
                    progress_callback(idx, len(video_paths), task.video_path, result)
        
        self.pipeline_analyzer.progress_callback = pipeline_progress
        completed_tasks = self.pipeline_analyzer.analyze_videos(videos)
        
        results = []
        for task in completed_tasks:
            result = {
                'generated_tags': task.final_tags,
                'frames_analyzed': len(task.frames_base64),
                'analysis_text': task.api_result.get('analysis', ''),
                'error': task.api_error if task.api_error else None
            }
            results.append({'path': task.video_path, 'result': result})
        
        return results
