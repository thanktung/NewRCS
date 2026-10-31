"""
InitSettings.py — Đọc thông số trạm từ station.ini, tính các giá trị dẫn
xuất, và validate so với giới hạn phần cứng tối đa của hệ thống.

Khi chuyển sang trạm khác: CHỈ SỬA station.ini (không cần biết Python).
Không cần đụng vào file này hay scheduler.py/ui.py.

File này export ra đúng các tên hằng số như config.py cũ, nên chỗ dùng
chỉ cần đổi `from config import ...` → `from InitSettings import ...`.
"""

import configparser
from pathlib import Path

_INI_PATH = Path(__file__).parent / "station.ini"
_FIXTURE_IP_PATH = Path(__file__).parent / "FixtureIP.ini"

# ════════════════════════════════════════════
# GIỚI HẠN TỐI ĐA CỦA HỆ THỐNG (phần cứng/protocol) — KHÔNG sửa khi đổi
# trạm. Đây là trần cứng để station.ini không thể khai vượt quá năng lực
# thiết kế của robot/gripper/tray.
# ════════════════════════════════════════════
MAX_BOX_COUNT      = 30
MAX_GRIPPER_HEADS  = 15
MAX_TRAY_COLS      = 20
MAX_TRAY_ROWS      = 20


def _load() -> configparser.ConfigParser:
    if not _INI_PATH.exists():
        raise FileNotFoundError(
            f"Không tìm thấy {_INI_PATH}. Cần tạo file station.ini cùng "
            f"thư mục với InitSettings.py (xem station.ini mẫu)."
        )
    cfg = configparser.ConfigParser()
    # Giữ nguyên hoa/thường của key — mặc định configparser lowercase hết,
    # sẽ làm hỏng nhãn hiển thị trong [layout] (vd "Side A" -> "side a").
    cfg.optionxform = str
    cfg.read(_INI_PATH, encoding="utf-8")
    return cfg


def _parse_range(spec: str) -> range:
    """'25-30' -> range(25, 31)"""
    start, end = spec.split("-")
    return range(int(start.strip()), int(end.strip()) + 1)


_cfg = _load()

# ════════════════════════════════════════════
# KẾT NỐI MẠNG
# ════════════════════════════════════════════
BOX_HOST       = _cfg.get("network", "box_host")
BOX_START_PORT = _cfg.getint("network", "box_start_port")
ROBOT_HOST     = _cfg.get("network", "robot_host")
ROBOT_PORT     = _cfg.getint("network", "robot_port")

# ════════════════════════════════════════════
# QUY MÔ TRẠM — số lượng thiết bị vật lý
# ════════════════════════════════════════════
BOX_COUNT     = _cfg.getint("scale", "box_count")
GRIPPER_HEADS = _cfg.getint("scale", "gripper_heads")

# ════════════════════════════════════════════
# ĐỊA CHỈ TỪNG BOX — box thật ngoài hiện trường có IP:port riêng, ghi
# CỨNG trong FixtureIP.ini (mỗi dòng "box_id = ip:port"). Box nào không
# khai trong FixtureIP.ini thì fallback về địa chỉ mô phỏng (box_host +
# box_start_port) để chạy BoxSimulator.py lúc test.
# scheduler.py dùng BOX_ADDRESS[box_id] -> (host, port) thay vì tự tính.
# ════════════════════════════════════════════
def _load_fixture_ip() -> dict:
    """Đọc FixtureIP.ini. Trả về dict box_id -> (host, port) cho box có
    khai IP:port cứng. Nếu file không tồn tại hoặc [fixtures] trống/thiếu,
    trả về dict rỗng — mọi box sẽ dùng địa chỉ mô phỏng."""
    if not _FIXTURE_IP_PATH.exists():
        return {}
    fcfg = configparser.ConfigParser()
    fcfg.optionxform = str
    fcfg.read(_FIXTURE_IP_PATH, encoding="utf-8")
    overrides = {}
    if fcfg.has_section("fixtures"):
        for box_id_str, value in fcfg.items("fixtures"):
            box_id = int(box_id_str)
            if ":" not in value:
                raise ValueError(
                    f"FixtureIP.ini: box {box_id_str} = '{value}' thiếu port. "
                    f"Bắt buộc ghi đúng dạng ip:port, vd 192.168.1.101:6100."
                )
            ip, port_str = value.rsplit(":", 1)
            overrides[box_id] = (ip.strip(), int(port_str.strip()))
    return overrides


_fixture_overrides = _load_fixture_ip()

