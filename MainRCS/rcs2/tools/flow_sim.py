"""Bộ mô phỏng "nếu - thì" của luồng tray (planner + sổ sách, sự kiện rời rạc, không robot, không mạng).

    python -m rcs2.tools.flow_sim                                  10 box, 8 tay, 80 sản phẩm, test 120 s
    python -m rcs2.tools.flow_sim --boxes 6 --test-time 60 --pass-rate 0.8 --cells 48 --seed 3
    python -m rcs2.tools.flow_sim --keep-free 0 --max-pick 4       thử cài đặt planner khác

Nó trả lời câu hỏi "một box phải nằm chờ bao lâu?": mỗi khi robot rảnh thì hỏi planner (rcs2/core/planner.py) việc tiếp theo, việc đó
tốn thời gian theo các thông số thời gian robot bên dưới, các box test xong vào thời điểm ngẫu nhiên với tỷ lệ đạt đã cho, và sổ sách
(rcs2/core/dut.py) được cập nhật y như engine thật. Test cũng dùng chính module này để kiểm tra các bất biến.
"""
import argparse
import random
from dataclasses import dataclass, field

from ..core import dut as D
from ..core.planner import FixtureView, Planner, PlannerConfig, ServiceTask, TakeTask, TrayTask, World


@dataclass
class SimConfig:
    boxes: int = 10
    heads: int = 8
    cells: int = 80                     # số sản phẩm trong tray Input
    ng_cells: int = 40
    outputs: tuple = ()                 # số ô của tray output 1, 2 ... cho hàng đạt (rỗng = hàng đạt về lại tray Input)
    test_time: float = 120.0            # số giây một lần test
    jitter: float = 0.15                # +- tỷ lệ dao động ngẫu nhiên của thời gian test
    pass_rate: float = 0.9
    max_attempts: int = 3
    # thời gian của robot (giây)
    travel: float = 3.0                 # giữa khu tray và các box (một chiều, tính một lần mỗi chuyến)
    move: float = 1.2                   # robot di chuyển để đưa một tay tới trên mục tiêu
    pick: float = 1.0                   # hạ xy lanh, bật hút, kiểm tra, nâng xy lanh
    place: float = 1.0                  # hạ xy lanh, tắt hút, nâng xy lanh
    scan: float = 0.8                   # đọc một mã vạch
    ats: float = 0.2                    # gửi mã vạch + placeDUTOK
    laser: float = 2.5                  # kiểm tra laser sau khi đặt xuống: 2 lần di chuyển + 2 lần đọc (0 = tắt kiểm tra laser)
    seed: int = 1
    planner: PlannerConfig = field(default_factory=PlannerConfig)


