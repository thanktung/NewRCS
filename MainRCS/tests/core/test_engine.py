"""Engine tests with a fake robot and fake ATS clients (fast, deterministic)."""
import copy
import time
import unittest

from rcs2.ats import protocol as AP
from rcs2.config import DEFAULTS
from rcs2.core import engine as E
from rcs2.robot.client import RobotError
from rcs2.reporting.data_sink import DataSink, ErrorTracker
from rcs2.reporting.outbox import Outbox
from tests.support.engine import POINTS, SEQ, EngineCase, FakeAts, FakeRobot, wait_until  # noqa: F401


class CycleTests(EngineCase):
    def test_full_cycle_pass(self):
        self.start_and_ready(1)
        wait_until(lambda: self.fx(1)["state"] == E.TESTING, what="TESTING")
        self.assertEqual(self.robot.calls[:2], [("get", 0), ("put", 1)])
        self.assertEqual(self.ats[1].calls, ["place_dut_ok"])
        self.eng.on_ats_event(1, AP.parse_message("TtoC_resultPass"))
        wait_until(lambda: self.fx(1)["passed"] == 1 and self.fx(1)["state"] == E.TESTING, what="reload after unload")
        self.assertEqual(self.robot.calls[2:4], [("get", 1), ("put", 8)])         # unload_pass
        self.assertEqual(self.robot.calls[4:6], [("get", 0), ("put", 1)])         # next DUT loaded
        self.assertEqual(self.results(), ["PASS"])
        self.assertEqual(self.ats[1].calls, ["place_dut_ok", "place_dut_ok"])

    def test_ng_goes_to_ng_sequence_and_retest_falls_back(self):
        self.start_and_ready(1)
        wait_until(lambda: self.fx(1)["state"] == E.TESTING)
        self.eng.on_ats_event(1, AP.parse_message("TtoC_resultNG+VCC+4.2"))
        wait_until(lambda: self.fx(1)["ng"] == 1 and self.fx(1)["state"] == E.TESTING)
        self.assertIn(("put", 9), self.robot.calls)
        self.assertEqual(self.fx(1)["last_detail"], "VCC=4.2")
        self.eng.on_ats_event(1, AP.parse_message("TtoC_resultRetest+x"))
        wait_until(lambda: self.fx(1)["retest"] == 1 and self.fx(1)["state"] == E.TESTING)
        self.assertEqual(self.robot.calls.count(("put", 9)), 2)                   # no unload_retest -> NG bin
        self.assertEqual(self.results(), ["NG", "RETEST"])

    def test_yield_and_totals(self):
        self.start_and_ready(1)
        for text in ("TtoC_resultPass", "TtoC_resultPass", "TtoC_resultNG+a+b", "TtoC_resultPass"):
            wait_until(lambda: self.fx(1)["state"] == E.TESTING)
            before = self.fx(1)["total"]
            self.eng.on_ats_event(1, AP.parse_message(text))
            wait_until(lambda: self.fx(1)["total"] == before + 1 and self.fx(1)["state"] == E.TESTING)
        self.assertAlmostEqual(self.fx(1)["yield_pct"], 75.0)
        self.assertEqual(self.eng.snapshot()["totals"]["total"], 4)

    def test_nothing_runs_until_started(self):
        for n in self.ats:
            self.eng.on_ats_event(n, AP.parse_message("TtoC_resultWaitdut"))
        time.sleep(0.4)
        self.assertEqual(self.robot.calls, [])
        self.eng.start_run()
        wait_until(lambda: self.fx(1)["state"] == E.TESTING and self.fx(2)["state"] == E.TESTING)

    def test_disabled_fixture_is_not_loaded(self):
        self.eng.set_enabled(2, False)
        self.start_and_ready()
        wait_until(lambda: self.fx(1)["state"] == E.TESTING)
        time.sleep(0.3)
        self.assertEqual(self.fx(2)["state"], E.NO_USED)
        self.eng.set_enabled(2, True)
        wait_until(lambda: self.fx(2)["state"] == E.TESTING, what="fixture 2 loaded after enabling")

    def test_pause_stops_new_jobs(self):
        self.start_and_ready(1)
        wait_until(lambda: self.fx(1)["state"] == E.TESTING)
        self.eng.pause_run()
        wait_until(lambda: self.eng.snapshot()["run_state"] == E.PAUSED)
        self.assertTrue(any(a["code"] == "9026" for a in self.eng.snapshot()["alarms"]))
        n = len(self.robot.calls)
        self.eng.on_ats_event(1, AP.parse_message("TtoC_resultPass"))
        wait_until(lambda: self.fx(1)["state"] == E.RESULT)
        time.sleep(0.4)
        self.assertEqual(len(self.robot.calls), n)          # unload waits while paused
        self.eng.start_run()
        wait_until(lambda: self.fx(1)["state"] == E.TESTING)
        self.assertFalse(any(a["code"] == "9026" for a in self.eng.snapshot()["alarms"]))

    def test_unexpected_result_is_ignored(self):
        self.eng.on_ats_event(1, AP.parse_message("TtoC_resultPass"))
        time.sleep(0.3)
        self.assertEqual(self.fx(1)["total"], 0)
        self.assertEqual(self.results(), [])

    def test_unload_has_priority_over_load(self):
        self.eng._queue_job("load", 1)
        self.eng._queue_job("unload", 2, "PASS")
        self.assertEqual(self.eng._next_job().kind, "unload")


