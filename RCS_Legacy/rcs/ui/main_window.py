"""
main_window.py - Main window.

The window knows only the PUBLIC API of the Scheduler (start / pause / stop /
snapshot / manual_set_* ...). It never touches scheduler internals.

Threading rules
---------------
* The scheduler calls our listener from ANY thread -> the listener only sets a
  dirty flag. A QTimer on the UI thread renders at most every REFRESH_MS.
* Log lines come through a Qt signal (logging handler -> signal -> UI thread).
* Anything that can block (connect, graceful stop, acknowledge) runs in a worker
  thread; its errors come back through a signal. Widgets are only touched on the
  UI thread.
"""

from __future__ import annotations

import threading
import time
from typing import Callable

from PySide6.QtCore import QObject, QTimer, Qt, Signal
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QMainWindow, QMessageBox, QPushButton,
                               QSizePolicy, QVBoxLayout, QWidget)

from ..core.scheduler import Scheduler
from ..models import SystemState as S
from . import theme as T
from .widgets import (Banner, BoxCard, Card, Chip, HeadCard, LogPanel,
                      SectionHead, StatPill, TrayPanel, shadow)

METRICS_REFRESH_SEC = 1.0      # averages change slowly - redraw them at most 1x/s

_STATUS = {
    S.STOPPED: ("Chưa kết nối", T.TEXT_DIS),
    S.IDLE: ("Sẵn sàng", T.ACCENT),
    S.RUNNING: ("Đang chạy", T.GREEN),
    S.PAUSING: ("Đang tạm dừng...", T.YELLOW),
    S.PAUSED: ("Tạm dừng", T.YELLOW),
    S.FAULT: ("LỖI - cần xác nhận", T.RED),
}


class Bridge(QObject):
    log = Signal(int, str)
    error = Signal(str)


def _button(text: str, bg: str, hover: str, w: int = 100) -> QPushButton:
    b = QPushButton(text)
    b.setFixedSize(w, 34)
    b.setStyleSheet(
        f"QPushButton {{ background:{bg}; color:white; font-family:'{T.FONT_UI}'; "
        f"font-size:9pt; font-weight:600; border:none; border-radius:{T.R_BTN}; }}"
        f"QPushButton:hover {{ background:{hover}; }}"
        f"QPushButton:disabled {{ background:{T.BORDER}; color:{T.TEXT_DIS}; }}")
    return b


