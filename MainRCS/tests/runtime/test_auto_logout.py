"""Automatic logout (default: 3 minutes after the login) and the tray sizes saved by the runtime."""
import os
import tempfile
import unittest

from rcs2.config import DEFAULTS
from rcs2.core.sequence import save_sequences
from rcs2.runtime import Runtime

from tests.support.engine import tray_settings


class Emp:
    name, id, dept = "Demo User", "12345678", "MNM561"


class FakeLogin:
    employee = Emp()
    job, level, allowed = "L5 MNM561", 5, frozenset({"operate", "manual", "teach"})


class FakeEmployee:
    def login(self, user, password):
        return FakeLogin()


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class RuntimeCase(unittest.TestCase):
    overrides = None

    def make_runtime(self, top=None, name="outbox.sqlite"):
        cfg = tray_settings()
        cfg["outbox_path"] = name
        cfg["engine"]["sequences_path"] = "sequences.json"
        cfg.update(top or {})
        for section, values in (self.overrides or {}).items():
            cfg[section].update(values)
        return Runtime(cfg, self.tmp.name)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        save_sequences(os.path.join(self.tmp.name, "sequences.json"), {"points": {}})
        self.rt = self.make_runtime()
        self.rt.employee = FakeEmployee()
        self.rt.clock = Clock()
        self.logs = []
        self.rt.on_log = lambda level, text: self.logs.append((level, text))

    def tearDown(self):
        self.rt.stop()
        self.tmp.cleanup()


class AutoLogoutTests(RuntimeCase):
    def test_default_is_three_minutes(self):
        self.assertEqual(DEFAULTS["employee"]["auto_logout_s"], 180)
        self.assertEqual(self.rt.auto_logout_s, 180)

    def test_nobody_logged_in_means_nothing_to_do(self):
        self.assertIsNone(self.rt.session_remaining())
        self.assertFalse(self.rt.check_auto_logout())

    def test_logged_out_exactly_after_three_minutes(self):
        self.rt.login("12345678", "pw")
        self.assertIsNotNone(self.rt.operator)
        self.assertAlmostEqual(self.rt.session_remaining(), 180.0)
        self.rt.clock.now += 179
        self.assertFalse(self.rt.check_auto_logout())
        self.assertIsNotNone(self.rt.operator)
        self.rt.clock.now += 1
        self.assertTrue(self.rt.check_auto_logout())
        self.assertIsNone(self.rt.operator)
        self.assertTrue(any("tự động đăng xuất" in t for _, t in self.logs), self.logs)
        self.assertFalse(self.rt.check_auto_logout())              # only once

    def test_activity_does_not_extend_a_fixed_session(self):
        self.rt.login("12345678", "pw")
        self.rt.clock.now += 170
        self.rt.touch()
        self.rt.clock.now += 11
        self.assertTrue(self.rt.check_auto_logout())

    def test_a_new_login_restarts_the_time(self):
        self.rt.login("12345678", "pw")
        self.rt.clock.now += 150
        self.rt.logout()
        self.rt.login("12345678", "pw")
        self.rt.clock.now += 100
        self.assertFalse(self.rt.check_auto_logout())
        self.assertAlmostEqual(self.rt.session_remaining(), 80.0)


class IdleLogoutTests(RuntimeCase):
    overrides = {"employee": {"auto_logout_idle": True}}

    def test_activity_restarts_the_idle_time(self):
        self.rt.login("12345678", "pw")
        self.rt.clock.now += 170
        self.rt.touch()
        self.rt.clock.now += 170
        self.assertFalse(self.rt.check_auto_logout())
        self.rt.clock.now += 11
        self.assertTrue(self.rt.check_auto_logout())


class DisabledLogoutTests(RuntimeCase):
    overrides = {"employee": {"auto_logout_s": 0}}

    def test_zero_turns_the_feature_off(self):
        self.rt.login("12345678", "pw")
        self.rt.clock.now += 10 ** 6
        self.assertIsNone(self.rt.session_remaining())
        self.assertFalse(self.rt.check_auto_logout())
        self.assertIsNotNone(self.rt.operator)


class TraySizeTests(RuntimeCase):
    overrides = {"employee": {}}

    def test_sizes_come_from_the_settings(self):
        again = self.make_runtime({"trays": {"_note": "x", "input": {"rows": 5, "cols": 8}, "ng": {"rows": 3, "cols": 4}}})
        try:
            trays = again.engine.snapshot()["trays"]
            self.assertEqual((trays["input"]["capacity"], trays["ng"]["capacity"]), (40, 12))
            self.assertEqual((trays["ng"]["rows"], trays["ng"]["cols"]), (3, 4))
        finally:
            again.stop()

    def test_invalid_sizes_stop_the_start_up_with_a_clear_message(self):
        from rcs2.core.tray import TrayConfigError
        with self.assertRaises(TrayConfigError) as cm:
            self.make_runtime({"trays": {"input": {"rows": 0, "cols": 8}}})
        self.assertIn("số hàng", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
