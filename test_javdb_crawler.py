#!/usr/bin/env python3
"""
测试脚本：比较直接调用JAVDB爬虫与通过media_library.py调用的差异
用于找出media_library.py中右键"JAVDB信息获取"功能无法使用JAVDB爬虫的原因
"""

import os
import sys
import json
import subprocess
import sqlite3
import traceback
from datetime import datetime

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 测试配置
TEST_VIDEO_CODE = "XVSR-800"  # 测试用番号
TEST_VIDEO_ID = 50194  # 测试用视频ID（XVSR-800在数据库中的实际ID）

def test_direct_javdb_crawler():
    """测试直接调用JAVDB爬虫"""
    print("=" * 50)
    print("测试1: 直接调用JAVDB爬虫")
    print("=" * 50)
    
    try:
        # 直接调用javdb_crawler_single.py
        print(f"执行命令: python javdb_crawler_single.py {TEST_VIDEO_CODE}")
        result = subprocess.run(
            [sys.executable, "javdb_crawler_single.py", TEST_VIDEO_CODE],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        print(f"返回码: {result.returncode}")
        print(f"标准输出:\n{result.stdout}")
        if result.stderr:
            print(f"标准错误:\n{result.stderr}")
        
        if result.returncode == 0:
            try:
                data = json.loads(result.stdout)
                if "error" in data:
                    print(f"直接调用JAVDB爬虫失败: {data['error']}")
                    return False
                else:
                    print(f"直接调用JAVDB爬虫成功，获取到视频信息: {data.get('title', 'N/A')}")
                    return True
            except json.JSONDecodeError as e:
                print(f"解析JSON输出失败: {e}")
                print("原始输出内容:")
                print(result.stdout[:500])  # 打印前500个字符
                return False
        else:
            print("直接调用JAVDB爬虫失败")
            return False
    except subprocess.TimeoutExpired:
        print("直接调用JAVDB爬虫超时")
        return False
    except Exception as e:
        print(f"直接调用JAVDB爬虫出错: {e}")
        traceback.print_exc()
        return False

def test_direct_javdb_crawler_import():
    """测试直接导入并调用JAVDB爬虫"""
    print("\n" + "=" * 50)
    print("测试1b: 直接导入并调用JAVDB爬虫")
    print("=" * 50)
    
    try:
        print("导入javdb_crawler_single模块...")
        import javdb_crawler_single
        
        print(f"调用crawl_single_video函数，参数: {TEST_VIDEO_CODE}")
        result = javdb_crawler_single.crawl_single_video(TEST_VIDEO_CODE)
        
        if result:
            print(f"直接导入调用JAVDB爬虫成功，获取到视频信息: {result.get('title', 'N/A')}")
            return True
        else:
            print("直接导入调用JAVDB爬虫失败，返回结果为空")
            return False
    except Exception as e:
        print(f"直接导入调用JAVDB爬虫出错: {e}")
        traceback.print_exc()
        return False

def test_media_library_javdb():
    """测试通过media_library.py调用JAVDB爬虫"""
    print("\n" + "=" * 50)
    print("测试2: 通过media_library.py调用JAVDB爬虫")
    print("=" * 50)
    
    conn = None
    try:
        # 导入media_library模块
        import sys
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        import media_library
        
        # 创建数据库连接
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'media_library.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 查找测试视频记录
        cursor.execute("SELECT id, title, file_path FROM videos WHERE id = ?", (TEST_VIDEO_ID,))
        video_record = cursor.fetchone()
        
        if not video_record:
            print(f"未找到视频ID {TEST_VIDEO_ID}")
            return False
            
        video_id, title, file_path = video_record
        print(f"找到视频记录: ID={video_id}, 标题={title}, 路径={file_path}")
        
        # 导入CodeExtractor
        from code_extractor import CodeExtractor
        extractor = CodeExtractor()
        
        # 使用正确的方法名
        print(f"从 {TEST_VIDEO_CODE} 中提取代码...")
        extracted_code = extractor.extract_code_from_filename(TEST_VIDEO_CODE)
        print(f"提取的代码: {extracted_code}")
        
        # 尝试调用media_library中的batch_process_javdb_info函数
        print("尝试调用batch_process_javdb_info函数...")
        try:
            # 直接调用batch_process_javdb_info函数处理单个视频
            result = media_library.batch_process_javdb_info(video_ids=[TEST_VIDEO_ID])
            print(f"batch_process_javdb_info结果: {result}")
            return True
        except Exception as e:
            print(f"调用batch_process_javdb_info函数出错: {str(e)}")
            traceback.print_exc()
            
            # 尝试直接调用save_javdb_info_to_db函数
            print("\n尝试直接调用save_javdb_info_to_db函数...")
            try:
                # 创建一个模拟的javdb_info字典
                mock_javdb_info = {
                    'title': '测试标题',
                    'code': TEST_VIDEO_CODE,
                    'release_date': '2023-01-01',
                    'duration': '120',
                    'rating': '8.5',
                    'tags': ['测试标签1', '测试标签2'],
                    'actors': ['测试演员1', '测试演员2'],
                    'studio': '测试片商',
                    'cover_image': None,
                    'sample_images': [],
                    'magnet_links': []
                }
                
                # 调用save_javdb_info_to_db函数
                result = media_library.save_javdb_info_to_db(video_id, mock_javdb_info)
                print(f"save_javdb_info_to_db结果: {result}")
                return True
            except Exception as e2:
                print(f"调用save_javdb_info_to_db函数出错: {str(e2)}")
                traceback.print_exc()
                return False
        
    except Exception as e:
        print(f"通过media_library.py调用JAVDB爬虫出错: {str(e)}")
        traceback.print_exc()
        return False
    finally:
        if conn:
            conn.close()

def test_batch_process_javdb_info():
    """测试media_library.py中的batch_process_javdb_info函数"""
    print("\n" + "=" * 50)
    print("测试3: 模拟media_library.py中的batch_process_javdb_info函数")
    print("=" * 50)
    
    try:
        # 导入必要的模块
        print("导入必要的模块...")
        import media_library
        import code_extractor
        import javdb_crawler_single
        import javbus_crawler_single
        
        # 创建测试视频ID列表
        test_video_ids = [50194]  # 使用XVSR-800在数据库中的实际ID
        
        # 模拟batch_process_javdb_info函数的逻辑
        for video_id in test_video_ids:
            print(f"处理视频ID: {video_id}")
            
            # 获取视频信息
            conn = sqlite3.connect("media_library.db")
            cursor = conn.cursor()
            cursor.execute("SELECT title, file_name FROM videos WHERE id = ?", (video_id,))
            video_record = cursor.fetchone()
            
            if not video_record:
                print(f"未找到视频ID {video_id}")
                continue
                
            title, file_name = video_record
            print(f"视频标题: {title}, 文件名: {file_name}")
            
            # 提取番号
            extractor = code_extractor.CodeExtractor()
            extracted_codes = extractor.extract_codes(title) or extractor.extract_codes(file_name)
            
            if not extracted_codes:
                print(f"无法从标题或文件名中提取番号: {title}, {file_name}")
                continue
                
            video_code = extracted_codes[0]
            print(f"提取到番号: {video_code}")
            
            # 尝试使用JAVDB爬虫
            print("尝试使用JAVDB爬虫...")
            javdb_result = javdb_crawler_single.crawl_single_video(video_code)
            
            if javdb_result and javdb_result.get('title') != 'N/A':
                print(f"JAVDB爬虫成功: {javdb_result.get('title')}")
                
                # 检查演员信息
                actors = javdb_result.get('actors', [])
                print(f"演员数量: {len(actors)}")
                if actors:
                    print("演员列表:")
                    for actor in actors:
                        print(f"  - {actor.get('name', 'N/A')}")
                else:
                    print("警告: 没有获取到演员信息")
                
                # 检查是否满足media_library.py中的条件
                print("检查是否满足media_library.py中的条件...")
                has_actors = len(actors) > 0
                print(f"是否有演员信息: {has_actors}")
                
                if has_actors:
                    print("满足条件，不会回退到JavBus爬虫")
                else:
                    print("不满足条件，会回退到JavBus爬虫")
            else:
                print("JAVDB爬虫失败或返回无效结果")
                
                # 尝试使用JavBus爬虫作为回退
                print("尝试使用JavBus爬虫作为回退...")
                javbus_result = javbus_crawler_single.crawl_single_video(video_code)
                
                if javbus_result and javbus_result.get('title') != 'N/A':
                    print(f"JavBus爬虫成功: {javbus_result.get('title')}")
                else:
                    print("JavBus爬虫也失败")
            
            conn.close()
            
        return True
        
    except Exception as e:
        print(f"测试batch_process_javdb_info函数出错: {e}")
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print(f"开始测试JAVDB爬虫，使用测试番号: {TEST_VIDEO_CODE}")
    print(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 测试1: 直接调用JAVDB爬虫
    test1_result = test_direct_javdb_crawler()
    
    # 测试1b: 直接导入并调用JAVDB爬虫
    test1b_result = test_direct_javdb_crawler_import()
    
    # 测试2: 通过media_library.py调用JAVDB爬虫
    test2_result = test_media_library_javdb()
    
    # 测试3: 模拟media_library.py中的batch_process_javdb_info函数
    test3_result = test_batch_process_javdb_info()
    
    # 总结
    print("\n" + "=" * 50)
    print("测试总结")
    print("=" * 50)
    print(f"直接调用JAVDB爬虫: {'成功' if test1_result else '失败'}")
    print(f"直接导入调用JAVDB爬虫: {'成功' if test1b_result else '失败'}")
    print(f"通过media_library.py调用JAVDB爬虫: {'成功' if test2_result else '失败'}")
    print(f"模拟batch_process_javdb_info函数: {'成功' if test3_result else '失败'}")
    
    if test1_result and not test2_result:
        print("\n可能的原因分析:")
        print("1. 直接调用JAVDB爬虫成功，但通过media_library.py调用失败")
        print("2. 可能是media_library.py中的调用方式或参数传递有问题")
        print("3. 可能是media_library.py中的环境设置与直接调用不同")
        print("4. 可能是media_library.py中的错误处理或异常捕获导致问题")
    elif test1_result and test2_result and not test3_result:
        print("\n可能的原因分析:")
        print("1. 直接调用和通过media_library.py调用JAVDB爬虫都成功")
        print("2. 但模拟batch_process_javdb_info函数失败")
        print("3. 可能是batch_process_javdb_info函数中的特定逻辑导致问题")
        print("4. 可能是演员信息检查或其他条件判断导致回退到JavBus爬虫")
    elif not test1_result and not test2_result:
        print("\n可能的原因分析:")
        print("1. 直接调用JAVDB爬虫就失败，可能是网络或代理问题")
        print("2. 可能是JAVDB网站结构变化或登录问题")
        print("3. 可能是测试番号不存在或已被删除")
    elif not test1_result and test1b_result:
        print("\n可能的原因分析:")
        print("1. 直接调用JAVDB爬虫失败，但直接导入调用成功")
        print("2. 可能是subprocess调用方式有问题")
        print("3. 可能是环境变量或工作目录问题")
    else:
        print("\n测试结果不符合预期，需要进一步分析")

if __name__ == "__main__":
    main()