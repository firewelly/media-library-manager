#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强版番号提取工具
整合了 javsp 项目的详细番号提取逻辑
支持更多格式和更准确的识别
"""

import os
import re
from typing import Optional, List, Tuple

class EnhancedCodeExtractor:
    """增强版番号提取器，基于 javsp 项目的逻辑"""
    
    def __init__(self):
        # 忽略模式（用于清理文件名）
        self.ignore_pattern = re.compile(r'[\[\(（].*?[\]\)）]|\d{3,4}[pP]|[hH][dD]|[uU][hH][dD]|[bB][dD]|[dD][vV][dD]|[rR][iI][pP]|[wW][eE][bB][-_]?[dD][lL]|[uU][nN][cC][eE][nN][sS][oO][rR][eE][dD]|[cC][eE][nN][sS][oO][rR][eE][dD]|[lL][eE][aA][kK][eE][dD]|[cC][hH][iI][nN][eE][sS][eE]|[sS][uU][bB]|[字幕]|[中文]|[无码]|[有码]|[高清]|[破解]|[流出]|[泄露]')
        
        # CD 后缀模式（用于移除分段标识）
        self.cd_postfix = re.compile(r'([-_]\w|cd\d)$')
    
    def _clean_filename(self, filename: str) -> str:
        """清理文件名，移除干扰信息"""
        # 移除文件扩展名
        filename = os.path.splitext(filename)[0]
        # 移除忽略模式
        filename = self.ignore_pattern.sub('', filename)
        return filename
    
    def extract_code_from_filename(self, filepath: str) -> Optional[str]:
        """从文件路径中提取番号（基于 javsp 的 get_id 函数）"""
        filename = os.path.basename(filepath)
        filename = self._clean_filename(filename)
        filename_lc = filename.lower()
        
        # FC2 系列
        if 'fc2' in filename_lc:
            # 根据FC2 Club的影片数据，FC2编号为5-7个数字
            match = re.search(r'fc2[^a-z\d]{0,5}(ppv[^a-z\d]{0,5})?(\d{5,7})', filename, re.I)
            if match:
                return 'FC2-' + match.group(2)
        
        # Heydouga 系列
        elif 'heydouga' in filename_lc:
            match = re.search(r'(heydouga)[-_]*(\d{4})[-_]0?(\d{3,5})', filename, re.I)
            if match:
                return '-'.join(match.groups())
        
        # Getchu 系列
        elif 'getchu' in filename_lc:
            match = re.search(r'getchu[-_]*(\d+)', filename, re.I)
            if match:
                return 'GETCHU-' + match.group(1)
        
        # Gyutto 系列
        elif 'gyutto' in filename_lc:
            match = re.search(r'gyutto-(\d+)', filename, re.I)
            if match:
                return 'GYUTTO-' + match.group(1)
        
        # 259LUXU 特殊情况
        elif '259luxu' in filename_lc:
            match = re.search(r'259luxu-(\d+)', filename, re.I)
            if match:
                return '259LUXU-' + match.group(1)
        
        else:
            # 先尝试移除可疑域名进行匹配
            no_domain = re.sub(r'\w{3,10}\.(com|net|app|xyz)', '', filename, flags=re.I)
            if no_domain != filename:
                avid = self.extract_code_from_filename(no_domain)
                if avid:
                    return avid
            
            # 匹配缩写成hey的heydouga影片
            match = re.search(r'(?:hey)[-_]*(\d{4})[-_]0?(\d{3,5})', filename, re.I)
            if match:
                return 'heydouga-' + '-'.join(match.groups())
            
            # 匹配片商 MUGEN 的奇怪番号
            match = re.search(r'(MKB?D)[-_]*(S\d{2,3})|(MK3D2DBD|S2M|S2MBD)[-_]*(\d{2,3})', filename, re.I)
            if match:
                if match.group(1) is not None:
                    return match.group(1) + '-' + match.group(2)
                else:
                    return match.group(3) + '-' + match.group(4)
            
            # 匹配IBW这样带有后缀z的番号
            match = re.search(r'(IBW)[-_](\d{2,5}z)', filename, re.I)
            if match:
                return match.group(1) + '-' + match.group(2)
            
            # 普通番号，优先尝试匹配带分隔符的（如ABC-123）
            match = re.search(r'([a-z]{2,10})[-_](\d{2,5})', filename, re.I)
            if match:
                return match.group(1).upper() + '-' + match.group(2)
            
            # 东热的red, sky, ex三个不带-分隔符的系列
            match = re.search(r'(red[01]\d\d|sky[0-3]\d\d|ex00[01]\d)', filename, re.I)
            if match:
                return match.group(1).upper()
            
            # 缺失了-分隔符的番号
            match = re.search(r'([a-z]{2,})(\d{2,5})', filename, re.I)
            if match:
                return match.group(1).upper() + '-' + match.group(2)
        
        # TMA制作的影片（如'T28-557'）
        match = re.search(r'(T28[-_]\d{3})', filename)
        if match:
            return match.group(1).replace('_', '-')
        
        # 东热n, k系列
        match = re.search(r'(n\d{4}|k\d{4})', filename, re.I)
        if match:
            return match.group(1).lower()
        
        # 纯数字番号（无码影片）
        match = re.search(r'(\d{6}[-_]\d{2,3})', filename)
        if match:
            return match.group(1).replace('_', '-')
        
        # 尝试将')('替换为'-'后再试
        if ')(' in filepath:
            avid = self.extract_code_from_filename(filepath.replace(')(', '-'))
            if avid:
                return avid
        
        # 如果仍然匹配不了，尝试使用文件所在文件夹的名字
        if os.path.isfile(filepath):
            norm = os.path.normpath(filepath)
            if os.sep in norm:
                folder = norm.split(os.sep)[-2]
                return self.extract_code_from_filename(folder)
        
        return None
    
    def extract_cid(self, filepath: str) -> Optional[str]:
        """提取CID（Content ID）"""
        basename = os.path.splitext(os.path.basename(filepath))[0]
        # 移除末尾可能带有的分段影片序号
        possible = self.cd_postfix.sub('', basename)
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
                match2 = re.match(r'''h_\d{3,4}[a-z]{1,10}\d{2,5}[a-z\d]{0,8}$  # 约 99.17%
                                    |^\d{3}_\d{4,5}$                            # 约 0.57%
                                    |^402[a-z]{3,6}\d*_[a-z]{3,8}\d{5,6}$       # 约 0.09%
                                    |^h_\d{3,4}wvr\d\w\d{4,5}[a-z\d]{0,8}$      # 约 0.06%
                                     $''', possible, re.VERBOSE)
                if match2:
                    return possible
        return None
    
    def guess_av_type(self, avid: str) -> str:
        """识别番号类型: normal, fc2, cid, getchu, gyutto"""
        if not avid:
            return 'unknown'
        
        # FC2 系列
        if re.match(r'^FC2-\d{5,7}$', avid, re.I):
            return 'fc2'
        
        # Getchu 系列
        if re.match(r'^GETCHU-(\d+)', avid, re.I):
            return 'getchu'
        
        # Gyutto 系列
        if re.match(r'^GYUTTO-(\d+)', avid, re.I):
            return 'gyutto'
        
        # CID 类型
        cid = self.extract_cid(avid)
        if cid == avid:
            return 'cid'
        
        # 默认为普通类型
        return 'normal'
    
    def extract_all_codes_from_filename(self, filepath: str) -> List[str]:
        """从文件名中提取所有可能的番号"""
        codes = []
        
        # 主要提取方法
        main_code = self.extract_code_from_filename(filepath)
        if main_code:
            codes.append(main_code)
        
        # CID 提取
        cid = self.extract_cid(filepath)
        if cid and cid not in codes:
            codes.append(cid)
        
        return codes
    
    def is_valid_code(self, code: str) -> bool:
        """验证番号是否有效"""
        if not code or len(code) < 3:
            return False
        
        # 检查是否包含有效字符
        if not re.match(r'^[A-Za-z0-9\-_]+$', code):
            return False
        
        # 检查是否为已知类型
        av_type = self.guess_av_type(code)
        return av_type != 'unknown'
    
    def test_extraction(self):
        """测试番号提取功能"""
        test_files = [
            'ABP-123.mp4',
            'FC2-PPV-1234567.mp4',
            'SSIS-001.mp4',
            'heydouga-4017-123.mp4',
            'n1234.mp4',
            'GETCHU-12345.mp4',
            '259LUXU-1234.mp4',
            'IBW-123z.mp4',
            'T28-557.mp4',
            'h_1234abcd567.mp4',
            '[厂商] SSIS-001 标题.mp4',
            'SSIS001.mp4',
            '123456-789.mp4'
        ]
        
        print("增强版番号提取测试:")
        print("-" * 50)
        
        for filename in test_files:
            code = self.extract_code_from_filename(filename)
            av_type = self.guess_av_type(code) if code else 'unknown'
            print(f"{filename:<30} -> {code or 'None':<15} ({av_type})")


if __name__ == "__main__":
    extractor = EnhancedCodeExtractor()
    extractor.test_extraction()