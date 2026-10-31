"""Calibration of the tray flow: teach the points the planner needs, then CHECK them by moving every head to computed places.

Opened from the Manual window (which has the jog buttons), so the two windows are used together: jog the robot, press "Lưu" here.
All six values of the robot pose (x y z w p r) and its CONFIG / UF / UT are saved by Runtime.teach_point; the poses shown and used for the
checks are the same ones a run would send (rcs2/core/geometry.py), computed from those taught points.

  1. Offsets of the heads: head 1 over the origin point O of the input tray -> save "Tay 1 tại O"; then, WITHOUT moving the tray, head 2 over the
     same point O -> "Tay 2 tại O" ... up to the last head (and the barcode reader).
  2. Input tray, NG tray and the output trays (output 1 / 2, when configured), with head 1: the first cell (O), the last cell of the first row
     (X), the first cell of the last row (Y).
  3. Every box, with head 1.
"""
import threading

from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Qt, Signal

from ...core import engine as E
from ...core import geometry as G
from ...core.tray import TITLES
from ..kit import fluent as F
from ..kit.fluent import InfoBar, Panel, Pill, repolish


def _num(v):
    """3 decimals, never '-0.000'."""
    return "%.3f" % (round(v, 3) or 0.0)


def _pose_text(pose):
    names = ("X", "Y", "Z", "W", "P", "R")
    return "   ".join("%s %s" % (n, _num(v)) for n, v in zip(names, pose["xyzwpr"][:6]))


