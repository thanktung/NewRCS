"""Scheduling engine.

One engine thread owns all state and handles events one at a time (ATS messages, operator commands,
job completions, ticks), so there are no shared-flag races. Robot sequences are blocking, so they run
in a separate job thread (one at a time: there is one robot) and report back with an event.

Per fixture:  OFFLINE/No Used -> IDLE --WAITDUT--> load job -> TESTING --result--> unload job -> IDLE ...
Robot jobs are the sequences "load" and "unload_pass" / "unload_ng" / "unload_retest" / "unload_fqc"
(see rcs2/core/sequence.py). Tested DUTs are unloaded before new ones are loaded.

Alarm codes (kept from the old RCS where they existed)
  9026 RCS stop/pause    9011 consecutive NG    9012 ATS not connected    9013 fixture error
  9010 test timeout      9201 robot/sequence error                         9100 robot link / disarmed
  9202 barcode could not be read (scan step failed after its retries; nothing was picked)
  9203 End Effector heads error (a head did not pick up / release, cylinder did not reach its position, I/O failure)
  9204 End Effector laser (IL-1000) check failed
  9205 the points needed by the tray flow are not taught yet (Start refused)
  9206 tray flow: no untested product left and everything is put away -> put a new input tray, then press "Nạp lại"
  9207 tray flow: the NG tray is full -> empty / change it, then press "Đã dọn"
  9209 tray flow: every output tray (passed products) is full -> empty / change them, then press "Đã dọn" of that tray
  9208 tray flow: a head dropped its product (carry check) -> run stopped and the robot program stopped
Trays (input / NG, see rcs2/core/tray.py): a load takes one cell from the input tray, an NG unload fills one cell of the
NG tray. No load starts while the input tray is empty.

Two flows (settings.json -> flow.mode). "classic" is the one described above. "tray" (rcs2/core/flow.py) serves up to 8 heads and
many boxes: the planner decides, the robot runs STAGES (pick / swap / sort), and a stage commit updates the books of every product
as the robot really finishes it; a stop takes effect between two stages.
"""
import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime

from ..ats import protocol as AP
from ..devices.heads import HeadError
from .flow import FlowController, FlowError, FlowSettings
from .geometry import GeometryError
from .sequence import SequenceError, SequenceRunner, validate
from .tasks import DropError
from .states import (FAULT, IDLE, LOADING, NO_USED, OFFLINE, PAUSED, RESULT, RUN_FAULT, RUNNING, STOPPED, TESTING,
                     UNLOADING, WAIT_LOAD)
from .tray import build_trays

log = logging.getLogger("rcs2.engine")

RESULT_LABEL = {AP.PASS: "PASS", AP.NG: "NG", AP.RETEST: "RETEST", AP.RETEST1: "RETEST",
                AP.FQC: "FQC", AP.WARNING: "WARNING", AP.OFFSET_PASS: "PASS", AP.OFFSET_NG: "NG"}
COUNTS_AS_FAIL = ("NG", "RETEST", "WARNING")
UNLOAD_SEQUENCE = {"PASS": ("unload_pass",), "NG": ("unload_ng",), "RETEST": ("unload_retest", "unload_ng"),
                   "FQC": ("unload_fqc", "unload_pass"), "WARNING": ("unload_ng",)}


@dataclass
class Fixture:
    number: int
    station: str
    robot_station: int
    ats_host: str = ""
    enabled: bool = False
    connected: bool = False
    ats_ready: bool = False        # the ATS reported "waiting for a DUT"
    dut_inside: bool = False
    state: str = OFFLINE
    sn: str = ""
    total: int = 0
    passed: int = 0
    ng: int = 0
    retest: int = 0
    consec_ng: int = 0
    last_result: str = ""
    last_detail: str = ""
    last_test_time: float = 0.0
    test_started: float = 0.0
    message: str = ""
    dut: object = None             # tray flow: the product inside (dut.Dut)
    finished: bool = False         # tray flow: the result of `dut` is in and it waits to be taken out
    idle_since: float = 0.0        # tray flow: since when the box waits for the robot

    @property
    def yield_pct(self):
        return (100.0 * self.passed / self.total) if self.total else None


@dataclass
class Job:
    id: int
    kind: str                     # "load" | "unload"
    fixture: int
    result: str = ""
    sn: str = ""                  # barcode read by a scanner step of the sequence
    sequence: str = ""            # name of the sequence that ran (set when the job starts)
    task: object = None           # tray flow: the planner task this job carries out
    stages: list = field(default_factory=list)     # tray flow: the stages (tasks.Stage) of the task
    created: float = field(default_factory=time.time)


