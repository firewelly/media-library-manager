#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
硅基流动GLM-4.1V-9B-Thinking模型视频分析器（带标签判定功能）
支持最大30帧的视频分析，并进行标签匹配判定
"""

import cv2
try:
    from .video_integrity import check_video_integrity
except ImportError:
    from video_integrity import check_video_integrity
import base64
import json
import os
import requests
from typing import List, Dict, Any, Optional
import time
from PIL import Image
import io
try:
    from .config import api_config, video_config, file_config
except ImportError:
    from config import api_config, video_config, file_config

class VideoAnalyzerSiliconFlowGLMWithTags:
    def __init__(self, api_key: str = None, tags_file: str = None, verbose: bool = True):
        """
        初始化视频分析器
        
        Args:
            api_key: SiliconFlow API密钥
            tags_file: 标签词汇文件路径
        """
        self.api_key = api_key or os.getenv("SILICONFLOW_API_KEY")
        if not self.api_key:
            raise ValueError("API密钥未设置。请通过参数传入或设置环境变量 SILICONFLOW_API_KEY")
        self.base_url = api_config.SILICONFLOW_BASE_URL
        # 简化模型配置，只使用单一模型
        self.model_name = api_config.SILICONFLOW_GLM_MODEL
        self.max_frames = video_config.DEFAULT_MAX_FRAMES
        self.tags_file = tags_file or file_config.VOCABULARY_TAGS_FILE
        self.verbose = verbose
        self.vocabulary_tags = self._load_vocabulary_tags()
        # 修复代理配置 - 移除错误的代理设置
        self.proxies = None
    
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
                return ["少妇", "人妻", "熟女", "巨乳", "黑丝", "丝袜", "性感"]  # 默认标签
        except Exception as e:
            if self.verbose:
                print(f"❌ 读取标签文件失败: {e}，使用默认标签")
            return ["少妇", "人妻", "熟女", "巨乳", "黑丝", "丝袜", "性感"]  # 默认标签
        
    def _compress_image(self, image_data: bytes, max_size_mb: float = None, 
                       target_width: int = None) -> bytes:
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
            
            # 计算新的尺寸，保持宽高比
            width, height = image.size
            if width > target_width:
                ratio = target_width / width
                new_height = int(height * ratio)
                image = image.resize((target_width, new_height), Image.Resampling.LANCZOS)
            
            # 转换为RGB模式（如果不是的话）
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # 压缩图片
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
                print(f"图片压缩后大小: {compressed_size:.2f}MB")
            return compressed_data
            
        except Exception as e:
            if self.verbose:
                print(f"图片压缩失败: {e}")
            return image_data

    def extract_frames(self, video_path: str, num_frames: int = None, interval_seconds: float = 3.0) -> List[str]:
        """
        从视频中提取帧，限制最大30帧
        
        Args:
            video_path: 视频文件路径
            num_frames: 指定提取的帧数（如果为None则根据interval_seconds计算）
            interval_seconds: 帧间隔时间（秒）
            
        Returns:
            base64编码的帧图片列表
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"视频文件不存在: {video_path}")

        # 可选的视频完整性检查：避免损坏视频导致分析卡死
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
            # 获取视频信息
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            duration = total_frames / fps if fps > 0 else 0
            
            if self.verbose:
                print(f"视频信息: 总帧数={total_frames}, FPS={fps:.2f}, 时长={duration:.2f}秒")
            
            # 确定提取策略
            if num_frames is None:
                # 根据时间间隔计算帧数
                calculated_frames = max(1, int(duration / interval_seconds))
                num_frames = min(calculated_frames, self.max_frames)
            else:
                # 限制用户指定的帧数
                num_frames = min(num_frames, self.max_frames)
            
            if self.verbose:
                print(f"计划提取 {num_frames} 帧 (最大限制: {self.max_frames})")
            
            # 超时与失败保护参数
            overall_deadline = time.time() + getattr(video_config, 'FRAME_EXTRACT_TIMEOUT', 30)
            max_failures = getattr(video_config, 'FRAME_READ_MAX_FAILS', 8)
            consecutive_failures = 0

            frames_base64 = []

            # 当视频元信息异常时，启用顺序读取回退模式
            use_sequential_read = (total_frames <= 0) or (fps is None) or (fps <= 0)
            if use_sequential_read and self.verbose:
                print("检测到视频元信息异常，启用顺序读取回退模式")

            if not use_sequential_read:
                # 正常：按索引均匀采样
                if total_frames <= 1 or duration <= 1.0:
                    frame_indices = [total_frames // 2]
                    if self.verbose:
                        print("视频过短，仅提取中间帧")
                else:
                    # 均匀分布提取帧
                    if num_frames >= total_frames:
                        frame_indices = list(range(0, total_frames, max(1, total_frames // num_frames)))
                    else:
                        step = total_frames / num_frames
                        frame_indices = [int(i * step) for i in range(num_frames)]

                # 确保不超过最大帧数限制
                frame_indices = frame_indices[:self.max_frames]

                for frame_idx in frame_indices:
                    # 全局超时保护
                    if time.time() >= overall_deadline:
                        if self.verbose:
                            print("帧提取达到超时，提前结束并返回已提取的帧")
                        break

                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                    ret, frame = cap.read()
                    
                    if ret:
                        consecutive_failures = 0
                        # 转换为JPEG格式
                        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                        # 压缩图片
                        compressed_data = self._compress_image(buffer.tobytes())
                        # 转换为base64
                        frame_base64 = base64.b64encode(compressed_data).decode('utf-8')
                        frames_base64.append(frame_base64)
                        # 计算时间点
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
                                print("连续读取失败过多，提前结束以跳过疑似损坏文件")
                            break
            else:
                # 回退：顺序读取，直到收集到目标帧数或达到超时/失败阈值
                while (len(frames_base64) < num_frames) and (time.time() < overall_deadline):
                    ret, frame = cap.read()
                    if not ret:
                        consecutive_failures += 1
                        if self.verbose:
                            print(f"警告: 顺序读取失败 (连续失败 {consecutive_failures}/{max_failures})")
                        if consecutive_failures >= max_failures:
                            if self.verbose:
                                print("顺序读取失败过多，结束提取以跳过疑似损坏文件")
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

    def _generate_prompt_with_tags(self, video_path: Optional[str] = None) -> str:
        """
        生成包含动态标签的提示词
        
        Returns:
            包含标签的提示词
        """
        # 将标签列表转换为字符串
        tags_str = "、".join(self.vocabulary_tags)
        title = None
        if video_path:
            try:
                title = os.path.splitext(os.path.basename(video_path))[0]
            except Exception:
                title = None
        
        title_line = f"视频标题/文件名提示：{title}\n\n" if title else ""

        prompt = f"""{title_line}仔细观察这组视频中提取的照片，针对以下内容进行详细描述和推测：

1. 女性人物形象描述： 
    - 外貌特征（年龄、身材、发型、妆容等） 
    - 服装穿着（衣物、类型、颜色、风格、鞋子、眼镜、眼罩等） 
    - 是否穿着丝袜以及丝袜的颜色
    - 文胸款式和颜色、内裤款式和颜色 
    - 整体气质和风格 
 
2. 场景和剧情推测： 
    - 女性职业 
    - 场景环境描述 
    - 可能的剧情情节 
    - 人物关系和互动 
 
3. 关键特征标签： 
    - 提取能够描述人物和场景的关键词 
    - 重点关注人物特征、服装、场景、动作等 

4. 标签匹配判定：
请判定视频内容是否存在以下标签，对于存在的标签请在最后列出：
{tags_str}

注意标签选择与同义词规则：
- 仅从上面给出的标签表中选择输出；
- 如果视频标题/文件名包含与标签同义或缩写（如“TS”“Shemale”“Ladyboy”“变性”“跨性别”“伪娘”等），且与画面信息一致或高度相关，请将其统一映射为标签“人妖”并纳入最终标签；
- 如仅标题提示而画面证据不足，可在正文分析中标注“可能”，但最终“匹配标签”仍输出“人妖”。

输出格式要求：
- 请在分析结果的最后单独给出一行，以“匹配标签：”开头，仅列出标签，使用中文顿号“、”分隔，不要附加说明文字或括号。
 
请用中文回答，尽量详细和准确。"""
        
        return prompt

    def analyze_frames_with_glm(self, frames_base64: List[str], prompt: str = None) -> Dict[str, Any]:
        """
        使用GLM-4.1V-9B-Thinking模型分析视频帧（带标签判定）
        
        Args:
            frames_base64: base64编码的帧图片列表
            prompt: 自定义分析提示词
            
        Returns:
            分析结果字典
        """
        if not frames_base64:
            return {"success": False, "error": "没有可分析的帧"}
        
        # 使用自定义提示词或生成默认提示词（带动态标签）
        analysis_prompt = prompt or self._generate_prompt_with_tags()
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # 重试与指数退避逻辑，必要时降低帧数以减轻请求负载
        attempts = 0
        frames_to_use = list(frames_base64)
        last_error: Dict[str, Any] = {}

        while attempts <= api_config.MAX_RETRIES:
            # 构建消息内容（使用当前帧集合）
            content = [{"type": "text", "text": analysis_prompt}]
            for frame_b64 in frames_to_use:
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
                    print(f"正在调用硅基流动GLM模型，帧数: {len(frames_to_use)}，尝试: {attempts+1}/{api_config.MAX_RETRIES+1}")

                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=api_config.API_TIMEOUT,
                    proxies=self.proxies
                )

                if response.status_code == 200:
                    result = response.json()
                    analysis_result = result['choices'][0]['message']['content']
                    return {
                        "success": True,
                        "analysis": analysis_result,
                        "raw_response": result,
                        "frames_analyzed": len(frames_to_use),
                        "model": self.model_name
                    }

                # 非200响应，判断是否可重试
                status = response.status_code
                text = response.text
                last_error = {"status_code": status, "text": text}
                retriable = (status == 429) or (500 <= status < 600)
                if self.verbose:
                    print(f"API调用失败: {status} - {text[:200]}{'...' if len(text)>200 else ''}")

                if status == 400 and "Model does not exist" in text:
                    if self.verbose:
                        print(f"模型不存在: {self.model_name}")
                    # 模型不存在，直接返回错误，不再尝试切换
                    break
                if retriable and attempts < api_config.MAX_RETRIES:
                    # 首次失败后降低帧数量以减轻负载
                    if attempts == 0 and len(frames_to_use) > 12:
                        new_len = max(6, len(frames_to_use) // 2)
                        frames_to_use = frames_to_use[:new_len]
                        if self.verbose:
                            print(f"降低负载重试，帧数缩减为 {new_len}")
                    # 指数退避 + 少量抖动
                    backoff = api_config.RETRY_DELAY * (2 ** attempts) + (0.5 * (attempts + 1))
                    if self.verbose:
                        print(f"准备重试，第 {attempts+1} 次，等待 {backoff:.1f}s")
                    time.sleep(backoff)
                    attempts += 1
                    continue
                else:
                    break

            except Exception as e:
                last_error = {"exception": str(e)}
                if self.verbose:
                    print(f"API调用异常: {str(e)}")
                if attempts < api_config.MAX_RETRIES:
                    backoff = api_config.RETRY_DELAY * (2 ** attempts) + (0.5 * (attempts + 1))
                    if self.verbose:
                        print(f"异常后准备重试，第 {attempts+1} 次，等待 {backoff:.1f}s")
                    time.sleep(backoff)
                    attempts += 1
                    continue
                else:
                    break
                # 简化模型切换逻辑 - 只使用单一模型
                break

        # 重试耗尽后返回失败
        return {
            "success": False,
            "error": f"API调用失败或异常，已重试 {attempts} 次",
            "raw_response": last_error
        }

    def analyze_video(self, video_path: str, num_frames: int = None, 
                     interval_seconds: float = 3.0, custom_prompt: str = None) -> Dict[str, Any]:
        """
        分析视频文件（带标签判定）
        
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
                print(f"开始分析视频: {video_path}")
            
            # 提取帧
            frames_base64 = self.extract_frames(video_path, num_frames, interval_seconds)
            
            if not frames_base64:
                return {
                    "success": False,
                    "error": "未能提取到有效帧"
                }
            
            # 分析帧（如未提供自定义提示词，则基于视频路径生成更有上下文的提示词）
            default_prompt = None if custom_prompt else self._generate_prompt_with_tags(video_path)
            analysis_result = self.analyze_frames_with_glm(frames_base64, custom_prompt or default_prompt)
            
            # 添加视频信息
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

def main(video_filename=None):
    """主函数 - 测试GLM-4.1V-9B-Thinking模型（带标签判定）"""
    print("=" * 60)
    print("硅基流动GLM-4.1V-9B-Thinking视频分析测试（带标签判定）")
    print("=" * 60)
    
    # 初始化分析器
    analyzer = VideoAnalyzerSiliconFlowGLMWithTags()
    
    # 确定要分析的视频文件
    if video_filename:
        if os.path.exists(video_filename):
            video_path = video_filename
        else:
            print(f"❌ 指定的视频文件不存在: {video_filename}")
            return
    else:
        # 查找视频文件
        video_files = [f for f in os.listdir('.') if f.endswith('.mp4')]
        
        if not video_files:
            print("❌ 当前目录下没有找到.mp4视频文件")
            return
        
        video_path = video_files[0]
    
    print(f"📹 分析视频文件: {video_path}")
    
    # 分析视频（限制最大30帧，带标签判定）
    result = analyzer.analyze_video(
        video_path=video_path,
        num_frames=None,  # 自动计算，但不超过30帧
        interval_seconds=3.0,
        custom_prompt=None
    )
    
    print("\n" + "=" * 60)
    print("分析结果（带标签判定）")
    print("=" * 60)
    
    if result["success"]:
        print("✅ 视频分析成功!")
        print(f"📊 分析帧数: {result['frames_extracted']}")
        print(f"🤖 使用模型: {result['model']}")
        print(f"📝 分析结果:\n{result['analysis']}")
        
        # 显示原始API响应信息
        if "raw_response" in result:
            raw_response = result["raw_response"]
            print(f"\n📈 Token使用情况:")
            if "usage" in raw_response:
                usage = raw_response["usage"]
                print(f"   - 输入Token: {usage.get('prompt_tokens', 'N/A')}")
                print(f"   - 输出Token: {usage.get('completion_tokens', 'N/A')}")
                print(f"   - 总Token: {usage.get('total_tokens', 'N/A')}")
    else:
        print("❌ 视频分析失败!")
        print(f"错误信息: {result.get('error', '未知错误')}")
        
        if "raw_response" in result:
            print(f"\n原始错误响应:")
            print(json.dumps(result["raw_response"], indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
