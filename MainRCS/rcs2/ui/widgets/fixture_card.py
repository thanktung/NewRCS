"""Fixture card of the main window."""
from PySide6 import QtWidgets
from PySide6.QtCore import Qt, Signal

from ...core import engine as E
from ..kit import fluent as F
from ..kit.fluent import Pill, Surface, ToggleSwitch, repolish
from ..kit.theme import STATE_COLORS
from .texts import RESULT_TEXT, STATE_TEXT


class FixtureCard(Surface):
    """Compact fixture card (about 190 x 130 px) so that many fixtures fit on one screen:
    name + ATS badge / state / serial number / test progress / counters / switch + last result."""
    toggled = Signal(int, bool)

    def __init__(self, number, station):
        super().__init__()
        self.number = number
        self.station_name = station
        self.setProperty("state", "off")
        self.setMinimumSize(176, 126)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(14, 7, 6, 9)
        root.setSpacing(1)

        top = QtWidgets.QHBoxLayout()
        top.setSpacing(6)
        name = QtWidgets.QLabel("Fixture %d" % number)
        name.setObjectName("fixName")
        self.ats = Pill("ATS", "grey", compact=True)
        top.addWidget(name)
        top.addWidget(self.ats)
        top.addStretch()
        root.addLayout(top)

        self.state = QtWidgets.QLabel(STATE_TEXT[E.OFFLINE])
        self.state.setObjectName("stateLabel")
        self.state.setProperty("state", "off")
        root.addWidget(self.state)

        self.sn = QtWidgets.QLabel(" ")
        self.sn.setObjectName("monoSmall")
        self.sn.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Fixed)     # never widens the card
        self.sn.setFixedHeight(15)
        root.addWidget(self.sn)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 100)
        root.addWidget(self.progress)
        root.addSpacing(3)

        stats = QtWidgets.QHBoxLayout()
        stats.setSpacing(8)
        self._vals = {}
        for key in ("total", "ng", "yield", "consec"):
            lab = QtWidgets.QLabel("")
            lab.setObjectName("cardStat")
            lab.setTextFormat(Qt.RichText)
            stats.addWidget(lab)
            self._vals[key] = lab
        stats.addStretch()
        root.addLayout(stats)
        root.addStretch()

        bottom = QtWidgets.QHBoxLayout()
        bottom.setSpacing(6)
        self.use = ToggleSwitch("Tắt", compact=True)
        self.use.clicked.connect(lambda checked: self.toggled.emit(self.number, checked))
        self.last = QtWidgets.QLabel("")
        self.last.setObjectName("cardStat")
        self.last.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Fixed)
        self.last.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        bottom.addWidget(self.use)
        bottom.addWidget(self.last, 1)
        root.addLayout(bottom)
        self._apply_tone("off")

    @staticmethod
    def _tone(d):
        s = d["state"]
        if s in (E.NO_USED, E.OFFLINE):
            return "off"
        if s == E.FAULT:
            return "fault"
        if s == E.TESTING:
            return "testing"
        if s == E.IDLE:
            return "idle"
        if s == E.RESULT:
            return {"PASS": "pass", "NG": "ng"}.get(d["last_result"], "warn")
        return "busy"

    def _apply_tone(self, tone):
        accent, _text, fill = STATE_COLORS[tone]
        self.set_accent(accent)
        self.set_fill(fill)
        self.setProperty("state", tone)
        self.state.setProperty("state", tone)
        repolish(self.state)

    @staticmethod
    def _stat_html(value, name, color=None):
        v = "<b>%s</b>" % value if color is None else '<b style="color:%s">%s</b>' % (color, value)
        return "%s&nbsp;%s" % (v, name) if name else v

    def update_from(self, d, test_timeout):
        tone = self._tone(d)
        if self.property("state") != tone:
            self._apply_tone(tone)
        text = STATE_TEXT.get(d["state"], d["state"])
        if d["state"] == E.RESULT and d["last_result"]:
            text = RESULT_TEXT.get(d["last_result"], d["last_result"])
        self.state.setText(text)
        self.ats.set("ATS", "green" if d["connected"] else "red")
        if d.get("dut") is not None:                                   # tray flow: which product is inside, from which cell, which test
            attempt = d.get("tests", 0) + (1 if d["state"] == E.TESTING else 0)
            self.sn.setText("%s  ô%d  L%d" % (d["sn"] or "-", d["cell"] + 1, max(1, attempt)))
            self.sn.setToolTip("Sản phẩm %d từ ô %d của tray Input · lần test %d%s" % (
                d["dut"], d["cell"] + 1, max(1, attempt), ("\nSN " + d["sn"]) if d["sn"] else ""))
        else:
            self.sn.setText(d["sn"] or (d["message"][:26] if d["message"] else " "))
            self.sn.setToolTip("")
        self.progress.setValue(int(min(100, 100 * d["elapsed"] / test_timeout)) if d["state"] == E.TESTING else 0)
        self._vals["total"].setText(self._stat_html(d["total"], "Tổng"))
        self._vals["ng"].setText(self._stat_html(d["ng"], "NG", F.DANGER if d["ng"] else None))
        self._vals["yield"].setText(self._stat_html("-" if d["yield_pct"] is None else "%.0f%%" % d["yield_pct"], ""))
        self._vals["consec"].setText(self._stat_html("×%d" % d["consec_ng"], "", F.WARNING)
                                     if d["consec_ng"] else "")
        self.use.setText("Bật" if d["enabled"] else "Tắt")
        if self.use.isChecked() != d["enabled"]:
            self.use.blockSignals(True)
            self.use.setChecked(d["enabled"])
            self.use.blockSignals(False)
            self.use.update()
        last = ""
        if d["state"] == E.TESTING:
            last = "%.0f s" % d["elapsed"]
        elif d["last_result"]:
            last = "%s  %.1f s" % (RESULT_TEXT.get(d["last_result"], d["last_result"]), d["last_test_time"])
        self.last.setText(last)
        tip = ["Fixture %d - %s - ATS %s" % (self.number, self.station_name, d["host"] or "-"),
               "Tỷ lệ đạt: %s   NG liên tiếp: %d" % ("-" if d["yield_pct"] is None else "%.1f%%" % d["yield_pct"],
                                                      d["consec_ng"])]
        if d["message"]:
            tip.append(d["message"])
        if d["last_detail"]:
            tip.append("Lần cuối: %s" % d["last_detail"])
        self.setToolTip("\n".join(tip))
