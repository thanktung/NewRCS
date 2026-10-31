"""The engine in the "tray" flow: planner + stages + commits with a fake robot, fake heads (I/O), a fake scanner and fake ATS."""
import copy
import time
import unittest

from rcs2.config import DEFAULTS
from rcs2.core import dut as D
from rcs2.core import engine as E
from rcs2.core import geometry as G
from rcs2.devices.end_effector import EndEffector
from rcs2.devices.heads import HeadBank
from rcs2.reporting.data_sink import DataSink, ErrorTracker
from rcs2.reporting.outbox import Outbox
from tests.devices.test_end_effector import FakeIo
from tests.support.engine import (BOXES, HEADS, TRAYS, TRAYS_OUT, EngineCase, FlowRobot, pt, taught_points,  # noqa: F401
                                  wait_until)


class RunTests(EngineCase):
    def test_all_products_pass_and_fill_the_input_tray_from_the_first_cell(self):
        self.start()
        self.run_all(lambda cell, attempt: "PASS")
        st = self.flow_snap()["stats"]
        self.assertEqual((st["passed"], st["ng"], st["fresh"], st["in_flight"]), (8, 0, 0, 0))
        self.assertEqual(self.book().cells, [D.PASS] * 8)                           # every product is back, in cells 0..7 in order
        for d in self.book().duts.values():
            self.assertEqual(d.location[0], D.TRAY)
        self.assertEqual(sum(f["total"] for f in self.fixtures().values()), 8)
        self.assertEqual(self.errors.active(), [])
        self.assertTrue(all(h["dut"] is None for h in self.flow_snap()["heads"]))

    def test_a_failure_is_tested_in_other_boxes_and_the_third_failure_goes_to_the_ng_tray(self):
        self.start()
        self.run_all(lambda cell, attempt: "NG" if cell == 3 else "PASS")
        st = self.flow_snap()["stats"]
        self.assertEqual((st["passed"], st["ng"], st["tests"]), (7, 1, 7 + 3))
        bad = next(d for d in self.book().duts.values() if d.origin == 3)
        self.assertEqual(len({a[0] for a in bad.attempts}), 3)                     # three different boxes
        self.assertEqual(bad.location, (D.NG_TRAY, 0))
        self.assertEqual(self.book().ng_used, 1)
        self.assertEqual(self.book().cells.count(D.EMPTY), 1)                         # the cell of the NG product stays empty
        self.assertEqual(self.book().cells.count(D.PASS), 7)

    def test_a_retest_that_passes_ends_in_the_input_tray(self):
        self.start()
        self.run_all(lambda cell, attempt: "NG" if (cell == 5 and attempt == 1) else "PASS")
        d = next(d for d in self.book().duts.values() if d.origin == 5)
        self.assertEqual((d.final, d.tests_made, d.location[0]), ("PASS", 2, D.TRAY))
        self.assertEqual(self.book().cells, [D.PASS] * 8)

    def test_every_result_is_reported_with_its_own_test(self):
        self.start()
        self.run_all(lambda cell, attempt: "NG" if cell == 0 else "PASS")
        results = [p["result"] for _, k, p in self.box.pending(1000) if k == "result"]
        self.assertEqual(results.count("PASS"), 7)
        self.assertEqual(results.count("NG"), 3)                                    # the three tests of the failing product

    def test_poses_use_all_six_values_and_the_offset_of_the_head(self):
        self.start()
        wait_until(lambda: self.flow_snap()["stats"]["in_flight"] >= HEADS, 5, "first pick-up")
        lay = G.Layout(self.points, TRAYS, list(range(1, BOXES + 1)), HEADS, scanner=True)
        sent = [m[0] for m in self.robot.moves]
        for head, cell in ((1, 0), (2, 1), (3, 2), (4, 3)):
            want = lay.pick_pose(head, cell)["xyzwpr"]
            self.assertTrue(any(G.pose_close(m, want, 1e-4, 1e-4) for m in sent), (head, cell, want))
        # head 2 is 22 mm "behind" head 1: over cell (0,1) = x 110 it needs the robot at x 88
        self.assertTrue(any(G.pose_close(m, [110 - 22, 200, 50, 180, 0, 0], 1e-4, 1e-4) for m in sent))
        self.assertTrue(all(m[1] == 5 for m in self.robot.moves))                    # flow.override
        self.assertTrue(all(m[2] == [0, 0, 1, 1, 0, 0, 0] and m[3] == 1 and m[4] == 1 for m in self.robot.moves))

    def test_barcodes_follow_their_products_to_the_ats(self):
        self.start()
        wait_until(lambda: all(f["state"] == E.TESTING for f in self.fixtures().values()), 8, "all boxes testing")
        sns = {f["number"]: f["sn"] for f in self.fixtures().values()}
        self.assertEqual(sorted(sns.values()), ["SN0001", "SN0002", "SN0003", "SN0004"])
        for n, sn in sns.items():
            self.assertIn("barcode:%s" % sn, self.ats[n].calls)
            self.assertLess(self.ats[n].calls.index("barcode:%s" % sn), self.ats[n].calls.index("place_dut_ok"))

    def test_a_product_with_a_chosen_cell_keeps_that_cell_in_the_books(self):
        self.start()
        wait_until(lambda: all(f["state"] == E.TESTING for f in self.fixtures().values()), 8, "all boxes testing")
        cells = sorted(f["cell"] for f in self.fixtures().values())
        self.assertEqual(cells, [0, 1, 2, 3])


