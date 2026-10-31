"""Engine lập lịch.

Một thread engine giữ toàn bộ trạng thái và xử lý từng sự kiện một (tin nhắn ATS, lệnh của người vận hành,
job xong, tick), nên không có tranh chấp cờ dùng chung. Việc của robot là blocking, nên chạy trong một
thread job riêng (mỗi lúc một job: chỉ có một robot) và báo lại bằng một sự kiện.

Robot phục vụ tối đa 8 tay hút và nhiều box (rcs2/core/flow.py): planner quyết định, robot chạy các STAGE
(lấy / đổi / cất), và commit của mỗi stage cập nhật sổ sách của từng sản phẩm đúng lúc robot thực sự làm xong;
lệnh dừng có hiệu lực giữa hai stage.

Mã alarm (giữ theo RCS cũ khi đã có)
  9026 RCS dừng/tạm dừng  9011 NG liên tiếp          9012 ATS chưa kết nối     9013 lỗi fixture
  9010 test quá thời gian 9201 lỗi robot/sequence                              9100 mất liên kết robot / bị disarm
  9202 không đọc được mã vạch (bước quét thất bại sau mọi lần thử lại; chưa hút gì)
  9203 lỗi tay hút của End Effector (tay không hút / nhả được, xy lanh không tới vị trí, lỗi I/O)
  9204 kiểm tra laser (IL-1000) của End Effector không đạt
  9205 chưa dạy đủ các điểm luồng tray cần (Bắt đầu bị từ chối)
  9206 luồng tray: hết hàng chưa test và mọi sản phẩm đã được cất -> đặt tray Input mới, rồi bấm "Nạp lại"
  9207 luồng tray: tray NG đã đầy -> dọn / thay tray, rồi bấm "Đã dọn"
  9209 luồng tray: mọi tray output (hàng đạt) đã đầy -> dọn / thay chúng, rồi bấm "Đã dọn" của tray đó
  9208 luồng tray: một tay đánh rơi sản phẩm (carry check) -> dừng chạy và dừng chương trình robot
"""
import logging
import queue
import threading
import time
from dataclasses import dataclass, field

from ..ats import protocol as AP
from ..devices.heads import HeadError
from .flow import FlowController, FlowError, FlowSettings
from .geometry import GeometryError
from .sequence import SequenceRunner, validate
from .tasks import DropError
from .states import (FAULT, IDLE, LOADING, NO_USED, OFFLINE, PAUSED, RESULT, RUN_FAULT, RUNNING, STOPPED, TESTING,
                     UNLOADING)
from .tray import build_trays

log = logging.getLogger("rcs2.engine")

RESULT_LABEL = {AP.PASS: "PASS", AP.NG: "NG", AP.RETEST: "RETEST", AP.RETEST1: "RETEST",
                AP.FQC: "FQC", AP.WARNING: "WARNING", AP.OFFSET_PASS: "PASS", AP.OFFSET_NG: "NG"}
COUNTS_AS_FAIL = ("NG", "RETEST", "WARNING")


@dataclass
class Fixture:
    number: int
    station: str
    robot_station: int
    ats_host: str = ""
    enabled: bool = False
    connected: bool = False
    ats_ready: bool = False        # ATS đã báo "đang chờ DUT"
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
    dut: object = None             # sản phẩm đang ở bên trong (dut.Dut)
    finished: bool = False         # đã có kết quả của `dut` và nó đang chờ được lấy ra
    idle_since: float = 0.0        # box chờ robot từ lúc nào

    @property
    def yield_pct(self):
        return (100.0 * self.passed / self.total) if self.total else None


@dataclass
class Job:
    id: int
    kind: str                     # "flow"
    fixture: int
    sequence: str = ""            # loại việc của planner (hiện trong log)
    task: object = None           # việc của planner mà job này thực hiện
    stages: list = field(default_factory=list)     # các stage (tasks.Stage) của việc
    created: float = field(default_factory=time.time)


