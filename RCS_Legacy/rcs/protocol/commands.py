"""
commands.py - Transport-independent description of robot commands and replies.

The scheduler only talks in terms of RobotCommand / Reply. How these are put on
the wire (legacy text or protocol v2) is the job of a codec
(see robot_legacy.py / robot_v2.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# Command names
PICK = "PICK"        # item = (tray_id, slot, head)
PLACE = "PLACE"      # item = (tray_id, slot, head)   tray_id 0 = NG tray
LOAD = "LOAD"        # item = (box_id, head)
UNLOAD = "UNLOAD"    # item = (box_id, head)
CHANGE = "CHANGE"    # no items
STATUS = "STATUS"    # v2 only, no items
RESET = "RESET"      # v2 only, clear robot fault, no items

# Arity (number of ints) of one item for each command
ITEM_ARITY = {PICK: 3, PLACE: 3, LOAD: 2, UNLOAD: 2, CHANGE: 0, STATUS: 0, RESET: 0}
# Commands that move the robot. These are NEVER retried automatically.
MOTION_COMMANDS = frozenset({PICK, PLACE, LOAD, UNLOAD, CHANGE})
# Commands that may carry several items in one batch (protocol v2 only)
BATCHABLE = frozenset({PICK, PLACE, LOAD, UNLOAD})


class ErrorCode:
    """Error codes the robot may answer in ERR (see docs/PROTOCOL_V2.md)."""
    VAC_FAIL = "VAC_FAIL"            # vacuum not reached / part lost
    NO_PART = "NO_PART"              # nothing to pick at the source slot
    COLLISION = "COLLISION"
    TRAY_EMPTY = "TRAY_EMPTY"
    BOX_NOT_READY = "BOX_NOT_READY"  # fixture door/lid not ready for the robot
    ALARM = "ALARM"
    ESTOP = "ESTOP"
    BAD_ARG = "BAD_ARG"
    BUSY = "BUSY"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class RobotCommand:
    name: str
    items: tuple = ()          # tuple of int-tuples, one per head/box

    def __post_init__(self) -> None:
        if self.name not in ITEM_ARITY:
            raise ValueError(f"unknown robot command '{self.name}'")
        arity = ITEM_ARITY[self.name]
        if arity == 0 and self.items:
            raise ValueError(f"{self.name} takes no items")
        if arity and not self.items:
            raise ValueError(f"{self.name} needs at least one item")
        for it in self.items:
            if len(it) != arity:
                raise ValueError(f"{self.name} item {it} must have {arity} ints")
        if len(self.items) > 1 and self.name not in BATCHABLE:
            raise ValueError(f"{self.name} cannot be batched")

    @property
    def is_motion(self) -> bool:
        return self.name in MOTION_COMMANDS

    def __str__(self) -> str:
        body = "|".join(",".join(str(v) for v in it) for it in self.items)
        return f"{self.name}:{body}" if body else self.name


# Convenience constructors (keep command construction in ONE place)
def pick(*items) -> RobotCommand:
    return RobotCommand(PICK, tuple(tuple(i) for i in items))


def place(*items) -> RobotCommand:
    return RobotCommand(PLACE, tuple(tuple(i) for i in items))


def load(*items) -> RobotCommand:
    return RobotCommand(LOAD, tuple(tuple(i) for i in items))


def unload(*items) -> RobotCommand:
    return RobotCommand(UNLOAD, tuple(tuple(i) for i in items))


def change() -> RobotCommand:
    return RobotCommand(CHANGE)


def status() -> RobotCommand:
    return RobotCommand(STATUS)


def reset() -> RobotCommand:
    return RobotCommand(RESET)


# ────────────────────────────────────────────
# Replies
# ────────────────────────────────────────────
ACK = "ack"
DONE = "done"
ERR = "err"
STAT = "stat"
OTHER = "other"     # unparseable / unrelated line (ignored by the gateway)


@dataclass(frozen=True)
class Reply:
    kind: str
    seq: Optional[int] = None   # None for legacy replies (no sequence number)
    name: str = ""              # command name the reply refers to
    index: int = 0              # ERR: index of the failing batch item
    code: str = ""              # ERR: error code, STAT: robot state
    raw: str = ""


# Robot states carried by STAT replies
ROBOT_IDLE = "IDLE"
ROBOT_BUSY = "BUSY"
ROBOT_ALARM = "ALARM"
ROBOT_ESTOP = "ESTOP"
