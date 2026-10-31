"""Tray block of the main window: the trays in ONE row (each with its reset button and its cells) and, below them, the state of the heads and the colour legend."""
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, Signal

from ...core.tray import TITLES
from ..kit import fluent as F
from ..kit.fluent import InfoBar, Panel


# --------------------------------------------------------------------------- #
# trays: input tray (DUTs waiting), NG tray (failed DUTs) and the optional output trays (passed DUTs)
# --------------------------------------------------------------------------- #
KINDS = ("input", "ng", "output1", "output2")
CELL_FULL = {"input": F.ACCENT, "ng": F.DANGER, "output1": F.SUCCESS, "output2": F.SUCCESS}      # colour of a cell that holds a DUT
CELL_NEXT = "#FFB900"                                      # outline of the cell the robot uses next

# tray flow. Input tray cell: chưa test | trống (| pass when there are no output trays).   NG tray cell: trống | NG.   Output tray cell: trống | pass.
# Head: trống | chưa test | pass | ng | retest.
EMPTY_COLOR = "#B5B5B5"                                                                       # an empty cell / an empty head is grey
FLOW_COLOR = {"fresh": F.ACCENT, "pass": F.SUCCESS, "ng": F.DANGER, "retest": "#F7630C", "empty": EMPTY_COLOR}
FLOW_TEXT = {"fresh": "chưa test", "pass": "pass", "ng": "NG", "retest": "retest", "empty": "trống"}
HEAD_ORDER = ("empty", "fresh", "pass", "ng", "retest")
HEAD_TEXT = {"empty": "trống", "fresh": "chưa test", "pass": "pass (chờ vào tray)", "ng": "NG (chờ vào tray NG)",
             "retest": "retest (chờ test ở box khác)"}


def flow_cell_states(flow, capacity=None):
    """{cell index: "fresh" | "empty" | "pass"} of the input tray, from the 'flow' part of the engine snapshot."""
    return dict(enumerate(flow.get("input_cells", ())))


class TrayView(QtWidgets.QWidget):
    """Grid of rows x cols cells, drawn to fit the available space. Cells are used in reading order:
    input tray = blue cells still hold a DUT, grey ones were picked; NG tray = red cells hold an NG DUT."""
    GAP = 4
    MAX_CELL = 40          # px, the size the cells get when there is room
    MIN_CELL = 12          # px, the smallest they shrink to

    def __init__(self, kind):
        super().__init__()
        self.kind = kind
        self._snap = None
        self._colors = None                 # tray flow: {cell index: state}; None = plain counter display (no flow data)
        # The tab area of the main window has ONE fixed size for every tab, so the view must not ask for room (its size hint would push the
        # area around): it takes what it is given and the cells shrink to fit (cell_size), at most MAX_CELL px each.
        self.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Ignored)

    def set_snapshot(self, snap, colors=None):
        if colors != self._colors:
            self._colors = dict(colors) if colors is not None else None
            self.update()
        if snap != self._snap:
            old = self._snap
            self._snap = dict(snap) if snap else None
            if (old or {}).get("rows") != (snap or {}).get("rows") or (old or {}).get("cols") != (snap or {}).get("cols"):
                self.updateGeometry()
            self.update()

    def sizeHint(self):
        snap = self._snap
        if not snap:
            return QtCore.QSize(120, 40)
        step = self.MAX_CELL + self.GAP
        return QtCore.QSize(snap["cols"] * step - self.GAP, snap["rows"] * step - self.GAP)

    def minimumSizeHint(self):
        snap = self._snap
        if not snap:
            return QtCore.QSize(60, 30)
        step = self.MIN_CELL + self.GAP
        return QtCore.QSize(snap["cols"] * step - self.GAP, snap["rows"] * step - self.GAP)

    def cell_size(self, width=None, height=None):
        """Edge of one cell (px) for the current size: as big as fits, but at most MAX_CELL px."""
        snap = self._snap
        if not snap:
            return 0
        w = self.width() if width is None else width
        h = self.height() if height is None else height
        gap = self.cell_gap(w, h)
        fit = min((w - (snap["cols"] - 1) * gap) / snap["cols"], (h - (snap["rows"] - 1) * gap) / snap["rows"])
        return max(0, int(min(self.MAX_CELL, fit)))                    # never bigger than the room: every row and column stays visible

    def cell_gap(self, width=None, height=None):
        """Spacing between cells; smaller on big grids so that all of them fit."""
        if not self._snap:
            return 0
        w = self.width() if width is None else width
        h = self.height() if height is None else height
        return max(0, min(self.GAP, int(w / (self._snap["cols"] * 3)), int(h / (self._snap["rows"] * 3))))

    def paintEvent(self, _event):
        snap = self._snap
        if not snap:
            return
        rows, cols, done = snap["rows"], snap["cols"], snap["done"]
        cell, gap = self.cell_size(), self.cell_gap()
        x0 = 0                                                          # cells start at the left edge
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        full = QtGui.QColor(CELL_FULL.get(self.kind, F.ACCENT))
        radius = min(4, cell / 4)
        for idx in range(rows * cols):
            r, c = divmod(idx, cols)
            rect = QtCore.QRectF(x0 + c * (cell + gap), r * (cell + gap), cell, cell)
            used = idx < done
            holds = used if self.kind == "ng" else not used            # does this cell hold a DUT?
            colour = None
            if self._colors is not None:                               # tray flow: the colour tells what happened to that product
                colour = FLOW_COLOR.get(self._colors.get(idx))
                holds = colour is not None
            if holds:
                p.setPen(Qt.NoPen)
                p.setBrush(QtGui.QColor(colour) if colour else full)
            else:
                p.setPen(QtGui.QPen(QtGui.QColor(F.STROKE_STRONG), 1))
                p.setBrush(QtGui.QColor("#FAFAFA"))
            p.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)
            if self._colors is None and idx == done and not snap["exhausted"]:      # the cell the robot works on next
                p.setBrush(Qt.NoBrush)
                p.setPen(QtGui.QPen(QtGui.QColor(CELL_NEXT), 2))
                p.drawRoundedRect(rect.adjusted(1, 1, -1, -1), radius, radius)


