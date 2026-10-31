"""Runtime: builds and wires every component from the settings (no Qt in here).

The class is assembled from five mixins that keep the methods of one concern together:
  SessionMixin        login / logout / automatic logout                  (session.py)
  BridgeLinkMixin     link to the bridge + robot, UO[3] PROGRUN monitor   (bridge_link.py)
  RobotOpsMixin       start / stop the robot program, manual motion, teach (robot_ops.py)
  EndEffectorOpsMixin heads / scanner / laser actions of the Manual window (end_effector_ops.py)
FlowOpsMixin        tray flow: calibration of the heads, trays and boxes (flow_ops.py)
"""
import logging
import os
import threading
import time

from ..ats.client import AtsClient
from ..config import env_secret, resolve_local_ip
from ..core.engine import Engine
from ..core.sequence import load_sequences
from ..core.tray import build_trays
from ..devices.end_effector import build_end_effector
from ..robot.client import BridgeClient
from ..robot.uop import normalize as normalize_robot_start
from ..reporting.data_sink import DataSink, ErrorTracker
from ..employee import EmployeeService
from ..reporting.mysql_writer import MySqlWriter
from ..reporting.outbox import Outbox
from ..reporting.sql_targets import SqlTargets
from .bridge_link import BridgeLinkMixin
from .end_effector_ops import EndEffectorOpsMixin
from .flow_ops import FlowOpsMixin
from .robot_ops import RobotOpsMixin
from .session import SessionMixin

log = logging.getLogger("rcs2.runtime")


class Runtime(SessionMixin, BridgeLinkMixin, RobotOpsMixin, EndEffectorOpsMixin, FlowOpsMixin):
    def __init__(self, settings, base_dir, sequences_data=None):
        build_trays(settings.get("trays"))          # fail early (before anything is opened) on a bad tray size
        normalize_robot_start(settings.get("robot_start"))      # ... or a bad robot_start entry
        self.cfg = settings
        self.base_dir = base_dir
        self._uop_abort = threading.Event()         # set by robot_stop_program: a start in progress gives up
        self._seq_data = sequences_data
        self._stop = threading.Event()
        self.ats = {}
        self.employee = EmployeeService.from_settings(settings, base_dir=base_dir)
        self.operator = None                       # LoginResult of the logged-in user
        self.on_log = None                         # callable(level, text)
        self.clock = time.monotonic
        emp = settings["employee"]
        self.auto_logout_s = float(emp.get("auto_logout_s", 0) or 0)       # 0 = never
        self.auto_logout_idle = bool(emp.get("auto_logout_idle", False))
        self._login_at = self._last_activity = 0.0

        ident = settings["identity"]
        self.local_ip = resolve_local_ip(settings)
        self.targets = SqlTargets(ident["model"], ident["stations"], self.local_ip)

        self.outbox = Outbox(self._path(settings["outbox_path"]))
        self.sink = DataSink(self.outbox, self._make_writer(), enabled=self._db_enabled,
                             flush_interval_s=settings["mysql"]["flush_interval_s"])
        self.errors = ErrorTracker(self.sink, self.targets.station_label)

        self._seq_path = None                      # file the points are saved to (None in demo mode)
        self._manual_lock = threading.Lock()
        if self._seq_data is None:
            self._seq_path = self._path(settings["engine"]["sequences_path"])
            self._seq_data = load_sequences(self._seq_path)
        self.bridge = BridgeClient(settings["bridge"]["host"], settings["bridge"]["port"],
                                   token=env_secret(settings["bridge"].get("token_env", "")),
                                   on_event=self._on_bridge_event)
        # the ONE End Effector of the robot: suction heads (robot I/O), barcode scanner, IL-1000 laser
        self.ee = build_end_effector(settings, self.bridge)
        self.engine = Engine(settings, self.bridge, self.ats, self.sink, self.errors,
                             self._seq_data["sequences"], self._seq_data["points"], ee=self.ee,
                             trays=settings.get("trays"))   # sizes come only from settings.json
        self.engine.on_log = self._emit_log
        self.engine.on_drop = self._on_drop                 # tray flow: a head dropped its product -> stop the robot program

        for key, f in settings["ats"]["fixtures"].items():
            n = int(key)
            self.ats[n] = AtsClient(
                str(n), f["host"], int(f["port"]),
                heartbeat_s=settings["ats"]["heartbeat_s"],
                connect_timeout_s=settings["ats"]["connect_timeout_s"], retry_s=settings["ats"]["retry_s"],
                on_event=lambda ev, n=n: self.engine.on_ats_event(n, ev),
                on_connection=lambda ok, n=n: self.engine.on_ats_connection(n, ok))

    # ------------------------------------------------------------------ #
    def _path(self, p):
        return p if os.path.isabs(p) else os.path.join(self.base_dir, p)

    @property
    def _db_enabled(self):
        m = self.cfg["mysql"]
        return bool(m["enabled"] and env_secret(m["password_env"]))

    def _make_writer(self):
        m = self.cfg["mysql"]
        if not m["enabled"]:
            return None
        password = env_secret(m["password_env"])
        if not password:
            log.warning("mysql.enabled but environment variable %s is empty: data stays in the local outbox",
                        m["password_env"])
            return None
        return MySqlWriter(self.targets, m["host"], m["port"], m["user"], password, m["database"],
                           m["connect_timeout_s"])

    def _emit_log(self, level, text):
        if self.on_log:
            self.on_log(level, text)

    def _on_bridge_event(self, name, data):
        pass        # the engine and UI read bridge.last_status

    # ------------------------------------------------------------------ #
    def start(self):
        closed = self.errors.recover()
        if closed:
            self._emit_log("warn", "%d lỗi còn mở từ lần chạy trước đã được đóng" % closed)
        self.engine.start()
        self.sink.start()
        for c in self.ats.values():
            c.start()
        threading.Thread(target=self._bridge_supervisor, name="bridge-supervisor", daemon=True).start()
        threading.Thread(target=self._alive_loop, name="alive", daemon=True).start()
        threading.Thread(target=self._program_monitor, name="program-monitor", daemon=True).start()

    @property
    def stopped(self):
        return self._stop.is_set()

    def stop(self):
        if self._stop.is_set():
            return                                  # already stopped (idempotent)
        self._stop.set()
        try:
            self.engine.stop_run()
            time.sleep(0.2)
        except Exception:
            pass
        self.engine.shutdown()
        for c in self.ats.values():
            c.stop()
        try:
            self.bridge.close()
        except Exception:
            pass
        self.ee.close()
        for alarm in self.errors.active():        # clean exit: every open error ends now (not "left open")
            self.errors.clear_error(alarm["key"])
        self.sink.stop(flush=True)
        self.outbox.close()

    def _alive_loop(self):
        while not self._stop.wait(60):
            self.errors.heartbeat()

    # ---- trays (sizes are set in settings.json only) ------------------------------- #
    def _on_drop(self, text):
        """A head dropped its product (called from the engine thread): stop the robot program like the 'Dừng robot' button does."""
        def work():
            try:
                self.robot_stop_program()
            except Exception as ex:
                self._emit_log("error", "không dừng được chương trình robot sau khi rơi hàng (%s): dùng E-stop!" % ex)
        threading.Thread(target=work, name="drop-stop", daemon=True).start()

    def reset_tray(self, kind):
        self.engine.reset_tray(kind)
