# 系统API文档

## 1. 简介

本文档详细描述了媒体库管理系统的API接口，包括数据库操作、视频管理、演员管理、标签系统等核心功能的接口定义。这些API主要用于系统内部模块间的通信，也可以用于第三方应用集成。

## 2. API设计原则

### 2.1 RESTful设计

系统API遵循RESTful设计原则，使用HTTP方法表示操作类型：

- GET：获取资源
- POST：创建资源
- PUT：更新资源
- DELETE：删除资源

### 2.2 统一响应格式

所有API响应使用统一的JSON格式：

```json
{
  "success": true,
  "message": "操作成功",
  "data": {},
  "error": null
}
```

### 2.3 错误处理

系统使用标准HTTP状态码表示操作结果：

- 200：操作成功
- 201：创建成功
- 400：请求参数错误
- 401：未授权
- 404：资源不存在
- 500：服务器内部错误

## 3. 数据库API

### 3.1 数据库连接

#### 3.1.1 初始化数据库连接

```python
# 初始化数据库连接
db_manager = DatabaseManager(db_path="media.db")
```

#### 3.1.2 获取数据库连接

```python
# 获取数据库连接
connection = db_manager.get_connection()
```

#### 3.1.3 关闭数据库连接

```python
# 关闭数据库连接
db_manager.close_connection()
```

### 3.2 数据库操作

#### 3.2.1 执行SQL查询

```python
# 执行SQL查询
results = db_manager.execute_query(
    "SELECT * FROM videos WHERE title LIKE ?",
    ["%关键词%"]
)
```

#### 3.2.2 执行SQL更新

```python
# 执行SQL更新
affected_rows = db_manager.execute_update(
    "UPDATE videos SET rating = ? WHERE id = ?",
    [5, 1]
)
```

#### 3.2.3 执行事务

```python
# 执行事务
with db_manager.transaction():
    db_manager.execute_update("INSERT INTO videos (...) VALUES (...)", [...])
    db_manager.execute_update("INSERT INTO video_actors (...) VALUES (...)", [...])
```

### 3.3 数据库维护

#### 3.3.1 优化数据库

```python
# 优化数据库
db_manager.optimize_database()
```

#### 3.3.2 备份数据库

```python
# 备份数据库
backup_path = db_manager.backup_database(backup_dir="backups")
```

#### 3.3.3 恢复数据库

```python
# 恢复数据库
db_manager.restore_database(backup_path="backups/media_backup_20230101.db")
```

## 4. 视频管理API

### 4.1 视频信息获取

#### 4.1.1 获取所有视频

```python
# 获取所有视频
videos = video_manager.get_all_videos()
```

#### 4.1.2 根据ID获取视频

```python
# 根据ID获取视频
video = video_manager.get_video_by_id(video_id=1)
```

#### 4.1.3 根据条件获取视频

```python
# 根据条件获取视频
videos = video_manager.get_videos_by_condition(
    filters={"rating": 5, "year": 2023},
    sort_by="title",
    sort_order="asc",
    limit=10,
    offset=0
)
```

### 4.2 视频信息更新

#### 4.2.1 更新视频信息

```python
# 更新视频信息
video_manager.update_video(
    video_id=1,
    updates={
        "title": "新标题",
        "rating": 5,
        "tags": ["标签1", "标签2"]
    }
)
```

#### 4.2.2 批量更新视频

```python
# 批量更新视频
video_manager.batch_update_videos(
    video_ids=[1, 2, 3],
    updates={"rating": 5}
)
```

### 4.3 视频文件操作

#### 4.3.1 添加视频文件

```python
# 添加视频文件
video_id = video_manager.add_video_file(
    file_path="/path/to/video.mp4",
    title="视频标题",
    metadata={"duration": 3600, "resolution": "1920x1080"}
)
```

#### 4.3.2 删除视频文件

```python
# 删除视频文件
video_manager.delete_video_file(video_id=1, delete_file=True)
```

#### 4.3.3 移动视频文件

```python
# 移动视频文件
video_manager.move_video_file(
    video_id=1,
    new_path="/new/path/to/video.mp4"
)
```

### 4.4 视频分析

#### 4.4.1 分析视频元数据

```python
# 分析视频元数据
metadata = video_manager.analyze_video_metadata(video_id=1)
```

#### 4.4.2 生成视频封面

```python
# 生成视频封面
cover_path = video_manager.generate_video_cover(
    video_id=1,
    output_dir="/path/to/covers"
)
```

#### 4.4.3 批量分析视频

```python
# 批量分析视频
results = video_manager.batch_analyze_videos(
    video_ids=[1, 2, 3],
    include_metadata=True,
    include_cover=True
)
```

