"""UI smoke test (offscreen). Skipped automatically when PySide6 is missing."""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    HAVE_QT = True
except ImportError:                                             # pragma: no cover
    HAVE_QT = False

from rcs.core.scheduler import Scheduler
from rcs.models import BoardState, SystemState as S
from tests.fakes import FakeFactory, make_cfg, wait_until


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class UiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from rcs.ui.main_window import StationWindow
        self.factory = FakeFactory()
        self.cfg = make_cfg(box_count=8, gripper_heads=4, tray_cols=4, tray_rows=3,
                            ng_tray_slots=12,
                            box_layout=(("Side A", (1, 2, 3, 4)), ("Side B", (5, 6, 7, 8))))
        self.sched = Scheduler(self.cfg, self.factory)
        self.win = StationWindow(self.sched)
        self.addCleanup(self.sched.emergency_stop)

    def pump(self, seconds=0.3):
        import time
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.app.processEvents()
            time.sleep(0.01)

    def test_window_builds_and_renders_all_states(self):
        self.pump(0.2)
        self.assertEqual(len(self.win._box_cards), 8)
        self.assertEqual(len(self.win._head_cards), 4)
        self.assertEqual(self.win._start_btn.text(), "Start")

        self.sched.start()
        self.assertTrue(wait_until(lambda: self.sched.stats["pass"] >= 3))
        self.pump(0.4)
        self.assertFalse(self.win._start_btn.isEnabled())
        self.assertTrue(self.win._pause_btn.isEnabled())

        self.sched.pause()
        self.assertTrue(wait_until(lambda: self.sched.sm.state == S.PAUSED))
        self.pump(0.4)
        self.assertEqual(self.win._start_btn.text(), "Resume")
        self.assertTrue(self.sched.snapshot().manual_edit_allowed)

    def test_fault_banner_and_acknowledge_button(self):
        from rcs.clients.errors import RobotTimeout
        self.factory.robot.fail_next(RobotTimeout("x"))
        self.sched.start()
        self.assertTrue(wait_until(lambda: self.sched.sm.state == S.FAULT))
        self.pump(0.4)
        self.assertFalse(self.win._ack_btn.isHidden())
        self.assertFalse(self.win._banner.isHidden())
        self.assertIn("LỖI", self.win._status_text.text())

    def test_manual_edit_callbacks_update_model(self):
        self.win._on_head_edit(0, BoardState.PASS)
        self.assertEqual(self.sched.gripper.heads[0].board.state, BoardState.PASS)
        self.win._on_tray_edit(1, 2, None)
        self.assertIsNone(self.sched.tray1.slots[2])
        self.win._on_box_toggle(3, False)
        self.assertFalse(self.sched.boxes[2].enabled)
        self.pump(0.3)
        self.assertTrue(self.win._box_cards[3]._state_lbl.text() == "DISABLED")


if __name__ == "__main__":
    unittest.main()
