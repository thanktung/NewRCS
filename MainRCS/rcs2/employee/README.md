# Module `rcs2/employee` — đăng nhập và phân quyền

Đăng nhập bằng **thẻ nhân viên**, tra qua web service ESD, rồi suy ra **cấp truy cập** từ **mã bộ phận**. Không import module khác của `rcs2`.

## File
| File | Nội dung |
|---|---|
| `service.py` | `EmployeeService` (`lookup`, `login`), `AccessPolicy`, `LoginResult`, `Employee`, `EmployeeError`, `build_soap/parse_response/http_post_soap` |
| `__init__.py` | re-export, nên viết `from rcs2.employee import EmployeeService, EmployeeError` |

## Luồng đăng nhập
1. Tên đăng nhập = **mã thẻ 8 ký tự chữ/số**; mật khẩu = mật khẩu chung (mặc định `wnc000000`, có thể đổi bằng `default_password` trong `departments.json`).
   Mật khẩu chung **không phải bí mật**; cổng thật là thẻ có tồn tại và bộ phận có trong danh sách.
2. Thẻ → SOAP `IsAuthorizedMeasuredESDEmp_NEW` → `ID_Tên_BộPhận_TrạngThái`. Tên quá ngắn (< 4 ký tự) = "thẻ không tồn tại".
3. Mã bộ phận (ví dụ `MNM561`) tra trong `config/departments.json` → cấp 1..5 (5 cao nhất). Không có trong danh sách → `default_level`
   (0 = từ chối). Hỗ trợ mẫu `MNM5*`.
4. `LoginResult(employee, job="L<cấp> <bộ phận>", level, allowed)`; `job` được ghi vào cột `StaffBP` của bảng login.

File `departments.json` được **đọc lại mỗi lần đăng nhập**: sửa xong không cần khởi động lại.

## Quyền hạn (`ACTIONS`)
`operate` (Bắt đầu/Tạm dừng/Dừng, công tắc fixture, đặt lại, kết nối robot, chạy/dừng chương trình robot), `manual` (cửa sổ Thủ công và jog),
`teach` (lưu điểm đã dạy). Cấp tối thiểu của mỗi quyền đặt ở `departments.json` → `min_level` (mặc định 1 = mọi người).
UI hỏi bằng `MainWindow.can("operate" | "manual" | "teach")`.

## Cài đặt (`settings.json` → `employee`)
`url`, `timeout_s`, `check_start` / `check_end`, `departments_path`, `offline_demo` (không gọi ESD, người dùng "Demo User" cấp 5),
`auto_logout_s` (0 = không tự đăng xuất), `auto_logout_idle` (tính từ lần dùng chuột/phím cuối thay vì từ lúc đăng nhập).
Tự đăng xuất do `runtime/session.py` thực hiện.

## Hướng dẫn sửa
### Thêm một quyền mới (ví dụ `recipe`)
1. `service.py`: thêm vào `ACTIONS` và `DEFAULT_MIN_LEVEL`.
2. `config/departments.json` (+ example): thêm khóa trong `min_level`.
3. UI: kiểm tra `self.main.can("recipe")` ở nút / cửa sổ cần khóa (`ui/windows/`).
4. Test: `tests/employee/test_employee.py` (mẫu `min_level`).

### Đổi cách tra thẻ (dịch vụ khác)
Thay `http_post_soap` / `build_soap` / `parse_response` (hoặc truyền `transport=` khi tạo `EmployeeService`), giữ nguyên kết quả là `Employee`.
Test dùng ESD giả trong `tests/employee/test_employee.py`.

### Thêm bộ phận / đổi cấp
Chỉ sửa `config/departments.json`.

## Test
`python run_tests.py employee` — thẻ sai, mật khẩu sai, bộ phận không có cấp, mẫu `*`, `min_level`, dịch vụ không tới được, kiểm tra file `departments*.json` đã gửi kèm.
