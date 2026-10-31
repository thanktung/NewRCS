"""Sản phẩm (DUT) của luồng tray: mỗi cái đang ở đâu, đã test bao nhiêu lần ở những box nào, và việc tiếp theo phải làm với nó.

Ô của tray INPUT chỉ có ba trạng thái:  FRESH (sản phẩm chưa test), EMPTY (trống), PASS (sản phẩm đã test, đạt).
Ô của tray NG trống hoặc chứa một sản phẩm NG (lấp theo thứ tự đọc: `ng_used` ô đã đầy).
Tray OUTPUT (tùy chọn, settings.json -> trays -> output1 / output2) CHỈ nhận hàng đạt: output 1 được lấp trước (theo thứ tự đọc),
đầy thì sang output 2; `out_used[k]` ô của tray output k đã đầy. Không có tray output thì hàng đạt về lại ô
trống đầu tiên của tray Input (ô đó chuyển sang PASS).

Vòng đời một DUT
    ô FRESH --take_from_tray--> ô EMPTY, sản phẩm trên tay k --place_in_box--> trong box n (đang test)
         --result()--> PASS  : nằm trong box tới khi được lấy ra, rồi đặt vào ô TRỐNG ĐẦU TIÊN của tray Input (ô thành PASS)
                       RETEST: được lấy ra, rồi test lại ở MỘT BOX KHÁC (không bao giờ là box đã test nó)
                       NG    : (lần test cuối được phép bị hỏng, hoặc không còn box nào khác) được lấy ra, rồi vào ô kế tiếp của tray NG
Số lần test đếm theo từng DUT: tối đa `max_attempts` lần (settings.json -> flow.max_attempts), mỗi lần ở một box khác.

`need` cho planner biết DUT đang chờ gì:
    TEST     sản phẩm mới, đặt vào box trống bất kỳ
    RETEST   đã hỏng một lần test, đặt vào box nó chưa được test
    TESTING  đang ở trong box, đang test
    RETURN   đã đạt: về lại tray (ô của tray Input / tray output)
    NG       hỏng hẳn: vào tray NG
    DONE     đã về tray (đạt) / đã ở tray NG (hỏng)
Module này chỉ giữ sổ sách: nó không di chuyển gì và không quyết định cái nào đi đâu (đó là việc của planner.py).
"""
from collections import deque

# ---- DUT đang chờ gì ------------------------------------------------------------------------------------------- #
TEST, RETEST, TESTING, RETURN, NG, DONE = "TEST", "RETEST", "TESTING", "RETURN", "NG", "DONE"
FRESH, EMPTY, PASS = "fresh", "empty", "pass"          # ba trạng thái của một ô tray Input
FAIL_LABELS = ("NG", "RETEST", "WARNING")          # kết quả tính là test hỏng (FQC tính là đạt)
HEAD, BOX, TRAY, NG_TRAY, OUT_TRAY = "head", "box", "tray", "ng", "out"


class DutError(Exception):
    """Một bước ghi sổ không thể xảy ra (lỗi ở bên gọi, hoặc một bước robot không làm đúng như kế hoạch)."""


class Dut:
    def __init__(self, id, origin):
        self.id = id
        self.origin = origin                  # ô tray Input nơi nó được lấy ra (thứ tự đọc); nơi nó được đặt lại là chuyện khác
        self.sn = ""
        self.location = (TRAY, origin)        # (TRAY, ô) | (HEAD, k) | (BOX, n) | (NG_TRAY, ô) | (OUT_TRAY, (chỉ số tray output, ô))
        self.need = TEST
        self.attempts = []                    # [(box, nhãn, số giây)] mỗi lần test xong một mục
        self.testing_in = None                # box của lần test đang chạy / vừa xong
        self.final = ""                       # "" khi chưa quyết định, sau đó "PASS" hoặc "NG"
        self.ng_cell = None

    @property
    def tests_made(self):
        return len(self.attempts)

    @property
    def tested_boxes(self):
        return {a[0] for a in self.attempts} | ({self.testing_in} if self.testing_in is not None else set())

    @property
    def head(self):
        return self.location[1] if self.location[0] == HEAD else None

    @property
    def box(self):
        return self.location[1] if self.location[0] == BOX else None

    def can_test_in(self, box):
        """DUT này có được đặt vào `box` để test (lại) không? (DUT đang chờ test và chưa được test ở box đó)"""
        return self.need in (TEST, RETEST) and box not in self.tested_boxes

    def __repr__(self):
        return "Dut(%d cell=%d %s %s tests=%d)" % (self.id, self.origin, self.location, self.need, self.tests_made)


