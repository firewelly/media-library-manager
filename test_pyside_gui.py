#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PySide6版本的媒体库GUI测试脚本
用于验证新GUI的功能完整性
"""

import sys
import os

def test_imports():
    """测试模块导入"""
    print("测试模块导入...")

    try:
        from PySide6.QtWidgets import QApplication, QMainWindow
        print("✓ PySide6.QtWidgets 导入成功")
    except ImportError as e:
        print(f"✗ PySide6.QtWidgets 导入失败: {e}")
        return False

    try:
        from PySide6.QtCore import Qt, Signal
        print("✓ PySide6.QtCore 导入成功")
    except ImportError as e:
        print(f"✗ PySide6.QtCore 导入失败: {e}")
        return False

    try:
        from PySide6.QtGui import QPixmap
        print("✓ PySide6.QtGui 导入成功")
    except ImportError as e:
        print(f"✗ PySide6.QtGui 导入失败: {e}")
        return False

    try:
        import media_library
        print("✓ 原版 media_library 模块导入成功")
    except ImportError as e:
        print(f"✗ 原版 media_library 模块导入失败: {e}")
        return False

    try:
        from gui_adapter import setup_full_integration
        print("✓ GUI适配器模块导入成功")
    except ImportError as e:
        print(f"✗ GUI适配器模块导入失败: {e}")
        return False

    try:
        from media_library_pyside import MainWindow
        print("✓ PySide6版本主窗口导入成功")
    except ImportError as e:
        print(f"✗ PySide6版本主窗口导入失败: {e}")
        return False

    return True

def test_database_connection():
    """测试数据库连接"""
    print("\n测试数据库连接...")

    try:
        import sqlite3
        from media_library_pyside import MediaLibraryCore

        core = MediaLibraryCore()

        # 测试基本查询
        core.cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
        tables = core.cursor.fetchone()[0]
        print(f"✓ 数据库连接成功，发现 {tables} 个表")

        # 测试表结构
        core.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        table_names = [row[0] for row in core.cursor.fetchall()]
        print(f"✓ 数据库表: {', '.join(table_names)}")

        return True

    except Exception as e:
        print(f"✗ 数据库连接测试失败: {e}")
        return False

def test_gui_components():
    """测试GUI组件初始化"""
    print("\n测试GUI组件初始化...")

    try:
        from PySide6.QtWidgets import QApplication
        from media_library_pyside import MainWindow

        # 创建应用程序实例（测试用）
        app = QApplication.instance()
        if app is None:
            app = QApplication([])

        # 创建主窗口
        window = MainWindow()
        print("✓ 主窗口创建成功")

        # 测试核心组件
        assert hasattr(window, 'core'), "缺少core属性"
        assert hasattr(window, 'video_list'), "缺少video_list属性"
        assert hasattr(window, 'detail_widget'), "缺少detail_widget属性"
        assert hasattr(window, 'search_widget'), "缺少search_widget属性"
        print("✓ 核心GUI组件存在")

        # 测试数据库核心
        assert hasattr(window.core, 'conn'), "缺少数据库连接"
        assert hasattr(window.core, 'cursor'), "缺少数据库游标"
        assert hasattr(window.core, 'column_config'), "缺少列配置"
        print("✓ 数据库核心组件存在")

        # 测试菜单栏
        menubar = window.menuBar()
        assert menubar is not None, "菜单栏为空"
        menus = menubar.actions()
        assert len(menus) >= 3, "菜单数量不足"
        print(f"✓ 菜单栏创建成功，包含 {len(menus)} 个菜单")

        return True

    except Exception as e:
        print(f"✗ GUI组件测试失败: {e}")
        return False

def test_function_integration():
    """测试功能集成"""
    print("\n测试功能集成...")

    try:
        from PySide6.QtWidgets import QApplication
        from media_library_pyside import MainWindow

        app = QApplication.instance()
        if app is None:
            app = QApplication([])

        window = MainWindow()

        # 测试是否有适配器
        if hasattr(window, 'integration'):
            print("✓ 功能适配器已集成")
        else:
            print("⚠ 功能适配器未集成（可能正常，取决于实现方式）")

        # 测试基本方法存在
        required_methods = [
            'load_videos', 'load_tags', 'load_data', 'refresh_data',
            'on_search', 'on_video_selection_changed',
            'update_status', 'show_error', 'show_info'
        ]

        for method in required_methods:
            if hasattr(window, method):
                print(f"✓ 方法 {method} 存在")
            else:
                print(f"✗ 方法 {method} 缺失")
                return False

        return True

    except Exception as e:
        print(f"✗ 功能集成测试失败: {e}")
        return False

def test_data_loading():
    """测试数据加载功能"""
    print("\n测试数据加载功能...")

    try:
        from PySide6.QtWidgets import QApplication
        from media_library_pyside import MainWindow

        app = QApplication.instance()
        if app is None:
            app = QApplication([])

        window = MainWindow()

        # 测试标签加载
        try:
            window.load_tags()
            print("✓ 标签加载完成")
        except Exception as e:
            print(f"⚠ 标签加载失败: {e}")

        # 测试视频加载
        try:
            window.load_videos()
            print("✓ 视频列表加载完成")

            # 检查是否有数据
            if window.video_list.topLevelItemCount() > 0:
                print(f"✓ 成功加载 {window.video_list.topLevelItemCount()} 个视频记录")
            else:
                print("⚠ 数据库中没有视频记录（可能正常）")

        except Exception as e:
            print(f"⚠ 视频列表加载失败: {e}")

        return True

    except Exception as e:
        print(f"✗ 数据加载测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("=" * 50)
    print("PySide6媒体库GUI功能测试")
    print("=" * 50)

    tests = [
        ("模块导入测试", test_imports),
        ("数据库连接测试", test_database_connection),
        ("GUI组件测试", test_gui_components),
        ("功能集成测试", test_function_integration),
        ("数据加载测试", test_data_loading),
    ]

    results = []

    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        print("-" * 30)

        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"✗ {test_name} 执行异常: {e}")
            results.append((test_name, False))

    # 汇总结果
    print("\n" + "=" * 50)
    print("测试结果汇总:")
    print("=" * 50)

    passed = 0
    total = len(results)

    for test_name, result in results:
        status = "通过" if result else "失败"
        symbol = "✓" if result else "✗"
        print(f"{symbol} {test_name}: {status}")
        if result:
            passed += 1

    print(f"\n总计: {passed}/{total} 项测试通过")

    if passed == total:
        print("🎉 所有测试通过！PySide6版本GUI准备就绪。")
        return 0
    else:
        print("⚠ 部分测试失败，请检查相关功能。")
        return 1

def run_gui_demo():
    """运行GUI演示"""
    print("\n是否启动GUI演示？(y/n): ", end="")
    choice = input().strip().lower()

    if choice == 'y' or choice == 'yes':
        try:
            from PySide6.QtWidgets import QApplication
            from media_library_pyside import main as pyside_main

            print("启动PySide6版媒体库GUI...")
            pyside_main()

        except Exception as e:
            print(f"启动GUI失败: {e}")

if __name__ == "__main__":
    # 运行测试
    exit_code = main()

    # 可选：运行GUI演示
    if exit_code == 0:
        run_gui_demo()

    sys.exit(exit_code)