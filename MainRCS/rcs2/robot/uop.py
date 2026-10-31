"""Chạy / dừng chương trình robot RSR0001 qua tín hiệu UOP của controller FANUC (UI / UO [1-18]).

Tín hiệu UI được map sang ngõ vào số chuẩn có CÙNG chỉ số (UI[n] = SDI[n]), nên được điều khiển bằng
`io.write` loại SDI qua bridge (cần bridge đang arm, xem rcs2/robot/client.py). Tín hiệu UO chỉ
được đọc (loại UO, không cần arm).

    UI[1] IMSTP  UI[2] HOLD  UI[3] SFSPD   phải BẬT (là ngõ vào "luôn BẬT": BẬT = không dừng / không giữ)
    UI[8] ENBL                             phải BẬT thì chương trình mới được chạy
    UI[9] RSR1                             xung = chọn RSR0001   (RSR n -> UI[8 + n])
    UI[5] RESET                            xung = reset lỗi, sau đó UO[6] FAULT phải TẮT
    UI[6] START                            xung = chạy chương trình đã chọn, sau đó UO[3] PROGRUN phải BẬT

Trình tự của `RobotStarter.start()` (thứ tự lúc chạy thử nghiệm thu cell):
    0. UO[3] PROGRUN đã BẬT      -> không cần làm gì
    1. SDI[1..3] = 1, SDI[8] = 1
    2. xung SDI[9]   (chọn RSR0001)
    3. xung SDI[5]   (reset), chờ UO[6] = 0            -> nếu không thì StartError "robot còn lỗi"
    4. xung SDI[6]   (start), chờ UO[3] = 1            -> nếu không thì StartError "chương trình chưa chạy"
Một xung là "ghi 1, chờ `pulse_s`, ghi 0", và số 0 vẫn được ghi kể cả khi có lỗi ở giữa.

Trình tự của `RobotStarter.stop()` (dùng được bất cứ lúc nào, kể cả khi đang chạy hoặc đang khởi động):
    1. xung SDI[4] (CSTOPI)           cycle stop: chương trình đang chạy được kết thúc
    2. SDI[1], SDI[2], SDI[3] = 0      tắt IMSTP, HOLD, SFSPD: robot dừng và không chạy lại được
       (bước 2 vẫn làm kể cả khi bước 1 lỗi; mọi lỗi đều được báo kèm lời nhắc dùng E-stop)
    3. chờ UO[3] PROGRUN = 0          -> nếu không thì StopError "robot chưa dừng"
Một trình tự khởi động đang chạy cùng lúc sẽ bị hủy. Khởi động lại (bước 1 của start) bật lại SDI[1..3].
UI[4] CSTOPI (cycle stop) và UI[5] RESET (reset lỗi) là hai tín hiệu khác nhau.

settings.json -> "robot_start" (đều tùy chọn, đây là giá trị mặc định):
    {"rsr": 1, "pulse_s": 0.3, "reset_wait_s": 3.0, "run_wait_s": 5.0, "stop_wait_s": 3.0, "poll_s": 0.05, "monitor_s": 0.5}

`monitor_s`: chu kỳ NewRCS đọc UO[3] PROGRUN để biết chương trình robot có đang chạy không (BridgeClient.program_state).
Mọi thứ ghi R[1] (chuyển động, vị trí an toàn, jog, sequence) đều bị chặn khi nó TẮT.
"""
import logging
import threading
import time

log = logging.getLogger("rcs2.uop")

KIND_IN, KIND_OUT = "SDI", "UO"            # UI[n] được điều khiển dưới dạng SDI[n]; UO[n] được đọc dưới dạng UO[n]

UI_IMSTP, UI_HOLD, UI_SFSPD, UI_CSTOPI, UI_RESET, UI_START, UI_ENBL, UI_RSR_BASE = 1, 2, 3, 4, 5, 6, 8, 8
UO_CMDENBL, UO_SYSRDY, UO_PROGRUN, UO_FAULT, UO_TPENBL = 1, 2, 3, 6, 8
UO_NAMES = {UO_CMDENBL: "CMDENBL", UO_SYSRDY: "SYSRDY", UO_PROGRUN: "PROGRUN", UO_FAULT: "FAULT", UO_TPENBL: "TPENBL"}

