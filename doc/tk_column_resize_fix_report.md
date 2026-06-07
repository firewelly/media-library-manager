# Tk 表格列宽异常收缩问题修复报告

- 文档版本: v1
- 适用文件: `media_library.py` / `media_library_fixed.py`
- 结论状态: 已在 `fixed` 版本中验证通过基础手工测试与针对性回归测试

## 1. 问题背景

在 Tk 主版本中，用户手动拖动 `Treeview` 任意列的宽度后，会出现以下异常现象：

1. 被调整的列宽可能不会正确保存。
2. 其他未调整列的宽度会一并被压缩。
3. 某些情况下列顺序调整、排序或重建表格后，所有列宽会回退到异常的小值。
4. 一旦进入异常状态，往往只能通过“重置整个界面布局”才能恢复。

这个问题表面看是“列宽缩小”，本质上是多个交互和状态持久化问题叠加导致的复合型缺陷。

## 2. 问题症状

### 2.1 用户可见症状

1. 拖动任意列分隔线后，整张表格突然变得非常拥挤。
2. 标题、演员、标签等宽列会被异常压缩，内容显示不完整。
3. 问题不是稳定复现于某一列，而是可能出现在任意列。
4. 同一次操作中，列宽缩小的目标列和受影响列并不固定，看起来像“随机”。

### 2.2 触发条件

常见触发链包括：

1. 用户拖动列分隔线调整宽度后松手。
2. 用户调整列宽后又进行列拖拽交换。
3. 用户调整列宽后触发表头排序或内部 `Treeview` 重建。
4. 用户在列宽调整操作附近触发表头事件，导致排序、拖拽和宽度更新逻辑互相干扰。

## 3. 根因分析

### 3.1 根因一：`<ButtonRelease-1>` 被重复绑定覆盖

主版本中，同一个 `Treeview` 的 `'<ButtonRelease-1>'` 被多次绑定，不同逻辑互相覆盖：

1. 一次绑定用于“列宽调整结束后保存宽度”
2. 另一次绑定用于“列拖拽结束”

由于 Tk 的 `bind()` 默认是覆盖式而不是追加式，后绑定的处理函数会覆盖先前绑定，导致至少有一条事件链实际失效。

直接影响：

1. 列宽调整后保存逻辑不稳定。
2. 拖拽列顺序与列宽持久化之间发生竞争。
3. 初次创建和重建后的 `Treeview` 行为不一致。

主版本关键位置：

