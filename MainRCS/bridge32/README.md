# `bridge32/` — simulator MỘT FILE của cả cell (không cần robot, không cần fixture)

`bridge_simple.py` (chỉ dùng thư viện chuẩn, Python 3.8+) giả lập **mọi thứ NewRCS nói chuyện cùng**, trong một tiến trình:
1. **Robot bridge** — cùng giao thức TCP/JSON như bridge thật, kèm chương trình robot `RSR0001` và các tín hiệu UOP.
2. **Chương trình ATS của từng fixture** — mỗi fixture một cổng.
3. **Máy quét mã Keyence** của End Effector.

> **Bridge thật** (lớp COM FRRJIf, Python 32-bit + pywin32) **không nằm trong thư mục này**: ở đây chỉ có simulator. Thư mục giữ tên `bridge32/` để chỗ đặt
> bridge thật không đổi; giao thức bridge thật: `../docs/robot_bridge_guide.md`. `Bridge(cfg, sim=False)` bị từ chối.

## Chạy
```powershell
python bridge32\bridge_simple.py                  # đọc cổng từ ..\config\settings.json; Ctrl+C để dừng
python bridge32\bridge_simple.py --cold           # robot "lạnh": dừng khẩn, chương trình chưa chạy
python bridge32\bridge_simple.py --pass-rate 0.5 --test-time 2 --delay 1.5 --seed 1 --strict -v
python bridge32\bridge_simple.py --no-settings --fixtures 4        # không đọc settings.json: bridge 5600, fixture 8801.., scanner 9004
```
Với `config/settings.json` hiện tại, tất cả nằm trên máy **`192.168.5.6`**: bridge `5600`, fixture N `8800 + N`, scanner `9004`. Máy chạy simulator phải có địa chỉ này
(hoặc đổi `settings.json` sang `127.0.0.1` nếu NewRCS chạy cùng máy). Simulator nghe mọi giao diện mạng, nhận mọi client, và **in cảnh báo** cho từng địa chỉ trong
`settings.json` không phải của máy nó.

| Tham số | Ý nghĩa |
|---|---|
| `--settings FILE` / `--no-settings` | lấy cổng từ `settings.json` khác / không đọc |
| `--host`, `--port`, `--allow IP`, `--token` | mạng; mặc định `0.0.0.0`, nhận mọi client, không token |
| `--fixtures N`, `--fixture-port-base P`, `--scanner-port`, `--no-scanner` | khi không dùng `settings.json` |
| `--test-time S`, `--pass-rate R`, `--retest-rate R`, `--seed N` | kết quả test: fixture n mất `S + 0.5·(n−1)` giây |
| `--delay S` | thời gian robot thực hiện một lệnh |
| `--cold` | robot lạnh (xem dưới) |
| `--strict` | lệnh bất khả thi thành lỗi robot; fixture bỏ qua `placeDUTOK` nếu robot chưa đặt DUT |
| `--config FILE`, `-v` | thêm cài đặt (xem `DEFAULTS`), log từng lệnh |

`python -m rcs2 --demo` chạy chính file này **trong tiến trình** của ứng dụng (xem `rcs2/tools/demo.py`).

## Những gì được mô phỏng
### Bridge
Đúng quy tắc của bridge thật: `hello`/token, danh sách IP, **arm** (một client, watchdog `watchdog_s`, ping giữ arm), `motion.*` với giới hạn (override,
rmove, workspace, số trạm), `BUSY / FAULT_LATCHED / TIMEOUT / ROBOT_ERROR / VERIFY_FAILED`, `r.read/write` (R[1] được bảo vệ), `pr.*`, `pos.read`,
`io.read/write`, `alarm.clear`, `fault.clear`, sự kiện `status` mỗi 0,5 s. Phản hồi `motion.*` chỉ về khi robot làm xong, ghép theo `id`.

### Robot (RSR0001)
Vòng lặp đúng hợp đồng: chờ `R[1] > 0` → thực hiện (mất `sim_delay_s`) → `R[1] = 0`; lỗi (trạm trong `sim_bad_stations`, lỗi bơm vào) → `R[1] = -1` rồi chờ `R[1] = 0`.
Chương trình bị dừng giữa chừng thì `R[1]` vẫn `> 0` và lệnh **được làm lại khi chạy lại** (giống vòng TP thật).
DUT được theo dõi: `get 0` lấy từ tray Input, `put N` đặt tại trạm N, `get N` lấy ra — nên fixture chỉ thật sự "có DUT" sau khi robot đặt vào.

