# MainRCS — mã nguồn NewRCS (bản đồ module và hướng dẫn sửa)

Chương trình giám sát cell robot. Gói Python tên **`rcs2`** (`python -m rcs2`), giao diện PySide6, nói chuyện với robot FANUC qua **bridge** TCP/JSON
và với **ATS** của từng fixture qua TCP. Tổng quan sản phẩm: `../README.md`. Kiến trúc chi tiết: `../docs/ARCHITECTURE.md`.

## Bản đồ thư mục
| Thư mục | Vai trò | Đọc thêm |
|---|---|---|
| `rcs2/config/` | giá trị mặc định + nạp `settings.json` | [README](rcs2/config/README.md) |
| `rcs2/core/` | **bộ não**: engine, luồng tray (planner, stage), sequence runner, tray | [README](rcs2/core/README.md) |
| `rcs2/robot/` | client bridge, giao thức, chạy/dừng chương trình robot (UOP) | [README](rcs2/robot/README.md) |
| `rcs2/ats/` | giao thức + client ATS của fixture, ATS giả | [README](rcs2/ats/README.md) |
| `rcs2/devices/` | End Effector: đầu hút, máy quét, laser | [README](rcs2/devices/README.md) |
| `rcs2/reporting/` | outbox SQLite → MySQL dashboard, ErrorTracker | [README](rcs2/reporting/README.md) |
| `rcs2/employee/` | đăng nhập thẻ + phân quyền theo bộ phận | [README](rcs2/employee/README.md) |
| `rcs2/runtime/` | lắp ráp mọi thứ + thao tác của người vận hành (không có Qt) | [README](rcs2/runtime/README.md) |
| `rcs2/ui/` | giao diện PySide6 (`kit/`, `widgets/`, `windows/`) | [README](rcs2/ui/README.md) |
| `rcs2/tools/` | bridge_cli, chế độ demo | [README](rcs2/tools/README.md) |
| `bridge32/` | `bridge_simple.py`: **simulator một file** (bridge giả + fixture + scanner) | [README](bridge32/README.md) |
| `config/` | file cấu hình thật (`settings.json`, `sequences.json`, `departments.json`) | [README](config/README.md) |
| `tests/` | test theo module + `support/` + test kiến trúc | [README](tests/README.md) |
| `data/`, `logs/` | outbox SQLite, log (sinh ra khi chạy, không sửa tay) | |

## Quy tắc phụ thuộc (có test canh: `python run_tests.py architecture`)
```
                    ┌──────────┐
                    │    ui    │──► tools (chỉ --demo)
                    └────┬─────┘
                         ▼
                    ┌──────────┐
                    │ runtime  │   lắp ráp, KHÔNG có Qt
                    └────┬─────┘
        ┌────────┬───────┼────────┬───────────┬──────────┐
        ▼        ▼       ▼        ▼           ▼          ▼
      core ──► ats    robot    devices   reporting   employee    config
        └────────────────────► devices
```
| Module | Được import |
|---|---|
| `config`, `robot`, `ats`, `devices`, `reporting`, `employee` | không module nào khác của `rcs2` |
| `core` | `ats`, `devices` |
| `tools` | `ats`, `robot`, `core` (flow_sim) |
| `runtime` | `config`, `core`, `robot`, `ats`, `devices`, `reporting`, `employee` |
| `ui` | `config`, `core` (hằng số), `employee`, `runtime`, `tools` |

Thêm nữa: **Qt chỉ ở `ui`**; ứng dụng không import `tests` hay simulator (trừ `tools/demo.py`); `bridge32/bridge_simple.py` chỉ dùng thư viện chuẩn.
Muốn thêm một phụ thuộc mới: sửa bảng `ALLOWED` trong `tests/test_architecture.py` **và** bảng này, kèm lý do.

