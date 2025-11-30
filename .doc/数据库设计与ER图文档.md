# 数据库设计与ER图文档
 - 版本: 开发版
 - 最后更新: 2025-11-29
 - 适用系统: Windows/macOS/Linux

## 1. 数据库概述

本媒体库管理系统采用关系型数据库设计，使用SQLite作为数据库引擎。数据库设计遵循第三范式，确保数据的一致性和完整性。数据库包含8个主要表，用于存储视频信息、演员信息、标签信息以及它们之间的关联关系。

## 2. 数据库表结构

### 2.1 videos表

**用途**：存储视频文件的基本信息和元数据

| 字段名 | 数据类型 | 约束 | 说明 |
|--------|----------|------|------|
| id | INTEGER | PK, AI | 主键，自增 |
| file_path | TEXT | UNIQUE, NOT NULL | 文件路径，唯一 |
| file_name | TEXT | NOT NULL | 文件名 |
| file_size | INTEGER | - | 文件大小（字节） |
| file_hash | TEXT | - | 文件MD5哈希值 |
| title | TEXT | - | 视频标题 |
| description | TEXT | - | 视频描述 |
| genre | TEXT | - | 视频类型 |
| year | INTEGER | - | 发行年份 |
| rating | REAL | - | 评分 |
| stars | INTEGER | DEFAULT 0 | 星级评分 |
| tags | TEXT | - | 标签（逗号分隔） |
| nas_path | TEXT | - | NAS路径 |
| is_nas_online | BOOLEAN | DEFAULT 1 | NAS是否在线 |
| thumbnail_data | BLOB | - | 缩略图二进制数据 |
| thumbnail_path | TEXT | - | 缩略图路径 |
| duration | INTEGER | - | 视频时长（秒） |
| resolution | TEXT | - | 视频分辨率 |
| created_at | TIMESTAMP | - | 创建时间 |
| updated_at | TIMESTAMP | - | 更新时间 |
| file_created_time | TIMESTAMP | - | 文件创建时间 |

### 2.2 actors表

**用途**：存储演员的详细信息

| 字段名 | 数据类型 | 约束 | 说明 |
|--------|----------|------|------|
| id | INTEGER | PK, AI | 主键，自增 |
| name | TEXT | UNIQUE, NOT NULL | 演员名称，唯一 |
| name_en | TEXT | - | 英文名 |
| name_zh_tw | TEXT | - | 繁体中文译名 |
| common_name | TEXT | - | 常用名 |
| aliases | TEXT | - | 别名（逗号分隔） |
| profile_url | TEXT | - | 个人资料URL |
| avatar_url | TEXT | - | 头像URL |
| local_avatar_path | TEXT | - | 本地头像路径 |
| birth_date | TEXT | - | 出生日期 |
| debut_date | TEXT | - | 出道日期 |
| height | TEXT | - | 身高 |
| measurements | TEXT | - | 三围 |
| description | TEXT | - | 描述 |
| last_crawled_at | TEXT | - | 最后爬取时间 |
| crawl_count | INTEGER | DEFAULT 0 | 爬取次数 |
| crawl_status | TEXT | DEFAULT 'pending' | 爬取状态 |
| created_at | TIMESTAMP | - | 创建时间 |
| updated_at | TIMESTAMP | - | 更新时间 |

### 2.3 video_actors表

**用途**：视频与演员的多对多关系表

| 字段名 | 数据类型 | 约束 | 说明 |
|--------|----------|------|------|
| id | INTEGER | PK, AI | 主键，自增 |
| video_id | INTEGER | FK | 关联videos表id |
| actor_id | INTEGER | FK | 关联actors表id |
| created_at | TIMESTAMP | - | 创建时间 |

### 2.4 javdb_info表

**用途**：存储JAVDB网站的视频信息

