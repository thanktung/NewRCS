"""
robot_v2.py - Robot protocol v2 (sequence numbers, ACK, DONE, ERR, batch).

PC -> Robot (one line, terminated by "\\n"):
    #<seq> <NAME>[:<item>[|<item>...]];
    #12 PICK:1,5,2;
    #13 PICK:1,5,0|1,6,1|1,7,2;       (batch, items separated by '|')
    #14 CHANGE;     #15 STATUS;     #16 RESET;

Robot -> PC:
    ACK:<seq>                         command accepted (fast, < ack_timeout)
    DONE:<seq>:<NAME>                 ALL items finished OK
    ERR:<seq>:<NAME>:<idx>:<CODE>     item <idx> failed; items before idx are
                                      done, items from idx on were NOT executed
    STAT:<seq>:<IDLE|BUSY|ALARM|ESTOP>   answer to STATUS

Full specification: docs/PROTOCOL_V2.md
"""

from __future__ import annotations

from . import commands as C
from .commands import Reply, RobotCommand

NAME = "v2"
SUPPORTS_BATCH = True
SUPPORTS_ACK = True
SUPPORTS_SEQ = True
TERMINATOR = "\n"


def encode(cmd: RobotCommand, seq: int) -> str:
    """Build the wire text of a command (without terminator)."""
    body = "|".join(",".join(str(v) for v in it) for it in cmd.items)
    return f"#{seq} {cmd.name}:{body};" if body else f"#{seq} {cmd.name};"


def _bad(line: str) -> Reply:
    return Reply(C.OTHER, raw=line)


def parse(line: str) -> Reply:
    """Parse one reply line. Never raises; garbage becomes Reply(OTHER)."""
    line = line.strip()
    parts = line.split(":")
    try:
        head = parts[0].upper()
        if head == "ACK" and len(parts) == 2:
            return Reply(C.ACK, seq=int(parts[1]), raw=line)
        if head == "DONE" and len(parts) == 3:
            return Reply(C.DONE, seq=int(parts[1]), name=parts[2].upper(), raw=line)
        if head == "ERR" and len(parts) == 5:
            return Reply(C.ERR, seq=int(parts[1]), name=parts[2].upper(),
                         index=int(parts[3]), code=parts[4].upper(), raw=line)
        if head == "STAT" and len(parts) == 3:
            return Reply(C.STAT, seq=int(parts[1]), code=parts[2].upper(), raw=line)
    except ValueError:
        pass
    return _bad(line)
