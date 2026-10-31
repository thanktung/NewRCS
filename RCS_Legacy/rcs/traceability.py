"""
traceability.py - One CSV row per finished test (logs/results_YYYYMMDD.csv).

Answers "which board was tested in which box, when, with what result" - the
basis for yield analysis and for finding a bad fixture.
"""

from __future__ import annotations

import csv
import logging
import threading
import time
from pathlib import Path

log = logging.getLogger("rcs.trace")

COLUMNS = ["timestamp", "board_id", "box_id", "head", "result",
           "origin_tray", "origin_slot", "test_seconds", "retest"]


class CsvRecorder:
    def __init__(self, directory: Path) -> None:
        self.dir = Path(directory)
        self._lock = threading.Lock()

    def record(self, row: dict) -> None:
        """Append a row. Never raises (a full disk must not stop the line)."""
        try:
            with self._lock:
                self.dir.mkdir(parents=True, exist_ok=True)
                path = self.dir / f"results_{time.strftime('%Y%m%d')}.csv"
                new = not path.exists()
                with open(path, "a", newline="", encoding="utf-8") as f:
                    w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
                    if new:
                        w.writeheader()
                    row = {"timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), **row}
                    w.writerow(row)
        except OSError as e:
            log.error("cannot write result CSV: %s", e)


class NullRecorder:
    def record(self, row: dict) -> None:
        pass


class ListRecorder:
    """In-memory recorder for tests."""

    def __init__(self) -> None:
        self.rows: list = []

    def record(self, row: dict) -> None:
        self.rows.append(row)
