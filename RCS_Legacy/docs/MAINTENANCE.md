# Bảo trì & mở rộng RCS

## 1. Chạy và kiểm thử

```powershell
cd D:\Travis\Test-Station\RCS\RCS
..\.venv\Scripts\python.exe main.py                       # chạy ứng dụng
..\.venv\Scripts\python.exe -m unittest discover -s tests -t .   # toàn bộ test (~15 s)
..\.venv\Scripts\python.exe -m unittest tests.test_scheduler     # một nhóm test
```

Chạy thử không cần phần cứng:

```powershell
python sim\robot_simulator.py --protocol legacy            # hoặc v2
python sim\box_simulator.py --count 30 --start-port 5001
python main.py                                             # station.ini: mode = sim
```

Test không dùng pytest; chỉ cần Python + (cho `test_ui_smoke`) PySide6. Nếu thiếu PySide6, test UI tự bỏ qua.

## 2. Tham chiếu `station.ini`

| Mục / khoá | Mặc định | Ý nghĩa |
|---|---|---|
| `[system] mode` | `sim` | `sim`: box ở `box_host:box_start_port+i-1`. `real`: box dùng IP trong `FixtureIP.ini` (box không có trong file → rơi về địa chỉ sim) |
| `[system] station_name` | `Station` | Tên hiển thị |
| `[network] robot_host/robot_port` | | Địa chỉ chương trình Fanuc |
| `[scale] box_count` | | 1..30 |
| `[scale] gripper_heads` | | 2..15 (luôn chừa 1 head trống nên cần ≥ 2) |
| `[tray] cols/rows/ng_tray_slots` | | ≤ 20×20; NG trống = cols×rows |
| `[layout]` | | Nhóm box trên UI; phải phủ đúng 1..box_count |
| `[timing] poll_interval` | 0.2 | Chu kỳ an toàn của vòng lặp (bình thường được đánh thức ngay bởi sự kiện) |
| `[timing] robot_recv_timeout` | 30 | Thời gian tối đa chờ `DONE` của một lệnh robot |
| `[timing] box_recv_timeout` | 5 | Chờ phản hồi `OK/BUSY` của box |
| `[timing] box_connect_timeout / box_reconnect_backoff` | 3 / 2 | Kết nối box; backoff nhân đôi đến 30 s |
| `[timing] robot_max_retries` | 3 | **Không còn tác dụng** (không gửi lại lệnh). Giữ lại để file cũ vẫn đọc được |
| `[robot] protocol` | `legacy` | `legacy` \| `v2` |
| `[robot] ack_timeout` | 3 | v2: chờ `ACK` |
| `[robot] batch_enabled / batch_max_items` | 0 / 4 | v2: gộp nhiều item mỗi lệnh |
| `[robot] heartbeat_interval` | 0 | v2: giây giữa các `STATUS`; 0 = tắt |
| `[policy] place_policy` | `tray1` | `tray1`: PASS vào ô trống đầu của tray 1. `origin`: PASS về đúng ô đã lấy |
| `[policy] box_fail_streak_limit` | 0 | Tự tắt box sau N lần FAIL liên tiếp (0 = không) |
| `[policy] retest_ng` | 0 | FAIL lần đầu → test lại ở box khác trước khi chốt NG |
| `[watchdog] test_timeout_sec / ready_timeout_sec` | 0 | Cảnh báo box ở `testing` / `ready_for_test` quá lâu |
| `[paths] state_file/log_dir/results_dir` | | Để trống = mặc định |

## 3. Triển khai trạm mới

1. Sửa `station.ini`: `box_count`, `gripper_heads`, `[tray]`, `[layout]`, `robot_host`, `station_name`.
2. Điền IP:port thật vào `FixtureIP.ini`, đặt `mode = real`.
3. Chạy thử `mode = sim` trước. Chỉ khi OK mới chuyển `real`.
4. `legacy` → `v2` theo `docs/PROTOCOL_V2.md` mục 10 khi chương trình robot đã nâng cấp.

## 4. Cách thêm…

### 4.1 Một lệnh robot mới (ví dụ `WASH:head`)

1. `protocol/commands.py`: thêm hằng `WASH`, đăng ký trong `ITEM_ARITY` (số int mỗi item), `MOTION_COMMANDS`
   (nếu có chuyển động), `BATCHABLE` (nếu gộp được) và hàm dựng `wash(*items)`.
