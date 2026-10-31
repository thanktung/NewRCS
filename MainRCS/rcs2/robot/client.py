"""Client của bridge robot (API blocking, thread đọc chạy nền, không phụ thuộc Qt).

    client = BridgeClient("127.0.0.1", 5600)       # bridge chạy trên cùng PC
    client.connect()
    client.arm()
    client.move([300, 0, 200, 180, 0, 0], override=10)      # chờ tới khi robot làm xong
    client.put(station=1)
    client.disarm()

Mọi lỗi được ném ra dạng RobotError(code, message) (code lấy từ protocol.E_*) hoặc
ConnectionError khi đường TCP bị mất.
"""
import logging
import socket
import threading
import time

from . import protocol as P
from .uop import UO_PROGRUN

log = logging.getLogger("rcs2.robot")


class RobotError(Exception):
    def __init__(self, code, message):
        super().__init__("%s: %s" % (code, message))
        self.code = code
        self.message = message


class BridgeClient:
    def __init__(self, host, port=P.DEFAULT_PORT, token="", connect_timeout=5.0,
                 ping_interval=1.0, on_event=None, on_disconnect=None):
        self.host, self.port, self.token = host, port, token
        self.connect_timeout = connect_timeout
        self.ping_interval = ping_interval      # 0 = tắt keep-alive (chỉ dùng trong test)
        self.on_event = on_event                # callable(name, data)
        self.on_disconnect = on_disconnect      # callable()
        self.hello = None                       # dữ liệu của phản hồi hello
        self.last_status = {}
        self.program_state = None               # UO[3] PROGRUN theo lần đọc gần nhất: True / False, None = chưa biết (xem refresh_program_state)
        self._sock = None
        self._send_lock = threading.Lock()
        self._pending = {}
        self._pending_lock = threading.Lock()
        self._next_id = 1
        self._reader = None
        self._pinger = None
        self._closing = threading.Event()

    # ------------------------------------------------------------------ #
    # kết nối
    # ------------------------------------------------------------------ #
    @property
    def connected(self):
        return self._sock is not None

    def connect(self):
        if self._sock is not None:
            return self.hello
        self._closing.clear()
        sock = socket.create_connection((self.host, self.port), timeout=self.connect_timeout)
        sock.settimeout(None)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self._sock = sock
        self._reader = threading.Thread(target=self._read_loop, args=(sock,), name="bridge-reader", daemon=True)
        self._reader.start()
        try:
            self.hello = self.call("hello", {"token": self.token}, timeout=self.connect_timeout)
        except Exception:
            self.close()
            raise
        if self.hello.get("protocol") != P.PROTOCOL_VERSION:
            self.close()
            raise RobotError(P.E_BAD_REQUEST, "bridge protocol %s, client expects %s"
                             % (self.hello.get("protocol"), P.PROTOCOL_VERSION))
        self.last_status = self.hello.get("state", {})
        if self.ping_interval > 0:
            self._pinger = threading.Thread(target=self._ping_loop, name="bridge-ping", daemon=True)
            self._pinger.start()
        log.info("connected to bridge %s:%s (%s, v%s)", self.host, self.port,
                 self.hello.get("mode"), self.hello.get("version"))
        return self.hello

    def close(self):
        self._closing.set()
        self._drop(notify=False)

    def _drop(self, notify=True):
        self.program_state = None
        sock, self._sock = self._sock, None
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass
        with self._pending_lock:
            pending, self._pending = self._pending, {}
        for done, box in pending.values():
            box["error"] = ConnectionError("bridge connection closed")
            done.set()
        if sock is not None and notify and self.on_disconnect:
            try:
                self.on_disconnect()
            except Exception:
                log.exception("on_disconnect failed")

    # ------------------------------------------------------------------ #
    # các thread
    # ------------------------------------------------------------------ #
    def _read_loop(self, sock):
        try:
            rfile = sock.makefile("rb")
            while True:
                line = rfile.readline(P.MAX_LINE_BYTES + 1)
                if not line:
                    break
                try:
                    msg = P.decode(line)
                except ValueError:
                    log.warning("undecodable line from bridge ignored")
                    continue
                if "event" in msg:
                    if msg["event"] == "status":
                        self.last_status = msg.get("data", {})
                    if self.on_event:
                        try:
                            self.on_event(msg["event"], msg.get("data"))
                        except Exception:
                            log.exception("on_event failed")
                    continue
                with self._pending_lock:
                    entry = self._pending.pop(msg.get("id"), None)
                if entry is not None:
                    entry[1]["response"] = msg
                    entry[0].set()
        except (OSError, ValueError):
            pass
        finally:
            if self._sock is sock:
                self._drop(notify=not self._closing.is_set())

    def _ping_loop(self):
        while not self._closing.wait(self.ping_interval):
            if self._sock is None:
                return
            try:
                self.call("ping", timeout=max(2.0, self.ping_interval * 3))
            except (ConnectionError, RobotError, OSError):
                log.warning("bridge keep-alive failed; closing the link")
                self._drop()
                return

    # ------------------------------------------------------------------ #
    # yêu cầu / phản hồi
    # ------------------------------------------------------------------ #
    def call(self, cmd, args=None, timeout=10.0):
        sock = self._sock
        if sock is None:
            raise ConnectionError("not connected to the bridge")
        done, box = threading.Event(), {}
        with self._pending_lock:
            rid = self._next_id
            self._next_id += 1
            self._pending[rid] = (done, box)
        try:
            with self._send_lock:
                sock.sendall(P.encode({"id": rid, "cmd": cmd, "args": args or {}}))
        except OSError as ex:
            with self._pending_lock:
                self._pending.pop(rid, None)
            self._drop()
            raise ConnectionError("send failed: %s" % ex)
        if not done.wait(timeout):
            with self._pending_lock:
                self._pending.pop(rid, None)
            raise RobotError(P.E_TIMEOUT, "no answer to '%s' within %.1fs" % (cmd, timeout))
        if "error" in box:
            raise box["error"]
        resp = box["response"]
        if resp.get("ok"):
            return resp.get("data")
        err = resp.get("error") or {}
        raise RobotError(err.get("code", P.E_INTERNAL), err.get("message", ""))

    # ------------------------------------------------------------------ #
    # API tiện dụng
    # ------------------------------------------------------------------ #
    def status(self):
        return self.call("status")

    def robot_connect(self, host=None):
        return self.call("robot.connect", {"host": host} if host else {}, timeout=40.0)

    def robot_disconnect(self):
        return self.call("robot.disconnect")

    def arm(self):
        data = self.call("arm")
        self.last_status = dict(self.last_status, armed=True)     # không chờ sự kiện status kế tiếp
        return data

    def disarm(self):
        data = self.call("disarm")
        self.last_status = dict(self.last_status, armed=False)
        return data

    def fault_clear(self, force=False):
        return self.call("fault.clear", {"force": True} if force else {})

    def alarm_clear(self):
        return self.call("alarm.clear")

    def pos_read(self):
        """Vị trí hiện tại, đọc mới: {'xyzwpr': [6], 'config': [7], 'uf': n, 'ut': n}."""
        return self.call("pos.read")

    def r_read(self, index):
        return self.call("r.read", {"index": index})["value"]

    def r_write(self, index, value):
        return self.call("r.write", {"index": index, "value": value})["value"]

    def pr_read(self, group, index):
        return self.call("pr.read", {"group": group, "index": index})["pos"]

    def pr_write(self, group, index, xyzwpr, config=None, uf=None, ut=None):
        args = {"group": group, "index": index, "xyzwpr": list(xyzwpr)}
        if config is not None:
            args["config"] = list(config)
        if uf is not None:
            args["uf"] = uf
        if ut is not None:
            args["ut"] = ut
        return self.call("pr.write", args)["pos"]

    def io_read(self, kind, index, count=1):
        return self.call("io.read", {"kind": kind, "index": index, "count": count})["values"]

    def io_write(self, kind, index, values):
        return self.call("io.write", {"kind": kind, "index": index, "values": list(values)})["values"]

    # --- chương trình robot có đang chạy không? (UO[3] PROGRUN; đọc không cần arm) ---
    def program_running(self):
        """True / False từ một lần đọc mới UO[3]. Ném RobotError / ConnectionError khi không đọc được."""
        return bool(self.io_read("UO", UO_PROGRUN, 1)[0])

    def refresh_program_state(self):
        """Đọc mới UO[3], lưu vào `program_state` và trả về: True / False, hoặc None khi không đọc được."""
        try:
            self.program_state = self.program_running()
        except (RobotError, ConnectionError, OSError):
            self.program_state = None
        return self.program_state

    # --- chuyển động (blocking tới khi robot báo xong) ---
    def _motion(self, op, args, timeout_s):
        if timeout_s is not None:
            args["timeout_s"] = timeout_s
        wait = (timeout_s if timeout_s is not None else 60.0) + 20.0
        return self.call("motion." + op, args, timeout=wait)

    @staticmethod
    def _target(xyzwpr, config, uf, ut):
        t = {"xyzwpr": list(xyzwpr)}
        if config is not None:
            t["config"] = list(config)
        if uf is not None:
            t["uf"] = uf
        if ut is not None:
            t["ut"] = ut
        return t

    def move(self, xyzwpr, override=None, config=None, uf=None, ut=None, timeout_s=None):
        args = {"target": self._target(xyzwpr, config, uf, ut)}
        if override is not None:
            args["override"] = override
        return self._motion("move", args, timeout_s)

    def rmove(self, offset_xyzwpr, override=None, timeout_s=None):
        args = {"target": self._target(offset_xyzwpr, None, None, None)}
        if override is not None:
            args["override"] = override
        return self._motion("rmove", args, timeout_s)

    def gosafetarge(self, xyzwpr, override=None, config=None, uf=None, ut=None, timeout_s=None):
        args = {"target": self._target(xyzwpr, config, uf, ut)}
        if override is not None:
            args["override"] = override
        return self._motion("gosafetarge", args, timeout_s)

    def gosafehere(self, override=None, timeout_s=None):
        args = {} if override is None else {"override": override}
        return self._motion("gosafehere", args, timeout_s)

    def _station_op(self, op, station, override, timeout_s):
        args = {"station": station}
        if override is not None:
            args["override"] = override
        return self._motion(op, args, timeout_s)

    def put(self, station, override=None, timeout_s=None):
        return self._station_op("put", station, override, timeout_s)

    def get(self, station, override=None, timeout_s=None):
        return self._station_op("get", station, override, timeout_s)

    def down(self, station, override=None, timeout_s=None):
        return self._station_op("down", station, override, timeout_s)

    def up(self, station, override=None, timeout_s=None):
        return self._station_op("up", station, override, timeout_s)
