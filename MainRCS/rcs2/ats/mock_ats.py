"""Chương trình ATS giả (đóng vai một fixture khi phát triển / test NewRCS).

    python -m rcs2.ats.mock_ats --port 8888 --test-time 3 --pass-rate 0.9

Hành vi (theo ADSServer cũ + một ATS điển hình):
  * nhận một kết nối RCS, ngắt nó nếu 4 s không có heartbeat (khi có --watchdog)
  * khi kết nối: gửi TtoC_resultWaitdut (fixture sẵn sàng nhận DUT)
  * B1=<SN>,            -> TtoC_readcodeOK
  * CtoT_placeDUTOK     -> TtoC_startOK, rồi sau --test-time: Pass / NG+item+value / Retest
  * CtoT_placeBarcode   -> TtoC_BarcodePass+<SN>
  * DUT_OUT             -> TtoC_resultWaitdut
  * f_open / f_close    -> fix_open / fix_close ; fixstatus -> fix_xxx hiện tại
"""
import argparse
import logging
import random
import socket
import sys
import threading
import time

from . import protocol as P

log = logging.getLogger("rcs2.mock_ats")


class MockAts:
    def __init__(self, host="127.0.0.1", port=8888, test_time=2.0, pass_rate=0.9, retest_rate=0.0,
                 ng_item="TEST_ITEM", ng_value="12.3", watchdog_s=0.0, seed=None):
        self.host, self.port = host, port
        self.test_time = test_time
        self.pass_rate = pass_rate
        self.retest_rate = retest_rate
        self.ng_item, self.ng_value = ng_item, ng_value
        self.watchdog_s = watchdog_s            # 0 = không ngắt client im lặng
        self.forced_results = []                # ví dụ ["NG", "PASS"], được dùng trước
        self.received = []                      # mọi khung không phải heartbeat, để kiểm tra trong test
        self.fixture_state = "fix_open"
        self.current_sn = ""
        self._rng = random.Random(seed)
        self._server = None
        self._conn = None
        self._conn_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._last_beat = time.monotonic()

    # ---- vòng đời ------------------------------------------------------- #
    def start(self):
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind((self.host, self.port))
        self._server.listen(2)
        self._server.settimeout(0.5)
        self.port = self._server.getsockname()[1]
        self._thread = threading.Thread(target=self._accept_loop, name="mock-ats", daemon=True)
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        self._drop_connection()
        if self._server is not None:
            self._server.close()
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def _drop_connection(self):
        with self._conn_lock:
            conn, self._conn = self._conn, None
        if conn is not None:
            try:
                conn.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            conn.close()

    # ---- mạng ----------------------------------------------------------- #
    def _accept_loop(self):
        while not self._stop.is_set():
            try:
                conn, addr = self._server.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            self._drop_connection()                 # RCS mới thay cho RCS cũ
            with self._conn_lock:
                self._conn = conn
            self._last_beat = time.monotonic()
            threading.Thread(target=self._serve, args=(conn,), name="mock-ats-conn", daemon=True).start()

    def _send(self, text, conn=None):
        conn = conn or self._conn
        if conn is None:
            return
        try:
            conn.sendall(P.encode_frame(text))
        except OSError:
            pass

    def _serve(self, conn):
        conn.settimeout(0.5)
        decoder = P.FrameDecoder()
        self._send("TtoC_resultWaitdut", conn)
        while not self._stop.is_set():
            if self.watchdog_s and time.monotonic() - self._last_beat > self.watchdog_s:
                log.info("no heartbeat for %.1fs: dropping the client", self.watchdog_s)
                break
            try:
                data = conn.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            if not data:
                break
            for frame in decoder.feed(data):
                self._handle(frame.strip(), conn)
        with self._conn_lock:
            if self._conn is conn:
                self._conn = None
        try:
            conn.close()
        except OSError:
            pass

    # ---- hành vi -------------------------------------------------------- #
    def _handle(self, frame, conn):
        low = frame.lower()
        if "aaa" in low:
            self._last_beat = time.monotonic()
            return
        if low == "fixstatus":
            self._last_beat = time.monotonic()
            self._send(self.fixture_state, conn)
            return
        self.received.append(frame)
        if "placedutok" in low:
            self._send("TtoC_startOK", conn)
            threading.Thread(target=self._run_test, args=(conn,), daemon=True).start()
        elif low.startswith("b1="):
            self.current_sn = frame[3:].strip().rstrip(",").replace("Code0:", "")
            self._send("TtoC_readcodeOK", conn)
        elif "placebarcode" in low:
            self._send("TtoC_BarcodePass+%s" % (self.current_sn or "SN000000"), conn)
        elif "dut_out" in low:
            self._send("TtoC_resultWaitdut", conn)
        elif low == "f_open":
            self.fixture_state = "fix_open"
            self._send("fix_open", conn)
        elif low == "f_close":
            self.fixture_state = "fix_close"
            self._send("fix_close", conn)

    def _next_result(self):
        if self.forced_results:
            return self.forced_results.pop(0).upper()
        r = self._rng.random()
        if r < self.retest_rate:
            return "RETEST"
        return "PASS" if self._rng.random() < self.pass_rate else "NG"

    def _run_test(self, conn):
        time.sleep(self.test_time)
        result = self._next_result()
        if result == "PASS":
            self._send("TtoC_resultPass", conn)
        elif result == "RETEST":
            self._send("TtoC_resultRetest+%s" % (self.current_sn or "SN"), conn)
        else:
            self._send("TtoC_resultNG+%s+%s" % (self.ng_item, self.ng_value), conn)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Mock ATS program")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8888)
    ap.add_argument("--test-time", type=float, default=2.0)
    ap.add_argument("--pass-rate", type=float, default=0.9)
    ap.add_argument("--retest-rate", type=float, default=0.0)
    ap.add_argument("--watchdog", type=float, default=0.0)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    mock = MockAts(args.host, args.port, args.test_time, args.pass_rate, args.retest_rate,
                   watchdog_s=args.watchdog).start()
    print("mock ATS listening on %s:%d (Ctrl+C to stop)" % (mock.host, mock.port))
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        mock.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
