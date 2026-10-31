"""Is the robot program running (UO[3] PROGRUN)? Nothing may write R[1] while it is off - e.g. 'safe position' after a stop."""
import copy
import tempfile
import time
import unittest

from tests.support import bridge as helpers
from rcs2.ats import protocol as AP
from rcs2.config import DEFAULTS
from rcs2.core import engine as E
from rcs2.robot import protocol as P
from rcs2.robot.client import BridgeClient, RobotError
from rcs2.runtime import Runtime

from tests.support.engine import SEQ, EngineCase, FakeRobot, wait_until


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.fx = helpers.BridgeFixture()
        self.c = self.fx.client()
        self.c.robot_connect()

    def tearDown(self):
        self.c.close()
        self.fx.close()

    def test_reads_uo3_and_remembers_it(self):
        self.assertIsNone(self.c.program_state)                     # nothing read yet
        self.assertTrue(self.c.program_running())                  # the simulated RSR0001 is running
        self.assertIs(self.c.refresh_program_state(), True)
        self.assertIs(self.c.program_state, True)
        self.c.call("sim.reset", {"cold": True})                   # controller without a running program
        self.assertIs(self.c.refresh_program_state(), False)
        self.assertIs(self.c.program_state, False)

    def test_unknown_when_the_link_is_down(self):
        self.c.refresh_program_state()
        self.c.close()
        self.assertIsNone(self.c.refresh_program_state())
        self.assertIsNone(self.c.program_state)


class FakeProgramRobot(FakeRobot):
    """Engine test robot that can say whether its program runs."""

    def __init__(self, running=True):
        FakeRobot.__init__(self)
        self.program_state = running

    def refresh_program_state(self):
        return self.program_state


class EngineProgramTests(EngineCase):
    fixtures = 1

    def setUp(self):
        super().setUp()
        self.eng.shutdown()
        self.robot = FakeProgramRobot(True)
        self.eng = E.Engine(self.cfg, self.robot, self.ats, self.sink, self.errors, SEQ, {})
        self.eng.start()
        self.eng.on_ats_connection(1, True)
        self.eng.set_enabled(1, True)

    def alarm_codes(self):
        return [a["key"] for a in self.eng.snapshot()["alarms"]]

    def test_snapshot_tells_whether_the_program_runs(self):
        self.assertIs(self.eng.snapshot()["program_running"], True)
        self.robot.program_state = False
        self.assertIs(self.eng.snapshot()["program_running"], False)
        self.robot.program_state = None
        self.assertIsNone(self.eng.snapshot()["program_running"])

    def test_the_run_does_not_start_while_the_program_is_off(self):
        self.robot.program_state = False
        self.eng.start_run()
        time.sleep(0.4)
        self.assertEqual(self.eng.snapshot()["run_state"], E.STOPPED)
        self.assertFalse(self.robot.armed)
        self.assertIn("robot_program", self.alarm_codes())

    def test_the_run_does_not_start_when_uo3_cannot_be_read(self):
        self.robot.program_state = None
        self.eng.start_run()
        time.sleep(0.4)
        self.assertEqual(self.eng.snapshot()["run_state"], E.STOPPED)
        self.assertFalse(self.robot.armed)

    def test_start_is_clean_once_the_program_runs(self):
        self.robot.program_state = False
        self.eng.start_run()
        wait_until(lambda: "robot_program" in self.alarm_codes(), what="alarm")
        self.robot.program_state = True
        self.eng.start_run()
        wait_until(lambda: self.eng.snapshot()["run_state"] == E.RUNNING, what="RUNNING")
        self.assertNotIn("robot_program", self.alarm_codes())

    def test_no_job_is_dispatched_while_the_program_is_off(self):
        self.eng.start_run()
        wait_until(lambda: self.eng.snapshot()["run_state"] == E.RUNNING, what="RUNNING")
        self.robot.program_state = False
        self.eng.on_ats_event(1, AP.parse_message("TtoC_resultWaitdut"))
        time.sleep(0.6)
        self.assertEqual(self.robot.calls, [])                       # nothing was written to the robot
        self.robot.program_state = True
        wait_until(lambda: self.fx(1)["state"] == E.TESTING, what="load after the program is back")

    def test_a_program_that_stops_during_the_run_pauses_it_with_an_alarm(self):
        self.eng.start_run()
        wait_until(lambda: self.eng.snapshot()["run_state"] == E.RUNNING, what="RUNNING")
        self.robot.program_state = False
        wait_until(lambda: self.eng.snapshot()["run_state"] == E.PAUSED, timeout=4, what="PAUSED")
        self.assertIn("robot_program", self.alarm_codes())
        self.robot.program_state = True
        wait_until(lambda: "robot_program" not in self.alarm_codes(), what="alarm cleared")

    def test_a_short_glitch_does_not_stop_the_cell(self):
        self.eng.start_run()
        wait_until(lambda: self.eng.snapshot()["run_state"] == E.RUNNING, what="RUNNING")
        self.robot.program_state = False
        time.sleep(0.4)                                              # shorter than the 1 s the engine waits
        self.robot.program_state = True
        time.sleep(1.2)
        self.assertEqual(self.eng.snapshot()["run_state"], E.RUNNING)


