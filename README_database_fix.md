# 数据库修复工具使用说明

## 概述

`fix_database.py` 是一个专门用于修复媒体库数据库缺失列问题的工具脚本。当媒体库程序因为数据库结构不匹配而出现错误时，可以使用此工具自动检查和修复数据库结构。

## 功能特性

- **自动备份**: 修复前自动备份现有数据库
- **智能检测**: 自动检测缺失的数据库列
- **安全修复**: 只添加缺失的列，不会删除现有数据
- **完整日志**: 详细显示修复过程和结果
- **表结构验证**: 显示修复后的完整表结构

## 使用方法

### 基本使用

```bash
python fix_database.py
```

### 运行环境要求

- Python 3.6+
- sqlite3 模块（Python标准库）
- 脚本需要在媒体库项目根目录下运行

## 修复的问题类型

### 1. 缺失列错误
当程序报告类似以下错误时：
```
not enough values to unpack (expected 20, got 16)
```

### 2. 数据库列名错误
当程序报告类似以下错误时：
```
no such column: file_created_time
no such column: source_folder
no such column: is_nas_online
```

### 3. 插入数据失败
当程序报告类似以下错误时：
```
table videos has no column named xxx
```

## 数据库表结构

修复后的 `videos` 表包含以下22个列：

| 序号 | 列名 | 类型 | 说明 |
|------|------|------|------|
| 1 | id | INTEGER PRIMARY KEY | 主键，自增 |
| 2 | file_path | TEXT NOT NULL | 文件路径，唯一 |
| 3 | file_name | TEXT NOT NULL | 文件名 |
| 4 | file_size | INTEGER | 文件大小 |
| 5 | file_hash | TEXT | 文件MD5哈希 |
| 6 | title | TEXT | 视频标题 |
| 7 | description | TEXT | 视频描述 |
| 8 | genre | TEXT | 视频类型 |
| 9 | year | INTEGER | 年份 |
| 10 | rating | REAL | 评分 |
| 11 | stars | INTEGER | 星级评价 |
| 12 | tags | TEXT | 标签 |
| 13 | nas_path | TEXT | NAS路径 |
| 14 | is_nas_online | BOOLEAN | NAS在线状态 |
| 15 | created_at | TIMESTAMP | 创建时间 |
| 16 | updated_at | TIMESTAMP | 更新时间 |
| 17 | thumbnail_data | BLOB | 缩略图数据 |
| 18 | thumbnail_path | TEXT | 缩略图路径 |
| 19 | duration | INTEGER | 视频时长 |
| 20 | resolution | TEXT | 分辨率 |
| 21 | file_created_time | TIMESTAMP | 文件创建时间 |
| 22 | source_folder | TEXT | 源文件夹 |

## 安全特性

- **自动备份**: 修复前会自动创建数据库备份文件
- **只读检查**: 首先检查表结构，不会立即修改
- **增量修复**: 只添加缺失的列，保留所有现有数据
- **错误处理**: 遇到错误时会显示详细信息并安全退出

## 备份文件

备份文件命名格式：`media_library.db.backup_YYYYMMDD_HHMMSS`

例如：`media_library.db.backup_20250810_070922`

## 故障排除

### 1. 权限错误
确保脚本有读写数据库文件的权限

### 2. 数据库锁定
确保媒体库程序已关闭，没有其他进程在使用数据库

### 3. 磁盘空间不足
确保有足够的磁盘空间进行备份和修复操作

## 注意事项

1. **运行前关闭媒体库程序**：避免数据库锁定冲突
2. **检查备份**：修复前会自动备份，如有问题可以恢复
3. **定期运行**：当程序更新后，可能需要重新运行修复脚本
4. **保留备份**：建议保留几个最近的备份文件

## 版本历史

- v1.0: 初始版本，支持基本的列缺失修复
- 支持自动备份和完整的表结构检查
- 支持创建辅助表（folders, tags）