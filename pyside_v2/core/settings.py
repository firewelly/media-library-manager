# -*- coding: utf-8 -*-
"""
应用设置管理器 —— v2 设置对话框的持久化后端。

存储文件：runtime_path('gui_config_v2.json')
    {
        "theme": "light",            # 主题（ThemeManager 同步写 gui_theme.json，此处冗余存一份）
        "page_size": 300,            # 每页条数
        "search_debounce_ms": 500,   # 搜索防抖
        "show_online_only": true,    # 默认仅在线
        "player_path": "",           # 自定义播放器（空 = 系统默认）
        "header_state": ""           # 表格列布局（QHeaderView state 的 base64）
    }

主线程使用，不做加锁。
"""

import json

try:
    from utils.runtime import runtime_path
except ImportError:  # pragma: no cover
    def runtime_path(*parts):
        import os
        return os.path.join(os.getcwd(), *parts)

_SETTINGS_FILE = runtime_path('gui_config_v2.json')

DEFAULTS = {
    "theme": "light",
    "page_size": 300,
    "search_debounce_ms": 500,
    "show_online_only": True,
    "player_path": "",
    "header_state": "",
}


class SettingsManager:
    """读写 gui_config_v2.json 的轻量封装。"""

    def __init__(self, path=None):
        self.path = path or _SETTINGS_FILE
        self._cache = None

    # ---- 内部 ----
    def _load(self) -> dict:
        if self._cache is None:
            data = {}
            try:
                with open(self.path, encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
            merged = dict(DEFAULTS)
            merged.update({k: v for k, v in data.items() if k in DEFAULTS})
            self._cache = merged
        return self._cache

    def _save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ---- 对外 ----
    def get(self, key):
        """读取设置项，未知 key 返回 None。"""
        return self._load().get(key, DEFAULTS.get(key))

    def set(self, key, value):
        """写入并立即落盘；未知 key 忽略。"""
        if key not in DEFAULTS:
            return
        self._load()[key] = value
        self._save()

    def update(self, **kwargs):
        """批量写入（仅接受已知 key）。"""
        data = self._load()
        for k, v in kwargs.items():
            if k in DEFAULTS:
                data[k] = v
        self._save()

    def all_settings(self) -> dict:
        return dict(self._load())
