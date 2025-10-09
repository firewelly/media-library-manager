# JAVDB爬虫系统设计文档

## 1. 系统概述

JAVDB爬虫系统是一个专为媒体库设计的自动化信息获取工具，能够从JAVDB网站提取视频元数据、演员信息和标签数据，并自动更新到本地数据库。系统采用模块化设计，包含登录助手、信息爬取器、数据处理器等多个组件，支持批量处理和单视频更新，为媒体库提供完整的数据支持。

## 2. 核心功能

### 2.1 登录状态管理
- 使用专用的Edge浏览器用户数据目录持久化登录状态
- 支持手动登录和安全验证处理
- 自动检测登录状态和验证码页面
- 提供友好的用户交互界面

### 2.2 视频信息爬取
- 支持按番号搜索视频
- 自动提取视频元数据（标题、发行日期、时长、评分等）
- 获取演员信息和标签数据
- 下载封面图片到本地

### 2.3 数据处理与存储
- 自动解析网页内容并结构化存储
- 支持多表关联数据更新
- 实现数据去重和完整性检查
- 提供详细的处理日志和统计信息

### 2.4 批量处理与任务管理
- 支持批量更新多个视频信息
- 提供任务进度显示和错误恢复
- 支持按文件夹筛选和批量操作
- 实现智能重试和异常处理机制

## 3. 系统架构

![系统架构图](系统架构图.png)

系统主要由以下组件构成：

1. **登录助手模块**：管理浏览器登录状态，处理安全验证
2. **信息爬取模块**：负责从JAVDB网站获取视频信息
3. **数据处理模块**：解析网页内容并结构化数据
4. **数据库接口**：与SQLite数据库交互，更新视频信息
5. **任务管理模块**：控制批量处理流程和进度显示
6. **异常处理模块**：处理各种异常情况并提供恢复机制

## 4. 核心类与方法

### 4.1 JAVDBInformationUpdater 类

**主要参数：**
- `db_path`：数据库文件路径，默认为"media_library.db"
- `covers_dir`：封面图片保存目录，默认为"covers"
- `SOCKS5_PROXY_HOST`：SOCKS5代理服务器地址
- `SOCKS5_PROXY_PORT`：SOCKS5代理服务器端口

**关键方法：**

#### `setup_driver()`
设置Edge浏览器驱动
```python
def setup_driver(self):
    # 配置Edge浏览器选项
    # 设置用户数据目录和代理
    # 启动浏览器驱动
    # 返回WebDriver实例
```

#### `is_login_page(driver)`
检测是否为登录页面
```python
def is_login_page(self, driver):
    # 检查URL是否包含登录关键词
    # 检查页面是否存在登录表单元素
    # 返回布尔值表示是否为登录页面
```

#### `wait_for_manual_login(driver)`
等待用户手动完成登录
```python
def wait_for_manual_login(self, driver):
    # 显示登录提示信息
    # 等待用户完成登录或超时
    # 检查登录状态
    # 返回登录是否成功
```

#### `get_videos_to_update(folder_id=None, refresh_all=False)`
获取需要更新的视频列表
```python
def get_videos_to_update(self, folder_id=None, refresh_all=False):
    # 连接数据库
    # 根据参数筛选视频
    # 返回视频列表
```

#### `update_video_info(video_id, driver)`
更新单个视频信息
```python
def update_video_info(self, video_id, driver):
    # 获取视频基本信息
    # 提取番号
    # 搜索并获取视频详情
    # 解析页面内容
    # 更新数据库
    # 下载封面图片
```

### 4.2 CodeExtractor 类

**主要功能：**
- 从文件名或标题中提取视频番号
- 支持多种番号格式识别
- 提供番号有效性验证

**关键方法：**

#### `extract_code(filename)`
从文件名中提取番号
```python
def extract_code(self, filename):
    # 清理文件名
    # 应用多种正则表达式匹配番号
    # 返回提取的番号或None
```

#### `_is_valid_code(code)`
验证番号有效性
```python
def _is_valid_code(self, code):
    # 检查番号格式
    # 排除无效字符
    # 返回布尔值表示是否有效
```

## 5. 数据模型

### 5.1 视频信息模型
系统从JAVDB网站提取以下视频信息：
- 基本信息标题、番号、发行日期、时长、评分
- 制作信息：片商、系列、导演
- 多媒体资源：封面图片URL、磁力链接
- 分类信息：标签、演员

### 5.2 数据库表结构
系统主要与以下数据库表交互：
- `videos`：存储视频基本信息
- `javdb_info`：存储从JAVDB获取的详细信息
- `actors`：存储演员信息
- `video_actors`：视频与演员的关联表
- `javdb_tags`：存储标签信息
- `javdb_info_tags`：JAVDB信息与标签的关联表

### 5.3 数据更新流程
1. 从`videos`表获取需要更新的视频
2. 提取视频番号
3. 使用番号在JAVDB搜索并获取详情页URL
4. 解析详情页内容
5. 更新`javdb_info`表
6. 处理演员信息并更新`actors`和`video_actors`表
7. 处理标签信息并更新`javdb_tags`和`javdb_info_tags`表
8. 下载封面图片并保存到本地

