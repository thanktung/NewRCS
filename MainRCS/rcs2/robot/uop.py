"""Start / stop the robot program RSR0001 through the UOP signals of the FANUC controller (UI / UO [1-18]).

The UI signals are mapped to the standard digital inputs with the SAME index (UI[n] = SDI[n]), so they are driven with
`io.write` on kind SDI through the bridge (it needs the bridge to be armed, see rcs2/robot/client.py). The UO signals are only
read (kind UO, no arm needed).

    UI[1] IMSTP  UI[2] HOLD  UI[3] SFSPD   must be ON (they are "always ON" inputs: ON = not stopped / not held)
    UI[8] ENBL                             must be ON so that the program is allowed to run
    UI[9] RSR1                             pulse = select RSR0001   (RSR n -> UI[8 + n])
    UI[5] RESET                            pulse = reset the fault, then UO[6] FAULT must be OFF
    UI[6] START                            pulse = start the selected program, then UO[3] PROGRUN must turn ON

Sequence of `RobotStarter.start()` (the order the cell was commissioned with):
    0. UO[3] PROGRUN already ON  -> nothing to do
    1. SDI[1..3] = 1, SDI[8] = 1
    2. pulse SDI[9]   (select RSR0001)
    3. pulse SDI[5]   (reset), wait for UO[6] = 0            -> StartError "robot còn lỗi" otherwise
    4. pulse SDI[6]   (start), wait for UO[3] = 1            -> StartError "chương trình chưa chạy" otherwise
A pulse is "write 1, wait `pulse_s`, write 0" and the 0 is written even when something fails in between.

Sequence of `RobotStarter.stop()` (works at any time, also while a run or a start is in progress):
    1. pulse SDI[4] (CSTOPI)           cycle stop: the running program is ended
    2. SDI[1], SDI[2], SDI[3] = 0      IMSTP, HOLD, SFSPD off: the robot stops and cannot be started
       (step 2 is done even if step 1 failed; any failure is reported and says to use the E-stop)
    3. wait for UO[3] PROGRUN = 0      -> StopError "robot chưa dừng" otherwise
A start sequence that is running at the same time is aborted. Starting again (step 1 of the start) switches SDI[1..3] on again.
UI[4] CSTOPI (cycle stop) and UI[5] RESET (reset fault) are two separate signals.

settings.json -> "robot_start" (all optional, these are the defaults):
    {"rsr": 1, "pulse_s": 0.3, "reset_wait_s": 3.0, "run_wait_s": 5.0, "stop_wait_s": 3.0, "poll_s": 0.05, "monitor_s": 0.5}

`monitor_s`: how often NewRCS reads UO[3] PROGRUN to know whether the robot program is running (BridgeClient.program_state).
Nothing that writes R[1] (motions, safe position, jog, sequences) is allowed while it is OFF.
"""
import logging
import threading
import time

log = logging.getLogger("rcs2.uop")

KIND_IN, KIND_OUT = "SDI", "UO"            # UI[n] is driven as SDI[n]; UO[n] is read as UO[n]

UI_IMSTP, UI_HOLD, UI_SFSPD, UI_CSTOPI, UI_RESET, UI_START, UI_ENBL, UI_RSR_BASE = 1, 2, 3, 4, 5, 6, 8, 8
UO_CMDENBL, UO_SYSRDY, UO_PROGRUN, UO_FAULT, UO_TPENBL = 1, 2, 3, 6, 8
UO_NAMES = {UO_CMDENBL: "CMDENBL", UO_SYSRDY: "SYSRDY", UO_PROGRUN: "PROGRUN", UO_FAULT: "FAULT", UO_TPENBL: "TPENBL"}

DEFAULTS = {"rsr": 1, "pulse_s": 0.3, "reset_wait_s": 3.0, "run_wait_s": 5.0, "stop_wait_s": 3.0, "poll_s": 0.05,
            "monitor_s": 0.5}


class StartError(Exception):
    """The robot program could not be started (bad configuration, I/O failure, fault not cleared, program not running)."""


class StopError(StartError):
    """The robot could not be stopped for sure (I/O failure, program still running): use the E-stop."""


def normalize(cfg):
    """settings["robot_start"] -> complete, validated dict. Raises StartError."""
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
    """`io` = BridgeClient-like (io_read / io_write)."""

    def __init__(self, io, cfg=None, sleep=time.sleep, clock=time.monotonic, log_fn=None, abort=None):
        """`abort` = threading.Event shared by the starter and the stopper: stop() sets it, a running start() gives up."""
        self.io, self.sleep, self.clock = io, sleep, clock
        self.abort = abort if abort is not None else threading.Event()
        self.cfg = normalize(cfg)
        self.program = "RSR%04d" % self.cfg["rsr"]
        self.select_bit = UI_RSR_BASE + self.cfg["rsr"]
        self._log = log_fn or (lambda text: None)
        self._lock = threading.Lock()

    # ---- I/O ------------------------------------------------------------------------------------ #
    def _write(self, index, values):
        """SDI[index...] = values, read back and compared."""
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
            self._write(index, [0])                    # never leave the input ON

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
        """UO[1..8] for the error message ('' when it cannot be read)."""
        try:
            vals = self.io.io_read(KIND_OUT, 1, 8)
        except Exception:
            return ""
        shown = ", ".join("UO[%d] %s=%d" % (i, name, int(vals[i - 1])) for i, name in sorted(UO_NAMES.items())
                          if i - 1 < len(vals))
        return " (%s)" % shown

    # ---- the sequence ------------------------------------------------------------------------------ #
    def start(self):
        """Runs the sequence; returns a short result text. Raises StartError."""
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
        self._write(UI_IMSTP, [1, 1, 1])               # SDI[1..3] in one write
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

    # ---- stop --------------------------------------------------------------------------------------- #
    def stop(self):
        """Pulse SDI[4] CSTOPI, switch SDI[1..3] off, check UO[3] PROGRUN = 0. Raises StopError. Never refuses to run
        (no lock, no guard): stopping must always be possible."""
        say = self._log
        self.abort.set()                               # a start that is running gives up at its next step
        problems = []
        say("xung UI[%d] CSTOPI: dừng chương trình" % UI_CSTOPI)
        try:
            self._pulse(UI_CSTOPI)
        except StartError as ex:
            problems.append(str(ex))
        say("tắt UI[%d] IMSTP, UI[%d] HOLD, UI[%d] SFSPD" % (UI_IMSTP, UI_HOLD, UI_SFSPD))
        try:
            self._write(UI_IMSTP, [0, 0, 0])           # done even when the pulse failed
        except StartError as ex:
            problems.append(str(ex))
        if problems:
            raise StopError("không chắc robot đã dừng, hãy dùng E-stop: %s" % "; ".join(problems))
        if not self._wait_uo(UO_PROGRUN, 0, self.cfg["stop_wait_s"], abortable=False):
            raise StopError("robot chưa dừng: UO[%d] PROGRUN vẫn = 1 sau %.1fs, hãy dùng E-stop%s"
                            % (UO_PROGRUN, self.cfg["stop_wait_s"], self._diag()))
        return "%s đã dừng" % self.program
