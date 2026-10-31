"""Giá trị mặc định của mọi cài đặt (config/settings.json được deep-merge đè lên đây).

Thêm cài đặt mới ở đây trước (kèm comment nói nó làm gì), rồi đọc bằng cfg["section"]["key"].
"""

DEFAULTS = {
    # Định danh trạm; dùng để đặt tên bảng MySQL giống hệt RCS cũ.
    "identity": {
        "bu": "",
        "model": "Model",
        "stations": ["Station1"],
        "local_ip": "",              # "" = tự tìm địa chỉ 10.x.x.x đầu tiên
    },

    # Database MySQL của dashboard. 'enabled' thay cho cờ FE/Updata trong Setting.ini cũ.
    "mysql": {
        "enabled": False,
        "host": "10.169.100.78",
        "port": 3306,
        "user": "root",
        "database": "rcs_dashboard",
        "password_env": "RCS_DB_PASSWORD",     # mật khẩu đọc từ biến môi trường này
        "connect_timeout_s": 5,
        "flush_interval_s": 2.0,
    },
    "outbox_path": "data/outbox.sqlite",       # bộ đệm cục bộ: không mất dữ liệu khi MySQL ngừng

    "employee": {
        "url": "http://10.169.96.12/WS_ESD/CheckEmpRightWithEsd.asmx",
        "timeout_s": 30,
        "check_start": "2026-01-01 00:00:00",
        "check_end": "2050-12-28 23:59:59",
        "departments_path": "config/departments.json",   # mã bộ phận -> cấp 1..5 (+ mật khẩu chung)
        "offline_demo": False,
        "auto_logout_s": 180,          # người vận hành bị đăng xuất sau khoảng này kể từ lúc đăng nhập (0 = không bao giờ)
        "auto_logout_idle": False,     # True: tính từ lần dùng chuột / phím cuối thay vì từ lúc đăng nhập
    },

    "bridge": {"host": "127.0.0.1", "port": 5600, "token_env": "RCS_BRIDGE_TOKEN",
               "default_override": 10},

    "ats": {
        "heartbeat_s": 0.5,
        "connect_timeout_s": 3.0,
        "retry_s": 2.0,
        # số fixture -> nơi chương trình ATS của nó đang lắng nghe
        "fixtures": {
            "1": {"host": "127.0.0.1", "port": 8888, "station": "Station1"},
        },
    },

    # MỘT End Effector duy nhất của robot và các tool trên nó (xem rcs2/devices/end_effector.py):
    #   "heads"   các cụm hút: mỗi cụm có van + xy lanh + cảm biến áp suất, nối vào I/O robot  (rcs2/devices/heads.py)
    #   "scanner" đầu đọc mã vạch Keyence                                                      (rcs2/devices/scanner.py)
    #   "laser"   kiểm tra bằng laser IL-1000                                                  (rcs2/devices/laser.py)
    # Được các bước sequence {"ee": "heads" | "scanner" | "laser", ...} dùng
    "end_effector": {},

    # Kích thước (hàng x cột) của tray Input và tray NG, CHỈ đặt ở đây: {"input": {"rows": 5, "cols": 8}, "ng": {...}}.
    # Tray OUTPUT tùy chọn cho hàng đạt ("output1", rồi "output2" khi tray đầu đã đầy): không có chúng thì hàng đạt
    # được trả về ô trống đầu tiên của tray Input.
    # Không có mặc định: tray không khai báo thì không hiển thị / không đếm.
    "trays": {},

    # Khởi động chương trình robot qua tín hiệu UOP (rcs2/robot/uop.py): rsr = chương trình RSR nào (1 -> RSR0001, UI[9]),
    # pulse_s = độ rộng xung UI, reset_wait_s / run_wait_s / stop_wait_s = thời gian chờ UO[6] FAULT = 0 / UO[3] PROGRUN = 1 / UO[3] PROGRUN = 0;
    # monitor_s = chu kỳ đọc UO[3] PROGRUN để biết chương trình robot có đang chạy không
    "robot_start": {"rsr": 1, "pulse_s": 0.3, "reset_wait_s": 3.0, "run_wait_s": 5.0, "stop_wait_s": 3.0, "poll_s": 0.05,
                    "monitor_s": 0.5},

    # Cách robot phục vụ các box (rcs2/core/flow.py): nhiều box, nhiều tay hút: planner lấy hàng từ tray Input, đổi hàng ở các box rồi cất
    # về (test tối đa 3 lần, mỗi lần ở một box khác). Chỉ đặt được các khóa dưới đây; mọi thứ khác (kích thước tray,
    # điểm dạy head_k_at_O / input_O.. / ng_O.. / fixture_N) nằm ở "trays" và sequences.json -> points.
    "flow": {
        "max_attempts": 3,             # số lần test mỗi sản phẩm, mỗi lần ở một box khác, sau đó vào tray NG
        "keep_free_heads": 1,          # số tay hút để trống để lấy hàng đã test ra khỏi box
        "max_pick": 8,                 # số sản phẩm lấy trong một lần tới tray (<= số tay hút)
        "max_sort": 8,                 # số sản phẩm cất trong một lần tới tray
        "pick_ahead": 0,               # số sản phẩm lấy thêm ngoài số box đang chờ
        "top_up_when_idle": True,      # lấy hàng khi mọi box đều đang test
        "fill_heads": True,            # tới tray thì nạp đầy MỌI tay trống (trừ keep_free_heads) thay vì chỉ lấy đủ cho các box đang chờ
        "scan": True,                  # đọc mã vạch từng sản phẩm trước khi hút (cần end_effector.scanner)
        "override": None,              # tốc độ (%) của các lần di chuyển; None = bridge.default_override
        "check_timeout_s": 1.0,        # thời gian cho cảm biến áp suất sau khi hút / nhả
        "via_tray": "",                # điểm dạy tùy chọn mà robot đi qua khi tới tray / tới các box
        "via_fixtures": "",
        # Sau khi ĐẶT XUỐNG một sản phẩm (box / tray Input / tray NG) đầu laser IL-1000 được đưa qua `offsets` (2 điểm đo, x y z mm
        # trong hệ tọa độ của chỗ đặt) và phải báo GO ở cả hai, nếu không thì sản phẩm bị nghiêng (alarm 9204). Cần end_effector.laser và
        # điểm dạy laser_at_O. places: box | input | output | ng.
        "laser_check": {"enabled": False, "places": ["box", "input", "output"], "offsets": [[-15, 0, 0], [15, 0, 0]], "timeout_s": 1.0},
        "stop_robot_on_drop": True,    # một tay đánh rơi sản phẩm trên đường đi: dừng chạy VÀ dừng chương trình robot (alarm 9208)
    },

    "consecutive_ng": {"limit": 3, "stop_fixture": True},

    "engine": {
        "auto_start_test": True,       # gửi CtoT_placeDUTOK cho ATS ngay sau khi đặt sản phẩm vào box
        "send_dut_out": False,         # gửi DUT_OUT cho ATS sau khi lấy sản phẩm đã test ra
        "test_timeout_s": 300,         # nâng alarm 9010 khi quá thời gian này mà chưa có kết quả
        "sequences_path": "config/sequences.json",
    },
}
