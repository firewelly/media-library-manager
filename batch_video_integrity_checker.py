#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量视频完整性检查和清理工具
检查数据库中最近4天添加的视频文件，将有问题的文件移动到回收站
"""

import os
import sys
import sqlite3
import cv2
import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
import platform
import shutil

class BatchVideoIntegrityChecker:
    def __init__(self, db_path: str = "media_library.db", silent: bool = True):
        self.db_path = db_path
        self.silent = silent
        self.trash_folder = self._get_trash_folder()
        
    def _get_trash_folder(self) -> str:
        """获取系统回收站路径"""
        system = platform.system()
        if system == "Darwin":  # macOS
            return os.path.expanduser("~/.Trash")
        elif system == "Windows":
            # Windows回收站比较复杂，这里使用一个临时文件夹
            trash_dir = os.path.expanduser("~/Desktop/VideoTrash")
            os.makedirs(trash_dir, exist_ok=True)
            return trash_dir
        else:  # Linux
            trash_dir = os.path.expanduser("~/.local/share/Trash/files")
            os.makedirs(trash_dir, exist_ok=True)
            return trash_dir
    
    def _log(self, message: str, force: bool = False):
        """日志输出"""
        if not self.silent or force:
            print(message)
    
    def get_recent_videos(self, days: int = 4) -> List[Dict[str, Any]]:
        """获取最近N天添加的视频记录"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 计算日期范围
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            query = """
            SELECT id, title, file_path, file_name, created_at
            FROM videos 
            WHERE created_at >= ? AND created_at <= ?
            ORDER BY created_at DESC
            """
            
            cursor.execute(query, (start_date.isoformat(), end_date.isoformat()))
            results = cursor.fetchall()
            
            videos = []
            for row in results:
                videos.append({
                    'id': row[0],
                    'title': row[1],
                    'file_path': row[2],
                    'file_name': row[3],
                    'created_at': row[4]
                })
            
            conn.close()
            return videos
            
        except Exception as e:
            self._log(f"❌ 数据库查询失败: {e}", force=True)
            return []
    
    def check_video_integrity(self, file_path: str) -> Dict[str, Any]:
        """检查单个视频文件的完整性"""
        result = {
            'file_path': file_path,
            'file_exists': False,
            'opencv_playable': False,
            'has_seeking_issues': False,
            'error_messages': [],
            'overall_status': 'unknown'
        }
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            result['error_messages'].append('文件不存在')
            result['overall_status'] = 'missing'
            return result
        
        result['file_exists'] = True
        
        # OpenCV基础检查
        try:
            cap = cv2.VideoCapture(file_path)
            if not cap.isOpened():
                result['error_messages'].append('OpenCV无法打开文件')
                result['overall_status'] = 'corrupted'
                return result
            
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if frame_count <= 0:
                result['error_messages'].append('视频帧数为0')
                result['overall_status'] = 'corrupted'
                cap.release()
                return result
            
            result['opencv_playable'] = True
            
            # 快速跳转测试（检测seeking问题）
            seeking_issues = self._test_video_seeking(cap, frame_count)
            result['has_seeking_issues'] = seeking_issues
            
            if seeking_issues:
                result['error_messages'].append('视频跳转存在问题（可能导致播放器崩溃）')
                result['overall_status'] = 'seeking_issues'
            else:
                result['overall_status'] = 'healthy'
            
            cap.release()
            
        except Exception as e:
            result['error_messages'].append(f'检查过程出错: {str(e)}')
            result['overall_status'] = 'error'
        
        return result
    
    def _test_video_seeking(self, cap, frame_count: int, test_points: int = 5) -> bool:
        """测试视频跳转功能，检测是否有seeking问题"""
        try:
            # 测试几个关键位置的跳转
            test_frames = [
                int(frame_count * 0.1),   # 10%
                int(frame_count * 0.3),   # 30%
                int(frame_count * 0.5),   # 50%
                int(frame_count * 0.7),   # 70%
                int(frame_count * 0.9)    # 90%
            ]
            
            for frame_num in test_frames:
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
                ret, frame = cap.read()
                
                if not ret or frame is None:
                    return True  # 跳转失败，存在问题
                
                # 检查实际位置是否接近目标位置
                actual_frame = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
                if abs(actual_frame - frame_num) > frame_count * 0.05:  # 允许5%的误差
                    return True  # 跳转不准确，存在问题
            
            return False  # 所有测试通过
            
        except Exception:
            return True  # 测试过程出错，认为存在问题
    
    def move_to_trash(self, file_path: str) -> bool:
        """将文件移动到回收站"""
        try:
            if not os.path.exists(file_path):
                return False
            
            file_name = os.path.basename(file_path)
            trash_path = os.path.join(self.trash_folder, file_name)
            
            # 如果回收站中已存在同名文件，添加时间戳
            if os.path.exists(trash_path):
                name, ext = os.path.splitext(file_name)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                trash_path = os.path.join(self.trash_folder, f"{name}_{timestamp}{ext}")
            
            shutil.move(file_path, trash_path)
            return True
            
        except Exception as e:
            self._log(f"❌ 移动文件到回收站失败: {e}", force=True)
            return False
    
    def batch_check_and_cleanup(self, days: int = 4, auto_delete: bool = False) -> Dict[str, Any]:
        """批量检查并清理视频文件"""
        self._log(f"🔍 开始检查最近 {days} 天添加的视频文件...", force=True)
        
        # 获取最近的视频记录
        videos = self.get_recent_videos(days)
        if not videos:
            self._log("📭 没有找到最近添加的视频记录", force=True)
            return {'total': 0, 'checked': 0, 'problematic': 0, 'deleted': 0}
        
        self._log(f"📊 找到 {len(videos)} 个视频文件需要检查", force=True)
        
        results = {
            'total': len(videos),
            'checked': 0,
            'problematic': 0,
            'deleted': 0,
            'details': []
        }
        
        for i, video in enumerate(videos, 1):
            if not self.silent:
                self._log(f"\r🔍 检查进度: {i}/{len(videos)}", force=False)
            
            check_result = self.check_video_integrity(video['file_path'])
            results['checked'] += 1
            
            # 判断是否有问题
            is_problematic = (
                check_result['overall_status'] in ['corrupted', 'seeking_issues', 'missing', 'error'] or
                check_result['has_seeking_issues']
            )
            
            if is_problematic:
                results['problematic'] += 1
                
                video_info = {
                    'id': video['id'],
                    'title': video['title'],
                    'file_path': video['file_path'],
                    'status': check_result['overall_status'],
                    'issues': check_result['error_messages'],
                    'deleted': False
                }
                
                if auto_delete and check_result['file_exists']:
                    if self.move_to_trash(video['file_path']):
                        video_info['deleted'] = True
                        results['deleted'] += 1
                        self._log(f"🗑️  已删除: {video['file_name']}", force=True)
                    else:
                        self._log(f"❌ 删除失败: {video['file_name']}", force=True)
                
                results['details'].append(video_info)
        
        return results
    
    def generate_report(self, results: Dict[str, Any], output_file: str = None) -> str:
        """生成检查报告"""
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"batch_video_check_report_{timestamp}.json"
        
        report_data = {
            'check_time': datetime.now().isoformat(),
            'summary': results,
            'problematic_videos': results['details']
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        
        return output_file

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='批量视频完整性检查和清理工具')
    parser.add_argument('--days', type=int, default=4, help='检查最近N天的视频 (默认: 4)')
    parser.add_argument('--auto-delete', action='store_true', help='自动删除有问题的文件到回收站')
    parser.add_argument('--verbose', action='store_true', help='显示详细输出')
    parser.add_argument('--db', type=str, default='media_library.db', help='数据库文件路径')
    
    args = parser.parse_args()
    
    # 创建检查器
    checker = BatchVideoIntegrityChecker(
        db_path=args.db,
        silent=not args.verbose
    )
    
    # 执行批量检查
    results = checker.batch_check_and_cleanup(
        days=args.days,
        auto_delete=args.auto_delete
    )
    
    # 生成报告
    report_file = checker.generate_report(results)
    
    # 输出结果摘要
    print(f"\n📋 检查完成!")
    print(f"📊 总计: {results['total']} 个视频")
    print(f"✅ 已检查: {results['checked']} 个")
    print(f"⚠️  有问题: {results['problematic']} 个")
    print(f"🗑️  已删除: {results['deleted']} 个")
    print(f"📄 详细报告: {report_file}")
    
    if results['problematic'] > 0 and not args.auto_delete:
        print(f"\n💡 提示: 使用 --auto-delete 参数可自动删除有问题的文件")

if __name__ == "__main__":
    main()