2. `robot_legacy.py` / `robot_v2.py`: `encode` đã tổng quát — thường không cần sửa.
3. `core/scheduler.py`: thêm một cặp `plan` + `apply` (xem `_plan_loads` / `_apply_load`) rồi gọi
   `self._run_ops(C.WASH, ops)` ở bước phù hợp trong `_run_cycle`.
4. Thêm test trong `tests/test_protocol.py` (encode/parse) và `tests/test_scheduler.py` (hành vi).
5. Cập nhật `docs/PROTOCOL_V2.md` bảng lệnh + `sim/robot_simulator.py` nếu cần mô phỏng.

### 4.2 Một mã lỗi robot mới

- Chỉ cần robot gửi mã đó: RCS hiển thị nguyên văn và vào FAULT.
- Muốn xử lý riêng (không FAULT): thêm hằng vào `ErrorCode`, rồi truyền `recover={ErrorCode.X: handler}`
  khi tạo `_Op` (xem `_recover_no_part`). Handler phải cập nhật mô hình cho khớp thực tế.

### 4.3 Chính sách đặt board / đổi khay mới

1. `core/policies.py`: lớp kế thừa `PlacePolicy` (`pass_slot`, `can_change`). Chỉ **đọc** scheduler.
2. Thêm vào `PLACE_POLICIES` (cùng file) **và** vào tuple `PLACE_POLICIES` trong `config.py`.
3. Test: thêm một test "không deadlock" tương tự `test_tray_full_does_not_deadlock`.

### 4.4 Thứ tự phục vụ box khác

Viết lớp kế thừa `BoxPriorityPolicy.order(boxes)` và truyền `Scheduler(..., priority=MyPolicy())`.

### 4.5 Loại robot/đường truyền khác

Cài đúng bộ phương thức mà scheduler dùng — `connect, reconnect, close, execute(cmd), query_status(),
connected, supports_batch` — rồi trả về từ một factory mới (xem `clients/factory.py`). `tests/fakes.py::FakeRobot`
là ví dụ nhỏ nhất.

## 5. Xử lý sự cố

| Triệu chứng | Nguyên nhân thường gặp | Kiểm tra |
|---|---|---|
| Banner đỏ "Robot … failed: no DONE" | Robot không trả lời trong `robot_recv_timeout` | Robot đang chạy lệnh dài? Mạng? Log `logs/rcs.log` xem dòng `->` cuối cùng |
| Banner đỏ "Robot refused … CODE" | Robot trả `ERR` | Xem mã lỗi (`docs/PROTOCOL_V2.md` mục 4); sửa tay trạng thái → **Xác nhận lỗi** |
| Banner đỏ "Box N answered 'BUSY' to LOAD" | Phần mềm và fixture lệch trạng thái | Kiểm tra fixture; sửa tay box N (chuột phải) cho khớp |
| Vàng "Box N connection lost" | Mất mạng tới fixture | Hệ thống tự kết nối lại; box bị loại khỏi lịch trong lúc mất |
| Vàng "Box N reports EMPTY but software had … inside" | Ai đó lấy board ra tay | Kiểm tra số liệu; board đã bị bỏ khỏi mô hình |
| Vàng "NG tray is FULL" | NG tray đầy | Đổ NG tray → **Đã đổ NG tray** → Resume |
| Hệ thống chạy nhưng không làm gì | Mọi head giữ board PASS không đặt được / hết box | Log mức DEBUG: `no free head …`; xem `place_policy`, tray đầy |
| Start báo lỗi kết nối robot | Sai `robot_host/port`, robot chưa chạy chương trình | `ping`, chạy `sim\robot_simulator.py` để loại trừ phía PC |
| Số liệu lệch sau khi crash | — | Khởi động lại → chọn **Yes** ở hộp khôi phục; nếu đã xếp lại hàng tay → **No** rồi sửa tay |

Log: `logs/rcs.log` (xoay vòng 5 × 2 MB). Kết quả test: `logs/results_YYYYMMDD.csv`.
Trạng thái: `station_last_state.json` (có thể xóa để bắt đầu sạch).

## 6. Quy ước code

- Comment trong code viết tiếng Anh; tài liệu tiếng Việt.
- Không dùng biến toàn cục cho cấu hình: truyền `StationConfig`.
- Không `assert` để kiểm tra cấu hình / dữ liệu vào; dùng exception (`ConfigError`, `ValueError`).
- Không giữ `Scheduler._lock` khi gọi robot/box. `apply()` tự khóa phần sửa mô hình.
- Mọi sửa lỗi scheduler đi kèm một test tái hiện trong `tests/test_scheduler.py`.
- `legacy/` chỉ để tham khảo, không import từ đó.
