#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多人脸头像提取工具使用示例
"""

import os
from pathlib import Path
from multi_person_face_extractor import MultiPersonFaceExtractor


def main():
    print("=== 多人脸头像提取工具使用示例 ===\n")
    
    # 设置输入和输出目录
    input_dir = "images"
    output_dir = "output_multi_example"
    
    # 方法1: 使用类实例处理单个文件
    print("方法1: 处理单个文件")
    
    # 获取images目录中的第一个文件作为示例
    image_files = [f for f in Path(input_dir).glob("*") 
                  if f.suffix.lower() in ['.jpg', '.jpeg', '.png', '.bmp', '.gif']]
    
    if image_files:
        sample_file = image_files[0]
        print(f"正在处理示例文件: {sample_file.name}")
        
        # 创建提取器实例
        extractor = MultiPersonFaceExtractor(input_dir, output_dir)
        
        # 处理单个文件
        extractor.process_single_file(str(sample_file))
        print()
    else:
        print(f"警告: 在{input_dir}目录中未找到图片文件\n")
    
    # 方法2: 使用命令行参数方式处理所有文件
    print("方法2: 处理所有文件")
    print("以下是如何通过命令行调用多人脸头像提取工具的示例:")
    print("\n# 处理所有文件")
    print(f"python3 multi_person_face_extractor.py --input {input_dir} --output {output_dir}")
    
    print("\n# 处理单个文件")
    if image_files:
        print(f"python3 multi_person_face_extractor.py --file {image_files[0]} --output {output_dir}")
    
    print("\n# 调整人脸相似度阈值")
    print(f"python3 multi_person_face_extractor.py --input {input_dir} --output {output_dir} --threshold 0.7")
    
    print("\n# 获取帮助信息")
    print("python3 multi_person_face_extractor.py --help")
    
    print("\n=== 注意事项 ===")
    print("1. 该工具会检测并提取图片中的所有正面人脸")
    print("2. 通过人脸相似度聚类算法区分不同的人物")
    print("3. 对于同一个人物的多张脸，只保留质量最高的一张")
    print("4. 提取的头像会保存为128x128像素的图片")
    print("5. 输出文件名格式: [原始文件名]_person_[编号]_face.jpg")
    

if __name__ == "__main__":
    main()