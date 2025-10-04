#!/usr/bin/env python3
"""
视频字幕提取工具
使用 MLX-Whisper 从视频中提取音频并生成SRT字幕文件
支持多种语言识别和翻译功能
"""

import os
import sys
import argparse
import subprocess
import tempfile
from pathlib import Path
import json
import re
from datetime import timedelta

def check_and_activate_venv():
    """检查并激活虚拟环境"""
    # 定义虚拟环境路径
    script_dir = Path(__file__).parent
    venv_path = script_dir / "mlx_whisper_env"
    
    # 检查是否已经在虚拟环境中
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("✅ 已在虚拟环境中运行")
        return True
    
    # 检查虚拟环境是否存在
    if not venv_path.exists():
        print(f"❌ 虚拟环境不存在: {venv_path}")
        print("请先创建虚拟环境:")
        print(f"python3 -m venv {venv_path}")
        print(f"source {venv_path}/bin/activate")
        print("pip install mlx-whisper")
        return False
    
    # 获取虚拟环境的Python路径
    venv_python = venv_path / "bin" / "python"
    if not venv_python.exists():
        print(f"❌ 虚拟环境Python不存在: {venv_python}")
        return False
    
    # 如果不在虚拟环境中，重新启动脚本使用虚拟环境的Python
    print(f"🔄 使用虚拟环境重新启动脚本: {venv_path}")
    
    # 构建新的命令行参数
    new_args = [str(venv_python)] + sys.argv
    
    # 使用虚拟环境的Python重新执行脚本
    try:
        result = subprocess.run(new_args, check=False)
        sys.exit(result.returncode)
    except Exception as e:
        print(f"❌ 启动虚拟环境失败: {e}")
        return False

def check_dependencies():
    """检查必要的依赖是否安装"""
    dependencies = {
        'mlx_whisper': 'mlx-whisper',
        'ffmpeg': 'ffmpeg'
    }
    
    missing = []
    
    # 检查 mlx-whisper
    try:
        import mlx_whisper
        print("✅ mlx-whisper 已安装")
    except ImportError:
        missing.append('mlx-whisper')
        print("❌ mlx-whisper 未安装")
    
    # 检查 ffmpeg
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("✅ ffmpeg 已安装")
        else:
            missing.append('ffmpeg')
            print("❌ ffmpeg 未安装")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        missing.append('ffmpeg')
        print("❌ ffmpeg 未安装或无法访问")
    
    if missing:
        print(f"\n缺少依赖: {', '.join(missing)}")
        print("请运行以下命令安装:")
        if 'mlx-whisper' in missing:
            print("  pip install mlx-whisper")
        if 'ffmpeg' in missing:
            print("  brew install ffmpeg  # macOS")
        return False
    
    return True

