from typing import Any, Dict, List, Optional, Callable

try:
    from javsp_integration import JavSPIntegration
except Exception:
    JavSPIntegration = None  # type: ignore

try:
    import code_extractor
except Exception:
    code_extractor = None  # type: ignore

from .db import upsert_jav_info

def extract_code(filename: str) -> Optional[str]:
    if code_extractor and hasattr(code_extractor, 'extract_code'):
        try:
            return code_extractor.extract_code(filename)
        except Exception:
            pass
    # 简单回退：移除扩展名后返回可能的编号
    base = filename.rsplit('.', 1)[0]
    return base

def _ensure_integration() -> Optional[Any]:
    if JavSPIntegration is None:
        return None
    try:
        return JavSPIntegration()
    except Exception:
        return None

def search_movie_info(code: str) -> Optional[Dict[str, Any]]:
    integration = _ensure_integration()
    if integration:
        try:
            return integration.search_movie_info(code)
        except Exception:
            return None
    return None

def save_movie_info_to_db(conn, video_id: int, info: Dict[str, Any]) -> bool:
    try:
        upsert_jav_info(conn, video_id, info)
        return True
    except Exception:
        return False

def batch_fetch_and_save(conn, video_ids: List[int], code_getter: Callable[[int], str], progress_cb: Optional[Callable[[Dict[str, Any]], None]] = None):
    total = len(video_ids)
    success = 0
    for idx, vid in enumerate(video_ids, 1):
        code = code_getter(vid)
        info = search_movie_info(code) if code else None
        if info and save_movie_info_to_db(conn, vid, info):
            success += 1
        if progress_cb:
            progress_cb({
                'current': idx,
                'total': total,
                'success': success
            })

def fix_error_titles(conn, titles: List[str], search_from_title: Callable[[str], Optional[str]], progress_cb: Optional[Callable[[Dict[str, Any]], None]] = None):
    total = len(titles)
    fixed = 0
    for idx, t in enumerate(titles, 1):
        code = search_from_title(t)
        info = search_movie_info(code) if code else None
        # 无 video_id 上下文，实际修复需外部映射；此处仅统计
        if info:
            fixed += 1
        if progress_cb:
            progress_cb({
                'current': idx,
                'total': total,
                'fixed': fixed
            })

