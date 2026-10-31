"""bridge_simple.py (single-file bridge) against the RCS2 client, with its built-in simulated robot."""
import ast
import copy
import os
import threading
import time
import unittest

from tests.support import bridge as helpers
import bridge_simple as BS
Fixture = helpers.BridgeFixture
from rcs2.robot.client import BridgeClient, RobotError

POSE = [300.0, 50.0, 200.0, 180.0, 0.0, 0.0]


class Case(unittest.TestCase):
    over = {}

    def setUp(self):
        self.fx = Fixture(**self.over)
        self.c = self.fx.client()
        self.c.robot_connect()

    def tearDown(self):
        self.c.close()
        self.fx.close()

    def err(self, code, fn, *a, **k):
        with self.assertRaises(RobotError) as cm:
            fn(*a, **k)
        self.assertEqual(cm.exception.code, code, cm.exception.message)


class MotionTests(Case):
    def test_hello(self):
        self.assertEqual(self.c.hello["mode"], "sim")
        self.assertEqual(self.c.hello["protocol"], 1)
        self.assertEqual(self.c.hello["limits"]["max_override"], 30)

    def test_needs_arm(self):
        self.err("NOT_ARMED", self.c.move, POSE)

    def test_move_and_station_commands(self):
        self.c.arm()
        r = self.c.move(POSE, override=20)
        self.assertEqual((r["op"], r["code"], r["r1"], r["override"]), ("move", 2, 0, 20))
        self.assertEqual(self.c.pos_read()["xyzwpr"][:3], POSE[:3])
        for op, code in (("put", 3), ("get", 4), ("down", 5), ("up", 6)):
            self.assertEqual(getattr(self.c, op)(1)["code"], code)
        self.assertEqual(self.c.gosafehere()["code"], 7)
        self.assertEqual(self.c.gosafetarge(POSE)["code"], 8)
        self.assertEqual(self.c.r_read(5), 10)           # default override was written

    def test_rmove_relative(self):
        self.c.arm()
        self.c.rmove([10, 0, 0, 0, 0, 0])
        self.c.rmove([0, 5, 0, 0, 0, 0])
        self.assertEqual(self.c.pos_read()["xyzwpr"][:2], [10.0, 5.0])

    def test_limits(self):
        self.c.arm()
        self.err("LIMIT", self.c.move, POSE, override=31)
        self.err("LIMIT", self.c.move, POSE, override=0)
        self.err("LIMIT", self.c.rmove, [500, 0, 0, 0, 0, 0])
        self.err("LIMIT", self.c.rmove, [0, 0, 0, 45, 0, 0])
        self.err("LIMIT", self.c.put, 121)
        self.err("BAD_REQUEST", self.c.move, [1, 2, 3])
        self.assertTrue(self.c.status()["armed"])        # rejected before reaching the robot: still armed

    def test_robot_error_disarms_and_latches(self):
        self.c.arm()
        self.err("ROBOT_ERROR", self.c.put, 99)
        st = self.c.status()
        self.assertFalse(st["armed"])
        self.assertTrue(st["fault"])
        self.assertEqual(self.c.r_read(1), -1)
        self.err("FAULT_LATCHED", self.c.arm)
        self.c.fault_clear()
        self.c.arm()
        self.c.put(1)

    def test_robot_receives_the_parameters(self):
        self.c.arm()
        self.c.move(POSE, override=20)
        code, pos, station, override = self.fx.sim.executed[-1]
        self.assertEqual((code, pos[:6], override), (2, POSE, 20))
        self.c.put(3, override=15)
        self.assertEqual(self.fx.sim.executed[-1][0::2], (3, 3))       # code and station

    def test_timeout_then_busy_until_the_robot_finishes(self):
        self.c.arm()
        self.fx.sim.responding = False                 # RSR0001 not running
        self.err("TIMEOUT", self.c.move, POSE, timeout_s=1.0)
        self.assertFalse(self.c.status()["armed"])      # a timeout disarms
        self.c.arm()
        self.err("BUSY", self.c.move, POSE)             # R[1] is still > 0
        self.fx.sim.responding = True                   # the robot wakes up and finishes the old command
        end = time.time() + 3
        while self.c.r_read(1) != 0 and time.time() < end:
            time.sleep(0.05)
        self.c.arm()
        self.c.move(POSE)

    def test_one_motion_at_a_time(self):
        self.c.arm()
        t = threading.Thread(target=lambda: self.c.move(POSE))
        t.start()
        time.sleep(0.05)
        self.err("BUSY", self.c.move, POSE)
        t.join(5)


