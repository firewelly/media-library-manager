from code_extractor import CodeExtractor

extractor = CodeExtractor()
filename = 'IPZZ-565_test_video.mp4'
cleaned = 'IPZZ-565_test_video'

print(f'测试文件名: {filename}')
print(f'清理后: {cleaned}')
print('\n测试各个正则模式:')

for i, pattern in enumerate(extractor.compiled_patterns):
    matches = pattern.findall(cleaned)
    if matches:
        print(f'模式 {i}: {pattern.pattern} -> 匹配: {matches}')
        for match in matches:
            code = extractor._format_code(match)
            valid = extractor._is_valid_code(code) if code else False
            print(f'  格式化后: {code}, 有效: {valid}')
    else:
        print(f'模式 {i}: {pattern.pattern} -> 无匹配')

print(f'\n最终提取结果: {extractor.extract_code_from_filename(filename)}')