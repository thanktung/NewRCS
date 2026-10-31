"""Alarm list of the main window."""
from PySide6 import QtWidgets
from PySide6.QtCore import Qt

from ..kit.fluent import InfoBar, Panel, Pill


class AlarmPanel(Panel):
    """Active alarms as Fluent InfoBars (9026 'RCS dừng' is a warning, every other code an error)."""

    def __init__(self):
        super().__init__("Báo động", "warning")
        self.count = Pill("0", "grey")
        self.header.addWidget(self.count)
        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setMinimumHeight(110)
        host = QtWidgets.QWidget()
        host.setAttribute(Qt.WA_StyledBackground, False)
        self.list = QtWidgets.QVBoxLayout(host)
        self.list.setContentsMargins(0, 0, 4, 0)
        self.list.setSpacing(6)
        self.empty = InfoBar("success", "Không có báo động", "")
        self.list.addWidget(self.empty)
        self.list.addStretch()
        self.scroll.setWidget(host)
        self.body.addWidget(self.scroll, 1)
        self._bars = []
        self._last = None

    def update_from(self, alarms):
        sig = [(a["key"], a["message"]) for a in alarms]
        if sig == self._last:
            return
        self._last = sig
        for bar in self._bars:
            self.list.removeWidget(bar)
            bar.deleteLater()
        self._bars = []
        self.empty.setVisible(not alarms)
        self.count.set(str(len(alarms)), "red" if alarms else "grey")
        for i, a in enumerate(alarms):
            severity = "warning" if a["code"] == "9026" else "error"
            bar = InfoBar(severity, "%s   ·   %s" % (a["code"], a["since"][11:16]), a["message"])
            self.list.insertWidget(i, bar)
            self._bars.append(bar)