class RawTests(Case):
    def test_raw_rw(self):
        self.assertEqual(self.c.r_write(2, 4), 4)
        self.err("FORBIDDEN", self.c.r_write, 1, 3)
        self.err("BAD_REQUEST", self.c.r_read, 500)
        self.err("UNKNOWN_CMD", self.c.call, "nope")
        self.err("UNKNOWN_CMD", self.c.call, "motion.fly")
        self.err("UNKNOWN_CMD", self.c.call, "handle")

    def test_io(self):
        self.err("NOT_ARMED", self.c.io_write, "SDO", 1, [1])
        self.c.arm()
        self.assertEqual(self.c.io_write("SDO", 1, [1, 0, 1]), [1, 0, 1])
        self.assertEqual(self.c.io_read("SDO", 1, 3), [1, 0, 1])
        self.err("FORBIDDEN", self.c.io_write, "UO", 1, [1])


class WorkspaceTests(Case):
    over = {"workspace": {"x": [-100, 400], "y": [-100, 100], "z": [0, 300]}}

    def test_workspace(self):
        self.c.arm()
        self.c.move(POSE)
        self.err("LIMIT", self.c.move, [900, 0, 100, 0, 0, 0])


class SafetyTests(unittest.TestCase):
    def test_disconnect_and_second_client(self):
        fx = Fixture()
        try:
            a, b = fx.client(), fx.client()
            a.robot_connect()
            a.arm()
            with self.assertRaises(RobotError) as cm:
                b.arm()
            self.assertEqual(cm.exception.code, "FORBIDDEN")
            with self.assertRaises(RobotError) as cm:
                b.move(POSE)
            self.assertEqual(cm.exception.code, "NOT_ARMED")
            a.close()
            end = time.time() + 3
            while fx.bridge.snap()["armed"] and time.time() < end:
                time.sleep(0.05)
            self.assertFalse(fx.bridge.snap()["armed"])
            b.close()
        finally:
            fx.close()

    def test_watchdog(self):
        fx = Fixture(watchdog_s=0.4)
        try:
            a = fx.client(ping_interval=0)               # silent client
            a.robot_connect()
            a.arm()
            end = time.time() + 3
            while fx.bridge.snap()["armed"] and time.time() < end:
                time.sleep(0.05)
            self.assertFalse(fx.bridge.snap()["armed"])
            a.close()
        finally:
            fx.close()

    def test_keepalive_keeps_the_arm(self):
        fx = Fixture(watchdog_s=0.6)
        try:
            a = fx.client(ping_interval=0.1)
            a.robot_connect()
            a.arm()
            time.sleep(1.5)
            self.assertTrue(fx.bridge.snap()["armed"])
            a.close()
        finally:
            fx.close()

    def test_allow_list(self):
        fx = Fixture(allow=["10.9.9.9"])
        try:
            c = BridgeClient("127.0.0.1", fx.port, ping_interval=0, connect_timeout=2.0)
            with self.assertRaises((ConnectionError, RobotError, OSError)):
                c.connect()
        finally:
            fx.close()

    def test_status_events(self):
        fx = Fixture()
        events = []
        try:
            a = BridgeClient("127.0.0.1", fx.port, ping_interval=0.2, on_event=lambda n, d: events.append(n))
            a.connect()
            a.robot_connect()
            end = time.time() + 3
            while "status" not in events and time.time() < end:
                time.sleep(0.05)
            self.assertIn("status", events)
            self.assertTrue(a.last_status.get("connected"))
            a.close()
        finally:
            fx.close()


class SourceTests(unittest.TestCase):
    def test_python38_syntax(self):
        """The robot PC may have an old 32-bit Python: keep the file parseable as Python 3.8."""
        path = os.path.join(helpers.ROOT, "bridge32", "bridge_simple.py")
        with open(path, encoding="utf-8") as fh:
            ast.parse(fh.read(), feature_version=(3, 8))

    def test_matches_rcs2_protocol_constants(self):
        """The bridge and the RCS2 client duplicate the protocol constants: they must never drift."""
        import re
        from rcs2.robot import protocol as P
        self.assertEqual(BS.MOTION, P.MOTION_CODES)
        self.assertEqual(BS.NEEDS_TARGET, P.NEEDS_TARGET)
        self.assertEqual(BS.NEEDS_STATION, P.NEEDS_STATION)
        self.assertEqual(BS.PROTOCOL, P.PROTOCOL_VERSION)
        self.assertEqual(BS.DEFAULTS["listen_port"], P.DEFAULT_PORT)
        with open(os.path.join(helpers.ROOT, "bridge32", "bridge_simple.py"), encoding="utf-8") as fh:
            used = set(re.findall(r'Err\("([A-Z_]+)"', fh.read()))
        known = {v for k, v in vars(P).items() if k.startswith("E_")}
        self.assertTrue(used)
        self.assertEqual(used - known, set(), "error codes unknown to the RCS2 client")

    def test_defaults_are_conservative(self):
        self.assertEqual(BS.DEFAULTS["allow"], ["127.0.0.1"])
        self.assertLessEqual(BS.DEFAULTS["max_override"], 30)
        self.assertIn(1, BS.DEFAULTS["protected_r"])


if __name__ == "__main__":
    unittest.main()
