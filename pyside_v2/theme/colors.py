# -*- coding: utf-8 -*-
"""
语义颜色 + 设计令牌（对齐 ui_design/assets/tokens.css + theme-*.css）。

设计稿用 CSS 变量做双主题，PySide6 QSS 不支持变量，这里用 Python 层
主题切换：Palette 持有当前主题的所有颜色，ThemeManager 切换时重建 Palette
并重应用 QSS。

两个主题：
    A 暗色「影院感」：玻璃拟态面板 + 琥珀金强调 (#f0b429)
    B 亮色「Fluent」：云母质感面板 + 青蓝强调 (#0f6fde)
"""

from PySide6.QtGui import QColor


class ThemeColors:
    """单主题颜色集（对应一个 theme-*.css 的 :root 变量）。"""

    def __init__(self, name: str):
        self.name = name
        # 由具体主题类填充
        self.bg_app = QColor()
        self.bg_sidebar = QColor()
        self.bg_panel = QColor()          # 半透明面板（侧栏/topbar/状态栏）
        self.bg_panel_solid = QColor()    # 实心面板（详情/弹窗）
        self.bg_hover = QColor()
        self.bg_active = QColor()
        self.bg_input = QColor()
        self.bg_skeleton = QColor()       # 骨架屏占位

        self.border = QColor()
        self.border_strong = QColor()

        self.text_1 = QColor()            # 主文字
        self.text_2 = QColor()            # 次文字
        self.text_3 = QColor()            # 弱提示
        self.text_on_accent = QColor()

        self.accent = QColor()
        self.accent_hover = QColor()
        self.accent_soft = QColor()       # 强调色淡底（选中行/导航激活）

        self.success = QColor()
        self.warning = QColor()
        self.danger = QColor()
        self.info = QColor()

        self.online = QColor()
        self.offline = QColor()

        self.star_on = QColor()
        self.star_off = QColor()

        self.shadow_panel = True          # 是否启用面板阴影


def _dark_theme() -> ThemeColors:
    """方向 A · 深色影院风（玻璃拟态 + 琥珀金）。"""
    t = ThemeColors("dark")
    t.bg_app = QColor("#0f1115")
    t.bg_sidebar = QColor("#14171d")
    t.bg_panel = QColor(255, 255, 255, 10)        # rgba 4% → 约 10/255
    t.bg_panel_solid = QColor("#1a1e26")
    t.bg_hover = QColor(255, 255, 255, 15)
    t.bg_active = QColor(255, 255, 255, 26)
    t.bg_input = QColor(0, 0, 0, 77)              # rgba 30%
    t.bg_skeleton = QColor(255, 255, 255, 18)

    t.border = QColor(255, 255, 255, 20)
    t.border_strong = QColor(255, 255, 255, 36)

    t.text_1 = QColor("#f2f4f8")
    t.text_2 = QColor("#aab2c0")
    t.text_3 = QColor("#6b7382")
    t.text_on_accent = QColor("#1a1405")

    t.accent = QColor("#f0b429")
    t.accent_hover = QColor("#ffc53d")
    t.accent_soft = QColor(240, 180, 41, 36)      # rgba 14%

    t.success = QColor("#3fb950")
    t.warning = QColor("#d29922")
    t.danger = QColor("#f47067")
    t.info = QColor("#58a6ff")

    t.online = QColor("#3fb950")
    t.offline = QColor("#8b949e")

    t.star_on = QColor("#f0b429")
    t.star_off = QColor(255, 255, 255, 46)
    return t


