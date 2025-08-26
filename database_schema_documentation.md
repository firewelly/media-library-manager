# 媒体库数据库结构文档

## 数据库概览

媒体库数据库包含8个主要表，用于管理视频文件、演员信息、标签系统和JAVDB数据。

## 表结构详细说明

### 1. videos 表（核心视频表）

**用途**: 存储视频文件的基本信息和元数据

| 字段名 | 数据类型 | 约束 | 说明 |
|--------|----------|------|------|
| id | INTEGER | PRIMARY KEY, AUTOINCREMENT | 主键，自增ID |
| file_path | TEXT | UNIQUE, NOT NULL | 文件完整路径，唯一 |
| file_name | TEXT | NOT NULL | 文件名 |
| file_size | INTEGER | | 文件大小（字节） |
| file_hash | TEXT | | 文件哈希值 |
| md5_hash | TEXT | | MD5哈希值 |
| title | TEXT | | 视频标题 |
| description | TEXT | | 视频描述 |
| genre | TEXT | | 视频类型/流派 |
| year | INTEGER | | 发行年份 |
| rating | REAL | | 评分 |
| stars | INTEGER | DEFAULT 0 | 星级评分 |
| tags | TEXT | | 标签（文本形式存储） |
| nas_path | TEXT | | NAS路径 |
| is_nas_online | BOOLEAN | DEFAULT 1 | NAS是否在线 |
| thumbnail_data | BLOB | | 缩略图二进制数据 |
| thumbnail_path | TEXT | | 缩略图文件路径 |
| duration | INTEGER | | 视频时长（秒） |
| resolution | TEXT | | 视频分辨率 |
| file_created_time | TIMESTAMP | | 文件创建时间 |
| source_folder | TEXT | | 源文件夹 |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 记录创建时间 |
| updated_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 记录更新时间 |

### 2. actors 表（演员表）

**用途**: 存储演员的详细信息

| 字段名 | 数据类型 | 约束 | 说明 |
|--------|----------|------|------|
| id | INTEGER | PRIMARY KEY, AUTOINCREMENT | 主键，自增ID |
| name | TEXT | UNIQUE, NOT NULL | 演员姓名（日文），唯一 |
| name_en | TEXT | | 演员英文名 |
| profile_url | TEXT | | 个人资料页面URL |
| avatar_url | TEXT | | 头像图片URL |
| local_avatar_path | TEXT | | 本地头像文件路径 |
| birth_date | TEXT | | 出生日期 |
| debut_date | TEXT | | 出道日期 |
| height | TEXT | | 身高 |
| measurements | TEXT | | 三围 |
| description | TEXT | | 个人描述 |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 记录创建时间 |
| updated_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 记录更新时间 |

### 3. video_actors 表（视频-演员关联表）

**用途**: 多对多关系表，连接视频和演员

| 字段名 | 数据类型 | 约束 | 说明 |
|--------|----------|------|------|
| id | INTEGER | PRIMARY KEY, AUTOINCREMENT | 主键，自增ID |
| video_id | INTEGER | NOT NULL, FK | 外键，关联videos.id |
| actor_id | INTEGER | NOT NULL, FK | 外键，关联actors.id |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 记录创建时间 |

**约束**: 
- UNIQUE(video_id, actor_id) - 防止重复关联
- ON DELETE CASCADE - 级联删除

### 4. javdb_info 表（JAVDB信息表）

**用途**: 存储从JAVDB爬取的视频详细信息

| 字段名 | 数据类型 | 约束 | 说明 |
|--------|----------|------|------|
| id | INTEGER | PRIMARY KEY, AUTOINCREMENT | 主键，自增ID |
| video_id | INTEGER | NOT NULL, FK | 外键，关联videos.id |
| javdb_code | TEXT | NOT NULL | JAVDB番号 |
| javdb_url | TEXT | | JAVDB页面URL |
| javdb_title | TEXT | | JAVDB标题 |
| release_date | TEXT | | 发行日期 |
| duration | TEXT | | 时长 |
| studio | TEXT | | 制作公司 |
| series | TEXT | | 系列名称 |
| rating | TEXT | | 评分（文本格式） |
| score | REAL | | 数值评分 |
| cover_url | TEXT | | 封面图片URL |
| local_cover_path | TEXT | | 本地封面文件路径 |
| cover_image_data | BLOB | | 封面图片二进制数据 |
| magnet_links | TEXT | | 磁力链接 |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 记录创建时间 |
| updated_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 记录更新时间 |

