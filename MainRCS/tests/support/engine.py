"""Engine fixtures: fake robot / ATS / scanner / laser, taught sample points, tray_settings() and EngineCase
(an Engine in the tray flow wired to the fakes)."""
import copy
import time
import unittest

from rcs2.ats import protocol as AP
from rcs2.config import DEFAULTS
from rcs2.core import engine as E
from rcs2.devices.end_effector import EndEffector
from rcs2.devices.heads import HeadBank
from rcs2.reporting.data_sink import DataSink, ErrorTracker
from rcs2.reporting.outbox import Outbox
from rcs2.robot.client import RobotError
from tests.devices.test_end_effector import FakeIo

HEADS, BOXES = 4, 4
TRAYS = {"input": {"rows": 2, "cols": 4}, "ng": {"rows": 1, "cols": 4}}
TRAYS_OUT = dict(TRAYS, output1={"rows": 1, "cols": 3}, output2={"rows": 1, "cols": 3})      # the passed products go to output 1, then output 2


def tray_settings():
    """DEFAULTS plus the smallest End Effector and trays the tray flow accepts (2 heads, 1 x 4 trays): for tests that build a Runtime."""
    cfg = copy.deepcopy(DEFAULTS)
    cfg["end_effector"] = {"heads": {"enabled": True, "units": [
        {"vacuum": "RDO[%d]" % n, "cylinder": "RDO[%d]" % (8 + n), "pressure": "RDI[%d]" % n} for n in (1, 2)]}}
    cfg["trays"] = {"input": {"rows": 1, "cols": 4}, "ng": {"rows": 1, "cols": 4}}
    cfg["flow"]["scan"] = False
    return cfg


def pt(x, y, z, w=180.0, p=0.0, r=0.0):
    return {"xyzwpr": [x, y, z, w, p, r], "config": [0, 0, 1, 1, 0, 0, 0], "uf": 1, "ut": 1}


def taught_points():
    pts = {"head_%d_at_O" % k: pt(500 - 22 * (k - 1), 100, 300) for k in range(1, HEADS + 1)}
    pts["scanner_at_O"] = pt(540, 100, 300)
    pts["laser_at_O"] = pt(560, 100, 300)                      # used only when flow.laser_check is on
    pts.update({"input_O": pt(100, 200, 50), "input_X": pt(130, 200, 50), "input_Y": pt(100, 260, 50),
                "ng_O": pt(300, 200, 50), "ng_X": pt(330, 200, 50), "ng_Y": pt(300, 200, 50),
                "output1_O": pt(100, 350, 50), "output1_X": pt(120, 350, 50), "output1_Y": pt(100, 350, 50),      # (used only with output trays)
                "output2_O": pt(300, 350, 50), "output2_X": pt(320, 350, 50), "output2_Y": pt(300, 350, 50)})
    for n in range(1, BOXES + 1):
        pts["fixture_%d" % n] = pt(100 * n, 500, 200)
    return pts


class FakeRobot:
    def __init__(self):
        self.connected = True
        self.last_status = {"armed": True, "connected": True}
        self.calls = []
        self.fail_on = None
        self.delay = 0.0
        self.armed = False
        self.fault_cleared = 0

    def arm(self):
        self.armed = True

    def disarm(self):
        self.armed = False

    def fault_clear(self, force=False):
        self.fault_cleared += 1

    def _op(self, name, *args, **kwargs):
        time.sleep(self.delay)
        if self.fail_on == name:
            raise RobotError("ROBOT_ERROR", "simulated %s failure" % name)
        self.calls.append((name,) + tuple(a for a in args if not isinstance(a, list)))

    def put(self, station, override=None, **kw):
        self._op("put", station)

    def get(self, station, override=None, **kw):
        self._op("get", station)

    def move(self, *a, **k):
        self._op("move")

    def rmove(self, *a, **k):
        self._op("rmove")

    def gosafehere(self, *a, **k):
        self._op("gosafehere")


class FlowRobot(FakeRobot):
    def __init__(self):
        super().__init__()
        self.moves = []
        self.hook = None                    # callable(number of moves so far), called inside every move

    def move(self, xyz, override=None, config=None, uf=None, ut=None, **kw):
        self._op("move")
        self.moves.append((list(xyz), override, config, uf, ut))
        if self.hook is not None:
            self.hook(len(self.moves))


class FakeAts:
    def __init__(self):
        self.connected = True
        self.calls = []

    def place_dut_ok(self):
        self.calls.append("place_dut_ok")
        return self.connected

    def dut_out(self):
        self.calls.append("dut_out")
        return self.connected


class FlowAts(FakeAts):
    def __init__(self):
        super().__init__()
        self.barcodes = []

    def send_barcode(self, sn):
        self.barcodes.append(sn)
        self.calls.append("barcode:%s" % sn)
        return True