class CalibrationDialog(QtWidgets.QDialog):
    done = Signal(str, str, bool)          # (label, message, ok)

    def __init__(self, runtime, main_window):
        super().__init__(main_window)
        self.rt = runtime
        self.main = main_window
        self._busy = False
        flow = runtime.engine.flow
        self.head_count = flow.heads if flow is not None else 0
        self.has_scanner = bool(flow.scanner) if flow is not None else False
        self.has_laser = bool(flow.laser) if flow is not None else False
        self.trays = dict(runtime.cfg.get("trays") or {})
        self.setWindowTitle("Hiệu chuẩn luồng tray")
        self.setMinimumWidth(820)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        content = QtWidgets.QWidget()
        root = QtWidgets.QVBoxLayout(content)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)
        scroll.setWidget(content)
        outer.addWidget(scroll)

        self.summary = InfoBar("info", "", "")
        root.addWidget(self.summary)
        root.addWidget(InfoBar("warning", "Dạy bằng Tay 1, các tay còn lại chỉ cần chạm cùng điểm O",
                               "Jog robot trong cửa sổ Thủ công (hoặc bằng teach pendant), đưa đầu hút tới đúng điểm rồi bấm Lưu. "
                               "Mỗi điểm lưu đủ 6 giá trị X Y Z W P R cùng CONFIG / UF / UT; ba điểm O, X, Y của một tray phải cùng CONFIG / UF / UT. "
                               "Tay hút phải ở vị trí làm việc (xy lanh lên) khi lưu."))

        self.rows = {}                      # point name -> (pill, save button, go button)
        for key, title, items in runtime.flow_groups():
            panel = Panel(title, "list")
            grid = QtWidgets.QGridLayout()
            grid.setHorizontalSpacing(10)
            grid.setVerticalSpacing(6)
            for i, (name, label) in enumerate(items):
                lab = QtWidgets.QLabel(label)
                pill = Pill("-", "grey")
                save = F.button("Lưu vị trí hiện tại", "save", None, size=14, gap=4)
                go = F.button("Tới", "arrow_right", "subtle", F.TEXT_2, size=14, gap=4)
                save.clicked.connect(lambda _=False, n=name: self._teach(n))
                go.clicked.connect(lambda _=False, n=name: self._go(n))
                grid.addWidget(lab, i, 0)
                grid.addWidget(pill, i, 1)
                grid.addWidget(save, i, 2)
                grid.addWidget(go, i, 3)
                self.rows[name] = (pill, save, go)
            grid.setColumnStretch(0, 1)
            panel.body.addLayout(grid)
            root.addWidget(panel)

        self.offsets = QtWidgets.QLabel("")
        self.offsets.setObjectName("monoSmall")
        self.offsets.setWordWrap(True)
        off_panel = Panel("Offset đã tính của các tay so với tay 1 (hệ tọa độ dụng cụ: X Y Z W P R)", "move")
        off_panel.body.addWidget(self.offsets)
        root.addWidget(off_panel)

        root.addWidget(self._build_check_panel())

        bottom = QtWidgets.QHBoxLayout()
        bottom.addStretch()
        close = QtWidgets.QPushButton("Đóng")
        close.clicked.connect(self.close)
        bottom.addWidget(close)
        root.addLayout(bottom)
        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        self.status.setObjectName("formStatus")
        self.status.setMinimumHeight(20)
        root.addWidget(self.status)

        self.done.connect(self._finished)
        self.resize(max(self.minimumWidth(), 860), 820)
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(300)
        self.refresh()

    # ---- the check panel ------------------------------------------------------------------------------- #
    def _build_check_panel(self):
        panel = Panel("%d. Kiểm tra: đưa từng tay tới ô / box tính ra" % (len(self.rt.flow_groups()) + 1), "target")
        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        self.head_box = QtWidgets.QComboBox()
        for k in range(1, self.head_count + 1):
            self.head_box.addItem("Tay %d" % k, k)
        if self.has_scanner:
            self.head_box.addItem("Máy quét", G.SCANNER)
        if self.has_laser:
            self.head_box.addItem("Đầu laser", G.LASER)
        self.speed = QtWidgets.QSpinBox()
        self.speed.setRange(1, 100)
        self.speed.setValue(min(5, int(self.main.rt.manual_override() or 5)))
        self.speed.setSuffix(" %")

        self.tray_box = QtWidgets.QComboBox()
        for kind in ("input", "ng", "output1", "output2"):
            if kind in self.trays:
                self.tray_box.addItem(TITLES[kind], kind)
        self.row_spin, self.col_spin = QtWidgets.QSpinBox(), QtWidgets.QSpinBox()
        self.tray_box.currentIndexChanged.connect(self._tray_changed)
        self.btn_calc_cell = F.button("Tính tọa độ", "list", "subtle", F.TEXT_2, size=14, gap=4)
        self.btn_go_cell = F.button("Đưa tới ô", "arrow_right", None, size=14, gap=4)
        self.btn_calc_cell.clicked.connect(self._calc_cell)
        self.btn_go_cell.clicked.connect(self._go_cell)

        self.box_box = QtWidgets.QComboBox()
        for n in self.rt.engine.flow.fixture_numbers if self.rt.engine.flow else []:
            self.box_box.addItem("Box %d" % n, n)
        self.btn_calc_box = F.button("Tính tọa độ", "list", "subtle", F.TEXT_2, size=14, gap=4)
        self.btn_go_box = F.button("Đưa tới box", "arrow_right", None, size=14, gap=4)
        self.btn_calc_box.clicked.connect(self._calc_box)
        self.btn_go_box.clicked.connect(self._go_box)

        def lab(text):
            w = QtWidgets.QLabel(text)
            w.setObjectName("muted")
            return w
        grid.addWidget(lab("Đầu"), 0, 0)
        grid.addWidget(self.head_box, 0, 1)
        grid.addWidget(lab("Tốc độ"), 0, 2)
        grid.addWidget(self.speed, 0, 3)
        grid.addWidget(lab("Tray"), 1, 0)
        grid.addWidget(self.tray_box, 1, 1)
        grid.addWidget(lab("Hàng / cột (từ 1)"), 1, 2)
        rc = QtWidgets.QHBoxLayout()
        rc.addWidget(self.row_spin)
        rc.addWidget(self.col_spin)
        grid.addLayout(rc, 1, 3)
        grid.addWidget(self.btn_calc_cell, 1, 4)
        grid.addWidget(self.btn_go_cell, 1, 5)
        grid.addWidget(lab("Box"), 2, 0)
        grid.addWidget(self.box_box, 2, 1)
        grid.addWidget(self.btn_calc_box, 2, 4)
        grid.addWidget(self.btn_go_box, 2, 5)
        grid.setColumnStretch(3, 1)
        panel.body.addLayout(grid)
        self.pose_label = QtWidgets.QLabel("")
        self.pose_label.setObjectName("monoSmall")
        self.pose_label.setWordWrap(True)
        self.pose_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        panel.body.addWidget(self.pose_label)
        self._tray_changed()
        return panel

    def _tray_changed(self, *_):
        kind = self.tray_box.currentData()
        size = self.trays.get(kind) or {"rows": 1, "cols": 1}
        self.row_spin.setRange(1, size["rows"])
        self.col_spin.setRange(1, size["cols"])

    def _cell_index(self):
        kind = self.tray_box.currentData()
        return kind, (self.row_spin.value() - 1) * self.trays[kind]["cols"] + (self.col_spin.value() - 1)

    # ---- actions ----------------------------------------------------------------------------------------- #
    def _set_status(self, text, tone=""):
        if self.status.property("tone") != tone:
            self.status.setProperty("tone", tone)
            repolish(self.status)
        self.status.setText(text)

    def _run(self, label, fn):
        self._busy = True
        self._set_status("%s ..." % label)

        def work():
            try:
                self.done.emit(label, str(fn() or "done"), True)
            except Exception as ex:
                self.done.emit(label, "%s" % ex, False)
        threading.Thread(target=work, daemon=True).start()

    def _finished(self, label, message, ok):
        self._busy = False
        self._set_status("%s: %s" % (label, message if not ok else "xong"), "success" if ok else "error")
        if not ok:
            self.main.append_log("error", "hiệu chuẩn %s thất bại: %s" % (label, message))
        self.refresh()

    def _teach(self, name):
        def work():
            p = self.rt.teach_point(name)
            return "%s = %s" % (name, _pose_text(p))
        self._run("Lưu %s" % name, work)

    def _go(self, name):
        self._run("Tới %s" % name, lambda: self.rt.manual_move_to(name, self.speed.value()))

    def _show(self, fn):
        try:
            self.pose_label.setText(_pose_text(fn()))
            self._set_status("")
        except Exception as ex:
            self.pose_label.setText("")
            self._set_status(str(ex), "error")

    def _calc_cell(self):
        kind, idx = self._cell_index()
        head = self.head_box.currentData()
        self._show(lambda: self.rt.flow_cell_pose(kind, idx, head))

    def _go_cell(self):
        kind, idx = self._cell_index()
        head = self.head_box.currentData()
        self._calc_cell()
        self._run("Đưa %s tới ô %d của tray %s" % (self.head_box.currentText(), idx + 1, kind),
                  lambda: self.rt.flow_move_head_to_cell(kind, idx, head, self.speed.value()))

    def _calc_box(self):
        n, head = self.box_box.currentData(), self.head_box.currentData()
        self._show(lambda: self.rt.flow_point_pose("fixture_%d" % n, head))

    def _go_box(self):
        n, head = self.box_box.currentData(), self.head_box.currentData()
        self._calc_box()
        self._run("Đưa %s tới box %d" % (self.head_box.currentText(), n),
                  lambda: self.rt.flow_move_head_to_point("fixture_%d" % n, head, self.speed.value()))

    # ---- refresh ------------------------------------------------------------------------------------------ #
    def refresh(self):
        snap = self.rt.engine.snapshot()
        taught = self.rt.flow_taught()
        status = self.rt.flow_status()
        if status["complete"]:
            self.summary.set("success", "Đã dạy đủ và nhất quán", "Có thể kiểm tra từng tay ở mục kiểm tra rồi bấm Bắt đầu.")
        elif status["problem"]:
            self.summary.set("error", "Điểm đã dạy chưa hợp lệ", status["problem"])
        else:
            self.summary.set("warning", "Còn %d điểm chưa dạy" % len(status["missing"]), ", ".join(status["missing"]))
        robot_ok = (snap["robot_link"] and bool(snap["robot"].get("connected")) and snap["run_state"] != E.RUNNING
                    and not snap["current_job"] and not self._busy and snap.get("program_running") is not False)
        may_teach = robot_ok and self.main.can("teach")
        may_move = robot_ok and self.main.can("manual")
        for name, (pill, save, go) in self.rows.items():
            ok = taught.get(name, False)
            pill.set("Đã dạy" if ok else "Chưa dạy", "green" if ok else "amber")
            save.setEnabled(may_teach)
            go.setEnabled(may_move and ok)
        for b in (self.btn_go_cell, self.btn_go_box):
            b.setEnabled(may_move)
        offs = self.rt.flow_head_offsets()
        self.offsets.setText("\n".join("%s:  %s" % ("Tay %s" % k if isinstance(k, int) else {G.SCANNER: "Máy quét", G.LASER: "Đầu laser"}.get(k, str(k)),
                                                      "   ".join("%s %s" % (n, _num(v)) for n, v in zip("XYZWPR", o)))
                                       for k, o in offs.items() if k != 1) or "Chưa dạy offset (cần Tay 1 và ít nhất một tay khác tại O)")
        if snap["run_state"] == E.RUNNING or snap["current_job"]:
            self._set_status("Đang chạy: hãy dừng (và đợi robot xong việc) để hiệu chuẩn.")
        elif snap.get("program_running") is False:
            self._set_status("Chương trình robot chưa chạy (UO[3] PROGRUN = 0): không lưu / di chuyển được. Bấm 'Chạy chương trình' ở panel Robot.")

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()
