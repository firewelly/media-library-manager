#!/bin/bash

# MacOS 视频媒体库管理软件启动脚本

# 获取脚本所在目录作为程序目录
APP_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# 检查程序目录是否存在
if [ ! -d "$APP_DIR" ]; then
    echo "错误: 未找到程序目录 $APP_DIR"
    exit 1
fi

# 切换到程序目录
cd "$APP_DIR" || exit 1

# 检查Python是否安装 - 尝试多个路径
PYTHON_CMD=""
PYTHON_PATHS=(
    "$HOME/anaconda3/bin/python3"
    "/opt/homebrew/bin/python3"
    "/usr/local/bin/python3"
    "/usr/bin/python3"
    "python3"
    "python"
)

for py_path in "${PYTHON_PATHS[@]}"; do
    if [ -x "$py_path" ]; then
        PYTHON_CMD="$py_path"
        echo "找到Python: $PYTHON_CMD"
        break
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "错误: 未找到 Python"
    echo "搜索的路径: ${PYTHON_PATHS[*]}"
    echo "请先安装 Python"
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
echo "程序目录: $APP_DIR"
echo "Python版本: $($PYTHON_CMD --version)"
"$PYTHON_CMD" media_library.py

# 检查程序退出状态
if [ $? -eq 0 ]; then
    echo "程序正常退出"
else
    echo "程序异常退出，退出码: $?"
    echo "请检查错误信息并重试"
fi