class FakeLaser:
    """IL-1000 stand-in: check() records the call and the robot pose it was made at; `fail` = judgement is not GO."""
    enabled = True

    def __init__(self, robot):
        self.robot, self.calls, self.fail = robot, [], False

    def check(self, timeout_s=None):
        self.calls.append(list(self.robot.moves[-1][0]))
        if self.fail:
            from rcs2.devices.laser import LaserError
            raise LaserError("laser IL-1000 không đạt (HIGH)")


class FakeScanner:
    def __init__(self):
        self.n = 0
        self.fail = False

    def scan(self, **kw):
        if self.fail:
            from rcs2.devices.scanner import ScanError
            raise ScanError("no read")
        self.n += 1
        return "SN%04d" % self.n

    def close(self):
        pass


def wait_until(cond, timeout=3.0, what="condition"):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.01)
    raise AssertionError("timeout waiting for " + what)


class EngineCase(unittest.TestCase):
    """An Engine in the tray flow: HEADS fake heads, BOXES fake ATS, a fake scanner (and a fake laser when `laser`)."""
    flow = {}
    laser = False                          # True: the End Effector carries a laser (FakeLaser)
    trays = TRAYS                          # TRAYS_OUT: with output trays for the passed products
    overrides = None                       # {"section": {key: value}} merged into the settings

    def setUp(self):
        cfg = copy.deepcopy(DEFAULTS)
        cfg["ats"]["fixtures"] = {str(i): {"host": "10.0.0.%d" % i, "port": 8888, "station": "S"} for i in range(1, BOXES + 1)}
        cfg["flow"].update({"override": 5})
        cfg["flow"].update(self.flow)
        cfg["trays"] = self.trays
        for section, values in (self.overrides or {}).items():
            cfg[section].update(values)
        self.cfg = cfg
        self.io = FakeIo(products=range(1, HEADS + 1))
        bank = HeadBank.from_config({"enabled": True, "cylinder_s": 0.0, "vacuum_s": 0.0, "pressure_timeout_s": 0.3,
                                     "cylinder_timeout_s": 0.3,
                                     "units": [{"vacuum": "RDO[%d]" % n, "cylinder": "RDO[%d]" % (8 + n), "pressure": "RDI[%d]" % n}
                                               for n in range(1, HEADS + 1)]}, self.io)
        bank.sleep = lambda s: None
        self.scanner = FakeScanner()
        self.robot = FlowRobot()
        self.laser_tool = FakeLaser(self.robot) if self.laser else None
        self.ee = EndEffector(bank, self.scanner, self.laser_tool)
        self.points = taught_points()
        self.box = Outbox(":memory:")
        self.sink = DataSink(self.box, None)
        self.errors = ErrorTracker(self.sink, "Model_S")
        self.ats = {i: FlowAts() for i in range(1, BOXES + 1)}
        self.eng = E.Engine(cfg, self.robot, self.ats, self.sink, self.errors, self.points, ee=self.ee, trays=self.trays)
        self.eng.start()
        for n in self.ats:
            self.eng.on_ats_connection(n, True)
            self.eng.set_enabled(n, True)
        self.logs = []
        self.eng.on_log = lambda lvl, text: self.logs.append((lvl, text))
        self.answered = set()

    def tearDown(self):
        self.eng.shutdown()

    # ---- helpers ----------------------------------------------------------------------------------- #
    def start(self):
        for n in self.ats:
            self.eng.on_ats_event(n, AP.parse_message("TtoC_resultWaitdut"))
        self.eng.start_run()
        self.eng.wait_processed()

    def flow_snap(self):
        return self.eng.snapshot()["flow"]

    def fixtures(self):
        return {f["number"]: f for f in self.eng.snapshot()["fixtures"]}

    def fx(self, n):
        return self.fixtures()[n]

    def alarm_codes(self):
        return {a["code"] for a in self.errors.active()}

    def answer_tests(self, fate):
        """Act as the ATS: every box that is testing gets the result `fate(cell, attempt_number)` ("PASS" / "NG") once."""
        for n, f in self.fixtures().items():
            if f["state"] == E.TESTING and f["dut"] is not None and (n, f["dut"], f["tests"]) not in self.answered:
                self.answered.add((n, f["dut"], f["tests"]))
                label = fate(f["cell"], f["tests"] + 1)
                msg = "TtoC_resultPass" if label == "PASS" else "TtoC_resultNG+item+1"
                self.eng.on_ats_event(n, AP.parse_message(msg))

    def run_all(self, fate, timeout=25.0):
        end = time.time() + timeout
        while time.time() < end:
            self.answer_tests(fate)
            st = self.flow_snap()["stats"]
            if self.eng.run_state != E.RUNNING:
                break
            if st["fresh"] == 0 and st["in_flight"] == 0:
                return
            time.sleep(0.02)
        self.fail("did not finish: state %s, %s, last log %s" % (self.eng.run_state, self.flow_snap()["stats"], self.logs[-3:]))

    def book(self):
        return self.eng.flow.book
