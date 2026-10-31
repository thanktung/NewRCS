"""Input tray / NG tray: sizes come from a file (never fixed in code), cells are consumed by the engine."""
import unittest

from rcs2.ats import protocol as AP
from rcs2.core import engine as E
from rcs2.core import tray as T

from tests.support.engine import POINTS, SEQ, EngineCase, FakeRobot, wait_until


class TrayModelTests(unittest.TestCase):
    def test_input_tray_starts_full_and_is_consumed_in_reading_order(self):
        t = T.Tray("input", 2, 3)
        self.assertEqual((t.capacity, t.count, t.exhausted), (6, 6, False))
        for expected in (5, 4, 3, 2, 1, 0):
            self.assertTrue(t.advance())
            self.assertEqual(t.count, expected)
        self.assertTrue(t.exhausted)
        self.assertFalse(t.advance())                              # nothing left, no overflow
        self.assertEqual(t.snapshot()["done"], 6)
        t.reset()
        self.assertEqual((t.count, t.exhausted), (6, False))

    def test_ng_tray_starts_empty_and_fills_up(self):
        t = T.Tray("ng", 1, 2)
        self.assertEqual(t.count, 0)
        t.advance()
        self.assertEqual((t.count, t.exhausted), (1, False))
        t.advance()
        self.assertEqual((t.count, t.exhausted), (2, True))
        t.reset()
        self.assertEqual(t.count, 0)

    def test_sizes_are_validated(self):
        for bad in ((0, 3), (3, 0), (-1, 2), (2, 51), (1.5, 2), ("2", 2), (None, 2), (True, 2)):
            with self.assertRaises(T.TrayConfigError, msg=str(bad)):
                T.Tray("input", *bad)
        with self.assertRaises(T.TrayConfigError):
            T.Tray("pass", 1, 1)
        self.assertEqual(T.Tray("input", 50, 50).capacity, 2500)

    def test_build_ignores_notes_and_rejects_garbage(self):
        built = T.build_trays({"_note": "x", "input": {"rows": 5, "cols": 8}})
        self.assertEqual(list(built), ["input"])                   # NG tray not configured: simply not there
        self.assertEqual(T.build_trays({}), {})
        self.assertEqual(T.build_trays(None), {})
        with self.assertRaises(T.TrayConfigError):
            T.build_trays({"input": 5})


class EngineTrayTests(EngineCase):
    fixtures = 1
    TRAYS = {"input": {"rows": 1, "cols": 2}, "ng": {"rows": 1, "cols": 2}}

    def setUp(self):
        super().setUp()
        self.eng.shutdown()
        self.robot = FakeRobot()
        self.eng = E.Engine(self.cfg, self.robot, self.ats, self.sink, self.errors, SEQ, POINTS, trays=self.TRAYS)
        self.eng.start()
        self.eng.on_ats_connection(1, True)
        self.eng.set_enabled(1, True)

    def tray(self, kind):
        return self.eng.snapshot()["trays"][kind]

    def finish_test(self, message):
        self.eng.on_ats_event(1, AP.parse_message(message))

    def test_snapshot_without_trays_is_an_empty_dict(self):
        self.eng.shutdown()
        eng = E.Engine(self.cfg, self.robot, self.ats, self.sink, self.errors, SEQ, POINTS)
        self.assertEqual(eng.snapshot()["trays"], {})

    def test_a_load_takes_one_cell_from_the_input_tray(self):
        self.assertEqual(self.tray("input")["count"], 2)
        self.start_and_ready(1)
        wait_until(lambda: self.fx(1)["state"] == E.TESTING, what="TESTING")
        self.assertEqual(self.tray("input")["count"], 1)
        self.assertEqual(self.tray("ng")["count"], 0)              # nothing failed yet

    def test_ng_fills_the_ng_tray_and_pass_does_not(self):
        self.start_and_ready(1)
        wait_until(lambda: self.fx(1)["state"] == E.TESTING)
        self.finish_test("TtoC_resultPass")
        wait_until(lambda: self.fx(1)["passed"] == 1 and self.tray("input")["count"] == 0, what="pass + reload")
        self.assertEqual(self.tray("ng")["count"], 0)
        self.finish_test("TtoC_resultNG+VCC+4.2")
        wait_until(lambda: self.fx(1)["ng"] == 1 and self.tray("ng")["count"] == 1, what="NG in the NG tray")

    def test_no_load_starts_while_the_input_tray_is_empty_and_resumes_after_a_reset(self):
        self.start_and_ready(1)
        wait_until(lambda: self.fx(1)["state"] == E.TESTING)
        self.finish_test("TtoC_resultPass")                          # takes the 2nd (last) DUT
        wait_until(lambda: self.tray("input")["exhausted"], what="input tray empty")
        self.finish_test("TtoC_resultPass")
        wait_until(lambda: self.fx(1)["passed"] == 2, what="second pass")
        loads_before = self.robot.calls.count(("get", 0))
        self.assertEqual(loads_before, 2)
        self.assertEqual(self.fx(1)["state"], "Wait load")           # waiting for stock, no third load
        import time
        time.sleep(0.5)
        self.assertEqual(self.robot.calls.count(("get", 0)), 2)
        self.eng.reset_tray("input")
        wait_until(lambda: self.fx(1)["state"] == E.TESTING, what="load after refill")
        self.assertEqual(self.robot.calls.count(("get", 0)), 3)
        self.assertEqual(self.tray("input")["count"], 1)

    def test_reset_of_a_fresh_tray_is_harmless_and_unknown_kinds_are_ignored(self):
        self.eng.reset_tray("ng")
        self.eng.reset_tray("pass")
        import time
        time.sleep(0.3)
        self.assertEqual(self.tray("ng")["count"], 0)
        self.assertEqual(self.tray("input")["capacity"], 2)

    def test_without_trays_loading_is_never_blocked(self):
        self.eng.shutdown()
        self.robot = FakeRobot()
        self.eng = E.Engine(self.cfg, self.robot, self.ats, self.sink, self.errors, SEQ, POINTS)
        self.eng.start()
        self.eng.on_ats_connection(1, True)
        self.eng.set_enabled(1, True)
        self.start_and_ready(1)
        wait_until(lambda: self.fx(1)["state"] == E.TESTING)


if __name__ == "__main__":
    unittest.main()
