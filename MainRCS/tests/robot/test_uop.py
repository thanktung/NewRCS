"""Starting RSR0001 through the UOP signals: UI[n] driven as SDI[n], results read from UO[n]."""
import copy
import os
import tempfile
import unittest

from tests.support import bridge as helpers
from rcs2.config import DEFAULTS
from rcs2.core.sequence import save_sequences
from rcs2.robot import uop as U
from rcs2.robot.client import RobotError
from rcs2.runtime import Runtime

from tests.support.engine import SEQ


class FakeController:
    """Bridge io on the UOP signals. Behaves like a robot controller:
       - a pulse on SDI[5] (RESET) clears FAULT (UO[6]) unless `fault_stays`
       - a pulse on SDI[6] (START) starts the program (UO[3]) only when SDI[1..3] and SDI[8] are ON and the program was
         selected by a pulse on SDI[9] and there is no fault - unless `never_runs`
       Every write is logged as (index, value) so the order can be checked."""

    def __init__(self, fault=True, running=False, fault_stays=False, never_runs=False, never_stops=False):
        self.sdi, self.uo, self.log = {}, {}, []
        self.uo[U.UO_FAULT] = 1 if fault else 0
        self.uo[U.UO_PROGRUN] = 1 if running else 0
        self.fault_stays, self.never_runs, self.never_stops = fault_stays, never_runs, never_stops
        self.selected = False
        self.fail_write_at = None
        self.wrong_readback = False

    def io_write(self, kind, index, values):
        assert kind == "SDI", kind                                  # UI is driven as SDI, never as UI
        if self.fail_write_at == index:
            raise RuntimeError("NOT_ARMED: io.write requires 'arm'")
        for i, v in enumerate(values):
            old = self.sdi.get(index + i, 0)
            self.sdi[index + i] = int(v)
            self.log.append((index + i, int(v)))
            if old == 0 and v == 1:
                self._rising(index + i)
        if any(self.sdi.get(i, 1) == 0 for i in (1, 2, 3)) and any(index <= i < index + len(values) for i in (1, 2, 3)):
            self._program_stops()                                   # IMSTP / HOLD / SFSPD off: the robot stops
        back = [self.sdi[index + i] for i in range(len(values))]
        return [1 - b for b in back] if self.wrong_readback else back

    def _program_stops(self):
        if not self.never_stops:
            self.uo[U.UO_PROGRUN] = 0

    def _rising(self, n):
        if 9 <= n <= 16:                                            # RSR1..RSR8
            self.selected = True
        elif n == 4:                                                # CSTOPI: cycle stop
            self._program_stops()
        elif n == 5 and not self.fault_stays:
            self.uo[U.UO_FAULT] = 0
        elif n == 6 and not self.never_runs:
            ready = all(self.sdi.get(i) == 1 for i in (1, 2, 3, 8)) and self.selected and not self.uo[U.UO_FAULT]
            if ready:
                self.uo[U.UO_PROGRUN] = 1

    def io_read(self, kind, index, count):
        assert kind == "UO", kind
        return [self.uo.get(index + i, 0) for i in range(count)]


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, s):
        self.now += s


def make(**kw):
    ctrl = FakeController(**kw)
    clock = Clock()
    texts = []
    starter = U.RobotStarter(ctrl, {}, sleep=clock.sleep, clock=clock, log_fn=texts.append)
    return starter, ctrl, texts


