#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# 测试MediaLibrary类的结构
import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from media_library import MediaLibrary
    
    # 检查类是否有fix_javdb_error_titles方法
    if hasattr(MediaLibrary, 'fix_javdb_error_titles'):
        print("✓ fix_javdb_error_titles方法存在")
        print(f"方法类型: {type(getattr(MediaLibrary, 'fix_javdb_error_titles'))}")
    else:
        print("✗ fix_javdb_error_titles方法不存在")
        
    # 列出所有包含'fix'的方法
    fix_methods = [method for method in dir(MediaLibrary) if 'fix' in method.lower()]
    print(f"包含'fix'的方法: {fix_methods}")
    
    # 检查类的所有方法
    all_methods = [method for method in dir(MediaLibrary) if not method.startswith('_')]
    print(f"类的所有公共方法数量: {len(all_methods)}")
    print(f"最后几个方法: {all_methods[-10:]}")
    
except ImportError as e:
    print(f"导入失败: {e}")
except Exception as e:
    print(f"其他错误: {e}")