---
type: 参考
title: 单元测试
description: 记录单元测试 —— test_pyside_utils.py（utils 模块的 mock 和断言）与 test_tk_column_width_logic.py（使用 FakeTreeWidget 进行 Tk Treeview 列调整大小/重新排序）。
openwiki:
  roles: [testing]
  source_paths: [tests/test_pyside_utils.py, tests/test_tk_column_width_logic.py]
---

# 单元测试

## `test_pyside_utils.py`

使用 `unittest` 和 `MagicMock` 测试共享的 `utils/` 模块及关键集成：

**测试的组件：**
- `ThumbnailGenerator.get_ffmpeg_command()` — 通过 mock `shutil.which` 和 `os.path.exists` 绕过环境特定的分支，验证正确的路径解析
- `BatchOperationManager` — Mock 数据库交互
- `MaintenanceManager` — Mock 数据库交互
- `JavSPIntegration` — Mock 爬虫管理器初始化
- `javdb_crawler_single.get_attempt_configs()` — CloudFlare 挑战检测
- `javdb_login_helper.get_login_attempts()` — 登录尝试跟踪

**关键测试模式：**
```python
# Cross-environment ffmpeg path test
with patch('shutil.which', return_value=test_path), \
     patch('os.path.exists', return_value=False):
    self.assertEqual(ThumbnailGenerator.get_ffmpeg_command(), test_path)
```

这种模式通过 mock 掉真实的文件系统检查，避免了测试与主机环境的耦合。

## `test_tk_column_width_logic.py`

在没有真实 Tk 显示的情况下测试 Tk Treeview 列宽调整和重排序逻辑：

**`FakeTreeWidget`** — 模拟 `tkinter.ttk.Treeview` 的测试替身：
- 跟踪 `heading()` 和 `column()` 调用
- 将列宽存储在字典中
- 实现 `winfo_exists()` 以通过存在性检查

**测试的行为：**
- 列宽调整：验证 `on_column_resize_end` 是否正确读取新宽度并调用 `save_column_config_after_resize`
- 列重排序：验证 `swap_columns` 是否正确交换位置并触发 `recreate_treeview`
- 事件绑定冲突：验证历史 bug 的修复，该 bug 中 `<ButtonRelease-1>` 被绑定了两次（参见 [fix_column_resize_plan](../documentation/fix_column_resize_plan.md)）

## 运行

```bash
cd /Users/firewell/bin/media
python3 tests/test_pyside_utils.py
python3 tests/test_tk_column_width_logic.py
```

## 另请参阅

- [测试概述](overview.md) — 完整的测试套件
- [集成测试](integration_tests.md) — v2 GUI 测试
- [fix_column_resize_plan](../documentation/fix_column_resize_plan.md) — 这些测试所验证的 bug 分析