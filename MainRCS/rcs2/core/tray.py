"""Các tray sản phẩm của cell: tray INPUT (DUT chờ được hút), tray NG (nơi đặt DUT hỏng) và, tùy chọn, hai tray OUTPUT
(output1, output2: chỉ hàng đạt, dùng theo thứ tự này)

Mỗi tray là một lưới `rows x cols` ô và kích thước KHÔNG cố định trong code: chỉ đặt trong settings.json
(khởi động lại để áp dụng):

    "trays": {"input": {"rows": 5, "cols": 8}, "ng": {"rows": 4, "cols": 6}}

Các ô được dùng theo thứ tự đọc (từng hàng, trái sang phải, bắt đầu từ góc trên bên trái).
  input  ban đầu ĐẦY.   Mỗi DUT robot hút đi làm trống ô kế tiếp. TRỐNG = hết hàng để nạp.
  ng     ban đầu TRỐNG. Mỗi DUT NG robot đặt xuống lấp ô kế tiếp. ĐẦY = phải dọn tray.
  output1 / output2  ban đầu TRỐNG, giống ng: mỗi DUT đạt được đặt xuống lấp ô kế tiếp (output1 trước, rồi output2).
Người vận hành báo cho chương trình khi tray đã được nạp lại / dọn trống (`reset`). Trạng thái không lưu xuống đĩa: sau khi
khởi động lại, tray Input lại được coi là đầy và tray NG là trống.
"""
KINDS = ("input", "ng", "output1", "output2")
TITLES = {"input": "Tray Input", "ng": "Tray NG", "output1": "Tray Output 1", "output2": "Tray Output 2"}      # như các màn hình hiển thị
MAX_SIDE = 50


class TrayConfigError(ValueError):
    pass


def check_size(kind, rows, cols):
    """(rows, cols) là số nguyên trong khoảng 1..MAX_SIDE, nếu không thì TrayConfigError."""
    for label, v in (("số hàng", rows), ("số cột", cols)):
        if isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= MAX_SIDE:
            raise TrayConfigError("tray %s: %s phải là số nguyên từ 1 đến %d (nhận %r)" % (kind, label, MAX_SIDE, v))
    return rows, cols


class Tray:
    def __init__(self, kind, rows, cols):
        if kind not in KINDS:
            raise TrayConfigError("loại tray %r không có (input | ng | output1 | output2)" % kind)
        self.kind = kind
        self.rows, self.cols = check_size(kind, rows, cols)
        self.done = 0                         # số ô đã dùng, đếm theo thứ tự đọc

    @property
    def capacity(self):
        return self.rows * self.cols

    @property
    def exhausted(self):
        """input: không còn gì để hút. ng: không còn chỗ đặt DUT."""
        return self.done >= self.capacity

    @property
    def count(self):
        """Số DUT đang nằm trong tray lúc này (input: còn chờ, ng: đã đặt xuống)."""
        return self.capacity - self.done if self.kind == "input" else self.done

    def advance(self):
        """Dùng một ô (hút một DUT từ tray Input / đặt một DUT vào tray NG). False khi không còn ô nào."""
        if self.exhausted:
            return False
        self.done += 1
        return True

    def reset(self):
        """Người vận hành đã nạp lại tray Input / dọn trống tray NG."""
        self.done = 0

    def snapshot(self):
        return {"kind": self.kind, "rows": self.rows, "cols": self.cols, "capacity": self.capacity,
                "done": self.done, "count": self.count, "exhausted": self.exhausted}


def build_trays(cfg):
    """{"input": {"rows", "cols"}, "ng": {...}} -> {kind: Tray}. Loại nào thiếu thì đơn giản là không dùng."""
    trays = {}
    for kind, size in (cfg or {}).items():
        if str(kind).startswith("_"):
            continue
        if not isinstance(size, dict):
            raise TrayConfigError("tray %s: cần {\"rows\": n, \"cols\": n}" % kind)
        trays[kind] = Tray(kind, size.get("rows"), size.get("cols"))
    return trays

