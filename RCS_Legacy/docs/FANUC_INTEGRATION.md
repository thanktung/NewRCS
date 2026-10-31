# Hướng dẫn nâng cấp chương trình Fanuc lên giao thức v2

Đối tượng đọc: người viết/chỉnh chương trình trên robot (TP / KAREL).
Đặc tả đầy đủ của giao thức: `docs/PROTOCOL_V2.md`. Hành vi chuẩn có thể chạy được để so sánh:
`python sim/robot_simulator.py --protocol v2`.

> Các đoạn mã dưới đây là **giả mã** (pseudo-code) mô tả logic, không phải cú pháp KAREL/TP.
> Tên tính năng cụ thể (Socket Messaging, task KAREL, biến hệ thống) tuỳ phiên bản controller của bạn.

## 1. Thay đổi cần làm, theo thứ tự ưu tiên

| # | Việc | Lợi ích | Bắt buộc? |
|---|---|---|---|
| 1 | Đọc `#<seq>` đầu dòng, **echo seq** trong mọi phản hồi | Không còn nhầm phản hồi giữa các lệnh | Có |
| 2 | Gửi `ACK:<seq>` ngay khi nhận lệnh | Phân biệt "chưa nhận" với "đang chạy lâu" | Có |
| 3 | Gửi `DONE:<seq>:<NAME>` khi xong, `ERR:<seq>:<NAME>:<idx>:<CODE>` khi lỗi | PC biết lý do lỗi, không đợi timeout 30 s | Có |
| 4 | Trả lời `STATUS` bằng task riêng, kể cả khi đang chạy | Phát hiện alarm/E-stop tức thì | Tuỳ chọn |
| 5 | Hỗ trợ `RESET` | Người vận hành xóa lỗi từ UI | Tuỳ chọn |
| 6 | Hỗ trợ batch (nhiều item/lệnh, ngăn cách `\|`) | Giảm số vòng gửi/nhận | Tuỳ chọn |

Có thể làm từng bước: 1–3 trước (đã đủ để chuyển `protocol = v2`), 4–6 sau.

## 2. Kiến trúc đề xuất: tách nhận lệnh và chuyển động

```
 ┌─────────────── Task A: RECEIVER (không bao giờ bị chặn) ───────────────┐
 │ loop:                                                                   │
 │    line = socket_read_line()                                            │
 │    cmd  = parse(line)               # seq, name, items[]                │
 │    if cmd invalid        → send "ERR:<seq>:<NAME>:0:BAD_ARG"           │
 │    if cmd.name == STATUS → send "STAT:<seq>:<state>"   (ngay lập tức)  │
 │    if cmd.name == RESET  → clear_error(); send ACK + DONE              │
 │    else (motion):                                                       │
 │         if motion_busy   → send "ERR:<seq>:<NAME>:0:BUSY"              │
 │         else             → send "ACK:<seq>"; queue.put(cmd)            │
 └─────────────────────────────────────────────────────────────────────────┘
 ┌─────────────── Task B: MOTION ──────────────────────────────────────────┐
 │ loop:                                                                    │
 │    cmd = queue.get();  motion_busy = TRUE                                │
 │    for idx, item in enumerate(cmd.items or [None]):                      │
 │        code = execute(cmd.name, item)       # PICK/PLACE/LOAD/...        │
 │        if code != OK:                                                    │
 │            send "ERR:<seq>:<NAME>:<idx>:<code>"                          │
 │            motion_busy = FALSE; goto next                                │
 │    send "DONE:<seq>:<NAME>"                                              │
 │    motion_busy = FALSE                                                   │
 └──────────────────────────────────────────────────────────────────────────┘
```

Nếu controller không cho chạy hai task, có thể bỏ STATUS khi đang chạy motion (đặt
`heartbeat_interval = 0`); các mục 1–3 vẫn hoạt động.

**Quan trọng:** gửi `DONE` **sau khi** chuyển động thật sự kết thúc (robot đã rời khỏi vị trí
nguy hiểm và board đã ở đúng chỗ). RCS cập nhật mô hình ngay khi nhận `DONE` và ngay sau đó
báo cho box (`LOAD` → box bắt đầu test), nên `DONE` sớm có thể làm box đóng nắp khi robot chưa rút.