class StationWindow(QMainWindow):
    def __init__(self, scheduler: Scheduler) -> None:
        super().__init__()
        self.sched = scheduler
        self.cfg = scheduler.cfg
        self.bridge = Bridge()
        self.bridge.log.connect(self._on_log)
        self.bridge.error.connect(self._on_error)

        self._dirty = True
        self._busy = False
        self._last_metrics = 0.0
        scheduler.add_listener(self._mark_dirty)

        self.setWindowTitle(f"{self.cfg.station_name} - RCS")
        self.setMinimumSize(900, 600)
        self.setStyleSheet(f"QMainWindow {{ background:{T.BG}; }}")
        self._build()
        self.showMaximized()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(T.REFRESH_MS)
        self._refresh()

    # ── thread-safe plumbing ───────────────
    def _mark_dirty(self) -> None:
        self._dirty = True

    def _tick(self) -> None:
        if self._dirty:
            self._dirty = False
            self._refresh()
        elif self.sched.sm.state in (S.RUNNING, S.PAUSING):
            self._refresh_clocks()

    def _run_async(self, fn: Callable[[], None]) -> None:
        """Run a possibly slow scheduler call off the UI thread."""
        if self._busy:
            return
        self._busy = True
        self._mark_dirty()

        def work() -> None:
            try:
                fn()
            except Exception as e:                                  # noqa: BLE001
                self.bridge.error.emit(str(e) or e.__class__.__name__)
            finally:
                self._busy = False
                self._mark_dirty()

        threading.Thread(target=work, daemon=True, name="ui-action").start()

    def _on_log(self, level: int, msg: str) -> None:
        self._log_panel.append(level, msg)

    def _on_error(self, msg: str) -> None:
        self._log_panel.append(40, f"ERROR {msg}")
        QMessageBox.warning(self, self.cfg.station_name, msg)

    # ════════════════════════════════════════
    # BUILD
    # ════════════════════════════════════════
    def _build(self) -> None:
        root = QWidget()
        root.setStyleSheet(f"background:{T.BG};")
        self.setCentralWidget(root)
        main_vb = QVBoxLayout(root)
        main_vb.setContentsMargins(0, 0, 0, 0)
        main_vb.setSpacing(0)

        main_vb.addWidget(self._build_topbar())

        self._banner = Banner()
        self._ack_btn = _button("Xác nhận lỗi", T.RED, "#A4262C", 120)
        self._ack_btn.clicked.connect(lambda: self._run_async(self.sched.acknowledge_fault))
        self._ng_btn = _button("Đã đổ NG tray", T.YELLOW, "#A04010", 130)
        self._ng_btn.clicked.connect(self.sched.clear_ng_tray)
        self._banner.add_widget(self._ack_btn)
        self._banner.add_widget(self._ng_btn)
        main_vb.addWidget(self._banner)

        body = QWidget()
        body.setStyleSheet(f"background:{T.BG};")
        body_hb = QHBoxLayout(body)
        body_hb.setContentsMargins(20, 16, 20, 16)
        body_hb.setSpacing(16)
        left = QVBoxLayout()
        left.setSpacing(12)
        body_hb.addLayout(left, stretch=1)
        body_hb.addWidget(self._build_log_panel())
        main_vb.addWidget(body, stretch=1)

        self._build_pills(left)
        self._build_boxes(left)
        self._build_gripper(left)
        self._build_trays(left)
        left.addStretch()

    def _build_topbar(self) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(52)
        bar.setStyleSheet(f"background:{T.SURFACE}; border-bottom:1px solid {T.BORDER};")
        hb = QHBoxLayout(bar)
        hb.setContentsMargins(24, 0, 24, 0)
        hb.setSpacing(10)

        accent = QFrame()
        accent.setFixedSize(4, 28)
        accent.setStyleSheet(f"background:{T.ACCENT}; border-radius:2px;")
        title = QLabel(self.cfg.station_name)
        title.setStyleSheet(
            f"font-family:'{T.FONT_UI}'; font-size:14pt; font-weight:600; "
            f"color:{T.TEXT_PRI}; background:transparent;")
        self._status_dot = QLabel("●")
        self._status_text = QLabel("")
        self._status_text.setStyleSheet(
            f"font-family:'{T.FONT_UI}'; font-size:9pt; color:{T.TEXT_SEC}; "
            f"background:transparent;")
        self._mode_chip = Chip()
        self._proto_chip = Chip()
        self._robot_chip = Chip()
        for w in (accent, title, self._status_dot, self._status_text,
                  self._mode_chip, self._proto_chip, self._robot_chip):
            hb.addWidget(w)
        hb.addStretch()

        self._start_btn = _button("Start", T.ACCENT, "#106EBE")
        self._pause_btn = _button("Pause", T.YELLOW, "#A04010")
        self._stop_btn = _button("Stop", T.TEXT_SEC, "#3B3A39")
        self._estop_btn = _button("E-STOP", T.RED, "#A4262C")
        self._start_btn.clicked.connect(self._on_start)
        self._pause_btn.clicked.connect(self.sched.pause)
        self._stop_btn.clicked.connect(self._on_stop)
        self._estop_btn.clicked.connect(self._on_estop)
        for b in (self._start_btn, self._pause_btn, self._stop_btn, self._estop_btn):
            hb.addWidget(b)
        return bar

    def _build_pills(self, left: QVBoxLayout) -> None:
        row = QHBoxLayout()
        row.setSpacing(10)
        self._pill_loaded = StatPill("Đã nạp", T.ACCENT)
        self._pill_pass = StatPill("Pass", T.GREEN)
        self._pill_ng = StatPill("NG", T.RED)
        self._pill_change = StatPill("Tray Pass", T.PURPLE)
        self._pill_rate = StatPill("Tốc độ (SP/h)", T.ACCENT)
        self._pill_pct = StatPill("Tỉ lệ Pass", T.GREEN)
        for p in (self._pill_loaded, self._pill_pass, self._pill_ng, self._pill_change,
                  self._pill_rate, self._pill_pct):
            row.addWidget(p)
        left.addLayout(row)

    def _build_boxes(self, left: QVBoxLayout) -> None:
        card = Card(pad=(12, 10, 12, 12))
        vb = card.layout()
        vb.addWidget(SectionHead("TEST BOXES", color=T.TEXT_SEC, size=8))
        sides = QHBoxLayout()
        sides.setSpacing(20)
        self._box_cards: dict = {}
        for label, ids in self.cfg.box_layout:
            ids = list(ids)
            per_row = (len(ids) + 1) // 2              # two rows per side
            col = QVBoxLayout()
            col.setSpacing(4)
            col.addWidget(SectionHead(f"{label}  ({ids[0]}–{ids[-1]})",
                                      color=T.TEXT_DIS, size=7, bold=False))
            grid = QGridLayout()
            grid.setSpacing(6)
            for i, box_id in enumerate(ids):
                c = BoxCard(box_id, on_edit=self._on_box_edit, on_toggle=self._on_box_toggle)
                self._box_cards[box_id] = c
                grid.addWidget(c, i // per_row, i % per_row)
            col.addLayout(grid)
            sides.addLayout(col)
        sides.addStretch()
        vb.addLayout(sides)
        left.addWidget(card)

    def _build_gripper(self, left: QVBoxLayout) -> None:
        card = Card(pad=(12, 10, 12, 12))
        vb = card.layout()
        vb.addWidget(SectionHead(f"GRIPPER  —  {self.cfg.gripper_heads} heads",
                                 color=T.TEXT_SEC, size=8))
        row = QHBoxLayout()
        row.setSpacing(6)
        self._head_cards: list = []
        for i in range(self.cfg.gripper_heads):
            c = HeadCard(i, on_edit=self._on_head_edit, on_toggle=self._on_head_toggle)
            self._head_cards.append(c)
            row.addWidget(c)
        row.addStretch()
        vb.addLayout(row)
        left.addWidget(card)

    def _build_trays(self, left: QVBoxLayout) -> None:
        cfg = self.cfg
        card = Card(pad=(12, 10, 12, 12))
        vb = card.layout()
        vb.addWidget(SectionHead(f"TRAYS  —  {cfg.tray_rows} × {cfg.tray_cols}",
                                 color=T.TEXT_SEC, size=8))
        row = QHBoxLayout()
        row.setSpacing(10)
        n = cfg.tray_slots
        self._tray1 = TrayPanel("Tray 1  —  Input / Pass", T.ACCENT, cfg.tray_cols,
                                cfg.tray_rows, n, tray_id=1, on_edit=self._on_tray_edit)
        self._tray2 = TrayPanel("Tray 2  —  Backup", T.BLUE, cfg.tray_cols,
                                cfg.tray_rows, n, tray_id=2, on_edit=self._on_tray_edit)
        self._ng = TrayPanel("NG Tray", T.RED, cfg.tray_cols, cfg.tray_rows,
                             cfg.ng_tray_slots if cfg.ng_tray_slots <= n else n)
        for p in (self._tray1, self._tray2, self._ng):
            row.addWidget(p)
        vb.addLayout(row)
        left.addWidget(card)

    def _build_log_panel(self) -> QFrame:
        frame = QFrame()
        frame.setFixedWidth(340)
        frame.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        frame.setStyleSheet(
            f"QFrame {{ background:{T.SURFACE}; border:1px solid {T.BORDER}; "
            f"border-radius:{T.R_CARD}; }}")
        shadow(frame)
        vb = QVBoxLayout(frame)
        vb.setContentsMargins(0, 0, 0, 0)
        vb.setSpacing(0)
        header = QFrame()
        header.setFixedHeight(36)
        header.setStyleSheet(
            f"background:{T.SURFACE_ALT}; border-bottom:1px solid {T.BORDER}; "
            f"border-top-left-radius:{T.R_CARD}; border-top-right-radius:{T.R_CARD};")
        hh = QHBoxLayout(header)
        hh.setContentsMargins(12, 0, 12, 0)
        hh.addWidget(SectionHead("Log", color=T.TEXT_SEC, size=8))
        hh.addStretch()
        self._log_panel = LogPanel()
        vb.addWidget(header)
        vb.addWidget(self._log_panel, stretch=1)
        return frame

    # ════════════════════════════════════════
    # Callbacks
    # ════════════════════════════════════════
    def _on_start(self) -> None:
        self._run_async(self.sched.start)

    def _on_stop(self) -> None:
        self._run_async(self.sched.stop)

    def _on_estop(self) -> None:
        # Not routed through _run_async: must work even while another action is busy.
        threading.Thread(target=self.sched.emergency_stop, daemon=True).start()

    def _on_box_edit(self, box_id, board_state) -> None:
        if self.sched.manual_set_box(box_id, board_state):
            self._mark_dirty()

    def _on_head_edit(self, head_id, board_state) -> None:
        if self.sched.manual_set_gripper(head_id, board_state):
            self._mark_dirty()

    def _on_tray_edit(self, tray_id, slot, board_state) -> None:
        if self.sched.manual_set_tray_slot(tray_id, slot, board_state):
            self._mark_dirty()

    def _on_box_toggle(self, box_id, enabled) -> None:
        self.sched.set_box_enabled(box_id, enabled)

    def _on_head_toggle(self, head_id, enabled) -> None:
        self.sched.set_head_enabled(head_id, enabled)

    def closeEvent(self, event) -> None:
        if self.sched.sm.state != S.STOPPED:
            ans = QMessageBox.question(
                self, "Thoát", "Hệ thống đang kết nối. Dừng và thoát?")
            if ans != QMessageBox.Yes:
                event.ignore()
                return
            self.sched.stop()
        event.accept()

    # ════════════════════════════════════════
    # Rendering
    # ════════════════════════════════════════
    def _refresh_clocks(self) -> None:
        """Between real changes only the 'seconds in state' text needs redrawing."""
        now = time.monotonic()
        if now - self._last_metrics >= 1.0:
            self._refresh()

    def _refresh(self) -> None:
        snap = self.sched.snapshot()
        st = snap.system_state

        # status + chips
        text, color = _STATUS[st]
        self._status_dot.setStyleSheet(f"font-size:10pt; color:{color}; background:transparent;")
        self._status_text.setText(text)
        if snap.mode == "real":
            self._mode_chip.setText("REAL")
            self._mode_chip.set_colors(T.RED_BG, T.RED)
        else:
            self._mode_chip.setText("SIM")
            self._mode_chip.set_colors(T.YELLOW_BG, T.YELLOW)
        self._proto_chip.setText(f"{snap.protocol}{' + batch' if snap.batch else ''}")
        self._proto_chip.set_colors(T.BLUE_BG, T.BLUE)
        if not snap.robot_connected:
            self._robot_chip.setText("Robot: offline")
            self._robot_chip.set_colors(T.BORDER, T.TEXT_SEC)
        else:
            rs = snap.robot_status or "online"
            bad = rs in ("ALARM", "ESTOP")
            self._robot_chip.setText(f"Robot: {rs}")
            self._robot_chip.set_colors(T.RED_BG if bad else T.GREEN_BG,
                                        T.RED if bad else T.GREEN)

        # buttons
        busy = self._busy
        self._start_btn.setText("Resume" if st in (S.PAUSED, S.PAUSING) else "Start")
        self._start_btn.setEnabled(not busy and st in (S.STOPPED, S.IDLE, S.PAUSED))
        self._pause_btn.setEnabled(st == S.RUNNING)
        self._stop_btn.setEnabled(not busy and st != S.STOPPED)
        self._estop_btn.setEnabled(st != S.STOPPED)

        # banner: FAULT (red) > alerts (amber)
        self._ack_btn.setVisible(st == S.FAULT)
        self._ack_btn.setEnabled(not busy)
        self._ng_btn.setVisible("ng_full" in snap.alerts)
        if st == S.FAULT:
            self._banner.show_message(f"LỖI HỆ THỐNG: {snap.fault}", T.RED, T.RED_BG)
        elif snap.alerts:
            self._banner.show_message("  |  ".join(snap.alerts.values()), T.YELLOW, T.YELLOW_BG)
        else:
            self._banner.hide()

        # pills
        s = snap.stats
        self._pill_loaded.set_value(s.get("loaded", 0))
        self._pill_pass.set_value(s.get("pass", 0))
        self._pill_ng.set_value(s.get("ng", 0))
        self._pill_change.set_value(s.get("change", 0))
        now = time.monotonic()
        update_metrics = now - self._last_metrics >= METRICS_REFRESH_SEC
        if update_metrics:
            self._last_metrics = now
            sm = snap.system_metrics
            self._pill_rate.set_value(f"{sm['rate_per_hour']:.1f}")
            self._pill_pct.set_value(f"{sm['pass_pct']:.0f}%"
                                     if sm["pass_pct"] is not None else "—")

        editable = snap.manual_edit_allowed
        for v in snap.boxes:
            card = self._box_cards[v.box_id]
            card.refresh(v)
            card.set_editable(editable)
            if update_metrics:
                card.refresh_metrics(v)
        for h in snap.heads:
            card = self._head_cards[h.head_id]
            card.refresh(h.board, h.enabled)
            card.set_editable(editable)

        self._tray1.update_slots(snap.tray1)
        self._tray2.update_slots(snap.tray2)
        self._ng.update_ng(snap.ng_count, snap.ng_capacity)
        self._tray1.set_editable(editable)
        self._tray2.set_editable(editable)