def extract_audio(video_path: str, audio_path: str) -> bool:
    """从视频文件中提取音频"""
    try:
        print(f"正在从视频中提取音频: {os.path.basename(video_path)}")
        
        # 使用ffmpeg提取音频为wav格式
        cmd = [
            'ffmpeg', '-i', video_path,
            '-vn',  # 不包含视频
            '-acodec', 'pcm_s16le',  # 16位PCM编码
            '-ar', '16000',  # 16kHz采样率
            '-ac', '1',  # 单声道
            '-y',  # 覆盖输出文件
            audio_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ 音频提取成功: {audio_path}")
            return True
        else:
            print(f"❌ 音频提取失败: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ 音频提取异常: {e}")
        return False

def transcribe_audio(audio_path: str, language: str = "auto", model_path: str = None) -> dict:
    """使用mlx-whisper转录音频"""
    try:
        import mlx_whisper
        
        # 设置模型路径
        if model_path is None:
            model_path = "/Users/firewell/.lmstudio/models/mlx-community/whisper-large-v3-turbo"
        
        print(f"正在使用 MLX-Whisper 转录音频...")
        print(f"模型路径: {model_path}")
        print(f"语言设置: {language}")
        
        # 检查模型路径是否存在
        if not os.path.exists(model_path):
            print(f"⚠️  模型路径不存在: {model_path}")
            print("使用默认模型...")
            model_path = "mlx-community/whisper-large-v3-turbo"
        
        # 设置转录参数
        if language == "auto":
            # 自动检测语言
            result = mlx_whisper.transcribe(
                audio_path,
                path_or_hf_repo=model_path,
                language=None,  # 自动检测
                task="transcribe",
                verbose=True,
                word_timestamps=True
            )
        else:
            # 指定语言
            result = mlx_whisper.transcribe(
                audio_path,
                path_or_hf_repo=model_path,
                language=language,
                task="transcribe", 
                verbose=True,
                word_timestamps=True
            )
        
        print(f"✅ 转录完成，检测到语言: {result.get('language', 'unknown')}")
        return result
        
    except Exception as e:
        print(f"❌ 转录失败: {e}")
        return {}

def format_timestamp(seconds: float) -> str:
    """将秒数转换为SRT时间格式 (HH:MM:SS,mmm)"""
    td = timedelta(seconds=seconds)
    hours = int(td.total_seconds() // 3600)
    minutes = int((td.total_seconds() % 3600) // 60)
    seconds = td.total_seconds() % 60
    milliseconds = int((seconds % 1) * 1000)
    seconds = int(seconds)
    
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

def translate_to_chinese(text: str, detected_language: str) -> str:
    """简单的文本翻译处理（这里可以集成翻译API）"""
    # 如果检测到的是中文，直接返回
    if detected_language in ['zh', 'chinese']:
        return text
    
    # 对于日文，这里可以集成翻译服务
    # 目前先返回原文，用户可以根据需要集成翻译API
    if detected_language in ['ja', 'japanese']:
        # TODO: 集成翻译API (如Google Translate, DeepL等)
        print(f"检测到日文，原文: {text}")
        return f"[日文] {text}"
    
    return text

def filter_meaningless_content(text: str) -> bool:
    """过滤无意义的重复内容"""
    if not text or len(text.strip()) == 0:
        return False
    
    text = text.strip()
    
    # 检查是否为单个字符或词的大量重复
    words = text.split()
    if len(words) > 5:  # 如果有超过5个词
        # 检查是否大部分都是相同的词
        word_counts = {}
        for word in words:
            word_counts[word] = word_counts.get(word, 0) + 1
        
        # 如果某个词出现次数超过总词数的70%，认为是重复内容
        max_count = max(word_counts.values())
        if max_count / len(words) > 0.7:
            return False
    
    # 检查是否为单个字符的重复（如 "об об об" 或 "可可可"）
    if len(text) > 10:
        # 检查是否主要由重复的短字符串组成
        for i in range(1, min(6, len(text) // 3)):  # 检查1-5个字符的重复模式
            pattern = text[:i]
            if text.replace(pattern, '').replace(' ', '') == '':
                return False
    
    # 检查是否为单个英文单词的重复（如 "Remember Remember Remember"）
    if len(words) > 3:
        unique_words = set(words)
        if len(unique_words) == 1:  # 所有词都相同
            return False
        elif len(unique_words) <= 2 and len(words) > 6:  # 只有1-2个不同的词但重复很多次
            return False
    
    # 检查是否为过短的内容（少于2个字符）
    if len(text.replace(' ', '')) < 2:
        return False
    
    return True

def generate_srt(transcription_result: dict, output_path: str, translate: bool = True) -> bool:
    """生成SRT字幕文件"""
    try:
        if not transcription_result or 'segments' not in transcription_result:
            print("❌ 转录结果为空或格式错误")
            return False
        
        detected_language = transcription_result.get('language', 'unknown')
        segments = transcription_result['segments']
        
        print(f"正在生成SRT字幕文件: {output_path}")
        print(f"共 {len(segments)} 个片段")
        
        filtered_count = 0
        segment_number = 1
        
        with open(output_path, 'w', encoding='utf-8') as f:
            for segment in segments:
                start_time = format_timestamp(segment['start'])
                end_time = format_timestamp(segment['end'])
                text = segment['text'].strip()
                
                if not text:
                    continue
                
                # 过滤无意义的重复内容
                if not filter_meaningless_content(text):
                    filtered_count += 1
                    continue
                
                # 如果需要翻译且不是中文
                if translate and detected_language not in ['zh', 'chinese']:
                    text = translate_to_chinese(text, detected_language)
                
                # 写入SRT格式
                f.write(f"{segment_number}\n")
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{text}\n\n")
                segment_number += 1
        
        print(f"✅ SRT字幕文件生成成功: {output_path}")
        print(f"📊 总共生成 {segment_number - 1} 个字幕片段")
        if filtered_count > 0:
            print(f"🧹 已过滤 {filtered_count} 个无意义的重复片段")
        return True
        
    except Exception as e:
        print(f"❌ SRT生成失败: {e}")
        return False

def main():
    # 首先检查并激活虚拟环境
    if not check_and_activate_venv():
        sys.exit(1)
    
    parser = argparse.ArgumentParser(description='MLX-Whisper 视频字幕提取工具')
    parser.add_argument('video_path', help='输入视频文件路径')
    parser.add_argument('-o', '--output', help='输出SRT文件路径（可选）')
    parser.add_argument('-l', '--language', default='auto', 
                       choices=['auto', 'zh', 'ja', 'en'],
                       help='音频语言 (auto=自动检测, zh=中文, ja=日文, en=英文)')
    parser.add_argument('--no-translate', action='store_true',
                       help='不翻译为中文，保持原文')
    parser.add_argument('--keep-audio', action='store_true',
                       help='保留提取的音频文件')
    parser.add_argument('--model-path', 
                       default="/Users/firewell/.lmstudio/models/mlx-community/whisper-large-v3-turbo",
                       help='Whisper模型路径')
    
    args = parser.parse_args()
    
    # 检查依赖
    if not check_dependencies():
        sys.exit(1)
    
    # 检查输入文件
    video_path = args.video_path
    if not os.path.exists(video_path):
        print(f"❌ 视频文件不存在: {video_path}")
        sys.exit(1)
    
    # 设置输出路径
    if args.output:
        srt_path = args.output
    else:
        video_name = Path(video_path).stem
        srt_path = f"{video_name}_subtitles.srt"
    
    print(f"🎬 输入视频: {video_path}")
    print(f"📝 输出字幕: {srt_path}")
    print(f"🌐 语言设置: {args.language}")
    print(f"🔄 翻译设置: {'关闭' if args.no_translate else '开启'}")
    print("-" * 50)
    
    # 创建临时音频文件
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_audio:
        audio_path = temp_audio.name
    
    try:
        # 步骤1: 提取音频
        if not extract_audio(video_path, audio_path):
            sys.exit(1)
        
        # 步骤2: 转录音频
        language = None if args.language == 'auto' else args.language
        transcription = transcribe_audio(audio_path, language, args.model_path)
        
        if not transcription:
            print("❌ 转录失败")
            sys.exit(1)
        
        # 步骤3: 生成SRT字幕
        translate = not args.no_translate
        if generate_srt(transcription, srt_path, translate):
            print(f"\n🎉 字幕提取完成!")
            print(f"📁 字幕文件: {srt_path}")
            
            # 显示统计信息
            if 'segments' in transcription:
                duration = transcription.get('duration', 0)
                segments_count = len(transcription['segments'])
                detected_lang = transcription.get('language', 'unknown')
                
                print(f"⏱️  视频时长: {duration:.1f}秒")
                print(f"📊 字幕片段: {segments_count}个")
                print(f"🌍 检测语言: {detected_lang}")
        else:
            sys.exit(1)
            
    finally:
        # 清理临时文件
        if os.path.exists(audio_path) and not args.keep_audio:
            os.unlink(audio_path)
            print(f"🗑️  已删除临时音频文件")
        elif args.keep_audio:
            audio_output = f"{Path(video_path).stem}_audio.wav"
            os.rename(audio_path, audio_output)
            print(f"💾 音频文件已保存: {audio_output}")

if __name__ == "__main__":
    main()