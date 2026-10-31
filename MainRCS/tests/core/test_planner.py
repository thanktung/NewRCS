"""Planner of the tray flow: single decisions, and whole runs of the what-if simulator (invariants + idle time of the boxes)."""
import unittest

from rcs2.core import dut as D
from rcs2.core.planner import (FixtureView, Planner, PlannerConfig, ServiceTask, TakeTask, TrayTask, World)
from rcs2.tools import flow_sim


class Scene:
    """A small world to build a situation by hand."""

    def __init__(self, boxes=4, heads=4, cells=20, ng_cells=10, now=100.0, out=(), **cfg):
        self.book = D.DutBook(cells, 3, ng_cells, out)
        self.heads = {k: None for k in range(1, heads + 1)}
        self.fixtures = [FixtureView(n) for n in range(1, boxes + 1)]
        self.now = now
        self.planner = Planner(PlannerConfig(**cfg))

    def fx(self, n):
        return next(f for f in self.fixtures if f.number == n)

    def fresh_on(self, head, cell=None):
        cell = self.book.peek_fresh(1)[0] if cell is None else cell
        d = self.book.take_from_tray(cell, head)
        self.heads[head] = d
        return d

    def testing(self, box, since=0.0):
        d = self.book.take_from_tray(self.book.peek_fresh(1)[0], 99)
        self.book.place_in_box(d, box)
        f = self.fx(box)
        f.dut, f.finished = d, False
        return d

    def finish(self, box, label="PASS", idle_since=0.0):
        f = self.fx(box)
        self.book.result(f.dut, label, 10.0, [x.number for x in self.fixtures])
        f.finished, f.idle_since = True, idle_since
        return f.dut

    def task(self):
        return self.planner.next_task(World(self.now, dict(self.heads), self.fixtures, self.book))


class SortPolicyTests(unittest.TestCase):
    """Tested products stay on their heads, and go to the tray only when (a) every product on the heads is tested (pass / ng) or
    (b) every box is busy testing - plus the two exceptions: no room at all, and nothing left to put in the boxes."""

    @staticmethod
    def on_head(s, head, need, attempts=()):
        """A product on `head` in the given state; `attempts` = [(box, label, seconds)] of the tests it already had."""
        d = s.book.take_from_tray(s.book.peek_fresh(1)[0], head)
        d.need, d.attempts = need, list(attempts)
        d.final = {D.RETURN: "PASS", D.NG: "NG"}.get(need, "")
        s.heads[head] = d
        return d

    def test_every_product_on_the_heads_is_tested_so_they_are_put_away_while_fetching(self):
        s = Scene(boxes=3, heads=3, cells=20)
        self.on_head(s, 1, D.RETURN, [(1, "PASS", 9.0)])
        self.on_head(s, 2, D.NG, [(1, "NG", 9.0), (2, "NG", 9.0), (3, "NG", 9.0)])
        t = s.task()
        self.assertIsInstance(t, TrayTask)
        self.assertEqual(sorted(k for k, _ in t.sorts), [1, 2])
        self.assertTrue(t.picks)

    def test_a_product_that_still_has_to_go_into_a_box_keeps_the_tested_ones_on_their_heads(self):
        s = Scene(boxes=2, heads=4, cells=20)
        self.on_head(s, 1, D.RETURN, [(1, "PASS", 9.0)])                            # head 1: passed, waits
        self.on_head(s, 2, D.RETEST, [(1, "NG", 9.0)])                              # head 2: must be tested again, but not in box 1
        s.testing(2)                                                                # box 2 busy; box 1 is empty and waits for a FRESH product
        t = s.task()
        self.assertIsInstance(t, TrayTask)
        self.assertEqual(t.sorts, ())                                               # the passed product is NOT put away on this trip
        self.assertEqual(len(t.picks), 1)

    def test_a_trip_with_no_room_puts_the_tested_products_away_to_make_room(self):
        s = Scene(boxes=2, heads=2, cells=20)
        self.on_head(s, 1, D.RETURN, [(1, "PASS", 9.0)])
        self.on_head(s, 2, D.RETEST, [(1, "NG", 9.0)])
        s.testing(2)
        t = s.task()                                                                # both heads are full and box 1 needs a fresh product
        self.assertIsInstance(t, TrayTask)
        self.assertEqual([k for k, _ in t.sorts], [1])
        self.assertEqual(t.picks, ())

    def test_when_every_box_is_testing_the_robot_tidies_up_whatever_is_on_the_heads(self):
        s = Scene(boxes=4, heads=4, cells=20)
        for n in (1, 2, 3, 4):
            s.testing(n)
        self.on_head(s, 1, D.RETURN, [(1, "PASS", 9.0)])
        self.on_head(s, 2, D.TEST)                                                  # a fresh product is on head 2 as well
        t = s.task()
        self.assertIsInstance(t, TrayTask)
        self.assertEqual([k for k, _ in t.sorts], [1])                              # the passed product goes away although head 2 has a fresh one


