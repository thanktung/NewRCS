import json
import tempfile
import time
import unittest
from pathlib import Path

from rcs.clients.errors import (RobotCommandError, RobotConnectionError,
                                RobotTimeout)
from rcs.core.policies import FifoPriority
from rcs.core.scheduler import ControlError, Scheduler
from rcs.models import (BoardState, BoxRecord, BoxState, SystemState as S)
from rcs.persistence import StateStore
from rcs.protocol import commands as C
from rcs.traceability import ListRecorder
from tests.fakes import (FakeFactory, FakeRobot, all_board_ids, make_cfg,
                         wait_until)


class Base(unittest.TestCase):
    def build(self, cfg_kw=None, robot=None, **box_kw):
        self.robot = robot or FakeRobot()
        self.factory = FakeFactory(self.robot, **box_kw)
        self.rec = ListRecorder()
        self.sched = Scheduler(make_cfg(**(cfg_kw or {})), self.factory,
                               recorder=self.rec)
        self.addCleanup(self.sched.emergency_stop)
        return self.sched

    def state(self):
        return self.sched.sm.state

    def assertNoDuplicateBoards(self):
        ids = all_board_ids(self.sched)
        self.assertEqual(len(ids), len(set(ids)), "a board exists twice")


class FlowTests(Base):
    def test_normal_run_makes_progress_and_keeps_boards_unique(self):
        s = self.build()
        s.start()
        self.assertTrue(wait_until(lambda: s.stats["pass"] >= 12), s.stats)
        s.pause()
        self.assertTrue(wait_until(lambda: self.state() == S.PAUSED))
        self.assertNoDuplicateBoards()
        self.assertEqual(len(self.rec.rows), sum(r.tested for r in s.boxes))

    def test_tray_full_does_not_deadlock(self):
        """Regression: PASS board waiting on a head because tray 1 is full used
        to block CHANGE forever (old _should_change required no tested heads)."""
        s = self.build()
        s.start()
        self.assertTrue(wait_until(lambda: s.stats["change"] >= 3, timeout=10),
                        f"stalled: {s.stats} state={self.state()}")
        self.assertEqual(self.state(), S.RUNNING)

    def test_origin_policy_returns_boards_to_their_slot(self):
        s = self.build({"place_policy": "origin"})
        s.start()
        self.assertTrue(wait_until(lambda: s.stats["change"] >= 2, timeout=10),
                        f"stalled: {s.stats}")
        s.pause()
        self.assertTrue(wait_until(lambda: self.state() == S.PAUSED))
        for tray in (s.tray1, s.tray2):
            for idx, b in enumerate(tray.slots):
                if b is not None and b.origin is not None:
                    self.assertEqual(b.origin, (tray.tray_id, idx))
        self.assertNoDuplicateBoards()

    def test_pause_stops_robot_traffic_and_resume_continues(self):
        s = self.build()
        s.start()
        self.assertTrue(wait_until(lambda: len(self.robot.commands) > 5))
        s.pause()
        self.assertTrue(wait_until(lambda: self.state() == S.PAUSED))
        n = len(self.robot.commands)
        time.sleep(0.2)
        self.assertEqual(len(self.robot.commands), n)
        s.resume()
        self.assertTrue(wait_until(lambda: len(self.robot.commands) > n))

    def test_stop_and_start_again_does_not_leak_clients(self):
        s = self.build()
        s.start()
        self.assertTrue(wait_until(lambda: s.stats["loaded"] >= 2))
        first_boxes = dict(self.factory.boxes)
        s.stop()
        self.assertEqual(self.state(), S.STOPPED)
        self.assertFalse(self.robot.connected)
        self.assertTrue(all(not b.connected for b in first_boxes.values()))
        self.assertEqual(s._box_clients, {})
        s.start()
        self.assertTrue(wait_until(lambda: self.state() == S.RUNNING))
        self.assertEqual(len(s._box_clients), 4)          # not 8
        self.assertTrue(all(b.connected for b in self.factory.boxes.values()))

    def test_connect_failure_leaves_system_stopped(self):
        s = self.build()
        self.robot.connect_error = RobotConnectionError("down")
        with self.assertRaises(RobotConnectionError):
            s.start()
        self.assertEqual(self.state(), S.STOPPED)


