#!/usr/bin/env python3
"""
重新打标签脚本 - 针对本机文件夹中有问题的视频
功能：
1. 识别本机文件夹中 tags 有问题的视频
2. 清理无效标签（保留 JAVDB 标签和词汇表标签）
3. 用当前词汇表重新匹配打标签

用法：
  # 预览（只看不改）
  python3 retag_local_videos.py --preview
  
  # 清理无效标签（保留合法标签，仅清理无效的）
  python3 retag_local_videos.py --clean
  
  # 完整流程：清理 + 用词汇表重新匹配打标签
  python3 retag_local_videos.py --retag
"""

import sqlite3
import os
import re
import sys
from collections import Counter

DB_PATH = "media_library.db"
OLD_VOCAB_FILE = "vocabulary_tags.txt"
NEW_VOCAB_FILE = "video_analyzer/vocabulary_tags.txt"

# 本机文件夹
LOCAL_FOLDERS = [
    '/Users/firewell/影视/AV',
    '/Users/firewell/影视/国产mac',
    '/Users/firewell/Downloads/mp42',
]


def load_vocab(filepath):
    if not os.path.exists(filepath):
        print(f"  警告: {filepath} 不存在，跳过")
        return set()
    with open(filepath, 'r', encoding='utf-8') as f:
        return set(line.strip().lower() for line in f if line.strip())


def load_javdb_tags(cursor):
    cursor.execute('SELECT DISTINCT tag_name FROM javdb_tags')
    tags = set()
    for row in cursor.fetchall():
        if row[0]:
            tags.add(row[0].strip().lower())
    return tags


def is_javdb_style(tag):
    traditional_chars = set(
        '單體無碼戲劇紀錄業餘亂倫處男禮儀藝護士秘書連褲戀乳癖濫交蕩婦強姦'
        '數位馬賽克軍人黨職員營業員學生會長齒科助手藥劑師理髮師美容師風俗嬌聲'
        '親屬關係母親女兒姊妹阿姨繼母岳母婆媳嫂嫂爺爺奶奶孫子'
        '興奮感動驚訝憤怒緊張憂鬱豐滿嬌小纖細高挑'
        '褲襪連衣裙內衣褲攝影攝錄攝製體型體態體格'
        '戀愛戀物癖對話對白選擇選拔藝人藝術飲食餐廳'
    )
    return any(c in tag for c in traditional_chars)


def get_local_condition():
    return ' OR '.join(f"file_path LIKE '{f}%'" for f in LOCAL_FOLDERS)


def find_problem_videos(cursor):
    current_vocab = load_vocab(NEW_VOCAB_FILE)
    old_vocab = load_vocab(OLD_VOCAB_FILE)
    javdb_tags_set = load_javdb_tags(cursor)
    
    legitimate = current_vocab | old_vocab | javdb_tags_set
    local_cond = get_local_condition()
    
    cursor.execute(f"""
        SELECT id, tags, file_name, title FROM videos
        WHERE ({local_cond})
          AND tags IS NOT NULL AND tags != ''
        ORDER BY id
    """)
    
    problem_videos = []
    all_tag_stats = Counter()
    
    for vid_id, tags, file_name, title in videos if (videos := cursor.fetchall()) else []:
        tag_list = [t.strip() for t in tags.split(',') if t.strip()]
        valid = []
        invalid = []
        
        for t in tag_list:
            t_lower = t.lower()
            if t_lower in legitimate or is_javdb_style(t):
                valid.append(t)
            else:
                invalid.append(t)
                all_tag_stats[t] += 1
        
        if invalid:
            problem_videos.append((vid_id, tags, valid, invalid, file_name, title))
    
    return problem_videos, all_tag_stats