class FlowSim:
    def __init__(self, cfg: SimConfig):
        self.cfg = cfg
        self.rng = random.Random(cfg.seed)
        self.book = D.DutBook(cfg.cells, cfg.max_attempts, cfg.ng_cells, cfg.outputs)
        self.heads = {k: None for k in range(1, cfg.heads + 1)}
        self.fixtures = [FixtureView(n) for n in range(1, cfg.boxes + 1)]
        self.fx = {f.number: f for f in self.fixtures}
        self.test_end = {}                      # box -> thời điểm test của nó kết thúc
        self.planner = Planner(cfg.planner)
        self._started = {}                       # box -> thời điểm test đang chạy của nó bắt đầu
        self.t = 0.0
        self.idle = {n: [] for n in self.fx}    # box -> số giây chờ trước mỗi sản phẩm được đặt vào
        self.busy_time = 0.0
        self.log = []                           # (thời điểm, mô tả) của mọi việc
        self.tasks = 0
        self.tray_visits = 0                    # số chuyến tới tray Input (mỗi chuyến là một quãng đường dài)

    # ---- hàm phụ ----------------------------------------------------------------------------------- #
    def world(self):
        return World(self.t, dict(self.heads), self.fixtures, self.book)

    def check(self):
        """Bất biến (ném AssertionError): mỗi sản phẩm ở đúng một chỗ, một box chứa tối đa một, số lần test <= max, các box khác nhau."""
        seen = {}
        for d in self.book.duts.values():
            assert d.tests_made <= self.cfg.max_attempts, d
            boxes = [a[0] for a in d.attempts]
            assert len(boxes) == len(set(boxes)), "a product was tested twice in the same box: %r %r" % (d, boxes)
            seen.setdefault(d.location, []).append(d)
        for loc, ds in seen.items():
            if loc[0] in (D.HEAD, D.BOX):
                assert len(ds) == 1, "two products at %r: %r" % (loc, ds)
        for k, d in self.heads.items():
            assert (d is None) == ((D.HEAD, k) not in seen), "head %d out of step with the books" % k
            assert d is None or d.location == (D.HEAD, k)
        for f in self.fixtures:
            assert (f.dut is None) == ((D.BOX, f.number) not in seen), "box %d out of step with the books" % f.number
        b = self.book
        assert len(b.cells) == self.cfg.cells
        assert b.cells.count(D.FRESH) + b.cells.count(D.EMPTY) + b.cells.count(D.PASS) == self.cfg.cells
        returned = [d for d in b.duts.values() if d.location[0] == D.TRAY]
        assert b.cells.count(D.PASS) == len(returned), "PASS cells and returned products differ"
        assert sorted(d.location[1] for d in returned) == [i for i, c in enumerate(b.cells) if c == D.PASS], "a product is not where the cell says"
        in_out = [d for d in b.duts.values() if d.location[0] == D.OUT_TRAY]
        assert sum(b.out_used) == len(in_out), "output tray counts and products differ"
        assert all(0 <= u <= c for u, c in zip(b.out_used, b.out_capacity)), "an output tray is over-filled"
        assert len({d.location[1] for d in in_out}) == len(in_out), "two products in the same output cell"
        picked = len(b.duts)
        assert b.cells.count(D.EMPTY) == picked - len(returned), "empty cells do not match the products that left"      # (sản phẩm trong tray output đã rời tray Input hẳn)

    def _finish_tests(self, up_to):
        """Kết quả của mọi lần test đã kết thúc trước hoặc đúng `up_to` (theo thứ tự)."""
        for n, end in sorted(self.test_end.items(), key=lambda kv: kv[1]):
            if end > up_to:
                continue
            f = self.fx[n]
            label = "PASS" if self.rng.random() < self.cfg.pass_rate else "NG"
            self.book.result(f.dut, label, end - self._started[n], [x.number for x in self.fixtures if x.available])
            f.finished, f.idle_since = True, end
            del self.test_end[n]
            self.book.settle_stuck([x.number for x in self.fixtures if x.available])

    # ---- thực hiện một việc --------------------------------------------------------------------------- #
    def _duration(self, task):
        c = self.cfg
        if isinstance(task, TrayTask):
            passed = sum(1 for _, i in task.sorts if self.book.duts[i].need == D.RETURN)       # (tray NG mặc định không kiểm tra)
            return (c.travel + len(task.sorts) * (c.move + c.place) + passed * c.laser + len(task.picks) * (c.scan + c.move + c.pick)
                    + (c.travel if any(self.book.duts[i].need == D.NG for _, i in task.sorts) else 0.0))
        if isinstance(task, ServiceTask):
            take = (c.move + c.pick) if task.take_head else 0.0
            return c.travel + take + c.move + c.place + c.laser + c.ats
        return c.travel + c.move + c.pick                                   # TakeTask

    def _place_time(self, task):
        """Số giây từ lúc bắt đầu việc tới khi sản phẩm nằm trong box và bắt đầu test."""
        c = self.cfg
        take = (c.move + c.pick) if getattr(task, "take_head", None) else 0.0
        return c.travel + take + c.move + c.place + c.laser                # test bắt đầu sau khi kiểm tra laser

    def _apply(self, task, t0):
        c = self.cfg
        self.tasks += 1
        self.log.append((t0, "%s: %s" % (task.kind, task.reason)))
        if isinstance(task, TrayTask):
            for head, dut_id in task.sorts:
                d = self.book.duts[dut_id]
                (self.book.put_in_output if d.need == D.RETURN and self.book.has_outputs else
                     self.book.return_to_tray if d.need == D.RETURN else self.book.put_in_ng)(d)
                self.heads[head] = None
            for head, cell in task.picks:
                self.heads[head] = self.book.take_from_tray(cell, head)
        else:
            f = self.fx[task.fixture]
            if isinstance(task, TakeTask):
                self.book.take_from_box(f.dut, task.head)
                self.heads[task.head] = f.dut
                f.dut, f.finished = None, False          # idle_since giữ nguyên: box đã chờ từ lúc có kết quả
                return
            if task.take_head:
                tested = f.dut
                self.book.take_from_box(tested, task.take_head)
                self.heads[task.take_head] = tested
            placed = self.heads[task.place_head]
            ts = t0 + self._place_time(task)
            self.book.place_in_box(placed, f.number)
            self.heads[task.place_head] = None
            self.idle[f.number].append(ts - f.idle_since)
            f.dut, f.finished = placed, False
            self._started[f.number] = ts
            self.test_end[f.number] = ts + c.test_time * (1 + self.rng.uniform(-c.jitter, c.jitter))

    # ---- vòng lặp chính ----------------------------------------------------------------------------- #
    def run(self, max_time=10 ** 7):
        stuck = False
        while self.t < max_time:
            self._finish_tests(self.t)
            task = self.planner.next_task(self.world())
            if task is not None:
                self.tray_visits += isinstance(task, TrayTask)
                dur = self._duration(task)
                self._apply(task, self.t)
                self.busy_time += dur
                self.t += dur
                self.check()
                continue
            if self.book.finished():
                break
            if not self.test_end:
                stuck = True
                break
            self.t = min(self.test_end.values())                          # chờ kết quả kế tiếp
        self.check()
        return self.report(stuck)

    def report(self, stuck=False):
        allidle = [x for xs in self.idle.values() for x in xs]
        st = self.book.stats()
        tests_sec = st["tests"] * self.cfg.test_time
        return {"stuck": stuck, "makespan_s": self.t, "products": self.cfg.cells,
                "passed": st["passed"], "ng": st["ng"], "tests": st["tests"], "retests": st["retests"],
                "tasks": self.tasks, "tray_visits": self.tray_visits, "robot_busy": self.busy_time / self.t if self.t else 0.0,
                "avg_idle_s": sum(allidle) / len(allidle) if allidle else 0.0, "max_idle_s": max(allidle) if allidle else 0.0,
                "box_utilisation": tests_sec / (self.cfg.boxes * self.t) if self.t else 0.0,
                "per_hour": 3600.0 * (st["passed"] + st["ng"]) / self.t if self.t else 0.0}