class FaultTests(Base):
    def test_robot_timeout_goes_to_fault_without_applying_the_move(self):
        s = self.build()
        self.robot.fail_next(RobotTimeout("no DONE"))
        s.start()
        self.assertTrue(wait_until(lambda: self.state() == S.FAULT))
        self.assertIn("Physical state unknown", s.snapshot().fault)
        # the PICK never completed -> model must be unchanged
        self.assertTrue(all(h.board is None for h in s.gripper.heads))
        self.assertEqual(s.tray1.untested_count(), 4)
        n = len(self.robot.commands)
        time.sleep(0.15)
        self.assertEqual(len(self.robot.commands), n, "robot still commanded in FAULT")

    def test_must_acknowledge_before_resume(self):
        s = self.build()
        self.robot.fail_next(RobotTimeout("x"))
        s.start()
        self.assertTrue(wait_until(lambda: self.state() == S.FAULT))
        with self.assertRaises(ControlError):
            s.start()
        s.acknowledge_fault()
        self.assertEqual(self.state(), S.PAUSED)
        self.assertEqual(self.robot.reconnects, 1)
        s.start()
        self.assertTrue(wait_until(lambda: s.stats["loaded"] >= 2))

    def test_manual_edit_allowed_in_fault(self):
        s = self.build()
        self.robot.fail_next(RobotTimeout("x"))
        s.start()
        self.assertTrue(wait_until(lambda: self.state() == S.FAULT))
        self.assertTrue(wait_until(lambda: s.manual_edit_allowed()))
        self.assertTrue(s.manual_set_gripper(0, BoardState.PASS))
        self.assertEqual(s.gripper.heads[0].board.state, BoardState.PASS)

    def test_connection_lost_is_a_fault(self):
        s = self.build()
        self.robot.fail_next(RobotConnectionError("cable"))
        s.start()
        self.assertTrue(wait_until(lambda: self.state() == S.FAULT))

    def test_batch_err_applies_only_items_before_the_failing_one(self):
        s = self.build({"protocol": "v2", "batch_enabled": True, "batch_max_items": 3},
                       robot=FakeRobot(supports_batch=True))
        self.robot.fail_next(RobotCommandError("PICK", 1, "VAC_FAIL"))
        s.start()
        self.assertTrue(wait_until(lambda: self.state() == S.FAULT))
        self.assertIn("VAC_FAIL", s.snapshot().fault)
        self.assertIsNotNone(s.gripper.heads[0].board)       # item 0 done
        self.assertIsNone(s.gripper.heads[1].board)          # item 1 failed
        self.assertIsNone(s.tray1.slots[0])
        self.assertIsNotNone(s.tray1.slots[1])               # still on the tray
        self.assertNoDuplicateBoards()

    def test_no_part_is_recovered_not_fatal(self):
        s = self.build()
        self.robot.fail_next(RobotCommandError("PICK", 0, "NO_PART"))
        s.start()
        self.assertTrue(wait_until(lambda: "nopart_1_0" in s.snapshot().alerts))
        self.assertTrue(wait_until(lambda: s.stats["loaded"] >= 3))
        self.assertEqual(self.state(), S.RUNNING)

    def test_box_refusing_load_is_a_fault(self):
        s = self.build()
        s.connect()
        self.factory.boxes[1].refuse = "BUSY"
        s.start()
        self.assertTrue(wait_until(lambda: self.state() == S.FAULT))
        self.assertIn("BUSY", s.snapshot().fault)

    def test_box_timeout_on_load_is_a_fault(self):
        s = self.build()
        s.connect()
        self.factory.boxes[1].timeout_next = True
        s.start()
        self.assertTrue(wait_until(lambda: self.state() == S.FAULT))

    def test_heartbeat_alarm_is_a_fault(self):
        s = self.build({"protocol": "v2", "heartbeat_interval": 0.03})
        s.start()
        self.assertTrue(wait_until(lambda: s.stats["loaded"] >= 1))
        self.robot.status = "ALARM"
        self.assertTrue(wait_until(lambda: self.state() == S.FAULT))
        self.assertIn("ALARM", s.snapshot().fault)
        # operator cannot resume while the robot still reports ALARM
        with self.assertRaises(Exception):
            s.acknowledge_fault()
        self.assertEqual(self.state(), S.FAULT)


