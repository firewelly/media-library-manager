#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频旋转工具模块
提供视频顺时针旋转功能
"""

import os
import shutil
import subprocess
import tempfile
import time
from .logger import get_logger

logger = get_logger("VideoRotate")

import re
import platform
import threading

def get_ffmpeg_command():
    """获取可用的FFmpeg命令路径，优先使用homebrew版本"""
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
    
    # 检查系统PATH中的ffmpeg
    if shutil.which('ffmpeg'):
        return 'ffmpeg'
    
    # 检查其他常见路径
    common_paths = [
        '/usr/local/bin/ffmpeg',
        '/usr/bin/ffmpeg',
    ]
    
    for path in common_paths:
        if os.path.exists(path):
            return path
    
    return None

def detect_gpu_acceleration():
    """检测GPU硬件编码支持"""
    ffmpeg_cmd = get_ffmpeg_command()
    if not ffmpeg_cmd:
        return {"available": False, "decoder": None, "encoder": None, "gpu_type": None}

    result = {
        "available": False,
        "decoder": None,
        "encoder": None,
        "gpu_type": None
    }

    try:
        # 获取FFmpeg支持的编码器
        cmd_result = subprocess.run([ffmpeg_cmd, "-encoders"], capture_output=True, text=True, timeout=5)
        if cmd_result.returncode != 0:
            return result

        encoders = cmd_result.stdout.lower()
        system = platform.system()

        # 检测支持的硬件编码器并选择最佳选项
        if system == 'Darwin':
            # macOS: VideoToolbox是原生硬件编码器
            if 'h264_videotoolbox' in encoders:
                result.update({
                    "available": True,
                    "encoder": "h264_videotoolbox",
                    "gpu_type": "Apple Silicon / Intel"
                })

        elif system == 'Windows':
            # Windows: 按优先级检测硬件编码器
            # 对于AMD集成显卡，优先考虑AMF编码器

            # 1. AMD AMF (AMD GPU)
            if 'h264_amf' in encoders:
                result.update({
                    "available": True,
                    "encoder": "h264_amf",
                    "gpu_type": "AMD"
                })
            # 2. Intel QSV (Intel GPU)
            elif 'h264_qsv' in encoders:
                result.update({
                    "available": True,
                    "encoder": "h264_qsv",
                    "gpu_type": "Intel"
                })
            # 3. NVIDIA NVENC (NVIDIA GPU) - 仅当实际可用时
            elif 'h264_nvenc' in encoders:
                # 验证NVENC是否实际可用
                try:
                    test_cmd = [ffmpeg_cmd, "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=1",
                                "-c:v", "h264_nvenc", "-f", "null", "-"]
                    test_result = subprocess.run(test_cmd, capture_output=True, timeout=5)
                    if test_result.returncode == 0:
                        result.update({
                            "available": True,
                            "encoder": "h264_nvenc",
                            "gpu_type": "NVIDIA"
                        })
                except:
                    pass

        elif system == 'Linux':
            # Linux: 按优先级检测硬件编码器

            # 1. VAAPI (Video Acceleration API - AMD/Intel GPU)
            if 'h264_vaapi' in encoders:
                result.update({
                    "available": True,
                    "encoder": "h264_vaapi",
                    "gpu_type": "AMD / Intel (VAAPI)"
                })
            # 2. Intel QSV
            elif 'h264_qsv' in encoders:
                result.update({
                    "available": True,
                    "encoder": "h264_qsv",
                    "gpu_type": "Intel"
                })
            # 3. NVIDIA NVENC - 仅当实际可用时
            elif 'h264_nvenc' in encoders:
                try:
                    test_cmd = [ffmpeg_cmd, "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=1",
                                "-c:v", "h264_nvenc", "-f", "null", "-"]
                    test_result = subprocess.run(test_cmd, capture_output=True, timeout=5)
                    if test_result.returncode == 0:
                        result.update({
                            "available": True,
                            "encoder": "h264_nvenc",
                            "gpu_type": "NVIDIA"
                        })
                except:
                    pass

    except Exception as e:
        logger.error(f"检测GPU编码器失败: {e}")

    return result

def get_video_duration_seconds(file_path):
    """获取视频时长（秒）"""
    try:
        ffmpeg_cmd = get_ffmpeg_command()
        if not ffmpeg_cmd:
            return 0.0
            
        cmd = [
            ffmpeg_cmd.replace('ffmpeg', 'ffprobe'), 
            '-v', 'error', 
            '-show_entries', 'format=duration', 
            '-of', 'default=noprint_wrappers=1:nokey=1', 
            file_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return float(result.stdout.strip())
    except Exception:
        return 0.0

def parse_time_str(time_str):
    """解析 ffmpeg 时间字符串 HH:MM:SS.ms 为秒数"""
    try:
        parts = time_str.split(':')
        if len(parts) == 3:
            h = float(parts[0])
            m = float(parts[1])
            s = float(parts[2])
            return h * 3600 + m * 60 + s
    except Exception:
        pass
    return 0.0

import platform
import threading

def rotate_video(file_path, degrees, progress_callback=None):
    """
    旋转视频文件
    
    参数:
        file_path: 视频文件路径
        degrees: 旋转角度 (90, 180, 270) - 顺时针
        progress_callback: 进度回调函数 callback(progress_percent, message)
        
    返回:
        tuple: (success, message)
    """
    if not os.path.exists(file_path):
        return False, f"文件不存在: {file_path}"
        
    if degrees not in [90, 180, 270]:
        return False, f"不支持的旋转角度: {degrees}，仅支持 90, 180, 270"
        
    # 获取ffmpeg命令
    ffmpeg_cmd = get_ffmpeg_command()
    if not ffmpeg_cmd:
        return False, "未找到FFmpeg，请安装FFmpeg\nmacOS: brew install ffmpeg"
        
    try:
        # 获取视频总时长，用于计算进度
        total_duration = get_video_duration_seconds(file_path)
        
        # 构建ffmpeg滤镜参数
        transpose_filter = ""
        if degrees == 90:
            transpose_filter = "transpose=1"
        elif degrees == 180:
            transpose_filter = "transpose=1,transpose=1"
        elif degrees == 270:
            transpose_filter = "transpose=2"
            
        # 创建临时输出文件
        directory = os.path.dirname(file_path)
        filename = os.path.basename(file_path)
        name, ext = os.path.splitext(filename)
        
        # 使用临时文件
        fd, temp_output_path = tempfile.mkstemp(suffix=ext, dir=directory)
        os.close(fd)
        
        # 构建ffmpeg命令
        # 根据系统环境选择编码器
        system = platform.system()
        
        # 检测GPU硬件编码支持
        gpu_info = detect_gpu_acceleration()
        
        cmd = [ffmpeg_cmd, '-y', '-i', file_path, '-vf', transpose_filter]
        
        # 根据GPU类型选择合适的硬件编码器
        if gpu_info["available"] and gpu_info["encoder"]:
            encoder = gpu_info["encoder"]
            gpu_type = gpu_info["gpu_type"]
            
            if encoder == 'h264_videotoolbox':
                # macOS VideoToolbox: 质量控制 -q:v (1-100)
                cmd.extend(['-c:v', 'h264_videotoolbox', '-q:v', '60'])
                logger.info(f"使用硬件编码: {gpu_type} ({encoder})")
            
            elif encoder == 'h264_nvenc':
                # NVIDIA NVENC: 质量控制 -cq (0-51, 值越小质量越高)
                cmd.extend(['-c:v', 'h264_nvenc', '-cq', '23', '-preset', 'p4'])
                logger.info(f"使用硬件编码: {gpu_type} ({encoder})")
            
            elif encoder == 'h264_qsv':
                # Intel QSV: 质量控制 -global_quality (1-51, 值越小质量越高)
                cmd.extend(['-c:v', 'h264_qsv', '-global_quality', '23', '-preset', 'medium'])
                logger.info(f"使用硬件编码: {gpu_type} ({encoder})")
            
            elif encoder == 'h264_amf':
                # AMD AMF: 质量控制 -quality (speed, balanced, quality)
                cmd.extend(['-c:v', 'h264_amf', '-quality', 'quality', '-rc', 'cqp', '-qp_i', '23', '-qp_p', '23'])
                logger.info(f"使用硬件编码: {gpu_type} ({encoder})")
            
            elif encoder == 'h264_vaapi':
                # Linux VAAPI: 质量控制 -qp_v (1-51)
                # VAAPI需要指定设备
                dri_path = '/dev/dri/renderD128'
                if os.path.exists(dri_path):
                    cmd.extend(['-vaapi_device', dri_path])
                # 添加像素格式转换（VAAPI需要）
                cmd.extend(['-vf', f'{transpose_filter},format=nv12,hwupload'])
                cmd.extend(['-c:v', 'h264_vaapi', '-qp_v', '23'])
                logger.info(f"使用硬件编码: {gpu_type} ({encoder})")
        else:
            # 没有硬件编码器，使用软件编码
            if system == 'Darwin':
                # macOS默认不使用硬件编码
                cmd.extend(['-c:v', 'libx264', '-preset', 'medium', '-crf', '23'])
            else:
                # Windows/Linux使用通用h264编码器
                cmd.extend(['-c:v', 'h264'])
            logger.info("使用软件编码 (libx264/h264)")
            
        # 通用参数
        cmd.extend([
            '-c:a', 'copy',
            '-metadata:s:v:0', 'rotate=0',
            temp_output_path
        ])
        
        logger.info(f"开始旋转视频: {file_path}, 角度: {degrees}")
        logger.debug(f"执行命令: {' '.join(cmd)}")
        
        # 执行命令
        # 注意：将stdout重定向到DEVNULL，防止缓冲区满导致死锁
        # 我们只从stderr读取进度信息
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            encoding='utf-8',
            errors='replace'
        )
        
        stderr_log = []
        
        def read_stderr(pipe, log_list):
            for line in pipe:
                if line:
                    log_list.append(line.strip())
                    if len(log_list) > 50:
                        log_list.pop(0)
                        
                    # 解析时间进度: time=00:00:05.12
                    if "time=" in line:
                        try:
                            time_match = re.search(r'time=(\d{2}:\d{2}:\d{2}\.\d+)', line)
                            if time_match:
                                current_time_str = time_match.group(1)
                                current_seconds = parse_time_str(current_time_str)
                                
                                if total_duration > 0:
                                    percent = min(99, int((current_seconds / total_duration) * 100))
                                    if progress_callback:
                                        progress_callback(percent, f"正在转码: {percent}%")
                                else:
                                    # 如果无法获取总时长，只显示当前时间
                                    if progress_callback:
                                        progress_callback(50, f"正在转码: {current_time_str}")
                        except Exception:
                            pass
        
        # 使用线程读取stderr
        reader_thread = threading.Thread(target=read_stderr, args=(process.stderr, stderr_log))
        reader_thread.daemon = True
        reader_thread.start()
        
        # 初始回调
        if progress_callback:
            progress_callback(0, "正在启动转码引擎...")

        # 等待进程结束
        while reader_thread.is_alive():
            reader_thread.join(0.5)
            if process.poll() is not None:
                break
                
        # 确保进程已退出
        process.wait()
            
        # 检查返回码
        if process.returncode != 0:
            error_msg = "\n".join(stderr_log[-10:]) if stderr_log else "无错误日志"
            if os.path.exists(temp_output_path):
                os.remove(temp_output_path)
            return False, f"转码失败 (code {process.returncode}): {error_msg}"
            
        # 转码成功，替换原文件
        backup_path = file_path + ".bak"
        shutil.move(file_path, backup_path)
        
        try:
            shutil.move(temp_output_path, file_path)
            os.remove(backup_path)
            logger.info(f"视频旋转完成: {file_path}")
            return True, "视频旋转成功"
        except Exception as e:
            if os.path.exists(backup_path):
                shutil.move(backup_path, file_path)
            logger.error(f"替换文件失败: {e}")
            return False, f"替换文件失败: {e}"
            
    except Exception as e:
        logger.error(f"视频旋转异常: {e}")
        return False, str(e)