class SequenceTests(unittest.TestCase):
    def test_the_whole_sequence_in_the_commissioned_order(self):
        starter, ctrl, texts = make()
        self.assertEqual(starter.start(), "RSR0001 đang chạy")
        self.assertEqual(ctrl.log, [
            (1, 1), (2, 1), (3, 1),            # IMSTP, HOLD, SFSPD on
            (8, 1),                            # ENBL on
            (9, 1), (9, 0),                    # pulse RSR1: select RSR0001
            (5, 1), (5, 0),                    # pulse RESET, then FAULT is read
            (6, 1), (6, 0)])                   # pulse START, then PROGRUN is read
        self.assertEqual(ctrl.uo[U.UO_PROGRUN], 1)
        self.assertEqual(ctrl.sdi[9] + ctrl.sdi[5] + ctrl.sdi[6], 0)           # no pulse left ON
        self.assertEqual((ctrl.sdi[1], ctrl.sdi[2], ctrl.sdi[3], ctrl.sdi[8]), (1, 1, 1, 1))   # enables stay ON
        self.assertTrue(any("UI[9]" in t for t in texts), texts)

    def test_pulse_has_the_configured_width(self):
        ctrl, clock = FakeController(), Clock()
        starter = U.RobotStarter(ctrl, {"pulse_s": 0.5}, sleep=clock.sleep, clock=clock)
        starter.start()
        self.assertGreaterEqual(clock.now, 1.5)                               # 3 pulses of 0.5 s

    def test_nothing_is_written_when_the_program_already_runs(self):
        starter, ctrl, _ = make(running=True)
        self.assertEqual(starter.start(), "RSR0001 đã đang chạy")
        self.assertEqual(ctrl.log, [])

    def test_other_rsr_number_selects_the_matching_ui(self):
        ctrl, clock = FakeController(), Clock()
        starter = U.RobotStarter(ctrl, {"rsr": 3}, sleep=clock.sleep, clock=clock)
        self.assertEqual(starter.program, "RSR0003")
        starter.start()
        self.assertIn((11, 1), ctrl.log)                                      # RSR3 = UI[11]
        self.assertNotIn((9, 1), ctrl.log)

    def test_fault_that_does_not_clear_stops_before_start(self):
        starter, ctrl, _ = make(fault_stays=True)
        with self.assertRaises(U.StartError) as cm:
            starter.start()
        self.assertIn("còn lỗi", str(cm.exception))
        self.assertIn("UO[6] FAULT=1", str(cm.exception))                     # diagnostic with the UO states
        self.assertNotIn((6, 1), ctrl.log)                                    # START was never pulsed
        self.assertEqual(ctrl.sdi[5], 0)

    def test_program_that_does_not_run_is_reported(self):
        starter, ctrl, _ = make(never_runs=True)
        with self.assertRaises(U.StartError) as cm:
            starter.start()
        self.assertIn("RSR0001 chưa chạy", str(cm.exception))
        self.assertIn("UO[3] PROGRUN=0", str(cm.exception))
        self.assertEqual(ctrl.sdi[6], 0)                                      # START released

    def test_a_slow_fault_reset_is_waited_for(self):
        ctrl, clock = FakeController(fault_stays=True), Clock()
        reads = {"n": 0}
        original = ctrl.io_read

        def slow_read(kind, index, count):
            if index == U.UO_FAULT and count == 1:
                reads["n"] += 1
                if reads["n"] == 4:
                    ctrl.uo[U.UO_FAULT] = 0                                    # clears after a few polls
            return original(kind, index, count)
        ctrl.io_read = slow_read
        starter = U.RobotStarter(ctrl, {}, sleep=clock.sleep, clock=clock)
        self.assertEqual(starter.start(), "RSR0001 đang chạy")

    def test_write_problems_are_reported_and_pulses_released(self):
        starter, ctrl, _ = make()
        ctrl.fail_write_at = 9
        with self.assertRaises(U.StartError) as cm:
            starter.start()
        self.assertIn("NOT_ARMED", str(cm.exception))
        starter, ctrl, _ = make()
        ctrl.wrong_readback = True
        with self.assertRaises(U.StartError) as cm:
            starter.start()
        self.assertIn("đọc lại", str(cm.exception))

    def test_pulse_is_released_even_if_waiting_fails(self):
        ctrl = FakeController()

        def boom(seconds):
            raise KeyboardInterrupt()
        starter = U.RobotStarter(ctrl, {}, sleep=boom)
        with self.assertRaises(KeyboardInterrupt):
            starter.start()
        self.assertEqual(ctrl.sdi[9], 0)                                       # the 0 was still written


