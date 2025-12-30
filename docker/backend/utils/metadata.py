import os
from typing import Tuple

def process_filename(name: str) -> str:
    return os.path.splitext(name)[0]

def extract_title(name: str) -> str:
    return process_filename(name)

def parse_stars(name: str) -> int:
    return 0

def get_video_media_info(path: str) -> Tuple[int, str]:
    # 占位：返回 (duration, resolution)
    return 0, ""

