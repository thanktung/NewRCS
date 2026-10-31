"""Manual window: step jog, go to a taught point, teach a point, retreat to a safe pose (Fluent light).

The robot base program (RSR0001) has no continuous jog: every button press is ONE relative move
(`rmove`, joint-interpolated, no safety check inside the robot) by the chosen step. Each press arms the
bridge for that single command only. Disabled while a run is active or a robot job is running.
"""
import threading

from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Qt, Signal

from ...core import engine as E
from ..kit import fluent as F
from ..kit.fluent import InfoBar, Panel, Pill, repolish

LINEAR_STEPS = [0.1, 0.5, 1, 5, 10, 50]
ANGULAR_STEPS = [0.1, 0.5, 1, 5, 10]
AXES = [("X", "mm", 0), ("Y", "mm", 1), ("Z", "mm", 2), ("W", "deg", 3), ("P", "deg", 4), ("R", "deg", 5)]


class ManualDialog(QtWidgets.QDialog):
    done = Signal(str, str, bool)          # (label, message, ok)
    scan_done = Signal(str, bool)          # (text, ok) of a barcode scanner test
    heads_done = Signal(str, bool, object)  # (text, ok, rows of HeadBank.status() or None)
    laser_done = Signal(str, bool)         # (text, ok) of a laser judgement read

    def __init__(self, runtime, main_window):
        super().__init__(main_window)
        self.rt = runtime
        self.main = main_window
        self._busy = False
        self._scan_busy = False
        self._heads_busy = False
        self._laser_busy = False
        # the robot has ONE End Effector; each of its tools may be missing
        self.ee = getattr(runtime, "ee", None)
        caps = self.ee.capabilities() if self.ee is not None else {}
        self.head_count = int(caps.get("heads", 0))
        self.has_scanner = bool(caps.get("scanner"))
        self.has_laser = bool(caps.get("laser"))
        self.setWindowTitle("Thủ công - jog / điểm")
        self.setMinimumWidth(780)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

        hello = getattr(runtime.bridge, "hello", None) or {}
        limits = hello.get("limits", {})
        self.max_override = int(limits.get("max_override", 30))
        self.max_mm = float(limits.get("max_rmove_mm", 100))
        self.max_deg = float(limits.get("max_rmove_deg", 30))

        # the window now holds many panels (jog, points, End Effector): everything scrolls inside the dialog
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        content = QtWidgets.QWidget()
        root = QtWidgets.QVBoxLayout(content)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)
        scroll.setWidget(content)
        outer.addWidget(scroll)

        root.addWidget(InfoBar("warning", "Mỗi lần bấm là một bước di chuyển tương đối (rmove)",
                               "Robot KHÔNG kiểm tra đường đi với lệnh này. Hãy đặt tay lên nút E-stop "
                               "và dùng tốc độ thấp."))

        # ---- current position
        pos_panel = Panel("Vị trí hiện tại", "target")
        pos_row = QtWidgets.QHBoxLayout()
        pos_row.setSpacing(18)
        self.pos = {}
        for name, unit, _ in AXES:
            box = QtWidgets.QVBoxLayout()
            box.setSpacing(0)
            v = QtWidgets.QLabel("-")
            v.setObjectName("statValue")
            v.setMinimumWidth(64)
            n = QtWidgets.QLabel("%s (%s)" % (name, "độ" if unit == "deg" else unit))
            n.setObjectName("statName")
            box.addWidget(v)
            box.addWidget(n)
            pos_row.addLayout(box)
            self.pos[name] = v
        pos_row.addStretch()
        pos_panel.body.addLayout(pos_row)
        root.addWidget(pos_panel)

        # ---- step / speed + jog buttons
        jog_panel = Panel("Jog", "move")
        cfg = QtWidgets.QHBoxLayout()
        cfg.setSpacing(8)
        self.lin = QtWidgets.QComboBox()
        self.ang = QtWidgets.QComboBox()
        for s in LINEAR_STEPS:
            if s <= self.max_mm:
                self.lin.addItem("%g mm" % s, s)
        for s in ANGULAR_STEPS:
            if s <= self.max_deg:
                self.ang.addItem("%g độ" % s, s)
        self.lin.setCurrentIndex(min(2, self.lin.count() - 1))
        self.ang.setCurrentIndex(min(2, self.ang.count() - 1))
        self.speed = QtWidgets.QSpinBox()
        self.speed.setRange(1, self.max_override)
        self.speed.setValue(min(5, self.max_override))
        self.speed.setSuffix(" %")
        for label, w in (("Bước tuyến tính", self.lin), ("Bước góc", self.ang), ("Tốc độ", self.speed)):
            lab = QtWidgets.QLabel(label)
            lab.setObjectName("muted")
            cfg.addWidget(lab)
            cfg.addWidget(w)
            cfg.addSpacing(8)
        cfg.addStretch()
        jog_panel.body.addLayout(cfg)

        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        self.jog_buttons = []
        for row, (name, unit, idx) in enumerate(AXES):
            minus = QtWidgets.QPushButton("%s  −" % name)
            plus = QtWidgets.QPushButton("%s  +" % name)
            for b in (minus, plus):
                b.setProperty("kind", "jog")
            minus.clicked.connect(lambda _=False, i=idx, u=unit: self._jog(i, -1, u))
            plus.clicked.connect(lambda _=False, i=idx, u=unit: self._jog(i, +1, u))
            grid.addWidget(minus, row // 3, (row % 3) * 2)
            grid.addWidget(plus, row // 3, (row % 3) * 2 + 1)
            self.jog_buttons += [minus, plus]
        for c in range(6):
            grid.setColumnStretch(c, 1)
        jog_panel.body.addLayout(grid)
        root.addWidget(jog_panel)

        # ---- go to point / teach
        pt_panel = Panel("Điểm", "list")
        pt = QtWidgets.QHBoxLayout()
        self.points = QtWidgets.QComboBox()
        self.points.setMinimumWidth(200)
        self.btn_goto = F.button("Di chuyển tới điểm", "arrow_right")
        self.btn_goto.clicked.connect(self._goto)
        lab = QtWidgets.QLabel("Điểm đã dạy")
        lab.setObjectName("muted")
        pt.addWidget(lab)
        pt.addWidget(self.points, 1)
        pt.addWidget(self.btn_goto)
        pt_panel.body.addLayout(pt)

        teach = QtWidgets.QHBoxLayout()
        self.name = QtWidgets.QLineEdit()
        self.name.setPlaceholderText("tên điểm mới, vd. above_fixture_1")
        self.btn_teach = F.button("Lưu vị trí hiện tại", "save")
        self.btn_teach.clicked.connect(self._teach)
        teach.addWidget(self.name, 1)
        teach.addWidget(self.btn_teach)
        pt_panel.body.addLayout(teach)
        root.addWidget(pt_panel)

        # ---- End Effector: heads (8 cylinders + vacuum), barcode scanner, IL-1000 laser
        self.ee_panel = Panel("End Effector", "robot")
        self.heads_panel = self.scan_panel = self.laser_panel = None
        if self.head_count:
            self._build_heads_section(self.ee_panel.body)
        else:
            self.ee_panel.body.addWidget(InfoBar("info", "End Effector chưa có đầu hút",
                                                 "Khai báo van hút, xy lanh và cảm biến áp suất trong config/settings.json, "
                                                 "mục \"end_effector\" -> \"heads\", rồi khởi động lại."))
        if self.has_scanner:
            self._build_scanner_section(self.ee_panel.body)
        else:
            self.ee_panel.body.addWidget(InfoBar("info", "End Effector chưa có máy quét mã",
                                                 "Khai báo máy quét Keyence trong config/settings.json, mục \"end_effector\" "
                                                 "-> \"scanner\", rồi khởi động lại. Thêm bước {\"ee\": \"scanner\"} vào "
                                                 "sequence load để đọc mã trước khi gắp."))
        if self.has_laser:
            self._build_laser_section(self.ee_panel.body)
        else:
            self.ee_panel.body.addWidget(InfoBar("info", "End Effector chưa có laser IL-1000",
                                                 "Khai báo trong config/settings.json, mục \"end_effector\" -> \"laser\"."))
        root.addWidget(self.ee_panel)

        bottom = QtWidgets.QHBoxLayout()
        self.btn_safe = F.button("Về vị trí an toàn", "home")
        self.btn_safe.clicked.connect(self._safe)
        self.btn_fault = F.button("Xóa lỗi robot", "refresh")
        self.btn_fault.clicked.connect(self._clear_fault)
        bottom.addWidget(self.btn_safe)
        bottom.addWidget(self.btn_fault)
        self.calib = None
        if getattr(self.rt, "flow_mode", False):                        # tray flow: teach the head offsets, trays and boxes
            self.btn_calib = F.button("Hiệu chuẩn luồng tray", "target")
            self.btn_calib.clicked.connect(self._open_calibration)
            bottom.addWidget(self.btn_calib)
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
        self.resize(max(self.minimumWidth(), 800), min(content.sizeHint().height() + 4, 900))
        self._fill_points()
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(200)
        self.refresh()

    # ------------------------------------------------------------------ #
    def _set_status(self, text, tone=""):
        if self.status.property("tone") != tone:
            self.status.setProperty("tone", tone)
            repolish(self.status)
        self.status.setText(text)

    def _open_calibration(self):
        from .calibration_dialog import CalibrationDialog
        if self.calib is None:
            self.calib = CalibrationDialog(self.rt, self.main)
        self.calib.show()
        self.calib.raise_()
        self.calib.activateWindow()

    def _fill_points(self):
        current = self.points.currentText()
        self.points.clear()
        self.points.addItems(sorted(self.rt.points()))
        if current:
            self.points.setCurrentText(current)

    def refresh(self):
        snap = self.rt.engine.snapshot()
        pos = snap["robot"].get("curpos")
        for name, _, idx in AXES:
            self.pos[name].setText("-" if not pos else "%.2f" % pos[idx])
        operator = self.main.can("manual")
        ok = (operator and snap["robot_link"] and bool(snap["robot"].get("connected"))
              and snap["run_state"] != E.RUNNING and not snap["current_job"] and not self._busy)
        prog = snap.get("program_running")                   # UO[3] PROGRUN
        moves_ok = ok and prog is not False                  # a motion writes R[1]: only with the program running
        for b in self.jog_buttons + [self.btn_goto, self.btn_safe]:
            b.setEnabled(moves_ok)
        self.btn_goto.setEnabled(moves_ok and self.points.count() > 0)
        self.btn_teach.setEnabled(operator and self.main.can("teach") and snap["robot_link"] and bool(snap["robot"].get("connected"))
                                  and not self._busy and prog is not False)
        self.btn_fault.setEnabled(operator and snap["robot_link"] and not self._busy and prog is not False)
        if self.scan_panel is not None:
            self.btn_scan_test.setEnabled(operator and not self._scan_busy)
            self.btn_scan_stop.setEnabled(operator)
        if self.laser_panel is not None:
            laser_on = bool(getattr(self.ee.laser, "enabled", True))
            self.laser_disabled.setVisible(not laser_on)
            self.btn_laser_read.setEnabled(operator and laser_on and not self._laser_busy and prog is not False)
        if self.heads_panel is not None:
            heads_ok = moves_ok and self._heads_enabled()               # robot I/O: also needs the program running
            for b in self.heads_buttons:
                b.setEnabled(heads_ok and not self._heads_busy)
        if not operator:
            self._set_status("Cần đăng nhập." if self.rt.operator is None else "Cấp của bạn không được dùng điều khiển thủ công.")
        elif snap["run_state"] == E.RUNNING or snap["current_job"]:
            self._set_status("Đang chạy: hãy dừng (và đợi robot xong việc) để dùng điều khiển thủ công.")
        elif prog is False:
            self._set_status("Chương trình robot chưa chạy (UO[3] PROGRUN = 0): không thực hiện được thao tác robot nào "
                             "(di chuyển, dạy điểm, đầu hút, xóa lỗi...). Bấm 'Chạy chương trình' ở panel Robot.")
        if self.points.count() != len(self.rt.points()):
            self._fill_points()

    # ------------------------------------------------------------------ #
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
            self.main.append_log("error", "thủ công %s thất bại: %s" % (label, message))
        self.refresh()

    # ---- End Effector: heads --------------------------------------------------------------- #
    def _section_title(self, body, text):
        lab = QtWidgets.QLabel(text)
        lab.setObjectName("sectionTitle")
        body.addSpacing(4)
        body.addWidget(lab)

    def _build_heads_section(self, body):
        self.heads_panel = self.ee_panel
        self._section_title(body, "Đầu hút (%d cụm xy lanh + van hút)" % self.head_count)
        sel = QtWidgets.QHBoxLayout()
        sel.addStretch()
        self.btn_heads_all = F.button("Chọn tất cả", None, "subtle")
        self.btn_heads_none = F.button("Bỏ chọn", None, "subtle")
        sel.addWidget(self.btn_heads_all)
        sel.addWidget(self.btn_heads_none)
        body.addLayout(sel)

        self.heads_disabled = InfoBar("warning", "Đầu hút đang tắt",
                                      "Đặt end_effector.heads.enabled: true trong settings.json sau khi đã sửa đúng địa chỉ IO.")
        body.addWidget(self.heads_disabled)

        self.heads_grid = QtWidgets.QGridLayout()
        self.heads_grid.setHorizontalSpacing(6)
        self.heads_grid.setVerticalSpacing(4)
        body.addLayout(self.heads_grid)
        self.head_chips, self.head_pills = [], []

        row = QtWidgets.QHBoxLayout()
        row.setSpacing(6)
        self.btn_vac_on = F.button("Hút bật", "play")
        self.btn_vac_off = F.button("Hút tắt", "stop")
        self.btn_cyl_down = F.button("Xy lanh xuống", "arrow_down")
        self.btn_cyl_up = F.button("Xy lanh lên", "arrow_up")
        self.btn_heads_read = F.button("Đọc trạng thái", "refresh")
        self.heads_buttons = [self.btn_vac_on, self.btn_vac_off, self.btn_cyl_down, self.btn_cyl_up, self.btn_heads_read]
        for b in self.heads_buttons:
            row.addWidget(b)
        body.addLayout(row)
        self.heads_result = QtWidgets.QLabel("")
        self.heads_result.setObjectName("formStatus")
        self.heads_result.setWordWrap(True)
        body.addWidget(self.heads_result)

        self.btn_heads_all.clicked.connect(lambda: [c.setChecked(True) for c in self.head_chips])
        self.btn_heads_none.clicked.connect(lambda: [c.setChecked(False) for c in self.head_chips])
        self.btn_vac_on.clicked.connect(lambda: self._heads_do("vacuum_on", "bật hút"))
        self.btn_vac_off.clicked.connect(lambda: self._heads_do("vacuum_off", "tắt hút"))
        self.btn_cyl_down.clicked.connect(lambda: self._heads_do("cylinder_down", "xy lanh xuống"))
        self.btn_cyl_up.clicked.connect(lambda: self._heads_do("cylinder_up", "xy lanh lên"))
        self.btn_heads_read.clicked.connect(lambda: self._heads_do(None, "đọc trạng thái"))
        self.heads_done.connect(self._heads_finished)
        self._rebuild_heads()

    def _heads_enabled(self):
        return bool(self.ee is not None and getattr(self.ee.heads, "enabled", True))

    def _rebuild_heads(self, *_):
        for i in range(self.head_count):
            chip = F.button(str(i + 1), None, "chip")
            chip.setCheckable(True)
            chip.setChecked(True)
            chip.setToolTip("Chọn đầu %d" % (i + 1))
            pill = Pill("-", "grey", compact=True)
            chip.setMaximumWidth(48)
            pill.setMaximumWidth(48)
            self.heads_grid.addWidget(chip, 0, i)
            self.heads_grid.addWidget(pill, 1, i)
            self.head_chips.append(chip)
            self.head_pills.append(pill)
        self.heads_grid.setColumnStretch(len(self.head_chips), 1)            # chips keep their size, spare room at the end
        self.heads_disabled.setVisible(not self._heads_enabled())

    def _selected_heads(self):
        chosen = [i + 1 for i, c in enumerate(self.head_chips) if c.isChecked()]
        return "all" if len(chosen) == len(self.head_chips) else chosen

    def _heads_do(self, action, label):
        heads = self._selected_heads()
        if action is not None and heads == []:
            self._set_heads_text("Hãy chọn ít nhất một đầu.", "error")
            return
        if action == "cylinder_down" and not F.confirm(
                self, "Xy lanh xuống", "Các đầu hút đã chọn sẽ đi xuống.\nHãy chắc chắn không có vật cản. Tiếp tục?",
                warning=True):
            return
        self._heads_busy = True
        self._set_heads_text("%s ..." % label, "")

        def work():
            try:
                if action is not None:
                    self.rt.heads_action(action, heads)
                rows = self.rt.heads_status()
                self.heads_done.emit("%s: xong" % label, True, rows)
            except Exception as ex:
                self.heads_done.emit("%s" % ex, False, None)
        threading.Thread(target=work, daemon=True).start()

    def _set_heads_text(self, text, tone):
        if self.heads_result.property("tone") != tone:
            self.heads_result.setProperty("tone", tone)
            repolish(self.heads_result)
        self.heads_result.setText(text)

    def _heads_finished(self, text, ok, rows):
        self._heads_busy = False
        self._set_heads_text(text, "success" if ok else "error")
        for row in rows or []:
            i = row["n"] - 1
            if i >= len(self.head_pills):
                continue
            hold, vac = row.get("hold"), row.get("vacuum")
            tone = "green" if hold else ("amber" if vac else "grey")
            self.head_pills[i].set(("↓" if row.get("cylinder_down") else "↑") + ("●" if hold else ""), tone)
            self.head_pills[i].setToolTip("Đầu %d: van hút %s, xy lanh %s, %s" % (
                row["n"], "bật" if vac else "tắt", "xuống" if row.get("cylinder_down") else "lên",
                "ĐANG HÚT (áp suất đạt)" if hold else ("chưa có áp suất" if hold is not None else "không có cảm biến")))
        self.refresh()

    # ---- End Effector: barcode scanner test ----------------------------------------------------- #
    def _build_scanner_section(self, body):
        self.scan_panel = self.ee_panel
        self._section_title(body, "Máy quét mã")
        sc = QtWidgets.QHBoxLayout()
        self.btn_scan_test = F.button("Đọc thử (LON)", "play")
        self.btn_scan_stop = F.button("Dừng đọc (LOFF)", "stop")
        self.btn_scan_test.clicked.connect(self._scan_test)
        self.btn_scan_stop.clicked.connect(self._scan_stop)
        sc.addWidget(self.btn_scan_test)
        sc.addWidget(self.btn_scan_stop)
        sc.addStretch()
        body.addLayout(sc)
        self.scan_result = QtWidgets.QLabel("")
        self.scan_result.setObjectName("formStatus")
        self.scan_result.setWordWrap(True)
        body.addWidget(self.scan_result)
        self.scan_done.connect(self._scan_finished)

    def _scan_test(self):
        self._scan_busy = True
        self._set_scan_text("Đang đọc (LON) ...", "")

        def work():
            try:
                self.scan_done.emit("Đã đọc: %s" % self.rt.scan_test(), True)
            except Exception as ex:
                self.scan_done.emit("%s" % ex, False)
        threading.Thread(target=work, daemon=True).start()

    def _scan_stop(self):
        def work():
            try:
                self.rt.scan_stop()
                self.scan_done.emit("Đã gửi LOFF", True)
            except Exception as ex:
                self.scan_done.emit("%s" % ex, False)
        threading.Thread(target=work, daemon=True).start()

    def _set_scan_text(self, text, tone):
        if self.scan_result.property("tone") != tone:
            self.scan_result.setProperty("tone", tone)
            repolish(self.scan_result)
        self.scan_result.setText(text)

    def _scan_finished(self, text, ok):
        self._scan_busy = False
        self._set_scan_text(text, "success" if ok else "error")
        self.refresh()

    # ---- End Effector: IL-1000 laser ------------------------------------------------------------ #
    def _build_laser_section(self, body):
        self.laser_panel = self.ee_panel
        self._section_title(body, "Laser IL-1000")
        self.laser_disabled = InfoBar("warning", "Laser đang tắt",
                                      "Đặt end_effector.laser.enabled: true trong settings.json sau khi đã sửa đúng địa chỉ IO.")
        body.addWidget(self.laser_disabled)
        row = QtWidgets.QHBoxLayout()
        self.btn_laser_read = F.button("Đọc judgement", "refresh")
        self.btn_laser_read.clicked.connect(self._laser_read)
        row.addWidget(self.btn_laser_read)
        row.addStretch()
        body.addLayout(row)
        self.laser_result = QtWidgets.QLabel("")
        self.laser_result.setObjectName("formStatus")
        self.laser_result.setWordWrap(True)
        body.addWidget(self.laser_result)
        self.laser_done.connect(self._laser_finished)

    def _laser_read(self):
        self._laser_busy = True

        def work():
            try:
                st = self.rt.laser_status()
                text = "GO (đạt)" if st["ok"] else "HIGH" if st["high"] else "LOW" if st["low"] else "không đạt"
                self.laser_done.emit("Judgement: %s" % text, bool(st["ok"]))
            except Exception as ex:
                self.laser_done.emit("%s" % ex, False)
        threading.Thread(target=work, daemon=True).start()

    def _laser_finished(self, text, ok):
        self._laser_busy = False
        if self.laser_result.property("tone") != ("success" if ok else "error"):
            self.laser_result.setProperty("tone", "success" if ok else "error")
            repolish(self.laser_result)
        self.laser_result.setText(text)
        self.refresh()

    def _jog(self, axis, sign, unit):
        step = float((self.lin if unit == "mm" else self.ang).currentData())
        offset = [0.0] * 6
        offset[axis] = sign * step
        label = "jog %s%+g" % (AXES[axis][0], sign * step)
        self._run(label, lambda: self.rt.manual_rmove(offset, self.speed.value()))

    def _goto(self):
        name = self.points.currentText()
        if not name:
            return
        if F.confirm(self, "Di chuyển tới điểm", "Di chuyển robot tới '%s' với tốc độ %d %%?\n"
                     "Hãy đặt tay lên nút E-stop." % (name, self.speed.value()), warning=True):
            self._run("di chuyển tới %s" % name, lambda: self.rt.manual_move_to(name, self.speed.value()))

    def _teach(self):
        name = self.name.text().strip()
        exists = name in self.rt.points()
        if exists and not F.confirm(self, "Ghi đè", "Điểm '%s' đã tồn tại. Ghi đè?" % name):
            return
        self._run("dạy điểm %s" % name, lambda: "đã lưu %s" % self.rt.teach_point(name)["xyzwpr"])

    def _safe(self):
        if F.confirm(self, "Về vị trí an toàn", "Robot sẽ lùi về tư thế an toàn từ vị trí hiện tại.\n"
                     "Hãy đặt tay lên nút E-stop. Tiếp tục?", warning=True):
            self._run("về vị trí an toàn", lambda: self.rt.robot_gosafehere(self.speed.value()))

    def _clear_fault(self):
        self._run("xóa lỗi", lambda: self.rt.robot_fault_clear())

    def showEvent(self, event):
        if not self.timer.isActive():            # closeEvent stopped it; the window can be re-opened
            self.timer.start(200)
        super().showEvent(event)

    def closeEvent(self, event):
        self.timer.stop()
        super().closeEvent(event)