class StopTests(unittest.TestCase):
    def test_pulse_cstopi_then_switch_the_enables_off(self):
        starter, ctrl, texts = make(running=True)
        self.assertEqual(starter.stop(), "RSR0001 đã dừng")
        self.assertEqual(ctrl.log, [(4, 1), (4, 0), (1, 0), (2, 0), (3, 0)])
        self.assertEqual(ctrl.uo[U.UO_PROGRUN], 0)
        self.assertEqual((ctrl.sdi[1], ctrl.sdi[2], ctrl.sdi[3], ctrl.sdi[4]), (0, 0, 0, 0))

    def test_stop_is_allowed_when_nothing_runs(self):
        starter, ctrl, _ = make(running=False)
        self.assertEqual(starter.stop(), "RSR0001 đã dừng")

    def test_a_robot_that_keeps_running_is_reported(self):
        starter, ctrl, _ = make(running=True, never_stops=True)
        with self.assertRaises(U.StopError) as cm:
            starter.stop()
        self.assertIn("chưa dừng", str(cm.exception))
        self.assertIn("E-stop", str(cm.exception))
        self.assertIn("UO[3] PROGRUN=1", str(cm.exception))

    def test_the_enables_are_switched_off_even_if_the_pulse_fails(self):
        starter, ctrl, _ = make(running=True)
        ctrl.fail_write_at = 4
        with self.assertRaises(U.StopError) as cm:
            starter.stop()
        self.assertIn("E-stop", str(cm.exception))
        self.assertEqual((ctrl.sdi[1], ctrl.sdi[2], ctrl.sdi[3]), (0, 0, 0))

    def test_stop_aborts_a_start_that_is_in_progress(self):
        ctrl, clock = FakeController(), Clock()
        starter = U.RobotStarter(ctrl, {}, sleep=clock.sleep, clock=clock)
        calls = {"n": 0}
        original = clock.sleep

        def sleeping(s):
            calls["n"] += 1
            if calls["n"] == 1:                                   # the operator presses Stop during the first pulse
                starter.abort.set()
            original(s)
        starter.sleep = sleeping
        with self.assertRaises(U.StartError) as cm:
            starter.start()
        self.assertIn("có lệnh dừng", str(cm.exception))
        self.assertNotIn((6, 1), ctrl.log)                          # START never pulsed
        self.assertEqual(ctrl.sdi[9], 0)                            # the pulse in flight was released

    def test_stop_settings_are_validated(self):
        self.assertEqual(U.normalize(None)["stop_wait_s"], 3.0)
        with self.assertRaises(U.StartError):
            U.normalize({"stop_wait_s": 0})


class ConfigTests(unittest.TestCase):
    def test_defaults_and_validation(self):
        self.assertEqual(U.normalize(None)["rsr"], 1)
        self.assertEqual(U.normalize({"_note": "x", "pulse_s": 1})["pulse_s"], 1)
        for bad in ({"rsr": 0}, {"rsr": 9}, {"rsr": "1"}, {"rsr": True}, {"pulse_s": 0}, {"run_wait_s": -1},
                    {"poll_s": "x"}):
            with self.assertRaises(U.StartError, msg=str(bad)):
                U.normalize(bad)

    def test_shipped_settings_are_valid(self):
        import json
        for name in ("settings.json", "settings.example.json"):
            with open(os.path.join(helpers.ROOT, "config", name), encoding="utf-8") as fh:
                self.assertEqual(U.normalize(json.load(fh)["robot_start"])["rsr"], 1)


