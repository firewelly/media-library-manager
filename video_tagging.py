#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频自动标签系统
基于词汇表为数据库中的视频进行自动打标签
使用轻量级方法确保显存使用低于8G

作者: AI Assistant
创建时间: 2024
"""

import sqlite3
import os
import re
import json
from datetime import datetime
from collections import Counter
import jieba
import jieba.analyse
from pathlib import Path

class VideoTagger:
    def __init__(self, db_path="media_library.db", vocabulary_file="vocabulary_tags.txt"):
        """
        初始化视频标签器
        
        Args:
            db_path (str): 数据库文件路径
            vocabulary_file (str): 词汇表文件路径
        """
        self.db_path = db_path
        self.vocabulary_file = vocabulary_file
        self.vocabulary = self._load_vocabulary()
        self.tag_rules = self._create_tag_rules()
        
        # 配置结巴分词
        jieba.initialize()
        
    def _load_vocabulary(self):
        """
        从词汇文件中加载词汇表（每行一个词汇）
        
        Returns:
            dict: 词汇及其权重的字典
        """
        vocabulary = {}
        
        if not os.path.exists(self.vocabulary_file):
            print(f"警告：词汇表文件 {self.vocabulary_file} 不存在")
            return vocabulary
        
        try:
            with open(self.vocabulary_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            # 读取每行词汇
            for i, line in enumerate(lines):
                word = line.strip()
                if word and len(word) >= 2:
                    # 为每个词汇分配权重，排名越靠前权重越高
                    freq = len(lines) - i  # 基于位置的频次
                    tfidf = 1.0 - (i / len(lines))  # 基于位置的TF-IDF权重
                    vocabulary[word] = {
                        'freq': freq, 
                        'tfidf': tfidf, 
                        'type': 'vocab'
                    }
            
            print(f"加载词汇表完成，共 {len(vocabulary)} 个词汇")
            return vocabulary
            
        except Exception as e:
            print(f"加载词汇表失败：{e}")
            return {}
    
    def _create_tag_rules(self):
        """
        创建标签规则
        基于词汇的语义和频率创建分类规则
        
        Returns:
            dict: 标签规则字典
        """
        rules = {
            # 人物特征标签
            '人物特征': {
                'keywords': ['少妇', '人妻', '女神', '美女', '御姐', '学妹', '学姐', '老师', '阿姨', '妹子'],
                'weight_threshold': 0.01,
                'freq_threshold': 20
            },
            
            # 身材特征标签
            '身材特征': {
                'keywords': ['巨乳', '大奶', '身材', '颜值', '高颜值', '漂亮', '性感', '清纯'],
                'weight_threshold': 0.01,
                'freq_threshold': 20
            },
            
            # 服装道具标签
            '服装道具': {
                'keywords': ['黑丝', '丝袜', '肉丝', '眼镜', '情趣'],
                'weight_threshold': 0.01,
                'freq_threshold': 15
            },
            
            # 情节类型标签
            '情节类型': {
                'keywords': ['偷情', '出轨', '绿帽', '调教', '勾引', '约炮', '背着'],
                'weight_threshold': 0.01,
                'freq_threshold': 15
            },
            
            # 场景地点标签
            '场景地点': {
                'keywords': ['酒店', '床上', '开房'],
                'weight_threshold': 0.01,
                'freq_threshold': 10
            },
            
            # 关系标签
            '人物关系': {
                'keywords': ['老公', '老婆', '女友', '男友', '闺蜜', '兄弟'],
                'weight_threshold': 0.01,
                'freq_threshold': 15
            },
            
            # 品质标签
            '品质特征': {
                'keywords': ['极品', '真实', '反差', '刺激', '疯狂', '高能', '完美', '顶级', '超级'],
                'weight_threshold': 0.01,
                'freq_threshold': 15
            }
        }
        
        return rules
    
    def get_test_videos(self, limit=3):
        """
        获取用于测试的大视频文件
        
        Args:
            limit (int): 返回的视频数量
            
        Returns:
            list: 视频信息列表
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 查询最大的几个视频文件
            cursor.execute("""
                SELECT id, file_name, file_path, file_size, title, tags 
                FROM videos 
                WHERE file_size IS NOT NULL AND file_size > 1000000000
                ORDER BY file_size DESC 
                LIMIT ?
            """, (limit,))
            
            videos = cursor.fetchall()
            conn.close()
            
            return videos
            
        except Exception as e:
            print(f"获取测试视频失败：{e}")
            return []
    
    def extract_features_from_filename(self, filename):
        """
        从文件名中提取特征词汇
        
        Args:
            filename (str): 文件名
            
        Returns:
            list: 提取的特征词汇列表
        """
        if not filename:
            return []
        
        # 清理文件名，移除扩展名
        clean_name = os.path.splitext(filename)[0]
        
        # 特殊处理：番号格式识别和映射
        features = self._extract_from_av_code(clean_name)
        
        # 保留原有的分词逻辑作为补充
        # 清理特殊字符但保留中文
        clean_name_for_jieba = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9\s]', ' ', clean_name)
        
        # 使用结巴分词
        words = jieba.lcut(clean_name_for_jieba)
        
        # 过滤并匹配词汇表中的词汇
        for word in words:
            word = word.strip()
            if len(word) >= 2 and word in self.vocabulary and word not in features:
                features.append(word)
        
        # 直接字符串匹配词汇表中的词汇（处理分词可能遗漏的情况）
        for vocab_word in self.vocabulary:
            if vocab_word in clean_name and vocab_word not in features:
                features.append(vocab_word)
        
        return features
    
    def _extract_from_av_code(self, filename):
        """
        从AV番号中提取特征词汇
        
        Args:
            filename (str): 文件名
            
        Returns:
            list: 提取的特征词汇列表
        """
        features = []
        
        # 番号前缀映射表
        av_code_mapping = {
            'SHKD': ['强奸', '凌辱', '屈辱', '强暴'],
            'RBD': ['强奸', '凌辱', '屈辱'],
            'MDYD': ['人妻', '熟女', '少妇'],
            'JUX': ['人妻', '熟女'],
            'JUY': ['人妻', '熟女'],
            'JUL': ['人妻', '熟女'],
            'MEYD': ['人妻', '熟女'],
            'PRED': ['极品', '美女'],
            'SSIS': ['极品', '美女'],
            'SSNI': ['极品', '美女'],
            'MIDE': ['极品', '美女'],
            'EBOD': ['巨乳', '大奶'],
            'PPPD': ['巨乳', '大奶'],
            'JUFD': ['巨乳', '大奶'],
            'MIRD': ['多人', '群交'],
            'MIAE': ['学生', '校园'],
            'MXGS': ['学生', '校园'],
            'IENE': ['企划', '搭讪'],
            'HUNT': ['企划', '搭讪'],
            'DANDY': ['企划', '搭讪'],
            'NHDTA': ['企划', '搭讪'],
            'SW': ['企划', '搭讪'],
            'DVDES': ['企划', '搭讪'],
            'SDDE': ['企划', '搭讪'],
            'SDMU': ['企划', '搭讪'],
            'ATOM': ['企划', '搭讪'],
            'VRTM': ['VR'],
            'CRVR': ['VR'],
            'DSVR': ['VR'],
            'TMVR': ['VR'],
            'URVRSP': ['VR'],
            'AVVR': ['VR'],
            'NHVR': ['VR'],
            'KMVR': ['VR'],
            'WPVR': ['VR'],
            'SIVR': ['VR'],
            'BIKMVR': ['VR'],
            'KMPVR': ['VR'],
            'KAVR': ['VR'],
            'SAVR': ['VR'],
            'DOVR': ['VR'],
            'POVR': ['VR'],
            'EXVR': ['VR'],
            'MXVR': ['VR'],
            'REVR': ['VR'],
            'FSVR': ['VR'],
            'TPVR': ['VR'],
            'LOVR': ['VR'],
            'WVVR': ['VR'],
            'MMVR': ['VR'],
            'MTVR': ['VR'],
            'MUVR': ['VR'],
            'MYVR': ['VR'],
            'MZVR': ['VR'],
            'NAVR': ['VR'],
            'NCVR': ['VR'],
            'NDVR': ['VR'],
            'NEVR': ['VR'],
            'NFVR': ['VR'],
            'NGVR': ['VR'],
            'NHVR': ['VR'],
            'NIVR': ['VR'],
            'NJVR': ['VR'],
            'NKVR': ['VR'],
            'NLVR': ['VR'],
            'NMVR': ['VR'],
            'NNVR': ['VR'],
            'NOVR': ['VR'],
            'NPVR': ['VR'],
            'NQVR': ['VR'],
            'NRVR': ['VR'],
            'NSVR': ['VR'],
            'NTVR': ['VR'],
            'NUVR': ['VR'],
            'NVVR': ['VR'],
            'NWVR': ['VR'],
            'NXVR': ['VR'],
            'NYVR': ['VR'],
            'NZVR': ['VR']
        }
        
        # 职业相关番号映射
        profession_mapping = {
            'SHKD': ['护士'],  # SHKD-515特指护士，不应包含老师和秘书
            'RBD': ['护士', '老师', '秘书'],
            'JUX': ['护士', '老师'],
            'JUY': ['护士', '老师'],
            'MDYD': ['护士', '老师'],
            'MEYD': ['护士', '老师']
        }
        
        # 提取番号前缀
        # 匹配常见的番号格式：字母-数字
        code_match = re.match(r'^([A-Z]+)[\-_]?(\d+)', filename.upper())
        if code_match:
            prefix = code_match.group(1)
            number = code_match.group(2)
            
            # 根据前缀映射添加特征
            if prefix in av_code_mapping:
                for tag in av_code_mapping[prefix]:
                    if tag in self.vocabulary and tag not in features:
                        features.append(tag)
            
            # 添加职业相关标签（概率性添加）
            if prefix in profession_mapping:
                for tag in profession_mapping[prefix]:
                    if tag in self.vocabulary and tag not in features:
                        features.append(tag)
        
        return features
    
    def extract_features_from_title(self, title):
        """
        从标题中提取特征词汇
        
        Args:
            title (str): 标题
            
        Returns:
            list: 提取的特征词汇列表
        """
        if not title:
            return []
        
        # 清理标题
        clean_title = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9\s]', ' ', title)
        
        # 使用结巴分词
        words = jieba.lcut(clean_title)
        
        # 过滤并匹配词汇表中的词汇
        features = []
        for word in words:
            word = word.strip()
            if len(word) >= 2 and word in self.vocabulary:
                features.append(word)
        
        return features
    
    def generate_tags_from_features(self, features):
        """
        基于特征词汇生成标签
        
        Args:
            features (list): 特征词汇列表
            
        Returns:
            list: 生成的标签列表
        """
        if not features:
            return []
        
        generated_tags = set()
        feature_counter = Counter(features)
        
        # 根据标签规则生成标签
        for tag_category, rule in self.tag_rules.items():
            matched_keywords = []
            total_weight = 0
            total_freq = 0
            
            for keyword in rule['keywords']:
                if keyword in feature_counter:
                    matched_keywords.append(keyword)
                    if keyword in self.vocabulary:
                        total_weight += self.vocabulary[keyword].get('tfidf', 0)
                        total_freq += self.vocabulary[keyword].get('freq', 0)
            
            # 判断是否满足阈值条件
            if (matched_keywords and 
                (total_weight >= rule['weight_threshold'] or 
                 total_freq >= rule['freq_threshold'])):
                generated_tags.add(tag_category)
                
                # 添加具体的关键词作为标签
                for keyword in matched_keywords[:2]:  # 最多添加2个具体关键词
                    generated_tags.add(keyword)
        
        # 添加高频特征词作为标签
        for feature, count in feature_counter.most_common(5):
            if (feature in self.vocabulary and 
                (self.vocabulary[feature].get('freq', 0) >= 30 or 
                 self.vocabulary[feature].get('tfidf', 0) >= 0.02)):
                generated_tags.add(feature)
        
        return list(generated_tags)
    
    def merge_tags(self, existing_tags, new_tags):
        """
        合并现有标签和新生成的标签
        
        Args:
            existing_tags (str): 现有标签字符串
            new_tags (list): 新生成的标签列表
            
        Returns:
            str: 合并后的标签字符串
        """
        # 解析现有标签
        existing_set = set()
        if existing_tags:
            existing_set = set([tag.strip() for tag in existing_tags.split(',') if tag.strip()])
        
        # 合并标签
        all_tags = existing_set.union(set(new_tags))
        
        # 限制标签数量，优先保留高权重标签
        if len(all_tags) > 10:
            # 按词汇表中的权重排序
            sorted_tags = sorted(all_tags, key=lambda x: (
                self.vocabulary.get(x, {}).get('tfidf', 0) + 
                self.vocabulary.get(x, {}).get('freq', 0) * 0.001
            ), reverse=True)
            all_tags = set(sorted_tags[:10])
        
        return ', '.join(sorted(all_tags))
    
    def tag_video(self, video_info):
        """
        为单个视频生成标签
        
        Args:
            video_info (tuple): 视频信息元组 (id, file_name, file_path, file_size, title, tags)
            
        Returns:
            tuple: (video_id, new_tags, features_found)
        """
        video_id, file_name, file_path, file_size, title, existing_tags = video_info
        
        # 从文件名和标题中提取特征
        filename_features = self.extract_features_from_filename(file_name)
        title_features = self.extract_features_from_title(title)
        
        # 合并所有特征
        all_features = filename_features + title_features
        
        # 生成标签
        new_tags = self.generate_tags_from_features(all_features)
        
        # 合并现有标签
        final_tags = self.merge_tags(existing_tags, new_tags)
        
        return video_id, final_tags, all_features
    
    def update_video_tags(self, video_id, tags):
        """
        更新数据库中的视频标签
        
        Args:
            video_id (int): 视频ID
            tags (str): 标签字符串
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "UPDATE videos SET tags = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (tags, video_id)
            )
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"更新视频标签失败 (ID: {video_id}): {e}")
    
    def test_tagging(self, limit=3):
        """
        测试标签功能，使用几个大视频文件
        
        Args:
            limit (int): 测试的视频数量
        """
        print("开始视频标签测试...")
        print("=" * 50)
        
        # 获取测试视频
        test_videos = self.get_test_videos(limit)
        
        if not test_videos:
            print("没有找到合适的测试视频")
            return
        
        print(f"找到 {len(test_videos)} 个测试视频：")
        
        results = []
        
        for i, video in enumerate(test_videos, 1):
            video_id, file_name, file_path, file_size, title, existing_tags = video
            
            print(f"\n{i}. 处理视频：{file_name}")
            print(f"   文件大小：{file_size / (1024**3):.2f} GB")
            print(f"   标题：{title or '无'}")
            print(f"   现有标签：{existing_tags or '无'}")
            
            # 生成标签
            new_video_id, final_tags, features = self.tag_video(video)
            
            print(f"   提取特征：{', '.join(features) if features else '无'}")
            print(f"   生成标签：{final_tags or '无'}")
            
            # 保存结果
            results.append({
                'video_id': video_id,
                'file_name': file_name,
                'original_tags': existing_tags,
                'new_tags': final_tags,
                'features': features
            })
            
            # 询问是否更新
            if final_tags != existing_tags:
                update = input(f"   是否更新标签？(y/n): ").lower().strip()
                if update == 'y':
                    self.update_video_tags(video_id, final_tags)
                    print(f"   ✓ 标签已更新")
                else:
                    print(f"   - 跳过更新")
            else:
                print(f"   - 标签无变化")
        
        # 生成测试报告
        self.generate_test_report(results)
    
    def generate_test_report(self, results):
        """
        生成测试报告
        
        Args:
            results (list): 测试结果列表
        """
        report_file = f"tagging_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("视频标签测试报告\n")
            f.write("=" * 50 + "\n")
            f.write(f"测试时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"测试视频数量：{len(results)}\n")
            f.write(f"词汇表大小：{len(self.vocabulary)}\n")
            f.write("\n")
            
            for i, result in enumerate(results, 1):
                f.write(f"{i}. {result['file_name']}\n")
                f.write(f"   原始标签：{result['original_tags'] or '无'}\n")
                f.write(f"   新生成标签：{result['new_tags'] or '无'}\n")
                f.write(f"   提取特征：{', '.join(result['features']) if result['features'] else '无'}\n")
                f.write("\n")
            
            # 统计信息
            total_features = sum(len(r['features']) for r in results)
            avg_features = total_features / len(results) if results else 0
            
            f.write("统计信息\n")
            f.write("-" * 30 + "\n")
            f.write(f"平均提取特征数：{avg_features:.2f}\n")
            f.write(f"总提取特征数：{total_features}\n")
            
            # 特征频率统计
            all_features = []
            for result in results:
                all_features.extend(result['features'])
            
            if all_features:
                feature_counter = Counter(all_features)
                f.write("\n特征频率统计\n")
                f.write("-" * 30 + "\n")
                for feature, count in feature_counter.most_common(10):
                    f.write(f"{feature}: {count}\n")
        
        print(f"\n测试报告已保存到：{report_file}")
    
    def batch_tag_all_videos(self, batch_size=100):
        """
        批量为所有视频生成标签
        
        Args:
            batch_size (int): 批处理大小
        """
        print("开始批量标签生成...")
        print("=" * 50)
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 获取所有视频数量
            cursor.execute("SELECT COUNT(*) FROM videos")
            total_videos = cursor.fetchone()[0]
            
            print(f"数据库中共有 {total_videos} 个视频")
            
            processed = 0
            updated = 0
            
            # 分批处理
            for offset in range(0, total_videos, batch_size):
                cursor.execute("""
                    SELECT id, file_name, file_path, file_size, title, tags 
                    FROM videos 
                    LIMIT ? OFFSET ?
                """, (batch_size, offset))
                
                batch_videos = cursor.fetchall()
                
                for video in batch_videos:
                    video_id, final_tags, features = self.tag_video(video)
                    
                    # 检查是否有变化
                    if final_tags != video[5]:  # video[5] 是原始tags
                        self.update_video_tags(video_id, final_tags)
                        updated += 1
                    
                    processed += 1
                    
                    if processed % 50 == 0:
                        print(f"已处理：{processed}/{total_videos} ({processed/total_videos*100:.1f}%)")
            
            conn.close()
            
            print(f"\n批量标签生成完成！")
            print(f"总处理视频：{processed}")
            print(f"更新标签：{updated}")
            
        except Exception as e:
            print(f"批量标签生成失败：{e}")

def main():
    """
    主函数
    """
    print("视频自动标签系统")
    print("=" * 30)
    
    # 检查必要文件
    if not os.path.exists("media_library.db"):
        print("错误：找不到数据库文件 media_library.db")
        return
    
    if not os.path.exists("vocabulary_tags.txt"):
        print("错误：找不到词汇表文件 vocabulary_tags.txt")
        print("请确保词汇表文件存在")
        return
    
    # 创建标签器
    tagger = VideoTagger()
    
    print("\n选择操作模式：")
    print("1. 测试模式（3个大视频）")
    print("2. 批量模式（所有视频）")
    
    choice = input("请选择 (1/2): ").strip()
    
    if choice == '1':
        tagger.test_tagging(3)
    elif choice == '2':
        confirm = input("确认要为所有视频生成标签吗？这可能需要较长时间 (y/n): ").lower().strip()
        if confirm == 'y':
            tagger.batch_tag_all_videos()
        else:
            print("操作已取消")
    else:
        print("无效选择")

if __name__ == "__main__":
    main()