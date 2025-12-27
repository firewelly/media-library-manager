#!/usr/bin/env python3
"""
JAVDB处理器改进应用脚本
用于自动应用JAVDB信息处理功能的改进

使用方法:
python apply_javdb_improvements.py
"""

import os
import shutil
import re
import sys

def backup_file(file_path):
    """备份文件"""
    backup_path = f"{file_path}.backup"
    if not os.path.exists(backup_path):
        shutil.copy2(file_path, backup_path)
        print(f"已备份: {backup_path}")
    else:
        print(f"备份文件已存在: {backup_path}")

def apply_patch(media_library_path, patch_path):
    """应用补丁到media_library.py"""
    print(f"正在应用补丁到 {media_library_path}...")
    
    # 读取原始文件
    with open(media_library_path, 'r', encoding='utf-8') as f:
        original_content = f.read()
    
    # 读取补丁文件
    with open(patch_path, 'r', encoding='utf-8') as f:
        patch_content = f.read()
    
    # 提取改进的函数
    functions_to_replace = {
        'save_javdb_info_to_db': 'save_javdb_info_to_db_improved',
        'batch_process_javdb_info': 'batch_process_javdb_info_improved'
    }
    
    new_content = original_content
    
    # 替换现有函数
    for old_func, new_func in functions_to_replace.items():
        # 查找函数定义
        pattern = rf"def {old_func}\((.*?)\n(.*?)(?=\n    def|\n\n    def|\n\n\nclass|\Z)"
        match = re.search(pattern, new_content, re.DOTALL)
        
        if match:
            # 从补丁中提取新函数
            new_func_pattern = rf"def {new_func}\((.*?)\n(.*?)(?=\ndef|\Z)"
            new_func_match = re.search(new_func_pattern, patch_content, re.DOTALL)
            
            if new_func_match:
                # 替换函数
                old_func_def = match.group(0)
                new_func_def = f"def {new_func}({match.group(1)}\n{new_func_match.group(2)})"
                new_content = new_content.replace(old_func_def, new_func_def)
                print(f"已替换函数: {old_func} -> {new_func}")
            else:
                print(f"警告: 在补丁中找不到新函数 {new_func}")
        else:
            print(f"警告: 在原始文件中找不到函数 {old_func}")
    
    # 添加新的辅助函数
    helper_functions = [
        '_parse_rating',
        '_save_tags_improved',
        '_save_actors_improved',
        'fetch_javdb_info_with_retry',
        '_normalize_javbus_result',
        '_normalize_javsp_result'
    ]
    
    for func_name in helper_functions:
        # 检查函数是否已存在
        if f"def {func_name}(" not in new_content:
            # 从补丁中提取函数
            func_pattern = rf"def {func_name}\((.*?)\n(.*?)(?=\ndef|\Z)"
            func_match = re.search(func_pattern, patch_content, re.DOTALL)
            
            if func_match:
                # 添加到文件末尾（在最后一个类方法之前）
                func_def = f"\n    def {func_name}({func_match.group(1)}\n{func_match.group(2)}"
                # 找到最后一个方法
                last_method_pattern = r"(\n    def [^(]*\([^)]*\).*?(?=\n    def|\n\n\nclass|\Z))"
                last_method_match = re.search(last_method_pattern, new_content, re.DOTALL)
                
                if last_method_match:
                    # 在最后一个方法后添加新函数
                    new_content = new_content.replace(
                        last_method_match.group(1),
                        last_method_match.group(1) + func_def
                    )
                    print(f"已添加函数: {func_name}")
                else:
                    print(f"警告: 无法找到合适位置添加函数 {func_name}")
            else:
                print(f"警告: 在补丁中找不到函数 {func_name}")
        else:
            print(f"函数已存在，跳过: {func_name}")
    
    # 更新函数调用
    new_content = new_content.replace('self.save_javdb_info_to_db(', 'self.save_javdb_info_to_db_improved(')
    new_content = new_content.replace('self.batch_process_javdb_info(', 'self.batch_process_javdb_info_improved(')
    
    # 写入更新后的内容
    with open(media_library_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print("补丁应用完成!")

def main():
    """主函数"""
    # 文件路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    media_library_path = os.path.join(current_dir, "media_library.py")
    patch_path = os.path.join(current_dir, "javdb_processor_patch.py")
    
    # 检查文件是否存在
    if not os.path.exists(media_library_path):
        print(f"错误: 找不到文件 {media_library_path}")
        sys.exit(1)
    
    if not os.path.exists(patch_path):
        print(f"错误: 找不到补丁文件 {patch_path}")
        sys.exit(1)
    
    # 备份原始文件
    backup_file(media_library_path)
    
    # 应用补丁
    try:
        apply_patch(media_library_path, patch_path)
        print("JAVDB处理器改进应用成功!")
    except Exception as e:
        print(f"应用补丁时出错: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()