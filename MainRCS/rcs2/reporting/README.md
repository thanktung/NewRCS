# Module `rcs2/reporting` — báo cáo dữ liệu lên MySQL dashboard (qua outbox cục bộ)

Mục tiêu: **không bao giờ mất dữ liệu** và **không bao giờ chặn máy** vì mạng/DB. Mọi sự kiện cần báo cáo được ghi vào một file SQLite cục bộ
(outbox) trước, một thread nền đẩy dần lên MySQL theo đúng thứ tự, thử lại có giãn cách khi lỗi. Bảng MySQL **giữ nguyên tên và cột của RCS cũ**
để dashboard hiện có không phải sửa.

Không import module khác của `rcs2` (engine / runtime gọi vào đây, không ngược lại).

## File
| File | Nội dung |
|---|---|
| `outbox.py` | `Outbox`: SQLite (`outbox`, `meta`, `open_errors`): `enqueue`, `pending`, `delete`, `mark_failed`, `count`, `set_meta/get_meta`, `save_open_error/open_errors` |
| `data_sink.py` | `DataSink`: `emit(kind, payload)` + `emit_login/result/robot_speed/ats_hourly`, thread upload, `stats()`; `ErrorTracker`: alarm → dòng "khoảng thời gian" |
| `sql_targets.py` | `SqlTargets`: tên bảng theo tháng, DDL `CREATE TABLE IF NOT EXISTS`, câu `INSERT` |
| `mysql_writer.py` | `MySqlWriter.write_batch(items)`: tạo bảng khi cần, ghi theo thứ tự, dừng ở mục lỗi đầu tiên |

## Luồng dữ liệu
```
engine / runtime ──emit()──► Outbox (SQLite, ngay lập tức, không bao giờ ném lỗi)
                                 │  thread "data-sink" (mỗi flush_interval_s, giãn cách khi lỗi)
                                 ▼
                          MySqlWriter.write_batch ──► bảng MySQL cũ        (chỉ khi mysql.enabled và có mật khẩu)
```
Các loại bản ghi (`kind`) và bảng:

| kind | Bảng | Ai phát |
|---|---|---|
| `result` | `TestResult_{Model}_{stations}_{ip}_Y{năm}_M{tháng}` | engine, mỗi kết quả test |
| `login` | `LoginLog_...` | `Runtime.login` |
| `error` | `{Model}_{stations}_{ip}_Y..._M...` | `ErrorTracker.clear_error` (một dòng khi alarm **kết thúc**, có start + end) |
| `ats_hourly` | `ATSHourlyIDE_...` | (dành cho báo cáo theo giờ) |
| `robot_speed` | `RobotSpeed_{Model}_{stations}_{ip}` (không hậu tố tháng) | (dành cho báo cáo tốc độ) |

Tháng của tên bảng lấy từ **thời điểm của chính sự kiện**, nên bản ghi nằm chờ lâu vẫn vào đúng bảng tháng.

## Nhãn "DB tắt · N đã lưu" trên giao diện
- `DB tắt` = `mysql.enabled` là `false` **hoặc** thiếu biến môi trường mật khẩu (`mysql.password_env`, mặc định `RCS_DB_PASSWORD`): không upload.
- `N` = số dòng còn trong outbox (`Outbox.count()`), chưa upload. File nằm ở `outbox_path` (mặc định `data/outbox.sqlite`), **còn nguyên sau khi tắt chương trình**,
  nên N tích lũy qua nhiều lần chạy. Bật MySQL thì toàn bộ N được đẩy lên. Chế độ `--demo` dùng file riêng `data/outbox_demo.sqlite`.
- Muốn bỏ dữ liệu test cũ: tắt NewRCS rồi xóa file outbox.

## ErrorTracker (alarm → bản ghi)
`raise_error(code, message, key)` mở một khoảng lỗi (bỏ qua nếu `key` đã mở) và lưu vào `open_errors` của SQLite; `clear_error(key)` đóng nó và phát
dòng `error`. Mất điện / crash: `recover()` ở lần khởi động sau đóng các lỗi còn mở bằng mốc "lần cuối còn sống" (`heartbeat()` mỗi phút).
`active()` trả danh sách alarm đang mở cho giao diện.

## Hướng dẫn sửa
### Thêm một loại bản ghi mới
1. `sql_targets.py`: thêm vào `KINDS`, tên bảng trong `table()`, khóa thời gian trong `when_of()`, cột trong `ddl()`, câu `INSERT` trong `insert()`.
2. `data_sink.py`: thêm `emit_<loại>(...)` gọi `self.emit("<loại>", {...})` (payload phải đủ trường mà `insert()` đọc).
3. Nơi phát (engine / runtime) gọi `emit_<loại>`.
4. Test: `tests/reporting/test_data_sink.py` (mẫu `test_ddl_and_insert_shapes`).
> Đổi tên/cột bảng cũ sẽ làm dashboard hiện tại hỏng: chỉ **thêm** loại mới, đừng đổi loại cũ.

### Đổi chu kỳ upload, thông số kết nối
`settings.json` → `mysql` (`flush_interval_s`, `connect_timeout_s`, `host`, ...); mật khẩu chỉ qua biến môi trường.

### Đổi cách đặt tên bảng
Chỉ trong `SqlTargets` (`_base`, `table`). Tên có dấu backtick hoặc NUL bị từ chối.

## Lưu ý
- `emit()` không bao giờ ném lỗi và không bao giờ chờ mạng — đừng thêm xử lý mạng vào đường này.
- `MySqlWriter` nhận `connect_fn` để test dùng kết nối DB-API giả, không cần MySQL thật.

## Test
`python run_tests.py reporting` — tên bảng cũ, DDL/INSERT, batch một phần / lỗi toàn bộ, giữ thứ tự, thread upload, đóng khoảng lỗi, phục hồi sau crash.
