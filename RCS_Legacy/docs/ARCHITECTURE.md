# Kiến trúc RCS

## 1. Bản đồ module

```
main.py                       entry point: nối các phần, không có logic
station.ini / FixtureIP.ini   cấu hình trạm / IP của 30 fixture
rcs/
  config.py                   StationConfig (bất biến) + load + validate
  models.py                   Board, Tray, Gripper, BoxRecord, enums   (thuần dữ liệu)
  protocol/                   định dạng dây — hàm thuần, không I/O
    commands.py               RobotCommand, Reply, mã lỗi
    robot_legacy.py           giao thức cũ  (DONE:<CMD>)
    robot_v2.py               giao thức v2  (seq / ACK / DONE / ERR / batch)
    box.py                    parse trạng thái box
  clients/                    TCP
    robot_client.py           RobotGateway: 1 reader thread, route theo seq, không resend
    box_client.py             BoxClient: 1 thread/box, tự reconnect
    factory.py                TcpClientFactory (tests dùng FakeFactory)
    errors.py                 hệ thống exception
  core/
    scheduler.py              bộ não: plan → execute → apply
    state_machine.py          STOPPED/IDLE/RUNNING/PAUSING/PAUSED/FAULT
    policies.py               PlacePolicy, BoxPriorityPolicy  (điểm mở rộng)
    manual_edit.py            sửa tay khi không chạy
    metrics.py, snapshot.py
  persistence.py              ghi/đọc trạng thái (atomic)
  traceability.py             CSV mỗi lần test
  logging_setup.py            logging + file xoay vòng + handler cho UI
  ui/                         PySide6: chỉ vẽ Snapshot, gọi API công khai của Scheduler
sim/                          box_simulator.py, robot_simulator.py
tests/                        unittest (không cần cài thêm gì)
legacy/                       mã nguồn phiên bản cũ (chỉ để tham khảo)
```

**Quy tắc phụ thuộc** (mũi tên = "được phép import"):

```
ui ──▶ core ──▶ clients ──▶ protocol ──▶ models
 │       │          │
 │       └──────────┴──▶ config
 └──▶ (chỉ API công khai + Snapshot của core)
```

`models` và `protocol` không import gì khác trong dự án → test được không cần socket/Qt.
`core` không import Qt. `ui` không đụng nội bộ scheduler.

## 2. Luồng một vòng (cycle)

```
_run_cycle():
  1. refill_gripper     PICK board UNTESTED vào các head trống (luôn chừa reserve head trống)
  2. process_boxes      EMPTY → LOAD ;  DONE → UNLOAD (rồi LOAD ngay)
  3. place_all_tested   PLACE board PASS/NG về tray / NG tray
  4. change?            nếu policy.can_change → CHANGE (Tray 2 → Tray 1)
  5. refill_gripper
  6. load_empty_boxes   (+ refill) bù các box bị bỏ qua
  7. watchdog           cảnh báo box kẹt / mất kết nối
```

Mỗi bước **lập kế hoạch** thành danh sách `_Op(item, apply)` rồi `_run_ops` thực thi:

```
plan (dưới lock)  ──▶  robot.execute(cmd)  (KHÔNG giữ lock)  ──▶  apply() từng item robot đã xác nhận
```

- Không batch: mỗi `_Op` là một lệnh. Batch: tối đa `batch_max_items` item/lệnh.
- `ERR` ở item `k` → apply item `0..k-1`, phần còn lại không đổi.
- `apply()` cập nhật mô hình rồi (nếu cần) báo box (`LOAD`/`UNLOAD`) **ngoài lock**.
- Kết quả bất thường (timeout, mất kết nối, `ERR` không có handler, box từ chối) → `_Fault` → **FAULT**.

## 3. Máy trạng thái

```
STOPPED ──connect──▶ IDLE ──start──▶ RUNNING ◀─resume─┐
   ▲                   │                │  │          │
   │                   │             pause fault     PAUSED
   │                   │                ▼  │          ▲
   └──── stop / emergency_stop ───── PAUSING ──────────┘
                                         │
                       FAULT ──acknowledge_fault──▶ PAUSED
```

