# -*- coding: utf-8 -*-
"""
导入视频文件对话框（原生 PySide6，对齐 ui_design 风格）。

替代 v1 的 Tkinter import_videos 窗口。复用桥接来的底层方法：
    - collect_video_files_from_folder  递归收集视频
    - can_play_video                   可播放性校验
    - calculate_md5_hash               MD5 去重
    - add_video_to_db_optimized        入库
    - FileUtils.move_file_smart        复制/移动文件

流程：选源(文件/文件夹) → 选目标文件夹 → 勾选选项 → 开始导入（后台线程 +
进度 + 日志）。导入在 worker 线程执行，UI 保持响应。
"""

import os
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QComboBox, QCheckBox, QProgressBar, QPlainTextEdit,
    QGroupBox, QFileDialog, QMessageBox, QButtonGroup, QRadioButton,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont

from pyside_v2.theme import Tokens


VIDEO_EXTS = ('.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v',
              '.3gp', '.ts', '.mts', '.m2ts')


class ImportVideosDialog(QDialog):
    """导入视频文件对话框。"""

    def __init__(self, main_window, parent=None):
        super().__init__(parent or main_window)
        self.mw = main_window              # MainWindow，用于访问桥接方法
        self.core = main_window.core
        self._import_worker = None
        self._setup_ui()
        self._load_target_folders()

    def _setup_ui(self):
        self.setWindowTitle("导入视频文件")
        self.resize(720, 640)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(Tokens.SP_5, Tokens.SP_5, Tokens.SP_5, Tokens.SP_5)
        lay.setSpacing(Tokens.SP_4)

        # ---- 导入源 ----
        src_box = QGroupBox("导入源")
        src_lay = QVBoxLayout(src_box)
        self.source_list = QListWidget()
        self.source_list.setAlternatingRowColors(True)
        self.source_list.setMinimumHeight(140)
        src_lay.addWidget(self.source_list)

        src_btns = QHBoxLayout()
        btn_add_folder = QPushButton("📁 添加文件夹")
        btn_add_files = QPushButton("📄 添加文件")
        btn_remove = QPushButton("移除选中")
        for b in (btn_add_folder, btn_add_files, btn_remove):
            b.setCursor(Qt.PointingHandCursor)
        btn_add_folder.clicked.connect(self._add_folder)
        btn_add_files.clicked.connect(self._add_files)
        btn_remove.clicked.connect(self._remove_selected)
        src_btns.addWidget(btn_add_folder)
        src_btns.addWidget(btn_add_files)
        src_btns.addWidget(btn_remove)
        src_btns.addStretch()
        src_lay.addLayout(src_btns)
        lay.addWidget(src_box)

        # ---- 目标文件夹 ----
        tgt_box = QGroupBox("目标文件夹")
        tgt_lay = QHBoxLayout(tgt_box)
        self.target_combo = QComboBox()
        self.target_combo.setEditable(False)
        tgt_lay.addWidget(self.target_combo, 1)
        btn_browse = QPushButton("自定义…")
        btn_browse.setCursor(Qt.PointingHandCursor)
        btn_browse.clicked.connect(self._browse_target)
        tgt_lay.addWidget(btn_browse)
        lay.addWidget(tgt_box)

        # ---- 导入选项 ----
        opt_box = QGroupBox("导入选项")
        opt_lay = QVBoxLayout(opt_box)
        self.chk_invalid = QCheckBox("删除无法播放的文件")
        self.chk_invalid.setChecked(True)
        self.chk_duplicate = QCheckBox("删除重复文件（基于 MD5）")
        self.chk_duplicate.setChecked(True)
        self.chk_rename = QCheckBox("自动清理文件名")
        self.chk_rename.setChecked(True)
        # 移动 vs 复制
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("操作方式："))
        self.mode_group = QButtonGroup(self)
        self.rb_copy = QRadioButton("复制（保留源文件）")
        self.rb_move = QRadioButton("移动（删除源文件）")
        self.rb_copy.setChecked(True)
        self.mode_group.addButton(self.rb_copy)
        self.mode_group.addButton(self.rb_move)
        mode_row.addWidget(self.rb_copy)
        mode_row.addWidget(self.rb_move)
        mode_row.addStretch()
        opt_lay.addWidget(self.chk_invalid)
        opt_lay.addWidget(self.chk_duplicate)
        opt_lay.addWidget(self.chk_rename)
        opt_lay.addLayout(mode_row)
        lay.addWidget(opt_box)

        # ---- 操作按钮 ----
        btn_row = QHBoxLayout()
        self.btn_import = QPushButton("开始导入")
        self.btn_import.setProperty("role", "primary")
        self.btn_import.setCursor(Qt.PointingHandCursor)
        self.btn_import.clicked.connect(self._start_import)
        btn_cancel = QPushButton("关闭")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_import)
        btn_row.addWidget(btn_cancel)
        lay.addLayout(btn_row)

        # ---- 进度 + 日志 ----
        prog_box = QGroupBox("导入进度")
        prog_lay = QVBoxLayout(prog_box)
        self.progress = QProgressBar()
        self.progress.setValue(0)
        prog_lay.addWidget(self.progress)

        self.status_label = QLabel("准备就绪")
        self.status_label.setStyleSheet("color: palette(mid);")
        prog_lay.addWidget(self.status_label)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        mono = QFont(Tokens.FONT_MONO.strip('"').split(',')[0])
        mono.setPointSize(10)
        self.log_view.setFont(mono)
        self.log_view.setMinimumHeight(140)
        prog_lay.addWidget(self.log_view)
        lay.addWidget(prog_box, 1)

    # ---- 源管理 ----
    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if folder:
            self.source_list.addItem(f"[文件夹] {folder}")

    def _add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择视频文件", "",
            f"视频文件 (*{' *'.join(VIDEO_EXTS)})"
        )
        for f in files:
            if os.path.exists(f):
                self.source_list.addItem(f"[文件] {f}")

    def _remove_selected(self):
        for item in reversed(self.source_list.selectedItems()):
            self.source_list.takeItem(self.source_list.row(item))

    # ---- 目标文件夹 ----
    def _load_target_folders(self):
        """从 folders 表加载可用目标文件夹。"""
        try:
            self.core.cursor.execute(
                "SELECT DISTINCT folder_path FROM folders WHERE is_active=1 ORDER BY folder_path"
            )
            folders = [r[0] for r in self.core.cursor.fetchall()]
        except Exception:
            folders = []
        self.target_combo.clear()
        self.target_combo.addItems(folders)

    def _browse_target(self):
        folder = QFileDialog.getExistingDirectory(self, "选择目标文件夹")
        if folder:
            if self.target_combo.findData(folder) < 0:
                self.target_combo.addItem(folder)
            self.target_combo.setCurrentText(folder)

    # ---- 日志 ----
    def _log(self, msg, level="info"):
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S")
        color = {"info": "", "success": "#1a7f37", "warning": "#9a6700",
                 "error": "#cf222e"}.get(level, "")
        prefix = f'<span style="color:{color}">' if color else '<span>'
        self.log_view.appendHtml(f'{prefix}[{ts}] {msg}</span>')

    # ---- 开始导入 ----
    def _start_import(self):
        target = self.target_combo.currentText().strip()
        if not target:
            QMessageBox.warning(self, "提示", "请选择目标文件夹")
            return
        if self.source_list.count() == 0:
            QMessageBox.warning(self, "提示", "请添加要导入的文件或文件夹")
            return

        # 收集源
        sources = []
        for i in range(self.source_list.count()):
            sources.append(self.source_list.item(i).text())

        options = {
            'delete_invalid': self.chk_invalid.isChecked(),
            'delete_duplicate': self.chk_duplicate.isChecked(),
            'rename': self.chk_rename.isChecked(),
            'move': self.rb_move.isChecked(),
        }

        self.btn_import.setEnabled(False)
        self.progress.setValue(0)
        self._log(f"开始导入到 {target}（{'移动' if options['move'] else '复制'}）")

        self._import_worker = ImportWorker(self.core, self.mw, sources, target, options)
        self._import_worker.progress_signal.connect(self._on_progress)
        self._import_worker.log_signal.connect(self._log)
        self._import_worker.finished_signal.connect(self._on_finished)
        self._import_worker.start()

    def _on_progress(self, value, status):
        self.progress.setValue(value)
        self.status_label.setText(status)

    def _on_finished(self, summary):
        self.btn_import.setEnabled(True)
        self.progress.setValue(100)
        self.status_label.setText(summary)
        self._log(summary, "success")
        # 通知主窗口刷新列表
        if hasattr(self.mw, 'load_videos'):
            self.mw.load_videos()


