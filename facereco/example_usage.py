#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
头像提取API使用示例
"""

from face_extractor_api import FaceExtractorAPI, extract_face_from_url, extract_face_from_file
import os

def main():
    print("=== 头像提取API使用示例 ===\n")
    
    # 方法1: 使用类实例
    print("方法1: 使用FaceExtractorAPI类")
    extractor = FaceExtractorAPI("output_api")
    
    # 从本地文件提取头像
    local_image_path = "images/ABP-246_ABP-246 僅限此片無套中出 彩美旬果 顯示原標題.jpg"
    if os.path.exists(local_image_path):
        print(f"正在从本地文件提取头像: {local_image_path}")
        success = extractor.extract_face_from_file(
            local_image_path, 
            "avatar_from_local.jpg"
        )
        if success:
            print("✓ 本地文件头像提取成功\n")
        else:
            print("✗ 本地文件头像提取失败\n")
    else:
        print(f"本地文件不存在: {local_image_path}\n")
    
    # 从URL提取头像（示例URL，实际使用时请替换为真实URL）
    # example_url = "https://example.com/sample_image.jpg"
    # print(f"正在从URL提取头像: {example_url}")
    # success = extractor.extract_face_from_url(
    #     example_url, 
    #     "avatar_from_url.jpg"
    # )
    # if success:
    #     print("✓ URL头像提取成功\n")
    # else:
    #     print("✗ URL头像提取失败\n")
    
    print("方法2: 使用便捷函数")
    
    # 使用便捷函数从本地文件提取
    if os.path.exists(local_image_path):
        print(f"使用便捷函数从本地文件提取头像")
        success = extract_face_from_file(
            local_image_path, 
            "avatar_convenience.jpg",
            "output_convenience"
        )
        if success:
            print("✓ 便捷函数头像提取成功\n")
        else:
            print("✗ 便捷函数头像提取失败\n")
    
    # 使用便捷函数从URL提取（示例）
    # success = extract_face_from_url(
    #     "https://example.com/image.jpg", 
    #     "avatar_url_convenience.jpg",
    #     "output_convenience"
    # )
    
    print("=== 示例完成 ===")
    print("您可以根据需要修改上述代码来处理您的图片")

if __name__ == "__main__":
    main()