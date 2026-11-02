"""Luồng tray theo cách engine dùng: cài đặt, sổ sách, layout, planner và bộ dựng stage gộp trong một đối tượng.

Đây là cách NewRCS chạy (chế độ "classic" cũ, mỗi fixture một sequence, đã bị bỏ). settings.json -> "flow":

    "flow": {
      "max_attempts": 3,            số lần test mỗi sản phẩm, mỗi lần ở một box khác (sau đó vào tray NG)
      "keep_free_heads": 1,         số tay để trống để có thể lấy hàng đã test ra khỏi box
      "max_pick": 8, "max_sort": 8, số sản phẩm một lần tới tray được lấy / cất (giữ cho mỗi lần tới tray ngắn)
      "pick_ahead": 0,              số sản phẩm lấy thêm ngoài số box đang chờ
      "top_up_when_idle": true,     lấy hàng khi mọi box đều đang bận
      "fill_heads": true,           tới tray thì nạp đầy MỌI tay trống (trừ keep_free): ít chuyến đi lại giữa tray và box hơn
      "scan": true,                 đọc mã vạch từng sản phẩm trước khi hút (cần end_effector.scanner)
      "override": null,             tốc độ (%) của các lần di chuyển; null = bridge.default_override
      "check_timeout_s": 1.0,       thời gian cho cảm biến áp suất sau khi hút / nhả
      "laser_check": {"enabled": true, "places": ["box", "output"], "offsets": [[-15, 0, 0], [15, 0, 0]], "timeout_s": 1.0},
                                    sau khi ĐẶT XUỐNG một sản phẩm (vào box / tray) đầu laser IL-1000 được đưa qua 2 điểm đo
                                    (offsets tính bằng mm trong hệ tọa độ của chỗ đặt) và phải báo GO ở cả hai, nếu không thì sản phẩm bị nghiêng
      "stop_robot_on_drop": true,   một tay đánh rơi sản phẩm trên đường đi: dừng chạy VÀ dừng chương trình robot, alarm 9208
      "via_tray": "", "via_fixtures": ""   điểm dạy tùy chọn robot đi qua khi tới tray / tới các box
    }

Engine sở hữu một FlowController. Mỗi khi robot rảnh, engine gọi `plan()` lấy việc tiếp theo, chạy các stage do `build()` tạo, và
gọi `commit()` khi từng stage xong. Vị trí của mọi thứ nằm trong `book` (dut.DutBook), các pose lấy từ `layout` (geometry.Layout),
được dựng từ các điểm dạy lúc bắt đầu chạy, nên điểm vừa dạy cũng được dùng.
"""
from dataclasses import dataclass

from . import dut as D
from . import geometry as G
from .planner import FixtureView, Planner, PlannerConfig, World
from .states import IDLE, TESTING
from .tasks import BuildSettings, StageBuilder

LASER_PLACES = ("box", "input", "output", "ng")
# tay đang cầm gì, theo cách màn hình hiển thị: empty | fresh (chưa test) | pass | ng | retest (đã hỏng, sẽ test ở box khác)
HEAD_STATE = {D.TEST: "fresh", D.RETEST: "retest", D.RETURN: "pass", D.NG: "ng"}


class FlowError(Exception):
    """Cài đặt flow sai (báo lúc chương trình khởi động)."""


def _int(value, name, low, high):
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise FlowError("flow.%s must be a whole number %d..%d (got %r)" % (name, low, high, value))
    return value


