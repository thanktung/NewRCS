"""
widgets.py - Reusable Qt widgets. They only render data they are given
(BoxView / Board / list of boards) and report user actions through callbacks.
No widget talks to the scheduler directly.
"""

from __future__ import annotations

import time
from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QCheckBox, QFrame, QGraphicsDropShadowEffect,
                               QHBoxLayout, QLabel, QMenu, QSizePolicy,
                               QTextEdit, QVBoxLayout, QWidget)

from ..core.snapshot import BoxView
from ..models import BoardState, BoxState
from . import theme as T


def shadow(widget, blur=12, dx=0, dy=2, color="#00000018"):
    fx = QGraphicsDropShadowEffect(widget)
    fx.setBlurRadius(blur)
    fx.setOffset(dx, dy)
    fx.setColor(QColor(color))
    widget.setGraphicsEffect(fx)
    return widget


def fmt_age(sec: float) -> str:
    sec = int(sec)
    return f"{sec}s" if sec < 60 else f"{sec // 60}:{sec % 60:02d}"


def _edit_menu(parent, on_pick: Callable, empty_text: str = "Set to EMPTY"):
    """Right-click menu shared by box / head / tray slot editing."""
    menu = QMenu(parent)
    menu.addAction(empty_text, lambda: on_pick(None))
    menu.addSeparator()
    menu.addAction("Set to UNTESTED", lambda: on_pick(BoardState.UNTESTED))
    menu.addAction("Set to PASS", lambda: on_pick(BoardState.PASS))
    menu.addAction("Set to NG", lambda: on_pick(BoardState.NG))
    return menu


class Card(QFrame):
    def __init__(self, parent=None, pad=(12, 10, 12, 10)):
        super().__init__(parent)
        self.setStyleSheet(
            f"Card {{ background:{T.SURFACE}; border:1px solid {T.BORDER}; "
            f"border-radius:{T.R_CARD}; }}")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(*pad)
        self._layout.setSpacing(6)
        shadow(self)

    def layout(self):
        return self._layout


class SectionHead(QLabel):
    def __init__(self, text, color=T.TEXT_PRI, size=9, bold=True, parent=None):
        super().__init__(text, parent)
        weight = "600" if bold else "400"
        self.setStyleSheet(
            f"color:{color}; font-family:'{T.FONT_UI}'; font-size:{size}pt; "
            f"font-weight:{weight}; background:transparent; letter-spacing:0.5px;")


class Chip(QLabel):
    """Small coloured label (SIM / REAL badge, robot status ...)."""

    def __init__(self, text="", bg=T.BORDER, fg=T.TEXT_SEC, parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignCenter)
        self.setFixedHeight(20)
        self.set_colors(bg, fg)

    def set_colors(self, bg: str, fg: str) -> None:
        self.setStyleSheet(
            f"background:{bg}; color:{fg}; font-family:'{T.FONT_UI}'; "
            f"font-size:8pt; font-weight:600; border-radius:{T.R_CHIP}; padding:0 8px;")


class StatPill(QFrame):
    def __init__(self, label: str, color: str, parent=None):
        super().__init__(parent)
        self.setFixedHeight(52)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet(
            f"StatPill {{ background:{T.SURFACE}; border:1px solid {T.BORDER}; "
            f"border-radius:{T.R_CARD}; }}")
        shadow(self, blur=8, dy=1)
        vb = QVBoxLayout(self)
        vb.setContentsMargins(12, 6, 12, 6)
        vb.setSpacing(1)
        self._val = QLabel("0")
        self._val.setStyleSheet(
            f"font-family:'{T.FONT_UI}'; font-size:14pt; font-weight:700; "
            f"color:{color}; background:transparent;")
        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"font-family:'{T.FONT_UI}'; font-size:7pt; color:{T.TEXT_SEC}; "
            f"background:transparent;")
        vb.addWidget(self._val)
        vb.addWidget(lbl)

    def set_value(self, v) -> None:
        text = str(v)
        if self._val.text() != text:
            self._val.setText(text)


