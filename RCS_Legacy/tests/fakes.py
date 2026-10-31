"""
fakes.py - In-memory robot / box clients so the Scheduler runs without sockets.

FakeRobot executes every command instantly (and records it). Faults can be
injected. FakeBox behaves like a real fixture: LOAD -> ready_for_test ->
(after test_delay) pass/fail; UNLOAD -> empty.
"""

from __future__ import annotations

import dataclasses
import threading
import time

from rcs.clients.errors import (BoxTimeout, RobotCommandError,
                                RobotConnectionError, RobotTimeout)
from rcs.config import StationConfig, validate
from rcs.models import BoxState
from rcs.protocol import commands as C


def make_cfg(**kw) -> StationConfig:
    n_boxes = kw.pop("box_count", 4)
    base = StationConfig(
        box_count=n_boxes, gripper_heads=3, tray_cols=2, tray_rows=2,
        ng_tray_slots=4,
        box_layout=(("A", tuple(range(1, n_boxes + 1))),),
        box_address={i: ("127.0.0.1", 0) for i in range(1, n_boxes + 1)},
        poll_interval=0.01, robot_done_timeout=1.0, robot_ack_timeout=0.5,
    )
    cfg = dataclasses.replace(base, **kw)
    validate(cfg)
    return cfg


class FakeRobot:
    def __init__(self, supports_batch: bool = False, delay: float = 0.0) -> None:
        self.supports_batch = supports_batch
        self.protocol_name = "fake"
        self.delay = delay
        self.connected = False
        self.commands: list = []          # RobotCommand history (executed ones)
        self._fail: list = []             # queued exceptions (one per command)
        self.status = "IDLE"
        self.connect_error = None
        self.reconnects = 0

    # fault injection ------------------------------------------------
    def fail_next(self, exc: Exception) -> None:
        self._fail.append(exc)

    # client API -----------------------------------------------------
    def connect(self) -> None:
        if self.connect_error:
            raise self.connect_error
        self.connected = True

    def reconnect(self) -> None:
        self.reconnects += 1
        self.connect()

    def close(self) -> None:
        self.connected = False

    def execute(self, cmd):
        if not self.connected:
            raise RobotConnectionError("fake robot closed")
        if self.delay:
            time.sleep(self.delay)
        if self._fail:
            exc = self._fail.pop(0)
            if not isinstance(exc, RobotCommandError):
                raise exc                  # timeout etc: command NOT recorded
            # ERR at item k: items before k were executed
            if exc.index > 0:
                self.commands.append(C.RobotCommand(cmd.name, cmd.items[:exc.index]))
            raise exc
        self.commands.append(cmd)
        return C.Reply(C.DONE, name=cmd.name)

    def query_status(self) -> str:
        return self.status

    # helpers --------------------------------------------------------
    def names(self) -> list:
        return [c.name for c in self.commands]

    def items_of(self, name: str) -> list:
        return [it for c in self.commands if c.name == name for it in c.items]


class FakeBox:
    def __init__(self, box_id: int, test_delay: float = 0.02,
                 results=None) -> None:
        self.box_id = box_id
        self.test_delay = test_delay
        self.results = list(results or [])       # popped per test, default "pass"
        self.refuse: str = ""                    # e.g. "BUSY" -> answer for LOAD
        self.timeout_next = False
        self.auto = True
        self.connected = False
        self.state = "empty"
        self.loads = 0
        self.unloads = 0
        self._on_state = None
        self._on_conn = None
        self._timers: list = []
        self._lock = threading.Lock()

    def start(self, on_state, on_connection=None) -> None:
        self._on_state, self._on_conn = on_state, on_connection
        self.connected = True
        if on_connection:
            on_connection(self.box_id, True)
        self.push(self.state)

    def stop(self) -> None:
        self.connected = False
        for t in self._timers:
            t.cancel()

    def push(self, state: str) -> None:
        self.state = state
        if self._on_state:
            self._on_state(self.box_id, BoxState(state))

    def drop(self) -> None:
        """Simulate connection loss."""
        self.connected = False
        if self._on_conn:
            self._on_conn(self.box_id, False)

    # commands -------------------------------------------------------
    def load(self) -> str:
        if self.timeout_next:
            self.timeout_next = False
            raise BoxTimeout("fake timeout")
        if self.refuse:
            return self.refuse
        self.loads += 1
        if self.auto:
            self.push("ready_for_test")
            t = threading.Timer(self.test_delay, self._finish)
            t.daemon = True
            self._timers.append(t)
            t.start()
        return "OK"

    def _finish(self) -> None:
        result = self.results.pop(0) if self.results else "pass"
        self.push("testing")
        self.push(result)

    def unload(self) -> str:
        self.unloads += 1
        self.push("empty")
        return "OK"


class FakeFactory:
    def __init__(self, robot: FakeRobot = None, **box_kw) -> None:
        self.robot = robot or FakeRobot()
        self.boxes: dict = {}
        self._box_kw = box_kw
        self.box_overrides: dict = {}      # box_id -> kwargs

    def create_robot(self, cfg):
        return self.robot

    def create_box(self, box_id, cfg):
        kw = dict(self._box_kw)
        kw.update(self.box_overrides.get(box_id, {}))
        box = FakeBox(box_id, **kw)
        self.boxes[box_id] = box
        return box


def wait_until(pred, timeout: float = 5.0, step: float = 0.01) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pred():
            return True
        time.sleep(step)
    return False


def all_board_ids(s) -> list:
    """Ids of every board currently known to the scheduler (for invariants)."""
    ids = []
    for tray in (s.tray1, s.tray2):
        ids += [b.board_id for b in tray.slots if b]
    ids += [b.board_id for b in s.ng_list]
    ids += [h.board.board_id for h in s.gripper.heads if h.board]
    ids += [r.board.board_id for r in s.boxes if r.board]
    return ids
