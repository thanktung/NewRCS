"""Scratch preview harness: builds the REAL MainWindow on a fake runtime and saves screenshots.

Nothing is shown on screen (WA_DontShowOnScreen). Run:  venv\\Scripts\\python.exe _preview\\preview.py
(contract_test.py imports the fakes and snapshots from here.)
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "MainRCS"))      # RCS2/devtools/ui_preview -> RCS2/MainRCS

from PySide6 import QtCore, QtWidgets  # noqa: E402

from rcs2.core import engine as E  # noqa: E402

OUT = os.path.join(HERE, "shots")
os.makedirs(OUT, exist_ok=True)


def fx(n, state, **kw):
    d = {"number": n, "station": "Station1", "state": state, "enabled": state not in (E.NO_USED,), "connected": True,
         "sn": "", "total": 0, "passed": 0, "ng": 0, "retest": 0, "yield_pct": None, "consec_ng": 0,
         "last_result": "", "last_detail": "", "last_test_time": 0.0, "message": "", "elapsed": 0.0,
         "dut_inside": False, "host": "10.164.125.%d" % n}
    d.update(kw)
    return d


class FakeEngine:
    def __init__(self):
        self.snap = {}
        self.calls = []
        self.flow = None                         # the tray flow object (FakeFlow) when the preview shows that flow

    def snapshot(self):
        return self.snap

    def __getattr__(self, name):
        if name in ("start_run", "pause_run", "stop_run", "acknowledge_fault", "set_enabled", "reset_flow"):
            return lambda *a: self.calls.append((name, a))
        raise AttributeError(name)


class FakeBridge:
    hello = {"limits": {"max_override": 30, "max_rmove_mm": 100, "max_rmove_deg": 30}}

    def fault_clear(self):
        return {}


class Emp:
    name, id = "Demo User", "12345678"


class Operator:
    employee = Emp()
    job = "L5 MNM561"
    level = 5
    allowed = frozenset({"operate", "manual", "teach"})


class FakeHeads:
    count = 8
    enabled = True


class FakeLaser:
    enabled = True


class FakeEe:
    """The robot's ONE End Effector: 8 heads + scanner + laser."""
    heads, scanner, laser = FakeHeads(), object(), FakeLaser()

    def capabilities(self):
        return {"heads": 8, "scanner": True, "laser": True}


class FakeRuntime:
    local_ip = "10.162.155.231"
    manual_busy = False
    stopped = False
    ee = FakeEe()
    auto_logout_idle = False

    def __init__(self):
        self.engine = FakeEngine()
        self.operator = None
        self.on_log = None
        self.bridge = FakeBridge()
        self.scan_calls = []
        self.hand_calls = []
        self.tray_calls = []
        self.sizes = {"input": {"rows": 5, "cols": 8}, "ng": {"rows": 4, "cols": 6}}
        self.remaining = 143.0                    # seconds until the automatic logout
        self.logged_out_by_timer = False

    def heads_action(self, action, heads=None):
        self.hand_calls.append((action, heads))

    def heads_status(self):
        hold = {1, 2, 3, 4, 6, 7, 8}
        return [{"n": n, "vacuum": True, "cylinder_down": False, "hold": n in hold} for n in range(1, 9)]

    def scan_test(self):
        self.scan_calls.append("LON")
        return "SN2610270013"

    def scan_stop(self):
        self.scan_calls.append("LOFF")

    def laser_status(self):
        return {"ok": True, "high": False, "low": False}

    def reset_tray(self, kind):
        self.tray_calls.append(("reset", kind))

    def robot_start_program(self):
        self.tray_calls.append(("start_program",))
        return "RSR0001 đang chạy"

    def robot_stop_program(self):
        self.tray_calls.append(("stop_robot",))
        return "RSR0001 đã dừng"

    def session_remaining(self):
        return self.remaining if self.operator is not None else None

    def check_auto_logout(self):
        if self.operator is not None and self.remaining <= 0:
            self.operator = None
            self.logged_out_by_timer = True
            return True
        return False

    def points(self):
        return {"above_input": [0] * 6, "above_pass": [0] * 6, "above_fixture_1": [0] * 6}

    cfg = {"trays": {"input": {"rows": 5, "cols": 8}, "ng": {"rows": 4, "cols": 6}}}
    flow_mode = False

    def manual_override(self):
        return 10

    def logout(self):
        self.operator = None

    def stop(self):
        pass

    def robot_connect(self):
        return {}

    def robot_gosafehere(self, *a):
        return {}

    def login(self, u, p):
        raise RuntimeError("not used")


