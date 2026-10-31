"""The suction heads of the End Effector: per head one vacuum valve, one up/down cylinder and one pressure sensor.

The robot has exactly ONE End Effector (see rcs2/devices/end_effector.py). This module is its "heads" tool: N identical
head units (8 on the real tool). All of it is wired to the I/O of the FANUC controller, so it is driven through the bridge
(`io.read` / `io.write`, see rcs2/robot/client.py). Nothing is hard-coded: every head names its own I/O in
settings.json -> "end_effector" -> "heads":

    "heads": {
      "enabled": true,
      "units": [
        {"vacuum": "RDO[1]", "cylinder": "RDO[9]",  "pressure": "RDI[1]"},
        {"vacuum": "RDO[2]", "cylinder": "RDO[10]", "pressure": "RDI[2]"},
        ... one entry per head (8 for the real End Effector) ...
      ],
      "cylinder_s": 0.6, "vacuum_s": 0.3, "pressure_timeout_s": 1.0,
      "pressure_active": 1, "cylinder_down": 1
    }

Two kinds of cylinder valve:
  single output   "cylinder": "RDO[9]"                      one coil + spring return: the output level says down / up (`cylinder_down`)
  double coil     "coil_down": "RDO[9]", "coil_up": "RDO[17]"   a bistable 5/2 valve with two coils: energise ONE coil to move, the other one
                  is switched off first (both coils are never on together). `coil_active` (default 1) = level that energises a coil;
                  `coil_pulse_s` > 0 = energise only that long (a pulse) and then switch both off; 0 (default) = keep the coil energised.
Per head, optional extras: "cyl_down" and "cyl_up" = input of the cylinder end-position sensors (the two ends of the stroke). When both
exist the cylinder step waits for the sensor instead of a fixed time ("cylinder_timeout_s", default 2 s) and reports a cylinder that
does not arrive (alarm 9203). Use them: the fixed time `cylinder_s` is a guess, the sensor is the fact.

Meaning of the values (change them to match the wiring):
  vacuum output        1 = valve on (suction)          cylinder output  `cylinder_down` (default 1) = head down
  pressure input       `pressure_active` (default 1) = product held (vacuum reached)

Used by the sequence steps  {"ee": "heads", "vacuum": "on", "heads": "all"},  {"ee": "heads", "cylinder": "down"},
{"ee": "heads", "check": "hold"}  and by the Manual window. A failed step raises HeadError (alarm 9203).
"""
import logging
import re
import threading
import time

log = logging.getLogger("rcs2.heads")

BIT_KINDS = ("SDO", "SDI", "RDO", "RDI", "SO", "SI", "UO", "UI")
_REF = re.compile(r"^\s*([A-Za-z]+)\s*\[\s*(\d+)\s*\]\s*$")


class HeadError(Exception):
    """A head action failed (bad configuration, I/O error, head did not pick up / release, cylinder stuck)."""


def parse_io(text):
    """'RDO[12]' -> ('RDO', 12)."""
    m = _REF.match(str(text))
    if not m or m.group(1).upper() not in BIT_KINDS or int(m.group(2)) < 1:
        raise ValueError("địa chỉ IO %r không hợp lệ (ví dụ RDO[1], RDI[3]; loại: %s)" % (text, ", ".join(BIT_KINDS)))
    return m.group(1).upper(), int(m.group(2))


class Head:
    @property
    def has_cylinder(self):
        return self.cylinder is not None or self.coil_down is not None

    def __init__(self, n, cfg):
        self.n = n
        self.vacuum = parse_io(cfg["vacuum"])
        self.cylinder = parse_io(cfg["cylinder"]) if cfg.get("cylinder") else None
        self.coil_down = parse_io(cfg["coil_down"]) if cfg.get("coil_down") else None       # double coil valve: the "down" coil
        self.coil_up = parse_io(cfg["coil_up"]) if cfg.get("coil_up") else None             # ... and the "up" coil
        if (self.coil_down is None) != (self.coil_up is None):
            raise ValueError("đầu %d: van 2 coil cần khai báo cả coil_down và coil_up" % n)
        if self.coil_down is not None and self.cylinder is not None:
            raise ValueError("đầu %d: dùng 'cylinder' (một ngõ ra) HOẶC 'coil_down' + 'coil_up' (van 2 coil), không dùng cả hai" % n)
        self.pressure = parse_io(cfg["pressure"]) if cfg.get("pressure") else None
        self.cyl_down = parse_io(cfg["cyl_down"]) if cfg.get("cyl_down") else None
        self.cyl_up = parse_io(cfg["cyl_up"]) if cfg.get("cyl_up") else None


