"""Input tray / NG tray: sizes come from a file (never fixed in code)."""
import unittest

from rcs2.core import tray as T


class TrayModelTests(unittest.TestCase):
    def test_input_tray_starts_full_and_is_consumed_in_reading_order(self):
        t = T.Tray("input", 2, 3)
        self.assertEqual((t.capacity, t.count, t.exhausted), (6, 6, False))
        for expected in (5, 4, 3, 2, 1, 0):
            self.assertTrue(t.advance())
            self.assertEqual(t.count, expected)
        self.assertTrue(t.exhausted)
        self.assertFalse(t.advance())                              # nothing left, no overflow
        self.assertEqual(t.snapshot()["done"], 6)
        t.reset()
        self.assertEqual((t.count, t.exhausted), (6, False))

    def test_ng_tray_starts_empty_and_fills_up(self):
        t = T.Tray("ng", 1, 2)
        self.assertEqual(t.count, 0)
        t.advance()
        self.assertEqual((t.count, t.exhausted), (1, False))
        t.advance()
        self.assertEqual((t.count, t.exhausted), (2, True))
        t.reset()
        self.assertEqual(t.count, 0)

    def test_sizes_are_validated(self):
        for bad in ((0, 3), (3, 0), (-1, 2), (2, 51), (1.5, 2), ("2", 2), (None, 2), (True, 2)):
            with self.assertRaises(T.TrayConfigError, msg=str(bad)):
                T.Tray("input", *bad)
        with self.assertRaises(T.TrayConfigError):
            T.Tray("pass", 1, 1)
        self.assertEqual(T.Tray("input", 50, 50).capacity, 2500)

    def test_build_ignores_notes_and_rejects_garbage(self):
        built = T.build_trays({"_note": "x", "input": {"rows": 5, "cols": 8}})
        self.assertEqual(list(built), ["input"])                   # NG tray not configured: simply not there
        self.assertEqual(T.build_trays({}), {})
        self.assertEqual(T.build_trays(None), {})
        with self.assertRaises(T.TrayConfigError):
            T.build_trays({"input": 5})


if __name__ == "__main__":
    unittest.main()
