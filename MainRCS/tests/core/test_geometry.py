"""Geometry of the tray flow: poses with 6 values, tray grids from 3 points, offsets between heads."""
import math
import random
import unittest

from rcs2.core import geometry as G


def pt(x, y, z, w=180.0, p=0.0, r=0.0, **extra):
    d = {"xyzwpr": [x, y, z, w, p, r]}
    d.update(extra)
    return d


class PoseMathTests(unittest.TestCase):
    def test_matrix_roundtrip(self):
        rng = random.Random(5)
        for _ in range(200):
            pose = [rng.uniform(-900, 900), rng.uniform(-900, 900), rng.uniform(-300, 900),
                    rng.uniform(-179, 179), rng.uniform(-85, 85), rng.uniform(-179, 179)]
            back = G.from_matrix(G.to_matrix(pose))
            self.assertTrue(G.pose_close(pose, back, 1e-6, 1e-6), (pose, back))

    def test_fanuc_convention_r_turns_about_z(self):
        m = G.to_matrix([0, 0, 0, 0, 0, 90])               # r = 90: the x axis becomes the y axis
        self.assertAlmostEqual(m[1][0], 1.0)
        self.assertAlmostEqual(m[0][0], 0.0)
        m = G.to_matrix([0, 0, 0, 90, 0, 0])               # w = 90: the y axis becomes the z axis
        self.assertAlmostEqual(m[2][1], 1.0)

    def test_inverse(self):
        m = G.to_matrix([100, -50, 300, 170, -20, 33])
        ident = G.mat_mul(m, G.mat_inv(m))
        for i in range(4):
            for j in range(4):
                self.assertAlmostEqual(ident[i][j], 1.0 if i == j else 0.0, places=9)

    def test_gimbal_lock_still_gives_the_same_matrix(self):
        pose = [1, 2, 3, 30, 90, 0]
        back = G.from_matrix(G.to_matrix(pose))
        a, b = G.to_matrix(pose), G.to_matrix(back)
        for i in range(4):
            for j in range(4):
                self.assertAlmostEqual(a[i][j], b[i][j], places=9)

    def test_wrap180(self):
        self.assertAlmostEqual(G.wrap180(190), -170)
        self.assertAlmostEqual(G.wrap180(-190), 170)
        self.assertAlmostEqual(G.wrap180(180), -180)
        self.assertAlmostEqual(G.wrap180(0.5), 0.5)

    def test_bad_points_are_refused(self):
        for bad in ([1, 2, 3], {"xyzwpr": "x"}, [1, 2, 3, 4, 5, True], None):
            with self.assertRaises(G.GeometryError):
                G.split_point(bad)


