"""
ui.py — PCB Test Station: giao diện PySide6
Light theme theo phong cách Fluent Design (Microsoft).
Responsive: tự co giãn theo cửa sổ. Số box/tay/tray đọc từ station.ini (qua InitSettings.py).

Chạy: python ui.py
Yêu cầu: pip install PySide6
"""

import sys
import time
import threading
from typing import Optional

from PySide6.QtCore    import Qt, Signal, QObject
from PySide6.QtGui     import (QColor, QPainter, QPalette)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QHBoxLayout, QVBoxLayout, QGridLayout, QTextEdit, QFrame, QSizePolicy,
    QGraphicsDropShadowEffect, QMenu, QCheckBox
)

from scheduler import (
    Scheduler, BoardState, BoxState, GRIPPER_HEADS, TRAY_SLOTS
)
from InitSettings import BOX_COUNT, TRAY_COLS, TRAY_ROWS, NG_TRAY_SLOTS, BOX_LAYOUT

# ════════════════════════════════════════════
# DESIGN TOKENS  —  Fluent / MD3 Light
# ════════════════════════════════════════════
BG          = "#F3F3F3"
SURFACE     = "#FFFFFF"
SURFACE_ALT = "#FAFAFA"
BORDER      = "#E0E0E0"
SHADOW      = "rgba(0,0,0,0.08)"

TEXT_PRI  = "#1A1A1A"
TEXT_SEC  = "#605E5C"
TEXT_DIS  = "#ADADAD"

ACCENT    = "#0078D4"
ACCENT_LT = "#EBF3FC"

GREEN     = "#107C10"
GREEN_BG  = "#DFF6DD"
RED       = "#D13438"
RED_BG    = "#FDE7E9"
YELLOW    = "#CA5010"
YELLOW_BG = "#FFF4CE"
BLUE      = "#0078D4"
BLUE_BG   = "#EBF3FC"
PURPLE    = "#8764B8"
PURPLE_BG = "#F0EBF8"

FONT_UI   = "Segoe LearnUI"
FONT_MONO = "Consolas"

R_CARD  = "8px"
R_CHIP  = "4px"
R_BTN   = "6px"

# Số tốc độ/tỉ lệ Pass là trung bình cộng dồn, đổi rất chậm — không cần
# vẽ lại nhanh hơn mức này dù backend gửi update dồn dập hơn nhiều.
METRICS_REFRESH_INTERVAL = 1.0  # giây

BOX_THEME = {
    BoxState.EMPTY   : (SURFACE,    BORDER,  TEXT_DIS),
    BoxState.READY   : (BLUE_BG,    BLUE,    BLUE),
    BoxState.TESTING : (YELLOW_BG,  YELLOW,  YELLOW),
    BoxState.PASS    : (GREEN_BG,   GREEN,   GREEN),
    BoxState.FAIL    : (RED_BG,     RED,     RED),
    BoxState.ERROR   : ("#FFF4CE",  "#CA5010","#CA5010"),
    BoxState.UNKNOWN : (SURFACE_ALT, BORDER, TEXT_DIS),
}

BOARD_COLOR = {
    BoardState.UNTESTED: BLUE,
    BoardState.PASS    : GREEN,
    BoardState.NG      : RED,
}

# ════════════════════════════════════════════
# SIGNAL BRIDGE
# ════════════════════════════════════════════
class Bridge(QObject):
    log    = Signal(str)
    update = Signal()


# ════════════════════════════════════════════
# REUSABLE WIDGETS
# ════════════════════════════════════════════

def shadow(widget, blur=12, dx=0, dy=2, color="#00000018"):
    fx = QGraphicsDropShadowEffect(widget)
    fx.setBlurRadius(blur)
    fx.setOffset(dx, dy)
    fx.setColor(QColor(color))
    widget.setGraphicsEffect(fx)
    return widget


class Card(QFrame):
    def __init__(self, parent=None, pad=(12, 10, 12, 10)):
        super().__init__(parent)
        self.setStyleSheet(
            f"Card {{ background:{SURFACE}; border:1px solid {BORDER}; "
            f"border-radius:{R_CARD}; }}"
        )
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(*pad)
        self._layout.setSpacing(6)
        shadow(self)

    def layout(self): return self._layout


class SectionHead(QLabel):
    def __init__(self, text, color=TEXT_PRI, size=9, bold=True, parent=None):
        super().__init__(text, parent)
        weight = "600" if bold else "400"
        self.setStyleSheet(
            f"color:{color}; font-family:'{FONT_UI}'; font-size:{size}pt; "
            f"font-weight:{weight}; background:transparent; letter-spacing:0.5px;"
        )


class Chip(QLabel):
    def __init__(self, text, bg, fg, parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignCenter)
        self.setFixedHeight(18)
        self.setStyleSheet(
            f"background:{bg}; color:{fg}; font-family:'{FONT_UI}'; "
            f"font-size:7pt; font-weight:600; border-radius:{R_CHIP}; padding:0 6px;"
        )


