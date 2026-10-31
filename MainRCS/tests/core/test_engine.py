"""Engine behaviour that does not depend on the planner: start / pause / stop, alarms, faults, the robot program (UO[3])."""
import time
import unittest

from rcs2.ats import protocol as AP
from rcs2.core import engine as E
from tests.support.engine import EngineCase, wait_until


def all_testing(case):
    return all(f["state"] == E.TESTING for f in case.fixtures().values())


class RunTests(EngineCase):
    def test_nothing_runs_until_started(self):
        for n in self.ats:
            self.eng.on_ats_event(n, AP.parse_message("TtoC_resultWaitdut"))
        time.sleep(0.4)
        self.assertEqual(self.robot.moves, [])
        self.eng.start_run()
        wait_until(lambda: all_testing(self), 8, "every box testing")

    def test_pause_stops_new_jobs_and_start_resumes(self):
        self.start()
        wait_until(lambda: all_testing(self), 8, "every box testing")
        self.eng.pause_run()
        wait_until(lambda: self.eng.run_state == E.PAUSED and self.eng.snapshot()["current_job"] is None, 5, "paused")
        self.assertIn("9026", self.alarm_codes())
        moves = len(self.robot.moves)
        self.answer_tests(lambda cell, attempt: "PASS")
        time.sleep(0.4)
        self.assertEqual(len(self.robot.moves), moves)                       # the tested products wait while paused
        self.eng.start_run()
        wait_until(lambda: len(self.robot.moves) > moves, 5, "work goes on")
        self.assertNotIn("9026", self.alarm_codes())

    def test_unexpected_result_is_ignored(self):
        self.eng.on_ats_event(1, AP.parse_message("TtoC_resultPass"))
        self.eng.wait_processed()
        self.assertEqual(self.fx(1)["total"], 0)
        self.assertEqual([p for _, k, p in self.box.pending(1000) if k == "result"], [])


class AlarmTests(EngineCase):
    def test_consecutive_ng_alarm_switches_the_box_off_and_re_enabling_clears_it(self):
        self.start()
        end = time.time() + 15
        while "9011" not in self.alarm_codes() and time.time() < end:
            self.answer_tests(lambda cell, attempt: "NG")
            time.sleep(0.02)
        self.assertIn("9011", self.alarm_codes())
        off = [n for n, f in self.fixtures().items() if not f["enabled"]]
        self.assertTrue(off)                                                  # consecutive_ng.stop_fixture
        self.eng.set_enabled(off[0], True)
        self.eng.wait_processed()
        self.assertFalse(any(a["key"] == "ng_%d" % off[0] for a in self.errors.active()))
        kinds = [p["error_code"] for _, k, p in self.box.pending(1000) if k == "error"]
        self.assertIn("9011", kinds)                                          # the interval row is written when it ends

    def test_robot_failure_halts_and_needs_acknowledge(self):
        self.robot.fail_on = "move"
        self.start()
        wait_until(lambda: self.eng.run_state == E.RUN_FAULT, 5, "FAULT")
        self.assertIn("9201", self.alarm_codes())
        self.assertIn("simulated move failure", self.eng.snapshot()["fault_text"])
        self.eng.start_run()                                                  # refused while faulted
        self.eng.wait_processed()
        self.assertEqual(self.eng.run_state, E.RUN_FAULT)
        self.robot.fail_on = None
        self.eng.acknowledge_fault()
        self.eng.wait_processed()
        self.assertEqual(self.eng.run_state, E.PAUSED)
        self.assertEqual(self.robot.fault_cleared, 1)
        self.assertNotIn("9201", self.alarm_codes())
        self.eng.reset_flow()
        self.eng.start_run()
        wait_until(lambda: all_testing(self), 8, "recovered")

    def test_ats_disconnect_raises_and_clears_9012(self):
        self.eng.on_ats_connection(1, False)
        self.eng.wait_processed()
        self.assertIn("9012", self.alarm_codes())
        self.assertEqual(self.fx(1)["state"], E.OFFLINE)
        self.eng.on_ats_connection(1, True)
        self.eng.wait_processed()
        self.assertNotIn("9012", self.alarm_codes())

    def test_cannot_start_without_robot_link(self):
        self.robot.connected = False
        self.eng.start_run()
        self.eng.wait_processed()
        self.assertIn("9100", self.alarm_codes())
        self.assertEqual(self.eng.run_state, E.STOPPED)

    def test_fixture_error_alarm(self):
        self.eng.on_ats_event(1, AP.parse_message("fix_error"))
        self.eng.wait_processed()
        self.assertIn("9013", self.alarm_codes())