## 3. Quy tắc cho từng lệnh

| Lệnh | Việc robot làm | Mã lỗi thường gặp |
|---|---|---|
| `PICK:t,s,h` | Đến `tray t` ô `s`, hút, kiểm tra chân không, gắn vào `head h` | `NO_PART`, `VAC_FAIL`, `TRAY_EMPTY`, `COLLISION` |
| `PLACE:t,s,h` | Đặt board từ `head h` xuống `tray t` ô `s` (`t=0` → NG tray), nhả, kiểm tra | `VAC_FAIL` (không nhả được), `COLLISION` |
| `LOAD:b,h` | Đặt board từ `head h` vào `box b` | `BOX_NOT_READY`, `COLLISION` |
| `UNLOAD:b,h` | Lấy board từ `box b` lên `head h` | `BOX_NOT_READY`, `VAC_FAIL`, `NO_PART` |
| `CHANGE` | Đổi khay (Tray 2 vào vị trí Tray 1) | `ALARM`, `COLLISION` |

- `NO_PART` ở `PICK`: RCS coi ô đó trống và **tiếp tục chạy** (không FAULT). Dùng mã này khi cảm biến
  báo ô thật sự không có board.
- Các lỗi còn lại đều đưa RCS vào FAULT → người vận hành kiểm tra, sửa tay trạng thái rồi xác nhận.
  Vì vậy robot **không nên tự thử lại** thao tác bị lỗi mà không báo; nếu có logic thử lại nội bộ,
  chỉ báo `ERR` sau khi thử lại thất bại.
- Phản hồi lỗi phải chính xác về **`idx`**: RCS dựa vào đó để biết board nào đã chuyển chỗ.

## 4. Batch

- Robot thực hiện các item theo thứ tự đã gửi (hoặc tối ưu đường đi, miễn báo `idx` đúng với thứ tự
  trong lệnh).
- Lỗi ở item `k`: item `0..k-1` đã xong (đã chuyển chỗ thật sự), item `k..` chưa làm.
- Giới hạn số item: `batch_max_items` (mặc định 4). Cần ≤ số head và robot chạy được liên tục.
- Một lệnh batch có thể rất dài → `robot_recv_timeout` phải ≥ thời gian tối đa của cả batch.

## 5. Checklist nghiệm thu phía robot

Chạy RCS ở `mode = sim`/`real` với `protocol = v2` và kiểm tra từng dòng:

- [ ] Mọi phản hồi mang đúng `seq` của lệnh.
- [ ] `ACK` đến trong < 1 s kể cả khi robot đang bận lệnh trước (lúc đó trả `ERR…:BUSY`, không nuốt lệnh).
- [ ] `DONE` chỉ gửi sau khi chuyển động xong.
- [ ] Rút chân không / cố tình đặt khay trống → nhận đúng `VAC_FAIL` / `NO_PART` với `idx` đúng.
- [ ] Batch 3 item, lỗi ở item giữa → item đầu đã xong thật, các item sau không bị di chuyển.
- [ ] Ngắt cáp mạng giữa chừng → robot không tự chạy lệnh cũ khi kết nối lại; chờ lệnh mới.
- [ ] Kết nối lại: robot chấp nhận kết nối mới và bỏ buffer cũ.
- [ ] (nếu có) `STATUS` trả lời trong khi robot đang chạy; `ALARM`/`ESTOP` phản ánh đúng.
- [ ] (nếu có) `RESET` xóa được trạng thái lỗi chương trình, không tự đưa robot ra khỏi E-stop.
- [ ] Lệnh lạ / thiếu tham số → `ERR:<seq>:<NAME>:0:BAD_ARG`, robot không chết.

## 6. Chạy thử không cần robot thật

```
cd RCS
python sim/robot_simulator.py --protocol v2 --port 6000      # robot giả
python sim/box_simulator.py --count 30 --start-port 5001     # 30 box giả
python main.py                                               # station.ini: mode = sim, protocol = v2
```

Simulator hỗ trợ tiêm lỗi (`inject_error`, `hang_next`, `set_alarm`) để diễn tập các tình huống
trong checklist ở trên; xem các bài test trong `tests/test_clients.py` và `tests/test_e2e.py`.
