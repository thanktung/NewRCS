"""
logging_setup.py - Central logging configuration.

Everything logs through the standard `logging` module (logger names "rcs.*").
Handlers: rotating file (always) + optional callback handler (the UI log panel).
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path
from typing import Callable, Optional

_FMT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


class CallbackHandler(logging.Handler):
    """Forwards formatted records to a callable (e.g. a Qt signal emitter)."""

    def __init__(self, callback: Callable[[int, str], None]) -> None:
        super().__init__(level=logging.INFO)
        self._callback = callback

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._callback(record.levelno, self.format(record))
        except Exception:                                    # noqa: BLE001
            self.handleError(record)


def setup_logging(log_dir: Optional[Path] = None,
                  callback: Optional[Callable[[int, str], None]] = None,
                  level: int = logging.INFO) -> Optional[CallbackHandler]:
    """Configure the "rcs" logger tree. Safe to call more than once."""
    root = logging.getLogger("rcs")
    root.setLevel(level)
    root.propagate = False
    for h in list(root.handlers):
        root.removeHandler(h)
        h.close()

    if log_dir is not None:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(
            log_dir / "rcs.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8")
        fh.setFormatter(logging.Formatter(_FMT))
        root.addHandler(fh)

    ch = None
    if callback is not None:
        ch = CallbackHandler(callback)
        ch.setFormatter(logging.Formatter("%(message)s"))
        root.addHandler(ch)
    return ch
