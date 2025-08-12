#!/bin/bash

# MacOS 视频媒体库管理软件启动脚本

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# 切换到程序目录
cd "$SCRIPT_DIR"

# 检查Python是否安装
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 Python 3"
    echo "请先安装 Python 3.7 或更高版本"
    exit 1
fi

# 检查主程序文件是否存在
if [ ! -f "media_library.py" ]; then
    echo "错误: 未找到 media_library.py 文件"
    echo "请确保所有程序文件都在同一目录下"
    exit 1
fi

# 启动程序
echo "正在启动视频媒体库管理软件..."
python3 media_library.py

# 检查程序退出状态
if [ $? -eq 0 ]; then
    echo "程序正常退出"
else
    echo "程序异常退出，退出码: $?"
    echo "请检查错误信息并重试"
fi