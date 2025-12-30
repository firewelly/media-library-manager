import os
from typing import Iterable, List

VIDEO_EXTS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv'}

def walk_videos(folders: Iterable[str], exts: Iterable[str] = None) -> List[str]:
    exts = set(exts) if exts else VIDEO_EXTS
    results = []
    for folder in folders:
        if not folder or not os.path.isdir(folder):
            continue
        for root, _, files in os.walk(folder):
            for f in files:
                p = os.path.join(root, f)
                if os.path.splitext(f)[1].lower() in exts:
                    results.append(p)
    return results

def open_file_cross_platform(path: str):
    if os.name == 'nt':
        os.startfile(path)  # type: ignore
    elif os.uname().sysname == 'Darwin':
        os.system(f"open '{path}'")
    else:
        os.system(f"xdg-open '{path}'")

