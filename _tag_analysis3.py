#!/usr/bin/env python3
import sqlite3
from collections import Counter

conn = sqlite3.connect('media_library.db')
cursor = conn.cursor()

with open('video_analyzer/vocabulary_tags.txt', 'r', encoding='utf-8') as f:
    current_vocab = set(line.strip().lower() for line in f if line.strip())

with open('vocabulary_tags.txt', 'r', encoding='utf-8') as f:
    old_vocab = set(line.strip().lower() for line in f if line.strip())

cursor.execute('SELECT DISTINCT tag_name FROM javdb_tags')
javdb_tags = set()
for row in cursor.fetchall():
    if row[0]:
        javdb_tags.add(row[0].strip().lower())

# 还有一种情况：JAVDB标签直接在videos.tags中但不在javdb_tags表里
# 通过繁体字特征识别
traditional_chars = set('單體無碼戲劇紀錄業餘亂倫處男禮儀藝護士秘書連褲戀乳癖濫交蕩婦強姦數位馬賽克蕩婦禮儀'
                        '軍人黨職員營業員學生會長齒科助手藥劑師理髮師美容師風俗嬌聲'
                        '親屬關係母親女兒姊妹阿姨繼母岳母婆媳嫂嫂爺爺奶奶孫子'
                        '興奮感動驚訝憤怒緊張憂鬱'
                        '選秀節目紀錄片綜藝節目訪談節目'
                        '豐滿嬌小纖細高挑'
                        '褲襪連衣裙內衣褲'
                        '攝影攝錄攝製'
                        '頭髮髮型髮飾'
                        '體型體態體格'
                        '戀愛戀物癖'
                        '對話對白'
                        '選擇選拔'
                        '藝人藝術'
                        '飲食餐廳'
                        '醫院醫生'
                        '學校學生'
                        '辦公廳辦公室'
                        '親密親熱')

# 合法标签 = 当前词汇表 + 旧词汇表 + JAVDB标签 + 繁体中文标签
legitimate_tags = current_vocab | old_vocab | javdb_tags

cursor.execute('SELECT id, tags, title, file_name FROM videos WHERE tags IS NOT NULL AND tags != ""')
videos = cursor.fetchall()

# 判断一个标签是否是JAVDB繁体标签
def is_javdb_tag(tag):
    tag_lower = tag.lower()
    if tag_lower in javdb_tags:
        return True
    if any(c in tag for c in traditional_chars):
        return True
    return False

all_tags = {}
tag_counts_per_video = []
problem_videos = {
    'truly_invalid': [],
    'too_many_tags': [],
    'duplicate_tags': [],
}

truly_invalid_tags = {}

for vid_id, tags, title, file_name in videos:
    tag_list = [t.strip() for t in tags.split(',') if t.strip()]
    tag_counts_per_video.append((vid_id, len(tag_list)))
    
    for tag in tag_list:
        tag_lower = tag.lower()
        if tag_lower not in all_tags:
            all_tags[tag_lower] = {'original': tag, 'count': 0, 'video_ids': []}
        all_tags[tag_lower]['count'] += 1
        all_tags[tag_lower]['video_ids'].append(vid_id)
    
    # 真正无效的标签：不在词汇表、不是JAVDB标签、不是繁体中文
    invalid = [t for t in tag_list 
               if t.lower() not in current_vocab 
               and t.lower() not in old_vocab
               and not is_javdb_tag(t)]
    if invalid:
        problem_videos['truly_invalid'].append((vid_id, tags, invalid))
        for t in invalid:
            t_lower = t.lower()
            if t_lower not in truly_invalid_tags:
                truly_invalid_tags[t_lower] = {'original': t, 'count': 0, 'video_ids': []}
            truly_invalid_tags[t_lower]['count'] += 1
            truly_invalid_tags[t_lower]['video_ids'].append(vid_id)
    
    if len(tag_list) > 10:
        problem_videos['too_many_tags'].append((vid_id, tags, len(tag_list)))
    
    seen = set()
    for t in tag_list:
        if t.lower() in seen:
            problem_videos['duplicate_tags'].append((vid_id, tags))
            break
        seen.add(t.lower())

print("=" * 60)
print("数据库标签分析（排除JAVDB繁体标签后）")
print("=" * 60)

print(f'\n总视频数: 33,399')
print(f'有标签视频: {len(videos)}')
print(f'唯一标签总数: {len(all_tags)}')