class AlarmTests(EngineCase):
    def test_consecutive_ng_alarm_stops_fixture_but_dut_is_unloaded(self):
        self.start_and_ready(1)
        for i in range(3):
            wait_until(lambda: self.fx(1)["state"] == E.TESTING, what="testing %d" % i)
            self.eng.on_ats_event(1, AP.parse_message("TtoC_resultNG+a+b"))
            wait_until(lambda: self.fx(1)["ng"] == i + 1)
        wait_until(lambda: self.fx(1)["dut_inside"] is False and self.fx(1)["state"] == E.NO_USED, what="unloaded and stopped")
        self.assertEqual(self.robot.calls.count(("put", 9)), 3)      # third NG DUT WAS taken out (old RCS left it in)
        alarms = self.eng.snapshot()["alarms"]
        self.assertTrue(any(a["code"] == "9011" for a in alarms))
        self.assertEqual(self.fx(1)["consec_ng"], 0)
        self.eng.set_enabled(1, True)                                 # operator re-enables: alarm clears
        wait_until(lambda: not any(a["code"] == "9011" for a in self.eng.snapshot()["alarms"]))
        kinds = [(k, p["error_code"]) for _, k, p in self.box.pending(1000) if k == "error"]
        self.assertIn(("error", "9011"), kinds)                       # interval row written when it ended

    def test_pass_resets_consecutive_counter(self):
        self.start_and_ready(1)
        for text in ("TtoC_resultNG+a+b", "TtoC_resultNG+a+b", "TtoC_resultPass", "TtoC_resultNG+a+b", "TtoC_resultNG+a+b"):
            wait_until(lambda: self.fx(1)["state"] == E.TESTING)
            before = self.fx(1)["total"]
            self.eng.on_ats_event(1, AP.parse_message(text))
            wait_until(lambda: self.fx(1)["total"] == before + 1 and self.fx(1)["state"] == E.TESTING)
        self.assertEqual(self.fx(1)["consec_ng"], 2)
        self.assertFalse(any(a["code"] == "9011" for a in self.eng.snapshot()["alarms"]))

    def test_robot_failure_halts_and_needs_acknowledge(self):
        self.robot.fail_on = "put"
        self.start_and_ready(1)
        wait_until(lambda: self.eng.snapshot()["run_state"] == E.RUN_FAULT, what="FAULT")
        snap = self.eng.snapshot()
        self.assertEqual(self.fx(1)["state"], E.FAULT)
        self.assertTrue(any(a["code"] == "9201" for a in snap["alarms"]))
        self.assertIn("simulated put failure", snap["fault_text"])
        self.eng.start_run()                                       # refused while faulted
        time.sleep(0.2)
        self.assertEqual(self.eng.snapshot()["run_state"], E.RUN_FAULT)
        self.robot.fail_on = None
        self.eng.acknowledge_fault()
        wait_until(lambda: self.eng.snapshot()["run_state"] == E.PAUSED)
        self.assertEqual(self.robot.fault_cleared, 1)
        self.assertFalse(any(a["code"] == "9201" for a in self.eng.snapshot()["alarms"]))
        self.eng.reset_fixture(1, dut_inside=False)
        self.eng.start_run()
        wait_until(lambda: self.fx(1)["state"] == E.TESTING, what="recovered")

    def test_ats_lost_after_load_is_fault(self):
        self.ats[1].connected = False
        self.start_and_ready(1)
        wait_until(lambda: self.fx(1)["state"] == E.FAULT)
        self.assertTrue(any(a["code"] == "9012" for a in self.eng.snapshot()["alarms"]))

    def test_ats_disconnect_raises_and_clears_9012(self):
        self.eng.on_ats_connection(1, False)
        wait_until(lambda: any(a["code"] == "9012" for a in self.eng.snapshot()["alarms"]))
        self.assertEqual(self.fx(1)["state"], E.OFFLINE)
        self.eng.on_ats_connection(1, True)
        wait_until(lambda: not any(a["code"] == "9012" for a in self.eng.snapshot()["alarms"]))

    def test_cannot_start_without_robot_link(self):
        self.robot.connected = False
        self.eng.start_run()
        wait_until(lambda: any(a["code"] == "9100" for a in self.eng.snapshot()["alarms"]))
        self.assertEqual(self.eng.snapshot()["run_state"], E.STOPPED)

    def test_fixture_error_alarm(self):
        self.eng.on_ats_event(1, AP.parse_message("fix_error"))
        wait_until(lambda: any(a["code"] == "9013" for a in self.eng.snapshot()["alarms"]))


