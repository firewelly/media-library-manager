#!/bin/bash
# 媒体库管理器 v2 启动脚本
# PySide6 v2：双主题界面（影院深色琥珀金 / Fluent 浅色青蓝）+ 高性能分页列表
# 入口：media_library_v2.py（启动 pyside_v2/ 模块包）

cd "$(dirname "$0")"

# 检查 Python 环境（完全按 PATH 顺序，不主动探测绝对路径）
if ! command -v python3 &> /dev/null; then
    if command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        echo "错误: 未找到 python3 或 python，请先安装 Python 3.9+"
        exit 1
    fi
else
    PYTHON_CMD="python3"
fi

echo "使用 Python: $($PYTHON_CMD --version 2>&1)"

# 检查 PySide6
if ! "$PYTHON_CMD" -c "import PySide6" 2>/dev/null; then
    echo "正在安装 PySide6..."
    "$PYTHON_CMD" -m pip install PySide6 -i https://pypi.tuna.tsinghua.edu.cn/simple
fi

# 启动应用
"$PYTHON_CMD" media_library_v2.py
