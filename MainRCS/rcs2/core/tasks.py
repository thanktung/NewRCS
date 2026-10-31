"""From a planner task to robot steps.

A task (planner.py) is turned into a list of STAGES. A stage is a short list of ordinary sequence steps (rcs2/core/sequence.py: robot
move / ee heads / ee scanner / ee laser / ats) plus an optional COMMIT: what the books must record once the stage has really finished, e.g.
"head 3 took the product of cell 12". The engine runs the stages one after the other and applies each commit when its stage is done,
so the books always say where every product is, even when a later stage fails or the run is stopped between two stages.

Poses are computed with all six values (geometry.Layout): a pick / place of head k at a cell or a box is ONE `move` to the pose that
brings that head there, then that head's cylinder goes down, the vacuum switches, the cylinder goes up and the pressure sensor is checked.

The cycles
  pick from the input tray:  move the barcode reader over the cell -> read the code -> move head k over the cell -> down, vacuum on, up, check hold
  put down (a box, an output tray, the input tray, the NG tray): move head k over the place -> down, vacuum off, up, check release
                             -> the IL-1000 laser is moved over 2 measuring points of the product and must say GO at both (a tilted product is
                                refused: alarm 9204)  [settings.json -> flow.laser_check]
  before every movement of a head: a CARRY CHECK = the pressure sensors of every head that carries a product must still say "holding";
  a head that lost its product on the way raises DropError (alarm 9208, the robot is stopped).

Commits (dicts, applied by FlowController.commit):
    {"op": "take_tray", "cell": c, "head": k}            the head picked the product of input cell c
    {"op": "take_box", "fixture": n, "head": k}          the head took the tested product out of box n
    {"op": "place_box", "fixture": n, "head": k}         the head put its product into box n (its test starts)
    {"op": "return_tray", "head": k, "cell": c}          the head put a passed product into the empty input cell c (the first empty one)
                                                         [only when there are no output trays]
    {"op": "put_out", "head": k, "tray": i, "cell": c}   the head put a passed product into cell c of output tray i (0-based): the next free one
    {"op": "put_ng", "head": k}                          the head put a failed product into the next cell of the NG tray
"""
from dataclasses import dataclass, field
from typing import List, Optional

from . import dut as D
from .planner import ServiceTask, TakeTask, TrayTask


class DropError(Exception):
    """A head that carries a product no longer holds it (the pressure sensor lost it on the way)."""


@dataclass
class Stage:
    label: str
    steps: list
    commit: Optional[dict] = None
    fixture: Optional[int] = None
    kind: str = ""                         # "carry" = the carry check: a failure means a dropped product


@dataclass
class BuildSettings:
    override: Optional[int] = None         # robot speed (%) of the moves; None = the bridge default
    check_timeout_s: float = 1.0           # time given to the pressure sensors
    scan: bool = True                      # read the barcode of every product before it is picked (needs a scanner in the layout)
    send_dut_out: bool = False             # tell the ATS that the tested product was taken out
    auto_start_test: bool = True           # send placeDUTOK after a product was put in
    via_tray: str = ""                     # optional taught points the robot passes through when it changes area
    via_fixtures: str = ""
    laser: bool = False                    # check a product that was put down with the IL-1000 (needs laser_at_O in the layout)
    laser_places: tuple = ("box", "input", "output")
    laser_offsets: tuple = ((-15.0, 0.0, 0.0), (15.0, 0.0, 0.0))
    laser_timeout_s: float = 1.0