| 字段名 | 数据类型 | 约束 | 说明 |
|--------|----------|------|------|
| id | INTEGER | PK, AI | 主键，自增 |
| video_id | INTEGER | FK, NOT NULL | 关联videos表id |
| javdb_code | TEXT | NOT NULL | JAVDB番号 |
| javdb_url | TEXT | - | JAVDB页面URL |
| javdb_title | TEXT | - | JAVDB标题 |
| release_date | TEXT | - | 发行日期 |
| duration | TEXT | - | 时长 |
| studio | TEXT | - | 制作商 |
| series | TEXT | - | 系列 |
| rating | TEXT | - | 评级 |
| score | REAL | - | 评分 |
| cover_url | TEXT | - | 封面URL |
| local_cover_path | TEXT | - | 本地封面路径 |
| cover_image_data | BLOB | - | 封面二进制数据 |
| magnet_links | TEXT | - | 磁力链接（逗号分隔） |
| created_at | TIMESTAMP | - | 创建时间 |
| updated_at | TIMESTAMP | - | 更新时间 |

### 2.5 tags表

**用途**：存储系统标签

| 字段名 | 数据类型 | 约束 | 说明 |
|--------|----------|------|------|
| id | INTEGER | PK, AI | 主键，自增 |
| tag_name | TEXT | UNIQUE, NOT NULL | 标签名称，唯一 |
| tag_color | TEXT | DEFAULT '#007AFF' | 标签颜色 |
| created_at | TIMESTAMP | - | 创建时间 |

### 2.6 javdb_tags表

**用途**：存储JAVDB标签

| 字段名 | 数据类型 | 约束 | 说明 |
|--------|----------|------|------|
| id | INTEGER | PK, AI | 主键，自增 |
| tag_name | TEXT | UNIQUE, NOT NULL | 标签名称，唯一 |
| tag_type | TEXT | DEFAULT 'general' | 标签类型 |
| created_at | TIMESTAMP | - | 创建时间 |

### 2.7 javdb_info_tags表

**用途**：JAVDB信息与标签的多对多关系表

| 字段名 | 数据类型 | 约束 | 说明 |
|--------|----------|------|------|
| id | INTEGER | PK, AI | 主键，自增 |
| javdb_info_id | INTEGER | FK | 关联javdb_info表id |
| tag_id | INTEGER | FK | 关联javdb_tags表id |
| created_at | TIMESTAMP | - | 创建时间 |

### 2.8 folders表

**用途**：存储文件夹信息

| 字段名 | 数据类型 | 约束 | 说明 |
|--------|----------|------|------|
| id | INTEGER | PK, AI | 主键，自增 |
| folder_path | TEXT | UNIQUE, NOT NULL | 文件夹路径，唯一 |
| folder_type | TEXT | DEFAULT 'local' | 文件夹类型（local/nas） |
| is_active | BOOLEAN | DEFAULT 1 | 是否激活 |
| device_name | TEXT | - | 设备名称 |

## 3. 数据库索引设计

为了提高查询性能，数据库设计了以下索引：

1. **videos表索引**
   - `file_path`：唯一索引，用于快速查找视频文件
   - `file_hash`：普通索引，用于文件去重
   - `title`：普通索引，用于标题搜索

2. **actors表索引**
   - `name`：唯一索引，用于快速查找演员
   - `common_name`：普通索引，用于常用名搜索

3. **video_actors表索引**
   - `video_id`：普通索引，用于查找视频的所有演员
   - `actor_id`：普通索引，用于查找演员的所有视频
   - `(video_id, actor_id)`：复合唯一索引，防止重复关联

4. **javdb_info表索引**
   - `video_id`：唯一索引，确保每个视频只有一个JAVDB信息
   - `javdb_code`：普通索引，用于番号搜索

5. **javdb_info_tags表索引**
   - `javdb_info_id`：普通索引，用于查找JAVDB信息的所有标签
   - `tag_id`：普通索引，用于查找标签的所有JAVDB信息
   - `(javdb_info_id, tag_id)`：复合唯一索引，防止重复关联

## 4. 表关系说明

### 4.1 一对一关系

- **videos ↔ javdb_info**：一个视频对应一个JAVDB信息，一个JAVDB信息对应一个视频

### 4.2 一对多关系

- **videos → video_actors**：一个视频可以有多个演员
- **actors → video_actors**：一个演员可以出演多个视频
- **javdb_info → javdb_info_tags**：一个JAVDB信息可以有多个标签
- **javdb_tags → javdb_info_tags**：一个标签可以关联多个JAVDB信息

### 4.3 多对多关系

- **videos ↔ actors**：通过video_actors表实现多对多关系
- **javdb_info ↔ javdb_tags**：通过javdb_info_tags表实现多对多关系