class FakeBridge:
    """The part of BridgeClient that Runtime.robot_start_program uses (plus the controller I/O)."""

    def __init__(self, ctrl):
        self.ctrl, self.connected, self.last_status = ctrl, True, {}
        self.calls = []
        self.is_armed = False

    def arm(self):
        self.calls.append("arm")
        self.is_armed = True

    def disarm(self):
        self.calls.append("disarm")
        self.is_armed = False

    def fault_clear(self, force=False):
        self.calls.append("fault_clear")

    def io_write(self, kind, index, values):
        assert self.is_armed, "io.write needs the bridge armed"
        return self.ctrl.io_write(kind, index, values)

    def io_read(self, kind, index, count):
        return self.ctrl.io_read(kind, index, count)


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        cfg = copy.deepcopy(DEFAULTS)
        cfg["outbox_path"] = "outbox.sqlite"
        cfg["engine"]["sequences_path"] = "sequences.json"
        cfg["robot_start"].update({"pulse_s": 0.01, "poll_s": 0.01, "reset_wait_s": 0.2, "run_wait_s": 0.2})
        save_sequences(os.path.join(self.tmp.name, "sequences.json"), {"points": {}, "sequences": SEQ})
        self.rt = Runtime(cfg, self.tmp.name)
        self.ctrl = FakeController()
        self.rt.bridge = FakeBridge(self.ctrl)
        self.logs = []
        self.rt.on_log = lambda level, text: self.logs.append(text)

    def tearDown(self):
        self.rt.stop()
        self.tmp.cleanup()

    def test_armed_only_for_the_start_and_disarmed_afterwards(self):
        self.assertEqual(self.rt.robot_start_program(), "RSR0001 đang chạy")
        self.assertEqual(self.rt.bridge.calls, ["arm", "disarm"])
        self.assertEqual(self.ctrl.uo[U.UO_PROGRUN], 1)
        self.assertTrue(any("RSR0001" in t for t in self.logs), self.logs)

    def test_a_latched_bridge_fault_is_cleared_first_and_a_failure_still_disarms(self):
        self.rt.bridge.last_status = {"fault": True}
        self.ctrl.never_runs = True
        with self.assertRaises(U.StartError):
            self.rt.robot_start_program()
        self.assertEqual(self.rt.bridge.calls, ["fault_clear", "arm", "disarm"])

    def test_refused_while_running_or_without_the_bridge(self):
        self.rt.engine.run_state = "RUNNING"
        with self.assertRaises(RobotError):
            self.rt.robot_start_program()
        self.rt.engine.run_state = "STOPPED"
        self.rt.bridge.connected = False
        with self.assertRaises(ConnectionError):
            self.rt.robot_start_program()
        self.assertEqual(self.ctrl.log, [])

    def test_robot_stop_arms_only_when_needed_and_stops_the_run(self):
        self.ctrl.uo[U.UO_PROGRUN] = 1
        stops = []
        self.rt.engine.stop_run = lambda: stops.append(1)
        self.assertEqual(self.rt.robot_stop_program(), "RSR0001 đã dừng")
        self.assertEqual(self.rt.bridge.calls, ["arm", "disarm"])
        self.assertEqual(stops, [1])
        self.assertEqual(self.ctrl.uo[U.UO_PROGRUN], 0)

    def test_robot_stop_keeps_an_arm_held_by_a_running_cell(self):
        self.ctrl.uo[U.UO_PROGRUN] = 1
        self.rt.bridge.is_armed = True
        self.rt.bridge.last_status = {"armed": True}
        self.rt.engine.run_state = "RUNNING"                          # stop is never refused while running
        self.rt.engine.stop_run = lambda: None
        self.rt.robot_stop_program()
        self.assertEqual(self.rt.bridge.calls, [])                    # neither armed nor disarmed by us
        self.assertEqual(self.ctrl.log[:2], [(4, 1), (4, 0)])

    def test_robot_stop_without_bridge_still_stops_the_run(self):
        stops = []
        self.rt.engine.stop_run = lambda: stops.append(1)
        self.rt.bridge.connected = False
        with self.assertRaises(ConnectionError):
            self.rt.robot_stop_program()
        self.assertEqual(stops, [1])

    def test_a_failed_stop_still_releases_the_arm_and_stops_the_run(self):
        self.ctrl.uo[U.UO_PROGRUN] = 1
        self.ctrl.never_stops = True
        stops = []
        self.rt.engine.stop_run = lambda: stops.append(1)
        with self.assertRaises(U.StopError):
            self.rt.robot_stop_program()
        self.assertEqual(self.rt.bridge.calls, ["arm", "disarm"])
        self.assertEqual(stops, [1])

    def test_a_start_after_a_stop_is_not_cancelled_by_the_old_stop(self):
        self.rt.engine.stop_run = lambda: None
        self.rt.robot_stop_program()
        self.assertEqual(self.rt.robot_start_program(), "RSR0001 đang chạy")

    def test_a_bad_robot_start_setting_stops_the_start_up(self):
        cfg = copy.deepcopy(DEFAULTS)
        cfg["outbox_path"] = "outbox2.sqlite"
        cfg["engine"]["sequences_path"] = "sequences.json"
        cfg["robot_start"]["rsr"] = 12
        with self.assertRaises(U.StartError):
            Runtime(cfg, self.tmp.name)


if __name__ == "__main__":
    unittest.main()
