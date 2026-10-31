"""
box.py - Fixture (box) protocol.

The box PUSHES one line whenever its state changes (and right after connect):
    empty | ready_for_test | testing | pass | fail | error
The PC sends LOAD / UNLOAD (terminated by "\\r\\n") and the box answers with a
response line: OK | BUSY | NOT_READY.

Because both kinds of lines arrive on the same socket, a line that is a valid
BoxState value is a state push; everything else is a command response.
"""

from __future__ import annotations

from typing import Optional

from ..models import BoxState

CMD_LOAD = "LOAD"
CMD_UNLOAD = "UNLOAD"
RESP_OK = "OK"
TERMINATOR = "\r\n"

_STATE_BY_TEXT = {s.value: s for s in BoxState}


def parse_state(line: str) -> Optional[BoxState]:
    """Return the BoxState if `line` is a state push, else None."""
    return _STATE_BY_TEXT.get(line.strip().lower())
