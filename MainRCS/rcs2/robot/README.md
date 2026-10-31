# Module `rcs2/robot` — nói chuyện với robot FANUC qua bridge

## Làm gì / không làm gì
- **Làm:** client TCP/JSON tới bridge (`client.py`), hằng số giao thức (`protocol.py`), khởi động / dừng chương trình robot qua
  tín hiệu UOP (`uop.py`).
- **Không làm:** không quyết định *khi nào* robot làm gì (đó là `core`), không biết sequence. Không import module khác của `rcs2`.
- Bridge là **chương trình riêng** (`bridge32/`): nó ghi `PR[1]`, `R[2]`, `R[5]`, rồi `R[1]` = mã lệnh, chờ chương trình TP `RSR0001`
  đặt `R[1] = 0` (xong) / `-1` (lỗi). Chi tiết: `docs/robot_bridge_guide.md`.

## File
| File | Nội dung |
|---|---|
| `client.py` | `BridgeClient` (thread-safe, ping giữ arm, ghép phản hồi theo `id`), `RobotError(code, message)` |
| `protocol.py` | `PROTOCOL_VERSION`, mã lỗi `E_*`, `MOTION_CODES`, `NEEDS_TARGET`, `NEEDS_STATION`, `encode/decode` |
| `uop.py` | `RobotStarter.start()/stop()`, `normalize()` (kiểm tra `robot_start`), `StartError/StopError`, số hiệu UI/UO |

### API chính của `BridgeClient`
`connect/close`, `robot_connect`, `arm/disarm`, `fault_clear`, `alarm_clear`, `status`, `pos_read`, `r_read/r_write`,
`pr_read/pr_write`, `io_read/io_write`, `call(cmd, args)` (lệnh thô), chuyển động blocking: `move rmove gosafetarge gosafehere put get down up`.
**Trạng thái chương trình robot:** `program_running()` (đọc mới UO[3]), `refresh_program_state()` (đọc và lưu vào `program_state`:
`True/False/None`). `Runtime` đọc định kỳ; `Engine` và UI dùng `program_state`.

## Quy tắc bridge (tóm tắt)
- Lệnh `motion.*` và `io.write` cần `arm`; chỉ **một** client được arm; arm tự hủy khi client ngắt, im lặng quá `watchdog_s`, hoặc lệnh
  kết thúc bằng `ROBOT_ERROR/TIMEOUT/VERIFY_FAILED/NOT_CONNECTED/INTERNAL`.
- Mã lỗi: `BAD_REQUEST UNKNOWN_CMD NOT_AUTH FORBIDDEN NOT_CONNECTED NOT_ARMED BUSY PENDING FAULT_LATCHED LIMIT VERIFY_FAILED ROBOT_ERROR TIMEOUT INTERNAL`
  và `PROGRAM_STOPPED` (do **NewRCS tự phát**, không phải bridge: UO[3] = 0).
- Hằng số giao thức được **sao chép** trong `bridge32/bridge_simple.py` (bridge triển khai một file riêng):
  `tests/robot/test_protocol_sync.py` + `tests/simulator/test_bridge_simple.py` báo lỗi nếu hai bên lệch nhau.

## UOP: chạy / dừng chương trình robot (`uop.py`)
UI[n] nối sang **SDI[n]** (ghi bằng `io.write`), UO[n] chỉ đọc.

| Tín hiệu | Ý nghĩa | Dùng |
|---|---|---|
| UI1 / UI2 / UI3 | IMSTP / HOLD / SFSPD (mức 1 = bình thường) | chạy: bật 1; **dừng: tắt 0** |
| UI4 | CSTOPI — cycle stop | dừng: xung |
| UI5 | RESET lỗi | chạy: xung rồi chờ UO6 = 0 |
| UI6 | START | chạy: xung rồi chờ UO3 = 1 |
| UI8 | ENBL | chạy: bật 1 |
| UI9.. | RSR1.. chọn chương trình | chạy: xung (`robot_start.rsr`) |
| UO3 | PROGRUN | đọc: chương trình đang chạy |
| UO6 | FAULT | đọc |

- **Chạy** (`RobotStarter.start`): nếu UO3 đã 1 thì thôi; ghi SDI1-3 và SDI8 = 1 rồi đọc lại; xung SDI(8+rsr); xung SDI5 rồi chờ UO6 = 0;
  xung SDI6 rồi chờ UO3 = 1. Xung = ghi 1, chờ `pulse_s`, ghi 0 (luôn ghi 0 kể cả khi lỗi giữa chừng).
- **Dừng** (`RobotStarter.stop`): xung SDI4; **luôn** tắt SDI1-3 (kể cả xung lỗi); chờ UO3 = 0 (`stop_wait_s`), không thì `StopError` ("dùng E-stop").
  Đặt `abort` để lần chạy đang dở tự hủy.
- Cài đặt: `settings.json` → `robot_start` (`rsr, pulse_s, reset_wait_s, run_wait_s, stop_wait_s, poll_s, monitor_s`).

## Hướng dẫn sửa
### Thêm một lệnh bridge / một phương thức client
1. **Bridge** (`bridge32/bridge_simple.py`): thêm `def cmd_<tên_với_gạch_dưới>(self, cl, a)` trong `Bridge` (tên lệnh `a.b` → `cmd_a_b`).
   Bridge thật (FRRJIf) phải có lệnh tương ứng, nên cập nhật cả `docs/robot_bridge_guide.md`.
2. **Client** (`client.py`): thêm phương thức gọi `self.call("<lệnh>", {...})`.
3. Nếu có mã lỗi mới: thêm `E_*` vào `protocol.py`; nếu bridge cũng dùng thì bridge phải dùng đúng chuỗi (test đồng bộ canh).
4. Test: `tests/simulator/test_bridge_simple.py` (bridge) + `tests/robot/` (client / UOP).

### Thêm một mã lệnh chuyển động (R[1] = 9...)
`MOTION_CODES` (+ `NEEDS_TARGET`/`NEEDS_STATION`) trong `protocol.py` **và** trong `bridge_simple.py`, thêm phương thức vào `client.py`,
thêm bước vào `core/sequence.py` (`POSE_OPS`/`STATION_OPS`), và chương trình TP trên robot phải xử lý mã mới.

### Đổi trình tự chạy / dừng chương trình
`RobotStarter._start()` và `stop()` trong `uop.py`. Giữ nguyên các bất biến: luôn ghi lại 0 sau xung; dừng không bao giờ bị khóa;
`stop` luôn tắt SDI1-3 dù xung lỗi. Thứ tự "chọn RSR rồi reset" phụ thuộc robot thật — đổi trong `_start()` nếu robot yêu cầu khác.

### Chương trình robot dừng thì sao?
Mọi thứ ghi `R[1]` bị chặn ở `runtime` (`_need_program_running`) và `core` (`_cmd_start`, `_dispatch`, `_watch_program`).
Client không tự chặn: nó chỉ cung cấp `program_state` để các lớp trên quyết định.

## Test
`python run_tests.py robot` — `test_uop` (trình tự chạy/dừng, cấu hình, `Runtime.robot_start/stop_program` với bridge giả), `test_protocol_sync`.
Test client với bridge thật mô phỏng nằm ở `tests/simulator/`. Fixture: `tests/support/bridge.py` (`BridgeFixture`).
