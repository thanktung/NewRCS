# scanBox.py
"""
BoxScanner — KHÔNG còn poll (GET) định kỳ nữa.

Mỗi BoxClient tự chạy 1 thread lắng nghe (listener) trên socket của nó.
Box (BoxSimulator.py) tự chủ động gửi 1 dòng trạng thái mới lên socket
bất cứ khi nào state của nó đổi (kể cả ngay lúc vừa kết nối) — không
cần PC phải hỏi GET nữa.

BoxScanner chỉ có nhiệm vụ:
  - khởi động / dừng listener của toàn bộ box_clients
  - nhận callback mỗi khi có 1 box báo trạng thái mới → cập nhật
    scheduler.box_states và gọi ui_update()
"""


class BoxScanner:
    def __init__(self, scheduler, interval=None):
        # `interval` được giữ lại trong chữ ký hàm cho tương thích ngược
        # (không còn dùng, vì không còn scan theo chu kỳ nữa).
        self.scheduler = scheduler
        self._running = False

    def start(self):
        if self._running:
            return
        self._running = True

        for box in self.scheduler.box_clients:
            box.start_listener(self._on_box_state)

        self.scheduler.ui_update()

    def _on_box_state(self, box_id: int, state):
        """Callback được BoxClient gọi (từ thread listener riêng của nó)
        mỗi khi box báo trạng thái mới."""
        if not self._running:
            return
        idx = box_id - 1
        if idx < 0 or idx >= len(self.scheduler.box_states):
            return
        self.scheduler.box_states[idx] = state
        self.scheduler.log(f"[PUSH] box{box_id} → {state.value}")
        self.scheduler.ui_update()

    def stop(self):
        self._running = False
        for box in self.scheduler.box_clients:
            box.stop_listener()
