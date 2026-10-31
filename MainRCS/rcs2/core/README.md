# Module `rcs2/core` — logic lịch chạy của cell

Đây là **bộ não**: quyết định robot làm việc gì tiếp theo (planner của luồng tray), chạy các stage của robot, đếm kết quả, đếm tray, phát alarm.
Không biết gì về giao diện, giao thức TCP hay SQL (chỉ nhận các đối tượng được đưa vào: robot client, ATS client, sink, errors).

## File
| File | Nội dung |
|---|---|
| `engine.py` | `Engine`: trạng thái các fixture, phát việc robot theo planner, lệnh vận hành, alarm, `snapshot()` cho UI |
| `sequence.py` | Bước robot/ATS/End Effector mô tả bằng **dữ liệu**: `validate`, `SequenceRunner` (chạy các stage), đọc/ghi `config/sequences.json` (điểm đã dạy) |
| `tray.py` | `Tray` / `build_trays`: tray Input (còn hàng) và NG (đã đầy), kích thước chỉ đặt trong `settings.json` → `trays` |
| `geometry.py` `dut.py` `planner.py` `tasks.py` `flow.py` `states.py` | **luồng tray** (nhiều tay hút, nhiều box, tray 3 điểm): xem mục "Luồng tray" bên dưới |

Phụ thuộc cho phép: `ats` (hằng số giao thức), `devices` (`ScanCancelled`). Không import `robot`, `ui`, `runtime`.

## Engine: cách hoạt động
- **Một thread duy nhất** (`engine`) giữ toàn bộ trạng thái và xử lý **từng sự kiện một**: tin nhắn ATS, lệnh vận hành, job xong, tick 0,2 s.
  Mọi hàm công khai (`start_run`, `set_enabled`, `on_ats_event`...) chỉ **post** sự kiện vào hàng đợi, nên thread-safe.
- Robot chỉ có một: **một job tại một thời điểm**, job chạy blocking trong thread riêng (`job-N`) rồi post `job_done`.
- Mỗi khi robot rảnh, engine hỏi **planner** việc tiếp theo (`_dispatch`) rồi chạy các **stage** của việc đó (xem "Luồng tray").
- Vòng đời một fixture (box): `OFFLINE/NO_USED → IDLE —WAITDUT→ LOADING → TESTING —kết quả→ RESULT → UNLOADING → ...`
- `run_state`: `STOPPED / RUNNING / PAUSED / FAULT`. Job lỗi → `FAULT` (alarm theo loại lỗi) cho tới khi người vận hành xác nhận.

### Bảng alarm (mã giữ từ RCS cũ khi có)
| Mã | Khóa (`key`) | Khi nào |
|---|---|---|
| 9026 | `run_stop` | Người vận hành dừng / tạm dừng |
| 9010 | `test_timeout_N` | Fixture N không có kết quả sau `engine.test_timeout_s` |
| 9011 | `ng_N` | NG / retest liên tiếp ≥ `consecutive_ng.limit` |
| 9012 | `ats_N` | ATS của fixture N chưa kết nối (hoặc rớt khi `place_dut_ok`) |
| 9013 | `fix_N` | ATS báo lỗi jig (`fix_error`) |
| 9100 | `robot_link` | Chưa kết nối / không arm được / bridge bị disarm khi đang chạy |
| 9100 | `robot_program` | **Chương trình robot dừng (UO[3] = 0)**: từ chối Bắt đầu, hoặc tạm dừng chạy sau 1 s |
| 9201 | `robot` | Lỗi robot / sequence |
| 9202 | `robot` | Không đọc được mã (scanner) sau khi thử lại — chưa gắp gì |
| 9203 | `robot` | Lỗi đầu hút (không hút được / xy lanh không tới vị trí / lỗi I/O) |
| 9204 | `robot` | Laser IL-1000 không đạt |
| 9205 | `flow_layout` | **Luồng tray:** thiếu / sai điểm dạy (Bắt đầu bị từ chối), tên điểm thiếu nằm trong thông báo |
| 9206 | `tray_input` | **Luồng tray:** hết hàng chưa test và mọi sản phẩm đã cất → **thay tray Input** rồi bấm "Nạp lại" (chạy tiếp tự động) |
| 9207 | `tray_ng` | **Luồng tray:** tray NG đầy → **thay / dọn tray NG** rồi bấm "Đã dọn" |
| 9209 | `tray_output` | **Luồng tray:** mọi tray output (hàng PASS) đã đầy → **thay / dọn tray output** rồi bấm "Đã dọn" của tray đó |
| 9208 | `robot` | **Luồng tray:** **rơi hàng** (tay đang cầm sản phẩm mà cảm biến áp suất mất tín hiệu) → dừng chạy **và dừng chương trình robot** |

