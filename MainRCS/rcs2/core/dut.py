"""Products (DUTs) of the tray flow: where each one is, how often it was tested and in which boxes, and what must happen to it next.

Cells of the INPUT tray have only three states:  FRESH (an untested product), EMPTY (nothing), PASS (a tested, passed product).
A cell of the NG tray is empty or holds an NG product (filled in reading order: `ng_used` cells are full).
OUTPUT trays (optional, settings.json -> trays -> output1 / output2) take the passed products ONLY: output 1 is filled first (reading order),
when it is full output 2; `out_used[k]` cells of output tray k are full. Without output trays a passed product goes back into the first
empty cell of the input tray (state PASS of that cell).

Life of a DUT
    cell FRESH --take_from_tray--> cell EMPTY, product on head k --place_in_box--> in box n (testing)
         --result()--> PASS  : stays in the box until taken out, then put into the FIRST EMPTY cell of the input tray (it becomes PASS)
                       RETEST: taken out, then tested again in ANOTHER box (never one it was already tested in)
                       NG    : (the last allowed test failed, or no other box left) taken out, then into the next cell of the NG tray
Test attempts are counted per DUT: at most `max_attempts` tests (settings.json -> flow.max_attempts), every one in a different box.

`need` tells the planner what the DUT is waiting for:
    TEST     a fresh product, to be placed in any free box
    RETEST   failed a test, to be placed in a box it has not been tested in
    TESTING  inside a box, the test is running
    RETURN   passed: to go back to its cell of the input tray
    NG       failed for good: to go into the NG tray
    DONE     back in its cell (passed) / in the NG tray (failed)
This module only keeps the books: it does not move anything and does not decide who goes where (that is planner.py).
"""
from collections import deque

# ---- what a DUT is waiting for ---------------------------------------------------------------------------------- #
TEST, RETEST, TESTING, RETURN, NG, DONE = "TEST", "RETEST", "TESTING", "RETURN", "NG", "DONE"
FRESH, EMPTY, PASS = "fresh", "empty", "pass"          # the three states of a cell of the input tray
FAIL_LABELS = ("NG", "RETEST", "WARNING")          # results that count as a failed test (FQC counts as a pass)
HEAD, BOX, TRAY, NG_TRAY, OUT_TRAY = "head", "box", "tray", "ng", "out"


class DutError(Exception):
    """An impossible book-keeping step (a bug in the caller, or a robot step that did not do what was planned)."""


class Dut:
    def __init__(self, id, origin):
        self.id = id
        self.origin = origin                  # input cell it was picked from (reading order); where it is put back is another matter
        self.sn = ""
        self.location = (TRAY, origin)        # (TRAY, cell) | (HEAD, k) | (BOX, n) | (NG_TRAY, cell) | (OUT_TRAY, (output tray index, cell))
        self.need = TEST
        self.attempts = []                    # [(box, label, seconds)] one per finished test
        self.testing_in = None                # box of the test that is running / just finished
        self.final = ""                       # "" while undecided, then "PASS" or "NG"
        self.ng_cell = None

    @property
    def tests_made(self):
        return len(self.attempts)

    @property
    def tested_boxes(self):
        return {a[0] for a in self.attempts} | ({self.testing_in} if self.testing_in is not None else set())

    @property
    def head(self):
        return self.location[1] if self.location[0] == HEAD else None

    @property
    def box(self):
        return self.location[1] if self.location[0] == BOX else None

    def can_test_in(self, box):
        """May this DUT be placed in `box` for a (re)test? (a DUT that waits for a test and was not tested there yet)"""
        return self.need in (TEST, RETEST) and box not in self.tested_boxes

    def __repr__(self):
        return "Dut(%d cell=%d %s %s tests=%d)" % (self.id, self.origin, self.location, self.need, self.tests_made)


