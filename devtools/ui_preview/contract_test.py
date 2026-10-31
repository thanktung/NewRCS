"""Checks the view contract that tests/test_ui_smoke.py relies on, using the fake runtime of preview.py
(test_ui_smoke itself needs bridge_simple.py, which is not in the folder right now). Offscreen, no robot."""
import os
import sys
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import preview as P  # noqa: E402
from PySide6 import QtWidgets  # noqa: E402

from rcs2.core import engine as E  # noqa: E402
from rcs2.employee import EmployeeError  # noqa: E402

app = QtWidgets.QApplication([])
rt = P.FakeRuntime()
rt.engine.snap = P.snap_running()
rt.engine.snap["run_state"] = E.STOPPED
rt.engine.snap["current_job"] = None
manual_calls = []
rt.manual_rmove = lambda off, speed: manual_calls.append((off, speed)) or {"ok": 1}

from rcs2.ui.windows.login_dialog import LoginDialog  # noqa: E402
from rcs2.ui.windows.main_window import MainWindow  # noqa: E402

win = MainWindow(rt, P.SETTINGS, require_login=True, columns=2)
win.show()
P.pump(app, 0.5)


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        check.failed = True


check.failed = False

# before login nothing can be operated
check(win.windowTitle().startswith("NewRCS"), "window title carries the new name: %r" % win.windowTitle())
check(not win.btn_start.isEnabled(), "Start disabled before login")
check(not any(s.btn.isEnabled() for s in win.tray_panel.sections.values()), "tray reset buttons disabled before login")
check(not win.cards[1].use.isEnabled(), "fixture toggle disabled before login")
check(win.user_btn.text() == "Đăng nhập", "user button says Login")

# wrong card -> message with tone=error; right card -> accepted
def bad(u, p):
    raise EmployeeError("wrong_card", "Sai mật khẩu")


rt.login = bad
dlg = LoginDialog(rt, win)
dlg.user.setText("24003437")
dlg.password.setText("123")
dlg.btn.click()
end = time.time() + 5
while time.time() < end and "sai mật khẩu" not in dlg.status.text().lower():
    app.processEvents()
    time.sleep(0.02)
check("sai mật khẩu" in dlg.status.text().lower(), "login error text shown: %r" % dlg.status.text())
check(dlg.status.property("tone") == "error", "login status has tone=error")

rt.operator = P.Operator()
P.pump(app, 0.6)
check(win.btn_start.isEnabled(), "Start enabled after login")
check(win.cards[1].use.isEnabled(), "fixture toggle enabled after login")
check("Demo User" in win.user_btn.text(), "user button shows the operator")

# toggle click -> engine.set_enabled(number, bool)
rt.engine.calls.clear()
before = win.cards[6].use.isChecked()
win.cards[6].use.click()
check(win.cards[6].use.isChecked() != before, "toggle flips on click")
check(rt.engine.calls and rt.engine.calls[-1][0] == "set_enabled" and rt.engine.calls[-1][1][0] == 6,
      "toggle calls engine.set_enabled(6, ...): %s" % (rt.engine.calls[-1:],))

# run pill / robot panel / totals / log contract
rt.engine.snap = P.snap_running()
P.pump(app, 0.6)
check(win.run_pill.text() == "ĐANG CHẠY", "run pill RUNNING")
check(win.robot_panel.arm.text() == "ĐÃ ARM", "robot_panel.arm == ARMED")
check(win.totals_panel._v["total"].text() == "37", "totals_panel._v['total'] == 37")
check(bool(win.log.toPlainText()), "log has text")
check(win.cards[1].use.isChecked(), "card 1 toggle reflects enabled state")

# alarms list
rt.engine.snap = P.snap_fault()
P.pump(app, 0.6)
check(len(win.alarm_panel._bars) == 4 and win.alarm_panel.count.text() == "4", "4 alarm bars")
check(win.btn_fault.isVisibleTo(win), "Xác nhận lỗi visible on FAULT")
rt.engine.snap = P.snap_running()
P.pump(app, 0.6)
check(not win.btn_fault.isVisibleTo(win), "Xác nhận lỗi hidden otherwise")

# levels: an operator whose level may only "operate" cannot open Manual or teach
class Lv:
    employee = P.Emp()
    job = "L2 MNM571"
    level = 2
    allowed = frozenset({"operate"})


