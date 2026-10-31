# Module `rcs2/ui` — giao diện PySide6 (Fluent, nền sáng)

Đây là **nơi duy nhất được dùng Qt** (`PySide6`); test kiến trúc canh điều này. Giao diện **chỉ đọc** `engine.snapshot()` mỗi 250 ms và **gọi**
các hàm của `Runtime` / `Engine`. Không chứa logic nghiệp vụ.

## Cấu trúc
```
ui/
├─ main.py                  điểm vào: tham số dòng lệnh, log file, dựng Runtime + MainWindow, --demo
├─ kit/                     "bộ dụng cụ" giao diện, không biết engine / runtime
│   ├─ fluent.py            token màu (ACCENT, DANGER...), icon, Pill, InfoBar, Surface, Panel, ToggleSwitch, FlowGrid, button(), confirm()
│   └─ theme.py             bảng màu + Qt style sheet (build_style), apply_app
├─ widgets/                 các khối của cửa sổ chính, MỖI KHỐI MỘT FILE (đều nhận dữ liệu qua update_from(...))
│   ├─ fixture_card.py      FixtureCard   thẻ fixture (trạng thái, SN, tiến độ test, bộ đếm, công tắc Dùng)
│   ├─ robot_panel.py       RobotPanel    liên kết, chương trình robot (UO[3]), lệnh R[1], nút Kết nối / Về an toàn / Chạy chương trình / Dừng robot
│   ├─ alarm_panel.py       AlarmPanel    danh sách alarm đang mở
│   ├─ totals_panel.py      TotalsPanel   dải KPI: tổng / đạt / không đạt / tỷ lệ
│   ├─ tray_panel.py        TrayView, TrayPanel   khối tray: các tray có trong settings xếp **một hàng ngang** (Input | NG | Output 1 | Output 2), mỗi tray chỉ có tên, nút reset ("Nạp lại" cho Input, "Đã dọn" cho các tray còn lại) và các ô (màu theo số phận của sản phẩm; ô tự co để hiện đủ mọi hàng / cột). Không có kích thước, số lượng, thanh tay hút, chú thích hay nút xóa trạng thái luồng
│   ├─ texts.py             nhãn tiếng Việt cho hằng số của engine (STATE_TEXT, RESULT_TEXT, JOB_TEXT)
│   └─ __init__.py          re-export: windows chỉ cần `from ..widgets import FixtureCard, ...`
└─ windows/
    ├─ main_window.py       MainWindow: thanh lệnh, thẻ fixture, tab Tray hàng / Nhật ký, panel Robot + Alarm, vòng refresh()
    ├─ manual_dialog.py     ManualDialog: jog, đi tới điểm, dạy điểm, đầu hút, máy quét, laser, xóa lỗi; nút "Hiệu chuẩn luồng tray" (khi flow.mode = tray)
    ├─ calibration_dialog.py CalibrationDialog: dạy offset các tay, 3 điểm mỗi tray, vị trí box; tính + đưa từng tay tới ô / box để kiểm tra (6 giá trị)
    └─ login_dialog.py      LoginDialog: đăng nhập bằng mã thẻ
```
Phụ thuộc cho phép: `config`, `core` (chỉ hằng số của engine), `employee` (`EmployeeError`), `runtime`, `tools` (`--demo`).

## Cách một màn hình cập nhật
`MainWindow.refresh()` (QTimer 250 ms): kiểm tra tự đăng xuất → `snap = rt.engine.snapshot()` → mỗi widget `update_from(...)` → bật/tắt nút theo
quyền (`can(...)`), trạng thái chạy, **`snap["program_running"]`** (UO[3]). **Nút nào ghi vào robot phải bị khóa khi `program_running is False`**.

Thao tác blocking (kết nối, chạy/dừng chương trình, jog...) chạy bằng `MainWindow._run_task(nhãn, hàm)` hoặc `ManualDialog._run(...)`: thread worker,
kết quả về qua signal, chỉ ghi vào nhật ký (không popup). Nút **Chạy chương trình** và **Dừng robot** chạy ngay, **không** hỏi xác nhận.

