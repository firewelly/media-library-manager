#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JAVDB系统 - 错误标题修正
从 media_library.py 第 11591-11850 行提取

函数说明:
  - fix_javdb_error_titles(): 修正JAVDB错误信息（工具菜单入口）
    针对标题为 '官方App下載' 等错误记录的重新获取

字段映射: 同 gui_fetch_single.py 中的 fetch_javdb_info()
"""

def fix_javdb_error_titles(self):
    """
    修正JAVDB错误信息，特别是标题为'官方App下載'的记录
    
    识别以下错误标题:
      - '官方App下載'
      - '官方App下载'
      - 'Official App Download'
      - 'アプリダウンロード'
      - '公式アプリ'
    
    流程:
      1. 查询所有标题为错误信息的记录
      2. 逐条重新获取正确信息
      3. 三级回退: JavDB → JavBus → JavSP
    """
    try:
        # 查询所有标题为错误信息的记录
        error_titles = [
            '官方App下載', '官方App下载', 'Official App Download',
            'アプリダウンロード', '公式アプリ'
        ]
        
        placeholders = ','.join(['?' for _ in error_titles])
        query = f"""
            SELECT v.id, v.file_name, v.file_path, j.javdb_title, j.javdb_code
            FROM videos v 
            JOIN javdb_info j ON v.id = j.video_id 
            WHERE j.javdb_title IN ({placeholders})
        """
        
        self.cursor.execute(query, error_titles)
        error_records = self.cursor.fetchall()
        
        if not error_records:
            messagebox.showinfo("信息", "没有找到需要修正的JAVDB错误信息")
            return
        
        # 确认对话框
        result = messagebox.askyesno(
            "确认修正", 
            f"找到 {len(error_records)} 条需要修正的JAVDB错误信息。\n\n"
            f"这些记录的标题包含错误信息（如'官方App下載'），\n"
            f"将重新获取正确的JAVDB信息。\n\n是否继续？"
        )
        if not result:
            return
        
        # 创建进度窗口
        progress_window = tk.Toplevel(self.root)
        progress_window.title("修正JAVDB错误信息")
        progress_window.geometry("600x400")
        progress_window.transient(self.root)
        progress_window.grab_set()
        
        progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(progress_window, variable=progress_var, maximum=100)
        progress_bar.pack(fill=tk.X, padx=10, pady=5)
        
        status_var = tk.StringVar(value="准备开始...")
        status_label = ttk.Label(progress_window, textvariable=status_var)
        status_label.pack(pady=5)
        
        log_frame = ttk.Frame(progress_window)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        log_text = tk.Text(log_frame, wrap=tk.WORD)
        log_scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=log_text.yview)
        log_text.configure(yscrollcommand=log_scrollbar.set)
        log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        cancel_var = tk.BooleanVar()
        cancel_button = ttk.Button(
            progress_window, text="取消",
            command=lambda: cancel_var.set(True)
        )
        cancel_button.pack(pady=5)
        
        def log_message(message):
            log_text.insert(tk.END, f"{message}\n")
            log_text.see(tk.END)
            progress_window.update()
        
        def fix_records():
            """在后台线程中修正记录"""
            try:
                # 准备备用模块
                javsp_available = False
                javsp = None
                try:
                    from javsp_integration import JavSPIntegration
                    javsp = JavSPIntegration()
                    if javsp.is_available():
                        javsp_available = True
                        log_message("JavSP爬虫系统已准备作为备用")
                    else:
                        log_message("JavSP不可用")
                except ImportError:
                    log_message("JavSP集成模块不可用")
                
                log_message("优先使用javdb_crawler_single.py爬虫")
                
                try:
                    from code_extractor import CodeExtractor
                    extractor = CodeExtractor()
                except ImportError:
                    log_message("警告：无法导入番号提取器，将使用简单的文件名解析")
                    extractor = None
                
                success_count = 0
                skip_count = 0
                
                for i, (video_id, file_name, file_path, old_title, old_code) in enumerate(error_records):
                    if cancel_var.get():
                        log_message("用户取消操作")
                        break
                    
                    progress = (i / len(error_records)) * 100
                    progress_var.set(progress)
                    status_var.set(f"修正 {i+1}/{len(error_records)}: {file_name}")
                    
                    log_message(f"\n处理: {file_name}")
                    log_message(f"原标题: {old_title}")
                    
                    # 从文件名提取番号
                    if extractor:
                        code = extractor.extract_code_from_filename(file_name)
                    else:
                        import re
                        code_match = re.search(r'([A-Z]+-\d+)', file_name.upper())
                        code = code_match.group(1) if code_match else None
                    
                    if not code:
                        log_message(f"无法从文件名提取番号，跳过: {file_name}")
                        skip_count += 1
                        continue
                    
                    log_message(f"提取的番号: {code}")
                    
                    # 三级回退获取信息
                    javdb_info = None
                    
                    # 1. javdb_crawler_single.py
                    try:
                        import subprocess
                        import json
                        result = subprocess.run(
                            [sys.executable, 'javdb_crawler_single.py', code],
                            capture_output=True, text=True, timeout=180
                        )
                        if result.returncode == 0:
                            javdb_info = json.loads(result.stdout)
                            if (javdb_info and javdb_info.get('title') and 
                                javdb_info['title'] not in error_titles and javdb_info.get('actors')):
                                log_message("✓ javdb_crawler_single.py获取信息成功")
                            else:
                                log_message("javdb_crawler_single.py获取的信息不完整或被屏蔽")
                                javdb_info = None
                        else:
                            log_message(f"javdb_crawler_single.py获取失败: {result.stderr}")
                    except Exception as e:
                        log_message(f"javdb_crawler_single.py执行失败: {str(e)}")
                    
                    # 2. JavBus 备用
                    if not javdb_info:
                        try:
                            log_message("使用javbus_crawler_single.py作为备用爬虫")
                            result = subprocess.run(
                                [sys.executable, 'javbus_crawler_single.py', code],
                                capture_output=True, text=True, timeout=60
                            )
                            if result.returncode == 0:
                                javbus_info = json.loads(result.stdout)
                                if (javbus_info and javbus_info.get('success') and
                                    javbus_info.get('title') and javbus_info['title'] not in error_titles):
                                    javdb_info = {
                                        'title': javbus_info['title'],
                                        'actors': javbus_info.get('actors', []),
                                        'release_date': javbus_info.get('release_date', ''),
                                        'duration': javbus_info.get('duration', ''),
                                        'studio': javbus_info.get('studio', ''),
                                        'tags': javbus_info.get('tags', []),
                                        'rating': javbus_info.get('rating', ''),
                                        'cover_image_url': javbus_info.get('cover_image_url', ''),
                                        'local_image_path': javbus_info.get('cover_image_path', ''),
                                        'magnet_links': javbus_info.get('magnet_links', []),
                                        'detail_url': f"https://www.javbus.com/{code}",
                                        'video_id': code
                                    }
                                    log_message("✓ javbus_crawler_single.py获取信息成功")
                                else:
                                    log_message("javbus_crawler_single.py获取的信息不完整")
                            else:
                                log_message(f"javbus_crawler_single.py获取失败: {result.stderr}")
                        except Exception as e:
                            log_message(f"javbus_crawler_single.py执行失败: {str(e)}")
                    
                    # 3. JavSP 最后备用
                    if not javdb_info and javsp_available:
                        try:
                            log_message("使用JavSP作为最后备用爬虫")
                            javdb_info = javsp.search_movie_info(code)
                            if javdb_info:
                                log_message("✓ JavSP备用爬虫获取信息成功")
                            else:
                                log_message("JavSP备用爬虫未找到信息")
                        except Exception as e:
                            log_message(f"JavSP备用爬虫获取失败: {str(e)}")
                    
                    if javdb_info and javdb_info.get('title') and javdb_info['title'] not in error_titles:
                        try:
                            self.save_javdb_info_to_db(video_id, javdb_info)
                            log_message(f"✓ 成功更新: {javdb_info['title']}")
                            success_count += 1
                        except Exception as e:
                            log_message(f"保存到数据库失败: {str(e)}")
                            skip_count += 1
                    else:
                        log_message("未获取到有效信息或信息仍为错误标题，跳过")
                        skip_count += 1
                
                self.conn.commit()
                
                if not cancel_var.get():
                    progress_var.set(100)
                    status_var.set("修正完成")
                    log_message(f"\n修正完成！")
                    log_message(f"成功修正: {success_count} 条")
                    log_message(f"跳过: {skip_count} 条")
                    self.root.after(0, self.load_videos)
                    messagebox.showinfo(
                        "完成",
                        f"JAVDB错误信息修正完成！\n\n成功修正: {success_count} 条\n跳过: {skip_count} 条"
                    )
                
            except Exception as e:
                log_message(f"修正过程出错: {str(e)}")
                messagebox.showerror("错误", f"修正JAVDB错误信息时出错: {str(e)}")
            finally:
                progress_window.destroy()
        
        # 在后台线程中执行修正
        import threading
        thread = threading.Thread(target=fix_records)
        thread.daemon = True
        thread.start()
        
    except Exception as e:
        messagebox.showerror("错误", f"修正JAVDB错误信息时出错: {str(e)}")
