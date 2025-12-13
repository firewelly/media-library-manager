#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频内容特征分析器
使用计算机视觉技术分析视频内容，检测特定的视觉特征
如服装、身材特征等，并生成相应的标签

作者: AI Assistant
创建时间: 2024
"""

import cv2
import numpy as np
import sqlite3
import os
import json
from datetime import datetime
from pathlib import Path
import threading
import queue
import time
from collections import Counter, defaultdict

class VideoContentAnalyzer:
    def __init__(self, db_path="media_library.db"):
        """
        初始化视频内容分析器
        
        Args:
            db_path (str): 数据库文件路径
        """
        self.db_path = db_path
        self.feature_detectors = self._init_feature_detectors()
        self.analysis_cache = {}
        
    def _init_feature_detectors(self):
        """
        初始化特征检测器
        使用轻量级的计算机视觉方法
        
        Returns:
            dict: 特征检测器字典
        """
        detectors = {
            # 颜色特征检测器
            'color_analyzer': {
                'black_stockings': self._detect_black_stockings,
                'skin_tone': self._detect_skin_tone,
                'clothing_colors': self._detect_clothing_colors
            },
            
            # 形状特征检测器
            'shape_analyzer': {
                'body_proportions': self._detect_body_proportions,
                'clothing_shapes': self._detect_clothing_shapes
            },
            
            # 纹理特征检测器
            'texture_analyzer': {
                'fabric_textures': self._detect_fabric_textures,
                'skin_textures': self._detect_skin_textures
            },
            
            # 职业特征检测器
            'profession_analyzer': {
                'nurse_uniform': self._detect_nurse_uniform,
                'medical_equipment': self._detect_medical_equipment
            },
            
            # 场景特征检测器
            'scene_analyzer': {
                'forced_scenario': self._detect_forced_scenario,
                'medical_environment': self._detect_medical_environment
            }
        }
        
        return detectors
    
    def _extract_frames(self, video_path, min_frames=100, max_interval=10, max_frames=300):
        """
        从视频中提取关键帧 - 性能优化版本
        
        Args:
            video_path (str): 视频文件路径
            min_frames (int): 最少提取帧数（默认30帧，降低以提高性能）
            max_interval (int): 最大提取间隔（秒）（默认15秒，提高以减少帧数）
            max_frames (int): 最大提取帧数（默认100帧，降低以提高性能）
            
        Returns:
            list: 提取的帧列表
        """
        if not os.path.exists(video_path):
            print(f"视频文件不存在: {video_path}")
            return []
        
        try:
            cap = cv2.VideoCapture(video_path)
            
            if not cap.isOpened():
                print(f"无法打开视频文件: {video_path}")
                return []
            
            # 获取视频信息
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = frame_count / fps if fps > 0 else 0
            
            print(f"视频信息: {duration:.1f}秒, {frame_count}帧, {fps:.1f}fps")
            
            # 计算提取策略
            if duration <= 0 or fps <= 0:
                print("无法获取视频时长信息")
                cap.release()
                return []
            
            # 性能优化：根据视频时长动态调整提取策略
            # 对于长视频，使用更大的间隔
            if duration > 600:  # 10分钟以上的视频
                max_interval = 30  # 30秒一帧
                max_frames = 300   # 最多300帧
            elif duration > 300:  # 5-10分钟的视频
                max_interval = 20  # 20秒一帧
                max_frames = 300   # 最多300帧
            
            # 计算理想的提取间隔
            # 优先使用较大间隔，但确保至少有min_frames帧，不超过max_frames帧
            interval_by_time = max_interval  # 默认15秒间隔
            interval_by_min_count = duration / min_frames  # 保证最少帧数的间隔
            interval_by_max_count = duration / max_frames  # 保证不超过最大帧数的间隔
            
            # 选择合适的间隔
            actual_interval = max(interval_by_max_count, min(interval_by_time, interval_by_min_count))
            actual_interval = max(1, actual_interval)  # 至少1秒间隔
            
            # 计算实际提取的帧数 - 限制最大帧数以提高性能
            expected_frames = min(max_frames, int(duration / actual_interval) + 1)
            
            print(f"提取策略: 每{actual_interval:.1f}秒一帧，预计提取{expected_frames}帧（限制最大{max_frames}帧）")
            
            frames = []
            frame_indices = []
            
            # 性能优化：使用更高效的帧提取方法
            # 直接计算所有需要提取的帧位置，然后一次性提取
            frame_positions = []
            current_time = 0
            
            # 预先计算所有帧位置
            while current_time <= duration and len(frame_positions) < expected_frames:
                frame_index = int(current_time * fps)
                if frame_index < frame_count:
                    frame_positions.append(frame_index)
                current_time += actual_interval
            
            print(f"计划提取 {len(frame_positions)} 帧")
            
            # 批量提取帧
            for frame_index in frame_positions:
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
                ret, frame = cap.read()
                
                if ret and frame is not None:
                    # 保持原始分辨率
                    frames.append(frame)
                    frame_indices.append(frame_index)
            
            cap.release()
            
            print(f"实际提取了 {len(frames)} 帧用于分析")
            
            # 只在帧数严重不足时才补充提取额外帧
            if len(frames) < min_frames // 2 and len(frames) < max_frames and len(frames) > 0:
                needed_frames = min(min_frames // 2, max_frames - len(frames))  # 只补充到最小帧数的一半
                print(f"帧数严重不足，尝试补充提取{needed_frames}帧...")
                additional_frames = self._extract_additional_frames(video_path, needed_frames, frame_indices)
                frames.extend(additional_frames)
                print(f"补充后共有 {len(frames)} 帧")
            
            return frames
            
        except Exception as e:
            print(f"提取视频帧失败: {e}")
            return []
    
    def _extract_additional_frames(self, video_path, needed_frames, existing_indices):
        """
        补充提取额外的帧 - 性能优化版本
        
        Args:
            video_path (str): 视频文件路径
            needed_frames (int): 需要补充的帧数
            existing_indices (list): 已提取的帧索引
            
        Returns:
            list: 补充的帧列表
        """
        additional_frames = []
        
        try:
            cap = cv2.VideoCapture(video_path)
            
            if not cap.isOpened():
                return additional_frames
            
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            existing_set = set(existing_indices)
            
            # 性能优化：预先计算所有可能的补充帧位置
            potential_positions = []
            
            # 在现有帧之间均匀插入新帧
            if len(existing_indices) >= 2:
                # 只处理较大间隔的帧
                gaps = []
                for i in range(len(existing_indices) - 1):
                    start_idx = existing_indices[i]
                    end_idx = existing_indices[i + 1]
                    gap_size = end_idx - start_idx
                    gaps.append((i, gap_size))
                
                # 按间隔大小排序，优先处理大间隔
                gaps.sort(key=lambda x: x[1], reverse=True)
                
                # 只处理前几个最大间隔
                for gap_idx, _ in gaps[:min(needed_frames, len(gaps))]:
                    i = gap_idx
                    start_idx = existing_indices[i]
                    end_idx = existing_indices[i + 1]
                    
                    # 在两个已有帧之间插入一帧
                    mid_idx = (start_idx + end_idx) // 2
                    
                    if mid_idx not in existing_set and mid_idx < frame_count:
                        potential_positions.append(mid_idx)
            
            # 批量提取帧
            for pos in potential_positions[:needed_frames]:
                cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
                ret, frame = cap.read()
                
                if ret and frame is not None:
                    # 保持原始分辨率
                    additional_frames.append(frame)
            
            cap.release()
            
        except Exception as e:
            print(f"补充提取帧失败: {e}")
        
        return additional_frames
    
    def _detect_black_stockings(self, frame):
        """
        检测黑丝袜
        
        Args:
            frame: 视频帧
            
        Returns:
            dict: 检测结果
        """
        try:
            # 转换到HSV色彩空间
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            
            # 定义黑色范围
            lower_black = np.array([0, 0, 0])
            upper_black = np.array([180, 255, 50])
            
            # 创建黑色掩码
            black_mask = cv2.inRange(hsv, lower_black, upper_black)
            
            # 形态学操作去除噪声
            kernel = np.ones((3, 3), np.uint8)
            black_mask = cv2.morphologyEx(black_mask, cv2.MORPH_CLOSE, kernel)
            black_mask = cv2.morphologyEx(black_mask, cv2.MORPH_OPEN, kernel)
            
            # 查找轮廓
            contours, _ = cv2.findContours(black_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # 分析轮廓特征
            stocking_features = []
            total_area = frame.shape[0] * frame.shape[1]
            
            for contour in contours:
                area = cv2.contourArea(contour)
                if area > total_area * 0.01:  # 面积阈值
                    # 计算轮廓的长宽比
                    x, y, w, h = cv2.boundingRect(contour)
                    aspect_ratio = h / w if w > 0 else 0
                    
                    # 检查是否符合丝袜特征（细长形状）
                    if aspect_ratio > 2.0 and area > total_area * 0.02:
                        stocking_features.append({
                            'area': area,
                            'aspect_ratio': aspect_ratio,
                            'position': (x, y, w, h)
                        })
            
            # 计算置信度
            confidence = 0.0
            if stocking_features:
                # 基于检测到的特征计算置信度
                total_stocking_area = sum(f['area'] for f in stocking_features)
                area_ratio = total_stocking_area / total_area
                
                # 考虑形状特征
                avg_aspect_ratio = np.mean([f['aspect_ratio'] for f in stocking_features])
                
                confidence = min(1.0, area_ratio * 10 + (avg_aspect_ratio - 2.0) * 0.1)
            
            return {
                'detected': confidence > 0.3,
                'confidence': confidence,
                'features': stocking_features,
                'black_area_ratio': np.sum(black_mask > 0) / total_area
            }
            
        except Exception as e:
            print(f"肌肤纹理检测失败: {e}")
            return {'detected': False, 'confidence': 0.0, 'features': []}
    
    def _detect_nurse_uniform(self, frame):
        """
        检测护士制服特征
        
        Args:
            frame: 视频帧
            
        Returns:
            dict: 护士制服检测结果
        """
        try:
            # 转换到HSV色彩空间
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            
            # 检测白色制服（护士服通常是白色或浅色）
            lower_white = np.array([0, 0, 200])
            upper_white = np.array([180, 30, 255])
            white_mask = cv2.inRange(hsv, lower_white, upper_white)
            
            # 检测浅蓝色制服（现代护士服常见颜色）
            lower_light_blue = np.array([100, 50, 150])
            upper_light_blue = np.array([130, 255, 255])
            blue_mask = cv2.inRange(hsv, lower_light_blue, upper_light_blue)
            
            # 合并制服颜色掩码
            uniform_mask = cv2.bitwise_or(white_mask, blue_mask)
            
            # 形态学操作
            kernel = np.ones((5, 5), np.uint8)
            uniform_mask = cv2.morphologyEx(uniform_mask, cv2.MORPH_CLOSE, kernel)
            
            # 查找轮廓
            contours, _ = cv2.findContours(uniform_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # 分析制服特征
            uniform_features = []
            total_area = frame.shape[0] * frame.shape[1]
            
            for contour in contours:
                area = cv2.contourArea(contour)
                if area > total_area * 0.05:  # 制服应该占一定面积
                    x, y, w, h = cv2.boundingRect(contour)
                    aspect_ratio = h / w if w > 0 else 0
                    
                    # 制服通常在上半身，且有一定的形状特征
                    if y < frame.shape[0] * 0.7 and 1.2 < aspect_ratio < 3.0:
                        uniform_features.append({
                            'area': area,
                            'position': (x, y, w, h),
                            'aspect_ratio': aspect_ratio
                        })
            
            # 计算置信度
            confidence = 0.0
            if uniform_features:
                total_uniform_area = sum(f['area'] for f in uniform_features)
                area_ratio = total_uniform_area / total_area
                
                # 基于面积比例和位置特征计算置信度
                position_score = sum(1 for f in uniform_features if f['position'][1] < frame.shape[0] * 0.5) / len(uniform_features)
                confidence = min(1.0, area_ratio * 5 + position_score * 0.3)
            
            return {
                'detected': confidence > 0.4,
                'confidence': confidence,
                'features': uniform_features,
                'uniform_area_ratio': np.sum(uniform_mask > 0) / total_area
            }
            
        except Exception as e:
            print(f"护士制服检测失败: {e}")
            return {'detected': False, 'confidence': 0.0, 'features': []}
    
    def _detect_medical_equipment(self, frame):
        """
        检测医疗设备和环境
        
        Args:
            frame: 视频帧
            
        Returns:
            dict: 医疗设备检测结果
        """
        try:
            # 转换到灰度图
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # 检测白色医疗设备（如病床、医疗器械）
            _, white_thresh = cv2.threshold(gray, 220, 255, cv2.THRESH_BINARY)
            
            # 检测金属质感（医疗器械常见）
            # 使用边缘检测来识别金属物体的反光特征
            edges = cv2.Canny(gray, 50, 150)
            
            # 查找轮廓
            contours, _ = cv2.findContours(white_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            medical_features = []
            total_area = frame.shape[0] * frame.shape[1]
            
            for contour in contours:
                area = cv2.contourArea(contour)
                if area > total_area * 0.02:
                    x, y, w, h = cv2.boundingRect(contour)
                    
                    # 检查是否有规则的几何形状（医疗设备特征）
                    hull = cv2.convexHull(contour)
                    hull_area = cv2.contourArea(hull)
                    solidity = area / hull_area if hull_area > 0 else 0
                    
                    if solidity > 0.8:  # 较规则的形状
                        medical_features.append({
                            'area': area,
                            'position': (x, y, w, h),
                            'solidity': solidity
                        })
            
            # 计算置信度
            confidence = 0.0
            if medical_features:
                total_medical_area = sum(f['area'] for f in medical_features)
                area_ratio = total_medical_area / total_area
                avg_solidity = np.mean([f['solidity'] for f in medical_features])
                
                confidence = min(1.0, area_ratio * 3 + avg_solidity * 0.5)
            
            return {
                'detected': confidence > 0.3,
                'confidence': confidence,
                'features': medical_features,
                'white_area_ratio': np.sum(white_thresh > 0) / total_area
            }
            
        except Exception as e:
            print(f"医疗设备检测失败: {e}")
            return {'detected': False, 'confidence': 0.0, 'features': []}
    
    def _detect_forced_scenario(self, frame):
        """
        检测强制场景的视觉特征
        
        Args:
            frame: 视频帧
            
        Returns:
            dict: 强制场景检测结果
        """
        try:
            # 转换到HSV色彩空间
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            
            # 检测暗色调（强制场景通常光线较暗）
            v_channel = hsv[:, :, 2]
            dark_ratio = np.sum(v_channel < 100) / (frame.shape[0] * frame.shape[1])
            
            # 检测红色（可能的暴力或紧张场景指示）
            lower_red1 = np.array([0, 50, 50])
            upper_red1 = np.array([10, 255, 255])
            lower_red2 = np.array([170, 50, 50])
            upper_red2 = np.array([180, 255, 255])
            
            red_mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
            red_mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
            red_mask = cv2.bitwise_or(red_mask1, red_mask2)
            
            red_ratio = np.sum(red_mask > 0) / (frame.shape[0] * frame.shape[1])
            
            # 检测混乱的纹理（可能表示挣扎或混乱场景）
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # 使用拉普拉斯算子检测纹理复杂度
            laplacian = cv2.Laplacian(gray, cv2.CV_64F)
            texture_variance = np.var(laplacian)
            
            # 计算置信度
            confidence = 0.0
            
            # 综合多个因素
            dark_score = min(1.0, dark_ratio * 2)  # 暗色调评分
            red_score = min(1.0, red_ratio * 10)   # 红色评分
            texture_score = min(1.0, texture_variance / 1000)  # 纹理复杂度评分
            
            confidence = (dark_score * 0.4 + red_score * 0.3 + texture_score * 0.3)
            
            return {
                'detected': confidence > 0.5,
                'confidence': confidence,
                'dark_ratio': dark_ratio,
                'red_ratio': red_ratio,
                'texture_variance': texture_variance
            }
            
        except Exception as e:
            print(f"强制场景检测失败: {e}")
            return {'detected': False, 'confidence': 0.0}
    
    def _detect_medical_environment(self, frame):
        """
        检测医疗环境特征
        
        Args:
            frame: 视频帧
            
        Returns:
            dict: 医疗环境检测结果
        """
        try:
            # 转换到HSV色彩空间
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            
            # 检测医院常见的白色和浅色调
            lower_white = np.array([0, 0, 200])
            upper_white = np.array([180, 50, 255])
            white_mask = cv2.inRange(hsv, lower_white, upper_white)
            
            # 检测医院绿色（手术服、医疗设备常见颜色）
            lower_medical_green = np.array([40, 50, 50])
            upper_medical_green = np.array([80, 255, 255])
            green_mask = cv2.inRange(hsv, lower_medical_green, upper_medical_green)
            
            # 检测蓝色（医疗环境常见）
            lower_medical_blue = np.array([100, 50, 50])
            upper_medical_blue = np.array([130, 255, 255])
            blue_mask = cv2.inRange(hsv, lower_medical_blue, upper_medical_blue)
            
            # 计算各种颜色的比例
            total_pixels = frame.shape[0] * frame.shape[1]
            white_ratio = np.sum(white_mask > 0) / total_pixels
            green_ratio = np.sum(green_mask > 0) / total_pixels
            blue_ratio = np.sum(blue_mask > 0) / total_pixels
            
            # 检测规则的线条（医疗设备、建筑特征）
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            
            # 使用霍夫变换检测直线
            lines = cv2.HoughLines(edges, 1, np.pi/180, threshold=100)
            line_count = len(lines) if lines is not None else 0
            
            # 计算置信度
            medical_color_score = white_ratio * 0.5 + green_ratio * 0.3 + blue_ratio * 0.2
            structure_score = min(1.0, line_count / 50)  # 规则结构评分
            
            confidence = min(1.0, medical_color_score * 2 + structure_score * 0.5)
            
            return {
                'detected': confidence > 0.4,
                'confidence': confidence,
                'white_ratio': white_ratio,
                'green_ratio': green_ratio,
                'blue_ratio': blue_ratio,
                'line_count': line_count
            }
            
        except Exception as e:
            print(f"医疗环境检测失败: {e}")
            return {'detected': False, 'confidence': 0.0}
    
    def _detect_skin_tone(self, frame):
        """
        检测肤色区域
        
        Args:
            frame: 视频帧
            
        Returns:
            dict: 肤色检测结果
        """
        try:
            # 转换到YCrCb色彩空间（更适合肤色检测）
            ycrcb = cv2.cvtColor(frame, cv2.COLOR_BGR2YCrCb)
            
            # 定义肤色范围
            lower_skin = np.array([0, 133, 77])
            upper_skin = np.array([255, 173, 127])
            
            # 创建肤色掩码
            skin_mask = cv2.inRange(ycrcb, lower_skin, upper_skin)
            
            # 形态学操作
            kernel = np.ones((3, 3), np.uint8)
            skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_OPEN, kernel)
            skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_CLOSE, kernel)
            
            # 计算肤色区域比例
            total_pixels = frame.shape[0] * frame.shape[1]
            skin_pixels = np.sum(skin_mask > 0)
            skin_ratio = skin_pixels / total_pixels
            
            return {
                'skin_ratio': skin_ratio,
                'large_skin_area': skin_ratio > 0.2,
                'mask': skin_mask
            }
            
        except Exception as e:
            print(f"肤色检测失败: {e}")
            return {'skin_ratio': 0.0, 'large_skin_area': False}
    
    def _detect_clothing_colors(self, frame):
        """
        检测服装颜色
        
        Args:
            frame: 视频帧
            
        Returns:
            dict: 服装颜色检测结果
        """
        try:
            # 转换到HSV色彩空间
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            
            # 定义颜色范围
            color_ranges = {
                'black': ([0, 0, 0], [180, 255, 50]),
                'white': ([0, 0, 200], [180, 30, 255]),
                'red': ([0, 50, 50], [10, 255, 255]),
                'blue': ([100, 50, 50], [130, 255, 255]),
                'pink': ([140, 50, 50], [170, 255, 255])
            }
            
            color_stats = {}
            total_pixels = frame.shape[0] * frame.shape[1]
            
            for color_name, (lower, upper) in color_ranges.items():
                lower = np.array(lower)
                upper = np.array(upper)
                
                mask = cv2.inRange(hsv, lower, upper)
                color_pixels = np.sum(mask > 0)
                color_ratio = color_pixels / total_pixels
                
                color_stats[color_name] = {
                    'ratio': color_ratio,
                    'dominant': color_ratio > 0.1
                }
            
            return color_stats
            
        except Exception as e:
            print(f"服装颜色检测失败: {e}")
            return {}
    
    def _detect_body_proportions(self, frame):
        """
        检测身体比例特征
        
        Args:
            frame: 视频帧
            
        Returns:
            dict: 身体比例检测结果
        """
        try:
            # 获取肤色区域
            skin_info = self._detect_skin_tone(frame)
            
            if not skin_info.get('large_skin_area', False):
                return {'detected': False, 'confidence': 0.0}
            
            skin_mask = skin_info.get('mask')
            if skin_mask is None:
                return {'detected': False, 'confidence': 0.0}
            
            # 查找肤色轮廓
            contours, _ = cv2.findContours(skin_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if not contours:
                return {'detected': False, 'confidence': 0.0}
            
            # 找到最大的肤色区域
            largest_contour = max(contours, key=cv2.contourArea)
            
            # 计算边界框
            x, y, w, h = cv2.boundingRect(largest_contour)
            
            # 分析比例特征
            aspect_ratio = h / w if w > 0 else 0
            area_ratio = cv2.contourArea(largest_contour) / (frame.shape[0] * frame.shape[1])
            
            # 简单的身材特征判断
            features = {
                'aspect_ratio': aspect_ratio,
                'area_ratio': area_ratio,
                'width_ratio': w / frame.shape[1],
                'height_ratio': h / frame.shape[0]
            }
            
            # 基于比例判断身材特征
            confidence = 0.0
            if area_ratio > 0.15 and aspect_ratio > 1.2:
                confidence = min(1.0, area_ratio * 2 + (aspect_ratio - 1.2) * 0.5)
            
            return {
                'detected': confidence > 0.3,
                'confidence': confidence,
                'features': features
            }
            
        except Exception as e:
            print(f"身体比例检测失败: {e}")
            return {'detected': False, 'confidence': 0.0}
    
    def _detect_clothing_shapes(self, frame):
        """
        检测服装形状特征
        
        Args:
            frame: 视频帧
            
        Returns:
            dict: 服装形状检测结果
        """
        try:
            # 转换为灰度图
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # 边缘检测
            edges = cv2.Canny(gray, 50, 150)
            
            # 查找轮廓
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            shape_features = []
            total_area = frame.shape[0] * frame.shape[1]
            
            for contour in contours:
                area = cv2.contourArea(contour)
                if area > total_area * 0.005:  # 面积阈值
                    # 计算形状特征
                    perimeter = cv2.arcLength(contour, True)
                    if perimeter > 0:
                        circularity = 4 * np.pi * area / (perimeter * perimeter)
                        
                        # 计算边界框
                        x, y, w, h = cv2.boundingRect(contour)
                        aspect_ratio = h / w if w > 0 else 0
                        
                        shape_features.append({
                            'area': area,
                            'circularity': circularity,
                            'aspect_ratio': aspect_ratio,
                            'position': (x, y, w, h)
                        })
            
            return {
                'shape_count': len(shape_features),
                'features': shape_features
            }
            
        except Exception as e:
            print(f"服装形状检测失败: {e}")
            return {'shape_count': 0, 'features': []}
    
    def _detect_fabric_textures(self, frame):
        """
        检测织物纹理
        
        Args:
            frame: 视频帧
            
        Returns:
            dict: 纹理检测结果
        """
        try:
            # 转换为灰度图
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # 计算局部二值模式 (简化版)
            # 使用Sobel算子检测纹理
            sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
            sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
            
            # 计算梯度幅值
            magnitude = np.sqrt(sobel_x**2 + sobel_y**2)
            
            # 计算纹理特征
            texture_mean = np.mean(magnitude)
            texture_std = np.std(magnitude)
            
            # 简单的纹理分类
            texture_type = 'smooth'
            if texture_std > 20:
                texture_type = 'textured'
            elif texture_std > 10:
                texture_type = 'moderate'
            
            return {
                'texture_mean': texture_mean,
                'texture_std': texture_std,
                'texture_type': texture_type,
                'is_textured': texture_std > 15
            }
            
        except Exception as e:
            print(f"纹理检测失败: {e}")
            return {'texture_type': 'unknown', 'is_textured': False}
    
    def _detect_skin_textures(self, frame):
        """
        检测肌肤纹理
        
        Args:
            frame: 视频帧
            
        Returns:
            dict: 肌肤纹理检测结果
        """
        try:
            # 获取肤色区域
            skin_info = self._detect_skin_tone(frame)
            skin_mask = skin_info.get('mask')
            
            if skin_mask is None:
                return {'detected': False}
            
            # 在肤色区域内分析纹理
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            skin_region = cv2.bitwise_and(gray, gray, mask=skin_mask)
            
            # 计算肤色区域的纹理特征
            skin_pixels = skin_region[skin_mask > 0]
            
            if len(skin_pixels) == 0:
                return {'detected': False}
            
            skin_mean = np.mean(skin_pixels)
            skin_std = np.std(skin_pixels)
            
            return {
                'detected': True,
                'skin_brightness': skin_mean,
                'skin_uniformity': 1.0 / (1.0 + skin_std),  # 越均匀值越大
                'smooth_skin': skin_std < 15
            }
            
        except Exception as e:
            print(f"肌肤纹理检测失败: {e}")
            return {'detected': False}
    
    def analyze_video_content(self, video_path, min_frames=100, max_interval=10, max_frames=500):
        """
        分析视频内容特征 - 性能优化版本
        
        Args:
            video_path (str): 视频文件路径
            min_frames (int): 最少分析帧数
            max_interval (int): 最大提取间隔（秒）
            max_frames (int): 最大提取帧数
            
        Returns:
            dict: 分析结果
        """
        print(f"开始分析视频: {os.path.basename(video_path)}")
        
        # 提取关键帧 - 减少帧数以提高性能
        frames = self._extract_frames(video_path, min_frames, max_interval, max_frames)
        
        if not frames:
            return {'error': '无法提取视频帧'}
        
        # 初始化结果统计
        results = {
            'black_stockings': [],
            'skin_analysis': [],
            'clothing_colors': [],
            'body_proportions': [],
            'clothing_shapes': [],
            'fabric_textures': [],
            'skin_textures': []
        }
        
        # 分析每一帧 - 使用采样分析以提高性能
        # 如果帧数超过30，则只分析每3帧
        sample_rate = 3 if len(frames) > 30 else 1
        frames_to_analyze = frames[::sample_rate]
        
        for i, frame in enumerate(frames_to_analyze):
            print(f"分析第 {i+1}/{len(frames_to_analyze)} 帧")
            
            try:
                # 黑丝检测
                black_stocking_result = self._detect_black_stockings(frame)
                results['black_stockings'].append(black_stocking_result)
                
                # 肤色分析
                skin_result = self._detect_skin_tone(frame)
                results['skin_analysis'].append(skin_result)
                
                # 服装颜色
                color_result = self._detect_clothing_colors(frame)
                results['clothing_colors'].append(color_result)
                
                # 身体比例
                proportion_result = self._detect_body_proportions(frame)
                results['body_proportions'].append(proportion_result)
                
                # 服装形状
                shape_result = self._detect_clothing_shapes(frame)
                results['clothing_shapes'].append(shape_result)
                
                # 织物纹理 - 这是计算密集型操作，减少处理
                if i % 2 == 0:  # 只在偶数帧分析纹理
                    fabric_result = self._detect_fabric_textures(frame)
                    results['fabric_textures'].append(fabric_result)
                
                # 肌肤纹理 - 这是计算密集型操作，减少处理
                if i % 2 == 0:  # 只在偶数帧分析纹理
                    skin_texture_result = self._detect_skin_textures(frame)
                    results['skin_textures'].append(skin_texture_result)
                
            except Exception as e:
                print(f"分析第 {i+1} 帧时出错: {e}")
                continue
        
        # 汇总分析结果
        summary = self._summarize_analysis_results(results)
        
        # 提取视频标题和文件名用于标签生成
        video_filename = os.path.basename(video_path)
        video_title = self._get_video_title_from_db(video_path)
        
        # 生成内容标签
        generated_tags = self._generate_content_tags(summary, video_title, video_filename)
        
        return {
            'video_path': video_path,
            'frames_analyzed': len(frames_to_analyze),
            'detailed_results': results,
            'summary': summary,
            'generated_tags': generated_tags
        }
    
    def _summarize_analysis_results(self, results):
        """
        汇总分析结果
        
        Args:
            results (dict): 详细分析结果
            
        Returns:
            dict: 汇总结果
        """
        summary = {}
        
        # 黑丝检测汇总
        black_stocking_detections = [r for r in results['black_stockings'] if r.get('detected', False)]
        if black_stocking_detections:
            avg_confidence = np.mean([r['confidence'] for r in black_stocking_detections])
            summary['black_stockings'] = {
                'detected': True,
                'confidence': avg_confidence,
                'detection_rate': len(black_stocking_detections) / len(results['black_stockings'])
            }
        else:
            summary['black_stockings'] = {'detected': False, 'confidence': 0.0}
        
        # 肤色分析汇总
        skin_ratios = [r['skin_ratio'] for r in results['skin_analysis'] if 'skin_ratio' in r]
        if skin_ratios:
            avg_skin_ratio = np.mean(skin_ratios)
            summary['skin_exposure'] = {
                'average_ratio': avg_skin_ratio,
                'high_exposure': avg_skin_ratio > 0.25,
                'moderate_exposure': 0.15 < avg_skin_ratio <= 0.25
            }
        
        # 服装颜色汇总
        color_summary = defaultdict(list)
        for color_result in results['clothing_colors']:
            for color, stats in color_result.items():
                if isinstance(stats, dict) and stats.get('dominant', False):
                    color_summary[color].append(stats['ratio'])
        
        dominant_colors = []
        for color, ratios in color_summary.items():
            if len(ratios) > len(results['clothing_colors']) * 0.3:  # 出现在30%以上的帧中
                dominant_colors.append({
                    'color': color,
                    'average_ratio': np.mean(ratios),
                    'frequency': len(ratios) / len(results['clothing_colors'])
                })
        
        summary['dominant_colors'] = dominant_colors
        
        # 身体比例汇总
        body_detections = [r for r in results['body_proportions'] if r.get('detected', False)]
        if body_detections:
            avg_confidence = np.mean([r['confidence'] for r in body_detections])
            summary['body_features'] = {
                'detected': True,
                'confidence': avg_confidence,
                'detection_rate': len(body_detections) / len(results['body_proportions'])
            }
        else:
            summary['body_features'] = {'detected': False}
        
        # 纹理分析汇总
        textured_frames = [r for r in results['fabric_textures'] if r.get('is_textured', False)]
        summary['fabric_texture'] = {
            'is_textured': len(textured_frames) > len(results['fabric_textures']) * 0.5,
            'texture_frequency': len(textured_frames) / len(results['fabric_textures']) if results['fabric_textures'] else 0
        }
        
        return summary
    
    def load_vocabulary_tags(self, vocab_file="vocabulary_tags.txt"):
        """
        从词汇文件中加载标签词汇（每行一个词汇）
        
        Args:
            vocab_file (str): 词汇文件路径
            
        Returns:
            list: 标签词汇列表
        """
        vocabulary_tags = []
        
        try:
            if not os.path.exists(vocab_file):
                print(f"词汇文件不存在: {vocab_file}")
                return []
            
            with open(vocab_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 读取每行词汇
            for line in lines:
                word = line.strip()
                if word and word not in vocabulary_tags:
                    vocabulary_tags.append(word)
            
            print(f"成功加载 {len(vocabulary_tags)} 个词汇标签")
            return vocabulary_tags
            
        except Exception as e:
            print(f"加载词汇标签失败: {e}")
            return []
    
    def _generate_content_tags(self, summary, video_title="", video_filename=""):
        """
        基于分析结果和词汇表生成内容标签
        
        Args:
            summary (dict): 分析结果汇总
            video_title (str): 视频标题
            video_filename (str): 视频文件名
            
        Returns:
            list: 生成的标签列表
        """
        tags = []
        
        # 加载词汇标签
        vocabulary_tags = self.load_vocabulary_tags()
        
        # 基于视觉检测的标签映射
        visual_tag_mapping = {
            # 黑丝检测映射到词汇表中的相关词汇
            'black_stockings': ['黑丝', '丝袜', '黑色', 'OL', '职业装', '办公室'],
            # 肌肤暴露映射
            'skin_exposure': ['身材', '巨乳', '大奶', '露脸', '颜值'],
            # 颜色映射
            'black_clothing': ['黑丝', '黑色', 'OL', '职业装'],
            'red_clothing': ['红色'],
            'white_clothing': ['白色', '职业装'],
            # 身材特征映射
            'body_features': ['身材', '巨乳', '大奶', '极品', '女神', '颜值'],
            # 职业装检测映射
            'professional_attire': ['OL', '职业装', '办公室', '秘书', '上司'],
            # 强制场景映射
            'forced_scenario': ['凌辱', '强暴', '屈辱', '變態']
        }
        
        # 1. 基于视觉检测结果匹配词汇标签
        
        # 黑丝检测
        if summary.get('black_stockings', {}).get('detected', False):
            confidence = summary['black_stockings']['confidence']
            if confidence > 0.5:
                for tag in visual_tag_mapping['black_stockings']:
                    if tag in vocabulary_tags:
                        tags.append(tag)
        
        # 肌肤暴露检测
        skin_info = summary.get('skin_exposure', {})
        if skin_info.get('high_exposure', False) or skin_info.get('moderate_exposure', False):
            for tag in visual_tag_mapping['skin_exposure']:
                if tag in vocabulary_tags:
                    tags.append(tag)
        
        # 颜色检测
        dominant_colors = summary.get('dominant_colors', [])
        for color_info in dominant_colors:
            color = color_info['color']
            frequency = color_info['frequency']
            if frequency > 0.4:  # 降低阈值以增加匹配
                if color == 'black':
                    for tag in visual_tag_mapping['black_clothing']:
                        if tag in vocabulary_tags:
                            tags.append(tag)
        
        # 身材特征检测
        body_features = summary.get('body_features', {})
        if body_features.get('detected', False):
            confidence = body_features.get('confidence', 0)
            if confidence > 0.4:  # 降低阈值
                for tag in visual_tag_mapping['body_features']:
                    if tag in vocabulary_tags:
                        tags.append(tag)
        
        # 2. 基于标题和文件名的文本匹配
        text_content = f"{video_title} {video_filename}".lower()
        
        # 番号特征提取
        av_tags = self._extract_from_av_code(video_filename)
        for tag in av_tags:
            if tag in vocabulary_tags and tag not in tags:
                tags.append(tag)
        
        # 直接匹配词汇表中的词汇
        for vocab_tag in vocabulary_tags:
            if vocab_tag in text_content:
                if vocab_tag not in tags:
                    tags.append(vocab_tag)
        
        # 3. 基于视觉特征的推理标签
        # 如果检测到大面积肌肤且有身材特征，推断可能的相关标签
        if (skin_info.get('high_exposure', False) and 
            body_features.get('detected', False)):
            
            inference_tags = ['极品', '女神', '身材', '颜值']
            for tag in inference_tags:
                if tag in vocabulary_tags and tag not in tags:
                    tags.append(tag)
        
        # 4. 特殊检测逻辑
        # 如果检测到黑丝，增加相关标签的权重
        if summary.get('black_stockings', {}).get('detected', False):
            related_tags = ['少妇', '人妻', '熟女', '反差']
            for tag in related_tags:
                if tag in vocabulary_tags and tag not in tags:
                    # 基于置信度决定是否添加
                    confidence = summary['black_stockings']['confidence']
                    if confidence > 0.7:  # 高置信度时添加相关标签
                        tags.append(tag)
        
        # 5. 职业装场景检测
        # 如果检测到黑丝+黑色服装，推断为职业装场景
        if (summary.get('black_stockings', {}).get('detected', False) and 
            any(color['color'] == 'black' and color['frequency'] > 0.5 
                for color in summary.get('dominant_colors', []))):
            
            for tag in visual_tag_mapping['professional_attire']:
                if tag in vocabulary_tags and tag not in tags:
                    tags.append(tag)
        
        # 6. 基于文件路径的语义推断
        # 从文件路径中提取语义信息
        if video_filename or video_title:
            full_text = f"{video_filename} {video_title}".lower()
            
            # 检测强制场景关键词
            force_keywords = ['討厭', '屈辱', '強暴', '變態', '凌辱', '强暴']
            if any(keyword.lower() in full_text for keyword in force_keywords):
                for tag in visual_tag_mapping['forced_scenario']:
                    if tag in vocabulary_tags and tag not in tags:
                        tags.append(tag)
            
            # 检测职场/办公室场景关键词
            office_keywords = ['上司', '秘书', '办公', 'ol', 'office']
            if any(keyword.lower() in full_text for keyword in office_keywords):
                for tag in visual_tag_mapping['professional_attire']:
                    if tag in vocabulary_tags and tag not in tags:
                        tags.append(tag)
        
        # 去重并返回
        return list(set(tags))
    
    def _extract_from_av_code(self, filename):
        """
        从AV番号中提取特征词汇
        
        Args:
            filename (str): 文件名
            
        Returns:
            list: 提取的特征词汇列表
        """
        import re
        
        features = []
        
        # 番号前缀到特征的映射
        av_code_mapping = {
            # 强制/凌辱系列
            'SHKD': ['强奸', '凌辱', '屈辱', '强暴'],
            'RBD': ['强奸', '凌辱', '屈辱'],
            'ATID': ['凌辱', '屈辱'],
            'JBD': ['凌辱', '束缚'],
            'SSPD': ['凌辱', '强暴'],
            'IESP': ['凌辱', '屈辱'],
            
            # 人妻/熟女系列
            'JUX': ['人妻', '熟女'],
            'JUY': ['人妻', '熟女'],
            'JUL': ['人妻', '熟女'],
            'MEYD': ['人妻', '熟女'],
            'MDYD': ['人妻', '熟女'],
            'SPRD': ['人妻', '熟女'],
            
            # VR系列
            'VR': ['VR'],
            'VRTM': ['VR'],
            'CRVR': ['VR'],
            
            # 其他特殊系列
            'MIRD': ['多人', '群交'],
            'MIAE': ['美少女'],
            'MIAE': ['学生'],
        }
        
        # 职业相关番号映射
        profession_mapping = {
            'SHKD': ['护士'],  # SHKD-515特指护士，不应包含老师和秘书
            'RBD': ['护士', '老师'],
            'ATID': ['OL', '秘书'],
            'JUX': ['人妻'],
            'JUY': ['人妻'],
            'JUL': ['人妻'],
        }
        
        # 使用正则表达式匹配番号格式
        av_pattern = r'([A-Z]+)[-_]?(\d+)'
        matches = re.findall(av_pattern, filename.upper())
        
        for prefix, number in matches:
            # 添加基本特征
            if prefix in av_code_mapping:
                features.extend(av_code_mapping[prefix])
            
            # 添加职业相关特征
            if prefix in profession_mapping:
                features.extend(profession_mapping[prefix])
        
        return list(set(features))  # 去重
    
    def _get_video_title_from_db(self, video_path):
        """
        从数据库中获取视频标题
        
        Args:
            video_path (str): 视频文件路径
            
        Returns:
            str: 视频标题
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT title FROM videos WHERE file_path = ?", (video_path,))
            result = cursor.fetchone()
            conn.close()
            
            return result[0] if result and result[0] else ""
            
        except Exception as e:
            print(f"获取视频标题失败: {e}")
            return ""
    
    def get_test_videos(self, limit=3):
        """
        获取用于测试的大视频文件
        
        Args:
            limit (int): 返回的视频数量
            
        Returns:
            list: 视频信息列表
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, file_name, file_path, file_size, title, tags 
                FROM videos 
                WHERE file_size IS NOT NULL AND file_size > 1000000000
                ORDER BY file_size DESC 
                LIMIT ?
            """, (limit,))
            
            videos = cursor.fetchall()
            conn.close()
            
            return videos
            
        except Exception as e:
            print(f"获取测试视频失败：{e}")
            return []
    
    def update_video_content_tags(self, video_id, content_tags):
        """
        更新视频的内容标签
        
        Args:
            video_id (int): 视频ID
            content_tags (list): 内容标签列表
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 获取现有标签
            cursor.execute("SELECT tags FROM videos WHERE id = ?", (video_id,))
            result = cursor.fetchone()
            existing_tags = result[0] if result and result[0] else ""
            
            # 合并标签
            existing_set = set([tag.strip() for tag in existing_tags.split(',') if tag.strip()])
            new_set = set(content_tags)
            all_tags = existing_set.union(new_set)
            
            # 更新数据库
            final_tags = ', '.join(sorted(all_tags))
            cursor.execute(
                "UPDATE videos SET tags = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (final_tags, video_id)
            )
            
            conn.commit()
            conn.close()
            
            print(f"视频 {video_id} 的标签已更新: {final_tags}")
            
        except Exception as e:
            print(f"更新视频内容标签失败 (ID: {video_id}): {e}")
    
    def single_file_mode(self, auto_update=False, file_paths=None):
        """
        单文件模式 - 分析单个或多个视频文件
        
        Args:
            auto_update (bool): 是否自动更新标签，不询问用户
            file_paths (str): 预设的文件路径，用分号分隔
        """
        if file_paths:
            input_paths = file_paths
        else:
            print("请输入视频文件路径（多个文件用分号;分隔）:")
            input_paths = input().strip()
        
        if not input_paths:
            print("未输入文件路径")
            return
        
        # 解析文件路径
        video_paths = [path.strip() for path in input_paths.split(';') if path.strip()]
        
        if not video_paths:
            print("未找到有效的文件路径")
            return
        
        print(f"\n准备分析 {len(video_paths)} 个视频文件")
        
        # 连接数据库
        conn = sqlite3.connect('media_library.db')
        cursor = conn.cursor()
        
        try:
            processed = 0
            failed = 0
            
            for i, video_path in enumerate(video_paths, 1):
                print(f"\n[{i}/{len(video_paths)}] 分析视频: {os.path.basename(video_path)}")
                
                if not os.path.exists(video_path):
                    print(f"   ✗ 文件不存在，跳过")
                    failed += 1
                    continue
                
                # 分析视频内容
                start_time = time.time()
                analysis_result = self.analyze_video_content(video_path, min_frames=100, max_interval=10, max_frames=300)
                analysis_time = time.time() - start_time
                
                if 'error' in analysis_result:
                    print(f"   ✗ 分析失败: {analysis_result['error']}")
                    failed += 1
                    continue
                
                # 显示分析结果
                generated_tags = analysis_result['generated_tags']
                
                print(f"   ✓ 分析完成，耗时 {analysis_time:.1f} 秒")
                print(f"   分析帧数：{analysis_result['frames_analyzed']}")
                print(f"   生成标签：{', '.join(generated_tags) if generated_tags else '无'}")
                
                # 查找视频记录
                cursor.execute("SELECT id, tags FROM videos WHERE file_path = ?", (video_path,))
                video_record = cursor.fetchone()
                
                if not video_record:
                    print(f"   ⚠ 该视频不在数据库中，无法更新标签")
                    continue
                
                video_id, existing_tags = video_record
                print(f"   现有标签：{existing_tags or '无'}")
                
                # 更新标签
                if generated_tags:
                    if auto_update:
                        self.update_video_content_tags(video_id, generated_tags)
                        print(f"   ✓ 内容标签已更新")
                        processed += 1
                    else:
                        update = input(f"   是否更新内容标签？(y/n): ").lower().strip()
                        if update == 'y':
                            self.update_video_content_tags(video_id, generated_tags)
                            print(f"   ✓ 内容标签已更新")
                            processed += 1
                        else:
                            print(f"   - 跳过更新")
                else:
                    print(f"   - 未生成新标签")
            
            print(f"\n处理完成：")
            print(f"  成功处理: {processed} 个视频")
            print(f"  失败: {failed} 个视频")
                
        except Exception as e:
            print(f"处理过程中发生错误: {e}")
        finally:
            conn.close()
    
    def no_tags_update_mode(self, progress_callback=None):
        """
        无标签更新模式 - 更新所有没有标签的视频
        
        Args:
            progress_callback (function): 进度回调函数，接收 (current, total, message) 参数
        """
        print("\n开始无标签更新模式...")
        
        # 连接数据库
        conn = sqlite3.connect('media_library.db')
        cursor = conn.cursor()
        
        try:
            # 查询没有标签的视频
            cursor.execute("""
                SELECT id, file_path, title 
                FROM videos 
                WHERE tags IS NULL OR tags = '' OR TRIM(tags) = ''
                ORDER BY id
            """)
            
            videos = cursor.fetchall()
            
            if not videos:
                print("所有视频都已有标签")
                if progress_callback:
                    progress_callback(0, 0, "所有视频都已有标签")
                return
            
            print(f"找到 {len(videos)} 个没有标签的视频")
            if progress_callback:
                progress_callback(0, len(videos), f"找到 {len(videos)} 个没有标签的视频")
            
            processed = 0
            failed = 0
            
            for i, (video_id, file_path, title) in enumerate(videos, 1):
                current_file = os.path.basename(file_path)
                print(f"\n[{i}/{len(videos)}] 处理视频: {current_file}")
                
                if progress_callback:
                    progress_callback(i-1, len(videos), f"正在处理: {current_file}")
                
                if not os.path.exists(file_path):
                    print(f"   ✗ 文件不存在，跳过")
                    failed += 1
                    continue
                
                # 分析视频内容
                analysis_result = self.analyze_video_content(file_path, min_frames=100, max_interval=10, max_frames=300)
                
                if 'error' in analysis_result:
                    print(f"   ✗ 分析失败: {analysis_result['error']}")
                    failed += 1
                    continue
                
                generated_tags = analysis_result['generated_tags']
                if generated_tags:
                    # 直接更新标签，无需确认
                    self.update_video_content_tags(video_id, generated_tags)
                    print(f"   ✓ 已添加标签: {', '.join(generated_tags)}")
                    processed += 1
                else:
                    print(f"   - 未生成标签")
            
            final_message = f"处理完成 - 成功: {processed}, 失败: {failed}"
            print(f"\n处理完成：")
            print(f"  成功处理: {processed} 个视频")
            print(f"  失败: {failed} 个视频")
            
            if progress_callback:
                progress_callback(len(videos), len(videos), final_message)
            
        except Exception as e:
            error_msg = f"处理过程中发生错误: {e}"
            print(error_msg)
            if progress_callback:
                progress_callback(-1, -1, error_msg)
        finally:
            conn.close()
    
    def full_update_mode(self, progress_callback=None, auto_confirm=False):
        """
        全部更新模式 - 更新数据库全部视频标签
        
        Args:
            progress_callback (function): 进度回调函数，接收 (current, total, message) 参数
            auto_confirm (bool): 是否自动确认，跳过用户确认步骤
        """
        print("\n开始全部更新模式...")
        print("警告：此操作将重新分析所有视频并更新标签")
        
        if not auto_confirm:
            confirm = input("确认继续？(y/n): ").strip().lower()
            if confirm != 'y':
                print("操作已取消")
                if progress_callback:
                    progress_callback(-1, -1, "操作已取消")
                return
        
        # 连接数据库
        conn = sqlite3.connect('media_library.db')
        cursor = conn.cursor()
        
        try:
            # 查询所有视频
            cursor.execute("""
                SELECT id, file_path, title, tags 
                FROM videos 
                ORDER BY id
            """)
            
            videos = cursor.fetchall()
            
            if not videos:
                print("数据库中没有视频记录")
                if progress_callback:
                    progress_callback(0, 0, "数据库中没有视频记录")
                return
            
            print(f"找到 {len(videos)} 个视频，开始批量处理...")
            if progress_callback:
                progress_callback(0, len(videos), f"找到 {len(videos)} 个视频，开始批量处理")
            
            processed = 0
            failed = 0
            updated = 0
            
            for i, (video_id, file_path, title, current_tags) in enumerate(videos, 1):
                current_file = os.path.basename(file_path)
                print(f"\n[{i}/{len(videos)}] 处理视频: {current_file}")
                
                if progress_callback:
                    progress_callback(i-1, len(videos), f"正在处理: {current_file}")
                
                if not os.path.exists(file_path):
                    print(f"   ✗ 文件不存在，跳过")
                    failed += 1
                    continue
                
                # 分析视频内容
                analysis_result = self.analyze_video_content(file_path, min_frames=100, max_interval=10, max_frames=300)
                
                if 'error' in analysis_result:
                    print(f"   ✗ 分析失败: {analysis_result['error']}")
                    failed += 1
                    continue
                
                processed += 1
                
                generated_tags = analysis_result['generated_tags']
                if generated_tags:
                    # 合并现有标签和新标签
                    existing_tags = set(tag.strip() for tag in (current_tags or '').split(',') if tag.strip())
                    new_tags = set(generated_tags)
                    all_tags = existing_tags.union(new_tags)
                    
                    # 更新标签
                    tags_str = ', '.join(sorted(all_tags))
                    cursor.execute("UPDATE videos SET tags = ? WHERE id = ?", (tags_str, video_id))
                    conn.commit()
                    
                    print(f"   ✓ 已更新标签: {tags_str}")
                    updated += 1
                else:
                    print(f"   - 未生成新标签")
            
            final_message = f"批量处理完成 - 总数: {len(videos)}, 成功: {processed}, 更新: {updated}, 失败: {failed}"
            print(f"\n批量处理完成：")
            print(f"  总视频数: {len(videos)}")
            print(f"  成功分析: {processed} 个")
            print(f"  更新标签: {updated} 个")
            print(f"  失败: {failed} 个")
            
            if progress_callback:
                progress_callback(len(videos), len(videos), final_message)
            
        except Exception as e:
            error_msg = f"处理过程中发生错误: {e}"
            print(error_msg)
            if progress_callback:
                progress_callback(-1, -1, error_msg)
        finally:
            conn.close()
    

    
    def generate_content_analysis_report(self, results):
        """
        生成内容分析测试报告
        
        Args:
            results (list): 测试结果列表
        """
        report_file = f"content_analysis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        # 准备报告数据
        report_data = {
            'test_time': datetime.now().isoformat(),
            'total_videos': len(results),
            'results': []
        }
        
        for result in results:
            analysis = result['analysis_result']
            summary = analysis.get('summary', {})
            
            report_data['results'].append({
                'video_id': result['video_id'],
                'file_name': result['file_name'],
                'frames_analyzed': analysis.get('frames_analyzed', 0),
                'analysis_time': result['analysis_time'],
                'black_stockings_detected': summary.get('black_stockings', {}).get('detected', False),
                'skin_exposure_ratio': summary.get('skin_exposure', {}).get('average_ratio', 0),
                'dominant_colors': [c['color'] for c in summary.get('dominant_colors', [])],
                'generated_tags': analysis.get('generated_tags', [])
            })
        
        # 保存JSON报告
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n内容分析报告已保存到：{report_file}")
        
        # 生成文本摘要
        summary_file = f"content_analysis_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write("视频内容分析测试摘要\n")
            f.write("=" * 50 + "\n")
            f.write(f"测试时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"测试视频数量：{len(results)}\n")
            f.write("\n")
            
            # 统计信息
            total_time = sum(r['analysis_time'] for r in results)
            avg_time = total_time / len(results) if results else 0
            
            black_stocking_count = sum(1 for r in results 
                                     if r['analysis_result'].get('summary', {}).get('black_stockings', {}).get('detected', False))
            
            f.write("统计信息\n")
            f.write("-" * 30 + "\n")
            f.write(f"总分析时间：{total_time:.1f} 秒\n")
            f.write(f"平均分析时间：{avg_time:.1f} 秒/视频\n")
            f.write(f"黑丝检测成功：{black_stocking_count}/{len(results)}\n")
            f.write("\n")
            
            # 详细结果
            f.write("详细结果\n")
            f.write("-" * 30 + "\n")
            for i, result in enumerate(results, 1):
                analysis = result['analysis_result']
                summary = analysis.get('summary', {})
                
                f.write(f"{i}. {result['file_name']}\n")
                f.write(f"   分析时间：{result['analysis_time']:.1f} 秒\n")
                f.write(f"   分析帧数：{analysis.get('frames_analyzed', 0)}\n")
                
                # 检测结果
                black_stockings = summary.get('black_stockings', {})
                if black_stockings.get('detected', False):
                    f.write(f"   黑丝检测：✓ (置信度: {black_stockings['confidence']:.2f})\n")
                else:
                    f.write(f"   黑丝检测：❌\n")
                
                skin_exposure = summary.get('skin_exposure', {})
                if skin_exposure:
                    ratio = skin_exposure.get('average_ratio', 0)
                    f.write(f"   肌肤暴露：{ratio:.2f} ({ratio*100:.1f}%)\n")
                
                generated_tags = analysis.get('generated_tags', [])
                f.write(f"   生成标签：{', '.join(generated_tags) if generated_tags else '无'}\n")
                f.write("\n")
        
        print(f"内容分析摘要已保存到：{summary_file}")

def main():
    """
    主函数
    """
    print("视频内容特征分析器")
    print("=" * 30)
    
    # 检查必要文件
    if not os.path.exists("media_library.db"):
        print("错误：找不到数据库文件 media_library.db")
        return
    
    # 检查OpenCV
    try:
        import cv2
        print(f"OpenCV版本：{cv2.__version__}")
    except ImportError:
        print("错误：未安装OpenCV，请运行 pip install opencv-python")
        return
    
    # 创建分析器
    analyzer = VideoContentAnalyzer()
    
    print("\n选择操作模式：")
    print("1. 单文件模式 - 分析单个视频文件")
    print("2. 无标签更新模式 - 更新所有没有标签的视频")
    print("3. 全部更新模式 - 更新数据库全部视频标签")
    
    choice = input("请选择 (1/2/3): ").strip()
    
    if choice == '1':
        analyzer.single_file_mode()
    elif choice == '2':
        analyzer.no_tags_update_mode()
    elif choice == '3':
        analyzer.full_update_mode()
    else:
        print("无效选择")

if __name__ == "__main__":
    main()