## Hướng dẫn sửa
| Muốn | Sửa ở |
|---|---|
| Đổi màu / font / bo góc | `kit/fluent.py` (token màu) và `kit/theme.py` (style sheet) |
| Đổi chữ tiếng Việt của trạng thái | `widgets/texts.py` |
| Đổi kích thước ô tray | `widgets/tray_panel.py` → `TrayView.MAX_CELL`, `MIN_CELL`, `GAP` (kích thước tray `rows x cols` ở `settings.json`) |
| Đổi bố cục cửa sổ chính | `windows/main_window.py` (`__init__`, `_build_*`) |
| Đổi cách khóa nút theo quyền / trạng thái | `MainWindow.refresh`, `RobotPanel.update_from`, `ManualDialog.refresh` |
| Thêm cửa sổ / hộp thoại | `windows/<ten>.py` (kế thừa `QDialog`), mở từ `main_window.py` |

### Thêm một khối (panel) mới vào cửa sổ chính
1. `widgets/<ten>.py`: lớp kế thừa `Panel` hoặc `Surface` (từ `..kit.fluent`), có `update_from(dữ_liệu)`.
2. Đăng ký trong `widgets/__init__.py`.
3. `windows/main_window.py`: tạo, đặt vào layout, gọi `update_from(...)` trong `refresh()`.
4. Nếu cần dữ liệu mới: thêm khóa vào `Engine.snapshot()` (xem `core/README.md`) và vào dữ liệu giả của `devtools/ui_preview/preview.py`.
5. Kiểm tra bằng `devtools/ui_preview` (ảnh chụp + `contract_test.py`).

### Luồng tray trên giao diện
`snapshot["flow"]` (None ở chế độ classic) mang sổ sách: `heads` (mỗi tay có `state`: `empty` / `fresh` / `pass` / `ng` / `retest`), `input_cells` (mỗi ô tray Input: `fresh` / `empty` / `pass`), `ng_used` (số ô tray NG đã có NG), `out_used` (số ô đã có hàng PASS của từng tray output), `stats`. `TrayPanel.update_from(trays, flow)` tô màu: ô input xanh dương = chưa test, xanh lá = pass, **xám = trống**; ô NG đỏ = NG, xám = trống; ô output xanh lá = pass, xám = trống; tay: xanh dương chưa test, xanh lá pass, đỏ ng, cam retest, xám trống; thẻ fixture hiện `SN · ô đã lấy ra · lần test`. Thêm trạng thái mới: `FLOW_COLOR` / `FLOW_TEXT` trong `widgets/tray_panel.py` và `HEAD_STATE` trong `core/flow.py`.

### Thêm một nút gọi thao tác của Runtime
1. Thêm phương thức vào `Runtime` (xem `runtime/README.md`), vì giao diện không tự nói chuyện với robot.
2. Tạo nút bằng `F.button("Nhãn", "icon", "danger"|"subtle"|None)` và `clicked.connect(...)`.
3. Gọi qua `_run_task` / `_run` (thread worker). Khóa nút theo `can("operate"|"manual"|"teach")` và `program_running`.
4. Cần hỏi xác nhận (thao tác nguy hiểm, **không** dùng cho Chạy/Dừng robot): `F.confirm(self, "Tiêu đề", "Nội dung", warning=True)`.

### Quy ước
- Widget chỉ nhận dữ liệu qua `update_from`, không giữ tham chiếu tới engine. Có `objectName` để style sheet nhắm tới.
- Chữ hiển thị là **tiếng Việt**; hằng số engine giữ tiếng Anh (`widgets/texts.py` dịch).
- Mọi số liệu giao diện phải chịu được `None` / khóa thiếu (snapshot giả của test có thể thiếu khóa mới: dùng `snap.get(...)`).

## Test và xem thử
- `python run_tests.py ui` — smoke test dựng cửa sổ chính (offscreen).
- `devtools/ui_preview/preview.py` — dựng **MainWindow thật** trên runtime giả và lưu ảnh vào `shots/`; `contract_test.py` kiểm tra "hợp đồng" nút ↔ snapshot.
  Chạy cả hai sau khi sửa giao diện.
