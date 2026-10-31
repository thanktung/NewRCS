"""The End Effector: the single tool carried by the robot flange.

A robot has exactly ONE End Effector. It carries small tools, each optional:

    heads     N suction units (8 on the real tool): vacuum valve + up/down cylinder + pressure sensor   (devices/heads.py)
    scanner   barcode reader (Keyence SR-710 / SR-X100) that reads the DUT code before it is picked        (devices/scanner.py)
    laser     IL-1000 laser sensor that checks the picked DUT                                              (devices/laser.py)

settings.json -> "end_effector" declares them (see config/settings.example.json):

    "end_effector": {
      "name": "End Effector",
      "heads":   {"enabled": true, "units": [ {"vacuum": "RDO[1]", "cylinder": "RDO[9]", "pressure": "RDI[1]"}, ... ]},
      "scanner": {"type": "tcp", "host": "192.168.1.50", "port": 9004, "length": 14, "retry": 2},
      "laser":   {"enabled": false, "ok": "RDI[20]"}
    }

Sequences address a tool with one step:  {"ee": "heads" | "scanner" | "laser", ...}  (see rcs2/core/sequence.py).
"""
from .heads import HeadBank, HeadError
from .laser import Laser, LaserError
from .scanner import KeyenceScanner, ScanError

TOOLS = ("heads", "scanner", "laser")


class EndEffector:
    def __init__(self, heads=None, scanner=None, laser=None, name="End Effector"):
        self.name = name
        self.heads = heads              # HeadBank-like or None
        self.scanner = scanner          # KeyenceScanner-like or None
        self.laser = laser              # Laser-like or None

    def tool(self, kind):
        """The tool object, or None when this End Effector does not carry it."""
        if kind not in TOOLS:
            raise KeyError(kind)
        return getattr(self, kind)

    def capabilities(self):
        """{"heads": number of heads (0 = none), "scanner": bool, "laser": bool} - used to validate sequences."""
        return {"heads": self.heads.count if self.heads is not None else 0,
                "scanner": self.scanner is not None, "laser": self.laser is not None}

    def close(self):
        if self.scanner is not None:
            self.scanner.close()


def build_end_effector(settings, io, serial_factory=None):
    """settings['end_effector'] -> EndEffector (an empty one when nothing is declared).
    Raises HeadError / ScanError / LaserError for a bad entry."""
    cfg = settings.get("end_effector") or {}
    heads = HeadBank.from_config(cfg["heads"], io) if cfg.get("heads") else None
    scanner = KeyenceScanner.from_config("scanner", cfg["scanner"], serial_factory) if cfg.get("scanner") else None
    laser = Laser.from_config(cfg["laser"], io) if cfg.get("laser") else None
    return EndEffector(heads, scanner, laser, cfg.get("name", "End Effector"))


__all__ = ["EndEffector", "build_end_effector", "TOOLS", "HeadError", "ScanError", "LaserError"]
