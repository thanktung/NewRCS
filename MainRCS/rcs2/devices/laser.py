"""Keyence IL-1000 laser displacement sensor on the End Effector (flatness / height / offset check of the DUT).

The result of the sensor is read as a judgement on the robot controller I/O (through the bridge, like the pressure
sensors of the heads). settings.json -> "end_effector" -> "laser":

    "laser": {
      "enabled": false, "model": "IL-1000",
      "ok": "RDI[20]",                       judgement GO (inside the tolerance)
      "high": "RDI[21]", "low": "RDI[22]",   optional: judgement HIGH / LOW (only used to explain a failure)
      "active": 1, "timeout_s": 1.0
    }

`active` = value of the inputs when the judgement is true. The shipped addresses are placeholders: set the real wiring
and `enabled: true`. Used by the sequence step  {"ee": "laser", "check": "ok", "timeout_s": 1.0}  (alarm 9204 when the
judgement is not GO) and by the Manual window (read the judgement).
Not done yet: reading the measured value itself (needs the IL-1000 communication unit); only the judgement is available.
"""
import logging
import threading
import time

from .heads import parse_io

log = logging.getLogger("rcs2.laser")


class LaserError(Exception):
    """The laser check failed (bad configuration, I/O error, judgement is not GO)."""


class Laser:
    def __init__(self, io, ok, high=None, low=None, enabled=True, active=1, timeout_s=1.0, model="IL-1000",
                 sleep=time.sleep):
        self.io, self.ok, self.high, self.low = io, ok, high, low
        self.enabled, self.active, self.timeout_s, self.model = enabled, int(active), float(timeout_s), model
        self.sleep = sleep
        self._lock = threading.Lock()

    @classmethod
    def from_config(cls, cfg, io):
        """cfg = settings["end_effector"]["laser"]. Raises LaserError for a bad entry."""
        try:
            return cls(io, parse_io(cfg["ok"]), parse_io(cfg["high"]) if cfg.get("high") else None,
                       parse_io(cfg["low"]) if cfg.get("low") else None, bool(cfg.get("enabled", True)),
                       cfg.get("active", 1), cfg.get("timeout_s", 1.0), cfg.get("model", "IL-1000"))
        except (KeyError, ValueError, TypeError) as ex:
            raise LaserError("End Effector, laser: cấu hình sai (%s: %s)" % (type(ex).__name__, ex))

    def _need_enabled(self):
        if not self.enabled:
            raise LaserError("laser %s của End Effector đang tắt (laser.enabled: false trong settings.json)" % self.model)

    def _read_one(self, ref):
        try:
            return int(self.io.io_read(ref[0], ref[1], 1)[0]) == self.active
        except Exception as ex:
            raise LaserError("End Effector: đọc %s[%d] thất bại (%s)" % (ref[0], ref[1], ex))

    def status(self):
        """{"ok": bool, "high": bool | None, "low": bool | None} (None = not wired)."""
        self._need_enabled()
        with self._lock:
            return {"ok": self._read_one(self.ok),
                    "high": None if self.high is None else self._read_one(self.high),
                    "low": None if self.low is None else self._read_one(self.low)}

    def check(self, timeout_s=None):
        """Wait until the judgement is GO. Raises LaserError (HIGH / LOW when wired) after `timeout_s`."""
        self._need_enabled()
        timeout_s = self.timeout_s if timeout_s is None else float(timeout_s)
        end = time.monotonic() + timeout_s
        while True:
            st = self.status()
            if st["ok"]:
                return st
            if time.monotonic() >= end:
                why = "HIGH" if st["high"] else "LOW" if st["low"] else "không đạt"
                raise LaserError("End Effector: laser %s %s sau %.1fs" % (self.model, why, timeout_s))
            self.sleep(0.03)
