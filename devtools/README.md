# `devtools/` — công cụ cho người phát triển (không thuộc ứng dụng)

| Thư mục | Dùng để |
|---|---|
| `ui_preview/` | dựng **MainWindow thật** trên runtime giả, chụp ảnh và kiểm tra "hợp đồng" nút ↔ dữ liệu |
| `sfcs_probe/` | thăm dò web service SFCS (chỉ gọi hàm chỉ-đọc) để tìm trường "stage" của một serial |

## `ui_preview/`
```powershell
cd devtools\ui_preview
python preview.py            # lưu shots\1_logged_out.png ... (nhiều trạng thái, kích thước cửa sổ); 10_flow.png = luồng tray, 11_ / 12_calibration*.png = hộp thoại hiệu chuẩn
python contract_test.py      # in PASS/FAIL từng kiểm tra, cuối cùng "RESULT: ALL OK"
```
- `preview.py` chứa **runtime giả** (`FakeRuntime`, `FakeEngine`) và các **snapshot mẫu** (`snap_running()`...). Khi thêm khóa vào `Engine.snapshot()` thì thêm vào đây.
- `contract_test.py` nhấn nút thật trên cửa sổ thật và kiểm tra: nút nào bật/tắt trong trạng thái nào, nút gọi đúng hàm của runtime, không có popup ngoài ý muốn,
  chữ báo lỗi/đăng nhập... Sau khi sửa `rcs2/ui/` hãy chạy cả hai và **xem ảnh** (`shots\2_running.png`, `10_tray_tab.png`...).
- Chạy offscreen, không mở cửa sổ. Cần `venv` của dự án (có PySide6). Nếu ảnh hiện chữ thành ô vuông (nền offscreen không thấy font): `$env:QT_QPA_FONTDIR='C:\Windows\Fonts'` trước khi chạy.

## `sfcs_probe/`
`test1.py` in danh sách hàm của WSDL (cần `pip install zeep`); `test2.py` thăm dò một serial qua các hàm **chỉ đọc** và lưu `sfcs_probe_<serial>.json`.
**Không** thêm hàm Set/Insert/Update/Delete/Hold/Start vào danh sách thăm dò; hỏi quản trị SFC trước khi thêm bất kỳ hàm nào. Chưa tích hợp vào NewRCS
(kiểm tra stage SFCS còn nằm trong "chưa chuyển" ở `docs/FEATURES.md`).
