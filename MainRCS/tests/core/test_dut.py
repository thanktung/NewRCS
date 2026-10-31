"""Book-keeping of the products of the tray flow: life cycle, the 3-test rule, boxes never repeated."""
import unittest

from rcs2.core import dut as D

BOXES = [1, 2, 3, 4, 5]


class LifeCycleTests(unittest.TestCase):
    def setUp(self):
        self.book = D.DutBook(capacity=6, max_attempts=3, ng_capacity=2)

    def test_a_product_that_passes_goes_into_the_first_empty_cell(self):
        d = self.book.take_from_tray(4, head=2)
        self.assertEqual((d.origin, d.location, d.need), (4, (D.HEAD, 2), D.TEST))
        self.assertNotIn(4, self.book.fresh)
        self.assertEqual(self.book.cells[4], D.EMPTY)
        self.book.place_in_box(d, 3)
        self.assertEqual((d.location, d.need), ((D.BOX, 3), D.TESTING))
        self.assertEqual(self.book.result(d, "PASS", 41.5, BOXES), "PASS")
        self.assertEqual((d.need, d.final), (D.RETURN, "PASS"))
        self.book.take_from_box(d, head=5)
        self.assertEqual(self.book.return_to_tray(d), 4)                       # the only empty cell
        self.assertEqual((d.location, d.need), ((D.TRAY, 4), D.DONE))
        self.assertEqual(self.book.cells[4], D.PASS)

    def test_fqc_counts_as_a_pass(self):
        d = self.book.take_from_tray(0, 1)
        self.book.place_in_box(d, 1)
        self.assertEqual(self.book.result(d, "FQC", 5, BOXES), "PASS")

    def test_ng_is_tested_again_in_other_boxes_and_the_third_failure_is_final(self):
        d = self.book.take_from_tray(0, 1)
        self.book.place_in_box(d, 1)
        self.assertEqual(self.book.result(d, "NG", 40, BOXES), "RETEST")
        self.assertEqual(d.need, D.RETEST)
        self.book.take_from_box(d, 2)
        self.assertFalse(d.can_test_in(1))                                     # not the box it already failed in
        self.assertTrue(d.can_test_in(2))
        with self.assertRaises(D.DutError):
            self.book.place_in_box(d, 1)
        self.book.place_in_box(d, 2)
        self.assertEqual(self.book.result(d, "RETEST", 40, BOXES), "RETEST")   # ATS "retest" counts like a failure
        self.book.take_from_box(d, 3)
        self.book.place_in_box(d, 5)
        self.assertEqual(self.book.result(d, "NG", 40, BOXES), "NG")           # third test failed: final
        self.assertEqual((d.tests_made, [a[0] for a in d.attempts]), (3, [1, 2, 5]))
        self.assertEqual((d.need, d.final), (D.NG, "NG"))
        self.book.take_from_box(d, 1)
        self.assertEqual(self.book.put_in_ng(d), 0)
        self.assertEqual((d.location, d.need, d.ng_cell), ((D.NG_TRAY, 0), D.DONE, 0))

    def test_a_retest_that_passes_is_a_pass(self):
        d = self.book.take_from_tray(1, 1)
        self.book.place_in_box(d, 1)
        self.book.result(d, "NG", 1, BOXES)
        self.book.take_from_box(d, 1)
        self.book.place_in_box(d, 4)
        self.assertEqual(self.book.result(d, "PASS", 1, BOXES), "PASS")
        self.assertEqual(d.tests_made, 2)

    def test_no_other_box_left_makes_the_failure_final_at_once(self):
        d = self.book.take_from_tray(0, 1)
        self.book.place_in_box(d, 1)
        self.assertEqual(self.book.result(d, "NG", 1, [1]), "NG")              # box 1 is the only eligible one
        self.assertEqual(d.tests_made, 1)

    def test_waiting_retests_that_lose_their_last_box_become_final(self):
        d = self.book.take_from_tray(0, 1)
        self.book.place_in_box(d, 1)
        self.book.result(d, "NG", 1, [1, 2])                                   # box 2 still possible
        self.assertEqual(d.need, D.RETEST)
        self.assertEqual(self.book.settle_stuck([1, 2]), [])
        self.assertEqual(self.book.settle_stuck([1]), [d])                     # box 2 was disabled meanwhile
        self.assertEqual((d.need, d.final), (D.NG, "NG"))

    def test_max_attempts_is_configurable(self):
        book = D.DutBook(4, max_attempts=1, ng_capacity=1)
        d = book.take_from_tray(0, 1)
        book.place_in_box(d, 1)
        self.assertEqual(book.result(d, "NG", 1, BOXES), "NG")                 # one test only: no retest
        with self.assertRaises(D.DutError):
            D.DutBook(4, max_attempts=0)


