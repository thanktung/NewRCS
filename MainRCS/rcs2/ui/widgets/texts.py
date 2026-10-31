"""Vietnamese labels for the engine constants (the engine itself keeps English constants)."""
from ...core import engine as E


STATE_TEXT = {E.NO_USED: "Không dùng", E.OFFLINE: "Mất kết nối", E.IDLE: "Sẵn sàng",
              E.LOADING: "Đang nạp", E.TESTING: "Đang test", E.RESULT: "Kết quả", E.UNLOADING: "Đang lấy ra",
              E.FAULT: "Lỗi"}
RESULT_TEXT = {"WARNING": "CẢNH BÁO"}