class _TraySection(QtWidgets.QWidget):
    """One tray: its name and reset button on one line, its cells below."""
    reset_clicked = Signal(str)

    def __init__(self, kind):
        super().__init__()
        self.kind = kind
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        head = QtWidgets.QHBoxLayout()
        head.setSpacing(8)
        title = QtWidgets.QLabel(TITLES[kind])
        title.setObjectName("fixName")
        self.btn = F.button("Nạp lại" if kind == "input" else "Đã dọn", "refresh", "subtle", F.TEXT_2, size=14, gap=4)
        self.btn.clicked.connect(lambda: self.reset_clicked.emit(self.kind))
        head.addWidget(title)
        head.addStretch()
        head.addWidget(self.btn)
        lay.addLayout(head)
        self.view = TrayView(kind)
        lay.addWidget(self.view, 1)                        # the view takes all the room the section is given

    def _flow_used(self, flow):
        """Cells of this NG / output tray that are full, from the 'flow' part of the engine snapshot."""
        if self.kind == "ng":
            return flow.get("ng_used", 0)
        k = int(self.kind[-1]) - 1
        used = flow.get("out_used", ())
        return used[k] if k < len(used) else 0

    def update_from(self, snap, flow=None):
        colors = None
        if flow and snap:
            if self.kind == "input":
                colors = flow_cell_states(flow, snap["capacity"])
            else:
                used = self._flow_used(flow)
                full = "ng" if self.kind == "ng" else "pass"
                colors = {i: (full if i < used else "empty") for i in range(snap["capacity"])}
        self.view.set_snapshot(snap, colors)


