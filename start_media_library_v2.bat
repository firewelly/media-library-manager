@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion
REM ============================================================
REM  媒体库管理器 v2 启动脚本（Windows）
REM  PySide6 v2：双主题界面 + 高性能分页列表
REM  入口：media_library_v2.py（启动 pyside_v2/ 模块包）
REM ============================================================

cd /d "%~dp0"

REM 检查 Python（完全按 PATH 顺序，不主动探测绝对路径）
set "PYTHON_CMD="
for %%P in (python python3 py) do (
    where %%P >nul 2>&1
    if !errorlevel! equ 0 (
        set "PYTHON_CMD=%%P"
        goto :found
    )
)

echo 错误: 未找到 Python（python / python3 / py）
echo 请先安装 Python 3.9+ 并加入 PATH
pause
exit /b 1

:found
echo 使用 Python: %PYTHON_CMD%

REM 检查 PySide6，缺失则安装
%PYTHON_CMD% -c "import PySide6" 2>nul
if errorlevel 1 (
    echo 正在安装 PySide6...
    %PYTHON_CMD% -m pip install PySide6 -i https://pypi.tuna.tsinghua.edu.cn/simple
)

REM 启动应用
echo ================================================================
echo   媒体库管理器 v2（PySide6 · 双主题 · 高性能）
echo ================================================================
%PYTHON_CMD% media_library_v2.py

if errorlevel 1 (
    echo.
    echo 程序异常退出，退出码: %errorlevel%
    pause
)
