"""
persistence.py - Save / restore the station state across restarts.

The robot and the boards are physical: when the software crashes they are
still where they were. The scheduler snapshot is therefore written after every
robot operation, ATOMICALLY (write temp file, then os.replace) so a crash while
writing can never leave a half-written file.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

log = logging.getLogger("rcs.store")

FORMAT_VERSION = 2


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def save(self, data: dict) -> None:
        data = dict(data)
        data["format"] = FORMAT_VERSION
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=self.path.name,
                                   suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def load(self) -> Optional[dict]:
        """Return the saved state, or None if missing / unreadable / old format."""
        if not self.path.exists():
            return None
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            log.warning("cannot read %s: %s", self.path, e)
            return None
        if data.get("format") != FORMAT_VERSION:
            log.info("ignoring %s (format %r != %d)", self.path,
                     data.get("format"), FORMAT_VERSION)
            return None
        return data

    def clear(self) -> None:
        try:
            self.path.unlink()
        except OSError:
            pass


class NullStore:
    """Used when persistence is disabled (tests)."""

    def save(self, data: dict) -> None:
        pass

    def load(self) -> Optional[dict]:
        return None

    def clear(self) -> None:
        pass
