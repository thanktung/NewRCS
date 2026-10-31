# `config/` — file cấu hình của nhà máy (dữ liệu, không phải code)

| File | Vai trò |
|---|---|
| `settings.json` | cài đặt chính của cell (xem bảng dưới). **Thật**, đang được dùng |
| `sequences.json` | các điểm robot (`points`) và quy trình (`sequences`) |
| `departments.json` | mã bộ phận → cấp truy cập, quyền tối thiểu |
| `*.example.json` | bản mẫu có chú thích; **test nạp thử** nên luôn phải hợp lệ |
| `sequences.json.bak` | bản sao **tự tạo** lần đầu khi dạy điểm (`Runtime.teach_point`); đừng xóa nếu muốn giữ bản gốc |
| `archive/` | file cũ không dùng nữa: `trays.json` (tính năng đã bỏ, kích thước tray nay ở `settings.json`), `settings.json.pre_sim.bak` (cấu hình thật trước khi trỏ sang simulator) |

Phần mặc định của mọi khóa nằm ở `rcs2/config/defaults.py`; `settings.json` chỉ cần ghi những khóa khác mặc định. Khóa bắt đầu bằng `_` (ví dụ `_note`) là chú thích, bị bỏ qua.
**Bí mật không ghi vào file:** `RCS_DB_PASSWORD`, `RCS_BRIDGE_TOKEN` là biến môi trường.

## `settings.json` — các nhóm khóa
| Nhóm | Khóa chính | Ý nghĩa |
|---|---|---|
| `identity` | `model`, `stations`, `local_ip` | tên dùng đặt tên bảng MySQL; `local_ip` rỗng = tự lấy IP `10.x` |
| `mysql` | `enabled`, `host`, `port`, `user`, `database`, `password_env`, `flush_interval_s` | MySQL dashboard. `enabled:false` hoặc thiếu mật khẩu → "DB tắt", dữ liệu nằm ở outbox |
| `outbox_path` | | file SQLite đệm (mặc định `data/outbox.sqlite`) |
| `employee` | `url`, `departments_path`, `offline_demo`, `auto_logout_s`, `auto_logout_idle` | đăng nhập ESD, tự đăng xuất (180 s; 0 = không) |
| `bridge` | `host`, `port`, `token_env`, `default_override` | địa chỉ bridge robot; override mặc định (%) |
| `ats` | `heartbeat_s`, `connect_timeout_s`, `retry_s`, `fixtures` | `fixtures`: `"N": {host, port, station, robot_station}`. **Thay hẳn** mặc định, liệt kê đủ |
| `end_effector` | `heads`, `scanner`, `laser` | xem `rcs2/devices/README.md`. Xy lanh từng đầu: van 2 coil `coil_down` / `coil_up` + 2 cảm biến `cyl_down` / `cyl_up` (địa chỉ trong file mẫu là **giữ chỗ**, sửa đúng dây) |
| `trays` | `input`, `ng` | `{"rows": n, "cols": m}` (1..50); tray không khai báo thì không hiển thị. Sửa xong **khởi động lại** |
| `robot_start` | `rsr`, `pulse_s`, `reset_wait_s`, `run_wait_s`, `stop_wait_s`, `poll_s`, `monitor_s` | chạy/dừng chương trình robot qua UOP; `monitor_s` = chu kỳ đọc UO[3] |
| `flow` | `mode`, `max_attempts`, `keep_free_heads`, `max_pick`, `max_sort`, `pick_ahead`, `top_up_when_idle`, `scan`, `override`, `check_timeout_s`, `via_tray`, `via_fixtures` | **luồng tray** (nhiều tay hút + nhiều box): `mode: "classic"` (mặc định) hoặc `"tray"`; xem mục bên dưới và `rcs2/core/README.md` |
| `consecutive_ng` | `limit`, `stop_fixture` | NG liên tiếp: ngưỡng và có dừng fixture không |
| `engine` | `reload_after_unload`, `auto_start_test`, `send_dut_out`, `test_timeout_s`, `sequences_path` | hành vi của engine |

## `sequences.json`
```json
{
  "example": true,                       // XÓA dòng này khi đã dạy điểm thật; còn dòng này thì không Start được trên robot thật
  "points": {
    "above_input": {"xyzwpr": [x,y,z,w,p,r], "config": [7 số], "uf": 1, "ut": 1},
    "above_fixture_1": [100, 300, 250, 180, 0, 0]          // dạng gọn: chỉ 6 số
  },
  "sequences": { "load": [ ...bước... ], "unload_pass": [...], "unload_ng": [...] }
}
```
- Ba sequence **bắt buộc**: `load`, `unload_pass`, `unload_ng`. Tùy chọn: `unload_retest`, `unload_fqc`.
- Cú pháp từng bước và biến `{fixture}`, `{robot_station}`, `{station}`, `{result}`, `{sn}`: `rcs2/core/README.md`.
- **Dạy điểm** bằng cửa sổ Thủ công (ghi `xyzwpr` + `config/uf/ut`, file ghi nguyên tử, mỗi điểm / bước một dòng). Sửa tay cũng được nhưng phải khởi động lại
  (điểm dạy từ giao diện thì engine thấy ngay).
