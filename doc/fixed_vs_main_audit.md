# `media_library_fixed.py` vs `media_library.py` 差异审计报告

- 文档版本: v1
- 审计目标: 识别 `fixed` 版相对主版本除了列宽修复之外还引入了哪些行为变化
- 使用场景: 后续决定是否把 `fixed` 的改动回灌到主版本时，作为风险评估依据

## 1. 审计结论

`media_library_fixed.py` 不是单纯的“列宽补丁版”，它还包含以下额外变化：

1. 配置文件从 `gui_config.json` 切换为 `gui_config_fixed.json`
2. 配置加载逻辑增加了深拷贝和脏配置清洗
3. 表头排序交互从“单击可触发”收敛为“明确双击排序”
4. 表头单击事件会更强地阻断默认事件链
5. 关闭窗口前会主动同步实时列宽再保存
6. `create_gui()` 与 `recreate_treeview()` 的初始化行为更一致

因此，后续如果要把 `fixed` 回灌到主版本，不能把它当成“只改列宽”的补丁去 cherry-pick，而应该按“可回灌 / 需确认 / 暂不回灌”三类拆分处理。

## 2. 审计范围

本次对比重点覆盖：

1. 列配置加载与保存
2. Treeview 创建与重建
3. 表头单击、双击、拖拽、列宽调整事件
4. 排序逻辑
5. 关闭窗口时配置保存

核心对比文件：

