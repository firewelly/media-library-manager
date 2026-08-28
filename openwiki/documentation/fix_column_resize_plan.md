---
type: 参考
title: 列宽调整修复方案
description: Tk Treeview 列宽调整/重新排序缺陷的根本原因分析与修复计划 —— 事件绑定冲突、重建时配置陈旧、缺少 stretch=False 以及事件重新绑定不完整。
tags: [documentation, bugfix, Tk]
openwiki:
  roles: [delivery]
  source_paths: [fix_column_resize_plan.md, media_library.py]
---

# 列宽调整修复方案

`fix_column_resize_plan.md` 记录了 `media_library.py` 中四个 Tk Treeview 列缺陷的根本原因分析。

## 问题现象

1. 拖动列分隔符调整宽度无效
2. 拖动列标头重新排序会重置所有列宽
3. 列宽有时会弹回原状

## 根本原因

### 问题 1：`<ButtonRelease-1>` 被绑定两次
- **位置**：`create_gui()`，约第 1158 行和 1176 行
- Tkinter 的 `bind()` 是**覆盖**操作，而非追加
- `on_drag_end` 覆盖了 `on_column_resize_end`，导致列宽调整保存事件永远不会触发

### 问题 2：重建时使用了陈旧配置
- **流程**：`on_drag_end` -> `swap_columns` -> `recreate_treeview`
- `recreate_treeview` 从 `self.column_config`（启动时加载）读取列宽
- 由于问题 1 阻止了保存，重建时会回退到旧值

### 问题 3：缺少 `stretch=False`
- `column()` 调用未传递 `stretch=False`
- 默认值 `True` 会导致自动修正列宽

### 问题 4：重建后事件绑定不完整
- `recreate_treeview()` 仅绑定了 `on_column_resize_end`
- 缺少 `on_drag_end` 和 `<B1-Motion>` 绑定

## 修复

该修复（在提交 `de1eb26` 和 `e7fa562` 中实现）整合了事件绑定，并确保在重建后重新应用所有处理程序。

## 测试覆盖率

`tests/test_tk_column_width_logic.py` 通过一个 `FakeTreeWidget` 测试替身验证了这些修复，该替身会跟踪绑定以及列/表头调用。

## 另请参阅

- [单元测试](../tests/unit_tests.md) — 列宽调整测试
- [Tk Classic](../main_application/v1.md) — 受影响的组件