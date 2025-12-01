#!/usr/bin/env python3
"""
测试NFO文件中javdb_title的映射逻辑
"""

import xml.etree.ElementTree as ET
import tempfile
import os

def parse_nfo_file(nfo_path):
    """复制自media_library.py的parse_nfo_file函数逻辑"""
    try:
        tree = ET.parse(nfo_path)
        root = tree.getroot()
        
        nfo_data = {}
        
        # 提取标题（完整截取到</title>）
        title_elem = root.find('title')
        if title_elem is not None and title_elem.text:
            full_title = title_elem.text.strip()
            nfo_data['title'] = full_title
            
            # javdb_title直接映射到title标签内容
            nfo_data['javdb_title'] = full_title
            
            # 从标题中提取番号
            # 第一个空格前面作为番号
            if ' ' in full_title:
                parts = full_title.split(' ', 1)
                nfo_data['code'] = parts[0]  # 番号
            else:
                nfo_data['code'] = full_title
            
            # 增强番号提取：检查番号格式是否符合常见模式
            code_val = nfo_data['code']
            # 如果番号不包含连字符或不符合常见格式，尝试从标题的其他位置提取
            if '-' not in code_val and not any(prefix in code_val.upper() for prefix in ['FC2', '1PONDO', 'CARIB', '10MUSUME']):
                # 使用正则表达式在标题中查找可能的番号
                import re
                # 匹配常见番号格式：字母-数字，如ABC-123
                pattern = r'\b([A-Za-z]{2,})-?(\d{3,})\b'
                matches = re.findall(pattern, full_title)
                if matches:
                    # 使用第一个匹配作为番号
                    letters, numbers = matches[0]
                    nfo_data['code'] = f"{letters}-{numbers}"
        
        return nfo_data
        
    except Exception as e:
        print(f"解析NFO文件失败: {e}")
        return None

def create_test_nfo(title_content):
    """创建测试NFO文件"""
    nfo_content = f"""<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<movie>
    <title>{title_content}</title>
    <plot>测试剧情描述</plot>
    <year>2024</year>
    <premiered>2024-01-01</premiered>
    <genre>测试类型</genre>
    <rating>8.5</rating>
    <studio>测试工作室</studio>
    <uniqueid type="num" default="true">TEST-123</uniqueid>
</movie>"""
    
    # 创建临时文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.nfo', delete=False, encoding='utf-8') as f:
        f.write(nfo_content)
        return f.name

def main():
    """测试不同的标题格式"""
    test_cases = [
        "IPX-123 美咲かんな 新人デビュー",
        "IPX123 美咲かんな 新人デビュー",
        "美咲かんな 新人デビュー",
        "IPX-123",
        "TEST-456 这是测试标题"
    ]
    
    print("=== NFO标题解析测试 ===\n")
    
    for title in test_cases:
        print(f"测试标题: '{title}'")
        nfo_path = create_test_nfo(title)
        
        try:
            result = parse_nfo_file(nfo_path)
            if result:
                print(f"  title: '{result.get('title', 'None')}'")
                print(f"  code: '{result.get('code', 'None')}'")
                print(f"  javdb_title: '{result.get('javdb_title', 'None')}'")
                print(f"  javdb_title == title: {result.get('javdb_title') == result.get('title')}")
            else:
                print("  解析失败")
        finally:
            os.unlink(nfo_path)
        
        print()

if __name__ == "__main__":
    main()