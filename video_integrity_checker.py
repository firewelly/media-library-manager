#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频完整性检查工具

功能：
1. 检查视频文件是否可以正常播放
2. 检查视频文件的完整性
3. 提供详细的检查报告
4. 支持单个文件和批量检查

作者: AI Assistant
创建时间: 2025-01-17
"""

import cv2
import os
import sqlite3
import sys
import time
from pathlib import Path
import subprocess
import json
from datetime import datetime

class VideoIntegrityChecker:
    def __init__(self, db_path="media_library.db"):
        self.db_path = db_path
        
    def check_file_exists(self, file_path):
        """检查文件是否存在"""
        return os.path.exists(file_path) and os.path.isfile(file_path)
    
    def check_file_size(self, file_path):
        """检查文件大小"""
        try:
            return os.path.getsize(file_path)
        except:
            return 0
    
    def check_opencv_playable(self, file_path):
        """使用OpenCV检查视频是否可播放"""
        try:
            cap = cv2.VideoCapture(file_path)
            if not cap.isOpened():
                return False, "无法打开视频文件"
            
            # 检查帧数
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if frame_count <= 0:
                cap.release()
                return False, "视频帧数为0或无法获取"
            
            # 尝试读取第一帧
            ret, frame = cap.read()
            if not ret or frame is None:
                cap.release()
                return False, "无法读取视频帧"
            
            # 获取视频信息
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            duration = frame_count / fps if fps > 0 else 0
            
            cap.release()
            
            info = {
                "frame_count": frame_count,
                "fps": fps,
                "width": width,
                "height": height,
                "duration": duration
            }
            
            return True, info
            
        except Exception as e:
            return False, f"OpenCV检查失败: {str(e)}"
    
    def check_ffprobe_info(self, file_path):
        """使用ffprobe获取视频详细信息"""
        try:
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                file_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                return False, f"ffprobe失败: {result.stderr}"
            
            data = json.loads(result.stdout)
            return True, data
            
        except subprocess.TimeoutExpired:
            return False, "ffprobe超时"
        except json.JSONDecodeError:
            return False, "ffprobe输出解析失败"
        except FileNotFoundError:
            return False, "ffprobe未安装"
        except Exception as e:
            return False, f"ffprobe检查失败: {str(e)}"
    
    def check_video_integrity(self, file_path, deep_check=False):
        """综合检查视频完整性"""
        print(f"\n正在检查视频: {os.path.basename(file_path)}")
        print(f"文件路径: {file_path}")
        print("=" * 60)
        
        report = {
            "file_path": file_path,
            "file_name": os.path.basename(file_path),
            "check_time": datetime.now().isoformat(),
            "checks": {},
            "overall_status": "unknown",
            "issues": [],
            "recommendations": []
        }
        
        # 1. 文件存在性检查
        print("1. 检查文件存在性...")
        if not self.check_file_exists(file_path):
            print("   ❌ 文件不存在")
            report["checks"]["file_exists"] = False
            report["issues"].append("文件不存在")
            report["overall_status"] = "failed"
            return report
        else:
            print("   ✅ 文件存在")
            report["checks"]["file_exists"] = True
        
        # 2. 文件大小检查
        print("2. 检查文件大小...")
        file_size = self.check_file_size(file_path)
        if file_size == 0:
            print("   ❌ 文件大小为0")
            report["checks"]["file_size"] = 0
            report["issues"].append("文件大小为0")
            report["overall_status"] = "failed"
            return report
        else:
            size_mb = file_size / (1024 * 1024)
            print(f"   ✅ 文件大小: {size_mb:.2f} MB")
            report["checks"]["file_size"] = file_size
            if size_mb < 1:
                report["issues"].append("文件过小，可能不完整")
        
        # 3. OpenCV播放性检查
        print("3. 检查OpenCV播放性...")
        opencv_ok, opencv_result = self.check_opencv_playable(file_path)
        if opencv_ok:
            print("   ✅ OpenCV可以播放")
            print(f"   📊 视频信息: {opencv_result['width']}x{opencv_result['height']}, {opencv_result['fps']:.2f}fps, {opencv_result['duration']:.2f}秒")
            report["checks"]["opencv_playable"] = True
            report["checks"]["opencv_info"] = opencv_result
        else:
            print(f"   ❌ OpenCV无法播放: {opencv_result}")
            report["checks"]["opencv_playable"] = False
            report["issues"].append(f"OpenCV播放失败: {opencv_result}")
        
        # 4. ffprobe详细检查（如果启用深度检查）
        if deep_check:
            print("4. 进行ffprobe深度检查...")
            ffprobe_ok, ffprobe_result = self.check_ffprobe_info(file_path)
            if ffprobe_ok:
                print("   ✅ ffprobe检查通过")
                report["checks"]["ffprobe_ok"] = True
                report["checks"]["ffprobe_info"] = ffprobe_result
                
                # 分析流信息
                video_streams = [s for s in ffprobe_result.get('streams', []) if s.get('codec_type') == 'video']
                audio_streams = [s for s in ffprobe_result.get('streams', []) if s.get('codec_type') == 'audio']
                
                print(f"   📊 视频流: {len(video_streams)}个, 音频流: {len(audio_streams)}个")
                
                if not video_streams:
                    report["issues"].append("没有视频流")
                if not audio_streams:
                    report["issues"].append("没有音频流")
                    
            else:
                print(f"   ❌ ffprobe检查失败: {ffprobe_result}")
                report["checks"]["ffprobe_ok"] = False
                report["issues"].append(f"ffprobe失败: {ffprobe_result}")
        
        # 5. 综合评估
        print("\n📋 检查结果汇总:")
        if not report["issues"]:
            report["overall_status"] = "healthy"
            print("   ✅ 视频文件完整，可以正常播放")
        elif opencv_ok:
            report["overall_status"] = "playable_with_issues"
            print("   ⚠️  视频可以播放，但存在一些问题")
            report["recommendations"].append("建议检查视频质量")
        else:
            report["overall_status"] = "corrupted"
            print("   ❌ 视频文件损坏，无法正常播放")
            report["recommendations"].append("建议重新下载或修复视频文件")
        
        if report["issues"]:
            print("\n⚠️  发现的问题:")
            for issue in report["issues"]:
                print(f"   - {issue}")
        
        if report["recommendations"]:
            print("\n💡 建议:")
            for rec in report["recommendations"]:
                print(f"   - {rec}")
        
        return report
    
    def check_video_by_id(self, video_id, deep_check=False):
        """根据数据库ID检查视频"""
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
            
            return self.check_video_integrity(file_path, deep_check)
            
        except Exception as e:
            print(f"❌ 数据库查询失败: {e}")
            return None
    
    def check_video_by_name(self, file_name_pattern, deep_check=False):
        """根据文件名模式检查视频"""
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
            
            reports = []
            for i, (video_id, title, file_path, file_name) in enumerate(results, 1):
                print(f"\n[{i}/{len(results)}] 视频信息:")
                print(f"   ID: {video_id}")
                print(f"   标题: {title}")
                print(f"   文件名: {file_name}")
                
                report = self.check_video_integrity(file_path, deep_check)
                report["video_id"] = video_id
                report["title"] = title
                reports.append(report)
            
            return reports
            
        except Exception as e:
            print(f"❌ 数据库查询失败: {e}")
            return []

def main():
    """主函数"""
    print("🎬 视频完整性检查工具")
    print("=" * 40)
    
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
    
    checker = VideoIntegrityChecker()
    
    # 测试指定的视频文件
    print("\n🎯 测试案例: 检查指定的视频文件")
    test_pattern = "巨乳大奶女神！不行了，你插的太深了，我受不了了_1"
    
    reports = checker.check_video_by_name(test_pattern, deep_check=True)
    
    if reports:
        print(f"\n📊 检查完成，共检查了 {len(reports)} 个视频")
        
        # 统计结果
        healthy = sum(1 for r in reports if r["overall_status"] == "healthy")
        playable = sum(1 for r in reports if r["overall_status"] == "playable_with_issues")
        corrupted = sum(1 for r in reports if r["overall_status"] == "corrupted")
        
        print(f"\n📈 统计结果:")
        print(f"   ✅ 健康: {healthy} 个")
        print(f"   ⚠️  有问题但可播放: {playable} 个")
        print(f"   ❌ 损坏: {corrupted} 个")
        
        # 保存详细报告
        report_file = f"video_check_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(reports, f, ensure_ascii=False, indent=2)
        print(f"\n💾 详细报告已保存到: {report_file}")
    
    print("\n🔧 其他使用方式:")
    print("   python video_integrity_checker.py  # 交互式模式")
    print("   # 在代码中调用:")
    print("   # checker.check_video_by_id(28616)  # 按ID检查")
    print("   # checker.check_video_by_name('视频名称')  # 按名称检查")

if __name__ == "__main__":
    main()