class SafetyTests(EngineCase):
    def test_start_is_refused_while_taught_points_are_missing(self):
        del self.points["fixture_2"], self.points["head_3_at_O"]
        self.start()
        wait_until(lambda: any(a["code"] == "9205" for a in self.errors.active()), 3, "alarm 9205")
        self.assertEqual(self.eng.run_state, E.STOPPED)
        self.assertIn("fixture_2", self.errors.active()[0]["message"])
        self.assertEqual(self.robot.moves, [])
        self.points["fixture_2"], self.points["head_3_at_O"] = pt(200, 500, 200), pt(434, 100, 300)
        self.eng.start_run()
        wait_until(lambda: self.eng.run_state == E.RUNNING, 3, "running")
        self.assertFalse(any(a["code"] == "9205" for a in self.errors.active()))

    def test_nothing_is_sent_while_the_robot_program_is_off(self):
        self.robot.program_state = False
        self.robot.refresh_program_state = lambda: False
        self.start()
        time.sleep(0.5)
        self.assertEqual(self.robot.moves, [])
        self.assertTrue(any(a["key"] == "robot_program" for a in self.errors.active()))

    def test_a_head_that_does_not_hold_stops_the_run_with_alarm_9203(self):
        self.io.products.discard(2)                                                # head 2 never gets a pressure signal
        self.start()
        wait_until(lambda: self.eng.run_state == E.RUN_FAULT, 8, "fault")
        self.assertTrue(any(a["code"] == "9203" for a in self.errors.active()))
        st = self.flow_snap()
        self.assertEqual(st["stats"]["in_flight"], 1)                               # head 1 did pick up its product
        self.assertEqual([h["dut"] is not None for h in st["heads"]], [True, False, False, False])

    def test_a_scan_that_cannot_be_read_stops_the_run_before_anything_is_picked(self):
        self.scanner.fail = True
        self.start()
        wait_until(lambda: self.eng.run_state == E.RUN_FAULT, 8, "fault")
        self.assertTrue(any(a["code"] == "9202" for a in self.errors.active()))
        self.assertEqual(self.flow_snap()["stats"]["in_flight"], 0)

    def test_stopping_takes_effect_between_stages_and_the_books_stay_exact(self):
        self.robot.delay = 0.02
        self.start()
        wait_until(lambda: self.flow_snap()["stats"]["in_flight"] >= 1, 5, "first product picked")
        self.eng.stop_run()
        wait_until(lambda: self.eng.snapshot()["current_job"] is None, 8, "job ended")
        self.assertEqual(self.eng.run_state, E.STOPPED)
        st = self.flow_snap()
        on_heads = [h for h in st["heads"] if h["dut"] is not None]
        in_boxes = [f for f in self.fixtures().values() if f["dut"] is not None]
        self.assertEqual(len(on_heads) + len(in_boxes), st["stats"]["in_flight"])
        moves = len(self.robot.moves)
        time.sleep(0.4)
        self.assertEqual(len(self.robot.moves), moves)                                # nothing new is sent after the stop
        self.assertLess(st["stats"]["in_flight"], 8)

    def test_reset_flow_forgets_every_product_and_refills_the_trays(self):
        self.start()
        wait_until(lambda: self.flow_snap()["stats"]["in_flight"] >= 1, 5, "first product picked")
        self.eng.stop_run()
        wait_until(lambda: self.eng.snapshot()["current_job"] is None, 8, "job ended")
        self.eng.reset_tray("input")                                              # refused: products are still out
        self.eng.wait_processed()
        self.assertGreater(self.flow_snap()["stats"]["in_flight"], 0)
        self.eng.reset_flow()
        self.eng.wait_processed()
        st = self.flow_snap()["stats"]
        self.assertEqual((st["in_flight"], st["fresh"]), (0, 8))
        self.assertTrue(all(f["dut"] is None for f in self.fixtures().values()))

    def test_a_disabled_box_gets_its_tested_product_back_but_no_new_one(self):
        self.start()
        wait_until(lambda: all(f["state"] == E.TESTING for f in self.fixtures().values()), 8, "all boxes testing")
        self.eng.set_enabled(1, False)
        self.answer_tests(lambda cell, attempt: "PASS")
        wait_until(lambda: self.fixtures()[1]["dut"] is None, 8, "box 1 emptied")
        time.sleep(0.5)
        self.assertIsNone(self.fixtures()[1]["dut"])                                # nobody was put into the disabled box


