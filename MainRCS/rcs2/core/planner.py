"""Planner of the tray flow: decides what the (single) robot does next. Pure logic: no I/O, no threads, no clock of its own.

Situation: H suction heads (8), N test boxes (10), an input tray full of untested products, an NG tray. The robot does ONE task
at a time, and a task is never interrupted, so the planner is asked again every time a task ends (or a box changes state).

Goal: **no box stays idle for long.** A box is idle from the moment its test finished (or it became free) until the robot has
put a new product in it. The rules, in order:

 1. SERVICE the box that has been idle the longest and that can be served NOW. Serving a box = (take the tested product out
    with a free head, if there is one) + (put a product from another head in). The product put in is, in this order, a product
    that failed a test and must be tested in ANOTHER box (never the same box twice), then a fresh product.
 2. If no box can be served because no head holds a suitable product -> go to the tray and fetch products (as many as there are boxes waiting,
    but never take the last free head: one head must stay free to take a tested product out of a box, except when every box is empty).
 3. If a box needs a free head and all heads are full -> go to the tray and put the tested products away first.
 4. If every box is busy testing (the robot has time): put the tested products away and top the heads up with fresh products so that the
    next box that finishes can be served at once.
 5. A visit to the tray does both: it puts tested products away first, then fetches fresh ones into the heads that became free.
 6. WHEN products are put away: only when every product on the heads is already tested (pass or ng, nothing left to put in a box), or when
    every box is busy testing. In between, tested products simply stay on their heads; the only exceptions are a box that needs a free head
    when none is left, and the end of the work (nothing fresh left): then they are put away too.
 7. FILL THE HEADS: whenever the robot is at the tray it fills every free head with fresh products (except the `keep_free` one) instead of
    fetching only what the waiting boxes need - a second trip to the tray costs more than a head that carries a product for a while.
    (`fill_heads` = False gives the old behaviour: fetch only what the waiting boxes need.)
 8. A task is kept short (`max_pick` / `max_sort`) so that a box that finishes meanwhile does not wait for a long trip.

The planner only reads the world (`World`) and returns a task; applying the result to the books (dut.DutBook) is the caller's job,
step by step, as the robot really does it.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from . import dut as D


# ---------------------------------------------------------------------------------------------------------------- #
# what the planner looks at
# ---------------------------------------------------------------------------------------------------------------- #
@dataclass
class FixtureView:
    number: int
    enabled: bool = True
    connected: bool = True
    ready: bool = True                 # the ATS can accept a product (it said "waiting for DUT")
    dut: Optional[D.Dut] = None        # the product inside (being tested, or tested and waiting to be taken out)
    finished: bool = False             # the result of `dut` is in
    idle_since: float = 0.0            # since when the box waits for the robot (result time, or the time it became free)

    @property
    def available(self):
        return self.enabled and self.connected and self.ready

    @property
    def needs_service(self):
        return self.available and (self.dut is None or self.finished)

    @property
    def has_dut(self):
        return self.dut is not None

    @property
    def can_take_out(self):
        """A tested product waits in a box that is no longer in use (disabled / offline): it must still come out."""
        return self.has_dut and self.finished and not self.available


@dataclass
class World:
    now: float
    heads: Dict[int, Optional[D.Dut]]          # head number -> product it holds (None = free)
    fixtures: List[FixtureView]
    book: D.DutBook

    def eligible_boxes(self):
        """Numbers of the boxes a retest may still go to."""
        return [f.number for f in self.fixtures if f.available]


@dataclass
class PlannerConfig:
    keep_free: int = 1                 # heads kept free for taking a tested product out of a box (not needed while all boxes are empty)
    max_pick: int = 8                  # products fetched in one visit to the tray
    max_sort: int = 8                  # products put away in one visit to the tray
    pick_ahead: int = 0                # extra fresh products fetched beyond the boxes that wait (0 = only what is needed)
    top_up_when_idle: bool = True      # fill the heads with fresh products while every box is testing
    fill_heads: bool = True            # a visit to the tray fills ALL free heads (keeping `keep_free`) instead of fetching only what the
                                       # waiting boxes need: fewer trips between the tray and the boxes


# ---------------------------------------------------------------------------------------------------------------- #
# tasks
# ---------------------------------------------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ServiceTask:
    """At box `fixture`: take the tested product out with `take_head` (None = the box is empty) and put in the product of `place_head`."""
    fixture: int
    place_head: int
    place_dut: int
    take_head: Optional[int] = None
    take_dut: Optional[int] = None
    reason: str = ""
    kind = "service"


@dataclass(frozen=True)
class TakeTask:
    """At box `fixture`: only take the tested product out (nothing left to put in)."""
    fixture: int
    head: int
    dut: int
    reason: str = ""
    kind = "take"


@dataclass(frozen=True)
class TrayTask:
    """One visit to the trays. `sorts` = ((head, dut id), ...) put away first: a passed product goes into its own cell of the input
    tray, a failed one into the next cell of the NG tray. `picks` = ((head, input cell), ...) fetched afterwards."""
    sorts: Tuple[Tuple[int, int], ...] = ()
    picks: Tuple[Tuple[int, int], ...] = ()
    reason: str = ""
    kind = "tray"


Task = object


# ---------------------------------------------------------------------------------------------------------------- #
class Planner:
    def __init__(self, cfg: Optional[PlannerConfig] = None):
        self.cfg = cfg or PlannerConfig()
        self.reason = ""                       # why the last call returned what it returned (also when it returned None)

    # ---- helpers ------------------------------------------------------------------------------------ #
    @staticmethod
    def _loaded(w):
        return [(k, d) for k, d in sorted(w.heads.items()) if d is not None]

    @staticmethod
    def _free(w):
        return [k for k, d in sorted(w.heads.items()) if d is None]

    def _reserve(self, w):
        """Heads that must stay free: none while every box is empty, otherwise `keep_free`."""
        return self.cfg.keep_free if any(f.has_dut for f in w.fixtures) else 0

    @staticmethod
    def _dut_for(fixture, loaded):
        """The head whose product should go into `fixture`: a product to retest first, then a fresh one (lowest head first)."""
        usable = [(0 if d.need == D.RETEST else 1, k, d) for k, d in loaded if d.can_test_in(fixture.number)]
        if not usable:
            return None
        _, k, d = min(usable, key=lambda t: (t[0], t[1]))
        return k, d

    def _sortable(self, w):
        """Heads whose product can be put away now: passed ones while there is room for them (output trays / empty input cells) and
        failed ones while the NG tray has room."""
        out, ng_room, pass_room = [], w.book.ng_free, w.book.pass_free
        for k, d in self._loaded(w):
            if d.need == D.RETURN and pass_room > 0:
                out.append((k, d))
                pass_room -= 1
            elif d.need == D.NG and ng_room > 0:
                out.append((k, d))
                ng_room -= 1
        return out[:self.cfg.max_sort]

    def _tray_visit(self, w, want_fresh, why, sort="auto"):
        """A visit to the tray: put away the tested products, then fetch up to `want_fresh` fresh ones. None if useless.
        sort = "auto": put away only when every product on the heads is tested (pass / ng); "always": put away whatever can be."""
        untested = any(d.need in (D.TEST, D.RETEST) for _, d in self._loaded(w))
        sorts = self._sortable(w) if (sort == "always" or not untested) else []
        free_after = sorted(set(self._free(w)) | {k for k, _ in sorts})
        room = len(free_after) - self._reserve(w)
        fill = self.cfg.fill_heads and (want_fresh > 0 or self.cfg.top_up_when_idle)    # (top_up off: a trip that fetches nothing stays so)
        wanted = self.cfg.max_pick if fill else want_fresh                          # at the tray: fill the heads, do not come back for more
        n = max(0, min(room, wanted, self.cfg.max_pick, w.book.fresh_left))
        heads = free_after[:n]
        cells = w.book.peek_fresh(n)
        picks = tuple(zip(heads, cells))
        if not sorts and not picks:
            return None
        return TrayTask(sorts=tuple((k, d.id) for k, d in sorts), picks=picks, reason=why)

    # ---- the decision ------------------------------------------------------------------------------- #
    def next_task(self, w: World):
        """The next task for the robot, or None (nothing useful to do now, or nothing left). `self.reason` says why."""
        if w.book.finished():
            self.reason = "finished"
            return None
        loaded, free = self._loaded(w), self._free(w)
        needy = sorted((f for f in w.fixtures if f.needs_service), key=lambda f: (f.idle_since, f.number))

        # 1. serve the box that has waited longest and can be served now
        for f in needy:
            if f.has_dut and not free:
                continue                                          # tested product inside and no free head to take it out
            choice = self._dut_for(f, loaded)
            if choice is None:
                continue
            place_head, placed = choice
            take_head = free[0] if f.has_dut else None
            self.reason = "service box %d (idle %.1fs)" % (f.number, w.now - f.idle_since)
            return ServiceTask(f.number, place_head, placed.id, take_head, f.dut.id if f.has_dut else None, self.reason)

        if free:                                                      # tested products in boxes that were switched off
            for f in w.fixtures:
                if f.can_take_out:
                    self.reason = "take the tested product out of box %d (box not in use)" % f.number
                    return TakeTask(f.number, free[0], f.dut.id, self.reason)

        if needy:
            waiting_full = [f for f in needy if f.has_dut]
            # box(es) wait but nothing suitable is on a head: fetch products (if every head is full, put some away first)
            fresh_wanted = max(0, len(needy) - sum(1 for _, d in loaded if d.need in (D.TEST, D.RETEST))) + self.cfg.pick_ahead
            if w.book.fresh_left > 0 and fresh_wanted == 0 and not self._loaded_usable(needy, loaded):
                fresh_wanted = 1                                  # products on the heads are all unsuitable for the waiting boxes
            why = "fetch for %d waiting box(es)" % len(needy)
            visit = self._tray_visit(w, fresh_wanted, why) if fresh_wanted else None
            if fresh_wanted and w.book.fresh_left and (visit is None or not visit.picks) and self._sortable(w):
                forced = self._tray_visit(w, fresh_wanted, why, "always")        # no room to fetch: put products away to make room
                if forced is not None and (forced.picks or visit is None):
                    visit = forced
            if visit is None and waiting_full and not free:
                visit = self._tray_visit(w, 0, "free a head for box %d" % waiting_full[0].number, "always")
            if visit is not None:
                self.reason = visit.reason
                return visit
            # nothing can be fetched: no fresh products left. Take tested products out so retests can go into those boxes
            if w.book.fresh_left == 0 and free:
                for f in needy:
                    if f.has_dut:
                        self.reason = "take the tested product out of box %d (nothing left to put in)" % f.number
                        return TakeTask(f.number, free[0], f.dut.id, self.reason)
            # nothing can be put in the waiting boxes (no fresh product left): do not let that block the tidying up
            visit = self._tray_visit(w, 0, "nothing to put in the waiting boxes: put the tested products away", "always")
            if visit is not None:
                self.reason = visit.reason
                return visit
            self.reason = "boxes wait but no suitable product / free head (waiting for results)"
            return None

        # 4. every box is busy: use the time
        want = self.cfg.max_pick if self.cfg.top_up_when_idle else 0
        visit = self._tray_visit(w, want, "every box is testing: put away the tested products and top up the heads", "always")
        if visit is not None:
            self.reason = visit.reason
            return visit
        self.reason = "nothing to do" if not w.book.finished() else "finished"
        return None

    @staticmethod
    def _loaded_usable(needy, loaded):
        return any(d.can_test_in(f.number) for f in needy for _, d in loaded)