@dataclass
class FlowSettings:
    max_attempts: int = 3
    keep_free: int = 1
    max_pick: int = 8
    max_sort: int = 8
    pick_ahead: int = 0
    top_up_when_idle: bool = True
    fill_heads: bool = True
    scan: bool = True
    override: object = None
    check_timeout_s: float = 1.0
    via_tray: str = ""
    via_fixtures: str = ""
    laser: bool = False                                  # kiểm tra bằng IL-1000 mọi sản phẩm được đặt xuống (cần end_effector.laser)
    laser_places: tuple = ("box", "input", "output")     # ở đâu: box | input (tray) | output (các tray) | ng (tray)
    laser_offsets: tuple = ((-15.0, 0.0, 0.0), (15.0, 0.0, 0.0))     # các điểm đo (x, y, z mm trong hệ tọa độ của chỗ đặt)
    laser_timeout_s: float = 1.0
    stop_robot_on_drop: bool = True

    @classmethod
    def from_config(cls, cfg, heads):
        f = cfg.get("flow") or {}
        if f.get("mode", "tray") != "tray":            # settings.json cũ có thể vẫn ghi tên chế độ đã bỏ
            raise FlowError("flow.mode %r is not supported any more: only the tray flow exists (delete flow.mode)" % (f.get("mode"),))
        if heads < 2:       # đổi hàng đã test lấy hàng mới cần một tay trống VÀ một tay đang cầm hàng
            raise FlowError("the tray flow needs at least 2 heads in end_effector.heads.units (found %d)" % heads)
        s, d = cls(), cls()                             # d: giá trị mặc định
        s.max_attempts = _int(f.get("max_attempts", d.max_attempts), "max_attempts", 1, 10)
        s.keep_free = min(_int(f.get("keep_free_heads", d.keep_free), "keep_free_heads", 0, 64), max(0, heads - 1))   # tối đa số tay - 1
        s.max_pick = min(_int(f.get("max_pick", d.max_pick), "max_pick", 1, 64), heads)
        s.max_sort = min(_int(f.get("max_sort", d.max_sort), "max_sort", 1, 64), heads)
        s.pick_ahead = min(_int(f.get("pick_ahead", d.pick_ahead), "pick_ahead", 0, 64), heads)
        s.top_up_when_idle = bool(f.get("top_up_when_idle", d.top_up_when_idle))
        s.fill_heads = bool(f.get("fill_heads", d.fill_heads))
        s.scan = bool(f.get("scan", d.scan))
        ov = f.get("override", d.override)
        if ov is not None and (isinstance(ov, bool) or not isinstance(ov, int) or ov < 1):
            raise FlowError("flow.override must be null or a positive whole number (got %r)" % (ov,))
        s.override = ov
        t = f.get("check_timeout_s", d.check_timeout_s)
        if isinstance(t, bool) or not isinstance(t, (int, float)) or not 0.1 <= t <= 30:
            raise FlowError("flow.check_timeout_s must be 0.1..30 seconds (got %r)" % (t,))
        s.check_timeout_s = float(t)
        s.via_tray, s.via_fixtures = str(f.get("via_tray", "") or ""), str(f.get("via_fixtures", "") or "")
        s.stop_robot_on_drop = bool(f.get("stop_robot_on_drop", d.stop_robot_on_drop))
        lc = f.get("laser_check") or {}
        s.laser = bool(lc.get("enabled", False))
        places = lc.get("places", list(d.laser_places))
        if not isinstance(places, (list, tuple)) or not places or any(p not in LASER_PLACES for p in places):
            raise FlowError("flow.laser_check.places must be a list of %s (got %r)" % (" / ".join(LASER_PLACES), places))
        s.laser_places = tuple(places)
        offsets = lc.get("offsets", [list(o) for o in d.laser_offsets])
        if (not isinstance(offsets, (list, tuple)) or not 1 <= len(offsets) <= 4 or any(
                not isinstance(o, (list, tuple)) or len(o) != 3 or any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in o)
                for o in offsets)):
            raise FlowError("flow.laser_check.offsets must be 1..4 measuring points [x, y, z] in mm (got %r)" % (offsets,))
        s.laser_offsets = tuple(tuple(float(v) for v in o) for o in offsets)
        lt = lc.get("timeout_s", d.laser_timeout_s)
        if isinstance(lt, bool) or not isinstance(lt, (int, float)) or not 0.1 <= lt <= 30:
            raise FlowError("flow.laser_check.timeout_s must be 0.1..30 seconds (got %r)" % (lt,))
        s.laser_timeout_s = float(lt)
        return s


