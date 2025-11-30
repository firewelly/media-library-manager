#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
扩展功能测试脚本
"""

import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget
from PySide6.QtCore import Qt

# 测试导入
try:
    from extension_dialogs import NFODialog, DuplicateManagerDialog, BatchOperationsDialog
    from utils import DatabaseManager
    print("✅ 扩展对话框导入成功")
except ImportError as e:
    print(f"❌ 扩展对话框导入失败: {e}")
    sys.exit(1)

class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("扩展功能测试")
        self.setGeometry(200, 200, 400, 300)

        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 创建布局
        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        # 创建数据库管理器
        try:
            self.db_manager = DatabaseManager('media_library.db')
            print("✅ 数据库连接成功")
        except Exception as e:
            print(f"❌ 数据库连接失败: {e}")
            self.db_manager = None

        # 创建测试按钮
        self.nfo_btn = QPushButton("测试NFO对话框")
        self.nfo_btn.clicked.connect(self.test_nfo_dialog)
        layout.addWidget(self.nfo_btn)

        self.duplicate_btn = QPushButton("测试重复文件对话框")
        self.duplicate_btn.clicked.connect(self.test_duplicate_dialog)
        layout.addWidget(self.duplicate_btn)

        self.batch_btn = QPushButton("测试批量操作对话框")
        self.batch_btn.clicked.connect(self.test_batch_dialog)
        layout.addWidget(self.batch_btn)

        # 创建数据库适配器
        self.db_adapter = self.create_db_adapter()

    def create_db_adapter(self):
        """创建数据库适配器"""
        if not self.db_manager:
            return None

        class DBAdapter:
            def __init__(self, db_manager):
                self.db = db_manager

            def execute_query(self, query, params=()):
                return self.db.execute_query(query, params)

            def execute_update(self, query, params=()):
                return self.db.execute_update(query, params)

            def get_videos(self, limit=None, offset=0, where_clause="", params=(), order_by="created_at DESC"):
                return self.db.get_videos(limit, offset, where_clause, params, order_by)

            def get_video_count(self, where_clause="", params=()):
                return self.db.get_video_count(where_clause, params)

            def update_video(self, video_id, video_data):
                return self.db.update_video(video_id, video_data)

            def delete_video(self, video_id):
                return self.db.delete_video(video_id)

            def find_duplicates(self):
                return self.db.find_duplicates()

        return DBAdapter(self.db_manager)

    def test_nfo_dialog(self):
        """测试NFO对话框"""
        try:
            dialog = NFODialog(self, self.db_adapter)
            dialog.exec()
            print("✅ NFO对话框测试完成")
        except Exception as e:
            print(f"❌ NFO对话框测试失败: {e}")

    def test_duplicate_dialog(self):
        """测试重复文件对话框"""
        try:
            dialog = DuplicateManagerDialog(self, self.db_adapter)
            dialog.exec()
            print("✅ 重复文件对话框测试完成")
        except Exception as e:
            print(f"❌ 重复文件对话框测试失败: {e}")

    def test_batch_dialog(self):
        """测试批量操作对话框"""
        try:
            # 模拟选中的视频ID
            selected_ids = [1, 2, 3]  # 示例ID
            dialog = BatchOperationsDialog(self, self.db_adapter, selected_ids)
            dialog.exec()
            print("✅ 批量操作对话框测试完成")
        except Exception as e:
            print(f"❌ 批量操作对话框测试失败: {e}")

    def closeEvent(self, event):
        """关闭事件"""
        try:
            if hasattr(self, 'db_manager') and self.db_manager:
                self.db_manager.close()
        except:
            pass
        event.accept()

def main():
    app = QApplication(sys.argv)

    window = TestWindow()
    window.show()

    print("🎉 扩展功能测试窗口已启动")
    print("📝 请点击按钮测试各个对话框功能")

    sys.exit(app.exec())

if __name__ == "__main__":
    main()