class TimeoutTests(EngineCase):
    overrides = {"engine": {"test_timeout_s": 0.3}}

    def test_test_timeout_alarm_cleared_by_result(self):
        self.start_and_ready(1)
        wait_until(lambda: self.fx(1)["state"] == E.TESTING)
        wait_until(lambda: any(a["code"] == "9010" for a in self.eng.snapshot()["alarms"]), what="9010")
        self.eng.on_ats_event(1, AP.parse_message("TtoC_resultPass"))
        wait_until(lambda: not any(a["code"] == "9010" for a in self.eng.snapshot()["alarms"]))


class StopTests(EngineCase):
    def test_stop_waits_for_the_running_sequence_before_disarming(self):
        self.robot.delay = 0.15
        self.start_and_ready(1)
        wait_until(lambda: self.eng.snapshot()["current_job"] is not None, what="job running")
        self.eng.stop_run()
        wait_until(lambda: self.eng.snapshot()["current_job"] is None, what="job finished")
        wait_until(lambda: not self.robot.armed, what="disarmed after the job")
        self.assertEqual(self.eng.snapshot()["run_state"], E.STOPPED)    # no fault from a mid-sequence disarm
        self.assertEqual(self.robot.calls[:2], [("get", 0), ("put", 1)])  # the sequence completed

    def test_stop_when_idle_disarms_immediately(self):
        self.eng.start_run()
        wait_until(lambda: self.robot.armed)
        self.eng.stop_run()
        wait_until(lambda: not self.robot.armed)


class ResetTests(EngineCase):
    def test_reset_with_dut_inside_unloads_to_ng(self):
        self.eng.reset_fixture(1, dut_inside=True)
        self.eng.start_run()
        wait_until(lambda: ("put", 9) in self.robot.calls, what="manual unload to NG bin")


class SequenceRequiredTests(unittest.TestCase):
    def test_missing_required_sequence(self):
        cfg = copy.deepcopy(DEFAULTS)
        sink = DataSink(Outbox(":memory:"), None)
        with self.assertRaises(Exception):
            E.Engine(cfg, FakeRobot(), {}, sink, ErrorTracker(sink), {"load": []}, {})


if __name__ == "__main__":
    unittest.main()