1. [media_library.py:L1157-L1176](file:///Users/firewell/bin/media/media_library.py#L1157-L1176)
2. [media_library.py:L626-L638](file:///Users/firewell/bin/media/media_library.py#L626-L638)

### 3.2 根因二：`Treeview` 列未显式设置 `stretch=False`

主版本在设置列宽时只传入了 `width` 和 `minwidth`，没有关闭默认的 `stretch`。

这意味着：

1. Tk 会根据可视区域自动重新分配列宽。
2. 用户拖动一列时，其他列有机会被被动压缩。
3. 一旦再叠加滚动条变化、表格重建、排序、列顺序调整等操作，整体宽度分配会进一步失稳。

这正是“明明只拖了一列，其他列却一起缩小”的最直接机制。

主版本关键位置：

1. [media_library.py:L592-L599](file:///Users/firewell/bin/media/media_library.py#L592-L599)
2. [media_library.py:L1132-L1139](file:///Users/firewell/bin/media/media_library.py#L1132-L1139)

### 3.3 根因三：表格重建前没有先同步当前真实列宽

主版本中，列顺序调整、重建 `Treeview`、某些排序路径都会重新创建列表控件。  
但在重建前，当前真实列宽没有稳定写回 `self.column_config`。

结果是：

1. 用户刚刚拖好的列宽只存在于当前 `Treeview` 组件内部。
2. 一旦触发重建，系统会重新按旧配置创建列。
3. 如果旧配置本身已经小、脏或未更新，就会出现“全部列突然变窄”的表现。

主版本关键位置：

1. [save_column_config](file:///Users/firewell/bin/media/media_library.py#L395-L408)
2. [recreate_treeview](file:///Users/firewell/bin/media/media_library.py#L555-L652)

### 3.4 根因四：表头点击、表头双击排序、列拖拽、列宽调整没有彻底隔离

主版本中，这几类交互共享同一块表头区域：

1. 单击表头
2. 双击表头排序
3. 拖动表头交换列顺序
4. 拖动分隔线调整列宽

由于事件边界没有被彻底隔离，某些情况下拖宽度动作会误触发表头相关逻辑，进一步触发排序或重建，从而把列宽状态再次写坏。

主版本关键位置：

1. [handle_single_click](file:///Users/firewell/bin/media/media_library.py#L3273-L3284)
2. [handle_double_click](file:///Users/firewell/bin/media/media_library.py#L3285-L3296)

### 3.5 次级问题：默认列配置是浅拷贝

主版本使用 `self.default_columns.copy()`，只会复制外层字典，不会复制内部每列的子字典。  
这会导致运行时对 `column_config` 的修改有机会污染“默认配置”的真实基线。

这不是首次触发异常的核心原因，但会放大后果：

1. 异常状态更难回退。
2. 重置布局未必真的回到“干净的默认状态”。

## 4. 修复思路

`fixed` 版本的修复不是单点补丁，而是针对整条问题链做收敛。

### 4.1 统一鼠标释放事件入口

新增统一的 `on_button_release()`，让列宽保存和列拖拽结束共用一个释放事件入口：

1. 先判断列宽是否发生变化
2. 若发生变化，则延迟保存当前真实宽度
3. 若当前存在列拖拽，则再处理列拖拽结束逻辑

关键位置：

1. [on_button_release](file:///Users/firewell/bin/media/media_library_fixed.py#L761-L771)

### 4.2 显式关闭 `stretch`

所有列统一通过 `_configure_treeview_columns()` 初始化，并显式设置：

```python
tree_widget.column(col_name, width=width, minwidth=50, stretch=False)
```

这样就能阻止 Tk 在用户调整某一列时自动挤压其他列。

关键位置：

1. [_configure_treeview_columns](file:///Users/firewell/bin/media/media_library_fixed.py#L455-L462)

### 4.3 重建、移动、排序前先同步当前列宽

新增当前列宽同步辅助逻辑：

1. `_get_current_treeview_widths()`
2. `_sync_current_treeview_widths_to_config()`

并在以下路径前调用：

1. `swap_columns()`
2. `move_column()`
3. `recreate_treeview()`
4. `sort_column()`
5. `on_closing()`

这样可以确保任何重建、排序、关闭前都先把当前真实列宽写回配置。

关键位置：

1. [同步辅助方法](file:///Users/firewell/bin/media/media_library_fixed.py#L439-L453)
2. [swap_columns](file:///Users/firewell/bin/media/media_library_fixed.py#L573-L591)
3. [move_column](file:///Users/firewell/bin/media/media_library_fixed.py#L628-L651)
4. [recreate_treeview](file:///Users/firewell/bin/media/media_library_fixed.py#L653-L749)
5. [sort_column](file:///Users/firewell/bin/media/media_library_fixed.py#L6523-L6536)
6. [on_closing](file:///Users/firewell/bin/media/media_library_fixed.py#L852-L861)

### 4.4 改造表头排序触发方式

为减少表头交互冲突，`fixed` 版本把排序触发从“单击表头或 heading command”收敛为“双击表头排序”。

具体变化：

1. 不再给 `heading(..., command=...)` 绑定排序
2. 单击表头主要用于拖拽开始
3. 双击表头才进入排序
4. `handle_single_click()` 把 `"break"` 正确向 Tk 返回，阻断默认事件链

关键位置：

1. [_configure_treeview_columns](file:///Users/firewell/bin/media/media_library_fixed.py#L455-L462)
2. [handle_single_click](file:///Users/firewell/bin/media/media_library_fixed.py#L3375-L3383)
3. [handle_double_click](file:///Users/firewell/bin/media/media_library_fixed.py#L3386-L3397)

### 4.5 增加配置清洗与深拷贝

`fixed` 版本新增：

1. `_clone_default_columns()`
2. `_sanitize_column_config()`

用途：

1. 深拷贝默认配置，防止默认值被运行时污染
2. 自动修复异常宽度
3. 自动重新归一化列顺序位置

关键位置：

1. [load_column_config 及其辅助方法](file:///Users/firewell/bin/media/media_library_fixed.py#L383-L437)

## 5. `fixed` 版本中的关键改动点

### 5.1 配置文件隔离

`fixed` 版本使用独立配置文件：

1. 主版本: `gui_config.json`
2. `fixed` 版本: `gui_config_fixed.json`

这样可以避免调试和修复过程中污染主版本用户正在使用的列配置。

关键位置：

1. [media_library_fixed.py:L321-L323](file:///Users/firewell/bin/media/media_library_fixed.py#L321-L323)

### 5.2 统一列初始化入口

`create_gui()` 和 `recreate_treeview()` 都改为通过 `_configure_treeview_columns()` 初始化列，避免两处逻辑再度漂移。

### 5.3 排序箭头刷新统一

新增 `_refresh_sort_heading_labels()`，避免排序箭头逻辑在多个 `sort_column()` 实现中分散维护。

## 6. 验证情况

### 6.1 手工验证

已完成基础手工验证，现象表现为：

1. 调整任意列宽后不再出现整表列宽异常收缩
2. 简单测试下问题应已修复

### 6.2 自动化验证

新增测试文件：

1. [test_tk_column_width_logic.py](file:///Users/firewell/bin/media/tests/test_tk_column_width_logic.py)

覆盖点包括：

1. 配置规范化
2. 最小列宽保护
3. `stretch=False` 生效
4. 列宽变化检测
5. 表头单击返回 `"break"` 的事件链

执行结果：

```bash
python3 tests/test_tk_column_width_logic.py -v
```

结果：`5` 个测试全部通过。

同时执行：

```bash
python3 -m py_compile media_library_fixed.py
```

结果：语法编译通过。

## 7. 修复结论

本次问题的真正根因并不是单一的“列宽算法错误”，而是以下四类问题叠加：

1. 释放事件重复绑定导致列宽保存不稳定
2. `Treeview` 默认 `stretch=True` 导致其他列被被动压缩
3. 重建前未同步真实列宽，导致旧配置回灌
4. 表头排序、拖拽、列宽调整事件混用

`fixed` 版本通过统一事件入口、关闭自动拉伸、同步真实列宽、隔离排序触发和清洗配置，已经将整条异常链路收敛。

## 8. 后续建议

### 8.1 如果要回灌到主版本

不建议只拷贝单个修复点。  
建议按“整组机制”回灌：

1. 配置清洗
2. `stretch=False`
3. 统一 `ButtonRelease`
4. 重建/排序前同步列宽
5. 排序触发方式改造

### 8.2 合并前要额外确认

1. 是否接受“表头排序由单击改为双击”的交互变化
2. 是否保留配置文件隔离策略
3. 是否进一步把 `create_gui()` 与 `recreate_treeview()` 中重复的表格初始化逻辑再抽一层，减少后续回归风险
