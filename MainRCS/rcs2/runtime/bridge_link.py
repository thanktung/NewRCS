"""Link to the robot bridge, and whether the robot PROGRAM is running (UO[3] PROGRUN)."""
from ..robot import protocol as P
from ..robot.client import RobotError
from ..robot.uop import normalize as normalize_robot_start


class BridgeLinkMixin:
    def _program_monitor(self):
        """Keeps `bridge.program_state` (UO[3] PROGRUN) up to date and tells the operator when it changes. The first reading
        after the link is up says whether the robot program is running when NewRCS is opened."""
        every = float(normalize_robot_start(self.cfg.get("robot_start"))["monitor_s"])
        announced = "never"
        while not self._stop.wait(every):
            if not self.bridge.connected or not (self.bridge.last_status or {}).get("connected"):
                self.bridge.program_state = None
                announced = "never" if announced is not None else announced
                continue
            state = self.bridge.refresh_program_state()
            if state != announced and (state is not None or announced == "never"):
                if state is True:
                    self._emit_log("info", "chương trình robot đang chạy (UO[3] PROGRUN = 1)")
                elif state is False:
                    self._emit_log("warn", "chương trình robot CHƯA chạy (UO[3] PROGRUN = 0): bấm 'Chạy chương trình' "
                                           "trước khi điều khiển robot")
            if state is not None:
                announced = state

    def _bridge_supervisor(self):
        """Keeps the link to the robot bridge (and the bridge's own robot link) up."""
        announced = None
        while not self._stop.is_set():
            try:
                if not self.bridge.connected:
                    hello = self.bridge.connect()
                    self._check_sequences_vs_mode(hello)
                    self._emit_log("info", "đã kết nối bridge robot (%s)" % hello.get("mode"))
                st = self.bridge.last_status or {}
                if self.bridge.connected and not st.get("connected"):
                    self.bridge.robot_connect()
                    self._emit_log("info", "đã kết nối robot qua bridge")
                if announced is not True:
                    announced = True
                    self.errors.clear_error("robot_link")
            except (ConnectionError, OSError, RobotError) as ex:
                if announced is not False:
                    announced = False
                    self._emit_log("warn", "bridge robot: %s" % ex)
            self._stop.wait(3.0)

    def _check_sequences_vs_mode(self, hello):
        if self._seq_data.get("example") and hello.get("mode") == "real":
            self.engine.block_reason = ("config/sequences.json là bản VÍ DỤ (EXAMPLE, tọa độ chỉ là giá trị giữ chỗ). "
                                        "Hãy dạy điểm thật và xóa dòng \"example\": true trước khi chạy robot thật")
            self._emit_log("error", self.engine.block_reason)
        else:
            self.engine.block_reason = ""

    def robot_connect(self):
        return self.bridge.robot_connect()

    def _refresh_program_state(self):
        refresh = getattr(self.bridge, "refresh_program_state", None)      # a bridge stand-in may not have it
        return refresh() if refresh is not None else None

    def _need_program_running(self):
        """Nothing may write R[1] while the robot program is not running (UO[3] PROGRUN = 0): the command would stay
        unanswered in R[1] and be executed later, when the program is started again. Fresh read, no arm needed."""
        refresh = getattr(self.bridge, "refresh_program_state", None)
        if refresh is None:                                    # a bridge stand-in without this feature (tests)
            return
        state = refresh()
        if state is False:
            raise RobotError(P.E_PROGRAM_STOPPED, "chương trình robot chưa chạy (UO[3] PROGRUN = 0): "
                                                  "hãy bấm 'Chạy chương trình' trước")
        if state is None:
            raise RobotError(P.E_PROGRAM_STOPPED, "không đọc được UO[3] PROGRUN: không biết chương trình robot có chạy không")