rt.operator = Lv()
P.pump(app, 0.6)
check(win.btn_pause.isEnabled() and win.cards[1].use.isEnabled(), "level-2 operator may operate (run is RUNNING)")
check(not win.btn_manual.isEnabled(), "level-2 operator may NOT open Manual")
check("L2 MNM571" in win.user_btn.text() and "Cấp 2" in win.user_btn.toolTip(), "user button shows level: %r" % win.user_btn.text())
view_only = Lv()
view_only.allowed = frozenset()
rt.operator = view_only
P.pump(app, 0.6)
check(not win.btn_pause.isEnabled() and not win.cards[1].use.isEnabled(), "view-only operator can not operate")
rt.operator = P.Operator()                       # no 'allowed' attribute: everything permitted
P.pump(app, 0.6)
check(win.btn_manual.isEnabled(), "operator object without level info keeps full access")

# manual dialog: jog X+ calls runtime.manual_rmove([1,0,0,0,0,0], 5) and reports ': ok'
rt.engine.snap["run_state"] = E.STOPPED
rt.engine.snap["current_job"] = None
win._open_manual()
man = win.manual
end = time.time() + 5
while time.time() < end and not man.jog_buttons[1].isEnabled():
    app.processEvents()
    time.sleep(0.02)
check(man.jog_buttons[1].isEnabled(), "jog buttons enabled")
man.jog_buttons[1].click()
end = time.time() + 5
while time.time() < end and not man.status.text().endswith(": xong"):
    app.processEvents()
    time.sleep(0.02)
check(man.status.text().endswith(": xong"), "jog status %r" % man.status.text())
check(man.status.property("tone") == "success", "jog status tone=success")
check(manual_calls == [([1.0, 0, 0, 0, 0, 0], 5)], "manual_rmove called with %r" % (manual_calls,))
check(man.btn_teach.isEnabled(), "teach button usable")

# barcode reader panel: LON test shows the code, LOFF is sent, buttons follow the operator level
check(man.ee_panel is not None and man.scan_panel is not None, "End Effector panel shows the scanner tool")
check(man.btn_scan_test.isEnabled(), "LON test button enabled")
man.btn_scan_test.click()
end = time.time() + 5
while time.time() < end and "SN2610270013" not in man.scan_result.text():
    app.processEvents()
    time.sleep(0.02)
check("SN2610270013" in man.scan_result.text(), "scan result shown: %r" % man.scan_result.text())
check(man.scan_result.property("tone") == "success", "scan result tone=success")
man.btn_scan_stop.click()
end = time.time() + 5
while time.time() < end and "LOFF" not in rt.scan_calls:
    app.processEvents()
    time.sleep(0.02)
check(rt.scan_calls == ["LON", "LOFF"], "runtime got LON then LOFF: %r" % (rt.scan_calls,))

# laser section: judgement read
check(man.laser_panel is not None and man.btn_laser_read.isEnabled(), "laser section with a read button")
man.btn_laser_read.click()
end = time.time() + 5
while time.time() < end and "Judgement" not in man.laser_result.text():
    app.processEvents()
    time.sleep(0.02)
check("GO" in man.laser_result.text() and man.laser_result.property("tone") == "success", "laser GO shown: %r" % man.laser_result.text())

# robot hand panel: chips select heads, actions reach the runtime, pressure pills show which heads hold
check(man.heads_panel is not None and len(man.head_chips) == 8, "heads section with 8 head chips")
check(man._selected_heads() == "all", "all heads selected by default")
man.head_chips[1].setChecked(False)
check(man._selected_heads() == [1, 3, 4, 5, 6, 7, 8], "unchecking head 2 -> %r" % (man._selected_heads(),))
man.btn_vac_on.click()
end = time.time() + 5
while time.time() < end and not man.heads_result.text().endswith("xong"):
    app.processEvents()
    time.sleep(0.02)
check(rt.hand_calls == [("vacuum_on", [1, 3, 4, 5, 6, 7, 8])], "heads_action called: %r" % (rt.hand_calls,))
check(man.heads_result.property("tone") == "success", "heads result tone=success")
check(man.head_pills[3].property("tone") == "success" and "ĐANG HÚT" in man.head_pills[3].toolTip(),
      "head 4 holds -> green: %r %r" % (man.head_pills[3].text(), man.head_pills[3].property("tone")))
check(man.head_pills[4].property("tone") == "warning" and "chưa có áp suất" in man.head_pills[4].toolTip(),
      "head 5 vacuum on but no pressure -> amber: %r" % (man.head_pills[4].property("tone"),))