class ImportWorker(QThread):
    """导入工作线程 —— 严格对齐 v1 start_import_process 的三阶段流程。

    第一阶段（0-50%）：收集 + 预处理（可播放校验 + MD5 + 记录元数据）
    第二阶段：去重（按 md5+size 分组；库内已存在整组跳过；多文件择优保留）
    第三阶段（50-100%）：处理有效文件（清理文件名 + 冲突解决 + 复制/移动 + 入库）

    关键对齐点：
    - 删除用 send2trash（回收站），失败才回退 os.remove
    - check_duplicate_by_hash(md5, size) 双重判定
    - process_filename + resolve_filename_conflict
    - folder_type 从 folders 表查（区分 local/nas）
    """

    progress_signal = Signal(int, str)   # value%, status
    log_signal = Signal(str, str)        # message, level
    finished_signal = Signal(str)        # summary

    def __init__(self, core, mw, sources, target, options):
        super().__init__()
        self.core = core
        self.mw = mw          # 访问桥接方法
        self.sources = sources
        self.target = target
        self.options = options
        self._cancelled = False

    def log(self, msg, level="info"):
        self.log_signal.emit(msg, level)

    def cancel(self):
        self._cancelled = True

    def _trash(self, file_path):
        """删除文件：优先回收站，失败回退直接删除。返回是否成功。"""
        try:
            from send2trash import send2trash
            send2trash(file_path)
            return True, "回收站"
        except Exception as e1:
            try:
                os.remove(file_path)
                return True, "直接删除"
            except Exception as e2:
                return False, f"{e1}; {e2}"

    def run(self):
        try:
            # ============================================================
            # 第一阶段：收集 + 预处理（0-50%）
            # ============================================================
            all_files = []
            self.log("收集视频文件…")
            for src in self.sources:
                if self._cancelled:
                    return
                if src.startswith("[文件夹] "):
                    folder = src[len("[文件夹] "):].strip()
                    try:
                        files = self.mw.collect_video_files_from_folder(folder)
                        all_files.extend(files)
                        self.log(f"文件夹 {os.path.basename(folder)}: {len(files)} 个视频", "success")
                    except Exception as e:
                        self.log(f"收集文件夹失败 {folder}: {e}", "error")
                elif src.startswith("[文件] "):
                    fp = src[len("[文件] "):].strip()
                    if os.path.exists(fp):
                        all_files.append(fp)

            if not all_files:
                self.finished_signal.emit("未找到视频文件")
                return

            total = len(all_files)
            self.log(f"共 {total} 个视频文件，开始预处理", "success")

            # file_info_map: {path: {hash, size, created_time, stars, valid}}
            file_info_map = {}
            from datetime import datetime as _dt

            for i, file_path in enumerate(all_files):
                if self._cancelled:
                    return
                fname = os.path.basename(file_path)
                progress = int((i / total) * 50)
                self.progress_signal.emit(progress, f"预处理 {i+1}/{total}: {fname}")

                try:
                    # 可播放性校验
                    if not self.mw.can_play_video(file_path):
                        self.log(f"无法播放，标记无效: {fname}", "warning")
                        file_info_map[file_path] = {'valid': False}
                        continue

                    # MD5
                    md5_hash = self.core.calculate_md5_hash(file_path)
                    if not md5_hash:
                        self.log(f"MD5 计算失败，标记无效: {fname}", "warning")
                        file_info_map[file_path] = {'valid': False}
                        continue

                    file_stat = os.stat(file_path)
                    file_info_map[file_path] = {
                        'hash': md5_hash,
                        'size': file_stat.st_size,
                        'created_time': _dt.fromtimestamp(file_stat.st_ctime),
                        'stars': self.core.parse_stars_from_filename(fname),
                        'valid': True,
                    }
                except Exception as e:
                    self.log(f"预处理失败 {fname}: {e}", "error")
                    file_info_map[file_path] = {'valid': False}

            # ============================================================
            # 第二阶段：去重处理
            # ============================================================
            self.log("去重处理…")
            hash_size_groups = {}
            for file_path, info in file_info_map.items():
                if info.get('valid') and info.get('hash'):
                    key = f"{info['hash']}_{info['size']}"
                    hash_size_groups.setdefault(key, []).append(file_path)

            files_to_process = []   # 最终要导入的文件
            files_to_delete = []    # 待删除的重复文件

            for key, file_paths in hash_size_groups.items():
                md5_hash, file_size_str = key.rsplit('_', 1)
                file_size = int(file_size_str)

                # 库内已存在 → 整组跳过
                if self.mw.check_duplicate_by_hash(md5_hash, file_size):
                    self.log(f"库内已存在 MD5 {md5_hash[:8]}… ({file_size//1024//1024}MB)，跳过 {len(file_paths)} 个", "warning")
                    if self.options['delete_duplicate']:
                        files_to_delete.extend(file_paths)
                    continue

                if len(file_paths) == 1:
                    files_to_process.append(file_paths[0])
                else:
                    # 多文件重复：择优（星级降序 + 创建时间升序）
                    self.log(f"发现 {len(file_paths)} 个重复 (MD5 {md5_hash[:8]}…)", "warning")
                    def sort_key(p):
                        info = file_info_map[p]
                        return (-info['stars'], info['created_time'])
                    sorted_paths = sorted(file_paths, key=sort_key)
                    keep = sorted_paths[0]
                    files_to_process.append(keep)
                    self.log(f"保留: {os.path.basename(keep)}（星{file_info_map[keep]['stars']}）", "info")
                    dups = sorted_paths[1:]
                    if self.options['delete_duplicate']:
                        files_to_delete.extend(dups)
                        for d in dups:
                            self.log(f"标记重复: {os.path.basename(d)}", "warning")

            # 删除无效文件
            invalid_count = 0
            if self.options['delete_invalid']:
                for file_path, info in file_info_map.items():
                    if self._cancelled:
                        break
                    if not info.get('valid'):
                        ok, _ = self._trash(file_path)
                        if ok:
                            invalid_count += 1
                            self.log(f"删除无效: {os.path.basename(file_path)}", "info")
                        else:
                            self.log(f"删除无效失败: {os.path.basename(file_path)}", "error")

            # 删除重复文件
            duplicate_count = 0
            for file_path in files_to_delete:
                if self._cancelled:
                    break
                ok, _ = self._trash(file_path)
                if ok:
                    duplicate_count += 1
                    self.log(f"删除重复: {os.path.basename(file_path)}", "info")
                else:
                    self.log(f"删除重复失败: {os.path.basename(file_path)}", "error")

            # ============================================================
            # 第三阶段：处理有效文件（50-100%）
            # ============================================================
            self.log(f"处理 {len(files_to_process)} 个有效文件…", "success")
            from utils.file_utils import FileUtils

            success_count = 0
            failed_count = 0
            n_proc = len(files_to_process)

            for i, file_path in enumerate(files_to_process):
                if self._cancelled:
                    break
                fname = os.path.basename(file_path)
                progress = 50 + int((i / max(n_proc, 1)) * 50)
                self.progress_signal.emit(progress, f"导入 {i+1}/{n_proc}: {fname}")

                try:
                    # 清理文件名
                    if self.options['rename']:
                        try:
                            new_filename = self.mw.process_filename(fname)
                        except Exception:
                            new_filename = fname
                    else:
                        new_filename = fname

                    target_path = os.path.join(self.target, new_filename)

                    # 冲突解决
                    try:
                        target_path = self.mw.resolve_filename_conflict(target_path)
                    except Exception:
                        base, ext = os.path.splitext(target_path)
                        n = 1
                        while os.path.exists(target_path):
                            target_path = f"{base}_{n}{ext}"
                            n += 1

                    # 复制 / 移动
                    if os.path.abspath(file_path) == os.path.abspath(target_path):
                        pass  # 同路径
                    else:
                        if self.options['move']:
                            ok, final, err = FileUtils.move_file_smart(file_path, target_path)
                        else:
                            ok, final, err = FileUtils.copy_file_smart(file_path, target_path)
                        if not ok:
                            self.log(f"文件操作失败 {fname}: {err}", "error")
                            failed_count += 1
                            continue
                        target_path = final

                    # folder_type：从 folders 表查目标文件夹类型
                    folder_type = "local"
                    try:
                        cur = self.core.conn.cursor()
                        cur.execute("SELECT folder_type FROM folders WHERE folder_path = ?", (self.target,))
                        r = cur.fetchone()
                        if r:
                            folder_type = r[0]
                        cur.close()
                    except Exception:
                        pass

                    # 入库
                    try:
                        self.mw.add_video_to_db_optimized(target_path, folder_type)
                        success_count += 1
                        self.log(f"成功导入: {os.path.basename(target_path)}", "success")
                    except Exception as e:
                        self.log(f"入库失败 {fname}: {e}", "error")
                        failed_count += 1

                except Exception as e:
                    self.log(f"处理失败 {fname}: {e}", "error")
                    failed_count += 1

            self.core.conn.commit()

            # 收尾
            self.progress_signal.emit(100, "导入完成")
            summary = (f"完成：成功 {success_count}，失败 {failed_count}，"
                       f"删除重复 {duplicate_count}，删除无效 {invalid_count}（共 {total}）")
            self.finished_signal.emit(summary)

        except Exception as e:
            self.log(f"导入出错: {e}", "error")
            self.finished_signal.emit(f"导入出错: {e}")
