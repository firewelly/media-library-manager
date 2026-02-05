#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整的Windows构建脚本
功能：
1. 以 media_library.py 为主入口编译成 exe
2. 打包所有依赖项（ffmpeg、msedgedriver等）
3. 编译其他功能性 py 文件（排除 obs 文件夹）
4. 输出到 release 文件夹
"""

import os
import re
import sys
import json
import shutil
import subprocess
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

# 根目录和输出目录
ROOT = Path(__file__).resolve().parent
RELEASE_DIR = ROOT / "release" / "MediaLibrary"
BIN_DIR = RELEASE_DIR / "bin"
TOOLS_DIR = BIN_DIR / "tools"
ASSETS_DIR = RELEASE_DIR / "assets"
SPECS_DIR = RELEASE_DIR / "specs"
WORK_DIR = RELEASE_DIR / "work"

# 排除的目录和文件
EXCLUDE_DIRS = {'obs', 'docker', 'JavSP', 'temp_backup', 'results', 'tests', '__pycache__', '.git', 'build', 'release'}
EXCLUDE_FILES = {'config.py', 'config.example.py', 'build_windows_complete.py'}


def run(cmd, cwd=None, check=True):
    """执行命令并返回输出"""
    print(f"[执行] {' '.join(map(str, cmd))}")
    # 实时输出
    process = subprocess.Popen(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output = []
    for line in process.stdout:
        line = line.rstrip()
        print(f"    {line}")
        output.append(line)
    process.wait()
    
    if check and process.returncode != 0:
        raise RuntimeError(f"Command failed ({process.returncode})")
    return process


def pyinstaller_cmd(script: Path, name: str, is_main=False):
    """生成 PyInstaller 命令"""
    data = []
    
    def add_data(src: Path, dest: str):
        if src.exists():
            data.append(f"{src}{os.pathsep}{dest}")
    
    # 添加配置文件和数据文件
    add_data(ROOT / "gui_config.json", ".")
    add_data(ROOT / "config.json", ".")
    add_data(ROOT / "covers" / "default.JPEG", "covers")
    add_data(ROOT / "vocabulary_tags.txt", ".")
    add_data(ROOT / "javsp_config.yaml", ".")
    add_data(ROOT / "README.md", ".")
    add_data(ROOT / "USER_MANUAL.md", ".")
    
    # 添加 utils 目录作为数据
    utils_dir = ROOT / "utils"
    if utils_dir.exists():
        add_data(utils_dir, "utils")
    
    # 添加 video_analyzer 目录作为数据
    video_analyzer_dir = ROOT / "video_analyzer"
    if video_analyzer_dir.exists():
        add_data(video_analyzer_dir, "video_analyzer")
    
    # 添加 facereco 目录作为数据
    facereco_dir = ROOT / "facereco"
    if facereco_dir.exists():
        add_data(facereco_dir, "facereco")
    
    # 添加 dbmigration 目录作为数据
    dbmigration_dir = ROOT / "dbmigration"
    if dbmigration_dir.exists():
        add_data(dbmigration_dir, "dbmigration")
    
    # 基础命令
    if is_main:
        # 主程序使用窗口模式（不显示控制台）
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--noconfirm",
            "--clean",
            "--onefile",
            "--windowed",  # 窗口模式，不显示控制台
            "--name", name,
            "--distpath", str(BIN_DIR),
            "--workpath", str(WORK_DIR / name),
            "--specpath", str(SPECS_DIR),
        ]
    else:
        # 辅助工具使用控制台模式
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--noconfirm",
            "--clean",
            "--onefile",
            "--console",  # 控制台模式
            "--name", name,
            "--distpath", str(BIN_DIR / "tools" / "scripts"),
            "--workpath", str(WORK_DIR / name),
            "--specpath", str(SPECS_DIR),
        ]
    
    # 图标（如果存在）
    icon_path = ROOT / "assets" / "icon.ico"
    if icon_path.exists():
        cmd += ["--icon", str(icon_path)]
    
    for d in data:
        cmd += ["--add-data", d]
    
    # 添加隐藏导入
    hidden_imports = [
        "PIL",
        "PIL._imagingtk",
        "PIL._tkinter_finder",
        "cv2",
        "sqlite3",
        "requests",
        "lxml",
        "cloudscraper",
        "coloredlogs",
        "yaml",
        "send2trash",
        "selenium",
        "selenium.webdriver",
        "selenium.webdriver.edge",
        "jieba",
    ]
    
    for imp in hidden_imports:
        cmd += ["--hidden-import", imp]
    
    cmd.append(str(script))
    return cmd


def is_entrypoint_script(path: Path) -> bool:
    """检查是否为入口点脚本（包含 if __name__ == '__main__'）"""
    try:
        txt = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False
    return bool(re.search(r"if\s+__name__\s*==\s*['\"]__main__['\"]\s*:", txt))


def collect_scripts():
    """收集需要编译的脚本"""
    scripts = []
    
    # 收集根目录下的 Python 文件
    root_py = sorted([p for p in ROOT.glob("*.py") if p.is_file()])
    for p in root_py:
        if p.name in EXCLUDE_FILES:
            continue
        if p.name in {"media_library.py", "media_library_pyside.py"}:
            continue
        if is_entrypoint_script(p):
            scripts.append((p.stem, p))
    
    # 收集 video_analyzer 目录下的脚本
    video_analyzer_dir = ROOT / "video_analyzer"
    if video_analyzer_dir.exists():
        for p in sorted(video_analyzer_dir.glob("*.py")):
            if p.is_file() and is_entrypoint_script(p):
                scripts.append((f"video_analyzer_{p.stem}", p))
    
    # 收集 facereco 目录下的脚本
    facereco_dir = ROOT / "facereco"
    if facereco_dir.exists():
        for p in sorted(facereco_dir.glob("*.py")):
            if p.is_file() and is_entrypoint_script(p):
                scripts.append((f"facereco_{p.stem}", p))
    
    # 收集 dbmigration 目录下的脚本
    dbmigration_dir = ROOT / "dbmigration"
    if dbmigration_dir.exists():
        for p in sorted(dbmigration_dir.glob("*.py")):
            if p.is_file() and is_entrypoint_script(p):
                scripts.append((f"dbmigration_{p.stem}", p))
    
    return scripts


def copy_external_assets():
    """复制外部资源文件到 assets 目录"""
    print("[步骤] 复制外部资源文件...")
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    
    files_to_copy = [
        "gui_config.json",
        "javsp_config.yaml",
        "vocabulary_tags.txt",
        "README.md",
        "USER_MANUAL.md",
        "requirements.txt"
    ]
    
    for rel in files_to_copy:
        src = ROOT / rel
        if src.exists():
            shutil.copy2(src, ASSETS_DIR / src.name)
            print(f"  已复制: {rel}")
    
    # 复制配置文件
    cfg_local = ROOT / "config.local.json"
    cfg_default = ROOT / "config.json"
    cfg_src = cfg_local if cfg_local.exists() else cfg_default
    if cfg_src.exists():
        shutil.copy2(cfg_src, ASSETS_DIR / "config.json")
        print(f"  已复制: config.json")
    
    # 复制 covers 目录
    covers = ROOT / "covers"
    if covers.exists():
        dst = ASSETS_DIR / "covers"
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(covers, dst)
        print(f"  已复制: covers/ 目录")


def stage_runtime_files():
    """准备运行时文件到 bin 目录"""
    print("[步骤] 准备运行时文件...")
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    
    files_to_copy = [
        "gui_config.json",
        "javsp_config.yaml",
        "vocabulary_tags.txt",
        "README.md",
        "USER_MANUAL.md"
    ]
    
    for rel in files_to_copy:
        src = ROOT / rel
        if src.exists():
            shutil.copy2(src, BIN_DIR / src.name)
    
    # 复制配置文件
    cfg_local = ROOT / "config.local.json"
    cfg_default = ROOT / "config.json"
    cfg_src = cfg_local if cfg_local.exists() else cfg_default
    if cfg_src.exists():
        shutil.copy2(cfg_src, BIN_DIR / "config.json")
    
    # 复制 covers 目录
    covers = ROOT / "covers"
    if covers.exists():
        dst = BIN_DIR / "covers"
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(covers, dst)


def find_ffmpeg():
    """查找 ffmpeg"""
    try:
        out = subprocess.run(["where.exe", "ffmpeg"], capture_output=True, text=True)
        if out.returncode == 0:
            p = out.stdout.splitlines()[0].strip()
            if p and Path(p).exists():
                return Path(p)
    except Exception:
        pass
    
    # 常见路径检查
    common_paths = [
        Path(r"C:\ffmpeg\bin\ffmpeg.exe"),
        Path(r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"),
        Path(r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe"),
    ]
    for p in common_paths:
        if p.exists():
            return p
    return None


def find_ffprobe():
    """查找 ffprobe"""
    try:
        out = subprocess.run(["where.exe", "ffprobe"], capture_output=True, text=True)
        if out.returncode == 0:
            p = out.stdout.splitlines()[0].strip()
            if p and Path(p).exists():
                return Path(p)
    except Exception:
        pass
    
    # 常见路径检查
    common_paths = [
        Path(r"C:\ffmpeg\bin\ffprobe.exe"),
        Path(r"C:\Program Files\ffmpeg\bin\ffprobe.exe"),
        Path(r"C:\Program Files (x86)\ffmpeg\bin\ffprobe.exe"),
    ]
    for p in common_paths:
        if p.exists():
            return p
    return None


def find_msedgedriver():
    """查找 msedgedriver"""
    candidates = [
        Path(r"C:\bin\edgedriver_win64\msedgedriver.exe"),
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedgedriver.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedgedriver.exe"),
        Path(r"C:\edgedriver_win64\msedgedriver.exe"),
        Path(r"C:\WebDriver\bin\msedgedriver.exe"),
        Path(r"C:\selenium\msedgedriver.exe"),
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def copy_tools():
    """复制外部工具到 tools 目录"""
    print("[步骤] 复制外部工具...")
    TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    
    tools_copied = []
    
    # 复制 ffmpeg
    ffmpeg = find_ffmpeg()
    if ffmpeg:
        shutil.copy2(ffmpeg, TOOLS_DIR / "ffmpeg.exe")
        print(f"  已复制: ffmpeg.exe")
        tools_copied.append("ffmpeg")
    else:
        print(f"  [警告] 未找到 ffmpeg.exe")
    
    # 复制 ffprobe
    ffprobe = find_ffprobe()
    if ffprobe:
        shutil.copy2(ffprobe, TOOLS_DIR / "ffprobe.exe")
        print(f"  已复制: ffprobe.exe")
        tools_copied.append("ffprobe")
    else:
        print(f"  [警告] 未找到 ffprobe.exe")
    
    # 复制 msedgedriver
    msedgedriver = find_msedgedriver()
    if msedgedriver:
        shutil.copy2(msedgedriver, TOOLS_DIR / "msedgedriver.exe")
        print(f"  已复制: msedgedriver.exe")
        tools_copied.append("msedgedriver")
    else:
        print(f"  [警告] 未找到 msedgedriver.exe")
    
    return tools_copied


def build_main_executable():
    """构建主程序可执行文件"""
    print("[步骤] 构建主程序 MediaLibrary.exe...")
    main_script = ROOT / "media_library.py"
    
    if not main_script.exists():
        raise FileNotFoundError(f"主程序脚本不存在: {main_script}")
    
    cmd = pyinstaller_cmd(main_script, "MediaLibrary", is_main=True)
    run(cmd)
    print("  主程序构建完成")


def build_additional_scripts(scripts):
    """构建额外的脚本"""
    print(f"[步骤] 构建 {len(scripts)} 个辅助工具...")
    
    built = []
    failed = []
    
    for name, script in scripts:
        print(f"  构建: {name}...", end=" ")
        try:
            cmd = pyinstaller_cmd(script, name, is_main=False)
            run(cmd, check=True)
            print("成功")
            built.append({"name": name, "script": str(script.relative_to(ROOT))})
        except Exception as e:
            print(f"失败: {e}")
            failed.append({"name": name, "script": str(script), "error": str(e)})
    
    return built, failed


def write_batch_files():
    """创建批处理文件"""
    print("[步骤] 创建批处理文件...")
    
    # 启动主程序的批处理
    start_bat = BIN_DIR / "启动媒体库.bat"
    start_content = """@echo off