class DutBook:
    """Mọi DUT của tray Input và vị trí của chúng. `capacity` = số ô của tray Input."""

    def __init__(self, capacity, max_attempts=3, ng_capacity=0, out_capacity=()):
        if max_attempts < 1:
            raise DutError("max_attempts must be >= 1")
        self.capacity = capacity
        self.max_attempts = max_attempts
        self.ng_capacity = ng_capacity
        self.out_capacity = list(out_capacity)          # số ô của tray output 1, 2 ... (rỗng = không có tray output)
        self.out_used = [0] * len(self.out_capacity)    # số ô đã lấp của từng tray output
        self.cells = [FRESH] * capacity                 # trạng thái từng ô của tray Input (thứ tự đọc)
        self.duts = {}                                  # id -> Dut (tạo khi một sản phẩm được lấy khỏi ô của nó)
        self.ng_used = 0                                # số ô tray NG đã lấp
        self._next_id = 1

    # ---- truy vấn ------------------------------------------------------------------------------- #
    @property
    def fresh(self):
        """Các ô (thứ tự đọc) còn chứa sản phẩm chưa test."""
        return [i for i, c in enumerate(self.cells) if c == FRESH]

    def peek_fresh(self, n):
        """n ô đầu tiên (thứ tự đọc) còn chứa sản phẩm chưa test."""
        return self.fresh[:max(0, n)]

    @property
    def fresh_left(self):
        return self.cells.count(FRESH)

    def empty_cells(self, n=None):
        """Các ô trống của tray Input theo thứ tự đọc (ô đầu tiên là nơi hàng đạt kế tiếp được đặt vào)."""
        out = [i for i, c in enumerate(self.cells) if c == EMPTY]
        return out if n is None else out[:max(0, n)]

    @property
    def ng_free(self):
        return max(0, self.ng_capacity - self.ng_used)

    @property
    def has_outputs(self):
        return bool(self.out_capacity)

    @property
    def out_free(self):
        return sum(c - u for c, u in zip(self.out_capacity, self.out_used))

    @property
    def pass_free(self):
        """Chỗ cho hàng đạt: các ô trống của tray output, hoặc (không có tray output) các ô trống của tray Input."""
        return self.out_free if self.has_outputs else self.cells.count(EMPTY)

    def output_slots(self, n=None):
        """Các ô trống của tray output theo thứ tự sử dụng: [(chỉ số tray output, ô), ...] - tray 1 trước."""
        out = [(k, c) for k, (cap, used) in enumerate(zip(self.out_capacity, self.out_used)) for c in range(used, cap)]
        return out if n is None else out[:max(0, n)]

    def on_head(self, k):
        return next((d for d in self.duts.values() if d.location == (HEAD, k)), None)

    def in_box(self, n):
        return next((d for d in self.duts.values() if d.location == (BOX, n)), None)

    def active(self):
        """Các DUT chưa DONE (đang ở đâu đó giữa lúc được lấy và lúc được cất)."""
        return [d for d in self.duts.values() if d.need != DONE]

    def finished(self):
        return self.fresh_left == 0 and not self.active()

    def stats(self):
        done = [d for d in self.duts.values() if d.need == DONE]
        return {"cells": self.capacity, "fresh": self.fresh_left, "empty": self.cells.count(EMPTY), "in_flight": len(self.active()),
                "passed": sum(1 for d in done if d.final == "PASS"), "ng": sum(1 for d in done if d.final == "NG"),
                "out_used": list(self.out_used),
                "tests": sum(d.tests_made for d in self.duts.values()),
                "retests": sum(max(0, d.tests_made - 1) for d in self.duts.values())}

    # ---- sự kiện vật lý (gọi khi bước robot đã thực sự xong) ---------------------------------------- #
    def take_from_tray(self, cell, head):
        """Tay `head` đã hút sản phẩm ở ô Input `cell`."""
        if not 0 <= cell < self.capacity or self.cells[cell] != FRESH:
            raise DutError("input cell %r has no untested product (empty or already taken?)" % (cell,))
        self.cells[cell] = EMPTY
        d = Dut(self._next_id, cell)
        self._next_id += 1
        d.location = (HEAD, head)
        self.duts[d.id] = d
        return d

    def place_in_box(self, dut, box):
        """DUT đã được đặt vào box `box` và bắt đầu test."""
        if dut.location[0] != HEAD:
            raise DutError("%r is not on a head" % dut)
        if not dut.can_test_in(box):
            raise DutError("%r cannot be tested in box %d (needs %s, tested in %s)" % (dut, box, dut.need, sorted(dut.tested_boxes)))
        dut.location, dut.need, dut.testing_in = (BOX, box), TESTING, box
        return dut

    def result(self, dut, label, seconds, eligible_boxes):
        """Box đã test xong. `label` = PASS | NG | RETEST | WARNING | FQC; `eligible_boxes` = các box mà một lần test lại
        còn có thể tới (đang bật và đang kết nối). Trả về kết luận: "PASS", "RETEST" (test lại ở chỗ khác) hoặc "NG" (cuối cùng)."""
        if dut.need != TESTING or dut.location[0] != BOX:
            raise DutError("%r is not being tested" % dut)
        box = dut.testing_in
        dut.attempts.append((box, label, seconds))
        dut.testing_in = None
        if label not in FAIL_LABELS:
            dut.need, dut.final = RETURN, "PASS"
            return "PASS"
        others = [b for b in eligible_boxes if b not in dut.tested_boxes]
        if dut.tests_made < self.max_attempts and others:
            dut.need = RETEST
            return "RETEST"
        dut.need, dut.final = NG, "NG"
        return "NG"

    def take_from_box(self, dut, head):
        """DUT đã test được tay `head` lấy ra khỏi box."""
        if dut.location[0] != BOX or dut.need == TESTING:
            raise DutError("%r is not a tested DUT inside a box" % dut)
        dut.location = (HEAD, head)
        return dut

    def return_to_tray(self, dut, cell=None):
        """Một DUT đạt đã được đặt vào một ô trống của tray Input (ô trống đầu tiên, trừ khi `cell` chỉ rõ ô nào); trả về chỉ số ô."""
        if dut.need != RETURN or dut.location[0] != HEAD:
            raise DutError("%r is not a passed DUT on a head" % dut)
        if cell is None:
            empties = self.empty_cells(1)
            if not empties:
                raise DutError("the input tray has no empty cell")
            cell = empties[0]
        if not 0 <= cell < self.capacity or self.cells[cell] != EMPTY:
            raise DutError("input cell %r is not empty" % (cell,))
        self.cells[cell] = PASS
        dut.location, dut.need = (TRAY, cell), DONE
        return cell

    def put_in_output(self, dut, tray=None, cell=None):
        """Một DUT đạt đã được đặt vào ô trống kế tiếp của các tray output (tray 1 trước); trả về (chỉ số tray, ô).
        `tray` / `cell` cho biết robot thực sự đặt ở đâu: phải là ô trống kế tiếp của tray đó (ô được dùng theo thứ tự đọc)."""
        if dut.need != RETURN or dut.location[0] != HEAD:
            raise DutError("%r is not a passed DUT on a head" % dut)
        if not self.has_outputs:
            raise DutError("there are no output trays")
        slots = self.output_slots(1)
        if not slots:
            raise DutError("the output trays are full")
        if tray is None:
            tray, cell = slots[0]
        if (tray, cell) != slots[0]:                                  # output 1 trước; output 2 chỉ khi output 1 đã đầy
            raise DutError("output tray %r cell %r is not the next free cell %r" % (tray, cell, slots[0]))
        self.out_used[tray] += 1
        dut.location, dut.need = (OUT_TRAY, (tray, cell)), DONE
        return tray, cell

    def put_in_ng(self, dut):
        """Một DUT hỏng đã được đặt vào ô trống kế tiếp của tray NG; trả về chỉ số ô đó."""
        if dut.need != NG or dut.location[0] != HEAD:
            raise DutError("%r is not a failed DUT on a head" % dut)
        if self.ng_used >= self.ng_capacity:
            raise DutError("the NG tray is full")
        cell = self.ng_used
        self.ng_used += 1
        dut.location, dut.need, dut.ng_cell = (NG_TRAY, cell), DONE, cell
        return cell

    # ---- quy tắc: test lại mà không còn box nào thì là NG cuối cùng -------------------------------- #
    def settle_stuck(self, eligible_boxes):
        """Các DUT chờ test lại mà không còn box nào để tới (mọi box hợp lệ đều đã test nó) trở thành NG cuối cùng.
        Trả về các DUT đã đổi."""
        changed = []
        for d in self.duts.values():
            if d.need == RETEST and not [b for b in eligible_boxes if b not in d.tested_boxes]:
                d.need, d.final = NG, "NG"
                changed.append(d)
        return changed