class OutputRoomTests(unittest.TestCase):
    """With output trays a passed product can only be put away while an output tray has room for it."""

    @staticmethod
    def passed_on_head(s, head):
        d = s.book.take_from_tray(s.book.peek_fresh(1)[0], head)
        d.need, d.final = D.RETURN, "PASS"
        s.heads[head] = d
        return d

    def every_box_testing(self, **kw):
        s = Scene(boxes=3, heads=4, **kw)
        for n in (1, 2, 3):
            s.testing(n)
        return s

    def test_passed_products_are_put_away_into_the_output_tray(self):
        s = self.every_box_testing(out=[3])
        self.passed_on_head(s, 1)
        t = s.task()
        self.assertIsInstance(t, TrayTask)
        self.assertEqual([k for k, _ in t.sorts], [1])

    def test_no_room_in_any_output_tray_means_the_passed_product_stays_on_its_head(self):
        s = self.every_box_testing(out=[1, 1], top_up_when_idle=False)
        s.book.out_used = [1, 1]
        self.passed_on_head(s, 1)
        self.assertIsNone(s.task())                                                 # nothing can be done until the operator empties a tray

    def test_only_as_many_passed_products_as_there_is_room_are_put_away(self):
        s = self.every_box_testing(out=[1, 1])
        s.book.out_used = [1, 0]                                                    # one free cell left
        self.passed_on_head(s, 1)
        self.passed_on_head(s, 2)
        t = s.task()
        self.assertEqual([k for k, _ in t.sorts], [1])

    def test_ng_products_do_not_use_the_output_trays(self):
        s = self.every_box_testing(out=[1])
        s.book.out_used = [1]
        d = s.book.take_from_tray(s.book.peek_fresh(1)[0], 1)
        d.need, d.final = D.NG, "NG"
        s.heads[1] = d
        t = s.task()
        self.assertEqual([k for k, _ in t.sorts], [1])                              # the NG tray has room: it goes there