## Muốn sửa X thì vào đâu
| Muốn... | Vào |
|---|---|
| Đổi IP/cổng fixture, bridge, scanner; đổi kích thước tray; bật MySQL | `config/settings.json` ([giải thích](config/README.md)) |
| Đổi điểm robot (dạy lại) | cửa sổ Thủ công → **Hiệu chuẩn luồng tray** (lưu vào `config/sequences.json`) |
| Đổi trình tự robot trong một việc (hút, quét mã, laser...) | `rcs2/core/tasks.py` ([bảng](rcs2/core/README.md)) |
| Đổi mức quyền / thêm bộ phận | `config/departments.json` |
| Đổi robot làm việc gì tiếp theo | `rcs2/core/planner.py` |
| Đổi xử lý kết quả, alarm | `rcs2/core/engine.py` |
| Thêm loại bước sequence | `rcs2/core/sequence.py` |
| Thêm lệnh vào bridge / đổi giao thức robot | `bridge32/bridge_simple.py` + `rcs2/robot/` |
| Đổi trình tự chạy / dừng chương trình robot (UOP) | `rcs2/robot/uop.py` |
| Chặn / cho phép thao tác khi UO[3] (chương trình robot) dừng | `rcs2/runtime/bridge_link.py`, `rcs2/core/engine.py` |
| Thêm nút / thao tác thủ công | `rcs2/runtime/robot_ops.py` + `rcs2/ui/windows/manual_dialog.py` |
| Luồng tray: luật ưu tiên, số lần test lại, trình tự hút / nhả | `rcs2/core/planner.py`, `dut.py`, `tasks.py` ([bảng](rcs2/core/README.md)) |
| Luồng tray: dạy offset tay, tray 3 điểm, vị trí box | cửa sổ Thủ công → **Hiệu chuẩn luồng tray** (`rcs2/ui/windows/calibration_dialog.py`, `rcs2/runtime/flow_ops.py`) |
| Thêm tin nhắn ATS mới | `rcs2/ats/protocol.py` + `rcs2/core/engine.py` |
| Thêm tool cho End Effector | `rcs2/devices/` (xem [README](rcs2/devices/README.md)) |
| Thêm cột / loại báo cáo MySQL | `rcs2/reporting/sql_targets.py` + `data_sink.py` |
| Đổi giao diện (màu, bố cục, nhãn, kích thước ô tray) | `rcs2/ui/` ([bảng](rcs2/ui/README.md)) |
| Thêm cài đặt mới | `rcs2/config/defaults.py` rồi `config/settings.example.json` |
| Mô phỏng thêm tình huống không cần robot | `bridge32/bridge_simple.py` (`sim.*`) |

## Chạy
```powershell
cd MainRCS
python run_rcs2.py                       # thật: cần config\settings.json và config\sequences.json
python run_rcs2.py --demo --autorun      # demo trong tiến trình, không cần phần cứng
python bridge32\bridge_simple.py         # simulator cả cell (bridge + 13 fixture + scanner) ở tiến trình riêng
python -m rcs2.tools.bridge_cli --host 127.0.0.1 status
python -m rcs2.tools.flow_sim            # thử luật ưu tiên của luồng tray (what-if, không robot)
```
Biến môi trường (bí mật không ghi vào file): `RCS_DB_PASSWORD` (MySQL), `RCS_BRIDGE_TOKEN` (bridge, tùy chọn).

## Kiểm thử
```powershell
python run_tests.py                      # tất cả
python run_tests.py robot ats            # chỉ module vừa sửa
python run_tests.py core -k tray -v      # lọc theo tên, hiện từng test
python run_tests.py --list
python ..\devtools\ui_preview\contract_test.py     # sau khi sửa giao diện
```
**Quy trình sửa an toàn:** đọc README của module → sửa → chạy test của module → chạy `architecture` → nếu đụng giao diện thì chạy `devtools/ui_preview` → chạy toàn bộ.

## Quy ước
- **Comment trong code bằng tiếng Anh**; chữ hiển thị cho người dùng bằng tiếng Việt.
- **Dữ liệu thay vì code**: thứ gì đổi theo nhà máy (IP, địa chỉ I/O, kích thước tray, điểm robot) nằm trong `config/`, không nằm trong code.
- Mỗi module tự kiểm tra cấu hình của mình **lúc khởi động** và báo lỗi rõ ràng.
- **Bất biến an toàn (xuyên suốt, đừng phá):**
  1. Không ghi lệnh robot (R[1]) khi chương trình robot dừng (UO[3] = 0).
  2. Chuyển động chỉ khi đã `arm`; chỉ một client arm; không disarm giữa chừng một việc robot.
  3. **Dừng robot luôn được phép**, không bị khóa bởi trạng thái chạy.
  4. Bridge không thể dừng một chuyển động đang chạy: luôn để E-stop trong tầm tay, thử với override thấp.
  5. Dữ liệu báo cáo ghi outbox trước; không bao giờ chặn máy vì mạng / DB.
- Khi có `__pycache__`, `*.pyc`, `data/*.sqlite`, `logs/`: đều là sản phẩm sinh ra, không sửa tay (đã trong `.gitignore`).
