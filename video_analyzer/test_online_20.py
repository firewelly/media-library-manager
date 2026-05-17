#!/usr/bin/env python3
"""测试20个在线无标签视频（不写库）"""
import sys, os, time, json, base64
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from video_analyzer_local_model_adult import VideoAnalyzerLocalModelAdult

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'media_library.db')

import sqlite3
conn = sqlite3.connect(DB)
cursor = conn.cursor()
cursor.execute('''
    SELECT v.id, v.file_path FROM videos v
    INNER JOIN folders f ON v.source_folder = f.folder_path
    WHERE (v.tags IS NULL OR v.tags = '')
    AND v.file_path IS NOT NULL AND v.file_path != ''
    AND f.is_active = 1 AND v.file_path LIKE '%.mp4'
    ORDER BY v.id
''')
rows = cursor.fetchall()
conn.close()

online = []
for vid, path in rows:
    if os.path.exists(path):
        online.append((vid, path))
        if len(online) >= 20:
            break

analyzer = VideoAnalyzerLocalModelAdult(verbose=False)

results = []
for i, (vid, path) in enumerate(online):
    print(f"\n[{i+1}/20] ID={vid} {os.path.basename(path)[:50]}")
    try:
        start = time.time()
        result = analyzer.analyze_video(path)
        elapsed = time.time() - start
        
        if result.get('success'):
            analysis = result['analysis']
            tags = analyzer.extract_tags_from_analysis(analysis)
            frames = result.get('frames_extracted', 0)
            print(f"  耗时: {elapsed:.1f}s | 帧数: {frames} | 标签({len(tags)}个): {tags}")
            results.append({'id': vid, 'path': path, 'tags': tags, 'frames': frames, 'time': elapsed, 'analysis': analysis})
        else:
            print(f"  失败: {result.get('error')}")
    except Exception as e:
        print(f"  异常: {e}")

print(f"\n{'='*60}")
print(f"测试完成！成功 {len(results)}/20")
print(f"{'='*60}")
for r in results:
    print(f"ID={r['id']:5d} {r['time']:5.1f}s {r['frames']:2d}帧 {r['tags']}")