class Engine:
    def __init__(self, settings, robot, ats, sink, errors, points, clock=time.monotonic, ee=None, trays=None):
        self.cfg = settings
        self.robot = robot
        self.ats = ats                      # {số fixture: đối tượng giống AtsClient}
        self.sink = sink
        self.errors = errors
        self.points = points
        self.clock = clock
        self.on_log = None                  # callable(level, text) cho log trên UI
        self.block_reason = ""              # khác rỗng: Bắt đầu bị từ chối (ví dụ điểm mẫu trên robot thật)

        self.ee = ee                        # End Effector (tay hút / đầu đọc mã / laser) hoặc None
        validate({}, points)                # điểm dạy viết sai được báo ngay lúc khởi động
        self.trays = build_trays(trays)     # {"input": Tray, "ng": Tray, ...}
        heads = getattr(getattr(ee, "heads", None), "count", 0)         # số tay hút (End Effector thay thế dùng trong test có thể không có)
        self.flow_settings = FlowSettings.from_config(settings, heads)

        e = settings["engine"]
        self.test_timeout_s = e["test_timeout_s"]
        self.ng_limit = settings["consecutive_ng"]["limit"]
        self.ng_stop = settings["consecutive_ng"]["stop_fixture"]

        self.fixtures = {}
        for key, f in settings["ats"]["fixtures"].items():
            n = int(key)
            self.fixtures[n] = Fixture(n, f.get("station", "Station1"), int(f.get("robot_station", n)),
                                       ats_host=f.get("host", ""))
        self.on_drop = None                 # callable(text): một tay đánh rơi sản phẩm (runtime dừng chương trình robot)
        laser = getattr(ee, "laser", None)
        if self.flow_settings.laser and (laser is None or not getattr(laser, "enabled", True)):
            raise FlowError("flow.laser_check is on but the End Effector has no enabled laser (end_effector.laser.enabled)")
        self.flow = FlowController(self.flow_settings, trays, self.fixtures.keys(), heads,
                                   getattr(ee, "scanner", None) is not None, settings["bridge"].get("default_override"), e)
        self.run_state = STOPPED
        self.fault_text = ""
        self._armed_at = 0.0
        self._disarm_after_job = False
        self._job_seq = 0
        self._current = None
        self._events = queue.Queue()
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._cancel = threading.Event()
        self._thread = None
        self._program_off_since = None      # UO[3] PROGRUN tắt từ lúc nào (None = bật / chưa biết)
        self._runner = SequenceRunner(robot, ats, points, settings["bridge"].get("default_override"),
                                      log=lambda m: self._log("debug", m), ee=ee)

    # ------------------------------------------------------------------ #
    # vòng đời
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
        if self.on_log and level != "debug":          # chi tiết từng bước chỉ ghi vào file log
            try:
                self.on_log(level, text)
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    # lệnh công khai (thread safe: chúng chỉ post sự kiện)
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
        """Chặn tới khi mọi lệnh post trước lần gọi này đã được thread engine xử lý (False nếu
        engine không chạy hoặc không trả lời kịp). Giúp bên gọi chắc chắn rằng, ví dụ, lệnh disarm sau
        stop_run() đã xảy ra, thay vì rơi vào giữa lần arm kế tiếp của chính nó."""
        thread = self._thread
        if thread is None or not thread.is_alive():
            return False
        done = threading.Event()
        self.post("cmd", "sync", done)
        return done.wait(timeout)

    def set_enabled(self, number, enabled):
        self.post("cmd", "enable", number, bool(enabled))

    def reset_tray(self, kind):
        """Người vận hành đã nạp lại tray Input / dọn trống tray NG."""
        self.post("cmd", "reset_tray", kind)

    def reset_flow(self):
        """Người vận hành đã dọn mọi tay hút và box bằng tay: quên vị trí của mọi sản phẩm và bắt đầu lại."""
        self.post("cmd", "reset_flow")

    def on_ats_event(self, number, event):
        self.post("ats", number, event)

    def on_ats_connection(self, number, connected):
        self.post("ats_conn", number, connected)

    # ------------------------------------------------------------------ #
    # snapshot cho UI
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
                "current_job": (self._current.kind, self._current.fixture) if self._current else None,
                "robot": dict(getattr(self.robot, "last_status", {}) or {}),
                "robot_link": bool(getattr(self.robot, "connected", False)),
                "program_running": getattr(self.robot, "program_state", None),    # UO[3] PROGRUN: True / False / None
                "alarms": self.errors.active() if hasattr(self.errors, "active") else [],
                "sink": self.sink.stats() if self.sink else {},
                "totals": {"total": total, "passed": passed, "yield_pct": (100.0 * passed / total) if total else None},
                "trays": {kind: t.snapshot() for kind, t in self.trays.items()},
                "flow": self.flow.snapshot(),
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
    # thread engine
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

    # ---- lệnh ----------------------------------------------------------- #
    def _cmd_start(self):
        if self.block_reason:
            self._log("error", "không thể bắt đầu: %s" % self.block_reason)
            return
        if self.run_state == RUN_FAULT:
            self._log("warn", "không thể bắt đầu: hãy xác nhận lỗi trước (%s)" % self.fault_text)
            return
        if not self._prepare_flow():
            return
        if not getattr(self.robot, "connected", False):
            self._log("error", "không thể bắt đầu: chưa kết nối bridge robot")
            self.errors.raise_error("9100", "chưa kết nối bridge robot", key="robot_link")
            return
        refresh = getattr(self.robot, "refresh_program_state", None)     # đối tượng thay thế không đọc được UO[3]: không kiểm tra
        if refresh is not None:
            state = refresh()                                              # đọc mới UO[3] PROGRUN
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
                f.idle_since = self._armed_at            # mọi box trống bắt đầu chờ từ lúc này

    def _cmd_sync(self, done):
        done.set()

    def _cmd_pause(self):
        if self.run_state == RUNNING:
            self.run_state = PAUSED
            self.errors.raise_error("9026", "RCS dừng", key="run_stop")
            self._log("info", "đã tạm dừng (việc robot đang làm sẽ chạy xong trước)")

    def _cmd_stop(self):
        self.run_state = STOPPED if self.run_state != RUN_FAULT else RUN_FAULT
        self.errors.raise_error("9026", "RCS dừng", key="run_stop")
        if self._current is None:
            self._disarm_robot()
        else:
            self._disarm_after_job = True      # không bao giờ disarm giữa chừng một sequence
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
        self._log("info", "đã xác nhận lỗi; hãy kiểm tra tay hút và box (nếu cần thì 'Xóa trạng thái luồng') rồi bấm Bắt đầu")

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
        self._log("info", "fixture %d %s" % (number, "đã bật" if enabled else "đã tắt"))

    def _cmd_reset_flow(self):
        if self._current is not None:
            self._log("warn", "robot đang làm việc: hãy dừng chạy rồi đợi xong trước khi xóa trạng thái luồng")
            return
        self.flow.reset("all")
        for key in ("tray_input", "tray_ng"):
            self.errors.clear_error(key)
        for f in self.fixtures.values():
            f.dut, f.finished, f.dut_inside, f.sn, f.message = None, False, False, "", ""
            f.idle_since = self.clock()
            if f.state in (TESTING, RESULT, LOADING, UNLOADING, FAULT):
                f.state = IDLE
        for tray in self.trays.values():
            tray.reset()
        self.errors.clear_error("robot")
        self._log("info", "đã xóa trạng thái luồng: mọi tay hút và box được coi là trống, tray input đầy, tray NG trống")

    def _cmd_reset_tray(self, kind):
        tray = self.trays.get(kind)
        if tray is None:
            return
        if kind == "input" and self.flow.in_flight():
            self._log("warn", "còn %d sản phẩm trên tay hút / trong box: không thể đặt lại tray input "
                              "(nếu đã dọn tay hết, dùng 'Xóa trạng thái luồng')" % len(self.flow.in_flight()))
            return
        self.flow.reset(kind)
        self.errors.clear_error({"input": "tray_input", "ng": "tray_ng"}.get(kind, "tray_output"))
        tray.reset()
        self._log("info", "tray %s đã đặt lại (%s)" % (kind, "đã nạp lại" if kind == "input" else "đã dọn trống"))

    # ---- sự kiện ATS ---------------------------------------------------- #
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
                f.enabled = False       # không nạp DUT mới; DUT đã test vẫn được lấy ra (RCS cũ để nó lại bên trong)
        self._log("info", self.flow.result(f, label, elapsed, self.fixtures, self.clock())[1])
        # planner lấy sản phẩm ra khi robot rảnh

    # ---- việc robot (việc của planner) ---------------------------------- #
    def _prepare_flow(self):
        """Bắt đầu một lượt chạy: phải có đủ mọi điểm dạy. False (alarm 9205) khi thiếu điểm."""
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

    def _dispatch(self):
        if self._current is not None or self.run_state != RUNNING or self.flow.layout is None:
            return
        if getattr(self.robot, "program_state", None) is False or not getattr(self.robot, "connected", False):
            return                                                       # không được ghi lệnh nào khi chương trình robot đang tắt
        task = self.flow.plan(self.flow.world(self.clock(), self.fixtures))
        if task is None:
            return
        try:
            stages = self.flow.build(task)
        except Exception as ex:                                          # hình học sai: không bao giờ gửi một pose chưa chắc chắn
            self._fail_flow("%s: %s" % (type(ex).__name__, ex), None)
            return
        self._job_seq += 1
        job = Job(self._job_seq, "flow", getattr(task, "fixture", 0) or 0, task=task, stages=stages, sequence=task.kind)
        self._current = job
        f = self.fixtures.get(job.fixture)
        if f is not None and f.state in (IDLE, RESULT, TESTING):
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
                    self.post("job_done", job.id, True, "")               # dừng giữa hai stage: sổ sách vẫn chính xác
                    return
                try:
                    self._runner.run(stage.label, stage.steps, {}, cancel=self._cancel, on_scan=scanned)
                except HeadError as ex:
                    if stage.kind == "carry":                              # tay đang mang sản phẩm mà không còn giữ được nó
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

    def _on_job_done(self, job_id, ok, error):
        job, self._current = self._current, None
        if job is None or job.id != job_id:
            return
        if self._disarm_after_job and self.run_state != RUNNING:
            self._disarm_robot()
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
        self.run_state = RUN_FAULT                          # đặt sau cùng: ai thấy lỗi thì cũng thấy alarm và yêu cầu dừng của nó

    # ---- định kỳ -------------------------------------------------------- #
    def _watch_program(self, now):
        """Chương trình robot (UO[3] PROGRUN) dừng giữa lúc đang chạy (E-stop, cycle stop, lỗi...): tạm dừng kèm alarm.
        Nó phải tắt liên tục một giây, để một lần đọc sai không làm dừng cả cell."""
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
        """Báo cho người vận hành khi cần thay tray."""
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
