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
