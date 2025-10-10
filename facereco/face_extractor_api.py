#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
头像提取API
提供简单易用的头像提取函数，支持URL和本地文件
"""

import os
import cv2
import numpy as np
import requests
from urllib.parse import urlparse
import tempfile
from pathlib import Path


class FaceExtractorAPI:
    def __init__(self, output_dir="output"):
        """
        初始化头像提取器
        
        Args:
            output_dir (str): 默认输出目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # 初始化人脸检测器
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        self.eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')
        
    def calculate_face_quality(self, face_img, face_rect, original_img):
        """计算人脸质量分数，用于选择最佳人脸"""
        x, y, w, h = face_rect
        
        # 1. 尺寸分数 (更大的人脸通常更清晰)
        size_score = w * h
        
        # 2. 清晰度分数 (使用拉普拉斯算子计算)
        gray_face = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY) if len(face_img.shape) == 3 else face_img
        laplacian_var = cv2.Laplacian(gray_face, cv2.CV_64F).var()
        
        # 3. 正面性分数 (检测眼睛来判断是否为正面)
        eyes = self.eye_cascade.detectMultiScale(gray_face, 1.1, 5)
        frontal_score = len(eyes) * 100  # 检测到的眼睛数量
        
        # 4. 位置分数 (中心位置的人脸通常是主角)
        img_center_x = original_img.shape[1] // 2
        img_center_y = original_img.shape[0] // 2
        face_center_x = x + w // 2
        face_center_y = y + h // 2
        
        distance_from_center = np.sqrt((face_center_x - img_center_x)**2 + (face_center_y - img_center_y)**2)
        position_score = 1000 / (1 + distance_from_center)  # 距离中心越近分数越高
        
        # 综合分数
        total_score = size_score * 0.3 + laplacian_var * 0.4 + frontal_score * 0.2 + position_score * 0.1
        
        return total_score, {
            'size': size_score,
            'clarity': laplacian_var,
            'frontal': frontal_score,
            'position': position_score,
            'total': total_score
        }
    
    def detect_and_extract_best_face(self, img):
        """检测并提取最佳人脸"""
        try:
            if img is None:
                print("无法读取图片")
                return None
                
            # 转换为灰度图进行人脸检测
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # 检测人脸
            faces = self.face_cascade.detectMultiScale(
                gray, 
                scaleFactor=1.1, 
                minNeighbors=5, 
                minSize=(50, 50),
                flags=cv2.CASCADE_SCALE_IMAGE
            )
            
            if len(faces) == 0:
                print("未检测到人脸")
                return None
                
            print(f"检测到 {len(faces)} 个人脸")
            
            # 如果只有一个人脸，直接使用
            if len(faces) == 1:
                best_face = faces[0]
                best_score_info = {'total': 0}
            else:
                # 多个人脸时，选择质量最高的
                best_face = None
                best_score = -1
                best_score_info = None
                
                for i, face in enumerate(faces):
                    x, y, w, h = face
                    face_img = img[y:y+h, x:x+w]
                    
                    score, score_info = self.calculate_face_quality(face_img, face, img)
                    print(f"  人脸 {i+1}: 总分={score:.2f}, 尺寸={score_info['size']}, 清晰度={score_info['clarity']:.2f}, 正面性={score_info['frontal']}, 位置={score_info['position']:.2f}")
                    
                    if score > best_score:
                        best_score = score
                        best_face = face
                        best_score_info = score_info
                
                print(f"  选择最佳人脸，总分: {best_score_info['total']:.2f}")
            
            # 提取最佳人脸
            x, y, w, h = best_face
            
            # 扩展边界以获得更好的头像效果
            padding = int(min(w, h) * 0.3)
            x1 = max(0, x - padding)
            y1 = max(0, y - padding)
            x2 = min(img.shape[1], x + w + padding)
            y2 = min(img.shape[0], y + h + padding)
            
            face_img = img[y1:y2, x1:x2]
            
            # 调整大小为128x128
            face_resized = cv2.resize(face_img, (128, 128), interpolation=cv2.INTER_LANCZOS4)
            
            return face_resized
            
        except Exception as e:
            print(f"处理图片时出错: {e}")
            return None
    
    def extract_face_from_url(self, image_url, output_filename, output_dir=None):
        """
        从图片URL提取头像并保存到指定文件
        
        Args:
            image_url (str): 图片的URL链接
            output_filename (str): 输出文件名（包含扩展名）
            output_dir (str, optional): 输出目录，如果不指定则使用默认输出目录
            
        Returns:
            bool: 成功返回True，失败返回False
        """
        try:
            # 确定输出目录
            if output_dir is None:
                save_dir = self.output_dir
            else:
                save_dir = Path(output_dir)
                save_dir.mkdir(exist_ok=True)
            
            # 下载图片
            print(f"正在下载图片: {image_url}")
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()
            
            # 创建临时文件保存下载的图片
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
                temp_file.write(response.content)
                temp_path = temp_file.name
            
            try:
                # 读取图片
                img = cv2.imread(temp_path)
                
                # 使用现有的人脸检测方法
                face_img = self.detect_and_extract_best_face(img)
                
                if face_img is not None:
                    # 保存头像
                    output_path = save_dir / output_filename
                    success = cv2.imwrite(str(output_path), face_img)
                    
                    if success:
                        print(f"头像已保存: {output_path}")
                        return True
                    else:
                        print(f"保存头像失败: {output_path}")
                        return False
                else:
                    print("未能从图片中提取到有效的人脸")
                    return False
                    
            finally:
                # 清理临时文件
                os.unlink(temp_path)
                
        except requests.RequestException as e:
            print(f"下载图片失败: {e}")
            return False
        except Exception as e:
            print(f"处理图片时出错: {e}")
            return False
    
    def extract_face_from_file(self, image_path, output_filename, output_dir=None):
        """
        从本地图片文件提取头像并保存到指定文件
        
        Args:
            image_path (str): 本地图片文件路径
            output_filename (str): 输出文件名（包含扩展名）
            output_dir (str, optional): 输出目录，如果不指定则使用默认输出目录
            
        Returns:
            bool: 成功返回True，失败返回False
        """
        try:
            # 确定输出目录
            if output_dir is None:
                save_dir = self.output_dir
            else:
                save_dir = Path(output_dir)
                save_dir.mkdir(exist_ok=True)
            
            # 检查输入文件是否存在
            input_path = Path(image_path)
            if not input_path.exists():
                print(f"输入文件不存在: {image_path}")
                return False
            
            print(f"正在处理本地文件: {input_path.name}")
            
            # 读取图片
            img = cv2.imread(str(input_path))
            
            # 使用现有的人脸检测方法
            face_img = self.detect_and_extract_best_face(img)
            
            if face_img is not None:
                # 保存头像
                output_path = save_dir / output_filename
                success = cv2.imwrite(str(output_path), face_img)
                
                if success:
                    print(f"头像已保存: {output_path}")
                    return True
                else:
                    print(f"保存头像失败: {output_path}")
                    return False
            else:
                print("未能从图片中提取到有效的人脸")
                return False
                
        except Exception as e:
            print(f"处理图片时出错: {e}")
            return False


