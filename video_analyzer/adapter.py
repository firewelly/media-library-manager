import re
import os
from typing import List, Dict, Any
from .video_analyzer_siliconflow_glm_with_tags import VideoAnalyzerSiliconFlowGLMWithTags

class VideoContentAnalyzer:
    def __init__(self, db_path="media_library.db"):
        self.db_path = db_path
        # Initialize the underlying analyzer
        # API key is retrieved from environment variables by the core class
        self.analyzer = VideoAnalyzerSiliconFlowGLMWithTags(verbose=True)

    def analyze_video_content(self, video_path, min_frames=100, max_interval=10, max_frames=300):
        """
        Analyze video content and return tags.
        Arguments min_frames, max_interval, max_frames are kept for compatibility 
        but are largely ignored in favor of the new model's optimal settings (20 frames).
        """
        try:
            # The new analyzer logic uses fewer frames (e.g. 20) and LLM
            # We ignore the old frame parameters to avoid excessive token usage/latency
            # and stick to the production script's default of 20 frames
            result = self.analyzer.analyze_video(video_path, num_frames=20)
            
            if not result.get('success', False):
                return {'error': result.get('error', 'Unknown error')}
            
            analysis_text = result.get('analysis', '')
            generated_tags = self._extract_tags_from_analysis(analysis_text)
            
            return {
                'generated_tags': generated_tags,
                'frames_analyzed': result.get('frames_extracted', 0),
                'analysis_text': analysis_text,
                'summary': {'generated_tags': generated_tags} # For compatibility if needed
            }
        except Exception as e:
            return {'error': str(e)}

    def _extract_tags_from_analysis(self, analysis_text: str) -> List[str]:
        """
        Extract tags from analysis text.
        Logic adapted from production_video_analyzer_fixed.py
        """
        if not analysis_text:
            return []
        
        # 查找匹配标签部分
        match = re.search(r'匹配标签[：:]\s*([^\n]+)', analysis_text)
        if match:
            tags_text = match.group(1).strip()
            # 清理标签文本
            tags_text = re.sub(r'[\n\r\t]', '', tags_text)
            tags_text = tags_text.replace('、', ',').replace('，', ',')
            # 分割标签并清理空白
            tags = [tag.strip() for tag in tags_text.split(',') if tag.strip()]
            return tags
        
        return []
