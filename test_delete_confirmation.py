#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试删除确认对话框功能
"""

import tkinter as tk
from tkinter import ttk
import os
import sys

# 添加当前目录到路径，以便导入media_library模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class TestDeleteConfirmation:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("测试删除确认对话框")
        self.root.geometry("400x200")
        
        # 创建测试按钮
        ttk.Label(self.root, text="点击按钮测试删除确认对话框", font=('Arial', 12)).pack(pady=20)
        
        ttk.Button(self.root, text="测试删除确认", command=self.test_confirmation).pack(pady=10)
        
        ttk.Label(self.root, text="快捷键说明：", font=('Arial', 10, 'bold')).pack(pady=(20, 5))
        ttk.Label(self.root, text="Y - 删除此文件\nN - 跳过此文件\nA - 删除所有后续文件\nCtrl+N - 跳过所有后续文件\nC - 取消操作\nESC - 跳过此文件", 
                 font=('Arial', 9), justify='left').pack()
    
    def ask_delete_confirmation(self, file_path, error):
        """询问用户是否直接删除文件（当send2trash失败时）"""
        import tkinter.messagebox as msgbox
        
        filename = os.path.basename(file_path)
        message = f"无法将文件移至回收站：\n{filename}\n\n错误信息：{str(error)}\n\n是否直接删除此文件？"
        
        # 创建自定义对话框
        dialog = tk.Toplevel(self.root)
        dialog.title("删除确认")
        dialog.geometry("600x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 居中显示
        dialog.geometry("+%d+%d" % (self.root.winfo_rootx() + 50, self.root.winfo_rooty() + 50))
        
        result = {'choice': 'n'}  # 默认选择不删除
        
        # 消息文本
        msg_frame = ttk.Frame(dialog)
        msg_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        ttk.Label(msg_frame, text=message, wraplength=450, justify="left").pack()
        
        # 按钮框架
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        def set_choice(choice):
            result['choice'] = choice
            dialog.destroy()
        
        # 第一行按钮
        btn_row1 = ttk.Frame(btn_frame)
        btn_row1.pack(fill="x", pady=5)
        
        ttk.Button(btn_row1, text="是(Y) - 删除此文件", 
                  command=lambda: set_choice('y')).pack(side="left", padx=5)
        ttk.Button(btn_row1, text="否(N) - 跳过此文件", 
                  command=lambda: set_choice('n')).pack(side="left", padx=5)
        ttk.Button(btn_row1, text="取消(C) - 停止操作", 
                  command=lambda: set_choice('c')).pack(side="left", padx=5)
        
        # 第二行按钮
        btn_row2 = ttk.Frame(btn_frame)
        btn_row2.pack(fill="x", pady=5)
        
        ttk.Button(btn_row2, text="全部删除(A) - 删除所有后续文件", 
                  command=lambda: set_choice('a')).pack(side="left", padx=5)
        ttk.Button(btn_row2, text="全部跳过(NA) - 跳过所有后续文件", 
                  command=lambda: set_choice('na')).pack(side="left", padx=5)
        
        # 键盘快捷键
        def on_key(event):
            key = event.char.lower()
            if key == 'y':
                set_choice('y')
            elif key == 'n':
                set_choice('n')
            elif key == 'a':
                set_choice('a')
            elif key == 'c':
                set_choice('c')
        
        # 处理特殊按键组合（如Ctrl+N代表na）
        def on_key_press(event):
            if event.state & 0x4:  # Ctrl键被按下
                if event.keysym.lower() == 'n':
                    set_choice('na')
            elif event.keysym == 'Escape':
                set_choice('n')  # ESC键默认为跳过
        
        dialog.bind('<Key>', on_key)
        dialog.bind('<KeyPress>', on_key_press)
        dialog.focus_set()
        
        # 等待用户选择
        dialog.wait_window()
        
        return result['choice']
    
    def test_confirmation(self):
        """测试确认对话框"""
        test_file = "/path/to/test/video.mp4"
        test_error = Exception("NAS上没有回收站功能")
        
        choice = self.ask_delete_confirmation(test_file, test_error)
        
        # 显示结果
        result_window = tk.Toplevel(self.root)
        result_window.title("测试结果")
        result_window.geometry("300x150")
        result_window.transient(self.root)
        
        choice_text = {
            'y': '是 - 删除此文件',
            'n': '否 - 跳过此文件', 
            'a': '全部删除 - 删除所有后续文件',
            'na': '全部跳过 - 跳过所有后续文件',
            'c': '取消 - 停止操作'
        }
        
        ttk.Label(result_window, text=f"您的选择：{choice_text.get(choice, choice)}", 
                 font=('Arial', 12)).pack(pady=30)
        ttk.Button(result_window, text="确定", 
                  command=result_window.destroy).pack()
    
    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = TestDeleteConfirmation()
    app.run()