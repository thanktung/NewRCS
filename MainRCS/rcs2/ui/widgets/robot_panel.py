"""Robot panel of the main window: link state, program state (UO[3]), current command, robot buttons."""
from PySide6 import QtWidgets
from PySide6.QtCore import Signal

from ...core import engine as E
from ..kit import fluent as F
from ..kit.fluent import Panel, Pill


class RobotPanel(Panel):
    connect_clicked = Signal()
    safe_clicked = Signal()
    program_clicked = Signal()
    stop_robot_clicked = Signal()

    def __init__(self):
        super().__init__("Robot", "robot")
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(6)
        self.link = Pill("Bridge mất", "red")
        self.robot = Pill("Robot mất", "red")
        self.arm = Pill("CHƯA ARM", "grey")
        row.addWidget(self.link)
        row.addWidget(self.robot)
        row.addWidget(self.arm)
        row.addStretch()
        self.body.addLayout(row)

        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(6)
        self._v = {}
        for i, (key, name) in enumerate((("prog", "Chương trình"), ("r1", "Lệnh R[1]"), ("op", "Đang chạy"),
                                         ("pos", "XYZ (mm)"), ("job", "Công việc"))):
            n = QtWidgets.QLabel(name)
            n.setObjectName("muted")
            if key == "prog":                       # UO[3] PROGRUN: is the robot program running?
                v = Pill("?", "grey", compact=True)
                v.setToolTip("UO[3] PROGRUN: chương trình robot (RSR0001) có đang chạy không")
                holder = QtWidgets.QHBoxLayout()
                holder.addWidget(v)
                holder.addStretch()
                grid.addWidget(n, i, 0)
                grid.addLayout(holder, i, 1)
            else:
                v = QtWidgets.QLabel("-")
                v.setObjectName("mono")
                grid.addWidget(n, i, 0)
                grid.addWidget(v, i, 1)
            self._v[key] = v
        grid.setColumnStretch(1, 1)
        self.body.addLayout(grid)
        self.msg = QtWidgets.QLabel("")
        self.msg.setObjectName("caption")
        self.msg.setWordWrap(True)
        self.body.addWidget(self.msg)

        buttons = QtWidgets.QHBoxLayout()
        self.btn_connect = F.button("Kết nối robot", "link")
        self.btn_safe = F.button("Về vị trí an toàn", "home")
        self.btn_connect.clicked.connect(self.connect_clicked)
        self.btn_safe.clicked.connect(self.safe_clicked)
        buttons.addWidget(self.btn_connect)
        buttons.addWidget(self.btn_safe)
        self.body.addLayout(buttons)
        prog_row = QtWidgets.QHBoxLayout()
        prog_row.setSpacing(6)
        self.btn_program = F.button("Chạy chương trình", "play")
        self.btn_program.setToolTip("Chạy RSR0001 qua tín hiệu UOP: bật UI1-3 và UI8, xung UI9 chọn chương trình, "
                                    "xung UI5 xóa lỗi (kiểm tra UO6), xung UI6 start (kiểm tra UO3)")
        self.btn_program.clicked.connect(self.program_clicked)
        self.btn_stop_robot = F.button("Dừng robot", "stop", "danger", "#FFFFFF")
        self.btn_stop_robot.setToolTip("Dừng robot qua tín hiệu UOP: xung UI4 (CSTOPI), tắt UI1-3, kiểm tra UO3 = 0. "
                                       "Luôn dùng được, kể cả khi đang chạy. Không thay thế nút E-stop.")
        self.btn_stop_robot.clicked.connect(self.stop_robot_clicked)
        prog_row.addWidget(self.btn_program, 1)
        prog_row.addWidget(self.btn_stop_robot)
        self.body.addLayout(prog_row)

    def update_from(self, snap):
        st = snap["robot"]
        link = snap["robot_link"]
        prog = snap.get("program_running")
        self._v["prog"].set("ĐANG CHẠY" if prog is True else "DỪNG" if prog is False else "?",
                            "green" if prog is True else "red" if prog is False else "grey")
        self.link.set("Bridge OK" if link else "Bridge mất", "green" if link else "red")
        rc = bool(st.get("connected"))
        self.robot.set("Robot OK" if rc else "Robot mất", "green" if rc else "red")
        armed = bool(st.get("armed"))
        self.arm.set("ĐÃ ARM" if armed else "CHƯA ARM", "amber" if armed else "grey")
        r1 = st.get("r1")
        self._v["r1"].setText("-" if r1 is None else str(r1))
        self._v["op"].setText(st.get("op") or "rảnh")
        pos = st.get("curpos")
        self._v["pos"].setText("-" if not pos else "%.0f   %.0f   %.0f" % tuple(pos[:3]))
        job = snap["current_job"]
        self._v["job"].setText("-" if not job else "%s F%d" % (job[0], job[1]))
        self.msg.setText(st.get("message", ""))
        self.btn_connect.setEnabled(link and not rc)
        idle = link and rc and snap["run_state"] != E.RUNNING and not job
        self.btn_safe.setEnabled(idle and prog is not False)               # a motion needs the program to be running
        self.btn_safe.setToolTip("Chương trình robot chưa chạy (UO[3] = 0): bấm 'Chạy chương trình' trước" if prog is False else "")
        self.btn_program.setEnabled(idle and prog is not True)             # nothing to start when it already runs
        self.btn_stop_robot.setEnabled(link and rc)               # a stop is allowed in every state
