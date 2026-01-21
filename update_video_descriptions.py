#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
根据CSV文件中的MD5值匹配数据库中的影片记录，
将CSV中的分析结果更新到数据库的描述和标签字段中
"""

import sqlite3
import pandas as pd
import os
from datetime import datetime

class VideoDescriptionUpdater:
    def __init__(self, db_path="media_library.db", csv_path=None):
        """
        初始化更新器
        
        Args:
            db_path (str): 数据库文件路径
            csv_path (str): CSV文件路径
        """
        self.db_path = db_path
        self.csv_path = csv_path
        
    def load_csv_data(self):
        """加载CSV数据"""
        try:
            print(f"正在加载CSV文件: {self.csv_path}")
            df = pd.read_csv(self.csv_path)
            print(f"CSV文件加载成功，共 {len(df)} 条记录")
            
            # 检查必要的列是否存在
            required_columns = ['file_md5', '女性人物形象描述', '场景和剧情推测', '提取关键词', '存在的标签有']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                print(f"错误：CSV文件缺少必要的列: {missing_columns}")
                return None
                
            return df
            
        except Exception as e:
            print(f"加载CSV文件失败: {e}")
            return None
    
    def combine_description_fields(self, row):
        """
        合并三个描述字段为一段完整的描述
        
        Args:
            row: pandas DataFrame的一行数据
            
        Returns:
            str: 合并后的描述文本
        """
        # 获取三个字段的内容
        character_desc = str(row['女性人物形象描述']).strip() if pd.notna(row['女性人物形象描述']) else ""
        scene_desc = str(row['场景和剧情推测']).strip() if pd.notna(row['场景和剧情推测']) else ""
        keywords = str(row['提取关键词']).strip() if pd.notna(row['提取关键词']) else ""
        
        # 合并描述
        description_parts = []
        
        if character_desc:
            description_parts.append(f"【人物形象】\n{character_desc}")
            
        if scene_desc:
            description_parts.append(f"【场景剧情】\n{scene_desc}")
            
        if keywords:
            description_parts.append(f"【关键词】\n{keywords}")
        
        return "\n\n".join(description_parts)
    
    def get_video_by_md5(self, md5_hash):
        """
        根据MD5值查找数据库中的视频记录
        
        Args:
            md5_hash (str): MD5哈希值
            
        Returns:
            tuple: 视频记录信息 (id, title, current_description, current_tags) 或 None
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 查找MD5匹配的记录，优先使用md5_hash字段，如果没有则使用file_hash字段
            cursor.execute("""
                SELECT id, title, description, tags, file_name
                FROM videos 
                WHERE md5_hash = ? OR file_hash = ?
            """, (md5_hash, md5_hash))
            
            result = cursor.fetchone()
            conn.close()
            
            return result
            
        except Exception as e:
            print(f"查询数据库失败 (MD5: {md5_hash}): {e}")
            return None
    
    def update_video_record(self, video_id, new_description, new_tags):
        """
        更新视频记录的描述和标签
        
        Args:
            video_id (int): 视频ID
            new_description (str): 新的描述
            new_tags (str): 新的标签
            
        Returns:
            bool: 更新是否成功
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE videos 
                SET description = ?, tags = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            """, (new_description, new_tags, video_id))
            
            conn.commit()
            conn.close()
            
            return True
            
        except Exception as e:
            print(f"更新视频记录失败 (ID: {video_id}): {e}")
            return False
    
    def process_updates(self, dry_run=True):
        """
        处理所有更新操作
        
        Args:
            dry_run (bool): 是否为预览模式，不实际执行更新
            
        Returns:
            dict: 处理结果统计
        """
        # 加载CSV数据
        df = self.load_csv_data()
        if df is None:
            return {"error": "无法加载CSV数据"}
        
        print(f"\n{'=' * 60}")
        print(f"开始处理更新操作 ({'预览模式' if dry_run else '执行模式'})")
        print(f"{'=' * 60}")
        
        stats = {
            "total_records": len(df),
            "matched_records": 0,
            "updated_records": 0,
            "failed_updates": 0,
            "not_found": 0,
            "errors": []
        }
        
        for index, row in df.iterrows():
            md5_hash = str(row['file_md5']).strip()
            
            if not md5_hash or md5_hash == 'nan':
                print(f"跳过第 {index + 1} 行：MD5值为空")
                continue
            
            # 查找匹配的视频记录
            video_record = self.get_video_by_md5(md5_hash)
            
            if not video_record:
                print(f"未找到MD5匹配的视频记录: {md5_hash}")
                stats["not_found"] += 1
                continue
            
            video_id, title, current_description, current_tags, file_name = video_record
            stats["matched_records"] += 1
            
            # 合并描述字段
            new_description = self.combine_description_fields(row)
            
            # 获取新标签
            new_tags = str(row['存在的标签有']).strip() if pd.notna(row['存在的标签有']) else ""
            
            print(f"\n找到匹配记录:")
            print(f"  视频ID: {video_id}")
            print(f"  文件名: {file_name}")
            print(f"  标题: {title or '无'}")
            print(f"  MD5: {md5_hash}")
            print(f"  当前描述长度: {len(current_description or '')}")
            print(f"  新描述长度: {len(new_description)}")
            print(f"  当前标签: {current_tags or '无'}")
            print(f"  新标签: {new_tags or '无'}")
            
            if not dry_run:
                # 执行更新
                if self.update_video_record(video_id, new_description, new_tags):
                    print(f"  ✓ 更新成功")
                    stats["updated_records"] += 1
                else:
                    print(f"  ✗ 更新失败")
                    stats["failed_updates"] += 1
            else:
                print(f"  [预览] 将要更新此记录")
        
        # 打印统计结果
        print(f"\n{'=' * 60}")
        print(f"处理完成统计:")
        print(f"  总记录数: {stats['total_records']}")
        print(f"  匹配记录数: {stats['matched_records']}")
        print(f"  未找到记录数: {stats['not_found']}")
        
        if not dry_run:
            print(f"  成功更新数: {stats['updated_records']}")
            print(f"  更新失败数: {stats['failed_updates']}")
        else:
            print(f"  预计更新数: {stats['matched_records']}")
        
        return stats