class Banner(QFrame):
    """Full-width message bar: red for FAULT, amber for alerts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        hb = QHBoxLayout(self)
        hb.setContentsMargins(24, 6, 24, 6)
        self._text = QLabel("")
        self._text.setWordWrap(True)
        hb.addWidget(self._text, stretch=1)
        self._extra = QHBoxLayout()
        hb.addLayout(self._extra)
        self.hide()

    def add_widget(self, w) -> None:
        self._extra.addWidget(w)

    def show_message(self, text: str, fg: str, bg: str) -> None:
        self.setStyleSheet(f"background:{bg}; border-bottom:1px solid {fg};")
        self._text.setStyleSheet(
            f"color:{fg}; font-family:'{T.FONT_UI}'; font-size:9pt; font-weight:600; "
            f"background:transparent; border:none;")
        if self._text.text() != text:
            self._text.setText(text)
        self.show()


# ────────────────────────────────────────────
# Box / head cards
# ────────────────────────────────────────────
class _EditableCard(QFrame):
    """Common behaviour: enable checkbox + right-click edit when allowed."""

    def __init__(self, ident: int, on_edit, on_toggle, parent=None):
        super().__init__(parent)
        self.ident = ident
        self.on_edit = on_edit
        self.on_toggle = on_toggle
        self._editable = False
        self._style_key = None

    def _make_checkbox(self, tip: str) -> QCheckBox:
        chk = QCheckBox(self)
        chk.setChecked(True)
        chk.setFixedSize(14, 14)
        chk.setToolTip(tip)
        chk.setCursor(Qt.PointingHandCursor)
        chk.toggled.connect(self._on_toggle_changed)
        return chk

    def _on_toggle_changed(self, checked: bool) -> None:
        if self.on_toggle:
            self.on_toggle(self.ident, checked)

    def set_editable(self, editable: bool) -> None:
        editable = editable and self.on_edit is not None
        if editable == self._editable:
            return
        self._editable = editable
        self.setCursor(Qt.PointingHandCursor if editable else Qt.ArrowCursor)
        self.setToolTip("Chuột phải để sửa tay (đang dừng)" if editable else "")

    def mousePressEvent(self, event):
        if self._editable and event.button() == Qt.RightButton:
            _edit_menu(self, lambda st: self.on_edit(self.ident, st)).exec(
                event.globalPosition().toPoint())
        else:
            super().mousePressEvent(event)

    def _set_checked(self, chk: QCheckBox, value: bool) -> None:
        if chk.isChecked() != value:
            chk.blockSignals(True)
            chk.setChecked(value)
            chk.blockSignals(False)


class BoxCard(_EditableCard):
    def __init__(self, box_id: int, on_edit=None, on_toggle=None, parent=None):
        super().__init__(box_id, on_edit, on_toggle, parent)
        self.setMinimumSize(112, 92)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        vb = QVBoxLayout(self)
        vb.setContentsMargins(6, 6, 6, 6)
        vb.setSpacing(2)

        top = QHBoxLayout()
        top.setSpacing(2)
        id_lbl = QLabel(f"Box {box_id:02d}", self)
        id_lbl.setStyleSheet(
            f"font-family:'{T.FONT_UI}'; font-size:7pt; font-weight:600; "
            f"color:{T.TEXT_SEC}; background:transparent;")
        top.addWidget(id_lbl)
        top.addStretch()
        self._chk = self._make_checkbox("Bật/tắt box này trong lịch chạy")
        top.addWidget(self._chk)
        vb.addLayout(top)

        self._state_lbl = QLabel("UNKNOWN", self)
        self._state_lbl.setAlignment(Qt.AlignCenter)
        self._board_lbl = QLabel("", self)
        self._board_lbl.setAlignment(Qt.AlignCenter)
        self._board_lbl.setStyleSheet(
            f"font-family:'{T.FONT_MONO}'; font-size:6pt; color:{T.TEXT_DIS}; "
            f"background:transparent;")
        self._metric_lbl = QLabel("", self)
        self._metric_lbl.setAlignment(Qt.AlignCenter)
        self._metric_lbl.setStyleSheet(
            f"font-family:'{T.FONT_MONO}'; font-size:6pt; color:{T.TEXT_SEC}; "
            f"background:transparent;")
        for w in (self._state_lbl, self._board_lbl, self._metric_lbl):
            vb.addWidget(w)
        vb.addStretch()

    def refresh(self, v: BoxView) -> None:
        self._set_checked(self._chk, v.enabled)
        if not v.enabled:
            key = ("disabled",)
            colors, text, style = (T.SURFACE_ALT, T.TEXT_DIS, T.TEXT_DIS), "DISABLED", "dashed"
        else:
            key = (v.state, v.connected)
            colors = T.BOX_THEME.get(v.state, (T.SURFACE, T.BORDER, T.TEXT_DIS))
            text = v.state.value.upper() if v.connected or v.state != BoxState.UNKNOWN \
                else "OFFLINE"
            style = "solid"
        if key != self._style_key:
            self._style_key = key
            bg, border, fg = colors
            self.setStyleSheet(
                f"BoxCard {{ background:{bg}; border:1.5px {style} {border}; "
                f"border-radius:6px; }}")
            self._state_lbl.setStyleSheet(
                f"font-family:'{T.FONT_UI}'; font-size:7pt; font-weight:700; "
                f"color:{fg}; background:transparent;")
            self._state_lbl.setText(text)
        board_txt = str(v.board) if (v.enabled and v.board) else ""
        if v.enabled and v.state in (BoxState.TESTING, BoxState.READY, BoxState.PASS,
                                     BoxState.FAIL, BoxState.ERROR):
            board_txt = (board_txt + "  " if board_txt else "") + fmt_age(v.state_age_sec)
        if self._board_lbl.text() != board_txt:
            self._board_lbl.setText(board_txt)

    def refresh_metrics(self, v: BoxView) -> None:
        pct = f"{v.pass_pct:.0f}%" if v.pass_pct is not None else "—"
        self._metric_lbl.setText(f"{v.tested}T · {pct} · {v.rate_per_hour:.1f}/h")


class HeadCard(_EditableCard):
    def __init__(self, head_id: int, on_edit=None, on_toggle=None, parent=None):
        super().__init__(head_id, on_edit, on_toggle, parent)
        self.setMinimumSize(90, 56)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        vb = QVBoxLayout(self)
        vb.setContentsMargins(6, 5, 6, 5)
        vb.setSpacing(2)
        top = QHBoxLayout()
        top.setSpacing(2)
        id_lbl = QLabel(f"Head {head_id}", self)
        id_lbl.setStyleSheet(
            f"font-family:'{T.FONT_UI}'; font-size:7pt; font-weight:600; "
            f"color:{T.TEXT_SEC}; background:transparent;")
        top.addWidget(id_lbl)
        top.addStretch()
        self._chk = self._make_checkbox("Bật/tắt tay gắp này trong lịch chạy")
        top.addWidget(self._chk)
        vb.addLayout(top)
        self._board_lbl = QLabel("empty", self)
        self._board_lbl.setAlignment(Qt.AlignCenter)
        vb.addWidget(self._board_lbl)

    def refresh(self, board, enabled: bool) -> None:
        self._set_checked(self._chk, enabled)
        if not enabled or board is None:
            key = ("off",) if not enabled else ("empty",)
            border = T.TEXT_DIS if not enabled else T.BORDER
            style = f"HeadCard {{ background:{T.SURFACE_ALT}; border:1.5px dashed {border}; " \
                    f"border-radius:6px; }}"
            text, color, weight = ("disabled" if not enabled else "empty"), T.TEXT_DIS, "400"
        else:
            key = (board.state,)
            color = T.BOARD_COLOR.get(board.state, T.TEXT_DIS)
            style = (f"HeadCard {{ background:{T.BOARD_BG.get(board.state, T.SURFACE_ALT)}; "
                     f"border:1.5px solid {color}; border-radius:6px; }}")
            text, weight = str(board), "600"
        if key != self._style_key:
            self._style_key = key
            self.setStyleSheet(style)
            self._board_lbl.setStyleSheet(
                f"font-family:'{T.FONT_MONO}'; font-size:7pt; font-weight:{weight}; "
                f"color:{color}; background:transparent;")
        if self._board_lbl.text() != text:
            self._board_lbl.setText(text)


# ────────────────────────────────────────────
# Trays
# ────────────────────────────────────────────
class TrayCanvas(QWidget):
    GAP = 3

    def __init__(self, cols: int, rows: int, n_slots: int,
                 tray_id: Optional[int] = None, on_edit=None, parent=None):
        super().__init__(parent)
        self.cols, self.rows, self.n_slots = cols, rows, n_slots
        self.tray_id = tray_id             # None -> not editable (NG tray)
        self.on_edit = on_edit
        self._editable = False
        self._colors = [T.BORDER] * n_slots
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(cols * 20 + self.GAP * (cols + 1),
                            rows * 16 + self.GAP * (rows + 1))

    def _set_colors(self, colors: list) -> None:
        colors = (colors + [T.BORDER] * self.n_slots)[:self.n_slots]
        if colors != self._colors:
            self._colors = colors
            self.update()

    def set_slots(self, slots: list) -> None:
        self._set_colors([T.BORDER if b is None else T.BOARD_COLOR.get(b.state, T.TEXT_DIS)
                          for b in slots])

    def set_ng(self, count: int) -> None:
        self._set_colors([T.RED if i < count else T.BORDER for i in range(self.n_slots)])

    def _cell(self):
        gap = self.GAP
        return ((self.width() - gap * (self.cols + 1)) / self.cols,
                (self.height() - gap * (self.rows + 1)) / self.rows)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cw, ch = self._cell()
        gap = self.GAP
        p.setPen(Qt.NoPen)
        for i, color in enumerate(self._colors):
            row, col = divmod(i, self.cols)
            if row >= self.rows:
                break
            p.setBrush(QColor(color))
            p.drawRoundedRect(int(gap + col * (cw + gap)), int(gap + row * (ch + gap)),
                              int(cw), int(ch), 3, 3)
        p.end()

    def set_editable(self, editable: bool) -> None:
        editable = editable and self.tray_id is not None and self.on_edit is not None
        if editable == self._editable:
            return
        self._editable = editable
        self.setCursor(Qt.PointingHandCursor if editable else Qt.ArrowCursor)
        self.setToolTip("Chuột phải vào 1 ô để sửa tay (đang dừng)" if editable else "")

    def _slot_at(self, pos) -> Optional[int]:
        cw, ch = self._cell()
        if cw <= 0 or ch <= 0:
            return None
        col = int((pos.x() - self.GAP) // (cw + self.GAP))
        row = int((pos.y() - self.GAP) // (ch + self.GAP))
        if 0 <= col < self.cols and 0 <= row < self.rows:
            idx = row * self.cols + col
            if idx < self.n_slots:
                return idx
        return None

    def mousePressEvent(self, event):
        if not self._editable or event.button() != Qt.RightButton:
            super().mousePressEvent(event)
            return
        idx = self._slot_at(event.position().toPoint())
        if idx is not None:
            _edit_menu(self, lambda st: self.on_edit(self.tray_id, idx, st),
                       f"Set Slot {idx} EMPTY").exec(event.globalPosition().toPoint())


class TrayPanel(QFrame):
    def __init__(self, title: str, title_color: str, cols: int, rows: int,
                 n_slots: int, tray_id: Optional[int] = None, on_edit=None, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setStyleSheet(
            f"TrayPanel {{ background:{T.SURFACE}; border:1px solid {T.BORDER}; "
            f"border-radius:{T.R_CARD}; }}")
        shadow(self)
        vb = QVBoxLayout(self)
        vb.setContentsMargins(10, 8, 10, 10)
        vb.setSpacing(4)
        hdr = QHBoxLayout()
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"font-family:'{T.FONT_UI}'; font-size:8pt; font-weight:700; "
            f"color:{title_color}; background:transparent;")
        self._info = QLabel("")
        self._info.setStyleSheet(
            f"font-family:'{T.FONT_UI}'; font-size:7pt; color:{T.TEXT_SEC}; "
            f"background:transparent;")
        hdr.addWidget(title_lbl)
        hdr.addStretch()
        hdr.addWidget(self._info)
        vb.addLayout(hdr)
        self._canvas = TrayCanvas(cols, rows, n_slots, tray_id, on_edit, self)
        self._canvas.setMinimumHeight(90)
        vb.addWidget(self._canvas)

    def set_editable(self, editable: bool) -> None:
        self._canvas.set_editable(editable)

    def update_slots(self, slots: list) -> None:
        u = sum(1 for b in slots if b and b.state == BoardState.UNTESTED)
        p = sum(1 for b in slots if b and b.state == BoardState.PASS)
        e = sum(1 for b in slots if b is None)
        self._info.setText(f"Untested {u}  ·  Pass {p}  ·  Empty {e}")
        self._canvas.set_slots(slots)

    def update_ng(self, count: int, capacity: int) -> None:
        self._info.setText(f"{count} / {capacity} boards")
        self._canvas.set_ng(count)


# ────────────────────────────────────────────
# Log
# ────────────────────────────────────────────
class LogPanel(QFrame):
    MAX_BLOCKS = 3000

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        vb = QVBoxLayout(self)
        vb.setContentsMargins(0, 0, 0, 0)
        self._text = QTextEdit(self)
        self._text.setReadOnly(True)
        self._text.document().setMaximumBlockCount(self.MAX_BLOCKS)   # bounded memory
        self._text.setStyleSheet(
            f"QTextEdit {{ background:transparent; color:{T.TEXT_PRI}; "
            f"font-family:'{T.FONT_MONO}'; font-size:8pt; border:none; padding:8px; }}")
        vb.addWidget(self._text)

    @staticmethod
    def _color(msg: str, levelno: int) -> str:
        if levelno >= 40 or "ERROR" in msg or "FAULT" in msg:
            return T.RED
        if levelno >= 30 or "WARN" in msg or "ALERT" in msg:
            return T.YELLOW
        if "CYCLE" in msg.upper() or "STATE" in msg:
            return T.PURPLE
        if "PICK" in msg or "LOAD" in msg or "PLACE" in msg or "->" in msg:
            return T.BLUE
        return T.TEXT_SEC

    def append(self, levelno: int, msg: str) -> None:
        ts = time.strftime("%H:%M:%S")
        msg = msg.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        self._text.append(
            f'<span style="color:{T.TEXT_DIS};font-size:7pt;">{ts}</span> '
            f'<span style="color:{self._color(msg, levelno)};font-family:{T.FONT_MONO};'
            f'font-size:8pt;">{msg}</span>')
        sb = self._text.verticalScrollBar()
        sb.setValue(sb.maximum())
