# Module `rcs2/devices` — End Effector (đầu gắp của robot)

Robot chỉ có **MỘT End Effector**, trên đó có các tool nhỏ, mỗi tool đều tùy chọn. Cấu hình ở `settings.json` → `end_effector`.

| Tool | File | Là gì | Đi qua đâu |
|---|---|---|---|
| `heads` | `heads.py` | 8 cụm hút: van chân không + xy lanh lên/xuống + cảm biến áp suất | I/O của controller FANUC qua bridge (`io.read` / `io.write`) |
| `scanner` | `scanner.py` | đầu đọc mã Keyence SR-710 / SR-X100 | TCP hoặc cổng COM trực tiếp từ PC |
| `laser` | `laser.py` | IL-1000: phán định GO / HIGH / LOW | đọc I/O qua bridge (mới chỉ đọc phán định) |
| (gộp) | `end_effector.py` | `EndEffector`, `build_end_effector(settings, io)`, `capabilities()` cho biết End Effector có tool nào | — |

Không import module nào khác của `rcs2`. `io` được **đưa vào** (`BridgeClient`), nên test dùng I/O giả.

## Cấu hình (`settings.json` → `end_effector`)
```json
"end_effector": {
  "name": "End Effector",
  "heads":   {"enabled": true, "cylinder_s": 0.6, "vacuum_s": 0.3, "pressure_timeout_s": 1.0, "cylinder_timeout_s": 2.0,
              "pressure_active": 1, "coil_active": 1, "coil_pulse_s": 0,
              "units": [{"vacuum": "RDO[1]", "coil_down": "RDO[9]", "coil_up": "RDO[17]",
                         "cyl_down": "RDI[41]", "cyl_up": "RDI[51]", "pressure": "RDI[1]"}, ...]},
  "scanner": {"type": "tcp", "host": "...", "port": 9004, "length": 14, "pattern": "[A-Z0-9]+", "retry": 2, "timeout_s": 3.0},
  "laser":   {"enabled": false, "ok": "RDI[20]", "high": "RDI[21]", "low": "RDI[22]", "active": 1, "timeout_s": 1.0}
}
```
- **heads:** mỗi đầu khai địa chỉ I/O riêng (`RDO[n]`, `RDI[n]`, ...). `pressure_active` = giá trị cảm biến khi **đã hút được**.
  - **Xy lanh dùng van điện từ 2 coil (5/2 giữ vị trí) + 2 cảm biến cuối hành trình** (loại đang dùng): mỗi đầu khai `coil_down`, `coil_up` (2 ngõ ra) và `cyl_down`, `cyl_up` (2 ngõ vào).
    Muốn xuống: **tắt coil_up trước, rồi cấp điện coil_down** (không bao giờ bật cả hai); muốn lên thì ngược lại. Có cảm biến thì chương trình **chờ cảm biến**
    (tối đa `cylinder_timeout_s`, quá hạn báo "xy lanh đầu k không tới vị trí", alarm 9203) thay vì chờ cố định `cylinder_s`. `coil_active` = mức cấp điện coil (mặc định 1);
    `coil_pulse_s` > 0 = chỉ cấp xung chừng đó giây rồi tắt cả hai coil (van giữ vị trí), 0 = giữ cấp điện tới lệnh ngược lại.
  - **Van 1 coil + lò xo hồi:** khai `cylinder` (một ngõ ra) thay cho `coil_down` / `coil_up`; `cylinder_down` = mức ngõ ra làm đầu đi xuống. Có thể trộn hai loại giữa các đầu; không khai cả hai loại cho cùng một đầu.
- **scanner:** `type` `tcp` (`host`, `port`) hoặc `serial` (`port` `COMx`, `baud`; cần `pyserial`). `length` 0 / `pattern` "" = không kiểm tra;
  `retry` = số lần thử **thêm** sau lần đầu. Giao thức Keyence: gửi `LON`+terminator → nhận mã + CR; `ERROR` = không đọc được; gửi `LOFF` để dừng.