## 5. ER图说明

ER图（实体关系图）直观地展示了数据库表之间的关系：

1. **实体表示**：
   - 每个表用一个矩形框表示
   - 主键字段用🔑符号标识
   - 外键字段用🔗符号标识
   - 时间戳字段用斜体表示

2. **关系表示**：
   - 一对一关系用1:1表示
   - 一对多关系用1:M表示
   - 多对多关系通过中间表实现

3. **特殊标记**：
   - 关系表（video_actors, javdb_info_tags）用浅黄色背景标识
   - 必填字段用NOT NULL约束标识
   - 唯一字段用UNIQUE约束标识

## 6. 数据流向

1. **视频信息流向**：
   - 视频文件 → videos表（基本信息）
   - videos表 → javdb_info表（JAVDB信息）
   - videos表 → video_actors表（演员关联）
   - javdb_info表 → javdb_info_tags表（标签关联）

2. **演员信息流向**：
   - 演员信息 → actors表（基本信息）
   - actors表 → video_actors表（视频关联）

3. **标签信息流向**：
   - 系统标签 → tags表（系统标签）
   - JAVDB标签 → javdb_tags表（JAVDB标签）
   - javdb_tags表 → javdb_info_tags表（JAVDB信息关联）

## 7. 特殊字段说明

1. **BLOB字段**：
   - `videos.thumbnail_data`：存储视频缩略图的二进制数据
   - `javdb_info.cover_image_data`：存储JAVDB封面的二进制数据

2. **时间戳字段**：
   - `created_at`：记录创建时间
   - `updated_at`：记录最后更新时间
   - `file_created_time`：记录文件创建时间

3. **布尔字段**：
   - `videos.is_nas_online`：标识NAS是否在线
   - `folders.is_active`：标识文件夹是否激活

4. **JSON格式字段**：
   - `actors.aliases`：存储演员别名，使用逗号分隔
   - `videos.tags`：存储视频标签，使用逗号分隔
   - `javdb_info.magnet_links`：存储磁力链接，使用逗号分隔

## 8. 数据库优化建议

1. **查询优化**：
   - 为常用查询条件创建适当的索引
   - 避免使用SELECT *，只查询需要的字段
   - 对于大表，考虑使用分页查询

2. **存储优化**：
   - 对于大文件（如缩略图、封面），考虑使用文件系统存储，数据库只保存路径
   - 定期清理过期或无用的数据

3. **性能优化**：
   - 对于频繁更新的表，考虑使用适当的缓存策略
   - 对于大数据量操作，使用事务处理

## 9. 数据库维护

1. **备份策略**：
   - 定期备份数据库文件
   - 保留多个版本的备份

2. **恢复策略**：
   - 测试备份文件的恢复流程
   - 制定灾难恢复计划

3. **监控策略**：
   - 监控数据库大小和增长趋势
   - 监控查询性能

## 10. 数据库安全

1. **访问控制**：
   - 限制数据库文件的访问权限
   - 使用适当的用户权限管理

2. **数据加密**：
   - 考虑对敏感数据进行加密存储
   - 使用安全的连接方式

3. **审计日志**：
   - 记录重要的数据库操作
   - 定期审查日志文件

## 11. 扩展性考虑

1. **水平扩展**：
   - 考虑数据分片策略
   - 设计支持分布式查询的表结构

2. **垂直扩展**：
   - 预留字段用于未来功能扩展
   - 设计灵活的元数据存储结构

3. **功能扩展**：
   - 考虑添加用户管理功能
   - 考虑添加播放历史记录功能

## 12. 版本控制

1. **数据库版本**：
   - 使用版本号标识数据库结构变更
   - 维护数据库变更日志

2. **迁移策略**：
   - 设计数据库升级脚本
   - 支持降级操作

## 13. 总结

本数据库设计充分考虑了媒体库管理系统的需求，通过合理的表结构设计和关系建立，实现了视频信息、演员信息、标签信息的有效管理。数据库设计遵循规范化原则，确保数据的一致性和完整性，同时通过索引优化提高了查询性能。ER图直观地展示了表之间的关系，便于理解和维护。未来可以根据系统需求的变化，对数据库进行相应的扩展和优化。
