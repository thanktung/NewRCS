# Module `rcs2/runtime` — lắp ráp và điều phối (không có Qt)

## Làm gì / không làm gì
- **Làm:** từ `settings` dựng và nối mọi thành phần (engine, bridge client, ATS client, End Effector, outbox/DB, đăng nhập), khởi
  động / dừng các thread nền, và cung cấp cho UI các **thao tác của người vận hành** (đăng nhập, chạy/dừng chương trình robot,
  jog, dạy điểm, đầu hút, máy quét, laser...).
- **Không làm:** không có logic lịch chạy (đó là `core/engine.py`), không giao tiếp giao thức thô (đó là `robot/`, `ats/`),
  không vẽ giao diện (đó là `ui/`). `Runtime` chỉ **nối** và **bảo vệ** (kiểm tra điều kiện trước khi cho robot làm gì).
- Không import `PySide6` (có test kiến trúc canh).

## File
`Runtime` là một lớp, chia thành các mixin để mỗi file chỉ chứa một nhóm việc:

| File | Lớp | Nội dung |
|---|---|---|
| `runtime.py` | `Runtime` | `__init__` (dựng mọi thứ), `start()`, `stop()`, `_alive_loop`, `reset_tray`, ghi log, đường dẫn, MySQL writer |
| `session.py` | `SessionMixin` | `login`, `logout`, `touch`, `session_remaining`, `check_auto_logout` |
| `bridge_link.py` | `BridgeLinkMixin` | giữ kết nối bridge/robot (`_bridge_supervisor`), **theo dõi UO[3] PROGRUN** (`_program_monitor`), `_need_program_running`, `robot_connect` |
| `robot_ops.py` | `RobotOpsMixin` | `robot_start_program`, `robot_stop_program`, `robot_gosafehere`, `manual_rmove`, `manual_move_to`, `teach_point`, `robot_fault_clear`, `_manual_motion`, `_manual_guard` |
| `end_effector_ops.py` | `EndEffectorOpsMixin` | `heads_action`, `heads_status`, `scan_test`, `scan_stop`, `laser_status` |
| `flow_ops.py` | `FlowOpsMixin` | **luồng tray:** `flow_groups`, `flow_taught`, `flow_status` (điểm nào chưa dạy / sai), `flow_cell_pose`, `flow_point_pose`, `flow_head_offsets`, `flow_move_head_to_cell/point` (kiểm tra hiệu chuẩn bằng đúng phép tính của lúc chạy), `reset_flow` |

## Thread do Runtime tạo
`engine` (một thread xử lý sự kiện), `bridge-supervisor` (3 s/lần kiểm tra kết nối), `program-monitor` (đọc UO[3] mỗi
`robot_start.monitor_s`), `alive` (nhịp tim 60 s cho `ErrorTracker`), `data-sink` (upload outbox), mỗi ATS một thread, mỗi job robot
một thread. Các hàm blocking của Runtime (`robot_start_program`, `teach_point`...) **phải gọi từ thread worker**, không gọi trong
thread giao diện (UI dùng `MainWindow._run_task`).

## Quy tắc bất biến (đừng phá)
1. **Mọi thao tác robot thủ công đi qua `_manual_motion`**: giữ khóa (một thao tác một lúc), từ chối khi đang chạy / có job, **bắt buộc
   UO[3] PROGRUN = 1**, arm bridge đúng cho lệnh đó rồi disarm. Chỉ `robot_start_program` truyền `needs_program=False`.
2. **Không bao giờ ghi R[1] khi chương trình robot dừng.** Lệnh ghi lúc đó nằm lại trong R[1] và bị thực hiện khi chạy lại. Mọi hàm
   thao tác robot mới phải gọi `_need_program_running()` (trực tiếp hoặc qua `_manual_motion`).
3. **Dừng robot luôn được phép** và không đi qua khóa thủ công. `robot_stop_program` đặt `_uop_abort` (hủy lần chạy đang dở), xung
   SDI[4], tắt SDI[1..3], rồi `engine.stop_run()` + `engine.wait_processed()` để lệnh disarm của engine xong **trước khi** trả về.
4. `Runtime.__init__` kiểm tra sớm `trays` và `robot_start` để lỗi cấu hình báo ngay lúc khởi động.
5. Bí mật (mật khẩu DB, token bridge) lấy từ biến môi trường, không ghi vào file.

## Hướng dẫn sửa
### Thêm một thao tác robot cho người vận hành
1. Viết phương thức trong mixin phù hợp (`robot_ops.py` cho robot, `end_effector_ops.py` cho đầu hút / scanner / laser).
2. Nếu thao tác chạm robot: bọc bằng `self._manual_motion(fn)` (mặc định đã đòi UO[3] = 1) và ghi log bằng `self._log_manual(...)`.
   Nếu chỉ đọc nhưng cũng chạm robot: gọi `self._need_program_running()` đầu hàm.
3. Thêm nút trong `ui/windows/manual_dialog.py` hoặc `ui/widgets/robot_panel.py`, gọi qua `_run` / `_run_task` (thread worker),
   và khóa nút khi `snap["program_running"] is False`.
4. Test: bổ sung vào `tests/runtime/test_program_state.py` (mẫu `test_every_robot_operation_is_refused_while_the_program_is_off`).

### Hiệu chuẩn luồng tray
Điểm dạy bằng `teach_point` (lưu **đủ 6 giá trị** x y z w p r + CONFIG / UF / UT vào `sequences.json` → `points`, engine thấy ngay). Tên điểm: `head_<k>_at_O`, `scanner_at_O`, `input_O/X/Y`, `ng_O/X/Y`, `fixture_<n>` (danh sách đầy đủ: `flow_groups()`). Các hàm `flow_move_*` đi qua `_manual_motion` như mọi thao tác robot (đòi UO[3] = 1, từ chối khi đang chạy).

### Thêm một mixin / nhóm thao tác mới
Tạo `runtime/<ten>.py` với lớp `XxxMixin`, thêm vào danh sách cơ sở của `Runtime` trong `runtime.py`. Mixin chỉ dùng các thuộc tính
đã có của `Runtime` (`self.bridge`, `self.engine`, `self.ee`, `self.cfg`, `self.operator`, `self._emit_log`...).

### Thêm thành phần mới vào `__init__`
Dựng trong `Runtime.__init__`, dừng trong `stop()` (theo thứ tự ngược lại), và nếu có thread thì tạo trong `start()` với
`self._stop.wait(chu_kỳ)` làm vòng lặp để thoát gọn.

### Đổi thời gian tự đăng xuất / cách tính
`session.py` (`session_remaining`, `check_auto_logout`); cài đặt `employee.auto_logout_s`, `employee.auto_logout_idle`.

## Test
`python run_tests.py runtime` — gồm `test_auto_logout`, `test_manual` (jog/điểm/dạy điểm với simulator), `test_program_state`
(chặn khi UO[3] = 0, chạy/dừng với simulator) và `test_runtime_demo` (cả một chu kỳ chạy với demo).
Test robot (`tests/robot/test_uop.py`) cũng dùng `Runtime` cho `robot_start_program` / `robot_stop_program`.
