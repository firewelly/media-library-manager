# media_library.py 列宽与列序修复方案

## 问题症状

1. 拖动列分隔线调整宽度，松手后无效，不保存
2. 拖动列头交换两列顺序，所有列宽回退到旧值
3. 列宽有时自动"弹回"

## 根因分析

### 问题 1：`<ButtonRelease-1>` 被重复绑定覆盖

**位置**：`create_gui()` 中第 1158 行和第 1176 行

```python
# 第 1158 行 - 第一次绑定
self.video_tree.bind('<ButtonRelease-1>', self.on_column_resize_end)

# ... 中间若干绑定 ...

# 第 1176 行 - 第二次绑定，覆盖了上面
self.video_tree.bind('<ButtonRelease-1>', self.on_drag_end)
```

Tkinter 的 `widget.bind()` 是覆盖式而非追加式。第二次绑定 `on_drag_end` 完全覆盖了第一次的 `on_column_resize_end`，导致用户拖动列宽后 `on_column_resize_end` 永远不会执行，其内部的 `save_column_config_after_resize`（第 665 行）形同虚设。

### 问题 2：拖拽交换列后 rebuild 使用旧配置

**位置**：`on_drag_end`(第 456 行) → `swap_columns`(第 479 行) → `recreate_treeview`(第 555 行)

`recreate_treeview` 销毁并重建整个 Treeview 时，列宽从 `self.column_config` 读取。但 `column_config` 是上次程序启动时从 `gui_config.json` 加载的旧值。由于问题 1 导致当前会话的列宽从未保存，重建后就回退到旧值。

### 问题 3：缺少 `stretch=False`

**位置**：第 598 行、第 1139 行

```python
self.video_tree.column(col_name, width=width, minwidth=50)
```

未传 `stretch` 参数，默认 `True`，导致列宽被自动拉伸修正。

### 问题 4：`recreate_treeview()` 事件绑定不完整

**位置**：第 627 行

重建后的 Treeview 只绑了 `on_column_resize_end`，缺少 `on_drag_end` 和 `<B1-Motion>` 绑定，行为与初始不一致。

---

## 修复方案

### 修复 1：合并两个 `<ButtonRelease-1>` 处理函数

**位置**：`create_gui()` 中第 1157-1176 行

删除两次独立的 `bind`，改为绑定一个统一处理函数：

```python
# 替换原来的两次 bind
self.video_tree.bind('<ButtonRelease-1>', self.on_button_release)
```

新增统一处理函数（可放在第 653 行 `on_column_resize_end` 附近）：

```python
def on_button_release(self, event):
    """统一处理 ButtonRelease-1：同时处理列宽调整和拖拽结束"""
    # 先检测列宽调整（拖动列分隔线）
    self.on_column_resize_end(event)
    # 再处理列头拖拽交换
    self.on_drag_end(event)
```

### 修复 2：`swap_columns` / `move_column` 前保存当前列宽

**位置**：第 479 行 `swap_columns` 方法开头，第 532 行 `move_column` 方法开头

```python
def swap_columns(self, col1, col2):
    # ---- 新增：重建前先保存当前列宽 ----
    if hasattr(self, 'video_tree') and self.video_tree.winfo_exists():
        for col in self.video_tree['columns']:
            if col in self.column_config:
                self.column_config[col]['width'] = self.video_tree.column(col, 'width')
    # ---- 原有代码继续 ----
    idx1 = self.video_tree['columns'].index(col1)
    ...
```

`move_column` 同理。

### 修复 3：设置 `stretch=False`

**位置**：第 598 行（`recreate_treeview` 内）和第 1139 行（`create_gui` 内）

```python
# 改为
self.video_tree.column(col_name, width=width, minwidth=50, stretch=False)
```

### 修复 4：补全 `recreate_treeview()` 的事件绑定

**位置**：第 627 行

```python
# 替换
self.video_tree.bind('<ButtonRelease-1>', self.on_column_resize_end)

# 为
self.video_tree.bind('<ButtonRelease-1>', self.on_button_release)
self.video_tree.bind('<B1-Motion>', self.on_drag_motion)
```

---

## 涉及行号总览

| 行号 | 操作 |
|------|------|
| 第 479-495 行 | `swap_columns` 开头新增保存当前列宽 |
| 第 532-553 行 | `move_column` 开头新增保存当前列宽 |
| 第 598 行 | `.column()` 加 `stretch=False` |
| 第 627 行 | 绑定改为 `on_button_release`，补充 `<B1-Motion>` |
| 第 653-663 行附近 | 新增 `on_button_release` 方法 |
| 第 1139 行 | `.column()` 加 `stretch=False` |
| 第 1157-1176 行 | 合并两次 bind 为一次 |

每个修复独立、改动最小，不会影响其他功能。