chcp 65001 >nul
echo 正在启动媒体库管理工具...
cd /d "%~dp0"
start "" "MediaLibrary.exe"
"""
    start_bat.write_text(start_content, encoding="utf-8")
    print(f"  已创建: {start_bat.name}")
    
    # 工具列表批处理
    tools_bat = BIN_DIR / "查看可用工具.bat"
    tools_content = """@echo off
chcp 65001 >nul
echo ========================================
echo      媒体库管理工具 - 可用工具列表
echo ========================================
echo.
dir /b "%~dp0tools\\scripts\\*.exe" 2>nul || echo 暂无辅助工具
echo.
pause
"""
    tools_bat.write_text(tools_content, encoding="utf-8")
    print(f"  已创建: {tools_bat.name}")


def write_readme():
    """创建发布说明"""
    readme = RELEASE_DIR / "使用说明.txt"
    content = """媒体库管理工具 - Windows 版本
================================

【目录结构】
- MediaLibrary.exe    主程序（双击启动）
- bin/                程序文件和配置
- tools/              外部工具（ffmpeg、msedgedriver等）
- assets/             资源文件和文档

【启动方式】
1. 双击 "MediaLibrary.exe" 启动主程序
2. 或运行 "启动媒体库.bat"

【辅助工具】
辅助工具位于 bin/tools/scripts/ 目录下，可通过命令行调用
运行 "查看可用工具.bat" 查看所有可用工具

