"""Từ việc của planner sang các bước của robot.

Một việc (planner.py) được đổi thành danh sách các STAGE. Một stage là một danh sách ngắn các bước sequence thông thường (rcs2/core/sequence.py: robot
move / ee heads / ee scanner / ee laser / ats) cộng một COMMIT tùy chọn: điều sổ sách phải ghi lại khi stage đã thực sự xong, ví dụ
"tay 3 đã lấy sản phẩm ở ô 12". Engine chạy lần lượt các stage và áp từng commit khi stage của nó xong,
nên sổ sách luôn biết từng sản phẩm đang ở đâu, kể cả khi một stage sau bị lỗi hoặc lượt chạy bị dừng giữa hai stage.

Pose được tính đủ sáu giá trị (geometry.Layout): một lần lấy / đặt của tay k tại một ô hoặc một box là MỘT lệnh `move` tới pose
đưa tay đó tới đúng chỗ, rồi xy lanh của tay đó hạ xuống, van hút chuyển trạng thái, xy lanh nâng lên và cảm biến áp suất được kiểm tra.

Các chu trình
  lấy từ tray Input:  đưa đầu đọc mã tới trên ô -> đọc mã -> đưa tay k tới trên ô -> hạ, bật hút, nâng, kiểm tra đã giữ
  đặt xuống (box, tray output, tray Input, tray NG): đưa tay k tới trên chỗ đặt -> hạ, tắt hút, nâng, kiểm tra đã nhả
                             -> đầu laser IL-1000 được đưa qua 2 điểm đo của sản phẩm và phải báo GO ở cả hai (sản phẩm nghiêng bị
                                từ chối: alarm 9204)  [settings.json -> flow.laser_check]
  trước mỗi lần một tay di chuyển: một CARRY CHECK = cảm biến áp suất của mọi tay đang cầm sản phẩm phải vẫn báo "đang giữ";
  một tay đánh rơi sản phẩm trên đường đi sẽ ném DropError (alarm 9208, robot bị dừng).

Commit (dict, được FlowController.commit áp dụng):
    {"op": "take_tray", "cell": c, "head": k}            tay đã lấy sản phẩm ở ô Input c
    {"op": "take_box", "fixture": n, "head": k}          tay đã lấy sản phẩm đã test ra khỏi box n
    {"op": "place_box", "fixture": n, "head": k}         tay đã đặt sản phẩm vào box n (bắt đầu test)
    {"op": "return_tray", "head": k, "cell": c}          tay đã đặt một sản phẩm đạt vào ô Input trống c (ô trống đầu tiên)
                                                         [chỉ khi không có tray output]
    {"op": "put_out", "head": k, "tray": i, "cell": c}   tay đã đặt một sản phẩm đạt vào ô c của tray output i (từ 0): ô trống kế tiếp
    {"op": "put_ng", "head": k}                          tay đã đặt một sản phẩm hỏng vào ô kế tiếp của tray NG
"""
from dataclasses import dataclass, field
from typing import List, Optional

from . import dut as D
from .planner import ServiceTask, TakeTask, TrayTask


class DropError(Exception):
    """Một tay đang mang sản phẩm mà không còn giữ được nó (cảm biến áp suất mất tín hiệu trên đường đi)."""


@dataclass
class Stage:
    label: str
    steps: list
    commit: Optional[dict] = None
    fixture: Optional[int] = None
    kind: str = ""                         # "carry" = carry check: lỗi nghĩa là đã đánh rơi sản phẩm


