# JavSP 复制功能修复报告

## 问题概述

JavSP复制功能存在多个关键bug，导致复制操作失败。主要问题包括：

1. **参数不匹配**: `copy_single`函数调用时参数顺序错误
2. **列名获取错误**: 使用`cursor.description`获取列名，但游标状态不一致导致`NoneType`错误
3. **变量未定义**: `resolve_copy_conflict`函数中`parent`变量未定义

## 修复详情

### 1. 修复参数不匹配问题

**问题**: 测试脚本中调用`copy_single`时参数顺序错误
```python
# 错误的调用
copy_single(video_id, file_path, target_dir)

# 正确的调用
copy_single(cursor, conn, file_path, video_id, target_dir)
```

**解决方案**: 更新测试脚本，确保参数顺序正确，包含所有必需的参数。

### 2. 修复列名获取错误

**问题**: 代码中混用两种不同的列名获取方式，导致`NoneType`错误
```python
# 有问题的代码
javdb_column_names = [col[1] for col in cursor.description]  # cursor.description可能为None
```

**解决方案**: 统一使用`PRAGMA table_info`获取列名信息
```python
# 修复后的代码
cursor.execute("PRAGMA table_info(javdb_info)")
javdb_columns_info = cursor.fetchall()
javdb_column_names = [col[1] for col in javdb_columns_info]
```

### 3. 修复变量未定义问题

**问题**: `resolve_copy_conflict`函数中`parent`变量未定义

**解决方案**: 在函数中添加缺失的变量定义
```python
base, ext = os.path.splitext(os.path.basename(dest_file_path))
parent = os.path.dirname(dest_file_path)  # 添加这行
counter = 1
```

## 功能特性

修复后的JavSP复制功能支持以下特性：

### 1. 智能冲突解决
- 自动检测目标位置是否已存在同名文件
- 支持文件重命名（添加序号后缀）
- 支持合并模式（复制到已存在目录）

### 2. 完整的附属文件处理
- 自动复制NFO文件：`{basename}.nfo`
- 复制缩略图：`{basename}-thumb.jpg`
- 复制海报：`poster.jpg`
- 复制背景图：`fanart.jpg`
- 复制extrafanart目录及其内容

### 3. 数据库记录完整复制
- 复制videos表记录（更新路径和大小信息）
- 复制演员关联（video_actors表）
- 复制JAVDB信息（javdb_info表）
- 复制JAVDB标签关联（javdb_info_tags表）

### 4. 路径处理
- 支持相对路径计算（基于源根目录）
- 智能处理特殊目录（如"#整理完成"）
- 保持原始目录结构

## 测试结果

### 测试用例1: 基本复制功能
- ✅ 复制成功到新位置
- ✅ 数据库记录创建正确
- ✅ 演员关联复制正确
- ✅ JAVDB信息复制正确
- ✅ JAVDB标签关联复制正确

### 测试用例2: 冲突解决
- ✅ 检测到已存在文件时自动重命名
- ✅ 合并模式下正确复制到已存在目录
- ✅ 附属文件正确处理

### 测试用例3: 附属文件处理
- ✅ NFO文件正确复制
- ✅ 缩略图正确复制
- ✅ 海报文件正确复制
- ✅ 背景图正确复制
- ✅ extrafanart目录完整复制

## 使用示例

```python
import sqlite3
from utils.javsp_copy import copy_single

# 连接到数据库
conn = sqlite3.connect('media_library.db')
cursor = conn.cursor()

# 复制视频
result = copy_single(
    cursor=cursor,
    conn=conn,
    old_file_path='/path/to/source/video.mp4',
    video_id=12345,
    target_library_path='/path/to/target/library'
)

if result['ok']:
    print(f"复制成功！新视频ID: {result['new_video_id']}")
    print(f"最终路径: {result['final_path']}")
else:
    print(f"复制失败: {result['error']}")

conn.close()
```

## 文件结构

修复后的相关文件：
- `utils/javsp_copy.py` - 主要的复制功能实现
- `test_copy_function.py` - 基础功能测试
- `test_copy_comprehensive.py` - 综合测试（包含冲突解决）
- `test_copy_with_sidecar.py` - 附属文件处理测试

## 总结

JavSP复制功能现已完全修复并正常工作。所有关键bug都已解决，功能完整测试通过。该功能现在可以可靠地用于媒体库的迁移和备份操作。