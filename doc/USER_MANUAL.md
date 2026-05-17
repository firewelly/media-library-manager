# Windows 用户手册（发行包）

本手册适用于 `media-library-windows.zip` 解压后的 Windows 版本。

## 1. 解压与启动

1. 解压 `media-library-windows.zip`
2. 进入 `bin/`
3. 双击启动：
   - `media_library.exe`（Tk 版本，默认推荐）
   - `media_library_pyside.exe`（PySide 版本）

首次启动会在 `bin/` 目录下自动生成或使用以下文件/目录：
- `media_library.db`：SQLite 数据库（媒体库数据）
- `results/`：抓取封面、临时结果等
- `.edge_driver_user_data/`：JavDB 登录态（Edge 用户数据，自动化使用）

## 2. 目录结构说明

解压后核心目录：
- `bin/`：主程序与全部辅助工具（exe）
- `bin/tools/`：内置工具
  - `ffmpeg.exe`：缩略图/视频处理需要
  - `msedgedriver.exe`：Selenium 驱动（JavDB 登录与抓取）
- `bin/covers/`：默认头像等资源
- `assets/`：随包附带的默认配置/资源备份

## 3. 配置文件（代理/延时/无头）

`bin/config.json` 用于配置代理与爬虫行为：

```json
{
  "proxy": { "enabled": true, "host": "127.0.0.1", "port": 8800 },
  "crawler": { "delay_between_requests": 2.0, "headless": true }
}
```

字段说明：
- `proxy.enabled`：是否启用 SOCKS5 代理访问 JavDB
- `proxy.host` / `proxy.port`：代理地址与端口
- `crawler.delay_between_requests`：请求间隔（秒）；用于减轻风控概率
- `crawler.headless`：是否无头（部分站点/风控情况下建议改为 `false` 便于手工验证）

注意：
- 本项目不会把你的密钥/Token 写入配置文件；如有第三方 API Key，请使用环境变量或运行参数传入（见相关工具说明）。

## 4. 核心功能速览（主程序）

### 4.1 扫描与入库
- 添加本地文件夹或 NAS 路径
- 扫描导入后，会写入 `media_library.db`

### 4.2 获取 JAVDB 信息（重点）
在列表中选择视频后：
- 点击右侧按钮或右键菜单：获取 JAVDB 信息
- 程序会提取番号（例如 `MIDA-203`）并调用 JavDB 工具抓取

抓取成功后可写入：
- `JAVDB标题 / 发行日期 / 评分 / 标签 / 演员 / 封面 / 磁力链接`

### 4.3 回退策略
当 JavDB 抓取失败或演员为空时：
- 自动回退到 JavBus
- 仍失败再回退到 JavSP（如果该功能可用）

## 5. 附带的辅助工具（exe）

所有辅助工具均在 `bin/` 下，以独立 exe 的形式提供（部分工具需要命令行运行）。

常用示例：
- `javdb_crawler_single.exe <番号>`：单个番号抓取（用于调试）
  - 示例：`javdb_crawler_single.exe MIDA-203`
- `javdb_login_helper.exe`：打开浏览器完成登录/验证并持久化登录态
- `javbus_crawler_single.exe <番号>`：JavBus 单个抓取
- `update_msedge_driver.exe`：更新/安装 EdgeDriver（当驱动版本不匹配时使用）

## 6. ffmpeg 使用说明

缩略图生成、视频处理等需要 ffmpeg。
- 发行包内置：`bin/tools/ffmpeg.exe`
- 程序会优先使用内置 ffmpeg；若不存在会尝试系统 PATH 或常见安装目录。

## 7. msedgedriver / Selenium 说明（JavDB 必需）

JavDB 抓取依赖 Selenium 驱动：
- 发行包内置：`bin/tools/msedgedriver.exe`
- 若出现 “WebDriver only supports Microsoft Edge version …”：
  1. 先运行 `update_msedge_driver.exe`
  2. 或更新本机 Edge 浏览器版本后再试

## 8. 常见问题排查

### 8.1 抓取失败/返回 “信息被屏蔽”
- 检查代理是否可用（`config.json`）
- 尝试把 `crawler.headless` 设为 `false`，用可视化模式完成验证码/安全验证
- 运行 `javdb_login_helper.exe` 先登录并通过验证

### 8.2 启动后目录不可写
- 请确保将发行包解压到有写入权限的位置（不要放在需要管理员权限的目录）
- 数据库与缓存默认写在 `bin/` 同目录下

### 8.3 杀毒软件误报
- PyInstaller 打包的 exe 在某些环境可能触发误报
- 建议将解压目录加入白名单，或使用自签名/企业签名方案

## 9. 发布建议（给维护者）

不建议把 `release/windows/bin/*.exe` 直接提交到 Git 仓库（体积大、diff 无意义）。
推荐做法：
- 提交源代码与构建脚本
- 在 GitHub Release 页面上传 `media-library-windows.zip` 作为 Release 资产