class DutBook:
    """All DUTs of the input tray and where they are. `capacity` = number of cells of the input tray."""

    def __init__(self, capacity, max_attempts=3, ng_capacity=0, out_capacity=()):
        if max_attempts < 1:
            raise DutError("max_attempts must be >= 1")
        self.capacity = capacity
        self.max_attempts = max_attempts
        self.ng_capacity = ng_capacity
        self.out_capacity = list(out_capacity)          # cells of output tray 1, 2 ... (empty = no output trays)
        self.out_used = [0] * len(self.out_capacity)    # cells of each output tray already filled
        self.cells = [FRESH] * capacity                 # state of every cell of the input tray (reading order)
        self.duts = {}                                  # id -> Dut (created when a product is taken from its cell)
        self.ng_used = 0                                # cells of the NG tray already filled
        self._next_id = 1

    # ---- queries -------------------------------------------------------------------------------- #
    @property
    def fresh(self):
        """Cells (reading order) that still hold an untested product."""
        return [i for i, c in enumerate(self.cells) if c == FRESH]

    def peek_fresh(self, n):
        """The first n cells (reading order) that still hold an untested product."""
        return self.fresh[:max(0, n)]

    @property
    def fresh_left(self):
        return self.cells.count(FRESH)

    def empty_cells(self, n=None):
        """Empty cells of the input tray in reading order (the first one is where the next passed product goes)."""
        out = [i for i, c in enumerate(self.cells) if c == EMPTY]
        return out if n is None else out[:max(0, n)]

    @property
    def ng_free(self):
        return max(0, self.ng_capacity - self.ng_used)

    @property
    def has_outputs(self):
        return bool(self.out_capacity)

    @property
    def out_free(self):
        return sum(c - u for c, u in zip(self.out_capacity, self.out_used))

    @property
    def pass_free(self):
        """Room for passed products: the free cells of the output trays, or (no output trays) the empty cells of the input tray."""
        return self.out_free if self.has_outputs else self.cells.count(EMPTY)

    def output_slots(self, n=None):
        """Free cells of the output trays in the order they are used: [(output tray index, cell), ...] - tray 1 first."""
        out = [(k, c) for k, (cap, used) in enumerate(zip(self.out_capacity, self.out_used)) for c in range(used, cap)]
        return out if n is None else out[:max(0, n)]

    def on_head(self, k):
        return next((d for d in self.duts.values() if d.location == (HEAD, k)), None)

    def in_box(self, n):
        return next((d for d in self.duts.values() if d.location == (BOX, n)), None)

    def active(self):
        """DUTs that are not DONE (somewhere between being picked and being put away)."""
        return [d for d in self.duts.values() if d.need != DONE]

    def finished(self):
        return self.fresh_left == 0 and not self.active()

    def stats(self):
        done = [d for d in self.duts.values() if d.need == DONE]
        return {"cells": self.capacity, "fresh": self.fresh_left, "empty": self.cells.count(EMPTY), "in_flight": len(self.active()),
                "passed": sum(1 for d in done if d.final == "PASS"), "ng": sum(1 for d in done if d.final == "NG"),
                "out_used": list(self.out_used),
                "tests": sum(d.tests_made for d in self.duts.values()),
                "retests": sum(max(0, d.tests_made - 1) for d in self.duts.values())}

    # ---- physical events (call these when the robot step has really finished) ---------------------- #
    def take_from_tray(self, cell, head):
        """The head `head` picked the product of input cell `cell`."""
        if not 0 <= cell < self.capacity or self.cells[cell] != FRESH:
            raise DutError("input cell %r has no untested product (empty or already taken?)" % (cell,))
        self.cells[cell] = EMPTY
        d = Dut(self._next_id, cell)
        self._next_id += 1
        d.location = (HEAD, head)
        self.duts[d.id] = d
        return d

    def place_in_box(self, dut, box):
        """The DUT was put into box `box` and its test starts."""
        if dut.location[0] != HEAD:
            raise DutError("%r is not on a head" % dut)
        if not dut.can_test_in(box):
            raise DutError("%r cannot be tested in box %d (needs %s, tested in %s)" % (dut, box, dut.need, sorted(dut.tested_boxes)))
        dut.location, dut.need, dut.testing_in = (BOX, box), TESTING, box
        return dut

    def result(self, dut, label, seconds, eligible_boxes):
        """The test in the box finished. `label` = PASS | NG | RETEST | WARNING | FQC; `eligible_boxes` = the boxes a retest could
        still go to (enabled and connected). Returns the verdict: "PASS", "RETEST" (test again elsewhere) or "NG" (final)."""
        if dut.need != TESTING or dut.location[0] != BOX:
            raise DutError("%r is not being tested" % dut)
        box = dut.testing_in
        dut.attempts.append((box, label, seconds))
        dut.testing_in = None
        if label not in FAIL_LABELS:
            dut.need, dut.final = RETURN, "PASS"
            return "PASS"
        others = [b for b in eligible_boxes if b not in dut.tested_boxes]
        if dut.tests_made < self.max_attempts and others:
            dut.need = RETEST
            return "RETEST"
        dut.need, dut.final = NG, "NG"
        return "NG"

    def take_from_box(self, dut, head):
        """The tested DUT was taken out of its box by head `head`."""
        if dut.location[0] != BOX or dut.need == TESTING:
            raise DutError("%r is not a tested DUT inside a box" % dut)
        dut.location = (HEAD, head)
        return dut

    def return_to_tray(self, dut, cell=None):
        """A passed DUT was put into an empty cell of the input tray (the first empty one unless `cell` says which); returns its index."""
        if dut.need != RETURN or dut.location[0] != HEAD:
            raise DutError("%r is not a passed DUT on a head" % dut)
        if cell is None:
            empties = self.empty_cells(1)
            if not empties:
                raise DutError("the input tray has no empty cell")
            cell = empties[0]
        if not 0 <= cell < self.capacity or self.cells[cell] != EMPTY:
            raise DutError("input cell %r is not empty" % (cell,))
        self.cells[cell] = PASS
        dut.location, dut.need = (TRAY, cell), DONE
        return cell

    def put_in_output(self, dut, tray=None, cell=None):
        """A passed DUT was put into the next free cell of the output trays (tray 1 first); returns (tray index, cell).
        `tray` / `cell` say where the robot really put it: it must be the next free cell of that tray (cells are used in reading order)."""
        if dut.need != RETURN or dut.location[0] != HEAD:
            raise DutError("%r is not a passed DUT on a head" % dut)
        if not self.has_outputs:
            raise DutError("there are no output trays")
        slots = self.output_slots(1)
        if not slots:
            raise DutError("the output trays are full")
        if tray is None:
            tray, cell = slots[0]
        if (tray, cell) != slots[0]:                                  # output 1 first; output 2 only while output 1 is full
            raise DutError("output tray %r cell %r is not the next free cell %r" % (tray, cell, slots[0]))
        self.out_used[tray] += 1
        dut.location, dut.need = (OUT_TRAY, (tray, cell)), DONE
        return tray, cell

    def put_in_ng(self, dut):
        """A failed DUT was put into the next free cell of the NG tray; returns that cell index."""
        if dut.need != NG or dut.location[0] != HEAD:
            raise DutError("%r is not a failed DUT on a head" % dut)
        if self.ng_used >= self.ng_capacity:
            raise DutError("the NG tray is full")
        cell = self.ng_used
        self.ng_used += 1
        dut.location, dut.need, dut.ng_cell = (NG_TRAY, cell), DONE, cell
        return cell

    # ---- rule: a retest with no box left is a final NG --------------------------------------------- #
    def settle_stuck(self, eligible_boxes):
        """DUTs waiting for a retest that has no box left to go to (all eligible boxes already tested it) become final NG.
        Returns the DUTs that changed."""
        changed = []
        for d in self.duts.values():
            if d.need == RETEST and not [b for b in eligible_boxes if b not in d.tested_boxes]:
                d.need, d.final = NG, "NG"
                changed.append(d)
        return changed
