#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量更新演员信息脚本
基于actor_crawler_headless_db.py，批量爬取和更新所有有演员链接的记录
"""

import sqlite3
import time
import random
from datetime import datetime
import re
import os

# 导入现有的爬虫类
from actor_crawler_headless_db import ActorCrawlerHeadlessDB

class BatchActorUpdater:
    def __init__(self, db_path="media_library.db"):
        self.db_path = db_path
        self.crawler = None
        
        # 统计信息
        self.stats = {
            'total': 0,
            'updated': 0,
            'failed': 0,
            'skipped': 0
        }
    
    def setup_driver(self):
        """初始化爬虫"""
        try:
            self.crawler = ActorCrawlerHeadlessDB()
            print("Edge驱动初始化成功，已配置SOCKS5代理")
            return True
        except Exception as e:
            print(f"❌ 爬虫初始化失败: {e}")
            return False
    
    def get_actors_to_update(self, limit=None):
        """获取需要更新的演员列表"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 查询所有有profile_url的演员，优先更新从未爬取过的
            query = """
            SELECT id, name, profile_url, last_crawled_at 
            FROM actors 
            WHERE profile_url IS NOT NULL AND profile_url != ''
            ORDER BY 
                CASE WHEN last_crawled_at IS NULL THEN 0 ELSE 1 END,
                last_crawled_at ASC
            """
            
            if limit:
                query += f" LIMIT {limit}"
            
            cursor.execute(query)
            actors = cursor.fetchall()
            
            conn.close()
            return actors
            
        except Exception as e:
            print(f"❌ 获取演员列表失败: {e}")
            return []
    

    

    
    def run_batch_update(self, limit=None, delay_range=(2, 5)):
        """运行批量更新"""
        print("=== 开始批量更新演员信息 ===")
        
        # 初始化爬虫
        if not self.setup_driver():
            return False
        
        try:
            # 获取需要更新的演员列表
            actors = self.get_actors_to_update(limit)
            self.stats['total'] = len(actors)
            
            if not actors:
                print("没有找到需要更新的演员")
                return True
            
            print(f"找到 {len(actors)} 个演员需要更新")
            
            for i, (actor_id, name, profile_url, last_crawled) in enumerate(actors, 1):
                print(f"\n[{i}/{len(actors)}] 处理演员: {name} (ID: {actor_id})")
                print(f"URL: {profile_url}")
                print(f"上次爬取: {last_crawled or '从未爬取'}")
                
                # 使用爬虫更新演员信息
                actor_id_result = self.crawler.crawl_and_save_actor(profile_url)
                
                if actor_id_result:
                    self.stats['updated'] += 1
                    print(f"✅ 成功更新演员: {name} (数据库ID: {actor_id_result})")
                else:
                    self.stats['failed'] += 1
                    print(f"❌ 更新失败: {name}")
                
                # 随机延迟
                if i < len(actors):  # 最后一个不需要延迟
                    delay = random.uniform(delay_range[0], delay_range[1])
                    print(f"等待 {delay:.1f} 秒...")
                    time.sleep(delay)
            
            return True
            
        except KeyboardInterrupt:
            print("\n用户中断操作")
            return False
        except Exception as e:
            print(f"❌ 批量更新过程中出错: {e}")
            return False
        finally:
            if self.crawler:
                self.crawler.close_driver()
            print("WebDriver 已关闭")
    
    def print_stats(self):
        """打印统计信息"""
        print("\n=== 更新统计 ===")
        print(f"总计: {self.stats['total']}")
        print(f"成功: {self.stats['updated']}")
        print(f"失败: {self.stats['failed']}")
        print(f"跳过: {self.stats['skipped']}")
        
        if self.stats['total'] > 0:
            success_rate = (self.stats['updated'] / self.stats['total']) * 100
            print(f"成功率: {success_rate:.1f}%")

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='批量更新演员信息')
    parser.add_argument('--limit', type=int, help='限制更新数量')
    parser.add_argument('--min-delay', type=float, default=2.0, help='最小延迟时间（秒）')
    parser.add_argument('--max-delay', type=float, default=5.0, help='最大延迟时间（秒）')
    
    args = parser.parse_args()
    
    updater = BatchActorUpdater()
    
    try:
        success = updater.run_batch_update(
            limit=args.limit,
            delay_range=(args.min_delay, args.max_delay)
        )
        
        updater.print_stats()
        
        if success:
            print("\n✅ 批量更新完成")
        else:
            print("\n❌ 批量更新失败")
            
    except Exception as e:
        print(f"❌ 程序执行出错: {e}")
        updater.print_stats()

if __name__ == "__main__":
    main()