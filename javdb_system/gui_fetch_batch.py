#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JAVDB系统 - 批量视频信息获取
从 media_library.py 第 6864-7363 行提取

函数说明:
  - batch_javdb_info_selected_videos(): 右键菜单"批量JAVDB信息获取"入口
  - batch_process_javdb_info(video_ids): 批量处理核心逻辑

字段映射: 同 gui_fetch_single.py 中的 fetch_javdb_info()
"""

def batch_javdb_info_selected_videos(self):
    """批量获取选中视频的JAVDB信息（右键菜单入口）"""
    try:
        selected_items = self.video_tree.selection()
        if not selected_items:
            messagebox.showwarning("警告", "请先选择要获取JAVDB信息的视频文件")
            return
        
        # 获取选中视频的数字ID
        video_ids = []
        for item in selected_items:
            try:
                tags = self.video_tree.item(item, 'tags')
                if tags:
                    video_id = int(tags[0])
                    self.cursor.execute("SELECT file_path FROM videos WHERE id = ?", (video_id,))
                    result = self.cursor.fetchone()
                    if result:
                        is_online = self.is_video_online(video_id)
                        if is_online:
                            video_ids.append(video_id)
            except Exception as e:
                print(f"获取视频ID时出错: {e}")
                continue
        
        if not video_ids:
            messagebox.showwarning("警告", "没有选中在线的视频文件")
            return
        
        # 确认对话框
        if not messagebox.askyesno(
            "确认",
            f"确定要获取 {len(video_ids)} 个视频的JAVDB信息吗？\n\n注意：这可能需要较长时间，请耐心等待。"
        ):
            return
        
        # 执行批量JAVDB信息获取
        self.batch_process_javdb_info(video_ids)
        
    except Exception as e:
        error_msg = f"批量JAVDB信息获取启动失败: {str(e)}"
        print(error_msg)
        messagebox.showerror("错误", error_msg)


def batch_process_javdb_info(self, video_ids):
    """
    批量处理JAVDB信息获取（核心批量方法）
    
    Args:
        video_ids: 视频ID列表
    
    流程:
        1. 遍历每个视频ID
        2. 从文件名提取番号
        3. 三级回退获取信息 (JavDB → JavBus → JavSP)
        4. 保存到数据库
        5. 延迟1秒避免频繁请求
    """
    try:
        print(f"开始批量处理JAVDB信息，视频数量: {len(video_ids)}")
        
        progress_window = ProgressWindow(self.root, "批量JAVDB信息获取", len(video_ids))
        
        def fetch_javdb_info():
            try:
                print("fetch_javdb_info线程开始执行")
                failed_files = []
                manual_action_prompted = False
                
                for i, video_id in enumerate(video_ids):
                    if progress_window.cancelled:
                        break
                    
                    self.cursor.execute(
                        "SELECT file_name, file_path FROM videos WHERE id = ?", (video_id,)
                    )
                    result = self.cursor.fetchone()
                    if not result:
                        failed_files.append(f"ID {video_id}: 未找到视频记录")
                        progress_window.update_progress(i + 1, f"ID {video_id}", success=False)
                        continue
                    
                    file_name, file_path = result
                    progress_window.update_progress(i + 1, file_name)
                    progress_window.update_status(f"正在提取番号: {file_name}")
                    
                    try:
                        from code_extractor import CodeExtractor
                        extractor = CodeExtractor()
                        av_code = extractor.extract_code_from_filename(file_name)
                        
                        if not av_code:
                            failed_files.append(f"{file_name}: 无法提取番号")
                            progress_window.update_progress(i + 1, file_name, success=False)
                            progress_window.update_status(f"失败: 无法提取番号", "red")
                            continue
                        
                        progress_window.update_status(f"正在爬取JAVDB信息: {av_code}")
                        
                        import subprocess
                        import json
                        
                        def normalize_actors_from_names(names):
                            if not isinstance(names, list):
                                return []
                            return [{"name": n, "link": ""} for n in names if isinstance(n, str) and n.strip()]
                        
                        result_data = None
                        blocked_titles = ['官方App下載', '官方App下载', 'Official App Download']
                        cwd_dir = runtime_dir()
                        
                        # ---- ① JavDB 优先 ----
                        try:
                            if getattr(sys, 'frozen', False):
                                cmd = [os.path.join(runtime_dir(), "javdb_crawler_single.exe"), av_code]
                            else:
                                cmd = [sys.executable, "javdb_crawler_single.py", av_code]
                            process = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd_dir, timeout=180)
                            if process.returncode == 0 and process.stdout:
                                try:
                                    parsed = json.loads(process.stdout)
                                    if parsed and not parsed.get('error') and parsed.get('title') and parsed.get('title') not in blocked_titles:
                                        result_data = parsed
                                        has_actors = isinstance(parsed.get('actors'), list) and len(parsed.get('actors')) > 0
                                        progress_window.update_status("✓ JavDB成功" if has_actors else "JavDB成功（演员缺失，尝试回退）")
                                    else:
                                        progress_window.update_status("JavDB信息不完整，尝试回退")
                                except json.JSONDecodeError:
                                    progress_window.update_status("JavDB解析失败，尝试回退")
                            else:
                                if (not manual_action_prompted) and self._crawler_needs_manual_action(process.stderr):
                                    manual_action_prompted = True
                                    self.root.after(0, lambda: messagebox.showwarning(
                                        "需要人工验证",
                                        "检测到JAVDB登录或Cloudflare验证需求。\n\n请先完成一次人工验证，再重新执行批量更新。"
                                    ))
                                progress_window.update_status("JavDB爬虫失败，尝试回退")
                        except Exception as e:
                            progress_window.update_status(f"JavDB异常: {e}，尝试回退")
                        
                        # ---- ② JavBus/JavSP 回退 ----
                        need_fallback = not result_data or not (
                            isinstance(result_data.get('actors'), list) and len(result_data.get('actors')) > 0
                        )
                        if need_fallback:
                            used_source = None
                            # 先尝试 JavBus
                            try:
                                progress_window.update_status("尝试JavBus回退...")
                                if getattr(sys, 'frozen', False):
                                    cmd_bus = [os.path.join(runtime_dir(), "javbus_crawler_single.exe"), av_code]
                                else:
                                    cmd_bus = [sys.executable, "javbus_crawler_single.py", av_code]
                                p_bus = subprocess.run(cmd_bus, capture_output=True, text=True, cwd=cwd_dir, timeout=60)
                                if p_bus.returncode == 0 and p_bus.stdout:
                                    try:
                                        bus_parsed = json.loads(p_bus.stdout)
                                        if bus_parsed and not bus_parsed.get('error'):
                                            result_data = {
                                                'title': bus_parsed.get('title'),
                                                'video_id': bus_parsed.get('number') or av_code,
                                                'detail_url': None,
                                                'release_date': bus_parsed.get('release_date'),
                                                'duration': None,
                                                'rating': None,
                                                'tags': bus_parsed.get('tags') or [],
                                                'actors': normalize_actors_from_names(bus_parsed.get('actors', [])),
                                                'studio': bus_parsed.get('studio'),
                                                'cover_image_url': bus_parsed.get('cover_image_url'),
                                                'local_image_path': bus_parsed.get('cover_image_path'),
                                                'magnet_links': bus_parsed.get('magnet_links', [])
                                            }
                                            used_source = 'javbus'
                                            progress_window.update_status("✓ 已切换到 JavBus 数据")
                                        else:
                                            progress_window.update_status("JavBus无有效数据")
                                    except json.JSONDecodeError:
                                        progress_window.update_status("JavBus解析失败")
                                else:
                                    progress_window.update_status("JavBus爬虫失败")
                            except Exception:
                                progress_window.update_status("JavBus异常")

                            # 若 JavBus 未成功，尝试 JavSP
                            if not used_source:
                                try:
                                    progress_window.update_status("尝试JavSP回退...")
                                    from javsp_integration import search_javdb_info as javsp_search
                                    sp_result = javsp_search(av_code)
                                    if sp_result:
                                        result_data = sp_result
                                        used_source = 'javsp'
                                        progress_window.update_status("✓ 已切换到 JavSP 数据")
                                    else:
                                        progress_window.update_status("JavSP无有效数据")
                                except Exception:
                                    progress_window.update_status("JavSP异常，回退结束")
                        
                        # ---- 最终检查与保存 ----
                        if not result_data or (result_data.get('title') in blocked_titles):
                            error_msg = 'JAVDB爬取失败' if not result_data else '信息被屏蔽'
                            failed_files.append(f"{file_name}: {error_msg}")
                            progress_window.update_progress(i + 1, file_name, success=False)
                            progress_window.update_status(f"失败: {error_msg}", "red")
                            continue
                        
                        progress_window.update_status(f"正在保存到数据库: {av_code}")
                        self.save_javdb_info_to_db(video_id, result_data)
                        self.conn.commit()
                        progress_window.update_progress(i + 1, file_name, success=True)
                        progress_window.update_status(f"成功保存: {av_code}", "green")
                        
                    except subprocess.TimeoutExpired:
                        # ... 超时处理
                        pass
                    except ImportError:
                        # ... 导入错误处理
                        pass
                    except Exception as e:
                        # ... 通用错误处理
                        pass
                    
                    # 延迟避免请求过于频繁
                    import time
                    time.sleep(1)
                
                # 处理完成
                if not progress_window.cancelled:
                    progress_window.update_status("批量处理完成！", "blue")
                    self.root.after(100, self.load_videos)
                    def safe_complete_close():
                        try:
                            if progress_window and hasattr(progress_window, 'cancelled') and not progress_window.cancelled:
                                progress_window.close()
                        except (tk.TclError, AttributeError):
                            pass
                    self.root.after(2000, safe_complete_close)
                else:
                    # 用户取消了操作
                    progress_window.update_status("操作已取消", "orange")
                    # ... 取消处理
                
            except Exception as e:
                print(f"批量处理出错: {e}")
            
            # 打印失败文件统计
            if failed_files:
                print(f"\n失败文件列表 ({len(failed_files)}个):")
                for ff in failed_files:
                    print(f"  - {ff}")
        
        # 在新线程中执行
        import threading
        thread = threading.Thread(target=fetch_javdb_info, daemon=True)
        thread.start()
        
    except Exception as e:
        print(f"批量JAVDB信息处理失败: {e}")
        messagebox.showerror("错误", f"批量JAVDB信息处理失败: {str(e)}")