class TimeoutTests(EngineCase):
    overrides = {"engine": {"test_timeout_s": 0.3}}

    def test_test_timeout_alarm_cleared_by_result(self):
        self.start()
        wait_until(lambda: all_testing(self), 8, "every box testing")
        wait_until(lambda: "9010" in self.alarm_codes(), 3, "9010")
        self.answer_tests(lambda cell, attempt: "PASS")
        wait_until(lambda: "9010" not in self.alarm_codes(), 3, "9010 cleared")


class StopTests(EngineCase):
    def test_stop_waits_for_the_running_stage_before_disarming(self):
        self.robot.delay = 0.05
        self.start()
        wait_until(lambda: self.eng.snapshot()["current_job"] is not None, 5, "job running")
        self.eng.stop_run()
        wait_until(lambda: self.eng.snapshot()["current_job"] is None, 8, "job finished")
        wait_until(lambda: not self.robot.armed, 3, "disarmed after the job")
        self.assertEqual(self.eng.run_state, E.STOPPED)                      # no fault from a mid-stage disarm

    def test_stop_when_idle_disarms_immediately(self):
        self.eng.start_run()
        wait_until(lambda: self.robot.armed, 3, "armed")
        self.eng.stop_run()
        wait_until(lambda: not self.robot.armed, 3, "disarmed")


class ProgramStateTests(EngineCase):
    """UO[3] PROGRUN: nothing may be written to R[1] while the robot program is off."""

    def setUp(self):
        super().setUp()
        self.robot.program_state = True
        self.robot.refresh_program_state = lambda: self.robot.program_state

    def keys(self):
        return [a["key"] for a in self.errors.active()]

    def test_snapshot_tells_whether_the_program_runs(self):
        self.assertIs(self.eng.snapshot()["program_running"], True)
        self.robot.program_state = False
        self.assertIs(self.eng.snapshot()["program_running"], False)
        self.robot.program_state = None
        self.assertIsNone(self.eng.snapshot()["program_running"])

    def test_the_run_does_not_start_while_the_program_is_off(self):
        self.robot.program_state = False
        self.start()
        self.assertEqual(self.eng.run_state, E.STOPPED)
        self.assertFalse(self.robot.armed)
        self.assertIn("robot_program", self.keys())

    def test_the_run_does_not_start_when_uo3_cannot_be_read(self):
        self.robot.program_state = None
        self.start()
        self.assertEqual(self.eng.run_state, E.STOPPED)
        self.assertFalse(self.robot.armed)

    def test_start_is_clean_once_the_program_runs(self):
        self.robot.program_state = False
        self.start()
        self.assertIn("robot_program", self.keys())
        self.robot.program_state = True
        self.eng.start_run()
        self.eng.wait_processed()
        self.assertEqual(self.eng.run_state, E.RUNNING)
        self.assertNotIn("robot_program", self.keys())

    def test_no_job_is_dispatched_while_the_program_is_off(self):
        self.robot.refresh_program_state = lambda: True                      # the fresh read at Start says "running" ...
        self.robot.program_state = False                                     # ... but the monitored state says "off"
        self.start()
        self.assertEqual(self.eng.run_state, E.RUNNING)
        time.sleep(0.5)                                                      # shorter than the 1 s before the engine pauses itself
        self.assertEqual(self.robot.moves, [])                               # nothing was written to the robot
        self.robot.program_state = True
        wait_until(lambda: len(self.robot.moves) > 0, 5, "work after the program is back")

    def test_a_program_that_stops_during_the_run_pauses_it_with_an_alarm(self):
        self.eng.start_run()
        self.eng.wait_processed()
        self.robot.program_state = False
        wait_until(lambda: self.eng.run_state == E.PAUSED, 4, "PAUSED")
        self.assertIn("robot_program", self.keys())
        self.robot.program_state = True
        wait_until(lambda: "robot_program" not in self.keys(), 3, "alarm cleared")

    def test_a_short_glitch_does_not_stop_the_cell(self):
        self.eng.start_run()
        self.eng.wait_processed()
        self.robot.program_state = False
        time.sleep(0.4)                                                      # shorter than the 1 s the engine waits
        self.robot.program_state = True
        time.sleep(1.2)
        self.assertEqual(self.eng.run_state, E.RUNNING)


if __name__ == "__main__":
    unittest.main()