class LaserCheckTests(EngineCase):
    """After a product is PUT DOWN the laser looks at 2 measuring points; a tilted product (not GO) stops the run."""
    laser = True
    flow = {"laser_check": {"enabled": True, "places": ["box", "input"], "offsets": [[-15, 0, 0], [15, 0, 0]], "timeout_s": 0.5}}

    def test_two_points_are_checked_after_every_put_down_in_a_box_and_in_the_input_tray(self):
        self.start()
        self.run_all(lambda cell, attempt: "PASS")
        self.assertEqual(len(self.laser_tool.calls), 2 * (8 + 8))                      # 8 products x (box + input tray) x 2 points
        lay = G.Layout(self.points, TRAYS, list(range(1, BOXES + 1)), HEADS, scanner=True, laser=True)
        for n in range(1, BOXES + 1):
            for want in lay.laser_poses("box", n, [(-15, 0, 0), (15, 0, 0)]):
                self.assertTrue(any(G.pose_close(c, want["xyzwpr"], 1e-4, 1e-4) for c in self.laser_tool.calls), (n, want))
        for want in lay.laser_poses("input", 0, [(-15, 0, 0), (15, 0, 0)]):
            self.assertTrue(any(G.pose_close(c, want["xyzwpr"], 1e-4, 1e-4) for c in self.laser_tool.calls), want)

    def test_the_two_measuring_points_are_the_offsets_apart(self):
        self.start()
        wait_until(lambda: len(self.laser_tool.calls) >= 2, 10, "first laser check")
        first, second = self.laser_tool.calls[:2]
        self.assertAlmostEqual(second[0] - first[0], 30.0, places=3)                    # offsets -15 / +15 mm along the x of the place
        self.assertAlmostEqual(second[1], first[1], places=3)

    def test_a_tilted_product_stops_the_run_and_the_test_is_not_started(self):
        self.laser_tool.fail = True
        self.start()
        wait_until(lambda: self.eng.run_state == E.RUN_FAULT, 10, "fault")
        codes = [a["code"] for a in self.errors.active()]
        self.assertIn("9204", codes)
        self.assertIn("laser check", [a["message"] for a in self.errors.active() if a["code"] == "9204"][0])      # names the stage
        placed = [n for n, f in self.fixtures().items() if f["dut"] is not None]
        self.assertEqual(len(placed), 1)                                                # the product is in the box ...
        self.assertNotIn("place_dut_ok", self.ats[placed[0]].calls)                     # ... but its test was never started
        self.assertNotIn("barcode:SN0001", self.ats[placed[0]].calls)

    def test_only_the_chosen_places_are_checked(self):
        self.flow = dict(self.flow, laser_check=dict(self.flow["laser_check"], places=["box"]))
        self.tearDown()
        self.setUp()
        self.start()
        self.run_all(lambda cell, attempt: "PASS")
        self.assertEqual(len(self.laser_tool.calls), 2 * 8)                             # boxes only, not the input tray