@dataclass
class BuildSettings:
    override: Optional[int] = None         # tốc độ robot (%) của các lần di chuyển; None = mặc định của bridge
    check_timeout_s: float = 1.0           # thời gian cho cảm biến áp suất
    scan: bool = True                      # đọc mã vạch từng sản phẩm trước khi hút (cần scanner trong layout)
    send_dut_out: bool = False             # báo ATS rằng sản phẩm đã test đã được lấy ra
    auto_start_test: bool = True           # gửi placeDUTOK sau khi đặt sản phẩm vào
    via_tray: str = ""                     # điểm dạy tùy chọn robot đi qua khi đổi khu vực
    via_fixtures: str = ""
    laser: bool = False                    # kiểm tra sản phẩm đã đặt xuống bằng IL-1000 (cần laser_at_O trong layout)
    laser_places: tuple = ("box", "input", "output")
    laser_offsets: tuple = ((-15.0, 0.0, 0.0), (15.0, 0.0, 0.0))
    laser_timeout_s: float = 1.0


class StageBuilder:
    def __init__(self, layout, book, settings: BuildSettings):
        self.layout, self.book, self.s = layout, book, settings
        self.holding = set()               # các tay đang mang sản phẩm ở thời điểm này của việc đang dựng

    # ---- từng lần di chuyển ---------------------------------------------------------------------- #
    def _move(self, pose):
        step = {"robot": "move", "target": pose}
        if self.s.override is not None:
            step["override"] = self.s.override
        return step

    def _hold(self, head):
        return [{"ee": "heads", "cylinder": "down", "heads": [head]},
                {"ee": "heads", "vacuum": "on", "heads": [head]},
                {"ee": "heads", "cylinder": "up", "heads": [head]},
                {"ee": "heads", "check": "hold", "heads": [head], "timeout_s": self.s.check_timeout_s}]

    def _release(self, head):
        return [{"ee": "heads", "cylinder": "down", "heads": [head]},
                {"ee": "heads", "vacuum": "off", "heads": [head]},
                {"ee": "heads", "cylinder": "up", "heads": [head]},
                {"ee": "heads", "check": "release", "heads": [head], "timeout_s": self.s.check_timeout_s}]

    def _via(self, point):
        return [self._move(point)] if point else []

    def _carry_check(self):
        """Trước khi một tay di chuyển: mọi tay đang mang sản phẩm phải vẫn giữ được nó. [] khi không tay nào mang hàng."""
        if not self.holding:
            return []
        return [Stage("carry check heads %s" % sorted(self.holding),
                      [{"ee": "heads", "check": "hold", "heads": sorted(self.holding), "timeout_s": self.s.check_timeout_s}], kind="carry")]

    def _laser(self, kind, ref, fixture=None):
        """Kiểm tra laser một sản phẩm vừa đặt xuống tại `ref` (chỉ số ô của một tray, hoặc số fixture): 2 điểm đo."""
        if not (self.s.laser and kind in self.s.laser_places):
            return []
        steps = []
        for pose in self.layout.laser_poses(kind, ref, self.s.laser_offsets):
            steps += [self._move(pose), {"ee": "laser", "check": "ok", "timeout_s": self.s.laser_timeout_s}]
        return [Stage("laser check of the product at %s %s" % (kind, ref), steps, None, fixture)]

    # ---- các stage ------------------------------------------------------------------------------- #
    def pick_from_tray(self, head, cell):
        stages = self._carry_check()
        if self.s.scan and self.layout.scanner:
            stages.append(Stage("scan cell %d" % cell, [self._move(self.layout.scan_pose(cell)),
                                                        {"ee": "scanner", "tag": "cell:%d" % cell}]))
        stages.append(Stage("head %d picks cell %d" % (head, cell),
                            [self._move(self.layout.pick_pose(head, cell))] + self._hold(head),
                            {"op": "take_tray", "cell": cell, "head": head}))
        self.holding.add(head)
        return stages

    def put_back(self, head, dut, cell):
        """Một sản phẩm đã test vào ô Input `cell` (đạt: ô trống đầu tiên) hoặc vào ô NG `cell` (hỏng)."""
        stages = self._carry_check()
        if dut.need == D.RETURN:
            stages.append(Stage("head %d puts a passed product into empty cell %d" % (head, cell),
                                [self._move(self.layout.input_pose(head, cell))] + self._release(head),
                                {"op": "return_tray", "head": head, "cell": cell}))
            self.holding.discard(head)
            return stages + self._laser("input", cell)
        stages.append(Stage("head %d puts a failed product into NG cell %d" % (head, cell),
                            [self._move(self.layout.ng_pose(head, cell))] + self._release(head), {"op": "put_ng", "head": head}))
        self.holding.discard(head)
        return stages + self._laser("ng", cell)

    def put_out(self, head, dut, slot):
        """Một sản phẩm đạt vào ô của tray output `slot` = (chỉ số tray, ô) (ô trống kế tiếp của các tray output)."""
        tray, cell = slot
        stages = self._carry_check()
        stages.append(Stage("head %d puts a passed product into output %d cell %d" % (head, tray + 1, cell),
                            [self._move(self.layout.output_pose(head, tray, cell))] + self._release(head),
                            {"op": "put_out", "head": head, "tray": tray, "cell": cell}))
        self.holding.discard(head)
        return stages + self._laser("output", slot)

    def take_from_box(self, fixture, head):
        stages = self._carry_check()
        stages.append(Stage("head %d takes the tested product out of box %d" % (head, fixture),
                            [self._move(self.layout.fixture_pose(head, fixture))] + self._hold(head),
                            {"op": "take_box", "fixture": fixture, "head": head}, fixture))
        self.holding.add(head)
        if self.s.send_dut_out:
            stages.append(Stage("box %d: DUT out" % fixture, [{"ats": "dut_out", "fixture": fixture}], None, fixture))
        return stages

    def place_in_box(self, fixture, head, dut):
        stages = self._carry_check()
        stages.append(Stage("head %d puts a product into box %d" % (head, fixture),
                            [self._move(self.layout.fixture_pose(head, fixture))] + self._release(head),
                            {"op": "place_box", "fixture": fixture, "head": head}, fixture))
        self.holding.discard(head)
        stages += self._laser("box", fixture, fixture)             # sản phẩm bị nghiêng thì không được bắt đầu test
        ats = []
        if dut.sn:
            ats.append({"ats": "barcode", "sn": dut.sn, "fixture": fixture})
        if self.s.auto_start_test:
            ats.append({"ats": "place_dut_ok", "fixture": fixture})
        if ats:
            stages.append(Stage("box %d: start the test" % fixture, ats, None, fixture))
        return stages

    # ---- cả một việc ----------------------------------------------------------------------------- #
    def build(self, task):
        self.holding = {d.location[1] for d in self.book.duts.values() if d.location[0] == D.HEAD}
        if isinstance(task, TrayTask):
            return self._tray(task)
        if isinstance(task, ServiceTask):
            stages = self._via_fixtures()
            if task.take_head:
                stages += self.take_from_box(task.fixture, task.take_head)
            stages += self.place_in_box(task.fixture, task.place_head, self.book.duts[task.place_dut])
            return stages
        if isinstance(task, TakeTask):
            return self._via_fixtures() + self.take_from_box(task.fixture, task.head)
        raise TypeError("unknown task %r" % (task,))

    def _via_fixtures(self):
        step = self._via(self.s.via_fixtures)
        return [Stage("via fixtures", step)] if step else []

    def _tray(self, task):
        stages = []
        via = self._via(self.s.via_tray)
        if via:
            stages.append(Stage("via tray", via))
        ng_next = self.book.ng_used
        empties = iter(self.book.empty_cells())                         # không có tray output: hàng đạt vào các ô Input trống đầu tiên
        outs = iter(self.book.output_slots())                           # có tray output: vào các ô trống kế tiếp của chúng, tray 1 trước
        for head, dut_id in task.sorts:
            dut = self.book.duts[dut_id]
            if dut.need == D.RETURN and self.book.has_outputs:
                stages += self.put_out(head, dut, next(outs))
            elif dut.need == D.RETURN:
                stages += self.put_back(head, dut, next(empties))
            else:
                stages += self.put_back(head, dut, ng_next)
                ng_next += 1
        for head, cell in task.picks:
            stages += self.pick_from_tray(head, cell)
        return stages