class Engine:
    def __init__(self, settings, robot, ats, sink, errors, sequences, points, clock=time.monotonic, ee=None, trays=None):
        self.cfg = settings
        self.robot = robot
        self.ats = ats                      # {fixture_no: AtsClient-like}
        self.sink = sink
        self.errors = errors
        self.sequences = sequences
        self.points = points
        self.clock = clock
        self.on_log = None                  # callable(level, text) for the UI log
        self.block_reason = ""              # non-empty: Start is refused (e.g. example points on a real robot)

        self.ee = ee                        # the End Effector (heads / scanner / laser) or None
        validate(sequences, points, ee.capabilities() if ee is not None else None)
        self.trays = build_trays(trays)     # {"input": Tray, "ng": Tray}; empty = trays not configured
        heads = getattr(getattr(ee, "heads", None), "count", 0)         # number of suction heads (a stand-in End Effector may have none)
        self.flow_settings = FlowSettings.from_config(settings, heads)
        if self.flow_settings.mode == "classic":
            for name in ("load", "unload_pass", "unload_ng"):
                if name not in sequences:
                    raise SequenceError("sequence %r is required" % name)

        e = settings["engine"]
        self.reload_after_unload = e["reload_after_unload"]
        self.auto_start_test = e["auto_start_test"]
        self.send_dut_out = e["send_dut_out"]
        self.test_timeout_s = e["test_timeout_s"]
        self.ng_limit = settings["consecutive_ng"]["limit"]
        self.ng_stop = settings["consecutive_ng"]["stop_fixture"]

        self.fixtures = {}
        for key, f in settings["ats"]["fixtures"].items():
            n = int(key)
            self.fixtures[n] = Fixture(n, f.get("station", "Station1"), int(f.get("robot_station", n)),
                                       ats_host=f.get("host", ""))
        self.flow = None                    # FlowController in the "tray" flow, otherwise None
        self.on_drop = None                 # callable(text): a head dropped its product (the runtime stops the robot program)
        if self.flow_settings.mode == "tray":
            laser = getattr(ee, "laser", None)
            if self.flow_settings.laser and (laser is None or not getattr(laser, "enabled", True)):
                raise FlowError("flow.laser_check is on but the End Effector has no enabled laser (end_effector.laser.enabled)")
            self.flow = FlowController(self.flow_settings, trays, self.fixtures.keys(), heads,
                                       getattr(ee, "scanner", None) is not None, settings["bridge"].get("default_override"), e)
        self.run_state = STOPPED
        self.fault_text = ""
        self._armed_at = 0.0
        self._disarm_after_job = False
        self._jobs = []
        self._job_seq = 0
        self._current = None
        self._events = queue.Queue()
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._cancel = threading.Event()
        self._thread = None
        self._tray_warned = set()           # tray kinds whose "empty / full" warning was already logged
        self._program_off_since = None      # since when UO[3] PROGRUN is off (None = on / unknown)
        self._runner = SequenceRunner(robot, ats, points, settings["bridge"].get("default_override"),
                                      log=lambda m: self._log("debug", m), ee=ee)

    # ------------------------------------------------------------------ #
    # lifecycle
    # ------------------------------------------------------------------ #
    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="engine", daemon=True)
        self._thread.start()

    def shutdown(self):
        self._stop.set()
        self._cancel.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)

    def post(self, *event):
        self._events.put(event)

    def _log(self, level, text):
        getattr(log, level if level != "warn" else "warning")(text)
        if self.on_log and level != "debug":          # per-step details only go to the log file
            try:
                self.on_log(level, text)
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    # public commands (thread safe: they only post events)
    # ------------------------------------------------------------------ #
    def start_run(self):
        self.post("cmd", "start")

    def pause_run(self):
        self.post("cmd", "pause")

    def stop_run(self):
        self.post("cmd", "stop")

    def acknowledge_fault(self):
        self.post("cmd", "ack_fault")

    def wait_processed(self, timeout=2.0):
        """Blocks until every command posted before this call has been handled by the engine thread (False if the
        engine is not running or did not answer in time). Lets a caller be sure that e.g. the disarm that follows
        stop_run() has happened, instead of landing in the middle of its own next arm."""
        thread = self._thread
        if thread is None or not thread.is_alive():
            return False
        done = threading.Event()
        self.post("cmd", "sync", done)
        return done.wait(timeout)

    def set_enabled(self, number, enabled):
        self.post("cmd", "enable", number, bool(enabled))

    def reset_fixture(self, number, dut_inside):
        self.post("cmd", "reset_fixture", number, bool(dut_inside))

    def reset_tray(self, kind):
        """The operator refilled the input tray / emptied the NG tray."""
        self.post("cmd", "reset_tray", kind)

    def reset_flow(self):
        """Tray flow: the operator cleared every head and box by hand: forget where all products were and start again."""
        self.post("cmd", "reset_flow")

    def on_ats_event(self, number, event):
        self.post("ats", number, event)

    def on_ats_connection(self, number, connected):
        self.post("ats_conn", number, connected)

    # ------------------------------------------------------------------ #
    # snapshot for the UI
    # ------------------------------------------------------------------ #
    def snapshot(self):
        with self._lock:
            fixtures = []
            for f in self.fixtures.values():
                fixtures.append({
                    "number": f.number, "station": f.station, "state": self._ui_state(f),
                    "enabled": f.enabled, "connected": f.connected, "sn": f.sn, "total": f.total,
                    "passed": f.passed, "ng": f.ng, "retest": f.retest, "yield_pct": f.yield_pct,
                    "consec_ng": f.consec_ng, "last_result": f.last_result, "last_detail": f.last_detail,
                    "last_test_time": f.last_test_time, "message": f.message,
                    "elapsed": (self.clock() - f.test_started) if f.state == TESTING and f.test_started else 0.0,
                    "dut_inside": f.dut_inside, "host": f.ats_host,
                    "dut": f.dut.id if f.dut is not None else None, "cell": f.dut.origin if f.dut is not None else None,
                    "tests": f.dut.tests_made if f.dut is not None else 0})
            total = sum(f.total for f in self.fixtures.values())
            passed = sum(f.passed for f in self.fixtures.values())
            return {
                "run_state": self.run_state, "fault_text": self.fault_text,
                "fixtures": fixtures,
                "queue": [(j.kind, j.fixture) for j in self._jobs],
                "current_job": (self._current.kind, self._current.fixture) if self._current else None,
                "robot": dict(getattr(self.robot, "last_status", {}) or {}),
                "robot_link": bool(getattr(self.robot, "connected", False)),
                "program_running": getattr(self.robot, "program_state", None),    # UO[3] PROGRUN: True / False / None
                "alarms": self.errors.active() if hasattr(self.errors, "active") else [],
                "sink": self.sink.stats() if self.sink else {},
                "totals": {"total": total, "passed": passed, "yield_pct": (100.0 * passed / total) if total else None},
                "trays": {kind: t.snapshot() for kind, t in self.trays.items()},
                "flow": self.flow.snapshot() if self.flow is not None else None,
            }

    @staticmethod
    def _ui_state(f):
        if f.state == FAULT:
            return FAULT
        if not f.enabled:
            return NO_USED
        if not f.connected:
            return OFFLINE
        return f.state

    # ------------------------------------------------------------------ #
    # engine thread
    # ------------------------------------------------------------------ #
    def _loop(self):
        last_tick = 0.0
        while not self._stop.is_set():
            try:
                ev = self._events.get(timeout=0.1)
            except queue.Empty:
                ev = None
            try:
                with self._lock:
                    if ev is not None:
                        self._handle(ev)
                    now = self.clock()
                    if now - last_tick >= 0.2:
                        last_tick = now
                        self._tick(now)
                    self._dispatch()
            except Exception:
                log.exception("engine error while handling %r", ev)
                self._log("error", "lỗi nội bộ của engine, xem file log")

    def _handle(self, ev):
        kind = ev[0]
        if kind == "ats":
            self._on_ats(ev[1], ev[2])
        elif kind == "ats_conn":
            self._on_ats_conn(ev[1], ev[2])
        elif kind == "job_done":
            self._on_job_done(ev[1], ev[2], ev[3])
        elif kind == "flow_commit":
            self._on_flow_commit(ev[1], ev[2])
        elif kind == "cmd":
            getattr(self, "_cmd_" + ev[1])(*ev[2:])

    # ---- commands ------------------------------------------------------- #
    def _cmd_start(self):
        if self.block_reason:
            self._log("error", "không thể bắt đầu: %s" % self.block_reason)
            return
        if self.run_state == RUN_FAULT:
            self._log("warn", "không thể bắt đầu: hãy xác nhận lỗi trước (%s)" % self.fault_text)
            return
        if self.flow is not None and not self._prepare_flow():
            return
        if not getattr(self.robot, "connected", False):
            self._log("error", "không thể bắt đầu: chưa kết nối bridge robot")
            self.errors.raise_error("9100", "chưa kết nối bridge robot", key="robot_link")
            return
        refresh = getattr(self.robot, "refresh_program_state", None)     # a stand-in without UO[3] reading: not checked
        if refresh is not None:
            state = refresh()                                              # fresh read of UO[3] PROGRUN
            if state is not True:
                why = ("chương trình robot chưa chạy (UO[3] PROGRUN = 0): hãy bấm 'Chạy chương trình' trước" if state is False
                       else "không đọc được UO[3] PROGRUN")
                self._log("error", "không thể bắt đầu: %s" % why)
                self.errors.raise_error("9100", why, key="robot_program")
                return
            self.errors.clear_error("robot_program")
        try:
            self.robot.arm()
        except Exception as ex:
            self._log("error", "không thể arm robot: %s" % ex)
            self.errors.raise_error("9100", "không thể arm robot: %s" % ex, key="robot_link")
            return
        self.errors.clear_error("robot_link")
        self.errors.clear_error("run_stop")
        self._armed_at = self.clock()
        self._disarm_after_job = False
        self.run_state = RUNNING
        self._log("info", "đã bắt đầu chạy")
        for f in self.fixtures.values():
            if f.dut is None and not f.idle_since:
                f.idle_since = self._armed_at            # tray flow: every empty box waits from the start
            self._maybe_queue_load(f)

    def _cmd_sync(self, done):
        done.set()

    def _cmd_pause(self):
        if self.run_state == RUNNING:
            self.run_state = PAUSED
            self.errors.raise_error("9026", "RCS dừng", key="run_stop")
            self._log("info", "đã tạm dừng (việc robot đang làm sẽ chạy xong trước)")

    def _cmd_stop(self):
        self.run_state = STOPPED if self.run_state != RUN_FAULT else RUN_FAULT
        self._drop_load_jobs()                                          # keep unloads: DUTs must not stay inside
        self.errors.raise_error("9026", "RCS dừng", key="run_stop")
        if self._current is None:
            self._disarm_robot()
        else:
            self._disarm_after_job = True      # never disarm in the middle of a sequence
        self._log("info", "đã dừng chạy")

    def _disarm_robot(self):
        self._disarm_after_job = False
        try:
            self.robot.disarm()
        except Exception:
            pass

    def _cmd_ack_fault(self):
        if self.run_state != RUN_FAULT:
            return
        try:
            self.robot.fault_clear()
        except Exception as ex:
            self._log("warn", "fault.clear: %s" % ex)
        self.errors.clear_error("robot")
        self.fault_text = ""
        self.run_state = PAUSED
        self._log("info", "đã xác nhận lỗi; hãy kiểm tra cell, đặt lại fixture rồi bấm Bắt đầu")

    def _cmd_enable(self, number, enabled):
        f = self.fixtures.get(number)
        if f is None:
            return
        f.enabled = enabled
        if enabled:
            if f.dut is None:
                f.idle_since = self.clock()
            self.errors.clear_error("ng_%d" % number)
            f.consec_ng = 0
            if f.state == NO_USED or f.state == OFFLINE:
                f.state = IDLE
            self._maybe_queue_load(f)
        else:
            self._drop_load_jobs(number)
        self._log("info", "fixture %d %s" % (number, "đã bật" if enabled else "đã tắt"))

    def _drop_load_jobs(self, number=None):
        """Remove queued 'load' jobs (all, or only those of one fixture) and free their fixtures."""
        keep = []
        for j in self._jobs:
            if j.kind == "load" and (number is None or j.fixture == number):
                f = self.fixtures[j.fixture]
                if f.state == WAIT_LOAD:
                    f.state = IDLE
            else:
                keep.append(j)
        self._jobs = keep

    def _cmd_reset_flow(self):
        if self.flow is None:
            return
        if self._current is not None:
            self._log("warn", "robot đang làm việc: hãy dừng chạy rồi đợi xong trước khi xóa trạng thái luồng")
            return
        self.flow.reset("all")
        for key in ("tray_input", "tray_ng"):
            self.errors.clear_error(key)
        for f in self.fixtures.values():
            f.dut, f.finished, f.dut_inside, f.sn, f.message = None, False, False, "", ""
            f.idle_since = self.clock()
            if f.state in (TESTING, RESULT, LOADING, UNLOADING, FAULT, WAIT_LOAD):
                f.state = IDLE
        for tray in self.trays.values():
            tray.reset()
        self._tray_warned.clear()
        self.errors.clear_error("robot")
        self._log("info", "đã xóa trạng thái luồng: mọi tay hút và box được coi là trống, tray input đầy, tray NG trống")

    def _cmd_reset_tray(self, kind):
        tray = self.trays.get(kind)
        if tray is None:
            return
        if self.flow is not None:
            if kind == "input" and self.flow.in_flight():
                self._log("warn", "còn %d sản phẩm trên tay hút / trong box: không thể đặt lại tray input "
                                  "(nếu đã dọn tay hết, dùng 'Xóa trạng thái luồng')" % len(self.flow.in_flight()))
                return
            self.flow.reset(kind)
            self.errors.clear_error({"input": "tray_input", "ng": "tray_ng"}.get(kind, "tray_output"))
        tray.reset()
        self._tray_warned.discard(kind)
        self._log("info", "tray %s đã đặt lại (%s)" % (kind, "đã nạp lại" if kind == "input" else "đã dọn trống"))

    def _cmd_reset_fixture(self, number, dut_inside):
        f = self.fixtures.get(number)
        if f is None or (self._current and self._current.fixture == number):
            return
        if self.flow is not None:
            self._log("warn", "luồng tray: không đặt lại từng fixture; dùng 'Xóa trạng thái luồng' sau khi đã dọn tay")
            return
        f.dut_inside = dut_inside
        f.message = ""
        f.state = IDLE
        self.errors.clear_error("fix_%d" % number)
        if dut_inside:
            f.state = RESULT
            self._queue_job("unload", number, "NG")
        else:
            self._maybe_queue_load(f)
        self._log("info", "fixture %d đã đặt lại (DUT bên trong: %s)" % (number, "có" if dut_inside else "không"))

    # ---- ATS events ----------------------------------------------------- #
    def _on_ats_conn(self, number, connected):
        f = self.fixtures.get(number)
        if f is None:
            return
        f.connected = connected
        if connected:
            self.errors.clear_error("ats_%d" % number)
            if f.state == OFFLINE:
                f.state = IDLE
        else:
            f.ats_ready = False
            if f.enabled:
                self.errors.raise_error("9012", "ATS %d chưa kết nối" % number, key="ats_%d" % number)

    def _on_ats(self, number, ev):
        f = self.fixtures.get(number)
        if f is None:
            return
        if ev.kind == AP.WAITDUT:
            f.ats_ready = True
            if not f.dut_inside:
                self._maybe_queue_load(f)
        elif ev.kind in (AP.BARCODE, AP.BARCODE_PASS):
            f.sn = ev.sn or f.sn
        elif ev.kind == AP.FIX_ERROR:
            self.errors.raise_error("9013", "fixture %d lỗi jig" % number, key="fix_%d" % number)
        elif ev.kind in RESULT_LABEL:
            self._on_result(f, ev)

    def _on_result(self, f, ev):
        if not f.dut_inside or f.state != TESTING:
            self._log("warn", "fixture %d: bỏ qua %s không mong đợi (trạng thái %s)" % (f.number, ev.kind, f.state))
            return
        label = RESULT_LABEL[ev.kind]
        elapsed = self.clock() - f.test_started
        f.total += 1
        if label == "PASS":
            f.passed += 1
            f.consec_ng = 0
        elif label == "NG":
            f.ng += 1
        elif label == "RETEST":
            f.retest += 1
        if label in COUNTS_AS_FAIL:
            f.consec_ng += 1
        f.last_result, f.last_test_time = label, elapsed
        f.last_detail = ("%s=%s" % (ev.item, ev.value)) if ev.kind == AP.NG else ev.detail
        f.state = RESULT
        self.errors.clear_error("test_timeout_%d" % f.number)
        self.sink.emit_result(f.ats_host, "FIXTURE %d" % f.number, label, elapsed, "NORMAL")
        self._log("info", "fixture %d: %s trong %.1fs %s" % (f.number, label, elapsed, f.last_detail))
        if f.consec_ng >= self.ng_limit:
            msg = "Fixture %d: %d lần NG/retest liên tiếp" % (f.number, f.consec_ng)
            self.errors.raise_error("9011", msg, key="ng_%d" % f.number)
            self._log("warn", msg)
            f.consec_ng = 0
            if self.ng_stop:
                f.enabled = False       # no new DUT; the tested one is still taken out (the old RCS left it inside)
        if self.flow is not None:
            self._log("info", self.flow.result(f, label, elapsed, self.fixtures, self.clock())[1])
            return                                     # the planner takes the product out when the robot is free
        self._queue_job("unload", f.number, label)

    # ---- jobs ----------------------------------------------------------- #
    def _maybe_queue_load(self, f):
        if self.flow is not None:
            return                                     # the tray flow has its own planner
        if (self.run_state == RUNNING and f.enabled and f.connected and f.ats_ready and not f.dut_inside
                and f.state in (IDLE, OFFLINE, NO_USED)
                and not any(j.fixture == f.number for j in self._jobs)
                and not (self._current and self._current.fixture == f.number)):
            self._queue_job("load", f.number)

    def _queue_job(self, kind, number, result=""):
        self._job_seq += 1
        self._jobs.append(Job(self._job_seq, kind, number, result))
        self.fixtures[number].state = WAIT_LOAD if kind == "load" else RESULT

    def _next_job(self):
        for j in self._jobs:
            if j.kind == "unload":
                return j
        input_tray = self.trays.get("input")
        no_stock = input_tray is not None and input_tray.exhausted
        for j in self._jobs:
            f = self.fixtures[j.fixture]
            if f.enabled and f.connected and not (j.kind == "load" and no_stock):    # nothing left to load
                return j
        return None

    def _dispatch(self):
        if self.flow is not None:
            self._dispatch_flow()
            return
        if self._current is not None or self.run_state != RUNNING or not self._jobs:
            return
        if getattr(self.robot, "program_state", None) is False:
            return                                                     # no command may be written while the program is off
        if not getattr(self.robot, "connected", False):
            return
        job = self._next_job()
        if job is None:
            return
        self._jobs.remove(job)
        self._current = job
        f = self.fixtures[job.fixture]
        f.state = LOADING if job.kind == "load" else UNLOADING
        threading.Thread(target=self._run_job, args=(job,), name="job-%d" % job.id, daemon=True).start()

    def _run_job(self, job):
        f = self.fixtures[job.fixture]
        variables = {"fixture": f.number, "robot_station": f.robot_station, "station": f.station,
                     "result": job.result}
        try:
            if job.kind == "load":
                names = ("load",)
            else:
                names = UNLOAD_SEQUENCE.get(job.result, ("unload_ng",))
            name = next((n for n in names if n in self.sequences), None)
            if name is None:
                raise SequenceError("no sequence for %s (%s)" % (job.kind, job.result))
            job.sequence = name
            self._log("info", "việc robot %d: %s fixture %d (%s)" % (job.id, name, f.number, job.result or "-"))
            def scanned(code, tool):
                job.sn = code
                with self._lock:
                    f.sn = code
                self._log("info", "fixture %d: đã đọc mã %s (máy quét của End Effector)" % (f.number, code))
            self._runner.run(name, self.sequences[name], variables, cancel=self._cancel, on_scan=scanned)
            self.post("job_done", job.id, True, "")
        except Exception as ex:
            self.post("job_done", job.id, False, "%s: %s" % (type(ex).__name__, ex))

    def _on_job_done(self, job_id, ok, error):
        job, self._current = self._current, None
        if job is None or job.id != job_id:
            return
        if self._disarm_after_job and self.run_state != RUNNING:
            self._disarm_robot()
        if job.kind == "flow":
            self._on_flow_job_done(job, ok, error)
            return
        f = self.fixtures[job.fixture]
        if not ok:
            f.state, f.message = FAULT, error
            self.fault_text = "fixture %d %s: %s" % (f.number, {"load": "nạp", "unload": "lấy ra"}.get(job.kind, job.kind), error)
            self.run_state = RUN_FAULT
            code = {"ScanError": "9202", "HeadError": "9203", "LaserError": "9204"}.get(error.split(":", 1)[0], "9201")
            self.errors.raise_error(code, self.fault_text, key="robot")
            self._log("error", "việc robot thất bại - dừng chạy: %s" % self.fault_text)
            return
        self._count_tray(job)
        if job.kind == "load":
            f.dut_inside = True
            f.sn = job.sn                     # "" unless a scan step read the code (the ATS may report it later)
            if self.auto_start_test:
                ats = self.ats.get(f.number)
                if ats is not None and ats.place_dut_ok():
                    f.state, f.test_started = TESTING, self.clock()
                else:
                    f.state, f.message = FAULT, "ATS chưa kết nối: không thể bắt đầu test"
                    self.errors.raise_error("9012", "ATS %d chưa kết nối" % f.number, key="ats_%d" % f.number)
            else:
                f.state = IDLE
        else:
            f.dut_inside = False
            f.state = IDLE
            if self.send_dut_out and self.ats.get(f.number):
                self.ats[f.number].dut_out()
            if self.reload_after_unload:
                self._maybe_queue_load(f)

    def _count_tray(self, job):
        """A finished load took a DUT from the input tray; a finished NG unload put one into the NG tray."""
        kind = "input" if job.kind == "load" else "ng" if job.sequence == "unload_ng" else None
        tray = self.trays.get(kind)
        if tray is None:
            return
        tray.advance()
        if tray.exhausted and kind not in self._tray_warned:
            self._tray_warned.add(kind)
            self._log("warn", "tray input đã hết hàng: hãy nạp tray rồi bấm 'Nạp lại'" if kind == "input"
                      else "tray NG đã đầy: hãy dọn tray rồi bấm 'Đã dọn'")

    # ---- tray flow ------------------------------------------------------- #
    def _prepare_flow(self):
        """Start of a run in the tray flow: every taught point must be there. False (alarm 9205) when something is missing."""
        missing = self.flow.missing_points(self.points)
        why = ""
        if missing:
            why = "chưa dạy đủ điểm cho luồng tray: %s" % ", ".join(missing)
        else:
            try:
                self.flow.prepare(self.points)
            except GeometryError as ex:
                why = "điểm đã dạy không hợp lệ: %s" % ex
        if why:
            self._log("error", "không thể bắt đầu: %s" % why)
            self.errors.raise_error("9205", why, key="flow_layout")
            return False
        self.errors.clear_error("flow_layout")
        return True

    def _dispatch_flow(self):
        if self._current is not None or self.run_state != RUNNING or self.flow.layout is None:
            return
        if getattr(self.robot, "program_state", None) is False or not getattr(self.robot, "connected", False):
            return                                                       # no command may be written while the program is off
        task = self.flow.plan(self.flow.world(self.clock(), self.fixtures))
        if task is None:
            return
        try:
            stages = self.flow.build(task)
        except Exception as ex:                                          # bad geometry: never send a half-known pose
            self._fail_flow("%s: %s" % (type(ex).__name__, ex), None)
            return
        self._job_seq += 1
        job = Job(self._job_seq, "flow", getattr(task, "fixture", 0) or 0, task=task, stages=stages, sequence=task.kind)
        self._current = job
        f = self.fixtures.get(job.fixture)
        if f is not None and f.state in (IDLE, RESULT, TESTING, WAIT_LOAD):
            f.state = UNLOADING if f.dut is not None else LOADING
        self._log("info", "việc robot %d (%s): %s" % (job.id, task.kind, task.reason))
        threading.Thread(target=self._run_flow_job, args=(job,), name="job-%d" % job.id, daemon=True).start()

    def _run_flow_job(self, job):
        def scanned(code, tool, tag=None):
            self.post("flow_commit", job.id, {"op": "sn", "tag": tag or "cell:-1", "sn": code})
        stage = None
        try:
            for stage in job.stages:
                if self._cancel.is_set() or self.run_state != RUNNING:
                    self.post("job_done", job.id, True, "")               # stopped between two stages: the books are exact
                    return
                try:
                    self._runner.run(stage.label, stage.steps, {}, cancel=self._cancel, on_scan=scanned)
                except HeadError as ex:
                    if stage.kind == "carry":                              # a head that carried a product does not hold it any more
                        raise DropError("%s" % ex)
                    raise
                if stage.commit is not None:
                    self.post("flow_commit", job.id, stage.commit)
            self.post("job_done", job.id, True, "")
        except Exception as ex:
            where = " [%s]" % stage.label if stage is not None else ""
            self.post("job_done", job.id, False, "%s: %s%s" % (type(ex).__name__, ex, where))

    def _on_flow_commit(self, job_id, commit):
        try:
            if commit["op"] == "place_box":
                f = self.fixtures[commit["fixture"]]
                waited = self.clock() - f.idle_since if f.idle_since else 0.0
                self._log("debug", "box %d chờ %.1fs trước khi nhận sản phẩm" % (f.number, waited))
            text = self.flow.commit(commit, self.fixtures, self.clock())
        except Exception as ex:
            log.exception("flow commit %r failed", commit)
            self._fail_flow("sổ sách luồng tray sai lệch (%s: %s): hãy kiểm tra tay hút và box, rồi 'Xóa trạng thái luồng'"
                            % (type(ex).__name__, ex), None)
            return
        self._log("debug" if commit["op"] == "sn" else "info", text)
        if commit["op"] == "take_tray" and "input" in self.trays:
            self.trays["input"].advance()
        elif commit["op"] == "put_ng" and "ng" in self.trays:
            self.trays["ng"].advance()
        elif commit["op"] == "put_out" and ("output%d" % (commit["tray"] + 1)) in self.trays:
            self.trays["output%d" % (commit["tray"] + 1)].advance()

    def _normalise_fixture_states(self):
        for f in self.fixtures.values():
            if f.state in (LOADING, UNLOADING):
                f.state = (TESTING if not f.finished else RESULT) if f.dut is not None else IDLE

    def _on_flow_job_done(self, job, ok, error):
        self._normalise_fixture_states()
        if ok:
            return
        f = self.fixtures.get(job.fixture)
        if f is not None:
            f.state, f.message = FAULT, error
        self._fail_flow(error, job)

    def _fail_flow(self, error, job):
        what = "%s " % job.task.kind if job is not None else ""
        self.fault_text = "luồng tray %s: %s" % (what, error)
        kind = error.split(":", 1)[0]
        code = {"ScanError": "9202", "HeadError": "9203", "LaserError": "9204", "DropError": "9208"}.get(kind, "9201")
        self.errors.raise_error(code, self.fault_text, key="robot")
        self._log("error", "việc robot thất bại - dừng chạy: %s. Kiểm tra hàng trên tay hút rồi xác nhận lỗi" % self.fault_text)
        if kind == "DropError" and self.flow_settings.stop_robot_on_drop and self.on_drop is not None:
            self._log("error", "RƠI HÀNG: dừng chương trình robot")
            try:
                self.on_drop(self.fault_text)
            except Exception:
                log.exception("on_drop failed")
        self.run_state = RUN_FAULT                          # last: whoever sees the fault also sees its alarm and the stop request

    # ---- periodic ------------------------------------------------------- #
    def _watch_program(self, now):
        """The robot program (UO[3] PROGRUN) stopped during a run (E-stop, cycle stop, fault...): pause with an alarm.
        It must stay off for a second, so that a single bad reading does not stop the cell."""
        state = getattr(self.robot, "program_state", None)
        if state is not False:
            self._program_off_since = None
            if state is True:
                self.errors.clear_error("robot_program")
            return
        if self._program_off_since is None:
            self._program_off_since = now
        if self.run_state == RUNNING and now - self._program_off_since >= 1.0:
            self.errors.raise_error("9100", "chương trình robot đã dừng (UO[3] PROGRUN = 0)", key="robot_program")
            self._cmd_pause()
            self._log("warn", "chương trình robot đã dừng: tạm dừng chạy. Bấm 'Chạy chương trình' rồi 'Bắt đầu'")

    def _watch_trays(self):
        """Tray flow: tell the operator when a tray must be changed."""
        book = self.flow.book
        if book.ng_capacity and book.ng_free == 0:
            if self.errors.raise_error("9207", "tray NG đã đầy: hãy thay / dọn tray NG rồi bấm 'Đã dọn'", key="tray_ng"):
                self._log("warn", "tray NG đã đầy: hãy thay / dọn tray NG rồi bấm 'Đã dọn'")
        if book.has_outputs and book.out_free == 0:
            msg = "mọi tray output đã đầy: hãy thay / dọn tray output rồi bấm 'Đã dọn'"
            if self.errors.raise_error("9209", msg, key="tray_output"):
                self._log("warn", msg)
        if self.run_state == RUNNING and self._current is None and book.finished():
            if self.errors.raise_error("9206", "tray Input hết hàng, đã xử lý xong: hãy thay tray Input rồi bấm 'Nạp lại'", key="tray_input"):
                self._log("warn", "tray Input hết hàng và mọi sản phẩm đã được cất: hãy thay tray Input rồi bấm 'Nạp lại'")

    def _tick(self, now):
        self._watch_program(now)
        if self.flow is not None:
            self._watch_trays()
        for f in self.fixtures.values():
            if f.state == TESTING and f.test_started and now - f.test_started > self.test_timeout_s:
                self.errors.raise_error("9010", "Fixture %d: không có kết quả sau %.0fs" % (f.number, now - f.test_started),
                                        key="test_timeout_%d" % f.number)
        if self.run_state == RUNNING and self._current is None and now - self._armed_at > 2.0:
            status = getattr(self.robot, "last_status", None) or {}
            if status.get("armed") is False:
                self.errors.raise_error("9100", "bridge robot chưa arm (watchdog/lỗi)", key="robot_link")
                self.run_state = PAUSED
                self._log("warn", "bridge bị disarm: tạm dừng chạy")
        for f in self.fixtures.values():
            self._maybe_queue_load(f)
