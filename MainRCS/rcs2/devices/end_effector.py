"""End Effector: dụng cụ duy nhất gắn trên mặt bích robot.

Robot có đúng MỘT End Effector. Trên nó có các tool nhỏ, mỗi tool đều tùy chọn:

    heads     N cụm hút (8 trên tool thật): van hút + xy lanh lên/xuống + cảm biến áp suất         (devices/heads.py)
    scanner   đầu đọc mã vạch (Keyence SR-710 / SR-X100) đọc mã DUT trước khi hút                 (devices/scanner.py)
    laser     cảm biến laser IL-1000 kiểm tra DUT đã đặt                                         (devices/laser.py)

settings.json -> "end_effector" khai báo chúng (xem config/settings.example.json):

    "end_effector": {
      "name": "End Effector",
      "heads":   {"enabled": true, "units": [ {"vacuum": "RDO[1]", "cylinder": "RDO[9]", "pressure": "RDI[1]"}, ... ]},
      "scanner": {"type": "tcp", "host": "192.168.1.50", "port": 9004, "length": 14, "retry": 2},
      "laser":   {"enabled": false, "ok": "RDI[20]"}
    }

Một bước sequence gọi một tool:  {"ee": "heads" | "scanner" | "laser", ...}  (xem rcs2/core/sequence.py).
"""
from .heads import HeadBank, HeadError
from .laser import Laser, LaserError
from .scanner import KeyenceScanner, ScanError

TOOLS = ("heads", "scanner", "laser")


class EndEffector:
    def __init__(self, heads=None, scanner=None, laser=None, name="End Effector"):
        self.name = name
        self.heads = heads              # giống HeadBank hoặc None
        self.scanner = scanner          # giống KeyenceScanner hoặc None
        self.laser = laser              # giống Laser hoặc None

    def tool(self, kind):
        """Đối tượng tool, hoặc None khi End Effector này không có tool đó."""
        if kind not in TOOLS:
            raise KeyError(kind)
        return getattr(self, kind)

    def capabilities(self):
        """{"heads": số tay hút (0 = không có), "scanner": bool, "laser": bool} - cho biết End Effector có tool nào."""
        return {"heads": self.heads.count if self.heads is not None else 0,
                "scanner": self.scanner is not None, "laser": self.laser is not None}

    def close(self):
        if self.scanner is not None:
            self.scanner.close()


def build_end_effector(settings, io, serial_factory=None):
    """settings['end_effector'] -> EndEffector (rỗng khi không khai báo gì).
    Ném HeadError / ScanError / LaserError khi một mục khai báo sai."""
    cfg = settings.get("end_effector") or {}
    heads = HeadBank.from_config(cfg["heads"], io) if cfg.get("heads") else None
    scanner = KeyenceScanner.from_config("scanner", cfg["scanner"], serial_factory) if cfg.get("scanner") else None
    laser = Laser.from_config(cfg["laser"], io) if cfg.get("laser") else None
    return EndEffector(heads, scanner, laser, cfg.get("name", "End Effector"))


__all__ = ["EndEffector", "build_end_effector", "TOOLS", "HeadError", "ScanError", "LaserError"]
