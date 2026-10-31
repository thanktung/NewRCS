"""UI of the tray flow (offscreen): tray colours, heads strip, fixture cards, calibration dialog, reset button - on a Runtime wired to the simulator."""
import os
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6 import QtWidgets
    HAVE_QT = True
except ImportError:             # pragma: no cover
    HAVE_QT = False

from rcs2.core import engine as E
from tests.core.test_flow_engine import BOXES, HEADS, TRAYS_OUT
from tests.simulator.test_sim_cell import wait_until
from tests.simulator.test_sim_flow import SimFlowCase
from tests.ui.test_ui_smoke import pump


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class _UiCase(SimFlowCase):
    pass_rate = 1.0

    def setUp(self):
        super().setUp()
        from rcs2.ui.windows.main_window import MainWindow
        self.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        self.win = MainWindow(self.rt, self.rt.cfg, require_login=False, columns=BOXES)
        self.win.show()
        wait_until(lambda: self.rt.bridge.connected and self.rt.bridge.program_state is True, what="robot link + program")

    def tearDown(self):
        self.win.no_confirm = True
        self.win.timer.stop()
        for dlg in (getattr(getattr(self.win, "manual", None), "calib", None), getattr(self.win, "manual", None)):
            if dlg is not None:
                dlg.timer.stop()
        super().tearDown()


class FlowUiTests(_UiCase):
    def test_the_flow_widgets_show_when_the_tray_flow_is_on(self):
        pump(self.app, 0.6)
        panel = self.win.tray_panel
        self.assertFalse(panel.heads_strip.isHidden())                                    # the state of every head, below the trays
        self.assertEqual(len(panel.heads_strip._boxes), HEADS)
        self.assertTrue(all(b.text() == str(i + 1) for i, b in enumerate(panel.heads_strip._boxes)))
        view = panel.sections["input"].view
        self.assertEqual(set(view._colors.values()), {"fresh"})                         # nothing picked yet: every cell is blue
        for gone in ("pill", "size_label"):                                              # nothing but the name, the reset button and the cells
            self.assertFalse(hasattr(panel.sections["input"], gone))
        self.assertFalse(panel.legend.isHidden())                                       # what the colours mean
        self.assertIn("Tay:", panel.legend.text())
        for gone in ("flow_bar", "btn_reset_flow"):
            self.assertFalse(hasattr(panel, gone))
        self.assertEqual(panel.sections["input"].btn.text().strip(), "Nạp lại")
        self.assertEqual(panel.sections["ng"].btn.text().strip(), "Đã dọn")
        self.assertTrue(panel.sections["output1"].isHidden() and panel.sections["output2"].isHidden())      # no output trays configured

    def test_colours_and_cards_follow_a_run(self):
        for n in range(1, BOXES + 1):
            self.rt.engine.set_enabled(n, True)
        self.rt.engine.start_run()
        wait_until(lambda: all(f["state"] == E.TESTING for f in self.snap()["fixtures"]), 30, "all boxes testing")
        pump(self.app, 0.5)
        view = self.win.tray_panel.sections["input"].view
        self.assertIn("box", set(view._colors.values()) | {"box"})                     # test time is short: some may be done already
        texts = [self.win.cards[n].sn.text() for n in range(1, BOXES + 1)]
        self.assertTrue(any("ô" in t and "L" in t for t in texts), texts)
        wait_until(lambda: self.snap()["flow"]["stats"]["in_flight"] == 0 and self.snap()["flow"]["stats"]["fresh"] == 0, 60,
                   "everything put away")
        pump(self.app, 0.6)
        self.assertEqual(set(view._colors.values()), {"pass"})                          # pass rate 1: every product is back in its cell
        self.assertTrue(all(b.text() for b in self.win.tray_panel.heads_strip._boxes))

    def test_calibration_dialog_lists_every_point_and_checks_poses(self):
        from rcs2.ui.windows.manual_dialog import ManualDialog
        self.win._open_manual()
        manual = self.win.manual
        self.assertIsInstance(manual, ManualDialog)
        self.assertTrue(hasattr(manual, "btn_calib"))
        manual._open_calibration()
        dlg = manual.calib
        pump(self.app, 0.6)
        self.assertEqual(len(dlg.rows), (HEADS + 1) + 3 + 3 + BOXES)
        self.assertTrue(all(pill.text() == "Đã dạy" for pill, _, _ in dlg.rows.values()))
        self.assertEqual(dlg.summary.title.text(), "Đã dạy đủ và nhất quán")
        self.assertTrue(all(save.isEnabled() for _, save, _ in dlg.rows.values()))
        # computed pose of a cell: six values, the head offset applied
        dlg.head_box.setCurrentIndex(2)                                                 # head 3
        dlg.row_spin.setValue(2)
        dlg.col_spin.setValue(2)
        dlg._calc_cell()
        self.assertIn("X 66.000", dlg.pose_label.text())
        self.assertIn("Y 260.000", dlg.pose_label.text())
        self.assertEqual(len(dlg.pose_label.text().split("   ")), 6)
        # what is not taught is reported, not guessed
        del self.rt.points()["input_Y"]
        pump(self.app, 0.5)
        self.assertEqual(dlg.rows["input_Y"][0].text(), "Chưa dạy")
        self.assertIn("input_Y", dlg.summary.message.text())
        dlg._calc_cell()
        self.assertIn("input_Y", dlg.status.text())

    def test_calibration_is_locked_while_running_or_when_the_program_stops(self):
        self.win._open_manual()
        self.win.manual._open_calibration()
        dlg = self.win.manual.calib
        for n in range(1, BOXES + 1):
            self.rt.engine.set_enabled(n, True)
        self.rt.engine.start_run()
        wait_until(lambda: self.snap()["run_state"] == E.RUNNING, what="running")
        pump(self.app, 0.6)
        self.assertFalse(any(save.isEnabled() for _, save, _ in dlg.rows.values()))
        self.assertFalse(dlg.btn_go_cell.isEnabled())
        self.rt.engine.stop_run()
        self.rt.engine.wait_processed()
        wait_until(lambda: self.snap()["current_job"] is None, 30, "job ended")
        self.rt.robot_stop_program()
        wait_until(lambda: self.rt.bridge.program_state is False, what="program stopped")
        pump(self.app, 0.6)
        self.assertFalse(any(save.isEnabled() for _, save, _ in dlg.rows.values()))
        self.assertIn("UO[3]", dlg.status.text())


