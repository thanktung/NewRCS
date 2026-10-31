"""Các tay hút của End Effector: mỗi tay có một van hút, một xy lanh lên/xuống và một cảm biến áp suất.

Robot có đúng MỘT End Effector (xem rcs2/devices/end_effector.py). Module này là tool "heads" của nó: N cụm tay
giống nhau (8 trên tool thật). Tất cả nối vào I/O của controller FANUC, nên được điều khiển qua bridge
(`io.read` / `io.write`, xem rcs2/robot/client.py). Không có gì cố định trong code: mỗi tay tự khai báo I/O của nó trong
settings.json -> "end_effector" -> "heads":

    "heads": {
      "enabled": true,
      "units": [
        {"vacuum": "RDO[1]", "cylinder": "RDO[9]",  "pressure": "RDI[1]"},
        {"vacuum": "RDO[2]", "cylinder": "RDO[10]", "pressure": "RDI[2]"},
        ... mỗi tay một mục (8 với End Effector thật) ...
      ],
      "cylinder_s": 0.6, "vacuum_s": 0.3, "pressure_timeout_s": 1.0,
      "pressure_active": 1, "cylinder_down": 1
    }

Hai loại van xy lanh:
  một ngõ ra       "cylinder": "RDO[9]"                      một coil + lò xo hồi: mức ngõ ra cho biết xuống / lên (`cylinder_down`)
  hai coil         "coil_down": "RDO[9]", "coil_up": "RDO[17]"   van 5/2 giữ vị trí có hai coil: cấp điện MỘT coil để chạy, coil kia
                  được tắt trước (không bao giờ bật cả hai cùng lúc). `coil_active` (mặc định 1) = mức cấp điện cho coil;
                  `coil_pulse_s` > 0 = chỉ cấp điện trong khoảng đó (một xung) rồi tắt cả hai; 0 (mặc định) = giữ coil có điện.
Mỗi tay có thể thêm: "cyl_down" và "cyl_up" = ngõ vào cảm biến cuối hành trình của xy lanh (hai đầu hành trình). Khi có cả hai,
bước xy lanh chờ theo cảm biến thay vì chờ thời gian cố định ("cylinder_timeout_s", mặc định 2 s) và báo xy lanh nào
không tới nơi (alarm 9203). Nên dùng: thời gian cố định `cylinder_s` chỉ là ước đoán, cảm biến mới là thực tế.

Ý nghĩa các giá trị (sửa cho khớp với dây):
  ngõ ra vacuum        1 = van bật (hút)               ngõ ra cylinder  `cylinder_down` (mặc định 1) = tay đi xuống
  ngõ vào pressure     `pressure_active` (mặc định 1) = đã giữ được sản phẩm (đạt chân không)

Được dùng bởi các bước sequence  {"ee": "heads", "vacuum": "on", "heads": "all"},  {"ee": "heads", "cylinder": "down"},
{"ee": "heads", "check": "hold"}  và bởi cửa sổ Thủ công. Bước lỗi ném HeadError (alarm 9203).
"""
import logging
import re
import threading
import time

log = logging.getLogger("rcs2.heads")

BIT_KINDS = ("SDO", "SDI", "RDO", "RDI", "SO", "SI", "UO", "UI")
_REF = re.compile(r"^\s*([A-Za-z]+)\s*\[\s*(\d+)\s*\]\s*$")


class HeadError(Exception):
    """Thao tác tay hút bị lỗi (cấu hình sai, lỗi I/O, tay không hút / nhả được, xy lanh bị kẹt)."""


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
        self.coil_down = parse_io(cfg["coil_down"]) if cfg.get("coil_down") else None       # van hai coil: coil "xuống"
        self.coil_up = parse_io(cfg["coil_up"]) if cfg.get("coil_up") else None             # ... và coil "lên"
        if (self.coil_down is None) != (self.coil_up is None):
            raise ValueError("đầu %d: van 2 coil cần khai báo cả coil_down và coil_up" % n)
        if self.coil_down is not None and self.cylinder is not None:
            raise ValueError("đầu %d: dùng 'cylinder' (một ngõ ra) HOẶC 'coil_down' + 'coil_up' (van 2 coil), không dùng cả hai" % n)
        self.pressure = parse_io(cfg["pressure"]) if cfg.get("pressure") else None
        self.cyl_down = parse_io(cfg["cyl_down"]) if cfg.get("cyl_down") else None
        self.cyl_up = parse_io(cfg["cyl_up"]) if cfg.get("cyl_up") else None


def _runs(refs):
    """[(kind, index), ...] -> [(kind, first_index, [refs...])]: các chỉ số liên tiếp cùng loại trong một lần gọi."""
    out = []
    for ref in sorted(set(refs)):
        if out and out[-1][0] == ref[0] and out[-1][1] + len(out[-1][2]) == ref[1]:
            out[-1][2].append(ref)
        else:
            out.append((ref[0], ref[1], [ref]))
    return out