class LaserNeedsALaser(unittest.TestCase):
    def build(self, laser):
        from rcs2.core.flow import FlowError
        cfg = copy.deepcopy(DEFAULTS)
        cfg["ats"]["fixtures"] = {"1": {"host": "h", "port": 1, "station": "S"}, "2": {"host": "h", "port": 2, "station": "S"}}
        cfg["flow"].update({"laser_check": {"enabled": True}})
        io = FakeIo(products=range(1, 3))
        bank = HeadBank.from_config({"enabled": True, "units": [{"vacuum": "RDO[%d]" % n, "cylinder": "RDO[%d]" % (8 + n), "pressure": "RDI[%d]" % n}
                                                                   for n in (1, 2)]}, io)
        sink = DataSink(Outbox(":memory:"), None)
        self.assertEqual(FlowError.__name__, "FlowError")
        return E.Engine(cfg, FlowRobot(), {}, sink, ErrorTracker(sink, "M"), taught_points(), ee=EndEffector(bank, None, laser),
                        trays=TRAYS)

    def test_the_program_refuses_to_start_without_a_laser(self):
        from rcs2.core.flow import FlowError
        with self.assertRaises(FlowError) as cm:
            self.build(None)
        self.assertIn("laser", str(cm.exception))

    def test_nor_with_a_laser_that_is_switched_off(self):
        from rcs2.core.flow import FlowError

        class Off:
            enabled = False
        with self.assertRaises(FlowError):
            self.build(Off())


class DropTests(EngineCase):
    """A head that loses its product on the way: the carry check before the next movement finds it."""

    def drop_head1_at_move(self, number):
        self.robot.hook = lambda n: self.io.products.discard(1) if n == number else None

    def test_a_dropped_product_stops_the_run_and_the_robot(self):
        dropped = []
        self.eng.on_drop = dropped.append
        self.drop_head1_at_move(3)                                                      # head 1 has picked (move 2); it loses the product in move 3
        self.start()
        wait_until(lambda: self.eng.run_state == E.RUN_FAULT, 10, "fault")
        active = {a["code"]: a["message"] for a in self.errors.active()}
        self.assertIn("9208", active)
        self.assertIn("đầu 1", active["9208"])
        self.assertIn("carry check", active["9208"])
        self.assertEqual(len(dropped), 1)                                               # the runtime is told to stop the robot program
        wait_until(lambda: self.eng.snapshot()["current_job"] is None, 5, "job ended")
        moves = len(self.robot.moves)
        time.sleep(0.4)
        self.assertEqual(len(self.robot.moves), moves)                                  # nothing is sent after the fault

    def test_the_robot_is_not_stopped_when_that_is_switched_off(self):
        self.eng.flow_settings.stop_robot_on_drop = False
        dropped = []
        self.eng.on_drop = dropped.append
        self.drop_head1_at_move(3)
        self.start()
        wait_until(lambda: self.eng.run_state == E.RUN_FAULT, 10, "fault")
        self.assertIn("9208", [a["code"] for a in self.errors.active()])
        self.assertEqual(dropped, [])

    def test_a_product_that_is_held_does_not_raise_anything(self):
        self.start()
        wait_until(lambda: self.flow_snap()["stats"]["in_flight"] >= HEADS, 8, "all heads loaded")
        self.assertNotIn("9208", [a["code"] for a in self.errors.active()])
        self.assertEqual(self.eng.run_state, E.RUNNING)


