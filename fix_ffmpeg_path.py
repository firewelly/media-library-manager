#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修改media_library.py和media_library_pyside.py中的get_ffmpeg_command方法
使其在macOS下优先使用homebrew版本的ffmpeg
"""

import re

def modify_get_ffmpeg_command(file_path):
    """修改get_ffmpeg_command方法"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 查找get_ffmpeg_command方法
    pattern = r'(def get_ffmpeg_command\(self\):\s*\n\s*"""获取可用的FFmpeg命令路径""")'
    
    if re.search(pattern, content):
        # 替换方法
        new_method = '''def get_ffmpeg_command(self):
        """获取可用的FFmpeg命令路径，优先使用homebrew版本"""
        # macOS下优先使用homebrew版本的ffmpeg
        if platform.system() == 'Darwin':
            # 优先检查homebrew路径
            homebrew_ffmpeg = '/opt/homebrew/bin/ffmpeg'
            if os.path.exists(homebrew_ffmpeg):
                try:
                    subprocess.run([homebrew_ffmpeg, "-version"], capture_output=True, check=True)
                    return homebrew_ffmpeg
                except (subprocess.CalledProcessError, FileNotFoundError):
                    pass
        
        # 首先尝试相对路径（用户通过homebrew安装的情况）
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
            return "ffmpeg"
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
            
        # 如果相对路径失败，尝试常见的绝对路径
        possible_paths = [
            "/usr/local/bin/ffmpeg",
            "/usr/bin/ffmpeg"
        ]
        
        for path in possible_paths:
            try:
                subprocess.run([path, "-version"], capture_output=True, check=True)
                return path
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
                
        return None'''
        
        # 查找并替换整个方法
        old_method_pattern = r'def get_ffmpeg_command\(self\):\s*\n\s*"""获取可用的FFmpeg命令路径"""\s*\n\s*# 首先尝试相对路径.*?return None'
        
        content = re.sub(old_method_pattern, new_method, content, flags=re.DOTALL)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ 已修改 {file_path}")
        return True
    else:
        print(f"❌ 未找到get_ffmpeg_command方法: {file_path}")
        return False

if __name__ == "__main__":
    files = [
        "/Users/firewell/Library/CloudStorage/OneDrive-个人/bioinfo/media/media_library.py",
        "/Users/firewell/Library/CloudStorage/OneDrive-个人/bioinfo/media/media_library_pyside.py"
    ]
    
    for file_path in files:
        modify_get_ffmpeg_command(file_path)