def preview(cursor):
    problem_videos, tag_stats = find_problem_videos(cursor)
    
    if not problem_videos:
        print("没有发现需要处理的视频")
        return
    
    print(f"\n找到 {len(problem_videos)} 个有问题的视频\n")
    
    print(f"{'ID':>6} | {'有效标签数':>8} | {'无效标签数':>8} | {'文件名':<30}")
    print("-" * 80)
    for vid_id, tags, valid, invalid, file_name, title in problem_videos[:20]:
        short_name = (file_name or title or '')[:28]
        print(f"{vid_id:>6} | {len(valid):>8} | {len(invalid):>8} | {short_name:<30}")
    
    if len(problem_videos) > 20:
        print(f"... 还有 {len(problem_videos) - 20} 个")
    
    print(f"\n最常见的无效标签 Top 20:")
    for tag, count in tag_stats.most_common(20):
        print(f"  \"{tag}\": {count} 次")


def clean(cursor, conn):
    problem_videos, tag_stats = find_problem_videos(cursor)
    if not problem_videos:
        print("没有发现需要处理的视频")
        return
    
    print(f"\n开始清理 {len(problem_videos)} 个视频的无效标签...")
    cleaned_count = 0
    
    for vid_id, tags, valid, invalid, file_name, title in problem_videos:
        if not invalid:
            continue
        
        new_tags = ', '.join(valid) if valid else ''
        
        if new_tags != tags:
            cursor.execute(
                "UPDATE videos SET tags = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (new_tags, vid_id)
            )
            cleaned_count += 1
    
    conn.commit()
    print(f"清理完成！已更新 {cleaned_count} 个视频的标签")


def retag_with_vocabulary(cursor, conn):
    """用当前词汇表对无JAVDB标签的视频重新打标签"""
    current_vocab = load_vocab(NEW_VOCAB_FILE)
    if not current_vocab:
        print("错误: 当前词汇表为空，无法重新打标签")
        return
    
    local_cond = get_local_condition()
    
    cursor.execute(f"""
        SELECT id, tags, file_name, title FROM videos
        WHERE ({local_cond})
          AND tags IS NOT NULL AND tags != ''
          AND NOT EXISTS (SELECT 1 FROM javdb_tags WHERE videos.tags LIKE '%' || javdb_tags.tag_name || '%')
        ORDER BY id
    """)
    videos = cursor.fetchall()
    
    print(f"\n找到 {len(videos)} 个无JAVDB标签的视频，尝试用词汇表匹配...")
    updated = 0
    
    for vid_id, tags, file_name, title in videos:
        existing_tags = set(t.strip() for t in tags.split(',') if t.strip())
        text_to_match = f"{file_name or ''} {title or ''}"
        
        matched = set()
        for word in current_vocab:
            if word.lower() in text_to_match.lower():
                matched.add(word)
        
        if matched:
            all_tags = existing_tags | matched
            new_tags = ', '.join(sorted(all_tags))
            
            if new_tags != tags:
                cursor.execute(
                    "UPDATE videos SET tags = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (new_tags, vid_id)
                )
                updated += 1
                print(f"  ID {vid_id}: {file_name or title} -> 新增 {len(matched)} 个标签: {', '.join(matched)}")
    
    conn.commit()
    print(f"词汇表匹配完成！更新了 {updated} 个视频")


def main():
    if not os.path.exists(DB_PATH):
        print(f"错误: 找不到数据库 {DB_PATH}")
        sys.exit(1)
    
    mode = 'preview'
    if '--preview' in sys.argv:
        mode = 'preview'
    elif '--clean' in sys.argv:
        mode = 'clean'
    elif '--retag' in sys.argv:
        mode = 'retag'
    elif len(sys.argv) > 1 and sys.argv[1] not in ('-h', '--help'):
        print(f"未知参数: {sys.argv[1]}")
        print("用法: python3 retag_local_videos.py [--preview|--clean|--retag]")
        sys.exit(1)
    
    print("=" * 60)
    print(f"模式: {mode}")
    print("=" * 60)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if mode == 'preview':
        preview(cursor)
    elif mode == 'clean':
        clean(cursor, conn)
    elif mode == 'retag':
        clean(cursor, conn)
        retag_with_vocabulary(cursor, conn)
    
    conn.close()
    print("\n完成！")


if __name__ == '__main__':
    main()
