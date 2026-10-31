"""
robot_legacy.py - Legacy robot protocol (the one the current Fanuc program speaks).

PC -> Robot : "PICK:1,5,2;"      "CHANGE;"
Robot -> PC : "DONE:PICK"        "DONE:CHANGE"

No sequence number, no ACK, no error codes, no batch. Kept so the new software
can run against the existing robot program until it is upgraded to v2.
"""

from __future__ import annotations

from . import commands as C
from .commands import Reply, RobotCommand

NAME = "legacy"
SUPPORTS_BATCH = False
SUPPORTS_ACK = False
SUPPORTS_SEQ = False
TERMINATOR = "\n"


def encode(cmd: RobotCommand, seq: int) -> str:   # noqa: ARG001 - seq unused
    if len(cmd.items) > 1:
        raise ValueError("legacy protocol cannot send a batch")
    if cmd.name in (C.STATUS, C.RESET):
        raise ValueError(f"legacy protocol does not support {cmd.name}")
    body = ",".join(str(v) for v in cmd.items[0]) if cmd.items else ""
    return f"{cmd.name}:{body};" if body else f"{cmd.name};"


def parse(line: str) -> Reply:
    line = line.strip()
    up = line.upper()
    if up == "DONE":
        # Bare DONE: robot did not say which command finished -> name = "".
        return Reply(C.DONE, name="", raw=line)
    if up.startswith("DONE:"):
        return Reply(C.DONE, name=up.split(":", 1)[1].strip(), raw=line)
    return Reply(C.OTHER, raw=line)
