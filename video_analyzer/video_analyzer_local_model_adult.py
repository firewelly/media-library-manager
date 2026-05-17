#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地模型成人视频分析器（优化版）
专门针对成人视频和成人电影的内容理解和标签打分
使用本地部署的minicpm-v-4.6 abliterated模型

作者: AI Assistant
创建时间: 2026-05-15
"""

import cv2
try:
    from .video_integrity import check_video_integrity
except ImportError:
    from video_integrity import check_video_integrity
import base64
import json
import os
import random
import requests
from typing import List, Dict, Any, Optional
import time
from PIL import Image
import io
import argparse
try:
    from .config import video_config, file_config
except ImportError:
    from config import video_config, file_config


class VideoAnalyzerLocalModelAdult:
    def __init__(self, 
                 api_base_url: str = "https://api.siliconflow.cn",
                 model_name: str = "Qwen/Qwen3-VL-30B-A3B-Instruct",
                 api_key: str = None,
                 tags_file: str = None,
                 verbose: bool = True):
        """
        初始化成人视频分析器
        
        Args:
            api_base_url: 本地模型API地址
            model_name: 模型名称
            tags_file: 标签词汇文件路径
            verbose: 是否显示详细输出
        """
        self.api_base_url = api_base_url
        self.model_name = model_name
        self.api_key = api_key or os.getenv("SILICONFLOW_API_KEY")
        if not self.api_key:
            raise ValueError("API密钥未设置。请通过参数传入或设置环境变量 SILICONFLOW_API_KEY")
        self.max_frames = video_config.DEFAULT_MAX_FRAMES
        self.long_video_threshold = 600  # 10分钟 = 600秒
        self.tags_file = tags_file or file_config.VOCABULARY_TAGS_FILE
        self.verbose = verbose
        self.vocabulary_tags = self._load_vocabulary_tags()
        
    def _load_vocabulary_tags(self) -> List[str]:
        """
        从文件中加载标签词汇表
        
        Returns:
            标签列表
        """
        try:
            if os.path.exists(self.tags_file):
                with open(self.tags_file, 'r', encoding='utf-8') as f:
                    tags = [line.strip() for line in f.readlines() if line.strip()]
                if self.verbose:
                    print(f"✅ 成功加载 {len(tags)} 个标签从文件: {self.tags_file}")
                return tags
            else:
                if self.verbose:
                    print(f"⚠️  标签文件不存在: {self.tags_file}，使用默认标签")
                return ["少妇", "人妻", "熟女", "巨乳", "黑丝", "丝袜", "性感"]
        except Exception as e:
            if self.verbose:
                print(f"❌ 读取标签文件失败: {e}，使用默认标签")
            return ["少妇", "人妻", "熟女", "巨乳", "黑丝", "丝袜", "性感"]
    
    def _compress_image(self, image_data: bytes, max_size_mb: float = 0.4,
                       target_width: int = 640) -> bytes:
        """
        压缩图片以减少token消耗
        
        Args:
            image_data: 原始图片数据
            max_size_mb: 最大文件大小（MB）
            target_width: 目标宽度
            
        Returns:
            压缩后的图片数据
        """
        max_size_mb = max_size_mb or video_config.MAX_IMAGE_SIZE_MB
        target_width = target_width or video_config.TARGET_WIDTH
        try:
            image = Image.open(io.BytesIO(image_data))
            
            width, height = image.size
            if width > target_width:
                ratio = target_width / width
                new_height = int(height * ratio)
                image = image.resize((target_width, new_height), Image.Resampling.LANCZOS)
            
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            output = io.BytesIO()
            quality = 85
            while quality > 20:
                output.seek(0)
                output.truncate()
                image.save(output, format='JPEG', quality=quality, optimize=True)
                
                size_mb = len(output.getvalue()) / (1024 * 1024)
                if size_mb <= max_size_mb:
                    break
                quality -= 10
            
            compressed_data = output.getvalue()
            original_size = len(image_data) / (1024 * 1024)
            compressed_size = len(compressed_data) / (1024 * 1024)
            
            if self.verbose:
                print(f"图片压缩: {original_size:.2f}MB -> {compressed_size:.2f}MB")
            return compressed_data
            
        except Exception as e:
            if self.verbose:
                print(f"图片压缩失败: {e}")
            return image_data

    def extract_frames(self, video_path: str, num_frames: int = None, 
                      interval_seconds: float = 3.0) -> List[str]:
        """
        从视频中提取帧
        - 超过10分钟的视频：按每分钟1帧，最多30帧
        - 10分钟以内的视频：固定8帧
        
        Args:
            video_path: 视频文件路径
            num_frames: 指定提取的帧数（如果为None则根据时长动态计算）
            interval_seconds: 帧间隔时间（秒），仅当num_frames为None且视频较短时使用
            
        Returns:
            base64编码的帧图片列表
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"视频文件不存在: {video_path}")

        try:
            enable_check = getattr(video_config, 'ENABLE_INTEGRITY_CHECK', True)
            seek_test = getattr(video_config, 'INTEGRITY_SEEK_TEST', True)
        except Exception:
            enable_check, seek_test = True, True
        if enable_check:
            ok = check_video_integrity(video_path, seek_test=seek_test)
            if not ok:
                raise ValueError(f"视频完整性检查未通过: {video_path}")
        
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"无法打开视频文件: {video_path}")
        
        try:
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            duration = total_frames / fps if fps > 0 else 0
            
            if self.verbose:
                print(f"视频信息: 总帧数={total_frames}, FPS={fps:.2f}, 时长={duration:.2f}秒")
            
            if num_frames is None:
                if duration > self.long_video_threshold:
                    num_frames = min(max(1, int(duration / 60)), self.max_frames)
                else:
                    num_frames = min(8, self.max_frames)
            else:
                num_frames = min(num_frames, self.max_frames)
            
            if self.verbose:
                print(f"计划提取 {num_frames} 帧 (最大限制: {self.max_frames})")
            
            overall_deadline = time.time() + getattr(video_config, 'FRAME_EXTRACT_TIMEOUT', 30)
            max_failures = getattr(video_config, 'FRAME_READ_MAX_FAILS', 8)
            consecutive_failures = 0

            frames_base64 = []

            use_sequential_read = (total_frames <= 0) or (fps is None) or (fps <= 0)
            if use_sequential_read and self.verbose:
                print("检测到视频元信息异常，启用顺序读取回退模式")

            if not use_sequential_read:
                if total_frames <= 1 or duration <= 1.0:
                    frame_indices = [total_frames // 2]
                    if self.verbose:
                        print("视频过短，仅提取中间帧")
                else:
                    if num_frames >= total_frames:
                        frame_indices = list(range(0, total_frames, max(1, total_frames // num_frames)))
                    else:
                        step = total_frames / num_frames
                        frame_indices = [int(i * step) for i in range(num_frames)]

                frame_indices = frame_indices[:self.max_frames]

                for frame_idx in frame_indices:
                    if time.time() >= overall_deadline:
                        if self.verbose:
                            print("帧提取达到超时，提前结束")
                        break

                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                    ret, frame = cap.read()
                    
                    if ret:
                        consecutive_failures = 0
                        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                        compressed_data = self._compress_image(buffer.tobytes())
                        frame_base64 = base64.b64encode(compressed_data).decode('utf-8')
                        frames_base64.append(frame_base64)
                        time_point = frame_idx / fps if fps and fps > 0 else 0
                        if self.verbose:
                            compressed_size = len(compressed_data) / (1024 * 1024)
                            print(f"提取第 {frame_idx} 帧 (时间: {time_point:.2f}s, 压缩后: {compressed_size:.2f}MB)")
                    else:
                        consecutive_failures += 1
                        if self.verbose:
                            print(f"警告: 无法读取第 {frame_idx} 帧 (连续失败 {consecutive_failures}/{max_failures})")
                        if consecutive_failures >= max_failures:
                            if self.verbose:
                                print("连续读取失败过多，提前结束")
                            break
            else:
                while (len(frames_base64) < num_frames) and (time.time() < overall_deadline):
                    ret, frame = cap.read()
                    if not ret:
                        consecutive_failures += 1
                        if self.verbose:
                            print(f"警告: 顺序读取失败 (连续失败 {consecutive_failures}/{max_failures})")
                        if consecutive_failures >= max_failures:
                            if self.verbose:
                                print("顺序读取失败过多，结束提取")
                            break
                        continue
                    consecutive_failures = 0
                    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    compressed_data = self._compress_image(buffer.tobytes())
                    frame_base64 = base64.b64encode(compressed_data).decode('utf-8')
                    frames_base64.append(frame_base64)
                
                if time.time() >= overall_deadline and self.verbose:
                    print("顺序读取模式达到超时，提前结束提取")
            
            if self.verbose:
                print(f"成功提取 {len(frames_base64)} 帧")
            return frames_base64
            
        finally:
            cap.release()

    def extract_frames_random(self, video_path: str, num_frames: int = 30) -> List[str]:
        """
        从视频中随机分布提取指定数量的帧
        用于重分析场景：当均匀采样无法获得有效标签时，尝试随机采样获取更多内容
        
        Args:
            video_path: 视频文件路径
            num_frames: 提取帧数，默认30
            
        Returns:
            base64编码的帧图片列表
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"视频文件不存在: {video_path}")

        try:
            enable_check = getattr(video_config, 'ENABLE_INTEGRITY_CHECK', True)
            seek_test = getattr(video_config, 'INTEGRITY_SEEK_TEST', True)
        except Exception:
            enable_check, seek_test = True, True
        if enable_check:
            ok = check_video_integrity(video_path, seek_test=seek_test)
            if not ok:
                raise ValueError(f"视频完整性检查未通过: {video_path}")

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"无法打开视频文件: {video_path}")

        try:
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            duration = total_frames / fps if fps > 0 else 0

            if self.verbose:
                print(f"随机帧提取: 总帧数={total_frames}, FPS={fps:.2f}, 时长={duration:.2f}秒, 目标帧数={num_frames}")

            if total_frames <= 1 or duration <= 1.0:
                frame_indices = [total_frames // 2]
            elif num_frames >= total_frames:
                frame_indices = sorted(random.sample(range(total_frames), min(num_frames, total_frames)))
            else:
                margin = total_frames * 0.05
                start = int(margin)
                end = int(total_frames - margin)
                usable_range = end - start
                if usable_range <= num_frames:
                    frame_indices = sorted(random.sample(range(start, end), min(num_frames, usable_range)))
                else:
                    frame_indices = sorted(random.sample(range(start, end), num_frames))

            overall_deadline = time.time() + 60
            max_failures = 8
            consecutive_failures = 0
            frames_base64 = []

            for frame_idx in frame_indices:
                if time.time() >= overall_deadline:
                    if self.verbose:
                        print("随机帧提取达到超时，提前结束")
                    break

                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, frame = cap.read()

                if ret:
                    consecutive_failures = 0
                    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    compressed_data = self._compress_image(buffer.tobytes())
                    frame_base64 = base64.b64encode(compressed_data).decode('utf-8')
                    frames_base64.append(frame_base64)
                    if self.verbose:
                        time_point = frame_idx / fps if fps and fps > 0 else 0
                        print(f"随机提取第 {frame_idx} 帧 (时间: {time_point:.2f}s)")
                else:
                    consecutive_failures += 1
                    if self.verbose:
                        print(f"警告: 无法读取第 {frame_idx} 帧 (连续失败 {consecutive_failures}/{max_failures})")
                    if consecutive_failures >= max_failures:
                        break

            if self.verbose:
                print(f"随机帧提取完成: 成功 {len(frames_base64)}/{len(frame_indices)} 帧")
            return frames_base64

        finally:
            cap.release()

    def _generate_analysis_prompt_adult(self, video_path: Optional[str] = None) -> str:
        """
        生成成人视频分析提示词（优化版）
        
        Args:
            video_path: 视频文件路径（用于提取标题信息）
            
        Returns:
            分析提示词
        """
        tags_str = "、".join(self.vocabulary_tags)
        title = None
        if video_path:
            try:
                title = os.path.splitext(os.path.basename(video_path))[0]
            except Exception:
                title = None
        
        title_line = f"视频标题/文件名提示：{title}\n\n" if title else ""

        prompt = f"""{title_line}你是一个专业的成人视频内容分析专家。请仔细观察这组从视频中提取的画面，进行深入的内容理解和剧情分析。

⚠️ **重要规则：只关注女性主角的特征，完全忽略男性人物！所有分析都针对女性主角。**

请从以下几个维度进行详细分析（仅针对女性主角）：

**1. 女性主角形象深度描述**
- 年龄特征（少女/大学生/少妇/熟女/阿姨等年龄段判断）
- 身材体型（苗条/丰满/微胖/娇小/高大，是否有巨乳/大奶特征）
- 外貌特征（发型：长发/短发/卷发/马尾/双马尾，妆容：浓妆/淡妆/素颜，是否有红唇特征）
- 整体颜值水平（高颜值/漂亮/性感/清纯等）
- 气质风格（女神/御姐/小姐姐/骚货/良家等）

**2. 女性服装穿着详细分析**
- 主要服装类型（制服/和服/比基尼/内衣/睡衣/运动装/旗袍/职业装/情趣装等）
- 服装颜色和款式细节
- 丝袜穿着情况（是否穿着、类型：黑丝/白丝/肉丝，款式）
- 内衣细节（文胸款式颜色、内裤款式颜色、丁字裤等）
- 配饰道具（眼镜、眼罩、其他情趣道具等）
- 是否露脸（面部是否清晰可见）

**3. 场景环境识别**
- 场景类型（酒店/浴室/厨房/车内/学校/医院/办公室/野外/会所/按摩/瑜伽场所等）
- 环境布置和氛围营造
- 时间线索（白天/夜晚）
- 场景转换情况

**4. 情节和剧情分析（仅针对女性主角的身份和关系）**
- 女性主角身份和职业（护士/医生/律师/警察/教授/秘书/空姐/OL/主播/模特/女技师/老师/学生等）
- 女性主角的人物关系（人妻/老婆/女友/闺蜜/上司/已婚/良家等）
- 情节类型（偷情/出轨/绿帽/调教/勾引/约炮/强奸/迷奸/凌辱/屈辱/强暴/换妻等）
- 特殊情节（双飞/群交/一男两女/女同/多人等）
- 情感氛围（淫荡/骚话/对白/淫语等语言特征，淫妻/绿帽等心理元素）

**5. 行为和姿势识别**
- 主要性行为姿势（后入/口交/足交/自慰/打桩等）
- 特殊行为元素（内射/精液/乳汁/哺乳等）
- 行为强度和节奏（温柔/激烈/疯狂等）

**6. 特殊类型识别（仅针对女性主角）**
- 特殊人物类型（人妖/孕妇/萝莉等）
- 特殊场景元素（野外/车内/浴室等）
- 特殊服装道具（制服诱惑/情趣装等）

**7. 关键特征标签提取**
请从以下标签列表中，严格选择最匹配的标签（**最多输出7个，严禁超过7个**）：
{tags_str}

## 标签选择铁律（必须完全遵守）：
- ⚠️ **最多选7个标签，一个都不能多！**
- ⚠️ **只能从上方列表中选，一个字都不能改！**
- ⚠️ **严禁添加任何解释、说明、括号、注释**
- ⚠️ **严禁输出"注"、"筛选"、"最终"等无关文字**
- ⚠️ **如果列表中没有匹配项，请只输出"无匹配标签"这五个字**
- ⚠️ **标签之间使用英文逗号分隔，不要顿号，不要空格**
- ⚠️ **所有标签都只针对女性主角的特征！**

## 标签优先级（必须严格遵守）：
- **特殊特征优先**：哺乳、乳汁、孕妇、萝莉、人妖等特殊特征标签优先级最高，必须优先选择！
- **服装特征次之**：黑丝、制服、情趣装、丝袜、眼镜等服装特征
- **情节特征**：偷情、出轨、调教、绿帽等情节特征
- **人物特征**：少妇、人妻、熟女、巨乳等人物特征
- **行为特征（最低）**：自慰、口交、后入、内射等行为特征（优先级最低）

## 输出格式（必须完全遵守）：
请按以下结构严格输出，每个【】段内容控制在50字以内，或写"无"：

【女性主角】（描述年龄、身材、气质，20字以内）
【服装穿着】（描述服装类型、丝袜、眼镜等，20字以内）
【场景环境】（描述场景类型，20字以内）
【情节剧情】（描述人物关系、情节类型，20字以内）
【行为姿势】（描述主要行为，20字以内）
【匹配标签】（只写逗号分隔的标签，最多7个，严禁任何附加文字）

记住：【匹配标签】行只能出现标签本身，不能有括号、冒号、说明文字。"""
        
        return prompt

    def analyze_frames_with_local_model(self, frames_base64: List[str], 
                                       prompt: str = None) -> Dict[str, Any]:
        """
        使用本地模型分析视频帧
        
        Args:
            frames_base64: base64编码的帧图片列表
            prompt: 自定义分析提示词
            
        Returns:
            分析结果字典
        """
        if not frames_base64:
            return {"success": False, "error": "没有可分析的帧"}
        
        analysis_prompt = prompt or self._generate_analysis_prompt_adult()
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        content = [{"type": "text", "text": analysis_prompt}]
        for frame_b64 in frames_base64:
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{frame_b64}"}
            })

        data = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": content}],
            "max_tokens": 4000,
            "temperature": 0.7,
            "stream": False
        }

        try:
            if self.verbose:
                print(f"正在调用本地模型: {self.model_name}")
                print(f"API地址: {self.api_base_url}")
                print(f"帧数: {len(frames_base64)}")

            response = requests.post(
                f"{self.api_base_url}/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=180
            )

            if response.status_code == 200:
                result = response.json()
                analysis_result = result['choices'][0]['message']['content']
                return {
                    "success": True,
                    "analysis": analysis_result,
                    "raw_response": result,
                    "frames_analyzed": len(frames_base64),
                    "model": self.model_name
                }
            else:
                error_msg = f"API调用失败: {response.status_code} - {response.text}"
                if self.verbose:
                    print(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "raw_response": {"status_code": response.status_code, "text": response.text}
                }

        except Exception as e:
            error_msg = f"API调用异常: {str(e)}"
            if self.verbose:
                print(error_msg)
            return {
                "success": False,
                "error": error_msg
            }

    def analyze_video(self, video_path: str, num_frames: int = None,
                     interval_seconds: float = 3.0, 
                     custom_prompt: str = None) -> Dict[str, Any]:
        """
        分析视频文件
        
        Args:
            video_path: 视频文件路径
            num_frames: 指定提取的帧数
            interval_seconds: 帧间隔时间
            custom_prompt: 自定义分析提示词
            
        Returns:
            完整的分析结果
        """
        try:
            if self.verbose:
                print(f"\n{'='*60}")
                print(f"开始分析成人视频: {video_path}")
                print(f"{'='*60}")
            
            frames_base64 = self.extract_frames(video_path, num_frames, interval_seconds)
            
            if not frames_base64:
                return {
                    "success": False,
                    "error": "未能提取到有效帧"
                }
            
            default_prompt = None if custom_prompt else self._generate_analysis_prompt_adult(video_path)
            analysis_result = self.analyze_frames_with_local_model(
                frames_base64, custom_prompt or default_prompt)
            
            analysis_result["video_path"] = video_path
            analysis_result["frames_extracted"] = len(frames_base64)
            analysis_result["max_frames_limit"] = self.max_frames
            
            return analysis_result
            
        except Exception as e:
            error_msg = f"视频分析失败: {str(e)}"
            if self.verbose:
                print(error_msg)
            return {
                "success": False,
                "error": error_msg
            }

    def extract_tags_from_analysis(self, analysis_result: str) -> List[str]:
        """
        从分析结果中提取匹配的标签，严格清洗格式
        """
        try:
            tags_text = ""
            if "【匹配标签】" in analysis_result:
                tags_text = analysis_result.split("【匹配标签】")[1].strip()
            elif "匹配标签：" in analysis_result:
                tags_text = analysis_result.split("匹配标签：")[1].strip()
            
            if not tags_text:
                return []
            
            # 只取第一行
            tags_text = tags_text.split("\n")[0].strip()
            
            # 去掉可能残留的括号内容（如 "（只写逗号分隔的标签"）
            if "）" in tags_text:
                tags_text = tags_text.split("）")[-1].strip()
            if ")" in tags_text:
                tags_text = tags_text.split(")")[-1].strip()
            
            # 先用逗号分隔（新格式要求用逗号）
            raw_tags = [t.strip() for t in tags_text.replace("，", ",").split(",") if t.strip()]
            if not raw_tags:
                raw_tags = [t.strip() for t in tags_text.split("、") if t.strip()]
            
            # 清洗每个标签：去掉括号、注释等杂质
            cleaned = []
            for tag in raw_tags:
                tag = tag.strip("（（））【】""''「」")
                # 去掉包含"注"、"筛选"、"最终"等关键词的垃圾文本
                skip_words = ["注", "筛选", "最终", "实际", "示例", "此处", "因", "故", "等", "经"]
                if any(w in tag for w in skip_words):
                    continue
                if len(tag) > 10:
                    continue
                if tag in self.vocabulary_tags or not self.vocabulary_tags:
                    cleaned.append(tag)
            
            # 如果清洗后还有脏数据，尝试用正则提取纯中文标签
            if len(cleaned) > 10:
                import re
                chinese_tags = re.findall(r'[\u4e00-\u9fff]{2,5}', tags_text)
                cleaned = [t for t in chinese_tags if t in self.vocabulary_tags][:8]
            
            return cleaned[:8]
        except Exception as e:
            if self.verbose:
                print(f"提取标签失败: {e}")
            return []

    def save_analysis_result(self, video_path: str, result: Dict[str, Any],
                            output_dir: str = None):
        """
        保存分析结果到文件
        
        Args:
            video_path: 视频文件路径
            result: 分析结果
            output_dir: 输出目录
        """
        if output_dir is None:
            output_dir = os.path.dirname(video_path)
        
        video_name = os.path.splitext(os.path.basename(video_path))[0]
        output_file = os.path.join(output_dir, f"{video_name}_analysis.txt")
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"成人视频分析报告\n")
                f.write(f"{'='*60}\n")
                f.write(f"视频文件: {video_path}\n")
                f.write(f"分析时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"使用模型: {result.get('model', 'N/A')}\n")
                f.write(f"分析帧数: {result.get('frames_extracted', 'N/A')}\n")
                f.write(f"{'='*60}\n\n")
                
                if result["success"]:
                    f.write("分析结果:\n")
                    f.write(f"{'-'*60}\n")
                    f.write(result["analysis"])
                    f.write(f"\n{'-'*60}\n\n")
                    
                    tags = self.extract_tags_from_analysis(result["analysis"])
                    if tags:
                        f.write(f"提取的标签: {', '.join(tags)}\n")
                else:
                    f.write(f"分析失败: {result.get('error', '未知错误')}\n")
            
            if self.verbose:
                print(f"\n✅ 分析结果已保存到: {output_file}")
                
        except Exception as e:
            if self.verbose:
                print(f"❌ 保存分析结果失败: {e}")


def main():
    """主函数 - 命令行入口"""
    parser = argparse.ArgumentParser(
        description="成人视频分析器 - 使用minicpm-v-4.6 abliterated模型进行内容理解和标签打分",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 分析单个成人视频文件
  python video_analyzer_local_model_adult.py video.mp4
  
  # 指定帧数和间隔
  python video_analyzer_local_model_adult.py video.mp4 --frames 20 --interval 2.0
  
  # 批量分析目录下的所有视频
  python video_analyzer_local_model_adult.py /path/to/videos --batch
  
  # 指定输出目录
  python video_analyzer_local_model_adult.py video.mp4 --output /path/to/output
  
  # 使用自定义API地址
  python video_analyzer_local_model_adult.py video.mp4 --api-url http://localhost:8080
        """
    )
    
    parser.add_argument("video_path", help="视频文件路径或包含视频的目录路径")
    parser.add_argument("--frames", type=int, default=None, 
                       help="指定提取的帧数（默认自动计算，最大30帧）")
    parser.add_argument("--interval", type=float, default=3.0,
                       help="帧间隔时间（秒），默认3.0秒")
    parser.add_argument("--batch", action="store_true",
                       help="批量分析目录下的所有视频文件")
    parser.add_argument("--output", type=str, default=None,
                       help="分析结果输出目录")
    parser.add_argument("--api-url", type=str, default="https://api.siliconflow.cn",
                       help="API地址，默认: https://api.siliconflow.cn")
    parser.add_argument("--model", type=str, default="Qwen/Qwen3-VL-30B-A3B-Instruct",
                       help="模型名称，默认: Qwen/Qwen3-VL-30B-A3B-Instruct")
    parser.add_argument("--api-key", type=str, default=None,
                       help="API密钥，也可通过环境变量 SILICONFLOW_API_KEY 设置")
    parser.add_argument("--tags-file", type=str, default=None,
                       help="标签词汇文件路径")
    parser.add_argument("--quiet", action="store_true",
                       help="静默模式，减少输出信息")
    
    args = parser.parse_args()
    
    verbose = not args.quiet
    
    analyzer = VideoAnalyzerLocalModelAdult(
        api_base_url=args.api_url,
        model_name=args.model,
        api_key=args.api_key,
        tags_file=args.tags_file,
        verbose=verbose
    )
    
    if args.batch:
        video_dir = args.video_path
        if not os.path.isdir(video_dir):
            print(f"❌ 错误: {video_dir} 不是有效的目录")
            return
        
        video_extensions = ['.mp4', '.avi', '.mkv', '.mov', '.flv', '.wmv']
        video_files = []
        for ext in video_extensions:
            video_files.extend([f for f in os.listdir(video_dir) if f.lower().endswith(ext)])
        
        if not video_files:
            print(f"❌ 目录 {video_dir} 中没有找到视频文件")
            return
        
        print(f"\n找到 {len(video_files)} 个视频文件")
        print(f"开始批量分析...\n")
        
        success_count = 0
        fail_count = 0
        
        for i, video_file in enumerate(video_files, 1):
            video_path = os.path.join(video_dir, video_file)
            print(f"\n[{i}/{len(video_files)}] 分析: {video_file}")
            
            result = analyzer.analyze_video(
                video_path=video_path,
                num_frames=args.frames,
                interval_seconds=args.interval
            )
            
            if result["success"]:
                analyzer.save_analysis_result(video_path, result, args.output)
                success_count += 1
            else:
                print(f"❌ 分析失败: {result.get('error', '未知错误')}")
                fail_count += 1
        
        print(f"\n{'='*60}")
        print(f"批量分析完成")
        print(f"成功: {success_count} 个")
        print(f"失败: {fail_count} 个")
        print(f"{'='*60}")
        
    else:
        video_path = args.video_path
        if not os.path.exists(video_path):
            print(f"❌ 错误: 视频文件不存在: {video_path}")
            return
        
        result = analyzer.analyze_video(
            video_path=video_path,
            num_frames=args.frames,
            interval_seconds=args.interval
        )
        
        print(f"\n{'='*60}")
        print("分析结果")
        print(f"{'='*60}")
        
        if result["success"]:
            print("✅ 视频分析成功!")
            print(f"📊 分析帧数: {result['frames_extracted']}")
            print(f"🤖 使用模型: {result['model']}")
            print(f"\n📝 分析内容:\n{result['analysis']}")
            
            tags = analyzer.extract_tags_from_analysis(result["analysis"])
            if tags:
                print(f"\n🏷️  提取的标签: {', '.join(tags)}")
            
            analyzer.save_analysis_result(video_path, result, args.output)
            
            if "raw_response" in result:
                raw_response = result["raw_response"]
                if "usage" in raw_response:
                    usage = raw_response["usage"]
                    print(f"\n📈 Token使用情况:")
                    print(f"   - 输入Token: {usage.get('prompt_tokens', 'N/A')}")
                    print(f"   - 输出Token: {usage.get('completion_tokens', 'N/A')}")
                    print(f"   - 总Token: {usage.get('total_tokens', 'N/A')}")
        else:
            print("❌ 视频分析失败!")
            print(f"错误信息: {result.get('error', '未知错误')}")


if __name__ == "__main__":
    main()