man.head_chips[1].setChecked(True)
man.btn_cyl_up.click()
end = time.time() + 5
while time.time() < end and len(rt.hand_calls) < 2:
    app.processEvents()
    time.sleep(0.02)
check(rt.hand_calls[-1] == ("cylinder_up", "all"), "cylinder up on all heads: %r" % (rt.hand_calls[-1],))
for c in man.head_chips:
    c.setChecked(False)
end = time.time() + 5
while time.time() < end and man._heads_busy:
    app.processEvents()
    time.sleep(0.02)
man.refresh()
n_calls = len(rt.hand_calls)
man.btn_vac_off.click()
app.processEvents()
check(len(rt.hand_calls) == n_calls and "ít nhất một đầu" in man.heads_result.text(), "no head selected -> refused: %r" % man.heads_result.text())

# re-open the manual window after closing: the refresh timer must run again
man.close()
check(not man.timer.isActive(), "timer stopped on close")
man.show()
check(man.timer.isActive(), "timer restarted on show")

# ---- trays: the block shows both trays, buttons act, sizes come from the dialog
man.hide()
rt.engine.snap = P.snap_running()
rt.operator = P.Operator()
P.pump(app, 0.6)
tp = win.tray_panel
check(win.tabs.tabText(0).startswith("Tray hàng") and win.tabs.tabText(1) == "Nhật ký hoạt động", "tabs: trays first, then the log")
check(win.tabs.currentIndex() == 0 and win.tab_tray == 0, "the tray tab is shown first")
check(not hasattr(tp, "btn_settings"), "no tray size button: sizes come from settings.json only")
P.pump(app, 0.3)
check(tp.holder.isVisibleTo(win) and not tp.empty.isVisibleTo(win), "tray block shows both trays")
check(not any(hasattr(sec, n) for sec in tp.sections.values() for n in ("pill", "size_label")), "no counters, no size labels")
check(hasattr(tp, "legend") and hasattr(tp, "heads_strip") and not hasattr(tp, "btn_reset_flow"), "the tray block: trays + reset buttons + heads + legend")
check(tp.sections["input"].btn.text().strip() == "Nạp lại" and tp.sections["ng"].btn.text().strip() == "Đã dọn", "buttons: Nạp lại / Đã dọn")
check(tp.sections["input"].view.cell_size() > 0, "cells are drawn: %d px" % tp.sections["input"].view.cell_size())
rt.engine.snap = P.snap_fault()
P.pump(app, 0.6)
check(win.tabs.tabText(win.tab_tray).endswith("●"), "empty input tray is flagged on the tab: %r" % win.tabs.tabText(win.tab_tray))
rt.engine.snap = P.snap_offline()
P.pump(app, 0.6)
check(win.tabs.tabText(win.tab_tray) == "Tray hàng", "no flag when nothing needs the operator")
check(tp.empty.isVisibleTo(win) and not tp.holder.isVisibleTo(win), "not configured -> hint instead of trays")
rt.engine.snap = P.snap_running()
P.pump(app, 0.6)
import rcs2.ui.kit.fluent as FL
saved_confirm = FL.confirm
FL.confirm = lambda *a, **k: True
tp.sections["input"].btn.click()
tp.sections["ng"].btn.click()
FL.confirm = saved_confirm
check(rt.tray_calls == [("reset", "input"), ("reset", "ng")], "reset buttons reach the runtime: %r" % (rt.tray_calls,))

# ---- start the robot program (RSR0001 through UOP)
check(win.robot_panel.btn_program.isVisibleTo(win), "robot panel has the start-program button")
stopped = P.snap_running()
stopped["run_state"] = E.STOPPED
stopped["current_job"] = None
stopped["program_running"] = False          # nothing to start when the program already runs
rt.engine.snap = stopped
P.pump(app, 0.6)
check(win.robot_panel.btn_program.isEnabled(), "start-program enabled when stopped and the robot is connected")
saved_confirm = FL.confirm
popups = []                                  # the start / stop buttons must act at once: no confirmation pop-up
FL.confirm = lambda *a, **k: popups.append(a) or True
win.robot_panel.btn_program.click()
FL.confirm = saved_confirm
end = time.time() + 5
while time.time() < end and ("start_program",) not in rt.tray_calls:
    app.processEvents()
    time.sleep(0.02)