class FakeBridge:
    """What Runtime uses for manual motions; `program` is UO[3]."""

    def __init__(self, program=True):
        self.connected = True
        self.last_status = {"connected": True}
        self.program = program
        self.program_state = None
        self.calls = []

    def refresh_program_state(self):
        self.program_state = self.program
        return self.program

    def arm(self):
        self.calls.append("arm")

    def disarm(self):
        self.calls.append("disarm")

    def gosafehere(self, override=None):
        self.calls.append("gosafehere")
        return {"op": "gosafehere"}

    def rmove(self, offset, override=None):
        self.calls.append("rmove")
        return {"op": "rmove"}

    def io_write(self, kind, index, values):
        self.calls.append(("io_write", kind, index))
        return list(values)

    def io_read(self, kind, index, count):
        return [0] * count

    def fault_clear(self, force=False):
        self.calls.append("fault_clear")
        return {"r1": 0}

    def pos_read(self):
        self.calls.append("pos_read")
        return {"xyzwpr": [0] * 6, "config": [0] * 7, "uf": 0, "ut": 1}


class _UopBridge(FakeBridge):
    """A bridge whose UOP signals the real RobotStarter can drive: SDI writes are accepted, UO[3] follows CSTOPI."""

    def __init__(self):
        FakeBridge.__init__(self, program=True)
        self.sdi = {}

    def io_write(self, kind, index, values):
        for i, v in enumerate(values):
            self.sdi[index + i] = v
            if index + i == 4 and v == 1:
                self.program = False
        return list(values)

    def io_read(self, kind, index, count):
        if kind == "UO":
            return [int(self.program) if index + i == 3 else 0 for i in range(count)]
        return [0] * count


class RuntimeGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        cfg = copy.deepcopy(DEFAULTS)
        cfg["outbox_path"] = "outbox.sqlite"
        self.rt = Runtime(cfg, self.tmp.name, {"points": {}, "sequences": SEQ})
        self.bridge = FakeBridge()
        self.rt.bridge = self.bridge

    def tearDown(self):
        self.rt.stop()
        self.tmp.cleanup()

    def test_motions_are_refused_while_the_program_is_off_and_nothing_is_armed_or_written(self):
        self.bridge.program = False
        for call in (self.rt.robot_gosafehere, lambda: self.rt.manual_rmove([1, 0, 0, 0, 0, 0], 5)):
            with self.assertRaises(RobotError) as cm:
                call()
            self.assertEqual(cm.exception.code, P.E_PROGRAM_STOPPED)
            self.assertIn("UO[3]", cm.exception.message)
        self.assertEqual(self.bridge.calls, [])                        # not armed, no command

    def test_motions_run_while_the_program_runs(self):
        self.rt.robot_gosafehere()
        self.rt.manual_rmove([1, 0, 0, 0, 0, 0], 5)
        self.assertEqual(self.bridge.calls, ["arm", "gosafehere", "disarm", "arm", "rmove", "disarm"])

    def test_unreadable_uo3_refuses_too(self):
        self.bridge.refresh_program_state = lambda: None
        with self.assertRaises(RobotError) as cm:
            self.rt.robot_gosafehere()
        self.assertEqual(cm.exception.code, P.E_PROGRAM_STOPPED)
        self.assertEqual(self.bridge.calls, [])

    def test_every_robot_operation_is_refused_while_the_program_is_off(self):
        self.bridge.program = False
        self.rt._seq_path = "sequences.json"                           # teaching is possible (not demo mode) ...
        self.rt.points = lambda: {"p1": [0, 0, 0, 0, 0, 0]}            # ... and the point exists: only the guard refuses
        operations = [lambda: self.rt.heads_action("vacuum_on"), lambda: self.rt.heads_action("cylinder_down", [1]),
                      self.rt.heads_status, self.rt.laser_status, self.rt.robot_fault_clear,
                      lambda: self.rt.teach_point("p1"), self.rt.robot_gosafehere,
                      lambda: self.rt.manual_rmove([1, 0, 0, 0, 0, 0], 5),
                      lambda: self.rt.manual_move_to("p1", 5)]
        for i, op in enumerate(operations):
            with self.assertRaises(RobotError, msg="operation %d" % i) as cm:
                op()
            self.assertEqual(cm.exception.code, P.E_PROGRAM_STOPPED, "operation %d" % i)
        self.assertEqual(self.bridge.calls, [])                        # nothing armed, nothing written

    def test_starting_and_stopping_the_program_do_not_need_it(self):
        self.bridge.program = False
        stops = []
        self.rt.engine.stop_run = lambda: stops.append(1)
        self.rt.bridge = _UopBridge()
        self.assertEqual(self.rt.robot_stop_program(), "RSR0001 đã dừng")      # works with the program off
        self.assertEqual(stops, [1])