### Quy tắc bất biến
1. **Không ghi lệnh robot khi UO[3] PROGRUN = 0**: `_cmd_start` đọc mới UO[3], `_dispatch` không phát job, `_watch_program` tạm dừng sau 1 s.
2. **Không disarm giữa chừng một sequence** (`_disarm_after_job`).
3. Mọi trạng thái chỉ đổi trong thread engine (có `self._lock` cho `snapshot()` đọc từ thread khác).
4. Sổ sách luồng tray (`DutBook`) và trạng thái tray nằm trong RAM: **mất khi khởi động lại** (Input = đầy, NG = trống).
5. `snapshot()` là **hợp đồng với UI**: thêm khóa thì thêm, đừng đổi tên / bỏ khóa mà không sửa `ui/` và `devtools/ui_preview`.

## Luồng tray: 8 tay hút, nhiều box, tray 3 điểm
Cách chạy **duy nhất** của NewRCS (chế độ "classic" mỗi fixture một sequence đã bỏ; `settings.json` còn ghi `flow.mode: "classic"` sẽ bị báo lỗi lúc khởi động). Cần **nhiều tay hút** (End Effector, tối thiểu 2) và khai báo tray Input + NG.

**Quy tắc nghiệp vụ**
- Robot lấy hàng **chưa test** từ tray Input vào từng tay hút (mỗi tay một sản phẩm), đem tới box nào **trống / test xong** để đặt vào rồi gửi `B1=<SN>` + `CtoT_placeDUTOK`.
- Box test xong: **đổi tại chỗ**: lấy hàng đã test ra bằng 1 tay trống, đặt hàng mới từ tay khác vào ngay. Luôn chừa ≥ 1 tay trống khi đi lấy hàng (trừ khi mọi box đang trống).
- **Ô tray Input chỉ có 3 trạng thái:** chưa test (`fresh`), trống (`empty`), pass (`pass`). Lấy hàng thì ô thành trống; **khi KHÔNG có tray output, hàng PASS được đặt vào ô TRỐNG ĐẦU TIÊN** của tray Input (không nhất thiết ô nó được lấy ra); hàng NG để ô của nó trống. Ô tray NG: trống / NG (điền lần lượt).
- **Tray output (tùy chọn, `settings.json` → `trays` → `output1`, `output2`):** chỉ để đặt hàng **PASS**. Hàng PASS được đặt **lần lượt** vào `output1` (theo thứ tự hàng, từng cột), `output1` đầy thì sang `output2`; khi người vận hành dọn `output1` thì hàng sau lại vào `output1` trước. Ô tray output: trống / pass. Khi có tray output, tray Input chỉ còn hai trạng thái (chưa test / trống). Cả hai tray output đầy thì hàng PASS **ở lại trên tay** và hiện alarm 9209 (robot vẫn chạy tiếp những việc khác cho tới khi các tay đầy). Điểm dạy: `output1_O/X/Y`, `output2_O/X/Y`.
- **Tay hút có 5 trạng thái:** trống, chưa test, pass, ng, retest (một trạng thái `retest` chung, số lần được phép test là `flow.max_attempts`, mặc định 3; muốn 1 lần đầu + 3 lần test lại thì đặt 4).
- NG → **test lại ở box khác** (không bao giờ cùng một box), tổng tối đa `max_attempts` lần; NG lần cuối (hoặc không còn box nào chưa thử) → ô kế tiếp của tray NG.
- **Ưu tiên "không để box rảnh lâu"**: phục vụ box đã chờ lâu nhất trước.
- Tọa độ: ô tray = nội suy lưới từ O, X, Y, **cả 6 giá trị** x y z w p r; tay k tới điểm Q dạy bằng tay 1 = `Pk(Q) = P1(Q)·A⁻¹·Bk` (A, Bk = pose robot khi tay 1 / tay k ở cùng điểm O), đúng với mọi hướng của Q.

**Các file**
| File | Nội dung |
|---|---|
| `geometry.py` | `to_matrix/from_matrix` (quy ước FANUC), `TrayGrid(O, X, Y, rows, cols)`, `HeadTransforms`, `Layout` (đọc các điểm đã dạy theo tên, báo điểm thiếu) |
| `dut.py` | `DutBook`: mỗi sản phẩm đang ở đâu (ô tray / tay k / box n / tray NG), đã test mấy lần ở box nào, luật test lại |
| `planner.py` | **logic thuần**: `Planner.next_task(World)` → `ServiceTask` (đổi hàng ở một box) / `TakeTask` (chỉ lấy ra) / `TrayTask` (một lượt tới tray: cất hàng đã test rồi lấy hàng mới) / `None` |
| `tasks.py` | `StageBuilder`: task → các **stage** (vài bước sequence + một *commit*) |
| `flow.py` | `FlowSettings` (kiểm tra `flow`), `FlowController` (sổ sách + layout + planner + builder), `commit()` cập nhật sổ khi stage xong |
| `states.py` | tên trạng thái fixture / run dùng chung (tránh import vòng) |

