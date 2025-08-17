#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
媒体库标题分析工具
从数据库中提取所有视频标题，使用结巴分词进行分词分析，
提取热词和高频词汇，生成Top 100词汇列表。

作者: AI Assistant
创建时间: 2024
"""

import sqlite3
import jieba
import jieba.analyse
from collections import Counter
import re
import os
from datetime import datetime

class TitleAnalyzer:
    def __init__(self, db_path="media_library.db"):
        """
        初始化标题分析器
        
        Args:
            db_path (str): 数据库文件路径
        """
        self.db_path = db_path
        self.stop_words = self._load_stop_words()
        
        # 配置结巴分词
        jieba.initialize()
        
    def _load_stop_words(self):
        """
        加载停用词列表
        
        Returns:
            set: 停用词集合
        """
        # 基础停用词
        stop_words = {
            '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个',
            '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好',
            '自己', '这', '那', '里', '来', '个', '把', '让', '给', '被', '从', '向',
            '以', '为', '与', '及', '或', '而', '但', '如果', '因为', '所以', '虽然',
            '然而', '因此', '于是', '接着', '然后', '最后', '首先', '其次', '再次',
            '同时', '另外', '此外', '除了', '包括', '根据', '按照', '通过', '由于',
            '关于', '对于', '至于', '无论', '不管', '只要', '只有', '除非', '即使',
            '尽管', '虽说', '话说', '据说', '听说', '看来', '似乎', '好像', '可能',
            '也许', '大概', '估计', '应该', '必须', '需要', '想要', '希望', '打算',
            '准备', '开始', '继续', '停止', '结束', '完成', '成功', '失败', '错误',
            '正确', '真的', '假的', '对的', '错的', '新的', '旧的', '大的', '小的',
            '多的', '少的', '高的', '低的', '长的', '短的', '快的', '慢的', '好的',
            '坏的', '美的', '丑的', '年', '月', '日', '时', '分', '秒', '今天',
            '昨天', '明天', '现在', '以前', '以后', '刚才', '马上', '立刻', '突然',
            '忽然', '渐渐', '慢慢', '快快', '赶紧', '连忙', '急忙', '匆忙', '悄悄',
            '静静', '轻轻', '重重', '深深', '浅浅', '远远', '近近', '高高', '低低',
            '大大', '小小', '长长', '短短', '宽宽', '窄窄', '厚厚', '薄薄', '粗粗',
            '细细', '胖胖', '瘦瘦', '圆圆', '方方', '尖尖', '平平', '直直', '弯弯',
            '第一', '第二', '第三', '第四', '第五', '第六', '第七', '第八', '第九',
            '第十', '一些', '一点', '一下', '一次', '一遍', '一会', '一直', '一起',
            '一样', '一边', '一面', '一方面', '另一方面', '这样', '那样', '怎样',
            '这里', '那里', '哪里', '这儿', '那儿', '哪儿', '这时', '那时', '什么时候',
            '这种', '那种', '哪种', '这些', '那些', '哪些', '这个', '那个', '哪个',
            '每个', '各个', '某个', '任何', '所有', '全部', '整个', '半个', '几个',
            '多少', '许多', '很多', '不少', '少数', '大部分', '小部分', '一部分',
            '大多数', '少数', '极少数', '绝大多数', '绝少数', '差不多', '几乎',
            '将近', '大约', '左右', '上下', '前后', '内外', '东西', '南北',
            '中间', '之间', '当中', '其中', '里面', '外面', '上面', '下面',
            '前面', '后面', '左面', '右面', '旁边', '附近', '周围', '四周',
            '到处', '处处', '各处', '别处', '他处', '此处', '何处', '无处',
            '随处', '遍地', '满地', '一地', '落地', '着地', '贴地', '沿地',
            '地上', '地下', '地面', '地底', '地表', '地层', '地壳', '地心',
            '天上', '天下', '天空', '天际', '天边', '天涯', '海角', '山顶',
            '山脚', '山腰', '山坡', '山谷', '山洞', '山路', '山水', '山川',
            '河流', '江河', '湖泊', '海洋', '大海', '小海', '内海', '外海',
            '东海', '南海', '西海', '北海', '黄海', '渤海', '东海', '南海',
            '太平洋', '大西洋', '印度洋', '北冰洋', '地中海', '红海', '黑海',
            '白海', '波罗的海', '里海', '咸海', '死海', '青海', '洞庭湖',
            '鄱阳湖', '太湖', '洪泽湖', '巢湖', '滇池', '西湖', '东湖',
            '南湖', '北湖', '中湖', '小湖', '大湖', '人工湖', '天然湖',
            '淡水湖', '咸水湖', '高原湖', '平原湖', '山地湖', '火山湖',
            '冰川湖', '堰塞湖', '牛轭湖', '构造湖', '岩溶湖', '风成湖'
        }
        
        # 添加常见的视频相关停用词
        video_stop_words = {
            '视频', '电影', '电视剧', '综艺', '动漫', '纪录片', '短片', '微电影',
            '预告片', '花絮', '幕后', '采访', '访谈', '直播', '录播', '回放',
            '高清', '超清', '蓝光', '4K', '1080P', '720P', '480P', '360P',
            '国语', '粤语', '英语', '日语', '韩语', '法语', '德语', '俄语',
            '中文', '英文', '字幕', '配音', '原声', '双语', '多语',
            '完整版', '删减版', '导演剪辑版', '加长版', '特别版', '限定版',
            '正片', '番外', '特辑', '精华', '合集', '全集', '单集',
            '第一季', '第二季', '第三季', '第四季', '第五季',
            '第1集', '第2集', '第3集', '第4集', '第5集',
            '上', '下', '中', '前', '后', '左', '右',
            '新', '老', '旧', '最新', '最热', '热门', '推荐',
            '免费', '付费', '会员', 'VIP', '独家', '首播', '重播',
            '更新', '完结', '连载', '待更新', '已完结',
            '国产', '进口', '内地', '香港', '台湾', '日本', '韩国',
            '美国', '英国', '法国', '德国', '意大利', '西班牙',
            '2024', '2023', '2022', '2021', '2020', '2019', '2018',
            '年代', '古装', '现代', '未来', '科幻', '奇幻', '魔幻',
            '动作', '喜剧', '爱情', '剧情', '悬疑', '惊悚', '恐怖',
            '战争', '历史', '传记', '音乐', '歌舞', '体育', '竞技',
            '教育', '儿童', '家庭', '青春', '校园', '职场', '都市',
            '农村', '军事', '警匪', '医疗', '法律', '政治', '商业'
        }
        
        stop_words.update(video_stop_words)
        return stop_words
    
    def extract_titles_from_db(self):
        """
        从数据库中提取所有视频标题
        
        Returns:
            list: 标题列表
        """
        if not os.path.exists(self.db_path):
            print(f"错误：数据库文件 {self.db_path} 不存在")
            return []
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 查询所有标题
            cursor.execute("SELECT title FROM videos WHERE title IS NOT NULL AND title != ''")
            titles = [row[0] for row in cursor.fetchall()]
            
            conn.close()
            
            print(f"从数据库中提取到 {len(titles)} 个标题")
            return titles
            
        except sqlite3.Error as e:
            print(f"数据库错误：{e}")
            return []
        except Exception as e:
            print(f"提取标题时发生错误：{e}")
            return []
    
    def clean_text(self, text):
        """
        清理文本，移除特殊字符和数字
        
        Args:
            text (str): 原始文本
            
        Returns:
            str: 清理后的文本
        """
        if not text:
            return ""
        
        # 移除特殊字符，保留中文、英文和空格
        text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z\s]', ' ', text)
        
        # 移除多余的空格
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def segment_titles(self, titles):
        """
        对标题进行分词
        
        Args:
            titles (list): 标题列表
            
        Returns:
            list: 分词结果列表
        """
        all_words = []
        
        for title in titles:
            if not title:
                continue
                
            # 清理文本
            cleaned_title = self.clean_text(title)
            if not cleaned_title:
                continue
            
            # 使用结巴分词
            words = jieba.lcut(cleaned_title)
            
            # 过滤停用词和短词
            filtered_words = [
                word.strip() for word in words 
                if len(word.strip()) >= 2 and word.strip() not in self.stop_words
            ]
            
            all_words.extend(filtered_words)
        
        print(f"分词完成，共提取到 {len(all_words)} 个词汇")
        return all_words
    
    def extract_keywords_tfidf(self, titles, topK=100):
        """
        使用TF-IDF提取关键词
        
        Args:
            titles (list): 标题列表
            topK (int): 返回前K个关键词
            
        Returns:
            list: 关键词列表，每个元素为(词汇, 权重)
        """
        # 合并所有标题
        all_text = ' '.join([self.clean_text(title) for title in titles if title])
        
        if not all_text:
            return []
        
        # 使用结巴的TF-IDF提取关键词
        keywords = jieba.analyse.extract_tags(
            all_text, 
            topK=topK, 
            withWeight=True,
            allowPOS=('n', 'nr', 'ns', 'nt', 'nz', 'v', 'vd', 'vn', 'a', 'ad', 'an')
        )
        
        # 过滤停用词
        filtered_keywords = [
            (word, weight) for word, weight in keywords 
            if word not in self.stop_words and len(word) >= 2
        ]
        
        return filtered_keywords
    
    def analyze_titles(self, output_file="title_analysis_result.txt"):
        """
        完整的标题分析流程
        
        Args:
            output_file (str): 输出文件名
        """
        print("开始分析媒体库标题...")
        print("=" * 50)
        
        # 1. 提取标题
        titles = self.extract_titles_from_db()
        if not titles:
            print("没有找到任何标题，分析结束")
            return
        
        # 2. 分词分析
        print("\n正在进行分词分析...")
        words = self.segment_titles(titles)
        
        # 3. 词频统计
        print("\n正在进行词频统计...")
        word_counter = Counter(words)
        top_100_freq = word_counter.most_common(100)
        
        # 4. TF-IDF关键词提取
        print("\n正在进行TF-IDF关键词提取...")
        tfidf_keywords = self.extract_keywords_tfidf(titles, 100)
        
        # 5. 生成报告
        self.generate_report(titles, top_100_freq, tfidf_keywords, output_file)
        
        print(f"\n分析完成！结果已保存到 {output_file}")
    
    def generate_report(self, titles, freq_words, tfidf_words, output_file):
        """
        生成分析报告
        
        Args:
            titles (list): 原始标题列表
            freq_words (list): 高频词汇列表
            tfidf_words (list): TF-IDF关键词列表
            output_file (str): 输出文件名
        """
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("媒体库标题分析报告\n")
            f.write("=" * 50 + "\n")
            f.write(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"数据库文件：{self.db_path}\n")
            f.write(f"分析标题数量：{len(titles)}\n")
            f.write("\n")
            
            # 基本统计信息
            f.write("基本统计信息\n")
            f.write("-" * 30 + "\n")
            total_chars = sum(len(title) for title in titles if title)
            avg_length = total_chars / len(titles) if titles else 0
            f.write(f"标题总字符数：{total_chars}\n")
            f.write(f"平均标题长度：{avg_length:.2f} 字符\n")
            f.write("\n")
            
            # Top 100 高频词汇（基于词频）
            f.write("Top 100 高频词汇（基于词频统计）\n")
            f.write("-" * 40 + "\n")
            f.write("排名\t词汇\t\t频次\n")
            f.write("-" * 40 + "\n")
            for i, (word, count) in enumerate(freq_words, 1):
                f.write(f"{i:3d}\t{word:<10}\t{count}\n")
            f.write("\n")
            
            # Top 100 关键词（基于TF-IDF）
            f.write("Top 100 关键词（基于TF-IDF权重）\n")
            f.write("-" * 40 + "\n")
            f.write("排名\t词汇\t\t权重\n")
            f.write("-" * 40 + "\n")
            for i, (word, weight) in enumerate(tfidf_words, 1):
                f.write(f"{i:3d}\t{word:<10}\t{weight:.6f}\n")
            f.write("\n")
            
            # 词汇分类统计
            f.write("词汇长度分布\n")
            f.write("-" * 30 + "\n")
            length_dist = {}
            for word, _ in freq_words:
                length = len(word)
                length_dist[length] = length_dist.get(length, 0) + 1
            
            for length in sorted(length_dist.keys()):
                f.write(f"{length} 字词汇：{length_dist[length]} 个\n")
            f.write("\n")
            
            # 示例标题
            f.write("示例标题（前10个）\n")
            f.write("-" * 30 + "\n")
            for i, title in enumerate(titles[:10], 1):
                f.write(f"{i:2d}. {title}\n")
            f.write("\n")
            
            f.write("分析完成\n")
            f.write("=" * 50 + "\n")

def main():
    """
    主函数
    """
    print("媒体库标题分析工具")
    print("=" * 30)
    
    # 检查数据库文件
    db_path = "media_library.db"
    if not os.path.exists(db_path):
        print(f"错误：找不到数据库文件 {db_path}")
        print("请确保在媒体库项目目录中运行此脚本")
        return
    
    # 创建分析器并开始分析
    analyzer = TitleAnalyzer(db_path)
    analyzer.analyze_titles()
    
    print("\n使用说明：")
    print("- 分析结果保存在 title_analysis_result.txt 文件中")
    print("- 包含高频词汇和TF-IDF关键词两种分析方法")
    print("- 可以根据需要调整停用词列表和分析参数")

if __name__ == "__main__":
    main()