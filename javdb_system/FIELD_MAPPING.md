# JAVDB 字段映射文档

## 1. 爬虫输出字段 → 中间数据字典字段

爬虫 `javdb_crawler_single.py` 输出 JSON 包含以下字段：

| JSON 字段 | 类型 | 说明 |
|-----------|------|------|
| `title` | str | 视频标题 |
| `video_id` | str | 番号（如 IPX-177） |
| `detail_url` | str | JAVDB 详情页 URL |
| `release_date` | str | 发行日期（格式: YYYY-MM-DD） |
| `duration` | str | 时长（如 "120分钟"） |
| `rating` | str/float | 评分（如 "8.5" 或 "N/A"） |
| `tags` | list[str] | 标签列表 |
| `actors` | list[dict] | 演员列表，格式: `[{"name": "演员名", "link": "URL"}]` |
| `studio` | str | 制作商 |
| `cover_image_url` | str | 封面图片 URL |
| `local_image_path` | str | 本地封面图片路径 |
| `magnet_links` | list[dict] | 磁力链接列表 |
| `preview_images` | list[str] | 预览图 URL 列表 |
| `series` | str | 系列名称 |
| `error` | str | 错误信息（失败时存在） |

## 2. 中间字典 → 数据库 javdb_info 表字段映射

`save_javdb_info_to_db()` 函数中：

| 爬虫数据字典 Key | 数据库列名 | SQLite 类型 | 说明 |
|---|---|---|---|
| `video_id` | `javdb_code` | TEXT | 番号 |
| `detail_url` | `javdb_url` | TEXT | JAVDB 详情页链接 |
| `title` | `javdb_title` | TEXT | 视频标题 |
| `release_date` | `release_date` | TEXT | 发行日期 |
| `duration` | `duration` | TEXT | 时长 |
| `studio` | `studio` | TEXT | 制作商 |
| `rating` | `score` | REAL | 评分（转换为 float） |
| `cover_image_url` | `cover_url` | TEXT | 封面图 URL |
| `local_image_path` | `local_cover_path` | TEXT | 本地封面路径 |
| (封面二进制) | `cover_image_data` | BLOB | 封面图片二进制数据 |
| `magnet_links` | `magnet_links` | TEXT | JSON 序列化的磁力链接列表 |
| — | `video_id` | INTEGER | 外键，关联 videos.id |
| — | `created_at` | TIMESTAMP | 创建时间 |
| — | `updated_at` | TIMESTAMP | 更新时间 |

## 3. 标签数据映射

标签存储在关联表中：

| 表 | 字段 | 说明 |
|---|---|---|
| `javdb_tags` | `id`, `tag_name`, `tag_type` | 标签主表，tag_name 唯一 |
| `javdb_info_tags` | `javdb_info_id`, `tag_id` | 多对多关联表 |

中间字典 `tags` (list[str]) → 处理流程:
1. 遍历 tags 列表
2. `INSERT OR IGNORE INTO javdb_tags (tag_name) VALUES (?)`
3. `INSERT OR IGNORE INTO javdb_info_tags (javdb_info_id, tag_id) VALUES (?, ?)`

## 4. 演员数据映射

| 表 | 字段 | 说明 |
|---|---|---|
| `actors` | `id`, `name`, `profile_url`, ... | 演员主表，name 唯一 |
| `video_actors` | `video_id`, `actor_id` | 多对多关联表 |

中间字典 `actors` (list[dict]) → 处理流程:
1. 遍历 actors 列表，取 `name`, `link`
2. `INSERT OR IGNORE INTO actors (name, profile_url) VALUES (?, ?)`
3. `INSERT OR IGNORE INTO video_actors (video_id, actor_id) VALUES (?, ?)`

## 5. 缓存与爬虫交互（所有汇总入口）

| 下载脚本 | 读取文件 | 备注 |
| :--- | :--- | :--- |
| **javdb_crawler_single.py** | `results/images/*.jpg` | 单番号下载 |
| 从 `detail_url` 解析到番号的 `$avcode.jpg` 名称 | 统一封面缓存目录 (results/images/) | 持久化下载 |

### 常用图片路径
- `results/images/` 封面库目录
- `local_image_path`: 图片下载后的本地路径
- `cover_image_data`: 存储在数据库 BLOB 字段
