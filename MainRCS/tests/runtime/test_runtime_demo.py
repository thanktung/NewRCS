"""Integration: Runtime + engine + real TCP clients + simulated bridge + mock ATS programs."""
import os
import tempfile
import time
import unittest

from rcs2.core import engine as E
from rcs2.tools.demo import sample_flow_points, start_demo
from tests.support.engine import tray_settings
from rcs2.runtime import Runtime


def demo_base():
    """tray_settings() with enough products in the input tray for a few cycles."""
    base = tray_settings()
    base["trays"]["input"] = {"rows": 2, "cols": 4}
    return base


def wait_until(cond, timeout=20.0, what="condition"):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.05)
    raise AssertionError("timeout waiting for " + what)


class RuntimeDemoTest(unittest.TestCase):
    def test_end_to_end_cycles(self):
        tmp = tempfile.mkdtemp()
        base = demo_base()
        base["outbox_path"] = os.path.join(tmp, "outbox.sqlite")
        cfg, stop_demo = start_demo(base, fixtures=2, speed=0.02, test_time=(0.2, 0.1))
        rt = Runtime(cfg, tmp, {"points": sample_flow_points(cfg), "example": True})
        rt.start()
        try:
            wait_until(lambda: rt.engine.snapshot()["robot"].get("connected"), what="robot link")
            wait_until(lambda: all(f["state"] != E.OFFLINE or not f["enabled"] for f in rt.engine.snapshot()["fixtures"])
                       and all(c.connected for c in rt.ats.values()), what="ATS links")
            for n in rt.ats:
                rt.engine.set_enabled(n, True)
            time.sleep(0.3)
            rt.engine.start_run()
            wait_until(lambda: len([1 for _, k, p in rt.outbox.pending(1000) if k == "result"]) >= 4, what="4 finished tests")
            snap = rt.engine.snapshot()
            self.assertNotEqual(snap["run_state"], E.RUN_FAULT, snap["fault_text"])
            self.assertTrue(snap["robot"]["armed"])
            results = [p["result"] for _, k, p in rt.outbox.pending(1000) if k == "result"]
            self.assertGreaterEqual(len(results), 4)
            self.assertTrue(set(results) <= {"PASS", "NG"})
            rt.engine.stop_run()
            wait_until(lambda: not rt.engine.snapshot()["robot"].get("armed"), what="disarm")
        finally:
            rt.stop()
            stop_demo()

    def test_login_is_stored(self):
        tmp = tempfile.mkdtemp()
        base = demo_base()
        base["outbox_path"] = os.path.join(tmp, "outbox.sqlite")
        cfg, stop_demo = start_demo(base, fixtures=1, speed=0.02, test_time=(0.2, 0.1))
        rt = Runtime(cfg, tmp, {"points": sample_flow_points(cfg)})
        try:
            result = rt.login("12345678", "wnc000000")
            self.assertEqual(result.employee.name, "Demo User")
            kinds = [k for _, k, _ in rt.outbox.pending(10)]
            self.assertEqual(kinds, ["login"])
        finally:
            rt.stop()
            stop_demo()

    def test_example_sequences_block_start_on_a_real_robot(self):
        tmp = tempfile.mkdtemp()
        base = demo_base()
        base["outbox_path"] = os.path.join(tmp, "outbox.sqlite")
        cfg, stop_demo = start_demo(base, fixtures=1, speed=0.02, test_time=(0.2, 0.1))
        rt = Runtime(cfg, tmp, {"points": sample_flow_points(cfg), "example": True})
        try:
            rt._check_sequences_vs_mode({"mode": "real"})
            self.assertIn("VÍ DỤ", rt.engine.block_reason)
            rt._check_sequences_vs_mode({"mode": "sim"})
            self.assertEqual(rt.engine.block_reason, "")
        finally:
            rt.stop()
            stop_demo()


if __name__ == "__main__":
    unittest.main()