## 6. 技术实现细节

### 6.1 网页解析技术
- 使用Selenium WebDriver控制浏览器
- 通过XPath和CSS选择器提取页面元素
- 实现多选择器备选机制提高解析成功率
- 支持动态内容等待和超时处理

### 6.2 反爬策略
- 使用SOCKS5代理隐藏真实IP
- 实现随机延迟模拟人类操作
- 使用专用的浏览器用户数据目录
- 模拟人类操作模式（鼠标移动、滚动等）

### 6.3 错误处理与恢复
- 多重异常捕获和处理
- 网络请求失败自动重试
- 页面解析失败尝试备选方案
- 详细的错误日志记录

### 6.4 性能优化
- 批量处理减少数据库交互
- 图片缓存避免重复下载
- 并行处理提高爬取效率
- 内存使用优化防止溢出

## 7. 配置与依赖

### 7.1 配置参数
- `SOCKS5_PROXY_HOST`：代理服务器地址（默认：127.0.0.1）
- `SOCKS5_PROXY_PORT`：代理服务器端口（默认：1080）
- `BASE_URL`：JAVDB基础URL（默认：https://javdb.com）
- `MIN_DELAY`, `MAX_DELAY`：随机延迟范围
- `DB_PATH`：数据库文件路径
- `COVERS_DIR`：封面图片保存目录

### 7.2 依赖项
- `selenium`：浏览器自动化
- `requests`：HTTP请求
- `sqlite3`：数据库操作
- `BeautifulSoup`：HTML解析
- `Pillow`：图像处理
- `webdriver_manager`：浏览器驱动管理

## 8. 使用指南

### 8.1 安装与配置
1. 安装依赖：
```bash
pip install selenium requests beautifulsoup4 pillow webdriver-manager
```

2. 确保已安装Microsoft Edge浏览器
3. 配置SOCKS5代理服务器（默认：127.0.0.1:1080）

### 8.2 基本使用
#### 按番号更新单个视频
```bash
python javdb_information_updater.py --code ABC-123
```

#### 批量更新视频信息
```bash
python javdb_information_updater.py
```

#### 刷新所有视频信息
```bash
python javdb_information_updater.py --refresh-all
```

### 8.3 登录状态管理
1. 首次使用时运行登录助手：
```bash
python javdb_login_helper.py
```

2. 在打开的浏览器中手动完成登录
3. 登录状态会自动保存，后续使用无需重新登录

## 9. 测试与验证

### 9.1 单元测试
- 番号提取测试
- 数据库操作测试
- 页面解析测试

### 9.2 集成测试
- 完整爬取流程测试
- 批量处理测试
- 错误恢复测试

### 9.3 测试脚本
系统提供多个测试脚本：
- `test_javdb_updater.py`：基本功能测试
- `test_refresh_by_code.py`：按番号刷新测试
- `local_db_write_smoke_test.py`：数据库写入测试

## 10. 限制与注意事项

1. 依赖JAVDB网站结构，网站改版可能需要更新解析逻辑
2. 需要稳定的网络环境和代理服务
3. 大规模爬取可能触发网站反爬机制
4. 首次使用需要手动登录
5. 封面图片下载可能需要较长时间

## 11. 版本历史

| 版本 | 日期 | 主要变更 |
|------|------|---------|
| v1.0 | 2024 | 初始版本，基本爬取功能 |
| v1.1 | 2024 | 增加登录助手，优化批量处理 |
| v1.2 | 2024 | 改进错误处理，增加备选解析方案 |
| v1.3 | 2024 | 优化性能，增加并行处理 |

## 12. 未来改进方向

1. 引入多线程/多进程提高爬取效率
2. 实现分布式爬取架构
3. 增加更多数据源支持
4. 开发图形用户界面
5. 实现智能调度和任务队列
6. 增加数据分析和统计功能

## 13. 附录

### 13.1 常见问题解决
**Q: 浏览器启动失败怎么办？**
A: 检查Edge浏览器是否正确安装，以及EdgeDriver是否与浏览器版本匹配。

**Q: 登录后仍然无法获取信息怎么办？**
A: 检查代理配置是否正确，以及是否可以正常访问JAVDB网站。

**Q: 无法提取番号怎么办？**
A: 检查文件名格式是否标准，必要时手动在数据库中添加番号。

### 13.2 性能指标
- 单视频处理时间：10-30秒
- 批量处理速度：约50-100视频/小时
- 内存占用：< 500MB
- 网络带宽需求：< 1MB/s

### 13.3 错误代码说明
- `ERR_LOGIN_FAILED`：登录失败
- `ERR_NO_CODE`：无法提取番号
- `ERR_SEARCH_FAILED`：搜索失败
- `ERR_PARSE_FAILED`：页面解析失败
- `ERR_DB_UPDATE`：数据库更新失败
- `ERR_DOWNLOAD_FAILED`：图片下载失败