SETTINGS = {"identity": {"model": "WNC-X1", "stations": ["Station1"]}, "engine": {"test_timeout_s": 300}}

ROBOT_OK = {"connected": True, "armed": True, "r1": 2, "op": "move", "curpos": [300.0, 300.0, 250.0, 180.0, 0.0, 0.0],
            "message": "running move"}


def snap_running():
    return {
        "run_state": E.RUNNING, "fault_text": "",
        "fixtures": [
            fx(1, E.IDLE, total=12, passed=10, ng=2, yield_pct=83.3, last_result="PASS", last_test_time=38.2),
            fx(2, E.IDLE, total=9, passed=9, ng=0, yield_pct=100.0),
            fx(3, E.TESTING, total=5, passed=4, ng=1, yield_pct=80.0, sn="SN2610270013", elapsed=96.0),
            fx(4, E.RESULT, total=7, passed=5, ng=2, yield_pct=71.4, last_result="NG", last_detail="TEST_ITEM=12.3",
               last_test_time=41.7, consec_ng=2),
            fx(5, E.RESULT, total=3, passed=3, yield_pct=100.0, last_result="PASS", last_test_time=35.0),
            fx(6, E.NO_USED, enabled=False),
            fx(7, E.UNLOADING, total=1, passed=1, yield_pct=100.0),
            fx(8, E.OFFLINE, enabled=True, connected=False),
        ],
        "current_job": ("flow", 7),
        "robot": dict(ROBOT_OK), "robot_link": True, "program_running": True, "alarms": [],
        "sink": {"enabled": True, "pending": 0},
        "totals": {"total": 37, "passed": 31, "yield_pct": 83.8},
        "trays": {"input": {"kind": "input", "rows": 5, "cols": 8, "capacity": 40, "done": 23, "count": 17, "exhausted": False},
                  "ng": {"kind": "ng", "rows": 4, "cols": 6, "capacity": 24, "done": 5, "count": 5, "exhausted": False}},
    }


def snap_fault():
    s = snap_running()
    s["run_state"] = E.RUN_FAULT
    s["fault_text"] = "fixture 4 lấy ra: SequenceError"
    s["current_job"] = None
    s["fixtures"][3] = fx(4, E.FAULT, message="RobotError: ROBOT_ERROR: robot reported R[1]=-1 during put",
                          total=7, passed=5, ng=2, yield_pct=71.4)
    s["fixtures"][7] = fx(8, E.IDLE, connected=False, enabled=True)
    s["robot"] = {"connected": True, "armed": False, "r1": -1, "op": None, "curpos": [101.0, 299.5, 251.0, 0, 0, 0],
                  "message": "disarmed: ROBOT_ERROR during put"}
    s["alarms"] = [
        {"key": "robot", "code": "9201", "message": "fixture 4 lấy ra: RobotError: ROBOT_ERROR: R[1]=-1",
         "since": "2026-10-27 16:41:07"},
        {"key": "scan", "code": "9202", "message": "fixture 2 nạp: ScanError: máy quét tay1: không đọc được mã sau 3 lần thử",
         "since": "2026-10-27 16:39:30"},
        {"key": "ng_4", "code": "9011", "message": "Fixture 4: 3 lần NG/retest liên tiếp", "since": "2026-10-27 16:38:52"},
        {"key": "run_stop", "code": "9026", "message": "RCS dừng", "since": "2026-10-27 16:30:10"},
    ]
    s["sink"] = {"enabled": True, "pending": 34}
    s["trays"] = {"input": {"kind": "input", "rows": 5, "cols": 8, "capacity": 40, "done": 40, "count": 0, "exhausted": True},
                  "ng": {"kind": "ng", "rows": 4, "cols": 6, "capacity": 24, "done": 22, "count": 22, "exhausted": False}}
    return s