**Chạy thế nào:** engine hỏi planner mỗi khi robot rảnh → `StageBuilder` đổi task thành stage → thread job chạy từng stage bằng `SequenceRunner` → xong mỗi stage gửi **commit** về thread engine (`take_tray`, `take_box`, `place_box`, `return_tray`, `put_ng`, `sn`) → `FlowController.commit` cập nhật `DutBook` và fixture. Vì sổ sách cập nhật **theo từng stage**, nên Dừng / lỗi giữa chừng vẫn biết từng sản phẩm đang ở đâu; **Dừng có hiệu lực giữa hai stage**. Bắt đầu bị từ chối (alarm **9205**) khi thiếu / sai điểm dạy.

**Chu trình của mỗi sản phẩm (đã chốt với người dùng)**
- **Lấy từ tray:** đưa đầu đọc mã tới ô → **quét mã** → đưa tay tới ô → hạ xy lanh, hút, nâng, kiểm tra áp suất.
- **Đặt xuống (box, tray output hoặc tray Input, tùy chọn tray NG):** đưa tay tới → hạ, nhả, nâng, kiểm tra đã nhả → **kiểm tra laser IL-1000 tại 2 điểm** (đưa đầu laser tới từng điểm, phải báo GO ở cả hai, nếu không thì sản phẩm bị nghiêng → alarm 9204 và dừng). Với box, **test chỉ được bắt đầu (`B1=<SN>` + `placeDUTOK`) sau khi laser đạt**. Cài đặt: `flow.laser_check` (`enabled`, `places` = `box` / `input` / `output` / `ng`, `offsets` = 2 điểm đo x y z mm trong hệ tọa độ của chỗ đặt, `timeout_s`); đầu laser dạy như đầu đọc mã: điểm `laser_at_O`.
- **Rơi hàng:** trước mỗi lần tay di chuyển có một **carry check** (`tasks.py`): mọi tay đang cầm sản phẩm phải còn tín hiệu hút. Mất tín hiệu → `DropError` → alarm **9208**, dừng chạy, và (nếu `flow.stop_robot_on_drop` = true) **dừng chương trình robot** như nút "Dừng robot" (`Engine.on_drop` → `Runtime._on_drop`). Sau khi dọn tay hút và box bằng tay: "Xóa trạng thái luồng".
- **Nạp đầy tay khi ở tray (`flow.fill_heads`, mặc định bật):** mỗi lần tới tray, robot **nạp đầy mọi tay trống** (trừ `keep_free_heads`), không chỉ lấy đủ cho số box đang chờ. Việc đã bắt đầu thì không bị ngắt giữa chừng, nên không còn cảnh vừa lấy dở vài sản phẩm đã phải bỏ đi phục vụ box rồi quay lại tray lần nữa. Mô phỏng (10 box): số chuyến tới tray giảm từ 31 xuống 21. Tắt bằng `fill_heads: false` để về cách cũ (chỉ lấy đủ cho box đang chờ).
- **Khi nào cất hàng (gom cất):** chỉ khi **mọi sản phẩm trên tay đều đã test (pass / ng)**, hoặc **mọi box đều đang test**. Ngoại lệ để không kẹt: hết chỗ trống trên tay mà cần lấy hàng / lấy hàng ra khỏi box, hoặc đã hết hàng chưa test.
- **Hết hàng / tray NG đầy:** engine tự nâng alarm 9206 / 9207 / 9209 (xóa khi người vận hành bấm "Nạp lại" của tray Input / "Đã dọn" của tray NG hoặc tray output). Mỗi nút chỉ đặt lại đúng tray của nó (thay tray Input giữ nguyên số ô của tray NG và tray output); "Xóa trạng thái luồng" thì xóa tất cả.

**Hướng dẫn sửa luồng tray**
| Muốn | Sửa ở |
|---|---|
| Đổi thứ tự ưu tiên / khi nào đi tray / lấy bao nhiêu hàng | `planner.py` → `Planner.next_task`, `_tray_visit`, `PlannerConfig` (và `flow` trong `settings.json`) |
| Đổi số lần test lại, luật chọn box | `dut.py` → `DutBook.result`, `Dut.can_test_in`; `flow.max_attempts` |
| Đổi trình tự hút / nhả của một tay | `tasks.py` → `StageBuilder._hold`, `_release` |
| Thêm đoạn đi qua điểm trung gian | `flow.via_tray` / `flow.via_fixtures` (điểm đã dạy) hoặc `tasks.py` |
| Thêm loại task mới | dataclass trong `planner.py`, nhánh trong `Planner.next_task`, `StageBuilder.build`, commit mới trong `FlowController.commit` |
| Thêm khóa vào giao diện | `FlowController.snapshot` (+ `ui/widgets/tray_panel.py`) |
| Thử luật mới mà không cần robot | `python -m rcs2.tools.flow_sim` (xem `tools/README.md`) và `tests/core/test_planner.py` |

