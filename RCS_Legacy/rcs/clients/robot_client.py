"""
robot_client.py - RobotGateway: TCP link to the Fanuc robot program.

Design
------
* ONE reader thread owns the socket for receiving. It parses every line with the
  protocol codec and routes the Reply to the caller waiting for that sequence
  number. Replies nobody waits for (late DONE after a timeout) are logged and
  dropped, so they can never be mistaken for the answer of the next command.
* execute() sends a command and blocks until DONE (or raises).
  - v2: waits for ACK (ack_timeout), then DONE/ERR (done_timeout).
  - legacy: waits for DONE:<NAME> (done_timeout).
* Motion commands are serialized by a lock and are NEVER re-sent automatically:
  after a timeout the robot may still be moving, so re-sending could execute
  the motion twice. The caller (scheduler) must go to FAULT instead.
* STATUS (v2 heartbeat) is not serialized with motion, so it can be answered
  while the robot is busy.
"""

from __future__ import annotations

import contextlib
import itertools
import logging
import queue
import socket
import threading
import time
from types import ModuleType
from typing import Optional

from ..protocol import commands as C
from ..protocol.commands import Reply, RobotCommand
from .errors import (RobotCommandError, RobotConnectionError, RobotError,
                     RobotProtocolError, RobotTimeout)
from .net import LineReader, close_quietly, open_connection

log = logging.getLogger("rcs.robot")

_LEGACY_KEY = -1          # legacy replies carry no seq -> one shared slot
_READ_POLL = 0.2          # socket timeout of the reader thread (stop-flag poll)


class RobotGateway:
    def __init__(self, host: str, port: int, codec: ModuleType,
                 ack_timeout: float = 3.0, done_timeout: float = 30.0,
                 connect_timeout: float = 3.0) -> None:
        self._address = (host, port)
        self._codec = codec
        self._ack_timeout = ack_timeout
        self._done_timeout = done_timeout
        self._connect_timeout = connect_timeout

        self._sock: Optional[socket.socket] = None
        self._reader = LineReader()
        self._reader_thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._connected = False
        self._send_lock = threading.Lock()
        self._motion_lock = threading.Lock()
        self._pending: dict = {}
        self._pending_lock = threading.Lock()
        self._seq = itertools.count(1)

    # ── properties ─────────────────────────
    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def supports_batch(self) -> bool:
        return bool(self._codec.SUPPORTS_BATCH)

    @property
    def protocol_name(self) -> str:
        return self._codec.NAME

    # ── lifecycle ──────────────────────────
    def connect(self) -> None:
        self.close()
        try:
            self._sock = open_connection(self._address, self._connect_timeout, _READ_POLL)
        except OSError as e:
            raise RobotConnectionError(f"cannot connect to robot {self._address}: {e}") from e
        self._reader.clear()
        self._stop.clear()
        self._connected = True
        self._reader_thread = threading.Thread(
            target=self._read_loop, name="robot-reader", daemon=True)
        self._reader_thread.start()
        log.info("robot connected %s (protocol=%s)", self._address, self._codec.NAME)

    def reconnect(self) -> None:
        """Drop the socket and connect again (used when resuming from FAULT so
        that no stale reply from before the fault can leak in)."""
        self.connect()

    def close(self) -> None:
        self._stop.set()
        self._connected = False
        close_quietly(self._sock)
        self._sock = None
        t = self._reader_thread
        if t is not None and t is not threading.current_thread():
            t.join(timeout=2.0)
        self._reader_thread = None
        self._fail_pending(RobotConnectionError("robot connection closed"))

    # ── reader thread ──────────────────────
    def _read_loop(self) -> None:
        sock = self._sock
        while not self._stop.is_set() and sock is not None:
            try:
                line = self._reader.read_line(sock)
            except (OSError, ConnectionError) as e:
                if not self._stop.is_set():
                    log.error("robot connection lost: %s", e)
                    self._connected = False
                    self._fail_pending(RobotConnectionError(f"robot connection lost: {e}"))
                return
            if not line:
                continue
            reply = self._codec.parse(line)
            if reply.kind == C.OTHER:
                log.debug("robot: ignored line %r", line)
                continue
            key = reply.seq if self._codec.SUPPORTS_SEQ else _LEGACY_KEY
            with self._pending_lock:
                q = self._pending.get(key)
            if q is None:
                log.warning("robot: stale/unexpected reply dropped: %r", line)
                continue
            q.put(reply)

    def _fail_pending(self, exc: Exception) -> None:
        with self._pending_lock:
            queues = list(self._pending.values())
        for q in queues:
            q.put(exc)

    # ── command execution ──────────────────
    def execute(self, cmd: RobotCommand) -> Reply:
        """Send `cmd`, wait for completion. Raises RobotError subclasses."""
        if not self._connected:
            raise RobotConnectionError("robot not connected")
        if len(cmd.items) > 1 and not self._codec.SUPPORTS_BATCH:
            raise ValueError(f"protocol '{self._codec.NAME}' cannot send a batch")

        guard = self._motion_lock if cmd.is_motion else contextlib.nullcontext()
        with guard:
            seq = next(self._seq)
            key = seq if self._codec.SUPPORTS_SEQ else _LEGACY_KEY
            q: queue.Queue = queue.Queue()
            with self._pending_lock:
                self._pending[key] = q
            try:
                text = self._codec.encode(cmd, seq)
                self._send_text(text)
                log.info("-> %s", text)
                reply = self._wait(q, cmd)
                log.info("<- %s", reply.raw)
                return reply
            finally:
                with self._pending_lock:
                    self._pending.pop(key, None)

    def _send_text(self, text: str) -> None:
        data = (text + self._codec.TERMINATOR).encode("utf-8")
        sock = self._sock
        if sock is None:
            raise RobotConnectionError("robot not connected")
        with self._send_lock:
            try:
                sock.sendall(data)
            except OSError as e:
                self._connected = False
                raise RobotConnectionError(f"send failed: {e}") from e

    def _wait(self, q: queue.Queue, cmd: RobotCommand) -> Reply:
        need_ack = bool(self._codec.SUPPORTS_ACK)
        done_to = self._ack_timeout if cmd.name == C.STATUS else self._done_timeout
        deadline = time.monotonic() + (self._ack_timeout if need_ack else done_to)

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                what = "ACK" if need_ack else "DONE"
                raise RobotTimeout(f"no {what} for {cmd} (robot may still be moving)")
            try:
                item = q.get(timeout=remaining)
            except queue.Empty:
                continue                      # loop re-checks the deadline
            if isinstance(item, Exception):
                raise item

            reply: Reply = item
            if reply.kind == C.ACK:
                if need_ack:
                    need_ack = False
                    deadline = time.monotonic() + done_to
                continue
            if reply.kind == C.ERR:
                raise RobotCommandError(reply.name or cmd.name, reply.index, reply.code)
            if reply.kind == C.STAT:
                if cmd.name == C.STATUS:
                    return reply
                continue
            if reply.kind == C.DONE:
                if reply.name != cmd.name:
                    raise RobotProtocolError(
                        f"sent '{cmd.name}' but robot answered '{reply.raw}'")
                return reply

    # ── helpers ────────────────────────────
    def query_status(self) -> str:
        """v2 only: return the robot state (IDLE/BUSY/ALARM/ESTOP)."""
        reply = self.execute(C.status())
        return reply.code


__all__ = ["RobotGateway", "RobotError"]
