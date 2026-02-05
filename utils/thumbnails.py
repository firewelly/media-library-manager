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
        try:
            from utils.runtime import runtime_path
            bundled = runtime_path('tools', 'ffmpeg.exe')
            if os.path.exists(bundled):
                return bundled
        except Exception:
            pass
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
    def detect_gpu_acceleration() -> dict:
        """检测GPU加速可用性，返回支持的硬件加速器列表"""
        ffmpeg = ThumbnailGenerator.get_ffmpeg_command()
        if not ffmpeg:
            return {"available": False, "hwaccel": None, "decoder": None, "encoder": None}
        
        result = {
            "available": False,
            "hwaccel": None,
            "decoder": None,
            "encoder": None,
            "gpu_type": None
        }
        
        try:
            # 获取FFmpeg支持的硬件加速器
            cmd_result = subprocess.run([ffmpeg, "-hwaccels"], capture_output=True, text=True, timeout=5)
            if cmd_result.returncode != 0:
                return result
            
            hwaccels = cmd_result.stdout.lower()
            system = platform.system()
            
            # 检测支持的硬件加速器并选择最佳选项
            if system == 'Darwin':
                # macOS: VideoToolbox是原生硬件加速
                if 'videotoolbox' in hwaccels:
                    result.update({
                        "available": True,
                        "hwaccel": "videotoolbox",
                        "decoder": "h264_videotoolbox",
                        "encoder": "h264_videotoolbox",
                        "gpu_type": "Apple Silicon / Intel"
                    })
                elif 'opencl' in hwaccels:
                    result.update({
                        "available": True,
                        "hwaccel": "opencl",
                        "decoder": None,
                        "encoder": None,
                        "gpu_type": "OpenCL"
                    })
            
            elif system == 'Windows':
                # Windows: 按优先级检测硬件加速器
                # 注意：对于AMD集成显卡，优先选择D3D11VA
                
                # 1. D3D11VA (DirectX 11 - 包括AMD GPU，推荐用于集成显卡)
                if 'd3d11va' in hwaccels:
                    result.update({
                        "available": True,
                        "hwaccel": "d3d11va",
                        "decoder": "h264_dxva2",
                        "encoder": "h264_qsv",  # Intel编码器备用
                        "gpu_type": "AMD / DirectX 11"
                    })
                # 2. Intel QSV (Intel集成显卡)
                elif 'qsv' in hwaccels:
                    result.update({
                        "available": True,
                        "hwaccel": "qsv",
                        "decoder": "h264_qsv",
                        "encoder": "h264_qsv",
                        "gpu_type": "Intel"
                    })
                # 3. DXVA2 (DirectX 9 - 旧版Windows)
                elif 'dxva2' in hwaccels:
                    result.update({
                        "available": True,
                        "hwaccel": "dxva2",
                        "decoder": "h264_dxva2",
                        "encoder": None,
                        "gpu_type": "DirectX 9"
                    })
                # 4. NVIDIA CUDA (仅当有实际NVIDIA GPU时验证)
                elif 'cuda' in hwaccels:
                    # 验证CUDA是否实际可用
                    try:
                        test_cmd = [ffmpeg, "-hwaccel", "cuda", "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=1", "-f", "null", "-"]
                        test_result = subprocess.run(test_cmd, capture_output=True, timeout=5)
                        if test_result.returncode == 0:
                            result.update({
                                "available": True,
                                "hwaccel": "cuda",
                                "decoder": "h264_cuvid",
                                "encoder": "h264_nvenc",
                                "gpu_type": "NVIDIA"
                            })
                    except:
                        pass
            
            elif system == 'Linux':
                # Linux: 按优先级检测硬件加速器
                
                # 1. VA-API (Video Acceleration API - 适用于AMD/Intel GPU)
                if 'vaapi' in hwaccels:
                    result.update({
                        "available": True,
                        "hwaccel": "vaapi",
                        "decoder": "h264_vaapi",
                        "encoder": "h264_vaapi",
                        "gpu_type": "AMD / Intel (VA-API)"
                    })
                # 2. Intel QSV
                elif 'qsv' in hwaccels:
                    result.update({
                        "available": True,
                        "hwaccel": "qsv",
                        "decoder": "h264_qsv",
                        "encoder": "h264_qsv",
                        "gpu_type": "Intel"
                    })
                # 3. NVIDIA CUDA (验证实际可用性)
                elif 'cuda' in hwaccels:
                    try:
                        test_cmd = [ffmpeg, "-hwaccel", "cuda", "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=1", "-f", "null", "-"]
                        test_result = subprocess.run(test_cmd, capture_output=True, timeout=5)
                        if test_result.returncode == 0:
                            result.update({
                                "available": True,
                                "hwaccel": "cuda",
                                "decoder": "h264_cuvid",
                                "encoder": "h264_nvenc",
                                "gpu_type": "NVIDIA"
                            })
                    except:
                        pass
                # 4. VDPAU (NVIDIA旧驱动)
                elif 'vdpau' in hwaccels:
                    result.update({
                        "available": True,
                        "hwaccel": "vdpau",
                        "decoder": "h264_vdpau",
                        "encoder": None,
                        "gpu_type": "NVIDIA (VDPAU)"
                    })
                # 5. OpenCL (通用跨平台)
                elif 'opencl' in hwaccels:
                    result.update({
                        "available": True,
                        "hwaccel": "opencl",
                        "decoder": None,
                        "encoder": None,
                        "gpu_type": "OpenCL"
                    })
            
        except Exception as e:
            print(f"检测GPU加速失败: {e}")
        
        return result

    @staticmethod
    def generate_thumbnail(video_path: str, output_path: str, seek_time: str = "00:00:10") -> bool:
        """生成视频缩略图，使用GPU硬件加速"""
        ffmpeg = ThumbnailGenerator.get_ffmpeg_command()
        if not ffmpeg:
            return False

        try:
            # 确保输出目录存在
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            
            cmd = [ffmpeg, "-y"]
            
            # 获取GPU加速信息
            gpu_info = ThumbnailGenerator.detect_gpu_acceleration()
            
            # 如果有硬件加速支持，添加硬件加速参数
            if gpu_info["available"] and gpu_info["hwaccel"]:
                cmd.extend(["-hwaccel", gpu_info["hwaccel"]])
                
                # 对于某些GPU（如VA-API、QSV），需要指定设备
                if gpu_info["hwaccel"] in ["vaapi", "qsv"]:
                    # 自动检测VAAPI设备
                    if gpu_info["hwaccel"] == "vaapi":
                        try:
                            # 尝试找到DRM设备
                            dri_path = "/dev/dri/renderD128"
                            if os.path.exists(dri_path):
                                cmd.extend(["-hwaccel_device", dri_path])
                        except:
                            pass
            
            # 寻求时间点 (放在-i之前为输入寻求，速度快)
            cmd.extend(["-ss", seek_time])
            
            # 输入文件
            cmd.extend(["-i", video_path])
            
            # 如果有硬件解码器，使用它（但缩略图生成通常不需要，因为只是截图一帧）
            # 对于缩略图生成，我们主要是为了快速定位到指定时间点
            
            # 截图一帧
            cmd.extend(["-vframes", "1"])
            
            # 输出格式优化
            cmd.extend(["-f", "image2"])
            
            # 输出路径
            cmd.append(output_path)
            
            # 执行命令
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
            
            return os.path.exists(output_path) and os.path.getsize(output_path) > 0
            
        except subprocess.CalledProcessError:
            return False
        except subprocess.TimeoutExpired:
            # 超时可能是因为硬件解码有问题，尝试不使用硬件加速重试
            try:
                cmd = [ffmpeg, "-y", "-ss", seek_time, "-i", video_path, "-vframes", "1", "-f", "image2", output_path]
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
                return os.path.exists(output_path) and os.path.getsize(output_path) > 0
            except:
                return False
        except Exception:
            return False
