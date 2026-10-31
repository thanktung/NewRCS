# Giao thức RCS ↔ Robot Fanuc — v2

Tài liệu này là **hợp đồng** giữa phần mềm RCS (PC) và chương trình trên robot Fanuc.
Code tương ứng: `rcs/protocol/robot_v2.py` (encode/parse) và `rcs/clients/robot_client.py` (gửi/nhận).
Giao thức cũ (`legacy`) vẫn được hỗ trợ, xem mục 9.

## 1. Khung truyền

- TCP, PC là client, robot là server (`robot_host:robot_port` trong `station.ini`).
- Mỗi message là **một dòng văn bản ASCII kết thúc bằng `\n`** (robot nên chấp nhận cả `\r\n`).
- Không phân biệt hoa/thường ở tên lệnh và mã lỗi, nhưng PC luôn gửi chữ HOA.

## 2. Quy ước đánh số

| Đối tượng | Bắt đầu từ | Ghi chú |
|---|---|---|
| `box_id` | 1 | Box 1 … `box_count` |
| `head` | 0 | Head 0 … `gripper_heads-1` |
| `slot` | 0 | Ô trên tray, theo hàng: `slot = row * cols + col` |
| `tray_id` | 1 | 1 = Tray 1, 2 = Tray 2, **0 = NG tray** (chỉ dùng với PLACE) |
| `seq` | 1 | Số thứ tự lệnh, tăng dần, do PC cấp |

## 3. PC → Robot

```
#<seq> <NAME>[:<item>[|<item>...]];
```

| Lệnh | Item | Ý nghĩa |
|---|---|---|
| `PICK` | `tray,slot,head` | Hút board ở `tray[slot]` lên `head` |
| `PLACE` | `tray,slot,head` | Đặt board từ `head` xuống `tray[slot]` (`tray=0` → NG tray) |
| `LOAD` | `box,head` | Đặt board từ `head` vào `box` |
| `UNLOAD` | `box,head` | Lấy board từ `box` lên `head` |
| `CHANGE` | *(không có)* | Đổi khay: Tray 2 trượt vào vị trí Tray 1 |
| `STATUS` | *(không có)* | Hỏi trạng thái robot (xem mục 5) |
| `RESET` | *(không có)* | Xóa lỗi robot (sau khi người vận hành đã xử lý) |

Ví dụ:

```
#12 PICK:1,5,2;                    một board
#13 PICK:1,5,0|1,6,1|1,7,2;        batch 3 board (các item cách nhau bằng '|')
#14 LOAD:3,0|4,1;                  batch 2 box
#15 CHANGE;
#16 STATUS;
```

**Batch:** chỉ `PICK / PLACE / LOAD / UNLOAD`. Robot thực hiện các item **theo thứ tự**
(hoặc sắp xếp lại đường đi nếu muốn, miễn là báo lỗi đúng chỉ số item). Số item tối đa mỗi lệnh
= `batch_max_items` trong `station.ini` (robot phải xử lý được ít nhất con số đó).

## 4. Robot → PC

| Message | Khi nào gửi |
|---|---|
| `ACK:<seq>` | **Ngay** khi nhận và chấp nhận lệnh (trước khi chạy). Trong vòng `ack_timeout` (mặc định 3 s). |
| `DONE:<seq>:<NAME>` | **Toàn bộ** item đã hoàn thành. |
| `ERR:<seq>:<NAME>:<idx>:<CODE>` | Item thứ `<idx>` (tính từ 0) bị lỗi. Các item **trước** `idx` đã xong, từ `idx` trở đi **chưa được thực hiện**. Robot dừng lệnh này. |
| `STAT:<seq>:<STATE>` | Trả lời `STATUS`. |

Trình tự bình thường: `ACK` → (robot chạy) → `DONE`. Với lệnh bị từ chối ngay (sai tham số,
robot đang alarm...) robot gửi `ACK` rồi `ERR` (hoặc chỉ `ERR`).

```
PC    #13 PICK:1,5,0|1,6,1;
Robot ACK:13
Robot DONE:13:PICK

PC    #14 PICK:1,5,0|1,6,1;
Robot ACK:14
Robot ERR:14:PICK:1:VAC_FAIL      ← item 0 đã hút xong, item 1 lỗi hút chân không
```

### Mã lỗi (`CODE`)