class RulesTests(Base):
    def test_disabled_box_and_head_are_never_used(self):
        s = self.build()
        s.set_box_enabled(2, False)
        s.set_head_enabled(0, False)
        s.start()
        self.assertTrue(wait_until(lambda: s.stats["pass"] >= 6))
        self.assertEqual(self.factory.boxes[2].loads, 0)
        for cmd in self.robot.commands:
            for it in cmd.items:
                if cmd.name in (C.PICK, C.PLACE):
                    self.assertNotEqual(it[2], 0, cmd)
                elif cmd.name in (C.LOAD, C.UNLOAD):
                    self.assertNotEqual(it[1], 0, cmd)
                    self.assertNotEqual(it[0], 2, cmd)

    def test_never_leaves_fewer_than_one_free_head(self):
        s = self.build()
        s.start()
        for _ in range(50):
            time.sleep(0.01)
            with s._lock:
                self.assertGreaterEqual(len(s.gripper.empty_heads()), 0)
        self.assertTrue(wait_until(lambda: s.stats["pass"] >= 6))

    def test_ng_tray_full_pauses_then_resumes_after_clear(self):
        s = self.build({"ng_tray_slots": 1}, results=["fail"] * 100)
        s.start()
        self.assertTrue(wait_until(lambda: "ng_full" in s.snapshot().alerts))
        self.assertTrue(wait_until(lambda: self.state() == S.PAUSED))
        self.assertEqual(s.snapshot().ng_count, 1)
        n_ng_cmds = sum(1 for it in self.robot.items_of(C.PLACE) if it[0] == 0)
        self.assertEqual(n_ng_cmds, 1, "robot was sent a slot beyond NG capacity")
        s.clear_ng_tray()
        self.assertNotIn("ng_full", s.snapshot().alerts)
        s.resume()
        self.assertTrue(wait_until(lambda: s.stats["ng"] >= 2))

    def test_retest_failed_board_in_another_box(self):
        s = self.build({"retest_ng": True})
        self.factory.box_overrides = {1: {"results": ["fail"]}}
        s.start()
        self.assertTrue(wait_until(lambda: len(self.rec.rows) >= 8))
        first_fail = next(r for r in self.rec.rows if r["result"] == "FAIL")
        self.assertEqual((first_fail["box_id"], first_fail["retest"]), (1, 0))
        again = [r for r in self.rec.rows
                 if r["board_id"] == first_fail["board_id"] and r["retest"] == 1]
        self.assertEqual(len(again), 1)
        self.assertNotEqual(again[0]["box_id"], 1)
        self.assertEqual(again[0]["result"], "PASS")
        self.assertEqual(s.stats["ng"], 0)

    def test_fail_streak_auto_disables_box(self):
        s = self.build({"box_fail_streak_limit": 2})
        self.factory.box_overrides = {1: {"results": ["fail"] * 50}}
        s.start()
        self.assertTrue(wait_until(lambda: not s.boxes[0].enabled))
        self.assertIn("box1_disabled", s.snapshot().alerts)
        s.set_box_enabled(1, True)
        self.assertNotIn("box1_disabled", s.snapshot().alerts)

    def test_watchdog_alerts_on_stuck_box(self):
        s = self.build({"ready_timeout_sec": 0.05})
        s.connect()
        self.factory.boxes[1].auto = False          # accepts the board, never tests
        s.start()
        self.assertTrue(wait_until(lambda: "box1_watchdog" in s.snapshot().alerts))

    def test_box_connection_loss_is_visible_and_recovers(self):
        s = self.build()
        s.start()
        self.assertTrue(wait_until(lambda: s.stats["loaded"] >= 1))
        box = self.factory.boxes[3]
        box.drop()
        self.assertTrue(wait_until(lambda: "box3_conn" in s.snapshot().alerts))
        self.assertEqual(s.boxes[2].state, BoxState.UNKNOWN)
        box.connected = True
        box._on_conn(3, True)
        box.push("empty")
        self.assertTrue(wait_until(lambda: "box3_conn" not in s.snapshot().alerts))

    def test_box_reporting_empty_while_software_holds_board_raises_alert(self):
        s = self.build()
        s.connect()
        s.boxes[0].board = s.new_manual_board(BoardState.UNTESTED)
        s.boxes[0].loaded_at = time.monotonic() - 100
        self.factory.boxes[1].push("empty")
        self.assertIsNone(s.boxes[0].board)
        self.assertIn("box1_lost", s.snapshot().alerts)


