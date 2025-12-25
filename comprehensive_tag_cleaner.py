#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全面的数据库标签清理工具
功能：
1. 去除重复标签（忽略大小写）
2. 清理空白标签
3. 标准化标签格式（去除多余空格）
4. 去除空的标签项
5. 统一标签分隔符
"""

import sqlite3
import os
import re
from datetime import datetime

def comprehensive_tag_cleanup(db_path="media_library.db"):
    """
    全面清理数据库中的标签
    
    Args:
        db_path (str): 数据库文件路径
    """
    if not os.path.exists(db_path):
        print(f"错误：找不到数据库文件 {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 查询所有有标签的视频
        cursor.execute("""
            SELECT id, tags, title, file_name 
            FROM videos 
            WHERE tags IS NOT NULL AND tags != ''
        """)
        
        videos = cursor.fetchall()
        
        if not videos:
            print("没有找到需要清理的标签数据")
            return True
        
        print(f"找到 {len(videos)} 个视频需要检查标签")
        print("开始全面清理标签...\n")
        
        updated_count = 0
        issues_found = {
            'duplicates': 0,
            'empty_tags': 0,
            'whitespace_issues': 0,
            'format_issues': 0
        }
        
        for video_id, tags, title, file_name in videos:
            if not tags or not tags.strip():
                continue
            
            original_tags = tags
            issues_in_this_video = []
            
            # 1. 标准化分隔符（统一使用逗号）
            normalized_tags = re.sub(r'[;，、]', ',', tags)
            
            # 2. 分割标签并清理
            tag_list = []
            for tag in normalized_tags.split(','):
                # 去除前后空格
                cleaned_tag = tag.strip()
                # 去除多余的内部空格
                cleaned_tag = re.sub(r'\s+', ' ', cleaned_tag)
                
                if cleaned_tag:  # 只保留非空标签
                    tag_list.append(cleaned_tag)
                elif tag.strip() != tag:  # 检测到空格问题
                    issues_in_this_video.append('whitespace_issues')
            
            # 3. 去除重复标签（忽略大小写）
            unique_tags = []
            seen_tags = set()
            
            for tag in tag_list:
                tag_lower = tag.lower()
                if tag_lower not in seen_tags:
                    seen_tags.add(tag_lower)
                    unique_tags.append(tag)
                else:
                    issues_in_this_video.append('duplicates')
            
            # 4. 检查是否有空标签
            if len(tag_list) != len([t for t in normalized_tags.split(',') if t.strip()]):
                issues_in_this_video.append('empty_tags')
            
            # 5. 检查格式问题
            if normalized_tags != tags:
                issues_in_this_video.append('format_issues')
            
            # 重新组合标签
            cleaned_tags = ', '.join(unique_tags)
            
            # 如果标签发生了变化，更新数据库
            if cleaned_tags != original_tags:
                cursor.execute(
                    "UPDATE videos SET tags = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (cleaned_tags, video_id)
                )
                
                updated_count += 1
                
                # 统计问题类型
                for issue in set(issues_in_this_video):
                    issues_found[issue] += 1
                
                print(f"✓ 更新视频 ID {video_id}: {file_name or title or 'Unknown'}")
                print(f"  原标签: {original_tags}")
                print(f"  新标签: {cleaned_tags}")
                if issues_in_this_video:
                    print(f"  发现问题: {', '.join(set(issues_in_this_video))}")
                print()
        
        # 提交更改
        conn.commit()
        conn.close()
        
        print(f"全面清理完成！")
        print(f"总共检查: {len(videos)} 个视频")
        print(f"更新标签: {updated_count} 个视频")
        print(f"无需更新: {len(videos) - updated_count} 个视频")
        print("\n发现的问题统计:")
        print(f"  重复标签: {issues_found['duplicates']} 个视频")
        print(f"  空白标签: {issues_found['empty_tags']} 个视频")
        print(f"  空格问题: {issues_found['whitespace_issues']} 个视频")
        print(f"  格式问题: {issues_found['format_issues']} 个视频")
        
        return True
        
    except Exception as e:
        print(f"清理标签时发生错误: {e}")
        return False

def analyze_tag_quality(db_path="media_library.db"):
    """
    分析标签质量，不进行修改
    
    Args:
        db_path (str): 数据库文件路径
    """
    if not os.path.exists(db_path):
        print(f"错误：找不到数据库文件 {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 查询所有视频的标签情况
        cursor.execute("""
            SELECT 
                COUNT(*) as total_videos,
                COUNT(CASE WHEN tags IS NOT NULL AND tags != '' THEN 1 END) as videos_with_tags,
                COUNT(CASE WHEN tags IS NULL OR tags = '' THEN 1 END) as videos_without_tags
            FROM videos
        """)
        
        stats = cursor.fetchone()
        total_videos, videos_with_tags, videos_without_tags = stats
        
        # 查询有标签的视频详情
        cursor.execute("""
            SELECT id, tags, title, file_name 
            FROM videos 
            WHERE tags IS NOT NULL AND tags != ''
        """)
        
        videos = cursor.fetchall()
        conn.close()
        
        print(f"数据库标签质量分析")
        print("=" * 50)
        print(f"总视频数: {total_videos}")
        print(f"有标签视频: {videos_with_tags} ({videos_with_tags/total_videos*100:.1f}%)")
        print(f"无标签视频: {videos_without_tags} ({videos_without_tags/total_videos*100:.1f}%)")
        print()
        
        if not videos:
            print("没有找到标签数据")
            return
        
        # 分析标签质量问题
        issues = {
            'duplicates': 0,
            'empty_tags': 0,
            'whitespace_issues': 0,
            'format_issues': 0,
            'single_tag': 0,
            'many_tags': 0
        }
        
        tag_counts = []
        all_tags = set()
        
        for video_id, tags, title, file_name in videos:
            if not tags:
                continue
            
            # 检查格式问题
            if re.search(r'[;，、]', tags):
                issues['format_issues'] += 1
            
            # 分割标签
            tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
            tag_counts.append(len(tag_list))
            
            # 收集所有标签
            for tag in tag_list:
                all_tags.add(tag.lower())
            
            # 检查重复
            seen = set()
            for tag in tag_list:
                if tag.lower() in seen:
                    issues['duplicates'] += 1
                    break
                seen.add(tag.lower())
            
            # 检查空标签
            if len([t for t in tags.split(',') if not t.strip()]) > 0:
                issues['empty_tags'] += 1
            
            # 检查空格问题
            if any(tag != tag.strip() or re.search(r'\s{2,}', tag) for tag in tags.split(',')):
                issues['whitespace_issues'] += 1
            
            # 标签数量统计
            if len(tag_list) == 1:
                issues['single_tag'] += 1
            elif len(tag_list) > 10:
                issues['many_tags'] += 1
        
        # 统计结果
        avg_tags = sum(tag_counts) / len(tag_counts) if tag_counts else 0
        max_tags = max(tag_counts) if tag_counts else 0
        min_tags = min(tag_counts) if tag_counts else 0
        
        print(f"标签统计:")
        print(f"  平均标签数: {avg_tags:.1f}")
        print(f"  最多标签数: {max_tags}")
        print(f"  最少标签数: {min_tags}")
        print(f"  唯一标签数: {len(all_tags)}")
        print()
        
        print(f"质量问题统计:")
        print(f"  重复标签: {issues['duplicates']} 个视频")
        print(f"  空白标签: {issues['empty_tags']} 个视频")
        print(f"  空格问题: {issues['whitespace_issues']} 个视频")
        print(f"  格式问题: {issues['format_issues']} 个视频")
        print(f"  单一标签: {issues['single_tag']} 个视频")
        print(f"  标签过多: {issues['many_tags']} 个视频 (>10个)")
        
        total_issues = sum(issues.values()) - issues['single_tag'] - issues['many_tags']
        print(f"\n需要清理的视频: {total_issues} 个")
        
    except Exception as e:
        print(f"分析标签时发生错误: {e}")

if __name__ == "__main__":
    print("全面标签清理工具")
    print("=" * 50)
    
    # 先分析标签质量
    print("\n1. 分析标签质量:")
    analyze_tag_quality()
    
    # 执行全面清理
    print("\n2. 开始全面清理标签:")
    success = comprehensive_tag_cleanup()
    
    if success:
        print("\n标签清理完成！")
        print("\n3. 清理后的标签质量:")
        analyze_tag_quality()
    else:
        print("\n标签清理失败！")