#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JAVDB系统 - 单视频信息获取
从 media_library.py 第 9001-9222 行提取

函数说明:
  - fetch_current_javdb_info(): 获取当前选中视频的JAVDB信息（按钮入口）
  - fetch_javdb_info(video_id): 核心单视频获取逻辑
  - _crawler_needs_manual_action(): 检测是否需要人工干预

三级回退策略:
  1. JavDB (javdb_crawler_single.py) - 主爬虫
  2. JavBus (javbus_crawler_single.py) - 备用1
  3. JavSP (javsp_integration.py) - 备用2

字段映射 (爬虫JSON → 数据库):
  title         → javdb_info.javdb_title
  video_id      → javdb_info.javdb_code (番号)
  detail_url    → javdb_info.javdb_url
  release_date  → javdb_info.release_date
  duration      → javdb_info.duration
  rating/score  → javdb_info.score (转为float)
  studio        → javdb_info.studio
  cover_image_url → javdb_info.cover_url
  local_image_path → javdb_info.local_cover_path
  magnet_links  → javdb_info.magnet_links (JSON序列化)
  tags (list)   → javdb_tags + javdb_info_tags 关联表
  actors (list) → actors + video_actors 关联表
"""

def fetch_current_javdb_info(self):
    """获取当前选中视频的JAVDB信息（详情面板按钮/单视频入口）"""
    if not self.current_video:
        messagebox.showwarning("警告", "请先选择一个视频")
        return
    
    video_id = self.current_video[0]  # 视频ID是第一个字段
    self.fetch_javdb_info(video_id)
    
    # 获取完成后刷新详情显示
    self.root.after(2000, lambda: self.load_javdb_details(video_id))


def _crawler_needs_manual_action(self, stderr_text):
    """检测爬虫是否需要人工干预（如登录/Cloudflare验证）"""
    if not stderr_text:
        return False
    text = str(stderr_text).lower()
    markers = [
        "cloudflare", "验证页", "just a moment",
        "checking your browser", "登录状态缺失",
        "访问详情页需要登录", "登录仍未成功", "login"
    ]
    return any(marker in text for marker in markers)


def fetch_javdb_info(self, video_id):
    """
    获取单个视频的JAVDB信息（核心方法）
    
    Args:
        video_id: 数据库中视频记录的ID
    
    流程:
        1. 从数据库获取视频文件名 → 提取番号
        2. 优先调用 javdb_crawler_single.py 获取
        3. 若失败/演员为空 → 回退到 JavBus
        4. 若仍失败 → 回退到 JavSP
        5. 保存结果到数据库
    """
    try:
        # 获取视频文件信息
        self.cursor.execute("SELECT file_path, file_name FROM videos WHERE id = ?", (video_id,))
        result = self.cursor.fetchone()
        if not result:
            messagebox.showerror("错误", "未找到视频记录")
            return

        file_path, file_name = result

        # 导入番号提取器
        from code_extractor import CodeExtractor

        # 提取番号
        extractor = CodeExtractor()
        av_code = extractor.extract_code_from_filename(file_name)

        if not av_code:
            messagebox.showwarning("警告", f"无法从文件名 '{file_name}' 中提取番号")
            return

        # 确认对话框
        if not messagebox.askyesno("确认", f"检测到番号: {av_code}\n\n是否获取JAVDB信息？"):
            return

        # 创建进度窗口
        progress_window = tk.Toplevel(self.root)
        progress_window.title("JAVDB信息获取")
        progress_window.geometry("420x220")
        progress_window.transient(self.root)
        progress_window.grab_set()

        progress_label = ttk.Label(progress_window, text=f"正在获取 {av_code} 的信息...")
        progress_label.pack(pady=20)

        progress_bar = ttk.Progressbar(progress_window, length=320, mode='indeterminate')
        progress_bar.pack(pady=10)
        progress_bar.start()

        status_label = ttk.Label(progress_window, text="初始化...")
        status_label.pack(pady=10)

        def fetch_thread():
            try:
                import subprocess
                import json
                cwd_dir = runtime_dir()

                # ---- 一级：JavDB 优先 ----
                self.root.after(0, lambda: status_label.config(text="使用JavDB爬虫获取..."))
                result_data = None
                try:
                    if getattr(sys, 'frozen', False):
                        cmd = [os.path.join(runtime_dir(), "javdb_crawler_single.exe"), av_code]
                    else:
                        cmd = [sys.executable, "javdb_crawler_single.py", av_code]
                    process = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd_dir, timeout=180)
                    if process.returncode == 0 and process.stdout:
                        try:
                            parsed = json.loads(process.stdout)
                            blocked_titles = ['官方App下載', '官方App下载', 'Official App Download']
                            if parsed and not parsed.get('error') and parsed.get('title') and parsed.get('title') not in blocked_titles:
                                result_data = parsed
                                has_actors = isinstance(parsed.get('actors'), list) and len(parsed.get('actors')) > 0
                                self.root.after(0, lambda: status_label.config(
                                    text="✓ JavDB成功" if has_actors else "JavDB成功（演员缺失，尝试回退）"
                                ))
                            else:
                                self.root.after(0, lambda: status_label.config(text="JavDB信息不完整，尝试回退"))
                        except json.JSONDecodeError:
                            self.root.after(0, lambda: status_label.config(text="JavDB解析失败，尝试回退"))
                    else:
                        self.root.after(0, lambda: status_label.config(text="JavDB爬虫失败，尝试回退"))
                except Exception as e:
                    err_msg = f"JavDB异常: {e}，尝试回退"
                    self.root.after(0, lambda msg=err_msg: status_label.config(text=msg))

                # ---- 二级：JavBus/JavSP 回退 ----
                def normalize_actors(maybe_list):
                    normalized = []
                    if isinstance(maybe_list, list):
                        for item in maybe_list:
                            if isinstance(item, dict):
                                name = (item.get('name') or '').strip()
                                link = item.get('link') or ''
                                if name:
                                    normalized.append({'name': name, 'link': link})
                            elif isinstance(item, str):
                                name = item.strip()
                                if name:
                                    normalized.append({'name': name, 'link': ''})
                    return normalized

                need_fallback = not result_data or not (
                    isinstance(result_data.get('actors'), list) and len(result_data.get('actors')) > 0
                )
                if need_fallback:
                    used_source = None
                    # 尝试 JavBus
                    try:
                        self.root.after(0, lambda: status_label.config(text="尝试JavBus回退..."))
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
                                        'actors': normalize_actors(bus_parsed.get('actors', [])),
                                        'studio': bus_parsed.get('studio'),
                                        'cover_image_url': bus_parsed.get('cover_image_url'),
                                        'local_image_path': bus_parsed.get('cover_image_path'),
                                        'magnet_links': bus_parsed.get('magnet_links', [])
                                    }
                                    used_source = 'javbus'
                                    self.root.after(0, lambda: status_label.config(text="✓ 已切换到 JavBus 数据"))
                                else:
                                    self.root.after(0, lambda: status_label.config(text="JavBus无有效数据"))
                            except json.JSONDecodeError:
                                self.root.after(0, lambda: status_label.config(text="JavBus解析失败"))
                        else:
                            self.root.after(0, lambda: status_label.config(text="JavBus爬虫失败"))
                    except Exception:
                        self.root.after(0, lambda: status_label.config(text="JavBus异常"))

                    # 尝试 JavSP
                    if not used_source:
                        try:
                            self.root.after(0, lambda: status_label.config(text="尝试JavSP回退..."))
                            from javsp_integration import search_javdb_info as javsp_search
                            sp_result = javsp_search(av_code)
                            if sp_result:
                                result_data = sp_result
                                used_source = 'javsp'
                                self.root.after(0, lambda: status_label.config(text="✓ 已切换到 JavSP 数据"))
                            else:
                                self.root.after(0, lambda: status_label.config(text="JavSP无有效数据"))
                        except Exception:
                            self.root.after(0, lambda: status_label.config(text="JavSP异常，回退结束"))

                # ---- 结果处理 ----
                if result_data:
                    self.root.after(0, lambda: status_label.config(text="正在保存到数据库..."))
                    try:
                        self.save_javdb_info_to_db(video_id, result_data)
                        self.root.after(0, lambda: status_label.config(text="获取完成"))
                        time.sleep(0.6)
                        self.root.after(0, lambda: progress_window.grab_release())
                        self.root.after(10, progress_window.destroy)
                        self.root.after(200, self.load_videos)
                        self.root.after(300, lambda: self.load_javdb_details(video_id))
                    except Exception as e:
                        err_msg = f"保存到数据库失败: {e}"
                        self.root.after(0, lambda: progress_window.grab_release())
                        self.root.after(10, progress_window.destroy)
                        self.root.after(100, lambda msg=err_msg: messagebox.showerror("错误", msg))
                else:
                    self.root.after(0, lambda: progress_window.grab_release())
                    self.root.after(10, progress_window.destroy)
                    self.root.after(100, lambda: messagebox.showwarning(
                        "警告",
                        f"未能获取到番号 {av_code} 的信息\n\n可能原因：\n1. 网络连接问题\n2. 站点没有该番号\n3. 需要登录验证或被屏蔽"
                    ))
            except Exception as e:
                err_msg = f"获取JAVDB信息失败: {e}"
                self.root.after(0, lambda: progress_window.grab_release())
                self.root.after(10, progress_window.destroy)
                self.root.after(100, lambda msg=err_msg: messagebox.showerror("错误", msg))

        # 后台线程执行
        thread = threading.Thread(target=fetch_thread, daemon=True)
        thread.start()

    except ImportError:
        messagebox.showerror("错误", "无法导入番号提取器模块")
    except Exception as e:
        messagebox.showerror("错误", f"获取JAVDB信息失败: {str(e)}")
