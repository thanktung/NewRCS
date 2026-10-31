"""
box_client.py - TCP link to ONE test fixture (box).

* One background thread per box: connect (with timeout) -> listen -> on
  connection loss reconnect with exponential backoff. start() never blocks, so
  30 boxes connect in parallel and one dead box cannot delay the others.
* The thread is the ONLY reader of the socket. A line that is a BoxState is a
  push -> on_state callback. Any other line is a command response -> queue.
* LOAD / UNLOAD wait for the response. Stale responses are flushed before every
  command so an old "OK" can never be taken as the answer of a new command.
"""

from __future__ import annotations

import logging
import queue
import socket
import threading
from typing import Callable, Optional

from ..models import BoxState
from ..protocol import box as box_proto
from .errors import BoxNotConnected, BoxTimeout
from .net import LineReader, close_quietly, open_connection

log = logging.getLogger("rcs.box")

_READ_POLL = 0.5
_MAX_BACKOFF = 30.0

StateCallback = Callable[[int, BoxState], None]
ConnectionCallback = Callable[[int, bool], None]


class BoxClient:
    def __init__(self, box_id: int, address: tuple,
                 connect_timeout: float = 3.0, recv_timeout: float = 5.0,
                 reconnect_backoff: float = 2.0) -> None:
        self.box_id = box_id
        self._address = address
        self._connect_timeout = connect_timeout
        self._recv_timeout = recv_timeout
        self._backoff0 = reconnect_backoff

        self._sock: Optional[socket.socket] = None
        self._reader = LineReader()
        self._resp: "queue.Queue[str]" = queue.Queue()
        self._cmd_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._connected = False
        self._on_state: Optional[StateCallback] = None
        self._on_connection: Optional[ConnectionCallback] = None

    @property
    def connected(self) -> bool:
        return self._connected

    # ── lifecycle ──────────────────────────
    def start(self, on_state: StateCallback,
              on_connection: Optional[ConnectionCallback] = None) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._on_state = on_state
        self._on_connection = on_connection
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name=f"box{self.box_id}-link", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        close_quietly(self._sock)          # unblocks recv immediately
        t = self._thread
        if t is not None and t is not threading.current_thread():
            t.join(timeout=2.0)
        self._thread = None
        self._connected = False

    # ── background thread ──────────────────
    def _notify_connection(self, up: bool) -> None:
        if self._on_connection is None:
            return
        try:
            self._on_connection(self.box_id, up)
        except Exception:                                  # noqa: BLE001
            log.exception("box%d connection callback failed", self.box_id)

    def _run(self) -> None:
        backoff = self._backoff0
        while not self._stop.is_set():
            try:
                sock = open_connection(self._address, self._connect_timeout, _READ_POLL)
            except OSError as e:
                log.warning("box%d connect %s failed: %s (retry in %.0fs)",
                            self.box_id, self._address, e, backoff)
                if self._stop.wait(backoff):
                    return
                backoff = min(backoff * 2, _MAX_BACKOFF)
                continue

            backoff = self._backoff0
            self._sock = sock
            self._reader.clear()
            self._flush_responses()
            self._connected = True
            log.info("box%d connected %s", self.box_id, self._address)
            self._notify_connection(True)
            try:
                self._listen(sock)
            except (OSError, ConnectionError) as e:
                if not self._stop.is_set():
                    log.error("box%d connection lost: %s", self.box_id, e)
            finally:
                self._connected = False
                close_quietly(sock)
                if not self._stop.is_set():
                    self._notify_connection(False)
            if self._stop.wait(backoff):
                return

    def _listen(self, sock: socket.socket) -> None:
        while not self._stop.is_set():
            line = self._reader.read_line(sock)
            if not line:
                continue
            state = box_proto.parse_state(line)
            if state is None:
                self._resp.put(line)               # response to LOAD / UNLOAD
                continue
            if self._on_state is not None:
                try:
                    self._on_state(self.box_id, state)
                except Exception:                              # noqa: BLE001
                    log.exception("box%d state callback failed", self.box_id)

    def _flush_responses(self) -> None:
        while True:
            try:
                self._resp.get_nowait()
            except queue.Empty:
                return

    # ── commands ───────────────────────────
    def _request(self, cmd: str) -> str:
        sock = self._sock
        if not self._connected or sock is None:
            raise BoxNotConnected(f"box{self.box_id} not connected")
        with self._cmd_lock:
            self._flush_responses()
            try:
                sock.sendall((cmd + box_proto.TERMINATOR).encode("utf-8"))
            except OSError as e:
                raise BoxNotConnected(f"box{self.box_id} send failed: {e}") from e
            try:
                return self._resp.get(timeout=self._recv_timeout).strip().upper()
            except queue.Empty:
                raise BoxTimeout(f"box{self.box_id}: no response to {cmd}") from None

    def load(self) -> str:
        """Tell the box a board was placed. Returns the response ('OK', 'BUSY'...)."""
        return self._request(box_proto.CMD_LOAD)

    def unload(self) -> str:
        """Tell the box the board was taken out."""
        return self._request(box_proto.CMD_UNLOAD)
