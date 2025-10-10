#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多人脸检测和头像截取程序
从所有图片中提取所有识别的正面人物头像
如果不是一个人则分别提取出来，如果是一个人出现多次则只保留一个正面最清晰的照片
输出128x128像素的头像图片
"""

import os
import cv2
import numpy as np
import random
from pathlib import Path
import argparse
from collections import defaultdict

class MultiPersonFaceExtractor:
    def __init__(self, input_dir="images", output_dir="output_multi"):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        
        # 创建输出目录
        self.output_dir.mkdir(exist_ok=True)
        
        # 初始化人脸检测器
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        self.eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')
        
        # 设置人脸聚类阈值
        self.face_similarity_threshold = 0.6  # 越低越严格，越高越宽松
    
    def get_all_image_files(self):
        """获取所有图片文件"""
        image_files = []
        
        if not self.input_dir.exists():
            print(f"输入目录不存在: {self.input_dir}")
            return image_files
            
        # 支持常见的图片格式
        image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.gif']
        
        for file_path in self.input_dir.glob("*"):
            if file_path.suffix.lower() in image_extensions:
                image_files.append(file_path)
                
        print(f"找到 {len(image_files)} 个图片文件")
        return image_files
    
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
        
        # 4. 位置分数 (中心位置的人脸通常更重要)
        img_center_x = original_img.shape[1] // 2
        img_center_y = original_img.shape[0] // 2
        face_center_x = x + w // 2
        face_center_y = y + h // 2
        
        distance_from_center = np.sqrt((face_center_x - img_center_x)**2 + (face_center_y - img_center_y)** 2)
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
    
    def compare_faces(self, face1, face2):
        """比较两个人脸的相似度"""
        # 调整大小为相同尺寸
        face1_resized = cv2.resize(face1, (128, 128))
        face2_resized = cv2.resize(face2, (128, 128))
        
        # 转换为灰度图
        face1_gray = cv2.cvtColor(face1_resized, cv2.COLOR_BGR2GRAY)
        face2_gray = cv2.cvtColor(face2_resized, cv2.COLOR_BGR2GRAY)
        
        # 计算直方图相似度
        hist1 = cv2.calcHist([face1_gray], [0], None, [256], [0, 256])
        hist2 = cv2.calcHist([face2_gray], [0], None, [256], [0, 256])
        
        # 归一化直方图
        hist1 = cv2.normalize(hist1, hist1).flatten()
        hist2 = cv2.normalize(hist2, hist2).flatten()
        
        # 计算相关性
        similarity = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)
        
        return similarity
    
    def cluster_faces(self, faces_with_info):
        """对检测到的人脸进行聚类，区分不同的人物"""
        clusters = []  # 每个聚类包含该人物的最佳人脸信息
        
        for face_info in faces_with_info:
            face_img, score_info, original_path, face_rect = face_info
            added_to_cluster = False
            
            # 尝试将人脸添加到现有的聚类中
            for i, cluster in enumerate(clusters):
                # 与聚类中最清晰的人脸进行比较
                best_face_in_cluster = cluster["face_img"]
                similarity = self.compare_faces(face_img, best_face_in_cluster)
                
                if similarity > self.face_similarity_threshold:
                    # 如果当前人脸质量更好，则更新聚类中的最佳人脸
                    if score_info['total'] > cluster["score_info"]['total']:
                        clusters[i] = {
                            "face_img": face_img,
                            "score_info": score_info,
                            "original_path": original_path,
                            "face_rect": face_rect,
                            "cluster_id": i
                        }
                    added_to_cluster = True
                    break
            
            # 如果没有匹配的聚类，则创建新的聚类
            if not added_to_cluster:
                clusters.append({
                    "face_img": face_img,
                    "score_info": score_info,
                    "original_path": original_path,
                    "face_rect": face_rect,
                    "cluster_id": len(clusters)
                })
        
        return clusters
    
    def detect_all_faces(self, image_path):
        """检测图片中的所有人脸"""
        try:
            # 读取图片
            img = cv2.imread(str(image_path))
            if img is None:
                print(f"无法读取图片: {image_path}")
                return []
                
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
                print(f"未检测到人脸: {image_path.name}")
                return []
                
            print(f"检测到 {len(faces)} 个人脸: {image_path.name}")
            
            faces_with_info = []
            
            for i, face_rect in enumerate(faces):
                x, y, w, h = face_rect
                face_img_cropped = img[y:y+h, x:x+w]
                
                # 计算人脸质量分数
                score, score_info = self.calculate_face_quality(face_img_cropped, face_rect, img)
                print(f"  人脸 {i+1}: 总分={score:.2f}, 尺寸={score_info['size']}, 清晰度={score_info['clarity']:.2f}, 正面性={score_info['frontal']}, 位置={score_info['position']:.2f}")
                
                # 扩展边界以获得更好的头像效果
                padding = int(min(w, h) * 0.3)
                x1 = max(0, x - padding)
                y1 = max(0, y - padding)
                x2 = min(img.shape[1], x + w + padding)
                y2 = min(img.shape[0], y + h + padding)
                
                face_img = img[y1:y2, x1:x2]
                
                # 只保留正面人脸（至少检测到一只眼睛）
                if score_info['frontal'] > 0:
                    faces_with_info.append((face_img, score_info, image_path, face_rect))
                else:
                    print(f"  人脸 {i+1} 不是正面，跳过")
            
            return faces_with_info
            
        except Exception as e:
            print(f"处理图片时出错 {image_path}: {e}")
            return []
    
    def process_all_files(self):
        """处理所有图片文件，提取多个人物头像"""
        image_files = self.get_all_image_files()
        
        if not image_files:
            print("没有找到图片文件")
            return
            
        # 存储所有检测到的人脸信息
        all_faces_info = []
        
        # 处理每个文件
        for i, file_path in enumerate(image_files, 1):
            print(f"\n处理文件 {i}/{len(image_files)}: {file_path.name}")
            
            # 检测所有人脸
            faces_info = self.detect_all_faces(file_path)
            all_faces_info.extend(faces_info)
        
        print(f"\n总共检测到 {len(all_faces_info)} 个正面人脸")
        
        if not all_faces_info:
            print("没有检测到有效的正面人脸")
            return
        
        # 对人脸进行聚类，区分不同的人物
        print("\n正在对人脸进行聚类，区分不同的人物...")
        face_clusters = self.cluster_faces(all_faces_info)
        
        print(f"共识别出 {len(face_clusters)} 个不同的人物")
        
        # 保存每个人物的最佳头像
        for i, cluster in enumerate(face_clusters):
            face_img = cluster["face_img"]
            original_path = cluster["original_path"]
            
            # 调整大小为128x128
            face_resized = cv2.resize(face_img, (128, 128), interpolation=cv2.INTER_LANCZOS4)
            
            # 生成输出文件名
            base_name = original_path.stem
            output_filename = f"{base_name}_person_{i+1}_face.jpg"
            output_path = self.output_dir / output_filename
            
            # 保存头像
            success = cv2.imwrite(str(output_path), face_resized)
            
            if success:
                print(f"✓ 头像已保存: {output_filename}")
            else:
                print(f"✗ 保存失败: {output_filename}")
        
        print(f"\n处理完成: 已提取 {len(face_clusters)} 个人物的最佳头像")

    def process_single_file(self, image_path):
        """处理单个文件，提取多个人物头像"""
        file_path = Path(image_path)
        
        if not file_path.exists():
            print(f"文件不存在: {image_path}")
            return
            
        print(f"\n处理文件: {file_path.name}")
        
        # 检测所有人脸
        faces_info = self.detect_all_faces(file_path)
        
        if not faces_info:
            print("没有检测到有效的正面人脸")
            return
        
        # 对人脸进行聚类，区分不同的人物
        print("\n正在对人脸进行聚类，区分不同的人物...")
        face_clusters = self.cluster_faces(faces_info)
        
        print(f"共识别出 {len(face_clusters)} 个不同的人物")
        
        # 保存每个人物的最佳头像
        for i, cluster in enumerate(face_clusters):
            face_img = cluster["face_img"]
            
            # 调整大小为128x128
            face_resized = cv2.resize(face_img, (128, 128), interpolation=cv2.INTER_LANCZOS4)
            
            # 生成输出文件名
            base_name = file_path.stem
            output_filename = f"{base_name}_person_{i+1}_face.jpg"
            output_path = self.output_dir / output_filename
            
            # 保存头像
            success = cv2.imwrite(str(output_path), face_resized)
            
            if success:
                print(f"✓ 头像已保存: {output_filename}")
            else:
                print(f"✗ 保存失败: {output_filename}")
        
        print(f"\n处理完成: 已提取 {len(face_clusters)} 个人物的最佳头像")

def main():
    parser = argparse.ArgumentParser(description='多人脸检测和头像截取程序')
    parser.add_argument('--input', '-i', default='images', help='输入目录 (默认: images)')
    parser.add_argument('--output', '-o', default='output_multi', help='输出目录 (默认: output_multi)')
    parser.add_argument('--file', '-f', help='单个文件路径，如果指定则只处理该文件')
    parser.add_argument('--threshold', '-t', type=float, default=0.6, help='人脸相似度阈值 (默认: 0.6)')
    
    args = parser.parse_args()
    
    print("=== 多人脸检测和头像截取程序 ===")
    print(f"输入目录: {args.input}")
    print(f"输出目录: {args.output}")
    print(f"人脸相似度阈值: {args.threshold}")
    print()
    
    extractor = MultiPersonFaceExtractor(args.input, args.output)
    extractor.face_similarity_threshold = args.threshold
    
    if args.file:
        extractor.process_single_file(args.file)
    else:
        extractor.process_all_files()

if __name__ == "__main__":
    main()