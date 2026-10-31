"""
state_machine.py - Scheduler life-cycle.

                 connect()                start()
      STOPPED ───────────────▶ IDLE ───────────────▶ RUNNING ◀──────────┐
         ▲                       ▲                     │   │              │ resume()
         │ disconnect()          │                pause()  fault          │
         │                       │                     ▼   │              │
         ├───────────────────────┼──────────────── PAUSING │          PAUSED
         │                       │                     │   │              ▲
         │                       │                     ▼   ▼              │
         └────────────────── any state ◀────────────  FAULT ── acknowledge_fault()

FAULT means "the software no longer trusts its picture of the physical world"
(robot timeout / ERR, box refused a command, unhandled exception ...). Only an
explicit operator acknowledgement leaves FAULT.
"""

from __future__ import annotations

import threading
from typing import Callable, Optional

from ..models import SystemState as S

_ALLOWED = {
    S.STOPPED: {S.IDLE},
    S.IDLE:    {S.RUNNING, S.STOPPED, S.FAULT},
    S.RUNNING: {S.PAUSING, S.FAULT, S.STOPPED},
    S.PAUSING: {S.PAUSED, S.RUNNING, S.FAULT, S.STOPPED},
    S.PAUSED:  {S.RUNNING, S.STOPPED, S.FAULT, S.IDLE},
    S.FAULT:   {S.PAUSED, S.STOPPED},
}


class InvalidTransition(RuntimeError):
    pass


class StateMachine:
    def __init__(self, on_change: Optional[Callable[[S, S, str], None]] = None) -> None:
        self._state = S.STOPPED
        self._lock = threading.Lock()
        self._on_change = on_change

    @property
    def state(self) -> S:
        return self._state

    def can(self, new: S) -> bool:
        return new in _ALLOWED[self._state]

    def transition(self, new: S, reason: str = "", *, strict: bool = True) -> bool:
        """Move to `new`. Returns True if the state changed.

        strict=False: an illegal transition returns False instead of raising
        (used by background threads that race with the operator).
        """
        with self._lock:
            old = self._state
            if new == old:
                return False
            if new not in _ALLOWED[old]:
                if strict:
                    raise InvalidTransition(f"{old.value} -> {new.value} not allowed")
                return False
            self._state = new
        if self._on_change is not None:
            self._on_change(old, new, reason)
        return True
