# -*- coding: utf-8 -*-
"""
去重对话框
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QRadioButton, QButtonGroup
)
from PySide6.QtCore import Qt

from ..core import Database
from ..workers import TaskWorker
from .task_progress_dialog import TaskProgressDialog


class DedupDialog(QDialog):
    """去重对话框"""

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.setWindowTitle("智能去重")
        self.setMinimumSize(800, 600)
        self.db = db

        self._setup_ui()
        self._find_duplicates()

    def _setup_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("智能去重")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(title)

        desc = QLabel("检测并删除重复的视频文件（基于 MD5）")
        desc.setStyleSheet("color: #aab2c0;")
        layout.addWidget(desc)

        # 保留策略
        policy_group = QLabel("保留策略:")
        policy_group.setStyleSheet("font-weight: 600;")
        layout.addWidget(policy_group)

        self.policy_group = QButtonGroup()
        
        policy_layout = QHBoxLayout()
        
        self.radio_largest = QRadioButton("保留最大文件")
        self.radio_largest.setChecked(True)
        self.policy_group.addButton(self.radio_largest, 0)
        policy_layout.addWidget(self.radio_largest)

        self.radio_newest = QRadioButton("保留最新文件")
        self.policy_group.addButton(self.radio_newest, 1)
        policy_layout.addWidget(self.radio_newest)

        self.radio_oldest = QRadioButton("保留最旧文件")
        self.policy_group.addButton(self.radio_oldest, 2)
        policy_layout.addWidget(self.radio_oldest)

        policy_layout.addStretch()
        layout.addLayout(policy_layout)

        # 重复文件列表
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["MD5", "路径", "大小", "创建时间", "操作"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 120)
        self.table.setColumnWidth(2, 80)
        self.table.setColumnWidth(3, 120)
        self.table.setColumnWidth(4, 80)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        # 统计
        self.stats_label = QLabel("发现 0 组重复文件")
        self.stats_label.setStyleSheet("color: #aab2c0;")
        layout.addWidget(self.stats_label)

        # 按钮
        buttons = QHBoxLayout()
        
        delete_btn = QPushButton("删除重复文件")
        delete_btn.setProperty("primary", "true")
        delete_btn.clicked.connect(self._delete_duplicates)
        buttons.addWidget(delete_btn)

        buttons.addStretch()

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        buttons.addWidget(close_btn)

        layout.addLayout(buttons)

    def _find_duplicates(self):
        """查找重复文件"""
        # 查找 MD5 重复
        rows = self.db.execute("""
            SELECT md5_hash, COUNT(*) as count
            FROM videos
            WHERE md5_hash IS NOT NULL AND md5_hash != ''
            GROUP BY md5_hash
            HAVING count > 1
            ORDER BY count DESC
        """)

        self._duplicates = []
        for row in rows:
            md5 = row["md5_hash"]
            videos = self.db.execute(
                "SELECT id, file_path, file_size, created_at FROM videos WHERE md5_hash = ? ORDER BY file_size DESC",
                (md5,)
            )
            self._duplicates.append({
                "md5": md5,
                "videos": [dict(v) for v in videos]
            })

        # 显示
        total_rows = sum(len(d["videos"]) for d in self._duplicates)
        self.table.setRowCount(total_rows)

        row_idx = 0
        for dup in self._duplicates:
            for i, video in enumerate(dup["videos"]):
                # MD5
                md5_item = QTableWidgetItem(dup["md5"][:16] + "...")
                md5_item.setToolTip(dup["md5"])
                self.table.setItem(row_idx, 0, md5_item)

                # 路径
                self.table.setItem(row_idx, 1, QTableWidgetItem(video["file_path"]))

                # 大小
                file_size = video["file_size"] or 0
                if file_size >= 1024**3:
                    size_str = f"{file_size / (1024**3):.2f} GB"
                elif file_size >= 1024**2:
                    size_str = f"{file_size / (1024**2):.1f} MB"
                else:
                    size_str = ""
                self.table.setItem(row_idx, 2, QTableWidgetItem(size_str))

                # 创建时间
                self.table.setItem(row_idx, 3, QTableWidgetItem(video["created_at"] or ""))

                # 操作（标记要删除的）
                if i == 0:
                    self.table.setItem(row_idx, 4, QTableWidgetItem("保留"))
                else:
                    delete_item = QTableWidgetItem("删除")
                    delete_item.setForeground(Qt.GlobalColor.red)
                    self.table.setItem(row_idx, 4, delete_item)

                row_idx += 1

        self.stats_label.setText(f"发现 {len(self._duplicates)} 组重复文件，共 {total_rows} 个文件")

    def _delete_duplicates(self):
        """删除重复文件"""
        if not self._duplicates:
            QMessageBox.information(self, "提示", "没有发现重复文件")
            return

        # 计算要删除的数量
        to_delete = sum(len(d["videos"]) - 1 for d in self._duplicates)
        
        reply = QMessageBox.question(
            self, "确认",
            f"确定要删除 {to_delete} 个重复文件吗？\n\n"
            "注意：这只会删除数据库记录，不会删除实际文件。\n"
            "如需删除文件，请手动操作。",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # 获取保留策略
        policy_id = self.policy_group.checkedId()
        
        def task(progress_callback=None, cancel_check=None):
            deleted = 0
            for dup in self._duplicates:
                if cancel_check and cancel_check():
                    break

                videos = dup["videos"]
                
                # 根据策略排序
                if policy_id == 0:  # 最大
                    videos.sort(key=lambda v: v["file_size"] or 0, reverse=True)
                elif policy_id == 1:  # 最新
                    videos.sort(key=lambda v: v["created_at"] or "", reverse=True)
                elif policy_id == 2:  # 最旧
                    videos.sort(key=lambda v: v["created_at"] or "")

                # 保留第一个，删除其余
                for video in videos[1:]:
                    self.db.execute_write("DELETE FROM videos WHERE id = ?", (video["id"],))
                    deleted += 1

                if progress_callback:
                    progress_callback(f"已删除 {deleted} 个重复文件", int(deleted / to_delete * 100))

            return {"success": deleted, "failed": 0}

        # 显示进度
        progress = TaskProgressDialog("删除重复文件", self)
        progress.show()

        worker = TaskWorker(task)
        worker.progress_signal.connect(progress.update_progress)
        progress.cancel_signal.connect(worker.cancel)

        def on_finished(result):
            progress.close()
            QMessageBox.information(
                self, "完成",
                f"已删除 {result['success']} 个重复文件"
            )
            self._find_duplicates()  # 刷新列表

        worker.finished_signal.connect(on_finished)
        worker.error_signal.connect(
            lambda err: (progress.close(), QMessageBox.critical(self, "错误", str(err)))
        )

        worker.start()
        self._worker = worker
