"""
robot_simulator.py - Simulates the Fanuc robot program on localhost.

Speaks BOTH protocols:
    legacy : "PICK:1,5,2;"            -> "DONE:PICK"
    v2     : "#12 PICK:1,5,0|1,6,1;"  -> "ACK:12" ... "DONE:12:PICK" | "ERR:12:PICK:1:VAC_FAIL"
             "#14 STATUS;"            -> "STAT:14:IDLE"   (answered even while moving)

Fault injection (for tests and demos):
    robot.inject_error("PICK", index=0, code="VAC_FAIL")   one-shot ERR
    robot.hang_next()                                       swallow next motion command
    robot.set_alarm(True)                                   STATUS -> ALARM

Run standalone:
    python sim/robot_simulator.py --protocol v2 --port 6000
"""

from __future__ import annotations

import argparse
import logging
import queue
import re
import socket
import threading
import time
from typing import Optional

log = logging.getLogger("sim.robot")

_V2_RE = re.compile(r"^#(\d+)\s+([A-Za-z]+)(?::([^;]*))?;?\s*$")
_LEGACY_RE = re.compile(r"^([A-Za-z]+)(?::([^;]*))?;?\s*$")
_MOTION = {"PICK", "PLACE", "LOAD", "UNLOAD", "CHANGE"}


class SimRobot:
    def __init__(self, host: str = "127.0.0.1", port: int = 0,
                 protocol: str = "legacy", move_time: float = 0.05) -> None:
        if protocol not in ("legacy", "v2"):
            raise ValueError("protocol must be 'legacy' or 'v2'")
        self.protocol = protocol
        self._move_time = move_time

        self.executed: list = []          # (name, items) of every completed item
        self.commands: list = []          # raw lines received
        self._errors: list = []           # one-shot injected errors
        self._hang = 0
        self._alarm = False
        self._busy = False
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._conn: Optional[socket.socket] = None
        self._work: "queue.Queue" = queue.Queue()
        self._send_lock = threading.Lock()

        self._srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv.bind((host, port))
        self._srv.listen(1)
        self._srv.settimeout(0.3)
        self.port = self._srv.getsockname()[1]
        self._threads = [
            threading.Thread(target=self._accept_loop, daemon=True, name="simrobot-acc"),
            threading.Thread(target=self._worker_loop, daemon=True, name="simrobot-work"),
        ]

    # â”€â”€ lifecycle â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def start(self) -> "SimRobot":
        for t in self._threads:
            t.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        self.drop_connection()
        try:
            self._srv.close()
        except OSError:
            pass

    def drop_connection(self) -> None:
        c, self._conn = self._conn, None
        if c:
            try:
                c.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            c.close()

    # â”€â”€ fault injection â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def inject_error(self, name: str, index: int = 0, code: str = "VAC_FAIL") -> None:
        self._errors.append((name.upper(), index, code))

    def hang_next(self, n: int = 1) -> None:
        self._hang += n

    def set_alarm(self, on: bool) -> None:
        self._alarm = on

    # â”€â”€ networking â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _send(self, text: str) -> None:
        c = self._conn
        if c is None:
            return
        with self._send_lock:
            try:
                c.sendall((text + "\n").encode())
            except OSError:
                pass

    def _accept_loop(self) -> None:
        while not self._stop.is_set():
            try:
                conn, _ = self._srv.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            self.drop_connection()
            self._conn = conn
            threading.Thread(target=self._reader_loop, args=(conn,), daemon=True).start()

    def _reader_loop(self, conn: socket.socket) -> None:
        buf = b""
        conn.settimeout(0.5)
        while not self._stop.is_set() and conn is self._conn:
            try:
                data = conn.recv(1024)
            except socket.timeout:
                continue
            except OSError:
                return
            if not data:
                return
            buf += data
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                text = line.decode(errors="replace").strip()
                if text:
                    self._dispatch(text)

    # â”€â”€ command handling â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    @staticmethod
    def _parse_items(body: Optional[str]) -> list:
        if not body:
            return []
        return [tuple(int(v) for v in it.split(",")) for it in body.split("|") if it]

    def _dispatch(self, text: str) -> None:
        self.commands.append(text)
        if self.protocol == "v2":
            m = _V2_RE.match(text)
            if not m:
                log.warning("bad v2 line: %r", text)
                return
            seq, name, body = int(m.group(1)), m.group(2).upper(), m.group(3)
        else:
            m = _LEGACY_RE.match(text)
            if not m:
                log.warning("bad legacy line: %r", text)
                return
            seq, name, body = None, m.group(1).upper(), m.group(2)

        if name == "STATUS" and self.protocol == "v2":
            state = "ALARM" if self._alarm else ("BUSY" if self._busy else "IDLE")
            self._send(f"STAT:{seq}:{state}")
            return
        if name == "RESET" and self.protocol == "v2":
            self._alarm = False
            self._send(f"ACK:{seq}")
            self._send(f"DONE:{seq}:RESET")
            return
        try:
            items = self._parse_items(body)
        except ValueError:
            if self.protocol == "v2":
                self._send(f"ERR:{seq}:{name}:0:BAD_ARG")
            return
        self._work.put((seq, name, items))

    def _worker_loop(self) -> None:
        while not self._stop.is_set():
            try:
                seq, name, items = self._work.get(timeout=0.3)
            except queue.Empty:
                continue
            self._busy = True
            try:
                self._run_command(seq, name, items)
            finally:
                self._busy = False

    def _run_command(self, seq: Optional[int], name: str, items: list) -> None:
        if self.protocol == "v2":
            self._send(f"ACK:{seq}")
        if self._hang > 0:
            self._hang -= 1
            log.info("hanging on %s (injected)", name)
            return
        if self._alarm and name in _MOTION:
            self._reply_err(seq, name, 0, "ALARM")
            return

        todo = items if items else [()]
        for idx, item in enumerate(todo):
            if self._errors and self._errors[0][0] == name and self._errors[0][1] == idx:
                _, _, code = self._errors.pop(0)
                self._reply_err(seq, name, idx, code)
                return
            time.sleep(self._move_time)
            self.executed.append((name, item))
        self._busy = False        # idle BEFORE the reply, so STATUS after DONE is IDLE
        if self.protocol == "v2":
            self._send(f"DONE:{seq}:{name}")
        else:
            self._send(f"DONE:{name}")

    def _reply_err(self, seq: Optional[int], name: str, idx: int, code: str) -> None:
        if self.protocol == "v2":
            self._send(f"ERR:{seq}:{name}:{idx}:{code}")
        # legacy robot has no error reply: it simply never answers -> PC times out


def main() -> None:
    ap = argparse.ArgumentParser(description="RCS robot simulator")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=6000)
    ap.add_argument("--protocol", choices=("legacy", "v2"), default="legacy")
    ap.add_argument("--move-time", type=float, default=0.3,
                    help="seconds per item (pick/place/...)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    robot = SimRobot(args.host, args.port, args.protocol, args.move_time).start()
    log.info("robot simulator (%s) listening on %s:%d", args.protocol, args.host, robot.port)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        robot.stop()


if __name__ == "__main__":
    main()

