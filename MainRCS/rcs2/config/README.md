# Module `rcs2/config` — nạp cấu hình

## Làm gì / không làm gì
- **Làm:** giữ **giá trị mặc định** của mọi cài đặt (`defaults.py`) và nạp `config/settings.json` đè lên mặc định (`loader.py`).
- **Không làm:** không kiểm tra ý nghĩa của từng cài đặt. Mỗi module tự kiểm tra phần của mình khi khởi động
  (`core/tray.build_trays`, `robot/uop.normalize`, `devices/end_effector.build_end_effector`, `core/sequence.validate`...).
- Không import module nào khác của `rcs2` (xem quy tắc phụ thuộc ở `MainRCS/README.md`).

## File
| File | Vai trò |
|---|---|
| `defaults.py` | `DEFAULTS`: từ điển mặc định, mỗi nhóm có chú thích. **Nơi duy nhất** khai báo một cài đặt mới |
| `loader.py` | `load_settings(path)` (deep-merge JSON lên `DEFAULTS`), `resolve_local_ip`, `detect_local_ip`, `env_secret`, `LEGACY_KEYS` |
| `__init__.py` | re-export, nên mọi nơi vẫn viết `from rcs2.config import DEFAULTS, load_settings` |

## Quy tắc nạp
- Gộp **đệ quy** theo từng khóa, **trừ** `ats.fixtures`: danh sách fixture trong `settings.json` **thay hẳn** danh sách mặc định
  (nên file phải liệt kê đủ mọi fixture).
- Khóa cũ đã bỏ (`hands`, `scanners`) làm `load_settings` báo lỗi kèm hướng dẫn chuyển sang `end_effector`.
- **Bí mật không nằm trong file**: mật khẩu MySQL đọc từ biến môi trường tên ghi ở `mysql.password_env`
  (mặc định `RCS_DB_PASSWORD`), token bridge từ `bridge.token_env` (`RCS_BRIDGE_TOKEN`) qua `env_secret()`.
- `identity.local_ip` rỗng thì tự lấy địa chỉ IPv4 đầu tiên bắt đầu bằng `10.` (dùng để đặt tên bảng MySQL).

## Hướng dẫn sửa
### Thêm một cài đặt mới
1. Thêm vào `defaults.py` trong đúng nhóm, **kèm chú thích** (đơn vị, ý nghĩa, giá trị an toàn).
2. Đọc ở nơi dùng: `cfg["nhóm"]["khóa"]` (nhờ có mặc định nên không cần `.get`).
3. Nếu giá trị cần kiểm tra (phạm vi, kiểu), kiểm tra **trong module sở hữu** và ném lỗi rõ ràng khi khởi động
   (mẫu: `core/tray.check_size`, `robot/uop.normalize`).
4. Thêm vào `config/settings.example.json` (file này được test nạp thử) và mô tả ở `MainRCS/config/README.md`.
5. Chạy: `python run_tests.py config` (kiểm tra file ví dụ vẫn hợp lệ) và test của module đọc cài đặt đó.

### Đổi giá trị mặc định
Sửa trong `defaults.py`. Lưu ý `settings.json` thật của nhà máy vẫn đè lên mặc định, nên đổi mặc định chỉ có tác dụng với
khóa mà `settings.json` **không** khai báo.

### Bỏ / đổi tên một khóa
Thêm khóa cũ vào `LEGACY_KEYS` (kèm lời khuyên) để file cũ báo lỗi rõ thay vì bị bỏ qua âm thầm.

## Test
`python run_tests.py config` — nạp `settings.example.json` và `sequences.example.json`, bảo đảm chúng luôn hợp lệ.
