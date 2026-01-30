import os
import sys
import shutil


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def runtime_dir() -> str:
    if is_frozen():
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(sys.argv[0] if sys.argv and sys.argv[0] else __file__))


def resource_dir() -> str:
    if is_frozen() and hasattr(sys, "_MEIPASS"):
        return getattr(sys, "_MEIPASS")
    return runtime_dir()


def resource_path(*parts: str) -> str:
    return os.path.join(resource_dir(), *parts)


def runtime_path(*parts: str) -> str:
    return os.path.join(runtime_dir(), *parts)


def ensure_file_in_runtime(relative_path: str) -> str:
    dst = runtime_path(relative_path)
    if os.path.exists(dst):
        return dst
    src = resource_path(relative_path)
    if os.path.exists(src):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
    return dst
