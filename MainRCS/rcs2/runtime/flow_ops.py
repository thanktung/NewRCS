"""Tray flow: what the operator needs to TEACH and CHECK (calibration of the heads, the trays and the boxes).

The points are taught with `teach_point` (robot_ops.py), always with all six values (x y z w p r) + CONFIG / UF / UT:
    head_<k>_at_O   the robot pose that puts head k over the origin point O of the input tray (k = 1..heads), and scanner_at_O / laser_at_O
    input_O input_X input_Y    ng_O ng_X ng_Y    (+ output1_*, output2_* when those trays are configured)
                                head 1 over the first cell, the last cell of the first row, the first cell of the last row
    fixture_<n>                 head 1 over the place where box n takes its product
The checks move the robot with the SAME pose maths as the run (core/geometry.py), so a point that is wrong shows up here, not in production.
All of it needs the robot program to run (UO[3]) like every robot operation, and is refused while a run / job is active.
"""
from ..core import geometry as G
from ..core.tray import TITLES
from ..core.geometry import GeometryError


class FlowOpsMixin:
    @property
    def flow_mode(self):
        return getattr(self.engine, "flow", None) is not None

    # ---- what has to be taught ------------------------------------------------------------------------ #
    def flow_groups(self):
        """[(group key, title, [(point name, label), ...])] of everything the flow needs, in teaching order."""
        flow = self.engine.flow
        if flow is None:
            return []
        heads = [("head_%d_at_O" % k, "Tay %d tại O" % k) for k in range(1, flow.heads + 1)]
        if flow.scanner:
            heads.append((G.head_point_name(G.SCANNER), "Máy quét tại O"))
        if flow.laser:
            heads.append((G.head_point_name(G.LASER), "Đầu laser IL-1000 tại O"))
        groups = [("heads", "1. Offset các tay (cùng một điểm O)", heads)]
        for kind in ("input", "ng", "output1", "output2"):                         # the trays that are configured, in this order
            if kind in flow.trays:
                groups.append((kind, "%d. %s (tay 1)" % (len(groups) + 1, TITLES[kind]),
                               [("%s_%s" % (kind, p), "%s %s" % (TITLES[kind], p)) for p in "OXY"]))
        fixtures = [("fixture_%d" % n, "Box %d" % n) for n in flow.fixture_numbers]
        groups.append(("fixtures", "%d. Vị trí các box (tay 1)" % (len(groups) + 1), fixtures))
        return groups

    def flow_taught(self):
        """{point name: True/False} for every point the flow needs."""
        pts = self.points()
        return {name: name in pts for _, _, items in self.flow_groups() for name, _ in items}

    def flow_status(self):
        """{"missing": [...], "problem": "" | text, "complete": bool}: complete = everything is taught and consistent."""
        flow = self.engine.flow
        if flow is None:
            return {"missing": [], "problem": "", "complete": True}
        missing = flow.missing_points(self.points())
        problem = ""
        if not missing:
            try:
                G.Layout(self.points(), flow.trays, flow.fixture_numbers, flow.heads, flow.scanner, flow.laser)
            except GeometryError as ex:
                problem = str(ex)
        return {"missing": missing, "problem": problem, "complete": not missing and not problem}

    # ---- poses (for display and for the checks) ---------------------------------------------------------- #
    def _transforms(self, head):
        pts = self.points()
        key = G.head_point_name(head)
        for name in (G.head_point_name(1), key):
            if name not in pts:
                raise GeometryError("chưa dạy %s" % name)
        return G.HeadTransforms({1: pts[G.head_point_name(1)], head: pts[key]}, count=1)

    def flow_point_pose(self, name, head=1):
        """Robot pose that puts `head` (1 = the taught one, "scanner" too) over the taught point `name`."""
        value = self.points().get(name)
        if value is None:
            raise GeometryError("chưa dạy điểm %s" % name)
        if head == 1:
            return G.make_point(G.split_point(value)[0], like=value)
        return self._transforms(head).pose_for(head, value)

    def flow_cell_pose(self, tray, index, head=1):
        """Robot pose that puts `head` over cell `index` (reading order) of the "input" or the "ng" tray, all six values."""
        flow = self.engine.flow
        pts = self.points()
        names = ["%s_%s" % (tray, p) for p in "OXY"]
        absent = [n for n in names if n not in pts]
        if absent:
            raise GeometryError("chưa dạy: %s" % ", ".join(absent))
        grid = G.TrayGrid(pts[names[0]], pts[names[1]], pts[names[2]], flow.trays[tray]["rows"], flow.trays[tray]["cols"], tray)
        cell = grid.cell_by_index(index)
        return cell if head == 1 else self._transforms(head).pose_for(head, cell)

    def flow_head_offsets(self):
        """{head: [x y z w p r]} offset of every taught head relative to head 1 (tool frame), for the calibration screen."""
        out = {}
        for k in [*range(1, (self.engine.flow.heads if self.engine.flow else 0) + 1), G.SCANNER, G.LASER]:
            try:
                out[k] = [round(v, 3) for v in self._transforms(k).offset(k)]
            except (GeometryError, KeyError):
                pass
        return out

    # ---- moves that check the calibration -------------------------------------------------------------- #
    def _move_to_pose(self, pose, label, override):
        value = pose
        self._log_manual("%s: %s" % (label, [round(v, 3) for v in value["xyzwpr"][:6]]))
        return self._manual_motion(lambda: self.bridge.move(value["xyzwpr"], override=override or self.manual_override(),
                                                            config=value.get("config"), uf=value.get("uf"), ut=value.get("ut")))

    def flow_move_head_to_point(self, name, head=1, override=None):
        """Put `head` over the taught point `name` (a tray corner, a box...)."""
        return self._move_to_pose(self.flow_point_pose(name, head), "tay %s tới điểm %s" % (head, name), override)

    def flow_move_head_to_cell(self, tray, index, head=1, override=None):
        """Put `head` over cell `index` of a tray (the pose is the one a run would use)."""
        return self._move_to_pose(self.flow_cell_pose(tray, index, head), "tay %s tới ô %d của tray %s" % (head, index, tray), override)

    # ---- state of the run ------------------------------------------------------------------------------ #
    def reset_flow(self):
        """After the heads and boxes were emptied by hand: forget where every product was, trays full / empty again."""
        self.engine.reset_flow()
        self._log_manual("xóa trạng thái luồng tray")
