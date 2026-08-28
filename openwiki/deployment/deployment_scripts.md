---
type: 参考
title: 部署脚本
description: 记录平台特定的启动脚本——start_media_library.sh (Tk)、start_media_library_v2.sh (v2, macOS/Linux)、start_media_library_v2.bat (v2, Windows) 以及 macOS .app 捆绑包。
openwiki:
  roles: [operations]
  source_paths: [start_media_library.sh, start_media_library_v2.sh, start_media_library_v2.bat, media_library_v2.py]
---

# 部署脚本

## Shell 脚本

### `start_media_library.sh` — Tk 经典版 (macOS/Linux)
```bash
#!/bin/bash
cd "$(dirname "$0")"
python3 media_library.py
```
检查 Python 3 并启动 Tkinter 版本。

### `start_media_library_v2.sh` — PySide6 v2 (macOS/Linux)
1. 切换到脚本所在目录
2. 检查 Python 3
3. 检查 PySide6，如果缺失则通过 pip（清华镜像）安装
4. 启动 `python3 media_library_v2.py`

### `start_media_library_v2.bat` — PySide6 v2 (Windows)
与 Shell 脚本逻辑相同，针对 Windows 进行了适配：
1. 检查 Python
2. 检查/安装 PySide6
3. 启动 `python media_library_v2.py`

## Python 入口点

### `media_library_v2.py`
推荐的启动器。执行以下操作：
1. 切换到项目根目录
2. 将 `sys.argv[0]` 锚定到项目根目录（以便 `utils/runtime.runtime_path()` 正确解析）
3. 检查 PySide6，如果缺失则从清华镜像安装
4. 导入并运行 `pyside_v2.app.main()`

```bash
python media_library_v2.py
```

## macOS .app 捆绑包

提供两个 `.app` 捆绑包以支持 Spotlight 启动：
- `Media Library.app` — 启动 Tk 经典版
- `Media Library v2.app` — 启动 PySide6 v2

用户可以通过 `Cmd+Space` 打开搜索并查找“Media Library”。

## 另请参阅

- [部署概述](overview.md) — 所有部署模式
- [Docker 脚本](docker_scripts.md) — 容器部署