class DecisionTests(unittest.TestCase):
    def test_start_with_all_boxes_empty_fetches_a_full_load_of_products(self):
        s = Scene(boxes=10, heads=8, cells=40)
        t = s.task()
        self.assertIsInstance(t, TrayTask)
        self.assertEqual(t.sorts, ())
        self.assertEqual(t.picks, tuple((k, k - 1) for k in range(1, 9)))          # all 8 heads, cells 0..7 in reading order

    def test_with_boxes_in_use_one_head_stays_free(self):
        s = Scene(boxes=4, heads=4)
        s.testing(1)
        s.fx(2).enabled = False
        t = s.task()                                                                # boxes 3, 4 empty and waiting
        self.assertIsInstance(t, TrayTask)
        self.assertEqual(len(t.picks), 3)                                           # at the tray: fill every free head except the reserved one
        s1 = Scene(boxes=4, heads=4, fill_heads=False)
        s1.testing(1)
        s1.fx(2).enabled = False
        self.assertEqual(len(s1.task().picks), 2)                                   # (old behaviour: only what the 2 waiting boxes need)
        s2 = Scene(boxes=6, heads=4)
        s2.testing(1)
        self.assertEqual(len(s2.task().picks), 3)                                   # 5 boxes wait but only 3 heads may be filled

    def test_a_visit_to_the_tray_fills_the_heads_so_that_no_second_trip_is_needed(self):
        s = Scene(boxes=3, heads=8, cells=40)
        s.testing(1)
        t = s.task()                                                                # boxes 2 and 3 wait, 8 heads are free
        self.assertEqual([k for k, _ in t.picks], [1, 2, 3, 4, 5, 6, 7])           # 7 products: all heads but the reserved one
        self.assertEqual([c for _, c in t.picks], [1, 2, 3, 4, 5, 6, 7])           # the next cells of the tray, in reading order

    def test_a_trip_that_fetches_nothing_stays_so_when_top_up_is_off(self):
        s = Scene(boxes=3, heads=4, top_up_when_idle=False)
        for n in (1, 2, 3):
            s.testing(n)
        d = s.fresh_on(1)
        d.need, d.final = D.RETURN, "PASS"
        t = s.task()                                                                # every box is testing: put the passed product away, nothing more
        self.assertIsInstance(t, TrayTask)
        self.assertEqual(t.picks, ())

    def test_serves_the_box_that_waited_longest(self):
        s = Scene()
        for n in (1, 2, 3, 4):
            s.testing(n)
        s.fresh_on(1)
        s.fresh_on(2)
        s.finish(3, idle_since=50.0)
        s.finish(2, idle_since=20.0)                                                # waits longer than box 3
        t = s.task()
        self.assertIsInstance(t, ServiceTask)
        self.assertEqual((t.fixture, t.take_head, t.place_head), (2, 3, 1))         # take with the first free head, place head 1
        self.assertEqual(t.take_dut, s.fx(2).dut.id)

    def test_swap_needs_a_free_head_otherwise_another_box_is_served(self):
        s = Scene(boxes=3, heads=2)
        s.testing(1)
        s.finish(1, idle_since=10.0)
        s.fresh_on(1)
        s.fresh_on(2)                                                               # no free head
        t = s.task()
        self.assertIsInstance(t, ServiceTask)
        self.assertEqual(t.fixture, 2)                                              # empty box 2 is served; box 1 cannot be (no free head)
        self.assertIsNone(t.take_head)

    def test_all_heads_full_of_tested_products_means_put_them_away_first(self):
        s = Scene(boxes=2, heads=2)
        s.testing(1)
        s.finish(1)
        s.testing(2)
        s.finish(2)
        a, b = s.fresh_on(1), s.fresh_on(2)                                          # heads hold tested products waiting to be put away
        a.need = D.RETURN
        b.need = D.NG
        t = s.task()
        self.assertIsInstance(t, TrayTask)
        self.assertEqual({d for _, d in t.sorts}, {a.id, b.id})
        self.assertEqual(len(t.picks), 1)                                           # both heads are free after the sort; one stays free

    def test_a_failed_product_goes_to_a_box_it_has_not_been_in_and_before_fresh_ones(self):
        s = Scene(boxes=3, heads=3)
        s.testing(1)
        s.finish(1, "NG")                                                           # failed in box 1 -> RETEST
        failed = s.fx(1).dut
        s.book.take_from_box(failed, 1)
        s.fx(1).dut, s.fx(1).finished = None, False
        s.heads[1] = failed
        fresh = s.fresh_on(2)
        s.testing(3)
        t = s.task()                                                                # box 1 (empty) and box 2 (empty) wait; 3 is testing
        self.assertIsInstance(t, ServiceTask)
        self.assertEqual(t.fixture, 1)
        self.assertEqual(t.place_head, 2)                                           # box 1: the retest product is NOT allowed -> fresh one
        s.fx(1).idle_since = 90.0
        s.fx(2).idle_since = 10.0                                                   # now box 2 waits longer
        t = s.task()
        self.assertEqual((t.fixture, t.place_head), (2, 1))                         # retest product first, in a box it never saw

    def test_nothing_to_do_while_every_box_tests_and_heads_are_ready(self):
        s = Scene(boxes=2, heads=3, cells=4)
        s.testing(1)
        s.testing(2)
        s.fresh_on(1)
        s.fresh_on(2)                                                               # the only fresh products are on the heads
        self.assertIsNone(s.task())

    def test_idle_robot_tidies_up_and_tops_the_heads_up(self):
        s = Scene(boxes=2, heads=4, cells=10)
        s.testing(1)
        s.testing(2)
        d = s.fresh_on(1)
        d.need, d.final = D.RETURN, "PASS"                                          # a tested product waiting on head 1
        t = s.task()
        self.assertIsInstance(t, TrayTask)
        self.assertEqual(t.sorts, ((1, d.id),))
        self.assertEqual(len(t.picks), 3)                                           # 4 heads - 1 reserve, head 1 is free again after the sort

    def test_top_up_can_be_switched_off(self):
        s = Scene(boxes=2, heads=4, cells=10, top_up_when_idle=False)
        s.testing(1)
        s.testing(2)
        self.assertIsNone(s.task())

    def test_failed_products_are_not_sorted_while_the_ng_tray_is_full(self):
        s = Scene(boxes=2, heads=2, cells=4, ng_cells=0)
        s.testing(1)
        s.testing(2)
        d = s.fresh_on(1)
        d.need, d.final = D.NG, "NG"
        t = s.task()
        self.assertTrue(t is None or not t.sorts)

    def test_end_game_takes_the_last_tested_products_out(self):
        s = Scene(boxes=2, heads=2, cells=1)
        s.testing(1)
        s.finish(1, "PASS", idle_since=5.0)                                         # the only product, tested, still in the box
        t = s.task()
        self.assertIsInstance(t, TakeTask)
        self.assertEqual((t.fixture, t.head), (1, 1))

    def test_finished_when_everything_is_put_away(self):
        s = Scene(boxes=2, heads=2, cells=1)
        d = s.testing(1)
        s.finish(1)
        s.book.take_from_box(d, 1)
        s.book.return_to_tray(d)
        s.fx(1).dut = None
        s.fx(1).finished = False
        s.fx(2).enabled = False
        self.assertIsNone(s.task())
        self.assertEqual(s.planner.reason, "finished")

    def test_disabled_or_disconnected_boxes_are_left_alone(self):
        s = Scene(boxes=3, heads=3, cells=9, top_up_when_idle=False)
        s.fx(1).enabled = False
        s.fx(2).connected = False
        s.fx(3).ready = False
        s.fresh_on(1)
        self.assertIsNone(s.task())                                                 # nothing available to serve; products are ready already