## 5. 演员管理API

### 5.1 演员信息获取

#### 5.1.1 获取所有演员

```python
# 获取所有演员
actors = actor_manager.get_all_actors()
```

#### 5.1.2 根据ID获取演员

```python
# 根据ID获取演员
actor = actor_manager.get_actor_by_id(actor_id=1)
```

#### 5.1.3 根据名称获取演员

```python
# 根据名称获取演员
actor = actor_manager.get_actor_by_name(name="演员名称")
```

### 5.2 演员信息更新

#### 5.2.1 更新演员信息

```python
# 更新演员信息
actor_manager.update_actor(
    actor_id=1,
    updates={
        "name": "新名称",
        "aliases": ["别名1", "别名2"],
        "profile": "演员简介"
    }
)
```

#### 5.2.2 批量更新演员

```python
# 批量更新演员
actor_manager.batch_update_actors(
    actor_ids=[1, 2, 3],
    updates={"profile": "更新简介"}
)
```

### 5.3 演员信息获取

#### 5.3.1 获取演员信息

```python
# 获取演员信息
actor_info = actor_manager.fetch_actor_info(actor_id=1)
```

#### 5.3.2 批量获取演员信息

```python
# 批量获取演员信息
results = actor_manager.batch_fetch_actor_info(
    actor_ids=[1, 2, 3]
)
```

### 5.4 演员作品管理

#### 5.4.1 获取演员作品

```python
# 获取演员作品
videos = actor_manager.get_actor_videos(actor_id=1)
```

#### 5.4.2 添加演员到视频

```python
# 添加演员到视频
actor_manager.add_actor_to_video(
    actor_id=1,
    video_id=1
)
```

#### 5.4.3 从视频中移除演员

```python
# 从视频中移除演员
actor_manager.remove_actor_from_video(
    actor_id=1,
    video_id=1
)
```

## 6. 标签系统API

### 6.1 标签管理

#### 6.1.1 获取所有标签

```python
# 获取所有标签
tags = tag_manager.get_all_tags()
```

#### 6.1.2 创建标签

```python
# 创建标签
tag_id = tag_manager.create_tag(
    name="标签名称",
    color="#FF0000",
    description="标签描述"
)
```

#### 6.1.3 更新标签

```python
# 更新标签
tag_manager.update_tag(
    tag_id=1,
    updates={
        "name": "新标签名称",
        "color="#00FF00"
    }
)
```

#### 6.1.4 删除标签

```python
# 删除标签
tag_manager.delete_tag(tag_id=1)
```

### 6.2 视频标签管理

#### 6.2.1 获取视频标签

```python
# 获取视频标签
tags = tag_manager.get_video_tags(video_id=1)
```

#### 6.2.2 添加标签到视频

```python
# 添加标签到视频
tag_manager.add_tag_to_video(
    tag_id=1,
    video_id=1
)
```

#### 6.2.3 从视频中移除标签

```python
# 从视频中移除标签
tag_manager.remove_tag_from_video(
    tag_id=1,
    video_id=1
)
```

### 6.3 标签自动生成

#### 6.3.1 自动生成标签

```python
# 自动生成标签
tags = tag_manager.auto_generate_tags(video_id=1)
```

#### 6.3.2 批量自动生成标签

```python
# 批量自动生成标签
results = tag_manager.batch_auto_generate_tags(
    video_ids=[1, 2, 3]
)
```

## 7. JAVDB信息API

### 7.1 JAVDB信息获取

#### 7.1.1 根据番号获取信息

```python
# 根据番号获取信息
javdb_info = javdb_manager.get_info_by_code(code="ABC-123")
```

#### 7.1.2 获取视频JAVDB信息

```python
# 获取视频JAVDB信息
javdb_info = javdb_manager.get_video_javdb_info(video_id=1)
```

#### 7.1.3 批量获取JAVDB信息

```python
# 批量获取JAVDB信息
results = javdb_manager.batch_get_javdb_info(
    video_ids=[1, 2, 3]
)
```

### 7.2 JAVDB信息更新

#### 7.2.1 更新视频JAVDB信息

```python
# 更新视频JAVDB信息
javdb_manager.update_video_javdb_info(
    video_id=1,
    javdb_info={
        "code": "ABC-123",
        "title": "标题",
        "release_date": "2023-01-01",
        "rating": 8.5
    }
)
```

#### 7.2.2 批量更新JAVDB信息

