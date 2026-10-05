# -*- coding: utf-8 -*-
"""展示层格式化工具：时长 / 文件大小 / 日期时间。

时长字段的历史包袱：JAVDB 导入会把 "122 分鍾" 这类日文本直接写进
videos.duration（全库约 5000 行），而 ffprobe 写入的是秒数（int/float）。
parse_duration_seconds 统一把两种来源归一成秒，调用方不再各自 try/except。
"""

import re

_DURATION_NUM_RE = re.compile(r"(\d+(?:\.\d+)?)")


def parse_duration_seconds(value):
    """把 duration 原始值归一成秒数（int）；无法解析返回 None。

    支持：
        int/float          —— 秒（ffprobe 来源）
        "3600" / "122.5"   —— 秒
        "122 分鍾" / "85 分钟" / "90 min" —— 分钟（JAVDB 来源）
        其他文本           —— None
    """
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, bytes):
        try:
            return int.from_bytes(value, byteorder="big")
        except (ValueError, OverflowError):
            return None
    text = str(value).strip()
    if not text:
        return None
    m = _DURATION_NUM_RE.search(text)
    if not m:
        return None
    n = float(m.group(1))
    lowered = text.lower()
    if "分" in text or "min" in lowered:
        return int(n * 60)
    if "小時" in text or "小时" in text or "hour" in lowered or lowered.endswith("h"):
        return int(n * 3600)
    return int(n)


def format_duration(value, empty="—"):
    """时长显示：秒 → HH:MM:SS / MM:SS；无法解析时原样截断返回文本。"""
    if value is None or value == "":
        return empty
    sec = parse_duration_seconds(value)
    if sec is None:
        return str(value)[:20]
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def format_file_size(size, empty="—"):
    """文件大小显示：字节 → 自适应单位。"""
    if size is None or size == "":
        return empty
    try:
        s = float(size)
    except (TypeError, ValueError):
        return str(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if s < 1024:
            return f"{s:.2f} {unit}"
        s /= 1024
    return f"{s:.2f} PB"


def format_datetime(dt, empty="—"):
    """日期时间显示：截断到秒，T 替换为空格。"""
    if not dt:
        return empty
    return str(dt)[:19].replace("T", " ")
