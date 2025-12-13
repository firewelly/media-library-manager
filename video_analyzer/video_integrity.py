#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频完整性检查工具

提供统一的 cv2 基础可播放检查与关键帧跳转(seeking)检测，
用于在分析前快速判定视频是否可靠，避免卡死或长时间重试。
"""

import os
from typing import List

import cv2


def _test_video_seeking(cap: cv2.VideoCapture, frame_count: int,
                        sample_ratios: List[float] = None,
                        tolerance_ratio: float = 0.05) -> bool:
    """测试视频跳转功能，检测是否有 seeking 问题。

    返回 True 表示存在跳转问题，False 表示正常。
    """
    if sample_ratios is None:
        sample_ratios = [0.1, 0.3, 0.5, 0.7, 0.9]

    try:
        # 在若干关键位置进行跳转与读取
        for r in sample_ratios:
            target = max(0, min(frame_count - 1, int(frame_count * r)))
            cap.set(cv2.CAP_PROP_POS_FRAMES, target)
            ret, frame = cap.read()
            if not ret or frame is None:
                return True  # 跳转后读取失败

            actual = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
            if abs(actual - target) > int(frame_count * tolerance_ratio):
                return True  # 跳转位置偏差过大

        return False
    except Exception:
        # 任何异常视为存在问题
        return True


def can_play_video_basic(file_path: str) -> bool:
    """基础可播放检查：能成功打开且帧数>0。"""
    if not os.path.exists(file_path):
        return False
    cap = cv2.VideoCapture(file_path)
    if not cap.isOpened():
        return False
    try:
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        return frame_count > 0
    finally:
        cap.release()


def check_video_integrity(file_path: str, seek_test: bool = True) -> bool:
    """综合完整性检查。

    - 基础可播放检查（打开成功且帧数>0）
    - 可选的关键帧跳转(seeking)检测

    返回 True 表示通过检查；False 表示不通过。
    """
    if not os.path.exists(file_path):
        return False

    cap = cv2.VideoCapture(file_path)
    if not cap.isOpened():
        return False

    try:
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if frame_count <= 0:
            return False

        if seek_test:
            has_issue = _test_video_seeking(cap, frame_count)
            if has_issue:
                return False

        return True
    except Exception:
        return False
    finally:
        cap.release()