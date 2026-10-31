# Kiến trúc NewRCS

Tài liệu này trả lời "các phần ghép với nhau thế nào". Muốn biết **sửa ở đâu**: `MainRCS/README.md` (bảng "Muốn sửa X thì vào đâu") và README của từng module.
Mô tả tính năng: `FEATURES.md`.

## 1. Các tiến trình và đường truyền
```
 PC vận hành (Windows)
 ┌────────────────────────────────────────┐   TCP 5600, JSON lines    ┌──────────────────────┐   FRRJIf COM    ┌──────────────┐
 │ NewRCS (Python 64-bit, PySide6)        │ ◄───────────────────────► │ bridge (Python 32-bit)│ ◄─────────────► │ robot FANUC  │
 │  ui · runtime · core · robot · ats ... │                           │  hoặc simulator       │                 │ RSR0001 (TP) │
 └───┬──────────────┬──────────────┬──────┘                           └──────────────────────┘                 └──────────────┘
     │ TCP "_CEND"  │ TCP LON/LOFF │ pymysql (qua outbox SQLite)
     ▼              ▼              ▼
  ATS từng fixture   máy quét    MySQL dashboard (bảng cũ)
```
Simulator (`MainRCS/bridge32/bridge_simple.py`) thay **cả bridge, robot, ATS của mọi fixture và máy quét** bằng một tiến trình, dùng đúng cùng giao thức.

## 2. Các lớp trong `rcs2`
```
 ui ──────────► runtime ─────────┬──► core ─────► ats (hằng số giao thức), devices (ScanCancelled)
 (Qt duy nhất)  (lắp ráp,         ├──► robot      (client bridge, UOP)
                 thao tác vận hành)├──► ats        (client ATS)
                                  ├──► devices    (End Effector)
                                  ├──► reporting  (outbox, MySQL)
                                  ├──► employee   (đăng nhập)
                                  └──► config
```
Quy tắc và test canh: `MainRCS/README.md` → "Quy tắc phụ thuộc". Nguyên tắc: **`core` không biết robot/ATS là ai** (nhận đối tượng "giống client" qua tham số), nên test được bằng đồ giả
và đổi phần cứng không đụng logic.

## 3. Thread
| Thread | Tạo bởi | Việc |
|---|---|---|
| UI (Qt) | `ui/main.py` | vẽ, `MainWindow.refresh()` 250 ms đọc `engine.snapshot()` |
| `engine` | `Engine.start` | **sở hữu toàn bộ trạng thái**, xử lý từng sự kiện (ATS, lệnh, job xong, tick 0,2 s) |
| `job-N` | `Engine._dispatch` | chạy các stage của một việc robot (blocking), xong thì post `job_done` |
| `ats-<n>` (+ `ats-beat-<n>`) | `AtsClient.start` | kết nối lại, nhịp tim, đọc khung |
| `bridge-supervisor` | `Runtime.start` | giữ kết nối bridge/robot (3 s/lần) |
| `program-monitor` | `Runtime.start` | đọc UO[3] mỗi `monitor_s` → `bridge.program_state` |
| `alive` | `Runtime.start` | nhịp tim 60 s cho `ErrorTracker` |
| `data-sink` | `DataSink.start` | upload outbox → MySQL |
| `BridgeClient` (đọc, ping) | `connect()` | đọc phản hồi, ping giữ arm mỗi giây |
| worker của UI | `_run_task`, `ManualDialog._run` | thao tác blocking của người vận hành (jog, chạy/dừng chương trình...) |

Sự kiện đi vào engine **luôn qua hàng đợi** (`Engine.post`), không bao giờ sửa trạng thái từ thread khác.

## 4. Vòng đời khởi động / tắt
1. `ui/main.py`: đọc tham số → log → `QApplication` + theme → `load_settings` (hoặc `--demo`: `tools/demo.start_demo`) → `Runtime(settings, ROOT, seq)`.
2. `Runtime.__init__`: kiểm tra sớm `trays`, `robot_start` → `EmployeeService` → `SqlTargets` → `Outbox` → `DataSink` → `ErrorTracker` → nạp `sequences.json` →
   `BridgeClient` → `EndEffector` → `Engine` (kiểm tra `flow`, điểm dạy) → `AtsClient` mỗi fixture.
3. `MainWindow(rt, ...)`, rồi `rt.start()`: đóng các lỗi mở từ lần trước (`errors.recover`) → bật engine, sink, ATS, 3 thread giám sát.
4. Tắt (`Runtime.stop`, idempotent): `engine.stop_run` → `engine.shutdown` → dừng ATS → đóng bridge → đóng End Effector → **đóng mọi alarm đang mở** → `sink.stop(flush)` → đóng outbox.

