#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量清理数据库中所有标题的脚本
一次性数据库清理任务，清理标题中的特殊字符、网址、括号内容等

作者: AI Assistant
创建时间: 2025
"""

import sqlite3
import os
import re
from datetime import datetime

def clean_title_text(title):
    """
    清理标题文本，基于process_single_filename的逻辑
    
    Args:
        title (str): 原始标题
        
    Returns:
        str: 清理后的标题
    """
    if not title or not title.strip():
        return title
    
    # 去除开头和结尾的句号
    cleaned_title = title.strip('.')
    
    # 去掉空格（可选，根据需要调整）
    # cleaned_title = cleaned_title.replace(" ", "")
    
    # 去掉"Chinese homemade video"和"_CHINESE_HOMEMADE_VIDEO"
    if "CHINESEHOMEMADEVIDEO" in cleaned_title.upper():
        cleaned_title = re.sub(r'CHINESEHOMEMADEVIDEO', '', cleaned_title, flags=re.IGNORECASE)
    if "_CHINESE_HOMEMADE_VIDEO" in cleaned_title.upper():
        cleaned_title = re.sub(r'_CHINESE_HOMEMADE_VIDEO', '', cleaned_title, flags=re.IGNORECASE)
    
    # 去掉"hhd800.com@"
    if "HHD800.COM@" in cleaned_title.upper():
        cleaned_title = re.sub(r'HHD800\.COM@', '', cleaned_title, flags=re.IGNORECASE)
    
    # 去掉"WoXav.Com@"
    if "WOXAV.COM@" in cleaned_title.upper():
        cleaned_title = re.sub(r'WOXAV\.COM@', '', cleaned_title, flags=re.IGNORECASE)
    
    # 匹配"【"和"】"之间的内容
    pattern = r"(【.*?】)"
    if "【" in cleaned_title and "】" in cleaned_title:
        cleaned_title = re.sub(pattern, "", cleaned_title)
    
    # 第二轮匹配各种括号情形
    partern2 = r"[\[\【\(\（][^)）].*?[\）\)\】\]]"
    cleaned_title = re.sub(partern2, "", cleaned_title)
    
    # 第三轮匹配各种括号没有括回而是.
    partern3 = r"[\[\【\(\（][^)）].*?\."
    cleaned_title = re.sub(partern3, "", cleaned_title)
    
    # 去掉直角单引号之间的内容
    if "「" in cleaned_title and "」" in cleaned_title:
        cleaned_title = re.sub(r"「.*?」", "", cleaned_title)
    
    # 去掉直角双引号之间的内容
    if "『" in cleaned_title and "』" in cleaned_title:
        cleaned_title = re.sub(r"『.*?』", "", cleaned_title)
    
    # 去掉网址名称格式
    url_pattern = r"(?:WWW\.)?[A-Z0-9]+\.(COM|NET|ORG|CN|CC|ME)"
    cleaned_title = re.sub(url_pattern, "", cleaned_title, flags=re.IGNORECASE)
    
    # 清理连续的句号，替换为空字符串
    cleaned_title = re.sub(r'\.{2,}', '', cleaned_title)
    
    # 最终清理：去除开头和结尾的句号和空格
    cleaned_title = cleaned_title.strip('. ')
    
    # 去除开头的叹号（如果有的话）
    while cleaned_title.startswith('!'):
        cleaned_title = cleaned_title[1:]
    
    # 清理多余的空格
    cleaned_title = re.sub(r'\s+', ' ', cleaned_title).strip()
    
    return cleaned_title

def batch_clean_titles(db_path="media_library.db", dry_run=True):
    """
    批量清理数据库中的所有标题
    
    Args:
        db_path (str): 数据库文件路径
        dry_run (bool): 是否为预览模式，不实际执行修改
    """
    if not os.path.exists(db_path):
        print(f"错误：找不到数据库文件 {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 查询所有有标题的视频记录
        cursor.execute("""
            SELECT id, title, file_name
            FROM videos 
            WHERE title IS NOT NULL AND title != '' AND TRIM(title) != ''
        """)
        
        videos = cursor.fetchall()
        
        if not videos:
            print("没有找到需要清理的标题记录")
            return True
        
        print(f"找到 {len(videos)} 条标题记录需要检查")
        print(f"模式: {'预览模式' if dry_run else '执行模式'}")
        print("=" * 60)
        
        updated_count = 0
        no_change_count = 0
        
        for video_id, title, file_name in videos:
            # 清理标题
            cleaned_title = clean_title_text(title)
            
            # 检查是否需要更新
            if title != cleaned_title:
                print(f"\n视频 ID: {video_id}")
                print(f"文件名: {file_name or 'Unknown'}")
                print(f"原标题: {title}")
                print(f"新标题: {cleaned_title}")
                
                if not dry_run:
                    try:
                        cursor.execute("""
                            UPDATE videos 
                            SET title = ?, updated_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                        """, (cleaned_title, video_id))
                        updated_count += 1
                        print(f"✓ 标题更新成功")
                    except Exception as e:
                        print(f"✗ 标题更新失败: {e}")
                else:
                    updated_count += 1
                    print(f"[预览] 将要更新")
            else:
                no_change_count += 1
        
        if not dry_run:
            conn.commit()
            print(f"\n清理完成！")
            print(f"标题更新: {updated_count} 条")
            print(f"无需更新: {no_change_count} 条")
        else:
            print(f"\n预览完成！")
            print(f"需要更新: {updated_count} 条")
            print(f"无需更新: {no_change_count} 条")
            print(f"\n要执行实际更新，请运行: python {__file__} --execute")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"清理标题时发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """
    主函数
    """
    import sys
    
    print("批量标题清理脚本")
    print("=" * 40)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 检查命令行参数
    execute_mode = '--execute' in sys.argv or '-e' in sys.argv
    dry_run = not execute_mode
    
    if dry_run:
        print("⚠️  当前为预览模式，不会实际修改数据库")
        print("   要执行实际更新，请添加 --execute 或 -e 参数")
        print()
    else:
        print("🚀 执行模式：将实际修改数据库")
        print()
        
        # 执行模式需要确认
        confirm = input("确定要执行批量标题清理吗？(y/N): ")
        if confirm.lower() not in ['y', 'yes', '是']:
            print("操作已取消")
            return
        print()
    
    try:
        # 执行清理
        success = batch_clean_titles(dry_run=dry_run)
        
        if success:
            print(f"\n任务完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            print("\n任务执行失败")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n操作被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n发生未预期的错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()