def simulate(**kw):
    planner_kw = {k: kw.pop(k) for k in list(kw) if k in PlannerConfig.__dataclass_fields__}
    cfg = SimConfig(planner=PlannerConfig(**planner_kw), **kw)
    sim = FlowSim(cfg)
    return sim.run(), sim


def main(argv=None):
    ap = argparse.ArgumentParser(description="What-if simulator of the tray flow (see the module docstring).")
    ap.add_argument("--boxes", type=int, default=10)
    ap.add_argument("--heads", type=int, default=8)
    ap.add_argument("--cells", type=int, default=80)
    ap.add_argument("--test-time", type=float, default=120.0)
    ap.add_argument("--pass-rate", type=float, default=0.9)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--travel", type=float, default=3.0)
    ap.add_argument("--move", type=float, default=1.2)
    ap.add_argument("--output-cells", type=int, nargs="*", default=[], help="cells of output tray 1 [2]; passed products go there")
    ap.add_argument("--laser", type=float, default=2.5, help="seconds of the laser check after a put down (0 = off)")
    ap.add_argument("--keep-free", type=int, default=1)
    ap.add_argument("--max-pick", type=int, default=8)
    ap.add_argument("--max-sort", type=int, default=8)
    ap.add_argument("--no-top-up", action="store_true", help="do not fetch products while every box is busy")
    ap.add_argument("--no-fill", action="store_true", help="at the tray fetch only what the waiting boxes need (old behaviour)")
    a = ap.parse_args(argv)
    rep, sim = simulate(boxes=a.boxes, heads=a.heads, cells=a.cells, ng_cells=a.cells, test_time=a.test_time,
                        pass_rate=a.pass_rate, seed=a.seed, travel=a.travel, move=a.move, laser=a.laser, outputs=tuple(a.output_cells), keep_free=a.keep_free,
                        max_pick=a.max_pick, max_sort=a.max_sort, top_up_when_idle=not a.no_top_up, fill_heads=not a.no_fill)
    print("products %d  passed %d  NG %d   tests %d (retests %d)" % (rep["products"], rep["passed"], rep["ng"], rep["tests"], rep["retests"]))
    print("time %.0f s   %.0f products/hour   box utilisation %.0f %%   robot busy %.0f %%" % (
        rep["makespan_s"], rep["per_hour"], 100 * rep["box_utilisation"], 100 * rep["robot_busy"]))
    print("trips to the input tray: %d" % rep["tray_visits"])
    print("box idle before a product is put in:  average %.1f s   longest %.1f s" % (rep["avg_idle_s"], rep["max_idle_s"]))
    if rep["stuck"]:
        print("STUCK: %s" % sim.planner.reason)
    return 1 if rep["stuck"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
