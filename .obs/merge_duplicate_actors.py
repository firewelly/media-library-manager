#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
演员重复记录合并脚本
检测并合并具有相同profile_url的演员记录
合并原则：
1. 以最近爬取过的记录为准（last_crawled_at最新的）
2. 将其他记录的名称合并到alias字段中
3. 删除重复记录，保留主记录
"""

import sqlite3
import os
from datetime import datetime
import argparse

class ActorMerger:
    def __init__(self, db_path='media_library.db'):
        self.db_path = db_path
        
    def find_duplicate_actors(self):
        """查找具有相同profile_url的重复演员记录"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 查找重复的profile_url
            cursor.execute("""
                SELECT profile_url, COUNT(*) as count, 
                       GROUP_CONCAT(id) as ids, 
                       GROUP_CONCAT(name) as names,
                       GROUP_CONCAT(name_common) as common_names,
                       GROUP_CONCAT(name_traditional) as traditional_names,
                       GROUP_CONCAT(aliases) as all_aliases,
                       GROUP_CONCAT(last_crawled_at) as crawl_times
                FROM actors 
                WHERE profile_url IS NOT NULL AND profile_url != '' 
                GROUP BY profile_url 
                HAVING COUNT(*) > 1 
                ORDER BY count DESC
            """)
            
            duplicates = cursor.fetchall()
            print(f"发现 {len(duplicates)} 组重复记录")
            
            return duplicates
            
        except Exception as e:
            print(f"查找重复记录失败: {e}")
            return []
        finally:
            conn.close()
    
    def find_comma_separated_actors(self):
        """查找名字中包含逗号的演员记录（可能是多个演员被错误合并）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT id, name, name_common, name_traditional, aliases, profile_url
                FROM actors 
                WHERE name LIKE '%,%' OR name_common LIKE '%,%' OR name_traditional LIKE '%,%'
                ORDER BY id
            """)
            
            comma_actors = cursor.fetchall()
            print(f"发现 {len(comma_actors)} 个包含逗号的演员记录")
            
            return comma_actors
            
        except Exception as e:
            print(f"查找包含逗号的演员记录失败: {e}")
            return []
        finally:
            conn.close()
    
    def get_actor_details(self, actor_ids):
        """获取指定演员ID的详细信息"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            placeholders = ','.join(['?' for _ in actor_ids])
            cursor.execute(f"""
                SELECT id, name, name_common, name_traditional, aliases, 
                       avatar_url, avatar_data, profile_url, last_crawled_at,
                       created_at, updated_at
                FROM actors 
                WHERE id IN ({placeholders})
                ORDER BY 
                    CASE WHEN last_crawled_at IS NULL THEN 1 ELSE 0 END,
                    last_crawled_at DESC,
                    updated_at DESC
            """, actor_ids)
            
            return cursor.fetchall()
            
        except Exception as e:
            print(f"获取演员详细信息失败: {e}")
            return []
        finally:
            conn.close()
    
    def merge_aliases(self, actors_data):
        """合并演员的所有名称到别名中"""
        all_names = set()
        main_actor = actors_data[0]  # 第一个是最新爬取的
        
        # 收集所有名称
        for actor in actors_data:
            # 添加各种名称
            if actor[1]:  # name
                all_names.add(actor[1].strip())
            if actor[2]:  # name_common
                all_names.add(actor[2].strip())
            if actor[3]:  # name_traditional
                all_names.add(actor[3].strip())
            if actor[4]:  # aliases
                # 分割现有别名
                existing_aliases = [alias.strip() for alias in actor[4].split(',') if alias.strip()]
                all_names.update(existing_aliases)
        
        # 移除主记录的当前名称（避免重复）
        main_names = {main_actor[1], main_actor[2], main_actor[3]}
        alias_names = all_names - main_names - {'', None}
        
        return ', '.join(sorted(alias_names)) if alias_names else ''
    
    def merge_actors_by_url(self, source_id, target_id):
        """基于URL相同将源演员合并到目标演员，确保名称字段不包含逗号"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 获取源演员和目标演员的信息
            cursor.execute("""
                SELECT id, name, name_common, name_traditional, aliases
                FROM actors WHERE id IN (?, ?)
            """, (source_id, target_id))
            
            actors = cursor.fetchall()
            if len(actors) != 2:
                print(f"无法找到演员记录: source_id={source_id}, target_id={target_id}")
                return False
            
            source_actor = actors[0] if actors[0][0] == source_id else actors[1]
            target_actor = actors[1] if actors[1][0] == target_id else actors[0]
            
            # 收集所有名称
            all_names = set()
            
            for actor in [source_actor, target_actor]:
                if actor[1]:  # name
                    names = [n.strip() for n in actor[1].split(',') if n.strip()]
                    all_names.update(names)
                if actor[2]:  # name_common
                    names = [n.strip() for n in actor[2].split(',') if n.strip()]
                    all_names.update(names)
                if actor[3]:  # name_traditional
                    names = [n.strip() for n in actor[3].split(',') if n.strip()]
                    all_names.update(names)
                if actor[4]:  # aliases
                    aliases = [alias.strip() for alias in actor[4].split(',') if alias.strip()]
                    all_names.update(aliases)
            
            # 移除空字符串
            all_names.discard('')
            
            # 选择目标演员的主名称（确保不包含逗号）
            target_name = target_actor[1] or ''
            if ',' in target_name:
                target_name = target_name.split(',')[0].strip()
            
            # 如果目标名称为空，从所有名称中选择一个
            if not target_name and all_names:
                target_name = sorted(all_names)[0]
            
            # 移除主名称，剩余的作为别名
            all_names.discard(target_name)
            merged_aliases = ', '.join(sorted(all_names)) if all_names else ''
            
            # 更新目标演员，确保名称字段不包含逗号
            cursor.execute("""
                UPDATE actors SET 
                    name = ?,
                    name_common = ?,
                    name_traditional = ?,
                    aliases = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (target_name, target_name, target_name, merged_aliases, target_id))
            
            # 更新video_actors表中的关联关系
            cursor.execute("""
                UPDATE video_actors 
                SET actor_id = ? 
                WHERE actor_id = ?
            """, (target_id, source_id))
            
            # 删除可能的重复关联
            cursor.execute("""
                DELETE FROM video_actors 
                WHERE rowid NOT IN (
                    SELECT MIN(rowid) 
                    FROM video_actors 
                    GROUP BY video_id, actor_id
                )
            """)
            
            # 删除源演员记录
            cursor.execute("DELETE FROM actors WHERE id = ?", (source_id,))
            
            conn.commit()
            print(f"成功合并演员 {source_id} 到 {target_id}，主名称: {target_name}")
            return True
            
        except Exception as e:
            print(f"合并演员失败: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def merge_duplicate_group_by_url(self, profile_url, actor_ids, dry_run=True):
        """基于URL相同合并一组重复的演员记录，保留ID最小的记录"""
        print(f"\n处理重复组: {profile_url}")
        print(f"演员ID: {actor_ids}")
        
        # 获取详细信息
        actors_data = self.get_actor_details(actor_ids)
        if not actors_data:
            print("无法获取演员详细信息")
            return False
        
        # 选择ID最小的记录作为主记录
        target_id = min(actor_ids)
        target_actor = None
        other_actors = []
        
        for actor in actors_data:
            if actor[0] == target_id:
                target_actor = actor
            else:
                other_actors.append(actor)
        
        if not target_actor:
            print("无法找到目标记录")
            return False
        
        print(f"主记录: ID={target_actor[0]}, 名称={target_actor[1]}")
        for actor in other_actors:
            print(f"待合并: ID={actor[0]}, 名称={actor[1]}")
        
        if dry_run:
            print("[DRY RUN] 不执行实际合并操作")
            return True
        
        # 执行合并
        success = True
        for other_actor in other_actors:
            if not self.merge_actors_by_url(other_actor[0], target_id):
                success = False
                break
        
        if success:
            print(f"成功合并演员记录，保留ID: {target_id}，删除ID: {[actor[0] for actor in other_actors]}")
        
        return success
    
    def find_existing_actor_by_name(self, name):
        """查找是否已存在同名演员（在name、name_common、name_traditional或aliases中）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT id, name, name_common, name_traditional, aliases
                FROM actors 
                WHERE name = ? OR name_common = ? OR name_traditional = ? 
                   OR aliases LIKE ? OR aliases LIKE ? OR aliases LIKE ?
                LIMIT 1
            """, (name, name, name, f"%{name}%", f"{name},%", f"%, {name}%"))
            
            result = cursor.fetchone()
            return result
            
        except Exception as e:
            print(f"查找现有演员失败: {e}")
            return None
        finally:
            conn.close()
    
    def merge_actor_into_existing(self, source_actor_id, target_actor_id, source_name):
        """将源演员合并到目标演员"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 获取目标演员的当前别名
            cursor.execute("SELECT aliases FROM actors WHERE id = ?", (target_actor_id,))
            target_aliases = cursor.fetchone()[0] or ''
            
            # 将源演员名称添加到目标演员的别名中
            if target_aliases:
                if source_name not in target_aliases:
                    new_aliases = f"{target_aliases}, {source_name}"
                else:
                    new_aliases = target_aliases
            else:
                new_aliases = source_name
            
            # 更新目标演员的别名
            cursor.execute("""
                UPDATE actors SET aliases = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (new_aliases, target_actor_id))
            
            # 将源演员的视频关联转移到目标演员
            cursor.execute("""
                UPDATE video_actors SET actor_id = ? 
                WHERE actor_id = ? AND NOT EXISTS (
                    SELECT 1 FROM video_actors 
                    WHERE actor_id = ? AND video_id = video_actors.video_id
                )
            """, (target_actor_id, source_actor_id, target_actor_id))
            
            # 删除重复的视频关联
            cursor.execute("DELETE FROM video_actors WHERE actor_id = ?", (source_actor_id,))
            
            # 删除源演员记录
            cursor.execute("DELETE FROM actors WHERE id = ?", (source_actor_id,))
            
            conn.commit()
            print(f"成功将演员 ID={source_actor_id} 合并到 ID={target_actor_id}，别名更新为: {new_aliases}")
            return True
            
        except Exception as e:
            print(f"合并演员失败: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def split_comma_separated_actor(self, actor_data, dry_run=True):
        """拆分包含逗号的演员记录"""
        actor_id, name, name_common, name_traditional, aliases, profile_url = actor_data
        
        print(f"\n处理包含逗号的演员记录: ID={actor_id}")
        print(f"名称: {name}")
        print(f"常用名: {name_common}")
        print(f"繁体名: {name_traditional}")
        
        # 分析哪个字段包含逗号
        names_to_split = []
        if name and ',' in name:
            names_to_split.extend([n.strip() for n in name.split(',') if n.strip()])
        if name_common and ',' in name_common:
            names_to_split.extend([n.strip() for n in name_common.split(',') if n.strip()])
        if name_traditional and ',' in name_traditional:
            names_to_split.extend([n.strip() for n in name_traditional.split(',') if n.strip()])
        
        # 去重
        unique_names = list(dict.fromkeys(names_to_split))  # 保持顺序的去重
        
        if len(unique_names) <= 1:
            print("没有发现需要拆分的多个名称")
            return False
        
        print(f"发现需要拆分的名称: {unique_names}")
        
        if dry_run:
            print("[DRY RUN] 不执行实际拆分操作")
            # 检查每个名称是否已存在
            for name_to_check in unique_names:
                existing = self.find_existing_actor_by_name(name_to_check)
                if existing:
                    print(f"  - {name_to_check}: 已存在 (ID={existing[0]})，将合并")
                else:
                    print(f"  - {name_to_check}: 不存在，将创建新记录")
            return True
        
        # 执行拆分
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 获取原记录的视频关联
            cursor.execute("SELECT video_id FROM video_actors WHERE actor_id = ?", (actor_id,))
            video_ids = [row[0] for row in cursor.fetchall()]
            
            # 处理第一个名称（更新原记录）
            first_name = unique_names[0]
            existing_first = self.find_existing_actor_by_name(first_name)
            
            if existing_first and existing_first[0] != actor_id:
                # 第一个名称已存在于其他记录中，合并到那个记录
                print(f"第一个名称 '{first_name}' 已存在于 ID={existing_first[0]}，将合并")
                if not self.merge_actor_into_existing(actor_id, existing_first[0], name):
                    return False
                processed_actor_id = existing_first[0]
            else:
                # 更新原记录为第一个名称
                cursor.execute("""
                    UPDATE actors SET 
                        name = ?, name_common = ?, name_traditional = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (first_name, first_name, first_name, actor_id))
                print(f"更新原记录 ID={actor_id} 为: {first_name}")
                processed_actor_id = actor_id
            
            # 处理其他名称
            for name_to_create in unique_names[1:]:
                existing = self.find_existing_actor_by_name(name_to_create)
                
                if existing:
                    # 名称已存在，将视频关联合并到现有记录
                    print(f"名称 '{name_to_create}' 已存在于 ID={existing[0]}，合并视频关联")
                    for video_id in video_ids:
                        cursor.execute("""
                            INSERT OR IGNORE INTO video_actors (video_id, actor_id, created_at)
                            VALUES (?, ?, CURRENT_TIMESTAMP)
                        """, (video_id, existing[0]))
                else:
                    # 创建新记录
                    cursor.execute("""
                        INSERT INTO actors (
                            name, name_common, name_traditional, aliases,
                            avatar_url, avatar_data, profile_url,
                            created_at, updated_at
                        ) VALUES (?, ?, ?, ?, NULL, NULL, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """, (name_to_create, name_to_create, name_to_create, aliases or ''))
                    
                    new_actor_id = cursor.lastrowid
                    print(f"创建新演员记录 ID={new_actor_id} 为: {name_to_create}")
                    
                    # 复制视频关联
                    for video_id in video_ids:
                        cursor.execute("""
                            INSERT OR IGNORE INTO video_actors (video_id, actor_id, created_at)
                            VALUES (?, ?, CURRENT_TIMESTAMP)
                        """, (video_id, new_actor_id))
            
            conn.commit()
            print(f"成功处理包含逗号的演员记录 ID={actor_id}")
            return True
            
        except Exception as e:
            print(f"拆分失败: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def find_name_based_duplicates(self):
        """查找基于名称的重复演员（在不同字段中出现相同名称）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 查找所有可能的重复情况
            cursor.execute("""
                WITH all_names AS (
                    SELECT id, name as actor_name, 'name' as name_type FROM actors WHERE name IS NOT NULL
                    UNION ALL
                    SELECT id, name_common as actor_name, 'name_common' as name_type FROM actors WHERE name_common IS NOT NULL
                    UNION ALL
                    SELECT id, name_traditional as actor_name, 'name_traditional' as name_type FROM actors WHERE name_traditional IS NOT NULL
                ),
                duplicate_names AS (
                    SELECT actor_name, COUNT(DISTINCT id) as actor_count, GROUP_CONCAT(DISTINCT id) as actor_ids
                    FROM all_names
                    WHERE actor_name != ''
                    GROUP BY actor_name
                    HAVING COUNT(DISTINCT id) > 1
                )
                SELECT actor_name, actor_count, actor_ids FROM duplicate_names
                ORDER BY actor_count DESC
            """)
            
            duplicates = cursor.fetchall()
            print(f"发现 {len(duplicates)} 组基于名称的重复演员")
            
            return duplicates
            
        except Exception as e:
            print(f"查找基于名称的重复演员失败: {e}")
            return []
        finally:
            conn.close()
    
    def merge_name_based_duplicates(self, dry_run=True, limit=None):
        """合并基于名称的重复演员"""
        duplicates = self.find_name_based_duplicates()
        
        if not duplicates:
            print("没有发现基于名称的重复演员")
            return
        
        success_count = 0
        
        if limit:
            duplicates = duplicates[:limit]
            print(f"限制处理数量: {limit}")
        
        for i, (actor_name, actor_count, actor_ids_str) in enumerate(duplicates, 1):
            print(f"\n=== 处理第 {i}/{len(duplicates)} 组重复名称 ===")
            print(f"重复名称: {actor_name}")
            
            actor_ids = [int(id_str) for id_str in actor_ids_str.split(',')]
            print(f"涉及演员ID: {actor_ids}")
            
            if dry_run:
                print("[DRY RUN] 不执行实际合并操作")
                # 显示将要合并的演员详情
                details = self.get_actor_details(actor_ids)
                for detail in details:
                    print(f"  ID={detail[0]}: {detail[1]} | {detail[2]} | {detail[3]}")
                success_count += 1
            else:
                # 选择最完整的记录作为目标（有profile_url且last_crawled_at最新的）
                target_id = self.select_best_actor_record(actor_ids)
                if target_id:
                    merge_success = True
                    for source_id in actor_ids:
                        if source_id != target_id:
                            if not self.merge_actor_into_existing(source_id, target_id, actor_name):
                                merge_success = False
                                break
                    
                    if merge_success:
                        success_count += 1
                        print(f"成功合并到 ID={target_id}")
                    else:
                        print(f"合并失败: {actor_name}")
                else:
                    print(f"无法确定最佳目标记录: {actor_name}")
        
        print(f"\n=== 名称合并完成 ===")
        print(f"总共处理: {len(duplicates)} 组")
        print(f"成功合并: {success_count} 组")
        print(f"失败: {len(duplicates) - success_count} 组")
        
        if not dry_run:
            # 显示合并后的统计
            self.show_statistics()
    
    def select_best_actor_record(self, actor_ids):
        """从多个演员记录中选择最佳的作为合并目标"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 获取所有候选记录的详细信息
            placeholders = ','.join(['?'] * len(actor_ids))
            cursor.execute(f"""
                SELECT id, name, profile_url, last_crawled_at, avatar_data,
                       CASE WHEN profile_url IS NOT NULL THEN 1 ELSE 0 END as has_url,
                       CASE WHEN last_crawled_at IS NOT NULL THEN 1 ELSE 0 END as has_crawled,
                       CASE WHEN avatar_data IS NOT NULL THEN 1 ELSE 0 END as has_avatar
                FROM actors 
                WHERE id IN ({placeholders})
                ORDER BY has_crawled DESC, has_url DESC, has_avatar DESC, last_crawled_at DESC
            """, actor_ids)
            
            records = cursor.fetchall()
            if records:
                return records[0][0]  # 返回最佳记录的ID
            
            return None
            
        except Exception as e:
            print(f"选择最佳记录失败: {e}")
            return None
        finally:
            conn.close()
    
    def process_comma_separated_actors(self, dry_run=True, limit=None):
        """处理所有包含逗号的演员记录"""
        comma_actors = self.find_comma_separated_actors()
        
        if not comma_actors:
            print("没有发现包含逗号的演员记录")
            return
        
        success_count = 0
        
        if limit:
            comma_actors = comma_actors[:limit]
            print(f"限制处理数量: {limit}")
        
        for i, actor_data in enumerate(comma_actors, 1):
            print(f"\n=== 处理第 {i}/{len(comma_actors)} 个包含逗号的记录 ===")
            
            if self.split_comma_separated_actor(actor_data, dry_run):
                success_count += 1
            else:
                print(f"拆分失败: ID={actor_data[0]}")
        
        print(f"\n=== 拆分完成 ===")
        print(f"总共处理: {len(comma_actors)} 个记录")
        print(f"成功拆分: {success_count} 个记录")
        print(f"失败: {len(comma_actors) - success_count} 个记录")
        
        if not dry_run:
            # 显示拆分后的统计
            self.show_statistics()
    
    def merge_all_duplicates(self, dry_run=True, limit=None):
        """合并所有重复记录（基于URL相同）"""
        duplicates = self.find_duplicate_actors()
        
        if not duplicates:
            print("没有发现重复记录")
            return
        
        success_count = 0
        total_count = len(duplicates)
        
        if limit:
            duplicates = duplicates[:limit]
            print(f"限制处理数量: {limit}")
        
        for i, (profile_url, count, ids_str, names_str, _, _, _, _) in enumerate(duplicates, 1):
            print(f"\n=== 处理第 {i}/{len(duplicates)} 组 ===")
            
            actor_ids = [int(id_str) for id_str in ids_str.split(',')]
            
            if self.merge_duplicate_group_by_url(profile_url, actor_ids, dry_run):
                success_count += 1
            else:
                print(f"合并失败: {profile_url}")
        
        print(f"\n=== 合并完成 ===")
        print(f"总共处理: {len(duplicates)} 组")
        print(f"成功合并: {success_count} 组")
        print(f"失败: {len(duplicates) - success_count} 组")
        
        if not dry_run:
            # 显示合并后的统计
            self.show_statistics()
    
    def show_statistics(self):
        """显示数据库统计信息"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_actors,
                    COUNT(DISTINCT profile_url) as unique_urls,
                    COUNT(CASE WHEN profile_url IS NOT NULL AND profile_url != '' THEN 1 END) as has_url
                FROM actors
            """)
            
            stats = cursor.fetchone()
            print(f"\n=== 数据库统计 ===")
            print(f"总演员数: {stats[0]}")
            print(f"唯一URL数: {stats[1]}")
            print(f"有URL的演员: {stats[2]}")
            
        except Exception as e:
            print(f"获取统计信息失败: {e}")
        finally:
            conn.close()

def main():
    parser = argparse.ArgumentParser(description='合并重复的演员记录和处理包含逗号的演员名称')
    parser.add_argument('--dry-run', action='store_true', default=True,
                       help='只显示将要执行的操作，不实际修改数据库（默认）')
    parser.add_argument('--execute', action='store_true',
                       help='实际执行合并操作')
    parser.add_argument('--limit', type=int,
                       help='限制处理的重复组数量')
    parser.add_argument('--db-path', default='media_library.db',
                       help='数据库文件路径')
    parser.add_argument('--split-comma', action='store_true',
                       help='处理包含逗号的演员名称（拆分为独立记录）')
    parser.add_argument('--merge-duplicates', action='store_true',
                       help='合并重复的演员记录（基于profile_url）')
    parser.add_argument('--merge-url', action='store_true',
                       help='合并基于profile_url的重复演员（同--merge-duplicates）')
    parser.add_argument('--merge-names', action='store_true',
                       help='合并基于名称的重复演员')
    
    args = parser.parse_args()
    
    # 如果指定了--execute，则不是dry run
    dry_run = not args.execute
    
    if not os.path.exists(args.db_path):
        print(f"错误：找不到数据库文件 {args.db_path}")
        return
    
    merger = ActorMerger(args.db_path)
    
    print(f"演员记录处理工具")
    print(f"数据库: {args.db_path}")
    print(f"模式: {'预览模式' if dry_run else '执行模式'}")
    
    if dry_run:
        print("\n注意：当前为预览模式，不会修改数据库")
        print("使用 --execute 参数来实际执行操作")
    
    # 显示当前统计
    merger.show_statistics()
    
    # 根据参数决定执行哪种操作
    if args.split_comma:
        print("\n=== 处理包含逗号的演员名称 ===")
        merger.process_comma_separated_actors(dry_run=dry_run, limit=args.limit)
    elif args.merge_duplicates or args.merge_url:
        print("\n=== 合并重复的演员记录（基于profile_url） ===")
        merger.merge_all_duplicates(dry_run=dry_run, limit=args.limit)
    elif args.merge_names:
        print("\n=== 合并基于名称的重复演员 ===")
        merger.merge_name_based_duplicates(dry_run=dry_run, limit=args.limit)
    else:
        # 默认先处理逗号分隔的名称，再合并重复记录
        print("\n=== 第一步：处理包含逗号的演员名称 ===")
        merger.process_comma_separated_actors(dry_run=dry_run, limit=args.limit)
        
        print("\n=== 第二步：合并重复的演员记录（基于profile_url） ===")
        merger.merge_all_duplicates(dry_run=dry_run, limit=args.limit)
        
        print("\n=== 第三步：合并基于名称的重复演员 ===")
        merger.merge_name_based_duplicates(dry_run=dry_run, limit=args.limit)

if __name__ == '__main__':
    main()