check(("start_program",) in rt.tray_calls, "button calls runtime.robot_start_program")
rt.engine.snap = P.snap_running()
P.pump(app, 0.6)
check(not win.robot_panel.btn_program.isEnabled(), "start-program disabled while RUNNING")
check(win.robot_panel.btn_stop_robot.isEnabled(), "stop-robot stays enabled while RUNNING")
popups = []                                  # the start / stop buttons must act at once: no confirmation pop-up
FL.confirm = lambda *a, **k: popups.append(a) or True
win.robot_panel.btn_stop_robot.click()
FL.confirm = saved_confirm
check(not popups, 'start / stop robot buttons show no confirmation pop-up')
end = time.time() + 5
while time.time() < end and ("stop_robot",) not in rt.tray_calls:
    app.processEvents()
    time.sleep(0.02)
check(("stop_robot",) in rt.tray_calls, "button calls runtime.robot_stop_program")
rt.operator = None
rt.engine.snap = stopped
P.pump(app, 0.6)
check(not win.robot_panel.btn_program.isEnabled(), "start-program disabled without login")
check(not win.robot_panel.btn_stop_robot.isEnabled(), "stop-robot disabled without login")
rt.operator = P.Operator()
rt.engine.snap = P.snap_running()
P.pump(app, 0.4)

# ---- robot program off (UO[3] PROGRUN = 0): nothing that writes R[1] may be offered
off = P.snap_running()
off["run_state"] = E.STOPPED
off["current_job"] = None
off["program_running"] = False
rt.engine.snap = off
P.pump(app, 0.6)
check(win.robot_panel._v["prog"].text() == "DỪNG" and win.robot_panel._v["prog"].property("tone") == "danger",
      "program pill says DỪNG in red: %r" % win.robot_panel._v["prog"].text())
check(not win.robot_panel.btn_safe.isEnabled(), "safe position disabled while the program is off")
check(not win.btn_start.isEnabled() and "UO[3]" in win.btn_start.toolTip(), "Start disabled with the reason as tooltip")
check(win.robot_panel.btn_program.isEnabled(), "'Chạy chương trình' offered while the program is off")
check(win.robot_panel.btn_stop_robot.isEnabled(), "stop stays available")
win._open_manual()
P.pump(app, 0.4)
check(not any(b.isEnabled() for b in win.manual.jog_buttons) and not win.manual.btn_safe.isEnabled()
      and not win.manual.btn_goto.isEnabled(), "manual window: jog / goto / safe disabled while the program is off")
check(not win.manual.btn_teach.isEnabled() and not win.manual.btn_fault.isEnabled(),
      "manual window: teach and clear-fault disabled while the program is off")
check(not any(b.isEnabled() for b in win.manual.heads_buttons) and not win.manual.btn_laser_read.isEnabled(),
      "manual window: heads and laser (robot I/O) disabled while the program is off")
check("UO[3]" in win.manual.status.text(), "manual window says why: %r" % win.manual.status.text())
win.manual.hide()
on = P.snap_running()
on["run_state"] = E.STOPPED
on["current_job"] = None
rt.engine.snap = on
P.pump(app, 0.6)
check(win.robot_panel._v["prog"].text() == "ĐANG CHẠY", "program pill says ĐANG CHẠY")
check(win.robot_panel.btn_safe.isEnabled() and win.btn_start.isEnabled(), "safe position and Start available again")
check(not win.robot_panel.btn_program.isEnabled(), "nothing to start when the program already runs")
rt.engine.snap = P.snap_running()
P.pump(app, 0.4)

# ---- automatic logout: countdown on the user button, and what happens when the time is up
rt.engine.snap = P.snap_running()
rt.remaining = 143.0
P.pump(app, 0.6)
check("(" not in win.user_btn.text() and "2:23" in win.user_btn.toolTip(), "tooltip has the countdown, button stays short: %r" % win.user_btn.text())
rt.remaining = 45.0
P.pump(app, 0.6)
check("(0:45)" in win.user_btn.text(), "last minute: countdown on the button: %r" % win.user_btn.text())
win._open_manual()
P.pump(app, 0.3)
check(win.manual.isVisible(), "manual open before the timeout")
rt.remaining = 0.0
P.pump(app, 0.6)
check(rt.logged_out_by_timer and rt.operator is None, "operator logged out when the time is up")
check(win.user_btn.text() == "Đăng nhập" and not win.btn_start.isEnabled(), "UI back to the logged-out state")
check(not win.manual.isVisible(), "manual window closed by the automatic logout")

win.timer.stop()
man.timer.stop()
print("RESULT:", "FAILED" if check.failed else "ALL OK")
sys.exit(1 if check.failed else 0)