class HeadsStrip(QtWidgets.QWidget):
    """Tray flow: one small box per suction head (8), coloured by what the head holds: grey = empty, blue = an untested product, orange = one
    to test again, green = passed, red = failed. The tooltip says which cell it came from and how often it was tested."""

    def __init__(self):
        super().__init__()
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        title = QtWidgets.QLabel("Tay hút")
        title.setObjectName("fixName")
        lay.addWidget(title)
        self._boxes = []
        self._lay = lay
        self._state = None
        lay.addStretch()

    def update_from(self, heads):
        key = [(h["head"], h["state"], h["cell"], h["sn"], h["tests"]) for h in heads]
        if key == self._state:
            return
        self._state = key
        while len(self._boxes) < len(heads):
            lab = QtWidgets.QLabel()
            lab.setAlignment(Qt.AlignCenter)
            lab.setFixedSize(34, 26)
            self._lay.insertWidget(1 + len(self._boxes), lab)
            self._boxes.append(lab)
        for lab, h in zip(self._boxes, heads):
            lab.setStyleSheet("background:%s;color:white;border-radius:4px;font-weight:600;" % FLOW_COLOR.get(h["state"], EMPTY_COLOR))
            lab.setText(str(h["head"]))
            tip = "Tay %d: %s" % (h["head"], HEAD_TEXT.get(h["state"], h["state"]))
            if h["cell"] is not None:
                tip += "\nLấy từ ô %d của tray Input · đã test %d lần%s" % (h["cell"] + 1, h["tests"], ("\nSN " + h["sn"]) if h["sn"] else "")
            lab.setToolTip(tip)


def _swatch(state):
    return "<span style='color:%s'>■</span>" % FLOW_COLOR[state]


def _legend_html(outputs=False):
    """What the colours mean: the cells of every tray and the heads. `outputs`: there are output trays (so the input tray has no 'pass' cells)."""
    tray = "&nbsp;&nbsp;".join("%s %s" % (_swatch(k), FLOW_TEXT[k]) for k in (("fresh", "empty") if outputs else ("fresh", "pass", "empty")))
    ng = "%s NG &nbsp;%s trống" % (_swatch("ng"), _swatch("empty"))
    out = "%s pass &nbsp;%s trống" % (_swatch("pass"), _swatch("empty"))
    heads = "&nbsp;&nbsp;".join("%s %s" % (_swatch(k), FLOW_TEXT[k]) for k in HEAD_ORDER)
    sep = " &nbsp;&nbsp;|&nbsp;&nbsp; "
    return sep.join(["Input: " + tray, "NG: " + ng] + (["Output: " + out] if outputs else []) + ["Tay: " + heads])


class TrayPanel(Panel):
    """The configured trays (settings.json -> "trays") side by side in one row: input | NG | output 1 | output 2. Each has its reset button
    ("Nạp lại" for the input tray, "Đã dọn" for the others) and its cells; below them (tray flow only) the state of the 8 heads and the colour legend."""
    reset_requested = Signal(str)

    def __init__(self):
        super().__init__("Tray hàng", "list")
        for i in range(self.header.count()):               # the tab already names the view: no header at all
            w = self.header.itemAt(i).widget()
            if w is not None:
                w.hide()
        self.body.removeItem(self.header)

        self.empty = InfoBar("info", "Chưa cài kích thước tray",
                             "Khai báo số hàng × số cột của tray Input, tray NG (và tray Output nếu cần) trong config/settings.json, mục "
                             "\"trays\", rồi khởi động lại.")
        self.body.addWidget(self.empty)
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(18)
        row.setContentsMargins(0, 0, 0, 0)
        self.sections = {k: _TraySection(k) for k in KINDS}
        for sec in self.sections.values():
            row.addWidget(sec, 1)
            sec.reset_clicked.connect(self.reset_requested)
        self.holder = QtWidgets.QWidget()
        self.holder.setLayout(row)
        self.body.addWidget(self.holder, 1)
        self.heads_strip = HeadsStrip()                    # tray flow only: what every head holds
        self.body.addWidget(self.heads_strip)
        self._legend_outputs = False
        self.legend = QtWidgets.QLabel(_legend_html(False))      # what the colours of the cells and of the heads mean
        self.legend.setObjectName("caption")
        self.legend.setTextFormat(Qt.RichText)
        self.legend.setWordWrap(True)
        self.body.addWidget(self.legend)
        self.update_from({})

    def update_from(self, trays, flow=None):
        trays = trays or {}
        self.empty.setVisible(not trays)
        self.holder.setVisible(bool(trays))
        self.heads_strip.setVisible(bool(flow) and bool(trays))
        self.legend.setVisible(bool(flow) and bool(trays))
        if flow:
            self.heads_strip.update_from(flow["heads"])
            outputs = any(k in trays for k in ("output1", "output2"))
            if outputs != self._legend_outputs:
                self._legend_outputs = outputs
                self.legend.setText(_legend_html(outputs))
        for kind, sec in self.sections.items():
            sec.setVisible(kind in trays)
            sec.update_from(trays.get(kind), flow)