def main():
    """主函数"""
    # 设置文件路径
    # 使用相对路径以支持不同环境(OneDrive-Personal/OneDrive-个人)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(current_dir, "analysis_out.csv")
    
    if not os.path.exists(csv_path):
        possible_paths = [
            "/Users/firewell/Library/CloudStorage/OneDrive-Personal/bioinfo/media/analysis_out.csv",
            "/Users/firewell/Library/CloudStorage/OneDrive-个人/bioinfo/media/analysis_out.csv"
        ]
        for p in possible_paths:
            if os.path.exists(p):
                csv_path = p
                break
    db_path = "media_library.db"
    
    # 检查文件是否存在
    if not os.path.exists(csv_path):
        print(f"错误：CSV文件不存在: {csv_path}")
        return
    
    if not os.path.exists(db_path):
        print(f"错误：数据库文件不存在: {db_path}")
        return
    
    # 创建更新器
    updater = VideoDescriptionUpdater(db_path, csv_path)
    
    # 首先运行预览模式
    print("正在运行预览模式...")
    stats = updater.process_updates(dry_run=True)
    
    if stats.get("error"):
        print(f"错误: {stats['error']}")
        return
    
    if stats["matched_records"] == 0:
        print("没有找到匹配的记录，无需更新")
        return
    
    # 询问是否执行实际更新
    print(f"\n预览完成，找到 {stats['matched_records']} 条匹配记录")
    confirm = input("是否执行实际更新？(y/n): ").strip().lower()
    
    if confirm == 'y':
        print("\n正在执行实际更新...")
        final_stats = updater.process_updates(dry_run=False)
        print(f"\n更新完成！成功更新了 {final_stats['updated_records']} 条记录")
    else:
        print("操作已取消")

if __name__ == "__main__":
    main()