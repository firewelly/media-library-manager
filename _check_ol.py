import sqlite3
conn = sqlite3.connect('media_library.db')
cursor = conn.cursor()

cursor.execute("SELECT COUNT(*) FROM videos WHERE tags LIKE '%OL%'")
print(f'包含 OL 标签的视频数: {cursor.fetchone()[0]}')

cursor.execute("SELECT id, tags FROM videos WHERE tags LIKE '%OL%' LIMIT 3")
for row in cursor.fetchall():
    print(f'  ID {row[0]}: {row[1][:100]}')

cursor.execute("SELECT * FROM tags WHERE tag_name = 'OL'")
print(f'\ntags表中OL: {cursor.fetchone()}')

with open('vocabulary_tags.txt', 'r') as f:
    lines = [l.strip() for l in f if l.strip()]
    idx = lines.index('OL') + 1 if 'OL' in lines else -1
    print(f'根目录词汇表 OL: 第{idx}个' if idx > 0 else 'OL 不在根目录词汇表')

with open('video_analyzer/vocabulary_tags.txt', 'r') as f:
    lines = [l.strip() for l in f if l.strip()]
    idx = lines.index('OL') + 1 if 'OL' in lines else -1
    print(f'新词汇表 OL: 第{idx}个' if idx > 0 else 'OL 不在新词汇表')

conn.close()