class InputCellTests(unittest.TestCase):
    """A cell of the input tray is fresh (untested) / empty / pass - a passed product goes into the FIRST empty cell, not its own."""

    def make_passed_on_head(self, book, cell, head):
        d = book.take_from_tray(cell, head)
        book.place_in_box(d, 1)
        book.result(d, "PASS", 1, BOXES)
        book.take_from_box(d, head)
        return d

    def test_the_cells_start_fresh_and_picking_empties_them(self):
        book = D.DutBook(5, ng_capacity=2)
        self.assertEqual(book.cells, [D.FRESH] * 5)
        book.take_from_tray(1, 1)
        book.take_from_tray(3, 2)
        self.assertEqual(book.cells, [D.FRESH, D.EMPTY, D.FRESH, D.EMPTY, D.FRESH])
        self.assertEqual(book.empty_cells(), [1, 3])
        self.assertEqual(book.peek_fresh(9), [0, 2, 4])
        with self.assertRaises(D.DutError):
            book.take_from_tray(1, 3)                                          # an empty cell has nothing to pick

    def test_passed_products_fill_the_first_empty_cells_in_order(self):
        book = D.DutBook(6, ng_capacity=2)
        a = self.make_passed_on_head(book, 3, 1)                                # picked from cell 3, ...
        b = self.make_passed_on_head(book, 1, 2)                                # ... then from cell 1
        self.assertEqual(book.empty_cells(), [1, 3])
        self.assertEqual(book.return_to_tray(a), 1)                             # the FIRST empty cell, whatever its origin
        self.assertEqual(book.return_to_tray(b), 3)
        self.assertEqual(book.cells, [D.FRESH, D.PASS, D.FRESH, D.PASS, D.FRESH, D.FRESH])
        self.assertEqual((a.origin, a.location), (3, (D.TRAY, 1)))

    def test_a_failed_product_leaves_its_cell_empty_for_good_and_a_later_pass_can_use_it(self):
        book = D.DutBook(4, max_attempts=1, ng_capacity=2)
        bad = book.take_from_tray(0, 1)
        book.place_in_box(bad, 1)
        book.result(bad, "NG", 1, BOXES)
        book.take_from_box(bad, 1)
        book.put_in_ng(bad)
        self.assertEqual(book.cells[0], D.EMPTY)
        good = self.make_passed_on_head(book, 2, 1)
        self.assertEqual(book.return_to_tray(good), 0)                          # cell 0 was freed by the NG product

    def test_an_explicit_cell_must_be_empty_and_a_full_tray_is_refused(self):
        book = D.DutBook(2, ng_capacity=1)
        d = self.make_passed_on_head(book, 0, 1)
        with self.assertRaises(D.DutError):
            book.return_to_tray(d, 1)                                           # cell 1 still holds a fresh product
        self.assertEqual(book.return_to_tray(d, 0), 0)
        e = self.make_passed_on_head(book, 1, 1)
        book.cells[0] = D.FRESH                                                 # (cannot happen: the books say there is no empty cell)
        book.cells[1] = D.FRESH
        with self.assertRaises(D.DutError):
            book.return_to_tray(e)


