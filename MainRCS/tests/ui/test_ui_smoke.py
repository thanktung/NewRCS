"""UI smoke test (offscreen): login dialog, enabling of controls, a short automatic run."""
import copy
import os
import tempfile
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


try:
    from PySide6 import QtWidgets
    HAVE_QT = True
except ImportError:             # pragma: no cover
    HAVE_QT = False

from rcs2.config import DEFAULTS


def pump(app, seconds, until=None):
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        if until and until():
            return True
        time.sleep(0.02)
    return bool(until and until())


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class UiSmokeTest(unittest.TestCase):
    def test_login_then_run(self):
        from rcs2.ui.windows.login_dialog import LoginDialog
        from rcs2.ui.windows.main_window import MainWindow
        from rcs2.tools.demo import DEMO_POINTS, DEMO_SEQUENCES, start_demo
        from rcs2.runtime import Runtime

        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        tmp = tempfile.mkdtemp()
        base = copy.deepcopy(DEFAULTS)
        base["outbox_path"] = os.path.join(tmp, "outbox.sqlite")
        cfg, stop_demo = start_demo(base, fixtures=2, speed=0.02, test_time=(0.2, 0.1))
        rt = Runtime(cfg, tmp, {"points": DEMO_POINTS, "sequences": DEMO_SEQUENCES, "example": True})
        win = MainWindow(rt, cfg, require_login=True, columns=2)
        rt.start()
        win.show()
        try:
            # before login nothing can be operated
            pump(app, 0.5)
            self.assertFalse(win.btn_start.isEnabled())
            self.assertFalse(win.cards[1].use.isEnabled())
            self.assertEqual(win.user_btn.text(), "Đăng nhập")

            # wrong card is rejected with a message, right one accepted
            dlg = LoginDialog(rt, win)
            dlg.user.setText("12345678")
            dlg.password.setText("wrong")
            dlg.btn.click()
            self.assertTrue(pump(app, 5, lambda: "sai mật khẩu" in dlg.status.text().lower()), dlg.status.text())
            self.assertFalse(dlg.result_login)
            dlg.password.setText("wnc000000")
            dlg.btn.click()
            self.assertTrue(pump(app, 5, lambda: dlg.result_login is not None), dlg.status.text())
            self.assertEqual(dlg.result_login.employee.name, "Demo User")
            pump(app, 0.6)
            self.assertTrue(win.btn_start.isEnabled())
            self.assertTrue(win.cards[1].use.isEnabled())
            self.assertIn("Demo User", win.user_btn.text())

            # use the controls like an operator
            for n in (1, 2):
                win.cards[n].use.click()
            pump(app, 0.5)
            win.btn_start.click()
            self.assertTrue(pump(app, 25, lambda: win.rt.engine.snapshot()["totals"]["total"] >= 3),
                            "no finished tests")
            self.assertEqual(win.run_pill.text(), "ĐANG CHẠY")
            self.assertTrue(win.cards[1].use.isChecked())
            self.assertTrue(win.robot_panel.arm.text() == "ĐÃ ARM")
            self.assertNotEqual(win.totals_panel._v["total"].text(), "0")
            self.assertTrue(win.log.toPlainText())
            # stop the run, then the manual window: jog X+ once
            win.no_confirm = True
            win.rt.engine.stop_run()
            self.assertTrue(pump(app, 15, lambda: win.rt.engine.snapshot()["current_job"] is None
                                 and win.rt.engine.snapshot()["run_state"] == "STOPPED"), "run did not stop")
            win._open_manual()
            man = win.manual
            self.assertTrue(pump(app, 10, lambda: man.jog_buttons[1].isEnabled()), "jog buttons stay disabled")
            before = win.rt.bridge.pos_read()["xyzwpr"][0]
            man.jog_buttons[1].click()                                  # "X +", linear step 1 mm
            self.assertTrue(pump(app, 10, lambda: man.status.text().endswith(": xong")), man.status.text())
            self.assertAlmostEqual(win.rt.bridge.pos_read()["xyzwpr"][0], before + 1.0, places=3)
            self.assertFalse(man.btn_teach.isEnabled() is False)        # teach button is usable (name checked on save)
            pixmap = win.grab()
            self.assertGreater(pixmap.width(), 800)
        finally:
            win.timer.stop()
            rt.stop()
            stop_demo()
            win.close()


if __name__ == "__main__":
    unittest.main()