class RunTests(unittest.TestCase):
    """Whole runs on the what-if simulator: the invariants are checked after every task (flow_sim.FlowSim.check)."""

    def run_sim(self, **kw):
        rep, sim = flow_sim.simulate(**kw)
        self.assertFalse(rep["stuck"], sim.planner.reason)
        self.assertEqual(rep["passed"] + rep["ng"], rep["products"])
        self.assertTrue(sim.book.finished())
        return rep, sim

    def test_every_product_ends_put_away_for_many_situations(self):
        for kw in ({}, {"pass_rate": 0.5, "seed": 2}, {"pass_rate": 0.95, "seed": 9}, {"boxes": 3, "heads": 8, "cells": 30},
                   {"boxes": 10, "heads": 4, "cells": 40, "seed": 5}, {"boxes": 2, "cells": 12, "pass_rate": 0.7},
                   {"boxes": 12, "heads": 8, "cells": 60, "test_time": 30.0}):
            with self.subTest(**kw):
                self.run_sim(**kw)

    def test_all_failures_are_tested_three_times_and_end_in_the_ng_tray(self):
        rep, sim = self.run_sim(boxes=10, cells=24, pass_rate=0.0)
        self.assertEqual((rep["passed"], rep["ng"], rep["tests"], rep["retests"]), (0, 24, 72, 48))
        for d in sim.book.duts.values():
            self.assertEqual(len({a[0] for a in d.attempts}), 3)                    # three DIFFERENT boxes
            self.assertEqual(d.location[0], D.NG_TRAY)

    def test_with_two_boxes_a_failure_has_only_one_other_box_so_it_is_tested_twice(self):
        rep, sim = self.run_sim(boxes=2, cells=10, pass_rate=0.0)
        self.assertEqual((rep["ng"], rep["tests"]), (10, 20))

    def test_passed_products_go_into_empty_cells_of_the_input_tray(self):
        rep, sim = self.run_sim(cells=40, pass_rate=0.8, seed=7)
        cells = sim.book.cells
        for d in sim.book.duts.values():
            if d.final == "PASS":
                self.assertEqual(d.location[0], D.TRAY)
                self.assertEqual(cells[d.location[1]], D.PASS)
        self.assertEqual(cells.count(D.PASS), rep["passed"])
        self.assertEqual(cells.count(D.FRESH), 0)
        self.assertEqual(cells.count(D.EMPTY), rep["ng"])                          # only the cells of the NG products stay empty
        self.assertEqual([i for i, c in enumerate(cells) if c == D.PASS], list(range(rep["passed"])))      # first empty cells first: no holes

    def test_a_head_always_stays_free_when_products_are_fetched_for_busy_boxes(self):
        rep, sim = self.run_sim(cells=60, pass_rate=0.7, seed=3)
        for t, text in sim.log:
            self.assertNotIn("STUCK", text)
        self.assertGreater(rep["tasks"], 0)

    def test_boxes_do_not_wait_long_when_the_robot_is_not_the_bottleneck(self):
        rep, _ = self.run_sim(boxes=4, cells=60, test_time=120.0, pass_rate=0.95, seed=4)
        self.assertLess(rep["avg_idle_s"], 16.0)
        self.assertGreater(rep["box_utilisation"], 0.8)

    def test_fetching_ahead_while_idle_keeps_the_boxes_busier(self):
        with_top, _ = self.run_sim(cells=80, seed=1, boxes=6, fill_heads=False)
        without, _ = self.run_sim(cells=80, seed=1, boxes=6, fill_heads=False, top_up_when_idle=False)
        self.assertLess(with_top["avg_idle_s"], without["avg_idle_s"])
        self.assertLess(with_top["makespan_s"], without["makespan_s"])

    def test_filling_the_heads_at_the_tray_saves_trips_to_the_tray(self):
        for boxes in (10, 13):
            with self.subTest(boxes=boxes):
                filled, _ = self.run_sim(cells=60, seed=4, boxes=boxes, pass_rate=0.95)
                old, _ = self.run_sim(cells=60, seed=4, boxes=boxes, pass_rate=0.95, fill_heads=False)
                self.assertLess(filled["tray_visits"], old["tray_visits"])
                self.assertLessEqual(filled["makespan_s"], old["makespan_s"] * 1.03)         # and the cell is not slower for it

    def test_the_same_seed_gives_the_same_run(self):
        a, _ = self.run_sim(seed=11, cells=40)
        b, _ = self.run_sim(seed=11, cells=40)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
