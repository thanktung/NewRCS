"""errors.py - Exceptions raised by the TCP clients."""

from __future__ import annotations


class ClientError(Exception):
    """Base class of every client-side communication error."""


# ── Robot ──────────────────────────────────
class RobotError(ClientError):
    """Base class of robot errors. Any RobotError during a motion command
    leaves the physical state UNKNOWN -> scheduler must go to FAULT."""


class RobotConnectionError(RobotError):
    """Not connected / connection lost."""


class RobotTimeout(RobotError):
    """No ACK / DONE within the timeout. The robot MAY still be moving."""


class RobotProtocolError(RobotError):
    """Reply does not match the command (wrong name, malformed ...)."""


class RobotCommandError(RobotError):
    """Robot answered ERR. `index` = failing batch item, `code` = reason.
    Items before `index` were executed, items from `index` on were not."""

    def __init__(self, name: str, index: int, code: str) -> None:
        super().__init__(f"{name} item {index} failed: {code}")
        self.name = name
        self.index = index
        self.code = code


# ── Box ────────────────────────────────────
class BoxError(ClientError):
    """Base class of box errors."""


class BoxNotConnected(BoxError):
    pass


class BoxTimeout(BoxError):
    pass
