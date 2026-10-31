"""Keyence barcode readers (SR-710, SR-X100 ...): read a code on command.

Protocol (Keyence SR series, same as the old C# program):
    NewRCS -> reader   "LON" + terminator     start reading
    reader -> NewRCS   "<decoded data>" CR    the code (reading stops by itself after a good read)
                     "ERROR"                 no-read string (default of the reader, configurable)
                     "ER,LON,xx"             the reader refused the command
    NewRCS -> reader   "LOFF" + terminator    stop reading (sent after a time-out or by the operator)

The reader is the scanner tool of the robot's End Effector (rcs2/devices/end_effector.py).
Connection: TCP/IP (Ethernet) or a COM port (RS-232, needs the `pyserial` package), chosen in
settings.json -> "end_effector" -> "scanner". A serial "port" may also be a pyserial URL (socket://host:port, rfc2217://...) for
RS-232 readers behind a serial-to-Ethernet adapter. Everything blocks, so call it from a worker thread (the robot job thread does).

    "scanner": {"type": "tcp", "host": "192.168.1.50", "port": 9004,
                "length": 14, "pattern": "[A-Z0-9]+", "retry": 2, "timeout_s": 3.0}
    or        {"type": "serial", "port": "COM3", "baud": 9600}
Optional keys: model (text), terminator (what is appended to LON/LOFF, default "\\r\\n" like the old program),
no_read (default "ERROR"), connect_timeout_s.
`length` 0 / `pattern` "" = no check. `retry` = EXTRA attempts after the first one.
"""
import logging
import re
import socket
import threading
import time

log = logging.getLogger("rcs2.scanner")

LON = "LON"
LOFF = "LOFF"


class ScanError(Exception):
    """A scan failed for good (after all retries)."""


class ScanCancelled(ScanError):
    """The caller asked to stop (run stopped) while the reader was working."""


class _NoRead(Exception):
    """One attempt gave no usable code (internal; counted as a failed attempt)."""


# --------------------------------------------------------------------------- #
# transports: open / close / write / read whatever arrives within a time / drop pending input
# --------------------------------------------------------------------------- #
class TcpTransport:
    def __init__(self, host, port, connect_timeout_s=3.0):
        self.host, self.port, self.connect_timeout_s = host, int(port), connect_timeout_s
        self._sock = None

    def describe(self):
        return "%s:%d" % (self.host, self.port)

    @property
    def is_open(self):
        return self._sock is not None

    def open(self):
        sock = socket.create_connection((self.host, self.port), timeout=self.connect_timeout_s)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self._sock = sock

    def close(self):
        sock, self._sock = self._sock, None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass

    def write(self, data):
        self._sock.sendall(data)

    def read(self, timeout):
        self._sock.settimeout(max(timeout, 0.001))
        try:
            data = self._sock.recv(4096)
        except socket.timeout:
            return b""
        if not data:
            raise ConnectionError("the reader closed the connection")
        return data

    def flush_input(self):
        self._sock.settimeout(0.0)
        try:
            while self._sock.recv(4096):
                pass
        except (BlockingIOError, socket.timeout):
            pass
        except OSError:
            pass


class SerialTransport:
    """RS-232 through pyserial (imported only when a serial reader is really used)."""

    def __init__(self, port, baud=9600, factory=None):
        self.port, self.baud = port, int(baud)
        self._factory = factory
        self._ser = None

    def describe(self):
        return "%s@%d" % (self.port, self.baud)

    @property
    def is_open(self):
        return self._ser is not None

    def open(self):
        factory = self._factory
        if factory is None:
            try:
                import serial
            except ImportError:
                raise ScanError("cổng COM cần thư viện pyserial (pip install pyserial)")
            # "COM3" -> normal port; "socket://host:port" / "rfc2217://..." (RS-232 over Ethernet adapters) -> URL handler
            factory = serial.serial_for_url if "://" in self.port else serial.Serial
        self._ser = factory(self.port, self.baud, timeout=0.05, write_timeout=2.0)

    def close(self):
        ser, self._ser = self._ser, None
        if ser is not None:
            try:
                ser.close()
            except Exception:
                pass

    def write(self, data):
        self._ser.write(data)
        self._ser.flush()

    def read(self, timeout):
        end = time.monotonic() + max(timeout, 0.0)
        while True:
            waiting = self._ser.in_waiting
            if waiting:
                return self._ser.read(waiting)
            if time.monotonic() >= end:
                return b""
            time.sleep(0.01)

    def flush_input(self):
        self._ser.reset_input_buffer()


