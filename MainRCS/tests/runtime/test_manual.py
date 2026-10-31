"""Manual control: jog (rmove), go to point, teach point, guards, and the new bridge limits."""
import json
import os
import shutil
import tempfile
import time
import unittest

from tests.support import bridge as helpers
from rcs2.tools.demo import sample_flow_points, start_demo
from tests.support.engine import tray_settings
from rcs2.robot import protocol as P
from rcs2.robot.client import BridgeClient, RobotError
from rcs2.runtime import Runtime


def wait_until(cond, timeout=15.0, what="condition"):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.05)
    raise AssertionError("timeout waiting for " + what)


class BridgeJogLimitTests(unittest.TestCase):
    def setUp(self):
        self.fx = helpers.BridgeFixture()
        self.c = BridgeClient("127.0.0.1", self.fx.port, ping_interval=0.2)
        self.c.connect()
        self.c.robot_connect()
        self.c.arm()

    def tearDown(self):
        self.c.close()
        self.fx.close()

    def test_rotation_limit(self):
        with self.assertRaises(RobotError) as cm:
            self.c.rmove([0, 0, 0, 45, 0, 0])
        self.assertEqual(cm.exception.code, P.E_LIMIT)
        self.c.rmove([0, 0, 0, 5, -5, 29])             # within 30 deg: accepted

    def test_hello_advertises_limits(self):
        self.assertEqual(self.c.hello["limits"]["max_rmove_deg"], 30.0)

    def test_pos_read_returns_full_pose(self):
        self.c.rmove([10, 0, 0, 0, 0, 0])
        pos = self.c.pos_read()
        self.assertEqual(pos["xyzwpr"][0], 10.0)
        self.assertEqual(len(pos["config"]), 7)
        self.assertIn("uf", pos)


class RuntimeManualTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmp, "config"))
        self.seq_file = os.path.join(self.tmp, "config", "sequences.json")
        base = tray_settings()
        base["outbox_path"] = os.path.join(self.tmp, "outbox.sqlite")
        self.cfg, self.stop_demo = start_demo(base, fixtures=1, speed=0.02, test_time=(0.2, 0.1))
        self.points = sample_flow_points(self.cfg)
        with open(self.seq_file, "w", encoding="utf-8") as fh:
            json.dump({"_note": "keep me", "points": self.points}, fh)
        self.rt = Runtime(self.cfg, self.tmp)            # loads config/sequences.json -> teach is possible
        self.rt.start()
        wait_until(lambda: self.rt.engine.snapshot()["robot"].get("connected"), what="robot link")
        from types import SimpleNamespace
        self.rt.operator = SimpleNamespace(employee=SimpleNamespace(name="Tester"), job="op", level=2)

    def tearDown(self):
        self.rt.operator = None
        self.rt.stop()
        self.stop_demo()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_jog_moves_the_robot_and_disarms_afterwards(self):
        self.rt.manual_rmove([5, 0, 0, 0, 0, 0], override=20)
        self.rt.manual_rmove([0, 3, 0, 0, 0, 0], override=20)
        pos = self.rt.bridge.pos_read()["xyzwpr"]
        self.assertEqual(pos[:2], [5.0, 3.0])
        wait_until(lambda: self.rt.bridge.last_status.get("armed") is False, what="disarm after the step")

    def test_jog_refused_while_running(self):
        self.rt.engine.start_run()
        wait_until(lambda: self.rt.engine.snapshot()["run_state"] == "RUNNING")
        with self.assertRaises(RobotError) as cm:
            self.rt.manual_rmove([1, 0, 0, 0, 0, 0])
        self.assertEqual(cm.exception.code, "BUSY")

    def test_jog_over_the_limit_is_rejected_by_the_bridge(self):
        with self.assertRaises(RobotError) as cm:
            self.rt.manual_rmove([500, 0, 0, 0, 0, 0])
        self.assertEqual(cm.exception.code, P.E_LIMIT)
        wait_until(lambda: self.rt.bridge.last_status.get("armed") is False)

    def test_move_to_point_uses_taught_config(self):
        self.rt.manual_move_to("input_O", override=20)
        self.assertEqual(self.rt.bridge.pos_read()["xyzwpr"][:3], self.points["input_O"]["xyzwpr"][:3])
        with self.assertRaises(KeyError):
            self.rt.manual_move_to("nope")

    def test_teach_saves_file_backup_and_live_point(self):
        self.rt.manual_rmove([7, 0, 0, 0, 0, 0], override=20)
        point = self.rt.teach_point("my_point")
        self.assertEqual(point["xyzwpr"][0], 7.0)
        with open(self.seq_file, encoding="utf-8") as fh:
            saved = json.load(fh)
        self.assertEqual(saved["points"]["my_point"], point)
        self.assertEqual(saved["_note"], "keep me")                      # rest of the file preserved
        self.assertTrue(os.path.exists(self.seq_file + ".bak"))
        self.assertIn("my_point", self.rt.engine.points)                # engine sees it without restart
        self.rt.manual_move_to("my_point", override=20)                 # and it can be used straight away

    def test_teach_rejects_bad_names(self):
        for bad in ("", "has space", "a/b", "x" * 41):
            with self.assertRaises(ValueError):
                self.rt.teach_point(bad)

    def test_teach_not_possible_in_demo_mode(self):
        rt = Runtime(self.cfg, self.tmp, {"points": dict(self.points)})
        try:
            with self.assertRaises(RuntimeError):
                rt.teach_point("x")
        finally:
            rt.stop()


if __name__ == "__main__":
    unittest.main()
