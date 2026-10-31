"""
box_simulator.py - Simulates the test fixtures (boxes) on localhost.

Each simulated box listens on its own TCP port and PUSHES its state
(empty | ready_for_test | testing | pass | fail | error) whenever it changes,
exactly like the real fixture. It answers LOAD / UNLOAD with OK / BUSY / NOT_READY.

Run standalone (matches station.ini in sim mode):
    python sim/box_simulator.py --count 30 --start-port 5001

Import in tests:
    from sim.box_simulator import SimBox
"""

from __future__ import annotations

import argparse
import logging
import random
import socket
import threading
import time
from typing import Optional

log = logging.getLogger("sim.box")


class SimBox:
    def __init__(self, box_id: int, host: str = "127.0.0.1", port: int = 0,
                 test_time: tuple = (1.0, 3.0), fail_rate: float = 0.1,
                 error_rate: float = 0.0, ready_delay: float = 0.1,
                 seed: Optional[int] = None) -> None:
        self.box_id = box_id
        self.host = host
        self._test_time = test_time
        self._fail_rate = fail_rate
        self._error_rate = error_rate
        self._ready_delay = ready_delay
        self._rng = random.Random(seed if seed is not None else box_id)

        self.state = "empty"
        self._lock = threading.Lock()
        self._conns: list = []
        self._stop = threading.Event()
        self._timers: list = []

        self._srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv.bind((host, port))
        self._srv.listen(5)
        self._srv.settimeout(0.3)
        self.port = self._srv.getsockname()[1]
        self._thread = threading.Thread(target=self._accept_loop,
                                        name=f"simbox{box_id}", daemon=True)

    # ── lifecycle ──────────────────────────
    def start(self) -> "SimBox":
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        for t in self._timers:
            t.cancel()
        self.drop_connections()
        try:
            self._srv.close()
        except OSError:
            pass

    def drop_connections(self) -> None:
        """Test helper: simulate a network failure."""
        with self._lock:
            conns, self._conns = self._conns, []
        for c in conns:
            try:
                c.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            c.close()

    # ── state machine ──────────────────────
    def _push(self, state: str) -> None:
        """Set state and push it to every connected client (lock held by caller)."""
        self.state = state
        data = (state + "\r\n").encode()
        for c in list(self._conns):
            try:
                c.sendall(data)
            except OSError:
                self._conns.remove(c)

    def force_state(self, state: str) -> None:
        """Test helper: jump to a state and push it."""
        with self._lock:
            self._push(state)

    def _later(self, delay: float, fn) -> None:
        t = threading.Timer(delay, fn)
        t.daemon = True
        self._timers.append(t)
        t.start()

    def _begin_testing(self) -> None:
        with self._lock:
            if self.state != "ready_for_test":
                return
            self._push("testing")
        self._later(self._rng.uniform(*self._test_time), self._finish_testing)

    def _finish_testing(self) -> None:
        with self._lock:
            if self.state != "testing":
                return
            r = self._rng.random()
            if r < self._error_rate:
                self._push("error")
            elif r < self._error_rate + self._fail_rate:
                self._push("fail")
            else:
                self._push("pass")

    def _handle(self, cmd: str, conn: socket.socket) -> None:
        cmd = cmd.strip().upper()
        with self._lock:
            if cmd == "LOAD":
                if self.state == "empty":
                    reply = "OK"
                else:
                    reply = "BUSY"
            elif cmd == "UNLOAD":
                if self.state in ("pass", "fail", "error"):
                    reply = "OK"
                else:
                    reply = "NOT_READY"
            else:
                reply = "ERR"
            conn.sendall((reply + "\r\n").encode())
            if reply == "OK":
                if cmd == "LOAD":
                    self._push("ready_for_test")
                    self._later(self._ready_delay, self._begin_testing)
                else:
                    self._push("empty")

    # ── networking ─────────────────────────
    def _accept_loop(self) -> None:
        while not self._stop.is_set():
            try:
                conn, _ = self._srv.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            with self._lock:
                self._conns.append(conn)
                try:
                    conn.sendall((self.state + "\r\n").encode())   # push on connect
                except OSError:
                    continue
            threading.Thread(target=self._client_loop, args=(conn,),
                             daemon=True).start()

    def _client_loop(self, conn: socket.socket) -> None:
        buf = b""
        conn.settimeout(0.5)
        while not self._stop.is_set():
            try:
                data = conn.recv(1024)
            except socket.timeout:
                continue
            except OSError:
                break
            if not data:
                break
            buf += data
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                if line.strip():
                    try:
                        self._handle(line.decode(), conn)
                    except OSError:
                        return
        with self._lock:
            if conn in self._conns:
                self._conns.remove(conn)
        try:
            conn.close()
        except OSError:
            pass


def main() -> None:
    ap = argparse.ArgumentParser(description="RCS box simulator")
    ap.add_argument("--count", type=int, default=30)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--start-port", type=int, default=5001)
    ap.add_argument("--test-time", type=float, nargs=2, default=(2.0, 6.0),
                    metavar=("MIN", "MAX"))
    ap.add_argument("--fail-rate", type=float, default=0.1)
    ap.add_argument("--error-rate", type=float, default=0.0)
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    boxes = [SimBox(i, args.host, args.start_port + i - 1,
                    tuple(args.test_time), args.fail_rate, args.error_rate).start()
             for i in range(1, args.count + 1)]
    log.info("%d boxes listening on %s:%d..%d", args.count, args.host,
             args.start_port, args.start_port + args.count - 1)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        for b in boxes:
            b.stop()


if __name__ == "__main__":
    main()
