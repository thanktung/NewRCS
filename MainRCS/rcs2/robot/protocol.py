"""Wire protocol constants, mirrored inside bridge32/bridge_simple.py.

They are intentionally duplicated (the bridge is deployed on its own 32-bit PC as a single file);
tests/test_bridge_simple.py fails if they ever drift apart.
"""
import json

PROTOCOL_VERSION = 1
DEFAULT_PORT = 5600
MAX_LINE_BYTES = 1 << 20

E_BAD_REQUEST = "BAD_REQUEST"
E_UNKNOWN_CMD = "UNKNOWN_CMD"
E_NOT_AUTH = "NOT_AUTH"
E_FORBIDDEN = "FORBIDDEN"
E_NOT_CONNECTED = "NOT_CONNECTED"
E_NOT_ARMED = "NOT_ARMED"
E_BUSY = "BUSY"
E_PENDING = "PENDING"
E_FAULT_LATCHED = "FAULT_LATCHED"
E_LIMIT = "LIMIT"
E_VERIFY = "VERIFY_FAILED"
E_ROBOT_ERROR = "ROBOT_ERROR"
E_TIMEOUT = "TIMEOUT"
E_PROGRAM_STOPPED = "PROGRAM_STOPPED"      # raised by NewRCS itself: UO[3] PROGRUN is off, no command may be written
E_INTERNAL = "INTERNAL"

MOTION_CODES = {
    "rmove": 1,
    "move": 2,
    "put": 3,
    "get": 4,
    "down": 5,
    "up": 6,
    "gosafehere": 7,
    "gosafetarge": 8,
}
NEEDS_TARGET = ("rmove", "move", "gosafetarge")
NEEDS_STATION = ("put", "get", "down", "up")


def encode(msg):
    return (json.dumps(msg, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def decode(line):
    if isinstance(line, bytes):
        line = line.decode("utf-8")
    obj = json.loads(line)
    if not isinstance(obj, dict):
        raise ValueError("message must be a JSON object")
    return obj