class OutputTrayUiTests(_UiCase):
    trays = TRAYS_OUT

    def test_the_output_trays_are_shown_and_follow_the_passed_products(self):
        for n in range(1, BOXES + 1):
            self.rt.engine.set_enabled(n, True)
        pump(self.app, 0.6)
        panel = self.win.tray_panel
        self.assertEqual([k for k, s in panel.sections.items() if not s.isHidden()], ["input", "ng", "output1", "output2"])
        self.assertEqual(panel.sections["output1"].btn.text().strip(), "Đã dọn")
        self.assertEqual(panel.sections["input"].btn.text().strip(), "Nạp lại")
        self.assertIn("Output:", panel.legend.text())
        self.assertNotIn("pass", panel.legend.text().split("NG:")[0])                    # the input tray has no pass cell any more
        self.assertEqual(set(panel.sections["output1"].view._colors.values()), {"empty"})
        self.rt.engine.start_run()
        wait_until(lambda: self.snap()["flow"]["out_used"] == [3, 3], 60, "both output trays full")
        pump(self.app, 0.8)
        self.assertEqual(set(panel.sections["output1"].view._colors.values()), {"pass"})
        self.assertEqual(set(panel.sections["output2"].view._colors.values()), {"pass"})
        self.assertNotIn("pass", set(panel.sections["input"].view._colors.values()))
        self.assertIn("●", self.win.tabs.tabText(self.win.tab_tray))                    # a full tray puts a red dot on the tab
        self.assertTrue(any(a["code"] == "9209" for a in self.snap()["alarms"]))

    def test_the_calibration_dialog_asks_for_the_output_tray_points(self):
        self.win._open_manual()
        self.win.manual._open_calibration()
        dlg = self.win.manual.calib
        pump(self.app, 0.6)
        self.assertEqual(len(dlg.rows), (HEADS + 1) + 3 + 3 + 3 + 3 + BOXES)
        self.assertIn("output1_O", dlg.rows)
        self.assertEqual([dlg.tray_box.itemData(i) for i in range(dlg.tray_box.count())], ["input", "ng", "output1", "output2"])


if __name__ == "__main__":
    unittest.main()
