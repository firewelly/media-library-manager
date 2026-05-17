import os
import re
import sys
import json
import shutil
import subprocess
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED


ROOT = Path(__file__).resolve().parents[2]
RELEASE_DIR = ROOT / "release" / "windows"
BIN_DIR = RELEASE_DIR / "bin"
TOOLS_DIR = BIN_DIR / "tools"
ASSETS_DIR = RELEASE_DIR / "assets"
SPECS_DIR = RELEASE_DIR / "specs"
WORK_DIR = RELEASE_DIR / "work"


def run(cmd, cwd=None):
    p = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(f"Command failed ({p.returncode}): {' '.join(map(str, cmd))}\n{p.stdout}\n{p.stderr}")
    return p.stdout


def pyinstaller_cmd(script: Path, name: str, is_main=False):
    data = []
    def add_data(src: Path, dest: str):
        if src.exists():
            data.append(f"{src}{os.pathsep}{dest}")

    if name == "user_manual":
        html_file = script.parent / "用户手册.html"
        if html_file.exists():
            data.append(f"{html_file}{os.pathsep}.")
    else:
        add_data(ROOT / "gui_config.json", ".")
        add_data(ROOT / "config.json", ".")
        add_data(ROOT / "covers" / "default.JPEG", "covers")
        add_data(ROOT / "vocabulary_tags.txt", ".")
        add_data(ROOT / "javsp_config.yaml", ".")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name", name,
        "--distpath", str(BIN_DIR),
        "--workpath", str(WORK_DIR / name),
        "--specpath", str(SPECS_DIR),
    ]
    for d in data:
        cmd += ["--add-data", d]
    cmd.append(str(script))
    return cmd


def is_entrypoint_script(path: Path) -> bool:
    try:
        txt = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False
    return bool(re.search(r"if\s+__name__\s*==\s*['\"]__main__['\"]\s*:", txt))


def collect_scripts():
    scripts = []
    root_py = sorted([p for p in ROOT.glob("*.py") if p.is_file()])
    skip = {
        "config.py",
        "config.example.py",
    }
    for p in root_py:
        if p.name in skip:
            continue
        if p.name in {"media_library.py", "media_library_pyside.py"}:
            continue
        if is_entrypoint_script(p):
            scripts.append(p)

    for p in sorted((ROOT / "video_analyzer").glob("*.py")):
        if p.is_file() and is_entrypoint_script(p):
            scripts.append(p)

    for p in sorted((ROOT / "facereco").glob("*.py")):
        if p.is_file() and is_entrypoint_script(p):
            scripts.append(p)

    return scripts


def copy_external_assets():
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    for rel in ["gui_config.json", "javsp_config.yaml", "vocabulary_tags.txt", "doc/USER_MANUAL.md"]:
        src = ROOT / rel
        if src.exists():
            shutil.copy2(src, ASSETS_DIR / src.name)
    cfg_local = ROOT / "config.local.json"
    cfg_default = ROOT / "config.json"
    cfg_src = cfg_local if cfg_local.exists() else cfg_default
    if cfg_src.exists():
        shutil.copy2(cfg_src, ASSETS_DIR / "config.json")
    covers = ROOT / "covers"
    if covers.exists():
        dst = ASSETS_DIR / "covers"
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(covers, dst)


def stage_runtime_files():
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    for rel in ["gui_config.json", "javsp_config.yaml", "vocabulary_tags.txt", "doc/USER_MANUAL.md"]:
        src = ROOT / rel
        if src.exists():
            shutil.copy2(src, BIN_DIR / src.name)
    cfg_local = ROOT / "config.local.json"
    cfg_default = ROOT / "config.json"
    cfg_src = cfg_local if cfg_local.exists() else cfg_default
    if cfg_src.exists():
        shutil.copy2(cfg_src, BIN_DIR / "config.json")
    covers = ROOT / "covers"
    if covers.exists():
        dst = BIN_DIR / "covers"
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(covers, dst)


def find_ffmpeg():
    try:
        out = run(["where.exe", "ffmpeg"])
        p = out.splitlines()[0].strip()
        if p and Path(p).exists():
            return Path(p)
    except Exception:
        pass
    return None


def find_msedgedriver():
    candidates = [
        Path(r"C:\bin\edgedriver_win64\msedgedriver.exe"),
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedgedriver.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedgedriver.exe"),
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def copy_tools():
    TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    ffmpeg = find_ffmpeg()
    if ffmpeg:
        shutil.copy2(ffmpeg, TOOLS_DIR / "ffmpeg.exe")
    msedgedriver = find_msedgedriver()
    if msedgedriver:
        shutil.copy2(msedgedriver, TOOLS_DIR / "msedgedriver.exe")


def write_report(report: dict):
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    (RELEASE_DIR / "build_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def zip_release():
    zip_path = RELEASE_DIR / "media-library-windows.zip"
    if zip_path.exists():
        zip_path.unlink()
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as z:
        for base in [BIN_DIR, ASSETS_DIR]:
            if not base.exists():
                continue
            for p in base.rglob("*"):
                if p.is_file():
                    rel = p.relative_to(base)
                    if any(part in {".edge_driver_user_data", "__pycache__"} for part in rel.parts):
                        continue
                    if rel.suffix.lower() in {".log"}:
                        continue
                    z.write(p, arcname=str(Path(base.name) / p.relative_to(base)))
        rep = RELEASE_DIR / "build_report.json"
        if rep.exists():
            z.write(rep, arcname="build_report.json")
    return zip_path


def main():
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    SPECS_DIR.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    report_path = RELEASE_DIR / "build_report.json"
    report = {"built": [], "failed": [], "tools": {}}
    if "--skip-build" in sys.argv and report_path.exists():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except Exception:
            report = {"built": [], "failed": [], "tools": {}}

    copy_external_assets()
    stage_runtime_files()

    skip_build = "--skip-build" in sys.argv
    if not skip_build:
        main_targets = [
            ("media_library", ROOT / "media_library.py"),
            ("media_library_pyside", ROOT / "media_library_pyside.py"),
        ]

        scripts = collect_scripts()

        targets = main_targets + [(p.stem, p) for p in scripts]
        
        user_manual_script = ASSETS_DIR / "user_manual.py"
        if user_manual_script.exists():
            targets.append(("user_manual", user_manual_script))

        for name, script in targets:
            try:
                run(pyinstaller_cmd(script, name))
                report["built"].append({"name": name, "script": str(script.relative_to(ROOT))})
            except Exception as e:
                report["failed"].append({"name": name, "script": str(script), "error": str(e)})

    copy_tools()
    report["tools"]["ffmpeg"] = str((TOOLS_DIR / "ffmpeg.exe").exists())
    report["tools"]["msedgedriver"] = str((TOOLS_DIR / "msedgedriver.exe").exists())

    if not report.get("built"):
        report["built"] = [{"name": p.stem, "script": ""} for p in sorted(BIN_DIR.glob("*.exe"))]

    write_report(report)
    zip_path = zip_release()
    print(str(zip_path))


if __name__ == "__main__":
    main()