# ════════════════════════════════════════════
# BOX CARD
# ════════════════════════════════════════════
class BoxCard(QFrame):
    def __init__(self, box_id: int, on_edit=None, on_toggle=None, parent=None):
        super().__init__(parent)
        self.box_id = box_id
        self.on_edit = on_edit          # callback(box_id, board_state|None)
        self.on_toggle = on_toggle      # callback(box_id, enabled: bool)
        self._editable = False
        self._enabled = True
        self._last_state = BoxState.UNKNOWN
        self._last_board = None
        self.setMinimumSize(112, 86)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        vb = QVBoxLayout(self)
        vb.setContentsMargins(6, 6, 6, 6)
        vb.setSpacing(2)

        top_hb = QHBoxLayout()
        top_hb.setSpacing(2)
        self._id_lbl = QLabel(f"Box {box_id:02d}", self)
        self._id_lbl.setStyleSheet(
            f"font-family:'{FONT_UI}'; font-size:7pt; font-weight:600; "
            f"color:{TEXT_SEC}; background:transparent;"
        )
        top_hb.addWidget(self._id_lbl)
        top_hb.addStretch()

        self._enable_chk = QCheckBox(self)
        self._enable_chk.setChecked(True)
        self._enable_chk.setFixedSize(14, 14)
        self._enable_chk.setToolTip("Bật/tắt sử dụng box này trong lịch chạy")
        self._enable_chk.setCursor(Qt.PointingHandCursor)
        self._enable_chk.toggled.connect(self._on_toggle_changed)
        top_hb.addWidget(self._enable_chk)
        vb.addLayout(top_hb)

        self._state_lbl = QLabel("UNKNOWN", self)
        self._state_lbl.setAlignment(Qt.AlignCenter)
        self._state_lbl.setStyleSheet(
            f"font-family:'{FONT_UI}'; font-size:7pt; font-weight:700; "
            f"color:{TEXT_DIS}; background:transparent;"
        )

        self._board_lbl = QLabel("", self)
        self._board_lbl.setAlignment(Qt.AlignCenter)
        self._board_lbl.setStyleSheet(
            f"font-family:'{FONT_MONO}'; font-size:6pt; color:{TEXT_DIS}; background:transparent;"
        )

        self._metric_lbl = QLabel("", self)
        self._metric_lbl.setAlignment(Qt.AlignCenter)
        self._metric_lbl.setStyleSheet(
            f"font-family:'{FONT_MONO}'; font-size:6pt; color:{TEXT_SEC}; background:transparent;"
        )

        vb.addWidget(self._state_lbl)
        vb.addWidget(self._board_lbl)
        vb.addWidget(self._metric_lbl)
        vb.addStretch()

        self._apply()

    def _on_toggle_changed(self, checked: bool):
        if self.on_toggle:
            self.on_toggle(self.box_id, checked)

    def _apply(self):
        if not self._enabled:
            bg, border, fg = (SURFACE_ALT, TEXT_DIS, TEXT_DIS)
            border_style = "dashed"
            state_text = "DISABLED"
        else:
            bg, border, fg = BOX_THEME.get(self._last_state, (SURFACE, BORDER, TEXT_DIS))
            border_style = "solid"
            state_text = self._last_state.value.upper()

        self.setStyleSheet(
            f"BoxCard {{ background:{bg}; border:1.5px {border_style} {border}; "
            f"border-radius:6px; }}"
        )
        self._state_lbl.setText(state_text)
        self._state_lbl.setStyleSheet(
            f"font-family:'{FONT_UI}'; font-size:7pt; font-weight:700; "
            f"color:{fg}; background:transparent;"
        )
        self._board_lbl.setText(str(self._last_board) if (self._enabled and self._last_board) else "")

    def refresh(self, state: BoxState, board):
        self._last_state = state
        self._last_board = board
        self._apply()

    def refresh_metrics(self, tested: int, passed: int, rate_per_hour: float, pass_pct):
        pct_text = f"{pass_pct:.0f}%" if pass_pct is not None else "—"
        self._metric_lbl.setText(f"{tested}T · {pct_text} · {rate_per_hour:.1f}/h")

    def set_enabled_state(self, enabled: bool):
        self._enabled = enabled
        self._enable_chk.blockSignals(True)
        self._enable_chk.setChecked(enabled)
        self._enable_chk.blockSignals(False)
        self._apply()

    # ── Sửa tay khi scheduler đang dừng ──────────
    def set_editable(self, editable: bool):
        self._editable = editable and self.on_edit is not None
        self.setCursor(Qt.PointingHandCursor if self._editable else Qt.ArrowCursor)
        self.setToolTip(
            "Nhấp để sửa tay trạng thái box (đang dừng)" if self._editable else ""
        )

    def mousePressEvent(self, event):
        if self._editable and event.button() == Qt.RightButton:
            self._show_edit_menu(event.globalPosition().toPoint())
        else:
            super().mousePressEvent(event)

    def _show_edit_menu(self, global_pos):
        menu = QMenu(self)
        menu.addAction(
            "Set to EMPTY",
            lambda: self.on_edit(self.box_id, None)
        )
        menu.addSeparator()
        menu.addAction(
            "Set to UNTESTED",
            lambda: self.on_edit(self.box_id, BoardState.UNTESTED)
        )
        menu.addAction(
            "Set to PASS",
            lambda: self.on_edit(self.box_id, BoardState.PASS)
        )
        menu.addAction(
            "Set to NG",
            lambda: self.on_edit(self.box_id, BoardState.NG)
        )
        menu.exec(global_pos)