DEFAULTS = {"rsr": 1, "pulse_s": 0.3, "reset_wait_s": 3.0, "run_wait_s": 5.0, "stop_wait_s": 3.0, "poll_s": 0.05,
            "monitor_s": 0.5}


class StartError(Exception):
    """Không chạy được chương trình robot (cấu hình sai, lỗi I/O, chưa xóa được lỗi, chương trình không chạy)."""


class StopError(StartError):
    """Không chắc chắn đã dừng được robot (lỗi I/O, chương trình vẫn chạy): hãy dùng E-stop."""


def normalize(cfg):
    """settings["robot_start"] -> dict đầy đủ, đã kiểm tra. Ném StartError."""
    out = dict(DEFAULTS)
    out.update({k: v for k, v in (cfg or {}).items() if not str(k).startswith("_")})
    rsr = out["rsr"]
    if isinstance(rsr, bool) or not isinstance(rsr, int) or not 1 <= rsr <= 8:
        raise StartError("robot_start.rsr phải là số nguyên từ 1 đến 8 (RSR1..RSR8 = UI[9..16]), nhận %r" % (rsr,))
    for key in ("pulse_s", "reset_wait_s", "run_wait_s", "stop_wait_s", "poll_s", "monitor_s"):
        v = out[key]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 < v <= 60:
            raise StartError("robot_start.%s phải là số giây trong khoảng (0, 60], nhận %r" % (key, v))
    return out


