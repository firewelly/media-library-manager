#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频播放问题检测工具

专门检测视频拖动进度条后自动关闭的问题
通过模拟播放器行为来检测视频文件的播放稳定性

作者: AI Assistant
创建时间: 2025-01-17
"""

import cv2
import os
import sqlite3
import sys
import time
import random
from datetime import datetime
import numpy as np

class VideoPlaybackTester:
    def __init__(self, db_path="media_library.db"):
        self.db_path = db_path
        
    def test_video_seeking(self, file_path, test_points=10):
        """测试视频的跳转播放功能"""
        print(f"\n🎬 测试视频跳转播放: {os.path.basename(file_path)}")
        print(f"文件路径: {file_path}")
        print("=" * 60)
        
        if not os.path.exists(file_path):
            return {
                "status": "failed",
                "error": "文件不存在",
                "test_results": []
            }
        
        try:
            cap = cv2.VideoCapture(file_path)
            if not cap.isOpened():
                return {
                    "status": "failed",
                    "error": "无法打开视频文件",
                    "test_results": []
                }
            
            # 获取视频基本信息
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            duration = total_frames / fps if fps > 0 else 0
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            print(f"📊 视频信息:")
            print(f"   分辨率: {width}x{height}")
            print(f"   帧率: {fps:.2f} fps")
            print(f"   总帧数: {total_frames}")
            print(f"   时长: {duration:.2f} 秒 ({duration/60:.1f} 分钟)")
            
            if total_frames <= 0 or fps <= 0:
                cap.release()
                return {
                    "status": "failed",
                    "error": "视频信息异常",
                    "video_info": {
                        "width": width,
                        "height": height,
                        "fps": fps,
                        "total_frames": total_frames,
                        "duration": duration
                    },
                    "test_results": []
                }
            
            # 生成测试点（包括开头、中间、结尾的随机位置）
            test_positions = []
            
            # 添加固定测试点
            test_positions.extend([0, total_frames // 4, total_frames // 2, total_frames * 3 // 4, total_frames - 10])
            
            # 添加随机测试点
            for _ in range(test_points - 5):
                test_positions.append(random.randint(0, total_frames - 1))
            
            test_positions = sorted(list(set(test_positions)))
            test_positions = [pos for pos in test_positions if 0 <= pos < total_frames]
            
            print(f"\n🎯 开始跳转测试，共 {len(test_positions)} 个测试点...")
            
            test_results = []
            successful_seeks = 0
            failed_seeks = 0
            
            for i, frame_pos in enumerate(test_positions, 1):
                time_pos = frame_pos / fps
                print(f"\n[{i}/{len(test_positions)}] 测试跳转到 {time_pos:.1f}秒 (帧 {frame_pos})")
                
                test_result = {
                    "test_index": i,
                    "target_frame": frame_pos,
                    "target_time": time_pos,
                    "success": False,
                    "actual_frame": None,
                    "frame_readable": False,
                    "error": None,
                    "seek_time": None
                }
                
                try:
                    # 记录跳转开始时间
                    start_time = time.time()
                    
                    # 跳转到指定帧
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_pos)
                    
                    # 获取实际位置
                    actual_frame = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
                    actual_time = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
                    
                    # 尝试读取帧
                    ret, frame = cap.read()
                    
                    seek_time = time.time() - start_time
                    
                    test_result["actual_frame"] = actual_frame
                    test_result["actual_time"] = actual_time
                    test_result["seek_time"] = seek_time
                    test_result["frame_readable"] = ret and frame is not None
                    
                    if ret and frame is not None:
                        # 检查帧是否有效（不是全黑或全白）
                        if frame.size > 0:
                            frame_mean = np.mean(frame)
                            frame_std = np.std(frame)
                            
                            test_result["frame_mean"] = float(frame_mean)
                            test_result["frame_std"] = float(frame_std)
                            
                            # 判断帧是否有效
                            if frame_std > 1.0:  # 有一定的变化，不是纯色
                                test_result["success"] = True
                                successful_seeks += 1
                                print(f"   ✅ 跳转成功 - 实际位置: {actual_time:.1f}秒, 耗时: {seek_time:.3f}秒")
                            else:
                                test_result["error"] = "帧内容异常（可能是纯色帧）"
                                failed_seeks += 1
                                print(f"   ⚠️  跳转到异常帧 - 帧可能损坏")
                        else:
                            test_result["error"] = "帧数据为空"
                            failed_seeks += 1
                            print(f"   ❌ 跳转失败 - 帧数据为空")
                    else:
                        test_result["error"] = "无法读取帧"
                        failed_seeks += 1
                        print(f"   ❌ 跳转失败 - 无法读取帧")
                        
                except Exception as e:
                    test_result["error"] = str(e)
                    failed_seeks += 1
                    print(f"   ❌ 跳转异常: {e}")
                
                test_results.append(test_result)
                
                # 短暂延迟，模拟真实播放器行为
                time.sleep(0.1)
            
            cap.release()
            
            # 计算成功率
            success_rate = (successful_seeks / len(test_positions)) * 100 if test_positions else 0
            
            print(f"\n📈 测试结果汇总:")
            print(f"   总测试点: {len(test_positions)}")
            print(f"   成功跳转: {successful_seeks}")
            print(f"   失败跳转: {failed_seeks}")
            print(f"   成功率: {success_rate:.1f}%")
            
            # 判断视频播放稳定性
            if success_rate >= 90:
                status = "excellent"
                print(f"   ✅ 播放稳定性: 优秀")
            elif success_rate >= 70:
                status = "good"
                print(f"   ✅ 播放稳定性: 良好")
            elif success_rate >= 50:
                status = "fair"
                print(f"   ⚠️  播放稳定性: 一般（可能存在跳转问题）")
            else:
                status = "poor"
                print(f"   ❌ 播放稳定性: 差（严重的跳转问题）")
            
            # 分析失败模式
            if failed_seeks > 0:
                print(f"\n🔍 问题分析:")
                error_types = {}
                for result in test_results:
                    if not result["success"] and result["error"]:
                        error_type = result["error"]
                        error_types[error_type] = error_types.get(error_type, 0) + 1
                
                for error_type, count in error_types.items():
                    print(f"   - {error_type}: {count} 次")
                
                if success_rate < 70:
                    print(f"\n💡 建议:")
                    print(f"   - 这个视频可能存在编码问题或文件损坏")
                    print(f"   - 建议使用专业视频修复工具")
                    print(f"   - 或者重新下载/转码视频文件")
            
            return {
                "status": status,
                "success_rate": success_rate,
                "successful_seeks": successful_seeks,
                "failed_seeks": failed_seeks,
                "total_tests": len(test_positions),
                "video_info": {
                    "width": width,
                    "height": height,
                    "fps": fps,
                    "total_frames": total_frames,
                    "duration": duration
                },
                "test_results": test_results
            }
            
        except Exception as e:
            return {
                "status": "failed",
                "error": f"测试过程异常: {str(e)}",
                "test_results": []
            }
    
    def test_video_by_id(self, video_id, test_points=10):
        """根据数据库ID测试视频"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT id, title, file_path, file_name FROM videos WHERE id = ?",
                (video_id,)
            )
            
            result = cursor.fetchone()
            conn.close()
            
            if not result:
                print(f"❌ 未找到ID为 {video_id} 的视频记录")
                return None
            
            video_id, title, file_path, file_name = result
            print(f"📹 视频信息:")
            print(f"   ID: {video_id}")
            print(f"   标题: {title}")
            print(f"   文件名: {file_name}")
            
            test_result = self.test_video_seeking(file_path, test_points)
            test_result["video_id"] = video_id
            test_result["title"] = title
            test_result["file_name"] = file_name
            
            return test_result
            
        except Exception as e:
            print(f"❌ 数据库查询失败: {e}")
            return None
    
    def test_video_by_name(self, file_name_pattern, test_points=10):
        """根据文件名模式测试视频"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT id, title, file_path, file_name FROM videos WHERE file_name LIKE ? OR title LIKE ?",
                (f"%{file_name_pattern}%", f"%{file_name_pattern}%")
            )
            
            results = cursor.fetchall()
            conn.close()
            
            if not results:
                print(f"❌ 未找到匹配 '{file_name_pattern}' 的视频记录")
                return []
            
            print(f"📹 找到 {len(results)} 个匹配的视频:")
            
            test_reports = []
            for i, (video_id, title, file_path, file_name) in enumerate(results, 1):
                print(f"\n{'='*80}")
                print(f"[{i}/{len(results)}] 测试视频:")
                print(f"   ID: {video_id}")
                print(f"   标题: {title}")
                print(f"   文件名: {file_name}")
                
                test_result = self.test_video_seeking(file_path, test_points)
                test_result["video_id"] = video_id
                test_result["title"] = title
                test_result["file_name"] = file_name
                test_reports.append(test_result)
            
            return test_reports
            
        except Exception as e:
            print(f"❌ 数据库查询失败: {e}")
            return []

def main():
    """主函数"""
    print("🎬 视频播放问题检测工具")
    print("专门检测视频拖动进度条后自动关闭的问题")
    print("=" * 50)
    
    # 检查数据库
    if not os.path.exists("media_library.db"):
        print("❌ 未找到数据库文件 media_library.db")
        return
    
    # 检查OpenCV
    try:
        import cv2
        print(f"✅ OpenCV版本: {cv2.__version__}")
    except ImportError:
        print("❌ 未安装OpenCV，请运行: pip install opencv-python")
        return
    
    tester = VideoPlaybackTester()
    
    # 测试指定的视频文件
    print("\n🎯 测试案例: 检查指定的视频播放稳定性")
    test_pattern = "巨乳大奶女神！不行了，你插的太深了，我受不了了_1"
    
    test_reports = tester.test_video_by_name(test_pattern, test_points=15)
    
    if test_reports:
        print(f"\n{'='*80}")
        print(f"📊 测试完成，共测试了 {len(test_reports)} 个视频")
        
        # 统计结果
        excellent = sum(1 for r in test_reports if r.get("status") == "excellent")
        good = sum(1 for r in test_reports if r.get("status") == "good")
        fair = sum(1 for r in test_reports if r.get("status") == "fair")
        poor = sum(1 for r in test_reports if r.get("status") == "poor")
        failed = sum(1 for r in test_reports if r.get("status") == "failed")
        
        print(f"\n📈 播放稳定性统计:")
        print(f"   ✅ 优秀 (≥90%): {excellent} 个")
        print(f"   ✅ 良好 (≥70%): {good} 个")
        print(f"   ⚠️  一般 (≥50%): {fair} 个")
        print(f"   ❌ 差 (<50%): {poor} 个")
        print(f"   💥 测试失败: {failed} 个")
        
        # 保存详细报告
        import json
        report_file = f"video_playback_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(test_reports, f, ensure_ascii=False, indent=2)
        print(f"\n💾 详细测试报告已保存到: {report_file}")
        
        # 给出针对性建议
        if poor > 0 or failed > 0:
            print(f"\n🚨 发现播放问题的视频:")
            for report in test_reports:
                if report.get("status") in ["poor", "failed"]:
                    print(f"   - {report.get('file_name', 'Unknown')}: {report.get('status', 'unknown')}")
                    if report.get("error"):
                        print(f"     错误: {report['error']}")
            
            print(f"\n💡 解决建议:")
            print(f"   1. 这些视频可能存在编码问题或文件损坏")
            print(f"   2. 建议使用 ffmpeg 重新编码:")
            print(f"      ffmpeg -i input.mp4 -c:v libx264 -c:a aac output.mp4")
            print(f"   3. 或者使用专业视频修复工具")
            print(f"   4. 检查原始下载源是否完整")
    
    print(f"\n🔧 其他使用方式:")
    print(f"   # 测试特定ID的视频:")
    print(f"   # tester.test_video_by_id(28616, test_points=20)")
    print(f"   # 测试特定文件:")
    print(f"   # tester.test_video_seeking('/path/to/video.mp4', test_points=10)")

if __name__ == "__main__":
    main()