class FlowController:
    def __init__(self, settings: FlowSettings, trays, fixtures, heads, has_scanner, default_override=None, engine_cfg=None):
        """`trays` = {"input": {"rows", "cols"}, "ng": {...}}; `fixtures` = số các fixture; `heads` = số tay hút."""
        if "input" not in (trays or {}) or "ng" not in (trays or {}):
            raise FlowError("the tray flow needs both trays in settings.json -> trays (input and ng)")
        self.s = settings
        self.trays, self.fixture_numbers, self.heads, self.scanner = trays, sorted(fixtures), heads, has_scanner and settings.scan
        self.laser = settings.laser                      # engine đã kiểm tra End Effector có laser đang bật
        self.default_override = default_override
        self.engine_cfg = engine_cfg or {}
        self.planner = Planner(PlannerConfig(keep_free=settings.keep_free, max_pick=settings.max_pick, max_sort=settings.max_sort,
                                             pick_ahead=settings.pick_ahead, top_up_when_idle=settings.top_up_when_idle,
                                             fill_heads=settings.fill_heads))
        self.book = self._new_book()
        self.layout = None
        self.sn_by_cell = {}
        self.settled = []                                # các DUT vừa thành NG cuối cùng do lần `result` gần nhất

    def _new_book(self):
        t = self.trays
        outs = [t[n]["rows"] * t[n]["cols"] for n in G.Layout.output_names(t)]
        return D.DutBook(t["input"]["rows"] * t["input"]["cols"], self.s.max_attempts, t["ng"]["rows"] * t["ng"]["cols"], outs)

    # ---- layout / sổ sách ---------------------------------------------------------------------------- #
    def missing_points(self, points):
        return G.Layout.missing(points, self.trays, self.fixture_numbers, self.heads, self.scanner, self.laser)

    def prepare(self, points):
        """Dựng layout từ các điểm dạy (ném geometry.GeometryError liệt kê điểm thiếu / không khớp)."""
        self.layout = G.Layout(points, self.trays, self.fixture_numbers, self.heads, self.scanner, self.laser)

    def reset(self, what="all"):
        """Sổ sách mới. what = "input": người vận hành đặt tray Input mới (các tray khác giữ số đếm); "ng": tray NG đã được dọn;
        "output1" / "output2": tray output đó đã được dọn; "all": mọi thứ đã được dọn bằng tay (tray Input đầy, các tray khác
        trống, tay hút và box trống)."""
        if what == "ng":
            self.book.ng_used = 0
            return
        if what in ("output1", "output2"):
            k = int(what[-1]) - 1
            if k < len(self.book.out_used):
                self.book.out_used[k] = 0
            return
        ng_used, out_used = self.book.ng_used, list(self.book.out_used)
        self.book = self._new_book()
        if what == "input":
            self.book.ng_used, self.book.out_used = ng_used, out_used
        self.sn_by_cell = {}

    def in_flight(self):
        """Các sản phẩm đang ở trên tay hút hoặc trong box (nạp lại tray Input lúc này sẽ làm mất dấu chúng)."""
        return [d for d in self.book.active()]

    # ---- lập kế hoạch -------------------------------------------------------------------------------- #
    def world(self, now, fixtures):
        views = [FixtureView(f.number, f.enabled, f.connected, f.ats_ready, f.dut, f.finished, f.idle_since)
                 for f in fixtures.values()]
        heads = {k: self.book.on_head(k) for k in range(1, self.heads + 1)}
        return World(now, heads, views, self.book)

    def plan(self, world):
        return self.planner.next_task(world)

    @property
    def reason(self):
        return self.planner.reason

    def build(self, task):
        s = self.s
        ov = s.override if s.override is not None else self.default_override
        e = self.engine_cfg
        bs = BuildSettings(override=ov, check_timeout_s=s.check_timeout_s, scan=s.scan,
                           send_dut_out=bool(e.get("send_dut_out", False)), auto_start_test=bool(e.get("auto_start_test", True)),
                           via_tray=s.via_tray, via_fixtures=s.via_fixtures, laser=self.laser, laser_places=s.laser_places,
                           laser_offsets=s.laser_offsets, laser_timeout_s=s.laser_timeout_s)
        return StageBuilder(self.layout, self.book, bs).build(task)

    # ---- sổ sách đi theo robot ------------------------------------------------------------------------ #
    def commit(self, c, fixtures, now):
        """Ghi nhận việc một stage vừa làm xong. `fixtures` = các đối tượng Fixture của engine. Trả về một câu ngắn cho log."""
        op, book = c["op"], self.book
        if op == "sn":
            self.sn_by_cell[int(c["tag"].split(":")[1])] = c["sn"]
            return "cell %s: barcode %s" % (c["tag"].split(":")[1], c["sn"])
        if op == "take_tray":
            d = book.take_from_tray(c["cell"], c["head"])
            d.sn = self.sn_by_cell.pop(c["cell"], "")
            return "product %d (cell %d%s) is on head %d" % (d.id, c["cell"], ", SN " + d.sn if d.sn else "", c["head"])
        if op == "take_box":
            f = fixtures[c["fixture"]]
            d = f.dut
            book.take_from_box(d, c["head"])
            f.dut, f.finished, f.dut_inside, f.state, f.sn, f.message = None, False, False, IDLE, "", ""
            return "product %d taken out of box %d by head %d" % (d.id, f.number, c["head"])
        if op == "place_box":
            f = fixtures[c["fixture"]]
            d = book.on_head(c["head"])
            book.place_in_box(d, f.number)
            f.dut, f.finished, f.dut_inside, f.state, f.test_started, f.sn, f.message = d, False, True, TESTING, now, d.sn, ""
            return "product %d put into box %d (test %d/%d)" % (d.id, f.number, d.tests_made + 1, book.max_attempts)
        if op == "return_tray":
            d = book.on_head(c["head"])
            cell = book.return_to_tray(d, c.get("cell"))
            return "product %d (picked from cell %d) is in empty cell %d" % (d.id, d.origin + 1, cell + 1)
        if op == "put_out":
            d = book.on_head(c["head"])
            tray, cell = book.put_in_output(d, c["tray"], c["cell"])
            return "product %d (picked from cell %d) is in output tray %d cell %d" % (d.id, d.origin + 1, tray + 1, cell + 1)
        if op == "put_ng":
            d = book.on_head(c["head"])
            cell = book.put_in_ng(d)
            return "product %d is in NG cell %d" % (d.id, cell)
        raise D.DutError("unknown commit %r" % (c,))

    def result(self, f, label, elapsed, fixtures, now):
        """Box `f` vừa test xong. Trả về (verdict, text) - verdict: "PASS", "RETEST" (test lại ở box khác) hoặc "NG" (kết luận cuối)."""
        d = f.dut
        eligible = [x.number for x in fixtures.values() if x.enabled and x.connected and x.ats_ready]
        verdict = self.book.result(d, label, elapsed, eligible)
        f.finished, f.idle_since = True, now
        self.settled = self.book.settle_stuck(eligible)
        text = "product %d (picked from cell %d): test %d/%d in box %d = %s -> %s" % (
            d.id, d.origin + 1, d.tests_made, self.book.max_attempts, f.number, label,
            {"PASS": "passed, goes into the output tray" if self.book.has_outputs else "passed, goes into the first empty cell of the input tray",
             "RETEST": "retest in another box",
             "NG": "failed for good, goes to the NG tray"}[verdict])
        return verdict, text

    def snapshot(self):
        b = self.book
        heads = []
        for k in range(1, self.heads + 1):
            d = b.on_head(k)
            heads.append({"head": k, "state": HEAD_STATE.get(d.need, "fresh") if d else "empty", "dut": d.id if d else None,
                          "cell": d.origin if d else None, "sn": d.sn if d else "", "tests": d.tests_made if d else 0})
        # tray Input: mỗi ô "fresh" (chưa test) | "empty" | "pass";  tray NG: `ng_used` ô đầu tiên chứa sản phẩm NG
        return {"mode": "tray", "heads": heads, "input_cells": list(b.cells), "ng_used": b.ng_used, "out_used": list(b.out_used),
                "out_capacity": list(b.out_capacity), "stats": b.stats(),
                "reason": self.planner.reason, "max_attempts": b.max_attempts}
