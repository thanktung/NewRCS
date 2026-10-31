"""KPI strip of the main window (total / passed / failed / yield)."""
from PySide6 import QtWidgets

from ..kit import fluent as F
from ..kit.fluent import Surface


def _stat(name):
    box = QtWidgets.QVBoxLayout()
    box.setSpacing(0)
    value = QtWidgets.QLabel("-")
    value.setObjectName("statValue")
    label = QtWidgets.QLabel(name)
    label.setObjectName("statName")
    box.addWidget(value)
    box.addWidget(label)
    return box, value


class TotalsPanel(Surface):
    """Production KPI strip: total / pass / NG / yield."""

    def __init__(self):
        super().__init__()
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(16, 8, 16, 10)
        lay.setSpacing(0)
        self._v = {}
        items = (("total", "Tổng đã test"), ("passed", "Đạt"), ("ng", "Không đạt"), ("yield", "Tỷ lệ đạt"))
        for i, (key, name) in enumerate(items):
            if i:
                line = QtWidgets.QFrame()
                line.setObjectName("divider")
                line.setFixedHeight(40)
                lay.addSpacing(8)
                lay.addWidget(line)
                lay.addSpacing(24)
            box = QtWidgets.QVBoxLayout()
            box.setSpacing(0)
            v = QtWidgets.QLabel("0")
            v.setObjectName("kpiValue")
            n = QtWidgets.QLabel(name)
            n.setObjectName("kpiName")
            box.addWidget(v)
            box.addWidget(n)
            lay.addLayout(box, 1)
            self._v[key] = v
        self._v["passed"].setStyleSheet("color: %s;" % F.SUCCESS)
        self._v["ng"].setStyleSheet("color: %s;" % F.DANGER)

    def update_from(self, totals):
        self._v["total"].setText(str(totals["total"]))
        self._v["passed"].setText(str(totals["passed"]))
        self._v["ng"].setText(str(totals["total"] - totals["passed"]))
        self._v["yield"].setText("-" if totals["yield_pct"] is None else "%.1f%%" % totals["yield_pct"])
