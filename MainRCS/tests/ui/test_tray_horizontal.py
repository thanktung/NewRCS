"""Checks for the horizontal tray layout and fitting all tray cells."""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets
from rcs2.ui.widgets.tray_panel import TrayPanel


class HorizontalTrayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        self.panel = TrayPanel()
        self.panel.resize(1000, 320)
        self.panel.show()

    def tearDown(self):
        self.panel.close()

    @staticmethod
    def snapshot(kind, rows, cols):
        return {"kind": kind, "rows": rows, "cols": cols, "capacity": rows * cols,
                "done": 0, "count": rows * cols if kind == "input" else 0, "exhausted": False}

    def check_fits(self, sec):
        view = sec.view
        rows, cols = view._snap["rows"], view._snap["cols"]
        cell, gap = view.cell_size(), view.cell_gap()
        self.assertGreater(cell, 0)
        self.assertLessEqual(cols * cell + (cols - 1) * gap, view.width())
        self.assertLessEqual(rows * cell + (rows - 1) * gap, view.height())
        self.assertLessEqual(sec.btn.geometry().right(), sec.width())

    def test_four_trays_are_horizontal_and_cells_fit(self):
        trays = {k: self.snapshot(k, 4, 8) for k in ("input", "ng", "output1", "output2")}
        self.panel.update_from(trays)
        self.app.processEvents()
        sections = [self.panel.sections[k] for k in trays]
        self.assertEqual(len({s.y() for s in sections}), 1)
        self.assertEqual(sorted(s.x() for s in sections), [s.x() for s in sections])
        for sec in sections:
            self.check_fits(sec)
        calls = []
        self.panel.reset_requested.connect(calls.append)
        for sec in sections:
            sec.btn.click()
        self.assertEqual(calls, list(trays))

    def test_large_tray_cells_fit_and_missing_trays_do_not_take_space(self):
        trays = {k: self.snapshot(k, 10, 20) for k in ("input", "ng", "output1", "output2")}
        self.panel.update_from(trays)
        self.app.processEvents()
        for sec in self.panel.sections.values():
            self.check_fits(sec)
        self.panel.update_from({"input": trays["input"], "ng": trays["ng"]})
        self.app.processEvents()
        self.assertTrue(self.panel.sections["output1"].isHidden())
        self.assertTrue(self.panel.sections["output2"].isHidden())
        for kind in ("input", "ng"):
            self.check_fits(self.panel.sections[kind])


if __name__ == "__main__":
    unittest.main()