- **Pause**: hoàn thành lệnh robot đang chạy, rồi dừng (kết nối giữ nguyên, box vẫn cập nhật).
- **Stop**: như pause rồi ngắt hết kết nối (`STOPPED`).
- **Emergency stop**: đóng socket ngay giữa lệnh. Trạng thái vật lý lúc đó là **không xác định**.
- **FAULT**: phần mềm không còn tin vào mô hình của mình. Chỉ thoát bằng `acknowledge_fault()`
  (mở lại kết nối robot, v2: `RESET`) sau khi người vận hành đã sửa tay trạng thái cho khớp thực tế.
- Sửa tay (`manual_set_*`) chỉ được phép khi luồng scheduler thật sự rảnh
  (`STOPPED/IDLE/PAUSED/FAULT` và không đang chạy cycle).

## 4. Luồng (thread) và khóa

| Luồng | Việc | Chạm vào mô hình? |
|---|---|---|
| scheduler-loop | chạy cycle | có (dưới `_lock`) |
| robot-reader | đọc socket robot, route reply theo seq | không |
| robot-heartbeat | `STATUS` định kỳ (v2) | không (chỉ gọi `_enter_fault`) |
| box{N}-link (×30) | kết nối/nghe push từ box | có, qua `_on_box_state` (dưới `_lock`) |
| UI | vẽ, gọi API | chỉ qua API công khai |
| ui-action | start/stop/acknowledge (có thể chặn lâu) | qua API công khai |

- `_lock` (RLock) bảo vệ mô hình, **không bao giờ giữ khi chờ robot hoặc box**. Lý do: luồng
  nghe box vừa cần `_lock` (khi có push) vừa là luồng chuyển phản hồi `OK` cho lệnh đang chờ →
  giữ khóa khi chờ sẽ tự khóa chết.
- `_cycle_lock` giữ suốt một cycle; "luồng scheduler đang rảnh" ⇔ `_cycle_lock` không bị giữ.
- UI nhận thay đổi bằng cờ `dirty` (listener) + `QTimer` 10 Hz; log đi qua signal.

## 5. Tính nhất quán dữ liệu

- Mô hình chỉ thay đổi **sau khi robot xác nhận**. Không xác nhận được → FAULT, mô hình giữ nguyên.
- Snapshot ghi ra đĩa **sau mỗi thao tác robot** (ghi file tạm → `os.replace`, không bao giờ hỏng nửa chừng).
  Khởi động lại sẽ hỏi có khôi phục không. Trạng thái **box** không lưu — box tự đẩy trạng thái thật khi kết nối.
- Box báo `empty` trong khi phần mềm nghĩ có board (và không phải tiếng vọng của lệnh vừa gửi) → cảnh báo
  và bỏ board khỏi mô hình.
- Mỗi lần test xong ghi một dòng CSV (`logs/results_YYYYMMDD.csv`).

## 6. Điểm mở rộng

| Muốn… | Làm ở đâu | Chi tiết |
|---|---|---|
| Thêm chiến lược đặt board / đổi khay | `core/policies.py` | Lớp mới kế thừa `PlacePolicy`, đăng ký vào `PLACE_POLICIES`, thêm tên vào `config.PLACE_POLICIES` |
| Đổi thứ tự phục vụ box | `core/policies.py` | Lớp mới kế thừa `BoxPriorityPolicy`, truyền vào `Scheduler(priority=...)` |
| Thêm lệnh robot | `protocol/commands.py` + `robot_*.py` + `scheduler.py` | Xem `docs/MAINTENANCE.md` |
| Thêm mã lỗi robot | `protocol/commands.py::ErrorCode` | + (tuỳ chọn) `recover` handler trong scheduler |
| Loại robot / đường truyền khác | `clients/` + `factory.py` | Cài đúng giao diện của `RobotGateway`, trả về từ factory |
| Nhiều trạm | tạo nhiều `StationConfig` + `Scheduler` | Cấu hình/mô hình/kết nối không có trạng thái toàn cục. Còn dùng chung: cây logger `rcs.*` (cần thêm tên trạm vào tên logger nếu chạy nhiều trạm trong một tiến trình) và UI hiện chỉ hiển thị một trạm |
| Lưu vào DB thay vì CSV | `traceability.py` | Lớp có `record(row: dict)` |

