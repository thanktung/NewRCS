"""Planner của luồng tray: quyết định robot (duy nhất) làm gì tiếp theo. Logic thuần: không I/O, không thread, không tự có đồng hồ.

Tình huống: H tay hút (8), N box test (10), một tray Input đầy sản phẩm chưa test, một tray NG. Robot làm MỘT việc
mỗi lúc, và một việc không bao giờ bị ngắt giữa chừng, nên planner được hỏi lại mỗi khi một việc xong (hoặc một box đổi trạng thái).

Mục tiêu: **không để box nào rảnh lâu.** Một box rảnh từ lúc test xong (hoặc lúc nó trống) tới khi robot đã
đặt sản phẩm mới vào. Các quy tắc, theo thứ tự:

 1. PHỤC VỤ box đã rảnh lâu nhất mà phục vụ được NGAY. Phục vụ một box = (lấy sản phẩm đã test ra
    bằng một tay trống, nếu có) + (đặt sản phẩm từ một tay khác vào). Sản phẩm được đặt vào, theo thứ tự ưu tiên: sản phẩm
    đã hỏng một lần test và phải test ở box KHÁC (không bao giờ hai lần cùng một box), rồi tới sản phẩm mới.
 2. Nếu không box nào phục vụ được vì không tay nào cầm sản phẩm phù hợp -> tới tray lấy hàng (bằng số box đang chờ,
    nhưng không bao giờ dùng tay trống cuối cùng: một tay phải để trống để lấy hàng đã test ra khỏi box, trừ khi mọi box đều trống).
 3. Nếu một box cần một tay trống mà mọi tay đều đầy -> tới tray cất hàng đã test trước.
 4. Nếu mọi box đều đang test (robot có thời gian): cất hàng đã test và nạp thêm hàng mới lên tay để
    box nào xong kế tiếp được phục vụ ngay.
 5. Một lần tới tray làm cả hai việc: cất hàng đã test trước, rồi lấy hàng mới vào các tay vừa trống.
 6. KHI NÀO cất hàng: chỉ khi mọi sản phẩm trên tay đều đã test (pass hoặc ng, không còn gì để đặt vào box), hoặc khi
    mọi box đều đang test. Trong lúc khác, hàng đã test cứ ở trên tay; ngoại lệ duy nhất là một box cần một tay trống
    mà không còn tay nào, và lúc hết việc (không còn hàng mới): khi đó chúng cũng được cất.
 7. NẠP ĐẦY TAY: mỗi lần robot ở tray, nó nạp đầy mọi tay trống bằng hàng mới (trừ tay `keep_free`) thay vì
    chỉ lấy đủ cho các box đang chờ - thêm một chuyến tới tray tốn hơn việc một tay cầm sản phẩm thêm một lúc.
    (`fill_heads` = False cho hành vi cũ: chỉ lấy đủ cho các box đang chờ.)
 8. Mỗi việc được giữ ngắn (`max_pick` / `max_sort`) để box nào xong trong lúc đó không phải chờ một chuyến dài.

Planner chỉ đọc thế giới (`World`) và trả về một việc; ghi kết quả vào sổ sách (dut.DutBook) là việc của bên gọi,
từng bước, đúng như robot thực sự làm.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from . import dut as D


# ---------------------------------------------------------------------------------------------------------------- #
# những gì planner nhìn vào
# ---------------------------------------------------------------------------------------------------------------- #
@dataclass
class FixtureView:
    number: int
    enabled: bool = True
    connected: bool = True
    ready: bool = True                 # ATS nhận được sản phẩm (nó đã báo "đang chờ DUT")
    dut: Optional[D.Dut] = None        # sản phẩm bên trong (đang test, hoặc đã test và chờ được lấy ra)
    finished: bool = False             # đã có kết quả của `dut`
    idle_since: float = 0.0            # box chờ robot từ lúc nào (lúc có kết quả, hoặc lúc nó trống)

    @property
    def available(self):
        return self.enabled and self.connected and self.ready

    @property
    def needs_service(self):
        return self.available and (self.dut is None or self.finished)

    @property
    def has_dut(self):
        return self.dut is not None

    @property
    def can_take_out(self):
        """Một sản phẩm đã test đang chờ trong một box không còn được dùng (đã tắt / mất kết nối): vẫn phải lấy nó ra."""
        return self.has_dut and self.finished and not self.available


@dataclass
class World:
    now: float
    heads: Dict[int, Optional[D.Dut]]          # số tay -> sản phẩm nó đang cầm (None = trống)
    fixtures: List[FixtureView]
    book: D.DutBook

    def eligible_boxes(self):
        """Số các box mà một lần test lại còn có thể tới."""
        return [f.number for f in self.fixtures if f.available]


@dataclass
class PlannerConfig:
    keep_free: int = 1                 # số tay để trống để lấy hàng đã test ra khỏi box (không cần khi mọi box đều trống)
    max_pick: int = 8                  # số sản phẩm lấy trong một lần tới tray
    max_sort: int = 8                  # số sản phẩm cất trong một lần tới tray
    pick_ahead: int = 0                # số hàng mới lấy thêm ngoài số box đang chờ (0 = chỉ lấy đủ)
    top_up_when_idle: bool = True      # nạp thêm hàng mới lên tay khi mọi box đều đang test
    fill_heads: bool = True            # một lần tới tray nạp đầy MỌI tay trống (giữ `keep_free`) thay vì chỉ lấy đủ cho
                                       # các box đang chờ: ít chuyến đi lại giữa tray và box hơn


# ---------------------------------------------------------------------------------------------------------------- #
# các loại việc
# ---------------------------------------------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ServiceTask:
    """Tại box `fixture`: lấy sản phẩm đã test ra bằng `take_head` (None = box đang trống) và đặt sản phẩm của `place_head` vào."""
    fixture: int
    place_head: int
    place_dut: int
    take_head: Optional[int] = None
    take_dut: Optional[int] = None
    reason: str = ""
    kind = "service"


@dataclass(frozen=True)
class TakeTask:
    """Tại box `fixture`: chỉ lấy sản phẩm đã test ra (không còn gì để đặt vào)."""
    fixture: int
    head: int
    dut: int
    reason: str = ""
    kind = "take"


@dataclass(frozen=True)
class TrayTask:
    """Một lần tới khu tray. `sorts` = ((tay, id dut), ...) cất trước: hàng đạt vào ô của nó trong tray
    Input, hàng hỏng vào ô kế tiếp của tray NG. `picks` = ((tay, ô Input), ...) lấy sau đó."""
    sorts: Tuple[Tuple[int, int], ...] = ()
    picks: Tuple[Tuple[int, int], ...] = ()
    reason: str = ""
    kind = "tray"


Task = object


# ---------------------------------------------------------------------------------------------------------------- #
class Planner:
    def __init__(self, cfg: Optional[PlannerConfig] = None):
        self.cfg = cfg or PlannerConfig()
        self.reason = ""                       # vì sao lần gọi cuối trả về kết quả đó (kể cả khi trả về None)

    # ---- hàm phụ ------------------------------------------------------------------------------------ #
    @staticmethod
    def _loaded(w):
        return [(k, d) for k, d in sorted(w.heads.items()) if d is not None]

    @staticmethod
    def _free(w):
        return [k for k, d in sorted(w.heads.items()) if d is None]

    def _reserve(self, w):
        """Các tay phải để trống: không tay nào khi mọi box đều trống, nếu không thì `keep_free`."""
        return self.cfg.keep_free if any(f.has_dut for f in w.fixtures) else 0

    @staticmethod
    def _dut_for(fixture, loaded):
        """Tay có sản phẩm nên đặt vào `fixture`: sản phẩm cần test lại trước, rồi tới sản phẩm mới (tay số nhỏ trước)."""
        usable = [(0 if d.need == D.RETEST else 1, k, d) for k, d in loaded if d.can_test_in(fixture.number)]
        if not usable:
            return None
        _, k, d = min(usable, key=lambda t: (t[0], t[1]))
        return k, d

    def _sortable(self, w):
        """Các tay có sản phẩm cất được ngay: hàng đạt khi còn chỗ cho chúng (tray output / ô Input trống) và
        hàng hỏng khi tray NG còn chỗ."""
        out, ng_room, pass_room = [], w.book.ng_free, w.book.pass_free
        for k, d in self._loaded(w):
            if d.need == D.RETURN and pass_room > 0:
                out.append((k, d))
                pass_room -= 1
            elif d.need == D.NG and ng_room > 0:
                out.append((k, d))
                ng_room -= 1
        return out[:self.cfg.max_sort]

    def _tray_visit(self, w, want_fresh, why, sort="auto"):
        """Một lần tới tray: cất hàng đã test, rồi lấy tối đa `want_fresh` hàng mới. None nếu chuyến đi vô ích.
        sort = "auto": chỉ cất khi mọi sản phẩm trên tay đều đã test (pass / ng); "always": cất mọi thứ cất được."""
        untested = any(d.need in (D.TEST, D.RETEST) for _, d in self._loaded(w))
        sorts = self._sortable(w) if (sort == "always" or not untested) else []
        free_after = sorted(set(self._free(w)) | {k for k, _ in sorts})
        room = len(free_after) - self._reserve(w)
        fill = self.cfg.fill_heads and (want_fresh > 0 or self.cfg.top_up_when_idle)    # (top_up tắt: chuyến đi không lấy gì thì vẫn không lấy gì)
        wanted = self.cfg.max_pick if fill else want_fresh                          # ở tray: nạp đầy tay, không quay lại lấy thêm
        n = max(0, min(room, wanted, self.cfg.max_pick, w.book.fresh_left))
        heads = free_after[:n]
        cells = w.book.peek_fresh(n)
        picks = tuple(zip(heads, cells))
        if not sorts and not picks:
            return None
        return TrayTask(sorts=tuple((k, d.id) for k, d in sorts), picks=picks, reason=why)

    # ---- quyết định --------------------------------------------------------------------------------- #
    def next_task(self, w: World):
        """Việc tiếp theo cho robot, hoặc None (lúc này không có việc gì hữu ích, hoặc đã hết việc). `self.reason` cho biết vì sao."""
        if w.book.finished():
            self.reason = "finished"
            return None
        loaded, free = self._loaded(w), self._free(w)
        needy = sorted((f for f in w.fixtures if f.needs_service), key=lambda f: (f.idle_since, f.number))

        # 1. phục vụ box đã chờ lâu nhất mà phục vụ được ngay
        for f in needy:
            if f.has_dut and not free:
                continue                                          # có hàng đã test bên trong mà không có tay trống để lấy ra
            choice = self._dut_for(f, loaded)
            if choice is None:
                continue
            place_head, placed = choice
            take_head = free[0] if f.has_dut else None
            self.reason = "service box %d (idle %.1fs)" % (f.number, w.now - f.idle_since)
            return ServiceTask(f.number, place_head, placed.id, take_head, f.dut.id if f.has_dut else None, self.reason)

        if free:                                                      # hàng đã test trong các box đã bị tắt
            for f in w.fixtures:
                if f.can_take_out:
                    self.reason = "take the tested product out of box %d (box not in use)" % f.number
                    return TakeTask(f.number, free[0], f.dut.id, self.reason)

        if needy:
            waiting_full = [f for f in needy if f.has_dut]
            # có box đang chờ nhưng không tay nào cầm hàng phù hợp: đi lấy hàng (nếu mọi tay đều đầy thì cất bớt trước)
            fresh_wanted = max(0, len(needy) - sum(1 for _, d in loaded if d.need in (D.TEST, D.RETEST))) + self.cfg.pick_ahead
            if w.book.fresh_left > 0 and fresh_wanted == 0 and not self._loaded_usable(needy, loaded):
                fresh_wanted = 1                                  # hàng trên các tay đều không phù hợp với các box đang chờ
            why = "fetch for %d waiting box(es)" % len(needy)
            visit = self._tray_visit(w, fresh_wanted, why) if fresh_wanted else None
            if fresh_wanted and w.book.fresh_left and (visit is None or not visit.picks) and self._sortable(w):
                forced = self._tray_visit(w, fresh_wanted, why, "always")        # không còn chỗ để lấy hàng: cất bớt hàng cho có chỗ
                if forced is not None and (forced.picks or visit is None):
                    visit = forced
            if visit is None and waiting_full and not free:
                visit = self._tray_visit(w, 0, "free a head for box %d" % waiting_full[0].number, "always")
            if visit is not None:
                self.reason = visit.reason
                return visit
            # không lấy được gì: hết hàng mới. Lấy hàng đã test ra để hàng cần test lại vào được các box đó
            if w.book.fresh_left == 0 and free:
                for f in needy:
                    if f.has_dut:
                        self.reason = "take the tested product out of box %d (nothing left to put in)" % f.number
                        return TakeTask(f.number, free[0], f.dut.id, self.reason)
            # không có gì để đặt vào các box đang chờ (hết hàng mới): đừng để việc đó chặn việc dọn dẹp
            visit = self._tray_visit(w, 0, "nothing to put in the waiting boxes: put the tested products away", "always")
            if visit is not None:
                self.reason = visit.reason
                return visit
            self.reason = "boxes wait but no suitable product / free head (waiting for results)"
            return None

        # 4. mọi box đều bận: tận dụng thời gian
        want = self.cfg.max_pick if self.cfg.top_up_when_idle else 0
        visit = self._tray_visit(w, want, "every box is testing: put away the tested products and top up the heads", "always")
        if visit is not None:
            self.reason = visit.reason
            return visit
        self.reason = "nothing to do" if not w.book.finished() else "finished"
        return None

    @staticmethod
    def _loaded_usable(needy, loaded):
        return any(d.can_test_in(f.number) for f in needy for _, d in loaded)