### UOP (UI[n] = SDI[n], UO chỉ đọc)
| Tín hiệu | Hành vi |
|---|---|
| UI1 IMSTP (1→0) | dừng chương trình + **FAULT** (UO6) |
| UI2 HOLD = 0 | tạm dừng chuyển động (UO5 HELD, UO4 PAUSED, UO3 tắt) |
| UI3 SFSPD = 0 | chuyển động chậm gấp 3 |
| UI4 CSTOPI (cạnh lên) | dừng chương trình (R[1] giữ nguyên) |
| UI5 RESET (cạnh lên) | xóa FAULT (chỉ khi IMSTP đã bật lại) |
| UI6 START (cạnh lên) | chạy chương trình đã chọn (cần SDI1-3 = 1, SDI8 = 1, không FAULT) |
| UI9..16 RSR1..8 (cạnh lên) | chọn chương trình RSR000n (ACK ở UO11..18); chỉ RSR0001 phục vụ bridge |
| UO | CMDENBL(1) SYSRDY(2) PROGRUN(3) PAUSED(4) HELD(5) FAULT(6) TPENBL(8) BUSY(10) ACK(11-18) |

Mặc định robot "ấm": SDI1-3, SDI8 = 1 và RSR0001 đang chạy. `--cold`: không tín hiệu nào, chương trình chưa chạy, đang FAULT — dùng để thử nút *Chạy chương trình*.
(`sim_strict_select` = true thì xung RSR bị bỏ qua khi đang FAULT.)

### I/O khác, fixture, scanner
- Nhóm I/O `SDI SDO RDI RDO SI SO GI GO`. `sim_io_follow`: ngõ vào bám ngõ ra (mặc định `RDI[n]` bám `RDO[n]`, n = 1..8: hút là giữ được sản phẩm); `sim_inputs`:
  giá trị đầu (mặc định `RDI[20] = 1`, laser GO).
- **Fixture:** `TtoC_resultWaitdut` khi kết nối, `startOK`, sau thời gian test thì `resultPass` / `resultNG+item+value` / `resultRetest`, `readcodeOK`, `BarcodePass`, `fix_open/close`, `DUT_OUT → Waitdut`.
- **Scanner:** `LON` → mã 14 ký tự `SIM00000000001`…; `LOFF` dừng; `ERROR` khi không đọc được.
- **Không mô phỏng:** web service đăng nhập ESD (dùng `employee.offline_demo`), MySQL, SFCS.

## Lập kịch bản tình huống (`sim.*`, không cần arm)
Gửi bằng `BridgeClient.call(...)` hoặc bất kỳ client JSON-lines nào (`{"id":1,"cmd":"sim.state","args":{}}`).

| Lệnh | `args` | Tác dụng |
|---|---|---|
| `sim.state` | — | chương trình / UOP / thanh ghi / vị trí / trạm có DUT / fixture / scanner |
| `sim.set` | `kind, index, values` | ép giá trị ngõ vào (cạnh SDI tác động như dây thật) |
| `sim.inject` | `fail_next`, `verify_fail`, `responding`, `bad_stations` | robot lỗi lệnh kế tiếp / đọc lại sai / không trả lời (TIMEOUT) / trạm gây lỗi |
| `sim.reset` | `cold` | về trạng thái ấm hoặc lạnh |
| `sim.fixture` | `n`, `forced_results:["NG","PASS"]`, `pass_rate`, `test_time`, `error`, `drop`, `send:"<khung>"` | điều khiển ATS của fixture n |
| `sim.scanner` | `fail_next`, `no_read_rate` | scanner không đọc được |

Ví dụ: ép fixture 2 ra NG hai lần: `sim.fixture {"n": 2, "forced_results": ["NG","NG"], "test_time": 1}`; ATS rớt mạng: `sim.fixture {"n": 2, "drop": true}`.

## Hướng dẫn sửa
- **Thêm lệnh bridge:** `Bridge.cmd_<tên>` (`a.b` → `cmd_a_b`). Dùng `Err("MÃ_LỖI", "...")` với **chuỗi mã viết thẳng** và mã phải có trong `rcs2/robot/protocol.py`
  (test `test_matches_rcs2_protocol_constants` quét mã lỗi trong file).
- **Thêm hành vi robot / UOP:** `SimRobot._on_sdi` (cạnh tín hiệu), `uo_value`, `_run_command`/`_apply` (hiệu ứng của lệnh), `_take`/`_leave` (DUT).
- **Thêm tin ATS:** `SimFixture._handle`, `_run_test`, `result_frame`; đồng thời `rcs2/ats/mock_ats.py` nếu demo cần.
- **Thêm lệnh kịch bản:** `Bridge.cmd_sim_<tên>`; thêm vào bảng ở trên và docstring đầu file.
- **Thêm cài đặt:** `DEFAULTS` (đầu file) + tham số dòng lệnh trong `build_parser`/`build_config`.
- **Ràng buộc:** một file, chỉ thư viện chuẩn, cú pháp Python 3.8 (`ast.parse(feature_version=(3,8))` được test canh), hằng số giao thức **trùng** `rcs2/robot/protocol.py`.

## Test
`python run_tests.py simulator` — `test_bridge_simple` (giao thức, arm, giới hạn, watchdog), `test_sim_cell` (fixture, scanner, trạm, dòng lệnh, **NewRCS chạy cả chu kỳ trên simulator**).
`test_bridge_gui` (Tk của bridge thật) tự bỏ qua vì `bridge_gui.py` không có trong repo.
