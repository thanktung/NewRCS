"""
scheduler.py — PCB Test Station: toàn bộ logic xử lý
Không import bất kỳ thứ gì liên quan đến LearnUI.

Logic tray:
  - Luôn ưu tiên pick UNTESTED từ tray1 trước
  - Khi tray1 hết UNTESTED mới pick từ tray2
  - Các board PASS đặt ngược lại tray1 (slot trống)
  - Board NG đặt vào NG tray riêng
  - Khi tray1 đầy toàn PASS (không còn UNTESTED):
      → CHANGE: tray2 trượt vào vị trí tray1, tray2 reset UNTESTED mới
  - KHÔNG fill tray1 từ tray2 theo slot — tray2 là nguồn pick độc lập
"""

import queue
import socket
import threading
import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Callable

from scanBox import BoxScanner
from InitSettings import (
    BOX_ADDRESS, BOX_COUNT,
    ROBOT_HOST, ROBOT_PORT,
    TRAY_SLOTS, GRIPPER_HEADS,
    POLL_INTERVAL, ROBOT_RECV_TIMEOUT, ROBOT_MAX_RETRIES, BOX_RECV_TIMEOUT,
)


# ════════════════════════════════════════════
# CONFIG — toàn bộ thông số nằm ở station.ini, sửa trạm mới thì sửa ở đó
# (InitSettings.py đọc + validate station.ini, không cần sửa)
# ════════════════════════════════════════════


# ════════════════════════════════════════════
# DATA MODEL
# ════════════════════════════════════════════
class BoardState(Enum):
    UNTESTED = "UNTESTED"
    PASS     = "PASS"
    NG       = "NG"


class BoxState(Enum):
    EMPTY   = "empty"
    READY   = "ready_for_test"
    TESTING = "testing"
    PASS    = "pass"
    FAIL    = "fail"
    ERROR   = "error"
    UNKNOWN = "unknown"


DONE_STATES    = {BoxState.PASS, BoxState.FAIL, BoxState.ERROR}
# Box đã có board bên trong (đang test hoặc chờ test bắt đầu)
ACTIVE_STATES  = {BoxState.TESTING, BoxState.READY}


@dataclass
class Board:
    board_id: int
    state: BoardState = BoardState.UNTESTED

    def __repr__(self):
        return f"B{self.board_id}({self.state.value})"


@dataclass
class Tray:
    tray_id: int
    slots: list[Optional["Board"]] = field(default_factory=list)

    def __post_init__(self):
        if not self.slots:
            self.slots = [None] * TRAY_SLOTS

    def prefill(self, start_id: int) -> int:
        for i in range(TRAY_SLOTS):
            self.slots[i] = Board(start_id + i)
        return start_id + TRAY_SLOTS

    def first_untested_slot(self) -> Optional[int]:
        for i, b in enumerate(self.slots):
            if b and b.state == BoardState.UNTESTED:
                return i
        return None

    def first_empty_slot(self) -> Optional[int]:
        for i, b in enumerate(self.slots):
            if b is None:
                return i
        return None

    def is_full(self) -> bool:
        return all(b is not None for b in self.slots)

    def has_empty(self) -> bool:
        return any(b is None for b in self.slots)

    def untested_count(self) -> int:
        return sum(1 for b in self.slots if b and b.state == BoardState.UNTESTED)

    def pass_count(self) -> int:
        return sum(1 for b in self.slots if b and b.state == BoardState.PASS)

    def all_pass_or_empty(self) -> bool:
        """True nếu không còn UNTESTED nào (toàn PASS hoặc trống)."""
        return self.untested_count() == 0

    def all_done(self) -> bool:
        """True nếu đầy và không còn UNTESTED."""
        return self.is_full() and self.untested_count() == 0


@dataclass
class GripperHead:
    head_id: int
    board: Optional[Board] = None
    enabled: bool = True   # False → không dùng head này trong lịch chạy

    @property
    def is_empty(self) -> bool:
        return self.board is None