```python
# 批量更新JAVDB信息
javdb_manager.batch_update_javdb_info(
    updates=[
        {"video_id": 1, "javdb_info": {...}},
        {"video_id": 2, "javdb_info": {...}}
    ]
)
```

### 7.3 JAVDB标签管理

#### 7.3.1 获取JAVDB标签

```python
# 获取JAVDB标签
tags = javdb_manager.get_javdb_tags(video_id=1)
```

#### 7.3.2 添加JAVDB标签

```python
# 添加JAVDB标签
javdb_manager.add_javdb_tag(
    video_id=1,
    tag_name="标签名称"
)
```

#### 7.3.3 移除JAVDB标签

```python
# 移除JAVDB标签
javdb_manager.remove_javdb_tag(
    video_id=1,
    tag_name="标签名称"
)
```

## 8. 文件夹管理API

### 8.1 文件夹管理

#### 8.1.1 获取所有文件夹

```python
# 获取所有文件夹
folders = folder_manager.get_all_folders()
```

#### 8.1.2 添加文件夹

```python
# 添加文件夹
folder_id = folder_manager.add_folder(
    path="/path/to/folder",
    name="文件夹名称",
    folder_type="local"  # 或 "nas"
)
```

#### 8.1.3 更新文件夹

```python
# 更新文件夹
folder_manager.update_folder(
    folder_id=1,
    updates={
        "name": "新文件夹名称",
        "path": "/new/path/to/folder"
    }
)
```

#### 8.1.4 删除文件夹

```python
# 删除文件夹
folder_manager.delete_folder(folder_id=1)
```

### 8.2 文件夹扫描

#### 8.2.1 扫描文件夹

```python
# 扫描文件夹
results = folder_manager.scan_folder(
    folder_id=1,
    recursive=True,
    include_subfolders=True
)
```

#### 8.2.2 批量扫描文件夹

```python
# 批量扫描文件夹
results = folder_manager.batch_scan_folders(
    folder_ids=[1, 2, 3]
)
```

### 8.3 文件夹监控

#### 8.3.1 启用文件夹监控

```python
# 启用文件夹监控
folder_manager.enable_folder_monitoring(folder_id=1)
```

#### 8.3.2 禁用文件夹监控

```python
# 禁用文件夹监控
folder_manager.disable_folder_monitoring(folder_id=1)
```

## 9. 搜索API

### 9.1 基本搜索

#### 9.1.1 搜索视频

```python
# 搜索视频
videos = search_manager.search_videos(
    keyword="关键词",
    fields=["title", "actors", "tags"],
    limit=10,
    offset=0
)
```

#### 9.1.2 搜索演员

```python
# 搜索演员
actors = search_manager.search_actors(
    keyword="关键词",
    fields=["name", "aliases"],
    limit=10,
    offset=0
)
```

#### 9.1.3 搜索标签

```python
# 搜索标签
tags = search_manager.search_tags(
    keyword="关键词",
    fields=["name", "description"],
    limit=10,
    offset=0
)
```

### 9.2 高级搜索

#### 9.2.1 高级搜索视频

```python
# 高级搜索视频
videos = search_manager.advanced_search_videos(
    filters={
        "title": {"contains": "关键词"},
        "rating": {"min": 4, "max": 5},
        "year": {"min": 2020, "max": 2023},
        "actors": {"contains": ["演员1", "演员2"]},
        "tags": {"contains": ["标签1", "标签2"]}
    },
    sort_by="title",
    sort_order="asc",
    limit=10,
    offset=0
)
```

#### 9.2.2 保存搜索条件

```python
# 保存搜索条件
search_id = search_manager.save_search(
    name="我的搜索",
    search_type="video",
    search_params={
        "keyword": "关键词",
        "filters": {...},
        "sort_by": "title",
        "sort_order": "asc"
    }
)
```

#### 9.2.3 加载保存的搜索

```python
# 加载保存的搜索
search_params = search_manager.load_saved_search(search_id=1)
```

## 10. 导入导出API

### 10.1 导入功能

#### 10.1.1 从CSV导入

```python
# 从CSV导入
results = import_export_manager.import_from_csv(
    file_path="/path/to/data.csv",
    mapping={
        "title": "标题",
        "actors": "演员",
        "rating": "评分",
        "tags": "标签"
    }
)
```

#### 10.1.2 从Excel导入

```python
# 从Excel导入
results = import_export_manager.import_from_excel(
    file_path="/path/to/data.xlsx",
    sheet_name="Sheet1",
    mapping={
        "title": "标题",
        "actors": "演员",
        "rating": "评分",
        "tags": "标签"
    }
)
```

#### 10.1.3 从NFO导入