**约束**: 
- ON DELETE CASCADE - 级联删除

### 5. tags 表（标签表）

**用途**: 存储用户自定义标签

| 字段名 | 数据类型 | 约束 | 说明 |
|--------|----------|------|------|
| id | INTEGER | PRIMARY KEY, AUTOINCREMENT | 主键，自增ID |
| tag_name | TEXT | UNIQUE, NOT NULL | 标签名称，唯一 |
| tag_color | TEXT | DEFAULT '#007AFF' | 标签颜色 |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 记录创建时间 |

### 6. javdb_tags 表（JAVDB标签表）

**用途**: 存储从JAVDB获取的标签信息

| 字段名 | 数据类型 | 约束 | 说明 |
|--------|----------|------|------|
| id | INTEGER | PRIMARY KEY, AUTOINCREMENT | 主键，自增ID |
| tag_name | TEXT | UNIQUE, NOT NULL | 标签名称，唯一 |
| tag_type | TEXT | DEFAULT 'general' | 标签类型 |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 记录创建时间 |

### 7. javdb_info_tags 表（JAVDB信息-标签关联表）

**用途**: 多对多关系表，连接JAVDB信息和标签

| 字段名 | 数据类型 | 约束 | 说明 |
|--------|----------|------|------|
| id | INTEGER | PRIMARY KEY, AUTOINCREMENT | 主键，自增ID |
| javdb_info_id | INTEGER | NOT NULL, FK | 外键，关联javdb_info.id |
| tag_id | INTEGER | NOT NULL, FK | 外键，关联javdb_tags.id |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 记录创建时间 |

**约束**: 
- UNIQUE(javdb_info_id, tag_id) - 防止重复关联
- ON DELETE CASCADE - 级联删除

### 8. folders 表（文件夹表）

**用途**: 存储扫描的文件夹路径信息

| 字段名 | 数据类型 | 约束 | 说明 |
|--------|----------|------|------|
| id | INTEGER | PRIMARY KEY, AUTOINCREMENT | 主键，自增ID |
| folder_path | TEXT | UNIQUE, NOT NULL | 文件夹路径，唯一 |
| folder_type | TEXT | DEFAULT 'local' | 文件夹类型 |
| is_active | BOOLEAN | DEFAULT 1 | 是否激活 |
| device_name | TEXT | | 设备名称 |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 记录创建时间 |

## 数据库索引

为了提高查询性能，数据库创建了以下索引：

- `idx_actors_name` - actors表的name字段
- `idx_javdb_info_video_id` - javdb_info表的video_id字段
- `idx_javdb_info_code` - javdb_info表的javdb_code字段
- `idx_video_actors_video_id` - video_actors表的video_id字段
- `idx_video_actors_actor_id` - video_actors表的actor_id字段
- `idx_javdb_tags_name` - javdb_tags表的tag_name字段
- `idx_javdb_info_tags_javdb_info_id` - javdb_info_tags表的javdb_info_id字段
- `idx_javdb_info_tags_tag_id` - javdb_info_tags表的tag_id字段

## 表关系说明

### 主要关系

1. **videos ↔ javdb_info** (1:1)
   - 一个视频对应一个JAVDB信息记录

2. **videos ↔ actors** (M:N)
   - 通过video_actors表实现多对多关系
   - 一个视频可以有多个演员，一个演员可以出演多个视频

3. **javdb_info ↔ javdb_tags** (M:N)
   - 通过javdb_info_tags表实现多对多关系
   - 一个JAVDB信息可以有多个标签，一个标签可以属于多个视频

### 数据流向

1. **视频扫描**: folders → videos
2. **JAVDB爬取**: videos → javdb_info → javdb_tags
3. **演员信息**: javdb_info → actors → video_actors
4. **用户标签**: 用户操作 → tags → videos.tags字段

## 特殊字段说明

### BLOB字段
- `videos.thumbnail_data`: 存储视频缩略图的二进制数据
- `javdb_info.cover_image_data`: 存储JAVDB封面图片的二进制数据

### 时间戳字段
- 所有表都包含`created_at`字段记录创建时间
- 部分表包含`updated_at`字段记录最后更新时间
- `videos.file_created_time`记录原始文件的创建时间

### 布尔字段
- `videos.is_nas_online`: 标识NAS设备是否在线
- `folders.is_active`: 标识文件夹是否处于活动状态

这个数据库设计支持完整的媒体库管理功能，包括文件管理、元数据存储、演员信息、标签系统和外部数据源集成。