- **laser:** `active` = giá trị ngõ vào khi phán định đúng. Địa chỉ trong file mẫu chỉ là giá trị giữ chỗ.

## Cách dùng
- **Sequence:** `{"ee": "heads" | "scanner" | "laser", ...}` (cú pháp đầy đủ ở `core/README.md`). Lỗi → ngoại lệ riêng → `engine` đặt alarm:
  `HeadError` → **9203**, `ScanError` → **9202**, `LaserError` → **9204**.
- **Cửa sổ Thủ công:** `Runtime.heads_action / heads_status / scan_test / scan_stop / laser_status` (heads và laser đòi UO[3] = 1; scanner thì không).

## Hướng dẫn sửa
### Thêm / bớt số tay hút
Số tay = số phần tử của `end_effector.heads.units` (mỗi phần tử một cụm: `vacuum`, `cylinder`, `pressure`). Không có số 8 nào cố định trong code.
- **Thêm tay:** thêm một phần tử vào `units` (đúng địa chỉ I/O), khởi động lại, rồi dạy điểm `head_<k>_at_O` của tay mới (Thủ công → Hiệu chuẩn luồng tray).
- **Bớt tay:** xóa phần tử cuối của `units` và khởi động lại; điểm `head_k_at_O` thừa trong `sequences.json` bị bỏ qua. Nếu bớt tay ở giữa thì các tay phía sau đổi số, phải dạy lại `head_k_at_O` theo số mới.
- **Giới hạn:** luồng tray cần **ít nhất 2 tay** (đổi hàng cần một tay trống và một tay đang cầm hàng); `max_pick`, `max_sort`, `pick_ahead` lớn hơn số tay thì tự cắt về số tay, `keep_free_heads` tối đa bằng số tay − 1.

### Đổi địa chỉ I/O / thời gian
Chỉ sửa `settings.json` (không đụng code). Địa chỉ sai bị báo lúc khởi động (`parse_io`, `from_config`).

### Thêm một tool mới cho End Effector (ví dụ camera)
1. `devices/<tool>.py`: lớp có `from_config(cfg, io)`, các hàm hành động / `check` / `status`, và một lớp lỗi riêng `XxxError`.
2. `end_effector.py`: thêm vào `TOOLS`, constructor `EndEffector`, `capabilities()`, `build_end_effector()`, `close()`.
3. `core/sequence.py`: thêm tên vào `EE_TOOLS`, kiểm tra tham số trong `_check_ee_step`, thực thi trong `_do_ee`.
4. `core/engine.py` (`_on_job_done`): ánh xạ `XxxError` → mã alarm mới; cập nhật bảng alarm ở `core/README.md`.
5. `runtime/end_effector_ops.py`: thêm thao tác cho Thủ công; `ui/windows/manual_dialog.py`: thêm một section (mẫu `_build_laser_section`).
6. Simulator (`bridge32/bridge_simple.py`): thêm I/O hoặc server TCP giả nếu tool cần.
7. Test: `tests/devices/` (mẫu `test_end_effector.py`); `settings.example.json` thêm khóa mẫu.

### Đổi giao thức máy quét (hãng khác)
Giữ `KeyenceScanner`, thêm một lớp transport mới (có `open/close/write/read/flush_input/describe/is_open`) hoặc một lớp scanner mới cùng giao diện
(`scan(...)`, `stop()`, `close()`), rồi chọn trong `from_config`.

## Lưu ý
- Hàm `scan` **blocking**: chạy trong thread job robot hoặc thread worker của UI, không chạy trên thread giao diện.
- Mọi ghi I/O của heads dùng bridge nên cần bridge đang **arm** (Runtime lo việc này cho thao tác thủ công; sequence chạy khi engine đã arm).

## Test
`python run_tests.py devices` — `test_end_effector` (heads, laser, cấu hình, bước sequence), `test_scanner` (giao thức, thử lại, hủy).