class TrayGridTests(unittest.TestCase):
    def test_axis_aligned_grid_has_exact_cells(self):
        o, x, y = pt(100, 200, 50), pt(170, 200, 50), pt(100, 260, 50)       # 8 cols (pitch 10) x 4 rows (pitch 20)
        g = G.TrayGrid(o, x, y, 4, 8)
        self.assertEqual(g.capacity, 32)
        self.assertEqual(g.cell(0, 0)["xyzwpr"], [100, 200, 50, -180.0, 0, 0])      # w 180 is stored as -180 (same angle)
        self.assertEqual(g.cell(0, 7)["xyzwpr"][:3], [170, 200, 50])
        self.assertEqual(g.cell(3, 0)["xyzwpr"][:3], [100, 260, 50])
        self.assertEqual(g.cell(2, 5)["xyzwpr"][:3], [150, 240, 50])
        self.assertEqual(g.cell_by_index(g.index(2, 5)), g.cell(2, 5))
        self.assertEqual(g.rc(21), (2, 5))

    def test_a_tilted_and_twisted_tray_follows_all_six_values(self):
        # z rises along the columns, the tray is rotated 2 degrees about z and tilted 1 degree about x
        o = pt(100, 200, 50, 180, 0, 0)
        x = pt(170, 214, 53.5, 181, 0.7, 2.0)
        y = pt(86, 260, 52, 180.5, 0.4, 2.0)
        g = G.TrayGrid(o, x, y, 4, 8)
        c = g.cell(2, 5)["xyzwpr"]
        expect = [100 + 5 * 10 - 2 * 4.666666666666667, 200 + 5 * 2 + 2 * 20, 50 + 5 * 0.5 + 2 * (2 / 3),
                  G.wrap180(180 + 5 * (1 / 7) + 2 * (0.5 / 3)), 0 + 5 * 0.1 + 2 * (0.4 / 3), 5 * (2 / 7) + 2 * (2 / 3)]
        self.assertTrue(G.pose_close(c, expect, 1e-6, 1e-6), (c, expect))
        far = g.cell(3, 7)["xyzwpr"]                           # the far corner is exactly O + (X-O) + (Y-O)
        corner = [100 + 70 - 14, 200 + 14 + 60, 50 + 3.5 + 2, G.wrap180(180 + 1 + 0.5), 0.7 + 0.4, 2.0 + 2.0]
        self.assertTrue(G.pose_close(far, corner, 1e-6, 1e-6), (far, corner))

    def test_angles_are_interpolated_through_the_wrap_at_180(self):
        o = pt(0, 0, 0, 179, 0, 0)
        x = pt(10, 0, 0, -179, 0, 0)                           # 179 -> 181: a turn of +2, not -358
        y = pt(0, 10, 0, 179, 0, 0)
        g = G.TrayGrid(o, x, y, 2, 3)
        self.assertAlmostEqual(G.wrap180(g.cell(0, 1)["xyzwpr"][3] - 180.0), 0.0, places=6)     # 180
        self.assertTrue(abs(G.wrap180(g.cell(0, 2)["xyzwpr"][3] - (-179))) < 1e-6)

    def test_config_uf_ut_come_from_o_and_must_agree(self):
        extra = dict(config=[0, 0, 1, 1, 0, 0, 0], uf=1, ut=1)
        g = G.TrayGrid(pt(0, 0, 0, **extra), pt(9, 0, 0, **extra), pt(0, 9, 0, **extra), 2, 2)
        self.assertEqual(g.cell(1, 1)["config"], [0, 0, 1, 1, 0, 0, 0])
        self.assertEqual((g.cell(1, 1)["uf"], g.cell(1, 1)["ut"]), (1, 1))
        with self.assertRaises(G.GeometryError) as cm:
            G.TrayGrid(pt(0, 0, 0, **extra), pt(9, 0, 0, **dict(extra, uf=2)), pt(0, 9, 0, **extra), 2, 2)
        self.assertIn("uf", str(cm.exception))
        with self.assertRaises(G.GeometryError):
            G.TrayGrid(pt(0, 0, 0, **extra), pt(9, 0, 0, **dict(extra, config=[1, 0, 1, 1, 0, 0, 0])), pt(0, 9, 0, **extra), 2, 2)

    def test_single_row_or_column_and_degenerate_sides(self):
        g = G.TrayGrid(pt(0, 0, 0), pt(50, 0, 0), pt(0, 0, 0), 1, 6)       # one row: the Y point is not used
        self.assertEqual(g.cell(0, 5)["xyzwpr"][:3], [50, 0, 0])
        with self.assertRaises(G.GeometryError):
            G.TrayGrid(pt(0, 0, 0), pt(0, 0, 0), pt(0, 9, 0), 2, 6)          # X == O but 6 columns
        with self.assertRaises(G.GeometryError):
            G.TrayGrid(pt(0, 0, 0), pt(9, 0, 0), pt(0, 9, 0), 0, 6)

    def test_cells_outside_the_tray_are_refused(self):
        g = G.TrayGrid(pt(0, 0, 0), pt(9, 0, 0), pt(0, 9, 0), 2, 2)
        for rc in ((2, 0), (0, 2), (-1, 0)):
            with self.assertRaises(G.GeometryError):
                g.cell(*rc)
        with self.assertRaises(G.GeometryError):
            g.rc(4)