# 便捷函数
def extract_face_from_url(image_url, output_filename, output_dir="output"):
    """
    便捷函数：从URL提取头像
    
    Args:
        image_url (str): 图片URL
        output_filename (str): 输出文件名
        output_dir (str): 输出目录
        
    Returns:
        bool: 成功返回True，失败返回False
    """
    extractor = FaceExtractorAPI(output_dir)
    return extractor.extract_face_from_url(image_url, output_filename)


def extract_face_from_file(image_path, output_filename, output_dir="output"):
    """
    便捷函数：从本地文件提取头像
    
    Args:
        image_path (str): 本地图片路径
        output_filename (str): 输出文件名
        output_dir (str): 输出目录
        
    Returns:
        bool: 成功返回True，失败返回False
    """
    extractor = FaceExtractorAPI(output_dir)
    return extractor.extract_face_from_file(image_path, output_filename)


# 示例用法
if __name__ == "__main__":
    # 创建提取器实例
    extractor = FaceExtractorAPI("output")
    
    # 示例1: 从URL提取头像
    # success = extractor.extract_face_from_url(
    #     "https://example.com/image.jpg", 
    #     "avatar_from_url.jpg"
    # )
    
    # 示例2: 从本地文件提取头像
    # success = extractor.extract_face_from_file(
    #     "images/sample.jpg", 
    #     "avatar_from_file.jpg"
    # )
    
    # 示例3: 使用便捷函数
    # success = extract_face_from_url("https://example.com/image.jpg", "avatar.jpg")
    # success = extract_face_from_file("images/sample.jpg", "avatar.jpg")
    
    print("头像提取API已准备就绪！")
    print("使用方法:")
    print("1. 从URL提取: extract_face_from_url(url, 'output.jpg')")
    print("2. 从文件提取: extract_face_from_file('path/to/image.jpg', 'output.jpg')")