# ════════════════════════════════════════════
# GRIPPER HEAD CARD
# ════════════════════════════════════════════
class HeadCard(QFrame):
    def __init__(self, head_id: int, on_edit=None, on_toggle=None, parent=None):
        super().__init__(parent)
        self.head_id = head_id
        self.on_edit = on_edit          # callback(head_id, board_state|None)
        self.on_toggle = on_toggle      # callback(head_id, enabled: bool)
        self._editable = False
        self._enabled = True
        self._last_board = None
        self.setMinimumSize(90, 56)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        vb = QVBoxLayout(self)
        vb.setContentsMargins(6, 5, 6, 5)
        vb.setSpacing(2)

        top_hb = QHBoxLayout()
        top_hb.setSpacing(2)
        self._id_lbl = QLabel(f"Head {head_id}", self)
        self._id_lbl.setStyleSheet(
            f"font-family:'{FONT_UI}'; font-size:7pt; font-weight:600; "
            f"color:{TEXT_SEC}; background:transparent;"
        )
        top_hb.addWidget(self._id_lbl)
        top_hb.addStretch()

        self._enable_chk = QCheckBox(self)
        self._enable_chk.setChecked(True)
        self._enable_chk.setFixedSize(14, 14)
        self._enable_chk.setToolTip("Bật/tắt sử dụng tay gắp này trong lịch chạy")
        self._enable_chk.setCursor(Qt.PointingHandCursor)
        self._enable_chk.toggled.connect(self._on_toggle_changed)
        top_hb.addWidget(self._enable_chk)
        vb.addLayout(top_hb)

        self._board_lbl = QLabel("empty", self)
        self._board_lbl.setAlignment(Qt.AlignCenter)
        self._board_lbl.setStyleSheet(
            f"font-family:'{FONT_MONO}'; font-size:7pt; color:{TEXT_DIS}; background:transparent;"
        )

        vb.addWidget(self._board_lbl)

        self._set_empty()

    def _on_toggle_changed(self, checked: bool):
        if self.on_toggle:
            self.on_toggle(self.head_id, checked)

    def _set_empty(self):
        if not self._enabled:
            self.setStyleSheet(
                f"HeadCard {{ background:{SURFACE_ALT}; border:1.5px dashed {TEXT_DIS}; border-radius:6px; }}"
            )
            self._board_lbl.setText("disabled")
        else:
            self.setStyleSheet(
                f"HeadCard {{ background:{SURFACE_ALT}; border:1.5px dashed {BORDER}; border-radius:6px; }}"
            )
            self._board_lbl.setText("empty")
        self._board_lbl.setStyleSheet(
            f"font-family:'{FONT_MONO}'; font-size:7pt; color:{TEXT_DIS}; background:transparent;"
        )

    def refresh(self, board):
        self._last_board = board
        if not self._enabled or board is None:
            self._set_empty()
        else:
            color = BOARD_COLOR.get(board.state, TEXT_DIS)
            bg    = {
                BoardState.PASS    : GREEN_BG,
                BoardState.NG      : RED_BG,
                BoardState.UNTESTED: BLUE_BG,
            }.get(board.state, SURFACE_ALT)
            self.setStyleSheet(
                f"HeadCard {{ background:{bg}; border:1.5px solid {color}; border-radius:6px; }}"
            )
            self._board_lbl.setText(str(board))
            self._board_lbl.setStyleSheet(
                f"font-family:'{FONT_MONO}'; font-size:7pt; font-weight:600; "
                f"color:{color}; background:transparent;"
            )

    def set_enabled_state(self, enabled: bool):
        self._enabled = enabled
        self._enable_chk.blockSignals(True)
        self._enable_chk.setChecked(enabled)
        self._enable_chk.blockSignals(False)
        self.refresh(self._last_board)

    # ── Sửa tay khi scheduler đang dừng ──────────
    def set_editable(self, editable: bool):
        self._editable = editable and self.on_edit is not None
        self.setCursor(Qt.PointingHandCursor if self._editable else Qt.ArrowCursor)
        self.setToolTip(
            "Nhấp để sửa tay board trên tay gắp (đang dừng)" if self._editable else ""
        )

    def mousePressEvent(self, event):
        if self._editable and event.button() == Qt.RightButton:
            self._show_edit_menu(event.globalPosition().toPoint())
        else:
            super().mousePressEvent(event)

    def _show_edit_menu(self, global_pos):
        menu = QMenu(self)
        menu.addAction(
            "Set to EMPTY",
            lambda: self.on_edit(self.head_id, None)
        )
        menu.addSeparator()
        menu.addAction(
            "Set to UNTESTED",
            lambda: self.on_edit(self.head_id, BoardState.UNTESTED)
        )
        menu.addAction(
            "Set to PASS",
            lambda: self.on_edit(self.head_id, BoardState.PASS)
        )
        menu.addAction(
            "Set to NG",
            lambda: self.on_edit(self.head_id, BoardState.NG)
        )
        menu.exec(global_pos)