def snap_offline():
    s = snap_running()
    s["run_state"] = E.STOPPED
    s["current_job"] = None
    s["robot_link"] = False
    s["robot"] = {}
    s["sink"] = {"enabled": False, "pending": 12}
    s["trays"] = {}                                     # trays not configured yet
    for i, f in enumerate(s["fixtures"][:4]):
        s["fixtures"][i] = fx(f["number"], E.OFFLINE, enabled=False, connected=False)
    return s


def snap_many(n=16):
    """n fixtures in assorted states (density check)."""
    s = snap_running()
    states = [E.IDLE, E.TESTING, E.LOADING, E.RESULT, E.TESTING, E.NO_USED, E.UNLOADING, E.OFFLINE, E.FAULT, E.TESTING]
    fixtures = []
    for i in range(1, n + 1):
        st = states[(i - 1) % len(states)]
        kw = dict(total=10 + i, passed=9 + i // 2, ng=1 + i % 3, yield_pct=80.0 + i % 15)
        if st == E.TESTING:
            kw.update(sn="SN26102700%02d" % i, elapsed=20.0 * (i % 5 + 1))
        if st == E.RESULT:
            kw.update(last_result="NG" if i % 2 else "PASS", last_test_time=38.4, last_detail="TEST_ITEM=12.3")
        if st == E.FAULT:
            kw.update(message="RobotError: ROBOT_ERROR: R[1]=-1")
        if st == E.NO_USED:
            kw.update(enabled=False, total=0, passed=0, ng=0, yield_pct=None)
        if st == E.OFFLINE:
            kw.update(connected=False)
        if i == 4:
            kw.update(consec_ng=2)
        fixtures.append(fx(i, st, **kw))
    s["fixtures"] = fixtures
    return s


# ---- tray flow -------------------------------------------------------------------------------------------- #
class FakeFlow:
    """What the engine's FlowController shows to the Runtime / the calibration dialog."""
    heads, scanner, laser = 8, True, True
    fixture_numbers = list(range(1, 9))
    trays = {"input": {"rows": 5, "cols": 8}, "ng": {"rows": 4, "cols": 6}, "output1": {"rows": 4, "cols": 8}, "output2": {"rows": 4, "cols": 8}}

    def missing_points(self, points):
        from rcs2.core.geometry import Layout
        return Layout.missing(points, self.trays, self.fixture_numbers, self.heads, self.scanner, self.laser)


def _pt(x, y, z, w=180.0, p=0.0, r=0.0):
    return {"xyzwpr": [x, y, z, w, p, r], "config": [0, 0, 1, 1, 0, 0, 0], "uf": 1, "ut": 1}


def taught_points(skip=()):
    pts = {"head_%d_at_O" % k: _pt(500.0 - 22.1 * (k - 1), 100.0 + 0.4 * (k - 1), 300.0, 180.0, 0.0, 0.05 * (k - 1)) for k in range(1, 9)}
    pts["scanner_at_O"] = _pt(541.5, 99.2, 300.0)
    pts["laser_at_O"] = _pt(561.0, 99.0, 300.0)
    pts.update({"input_O": _pt(100, 200, 50), "input_X": _pt(170, 200.6, 50.2, 180.1, 0, 0.3), "input_Y": _pt(99.7, 260, 50.1, 180, 0.1, 0.2),
                "ng_O": _pt(300, 200, 50), "ng_X": _pt(350, 200, 50), "ng_Y": _pt(300, 230, 50),
                "output1_O": _pt(100, 350, 50), "output1_X": _pt(170, 350, 50), "output1_Y": _pt(100, 380, 50),
                "output2_O": _pt(300, 350, 50), "output2_X": _pt(370, 350, 50), "output2_Y": _pt(300, 380, 50)})
    for n in range(1, 9):
        pts["fixture_%d" % n] = _pt(80 * n, 500, 200)
    for name in skip:
        pts.pop(name, None)
    return pts


def _flow_runtime_class():
    from rcs2.runtime.flow_ops import FlowOpsMixin

    class FakeFlowRuntime(FakeRuntime, FlowOpsMixin):
        flow_mode = True

        def __init__(self, skip=()):
            super().__init__()
            self._points = taught_points(skip)
            self.engine.flow = FakeFlow()
            self.moves, self.taught = [], []

        def points(self):
            return self._points

        def teach_point(self, name):
            self.taught.append(name)
            self._points[name] = _pt(1, 2, 3)
            return self._points[name]

        def manual_move_to(self, name, override=None):
            self.moves.append(("to", name))

        def flow_move_head_to_cell(self, tray, index, head=1, override=None):
            self.moves.append(("cell", tray, index, head))

        def flow_move_head_to_point(self, name, head=1, override=None):
            self.moves.append(("point", name, head))

        def reset_flow(self):
            self.tray_calls.append(("reset_flow",))
    return FakeFlowRuntime


def snap_flow():
    """Tray flow in the middle of a run: input cells fresh / empty / pass, an NG cell, heads empty / fresh / pass / ng / retest."""
    s = snap_running()
    cells = ["empty"] * 12 + ["fresh"] * 28                          # 12 cells emptied: 6 products are in the output trays, 6 still out
    heads = [{"head": k, "state": "empty", "dut": None, "cell": None, "sn": "", "tests": 0} for k in range(1, 9)]
    for k, state, cell, tests in ((1, "fresh", 8, 0), (2, "retest", 9, 1), (3, "pass", 10, 1), (4, "ng", 11, 3), (6, "fresh", 20, 0)):
        heads[k - 1].update(state=state, dut=cell + 1, cell=cell, sn="SN26102700%02d" % cell, tests=tests)
    fresh = cells.count("fresh")
    s["flow"] = {"mode": "tray", "heads": heads, "input_cells": cells, "ng_used": 1, "out_used": [5, 0], "out_capacity": [32, 32],
                 "stats": {"cells": 40, "fresh": fresh, "empty": cells.count("empty"), "in_flight": 7, "passed": 5, "ng": 1, "tests": 9, "retests": 2},
                 "reason": "service box 3", "max_attempts": 3}
    s["trays"] = {"input": {"kind": "input", "rows": 5, "cols": 8, "capacity": 40, "done": 12, "count": 28, "exhausted": False},
                  "ng": {"kind": "ng", "rows": 4, "cols": 6, "capacity": 24, "done": 1, "count": 1, "exhausted": False},
                  "output1": {"kind": "output1", "rows": 4, "cols": 8, "capacity": 32, "done": 5, "count": 5, "exhausted": False},
                  "output2": {"kind": "output2", "rows": 4, "cols": 8, "capacity": 32, "done": 0, "count": 0, "exhausted": False}}
    s["fixtures"][2].update(dut=7, cell=6, tests=0, sn="SN2610270006")
    s["fixtures"][3].update(dut=8, cell=7, tests=1, sn="SN2610270007", state=E.TESTING, elapsed=40.0)
    return s


def pump(app, sec=0.4):
    end = time.time() + sec
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def shoot(app, widget, name, size=None):
    widget.setAttribute(QtCore.Qt.WA_DontShowOnScreen, True)
    if size:
        widget.resize(*size)
    widget.show()
    pump(app, 0.9)
    path = os.path.join(OUT, name)
    widget.grab().save(path)
    print("saved", path, widget.size().width(), "x", widget.size().height())


def main():
    from rcs2.ui.windows.main_window import MainWindow
    from rcs2.ui.windows.login_dialog import LoginDialog
    from rcs2.ui.windows.manual_dialog import ManualDialog

    app = QtWidgets.QApplication([])
    rt = FakeRuntime()
    rt.engine.snap = snap_running()
    win = MainWindow(rt, SETTINGS, require_login=True)
    for lvl, t in [("info", "NewRCS sẵn sàng. Cần đăng nhập để vận hành."), ("info", "đã kết nối bridge robot (sim)"),
                   ("info", "fixture 3 đã bật"), ("info", "đã bắt đầu chạy"),
                   ("info", "fixture 3: đã đọc mã SN2610270013 (máy quét tay1)"),
                   ("info", "việc robot 5 (swap): box 4 test xong"), ("info", "fixture 4: NG trong 41.7s TEST_ITEM=12.3"),
                   ("warn", "bridge bị disarm: tạm dừng chạy"),
                   ("error", "việc robot thất bại - dừng chạy: fixture 2 nạp: ScanError: máy quét tay1: không đọc được mã"),
                   ("debug", "load step 1: {'scan': 'tay1'}")]:
        win.append_log(lvl, t)

    shoot(app, win, "1_logged_out.png")
    rt.operator = Operator()
    pump(app, 0.5)
    shoot(app, win, "2_running.png")
    rt.engine.snap = snap_fault()
    pump(app, 0.6)
    shoot(app, win, "3_fault.png")
    rt.engine.snap = snap_offline()
    pump(app, 0.6)
    shoot(app, win, "4_offline.png")
    rt.engine.snap = snap_running()
    pump(app, 0.5)
    win.resize(1040, 700)
    pump(app, 0.5)
    shoot(app, win, "5_narrow.png", size=(1040, 700))
    win.resize(1380, 860)

    rt2 = FakeRuntime()                       # the card grid is built once from the first snapshot -> new window
    rt2.engine.snap = snap_many(16)
    rt2.operator = Operator()
    win2 = MainWindow(rt2, SETTINGS, require_login=True)
    for lvl, tx in [("info", "đã bắt đầu chạy"), ("info", "fixture 3: đã đọc mã SN2610270003 (máy quét tay1)")]:
        win2.append_log(lvl, tx)
    shoot(app, win2, "8_many_1380.png")
    win2.resize(1900, 1000)
    shoot(app, win2, "9_many_1900.png", size=(1900, 1000))
    win2.timer.stop()

    dlg = LoginDialog(rt, win)
    dlg.user.setText("24003437")
    dlg._set_status("Sai mật khẩu", "error")
    shoot(app, dlg, "6_login.png")

    rt.engine.snap = snap_running()
    rt.engine.snap["run_state"] = E.STOPPED
    rt.engine.snap["current_job"] = None
    man = ManualDialog(rt, win)
    man._set_status("jog X+1: xong", "success")
    man._scan_finished("Đã đọc: SN2610270013", True)
    shoot(app, man, "7_manual.png")
    win.timer.stop()
    man.timer.stop()

    # ---- tray flow: main window with the products in every stage, and the calibration dialog
    from rcs2.ui.windows.calibration_dialog import CalibrationDialog
    flow_cls = _flow_runtime_class()
    rt3 = flow_cls()
    rt3.operator = Operator()
    rt3.engine.snap = snap_flow()
    win3 = MainWindow(rt3, SETTINGS, require_login=True)
    for lvl, tx in [("info", "việc robot 12 (service): service box 3 (idle 4.2s)"), ("info", "product 9 (cell 8, SN SN2610270008) is on head 1"),
                    ("info", "product 8 (cell 7): test 2/3 in box 4 = NG -> test again in another box")]:
        win3.append_log(lvl, tx)
    shoot(app, win3, "10_flow.png")
    win3.timer.stop()
    rt3.engine.snap["run_state"] = E.STOPPED
    rt3.engine.snap["current_job"] = None
    cal = CalibrationDialog(rt3, win3)
    cal._calc_cell()
    cal.head_box.setCurrentIndex(2)
    cal.row_spin.setValue(2)
    cal.col_spin.setValue(3)
    cal._calc_cell()
    shoot(app, cal, "11_calibration.png", size=(900, 1560))
    cal.timer.stop()
    rt4 = flow_cls(skip=("head_5_at_O", "head_6_at_O", "scanner_at_O", "laser_at_O", "ng_Y", "fixture_7", "fixture_8"))
    rt4.operator = Operator()
    rt4.engine.snap = rt3.engine.snap
    cal2 = CalibrationDialog(rt4, win3)
    shoot(app, cal2, "12_calibration_missing.png", size=(900, 1560))
    cal2.timer.stop()


if __name__ == "__main__":
    main()