# --------------------------------------------------------------------------- #
# reader
# --------------------------------------------------------------------------- #
class KeyenceScanner:
    def __init__(self, name, transport, length=0, pattern="", retry=2, timeout_s=3.0, terminator="\r\n",
                 no_read="ERROR", model=""):
        self.name, self.transport = name, transport
        self.length, self.retry, self.timeout_s = int(length), int(retry), float(timeout_s)
        self.pattern = pattern or ""
        self._re = re.compile(self.pattern) if self.pattern else None
        self.terminator = terminator.encode("ascii")
        self.no_read = no_read.strip().upper()
        self.model = model
        self._lock = threading.Lock()          # one reading at a time
        self._wlock = threading.Lock()         # writes (LON from the job thread, LOFF from the operator button)
        self._buf = b""

    # ---- construction from settings --------------------------------------------- #
    @classmethod
    def from_config(cls, name, cfg, serial_factory=None):
        kind = str(cfg.get("type", "tcp")).lower()
        try:
            if kind == "tcp":
                transport = TcpTransport(cfg["host"], cfg.get("port", 9004), cfg.get("connect_timeout_s", 3.0))
            elif kind == "serial":
                transport = SerialTransport(cfg["port"], cfg.get("baud", 9600), serial_factory)
            else:
                raise ValueError("type phải là 'tcp' hoặc 'serial'")
            return cls(name, transport, cfg.get("length", 0), cfg.get("pattern", ""), cfg.get("retry", 2),
                       cfg.get("timeout_s", 3.0), cfg.get("terminator", "\r\n"), cfg.get("no_read", "ERROR"),
                       cfg.get("model", ""))
        except (KeyError, ValueError, TypeError, re.error) as ex:
            raise ScanError("máy quét %r: cấu hình sai (%s: %s)" % (name, type(ex).__name__, ex))

    def describe(self):
        return "%s (%s%s)" % (self.name, self.transport.describe(), ", " + self.model if self.model else "")

    # ---- connection ----------------------------------------------------------------- #
    def close(self):
        with self._lock:
            self.transport.close()
            self._buf = b""

    def _ensure_open(self):
        if not self.transport.is_open:
            try:
                self.transport.open()
            except ScanError:
                raise
            except OSError as ex:
                raise ScanError("máy quét %s: không kết nối được %s (%s)" % (self.name, self.transport.describe(), ex))
            self._buf = b""

    def _drop(self):
        self.transport.close()
        self._buf = b""

    def _send(self, command):
        with self._wlock:
            self.transport.write(command.encode("ascii") + self.terminator)

    # ---- one attempt ------------------------------------------------------------------ #
    def _next_line(self):
        for i, ch in enumerate(self._buf):
            if ch in (10, 13):
                line, self._buf = self._buf[:i], self._buf[i + 1:]
                text = line.decode("ascii", "replace").strip()
                if text:
                    return text
                return self._next_line()
        return None

    def _attempt(self, timeout_s, should_stop):
        self.transport.flush_input()
        self._buf = b""
        self._send(LON)
        end = time.monotonic() + timeout_s
        while True:
            if should_stop is not None and should_stop():
                self._stop_reading()
                raise ScanCancelled("máy quét %s: đã hủy" % self.name)
            line = self._next_line()
            if line is not None:
                up = line.upper()
                if up.startswith("ER,"):
                    raise _NoRead("máy quét báo lỗi lệnh: %s" % line)
                if up == self.no_read:
                    raise _NoRead("máy quét không đọc được mã (%s)" % line)
                return line.replace(" ", "").replace("\t", "")
            remaining = end - time.monotonic()
            if remaining <= 0:
                self._stop_reading()
                raise _NoRead("hết thời gian chờ (%.1fs)" % timeout_s)
            self._buf += self.transport.read(min(0.1, remaining))

    def _stop_reading(self):
        try:
            self._send(LOFF)
            self.transport.flush_input()
        except Exception:
            pass

    def check(self, code, length=None, pattern=None):
        """Raises _NoRead when `code` does not satisfy the length / pattern."""
        length = self.length if length is None else int(length)
        if length and len(code) != length:
            raise _NoRead("mã '%s' dài %d ký tự, cần %d" % (code, len(code), length))
        regex = self._re if pattern is None else (re.compile(pattern) if pattern else None)
        if regex is not None and not regex.fullmatch(code):
            raise _NoRead("mã '%s' không đúng mẫu %s" % (code, regex.pattern))

    # ---- public API --------------------------------------------------------------------- #
    def scan(self, length=None, pattern=None, retry=None, timeout_s=None, should_stop=None, blocking=True):
        """Read one code (LON ... result), validate it, retry on failure. Returns the code or raises ScanError."""
        if not self._lock.acquire(blocking):
            raise ScanError("máy quét %s đang bận" % self.name)
        try:
            retry = self.retry if retry is None else int(retry)
            timeout_s = self.timeout_s if timeout_s is None else float(timeout_s)
            reasons = []
            for attempt in range(retry + 1):
                if should_stop is not None and should_stop():
                    raise ScanCancelled("máy quét %s: đã hủy" % self.name)
                try:
                    try:
                        self._ensure_open()
                    except ScanCancelled:
                        raise
                    except ScanError as ex:                      # cannot connect: a failed attempt like any other
                        raise _NoRead(str(ex).replace("máy quét %s: " % self.name, ""))
                    code = self._attempt(timeout_s, should_stop)
                    self.check(code, length, pattern)
                    log.info("scanner %s: %s (attempt %d)", self.name, code, attempt + 1)
                    return code
                except _NoRead as ex:
                    reasons.append(str(ex))
                    log.warning("scanner %s attempt %d/%d: %s", self.name, attempt + 1, retry + 1, ex)
                except (OSError, ConnectionError) as ex:         # link lost: reconnect on the next attempt
                    reasons.append("mất kết nối (%s)" % ex)
                    self._drop()
            raise ScanError("máy quét %s: không đọc được mã sau %d lần thử - %s"
                            % (self.name, retry + 1, reasons[-1]))
        finally:
            self._lock.release()

    def stop(self):
        """LOFF: stop a reading in progress (operator button). Safe to call at any time, also during a scan."""
        if not self.transport.is_open:
            return                                               # not connected: nothing is being read
        try:
            self._send(LOFF)
        except (OSError, ConnectionError) as ex:
            raise ScanError("máy quét %s: không gửi được LOFF (%s)" % (self.name, ex))