# ════════════════════════════════════════════
# TRAY CANVAS  — lưới COLS×ROWS đọc từ station.ini
# ════════════════════════════════════════════
class TrayCanvas(QWidget):
    """
    Hiển thị n_slots slot tray dạng lưới COLS × ROWS (đọc từ station.ini).
    Mặc định theo config hiện tại: COLS=8, ROWS=5 (8 cột × 5 hàng = 40 slot).
    Kích thước mỗi ô tự co giãn theo widget.
    """
    COLS = TRAY_COLS
    ROWS = TRAY_ROWS
    GAP  = 3

    def __init__(self, n_slots: int = TRAY_SLOTS, tray_id: Optional[int] = None,
                 on_edit=None, parent=None):
        super().__init__(parent)
        self.n_slots = n_slots
        self.tray_id = tray_id           # None → không cho sửa tay (vd NG tray)
        self.on_edit = on_edit           # callback(tray_id, slot_idx, board_state|None)
        self._editable = False
        self._colors: list[str] = [BORDER] * n_slots
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(self.COLS * 20 + self.GAP * (self.COLS + 1),
                            self.ROWS * 16 + self.GAP * (self.ROWS + 1))

    def set_slots(self, slots: list):
        self._colors = []
        for b in slots:
            if b is None:
                self._colors.append(BORDER)
            else:
                self._colors.append(BOARD_COLOR.get(b.state, TEXT_DIS))
        # pad to n_slots
        while len(self._colors) < self.n_slots:
            self._colors.append(BORDER)
        self.update()

    def set_ng(self, count: int):
        self._colors = [RED if i < count else BORDER for i in range(self.n_slots)]
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        gap = self.GAP

        cell_w = (w - gap * (self.COLS + 1)) / self.COLS
        cell_h = (h - gap * (self.ROWS + 1)) / self.ROWS

        for i, color in enumerate(self._colors):
            col = i % self.COLS
            row = i // self.COLS
            if row >= self.ROWS:
                break
            x = gap + col * (cell_w + gap)
            y = gap + row * (cell_h + gap)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(color))
            p.drawRoundedRect(int(x), int(y), int(cell_w), int(cell_h), 3, 3)

        p.end()

    # ── Sửa tay khi scheduler đang dừng ──────────
    def set_editable(self, editable: bool):
        self._editable = editable and self.tray_id is not None and self.on_edit is not None
        self.setCursor(Qt.PointingHandCursor if self._editable else Qt.ArrowCursor)
        self.setToolTip(
            "Nhấp vào 1 ô để sửa tay trạng thái liệu trên tray (đang dừng)"
            if self._editable else ""
        )

    def _slot_at(self, pos) -> Optional[int]:
        w, h = self.width(), self.height()
        gap = self.GAP
        cell_w = (w - gap * (self.COLS + 1)) / self.COLS
        cell_h = (h - gap * (self.ROWS + 1)) / self.ROWS
        if cell_w <= 0 or cell_h <= 0:
            return None
        col = int((pos.x() - gap) // (cell_w + gap))
        row = int((pos.y() - gap) // (cell_h + gap))
        if 0 <= col < self.COLS and 0 <= row < self.ROWS:
            idx = row * self.COLS + col
            if idx < self.n_slots:
                return idx
        return None

    def mousePressEvent(self, event):
        if not self._editable or event.button() != Qt.RightButton:
            super().mousePressEvent(event)
            return
        idx = self._slot_at(event.position().toPoint())
        if idx is None:
            return
        self._show_edit_menu(idx, event.globalPosition().toPoint())

    def _show_edit_menu(self, idx: int, global_pos):
        menu = QMenu(self)
        menu.addAction(
            f"Set Slot {idx} EMPTY",
            lambda: self.on_edit(self.tray_id, idx, None)
        )
        menu.addSeparator()
        menu.addAction(
            "Set to UNTESTED",
            lambda: self.on_edit(self.tray_id, idx, BoardState.UNTESTED)
        )
        menu.addAction(
            "Set to PASS",
            lambda: self.on_edit(self.tray_id, idx, BoardState.PASS)
        )
        menu.addAction(
            "Set to NG",
            lambda: self.on_edit(self.tray_id, idx, BoardState.NG)
        )
        menu.exec(global_pos)


class TrayPanel(QFrame):
    def __init__(self, title: str, title_color: str, n_slots: int = TRAY_SLOTS,
                 tray_id: Optional[int] = None, on_edit=None, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setStyleSheet(
            f"TrayPanel {{ background:{SURFACE}; border:1px solid {BORDER}; border-radius:{R_CARD}; }}"
        )
        shadow(self)

        vb = QVBoxLayout(self)
        vb.setContentsMargins(10, 8, 10, 10)
        vb.setSpacing(4)

        hdr = QHBoxLayout()
        self._title_lbl = QLabel(title)
        self._title_lbl.setStyleSheet(
            f"font-family:'{FONT_UI}'; font-size:8pt; font-weight:700; "
            f"color:{title_color}; background:transparent;"
        )
        self._info_lbl = QLabel("")
        self._info_lbl.setStyleSheet(
            f"font-family:'{FONT_UI}'; font-size:7pt; color:{TEXT_SEC}; background:transparent;"
        )
        hdr.addWidget(self._title_lbl)
        hdr.addStretch()
        hdr.addWidget(self._info_lbl)
        vb.addLayout(hdr)

        self._canvas = TrayCanvas(n_slots, tray_id=tray_id, on_edit=on_edit, parent=self)
        self._canvas.setMinimumHeight(90)
        vb.addWidget(self._canvas)

    def set_editable(self, editable: bool):
        self._canvas.set_editable(editable)

    def update_slots(self, slots: list):
        untested = sum(1 for b in slots if b and b.state == BoardState.UNTESTED)
        passed   = sum(1 for b in slots if b and b.state == BoardState.PASS)
        empty    = sum(1 for b in slots if b is None)
        self._info_lbl.setText(f"Untested {untested}  ·  Pass {passed}  ·  Empty {empty}")
        self._canvas.set_slots(slots)

    def update_ng(self, count: int):
        self._info_lbl.setText(f"{count} boards")
        self._canvas.set_ng(count)


# ════════════════════════════════════════════
# LOG PANEL
# ════════════════════════════════════════════
class LogPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.setStyleSheet(
            f"LogPanel {{ background:{SURFACE}; border:1px solid {BORDER}; border-radius:{R_CARD}; }}"
        )
        shadow(self)

        vb = QVBoxLayout(self)
        vb.setContentsMargins(0, 0, 0, 0)

        self._text = QTextEdit(self)
        self._text.setReadOnly(True)
        self._text.setStyleSheet(
            f"QTextEdit {{ background:transparent; color:{TEXT_PRI}; "
            f"font-family:'{FONT_MONO}'; font-size:8pt; border:none; "
            f"padding:8px; }}"
            f"QScrollBar:vertical {{ background:{SURFACE_ALT}; width:6px; border:none; border-radius:3px; }}"
            f"QScrollBar::handle:vertical {{ background:{BORDER}; border-radius:3px; }}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}"
        )
        vb.addWidget(self._text)

    _TAG = {
        "send" : BLUE,
        "recv" : GREEN,
        "warn" : YELLOW,
        "error": RED,
        "cycle": PURPLE,
        "info" : TEXT_SEC,
    }

    def append(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        if "→" in msg:       tag = "send"
        elif "←" in msg:     tag = "recv"
        elif "WARN" in msg:  tag = "warn"
        elif "ERROR" in msg: tag = "error"
        elif "CYCLE" in msg.upper(): tag = "cycle"
        else:                tag = "info"
        color = self._TAG[tag]
        html = (f'<span style="color:{TEXT_DIS};font-size:7pt;">{ts}</span> '
                f'<span style="color:{color};font-family:{FONT_MONO};font-size:8pt;">{msg}</span>')
        self._text.append(html)
        sb = self._text.verticalScrollBar()
        sb.setValue(sb.maximum())


# ════════════════════════════════════════════
# STAT PILL
# ════════════════════════════════════════════
class StatPill(QFrame):
    def __init__(self, label: str, color: str, parent=None):
        super().__init__(parent)
        self._color = color
        self.setFixedHeight(52)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet(
            f"StatPill {{ background:{SURFACE}; border:1px solid {BORDER}; "
            f"border-radius:{R_CARD}; }}"
        )
        shadow(self, blur=8, dy=1)

        vb = QVBoxLayout(self)
        vb.setContentsMargins(12, 6, 12, 6)
        vb.setSpacing(1)

        self._val = QLabel("0")
        self._val.setStyleSheet(
            f"font-family:'{FONT_UI}'; font-size:14pt; font-weight:700; "
            f"color:{color}; background:transparent;"
        )
        self._lbl = QLabel(label)
        self._lbl.setStyleSheet(
            f"font-family:'{FONT_UI}'; font-size:7pt; color:{TEXT_SEC}; background:transparent;"
        )
        vb.addWidget(self._val)
        vb.addWidget(self._lbl)

    def set_value(self, v: int):
        self._val.setText(str(v))


# ════════════════════════════════════════════
# MAIN WINDOW
# ════════════════════════════════════════════
class StationUI(QMainWindow):
    def __init__(self, scheduler: Scheduler):
        super().__init__()
        self.sched   = scheduler
        self._bridge = Bridge()
        self._bridge.log.connect(self._on_log)
        self._bridge.update.connect(self._refresh)
        self._last_metrics_refresh = 0.0   # 0 → lần _refresh() đầu tiên luôn hiện số ngay

        self.setWindowTitle("Test Station")
        self.setMinimumSize(900, 600)
        # Start maximized to fill current screen; user can resize freely
        self.showMaximized()
        self.setStyleSheet(f"QMainWindow {{ background:{BG}; }}")

        self._build()
        self._refresh()

    # ════════════════════════════════════════
    # BUILD
    # ════════════════════════════════════════
    def _build(self):
        root = QWidget()
        root.setStyleSheet(f"background:{BG};")
        self.setCentralWidget(root)

        main_vb = QVBoxLayout(root)
        main_vb.setContentsMargins(0, 0, 0, 0)
        main_vb.setSpacing(0)

        # ── Top bar ─────────────────────────────
        topbar = QFrame()
        topbar.setFixedHeight(52)
        topbar.setStyleSheet(
            f"background:{SURFACE}; border-bottom:1px solid {BORDER};"
        )
        tb_hb = QHBoxLayout(topbar)
        tb_hb.setContentsMargins(24, 0, 24, 0)

        logo_row = QHBoxLayout()
        logo_row.setSpacing(10)
        accent_bar = QFrame()
        accent_bar.setFixedSize(4, 28)
        accent_bar.setStyleSheet(f"background:{ACCENT}; border-radius:2px;")
        title = QLabel("Test Station")
        title.setStyleSheet(
            f"font-family:'{FONT_UI}'; font-size:14pt; font-weight:600; "
            f"color:{TEXT_PRI}; background:transparent; letter-spacing:-0.3px;"
        )
        logo_row.addWidget(accent_bar)
        logo_row.addWidget(title)
        logo_row.addSpacing(8)

        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet(
            f"font-size:10pt; color:{TEXT_DIS}; background:transparent;"
        )
        self._status_text = QLabel("Chưa kết nối")
        self._status_text.setStyleSheet(
            f"font-family:'{FONT_UI}'; font-size:9pt; color:{TEXT_SEC}; background:transparent;"
        )
        logo_row.addWidget(self._status_dot)
        logo_row.addWidget(self._status_text)
        logo_row.addStretch()

        tb_hb.addLayout(logo_row)
        tb_hb.addStretch()

        self._start_btn = QPushButton("  Start")
        self._start_btn.setFixedSize(100, 34)
        self._start_btn.setStyleSheet(
            f"QPushButton {{ background:{ACCENT}; color:white; "
            f"font-family:'{FONT_UI}'; font-size:9pt; font-weight:600; "
            f"border:none; border-radius:{R_BTN}; }}"
            f"QPushButton:hover {{ background:#106EBE; }}"
            f"QPushButton:disabled {{ background:{BORDER}; color:{TEXT_DIS}; }}"
        )
        self._start_btn.clicked.connect(self._on_start)

        stop_btn = QPushButton("  Stop")
        stop_btn.setFixedSize(100, 34)
        stop_btn.setStyleSheet(
            f"QPushButton {{ background:{RED}; color:white; "
            f"font-family:'{FONT_UI}'; font-size:9pt; font-weight:600; "
            f"border:none; border-radius:{R_BTN}; }}"
            f"QPushButton:hover {{ background:#A4262C; }}"
        )
        stop_btn.clicked.connect(self._on_stop)

        tb_hb.addWidget(self._start_btn)
        tb_hb.addSpacing(8)
        tb_hb.addWidget(stop_btn)

        main_vb.addWidget(topbar)

        # ── Body ────────────────────────────────
        body = QWidget()
        body.setStyleSheet(f"background:{BG};")
        body_hb = QHBoxLayout(body)
        body_hb.setContentsMargins(20, 16, 20, 16)
        body_hb.setSpacing(16)

        left  = QVBoxLayout()
        left.setSpacing(12)
        right = QVBoxLayout()
        right.setSpacing(10)
        right.setContentsMargins(0, 0, 0, 0)

        # Right panel fixed width; left stretches
        body_hb.addLayout(left, stretch=1)
        body_hb.addLayout(right, stretch=0)

        main_vb.addWidget(body, stretch=1)

        # ── STAT PILLS ──────────────────────────
        stat_row = QHBoxLayout()
        stat_row.setSpacing(10)
        self._pill_loaded = StatPill("Đã nạp",    ACCENT)
        self._pill_pass   = StatPill("Pass",       GREEN)
        self._pill_ng     = StatPill("NG",         RED)
        self._pill_change = StatPill("Tray Pass",   PURPLE)
        self._pill_rate      = StatPill("Tốc độ (SP/h)", ACCENT)
        self._pill_pass_pct  = StatPill("Tỉ lệ Pass",    GREEN)
        for p in (self._pill_loaded, self._pill_pass, self._pill_ng, self._pill_change,
                  self._pill_rate, self._pill_pass_pct):
            stat_row.addWidget(p)
        left.addLayout(stat_row)

        # ── BOX GRID ────────────────────────────
        box_card = Card(pad=(12, 10, 12, 12))
        box_vb   = box_card.layout()
        box_vb.addWidget(SectionHead("TEST BOXES", color=TEXT_SEC, size=8))

        sides_hb = QHBoxLayout()
        sides_hb.setSpacing(20)
        self._box_cards: list[BoxCard] = []

        for label, rng in BOX_LAYOUT:
            ids = list(rng)
            full_label = f"{label}  ({ids[0]}–{ids[-1]})"
            per_row = (len(ids) + 1) // 2   # chia đều thành 2 hàng, tránh dày/chèn lên nhau

            col_vb = QVBoxLayout()
            col_vb.setSpacing(4)
            col_vb.addWidget(SectionHead(full_label, color=TEXT_DIS, size=7, bold=False))

            grid = QGridLayout()
            grid.setSpacing(6)
            for i, box_id in enumerate(ids):
                card = BoxCard(box_id, on_edit=self._on_box_edit, on_toggle=self._on_box_toggle)
                self._box_cards.append(card)
                grid.addWidget(card, i // per_row, i % per_row)
            col_vb.addLayout(grid)
            sides_hb.addLayout(col_vb)

        sides_hb.addStretch()
        box_vb.addLayout(sides_hb)
        left.addWidget(box_card)

        # ── GRIPPER ─────────────────────────────
        grip_card = Card(pad=(12, 10, 12, 12))
        grip_vb   = grip_card.layout()
        grip_vb.addWidget(SectionHead(f"GRIPPER  —  {GRIPPER_HEADS} heads", color=TEXT_SEC, size=8))
        grip_row_hb = QHBoxLayout()
        grip_row_hb.setSpacing(6)
        self._head_cards: list[HeadCard] = []
        for i in range(GRIPPER_HEADS):
            card = HeadCard(i, on_edit=self._on_head_edit, on_toggle=self._on_head_toggle)
            self._head_cards.append(card)
            grip_row_hb.addWidget(card)
        grip_row_hb.addStretch()
        grip_vb.addLayout(grip_row_hb)
        left.addWidget(grip_card)

        # ── TRAYS ───────────────────────────────
        tray_card = Card(pad=(12, 10, 12, 12))
        tray_vb   = tray_card.layout()
        tray_vb.addWidget(SectionHead(f"TRAYS  —  {TRAY_ROWS} × {TRAY_COLS}", color=TEXT_SEC, size=8))

        tray_row_hb = QHBoxLayout()
        tray_row_hb.setSpacing(10)

        self._tray1_panel = TrayPanel("Tray 1  —  Input / Pass", ACCENT,
                                       tray_id=1, on_edit=self._on_tray_edit)
        self._tray2_panel = TrayPanel("Tray 2  —  Backup",       BLUE,
                                       tray_id=2, on_edit=self._on_tray_edit)
        self._ng_panel    = TrayPanel("NG Tray", RED, n_slots=NG_TRAY_SLOTS)

        for panel in (self._tray1_panel, self._tray2_panel, self._ng_panel):
            tray_row_hb.addWidget(panel)

        tray_vb.addLayout(tray_row_hb)
        left.addWidget(tray_card)
        left.addStretch()

        # ── RIGHT: LOG ──────────────────────────
        right_frame = QFrame()
        right_frame.setFixedWidth(340)
        right_frame.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        right_frame.setStyleSheet(
            f"QFrame {{ background:{SURFACE}; border:1px solid {BORDER}; border-radius:{R_CARD}; }}"
        )
        shadow(right_frame)

        right_vb = QVBoxLayout(right_frame)
        right_vb.setContentsMargins(0, 0, 0, 0)
        right_vb.setSpacing(0)

        log_header = QFrame()
        log_header.setFixedHeight(36)
        log_header.setStyleSheet(
            f"background:{SURFACE_ALT}; border-bottom:1px solid {BORDER}; "
            f"border-top-left-radius:{R_CARD}; border-top-right-radius:{R_CARD};"
        )
        lh_hb = QHBoxLayout(log_header)
        lh_hb.setContentsMargins(12, 0, 12, 0)
        lh_hb.addWidget(SectionHead("Log", color=TEXT_SEC, size=8))
        lh_hb.addStretch()

        self._log_panel = LogPanel()
        right_vb.addWidget(log_header)
        right_vb.addWidget(self._log_panel, stretch=1)

        right.addWidget(right_frame, stretch=1)

    # ════════════════════════════════════════
    # CALLBACKS
    # ════════════════════════════════════════
    def _on_start(self):
        self._start_btn.setEnabled(False)
        self._status_dot.setStyleSheet(f"font-size:10pt; color:{YELLOW}; background:transparent;")
        self._status_text.setText("Đang kết nối...")

        def _connect():
            try:
                self.sched.connect()
                self.sched.log       = lambda m: self._bridge.log.emit(m)
                self.sched.ui_update = lambda:   self._bridge.update.emit()
                self.sched.start()
                self._bridge.log.emit("[INIT] Scheduler started")
                self._bridge.update.emit()
            except Exception as e:
                self._bridge.log.emit(f"[ERROR] {e}")
                self._start_btn.setEnabled(True)

        threading.Thread(target=_connect, daemon=True).start()

    def _on_stop(self):
        self.sched.stop()
        self._log_panel.append("[STOP] Scheduler dừng.")
        self._status_dot.setStyleSheet(f"font-size:10pt; color:{TEXT_DIS}; background:transparent;")
        self._status_text.setText("Đã dừng")
        self._start_btn.setEnabled(True)
        self._refresh()   # bật chế độ sửa tay (box/tay gắp/tray) ngay khi vừa dừng

    def _on_log(self, msg: str):
        self._log_panel.append(msg)

    # ── Sửa tay khi scheduler đang dừng ──────────────
    # Công nhân có thể lấy hàng ra / đặt thêm hàng vào box test, tay gắp,
    # hoặc tray đầu vào lúc hệ thống stop. Các callback này đồng bộ lại
    # trạng thái phần mềm cho khớp thực tế trước khi Start lại.
    def _on_box_edit(self, box_id: int, board_state):
        if self.sched.manual_set_box(box_id, board_state):
            self._refresh()

    def _on_head_edit(self, head_id: int, board_state):
        if self.sched.manual_set_gripper(head_id, board_state):
            self._refresh()

    def _on_tray_edit(self, tray_id: int, slot: int, board_state):
        if self.sched.manual_set_tray_slot(tray_id, slot, board_state):
            self._refresh()

    # ── Bật/tắt box, tay gắp — dùng được bất kỳ lúc nào ──────────
    def _on_box_toggle(self, box_id: int, enabled: bool):
        self.sched.set_box_enabled(box_id, enabled)
        self._refresh()

    def _on_head_toggle(self, head_id: int, enabled: bool):
        self.sched.set_head_enabled(head_id, enabled)
        self._refresh()

    # ════════════════════════════════════════
    # REFRESH
    # ════════════════════════════════════════
    def _refresh(self):
        snap = self.sched.get_snapshot()

        if self.sched._running:
            self._status_dot.setStyleSheet(f"font-size:10pt; color:{GREEN}; background:transparent;")
            self._status_text.setText("Đang chạy")

        st = snap["stats"]
        self._pill_loaded.set_value(st["loaded"])
        self._pill_pass.set_value(st["pass"])
        self._pill_ng.set_value(st["ng"])
        self._pill_change.set_value(st["change"])

        # Số tốc độ/tỉ lệ Pass là trung bình cộng dồn, đổi rất chậm — chỉ cập
        # nhật tối đa 1 lần/giây dù _refresh() có thể được gọi dồn dập hơn
        # (mỗi cycle scheduler + mỗi lệnh gửi robot), tránh số nhảy liên tục
        # gây rối mắt mà không mang lại thông tin gì thêm.
        now = time.monotonic()
        update_metrics = (now - self._last_metrics_refresh) >= METRICS_REFRESH_INTERVAL
        if update_metrics:
            self._last_metrics_refresh = now
            sm = snap["system_metrics"]
            self._pill_rate.set_value(f"{sm['rate_per_hour']:.1f}")
            self._pill_pass_pct.set_value(
                f"{sm['pass_pct']:.0f}%" if sm["pass_pct"] is not None else "—"
            )

        # Chỉ cho sửa tay khi scheduler đang dừng
        editable = self.sched.manual_edit_allowed()

        box_states  = snap["box_states"]
        box_boards  = snap["box_boards"]
        box_enabled = snap["box_enabled"]
        box_metrics = snap["box_metrics"]
        for card in self._box_cards:
            idx   = card.box_id - 1
            state = box_states[idx] if idx < len(box_states) else BoxState.UNKNOWN
            board = box_boards.get(card.box_id)
            card.refresh(state, board)
            card.set_editable(editable)
            card.set_enabled_state(box_enabled[idx] if idx < len(box_enabled) else True)
            if update_metrics:
                m = box_metrics[idx] if idx < len(box_metrics) else None
                if m:
                    card.refresh_metrics(m["tested"], m["pass"], m["rate_per_hour"], m["pass_pct"])

        gripper_enabled = snap["gripper_enabled"]
        for head_id, board in snap["gripper"]:
            self._head_cards[head_id].refresh(board)
            self._head_cards[head_id].set_editable(editable)
            self._head_cards[head_id].set_enabled_state(
                gripper_enabled[head_id] if head_id < len(gripper_enabled) else True
            )

        self._tray1_panel.update_slots(snap["tray1_slots"])
        self._tray2_panel.update_slots(snap["tray2_slots"])
        self._ng_panel.update_ng(snap["ng_count"])
        self._tray1_panel.set_editable(editable)
        self._tray2_panel.set_editable(editable)


# ════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════
if __name__ == "__main__":
    sched = Scheduler()
    app   = QApplication(sys.argv)
    app.setStyle("Fusion")

    pal = QPalette()
    pal.setColor(QPalette.Window,          QColor(BG))
    pal.setColor(QPalette.WindowText,      QColor(TEXT_PRI))
    pal.setColor(QPalette.Base,            QColor(SURFACE))
    pal.setColor(QPalette.AlternateBase,   QColor(SURFACE_ALT))
    pal.setColor(QPalette.Text,            QColor(TEXT_PRI))
    pal.setColor(QPalette.Button,          QColor(SURFACE))
    pal.setColor(QPalette.ButtonText,      QColor(TEXT_PRI))
    pal.setColor(QPalette.Highlight,       QColor(ACCENT))
    pal.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    app.setPalette(pal)

    win = StationUI(sched)
    sys.exit(app.exec())