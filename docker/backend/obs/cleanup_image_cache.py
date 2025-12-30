#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理本地图片缓存脚本
删除results/images目录中的所有图片文件
"""

import os
import shutil
from pathlib import Path

def cleanup_image_cache():
    """清理本地图片缓存"""
    images_dir = Path('results/images')
    
    if not images_dir.exists():
        print("图片缓存目录不存在")
        return
    
    try:
        # 获取目录中的所有文件
        files = list(images_dir.glob('*'))
        
        if not files:
            print("图片缓存目录为空")
            return
        
        print(f"找到 {len(files)} 个缓存文件")
        
        # 删除所有文件
        for file_path in files:
            if file_path.is_file():
                try:
                    file_path.unlink()
                    print(f"已删除: {file_path.name}")
                except Exception as e:
                    print(f"删除失败 {file_path.name}: {e}")
        
        print("\n图片缓存清理完成！")
        
    except Exception as e:
        print(f"清理图片缓存时出错: {e}")

if __name__ == "__main__":
    print("开始清理图片缓存...")
    cleanup_image_cache()