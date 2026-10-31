"""Main window of NewRCS (Fluent light): command bar, KPI strip, tray block, responsive fixture grid, log, robot / alarm panels."""
import html
import threading
from datetime import datetime

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, Signal

from ...core import engine as E
from ...core.tray import TITLES
from ..kit import fluent as F
from .login_dialog import LoginDialog
from ..kit.theme import LOG_COLORS, apply_app, build_style
from ..widgets import AlarmPanel, FixtureCard, Pill, RobotPanel, TotalsPanel, TrayPanel

RUN_TONE = {E.STOPPED: "grey", E.RUNNING: "green", E.PAUSED: "amber", E.RUN_FAULT: "red"}
RUN_TEXT = {E.STOPPED: "ĐÃ DỪNG", E.RUNNING: "ĐANG CHẠY", E.PAUSED: "TẠM DỪNG", E.RUN_FAULT: "LỖI"}
ACTION_TEXT = {"operate": "vận hành", "manual": "thủ công", "teach": "dạy điểm"}


class _FixedAreaTabs(QtWidgets.QTabWidget):
    """A tab widget whose size hint does not depend on its pages: the area it gets from the layout is the same for every tab."""
    AREA_HINT = QtCore.QSize(400, 300)

    def sizeHint(self):
        return self.AREA_HINT

    def minimumSizeHint(self):
        return QtCore.QSize(200, 200)


