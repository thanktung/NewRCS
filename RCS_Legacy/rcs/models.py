"""
models.py - Pure data model (no sockets, no threads, no Qt).

Everything here is deterministic and unit-testable.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Enums
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class BoardState(Enum):
    UNTESTED = "UNTESTED"
    PASS = "PASS"
    NG = "NG"


class BoxState(Enum):
    EMPTY = "empty"
    READY = "ready_for_test"
    TESTING = "testing"
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"
    UNKNOWN = "unknown"       # no information (not connected / connection lost)


# Box finished a test (result is waiting to be unloaded)
DONE_STATES = frozenset({BoxState.PASS, BoxState.FAIL, BoxState.ERROR})
# Box already holds a board (waiting for test, or testing)
ACTIVE_STATES = frozenset({BoxState.TESTING, BoxState.READY})


class SystemState(Enum):
    """Life-cycle of the scheduler (see core/state_machine.py)."""
    STOPPED = "stopped"       # not connected
    IDLE = "idle"             # connected, loop not running
    RUNNING = "running"
    PAUSING = "pausing"       # finishing the current robot command
    PAUSED = "paused"
    FAULT = "fault"           # needs operator acknowledgement


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Board / Tray / Gripper
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@dataclass
class Board:
    board_id: int
    state: BoardState = BoardState.UNTESTED
    # (tray_id, slot) the board was picked from. Used by place_policy=origin.
    origin: Optional[tuple] = None
    # True once the board has already been re-tested after a first FAIL.
    retested: bool = False
    # Box ids that have already tested this board (for retest in another box).
    tested_in: list = field(default_factory=list)

    def __repr__(self) -> str:
        return f"B{self.board_id}({self.state.value})"


@dataclass
class Tray:
    tray_id: int
    n_slots: int
    slots: list = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.slots:
            self.slots = [None] * self.n_slots

    def prefill(self, start_id: int) -> int:
        """Fill every slot with a fresh UNTESTED board, return next free id."""
        for i in range(self.n_slots):
            self.slots[i] = Board(start_id + i)
        return start_id + self.n_slots

    def first_untested_slot(self) -> Optional[int]:
        for i, b in enumerate(self.slots):
            if b and b.state == BoardState.UNTESTED:
                return i
        return None

    def first_empty_slot(self) -> Optional[int]:
        for i, b in enumerate(self.slots):
            if b is None:
                return i
        return None

    def is_full(self) -> bool:
        return all(b is not None for b in self.slots)

    def has_empty(self) -> bool:
        return any(b is None for b in self.slots)

    def untested_count(self) -> int:
        return sum(1 for b in self.slots if b and b.state == BoardState.UNTESTED)

    def pass_count(self) -> int:
        return sum(1 for b in self.slots if b and b.state == BoardState.PASS)

    def empty_count(self) -> int:
        return sum(1 for b in self.slots if b is None)


@dataclass
class GripperHead:
    head_id: int
    board: Optional[Board] = None
    enabled: bool = True      # False -> head is not used for NEW operations

    @property
    def is_empty(self) -> bool:
        return self.board is None


class Gripper:
    def __init__(self, n_heads: int) -> None:
        self.heads = [GripperHead(i) for i in range(n_heads)]

    def empty_heads(self) -> list:
        return [h.head_id for h in self.heads if h.enabled and h.is_empty]

    def untested_heads(self) -> list:
        return [h.head_id for h in self.heads
                if h.enabled and h.board and h.board.state == BoardState.UNTESTED]

    def tested_heads(self) -> list:
        """Heads holding a tested (PASS/NG) board. A disabled head keeps its
        board untouched until it is enabled again."""
        return [h.head_id for h in self.heads
                if h.enabled and h.board and h.board.state != BoardState.UNTESTED]

    def loaded_count(self) -> int:
        return sum(1 for h in self.heads if h.enabled and not h.is_empty)

    def empty_count(self) -> int:
        return sum(1 for h in self.heads if h.enabled) - self.loaded_count()


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Box record
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@dataclass
class BoxRecord:
    """Everything the scheduler knows about one test fixture."""
    box_id: int
    state: BoxState = BoxState.UNKNOWN
    state_since: float = field(default_factory=time.monotonic)
    loaded_at: float = 0.0           # monotonic time of the last successful LOAD
    board: Optional[Board] = None
    enabled: bool = True
    connected: bool = False
    tested: int = 0
    passed: int = 0
    fail_streak: int = 0
    watchdog_warned: bool = False

    def set_state(self, state: BoxState) -> bool:
        """Update state; returns True when it actually changed."""
        if state == self.state:
            return False
        self.state = state
        self.state_since = time.monotonic()
        self.watchdog_warned = False
        return True