class ManualEditTests(Base):
    def test_edit_allowed_only_when_not_running(self):
        s = self.build()
        self.assertTrue(s.manual_edit_allowed())
        self.assertTrue(s.manual_set_tray_slot(1, 0, None))
        self.assertIsNone(s.tray1.slots[0])
        self.assertTrue(s.manual_set_box(2, BoardState.NG))
        self.assertEqual(s.boxes[1].state, BoxState.FAIL)
        self.assertTrue(s.manual_set_box(2, None))
        self.assertEqual(s.boxes[1].state, BoxState.EMPTY)
        s.start()
        self.assertTrue(wait_until(lambda: self.state() == S.RUNNING))
        self.assertFalse(s.manual_set_tray_slot(1, 1, None))
        self.assertFalse(s.manual_set_gripper(0, BoardState.PASS))

    def test_invalid_targets_rejected(self):
        s = self.build()
        self.assertFalse(s.manual_set_box(99, None))
        self.assertFalse(s.manual_set_gripper(99, None))
        self.assertFalse(s.manual_set_tray_slot(3, 0, None))
        self.assertFalse(s.manual_set_tray_slot(1, 99, None))


class PersistenceTests(Base):
    def test_export_restore_roundtrip_through_file(self):
        s = self.build()
        s.start()
        self.assertTrue(wait_until(lambda: s.stats["pass"] >= 5))
        s.pause()
        self.assertTrue(wait_until(lambda: self.state() == S.PAUSED))
        with tempfile.TemporaryDirectory() as d:
            store = StateStore(Path(d) / "state.json")
            store.save(s.export_state())
            data = store.load()
        s2 = Scheduler(make_cfg(), FakeFactory())
        s2.restore_state(data)
        self.assertEqual(s2.stats, s.stats)
        self.assertEqual([b and (b.board_id, b.state) for b in s2.tray1.slots],
                         [b and (b.board_id, b.state) for b in s.tray1.slots])
        self.assertEqual([r.tested for r in s2.boxes], [r.tested for r in s.boxes])
        self.assertEqual(s2._board_counter, s._board_counter)

    def test_restore_refused_while_running(self):
        s = self.build()
        s.start()
        self.assertTrue(wait_until(lambda: self.state() == S.RUNNING))
        with self.assertRaises(ControlError):
            s.restore_state(s.export_state())

    def test_store_is_atomic_and_tolerates_garbage(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "s.json"
            store = StateStore(p)
            self.assertIsNone(store.load())
            store.save({"a": 1})
            self.assertEqual(store.load()["a"], 1)
            self.assertEqual([x.name for x in Path(d).iterdir()], ["s.json"])
            p.write_text("{not json", encoding="utf-8")
            self.assertIsNone(store.load())
            p.write_text(json.dumps({"format": 1}), encoding="utf-8")
            self.assertIsNone(store.load())

    def test_state_saved_after_robot_operations(self):
        with tempfile.TemporaryDirectory() as d:
            store = StateStore(Path(d) / "s.json")
            s = self.build()
            s.store = store
            s.start()
            self.assertTrue(wait_until(lambda: s.stats["loaded"] >= 2))
            s.stop()                       # no writer thread left before the dir is removed
            data = store.load()
            self.assertIsNotNone(data)
            self.assertGreaterEqual(data["stats"]["loaded"], 1)


class PolicyTests(unittest.TestCase):
    def test_fifo_serves_longest_waiting_actionable_box_first(self):
        now = time.monotonic()
        boxes = []
        for i, (state, age) in enumerate([(BoxState.EMPTY, 1), (BoxState.PASS, 9),
                                          (BoxState.TESTING, 50), (BoxState.EMPTY, 5)], 1):
            r = BoxRecord(i, state=state)
            r.state_since = now - age
            boxes.append(r)
        boxes[3].enabled = True
        order = [r.box_id for r in FifoPriority().order(boxes)]
        self.assertEqual(order, [2, 4, 1])           # TESTING box not actionable

    def test_disabled_boxes_are_not_served(self):
        r = BoxRecord(1, state=BoxState.EMPTY)
        r.enabled = False
        self.assertEqual(FifoPriority().order([r]), [])


if __name__ == "__main__":
    unittest.main()