class Gripper:
    def __init__(self):
        self.heads = [GripperHead(i) for i in range(GRIPPER_HEADS)]

    def empty_heads(self) -> list[int]:
        """Danh sách head đang trống VÀ đang bật (enabled)."""
        return [h.head_id for h in self.heads if h.enabled and h.is_empty]

    def untested_heads(self) -> list[int]:
        """Danh sách head đang giữ board UNTESTED VÀ đang bật."""
        return [h.head_id for h in self.heads
                if h.enabled and h.board and h.board.state == BoardState.UNTESTED]

    def tested_heads(self) -> list[int]:
        """Danh sách head đang giữ board đã test (PASS/NG) VÀ đang bật.

        Head bị disable trong lúc đang giữ board đã test sẽ KHÔNG được liệt
        kê ở đây → board đó bị giữ nguyên trên head cho đến khi bật lại
        (nhất quán với nguyên tắc "disable = không dùng thành phần đó").
        """
        return [h.head_id for h in self.heads
                if h.enabled and h.board and h.board.state != BoardState.UNTESTED]

    def first_empty(self) -> Optional[int]:
        h = self.empty_heads()
        return h[0] if h else None

    def first_untested(self) -> Optional[int]:
        h = self.untested_heads()
        return h[0] if h else None

    def loaded_count(self) -> int:
        return sum(1 for h in self.heads if h.enabled and not h.is_empty)

    def empty_count(self) -> int:
        enabled_total = sum(1 for h in self.heads if h.enabled)
        return enabled_total - self.loaded_count()


# ════════════════════════════════════════════
# TCP CLIENTS
# ════════════════════════════════════════════
class BoxClient:
    """
    Không còn dùng lệnh GET để hỏi trạng thái.
    Box (BoxSimulator.py) tự chủ động gửi 1 dòng trạng thái mới lên
    socket bất cứ khi nào state của nó thay đổi (push, không cần PC hỏi),
    kể cả ngay lúc vừa kết nối.

    Vì vậy chỉ có DUY NHẤT 1 thread (listener) được phép đọc socket:
      - Nếu dòng nhận được khớp với 1 giá trị BoxState hợp lệ
        → coi là push trạng thái, gọi callback on_state_cb(box_id, state)
      - Ngược lại (vd "OK"/"BUSY"/"NOT_READY") → coi là response của
        lệnh LOAD/UNLOAD, đẩy vào hàng đợi để _send() đang chờ nhận được
    """
    def __init__(self, box_id: int):
        self.box_id = box_id
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.connect(BOX_ADDRESS[box_id])
        self._sock.settimeout(0.5)   # timeout ngắn để listener kiểm tra cờ dừng
        self._buf = ""
        self._lock = threading.Lock()

        self._resp_queue: "queue.Queue[str]" = queue.Queue()
        self._on_state_cb: Optional[Callable[[int, "BoxState"], None]] = None
        self._listening = False
        self._listen_thread: Optional[threading.Thread] = None

    # ── Listener (chạy trong thread riêng) ──────────────────────
    def _recv_line(self) -> Optional[str]:
        while "\n" not in self._buf:
            try:
                data = self._sock.recv(1024)
            except socket.timeout:
                return None
            if not data:
                raise ConnectionError(f"Box{self.box_id} ngắt kết nối")
            self._buf += data.decode()
        line, self._buf = self._buf.split("\n", 1)
        return line.strip()

    def _listen_loop(self):
        while self._listening:
            try:
                line = self._recv_line()
            except Exception:
                break  # mất kết nối → dừng listener
            if not line:
                continue
            try:
                state = BoxState(line)
            except ValueError:
                # Không phải state hợp lệ → là response của lệnh (OK/BUSY/...)
                self._resp_queue.put(line)
                continue
            if self._on_state_cb:
                self._on_state_cb(self.box_id, state)

    def start_listener(self, on_state_cb: Callable[[int, "BoxState"], None]):
        if self._listening:
            return
        self._on_state_cb = on_state_cb
        self._listening = True
        self._listen_thread = threading.Thread(
            target=self._listen_loop,
            daemon=True,
            name=f"box{self.box_id}-listen",
        )
        self._listen_thread.start()

    def stop_listener(self):
        self._listening = False

    # ── Lệnh (LOAD/UNLOAD) — chờ response qua hàng đợi ──────────
    def _send(self, cmd: str) -> str:
        with self._lock:
            self._sock.sendall((cmd + "\r\n").encode())
            return self._resp_queue.get(timeout=BOX_RECV_TIMEOUT)

    def load(self) -> bool:
        try:
            return self._send("LOAD") == "OK"
        except Exception:
            return False

    def unload(self) -> bool:
        try:
            return self._send("UNLOAD") == "OK"
        except Exception:
            return False


