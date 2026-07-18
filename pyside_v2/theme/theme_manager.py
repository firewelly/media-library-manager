# -*- coding: utf-8 -*-
"""
主题管理器 - 双主题切换（对齐 ui_design 双主题设计稿）。

设计稿用 CSS 变量，PySide6 QSS 不支持，这里用模板插值：
    base.qss 用占位符 @@token@@，ThemeManager 按当前主题颜色替换后应用。
    切换主题时重新插值 + setStyleSheet，即时生效。

主题：
    A dark  影院感深色 + 玻璃拟态 + 琥珀金
    B light Fluent 浅色 + 云母质感 + 青蓝
"""

import json
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QColor

from pyside_v2.theme.colors import ThemeColors, Tokens, current, set_theme

_QSS_DIR = Path(__file__).parent
_THEME_FILE = _QSS_DIR.parent.parent / "gui_theme.json"   # 持久化用户选择


class ThemeManager:
    """双主题管理：加载 base.qss 模板 → 按主题插值 → 应用。"""

    def __init__(self, app: QApplication):
        self.app = app
        self._base_qss = ""
        self._theme_name = "light"
        self.colors: ThemeColors = current()

    @property
    def theme_name(self) -> str:
        return self._theme_name

    def load(self):
        """读取 base.qss 模板 + 用户上次主题选择。"""
        self._base_qss = (_QSS_DIR / "base.qss").read_text(encoding="utf-8")
        # 读持久化
        if _THEME_FILE.exists():
            try:
                self._theme_name = json.loads(
                    _THEME_FILE.read_text(encoding="utf-8")
                ).get("theme", "light")
            except Exception:
                self._theme_name = "light"

    def apply(self, theme_name: str = None):
        """应用指定主题（不传则用当前/上次）。"""
        if theme_name:
            self._theme_name = theme_name
        self.colors = set_theme(self._theme_name)
        qss = self._render(self._base_qss, self.colors)
        self.app.setStyleSheet(qss)
        # 持久化
        try:
            _THEME_FILE.write_text(
                json.dumps({"theme": self._theme_name}), encoding="utf-8"
            )
        except Exception:
            pass

    def toggle(self):
        """在 dark/light 间切换。"""
        self.apply("dark" if self._theme_name == "light" else "light")

    def _render(self, template: str, c: ThemeColors) -> str:
        """把 base.qss 的占位符替换为实际颜色。"""
        def rgba(q: QColor) -> str:
            return f"rgba({q.red()}, {q.green()}, {q.blue()}, {q.alpha()})"

        mapping = {
            "@@font_ui@@": Tokens.FONT_UI,
            "@@font_mono@@": Tokens.FONT_MONO,
            "@@bg_app@@": rgba(c.bg_app),
            "@@bg_sidebar@@": rgba(c.bg_sidebar),
            "@@bg_panel@@": rgba(c.bg_panel),
            "@@bg_panel_solid@@": rgba(c.bg_panel_solid),
            "@@bg_hover@@": rgba(c.bg_hover),
            "@@bg_active@@": rgba(c.bg_active),
            "@@bg_input@@": rgba(c.bg_input),
            "@@bg_skeleton@@": rgba(c.bg_skeleton),
            "@@border@@": rgba(c.border),
            "@@border_strong@@": rgba(c.border_strong),
            "@@text_1@@": rgba(c.text_1),
            "@@text_2@@": rgba(c.text_2),
            "@@text_3@@": rgba(c.text_3),
            "@@text_on_accent@@": rgba(c.text_on_accent),
            "@@accent@@": rgba(c.accent),
            "@@accent_hover@@": rgba(c.accent_hover),
            "@@accent_soft@@": rgba(c.accent_soft),
            "@@success@@": rgba(c.success),
            "@@warning@@": rgba(c.warning),
            "@@danger@@": rgba(c.danger),
            "@@info@@": rgba(c.info),
            "@@online@@": rgba(c.online),
            "@@offline@@": rgba(c.offline),
            "@@star_on@@": rgba(c.star_on),
            "@@star_off@@": rgba(c.star_off),
        }
        out = template
        for k, v in mapping.items():
            out = out.replace(k, v)
        return out


def init_theme(app: QApplication) -> ThemeManager:
    """便捷入口：创建 ThemeManager，加载并应用上次主题。"""
    mgr = ThemeManager(app)
    mgr.load()
    mgr.apply()
    return mgr
