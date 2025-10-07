# 修复所有文件中volume被错误拼写为volumn的问题
import os

# 需要修复的文件路径
file_paths = [
    '/Users/firewell/Library/CloudStorage/OneDrive-个人/bioinfo/media/outside_root_paths.txt',
    '/Users/firewell/Library/CloudStorage/OneDrive-个人/bioinfo/media/quick_import_from_csv.py',
    '/Users/firewell/Library/CloudStorage/OneDrive-个人/bioinfo/media/smart_video_updater.py'
]

# 替换规则
replacements = {
    '/Volumns/': '/Volumes/',  # 大写开头的复数形式
    '/volumns/': '/volumes/',  # 小写开头的复数形式
    '/Volumn1/': '/Volume1/',  # 大写开头的单数形式带数字
    '/volumn1/': '/volume1/'   # 小写开头的单数形式带数字
}

for file_path in file_paths:
    if os.path.exists(file_path):
        try:
            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 记录替换前的内容以便比较
            original_content = content
            
            # 执行所有替换
            for old_str, new_str in replacements.items():
                content = content.replace(old_str, new_str)
            
            # 如果内容发生了变化，写回文件
            if content != original_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f'已成功修复 {file_path} 中的路径拼写错误')
            else:
                print(f'{file_path} 中未发现需要修复的路径拼写错误')
                
        except Exception as e:
            print(f'修复 {file_path} 时出错: {str(e)}')
    else:
        print(f'文件不存在: {file_path}')

print('所有文件修复完成')