class HeadTests(unittest.TestCase):
    """Ground truth: the heads sit on the tool at fixed places `d_k` (a rigid transform from the flange). The robot flange
    pose F puts head k's tip at F * d_k. So head 1 at O needs A = O * inv(d1), head k at O needs Bk = O * inv(dk) and, for any
    other place W, head 1 needs P1 = W * inv(d1) while head k needs W * inv(dk) - which pose_for(k, P1) must reproduce."""

    D = {1: [0, 0, 0, 0, 0, 0], 2: [-22, 0.5, 0, 0, 0, 0.4], 3: [-44.2, 1.0, -0.3, 0.2, 0, 0.8],
         4: [-66.1, 1.2, 0.2, 0, 0.1, 1.1], 5: [-88.0, 2.0, 0.5, 0.3, 0.2, 2.5]}

    def flange_for(self, tip_world, k):
        return G.from_matrix(G.mat_mul(G.to_matrix(tip_world), G.mat_inv(G.to_matrix(self.D[k]))))

    def test_offsets_are_right_for_any_orientation_of_the_target(self):
        o_world = [500, 100, 300, 180, 0, 10]
        at_o = {k: self.flange_for(o_world, k) for k in self.D}
        ht = G.HeadTransforms(at_o, count=None)
        rng = random.Random(11)
        for _ in range(100):
            w = [rng.uniform(-600, 900), rng.uniform(-600, 600), rng.uniform(-100, 500),
                 rng.uniform(-179, 179), rng.uniform(-60, 60), rng.uniform(-179, 179)]
            p1 = self.flange_for(w, 1)                                  # what the operator teaches with head 1
            for k in (2, 3, 4, 5):
                got = ht.pose_for(k, {"xyzwpr": p1, "config": [0, 0, 1, 1, 0, 0, 0], "uf": 1, "ut": 1})
                self.assertTrue(G.pose_close(got["xyzwpr"], self.flange_for(w, k), 1e-6, 1e-6), (k, got, w))
                self.assertEqual(got["config"], [0, 0, 1, 1, 0, 0, 0])      # CONFIG / UF / UT of the target are kept

    def test_head_at_o_is_exactly_the_taught_pose(self):
        o_world = [500, 100, 300, 180, 0, 10]
        at_o = {k: self.flange_for(o_world, k) for k in self.D}
        ht = G.HeadTransforms(at_o)
        for k in self.D:
            self.assertTrue(G.pose_close(ht.pose_for(k, at_o[1])["xyzwpr"], at_o[k], 1e-6, 1e-6))
        self.assertTrue(G.pose_close(ht.pose_for(1, at_o[1])["xyzwpr"], at_o[1], 1e-9, 1e-9))

    def test_same_orientation_reduces_to_a_shift_of_x_y_z(self):
        a = [500, 100, 300, 180, 0, 0]
        ht = G.HeadTransforms({1: a, 2: [478, 100.5, 300, 180, 0, 0]})
        got = ht.pose_for(2, [200, 300, 250, 180, 0, 0])["xyzwpr"]
        self.assertTrue(G.pose_close(got, [178, 300.5, 250, 180, 0, 0], 1e-6, 1e-6), got)

    def test_scanner_is_one_more_head_and_missing_ones_are_reported(self):
        a = [500, 100, 300, 180, 0, 0]
        ht = G.HeadTransforms({1: a, 2: [478, 100, 300, 180, 0, 0], G.SCANNER: [520, 100, 300, 180, 0, 0]}, count=2)
        self.assertTrue(ht.has(G.SCANNER))
        self.assertTrue(G.pose_close(ht.pose_for(G.SCANNER, [0, 0, 0, 180, 0, 0])["xyzwpr"], [20, 0, 0, -180, 0, 0]))
        with self.assertRaises(G.GeometryError):
            ht.pose_for(3, a)
        with self.assertRaises(G.GeometryError):
            G.HeadTransforms({2: a})                                            # no reference head
        with self.assertRaises(G.GeometryError):
            G.HeadTransforms({1: a}, count=3)                                   # heads 2 and 3 not taught