- Kiểm tra lúc khởi động: sai bước nào báo bước đó.

## Luồng tray: điểm phải dạy trong `sequences.json` → `points`
Chế độ `flow.mode: "tray"` không dùng các sequence `load / unload_*` mà tính tọa độ từ các điểm sau (dạy bằng cửa sổ Thủ công → **Hiệu chuẩn luồng tray**; mỗi điểm lưu đủ `xyzwpr` 6 giá trị + `config / uf / ut`):

| Tên điểm | Là gì |
|---|---|
| `head_1_at_O` … `head_K_at_O` | pose robot khi **tay k** nằm đúng **cùng một điểm O** của tray Input (O = ô hàng 1, cột 1). Từ đây tính offset 6 bậc tự do của từng tay so với tay 1 |
| `scanner_at_O` | như trên nhưng cho đầu đọc mã (chỉ khi có `end_effector.scanner` và `flow.scan`) |
| `laser_at_O` | như trên nhưng cho đầu laser IL-1000 (chỉ khi `flow.laser_check.enabled` và `end_effector.laser.enabled`) |
| `input_O`, `input_X`, `input_Y` | **tay 1** ở ô hàng 1 cột 1 (O), ô hàng 1 cột cuối (X), ô hàng cuối cột 1 (Y) của tray Input; kích thước `rows × cols` ở `trays.input` |
| `ng_O`, `ng_X`, `ng_Y` | như trên cho tray NG |
| `output1_O/X/Y`, `output2_O/X/Y` | như trên cho tray output 1 / 2 (chỉ khi có khai báo `trays.output1` / `trays.output2`; hàng PASS được đặt vào đó) |
| `fixture_1` … `fixture_N` | **tay 1** ở vị trí đặt hàng của từng box (N theo `ats.fixtures`) |

Ba điểm O, X, Y của một tray phải cùng `config / uf / ut`. Điểm khác (`via_tray`, `via_fixtures`) là tùy chọn. Thiếu / sai điểm → **Bắt đầu bị từ chối** (alarm 9205) và thông báo ghi rõ tên điểm thiếu. Ví dụ bật chế độ: `"flow": {"mode": "tray", "override": 10}`. Số tay hút lấy từ `end_effector.heads.units` (tối thiểu 2). `flow.fill_heads` (mặc định true) = tới tray thì nạp đầy mọi tay trống để đỡ phải quay lại tray. `flow.laser_check` (`enabled`, `places` = `box` / `input` / `ng`, `offsets` = 2 điểm đo [x, y, z] mm, `timeout_s`) bật kiểm tra laser 2 điểm sau mỗi lần đặt xuống; `flow.stop_robot_on_drop` (mặc định true) dừng chương trình robot khi rơi hàng.

`settings.json` hiện **đã bật `flow.mode: "tray"`** và `sequences.json` có sẵn bộ điểm **MẪU** (8 tay, scanner, 2 tray, 13 box) để chạy thử với simulator; vì file còn dòng `"example": true` nên Bắt đầu vẫn bị từ chối trên robot thật cho tới khi dạy điểm thật. Bản gốc trước khi bật: `archive/settings.json.pre_tray.bak`, `archive/sequences.json.pre_tray.bak`.

## `departments.json`
`departments` (mã → cấp 1..5, hỗ trợ `MNM5*`), `default_level` (0 = từ chối bộ phận không có tên), `min_level` (`operate`, `manual`, `teach`), `default_password`
(tùy chọn). Đọc lại mỗi lần đăng nhập, sửa xong không cần khởi động lại. Chi tiết: `rcs2/employee/README.md`.

## Dùng với simulator
`settings.json` hiện trỏ bridge, fixture 1..13 (`8800 + N`) và scanner (9004) về `192.168.5.6`, đúng cổng mà `bridge32/bridge_simple.py` mở. Để chạy với phần cứng thật,
chép lại giá trị trong `archive/settings.json.pre_sim.bak` (fixture thật `10.164.125.x:8888`, scanner `192.168.1.50`).

## Khi sửa
1. Sửa `settings.json` / `sequences.json`, khởi động lại NewRCS (lỗi cấu hình báo ngay lúc khởi động).
2. Thêm khóa mới? Thêm ở `rcs2/config/defaults.py` và `settings.example.json` trước (xem `rcs2/config/README.md`).
3. `python run_tests.py config` bảo đảm file mẫu vẫn hợp lệ.
