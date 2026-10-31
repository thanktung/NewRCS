# Module `rcs2/ats` — nói chuyện với chương trình ATS của từng fixture

Mỗi fixture có một **chương trình ATS** (test tự động) lắng nghe trên một cổng TCP. NewRCS là **client**: kết nối, gửi nhịp tim,
gửi lệnh và nhận kết quả. Module này chỉ lo khung tin và đường truyền; việc diễn giải kết quả (PASS/NG → lấy ra đâu) nằm ở `core/engine.py`.

## File
| File | Nội dung |
|---|---|
| `protocol.py` | Khung tin `<text>_CEND`, `FrameDecoder` (ghép/cắt luồng TCP), `parse_message()` → `AtsEvent`, các hàm dựng tin gửi đi |
| `client.py` | `AtsClient`: thread giám sát tự kết nối lại, nhịp tim `aaa` mỗi `heartbeat_s`, callback `on_event` / `on_connection` |
| `mock_ats.py` | `MockAts`: ATS giả (chạy được độc lập: `python -m rcs2.ats.mock_ats --port 8888`), dùng cho `--demo` và test |

## Giao thức (không đổi so với RCS cũ)
- Khung UTF-8 kết thúc bằng `_CEND`; các trường cách nhau bằng `+`.
- **NewRCS → ATS:** `CtoT_placeDUTOK`, `B1=<SN>,`, `CtoT_placeBarcode`, `DUT_OUT`, `f_open`, `f_close`, `aaa` (nhịp tim), `fixstatus`.
- **ATS → NewRCS:** `TtoC_resultPass`, `TtoC_resultNG+<item>+<value>`, `TtoC_resultRetest`, `...Retest1`, `...FQC`, `...Warning`,
  `TtoC_resultWaitdut` (sẵn sàng nhận DUT), `TtoC_resultBusy`, `TtoC_BarcodePass+<SN>`, `TtoC_BarcodeNG`, `TtoC_startOK`,
  `TtoC_readcodeOK`, `fix_open`, `fix_close`, `fix_error`, `TtoC_resultOffsetPass|NG...`, `TtoC_AVI...`.
- Nhận diện theo kiểu **"chứa chuỗi", không phân biệt hoa thường** như chương trình cũ, nhưng thử tên **cụ thể trước**
  (`Retest1` trước `Retest`, `BarcodePass` trước `Barcode`) — thứ tự trong bảng `_RULES` là quan trọng.

## Hướng dẫn sửa
### Thêm một loại tin mới từ ATS
1. `protocol.py`: thêm hằng loại sự kiện (ví dụ `NEW = "NEW"`), thêm dòng vào `_RULES` **đúng vị trí** (tên dài / cụ thể đặt trước),
   thêm cách bóc trường trong `parse_message` nếu có tham số, nếu là kết quả thì thêm vào `AtsEvent.is_result`.
2. `core/engine.py`: xử lý trong `_on_ats` (và `RESULT_LABEL` / `UNLOAD_SEQUENCE` nếu là kết quả).
3. Cho simulator biết tin mới: `ats/mock_ats.py` (`_handle`, `_run_test`) **và** `bridge32/bridge_simple.py` (`SimFixture`).
4. Test: `tests/ats/test_ats.py` (phân tích tin) + `tests/core/test_engine.py` (cách engine phản ứng).

### Thêm một lệnh gửi sang ATS
`protocol.py` thêm hàm dựng tin, `client.py` thêm phương thức mỏng gọi `self.send(...)`, `core/sequence.py` thêm tên vào `ATS_ACTIONS`
(và nhánh trong `SequenceRunner._do` nếu lệnh có tham số), mock/simulator trả lời tương ứng.

### Đổi nhịp tim / thời gian chờ
`settings.json` → `ats.heartbeat_s`, `ats.connect_timeout_s`, `ats.retry_s` (đọc trong `runtime/runtime.py` khi tạo `AtsClient`).

### Thêm / đổi fixture
Chỉ sửa `settings.json` → `ats.fixtures` (`host`, `port`, `station`, `robot_station`). **Danh sách này thay hẳn mặc định**, hãy liệt kê đủ.

## Lưu ý
- Callback `on_event` / `on_connection` chạy trên thread của client: phải ngắn, chỉ post sự kiện cho engine (`Engine.on_ats_event`).
- `AtsClient.send()` trả `False` và **bỏ tin** khi chưa kết nối; nơi gọi phải kiểm tra (engine báo alarm 9012).

## Test
`python run_tests.py ats` — phân tích khung, ghép luồng bị cắt, kết nối lại, nhịp tim.
