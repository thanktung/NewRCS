"""
metrics.py - Throughput / yield numbers.

ActiveClock counts only the time the scheduler was really RUNNING (Pause /
Stop / Fault time is excluded) so a long maintenance stop does not drag the
displayed rate down.
"""

from __future__ import annotations

import threading
import time
from typing import Optional


class ActiveClock:
    def __init__(self, accumulated: float = 0.0) -> None:
        self._accumulated = accumulated
        self._started: Optional[float] = None
        self._lock = threading.Lock()

    def start(self) -> None:
        with self._lock:
            if self._started is None:
                self._started = time.monotonic()

    def stop(self) -> None:
        with self._lock:
            if self._started is not None:
                self._accumulated += time.monotonic() - self._started
                self._started = None

    def elapsed(self) -> float:
        with self._lock:
            total = self._accumulated
            if self._started is not None:
                total += time.monotonic() - self._started
            return total

    def reset(self, accumulated: float = 0.0) -> None:
        with self._lock:
            self._accumulated = accumulated
            self._started = None


def rate_per_hour(count: int, elapsed_sec: float) -> float:
    return (count / elapsed_sec * 3600.0) if elapsed_sec > 0 else 0.0


def pass_percent(passed: int, tested: int) -> Optional[float]:
    return (passed / tested * 100.0) if tested > 0 else None