**Số tay hút** lấy từ `end_effector.heads.units`, tối thiểu 2 (1 tay không đổi hàng được: sẽ bị `FlowError` khi khởi động).

**Giới hạn hiện tại:** sau lỗi (rơi hàng, laser, tay không hút được) người vận hành dọn tay hút / box bằng tay rồi `Xóa trạng thái luồng` (chưa tự phục hồi); simulator chưa theo dõi vị trí thật của sản phẩm (nó chỉ kiểm tra luồng lệnh, không kiểm tra tọa độ).

## Sequence (`sequence.py`)
`config/sequences.json` chỉ chứa **điểm đã dạy**: `{"points": {...}}`. Các stage của luồng tray (`tasks.py`) là danh sách bước, mỗi bước là **đúng một** trong `robot / ats / ee / wait / log`:
```
{"robot": "move|rmove|gosafetarge", "pose": "<điểm>" | "target": [x,y,z,w,p,r], "override": 10}
{"robot": "put|get|up|down", "station": 1}        {"robot": "gosafehere"}
{"ats": "place_dut_ok|fixture_open|fixture_close|dut_out|request_barcode|barcode", "sn": "{sn}"}
{"ee": "scanner"}                                  đọc mã -> biến {sn}; lỗi -> 9202
{"ee": "heads", "vacuum": "on|off" | "cylinder": "down|up" | "check": "hold|release", "heads": "all"|[1,2]}
{"ee": "laser", "check": "ok"}
{"wait": 0.5}    {"log": "..."}
```
Biến trong chuỗi: `{sn}` (sau bước scanner). Bước `ats` ghi `"fixture": 3` để chỉ rõ box; bước scanner có `"tag"` được trả lại cùng mã (`on_scan(code, "scanner", tag)`). Lúc khởi động engine gọi `validate({}, points)` để báo ngay
điểm dạy nào viết sai. `save_sequences()` ghi nguyên tử, mỗi điểm một dòng.

## Hướng dẫn sửa
### Đổi logic chạy
| Muốn | Sửa ở |
|---|---|
| Robot làm việc gì tiếp theo | `planner.py` (xem "Hướng dẫn sửa luồng tray") |
| Kết quả nào tính là NG liên tiếp | `COUNTS_AS_FAIL`, `_on_result` |
| Việc gì xảy ra sau khi job xong / lỗi | `_on_job_done`, `_fail_flow` |
| Thêm lệnh vận hành (ví dụ "bỏ qua fixture") | thêm `def _cmd_<tên>(self, ...)` + hàm công khai `post("cmd", "<tên>", ...)`; `_handle` tự gọi `_cmd_<tên>` |
| Thêm mã alarm mới | `self.errors.raise_error("9xxx", "mô tả", key="...")` + `clear_error(key)` khi hết; thêm vào bảng trên và docstring đầu `engine.py` |
| Thêm khóa vào `snapshot()` | `Engine.snapshot` + chỗ UI đọc (`ui/windows/main_window.refresh`) + `devtools/ui_preview/preview.py` (dữ liệu giả) |
| Thêm loại kết quả ATS | `ats/protocol.py` (xem README của `ats`), rồi `RESULT_LABEL`, `COUNTS_AS_FAIL` |

### Thêm một loại bước sequence
1. `validate()` (hoặc `_check_ee_step` cho bước `ee`): kiểm tra tham số, báo lỗi rõ.
2. `SequenceRunner._do`: nhánh thực thi (với `ee`: `_do_ee`).
3. Cập nhật docstring đầu `sequence.py`, bảng ở trên và `MainRCS/config/README.md`.
4. Thêm thao tác tương ứng cho simulator nếu cần (`bridge32/bridge_simple.py`).
5. Test: `tests/core/test_sequence.py`.

### Đổi kích thước tray
Chỉ trong `settings.json` → `trays` (1..50 mỗi chiều, `tray.MAX_SIDE`), rồi khởi động lại.

## Test
`python run_tests.py core` — `test_engine` (bắt đầu / tạm dừng / dừng, alarm, lỗi + xác nhận, timeout, chương trình robot dừng), `test_flow_engine` (luồng tray), `test_planner`, `test_sequence`, `test_tray`.
Fixture dùng chung nằm ở `tests/support/engine.py` (`EngineCase`, `FlowRobot`, `FakeAts`, `taught_points`, `tray_settings`).