【依赖说明】
本打包版本已包含以下依赖：
- ffmpeg / ffprobe    视频处理工具
- msedgedriver        Edge浏览器驱动（用于爬虫功能）

【注意事项】
1. 首次运行前请确保已正确配置 config.json
2. 数据库文件将自动创建在程序目录
3. 如有问题请查看 USER_MANUAL.md

================================
"""
    readme.write_text(content, encoding="utf-8")
    print(f"  已创建: {readme.name}")


def write_report(report: dict):
    """写入构建报告"""
    report_path = RELEASE_DIR / "build_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  构建报告已保存: {report_path}")


def zip_release():
    """打包发布文件为 zip"""
    print("[步骤] 打包发布文件...")
    zip_path = ROOT / "release" / "MediaLibrary-Windows-Complete.zip"
    
    # 删除旧的 zip 文件
    if zip_path.exists():
        zip_path.unlink()
        print(f"  已删除旧的 zip 文件")
    
    added_files = set()  # 用于追踪已添加的文件
    
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as z:
        # 添加主程序
        main_exe = BIN_DIR / "MediaLibrary.exe"
        if main_exe.exists():
            z.write(main_exe, arcname="MediaLibrary.exe")
            added_files.add("MediaLibrary.exe")
        
        # 添加批处理文件
        for bat_file in BIN_DIR.glob("*.bat"):
            arcname = str(Path("bin") / bat_file.name)
            if arcname not in added_files:
                z.write(bat_file, arcname=arcname)
                added_files.add(arcname)
        
        # 添加 bin 目录内容
        for p in BIN_DIR.rglob("*"):
            if p.is_file():
                # 跳过批处理文件（已添加）
                if p.suffix == ".bat":
                    continue
                # 跳过不需要的文件
                rel = p.relative_to(BIN_DIR)
                if any(part in {".edge_driver_user_data", "__pycache__", ".pyc"} for part in rel.parts):
                    continue
                if rel.suffix.lower() in {".log", ".pyc", ".pyo"}:
                    continue
                arcname = str(Path("bin") / rel)
                if arcname not in added_files:
                    z.write(p, arcname=arcname)
                    added_files.add(arcname)
        
        # 添加 tools 目录内容
        for p in TOOLS_DIR.rglob("*"):
            if p.is_file():
                rel = p.relative_to(TOOLS_DIR)
                arcname = str(Path("tools") / rel)
                if arcname not in added_files:
                    z.write(p, arcname=arcname)
                    added_files.add(arcname)
        
        # 添加 assets 目录内容
        for p in ASSETS_DIR.rglob("*"):
            if p.is_file():
                rel = p.relative_to(ASSETS_DIR)
                arcname = str(Path("assets") / rel)
                if arcname not in added_files:
                    z.write(p, arcname=arcname)
                    added_files.add(arcname)
        
        # 添加文档
        for doc in ["使用说明.txt", "build_report.json"]:
            doc_path = RELEASE_DIR / doc
            if doc_path.exists() and doc not in added_files:
                z.write(doc_path, arcname=doc)
                added_files.add(doc)
    
    print(f"  打包完成: {zip_path}")
    print(f"  包含 {len(added_files)} 个文件")
    return zip_path


def main():
    """主函数"""
    print("="*60)
    print("媒体库管理工具 - Windows 完整打包脚本")
    print("="*60)
    print()
    
    # 清理旧的构建
    if RELEASE_DIR.exists():
        print("[清理] 删除旧的构建目录...")
        shutil.rmtree(RELEASE_DIR)
    
    # 创建目录结构
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    SPECS_DIR.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    (BIN_DIR / "tools" / "scripts").mkdir(parents=True, exist_ok=True)
    
    # 报告
    report = {
        "build_time": subprocess.check_output(["cmd", "/c", "echo %date% %time%"], text=True).strip(),
        "main_executable": None,
        "tools": {},
        "scripts_built": [],
        "scripts_failed": []
    }
    
    try:
        # 复制外部资源
        copy_external_assets()
        
        # 准备运行时文件
        stage_runtime_files()
        
        # 复制工具
        tools_copied = copy_tools()
        report["tools"] = {tool: True for tool in tools_copied}
        
        # 构建主程序
        skip_main = "--skip-main" in sys.argv
        if not skip_main:
            build_main_executable()
            report["main_executable"] = "MediaLibrary.exe"
        
        # 收集并构建辅助脚本
        skip_scripts = "--skip-scripts" in sys.argv
        if not skip_scripts:
            scripts = collect_scripts()
            print(f"[信息] 发现 {len(scripts)} 个辅助脚本需要编译")
            built, failed = build_additional_scripts(scripts)
            report["scripts_built"] = built
            report["scripts_failed"] = failed
        
        # 创建批处理文件
        write_batch_files()
        
        # 创建使用说明
        write_readme()
        
        # 写入构建报告
        write_report(report)
        
        # 打包
        if "--no-zip" not in sys.argv:
            zip_path = zip_release()
        
        print()
        print("="*60)
        print("构建完成!")
        print("="*60)
        print(f"输出目录: {RELEASE_DIR}")
        if "--no-zip" not in sys.argv:
            print(f"ZIP 文件: {zip_path}")
        print()
        print("主程序: MediaLibrary.exe")
        print(f"辅助工具: {len(report['scripts_built'])} 个")
        print(f"失败: {len(report['scripts_failed'])} 个")
        
        if report["scripts_failed"]:
            print("\n失败的脚本:")
            for item in report["scripts_failed"]:
                print(f"  - {item['name']}: {item['error']}")
        
    except Exception as e:
        print()
        print("="*60)
        print("构建失败!")
        print("="*60)
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
