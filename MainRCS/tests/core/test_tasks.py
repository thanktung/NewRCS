"""Stages built from planner tasks: the order of the cycles, the carry checks, the laser checks."""
import unittest

from rcs2.core import dut as D
from rcs2.core import geometry as G
from rcs2.core.planner import ServiceTask, TakeTask, TrayTask
from rcs2.core.tasks import BuildSettings, StageBuilder

TRAYS = {"input": {"rows": 2, "cols": 4}, "ng": {"rows": 1, "cols": 4}}


def pt(x, y, z):
    return {"xyzwpr": [float(x), float(y), float(z), 180.0, 0.0, 0.0], "config": [0, 0, 1, 1, 0, 0, 0], "uf": 1, "ut": 1}


TRAYS_OUT = dict(TRAYS, output1={"rows": 1, "cols": 4}, output2={"rows": 1, "cols": 4})


def layout(heads=3, trays=TRAYS):
    pts = {"head_%d_at_O" % k: pt(500 - 22 * (k - 1), 100, 300) for k in range(1, heads + 1)}
    pts.update({"scanner_at_O": pt(540, 100, 300), "laser_at_O": pt(560, 100, 300), "input_O": pt(100, 200, 50), "input_X": pt(130, 200, 50),
                "input_Y": pt(100, 220, 50), "ng_O": pt(300, 200, 50), "ng_X": pt(330, 200, 50), "ng_Y": pt(300, 200, 50),
                "fixture_1": pt(400, 500, 200), "fixture_2": pt(500, 500, 200),
                "output1_O": pt(100, 350, 50), "output1_X": pt(136, 350, 50), "output1_Y": pt(100, 350, 50),
                "output2_O": pt(300, 350, 50), "output2_X": pt(336, 350, 50), "output2_Y": pt(300, 350, 50)})
    return G.Layout(pts, trays, [1, 2], heads, scanner=True, laser=True)


def kinds(stages):
    """One word per stage: what it does."""
    out = []
    for s in stages:
        first = s.steps[0]
        if s.kind == "carry":
            out.append("carry")
        elif s.label.startswith("scan"):
            out.append("scan")
        elif s.label.startswith("laser"):
            out.append("laser")
        elif s.commit:
            out.append(s.commit["op"])
        elif first.get("ats"):
            out.append("ats")
        else:
            out.append(s.label)
    return out


class BuilderTests(unittest.TestCase):
    def setUp(self):
        self.book = D.DutBook(8, 3, 4)
        self.lay = layout()

    def builder(self, **kw):
        return StageBuilder(self.lay, self.book, BuildSettings(laser=True, **kw))

    def test_picking_scans_first_then_picks_and_checks_what_is_already_carried(self):
        stages = self.builder().build(TrayTask(sorts=(), picks=((1, 0), (2, 1)), reason="t"))
        self.assertEqual(kinds(stages), ["scan", "take_tray", "carry", "scan", "take_tray"])          # no carry check while nothing is held
        carry = stages[2]
        self.assertEqual(carry.steps[0]["heads"], [1])                                                 # head 1 holds its product while head 2 picks
        self.assertEqual(stages[0].steps[1], {"ee": "scanner", "tag": "cell:0"})

    def test_a_passed_product_is_put_into_the_first_empty_cell_and_checked_with_the_laser(self):
        d = self.book.take_from_tray(5, 1)
        d.need, d.final = D.RETURN, "PASS"
        stages = self.builder().build(TrayTask(sorts=((1, d.id),), picks=(), reason="t"))
        self.assertEqual(kinds(stages), ["carry", "return_tray", "laser"])
        self.assertEqual(stages[1].commit, {"op": "return_tray", "head": 1, "cell": 5})                 # cell 5 is the only empty one
        laser = stages[2].steps
        self.assertEqual([s.get("ee") for s in laser if "ee" in s], ["laser", "laser"])                 # 2 measuring points
        self.assertEqual(sum(1 for s in laser if s.get("robot") == "move"), 2)

    def test_a_failed_product_into_the_ng_tray_is_not_checked_by_default(self):
        d = self.book.take_from_tray(0, 2)
        d.need, d.final = D.NG, "NG"
        self.assertEqual(kinds(self.builder().build(TrayTask(sorts=((2, d.id),), picks=(), reason="t"))), ["carry", "put_ng"])
        stages = self.builder(laser_places=("ng",)).build(TrayTask(sorts=((2, d.id),), picks=(), reason="t"))
        self.assertEqual(kinds(stages), ["carry", "put_ng", "laser"])

    def test_a_service_takes_out_checks_the_carried_products_places_and_checks_the_laser_before_the_test_starts(self):
        old = self.book.take_from_tray(0, 99)
        self.book.place_in_box(old, 1)
        self.book.result(old, "PASS", 9.0, [1, 2])
        new = self.book.take_from_tray(1, 2)
        new.sn = "SN1"
        stages = self.builder().build(ServiceTask(1, 2, new.id, 1, old.id, "t"))
        self.assertEqual(kinds(stages), ["carry", "take_box", "carry", "place_box", "laser", "ats"])
        self.assertEqual(stages[0].steps[0]["heads"], [2])                                             # head 2 carries the new product
        self.assertEqual(stages[2].steps[0]["heads"], [1, 2])                                          # and now head 1 carries the tested one too
        self.assertEqual([s.get("ats") for s in stages[-1].steps], ["barcode", "place_dut_ok"])         # the test starts only after the laser

    def test_the_laser_can_be_switched_off(self):
        d = self.book.take_from_tray(5, 1)
        d.need = D.RETURN
        stages = StageBuilder(self.lay, self.book, BuildSettings(laser=False)).build(TrayTask(sorts=((1, d.id),), picks=(), reason="t"))
        self.assertEqual(kinds(stages), ["carry", "return_tray"])

    def test_a_take_only_task_checks_what_is_carried(self):
        a = self.book.take_from_tray(0, 1)
        old = self.book.take_from_tray(1, 99)
        self.book.place_in_box(old, 2)
        self.book.result(old, "PASS", 9.0, [1, 2])
        stages = self.builder().build(TakeTask(2, 2, old.id, "t"))
        self.assertEqual(kinds(stages), ["carry", "take_box"])
        self.assertEqual(stages[0].steps[0]["heads"], [1])
        self.assertIsNotNone(a)