class RuntimeSimTests(unittest.TestCase):
    """The reported bug against the simulated robot: after Stop, 'safe position' must not write R[1]."""

    def setUp(self):
        self.fx = helpers.BridgeFixture(sim_delay_s=0.05)
        self.tmp = tempfile.TemporaryDirectory()
        cfg = copy.deepcopy(DEFAULTS)
        cfg["outbox_path"] = "outbox.sqlite"
        cfg["bridge"].update({"host": "127.0.0.1", "port": self.fx.port})
        cfg["robot_start"].update({"pulse_s": 0.02, "poll_s": 0.01, "monitor_s": 0.1, "reset_wait_s": 1.0,
                                   "run_wait_s": 1.0, "stop_wait_s": 1.0})
        self.rt = Runtime(cfg, self.tmp.name, {"points": {}, "sequences": SEQ})
        self.logs = []
        self.rt.on_log = lambda level, text: self.logs.append((level, text))
        self.rt.start()
        wait_until(lambda: self.rt.bridge.program_state is True, what="UO[3] read after opening")

    def tearDown(self):
        self.rt.stop()
        self.fx.close()
        self.tmp.cleanup()

    def r1_commands(self):
        return len(self.fx.sim.executed)

    def test_opening_tells_whether_the_robot_runs(self):
        self.assertTrue(any("đang chạy (UO[3] PROGRUN = 1)" in t for _, t in self.logs), self.logs)
        self.assertIs(self.rt.engine.snapshot()["program_running"], True)

    def test_a_cold_robot_is_reported_when_opening(self):
        self.fx.sim.reset(cold=True)
        wait_until(lambda: self.rt.bridge.program_state is False, what="UO[3] = 0 noticed")
        self.assertTrue(any(level == "warn" and "CHƯA chạy" in t for level, t in self.logs), self.logs)
        self.assertIs(self.rt.engine.snapshot()["program_running"], False)

    def test_safe_position_after_stop_is_refused_and_r1_is_never_written(self):
        self.rt.robot_stop_program()
        self.assertIs(self.rt.bridge.program_state, False)
        before = self.r1_commands()
        with self.assertRaises(RobotError) as cm:
            self.rt.robot_gosafehere()
        self.assertEqual(cm.exception.code, P.E_PROGRAM_STOPPED)
        with self.assertRaises(RobotError):
            self.rt.manual_rmove([1, 0, 0, 0, 0, 0], 5)
        self.assertEqual(self.fx.sim.r_get(1), 0)                    # R[1] untouched
        self.assertEqual(self.r1_commands(), before)
        self.assertFalse(self.rt.bridge.last_status.get("armed"))     # not even armed for it

    def test_after_start_the_robot_moves_again(self):
        self.rt.robot_stop_program()
        wait_until(lambda: self.rt.bridge.program_state is False, what="program off")
        self.rt.robot_start_program()
        self.assertIs(self.rt.bridge.program_state, True)
        self.rt.robot_gosafehere()
        self.assertEqual(self.fx.sim.executed[-1][0], 7)              # gosafehere ran

    def test_the_run_is_refused_after_a_stop_and_allowed_after_a_start(self):
        self.rt.robot_stop_program()
        self.rt.engine.start_run()
        time.sleep(0.5)
        self.assertEqual(self.rt.engine.snapshot()["run_state"], E.STOPPED)
        self.rt.robot_start_program()
        self.rt.engine.start_run()
        wait_until(lambda: self.rt.engine.snapshot()["run_state"] == E.RUNNING, what="RUNNING")


if __name__ == "__main__":
    unittest.main()
