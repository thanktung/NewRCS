"""Engine fixtures: FakeRobot / FakeAts, a small sequence set and EngineCase (an Engine wired to the fakes)."""
import copy
import time
import unittest

from rcs2.ats import protocol as AP
from rcs2.config import DEFAULTS
from rcs2.core import engine as E
from rcs2.reporting.data_sink import DataSink, ErrorTracker
from rcs2.reporting.outbox import Outbox
from rcs2.robot.client import RobotError

POINTS = {}
SEQ = {
    "load": [{"robot": "get", "station": 0}, {"robot": "put", "station": "{robot_station}"}],
    "unload_pass": [{"robot": "get", "station": "{robot_station}"}, {"robot": "put", "station": 8}],
    "unload_ng": [{"robot": "get", "station": "{robot_station}"}, {"robot": "put", "station": 9}],
}


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


def wait_until(cond, timeout=3.0, what="condition"):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.01)
    raise AssertionError("timeout waiting for " + what)


class EngineCase(unittest.TestCase):
    fixtures = 2
    overrides = None

    def setUp(self):
        cfg = copy.deepcopy(DEFAULTS)
        cfg["ats"]["fixtures"] = {str(i): {"host": "10.0.0.%d" % i, "port": 8888, "station": "Station1"}
                                  for i in range(1, self.fixtures + 1)}
        cfg["consecutive_ng"]["limit"] = 3
        for section, values in (self.overrides or {}).items():
            cfg[section].update(values)
        self.cfg = cfg
        self.box = Outbox(":memory:")
        self.sink = DataSink(self.box, None)
        self.errors = ErrorTracker(self.sink, "Model_Station1")
        self.robot = FakeRobot()
        self.ats = {i: FakeAts() for i in range(1, self.fixtures + 1)}
        self.eng = E.Engine(cfg, self.robot, self.ats, self.sink, self.errors, SEQ, POINTS)
        self.eng.start()
        for n in self.ats:
            self.eng.on_ats_connection(n, True)
            self.eng.set_enabled(n, True)

    def tearDown(self):
        self.eng.shutdown()

    def fx(self, n):
        return next(f for f in self.eng.snapshot()["fixtures"] if f["number"] == n)

    def results(self):
        return [p["result"] for _, k, p in self.box.pending(1000) if k == "result"]

    def start_and_ready(self, *numbers):
        self.eng.start_run()
        for n in numbers or self.ats:
            self.eng.on_ats_event(n, AP.parse_message("TtoC_resultWaitdut"))