```python
# 从NFO导入
results = import_export_manager.import_from_nfo(
    directory_path="/path/to/nfo/files",
    recursive=True
)
```

### 10.2 导出功能

#### 10.2.1 导出为CSV

```python
# 导出为CSV
file_path = import_export_manager.export_to_csv(
    video_ids=[1, 2, 3],
    output_path="/path/to/output.csv",
    fields=["title", "actors", "rating", "tags"]
)
```

#### 10.2.2 导出为Excel

```python
# 导出为Excel
file_path = import_export_manager.export_to_excel(
    video_ids=[1, 2, 3],
    output_path="/path/to/output.xlsx",
    fields=["title", "actors", "rating", "tags"],
    sheet_name="Videos"
)
```

#### 10.2.3 导出为JSON

```python
# 导出为JSON
file_path = import_export_manager.export_to_json(
    video_ids=[1, 2, 3],
    output_path="/path/to/output.json",
    include_metadata=True
)
```

#### 10.2.4 导出为NFO

```python
# 导出为NFO
results = import_export_manager.export_to_nfo(
    video_ids=[1, 2, 3],
    output_dir="/path/to/output",
    include_cover=True
)
```

## 11. 批量操作API

### 11.1 批量选择

#### 11.1.1 根据条件选择视频

```python
# 根据条件选择视频
video_ids = batch_manager.select_videos_by_condition(
    filters={"rating": 5, "year": 2023}
)
```

#### 11.1.2 根据标签选择视频

```python
# 根据标签选择视频
video_ids = batch_manager.select_videos_by_tags(
    tag_names=["标签1", "标签2"],
    match_all=True
)
```

### 11.2 批量编辑

#### 11.2.1 批量更新视频信息

```python
# 批量更新视频信息
results = batch_manager.batch_update_videos(
    video_ids=[1, 2, 3],
    updates={
        "rating": 5,
        "tags": ["新标签1", "新标签2"]
    }
)
```

#### 11.2.2 批量添加演员

```python
# 批量添加演员
results = batch_manager.batch_add_actors(
    video_ids=[1, 2, 3],
    actor_ids=[1, 2]
)
```

#### 11.2.3 批量添加标签

```python
# 批量添加标签
results = batch_manager.batch_add_tags(
    video_ids=[1, 2, 3],
    tag_ids=[1, 2]
)
```

### 11.3 批量文件操作

#### 11.3.1 批量生成封面

```python
# 批量生成封面
results = batch_manager.batch_generate_covers(
    video_ids=[1, 2, 3],
    output_dir="/path/to/covers"
)
```

#### 11.3.2 批量重命名

```python
# 批量重命名
results = batch_manager.batch_rename_files(
    video_ids=[1, 2, 3],
    naming_pattern="{title}_{year}_{code}"
)
```

#### 11.3.3 批量移动文件

```python
# 批量移动文件
results = batch_manager.batch_move_files(
    video_ids=[1, 2, 3],
    target_dir="/path/to/target"
)
```

## 12. 配置API

### 12.1 系统配置

#### 12.1.1 获取系统配置

```python
# 获取系统配置
config = config_manager.get_system_config()
```

#### 12.1.2 更新系统配置

```python
# 更新系统配置
config_manager.update_system_config(
    updates={
        "proxy": {
            "enabled": True,
            "host": "127.0.0.1",
            "port": 1080
        },
        "crawler": {
            "request_interval": 2.0,
            "headless": True
        }
    }
)
```

### 12.2 GUI配置

#### 12.2.1 获取GUI配置

```python
# 获取GUI配置
gui_config = config_manager.get_gui_config()
```

#### 12.2.2 更新GUI配置

```python
# 更新GUI配置
config_manager.update_gui_config(
    updates={
        "columns": [
            {"title": "标题", "width": 300, "position": 0},
            {"title": "演员", "width": 150, "position": 1},
            {"title": "星级", "width": 100, "position": 2}
        ]
    }
)
```

### 12.3 用户配置

#### 12.3.1 获取用户配置

```python
# 获取用户配置
user_config = config_manager.get_user_config()
```

#### 12.3.2 更新用户配置

```python
# 更新用户配置
config_manager.update_user_config(
    updates={
        "theme": "dark",
        "language": "zh_CN",
        "default_sort": "title"
    }
)
```

## 13. 日志API

### 13.1 日志记录

#### 13.1.1 记录信息日志

```python
# 记录信息日志
log_manager.info("这是一条信息日志")
```

#### 13.1.2 记录警告日志

```python
# 记录警告日志
log_manager.warning("这是一条警告日志")
```

#### 13.1.3 记录错误日志