class TrayAlarmTests(EngineCase):
    def codes(self):
        return {a["code"] for a in self.errors.active()}

    def test_the_input_tray_must_be_changed_when_everything_is_done(self):
        self.start()
        self.run_all(lambda cell, attempt: "PASS")
        wait_until(lambda: "9206" in self.codes(), 5, "alarm 9206")
        self.assertEqual(self.eng.run_state, E.RUNNING)                                  # it keeps waiting for the new tray
        self.eng.reset_tray("input")                                                     # the operator put a new tray and pressed "Đã nạp đầy"
        self.eng.wait_processed()
        self.assertNotIn("9206", self.codes())
        self.assertNotIn(D.PASS, self.book().cells)                                      # a new tray: no passed products in it
        wait_until(lambda: self.flow_snap()["stats"]["in_flight"] > 0, 10, "work goes on with the new tray")

    def test_a_new_input_tray_keeps_the_count_of_the_ng_tray(self):
        self.start()
        self.run_all(lambda cell, attempt: "NG" if cell == 3 else "PASS")
        self.assertEqual(self.book().ng_used, 1)
        self.eng.reset_tray("input")
        self.eng.wait_processed()
        self.assertEqual(self.book().ng_used, 1)                                         # the NG tray was not touched

    def test_the_ng_tray_must_be_changed_when_it_is_full(self):
        self.start()
        self.run_all(lambda cell, attempt: "NG" if cell in (0, 1, 2, 3) else "PASS")      # 4 failed products fill the 1 x 4 NG tray
        wait_until(lambda: "9207" in self.codes(), 5, "alarm 9207")
        self.assertEqual(self.book().ng_used, 4)
        self.eng.reset_tray("ng")                                                        # the operator emptied it and pressed "Đã dọn"
        self.eng.wait_processed()
        self.assertNotIn("9207", self.codes())
        self.assertEqual(self.book().ng_used, 0)


class OutputTrayFlowTests(EngineCase):
    """The passed products go into output 1 (3 cells) and then output 2 (3 cells), never back into the input tray."""
    trays = TRAYS_OUT

    def codes(self):
        return {a["code"] for a in self.errors.active()}

    def pass_until(self, condition, timeout=25.0):
        """Act as the ATS (every test passes) until `condition()` holds."""
        end = time.time() + timeout
        while time.time() < end and not condition():
            self.answer_tests(lambda cell, attempt: "PASS")
            time.sleep(0.02)
        self.assertTrue(condition(), "condition not reached: %s, %s" % (self.book().out_used, self.logs[-3:]))

    def test_passed_products_fill_output_1_then_output_2_and_the_input_tray_gets_no_pass_cell(self):
        self.start()
        self.pass_until(lambda: self.book().out_used == [3, 3])
        self.assertNotIn(D.PASS, self.book().cells)
        trays = self.eng.snapshot()["trays"]
        self.assertEqual((trays["output1"]["done"], trays["output2"]["done"]), (3, 3))        # the counters of the screen follow the books
        self.assertEqual(self.flow_snap()["out_used"], [3, 3])
        placed = [d.location for d in self.book().duts.values() if d.location[0] == D.OUT_TRAY]
        self.assertEqual(sorted(p[1] for p in placed), [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2)])

    def test_the_operator_is_told_when_every_output_tray_is_full_and_work_goes_on_after_it_is_emptied(self):
        self.start()
        self.pass_until(lambda: "9209" in self.codes())                                      # 6 of the 8 products are out, 2 wait on heads
        self.assertEqual(self.book().out_used, [3, 3])
        self.assertEqual(self.eng.run_state, E.RUNNING)                                      # it waits for the operator: no fault
        self.eng.reset_tray("output1")                                                       # the operator emptied output 1: "Đã dọn"
        self.eng.wait_processed()
        self.assertNotIn("9209", self.codes())
        self.assertEqual(self.book().out_used[1], 3)                                         # output 2 was not touched (output 1 may be refilling already)
        self.run_all(lambda cell, attempt: "PASS")                                           # the last 2 products go into the emptied output 1
        self.assertEqual(self.book().out_used, [2, 3])

    def test_the_resets_touch_only_what_they_name(self):
        flow = self.eng.flow
        flow.book.out_used, flow.book.ng_used = [2, 1], 3
        flow.reset("input")
        self.assertEqual((self.book().out_used, self.book().ng_used), ([2, 1], 3))           # a new input tray keeps the other trays
        flow.reset("output2")
        self.assertEqual(self.book().out_used, [2, 0])
        flow.reset("ng")
        self.assertEqual((self.book().out_used, self.book().ng_used), ([2, 0], 0))
        flow.reset("all")
        self.assertEqual(self.book().out_used, [0, 0])


if __name__ == "__main__":
    unittest.main()