| Mã | Ý nghĩa | Phản ứng của RCS |
|---|---|---|
| `VAC_FAIL` | Không đạt chân không / rơi board | FAULT |
| `NO_PART` | Không có board ở vị trí nguồn (PICK) | **Tự xử lý**: coi ô trống, cảnh báo, chạy tiếp |
| `COLLISION` | Va chạm / chạm giới hạn lực | FAULT |
| `TRAY_EMPTY` | Khay không có | FAULT |
| `BOX_NOT_READY` | Fixture chưa sẵn sàng cho robot (cửa/nắp) | FAULT |
| `ALARM` | Robot đang alarm | FAULT |
| `ESTOP` | Dừng khẩn | FAULT |
| `BAD_ARG` | Tham số sai (ngoài phạm vi, sai số lượng) | FAULT |
| `BUSY` | Robot đang chạy lệnh khác | FAULT |

Mã lạ vẫn được chấp nhận và hiển thị nguyên văn. Thêm mã mới: xem `docs/MAINTENANCE.md`.

## 5. STATUS / heartbeat

`#<seq> STATUS;` → `STAT:<seq>:<STATE>` với `STATE` ∈ `IDLE | BUSY | ALARM | ESTOP`.

- **Robot phải trả lời STATUS kể cả khi đang chạy một lệnh chuyển động** (cần một task nhận
  dữ liệu riêng, không bị chặn bởi motion). Nếu không làm được, để `heartbeat_interval = 0`.
- Khi `heartbeat_interval > 0`, RCS hỏi định kỳ; `ALARM`/`ESTOP` hoặc mất phản hồi → hệ thống vào FAULT ngay,
  không phải chờ timeout 30 s.

## 6. RESET

`#<seq> RESET;` → `ACK:<seq>` rồi `DONE:<seq>:RESET`.
Chỉ gửi khi người vận hành bấm **Xác nhận lỗi** trên UI. Robot xóa trạng thái lỗi của chương trình
(không được tự động đưa robot ra khỏi ESTOP vật lý).

## 7. Timeout và thử lại

| Tham số (`station.ini`) | Ý nghĩa |
|---|---|
| `[robot] ack_timeout` | Từ lúc gửi đến khi nhận `ACK` |
| `[timing] robot_recv_timeout` | Từ `ACK` đến `DONE`/`ERR` (thời gian tối đa của một lệnh) |

- **RCS không bao giờ gửi lại lệnh chuyển động** sau timeout (robot có thể vẫn đang chạy,
  gửi lại sẽ thực hiện hai lần). Timeout → FAULT, người vận hành kiểm tra và xác nhận.
- Mọi phản hồi có `seq` không khớp lệnh đang chờ (ví dụ `DONE` đến trễ sau khi đã timeout) bị
  **bỏ qua và ghi log**, không thể nhầm thành phản hồi của lệnh sau.
- Robot nên **tự bỏ qua** (ghi log) dòng không hiểu được, không được tự ngắt kết nối.

## 8. Giao thức Box (fixture) — không đổi

Box **tự đẩy** một dòng khi trạng thái đổi (và ngay khi vừa kết nối):

```
empty | ready_for_test | testing | pass | fail | error
```

PC gửi `LOAD\r\n` / `UNLOAD\r\n`, box trả `OK | BUSY | NOT_READY`.
`LOAD` chỉ hợp lệ khi `empty`; `UNLOAD` chỉ hợp lệ khi `pass | fail | error`.
RCS gửi `LOAD`/`UNLOAD` cho box **sau khi** robot báo `DONE` thao tác tương ứng.

## 9. Giao thức `legacy` (chương trình Fanuc hiện tại)

```
PC → Robot : PICK:1,5,2;        CHANGE;
Robot → PC : DONE:PICK          DONE:CHANGE
```

Không có seq, ACK, mã lỗi, batch, STATUS. RCS vẫn chạy được (`protocol = legacy`) nhưng:
lỗi robot chỉ lộ ra dưới dạng timeout, và `batch_enabled`/`heartbeat_interval` bị từ chối khi cấu hình.
Lệnh `legacy` cũng **không còn được gửi lại** khi timeout (khác phiên bản cũ).

## 10. Chuyển từ legacy sang v2

1. Cập nhật chương trình Fanuc theo `docs/FANUC_INTEGRATION.md`.
2. Kiểm thử với `sim/robot_simulator.py --protocol v2` làm mẫu hành vi chuẩn.
3. Đổi `protocol = v2` trong `station.ini`. Chạy thử ở chế độ `sim` rồi mới `real`.
4. Bật dần: `heartbeat_interval`, rồi `batch_enabled`.
