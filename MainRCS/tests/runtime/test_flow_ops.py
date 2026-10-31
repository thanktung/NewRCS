"""Tray flow, operator side: what to teach, the check of the calibration, moves that use the same pose maths as a run."""
import json
import os

from rcs2.core import geometry as G
from rcs2.robot.client import RobotError
from tests.core.test_flow_engine import BOXES, HEADS, TRAYS, taught_points
from tests.simulator.test_sim_flow import SimFlowCase
from tests.simulator.test_sim_cell import wait_until


class FlowOpsTests(SimFlowCase):
    def setUp(self):
        super().setUp()
        wait_until(lambda: self.rt.bridge.connected, what="bridge link")
        wait_until(lambda: self.rt.bridge.program_state is True, what="robot program running")

    def test_groups_list_everything_to_teach_in_order(self):
        groups = {key: [n for n, _ in items] for key, _, items in self.rt.flow_groups()}
        self.assertEqual(groups["heads"], ["head_%d_at_O" % k for k in range(1, HEADS + 1)] + ["scanner_at_O"])
        self.assertEqual(groups["input"], ["input_O", "input_X", "input_Y"])
        self.assertEqual(groups["ng"], ["ng_O", "ng_X", "ng_Y"])
        self.assertEqual(groups["fixtures"], ["fixture_%d" % n for n in range(1, BOXES + 1)])
        self.assertTrue(all(self.rt.flow_taught().values()))

    def test_status_names_what_is_missing_or_wrong(self):
        self.assertEqual(self.rt.flow_status(), {"missing": [], "problem": "", "complete": True})
        del self.rt.points()["fixture_3"]
        st = self.rt.flow_status()
        self.assertEqual((st["missing"], st["complete"]), (["fixture_3"], False))
        self.assertFalse(self.rt.flow_taught()["fixture_3"])
        self.rt.points()["fixture_3"] = taught_points()["fixture_3"]
        self.rt.points()["input_X"] = dict(self.rt.points()["input_X"], uf=2)              # not taught in the same frame as O
        st = self.rt.flow_status()
        self.assertFalse(st["complete"])
        self.assertIn("uf", st["problem"])

    def test_cell_poses_have_six_values_and_follow_the_head_offset(self):
        p1 = self.rt.flow_cell_pose("input", 5, head=1)                    # cell 5 of 4 columns = row 1, col 1
        self.assertTrue(G.pose_close(p1["xyzwpr"], [110, 260, 50, 180, 0, 0]))
        self.assertEqual((p1["config"], p1["uf"], p1["ut"]), ([0, 0, 1, 1, 0, 0, 0], 1, 1))
        p3 = self.rt.flow_cell_pose("input", 5, head=3)                    # head 3 sits 44 mm behind head 1
        self.assertTrue(G.pose_close(p3["xyzwpr"], [110 - 44, 260, 50, 180, 0, 0]))
        pn = self.rt.flow_cell_pose("ng", 2, head=2)
        self.assertTrue(G.pose_close(pn["xyzwpr"], [320 - 22, 200, 50, 180, 0, 0]))
        offsets = self.rt.flow_head_offsets()
        self.assertEqual(sorted(k for k in offsets if isinstance(k, int)), list(range(1, HEADS + 1)))
        self.assertAlmostEqual(offsets[2][0], -22.0, places=3)

    def test_the_robot_really_goes_where_the_run_would_send_it(self):
        self.rt.flow_move_head_to_cell("input", 5, head=3)
        pos = self.rt.bridge.pos_read()["xyzwpr"]
        self.assertTrue(G.pose_close(pos, [110 - 44, 260, 50, 180, 0, 0], 1e-2, 1e-2), pos)
        self.rt.flow_move_head_to_point("fixture_2", head=4)
        pos = self.rt.bridge.pos_read()["xyzwpr"]
        self.assertTrue(G.pose_close(pos, [200 - 66, 500, 200, 180, 0, 0], 1e-2, 1e-2), pos)
        self.assertFalse(self.rt.bridge.last_status.get("armed"))                       # armed for that move only

    def test_what_is_not_taught_is_named(self):
        del self.rt.points()["head_3_at_O"], self.rt.points()["ng_Y"]
        with self.assertRaises(G.GeometryError) as cm:
            self.rt.flow_cell_pose("ng", 0, head=1)
        self.assertIn("ng_Y", str(cm.exception))
        with self.assertRaises(G.GeometryError) as cm:
            self.rt.flow_move_head_to_point("fixture_1", head=3)
        self.assertIn("head_3_at_O", str(cm.exception))

    def test_teaching_stores_all_six_values_and_the_config(self):
        self.rt.manual_move_to("fixture_1")
        point = self.rt.teach_point("head_7_at_O")
        self.assertEqual(len(point["xyzwpr"]), 6)
        self.assertTrue({"config", "uf", "ut"} <= set(point))
        saved = json.load(open(os.path.join(self.tmp.name, "sequences.json"), encoding="utf-8"))["points"]["head_7_at_O"]
        self.assertEqual(saved["xyzwpr"], point["xyzwpr"])
        self.assertTrue(G.pose_close(saved["xyzwpr"], taught_points()["fixture_1"]["xyzwpr"], 1e-2, 1e-2))
        self.assertIn("head_7_at_O", self.rt.points())

    def test_nothing_moves_while_the_robot_program_is_off_or_a_run_is_active(self):
        self.rt.robot_stop_program()
        wait_until(lambda: self.rt.bridge.program_state is False, what="program stopped")
        with self.assertRaises(RobotError) as cm:
            self.rt.flow_move_head_to_cell("input", 0)
        self.assertEqual(cm.exception.code, "PROGRAM_STOPPED")


class FlowLaserTests(SimFlowCase):
    """The tray flow with the IL-1000: the laser looks at 2 points of every product that is put down in a box / in the input tray."""
    laser = True

    def test_the_laser_point_is_taught_like_the_scanner(self):
        groups = {key: [n for n, _ in items] for key, _, items in self.rt.flow_groups()}
        self.assertEqual(groups["heads"][-2:], ["scanner_at_O", "laser_at_O"])
        self.assertIn(G.LASER, self.rt.flow_head_offsets())

    def test_a_whole_run_checks_the_laser_twice_per_put_down(self):
        calls = []
        laser = self.rt.engine.ee.laser
        original = laser.check
        laser.check = lambda timeout_s=None: (calls.append(1), original(timeout_s))[1]
        end = self.run_to_the_end()
        st = end["flow"]["stats"]
        self.assertEqual(end["run_state"], "RUNNING")
        self.assertEqual(st["in_flight"], 0)
        # every box placement + every pass put back (the last put-back is booked before its laser check runs: wait for it)
        wait_until(lambda: len(calls) == 2 * (st["tests"] + st["passed"]), 10, "the last laser check")
        self.assertNotIn("9204", [a["code"] for a in end["alarms"]])


class DropStopsTheRobotTests(SimFlowCase):
    def test_a_dropped_product_stops_the_robot_program(self):
        wait_until(lambda: self.rt.bridge.connected, what="bridge link")
        wait_until(lambda: self.rt.bridge.program_state is True, what="robot program running")
        self.rt.engine.on_drop("head 1 lost its product")
        wait_until(lambda: self.rt.bridge.program_state is False, 15, "the robot program stopped")