class LayoutTests(unittest.TestCase):
    def points(self, heads=3, fixtures=(1, 2)):
        pts = {"head_%d_at_O" % k: pt(500 - 22 * (k - 1), 100, 300) for k in range(1, heads + 1)}
        pts.update({"input_O": pt(100, 200, 50), "input_X": pt(170, 200, 50), "input_Y": pt(100, 260, 50),
                    "ng_O": pt(300, 200, 50), "ng_X": pt(350, 200, 50), "ng_Y": pt(300, 230, 50)})
        for n in fixtures:
            pts["fixture_%d" % n] = pt(100 * n, 500, 200)
        return pts

    TRAYS = {"input": {"rows": 4, "cols": 8}, "ng": {"rows": 2, "cols": 6}}

    def test_complete_layout_gives_poses_for_every_head(self):
        lay = G.Layout(self.points(), self.TRAYS, [1, 2], heads=3)
        # head 3 is 44 mm "behind" head 1: to put it over input cell (0, 0) the robot goes 44 mm back
        self.assertTrue(G.pose_close(lay.pick_pose(3, 0)["xyzwpr"], [100 - 44, 200, 50, 180, 0, 0]))
        self.assertTrue(G.pose_close(lay.fixture_pose(2, 2)["xyzwpr"], [200 - 22, 500, 200, 180, 0, 0]))
        self.assertEqual(lay.ng.rc(7), (1, 1))                                   # cell 7 of 6 columns = row 1, col 1
        self.assertTrue(G.pose_close(lay.ng_pose(1, 7)["xyzwpr"], [310, 230, 50, 180, 0, 0]))

    def test_missing_points_are_listed_by_name(self):
        pts = self.points()
        del pts["head_3_at_O"], pts["ng_Y"], pts["fixture_2"]
        self.assertEqual(G.Layout.missing(pts, self.TRAYS, [1, 2], 3), ["head_3_at_O", "ng_Y", "fixture_2"])
        with self.assertRaises(G.GeometryError) as cm:
            G.Layout(pts, self.TRAYS, [1, 2], heads=3)
        self.assertIn("head_3_at_O", str(cm.exception))
        self.assertIn("settings.json -> trays -> ng", " ".join(G.Layout.missing(pts, {"input": self.TRAYS["input"]}, [1], 3)))

    def test_scanner_pose_needs_scanner_at_o(self):
        pts = self.points()
        pts["scanner_at_O"] = pt(540, 100, 300)
        lay = G.Layout(pts, self.TRAYS, [1, 2], heads=3, scanner=True)
        self.assertTrue(G.pose_close(lay.scan_pose(0)["xyzwpr"], [140, 200, 50, 180, 0, 0]))
        with self.assertRaises(G.GeometryError):
            G.Layout(self.points(), self.TRAYS, [1, 2], heads=3, scanner=True)





class OutputTrayGeometryTests(unittest.TestCase):
    TRAYS = {"input": {"rows": 2, "cols": 4}, "ng": {"rows": 1, "cols": 4}, "output1": {"rows": 2, "cols": 3}, "output2": {"rows": 1, "cols": 2}}

    def points(self):
        pts = {"head_%d_at_O" % k: pt(500 - 22 * (k - 1), 100, 300) for k in (1, 2)}
        pts.update({"input_O": pt(100, 200, 50), "input_X": pt(130, 200, 50), "input_Y": pt(100, 220, 50),
                    "ng_O": pt(300, 200, 50), "ng_X": pt(330, 200, 50), "ng_Y": pt(300, 200, 50), "fixture_1": pt(400, 500, 200),
                    "output1_O": pt(100, 350, 50), "output1_X": pt(120, 350, 50), "output1_Y": pt(100, 380, 50),
                    "output2_O": pt(300, 350, 50), "output2_X": pt(310, 350, 50), "output2_Y": pt(300, 350, 50)})
        return pts

    def test_the_output_trays_are_part_of_the_layout_when_they_are_configured(self):
        self.assertEqual(G.Layout.output_names(self.TRAYS), ["output1", "output2"])
        self.assertEqual(G.Layout.output_names({"input": {}, "ng": {}}), [])
        self.assertEqual(G.Layout.output_names({"output2": {}}), ["output2"])
        lay = G.Layout(self.points(), self.TRAYS, [1], heads=2)
        self.assertEqual(len(lay.outputs), 2)
        # output 1: 2 rows x 3 cols, O (100,350) X (120,350) Y (100,380): pitch 10 x 30, cell 4 = row 1 col 1 -> x 110, y 380
        self.assertTrue(G.pose_close(lay.output_pose(2, 0, 4)["xyzwpr"], [110 - 22, 380, 50, 180, 0, 0], 1e-6, 1e-6))
        self.assertTrue(G.pose_close(lay.output_pose(2, 1, 1)["xyzwpr"], [310 - 22, 350, 50, 180, 0, 0], 1e-6, 1e-6))

    def test_missing_output_points_are_named_only_for_the_configured_trays(self):
        pts = self.points()
        del pts["output2_Y"]
        self.assertEqual(G.Layout.missing(pts, self.TRAYS, [1], 2), ["output2_Y"])
        self.assertEqual(G.Layout.missing(pts, {k: v for k, v in self.TRAYS.items() if k != "output2"}, [1], 2), [])      # output 2 not configured

    def test_a_laser_check_at_an_output_cell(self):
        pts = self.points()
        pts["laser_at_O"] = pt(560, 100, 300)
        lay = G.Layout(pts, self.TRAYS, [1], heads=2, laser=True)
        a, b = lay.laser_poses("output", (0, 1), [(-5, 0, 0), (5, 0, 0)])
        self.assertAlmostEqual(b["xyzwpr"][0] - a["xyzwpr"][0], 10.0, places=6)
        self.assertAlmostEqual(a["xyzwpr"][0], 110 + 60 - 5, places=6)


