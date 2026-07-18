#!/bin/bash
# 媒体库管理器 v4 启动脚本
# 深色影院风界面（琥珀金强调色）

cd "$(dirname "$0")"

# 检查 Python 环境
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 python3，请先安装 Python 3.8+"
    exit 1
fi

# 检查 PySide6
if ! python3 -c "import PySide6" 2>/dev/null; then
    echo "正在安装 PySide6..."
    pip3 install PySide6 -i https://pypi.tuna.tsinghua.edu.cn/simple
fi

# 启动应用
python3 media_library_v4.py
