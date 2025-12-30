import os
import subprocess
import shutil
import platform
from typing import Optional

class ThumbnailGenerator:
    """缩略图生成器"""
    
    @staticmethod
    def get_ffmpeg_command() -> Optional[str]:
        """获取系统中的FFmpeg命令路径，优先使用homebrew版本"""
        # macOS下优先使用homebrew版本的ffmpeg
        if platform.system() == 'Darwin':
            # 优先检查homebrew路径
            homebrew_ffmpeg = '/opt/homebrew/bin/ffmpeg'
            if os.path.exists(homebrew_ffmpeg):
                return homebrew_ffmpeg
        
        # 常见路径检查
        common_paths = [
            'ffmpeg',  # PATH
            '/usr/local/bin/ffmpeg',
            'C:\\ffmpeg\\bin\\ffmpeg.exe',
            'C:\\Program Files\\ffmpeg\\bin\\ffmpeg.exe'
        ]
        
        for path in common_paths:
            full_path = shutil.which(path)
            if full_path:
                return full_path
        return None

    @staticmethod
    def detect_gpu_acceleration() -> Optional[str]:
        """检测GPU加速可用性"""
        system = platform.system()
        if system == 'Darwin':
            # macOS通常支持videotoolbox
            return 'videotoolbox'
        elif system == 'Windows':
            # 简单假设，实际可能需要更复杂的检测
            return 'd3d11va' 
        return None

    @staticmethod
    def generate_thumbnail(video_path: str, output_path: str, seek_time: str = "00:00:10") -> bool:
        """生成视频缩略图"""
        ffmpeg = ThumbnailGenerator.get_ffmpeg_command()
        if not ffmpeg:
            return False

        try:
            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            cmd = [ffmpeg, "-y"]
            
            # 硬件加速参数
            hwaccel = ThumbnailGenerator.detect_gpu_acceleration()
            if hwaccel == 'videotoolbox':
                 cmd.extend(["-hwaccel", "videotoolbox"])
            
            # 寻求时间点 (放在-i之前为输入寻求，速度快)
            cmd.extend(["-ss", seek_time])
            
            # 输入文件
            cmd.extend(["-i", video_path])
            
            # 截图一帧
            cmd.extend(["-vframes", "1"])
            
            # 输出格式优化
            cmd.extend(["-f", "image2"])
            
            # 输出路径
            cmd.append(output_path)
            
            # 执行命令
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            return os.path.exists(output_path) and os.path.getsize(output_path) > 0
            
        except subprocess.CalledProcessError:
            return False
        except Exception:
            return False