class LaserGeometryTests(unittest.TestCase):
    """The laser is one more tool taught at O; its measuring points are offsets in the frame of the place where the product was put."""
    TRAYS = {"input": {"rows": 4, "cols": 8}, "ng": {"rows": 2, "cols": 6}}

    def points(self):
        pts = {"head_%d_at_O" % k: pt(500 - 22 * (k - 1), 100, 300) for k in (1, 2)}
        pts["laser_at_O"] = pt(560, 100, 300)                                    # 60 mm in front of head 1
        pts.update({"input_O": pt(100, 200, 50), "input_X": pt(170, 200, 50), "input_Y": pt(100, 260, 50),
                    "ng_O": pt(300, 200, 50), "ng_X": pt(350, 200, 50), "ng_Y": pt(300, 230, 50), "fixture_1": pt(400, 500, 200, r=90.0)})
        return pts

    def test_shift_follows_the_orientation_of_the_place(self):
        out = G.shift_pose(pt(100, 200, 50, 180, 0, 90), (10, 0, 0))             # r = 90: the place's x axis points along the world y axis
        self.assertTrue(G.pose_close(out["xyzwpr"], [100, 210, 50, 180, 0, 90], 1e-6, 1e-6))
        out = G.shift_pose(pt(100, 200, 50, 180, 0, 0), (0, 5, -3))              # w = 180: the tool z axis points down, y is mirrored
        self.assertTrue(G.pose_close(out["xyzwpr"], [100, 195, 53, 180, 0, 0], 1e-6, 1e-6))

    def test_the_laser_poses_are_the_place_shifted_and_moved_to_the_laser_tool(self):
        lay = G.Layout(self.points(), self.TRAYS, [1], heads=2, laser=True)
        a, b = lay.laser_poses("input", 0, [(-15, 0, 0), (15, 0, 0)])
        # laser_at_O is taught 60 mm in front of head 1: over the cell (100, 200) the laser must be 60 mm "behind" ... so x = 100 + 60 -/+ 15
        self.assertAlmostEqual(a["xyzwpr"][0], 100 + 60 - 15, places=6)
        self.assertAlmostEqual(b["xyzwpr"][0], 100 + 60 + 15, places=6)
        self.assertAlmostEqual(a["xyzwpr"][1], 200, places=6)
        a, b = lay.laser_poses("box", 1, [(-15, 0, 0), (15, 0, 0)])             # the box is turned by r = 90: the points are 30 mm apart along y
        self.assertAlmostEqual(b["xyzwpr"][1] - a["xyzwpr"][1], 30.0, places=6)
        self.assertAlmostEqual(b["xyzwpr"][0], a["xyzwpr"][0], places=6)
        self.assertEqual(len(lay.laser_poses("ng", 7, [(0, 0, 0)])), 1)
        with self.assertRaises(G.GeometryError):
            lay.laser_poses("shelf", 1, [(0, 0, 0)])

    def test_laser_at_o_is_required_only_when_the_laser_is_used(self):
        pts = self.points()
        del pts["laser_at_O"]
        self.assertEqual(G.Layout.missing(pts, self.TRAYS, [1], 2, scanner=False, laser=False), [])
        self.assertEqual(G.Layout.missing(pts, self.TRAYS, [1], 2, scanner=False, laser=True), ["laser_at_O"])
        with self.assertRaises(G.GeometryError):
            G.Layout(pts, self.TRAYS, [1], 2, laser=True)


if __name__ == "__main__":
    unittest.main()