class HeadBank:
    """Tất cả tay hút của End Effector (thao tác trên mọi tay, hoặc trên một nhóm được chọn)."""

    def __init__(self, heads, io, enabled=True, cylinder_s=0.6, vacuum_s=0.3, pressure_timeout_s=1.0,
                 pressure_active=1, cylinder_down=1, cylinder_timeout_s=2.0, sleep=time.sleep, coil_active=1, coil_pulse_s=0.0):
        self.heads, self.io, self.enabled = heads, io, enabled
        self.cylinder_s, self.vacuum_s = float(cylinder_s), float(vacuum_s)
        self.pressure_timeout_s, self.cylinder_timeout_s = float(pressure_timeout_s), float(cylinder_timeout_s)
        self.pressure_active, self.cylinder_down = int(pressure_active), int(cylinder_down)
        self.coil_active, self.coil_pulse_s = int(coil_active), float(coil_pulse_s)         # chỉ dành cho van hai coil
        self.sleep = sleep
        self._lock = threading.RLock()

    # ---- dựng từ cấu hình ------------------------------------------------------------------- #
    @classmethod
    def from_config(cls, cfg, io):
        """cfg = settings["end_effector"]["heads"]. Ném HeadError khi một mục khai báo sai."""
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
        """'all' / None -> mọi tay, hoặc danh sách số thứ tự tay (bắt đầu từ 1)."""
        if heads in (None, "all"):
            return list(self.heads)
        if not isinstance(heads, (list, tuple)) or not heads or any(
                isinstance(h, bool) or not isinstance(h, int) or not 1 <= h <= self.count for h in heads):
            raise HeadError("End Effector: heads phải là \"all\" hoặc danh sách số từ 1 đến %d" % self.count)
        return [self.heads[h - 1] for h in sorted(set(heads))]

    def _need_enabled(self):
        if not self.enabled:
            raise HeadError("đầu hút của End Effector đang tắt (heads.enabled: false trong settings.json)")

    # ---- I/O qua bridge --------------------------------------------------------------------------------- #
    def _write(self, items):
        """items: [(ref, 0|1)]. Mỗi dãy liên tiếp một lần io.write; ngõ ra được đọc lại và so sánh."""
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

    # ---- thao tác -------------------------------------------------------------------------------------- #
    def vacuum_set(self, on, heads=None):
        """Bật / tắt van của các tay được chọn. Sau khi bật, chờ `vacuum_s` cho chân không tạo thành."""
        self._need_enabled()
        with self._lock:
            sel = self.select(heads)
            self._write([(h.vacuum, 1 if on else 0) for h in sel])
            log.info("heads: vacuum %s heads %s", "ON" if on else "off", [h.n for h in sel])
            if on and self.vacuum_s > 0:
                self.sleep(self.vacuum_s)

    def cylinder_set(self, down, heads=None):
        """Hạ / nâng tay. Chờ cảm biến cuối hành trình khi mọi tay được chọn đều có, nếu không thì chờ `cylinder_s`."""
        self._need_enabled()
        with self._lock:
            sel = [h for h in self.select(heads) if h.has_cylinder]
            if not sel:
                raise HeadError("End Effector: các đầu được chọn không có xy lanh")
            level = self.cylinder_down if down else 1 - self.cylinder_down
            idle = 1 - self.coil_active
            switch_off, switch_on = [], []                                # van hai coil: tắt coil kia trước, không bao giờ bật cả hai
            for h in sel:
                if h.coil_down is not None:
                    on, off = (h.coil_down, h.coil_up) if down else (h.coil_up, h.coil_down)
                    switch_off.append((off, idle))
                    switch_on.append((on, self.coil_active))
            if switch_off:
                self._write(switch_off)
            self._write([(h.cylinder, level) for h in sel if h.cylinder is not None] + switch_on)
            if switch_on and self.coil_pulse_s > 0:                       # với van giữ vị trí chỉ cần một xung
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
        """{số tay: True (đang giữ) / False / None (không có cảm biến)}."""
        self._need_enabled()
        with self._lock:
            sel = self.select(heads)
            state = self._read([h.pressure for h in sel if h.pressure is not None])
            return {h.n: (None if h.pressure is None else state[h.pressure] == self.pressure_active) for h in sel}

    def check(self, hold=True, heads=None, timeout_s=None):
        """Chờ tới khi mọi tay được chọn (có cảm biến) giữ được sản phẩm (hold=True) hoặc đã nhả ra.
        Ném HeadError ghi rõ tay nào chưa làm được trong `timeout_s`."""
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
        """Tay có đang ở dưới không? Cảm biến cuối hành trình cho biết; không có cảm biến thì dựa vào mức ngõ ra (None = không có xy lanh)."""
        if h.cyl_down is not None:
            return state[h.cyl_down] == 1
        if h.coil_down is not None:
            return state[h.coil_down] == self.coil_active
        return None if h.cylinder is None else state[h.cylinder] == self.cylinder_down

    def status(self):
        """Mọi thông tin cho cửa sổ Thủ công trong một lần: [{n, vacuum, cylinder, hold}] (None = không có I/O đó)."""
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
