# -*- coding: utf-8 -*-
"""
深色影院风主题 - QSS 样式表
"""

from .colors import Colors


def get_main_qss() -> str:
    """返回主窗口 QSS 样式表"""
    return f"""
    /* ========== 全局基础 ========== */
    QWidget {{
        background-color: {Colors.BG_APP};
        color: {Colors.TEXT_1};
        font-family: "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", sans-serif;
        font-size: 13px;
    }}
    
    QMainWindow {{
        background-color: {Colors.BG_APP};
    }}
    
    /* ========== 侧栏 ========== */
    #sidebar {{
        background-color: {Colors.BG_SIDEBAR};
        border-right: 1px solid {Colors.BORDER};
    }}
    
    #sidebarBrand {{
        font-size: 16px;
        font-weight: 700;
        padding: 12px 16px;
    }}
    
    #sidebarBrandLogo {{
        background-color: {Colors.ACCENT};
        color: {Colors.TEXT_ON_ACCENT};
        border-radius: 8px;
        font-size: 14px;
        font-weight: 800;
        min-width: 28px;
        min-height: 28px;
        max-width: 28px;
        max-height: 28px;
    }}
    
    .navSection {{
        color: {Colors.TEXT_3};
        font-size: 11px;
        padding: 12px 12px 4px 12px;
        letter-spacing: 0.06em;
    }}
    
    .navItem {{
        padding: 8px 12px;
        border-radius: 8px;
        color: {Colors.TEXT_2};
        margin: 1px 8px;
    }}
    
    .navItem:hover {{
        background-color: {Colors.BG_HOVER};
        color: {Colors.TEXT_1};
    }}
    
    .navItem[active="true"] {{
        background-color: {Colors.ACCENT_SOFT};
        color: {Colors.ACCENT};
        font-weight: 600;
    }}
    
    .navItem .count {{
        color: {Colors.TEXT_3};
        font-size: 11px;
        background-color: {Colors.BG_HOVER};
        border-radius: 999px;
        padding: 1px 7px;
        margin-left: 8px;
    }}
    
    .navItem[active="true"] .count {{
        color: {Colors.ACCENT};
        background-color: transparent;
    }}
    
    /* ========== 顶部工具栏 ========== */
    #topbar {{
        background-color: {Colors.BG_PANEL};
        border-bottom: 1px solid {Colors.BORDER};
        min-height: 52px;
        padding: 0 16px;
    }}
    
    #searchBox {{
        background-color: {Colors.BG_INPUT};
        border: 1px solid {Colors.BORDER};
        border-radius: 8px;
        padding: 0 12px;
        min-height: 32px;
        min-width: 340px;
    }}
    
    #searchBox:focus {{
        border: 1px solid {Colors.ACCENT};
    }}
    
    #searchBox QLineEdit {{
        background-color: transparent;
        border: none;
        color: {Colors.TEXT_1};
        font-size: 13px;
    }}
    
    #searchBox QLineEdit::placeholder {{
        color: {Colors.TEXT_3};
    }}
    
    /* ========== 按钮 ========== */
    QPushButton {{
        background-color: {Colors.BG_PANEL};
        border: 1px solid {Colors.BORDER};
        border-radius: 8px;
        color: {Colors.TEXT_2};
        padding: 0 12px;
        min-height: 32px;
        font-size: 13px;
    }}
    
    QPushButton:hover {{
        background-color: {Colors.BG_HOVER};
        color: {Colors.TEXT_1};
        border: 1px solid {Colors.BORDER_STRONG};
    }}
    
    QPushButton[primary="true"] {{
        background-color: {Colors.ACCENT};
        border: none;
        color: {Colors.TEXT_ON_ACCENT};
        font-weight: 600;
    }}
    
    QPushButton[primary="true"]:hover {{
        background-color: {Colors.ACCENT_HOVER};
    }}
    
    QPushButton[active="true"] {{
        background-color: {Colors.ACCENT_SOFT};
        color: {Colors.ACCENT};
        border: none;
    }}
    
    /* ========== 表格/列表 ========== */
    QTableWidget {{
        background-color: {Colors.BG_APP};
        alternate-background-color: {Colors.BG_HOVER};
        border: none;
        gridline-color: {Colors.BORDER};
        selection-background-color: {Colors.ACCENT_SOFT};
        selection-color: {Colors.TEXT_1};
    }}
    
    QTableWidget::item {{
        padding: 8px;
        border-bottom: 1px solid {Colors.BORDER};
    }}
    
    QTableWidget::item:selected {{
        background-color: {Colors.ACCENT_SOFT};
        color: {Colors.TEXT_1};
    }}
    
    QHeaderView::section {{
        background-color: {Colors.BG_PANEL};
        color: {Colors.TEXT_3};
        padding: 8px;
        border: none;
        border-bottom: 1px solid {Colors.BORDER};
        font-size: 12px;
    }}
    
    QHeaderView::section:hover {{
        color: {Colors.TEXT_1};
    }}
    
    /* ========== 详情面板 ========== */
    #detailPanel {{
        background-color: {Colors.BG_PANEL};
        border-left: 1px solid {Colors.BORDER};
        min-width: 360px;
        max-width: 360px;
    }}
    
    #detailCover {{
        background-color: {Colors.BG_SKELETON};
        min-height: 270px;
    }}
    
    #detailBody {{
        padding: 16px;
    }}
    
    #detailTitle {{
        font-size: 16px;
        font-weight: 600;
        margin-bottom: 4px;
    }}
    
    #detailSubtitle {{
        color: {Colors.TEXT_3};
        font-size: 12px;
        margin-bottom: 12px;
    }}
    
    .kvRow {{
        padding: 5px 0;
        font-size: 12px;
    }}
    
    .kvRow .key {{
        color: {Colors.TEXT_3};
        min-width: 76px;
    }}
    
    .kvRow .value {{
        color: {Colors.TEXT_1};
    }}
    
    /* ========== 状态栏 ========== */
    #statusbar {{
        background-color: {Colors.BG_PANEL};
        border-top: 1px solid {Colors.BORDER};
        min-height: 28px;
        padding: 0 16px;
        font-size: 12px;
        color: {Colors.TEXT_3};
    }}
    
    /* ========== 滚动条 ========== */
    QScrollBar:vertical {{
        background-color: transparent;
        width: 10px;
        margin: 0;
    }}
    
    QScrollBar::handle:vertical {{
        background-color: {Colors.BG_ACTIVE};
        border-radius: 5px;
        min-height: 20px;
        margin: 2px;
    }}
    
    QScrollBar::handle:vertical:hover {{
        background-color: {Colors.BORDER_STRONG};
    }}
    
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    
    QScrollBar:horizontal {{
        background-color: transparent;
        height: 10px;
        margin: 0;
    }}
    
    QScrollBar::handle:horizontal {{
        background-color: {Colors.BG_ACTIVE};
        border-radius: 5px;
        min-width: 20px;
        margin: 2px;
    }}
    
    QScrollBar::handle:horizontal:hover {{
        background-color: {Colors.BORDER_STRONG};
    }}
    
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}
    
    /* ========== 复选框 ========== */
    QCheckBox {{
        spacing: 8px;
        color: {Colors.TEXT_1};
    }}
    
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border: 1px solid {Colors.BORDER_STRONG};
        border-radius: 4px;
        background-color: {Colors.BG_INPUT};
    }}
    
    QCheckBox::indicator:hover {{
        border: 1px solid {Colors.ACCENT};
    }}
    
    QCheckBox::indicator:checked {{
        background-color: {Colors.ACCENT};
        border: 1px solid {Colors.ACCENT};
        image: url(none);
    }}
    
    /* ========== 下拉框 ========== */
    QComboBox {{
        background-color: {Colors.BG_PANEL};
        border: 1px solid {Colors.BORDER};
        border-radius: 8px;
        padding: 0 12px;
        min-height: 32px;
        color: {Colors.TEXT_2};
    }}
    
    QComboBox:hover {{
        border: 1px solid {Colors.BORDER_STRONG};
        color: {Colors.TEXT_1};
    }}
    
    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}
    
    QComboBox QAbstractItemView {{
        background-color: {Colors.BG_PANEL};
        border: 1px solid {Colors.BORDER_STRONG};
        border-radius: 8px;
        selection-background-color: {Colors.ACCENT_SOFT};
        selection-color: {Colors.ACCENT};
        outline: none;
    }}
    
    /* ========== 标签/徽章 ========== */
    .tag {{
        background-color: {Colors.BG_ACTIVE};
        border-radius: 999px;
        padding: 1px 7px;
        font-size: 11px;
        color: {Colors.TEXT_2};
    }}
    
    .tag[hot="true"] {{
        background-color: {Colors.ACCENT_SOFT};
        color: {Colors.ACCENT};
    }}
    
    /* ========== 星级 ========== */
    .starRating {{
        color: {Colors.STAR_OFF};
        font-size: 12px;
        letter-spacing: 2px;
    }}
    
    .starRating .filled {{
        color: {Colors.STAR_ON};
    }}
    
    /* ========== 状态点 ========== */
    .statusDot {{
        min-width: 7px;
        min-height: 7px;
        max-width: 7px;
        max-height: 7px;
        border-radius: 50%;
    }}
    
    .statusDot[online="true"] {{
        background-color: {Colors.ONLINE};
    }}
    
    .statusDot[online="false"] {{
        background-color: {Colors.OFFLINE};
    }}
    
    /* ========== 筛选条 ========== */
    #filterbar {{
        background-color: {Colors.BG_APP};
        border-bottom: 1px solid {Colors.BORDER};
        padding: 8px 16px;
    }}
    
    .filterChip {{
        background-color: {Colors.ACCENT_SOFT};
        color: {Colors.ACCENT};
        border-radius: 999px;
        padding: 0 6px 0 12px;
        min-height: 24px;
        font-size: 12px;
    }}
    
    .filterChip .closeBtn {{
        background-color: transparent;
        border: none;
        color: {Colors.ACCENT};
        min-width: 16px;
        min-height: 16px;
        border-radius: 50%;
    }}
    
    .filterChip .closeBtn:hover {{
        background-color: rgba(0, 0, 0, 0.15);
    }}
    """