class RobotStarter:
    """`io` = đối tượng giống BridgeClient (io_read / io_write)."""

    def __init__(self, io, cfg=None, sleep=time.sleep, clock=time.monotonic, log_fn=None, abort=None):
        """`abort` = threading.Event dùng chung cho bộ chạy và bộ dừng: stop() đặt nó, start() đang chạy sẽ bỏ dở."""
        self.io, self.sleep, self.clock = io, sleep, clock
        self.abort = abort if abort is not None else threading.Event()
        self.cfg = normalize(cfg)
        self.program = "RSR%04d" % self.cfg["rsr"]
        self.select_bit = UI_RSR_BASE + self.cfg["rsr"]
        self._log = log_fn or (lambda text: None)
        self._lock = threading.Lock()

    # ---- I/O ------------------------------------------------------------------------------------ #
    def _write(self, index, values):
        """SDI[index...] = values, đọc lại và so sánh."""
        try:
            back = self.io.io_write(KIND_IN, index, list(values))
        except Exception as ex:
            raise StartError("ghi %s[%d] thất bại (%s)" % (KIND_IN, index, ex))
        if [int(v) for v in back] != list(values):
            raise StartError("ghi %s[%d] = %s nhưng đọc lại %s" % (KIND_IN, index, list(values), list(back)))

    def _uo(self, index):
        try:
            return int(self.io.io_read(KIND_OUT, index, 1)[0])
        except Exception as ex:
            raise StartError("đọc %s[%d] thất bại (%s)" % (KIND_OUT, index, ex))

    def _pulse(self, index):
        self._write(index, [1])
        try:
            self.sleep(self.cfg["pulse_s"])
        finally:
            self._write(index, [0])                    # không bao giờ để ngõ vào BẬT

    def _check_abort(self):
        if self.abort.is_set():
            raise StartError("khởi động bị hủy: có lệnh dừng robot")

    def _wait_uo(self, index, value, timeout_s, abortable=True):
        end = self.clock() + timeout_s
        while True:
            if abortable:
                self._check_abort()
            if self._uo(index) == value:
                return True
            if self.clock() >= end:
                return False
            self.sleep(self.cfg["poll_s"])

    def _diag(self):
        """UO[1..8] cho thông báo lỗi ('' khi không đọc được)."""
        try:
            vals = self.io.io_read(KIND_OUT, 1, 8)
        except Exception:
            return ""
        shown = ", ".join("UO[%d] %s=%d" % (i, name, int(vals[i - 1])) for i, name in sorted(UO_NAMES.items())
                          if i - 1 < len(vals))
        return " (%s)" % shown

    # ---- trình tự ----------------------------------------------------------------------------------- #
    def start(self):
        """Chạy trình tự; trả về một câu kết quả ngắn. Ném StartError."""
        if not self._lock.acquire(False):
            raise StartError("đang có một lần khởi động chương trình khác")
        try:
            return self._start()
        finally:
            self._lock.release()

    def _start(self):
        name, say = self.program, self._log
        if self._uo(UO_PROGRUN) == 1:
            say("%s đã chạy (UO[%d] PROGRUN = 1): không cần khởi động" % (name, UO_PROGRUN))
            return "%s đã đang chạy" % name
        say("bật UI[%d] IMSTP, UI[%d] HOLD, UI[%d] SFSPD và UI[%d] ENBL" % (UI_IMSTP, UI_HOLD, UI_SFSPD, UI_ENBL))
        self._check_abort()
        self._write(UI_IMSTP, [1, 1, 1])               # SDI[1..3] trong một lần ghi
        self._write(UI_ENBL, [1])
        say("xung UI[%d] RSR%d: chọn chương trình %s" % (self.select_bit, self.cfg["rsr"], name))
        self._check_abort()
        self._pulse(self.select_bit)
        say("xung UI[%d] RESET: xóa lỗi" % UI_RESET)
        self._check_abort()
        self._pulse(UI_RESET)
        if not self._wait_uo(UO_FAULT, 0, self.cfg["reset_wait_s"]):
            raise StartError("robot còn lỗi sau khi reset: UO[%d] FAULT vẫn = 1 sau %.1fs%s"
                             % (UO_FAULT, self.cfg["reset_wait_s"], self._diag()))
        say("xung UI[%d] START: chạy chương trình" % UI_START)
        self._check_abort()
        self._pulse(UI_START)
        if not self._wait_uo(UO_PROGRUN, 1, self.cfg["run_wait_s"]):
            raise StartError("%s chưa chạy: UO[%d] PROGRUN vẫn = 0 sau %.1fs%s"
                             % (name, UO_PROGRUN, self.cfg["run_wait_s"], self._diag()))
        return "%s đang chạy" % name

    # ---- dừng --------------------------------------------------------------------------------------- #
    def stop(self):
        """Xung SDI[4] CSTOPI, tắt SDI[1..3], kiểm tra UO[3] PROGRUN = 0. Ném StopError. Không bao giờ từ chối chạy
        (không khóa, không chặn): dừng robot phải luôn làm được."""
        say = self._log
        self.abort.set()                               # một lần start đang chạy sẽ bỏ dở ở bước kế tiếp
        problems = []
        say("xung UI[%d] CSTOPI: dừng chương trình" % UI_CSTOPI)
        try:
            self._pulse(UI_CSTOPI)
        except StartError as ex:
            problems.append(str(ex))
        say("tắt UI[%d] IMSTP, UI[%d] HOLD, UI[%d] SFSPD" % (UI_IMSTP, UI_HOLD, UI_SFSPD))
        try:
            self._write(UI_IMSTP, [0, 0, 0])           # vẫn làm kể cả khi xung bị lỗi
        except StartError as ex:
            problems.append(str(ex))
        if problems:
            raise StopError("không chắc robot đã dừng, hãy dùng E-stop: %s" % "; ".join(problems))
        if not self._wait_uo(UO_PROGRUN, 0, self.cfg["stop_wait_s"], abortable=False):
            raise StopError("robot chưa dừng: UO[%d] PROGRUN vẫn = 1 sau %.1fs, hãy dùng E-stop%s"
                            % (UO_PROGRUN, self.cfg["stop_wait_s"], self._diag()))
        return "%s đã dừng" % self.program
