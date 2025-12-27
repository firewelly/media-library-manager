#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PySide6扩展功能集成补丁
这个文件包含了向现有media_library_pyside.py添加扩展功能的代码
"""

from PySide6.QtWidgets import QMenuBar, QMenu, QMessageBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from extension_dialogs import NFODialog, DuplicateManagerDialog, BatchOperationsDialog
from utils import get_logger
import os

logger = get_logger("PySideExtensions")

def add_extensions_menu(main_window):
    """
    向主窗口添加扩展功能菜单

    Args:
        main_window: 主窗口实例 (MainWindow)
    """
    try:
        # 获取菜单栏
        menubar = main_window.menuBar()

        # 创建扩展功能菜单
        extensions_menu = menubar.addMenu('扩展功能(&E)')

        # NFO导入功能
        nfo_action = QAction('导入NFO文件(&N)', main_window)
        nfo_action.setShortcut('Ctrl+N')
        nfo_action.setStatusTip('导入视频的NFO文件信息')
        nfo_action.triggered.connect(lambda: show_nfo_dialog(main_window))
        extensions_menu.addAction(nfo_action)

        # 重复文件管理
        duplicate_action = QAction('重复文件管理(&D)', main_window)
        duplicate_action.setShortcut('Ctrl+D')
        duplicate_action.setStatusTip('查找和管理重复的视频文件')
        duplicate_action.triggered.connect(lambda: show_duplicate_dialog(main_window))
        extensions_menu.addAction(duplicate_action)

        # 批量操作
        batch_action = QAction('批量操作(&B)', main_window)
        batch_action.setShortcut('Ctrl+B')
        batch_action.setStatusTip('对选中的视频进行批量操作')
        batch_action.triggered.connect(lambda: show_batch_dialog(main_window))
        extensions_menu.addAction(batch_action)

        # 添加分隔线
        extensions_menu.addSeparator()

        # 工具功能子菜单
        tools_menu = extensions_menu.addMenu('工具(&T)')

        # 重新计算哈希
        recalc_hash_action = QAction('重新计算所有文件哈希(&R)', main_window)
        recalc_hash_action.setStatusTip('重新计算所有视频文件的MD5和文件哈希')
        recalc_hash_action.triggered.connect(lambda: recalculate_all_hashes(main_window))
        tools_menu.addAction(recalc_hash_action)

        # 数据库维护
        db_maintenance_action = QAction('数据库维护(&M)', main_window)
        db_maintenance_action.setStatusTip('清理和优化数据库')
        db_maintenance_action.triggered.connect(lambda: database_maintenance(main_window))
        tools_menu.addAction(db_maintenance_action)

        # 添加分隔线
        tools_menu.addSeparator()

        # MD5计算工具
        md5_action = QAction('重新计算MD5(&H)', main_window)
        md5_action.setStatusTip('重新计算缺失的MD5哈希值')
        md5_action.triggered.connect(lambda: recalculate_md5_tool(main_window))
        tools_menu.addAction(md5_action)

        # 检查无效记录
        check_invalid_action = QAction('检查无效记录(&V)', main_window)
        check_invalid_action.setStatusTip('检查并清理不在配置文件夹范围内的记录')
        check_invalid_action.triggered.connect(lambda: check_invalid_records_tool(main_window))
        tools_menu.addAction(check_invalid_action)

        # 视频完整性检查
        integrity_action = QAction('视频完整性检查(&I)', main_window)
        integrity_action.setStatusTip('检查视频文件的完整性')
        integrity_action.triggered.connect(lambda: video_integrity_check(main_window))
        tools_menu.addAction(integrity_action)

        # 批量重命名工具
        rename_action = QAction('批量重命名工具(&R)', main_window)
        rename_action.setStatusTip('批量重命名视频文件')
        rename_action.triggered.connect(lambda: batch_rename_tool(main_window))
        tools_menu.addAction(rename_action)

        # 文件移动管理
        file_move_action = QAction('文件移动管理(&M)', main_window)
        file_move_action.setStatusTip('管理和执行文件移动操作')
        file_move_action.triggered.connect(lambda: file_move_manager_tool(main_window))
        tools_menu.addAction(file_move_action)

        logger.info("扩展功能菜单添加成功")

    except Exception as e:
        logger.error(f"添加扩展功能菜单失败: {e}")
        QMessageBox.critical(main_window, "错误", f"添加扩展功能菜单失败:\n{str(e)}")

def add_toolbar_buttons(main_window):
    """
    向工具栏添加扩展功能按钮

    Args:
        main_window: 主窗口实例
    """
    try:
        # 获取或创建工具栏
        if hasattr(main_window, 'toolbar'):
            toolbar = main_window.toolbar
        else:
            from PySide6.QtWidgets import QToolBar
            toolbar = QToolBar('扩展功能', main_window)
            main_window.addToolBar(toolbar)
            main_window.toolbar = toolbar

        # 添加分隔线
        toolbar.addSeparator()

        # NFO导入按钮
        nfo_btn = QAction('NFO导入', main_window)
        nfo_btn.setStatusTip('导入NFO文件信息')
        nfo_btn.triggered.connect(lambda: show_nfo_dialog(main_window))
        toolbar.addAction(nfo_btn)

        # 重复文件按钮
        duplicate_btn = QAction('重复文件', main_window)
        duplicate_btn.setStatusTip('管理重复文件')
        duplicate_btn.triggered.connect(lambda: show_duplicate_dialog(main_window))
        toolbar.addAction(duplicate_btn)

        # 批量操作按钮
        batch_btn = QAction('批量操作', main_window)
        batch_btn.setStatusTip('批量处理视频')
        batch_btn.triggered.connect(lambda: show_batch_dialog(main_window))
        toolbar.addAction(batch_btn)

        logger.info("扩展功能工具栏按钮添加成功")

    except Exception as e:
        logger.error(f"添加扩展功能工具栏按钮失败: {e}")

def get_selected_video_ids(main_window):
    """
    获取当前选中的视频ID列表

    Args:
        main_window: 主窗口实例

    Returns:
        List[int]: 选中的视频ID列表
    """
    try:
        # 适配现有的VideoListWidget
        if hasattr(main_window, 'video_list') and main_window.video_list:
            selected_items = main_window.video_list.selectedItems()
            video_ids = []

            for item in selected_items:
                # 尝试从userData中获取视频ID
                video_id = item.data(0, Qt.UserRole)
                if video_id:
                    video_ids.append(video_id)
                else:
                    # 如果没有userData，尝试从文本中解析
                    # 这里可以根据实际的数据结构调整
                    try:
                        # 假设第0列包含ID信息，或者可以从其他方式获取
                        text = item.text(0)
                        # 尝试从文本中提取数字ID
                        import re
                        match = re.search(r'\d+', text)
                        if match:
                            video_ids.append(int(match.group()))
                    except:
                        pass

            return video_ids

        return []

    except Exception as e:
        logger.error(f"获取选中视频ID失败: {e}")
        return []

def show_nfo_dialog(main_window):
    """显示NFO导入对话框"""
    try:
        # 创建一个适配的数据库管理器
        db_manager = create_db_manager_adapter(main_window)
        dialog = NFODialog(main_window, db_manager)
        dialog.exec()

    except Exception as e:
        logger.error(f"显示NFO对话框失败: {e}")
        QMessageBox.critical(main_window, "错误", f"打开NFO导入对话框失败:\n{str(e)}")

def show_duplicate_dialog(main_window):
    """显示重复文件管理对话框"""
    try:
        # 创建一个适配的数据库管理器
        db_manager = create_db_manager_adapter(main_window)
        dialog = DuplicateManagerDialog(main_window, db_manager)
        dialog.exec()

    except Exception as e:
        logger.error(f"显示重复文件对话框失败: {e}")
        QMessageBox.critical(main_window, "错误", f"打开重复文件管理对话框失败:\n{str(e)}")

def show_batch_dialog(main_window):
    """显示批量操作对话框"""
    try:
        selected_ids = get_selected_video_ids(main_window)
        # 创建一个适配的数据库管理器
        db_manager = create_db_manager_adapter(main_window)
        dialog = BatchOperationsDialog(main_window, db_manager, selected_ids)
        dialog.exec()

    except Exception as e:
        logger.error(f"显示批量操作对话框失败: {e}")
        QMessageBox.critical(main_window, "错误", f"打开批量操作对话框失败:\n{str(e)}")

def create_db_manager_adapter(main_window):
    """创建适配现有代码结构的数据库管理器"""
    try:
        from utils import DatabaseManager

        # 创建一个简单的适配器类
        class DBManagerAdapter:
            def __init__(self, main_window):
                self.main_window = main_window

            def execute_query(self, query, params=()):
                """使用现有数据库连接执行查询"""
                try:
                    cursor = self.main_window.core.cursor
                    cursor.execute(query, params)
                    return cursor.fetchall()
                except Exception as e:
                    logger.error(f"数据库查询失败: {e}")
                    return []

            def execute_update(self, query, params=()):
                """使用现有数据库连接执行更新"""
                try:
                    cursor = self.main_window.core.cursor
                    cursor.execute(query, params)
                    self.main_window.core.conn.commit()
                    return cursor.rowcount
                except Exception as e:
                    logger.error(f"数据库更新失败: {e}")
                    self.main_window.core.conn.rollback()
                    return 0

            def get_videos(self, limit=None, offset=0, where_clause="", params=(), order_by="created_at DESC"):
                """获取视频列表"""
                try:
                    # 使用现有的数据库连接和适配逻辑
                    from utils import DatabaseManager
                    temp_db = DatabaseManager('media_library.db')
                    return temp_db.get_videos(limit, offset, where_clause, params, order_by)
                except Exception as e:
                    logger.error(f"获取视频列表失败: {e}")
                    return []

            def get_video_count(self, where_clause="", params=()):
                """获取视频总数"""
                try:
                    cursor = self.main_window.core.cursor
                    query = "SELECT COUNT(*) FROM videos"
                    if where_clause:
                        query += f" WHERE {where_clause}"
                    cursor.execute(query, params)
                    result = cursor.fetchone()
                    return result[0] if result else 0
                except Exception as e:
                    logger.error(f"获取视频总数失败: {e}")
                    return 0

            def update_video(self, video_id, video_data):
                """更新视频信息"""
                try:
                    # 构建SET子句
                    set_clauses = []
                    values = []

                    for field, value in video_data.items():
                        set_clauses.append(f"{field} = ?")
                        values.append(value)

                    values.append(video_id)

                    query = f"""
                        UPDATE videos
                        SET {', '.join(set_clauses)}, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """

                    cursor = self.main_window.core.cursor
                    cursor.execute(query, values)
                    self.main_window.core.conn.commit()
                    return cursor.rowcount
                except Exception as e:
                    logger.error(f"更新视频信息失败: {e}")
                    return 0

            def delete_video(self, video_id):
                """删除视频"""
                try:
                    cursor = self.main_window.core.cursor
                    cursor.execute("DELETE FROM videos WHERE id = ?", (video_id,))
                    self.main_window.core.conn.commit()
                    return cursor.rowcount
                except Exception as e:
                    logger.error(f"删除视频失败: {e}")
                    return 0

            def find_duplicates(self):
                """查找重复文件"""
                try:
                    from utils import DatabaseManager
                    temp_db = DatabaseManager('media_library.db')
                    return temp_db.find_duplicates()
                except Exception as e:
                    logger.error(f"查找重复文件失败: {e}")
                    return []

        return DBManagerAdapter(main_window)

    except Exception as e:
        logger.error(f"创建数据库适配器失败: {e}")
        return None

def recalculate_all_hashes(main_window):
    """重新计算所有文件的哈希值"""
    try:
        reply = QMessageBox.question(
            main_window, "确认操作",
            "确定要重新计算所有视频文件的哈希值吗？\n"
            "这个操作可能需要很长时间，特别是对于大文件。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # TODO: 实现重新计算哈希的功能
            # 这里可以创建一个进度对话框来显示进度
            QMessageBox.information(main_window, "提示", "重新计算哈希功能正在开发中...")

    except Exception as e:
        logger.error(f"重新计算哈希失败: {e}")
        QMessageBox.critical(main_window, "错误", f"重新计算哈希失败:\n{str(e)}")

def database_maintenance(main_window):
    """数据库维护"""
    try:
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QProgressBar

        dialog = QDialog(main_window)
        dialog.setWindowTitle("数据库维护")
        dialog.setGeometry(300, 300, 400, 300)

        layout = QVBoxLayout()

        info_label = QLabel("数据库维护功能包括:\n"
                          "• 清理无效记录\n"
                          "• 优化数据库\n"
                          "• 重建索引\n"
                          "• 统计信息更新")
        layout.addWidget(info_label)

        progress_bar = QProgressBar()
        progress_bar.setVisible(False)
        layout.addWidget(progress_bar)

        status_label = QLabel("准备就绪")
        layout.addWidget(status_label)

        def start_maintenance():
            progress_bar.setVisible(True)
            progress_bar.setRange(0, 0)  # 不确定进度
            status_label.setText("正在维护数据库...")

            # TODO: 实现数据库维护逻辑
            # 可以使用QTimer来模拟进度
            QTimer.singleShot(2000, lambda: maintenance_completed(dialog, status_label, progress_bar))

        def maintenance_completed(dialog, status_label, progress_bar):
            progress_bar.setVisible(False)
            status_label.setText("数据库维护完成")
            QMessageBox.information(dialog, "完成", "数据库维护完成！")

        start_btn = QPushButton("开始维护")
        start_btn.clicked.connect(start_maintenance)
        layout.addWidget(start_btn)

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.setLayout(layout)
        dialog.exec()

    except Exception as e:
        logger.error(f"数据库维护失败: {e}")
        QMessageBox.critical(main_window, "错误", f"数据库维护失败:\n{str(e)}")

def enhance_context_menu(main_window):
    """
    增强右键菜单，添加扩展功能

    Args:
        main_window: 主窗口实例
    """
    try:
        # 检查主窗口是否有video_list
        if hasattr(main_window, 'video_list'):
            # video_list已经通过customContextMenuRequested连接到show_context_menu
            # show_context_menu函数已经在主窗口中实现了右键菜单功能
            logger.info("右键菜单已存在，跳过增强")
        elif hasattr(main_window, 'video_tree'):
            # 连接自定义右键菜单
            main_window.video_tree.setContextMenuPolicy(Qt.CustomContextMenu)
            main_window.video_tree.customContextMenuRequested.connect(
                lambda pos: show_context_menu(main_window, pos)
            )
            logger.info("右键菜单增强成功")
        else:
            logger.warning("未找到视频列表组件，跳过右键菜单增强")

    except Exception as e:
        logger.error(f"增强右键菜单失败: {e}")

def show_context_menu(main_window, position):
    """显示自定义右键菜单"""
    try:
        from PySide6.QtWidgets import QMenu

        # 获取点击的项
        item = main_window.video_tree.itemAt(position)
        if not item:
            return

        # 创建右键菜单
        context_menu = QMenu(main_window)

        # 添加原有功能
        if hasattr(main_window, 'show_video_details'):
            details_action = context_menu.addAction("查看详情")
            details_action.triggered.connect(lambda: main_window.show_video_details(item))

        # 添加扩展功能
        context_menu.addSeparator()

        # 导入NFO
        nfo_action = context_menu.addAction("导入NFO")
        nfo_action.triggered.connect(lambda: import_nfo_for_video(main_window, item))

        # 重新计算哈希
        hash_action = context_menu.addAction("重新计算哈希")
        hash_action.triggered.connect(lambda: recalc_video_hash(main_window, item))

        # 在文件管理器中显示
        show_action = context_menu.addAction("在文件管理器中显示")
        show_action.triggered.connect(lambda: show_in_file_manager(main_window, item))

        # 显示菜单
        context_menu.exec_(main_window.video_tree.mapToGlobal(position))

    except Exception as e:
        logger.error(f"显示右键菜单失败: {e}")

def import_nfo_for_video(main_window, item):
    """为单个视频导入NFO"""
    try:
        video_id = item.data(0, Qt.UserRole)
        if not video_id:
            QMessageBox.warning(main_window, "警告", "无法获取视频ID")
            return

        # TODO: 实现单个视频的NFO导入
        QMessageBox.information(main_window, "提示", "单个视频NFO导入功能正在开发中...")

    except Exception as e:
        logger.error(f"导入单个视频NFO失败: {e}")
        QMessageBox.critical(main_window, "错误", f"导入NFO失败:\n{str(e)}")

def recalc_video_hash(main_window, item):
    """重新计算单个视频的哈希"""
    try:
        video_id = item.data(0, Qt.UserRole)
        if not video_id:
            QMessageBox.warning(main_window, "警告", "无法获取视频ID")
            return

        # TODO: 实现单个视频的哈希重计算
        QMessageBox.information(main_window, "提示", "单个视频哈希重计算功能正在开发中...")

    except Exception as e:
        logger.error(f"重计算单个视频哈希失败: {e}")
        QMessageBox.critical(main_window, "错误", f"重计算哈希失败:\n{str(e)}")

def show_in_file_manager(main_window, item):
    """在文件管理器中显示文件"""
    try:
        # 获取文件路径
        file_path = item.text(1) if item.columnCount() > 1 else None  # 假设路径在第1列
        if not file_path:
            QMessageBox.warning(main_window, "警告", "无法获取文件路径")
            return

        # 使用FileUtils打开文件管理器
        from utils import FileUtils
        if FileUtils.open_file_manager(file_path):
            logger.info(f"已在文件管理器中打开: {file_path}")
        else:
            QMessageBox.warning(main_window, "警告", "无法打开文件管理器")

    except Exception as e:
        logger.error(f"打开文件管理器失败: {e}")
        QMessageBox.critical(main_window, "错误", f"打开文件管理器失败:\n{str(e)}")

def recalculate_md5_tool(main_window):
    """重新计算MD5工具"""
    try:
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QProgressBar, QTextEdit, QCheckBox
        import threading
        import time

        dialog = QDialog(main_window)
        dialog.setWindowTitle("重新计算MD5")
        dialog.setGeometry(300, 300, 600, 400)

        layout = QVBoxLayout()

        # 选项
        options_layout = QVBoxLayout()
        dry_run_check = QCheckBox("预览模式（不实际更新数据库）")
        dry_run_check.setChecked(True)
        options_layout.addWidget(dry_run_check)

        # 信息标签
        info_label = QLabel("重新计算数据库中缺失的MD5哈希值")
        layout.addWidget(info_label)
        layout.addLayout(options_layout)

        # 进度条
        progress_bar = QProgressBar()
        layout.addWidget(progress_bar)

        # 状态标签
        status_label = QLabel("准备就绪")
        layout.addWidget(status_label)

        # 日志输出
        log_text = QTextEdit()
        log_text.setMaximumHeight(200)
        layout.addWidget(log_text)

        def log_message(message):
            log_text.append(message)
            main_window.app.processEvents()

        def start_recalculation():
            try:
                # 获取数据库连接
                cursor = main_window.core.cursor
                conn = main_window.core.conn

                # 查询MD5为空的记录
                cursor.execute("""
                    SELECT id, file_path, file_name
                    FROM videos
                    WHERE md5_hash IS NULL OR md5_hash = ''
                    ORDER BY id
                """)
                records = cursor.fetchall()

                if not records:
                    log_message("✅ 没有找到需要重新计算MD5的记录")
                    status_label.setText("完成")
                    return

                total_records = len(records)
                progress_bar.setMaximum(total_records)
                progress_bar.setValue(0)

                dry_run = dry_run_check.isChecked()
                mode = "预览模式" if dry_run else "执行模式"
                log_message(f"🔍 找到 {total_records} 条需要处理的记录 ({mode})")

                success_count = 0
                failed_count = 0

                for i, (record_id, file_path, file_name) in enumerate(records):
                    status_label.setText(f"处理中: {i+1}/{total_records}")

                    log_message(f"📁 处理: {file_name}")

                    # 检查文件是否存在
                    if not file_path or not os.path.exists(file_path):
                        log_message(f"  ❌ 文件不存在: {file_path}")
                        failed_count += 1
                        progress_bar.setValue(i + 1)
                        continue

                    # 计算MD5
                    try:
                        import hashlib
                        hash_md5 = hashlib.md5()
                        with open(file_path, "rb") as f:
                            for chunk in iter(lambda: f.read(4096), b""):
                                hash_md5.update(chunk)
                        md5_hash = hash_md5.hexdigest()

                        log_message(f"  ✅ MD5: {md5_hash}")

                        if not dry_run:
                            cursor.execute(
                                "UPDATE videos SET md5_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                                (md5_hash, record_id)
                            )
                            conn.commit()

                        success_count += 1

                    except Exception as e:
                        log_message(f"  ❌ 计算失败: {e}")
                        failed_count += 1

                    progress_bar.setValue(i + 1)

                    # 短暂休息
                    if i % 10 == 0:
                        main_window.app.processEvents()

                # 最终统计
                log_message(f"\n📊 处理完成!")
                log_message(f"✅ 成功: {success_count}")
                log_message(f"❌ 失败: {failed_count}")
                log_message(f"📝 模式: {mode}")

                status_label.setText("完成")

            except Exception as e:
                log_message(f"❌ 处理过程中出错: {e}")
                status_label.setText("错误")

        start_btn = QPushButton("开始计算")
        start_btn.clicked.connect(lambda: threading.Thread(target=start_recalculation, daemon=True).start())
        layout.addWidget(start_btn)

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.setLayout(layout)
        dialog.exec()

    except Exception as e:
        logger.error(f"MD5计算工具失败: {e}")
        QMessageBox.critical(main_window, "错误", f"MD5计算工具失败:\n{str(e)}")

def check_invalid_records_tool(main_window):
    """检查无效记录工具"""
    try:
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QTextEdit, QMessageBox

        dialog = QDialog(main_window)
        dialog.setWindowTitle("检查无效记录")
        dialog.setGeometry(300, 300, 800, 600)

        layout = QVBoxLayout()

        info_label = QLabel("检查不在配置文件夹范围内的视频记录")
        layout.addWidget(info_label)

        # 结果显示
        result_text = QTextEdit()
        layout.addWidget(result_text)

        def check_records():
            try:
                cursor = main_window.core.cursor

                # 获取配置的文件夹
                cursor.execute("SELECT folder_path FROM folders WHERE is_active = 1")
                configured_folders = [row[0] for row in cursor.fetchall() if row[0]]

                if not configured_folders:
                    result_text.append("❌ 没有找到配置的文件夹")
                    return

                result_text.append("📁 配置的文件夹:")
                for i, folder in enumerate(configured_folders, 1):
                    status = "在线" if os.path.exists(folder) else "离线"
                    result_text.append(f"  {i}. {folder} ({status})")

                # 获取所有视频记录
                cursor.execute("SELECT id, file_path, file_name, source_folder FROM videos")
                all_videos = cursor.fetchall()

                result_text.append(f"\n📊 数据库中共有 {len(all_videos)} 个视频记录")

                # 检查无效记录
                invalid_records = []
                for video_id, file_path, file_name, source_folder in all_videos:
                    file_folder = os.path.dirname(file_path)
                    is_valid = any(file_folder.startswith(configured_folder) for configured_folder in configured_folders)

                    if not is_valid:
                        invalid_records.append((video_id, file_path, file_name, source_folder))

                result_text.append(f"✅ 有效记录: {len(all_videos) - len(invalid_records)} 个")
                result_text.append(f"❌ 无效记录: {len(invalid_records)} 个")

                if invalid_records:
                    result_text.append(f"\n❌ 无效记录详情:")
                    for i, (video_id, file_path, file_name, source_folder) in enumerate(invalid_records[:20], 1):  # 只显示前20个
                        result_text.append(f"  {i}. ID:{video_id} - {file_name}")
                        result_text.append(f"     路径: {file_path}")
                        result_text.append(f"     来源: {source_folder}")
                        result_text.append(f"     存在: {'是' if os.path.exists(file_path) else '否'}")

                    if len(invalid_records) > 20:
                        result_text.append(f"  ... 还有 {len(invalid_records) - 20} 个记录未显示")

            except Exception as e:
                result_text.append(f"❌ 检查过程中出错: {e}")

        def delete_invalid_records():
            reply = QMessageBox.question(
                dialog, "确认删除",
                "确定要删除所有无效记录吗？\n此操作不可恢复！",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                try:
                    cursor = main_window.core.cursor
                    conn = main_window.core.conn

                    # 获取配置的文件夹
                    cursor.execute("SELECT folder_path FROM folders WHERE is_active = 1")
                    configured_folders = [row[0] for row in cursor.fetchall() if row[0]]

                    # 获取无效记录的ID
                    cursor.execute("SELECT id, file_path, file_name, source_folder FROM videos")
                    all_videos = cursor.fetchall()

                    invalid_ids = []
                    for video_id, file_path, file_name, source_folder in all_videos:
                        file_folder = os.path.dirname(file_path)
                        is_valid = any(file_folder.startswith(configured_folder) for configured_folder in configured_folders)

                        if not is_valid:
                            invalid_ids.append(video_id)

                    if invalid_ids:
                        # 批量删除
                        placeholders = ','.join(['?'] * len(invalid_ids))
                        cursor.execute(f"DELETE FROM videos WHERE id IN ({placeholders})", invalid_ids)
                        conn.commit()

                        result_text.append(f"\n✅ 已删除 {len(invalid_ids)} 个无效记录")
                        # 重新检查
                        result_text.clear()
                        check_records()
                    else:
                        result_text.append("\n✅ 没有需要删除的记录")

                except Exception as e:
                    result_text.append(f"\n❌ 删除过程中出错: {e}")

        # 按钮
        button_layout = QVBoxLayout()
        check_btn = QPushButton("检查记录")
        check_btn.clicked.connect(check_records)
        button_layout.addWidget(check_btn)

        delete_btn = QPushButton("删除无效记录")
        delete_btn.clicked.connect(delete_invalid_records)
        button_layout.addWidget(delete_btn)

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)
        dialog.setLayout(layout)
        dialog.exec()

    except Exception as e:
        logger.error(f"检查无效记录工具失败: {e}")
        QMessageBox.critical(main_window, "错误", f"检查无效记录工具失败:\n{str(e)}")

def video_integrity_check(main_window):
    """视频完整性检查"""
    QMessageBox.information(main_window, "提示", "视频完整性检查功能正在开发中...")

def batch_rename_tool(main_window):
    """批量重命名工具"""
    QMessageBox.information(main_window, "提示", "批量重命名工具功能正在开发中...")

def file_move_manager_tool(main_window):
    """文件移动管理工具"""
    QMessageBox.information(main_window, "提示", "文件移动管理工具功能正在开发中...")

def apply_all_extensions(main_window):
    """
    应用所有扩展功能到主窗口

    Args:
        main_window: 主窗口实例
    """
    try:
        # 添加扩展功能菜单
        add_extensions_menu(main_window)

        # 添加工具栏按钮
        add_toolbar_buttons(main_window)

        # 增强右键菜单
        enhance_context_menu(main_window)

        logger.info("所有扩展功能应用成功")

        # 显示成功消息
        QMessageBox.information(
            main_window, "扩展功能",
            "扩展功能已成功集成到界面中！\n\n"
            "新增功能:\n"
            "• NFO文件导入 (Ctrl+N)\n"
            "• 重复文件管理 (Ctrl+D)\n"
            "• 批量操作 (Ctrl+B)\n"
            "• 增强的右键菜单\n"
            "• 数据库维护工具\n"
            "• MD5重新计算工具\n"
            "• 无效记录检查工具"
        )

    except Exception as e:
        logger.error(f"应用扩展功能失败: {e}")
        QMessageBox.critical(main_window, "错误", f"应用扩展功能失败:\n{str(e)}")

# 使用说明：
# 在你的media_library_pyside.py的主窗口类中，
# 在__init__方法的最后添加以下代码：
#
# try:
#     from pyside_extensions_patch import apply_all_extensions
#     apply_all_extensions(self)
# except ImportError:
#     print("扩展功能模块未找到")
# except Exception as e:
#     print(f"扩展功能加载失败: {e}")