## 5. Một chu kỳ đi qua các module thế nào
| # | Việc | Module / hàm |
|---|---|---|
| 1 | ATS gửi `TtoC_resultWaitdut`: box sẵn sàng nhận hàng | `ats/client` đọc khung → `ats/protocol.parse_message` → `Engine.on_ats_event` (post) → `_on_ats` đặt `ats_ready` |
| 2 | Robot rảnh **và chương trình robot đang chạy**: planner chọn việc tiếp theo (đi tray lấy hàng / đổi hàng ở box / cất hàng) | `Engine._dispatch` (chặn khi `program_state is False`) → `FlowController.plan` → `planner.Planner.next_task` |
| 3 | Việc được đổi thành các **stage** (danh sách bước + commit) | `FlowController.build` → `tasks.StageBuilder` (tọa độ từ `geometry.Layout`) |
| 4 | Thread job chạy từng stage | `core/sequence.SequenceRunner` → `robot/client` (`move`...) · `devices/*` (`ee`: heads / scanner / laser) · `ats/client` |
| 5 | Lệnh robot: ghi `PR[1]`, `R[2]`, `R[5]`, rồi `R[1]` = mã; chờ `R[1]` = 0 | `robot/client` ⇄ bridge ⇄ RSR0001 |
| 6 | Mỗi stage xong gửi **commit** → sổ sách (`DutBook`) và fixture được cập nhật; đặt hàng vào box xong thì `B1=<SN>` + `CtoT_placeDUTOK` | `Engine._on_flow_commit` → `FlowController.commit` |
| 7 | ATS gửi kết quả → đếm, phát bản ghi, alarm NG liên tiếp, sổ sách quyết định test lại / cất | `Engine._on_result` → `reporting/data_sink.emit_result`, `FlowController.result` |
| 8 | UI đọc `snapshot()` và vẽ | `ui/windows/main_window.refresh` → các `widgets/*.update_from` |

## 6. Dữ liệu và file
| Nơi | Ghi bởi | Nội dung |
|---|---|---|
| `config/settings.json`, `sequences.json`, `departments.json` | người dùng (và `Runtime.teach_point` cho điểm dạy) | cấu hình |
| `data/outbox.sqlite` (`outbox_demo.sqlite` ở demo) | `reporting/outbox` | hàng đợi báo cáo, mốc "còn sống", lỗi đang mở |
| `logs/rcs2.log` (xoay theo ngày, giữ 30) | `ui/main.setup_logging` | log chương trình |
| MySQL | `reporting/mysql_writer` | bảng cũ của RCS (kết quả, đăng nhập, lỗi...) |
| Trạng thái tray | RAM của `Engine` | mất khi khởi động lại (Input = đầy, NG = trống) |

## 7. Chương trình robot (UO[3]) — một quy tắc chạy xuyên mọi lớp
UO[3] PROGRUN = 0 nghĩa là RSR0001 không chạy: **lệnh ghi vào R[1] sẽ nằm lại và bị thực hiện khi chạy lại**. Vì vậy:

| Lớp | Cơ chế |
|---|---|
| `robot/client` | `program_running()` đọc UO[3]; `refresh_program_state()` lưu vào `program_state` |
| `runtime/bridge_link` | `_program_monitor` đọc định kỳ + ghi log khi đổi; `_need_program_running()` đọc mới trước thao tác thủ công |
| `runtime/robot_ops`, `end_effector_ops` | `_manual_motion` và các hàm đọc robot đều gọi `_need_program_running` |
| `core/engine` | `_cmd_start` từ chối; `_dispatch` không phát job; `_watch_program` tạm dừng chạy sau 1 s (alarm 9100 `robot_program`) |
| `ui` | khóa nút theo `snapshot["program_running"]`; panel Robot hiện ĐANG CHẠY / DỪNG / ? |

Ngoại lệ có chủ đích: **chạy / dừng chương trình** (`robot/uop`) không cần UO[3] = 1; **dừng robot luôn được phép**.

## 8. Bất biến an toàn và nơi bảo đảm
| Bất biến | Bảo đảm bởi |
|---|---|
| Chuyển động chỉ khi đã `arm`; một client arm | bridge (`NOT_ARMED`, `FORBIDDEN`); `Runtime._manual_motion` arm/disarm từng lệnh; `Engine._cmd_start` arm cho cả lượt chạy |
| Không disarm giữa chừng một việc robot | `Engine._disarm_after_job` |
| Dừng robot luôn được | `Runtime.robot_stop_program` không qua khóa thủ công; tắt SDI1-3 kể cả khi xung lỗi |
| Không mất dữ liệu báo cáo | outbox SQLite trước, upload sau; `ErrorTracker.recover` |
| Cấu hình sai báo ngay khi khởi động | `build_trays`, `uop.normalize`, `FlowSettings.from_config`, `validate({}, points)`, `build_end_effector` |
| Bí mật không nằm trong file | `env_secret` |
| Điểm ví dụ không chạy robot thật | `Engine.block_reason` khi `sequences.json` còn `"example": true` và bridge báo `mode = real` |

## 9. Luồng tray (nhiều tay hút, nhiều box)
```
 Engine (thread engine) ──world──► Planner.next_task ──► Task (Service / Take / Tray)
        ▲                                                   │ StageBuilder (poses 6 giá trị từ Layout)
        │ commit (take_tray / take_box / place_box /        ▼
        │         return_tray / put_ng / sn)         Stage = [bước sequence...] + commit
        └─────────── job thread: SequenceRunner chạy từng stage (robot move · ee heads · ee scanner · ats) ───────────┘
```
Sổ sách (`DutBook`) chỉ đổi khi **commit** của stage đã xong, nên mọi lúc đều biết từng sản phẩm đang ở đâu, và **Dừng có hiệu lực giữa hai stage**. Các bất biến an toàn ở mục 8 (UO[3], arm, một việc robot một lúc) áp dụng cho mọi stage. Chi tiết và cách sửa: `MainRCS/rcs2/core/README.md`; thử luật ưu tiên không cần robot: `python -m rcs2.tools.flow_sim`.

## 10. Điểm mở rộng thường gặp
Thêm tool End Effector · thêm loại bước · thêm tin ATS · thêm lệnh bridge · thêm loại bản ghi báo cáo · thêm quyền · thêm panel UI · thêm thao tác thủ công:
mỗi mục có công thức từng bước trong README của module sở hữu (xem bảng ở `MainRCS/README.md`).
