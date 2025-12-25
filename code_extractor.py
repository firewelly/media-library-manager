#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
番号提取工具
从文件名中提取AV番号，支持多种常见格式
整合了 javsp_mac 项目的高级番号识别逻辑
"""

import re
import os
from typing import Optional, List, Tuple

class CodeExtractor:
    """增强版番号提取器，整合了 javsp_mac 的先进识别逻辑"""
    
    def __init__(self):
        # 忽略模式配置（类似 javsp_mac 的 ignore_pattern）
        self.ignore_pattern = re.compile(r'', re.I)  # 可以根据需要配置
        
        # 常见的无效匹配（需要过滤掉的）
        self.invalid_patterns = [
            r'^\d{4}$',  # 纯4位数字（可能是年份）
            r'^19\d{2}$|^20\d{2}$',  # 年份格式
            r'^\d{1,2}p$',  # 分辨率标识如720p, 1080p
            r'^[xX]\d+$',  # x264, x265等编码标识
            r'^\d{1,3}$',  # 过短的纯数字
        ]
        
        self.invalid_compiled = [re.compile(pattern, re.IGNORECASE) for pattern in self.invalid_patterns]
    
    def extract_code_from_filename(self, filename: str) -> Optional[str]:
        """
        从文件名中提取番号（基于 javsp_mac 的 get_id 函数增强）
        
        Args:
            filename: 文件名（可以包含路径）
            
        Returns:
            提取到的番号，如果没有找到则返回None
        """
        # 获取文件名并应用忽略模式
        basename = os.path.basename(filename)
        basename = self.ignore_pattern.sub('', basename)
        filename_lc = basename.lower()
        
        # FC2 格式处理（根据FC2 Club的影片数据，FC2编号为5-7个数字）
        if 'fc2' in filename_lc:
            match = re.search(r'fc2[^a-z\d]{0,5}(ppv[^a-z\d]{0,5})?(\d{5,7})', basename, re.I)
            if match:
                return 'FC2-' + match.group(2)
        
        # 一本道格式：1pondo-123456_789
        elif '1pondo' in filename_lc or 'pondo' in filename_lc:
            match = re.search(r'(1pondo|pondo)[-_]*(\d{6})[-_]*(\d{3})', basename, re.I)
            if match:
                return '1pondo-' + match.group(2) + '_' + match.group(3)
        
        # 加勒比格式：carib-123456-789, caribbeancom-123456-789
        elif 'carib' in filename_lc:
            match = re.search(r'(carib|caribbeancom)[-_]*(\d{6})[-_]*(\d{3})', basename, re.I)
            if match:
                return match.group(1) + '-' + match.group(2) + '-' + match.group(3)
        
        # 天然素人格式：10musume-123456_01
        elif '10musume' in filename_lc or 'musume' in filename_lc:
            match = re.search(r'(10musume|musume)[-_]*(\d{6})[-_]*(\d{2})', basename, re.I)
            if match:
                return '10musume-' + match.group(2) + '_' + match.group(3)
        
        # Heydouga 格式
        elif 'heydouga' in filename_lc:
            match = re.search(r'(heydouga)[-_]*(\d{4})[-_]0?(\d{3,5})', basename, re.I)
            if match:
                return '-'.join(match.groups())
        
        # Getchu 格式
        elif 'getchu' in filename_lc:
            match = re.search(r'getchu[-_]*(\d+)', basename, re.I)
            if match:
                return 'GETCHU-' + match.group(1)
        
        # Gyutto 格式
        elif 'gyutto' in filename_lc:
            match = re.search(r'gyutto-(\d+)', basename, re.I)
            if match:
                return 'GYUTTO-' + match.group(1)
        
        # 259LUXU 特殊格式
        elif '259luxu' in filename_lc:
            match = re.search(r'259luxu-(\d+)', basename, re.I)
            if match:
                return '259LUXU-' + match.group(1)
        
        else:
            # 先尝试移除可疑域名进行匹配
            no_domain = re.sub(r'\w{3,10}\.(com|net|app|xyz)', '', basename, flags=re.I)
            if no_domain != basename:
                avid = self.extract_code_from_filename(no_domain)
                if avid:
                    return avid
            
            # 匹配缩写成hey的heydouga影片
            match = re.search(r'(?:hey)[-_]*(\d{4})[-_]0?(\d{3,5})', basename, re.I)
            if match:
                return 'heydouga-' + '-'.join(match.groups())
            
            # 匹配片商 MUGEN 的奇怪番号
            match = re.search(r'(MKB?D)[-_]*(S\d{2,3})|(MK3D2DBD|S2M|S2MBD)[-_]*(\d{2,3})', basename, re.I)
            if match:
                if match.group(1) is not None:
                    return match.group(1) + '-' + match.group(2)
                else:
                    return match.group(3) + '-' + match.group(4)
            
            # 匹配IBW这样带有后缀z的番号
            match = re.search(r'(IBW)[-_](\d{2,5}z)', basename, re.I)
            if match:
                return match.group(1) + '-' + match.group(2)
            
            # 普通番号，优先尝试匹配带分隔符的（如ABC-123）
            match = re.search(r'([a-z]{2,10})[-_](\d{2,5})', basename, re.I)
            if match:
                return match.group(1) + '-' + match.group(2)
            
            # 东热的red, sky, ex三个不带-分隔符的系列
            match = re.search(r'(red[01]\d{2}|sky[0-3]\d{2}|ex00[01]\d)', basename, re.I)
            if match:
                return match.group(1)
            
            # 缺失了-分隔符的普通番号
            match = re.search(r'([a-z]{2,})([0-9]{2,5})', basename, re.I)
            if match:
                return match.group(1) + '-' + match.group(2)
        
        # TMA制作的影片（如'T28-557'）
        match = re.search(r'(T28[-_]\d{3})', basename)
        if match:
            return match.group(1)
        
        # 东热n, k系列
        match = re.search(r'(n\d{4}|k\d{4})', basename, re.I)
        if match:
            return match.group(1)
        
        # 纯数字番号（无码影片）
        match = re.search(r'(\d{6}[-_]\d{2,3})', basename)
        if match:
            return match.group(1)
        
        # 尝试将')('替换为'-'后再试
        if ')(' in filename:
            avid = self.extract_code_from_filename(filename.replace(')(', '-'))
            if avid:
                return avid
        
        # 如果仍然匹配不了，尝试使用文件所在文件夹的名字
        if os.path.isfile(filename):
            norm = os.path.normpath(filename)
            if os.sep in norm:
                folder = norm.split(os.sep)[-2]
                return self.extract_code_from_filename(folder)
        
        return None
    
    def extract_all_codes_from_filename(self, filename: str) -> List[str]:
        """
        从文件名中提取所有可能的番号
        
        Args:
            filename: 文件名
            
        Returns:
            所有提取到的番号列表
        """
        codes = []
        
        # 首先尝试主要提取方法
        main_code = self.extract_code_from_filename(filename)
        if main_code:
            codes.append(main_code.upper())
        
        # 然后尝试其他可能的模式（使用原有的模式匹配作为补充）
        basename = os.path.splitext(os.path.basename(filename))[0]
        cleaned_name = self._clean_filename(basename)
        
        # 补充模式：标准格式
        additional_patterns = [
            r'\b([A-Z]{2,5})[-]?(\d{3,4})\b',
            r'\[.*?\]\s*([A-Z]{2,5})[-]?(\d{3,4})',
        ]
        
        for pattern in additional_patterns:
            matches = re.findall(pattern, cleaned_name, re.IGNORECASE)
            if matches:
                for match in matches:
                    code = self._format_code(match)
                    if code and self._is_valid_code(code) and code.upper() not in codes:
                        codes.append(code.upper())
        
        return codes
    
    def _clean_filename(self, filename: str) -> str:
        """
        清理文件名，移除常见的无关信息
        """
        # 移除常见的分辨率、编码、格式标识
        patterns_to_remove = [
            r'\b\d{3,4}[pP]\b',  # 720p, 1080p等
            r'\b[xX]26[45]\b',   # x264, x265
            r'\b[hH]26[45]\b',   # h264, h265
            r'\bHEVC\b',         # HEVC编码
            r'\bBlu[-]?ray\b',   # Blu-ray
            r'\bWEB[-]?DL\b',    # WEB-DL
            r'\b中文字幕\b',      # 中文字幕
            r'\b无码\b',         # 无码
            r'\b有码\b',         # 有码
            r'\b发布组.*?\b',     # 发布组信息
            r'\b20\d{2}\b',      # 年份
        ]
        
        cleaned = filename
        for pattern in patterns_to_remove:
            cleaned = re.sub(pattern, ' ', cleaned, flags=re.IGNORECASE)
        
        return cleaned
    
    def _format_code(self, match) -> Optional[str]:
        """
        格式化匹配到的番号
        """
        if isinstance(match, tuple):
            if len(match) == 2:
                # 标准格式：(厂商, 编号)
                return f"{match[0]}-{match[1]}"
            elif len(match) == 3:
                # 特殊格式：(前缀, 中间, 后缀)
                if match[1]:  # 如果中间部分存在
                    return f"{match[0]}-{match[1]}-{match[2]}"
                else:
                    return f"{match[0]}-{match[2]}"
        elif isinstance(match, str):
            return match
        
        return None
    
    def _is_valid_code(self, code: str) -> bool:
        """
        验证番号是否有效（增强版验证逻辑）
        """
        if not code or len(code) < 3:
            return False
        
        # 检查是否匹配无效模式
        for pattern in self.invalid_compiled:
            if pattern.match(code):
                return False
        
        # FC2格式验证
        if re.match(r'^FC2-\d{5,7}$', code, re.IGNORECASE):
            return True
        
        # Heydouga格式验证
        if re.match(r'^heydouga-\d{4}-\d{3,5}$', code, re.IGNORECASE):
            return True
        
        # Getchu格式验证
        if re.match(r'^GETCHU-\d+$', code, re.IGNORECASE):
            return True
        
        # Gyutto格式验证
        if re.match(r'^GYUTTO-\d+$', code, re.IGNORECASE):
            return True
        
        # 259LUXU格式验证
        if re.match(r'^259LUXU-\d+$', code, re.IGNORECASE):
            return True
        
        # MUGEN格式验证
        if re.match(r'^(MKB?D-S\d{2,3}|MK3D2DBD-\d{2,3}|S2M-\d{2,3}|S2MBD-\d{2,3})$', code, re.IGNORECASE):
            return True
        
        # IBW格式验证
        if re.match(r'^IBW-\d{2,5}z$', code, re.IGNORECASE):
            return True
        
        # 基本格式验证（带连字符）
        if re.match(r'^[A-Z]{2,10}-\d{2,5}$', code, re.IGNORECASE):
            return True
        
        # 东热特殊格式
        if re.match(r'^(red[01]\d{2}|sky[0-3]\d{2}|ex00[01]\d)$', code, re.IGNORECASE):
            return True
        
        # TMA格式
        if re.match(r'^T28-\d{3}$', code, re.IGNORECASE):
            return True
        
        # 东热n, k系列
        if re.match(r'^[nkNK]\d{4}$', code, re.IGNORECASE):
            return True
        
        # 纯数字格式（无码）
        if re.match(r'^\d{6}-\d{2,3}$', code):
            return True
        
        # 其他特殊格式验证
        special_patterns = [
            r'^1pondo-\d{6}_\d{3}$',
            r'^(carib|caribbeancom)-\d{6}-\d{3}$',
            r'^10musume-\d{6}_\d{2}$',
            r'^(HEYZO|Heyzo)-\d{4}$',
            r'^XXXAV-\d{4,5}$',
        ]
        
        for pattern in special_patterns:
            if re.match(pattern, code, re.IGNORECASE):
                return True
        
        return False
    
    def get_cid(self, filepath: str) -> str:
        """
        尝试将给定的文件名匹配为CID（Content ID）
        基于 javsp_mac 的 get_cid 函数
        """
        basename = os.path.splitext(os.path.basename(filepath))[0]
        # 移除末尾可能带有的分段影片序号
        cd_postfix = re.compile(r'([-_]\w|cd\d)$')
        possible = cd_postfix.sub('', basename)
        
        # cid只由数字、小写字母和下划线组成
        match = re.match(r'^([a-z\d_]+)$', possible, re.A)
        if match:
            possible = match.group(1)
            if '_' not in possible:
                # 长度为7-14的cid就占了约99.01%
                match = re.match(r'^[a-z\d]{7,19}$', possible)
                if match:
                    return possible
            else:
                # 绝大多数都只有一个下划线
                match2 = re.match(r'''^h_\d{3,4}[a-z]{1,10}\d{2,5}[a-z\d]{0,8}$|^\d{3}_\d{4,5}$|^402[a-z]{3,6}\d*_[a-z]{3,8}\d{5,6}$|^h_\d{3,4}wvr\d\w\d{4,5}[a-z\d]{0,8}$''', possible, re.VERBOSE)
                if match2:
                    return possible
        return ''
    
    def guess_av_type(self, avid: str) -> str:
        """
        识别给定的番号所属的分类: normal, fc2, cid, getchu, gyutto
        基于 javsp_mac 的 guess_av_type 函数
        """
        if re.match(r'^FC2-\d{5,7}$', avid, re.I):
            return 'fc2'
        if re.match(r'^GETCHU-(\d+)', avid, re.I):
            return 'getchu'
        if re.match(r'^GYUTTO-(\d+)', avid, re.I):
            return 'gyutto'
        
        # 如果传入的avid完全匹配cid的模式，则将影片归类为cid
        cid = self.get_cid(avid)
        if cid == avid:
            return 'cid'
        
        # 以上都不是: 默认归类为normal
        return 'normal'
    
    def test_extraction(self, test_files: List[str]) -> None:
        """
        测试番号提取功能（增强版测试）
        """
        print("增强版番号提取测试")
        print("=" * 60)
        
        for filename in test_files:
            code = self.extract_code_from_filename(filename)
            all_codes = self.extract_all_codes_from_filename(filename)
            cid = self.get_cid(filename) if code else ''
            av_type = self.guess_av_type(code) if code else ''
            
            print(f"文件名: {filename}")
            print(f"主要番号: {code if code else '未找到'}")
            print(f"所有番号: {', '.join(all_codes) if all_codes else '未找到'}")
            if cid:
                print(f"CID: {cid}")
            if av_type:
                print(f"类型: {av_type}")
            print("-" * 40)

# 测试用例
if __name__ == "__main__":
    extractor = CodeExtractor()
    
    # 增强版测试文件名 - 包含更多特殊格式
    test_files = [
        # 原有测试用例
        "httm-012.mp4",
        "ABF-255.mp4",
        "4k2.com@13dsvr01774_1_8k.mp4",
        "MYBA-082.mp4",
        "ADN-689.mp4",
        "OFES-025-C.mp4",
        "IPZZ-524-C.mp4",
        "ABF-255耳元でそっとささやく家庭崩壊確定な不倫のお誘い。 涼森れむ.mp4",
        "[PRESTIGE] ABF-255 [1080p].mp4",
        "SSIS-123 新人NO.1STYLE 夢乃あいか.mp4",
        "MIDE123 Julia.mp4",
        "JUL-001.mp4",
        "PRED-123.mp4",
        
        # javsp_mac 特殊格式测试
        "FC2-PPV-1234567 素人美女.mp4",
        "fc2ppv1234567.mp4",
        "FC2 PPV 1234567.mp4",
        "heydouga-4017-123.mp4",
        "hey-4017-123.mp4",
        "getchu-12345.mp4",
        "gyutto-67890.mp4",
        "259luxu-1234.mp4",
        "MKBD-S123.mp4",
        "MK3D2DBD-45.mp4",
        "IBW-123z.mp4",
        "T28-557.mp4",
        "n1234.mp4",
        "k5678.mp4",
        "red0123.mp4",
        "sky0456.mp4",
        "ex0012.mp4",
        "123456-789.mp4",
        "1pondo-123456_789.mp4",
        "carib-123456-789.mp4",
        "caribbeancom-123456-789.mp4",
        "10musume-123456_01.mp4",
        "HEYZO-1234.mp4",
        "h_826zizd021.mp4",  # CID 格式
        
        # 域名过滤测试
        "javbus.com_ABC-123.mp4",
        "xxx.net@DEF-456.mp4",
        
        # 应该提取不到番号的文件
        "movie_2024_1080p.mp4",
        "random_file.mp4",
        "2024.mp4",
        "720p.mp4",
    ]
    
    extractor.test_extraction(test_files)