class MainWindow(QtWidgets.QMainWindow):
    log_signal = Signal(str, str)
    task_done = Signal(str, object, object)      # label, result, error text

    def __init__(self, runtime, settings, require_login=True, columns=8):
        super().__init__()
        self.rt = runtime
        self.cfg = settings
        self.no_confirm = False             # automation (screenshots/tests): close without asking
        self.require_login = require_login
        self.test_timeout = float(settings["engine"]["test_timeout_s"])
        ident = settings["identity"]
        self.setWindowTitle("NewRCS - %s" % ident["model"])
        self.resize(1380, 860)
        self.setMinimumSize(980, 640)
        app = QtWidgets.QApplication.instance()
        if app is not None:
            apply_app(app)
        self.setStyleSheet(build_style())

        central = QtWidgets.QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        outer = QtWidgets.QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._build_command_bar(ident))

        body = QtWidgets.QWidget()
        outer.addWidget(body, 1)
        blay = QtWidgets.QHBoxLayout(body)
        blay.setContentsMargins(14, 10, 14, 10)
        blay.setSpacing(10)

        left = QtWidgets.QVBoxLayout()
        left.setSpacing(6)
        self.totals_panel = TotalsPanel()
        left.addWidget(self.totals_panel)
        self.tray_panel = TrayPanel()                      # state of the input tray and the NG tray
        self.tray_panel.reset_requested.connect(self._reset_tray)
        self.fix_scroll = self._build_fixtures(columns)    # never taller than its cards need (see _build_fixtures)
        left.addWidget(self.fix_scroll, 3)
        # bottom area: one tab per view, so the trays and the log do not fight for the same space
        # ONE area for both tabs: its size must not depend on the page that is shown (the tray page asks for much more room than the log),
        # otherwise the area jumps and squeezes the fixture cards on every tab change (see _FixedAreaTabs). The tray cells shrink to fit it.
        self.tabs = _FixedAreaTabs()
        self.tabs.setDocumentMode(True)
        page = QtWidgets.QWidget()
        page_lay = QtWidgets.QVBoxLayout(page)
        page_lay.setContentsMargins(0, 0, 0, 0)
        page_lay.addWidget(self.tray_panel)                         # fills the whole tab area, like the log
        self.tabs.addTab(page, "Tray hàng")                       # first tab, shown by default
        self.tabs.addTab(self._build_log_panel(), "Nhật ký hoạt động")
        self.tab_tray = 0
        log_panel = self.tabs.widget(1)                           # the tab already names the view: keep only the buttons
        log_panel.title.hide()
        log_panel.header.itemAt(0).widget().hide()
        left.addWidget(self.tabs, 1)                       # takes whatever the cards do not need
        blay.addLayout(left, 1)

        right = QtWidgets.QVBoxLayout()
        right.setSpacing(8)
        self.robot_panel = RobotPanel()
        self.alarm_panel = AlarmPanel()
        right.addWidget(self.robot_panel)
        right.addWidget(self.alarm_panel, 1)
        wrap = QtWidgets.QWidget()
        wrap.setFixedWidth(340)
        wrap.setLayout(right)
        right.setContentsMargins(0, 0, 0, 0)
        blay.addWidget(wrap)

        self.log_signal.connect(self.append_log)
        self.task_done.connect(self._task_done)
        self.rt.on_log = self.log_signal.emit
        self.robot_panel.connect_clicked.connect(lambda: self._run_task("Kết nối robot", self.rt.robot_connect))
        self.robot_panel.safe_clicked.connect(self._go_safe)
        self.robot_panel.program_clicked.connect(self._start_program)
        self.robot_panel.stop_robot_clicked.connect(self._stop_robot)

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(250)
        self._snap = None
        if app is not None:
            app.installEventFilter(self)                   # any mouse / key use counts as activity (idle auto-logout)
        self.refresh()
        self.append_log("info", "NewRCS sẵn sàng. %s" % ("Cần đăng nhập để vận hành." if require_login else ""))

    # ------------------------------------------------------------------ #
    # building blocks
    # ------------------------------------------------------------------ #
    _button = staticmethod(F.button)

    def _build_command_bar(self, ident):
        bar = QtWidgets.QFrame()
        bar.setObjectName("commandBar")
        bar.setFixedHeight(60)
        lay = QtWidgets.QHBoxLayout(bar)
        lay.setContentsMargins(20, 0, 20, 0)
        lay.setSpacing(8)

        titles = QtWidgets.QVBoxLayout()
        titles.setSpacing(0)
        t = QtWidgets.QLabel("NewRCS")
        t.setObjectName("appTitle")
        sub = QtWidgets.QLabel("%s  ·  %s  ·  %s" % (ident["model"], ", ".join(ident["stations"]),
                                                      self.rt.local_ip or "không có IP 10.x"))
        sub.setObjectName("subtitle")
        titles.addStretch()
        titles.addWidget(t)
        titles.addWidget(sub)
        titles.addStretch()
        lay.addLayout(titles)
        lay.addSpacing(16)
        sep = QtWidgets.QFrame()
        sep.setObjectName("divider")
        sep.setFixedHeight(28)
        lay.addWidget(sep)
        lay.addSpacing(8)

        self.run_pill = Pill(RUN_TEXT[E.STOPPED], "grey")
        self.run_pill.setMinimumWidth(90)
        lay.addWidget(self.run_pill)
        lay.addSpacing(4)
        self.btn_start = self._button("Bắt đầu", "play", "accent", "#FFFFFF")
        self.btn_pause = self._button("Tạm dừng", "pause", None, F.WARNING)
        self.btn_stop = self._button("Dừng", "stop", None, F.DANGER)
        self.btn_fault = self._button("Xác nhận lỗi", "warning", "danger", "#FFFFFF")
        for b in (self.btn_start, self.btn_pause, self.btn_stop, self.btn_fault):
            lay.addWidget(b)
        self.btn_start.clicked.connect(self.rt.engine.start_run)
        self.btn_pause.clicked.connect(self.rt.engine.pause_run)
        self.btn_stop.clicked.connect(self._confirm_stop)
        self.btn_fault.clicked.connect(self.rt.engine.acknowledge_fault)
        lay.addStretch()

        self.btn_manual = self._button("Thủ công", "move")
        self.btn_manual.clicked.connect(self._open_manual)
        lay.addWidget(self.btn_manual)
        self.db_pill = Pill("DB tắt", "grey")
        lay.addWidget(self.db_pill)
        self.user_btn = self._button("Đăng nhập", "person", "subtle")
        self.user_btn.clicked.connect(self._login_or_logout)
        lay.addWidget(self.user_btn)
        return bar

    def _build_fixtures(self, columns):
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setMinimumHeight(60)
        self.grid = F.FlowGrid(max_cols=columns, min_item_width=180, spacing=6)
        self.grid.height_changed.connect(lambda h: scroll.setMaximumHeight(h + 6))
        self.cards = {}
        for f in self.rt.engine.snapshot()["fixtures"]:
            card = FixtureCard(f["number"], f["station"])
            card.toggled.connect(self.rt.engine.set_enabled)
            self.cards[f["number"]] = card
        self.grid.set_widgets(list(self.cards.values()))
        scroll.setWidget(self.grid)
        return scroll

    def _build_log_panel(self):
        panel = F.Panel("Nhật ký hoạt động", "history")
        clear = F.button("Xóa", "clear", "subtle", F.TEXT_2)
        panel.header.addWidget(clear)
        self.log = QtWidgets.QPlainTextEdit()
        self.log.setObjectName("log")
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(1500)
        panel.body.addWidget(self.log, 1)
        clear.clicked.connect(self.log.clear)
        panel.setMinimumHeight(150)
        return panel

    def can(self, action):
        """May the current operator do `action` (operate | manual | teach)? Without a login requirement: always."""
        if not self.require_login:
            return True
        op = self.rt.operator
        if op is None:
            return False
        allowed = getattr(op, "allowed", None)            # None: operator object without level info
        return True if allowed is None else action in allowed

    # ------------------------------------------------------------------ #
    # refresh from the engine snapshot
    # ------------------------------------------------------------------ #
    def eventFilter(self, obj, event):
        if event.type() in (QtCore.QEvent.MouseButtonPress, QtCore.QEvent.KeyPress):
            touch = getattr(self.rt, "touch", None)
            if touch is not None:
                touch()
        return False

    def _auto_logout(self):
        """Time is up: log out, close what the operator had open (a pending confirmation must not be answered afterwards)."""
        modal = QtWidgets.QApplication.activeModalWidget()
        if modal is not None and modal is not self:
            modal.close()
        manual = getattr(self, "manual", None)
        if manual is not None:
            manual.hide()
            if getattr(manual, "calib", None) is not None:
                manual.calib.hide()

    def refresh(self):
        check = getattr(self.rt, "check_auto_logout", None)
        if check is not None and self.require_login and check():
            self._auto_logout()
        snap = self.rt.engine.snapshot()
        self._snap = snap
        state = snap["run_state"]
        self.run_pill.set(RUN_TEXT.get(state, state), RUN_TONE.get(state, "grey"))
        operator = self.can("operate")
        prog = snap.get("program_running")                  # UO[3] PROGRUN: the run needs the robot program
        self.btn_start.setEnabled(operator and state in (E.STOPPED, E.PAUSED) and not self.rt.manual_busy
                                  and prog is not False)
        self.btn_start.setToolTip("Chương trình robot chưa chạy (UO[3] = 0): bấm 'Chạy chương trình' trước" if prog is False
                                  else "")
        self.btn_manual.setEnabled(self.can("manual"))
        self.btn_pause.setEnabled(operator and state == E.RUNNING)
        self.btn_stop.setEnabled(operator and state in (E.RUNNING, E.PAUSED))
        self.btn_fault.setVisible(state == E.RUN_FAULT)
        self.btn_fault.setEnabled(operator)
        for f in snap["fixtures"]:
            card = self.cards[f["number"]]
            card.update_from(f, self.test_timeout)
            card.use.setEnabled(operator)
        self.robot_panel.update_from(snap)
        self.robot_panel.btn_connect.setEnabled(self.robot_panel.btn_connect.isEnabled() and operator)
        self.robot_panel.btn_safe.setEnabled(self.robot_panel.btn_safe.isEnabled() and operator)
        self.robot_panel.btn_program.setEnabled(self.robot_panel.btn_program.isEnabled() and operator
                                                and not self.rt.manual_busy)
        self.robot_panel.btn_stop_robot.setEnabled(self.robot_panel.btn_stop_robot.isEnabled() and operator)
        self.alarm_panel.update_from(snap["alarms"])
        self.totals_panel.update_from(snap["totals"])
        trays = snap.get("trays") or {}
        self.tray_panel.update_from(trays, snap.get("flow"))
        # a tray that needs the operator (input empty / NG full) is flagged on its tab, also while the log is shown
        alert = any(t.get("exhausted") for t in trays.values())
        self.tabs.setTabText(self.tab_tray, "Tray hàng  ●" if alert else "Tray hàng")
        self.tabs.tabBar().setTabTextColor(self.tab_tray, QtGui.QColor(F.DANGER if alert else F.TEXT_2))
        for sec in self.tray_panel.sections.values():
            sec.btn.setEnabled(operator)
        sink = snap["sink"]
        if sink.get("enabled"):
            pending = sink.get("pending", 0)
            self.db_pill.set("DB · %d chờ gửi" % pending if pending else "DB OK",
                             "amber" if pending > 20 else "green")
        else:
            self.db_pill.set("DB tắt · %d đã lưu" % sink.get("pending", 0), "grey")
        op = self.rt.operator
        left = getattr(self.rt, "session_remaining", lambda: None)() if op else None
        # the countdown is only printed on the button during the last minute (the tooltip always has it)
        clock = "  (%d:%02d)" % divmod(max(0, int(left + 0.999)), 60) if left is not None and left <= 60 else ""
        self.user_btn.setText("%s · %s%s" % (op.employee.name, op.job, clock) if op else "Đăng nhập")
        if op:
            allowed = ", ".join(ACTION_TEXT.get(a, a) for a in sorted(getattr(op, "allowed", ()))) or "chỉ xem"
            auto = ("\nTự động đăng xuất sau %d:%02d" % divmod(max(0, int(left + 0.999)), 60)) if left is not None else ""
            self.user_btn.setToolTip("%s (%s)\nCấp %d - được phép: %s%s\nBấm để đăng xuất" % (
                op.employee.name, op.employee.id, op.level, allowed, auto))
        else:
            self.user_btn.setToolTip("Đăng nhập bằng mã thẻ")

    # ------------------------------------------------------------------ #
    # actions
    # ------------------------------------------------------------------ #
    def append_log(self, level, text):
        color = LOG_COLORS.get(level, LOG_COLORS["info"])
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log.appendHtml('<span style="color:#8A8886">%s</span>&nbsp;&nbsp;<span style="color:%s">%s</span>'
                            % (stamp, color, html.escape(text)))

    def _open_manual(self):
        from .manual_dialog import ManualDialog
        if getattr(self, "manual", None) is None:
            self.manual = ManualDialog(self.rt, self)
        self.manual.show()
        self.manual.raise_()
        self.manual.activateWindow()

    def _login_or_logout(self):
        if self.rt.operator is not None:
            self.append_log("info", "đăng xuất: %s" % self.rt.operator.employee.name)
            self.rt.logout()
            return
        LoginDialog(self.rt, self).exec()

    def _confirm_stop(self):
        if self._snap and self._snap["current_job"]:
            msg = "Robot đang chạy một chuỗi thao tác. Chuỗi này sẽ chạy xong trước, sau đó robot mới được disarm. Dừng?"
        else:
            msg = "Dừng chạy?"
        if F.confirm(self, "Dừng", msg, default_yes=True):
            self.rt.engine.stop_run()

    def _reset_tray(self, kind):
        what = ("đã NẠP LẠI tray Input (các ô đều có DUT)" if kind == "input"
                else "đã DỌN TRỐNG %s (các ô đều trống)" % TITLES[kind])
        if F.confirm(self, "Đặt lại tray", "Xác nhận %s?" % what):
            self.rt.reset_tray(kind)

    def _start_program(self):
        self._run_task("Khởi động chương trình robot", self.rt.robot_start_program)      # no confirmation pop-up

    def _stop_robot(self):
        self._run_task("Dừng robot", self.rt.robot_stop_program)                         # no confirmation pop-up

    def _go_safe(self):
        if F.confirm(self, "Về vị trí an toàn",
                     "Robot sẽ di chuyển về tư thế an toàn từ vị trí hiện tại.\nHãy đặt tay lên nút E-stop. Tiếp tục?",
                     warning=True):
            self._run_task("Về vị trí an toàn", self.rt.robot_gosafehere)

    def _run_task(self, label, fn):
        def work():
            try:
                self.task_done.emit(label, fn(), "")
            except Exception as ex:
                self.task_done.emit(label, None, "%s" % ex)
        threading.Thread(target=work, daemon=True).start()

    def _task_done(self, label, result, error):
        if error:
            self.append_log("error", "%s thất bại: %s" % (label, error))
        else:
            self.append_log("info", "%s: xong" % label)

    def closeEvent(self, event):
        if (not self.no_confirm and not self.rt.stopped
                and self.rt.engine.snapshot()["run_state"] == E.RUNNING):
            if not F.confirm(self, "Thoát", "Đang chạy. Dừng và thoát?"):
                event.ignore()
                return
        self.timer.stop()
        self.rt.stop()
        event.accept()