class OutputTrayBuilderTests(unittest.TestCase):
    """With output trays the passed products are put into them (the next free cells, tray 1 first), not back into the input tray."""

    def setUp(self):
        self.book = D.DutBook(8, 3, 4, out_capacity=[2, 4])
        self.lay = layout(trays=TRAYS_OUT)

    def passed(self, cell, head):
        d = self.book.take_from_tray(cell, head)
        d.need, d.final = D.RETURN, "PASS"
        return d

    def build(self, *heads_dut):
        return StageBuilder(self.lay, self.book, BuildSettings(laser=True)).build(
            TrayTask(sorts=tuple((h, d.id) for h, d in heads_dut), picks=(), reason="t"))

    def test_a_passed_product_goes_into_the_first_free_output_cell_and_is_checked_with_the_laser(self):
        d = self.passed(0, 1)
        stages = self.build((1, d))
        self.assertEqual(kinds(stages), ["carry", "put_out", "laser"])
        self.assertEqual(stages[1].commit, {"op": "put_out", "head": 1, "tray": 0, "cell": 0})
        want = self.lay.laser_poses("output", (0, 0), [(-15, 0, 0), (15, 0, 0)])
        moves = [s["target"] for s in stages[2].steps if s.get("robot") == "move"]
        self.assertTrue(all(G.pose_close(m["xyzwpr"], w["xyzwpr"], 1e-6, 1e-6) for m, w in zip(moves, want)))

    def test_several_passed_products_fill_the_cells_in_order_and_cross_over_to_output_2(self):
        a, b, c = self.passed(0, 1), self.passed(1, 2), self.passed(2, 3)
        stages = self.build((1, a), (2, b), (3, c))
        commits = [s.commit for s in stages if s.commit]
        self.assertEqual([(m["tray"], m["cell"]) for m in commits], [(0, 0), (0, 1), (1, 0)])       # output 1 has 2 cells: the third goes to output 2

    def test_the_head_goes_over_the_cell_of_the_output_tray_with_the_head_offset(self):
        d = self.passed(0, 2)
        stages = self.build((2, d))
        target = stages[1].steps[0]["target"]["xyzwpr"]
        self.assertTrue(G.pose_close(target, self.lay.output_pose(2, 0, 0)["xyzwpr"], 1e-6, 1e-6))
        self.assertTrue(G.pose_close(target, [100 - 22, 350, 50, 180, 0, 0], 1e-6, 1e-6))             # head 2 sits 22 mm behind head 1

    def test_a_failed_product_still_goes_to_the_ng_tray(self):
        d = self.book.take_from_tray(0, 1)
        d.need, d.final = D.NG, "NG"
        self.assertEqual(kinds(self.build((1, d))), ["carry", "put_ng"])


if __name__ == "__main__":
    unittest.main()