class OutputTrayTests(unittest.TestCase):
    """Passed products go to the OUTPUT trays (only them): output 1 first, when it is full output 2. The input tray keeps no PASS cell."""

    def setUp(self):
        self.book = D.DutBook(10, 3, 4, out_capacity=[3, 2])

    def passed_on_head(self, cell, head):
        d = self.book.take_from_tray(cell, head)
        self.book.place_in_box(d, 1)
        self.book.result(d, "PASS", 1, BOXES)
        self.book.take_from_box(d, head)
        return d

    def test_the_book_knows_its_output_trays(self):
        self.assertTrue(self.book.has_outputs)
        self.assertEqual((self.book.out_free, self.book.pass_free, self.book.out_used), (5, 5, [0, 0]))
        self.assertEqual(self.book.output_slots(), [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1)])
        plain = D.DutBook(10)
        self.assertFalse(plain.has_outputs)
        self.assertEqual(plain.pass_free, 0)                                       # nothing taken yet: no empty cell
        plain.take_from_tray(2, 1)
        self.assertEqual(plain.pass_free, 1)                                       # without output trays the room is the empty input cells

    def test_passed_products_fill_output_1_first_then_output_2(self):
        places = []
        for cell in range(5):
            d = self.passed_on_head(cell, 1)
            places.append(self.book.put_in_output(d))
            self.assertEqual((d.need, d.location), (D.DONE, (D.OUT_TRAY, places[-1])))
        self.assertEqual(places, [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1)])
        self.assertEqual((self.book.out_used, self.book.out_free), ([3, 2], 0))
        self.assertEqual(self.book.cells.count(D.PASS), 0)                           # the input tray never gets a PASS cell
        d = self.passed_on_head(5, 1)
        with self.assertRaises(D.DutError):
            self.book.put_in_output(d)                                             # every output tray is full

    def test_the_cell_the_robot_used_must_be_the_next_free_one(self):
        d = self.passed_on_head(0, 1)
        with self.assertRaises(D.DutError):
            self.book.put_in_output(d, 0, 1)                                       # cell 0 is the next one, not 1
        with self.assertRaises(D.DutError):
            self.book.put_in_output(d, 1, 0)                                       # output 2 is used only when output 1 is full
        self.assertEqual(self.book.put_in_output(d, 0, 0), (0, 0))

    def test_only_passed_products_can_go_to_an_output_tray(self):
        d = self.book.take_from_tray(0, 1)                                         # untested, on a head
        with self.assertRaises(D.DutError):
            self.book.put_in_output(d)
        with self.assertRaises(D.DutError):
            D.DutBook(4).put_in_output(self.passed_on_head(1, 1))                   # no output trays configured (other book, other DUT)

    def test_emptying_output_1_lets_it_be_used_first_again(self):
        for cell in range(4):
            self.book.put_in_output(self.passed_on_head(cell, 1))
        self.assertEqual(self.book.out_used, [3, 1])
        self.book.out_used[0] = 0                                                  # the operator emptied output 1 ("Đã dọn")
        self.assertEqual(self.book.output_slots(1), [(0, 0)])


class RulesTests(unittest.TestCase):
    def test_impossible_steps_are_refused(self):
        book = D.DutBook(3, ng_capacity=1)
        d = book.take_from_tray(0, 1)
        with self.assertRaises(D.DutError):
            book.take_from_tray(0, 2)                                          # the cell is empty now
        with self.assertRaises(D.DutError):
            book.result(d, "PASS", 1, BOXES)                                   # not in a box
        with self.assertRaises(D.DutError):
            book.take_from_box(d, 2)                                           # not in a box
        with self.assertRaises(D.DutError):
            book.return_to_tray(d)                                             # has not been tested
        book.place_in_box(d, 1)
        with self.assertRaises(D.DutError):
            book.place_in_box(d, 2)                                            # already in a box
        with self.assertRaises(D.DutError):
            book.take_from_box(d, 2)                                           # still testing
        book.result(d, "NG", 1, [1])
        book.take_from_box(d, 1)
        book.put_in_ng(d)
        e = book.take_from_tray(1, 1)
        book.place_in_box(e, 1)
        book.result(e, "NG", 1, [1])
        book.take_from_box(e, 1)
        with self.assertRaises(D.DutError):
            book.put_in_ng(e)                                                  # the NG tray has 1 cell

    def test_queries_and_stats(self):
        book = D.DutBook(5, ng_capacity=2)
        self.assertEqual(book.peek_fresh(3), [0, 1, 2])
        a = book.take_from_tray(1, 1)
        b = book.take_from_tray(0, 2)
        self.assertEqual(book.peek_fresh(9), [2, 3, 4])
        self.assertIs(book.on_head(1), a)
        self.assertIs(book.on_head(2), b)
        self.assertIsNone(book.on_head(3))
        book.place_in_box(a, 7)
        self.assertIs(book.in_box(7), a)
        self.assertFalse(book.finished())
        st = book.stats()
        self.assertEqual((st["fresh"], st["in_flight"], st["passed"], st["ng"]), (3, 2, 0, 0))
        self.assertEqual(book.ng_free, 2)

    def test_finished_when_everything_is_put_away(self):
        book = D.DutBook(2, ng_capacity=1)
        for cell in (0, 1):
            d = book.take_from_tray(cell, 1)
            book.place_in_box(d, cell + 1)
            book.result(d, "PASS", 1, BOXES)
            book.take_from_box(d, 1)
            book.return_to_tray(d)
        self.assertTrue(book.finished())
        self.assertEqual(book.stats()["passed"], 2)


if __name__ == "__main__":
    unittest.main()