class StageBuilder:
    def __init__(self, layout, book, settings: BuildSettings):
        self.layout, self.book, self.s = layout, book, settings
        self.holding = set()               # heads that carry a product at this point of the task being built

    # ---- single movements ------------------------------------------------------------------------ #
    def _move(self, pose):
        step = {"robot": "move", "target": pose}
        if self.s.override is not None:
            step["override"] = self.s.override
        return step

    def _hold(self, head):
        return [{"ee": "heads", "cylinder": "down", "heads": [head]},
                {"ee": "heads", "vacuum": "on", "heads": [head]},
                {"ee": "heads", "cylinder": "up", "heads": [head]},
                {"ee": "heads", "check": "hold", "heads": [head], "timeout_s": self.s.check_timeout_s}]

    def _release(self, head):
        return [{"ee": "heads", "cylinder": "down", "heads": [head]},
                {"ee": "heads", "vacuum": "off", "heads": [head]},
                {"ee": "heads", "cylinder": "up", "heads": [head]},
                {"ee": "heads", "check": "release", "heads": [head], "timeout_s": self.s.check_timeout_s}]

    def _via(self, point):
        return [self._move(point)] if point else []

    def _carry_check(self):
        """Before a head moves: every head that carries a product must still hold it. [] when no head carries one."""
        if not self.holding:
            return []
        return [Stage("carry check heads %s" % sorted(self.holding),
                      [{"ee": "heads", "check": "hold", "heads": sorted(self.holding), "timeout_s": self.s.check_timeout_s}], kind="carry")]

    def _laser(self, kind, ref, fixture=None):
        """The laser check of a product just put down at `ref` (cell index of a tray, or the fixture number): 2 measuring points."""
        if not (self.s.laser and kind in self.s.laser_places):
            return []
        steps = []
        for pose in self.layout.laser_poses(kind, ref, self.s.laser_offsets):
            steps += [self._move(pose), {"ee": "laser", "check": "ok", "timeout_s": self.s.laser_timeout_s}]
        return [Stage("laser check of the product at %s %s" % (kind, ref), steps, None, fixture)]

    # ---- stages ---------------------------------------------------------------------------------- #
    def pick_from_tray(self, head, cell):
        stages = self._carry_check()
        if self.s.scan and self.layout.scanner:
            stages.append(Stage("scan cell %d" % cell, [self._move(self.layout.scan_pose(cell)),
                                                        {"ee": "scanner", "tag": "cell:%d" % cell}]))
        stages.append(Stage("head %d picks cell %d" % (head, cell),
                            [self._move(self.layout.pick_pose(head, cell))] + self._hold(head),
                            {"op": "take_tray", "cell": cell, "head": head}))
        self.holding.add(head)
        return stages

    def put_back(self, head, dut, cell):
        """A tested product goes into input cell `cell` (passed: the first empty cell) or into NG cell `cell` (failed)."""
        stages = self._carry_check()
        if dut.need == D.RETURN:
            stages.append(Stage("head %d puts a passed product into empty cell %d" % (head, cell),
                                [self._move(self.layout.input_pose(head, cell))] + self._release(head),
                                {"op": "return_tray", "head": head, "cell": cell}))
            self.holding.discard(head)
            return stages + self._laser("input", cell)
        stages.append(Stage("head %d puts a failed product into NG cell %d" % (head, cell),
                            [self._move(self.layout.ng_pose(head, cell))] + self._release(head), {"op": "put_ng", "head": head}))
        self.holding.discard(head)
        return stages + self._laser("ng", cell)

    def put_out(self, head, dut, slot):
        """A passed product goes into the output tray cell `slot` = (tray index, cell) (the next free cell of the output trays)."""
        tray, cell = slot
        stages = self._carry_check()
        stages.append(Stage("head %d puts a passed product into output %d cell %d" % (head, tray + 1, cell),
                            [self._move(self.layout.output_pose(head, tray, cell))] + self._release(head),
                            {"op": "put_out", "head": head, "tray": tray, "cell": cell}))
        self.holding.discard(head)
        return stages + self._laser("output", slot)

    def take_from_box(self, fixture, head):
        stages = self._carry_check()
        stages.append(Stage("head %d takes the tested product out of box %d" % (head, fixture),
                            [self._move(self.layout.fixture_pose(head, fixture))] + self._hold(head),
                            {"op": "take_box", "fixture": fixture, "head": head}, fixture))
        self.holding.add(head)
        if self.s.send_dut_out:
            stages.append(Stage("box %d: DUT out" % fixture, [{"ats": "dut_out", "fixture": fixture}], None, fixture))
        return stages

    def place_in_box(self, fixture, head, dut):
        stages = self._carry_check()
        stages.append(Stage("head %d puts a product into box %d" % (head, fixture),
                            [self._move(self.layout.fixture_pose(head, fixture))] + self._release(head),
                            {"op": "place_box", "fixture": fixture, "head": head}, fixture))
        self.holding.discard(head)
        stages += self._laser("box", fixture, fixture)             # a tilted product must not start its test
        ats = []
        if dut.sn:
            ats.append({"ats": "barcode", "sn": dut.sn, "fixture": fixture})
        if self.s.auto_start_test:
            ats.append({"ats": "place_dut_ok", "fixture": fixture})
        if ats:
            stages.append(Stage("box %d: start the test" % fixture, ats, None, fixture))
        return stages

    # ---- whole tasks ----------------------------------------------------------------------------- #
    def build(self, task):
        self.holding = {d.location[1] for d in self.book.duts.values() if d.location[0] == D.HEAD}
        if isinstance(task, TrayTask):
            return self._tray(task)
        if isinstance(task, ServiceTask):
            stages = self._via_fixtures()
            if task.take_head:
                stages += self.take_from_box(task.fixture, task.take_head)
            stages += self.place_in_box(task.fixture, task.place_head, self.book.duts[task.place_dut])
            return stages
        if isinstance(task, TakeTask):
            return self._via_fixtures() + self.take_from_box(task.fixture, task.head)
        raise TypeError("unknown task %r" % (task,))

    def _via_fixtures(self):
        step = self._via(self.s.via_fixtures)
        return [Stage("via fixtures", step)] if step else []

    def _tray(self, task):
        stages = []
        via = self._via(self.s.via_tray)
        if via:
            stages.append(Stage("via tray", via))
        ng_next = self.book.ng_used
        empties = iter(self.book.empty_cells())                         # no output trays: passed products go into the first empty input cells
        outs = iter(self.book.output_slots())                           # output trays: into their next free cells, tray 1 first
        for head, dut_id in task.sorts:
            dut = self.book.duts[dut_id]
            if dut.need == D.RETURN and self.book.has_outputs:
                stages += self.put_out(head, dut, next(outs))
            elif dut.need == D.RETURN:
                stages += self.put_back(head, dut, next(empties))
            else:
                stages += self.put_back(head, dut, ng_next)
                ng_next += 1
        for head, cell in task.picks:
            stages += self.pick_from_tray(head, cell)
        return stages
