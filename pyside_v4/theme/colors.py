# -*- coding: utf-8 -*-
"""
深色影院风主题 - 颜色定义
琥珀金强调色 + 深色背景层次
"""


class Colors:
    """主题颜色常量"""
    
    # 背景层次
    BG_APP = "#0f1115"           # 应用底色
    BG_SIDEBAR = "#14171d"       # 侧栏
    BG_PANEL = "#1a1e26"         # 实心面板（详情/弹窗）
    BG_HOVER = "#1f232c"         # 悬浮态
    BG_ACTIVE = "#2a2f3a"        # 激活态
    BG_INPUT = "#0a0c0f"         # 输入框背景
    BG_SKELETON = "#1e2229"      # 骨架屏占位
    
    # 边框与分隔
    BORDER = "#1f232c"           # 普通边框
    BORDER_STRONG = "#2d3340"    # 强调边框
    
    # 文字
    TEXT_1 = "#f2f4f8"           # 主文字
    TEXT_2 = "#aab2c0"           # 次文字
    TEXT_3 = "#6b7382"           # 弱提示
    TEXT_ON_ACCENT = "#1a1405"   # 强调色上的文字
    
    # 强调色：琥珀金
    ACCENT = "#f0b429"           # 主强调色
    ACCENT_HOVER = "#ffc53d"     # 强调色悬浮
    ACCENT_SOFT = "#2a2210"      # 柔和强调色背景
    
    # 语义色
    SUCCESS = "#3fb950"          # 成功
    WARNING = "#d29922"          # 警告
    DANGER = "#f47067"           # 危险
    INFO = "#58a6ff"             # 信息
    
    # NAS 在线状态
    ONLINE = "#3fb950"           # 在线
    OFFLINE = "#8b949e"          # 离线
    
    # 星级
    STAR_ON = "#f0b429"          # 点亮星星
    STAR_OFF = "#2d3340"         # 未点亮星星
