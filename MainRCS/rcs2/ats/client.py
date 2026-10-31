"""TCP client tới chương trình ATS của một fixture (RCS là client, ATS lắng nghe).

Chạy một thread giám sát: kết nối, gửi heartbeat, giải mã khung và kết nối lại
mãi mãi. Callback chạy trên thread của chính client: giữ chúng thật ngắn (ví dụ phát một Qt signal).
"""
import logging
import socket
import threading

from . import protocol as P

log = logging.getLogger("rcs2.ats")


class AtsClient:
    def __init__(self, name, host, port, heartbeat_s=0.5, connect_timeout_s=3.0, retry_s=2.0,
                 on_event=None, on_connection=None, heartbeat_text=P.HEARTBEAT):
        self.name = name
        self.host, self.port = host, port
        self.heartbeat_s = heartbeat_s
        self.connect_timeout_s = connect_timeout_s
        self.retry_s = retry_s
        self.on_event = on_event                # callable(AtsEvent)
        self.on_connection = on_connection      # callable(bool)
        self.heartbeat_text = heartbeat_text
        self.connected = False
        self.stats = {"sent": 0, "received": 0, "reconnects": 0}
        self._sock = None
        self._send_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None

    # ------------------------------------------------------------------ #
    def start(self):
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="ats-%s" % self.name, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._close_socket()
        if self._thread is not None:
            self._thread.join(timeout=3.0)
        self._thread = None

    def send(self, text):
        """Gửi một khung. Trả về False (và bỏ khung đó) khi ATS chưa kết nối."""
        sock = self._sock
        if sock is None or not self.connected:
            return False
        try:
            with self._send_lock:
                sock.sendall(P.encode_frame(text))
            self.stats["sent"] += 1
            if text != self.heartbeat_text:
                log.info("[%s] -> %s", self.name, text)
            return True
        except OSError as ex:
            log.warning("[%s] send failed: %s", self.name, ex)
            self._close_socket()
            return False

    # ------------------------------------------------------------------ #
    def _close_socket(self):
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

    def _set_connected(self, state):
        if self.connected != state:
            self.connected = state
            log.info("[%s] %s", self.name, "connected" if state else "disconnected")
            if self.on_connection:
                try:
                    self.on_connection(state)
                except Exception:
                    log.exception("on_connection failed")

    def _run(self):
        while not self._stop.is_set():
            try:
                sock = socket.create_connection((self.host, self.port), timeout=self.connect_timeout_s)
            except OSError:
                self._stop.wait(self.retry_s)
                continue
            sock.settimeout(1.0)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self._sock = sock
            self.stats["reconnects"] += 1
            self._set_connected(True)
            beat_stop = threading.Event()
            beat = threading.Thread(target=self._heartbeat_loop, args=(beat_stop,),
                                    name="ats-beat-%s" % self.name, daemon=True)
            beat.start()
            try:
                self._read_loop(sock)
            finally:
                beat_stop.set()
                self._close_socket()
                self._set_connected(False)
            self._stop.wait(self.retry_s)

    def _heartbeat_loop(self, beat_stop):
        while not beat_stop.wait(self.heartbeat_s) and not self._stop.is_set():
            if not self.send(self.heartbeat_text):
                return

    def _read_loop(self, sock):
        decoder = P.FrameDecoder()
        while not self._stop.is_set():
            try:
                data = sock.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                return
            if not data:
                return
            for frame in decoder.feed(data):
                self.stats["received"] += 1
                event = P.parse_message(frame)
                if event.kind != P.UNKNOWN or frame.strip().lower() != self.heartbeat_text:
                    log.info("[%s] <- %s", self.name, frame)
                if self.on_event:
                    try:
                        self.on_event(event)
                    except Exception:
                        log.exception("on_event failed")

    # ------------------------------------------------------------------ #
    # các hàm tiện ích RCS -> ATS
    # ------------------------------------------------------------------ #
    def place_dut_ok(self):
        return self.send(P.place_dut_ok())

    def send_barcode(self, sn):
        return self.send(P.barcode(sn))

    def request_barcode(self):
        return self.send(P.request_barcode())

    def dut_out(self):
        return self.send(P.dut_out())

    def fixture_open(self):
        return self.send(P.fixture_open())

    def fixture_close(self):
        return self.send(P.fixture_close())
