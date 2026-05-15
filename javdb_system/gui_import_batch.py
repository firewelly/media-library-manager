#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JAVDB系统 - 批量导入JAVDB信息（针对无标题视频）
从 media_library.py 第 11235-11435 行提取

函数说明:
  - batch_import_javdb_for_no_title(): 顶部菜单"批量导入JAVDB信息"
    针对选定文件夹中没有JAVDB标题的视频，批量获取信息
"""

def batch_import_javdb_for_no_title(self):
    """
    批量导入JAVDB信息 - 针对没有JAVDB标题的视频
    
    流程:
      1. 获取当前选定的文件夹
      2. 查询该文件夹下没有JAVDB标题的视频
      3. 优先使用JavSP集成模块（如果可用）
      4. 否则回退到 javdb_crawler_single.py
      5. 保存结果到数据库
    """
    try:
        # 获取当前选定的文件夹
        selected_folder_indices = self.folder_listbox.curselection()
        if not selected_folder_indices or not hasattr(self, 'folder_path_mapping'):
            messagebox.showwarning("警告", "请先选择一个文件夹")
            return
            
        selected_folder = self.folder_listbox.get(selected_folder_indices[0])
        if selected_folder == "全部":
            messagebox.showwarning("警告", "请选择具体的文件夹，不能选择'全部'")
            return
            
        if selected_folder not in self.folder_path_mapping:
            messagebox.showwarning("警告", "无法找到选定文件夹的路径")
            return
            
        folder_path = self.folder_path_mapping[selected_folder]
        
        # 查询该文件夹下没有JAVDB标题的视频
        if platform.system() == "Windows":
            self.cursor.execute("""
                SELECT v.id, v.file_path, v.file_name 
                FROM videos v
                LEFT JOIN javdb_info j ON v.id = j.video_id
                WHERE REPLACE(v.source_folder, CHAR(92), '/') LIKE REPLACE(?, CHAR(92), '/') || '%' 
                  AND (j.javdb_title IS NULL OR j.javdb_title = '')
            """, (folder_path,))
        else:
            self.cursor.execute("""
                SELECT v.id, v.file_path, v.file_name 
                FROM videos v
                LEFT JOIN javdb_info j ON v.id = j.video_id
                WHERE v.source_folder LIKE ? AND (j.javdb_title IS NULL OR j.javdb_title = '')
            """, (f"{folder_path}%",))
        
        videos_without_javdb = self.cursor.fetchall()
        
        if not videos_without_javdb:
            messagebox.showinfo(
                "信息",
                f"文件夹 '{selected_folder}' 中没有找到缺少JAVDB标题的视频"
            )
            return
            
        # 确认对话框
        if not messagebox.askyesno(
            "确认",
            f"找到 {len(videos_without_javdb)} 个没有JAVDB标题的视频\n\n是否开始批量导入JAVDB信息？\n\n注意：此操作可能需要较长时间"
        ):
            return
            
        # 创建进度窗口
        progress_window = tk.Toplevel(self.root)
        progress_window.title("批量导入JAVDB信息")
        progress_window.geometry("600x400")
        progress_window.transient(self.root)
        progress_window.grab_set()
        
        progress_label = ttk.Label(progress_window, text="准备导入...")
        progress_label.pack(pady=10)
        
        progress_bar = ttk.Progressbar(
            progress_window, length=500, maximum=len(videos_without_javdb)
        )
        progress_bar.pack(pady=10)
        
        log_frame = ttk.Frame(progress_window)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        log_text = tk.Text(log_frame, height=15, width=70)
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=log_text.yview)
        log_text.configure(yscrollcommand=scrollbar.set)
        log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        def log_message(message):
            log_text.insert(tk.END, message + "\n")
            log_text.see(tk.END)
            progress_window.update()
            
        cancel_button = ttk.Button(progress_window, text="取消")
        cancel_button.pack(pady=5)
        
        self.cancel_import = False
        
        def cancel_import():
            self.cancel_import = True
            cancel_button.config(text="关闭", command=progress_window.destroy)
            
        cancel_button.config(command=cancel_import)
        
        def import_thread():
            try:
                # 尝试使用新的JavSP集成模块
                try:
                    from javsp_integration import get_integration_instance
                    javsp_integration = get_integration_instance(self.db_path)
                    use_javsp = javsp_integration.is_available()
                    if use_javsp:
                        log_message("使用JavSP爬虫系统进行批量导入")
                    else:
                        log_message("JavSP系统不可用，回退到原有方法")
                except ImportError:
                    use_javsp = False
                    log_message("JavSP集成模块不可用，使用原有方法")
                
                if not use_javsp:
                    from code_extractor import CodeExtractor
                    import subprocess
                    import json
                    extractor = CodeExtractor()
                
                imported_count = 0
                skipped_count = 0
                
                for i, (video_id, file_path, file_name) in enumerate(videos_without_javdb):
                    if self.cancel_import:
                        break
                        
                    progress_bar.config(value=i + 1)
                    progress_label.config(
                        text=f"处理: {file_name} ({i + 1}/{len(videos_without_javdb)})"
                    )
                    
                    if use_javsp:
                        av_code = javsp_integration.extract_code_from_filename(file_name)
                    else:
                        av_code = extractor.extract_code_from_filename(file_name)
                    
                    if not av_code:
                        skipped_count += 1
                        log_message(f"- 无法提取番号: {file_name}")
                        continue
                        
                    log_message(f"提取番号: {av_code} <- {file_name}")
                    
                    try:
                        if use_javsp:
                            result = javsp_integration.search_movie_info(av_code)
                            if result:
                                if javsp_integration.save_movie_info_to_db(video_id, result):
                                    imported_count += 1
                                    log_message(f"✓ 成功导入: {av_code} - {result.get('title', 'N/A')}")
                                else:
                                    skipped_count += 1
                                    log_message(f"✗ 保存失败: {av_code}")
                            else:
                                skipped_count += 1
                                log_message(f"✗ 未找到信息: {av_code}")
                        else:
                            # 回退到原有的JAVDB爬虫逻辑
                            cmd = [sys.executable, "javdb_crawler_single.py", av_code]
                            process = subprocess.run(
                                cmd, capture_output=True, text=True,
                                cwd=os.path.dirname(os.path.abspath(__file__)), timeout=180
                            )
                            if process.returncode == 0 and process.stdout:
                                try:
                                    result = json.loads(process.stdout)
                                    if "error" not in result:
                                        self.save_javdb_info_to_db(video_id, result)
                                        imported_count += 1
                                        log_message(f"✓ 成功导入: {av_code} - {result.get('title', 'N/A')}")
                                    else:
                                        skipped_count += 1
                                        log_message(f"✗ JAVDB返回错误: {av_code} - {result.get('error', 'Unknown error')}")
                                except json.JSONDecodeError:
                                    skipped_count += 1
                                    log_message(f"✗ 解析JAVDB响应失败: {av_code}")
                            else:
                                skipped_count += 1
                                log_message(f"✗ JAVDB获取失败: {av_code}")
                                
                    except subprocess.TimeoutExpired:
                        skipped_count += 1
                        log_message(f"✗ 获取超时: {av_code}")
                    except Exception as e:
                        skipped_count += 1
                        log_message(f"✗ 处理错误: {av_code} - {str(e)}")
                
                progress_label.config(text="导入完成")
                log_message(f"\n=== 导入完成 ===")
                log_message(f"成功导入: {imported_count} 个")
                log_message(f"跳过: {skipped_count} 个")
                cancel_button.config(text="关闭", command=progress_window.destroy)
                self.root.after(100, self.load_videos)
                
            except ImportError:
                log_message("错误: 无法导入番号提取器模块")
                cancel_button.config(text="关闭", command=progress_window.destroy)
            except Exception as e:
                log_message(f"批量导入过程中发生错误: {str(e)}")
                cancel_button.config(text="关闭", command=progress_window.destroy)
        
        thread = threading.Thread(target=import_thread, daemon=True)
        thread.start()
        
    except Exception as e:
        messagebox.showerror("错误", f"批量导入JAVDB信息失败: {str(e)}")