1. [media_library.py](file:///Users/firewell/bin/media/media_library.py)
2. [media_library_fixed.py](file:///Users/firewell/bin/media/media_library_fixed.py)

参考材料：

1. [fix_column_resize_plan.md](file:///Users/firewell/bin/media/fix_column_resize_plan.md)
2. [tk_column_resize_fix_report.md](file:///Users/firewell/bin/media/doc/tk_column_resize_fix_report.md)

## 3. 明确的非列宽行为变化

### 3.1 配置文件隔离

主版本：

1. 使用 `gui_config.json`

`fixed` 版本：

1. 改用 `gui_config_fixed.json`

影响：

1. `fixed` 启动时不会继承主版本已有的列配置
2. `fixed` 调试时不会污染主版本配置
3. 如果未来回灌到主版本，这个隔离会消失，需要重新考虑旧配置兼容性

证据：

1. [主版本配置路径](file:///Users/firewell/bin/media/media_library.py#L320-L321)
2. [fixed 配置路径](file:///Users/firewell/bin/media/media_library_fixed.py#L321-L323)

### 3.2 配置加载增加容错与自动修复

主版本：

1. 直接读取 `saved_config['columns']`
2. 使用 `self.default_columns.copy()`

`fixed` 版本：

1. 使用 `_clone_default_columns()` 深拷贝
2. 使用 `_sanitize_column_config()` 自动纠正非法宽度
3. 自动重新归一化 `position`

影响：

1. `fixed` 会自动修正脏配置
2. 用户若之前存了异常列顺序，`fixed` 会主动调整
3. 如果回灌到主版本，旧用户配置的兼容行为会变化

证据：

1. [主版本加载逻辑](file:///Users/firewell/bin/media/media_library.py#L382-L410)
2. [fixed 加载逻辑](file:///Users/firewell/bin/media/media_library_fixed.py#L383-L437)

### 3.3 表头排序交互变化

主版本：

1. `heading(..., command=lambda ...)` 可触发表头排序
2. 还保留了双击表头排序逻辑

`fixed` 版本：

1. 去掉了 `heading(..., command=...)`
2. 排序统一由双击表头触发

影响：

1. 排序交互从“更容易触发”变为“更明确但更保守”
2. 用户若习惯单击表头排序，会感知为交互变化
3. 这是为了避免拖拽列宽、拖拽列顺序时误触发排序

证据：

1. [主版本列标题绑定](file:///Users/firewell/bin/media/media_library.py#L592-L599)
2. [主版本初始 Treeview 列标题绑定](file:///Users/firewell/bin/media/media_library.py#L1132-L1139)
3. [fixed 列标题绑定](file:///Users/firewell/bin/media/media_library_fixed.py#L455-L462)
4. [fixed 双击排序入口](file:///Users/firewell/bin/media/media_library_fixed.py#L3386-L3397)

### 3.4 表头单击的事件拦截更强

主版本：

```python
self.on_drag_start(event)
return
```

`fixed` 版本：

```python
return self.on_drag_start(event)
```

影响：

1. `on_drag_start()` 返回 `"break"` 时，`fixed` 会把它继续上传给 Tk
2. 这样可以更稳定地阻断默认表头行为
3. 这不只是列宽修复，也改变了表头单击的整体事件语义

证据：

1. [主版本 handle_single_click](file:///Users/firewell/bin/media/media_library.py#L3273-L3284)
2. [fixed handle_single_click](file:///Users/firewell/bin/media/media_library_fixed.py#L3375-L3383)

### 3.5 关闭窗口时的保存语义变化

主版本：

1. 关闭时直接 `save_column_config()`

`fixed` 版本：

1. 关闭前先 `_sync_current_treeview_widths_to_config()`
2. 再执行保存

影响：

1. 用户最后一次手工调整的列宽更容易被真正持久化
2. 这会改变关闭窗口的保存时机和状态来源

证据：

1. [主版本 on_closing](file:///Users/firewell/bin/media/media_library.py#L749-L752)
2. [fixed on_closing](file:///Users/firewell/bin/media/media_library_fixed.py#L852-L861)

### 3.6 重建后的行为一致性增强

主版本：

1. `create_gui()` 和 `recreate_treeview()` 的绑定逻辑并不完全一致
2. 这使得“首次创建”和“重建后”的表格行为不同

`fixed` 版本：

1. 两处都统一使用 `_configure_treeview_columns()`
2. 两处都统一绑定 `on_button_release`
3. 两处都统一绑定 `<B1-Motion>`

影响：

1. 固定版行为更稳定
2. 但也意味着如果未来再改一处而漏掉另一处，风险依然存在

证据：

1. [主版本 recreate_treeview](file:///Users/firewell/bin/media/media_library.py#L555-L652)
2. [主版本 create_gui Treeview 部分](file:///Users/firewell/bin/media/media_library.py#L1125-L1183)
3. [fixed recreate_treeview](file:///Users/firewell/bin/media/media_library_fixed.py#L653-L749)
4. [fixed create_gui Treeview 部分](file:///Users/firewell/bin/media/media_library_fixed.py#L1223-L1274)

## 4. 仍然存在的结构问题

### 4.1 仍有重复定义的排序相关方法

`media_library.py` 和 `media_library_fixed.py` 都保留了后半段的另一组：

1. `on_header_double_click`
2. `sort_column`

最终生效的是后定义版本。

这意味着：

1. 前半段修复逻辑如果没有同步到后半段，可能被覆盖
2. 维护者很容易误判“自己改的代码为什么不生效”

证据：

1. [主版本前段 sort_column](file:///Users/firewell/bin/media/media_library.py#L684-L724)
2. [主版本后段 sort_column](file:///Users/firewell/bin/media/media_library.py#L6422-L6435)
3. [fixed 前段 sort_column](file:///Users/firewell/bin/media/media_library_fixed.py#L792-L827)
4. [fixed 后段 sort_column](file:///Users/firewell/bin/media/media_library_fixed.py#L6523-L6536)

### 4.2 `create_gui()` 与 `recreate_treeview()` 仍有大量重复代码

虽然 `fixed` 抽出了 `_configure_treeview_columns()`，但仍有大量重复：

1. `Treeview` 创建
2. 滚动条创建
3. 事件绑定
4. `_last_column_widths` 初始化

这意味着：

1. 当前问题修复后仍可能在未来再次出现“首创正常、重建异常”的回归
2. 若要长期维护，最好再做一次 UI 初始化抽取

## 5. 回灌分类建议

### 5.1 建议直接回灌

以下改动建议直接回灌主版本：

1. `stretch=False`
2. 统一 `on_button_release`
3. 列宽变化后按真实宽度保存
4. `swap_columns()` / `move_column()` / `recreate_treeview()` / `sort_column()` / `on_closing()` 前同步当前列宽
5. 默认列配置深拷贝
6. 脏配置清洗逻辑

原因：

1. 这些都直接服务于修复列宽和状态持久化问题
2. 风险可控
3. 收益明确

### 5.2 需要确认后再回灌

以下改动需要产品/使用习惯确认后再决定是否回灌：

1. 排序从“单击表头”改成“双击表头”
2. 配置文件是否继续隔离

原因：

1. 这是用户可感知的交互变化
2. 不是纯内部修复

### 5.3 暂不建议直接照搬

以下状态不建议“整块复制”：

1. `fixed` 中与表格初始化相关的大段重复代码
2. 前后两套 `sort_column()` / `on_header_double_click()` 重复定义的现状

原因：

1. 这些属于结构债，不是回灌目标
2. 直接照搬只会把技术债继续带回主版本

## 6. 合并回主版本的推荐策略

建议按下面顺序回灌，而不是直接整文件替换：

1. 回灌列配置深拷贝和清洗逻辑
2. 回灌 `Treeview` 统一列初始化和 `stretch=False`
3. 回灌统一 `ButtonRelease` 和列宽同步逻辑
4. 回灌关闭窗口前同步列宽逻辑
5. 单独评估“单击排序改双击排序”是否接受
6. 最后再处理排序相关重复定义，做一次结构清理

## 7. 最终结论

`fixed` 版本除了修好列宽问题，还带来了若干真实的行为变化：

1. 排序触发方式变化
2. 配置文件隔离
3. 配置容错增强
4. 关闭时保存语义增强

如果后续要把 `fixed` 合并回主版本，最安全的方式不是整文件覆盖，而是按“修复机制”逐项回灌，并明确区分：

1. 哪些是必须回灌的 bug fix
2. 哪些是需要确认的 UX 变化
3. 哪些是当前仍应继续重构的技术债