```python
# 记录错误日志
log_manager.error("这是一条错误日志")
```

### 13.2 日志查询

#### 13.2.1 查询日志

```python
# 查询日志
logs = log_manager.query_logs(
    level="ERROR",
    start_date="2023-01-01",
    end_date="2023-12-31",
    keyword="错误",
    limit=100,
    offset=0
)
```

#### 13.2.2 导出日志

```python
# 导出日志
file_path = log_manager.export_logs(
    output_path="/path/to/logs.csv",
    level="ERROR",
    start_date="2023-01-01",
    end_date="2023-12-31"
)
```

## 14. 事件系统API

### 14.1 事件订阅

#### 14.1.1 订阅事件

```python
# 定义事件处理函数
def on_video_added(video_id):
    print(f"视频已添加: {video_id}")

# 订阅事件
event_manager.subscribe("video_added", on_video_added)
```

#### 14.1.2 取消订阅

```python
# 取消订阅
event_manager.unsubscribe("video_added", on_video_added)
```

### 14.2 事件触发

#### 14.2.1 触发事件

```python
# 触发事件
event_manager.trigger("video_added", video_id=1)
```

#### 14.2.2 批量触发事件

```python
# 批量触发事件
events = [
    ("video_added", {"video_id": 1}),
    ("video_updated", {"video_id": 2}),
    ("video_deleted", {"video_id": 3})
]
event_manager.batch_trigger(events)
```

## 15. 插件系统API

### 15.1 插件管理

#### 15.1.1 加载插件

```python
# 加载插件
plugin_manager.load_plugin("/path/to/plugin.py")
```

#### 15.1.2 卸载插件

```python
# 卸载插件
plugin_manager.unload_plugin("plugin_name")
```

#### 15.1.3 获取已加载插件

```python
# 获取已加载插件
plugins = plugin_manager.get_loaded_plugins()
```

### 15.2 插件开发

#### 15.2.1 插件基类

```python
class BasePlugin:
    def __init__(self, name, version):
        self.name = name
        self.version = version
    
    def initialize(self, api):
        """初始化插件"""
        pass
    
    def on_video_added(self, video_id):
        """视频添加事件处理"""
        pass
    
    def on_video_updated(self, video_id):
        """视频更新事件处理"""
        pass
    
    def on_video_deleted(self, video_id):
        """视频删除事件处理"""
        pass
```

#### 15.2.2 插件示例

```python
class MyPlugin(BasePlugin):
    def __init__(self):
        super().__init__("MyPlugin", "1.0.0")
    
    def initialize(self, api):
        self.api = api
        self.api.subscribe("video_added", self.on_video_added)
    
    def on_video_added(self, video_id):
        video = self.api.get_video_by_id(video_id)
        print(f"新视频添加: {video['title']}")
```

## 16. 安全API

### 16.1 认证授权

#### 16.1.1 用户认证

```python
# 用户认证
token = security_manager.authenticate(
    username="用户名",
    password="密码"
)
```

#### 16.1.2 验证令牌

```python
# 验证令牌
is_valid = security_manager.verify_token(token)
```

#### 16.1.3 权限检查

```python
# 权限检查
has_permission = security_manager.check_permission(
    user_id=1,
    permission="video.delete"
)
```

### 16.2 数据加密

#### 16.2.1 加密数据

```python
# 加密数据
encrypted_data = security_manager.encrypt_data(
    data="敏感数据",
    key="加密密钥"
)
```

#### 16.2.2 解密数据

```python
# 解密数据
decrypted_data = security_manager.decrypt_data(
    encrypted_data=encrypted_data,
    key="加密密钥"
)
```

### 16.3 数据备份

#### 16.3.1 创建备份

```python
# 创建备份
backup_path = security_manager.create_backup(
    backup_dir="/path/to/backups",
    include_config=True,
    include_database=True
)
```

#### 16.3.2 恢复备份

```python
# 恢复备份
security_manager.restore_backup(
    backup_path="/path/to/backup.zip",
    restore_config=True,
    restore_database=True
)
```

## 17. 总结

本文档详细介绍了媒体库管理系统的API接口，包括数据库操作、视频管理、演员管理、标签系统、JAVDB信息获取、文件夹管理、搜索、导入导出、批量操作、配置管理、日志记录、事件系统、插件系统和安全功能等各个方面。

这些API接口提供了系统的核心功能，可以用于系统内部模块间的通信，也可以用于第三方应用集成。开发者可以根据需要选择合适的API接口，实现自定义功能或扩展现有功能。

如果您在使用API过程中遇到问题，可以参考示例代码或联系技术支持获取帮助。