def _light_theme() -> ThemeColors:
    """方向 B · 浅色 Fluent 风（云母质感 + 青蓝）。"""
    t = ThemeColors("light")
    t.bg_app = QColor("#f3f4f7")
    t.bg_sidebar = QColor("#eceef2")
    t.bg_panel = QColor(255, 255, 255, 184)       # rgba 72%
    t.bg_panel_solid = QColor("#ffffff")
    t.bg_hover = QColor(16, 24, 40, 13)           # rgba 5%
    t.bg_active = QColor(16, 24, 40, 23)          # rgba 9%
    t.bg_input = QColor("#ffffff")
    t.bg_skeleton = QColor(16, 24, 40, 15)        # rgba 6%

    t.border = QColor(16, 24, 40, 23)             # rgba 9%
    t.border_strong = QColor(16, 24, 40, 41)      # rgba 16%

    t.text_1 = QColor("#1b1f27")
    t.text_2 = QColor("#52596b")
    t.text_3 = QColor("#8a91a1")
    t.text_on_accent = QColor("#ffffff")

    t.accent = QColor("#0f6fde")
    t.accent_hover = QColor("#2b84e8")
    t.accent_soft = QColor(15, 111, 222, 26)      # rgba 10%

    t.success = QColor("#1a7f37")
    t.warning = QColor("#9a6700")
    t.danger = QColor("#cf222e")
    t.info = QColor("#0969da")

    t.online = QColor("#1a7f37")
    t.offline = QColor("#8a91a1")

    t.star_on = QColor("#e8a009")
    t.star_off = QColor(16, 24, 40, 36)           # rgba 14%
    return t


# 当前主题颜色（由 ThemeManager 切换；初始为亮色）
_current: ThemeColors = _light_theme()


def current() -> ThemeColors:
    return _current


def set_theme(name: str) -> ThemeColors:
    """切换当前主题颜色集。"""
    global _current
    _current = _dark_theme() if name == "dark" else _light_theme()
    return _current


def color_hex(name: str) -> str:
    """返回当前主题某颜色的 #RRGGBB 字符串，用于内联 setStyleSheet。

    PySide6 的 setStyleSheet 不解析 @@token@@ 占位符（那是 base.qss 层的
    模板插值），内联样式需要直接写 #RRGGBB。本函数提供统一入口，避免各处
    硬编码十六进制色值——切换主题后重新调用即可获得新主题对应色。

    支持的 name：star_on / accent / danger / success / warning / text_1 /
    text_2 / text_3 / offline / online / info
    """
    c = _current
    _map = {
        'star_on':  c.star_on,
        'accent':   c.accent,
        'danger':   c.danger,
        'success':  c.success,
        'warning':  c.warning,
        'text_1':   c.text_1,
        'text_2':   c.text_2,
        'text_3':   c.text_3,
        'offline':  c.offline,
        'online':   c.online,
        'info':     c.info,
    }
    color = _map.get(name)
    if color is None:
        raise KeyError(f"未知颜色名: {name}，可选: {list(_map)}")
    return color.name()


# ---- 设计令牌（主题无关，对齐 tokens.css）----
class Tokens:
    """布局/字号/间距/圆角令牌（与 CSS --sp-*/--fs-*/--r-* 一致）。"""
    # 字号
    FS_11, FS_12, FS_13, FS_14 = 11, 12, 13, 14
    FS_16, FS_18, FS_20, FS_24, FS_32 = 16, 18, 20, 24, 32
    # 间距（4px 基准）
    SP_1, SP_2, SP_3, SP_4 = 4, 8, 12, 16
    SP_5, SP_6, SP_8, SP_10 = 20, 24, 32, 40
    # 圆角
    R_SM, R_MD, R_LG, R_XL, R_FULL = 4, 8, 12, 16, 999
    # 布局尺寸
    TOPBAR_H = 52
    SIDEBAR_W = 220
    SIDEBAR_W_FOLD = 56
    DETAIL_W = 360
    STATUSBAR_H = 28
    ROW_H = 36           # 紧凑
    ROW_H_COMFY = 44     # 舒适
    COVER_RATIO = 0.6667  # 2:3

    FONT_UI = '"PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", "Segoe UI", Roboto, sans-serif'
    FONT_MONO = '"SF Mono", "JetBrains Mono", Consolas, "Courier New", monospace'