def _runs(refs):
    """[(kind, index), ...] -> [(kind, first_index, [refs...])]: contiguous indexes of one kind in one call."""
    out = []
    for ref in sorted(set(refs)):
        if out and out[-1][0] == ref[0] and out[-1][1] + len(out[-1][2]) == ref[1]:
            out[-1][2].append(ref)
        else:
            out.append((ref[0], ref[1], [ref]))
    return out


class HeadBank:
    """All suction heads of the End Effector (acts on every head, or on a chosen subset)."""

    def __init__(self, heads, io, enabled=True, cylinder_s=0.6, vacuum_s=0.3, pressure_timeout_s=1.0,
                 pressure_active=1, cylinder_down=1, cylinder_timeout_s=2.0, sleep=time.sleep, coil_active=1, coil_pulse_s=0.0):
        self.heads, self.io, self.enabled = heads, io, enabled
        self.cylinder_s, self.vacuum_s = float(cylinder_s), float(vacuum_s)
        self.pressure_timeout_s, self.cylinder_timeout_s = float(pressure_timeout_s), float(cylinder_timeout_s)
        self.pressure_active, self.cylinder_down = int(pressure_active), int(cylinder_down)
        self.coil_active, self.coil_pulse_s = int(coil_active), float(coil_pulse_s)         # double coil valves only
        self.sleep = sleep
        self._lock = threading.RLock()

    # ---- construction ------------------------------------------------------------------------ #
    @classmethod
    def from_config(cls, cfg, io):
        """cfg = settings["end_effector"]["heads"]. Raises HeadError for a bad entry."""
        try:
            heads = [Head(i, h) for i, h in enumerate(cfg["units"], 1)]
            if not heads:
                raise ValueError("chưa có đầu hút nào")
            return cls(heads, io, bool(cfg.get("enabled", True)), cfg.get("cylinder_s", 0.6),
                       cfg.get("vacuum_s", 0.3), cfg.get("pressure_timeout_s", 1.0), cfg.get("pressure_active", 1),
                       cfg.get("cylinder_down", 1), cfg.get("cylinder_timeout_s", 2.0),
                       coil_active=cfg.get("coil_active", 1), coil_pulse_s=cfg.get("coil_pulse_s", 0.0))
        except (KeyError, ValueError, TypeError) as ex:
            raise HeadError("End Effector, đầu hút: cấu hình sai (%s: %s)" % (type(ex).__name__, ex))

    @property
    def count(self):
        return len(self.heads)

    def select(self, heads=None):
        """'all' / None -> every head, or a list of head numbers (1-based)."""
        if heads in (None, "all"):
            return list(self.heads)
        if not isinstance(heads, (list, tuple)) or not heads or any(
                isinstance(h, bool) or not isinstance(h, int) or not 1 <= h <= self.count for h in heads):
            raise HeadError("End Effector: heads phải là \"all\" hoặc danh sách số từ 1 đến %d" % self.count)
        return [self.heads[h - 1] for h in sorted(set(heads))]

    def _need_enabled(self):
        if not self.enabled:
            raise HeadError("đầu hút của End Effector đang tắt (heads.enabled: false trong settings.json)")

    # ---- I/O through the bridge -------------------------------------------------------------------- #
    def _write(self, items):
        """items: [(ref, 0|1)]. One io.write per contiguous run; the outputs are read back and compared."""
        values = {}
        for ref, v in items:
            values[ref] = int(v)
        for kind, first, refs in _runs(values):
            wanted = [values[r] for r in refs]
            try:
                back = self.io.io_write(kind, first, wanted)
            except Exception as ex:
                raise HeadError("End Effector: ghi %s[%d] thất bại (%s)" % (kind, first, ex))
            if list(back) != wanted:
                raise HeadError("End Effector: ghi %s[%d..%d] = %s nhưng đọc lại %s"
                                % (kind, first, first + len(refs) - 1, wanted, list(back)))

    def _read(self, refs):
        """refs -> {ref: 0|1}."""
        out = {}
        for kind, first, group in _runs(refs):
            try:
                vals = self.io.io_read(kind, first, len(group))
            except Exception as ex:
                raise HeadError("End Effector: đọc %s[%d] thất bại (%s)" % (kind, first, ex))
            for ref, v in zip(group, vals):
                out[ref] = int(v)
        return out

    # ---- actions --------------------------------------------------------------------------------------- #
    def vacuum_set(self, on, heads=None):
        """Valve on/off for the selected heads. After switching on, waits `vacuum_s` for the vacuum to build."""
        self._need_enabled()
        with self._lock:
            sel = self.select(heads)
            self._write([(h.vacuum, 1 if on else 0) for h in sel])
            log.info("heads: vacuum %s heads %s", "ON" if on else "off", [h.n for h in sel])
            if on and self.vacuum_s > 0:
                self.sleep(self.vacuum_s)

    def cylinder_set(self, down, heads=None):
        """Heads down / up. Waits for the end-position sensors when every selected head has them, else `cylinder_s`."""
        self._need_enabled()
        with self._lock:
            sel = [h for h in self.select(heads) if h.has_cylinder]
            if not sel:
                raise HeadError("End Effector: các đầu được chọn không có xy lanh")
            level = self.cylinder_down if down else 1 - self.cylinder_down
            idle = 1 - self.coil_active
            switch_off, switch_on = [], []                                # double coil valves: the other coil first, never both on
            for h in sel:
                if h.coil_down is not None:
                    on, off = (h.coil_down, h.coil_up) if down else (h.coil_up, h.coil_down)
                    switch_off.append((off, idle))
                    switch_on.append((on, self.coil_active))
            if switch_off:
                self._write(switch_off)
            self._write([(h.cylinder, level) for h in sel if h.cylinder is not None] + switch_on)
            if switch_on and self.coil_pulse_s > 0:                       # a pulse is enough for a bistable valve
                self.sleep(self.coil_pulse_s)
                self._write([(ref, idle) for ref, _ in switch_on])
            log.info("heads: cylinder %s heads %s", "DOWN" if down else "up", [h.n for h in sel])
            sensors = {h.n: (h.cyl_down if down else h.cyl_up) for h in sel}
            if all(sensors.values()):
                self._wait_sensors(sensors, "xuống" if down else "lên")
            elif self.cylinder_s > 0:
                self.sleep(self.cylinder_s)

    def _wait_sensors(self, sensors, word):
        end = time.monotonic() + self.cylinder_timeout_s
        while True:
            state = self._read(list(sensors.values()))
            late = [n for n, ref in sensors.items() if state[ref] != 1]
            if not late:
                return
            if time.monotonic() >= end:
                raise HeadError("End Effector: xy lanh đầu %s không tới vị trí %s sau %.1fs"
                                % (", ".join(map(str, late)), word, self.cylinder_timeout_s))
            self.sleep(0.03)

    def pressure(self, heads=None):
        """{head number: True (holding) / False / None (no sensor)}."""
        self._need_enabled()
        with self._lock:
            sel = self.select(heads)
            state = self._read([h.pressure for h in sel if h.pressure is not None])
            return {h.n: (None if h.pressure is None else state[h.pressure] == self.pressure_active) for h in sel}

    def check(self, hold=True, heads=None, timeout_s=None):
        """Wait until every selected head (with a sensor) holds the product (hold=True) or has released it.
        Raises HeadError naming the heads that did not make it within `timeout_s`."""
        self._need_enabled()
        timeout_s = self.pressure_timeout_s if timeout_s is None else float(timeout_s)
        with self._lock:
            sel = [h for h in self.select(heads) if h.pressure is not None]
            if not sel:
                raise HeadError("End Effector: các đầu được chọn không có cảm biến áp suất")
            end = time.monotonic() + timeout_s
            while True:
                state = self._read([h.pressure for h in sel])
                bad = [h.n for h in sel if (state[h.pressure] == self.pressure_active) != bool(hold)]
                if not bad:
                    return
                if time.monotonic() >= end:
                    raise HeadError("End Effector: đầu %s %s (cảm biến áp suất) sau %.1fs"
                                    % (", ".join(map(str, bad)),
                                       "không hút được sản phẩm" if hold else "chưa nhả sản phẩm", timeout_s))
                self.sleep(0.03)

    def _is_down(self, h, state):
        """Is the head down? The end-position sensor tells it; without one the level of the output(s) does (None = no cylinder)."""
        if h.cyl_down is not None:
            return state[h.cyl_down] == 1
        if h.coil_down is not None:
            return state[h.coil_down] == self.coil_active
        return None if h.cylinder is None else state[h.cylinder] == self.cylinder_down

    def status(self):
        """Everything for the Manual window in one go: [{n, vacuum, cylinder, hold}] (None = no such I/O)."""
        self._need_enabled()
        with self._lock:
            refs = [r for h in self.heads for r in (h.vacuum, h.cylinder, h.coil_down, h.cyl_down, h.pressure) if r is not None]
            state = self._read(refs)
            rows = []
            for h in self.heads:
                rows.append({
                    "n": h.n,
                    "vacuum": None if h.vacuum is None else bool(state[h.vacuum]),
                    "cylinder_down": self._is_down(h, state),
                    "hold": None if h.pressure is None else state[h.pressure] == self.pressure_active})
            return rows