# 标签分类
vocab_only = {k: v for k, v in all_tags.items() if k in current_vocab}
old_only = {k: v for k, v in all_tags.items() if k in old_vocab and k not in current_vocab}
javdb_only = {k: v for k, v in all_tags.items() if is_javdb_tag(k) and k not in current_vocab and k not in old_vocab}
invalid_only = {k: v for k, v in all_tags.items() if k not in current_vocab and k not in old_vocab and not is_javdb_tag(k)}

print(f'\n=== 标签来源分类 ===')
print(f'当前词汇表标签: {len(vocab_only)} 种')
print(f'旧词汇表(已移除)标签: {len(old_only)} 种')
print(f'JAVDB繁体标签: {len(javdb_only)} 种')
print(f'真正无效标签(不属于以上任何): {len(invalid_only)} 种')

# 真正无效标签详情
print(f'\n=== 真正无效标签 Top 60 (共{len(truly_invalid_tags)}种) ===')
sorted_invalid = sorted(truly_invalid_tags.items(), key=lambda x: x[1]['count'], reverse=True)
for tag_lower, info in sorted_invalid[:60]:
    vid_sample = info['video_ids'][:3]
    print(f'  "{info["original"]}": {info["count"]}次, ID示例: {vid_sample}')

# 对无效标签进行分类
print(f'\n=== 无效标签类型分析 ===')
generic_tags = []
descriptor_tags = []
number_tags = []
other_tags = []

for tag_lower, info in truly_invalid_tags.items():
    tag = info['original']
    if any(c.isdigit() for c in tag):
        number_tags.append((tag_lower, info))
    elif len(tag) <= 1:
        generic_tags.append((tag_lower, info))
    else:
        other_tags.append((tag_lower, info))

print(f'含数字的标签: {len(number_tags)} 种')
print(f'单字标签: {len(generic_tags)} 种')
print(f'其他描述性标签: {len(other_tags)} 种')

# 问题视频统计
print(f'\n=== 问题视频统计 ===')
print(f'含真正无效标签的视频: {len(problem_videos["truly_invalid"])} 个')
print(f'标签过多的视频(>10): {len(problem_videos["too_many_tags"])} 个')
print(f'有重复标签的视频: {len(problem_videos["duplicate_tags"])} 个')

# 受影响视频ID
all_problem_ids = set()
for vid_id, _, _ in problem_videos['truly_invalid']:
    all_problem_ids.add(vid_id)
for vid_id, _, _ in problem_videos['too_many_tags']:
    all_problem_ids.add(vid_id)
for vid_id, _ in problem_videos['duplicate_tags']:
    all_problem_ids.add(vid_id)

print(f'\n总受影响视频: {len(all_problem_ids)} 个')

if all_problem_ids:
    sorted_ids = sorted(all_problem_ids)
    print(f'最小ID: {sorted_ids[0]}')
    print(f'最大ID: {sorted_ids[-1]}')

    # ID分布
    segments = [
        (13714, 20000),
        (20001, 30000),
        (30001, 40000),
        (40001, 50000),
        (50001, 57109),
    ]
    
    cursor.execute('SELECT id FROM videos ORDER BY id')
    all_vid_ids = set(r[0] for r in cursor.fetchall())
    
    print('\n受影响视频按ID段分布:')
    for lo, hi in segments:
        total_in_seg = sum(1 for i in all_vid_ids if lo <= i <= hi)
        problems_in_seg = sum(1 for i in all_problem_ids if lo <= i <= hi)
        pct = problems_in_seg / total_in_seg * 100 if total_in_seg else 0
        print(f'  ID {lo}-{hi}: 总{total_in_seg}, 有问题{problems_in_seg} ({pct:.1f}%)')

# 旧词汇表已移除标签影响范围
print(f'\n=== 旧词汇表已移除标签的影响 ===')
only_in_old = old_vocab - current_vocab
for tag in sorted(only_in_old):
    tag_lower = tag.lower()
    if tag_lower in all_tags:
        info = all_tags[tag_lower]
        print(f'  "{tag}": 被使用 {info["count"]} 次, 涉及 {len(info["video_ids"])} 个视频, ID范围: {min(info["video_ids"])}-{max(info["video_ids"])}')

# 标签数量分布
counts = [c for _, c in tag_counts_per_video]
print(f'\n=== 标签数量分布 ===')
print(f'平均: {sum(counts)/len(counts):.1f}, 最多: {max(counts)}, 最少: {min(counts)}')
brackets = [(1,1), (2,5), (6,10), (11,20), (21,50), (51,100), (101,1500)]
for lo, hi in brackets:
    cnt = sum(1 for c in counts if lo <= c <= hi)
    print(f'  {lo}-{hi}个: {cnt} 视频 ({cnt/len(counts)*100:.1f}%)')

conn.close()