BOX_ADDRESS: dict[int, tuple[str, int]] = {}
for _bid in range(1, BOX_COUNT + 1):
    if _bid in _fixture_overrides:
        BOX_ADDRESS[_bid] = _fixture_overrides[_bid]       # IP:port cứng
    else:
        BOX_ADDRESS[_bid] = (BOX_HOST, BOX_START_PORT + _bid - 1)  # mô phỏng

# ════════════════════════════════════════════
# TRAY — kích thước vật lý (hàng × cột)
# ════════════════════════════════════════════
TRAY_COLS  = _cfg.getint("tray", "cols")
TRAY_ROWS  = _cfg.getint("tray", "rows")
TRAY_SLOTS = TRAY_COLS * TRAY_ROWS   # tự tính, không sửa trực tiếp trong ini

# Sức chứa NG tray — để trống trong ini = mặc định dùng bằng tray input
_ng_raw = _cfg.get("tray", "ng_tray_slots", fallback="").strip()
NG_TRAY_SLOTS = int(_ng_raw) if _ng_raw else TRAY_SLOTS

# ════════════════════════════════════════════
# LearnUI — chia box hiển thị thành các khu vực (theo vị trí lắp đặt thực tế)
# Mỗi phần tử: (nhãn hiển thị, dải box_id thuộc khu đó).
# Tổng các dải PHẢI khớp đúng 1..BOX_COUNT, không thiếu/thừa/trùng.
# ════════════════════════════════════════════
BOX_LAYOUT = [
    (label, _parse_range(rng)) for label, rng in _cfg.items("layout")
]

# ════════════════════════════════════════════
# THỜI GIAN / TIMEOUT
# ════════════════════════════════════════════
POLL_INTERVAL      = _cfg.getfloat("timing", "poll_interval")
ROBOT_RECV_TIMEOUT = _cfg.getfloat("timing", "robot_recv_timeout")
ROBOT_MAX_RETRIES  = _cfg.getint("timing", "robot_max_retries")
BOX_RECV_TIMEOUT   = _cfg.getfloat("timing", "box_recv_timeout")

# ════════════════════════════════════════════
# ÁNH XẠ TỌA ĐỘ — CHỈ CẦN SỬA NẾU ROBOT THẬT DÙNG QUY ƯỚC KHÁC
# ════════════════════════════════════════════
# Mặc định scheduler gửi slot dạng số phẳng (0..TRAY_SLOTS-1) trong lệnh
# PICK/PLACE, vd "PICK:1,7,2;" = tray1, slot phẳng số 7, head 2.
# Nếu robot thật cần tọa độ (hàng, cột) thay vì số phẳng, thêm hàm quy đổi
# ở đây rồi gọi tại nơi tạo lệnh trong scheduler.py (_pick_next, _place_board):
#
#   def slot_to_rowcol(slot: int) -> tuple[int, int]:
#       return slot // TRAY_COLS, slot % TRAY_COLS


# ════════════════════════════════════════════
# TỰ KIỂM TRA — phát hiện ngay lỗi khai config sai khi đổi trạm
# ════════════════════════════════════════════
assert BOX_COUNT <= MAX_BOX_COUNT, (
    f"station.ini: box_count={BOX_COUNT} vượt giới hạn tối đa "
    f"MAX_BOX_COUNT={MAX_BOX_COUNT}."
)
assert GRIPPER_HEADS <= MAX_GRIPPER_HEADS, (
    f"station.ini: gripper_heads={GRIPPER_HEADS} vượt giới hạn tối đa "
    f"MAX_GRIPPER_HEADS={MAX_GRIPPER_HEADS}."
)
assert TRAY_COLS <= MAX_TRAY_COLS and TRAY_ROWS <= MAX_TRAY_ROWS, (
    f"station.ini: tray {TRAY_COLS}x{TRAY_ROWS} vượt giới hạn tối đa "
    f"{MAX_TRAY_COLS}x{MAX_TRAY_ROWS}."
)

_covered = sorted(bid for _, rng in BOX_LAYOUT for bid in rng)
assert _covered == list(range(1, BOX_COUNT + 1)), (
    f"[layout] trong station.ini không khớp box_count={BOX_COUNT}: "
    f"phải phủ đúng 1..{BOX_COUNT}, hiện đang phủ {_covered}. "
    f"Kiểm tra lại các dải start-end trong [layout] của station.ini."
)

_bad_box_ids = sorted(b for b in _fixture_overrides if not (1 <= b <= MAX_BOX_COUNT))
assert not _bad_box_ids, (
    f"FixtureIP.ini: box_id {_bad_box_ids} nằm ngoài phạm vi tối đa "
    f"1..{MAX_BOX_COUNT} (MAX_BOX_COUNT). Kiểm tra lại [fixtures] trong FixtureIP.ini."
)