class ProtocolError(Exception):
    """Robot phản hồi DONE nhưng không khớp với lệnh vừa gửi."""
    pass


class RobotClient:
    def __init__(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.connect((ROBOT_HOST, ROBOT_PORT))
        self._sock.settimeout(ROBOT_RECV_TIMEOUT)
        self._buf = ""
        self._lock = threading.Lock()

    def _recv_line(self) -> str:
        while "\n" not in self._buf:
            data = self._sock.recv(1024)
            if not data:
                raise ConnectionError("Robot ngắt kết nối")
            self._buf += data.decode()
        line, self._buf = self._buf.split("\n", 1)
        return line.strip()

    def send(self, cmd: str) -> str:
        # Tên lệnh mong đợi, trích từ cmd gửi đi:
        # "PICK:1,5,2;" -> "PICK", "CHANGE;" -> "CHANGE"
        cmd_name = cmd.split(":", 1)[0].split(";", 1)[0].strip().upper()
        expected = f"DONE:{cmd_name}"

        with self._lock:
            for attempt in range(1, ROBOT_MAX_RETRIES + 1):
                try:
                    self._sock.sendall((cmd + "\n").encode())
                    while True:
                        line = self._recv_line()
                        if line == expected:
                            return line
                        if line == "DONE" or line.startswith("DONE"):
                            # Robot trả DONE nhưng không đúng lệnh vừa gửi
                            # -> lỗi giao thức, KHÔNG được coi là hoàn tất
                            raise ProtocolError(
                                f"Robot phản hồi sai lệnh: gửi '{cmd_name}', "
                                f"nhận '{line}' (mong đợi '{expected}')"
                            )
                except TimeoutError:
                    if attempt < ROBOT_MAX_RETRIES:
                        self._buf = ""
                        continue
                    raise TimeoutError(
                        f"Robot không phản hồi sau {ROBOT_MAX_RETRIES} lần thử "
                        f"(cmd={cmd.strip()}, timeout={ROBOT_RECV_TIMEOUT}s)"
                    )
                except ConnectionError:
                    raise

    def close(self):
        try:
            self._sock.close()
        except Exception:
            pass


# ════════════════════════════════════════════
# SCHEDULER
# ════════════════════════════════════════════
class Scheduler:
    def __init__(self):
        self.log: Callable[[str], None] = print
        self.ui_update: Callable[[], None] = lambda: None
        self.box_scanner = BoxScanner(self, interval=1.0)

        # Tray 1: nguồn UNTESTED chính, nhận PASS về
        # Tray 2: nguồn UNTESTED dự phòng khi tray1 hết
        self.tray1 = Tray(tray_id=1)
        self.tray2 = Tray(tray_id=2)
        self.ng_list: list[Board] = []
        self.gripper = Gripper()
        self._board_counter = 1

        self._board_counter = self.tray1.prefill(self._board_counter)
        self._board_counter = self.tray2.prefill(self._board_counter)

        self.box_clients: list[BoxClient] = []
        self.box_states: list[BoxState] = [BoxState.UNKNOWN] * BOX_COUNT
        self.box_boards: dict[int, Board] = {}   # box_id → Board đang test
        self.box_enabled: list[bool] = [True] * BOX_COUNT  # False → không dùng box này

        # Số liệu theo từng box (index = box_id - 1), dùng để tính tốc độ
        # test và tỉ lệ Pass — đếm tại thời điểm UNLOAD (biết kết quả PASS/FAIL/ERROR)
        self.box_tested_count: list[int] = [0] * BOX_COUNT
        self.box_pass_count: list[int] = [0] * BOX_COUNT

        # Đồng hồ đo thời gian CHẠY THỰC TẾ (loại trừ thời gian Stop), dùng
        # làm mẫu số tính tốc độ test — Stop lâu không làm tụt tốc độ hiển thị
        self._active_seconds: float = 0.0
        self._run_started_at: Optional[float] = None

        self.robot: Optional[RobotClient] = None
        self._running = False
        self.stats = {"loaded": 0, "pass": 0, "ng": 0, "change": 0}

        self._manual_id_counter = -1  # id âm để phân biệt board tạo tay khỏi board hệ thống

    # ── Kết nối ──────────────────────────────────
    def connect(self):
        self.log("[INIT] Kết nối box simulators...")
        for i in range(BOX_COUNT):
            self.box_clients.append(BoxClient(i + 1))
        self.log(f"[INIT] {BOX_COUNT} boxes OK")
        self.log("[INIT] Kết nối robot...")
        self.robot = RobotClient()
        self.log("[INIT] Robot OK")

    # ── Robot wrapper ────────────────────────────
    def _robot(self, cmd: str) -> Optional[str]:
        self.log(f"→ {cmd.strip()}")
        try:
            resp = self.robot.send(cmd)
            self.log(f"← {resp}")
            self.ui_update()
            return resp
        except TimeoutError as e:
            self.log(f"[WARN] Timeout robot: {e}")
            self.ui_update()
            return None
        except ProtocolError as e:
            # Robot trả về DONE nhưng sai lệnh -> không được coi là hoàn tất,
            # trả None để nơi gọi (_pick_next/_load_box/_unload_box/_place_board/
            # _do_change) dừng lại, không tiếp tục bước kế tiếp.
            self.log(f"[ERROR] Robot phản hồi sai lệnh: {e}")
            self.ui_update()
            return None
        except ConnectionError as e:
            self.log(f"[ERROR] Mất kết nối robot: {e}")
            self._running = False
            self.ui_update()
            return None


    # ════════════════════════════════════════════
    # PICK — lấy board UNTESTED từ tray vào gripper head
    # Ưu tiên tray1, chỉ dùng tray2 khi tray1 hết UNTESTED
    # ════════════════════════════════════════════
    def _pick_next(self, head: int) -> bool:
        """Pick 1 board UNTESTED vào head đã chỉ định."""
        # Ưu tiên tray1
        for tray in [self.tray1, self.tray2]:
            slot = tray.first_untested_slot()
            if slot is not None:
                board = tray.slots[slot]
                resp = self._robot(f"PICK:{tray.tray_id},{slot},{head};")
                if resp is None:
                    return False
                self.gripper.heads[head].board = board
                tray.slots[slot] = None
                self.log(f"  PICK tray{tray.tray_id}[{slot}] → head{head} ({board})")
                return True
        return False  # cả 2 tray hết UNTESTED

    # ════════════════════════════════════════════
    # LOAD — đặt board UNTESTED từ gripper vào box
    # ════════════════════════════════════════════
    def _load_box(self, box_id: int, head: int) -> bool:
        board = self.gripper.heads[head].board
        if board is None or board.state != BoardState.UNTESTED:
            return False
        resp = self._robot(f"LOAD:{box_id},{head};")
        if resp is None:
            return False
        self.gripper.heads[head].board = None
        self.box_boards[box_id] = board
        self.box_clients[box_id - 1].load()
        # Box simulator trả về ready_for_test sau lệnh LOAD,
        # sau đó tự chuyển sang testing rồi pass/fail

        self.stats["loaded"] += 1
        self.log(f"  LOAD box{box_id} ← head{head} ({board})")
        return True

    # ════════════════════════════════════════════
    # UNLOAD — lấy board đã test từ box ra gripper
    # ════════════════════════════════════════════
    def _unload_box(self, box_id: int, result: BoxState, head: int) -> bool:
        resp = self._robot(f"UNLOAD:{box_id},{head};")
        if resp is None:
            return False
        board = self.box_boards.pop(box_id, Board(0))
        board.state = BoardState.PASS if result == BoxState.PASS else BoardState.NG
        self.gripper.heads[head].board = board
        self.box_clients[box_id - 1].unload()

        idx = box_id - 1
        self.box_tested_count[idx] += 1
        if result == BoxState.PASS:
            self.box_pass_count[idx] += 1

        self.log(f"  UNLOAD box{box_id} → head{head} ({board})")
        return True

    # ════════════════════════════════════════════
    # PLACE — đặt board đã test từ gripper vào tray/NG
    # Board PASS → tray1 (slot trống), fallback tray2
    # Board NG   → ng_list
    # ════════════════════════════════════════════
    def _place_board(self, head: int) -> bool:
        board = self.gripper.heads[head].board

        if board is None or board.state == BoardState.UNTESTED:
            return False

        # PASS -> chỉ đặt về tray1
        if board.state == BoardState.PASS:

            slot = self.tray1.first_empty_slot()

            # Tray1 đầy -> giữ board trên gripper chờ CHANGE
            if slot is None:
                self.log(
                    f"  [WAIT] Tray1 đầy, board PASS {board} giữ trên head{head}"
                )
                return False

            resp = self._robot(f"PLACE:1,{slot},{head};")
            if resp is None:
                return False

            self.tray1.slots[slot] = board
            self.gripper.heads[head].board = None

            self.stats["pass"] += 1

            self.log(
                f"  PLACE head{head} → tray1[{slot}] (PASS)"
            )
            return True

        # NG
        ng_slot = len(self.ng_list)

        resp = self._robot(f"PLACE:0,{ng_slot},{head};")
        if resp is None:
            return False

        self.ng_list.append(board)
        self.gripper.heads[head].board = None

        self.stats["ng"] += 1

        self.log(
            f"  PLACE head{head} → NG_TRAY[{ng_slot}] (NG)"
        )

        return True

    # ════════════════════════════════════════════
    # CHANGE — khi tray1 hết UNTESTED và không còn
    # board PASS/UNTESTED đang trên không (gripper/box)
    # → tray2 → tray1, tray2 reset UNTESTED mới
    # ════════════════════════════════════════════
    def _should_change(self) -> bool:
        """True khi không còn board nào (ở bất kỳ đâu) còn khả năng quay
        lại tray1 nữa — tức đã đến lúc đổi tray.

        LƯU Ý: KHÔNG dùng `tray1.has_empty()` làm điều kiện. Board NG lấy
        từ tray1 không bao giờ quay lại tray1 (đi thẳng NG tray), nên ô đó
        để trống VĨNH VIỄN trừ khi có board PASS khác (từ tray1 hoặc
        tray2) lấp vào. Nếu tỉ lệ NG toàn trạm > 50%, tổng số board PASS
        khả dĩ (tối đa 2×TRAY_SLOTS − NG_total) sẽ KHÔNG BAO GIỜ đủ lấp
        đầy tray1 → nếu bắt buộc "tray1 đầy" mới change, hệ thống sẽ treo
        vĩnh viễn ngay khi cả 2 tray cạn UNTESTED mà tray1 vẫn còn ô trống.
        Điều kiện đúng chỉ cần: không còn UNTESTED nào phải xử lý, và
        không còn board nào đang "trôi nổi" (trên gripper hoặc trong box)
        có thể còn quay về tray1 nữa. Các ô trống do NG để lại là bình
        thường về mặt vật lý — tray1 khi đổi ra ngoài có thể còn vài ô
        trống vì board đó bị NG, không phải mất dữ liệu.
        """
        # Tray1 còn UNTESTED → chưa cần change
        if self.tray1.untested_count() > 0:
            return False
        # Còn board UNTESTED trên gripper chờ vào box (có thể từ tray2,
        # nhưng nếu test PASS thì vẫn sẽ quay về tray1 → chưa change được)
        if self.gripper.untested_heads():
            return False
        # Còn box đang có board bên trong (READY hoặc TESTING) — kết quả
        # của nó (nếu PASS) còn có thể quay về tray1
        if any(s in ACTIVE_STATES for s in self.box_states):
            return False
        # Còn board PASS/NG trên gripper chưa place — PASS thì còn cần về tray1
        if self.gripper.tested_heads():
            return False
        return True

    def _do_change(self):
        self.log("[CHANGE] Tray1 hết UNTESTED và không còn board nào đang xử lý → CHANGE tray...")
        resp = self._robot("CHANGE;")
        if resp is None:
            return
        # Tray2 trượt vào vị trí tray1
        self.tray1 = Tray(tray_id=1)
        self.tray1.slots = list(self.tray2.slots)
        # Reset tray2 với board UNTESTED mới
        self.tray2 = Tray(tray_id=2)
        self._board_counter = self.tray2.prefill(self._board_counter)
        self.stats["change"] += 1
        self.log(f"[CHANGE] Done. tray1 ← tray2 cũ, tray2 ← UNTESTED mới (B{self._board_counter-TRAY_SLOTS}–B{self._board_counter-1})")

    # ════════════════════════════════════════════
    # MANUAL EDIT — sửa tay trạng thái khi scheduler đang STOP
    # Dùng khi công nhân lấy board ra / đặt thêm board vào box test,
    # tay gắp, hoặc tray đầu vào trong lúc hệ thống dừng, để phần mềm
    # đồng bộ lại đúng với thực tế trước khi Start lại.
    # ════════════════════════════════════════════
    def manual_edit_allowed(self) -> bool:
        """Chỉ cho phép sửa tay khi scheduler đang dừng."""
        return not self._running

    # ════════════════════════════════════════════
    # ENABLE/DISABLE — bật/tắt từng box, từng tay gắp
    # Dùng được BẤT KỲ LÚC NÀO (kể cả khi đang chạy), khác với manual edit.
    # Đơn giản: disable = scheduler không dùng thành phần đó nữa cho các
    # thao tác MỚI (pick/load/unload/place). Board đang dở trên thành phần
    # bị disable sẽ được GIỮ NGUYÊN, không tự động xử lý tiếp cho tới khi
    # bật lại — tránh robot đưa hàng vào chỗ đang bị khóa vì lý do vật lý
    # (sửa chữa, bảo trì...).
    # ════════════════════════════════════════════
    def set_box_enabled(self, box_id: int, enabled: bool) -> bool:
        idx = box_id - 1
        if idx < 0 or idx >= len(self.box_enabled):
            return False
        self.box_enabled[idx] = enabled
        self.log(f"[CONFIG] Box{box_id} → {'ENABLED' if enabled else 'DISABLED'}")
        self.ui_update()
        return True

    def set_head_enabled(self, head_id: int, enabled: bool) -> bool:
        if head_id < 0 or head_id >= len(self.gripper.heads):
            return False
        self.gripper.heads[head_id].enabled = enabled
        self.log(f"[CONFIG] Head{head_id} → {'ENABLED' if enabled else 'DISABLED'}")
        self.ui_update()
        return True

    def _new_manual_board(self, board_state: BoardState) -> Board:
        board = Board(board_id=self._manual_id_counter, state=board_state)
        self._manual_id_counter -= 1
        return board

    def manual_set_box(self, box_id: int, board_state: Optional[BoardState]) -> bool:
        """Sửa tay trạng thái 1 box test.

        board_state=None              → box trống (không có board bên trong)
        board_state=UNTESTED/PASS/NG  → box đang chứa board ở trạng thái đó
        """
        if not self.manual_edit_allowed():
            return False
        idx = box_id - 1
        if idx < 0 or idx >= len(self.box_states):
            return False

        if board_state is None:
            self.box_states[idx] = BoxState.EMPTY
            self.box_boards.pop(box_id, None)
            self.log(f"[MANUAL] Box{box_id} → EMPTY (lấy board ra)")
        else:
            board = self.box_boards.get(box_id)
            if board is None:
                board = self._new_manual_board(board_state)
            else:
                board.state = board_state
            self.box_boards[box_id] = board

            if board_state == BoardState.UNTESTED:
                self.box_states[idx] = BoxState.READY
            elif board_state == BoardState.PASS:
                self.box_states[idx] = BoxState.PASS
            else:
                self.box_states[idx] = BoxState.FAIL

            self.log(f"[MANUAL] Box{box_id} → {self.box_states[idx].value} ({board})")

        self.ui_update()
        return True

    def manual_set_gripper(self, head_id: int, board_state: Optional[BoardState]) -> bool:
        """Sửa tay board đang giữ trên 1 head của tay gắp.

        board_state=None → head trống (bỏ board ra)
        board_state=...   → head đang giữ board ở trạng thái đó
        """
        if not self.manual_edit_allowed():
            return False
        if head_id < 0 or head_id >= len(self.gripper.heads):
            return False

        head = self.gripper.heads[head_id]
        if board_state is None:
            head.board = None
            self.log(f"[MANUAL] Head{head_id} → empty")
        else:
            if head.board is None:
                head.board = self._new_manual_board(board_state)
            else:
                head.board.state = board_state
            self.log(f"[MANUAL] Head{head_id} → {head.board}")

        self.ui_update()
        return True

    def manual_set_tray_slot(self, tray_id: int, slot: int,
                              board_state: Optional[BoardState]) -> bool:
        """Sửa tay 1 slot trên tray đầu vào (tray1 hoặc tray2).

        board_state=None → slot trống (lấy board ra)
        board_state=...   → slot đang có board ở trạng thái đó
        """
        if not self.manual_edit_allowed():
            return False
        tray = self.tray1 if tray_id == 1 else self.tray2 if tray_id == 2 else None
        if tray is None or slot < 0 or slot >= len(tray.slots):
            return False

        if board_state is None:
            tray.slots[slot] = None
            self.log(f"[MANUAL] Tray{tray_id}[{slot}] → empty (lấy board ra)")
        else:
            board = tray.slots[slot]
            if board is None:
                board = self._new_manual_board(board_state)
            else:
                board.state = board_state
            tray.slots[slot] = board
            self.log(f"[MANUAL] Tray{tray_id}[{slot}] → {board}")

        self.ui_update()
        return True

    # ════════════════════════════════════════════
    # CÁC BƯỚC CỦA 1 CYCLE — tách riêng để _loop() dễ đọc/bảo trì
    # ════════════════════════════════════════════
    def _refill_gripper(self):
        """Pick board UNTESTED bù vào các head trống.

        LUÔN chừa lại đúng 1 tay trống hoàn toàn (không đụng tới khi refill),
        bất kể hiện có bao nhiêu box đang trống hay đang test. Tay này là
        "van an toàn" duy nhất đảm bảo lúc nào cũng unload được box vừa test
        xong, không phụ thuộc vào có bao nhiêu box trống hay box DONE đứng
        trước/sau box trống trong thứ tự duyệt ở BƯỚC 2 (_process_boxes).

        Các tay UNTESTED pick dư ra (khi tạm thời chưa có đủ box trống để
        nhận ngay) không phải lỗi — chúng là hàng "chờ sẵn" trên gripper,
        sẽ được đặt vào ngay khi box kế tiếp trống ra, khỏi mất công pick lại.
        """
        max_pick = max(0, self.gripper.empty_count() - 1)
        picked_n = 0
        for head_id in self.gripper.empty_heads():
            if picked_n >= max_pick:
                break
            if not self._pick_next(head_id):
                break
            picked_n += 1

    def _place_all_tested(self):
        """Đặt hết các board đã test (PASS/NG) đang trên gripper về tray/NG."""
        for head_id in list(self.gripper.tested_heads()):
            self._place_board(head_id)

    def _load_pending_empty_boxes(self, limit: Optional[int] = None):
        """Load UNTESTED vào các box đang EMPTY nhưng chưa có board.

        limit: nếu truyền vào, chỉ xét các box có index < limit (dùng khi
        đang xử lý dở dang trong vòng lặp BƯỚC 2, chỉ muốn bù lại các box
        EMPTY nằm phía trước box hiện tại). None → xét toàn bộ.
        """
        indices = range(limit) if limit is not None else range(len(self.box_states))
        for j in indices:
            box_id = j + 1
            if not self.box_enabled[j]:
                continue  # box bị disable → không dùng, bỏ qua hoàn toàn
            if self.box_states[j] == BoxState.EMPTY and (box_id not in self.box_boards):
                untested_h = self.gripper.untested_heads()
                if not untested_h:
                    break
                self._load_box(box_id, untested_h[0])

    def _process_boxes(self):
        """BƯỚC 2: duyệt box theo thứ tự tự nhiên — hành động theo trạng thái.

        EMPTY → đặt UNTESTED vào
        DONE  → lấy PASS/FAIL ra bằng tay dự phòng, đặt UNTESTED vào ngay
        Không ưu tiên DONE hơn EMPTY → box nào đến lượt thì xử lý,
        tránh box EMPTY bị bỏ đói khi test nhanh liên tục.
        PASS/FAIL gom trên tay, chỉ place 1 lượt khi hết tay trống hoặc hết box.
        """
        for i, state in enumerate(self.box_states):
            box_id = i + 1

            if not self.box_enabled[i]:
                continue  # box bị disable → không dùng, bỏ qua hoàn toàn

            if state == BoxState.EMPTY and (box_id not in self.box_boards):
                untested_h = self.gripper.untested_heads()
                if untested_h:
                    self._load_box(box_id, untested_h[0])

            elif state in DONE_STATES:
                empty_heads = self.gripper.empty_heads()
                if not empty_heads:
                    # Tay trống hết → place toàn bộ PASS/FAIL 1 lượt để lấy lại tay
                    self._place_all_tested()
                    # Refill tay vừa trống thành UNTESTED
                    self._refill_gripper()
                    # Sau flush+refill: load ngay các box EMPTY bị bỏ qua trước đó
                    # (chỉ duyệt các box phía trước box hiện tại)
                    self._load_pending_empty_boxes(limit=i)
                    empty_heads = self.gripper.empty_heads()
                    if not empty_heads:
                        self.log(f"  [WARN] Không có head trống để unload box{box_id}")
                        continue
                spare = empty_heads[0]
                if not self._unload_box(box_id, state, spare):
                    continue
                # Load UNTESTED vào box ngay — tay spare giữ PASS/FAIL, gom tiếp
                untested_h = self.gripper.untested_heads()
                if untested_h:
                    self._load_box(box_id, untested_h[0])

    # ════════════════════════════════════════════
    # VÒNG LẶP CHÍNH
    # ════════════════════════════════════════════
    def _loop(self):
        self.log("=" * 56)
        self.log("  SCHEDULER STARTED")
        self.log("=" * 56)

        cycle = 0
        while self._running:
            cycle += 1
            self.log(f"── CYCLE {cycle:04d} " + "─" * 32)

            # BƯỚC 1: fill tay UNTESTED trước khi xử lý box
            self._refill_gripper()

            # BƯỚC 2: duyệt box theo thứ tự — load EMPTY / unload DONE
            self._process_boxes()

            # BƯỚC 3: gom đủ PASS/FAIL rồi → place về tray 1 lượt
            self._place_all_tested()

            # BƯỚC 4: kiểm tra CHANGE
            if self._should_change():
                self._do_change()

            # BƯỚC 5: refill toàn bộ tay trống thành UNTESTED
            # (tái đánh giá reserve vì trạng thái box có thể đã đổi ở BƯỚC 2)
            self._refill_gripper()

            # BƯỚC 5.5: load lại các box EMPTY bị bỏ qua trong cycle này
            # (xảy ra khi unload xong nhưng lúc đó chưa có head UNTESTED)
            self._load_pending_empty_boxes()

            # BƯỚC 6: refill lại tay vừa bị consume bởi BƯỚC 5.5
            self._refill_gripper()

            self.ui_update()
            time.sleep(POLL_INTERVAL)

        self.log("[SCHEDULER] Loop kết thúc.")

    # ── Public API ───────────────────────────────
    def start(self):
        self._running = True
        if self._run_started_at is None:
            self._run_started_at = time.time()

        threading.Thread(
            target=self._loop,
            daemon=True,
            name="scheduler-loop"
        ).start()

        self.box_scanner.start()

    def stop(self):
        self._running = False
        if self._run_started_at is not None:
            self._active_seconds += time.time() - self._run_started_at
            self._run_started_at = None

        self.box_scanner.stop()

        if self.robot:
            self.robot.close()

    def _elapsed_active_seconds(self) -> float:
        """Tổng thời gian scheduler thực sự CHẠY (loại trừ lúc Stop).

        Dùng làm mẫu số tính tốc độ test — Stop lâu để bảo trì không làm
        tụt số "tốc độ" hiển thị so với thực tế.
        """
        total = self._active_seconds
        if self._run_started_at is not None:
            total += time.time() - self._run_started_at
        return total

    def get_snapshot(self) -> dict:
        elapsed = self._elapsed_active_seconds()

        box_metrics = []
        for i in range(BOX_COUNT):
            tested = self.box_tested_count[i]
            passed = self.box_pass_count[i]
            rate_per_hour = (tested / elapsed * 3600) if elapsed > 0 else 0.0
            pass_pct = (passed / tested * 100) if tested > 0 else None
            box_metrics.append({
                "tested": tested,
                "pass": passed,
                "rate_per_hour": rate_per_hour,
                "pass_pct": pass_pct,
            })

        total_tested = sum(self.box_tested_count)
        total_pass = sum(self.box_pass_count)
        system_metrics = {
            "tested": total_tested,
            "pass": total_pass,
            "rate_per_hour": (total_tested / elapsed * 3600) if elapsed > 0 else 0.0,
            "pass_pct": (total_pass / total_tested * 100) if total_tested > 0 else None,
            "elapsed_sec": elapsed,
        }

        return {
            "box_states"  : list(self.box_states),
            "box_boards"  : dict(self.box_boards),
            "box_enabled" : list(self.box_enabled),
            "gripper"     : [(h.head_id, h.board) for h in self.gripper.heads],
            "gripper_enabled": [h.enabled for h in self.gripper.heads],
            "tray1_slots" : list(self.tray1.slots),
            "tray2_slots" : list(self.tray2.slots),
            "ng_count"    : len(self.ng_list),
            "stats"       : dict(self.stats),
            "box_metrics" : box_metrics,
            "system_metrics": system_metrics,
        }