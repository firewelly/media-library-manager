# -*- coding: utf-8 -*-
"""
演员浏览窗口（侧栏"演员库"点击打开）。

网格卡片式展示全部演员：头像 + 名字 + 作品数 + 收藏标记。
功能：搜索 / 排序（作品数/名字/收藏优先）/ 筛选（仅收藏/有头像）/ 翻页。
点击卡片 → 打开 ActorDetailWindow 看详情。
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QScrollArea, QWidget, QGridLayout, QFrame, QMessageBox,
    QButtonGroup, QRadioButton, QHBoxLayout as QHBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QFont, QColor

from pyside_v2.theme import Tokens


PAGE_SIZE = 60   # 每页展示演员数（网格 5列 x 12行）


class ActorCard(QFrame):
    """单个演员卡片（可点击）。"""

    clicked = Signal(int)   # actor_id

    def __init__(self, actor_id, name, movie_count, is_favorite, avatar_data=None, parent=None):
        super().__init__(parent)
        self.actor_id = actor_id
        self.setFrameShape(QFrame.NoFrame)
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("actorCard")
        self.setStyleSheet("""
            #actorCard {
                background: palette(base);
                border: 1px solid palette(midlight);
                border-radius: 8px;
            }
            #actorCard:hover {
                border: 1px solid #0f6fde;
                background: palette(light);
            }
        """)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(4)

        # 头像
        self.avatar = QLabel()
        self.avatar.setFixedSize(120, 160)
        self.avatar.setAlignment(Qt.AlignCenter)
        self.avatar.setStyleSheet("background: palette(midlight); border-radius:6px;")
        if avatar_data:
            pix = QPixmap()
            pix.loadFromData(avatar_data)
            if not pix.isNull():
                self.avatar.setPixmap(
                    pix.scaled(120, 160, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                )
            else:
                self.avatar.setText("无头像")
        else:
            self.avatar.setText("无头像")
        # 头像右上角收藏星
        self.fav_label = QLabel("★" if is_favorite else "")
        self.fav_label.setStyleSheet("color: #e8a009; font-size: 16px; background: transparent;")
        self.fav_label.setFixedSize(20, 20)
        self.fav_label.move(110, 4)
        self.fav_label.setParent(self.avatar)
        lay.addWidget(self.avatar, alignment=Qt.AlignCenter)

        # 名字
        self.name_label = QLabel(name)
        f = QFont(); f.setPointSize(10); f.setBold(True); self.name_label.setFont(f)
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setWordWrap(True)
        self.name_label.setMaximumHeight(36)
        lay.addWidget(self.name_label)

        # 作品数
        cnt_text = f"{movie_count or 0} 部"
        cnt_color = "#0f6fde" if movie_count else "#8a91a1"
        self.count_label = QLabel(cnt_text)
        self.count_label.setStyleSheet(f"color: {cnt_color}; font-size: 11px;")
        self.count_label.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.count_label)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.actor_id)
        super().mousePressEvent(event)


class ActorBrowserDialog(QDialog):
    """演员浏览窗口：网格卡片 + 搜索/排序/筛选/翻页。"""

    def __init__(self, main_window, parent=None):
        super().__init__(parent or main_window)
        self.mw = main_window
        self.core = main_window.core
        self.setWindowTitle("演员库")
        self.resize(900, 680)
        self._page_no = 0
        self._total = 0
        self._search = ""
        self._sort = "movie_count"   # movie_count / name / favorite
        self._fav_only = False
        self._setup_ui()
        self.load_actors()

    def _setup_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(Tokens.SP_4, Tokens.SP_4, Tokens.SP_4, Tokens.SP_4)
        lay.setSpacing(Tokens.SP_3)

        # ---- 工具栏 ----
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索演员名/别名…")
        self.search_input.setFixedWidth(220)
        self.search_input.returnPressed.connect(self._on_search)
        toolbar.addWidget(self.search_input)

        self.btn_search = QPushButton("搜索")
        self.btn_search.setProperty("role", "primary")
        self.btn_search.setCursor(Qt.PointingHandCursor)
        self.btn_search.clicked.connect(self._on_search)
        toolbar.addWidget(self.btn_search)

        toolbar.addSpacing(12)
        toolbar.addWidget(QLabel("排序："))
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["作品数（多→少）", "名字（A→Z）", "收藏优先"])
        self.sort_combo.currentIndexChanged.connect(self._on_sort_change)
        toolbar.addWidget(self.sort_combo)

        self.chk_fav = QPushButton("仅收藏")
        self.chk_fav.setCheckable(True)
        self.chk_fav.setCursor(Qt.PointingHandCursor)
        self.chk_fav.toggled.connect(self._on_fav_toggle)
        toolbar.addWidget(self.chk_fav)

        toolbar.addStretch()
        self.count_label = QLabel("0 个演员")
        self.count_label.setStyleSheet("color: palette(mid);")
        toolbar.addWidget(self.count_label)
        lay.addLayout(toolbar)

        # ---- 卡片网格区（滚动）----
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(Tokens.SP_3)
        self.grid_layout.setContentsMargins(4, 4, 4, 4)
        self.grid_layout.setAlignment(Qt.AlignTop)
        self.scroll.setWidget(self.grid_container)
        lay.addWidget(self.scroll, 1)

        # ---- 翻页栏 ----
        page_bar = QHBoxLayout()
        page_bar.addStretch()
        self.btn_first = QPushButton("⟨⟨"); self.btn_first.setFixedWidth(34)
        self.btn_prev = QPushButton("⟨"); self.btn_prev.setFixedWidth(34)
        self.page_label = QLabel("0 / 0")
        self.page_label.setStyleSheet("color: palette(mid); padding: 0 10px;")
        self.btn_next = QPushButton("⟩"); self.btn_next.setFixedWidth(34)
        self.btn_last = QPushButton("⟩⟩"); self.btn_last.setFixedWidth(34)
        for b in (self.btn_first, self.btn_prev, self.btn_next, self.btn_last):
            b.setCursor(Qt.PointingHandCursor)
            b.setProperty("role", "icon")
        self.btn_first.clicked.connect(lambda: self._goto(0))
        self.btn_prev.clicked.connect(lambda: self._goto(max(0, self._page_no - 1)))
        self.btn_next.clicked.connect(self._go_next)
        self.btn_last.clicked.connect(self._go_last)
        for b in (self.btn_first, self.btn_prev, self.page_label, self.btn_next, self.btn_last):
            page_bar.addWidget(b)
        page_bar.addStretch()
        lay.addLayout(page_bar)

        # ---- 关闭 ----
        btn_close = QPushButton("关闭")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.clicked.connect(self.accept)
        row2 = QHBoxLayout()
        row2.addStretch()
        row2.addWidget(btn_close)
        lay.addLayout(row2)

    # ---- 数据加载 ----
    # 注：actors.movie_count 字段在历史数据里大多为 NULL/0（爬虫未回填），
    # 这里用子查询实时统计 video_actors 关联表的真实作品数，保证排序准确。
    REAL_COUNT = "(SELECT COUNT(*) FROM video_actors va WHERE va.actor_id = a.id)"

    def _build_query(self):
        conditions = []
        params = []
        if self._search:
            conditions.append(
                "(a.name LIKE ? OR a.name_common LIKE ? OR a.name_traditional LIKE ? OR a.aliases LIKE ?)"
            )
            kw = f"%{self._search}%"
            params.extend([kw, kw, kw, kw])
        if self._fav_only:
            conditions.append("a.is_favorite = 1")

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        # 排序用真实作品数（real_count），不走失效的 movie_count 字段
        sort_map = {
            "movie_count": f"{self.REAL_COUNT} DESC, a.name ASC",
            "name": "a.name ASC",
            "favorite": f"a.is_favorite DESC, {self.REAL_COUNT} DESC, a.name ASC",
        }
        order = sort_map.get(self._sort, sort_map["movie_count"])
        return where, params, order

    def load_actors(self):
        where, params, order = self._build_query()

        try:
            # 总数
            self.core.cursor.execute(f"SELECT COUNT(*) FROM actors a {where}", params)
            self._total = self.core.cursor.fetchone()[0]

            # 当前页：作品数用子查询实时统计
            offset = self._page_no * PAGE_SIZE
            sql = (
                f"SELECT a.id, a.name, {self.REAL_COUNT} AS real_count, "
                f"a.is_favorite, a.avatar_data "
                f"FROM actors a {where} ORDER BY {order} LIMIT ? OFFSET ?"
            )
            self.core.cursor.execute(sql, params + [PAGE_SIZE, offset])
            rows = self.core.cursor.fetchall()
        except Exception as e:
            QMessageBox.warning(self, "查询失败", str(e))
            return

        # 清空旧卡片
        self._clear_grid()
        cols = 5
        for i, (aid, name, mcount, fav, avatar) in enumerate(rows):
            card = ActorCard(aid, name or "—", mcount or 0, bool(fav), avatar)
            card.clicked.connect(self._open_detail)
            self.grid_layout.addWidget(card, i // cols, i % cols)

        # 状态
        self.count_label.setText(f"共 {self._total} 个演员")
        max_page = max(1, (self._total - 1) // PAGE_SIZE + 1) if self._total > 0 else 1
        self.page_label.setText(f"{self._page_no + 1} / {max_page}")

    def _clear_grid(self):
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    # ---- 事件 ----
    def _on_search(self):
        self._search = self.search_input.text().strip()
        self._page_no = 0
        self.load_actors()

    def _on_sort_change(self, idx):
        self._sort = ["movie_count", "name", "favorite"][idx]
        self._page_no = 0
        self.load_actors()

    def _on_fav_toggle(self, checked):
        self._fav_only = checked
        self._page_no = 0
        self.load_actors()

    def _goto(self, page_no):
        if page_no != self._page_no:
            self._page_no = page_no
            self.load_actors()

    def _go_next(self):
        max_page = max(0, (self._total - 1) // PAGE_SIZE)
        self._goto(min(max_page, self._page_no + 1))

    def _go_last(self):
        max_page = max(0, (self._total - 1) // PAGE_SIZE)
        self._goto(max_page)

    def _open_detail(self, actor_id):
        """点击卡片 → 打开演员详情。"""
        try:
            self.core.cursor.execute("SELECT name FROM actors WHERE id=?", (actor_id,))
            r = self.core.cursor.fetchone()
            if r and r[0]:
                from pyside_v2.dialogs.actor_detail import ActorDetailWindow
                dlg = ActorDetailWindow(self.mw, actor_name=r[0], parent=self)
                dlg.exec()
        except Exception as e:
            QMessageBox.warning(self, "打开详情失败", str(e))
