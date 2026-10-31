# Hướng dẫn điều khiển robot FANUC qua Robot Bridge (TCP/JSON → FRRJIf)

*Dựa trên `bridge_simple.py`, `bridge_gui.py`, `FRRJIf_gen.py` (bản đã bỏ chế độ sim). Giao thức đã được thử với code thật bằng robot giả; chưa thử trên robot thật.*

## 1. Tổng quan

```
Chương trình điều khiển ──TCP 5600, JSON lines──► Bridge (Python 32-bit) ──COM FRRJIf──► Robot FANUC (RSR0001)
(RCS2, script, tool...)                            bridge_simple.py / bridge_gui.py
```

Bridge **không tự điều khiển quỹ đạo**. Nó chỉ làm 3 việc: nhận lệnh JSON, kiểm tra an toàn, rồi ghi các thanh ghi của robot qua FRRJIf. Chương trình TP trên robot (RSR0001) mới là nơi thực hiện chuyển động:

1. Bridge ghi tham số: `PR[1]` (đích hoặc offset), `R[2]` (số trạm), `R[5]` (override %).
2. Bridge ghi mã lệnh vào `R[1]` (1 rmove, 2 move, 3 put, 4 get, 5 down, 6 up, 7 gosafehere, 8 gosafetarge).
3. Robot thực hiện xong thì đặt `R[1] = 0`; nếu lỗi thì đặt `R[1] = -1`. Bridge chờ và trả kết quả cho client.

## 2. Kết nối

- **Địa chỉ:** TCP, mặc định `<IP máy bridge>:5600` (`listen_host`, `listen_port`).
- **Danh sách IP cho phép (`allow`):** IP không có trong danh sách bị đóng kết nối ngay, **không có thông báo lỗi**. Mở cổng 5600 trong firewall chỉ cho máy điều khiển.
- **Khuôn dạng:** mỗi dòng là một đối tượng JSON, UTF-8, kết thúc bằng `\n`, tối đa 1 MiB.

Yêu cầu từ client:
```json
{"id":7,"cmd":"motion.rmove","args":{"target":{"xyzwpr":[10,0,0,0,0,0]},"override":5}}
```
Thành công / thất bại:
```json
{"id":7,"ok":true,"data":{"op":"rmove","code":1,"elapsed_s":1.2,"r1":0,"override":5}}
{"id":7,"ok":false,"error":{"code":"NOT_ARMED","message":"send 'arm' before motion commands"}}
```
Bridge còn tự đẩy sự kiện trạng thái khoảng 0,5 s một lần tới mọi client:
```json
{"event":"status","data":{"connected":true,"armed":false,"r1":0,"curpos":[...]}}
```

**Hai điều client bắt buộc phải xử lý:**
- Dòng có khóa `event` là sự kiện đẩy, không phải phản hồi: phải bỏ qua khi chờ phản hồi.
- Phản hồi của `motion.*` chỉ về khi robot chạy xong (có thể vài giây tới `timeout_s`), nên **có thể đến sau** phản hồi của lệnh gửi muộn hơn. Phải ghép bằng `id`, không ghép theo thứ tự.

## 3. Vòng đời một phiên điều khiển

1. Kết nối TCP, gửi `hello` (xem giới hạn, `state`).
2. Nếu `state.connected` là `false` và `auto_connect` tắt, gửi `robot.connect`.
3. Bắt đầu **ping mỗi 1 giây** (giữ arm sống, mục 4).
4. Gửi `arm`.
5. Gửi các lệnh `motion.*` (mỗi lúc một lệnh), chờ phản hồi.
6. Xong việc gửi `disarm`, rồi đóng kết nối.

## 4. Quy tắc arm (bắt buộc cho chuyển động)

Lệnh `motion.*` và `io.write` bị từ chối (`NOT_ARMED`) nếu client chưa `arm`. Chỉ **một** client được arm cùng lúc. `arm` bị từ chối khi robot chưa kết nối, đang có fault (`R[1] < 0`) hoặc client khác đang arm.

Arm tự bị hủy khi:
- client ngắt kết nối;
- bridge không nhận được dòng nào từ client trong `watchdog_s` (5 s). Mọi dòng, kể cả `ping`, đều làm mới đồng hồ này;
- lệnh motion kết thúc bằng `ROBOT_ERROR`, `TIMEOUT`, `VERIFY_FAILED`, `NOT_CONNECTED` hoặc `INTERNAL`;
- mất kết nối tới robot hoặc gọi `robot.disconnect`.

> Hủy arm chỉ chặn **lệnh mới**. Không thể dừng một chuyển động robot đang chạy. Luôn để E-stop trong tầm tay.

## 5. Danh sách lệnh

### 5.1 Lệnh chung

| Lệnh | `args` | `data` trả về | Cần arm |
|---|---|---|---|
| `hello` | – | `name, version, protocol, mode` (`"real"`), `robot_host, limits, state` | không |
| `ping` | – | `{t}` | không |
| `status` | – | trạng thái (5.2) | không |
| `robot.connect` | `host?` | `{connected, host, r1}` | không |
| `robot.disconnect` | – | `{connected:false}` (hủy arm) | không |
| `arm` / `disarm` | – | `{armed:true/false}` | – |
| `r.read` | `index` | `{index, value}` | không |
| `r.write` | `index, value` | `{index, value}` (giá trị đọc lại) | không |
| `pos.read` | – | `{xyzwpr[6], config[7], uf, ut}` | không |
| `io.read` | `kind, index, count (1..100)` | `{kind, index, values}` | không |
| `io.write` | `kind, index, values` (danh sách 0/1) | `{kind, index, values}` (đọc lại) | **có** |
| `alarm.clear` | – | `{cleared}` | không |
| `fault.clear` | `force?` | `{r1}` | không |

- `kind` hợp lệ: `SDO SDI RDO RDI SO SI UO UI GO GI`. Chỉ ghi được các loại trong `io_write_kinds` (mặc định `SDO, RDO, SDI`).
- `r.write` không ghi được thanh ghi trong `protected_r` (mặc định `R[1]`). Chỉ đọc/ghi được các `R[]` đã đăng ký (`register_int`, `register_real`).
- `fault.clear` ghi `R[1] = 0` khi `R[1] < 0`. Nếu `R[1] > 0` (robot đang chạy) thì trả `BUSY`.

### 5.2 Trường của `status`

`connected`, `armed`, `busy` (bridge đang chạy một lệnh), `fault` (`R[1] < 0`, đang khóa), `pending` (`R[1] > 0` mà không phải lệnh đang theo dõi, ví dụ sau `TIMEOUT`), `r1`, `r2`, `r5`, `op` (lệnh đang chạy), `last_result`, `curpos` (`[X,Y,Z,W,P,R]` hoặc `null`), `message`, `t`.

### 5.3 Lệnh chuyển động `motion.<tên>`

| Lệnh | Mã `R[1]` | Tham số bắt buộc | Ý nghĩa tham số |
|---|---|---|---|
| `motion.rmove` | 1 | `target` | `PR[1]` = offset tương đối |
| `motion.move` | 2 | `target` | `PR[1]` = vị trí tuyệt đối |
| `motion.put` | 3 | `station` | `R[2]` = số trạm |
| `motion.get` | 4 | `station` | `R[2]` = số trạm |
| `motion.down` | 5 | `station` | `R[2]` = số trạm |
| `motion.up` | 6 | `station` | `R[2]` = số trạm |
| `motion.gosafehere` | 7 | không | – |
| `motion.gosafetarge` | 8 | `target` | `PR[1]` = điểm an toàn |

Các `args` chung:
- `override`: số nguyên 1..`max_override` (mặc định 30), nếu thiếu dùng `default_override` (10). Được ghi vào `R[5]`.
- `target`: `{"xyzwpr":[x,y,z,w,p,r], "config":[7 số]?, "uf":?, "ut":?}`. `xyzwpr` có 6 hoặc 9 số hữu hạn. Thiếu `config/uf/ut` thì dùng `pose_config` (`[0,0,1,1,0,0,0]`), `pose_uf` và `pose_ut` (-1).
- `station`: số nguyên 0..`max_station`.
- `timeout_s`: 1..600 (mặc định `op_timeout_s` = 60). Client nên đặt thời gian chờ phía mình lớn hơn giá trị này.

Giới hạn bridge kiểm tra: `rmove` không quá `max_rmove_mm` (khoảng cách XYZ) và `max_rmove_deg` (|W|, |P|, |R|); các lệnh có đích tuyệt đối phải nằm trong `workspace` nếu bạn đã cấu hình (hiện đang `null`, tức không giới hạn).

Kết quả thành công: `{op, code, elapsed_s, r1:0, override}`.

## 6. Mã lỗi

| Mã | Nghĩa và cách xử lý |
|---|---|
| `BAD_REQUEST` | Sai JSON/tham số, hoặc thanh ghi chưa đăng ký |
| `UNKNOWN_CMD` | Tên lệnh không tồn tại |
| `NOT_CONNECTED` | Chưa nối robot hoặc mất link: gọi `robot.connect` |
| `NOT_ARMED` | Chưa `arm`, hoặc arm đã bị hủy (mục 4) |
| `FORBIDDEN` | Thanh ghi bị bảo vệ, loại I/O không được ghi, hoặc client khác đang arm |
| `LIMIT` | Vượt override, rmove, workspace hoặc số trạm |
| `BUSY` | Đang có lệnh khác (bridge hoặc `R[1] > 0`) |
| `FAULT_LATCHED` | `R[1] < 0`: kiểm tra robot rồi gọi `fault.clear` |
| `VERIFY_FAILED` | Ghi rồi đọc lại không khớp: arm bị hủy |
| `ROBOT_ERROR` | Robot đặt `R[1] = -1`: arm bị hủy, fault bị khóa |
| `TIMEOUT` | Hết `timeout_s`; robot có thể vẫn đang chạy. Kiểm tra RSR0001 có đang chạy không |
| `INTERNAL` | Lỗi COM hoặc lỗi nội bộ |

Sau `ROBOT_ERROR` quy trình phục hồi là: xử lý nguyên nhân trên robot, `fault.clear`, `arm`, rồi gửi lại lệnh.

## 7. Client mẫu bằng Python

Chỉ dùng thư viện chuẩn. Đoạn mã này đã được thử với code bridge thật (robot giả): arm, ping giữ arm sống, các lệnh motion, lỗi `ROBOT_ERROR` và `fault.clear` đều chạy đúng.

```python
import itertools, json, socket, threading, time


class BridgeError(Exception):
    def __init__(self, code, message):
        Exception.__init__(self, "%s: %s" % (code, message))
        self.code, self.message = code, message


class BridgeClient:
    def __init__(self, host, port=5600, ping_s=1.0):
        self.sock = socket.create_connection((host, port), timeout=5)
        self.sock.settimeout(None)
        self.rfile = self.sock.makefile("rb")
        self.wlock = threading.Lock()
        self.ids = itertools.count(1)
        self.pending = {}                    # id -> [Event, response]
        self.status = {}                     # status event mới nhất
        self.closed = False
        threading.Thread(target=self._reader, daemon=True).start()
        threading.Thread(target=self._keepalive, args=(ping_s,), daemon=True).start()

    def _reader(self):
        try:
            for line in self.rfile:
                msg = json.loads(line.decode("utf-8"))
                if "event" in msg:           # sự kiện đẩy, không phải phản hồi
                    if msg["event"] == "status":
                        self.status = msg["data"]
                    continue
                slot = self.pending.get(msg.get("id"))
                if slot:
                    slot[1] = msg
                    slot[0].set()
        except (OSError, ValueError):
            pass
        self.closed = True
        for slot in list(self.pending.values()):
            slot[0].set()

    def _keepalive(self, period):            # im lặng quá watchdog_s (5 s) thì arm bị hủy
        while not self.closed:
            time.sleep(period)
            try:
                self.call("ping", timeout=3)
            except Exception:
                pass

    def call(self, cmd, args=None, timeout=10.0):
        rid = next(self.ids)
        slot = self.pending[rid] = [threading.Event(), None]
        data = (json.dumps({"id": rid, "cmd": cmd, "args": args or {}}, separators=(",", ":")) + "\n").encode("utf-8")
        try:
            with self.wlock:
                self.sock.sendall(data)
            if not slot[0].wait(timeout):
                raise BridgeError("CLIENT_TIMEOUT", "no answer to %s within %.0f s" % (cmd, timeout))
        finally:
            self.pending.pop(rid, None)
        resp = slot[1]
        if resp is None:
            raise BridgeError("CLOSED", "connection closed")
        if not resp.get("ok"):
            err = resp.get("error") or {}
            raise BridgeError(err.get("code", "?"), err.get("message", ""))
        return resp.get("data")

    def close(self):
        self.closed = True
        try:
            self.sock.close()
        except OSError:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
```

Cách dùng (override 5%, E-stop trong tầm tay):
```python
with BridgeClient("192.168.1.50") as b:
    print(b.call("hello")["limits"])
    b.call("arm")
    b.call("motion.gosafehere", {"override": 5}, timeout=80)
    b.call("motion.rmove", {"target": {"xyzwpr": [10, 0, 0, 0, 0, 0]}, "override": 5}, timeout=80)
    b.call("motion.put", {"station": 2, "override": 5}, timeout=80)
    print(b.call("pos.read")["xyzwpr"])
    b.call("disarm")
```

## 8. Từ lệnh JSON đến hành động của robot

Lệnh `motion.<tên>` đi qua các bước sau (`Bridge.motion` rồi `Bridge.motion_job`):

1. **Kiểm tra** (thread của client): robot đã nối, client đang giữ arm, override, `target`/`station` hợp lệ và trong giới hạn, chỉ một motion tại một thời điểm.
2. **Chuyển cho COM thread** (`robot_call`): mọi lệnh FRRJIf chạy trên **một** thread có `CoInitialize()`, vì đối tượng COM gắn với thread tạo ra nó.
3. **Đọc `R[1]`**: `> 0` trả `BUSY`; `< 0` trả `FAULT_LATCHED`.
4. **Ghi tham số rồi đọc lại để xác nhận**: `PR[1]` (sai lệch tối đa 0,01), sau đó `R[2]` và `R[5]`.
5. **Ghi `R[1] = mã lệnh`** (kích hoạt). Từ lúc này robot sở hữu lệnh.
6. **Chờ**: đọc `R[1]` mỗi `poll_s` (50 ms). `0` là xong, `< 0` là `ROBOT_ERROR`, quá hạn là `TIMEOUT`.

Bảng ánh xạ sang FRRJIf (`ComRobot` trong `bridge_simple.py`):

| Việc | Hàm | Lời gọi FRRJIf |
|---|---|---|
| Kết nối | `open` | `Core = FRRJIf.Core()`; `DataTable = Core.DataTable`; đăng ký `AddCurPosUF(CURPOS,1,15)`, `AddNumReg(NUMREG_INT, lo, hi)`, `AddPosReg(POSREG, nhóm, lo, hi)`; `Core.TimeOutValue`; `Core.Connect(host)` |
| Đọc `R[i]` | `r_get` | `DataTable.Refresh()` rồi `DataNumReg.GetValue(i, 0)` → `(ok, giá trị)` |
| Ghi `R[i]` | `r_set` | `DataNumReg.SetValues(i, VARIANT(VT_ARRAY\|VT_I4,[v]), 1)`, dự phòng `SetValue` |
| Ghi `PR` | `pr_set` | `DataPosReg.SetValueXyzwpr(i, xyzwpr9, config7, uf, ut)` |
| Đọc `PR` | `pr_get` | `Refresh()` + `DataPosReg.GetValue(i, ...)` |
| Vị trí | `curpos` | `Refresh()` + `DataCurPos.GetValue(...)` |
| I/O | `io_get`, `io_set` | `Core.Read<kind>(idx, buf, n)` / `Core.Write<kind>(idx, vals, n)` |
| Xóa alarm | `clear_alarm` | `Core.ClearAlarm(0)` |
| Ngắt | `close` | `Core.Disconnect()` |

**Quy tắc quan trọng của FRRJIf:** biến phải được đăng ký vào `DataTable` **trước** `Core.Connect()`. Muốn đọc/ghi thêm loại dữ liệu nào thì phải đăng ký ở `open()`, không thể thêm sau khi đã nối.

## 9. Hợp đồng với chương trình robot (RSR0001)

Bridge chỉ đúng khi chương trình TP tuân theo các quy tắc sau:

- Chờ `R[1] > 0`, đọc `R[1]` để biết hành động, đọc `PR[1]`, `R[2]`, `R[5]` khi cần.
- Áp dụng override từ `R[5]` trước khi chạy.
- **Chỉ đặt `R[1] = 0` ở bước cuối**, sau khi chuyển động thực sự xong. Nếu xóa sớm, bridge báo "xong" khi robot còn đang chạy.
- Khi lỗi hoặc mã lệnh lạ: đặt `R[1] = -1`, rồi **chờ `R[1] = 0`** (do `fault.clear` ghi) trước khi quay lại vòng chờ.
- `PR[1]` **không bị xóa** giữa các lệnh: với `put/get/up/down/gosafehere` nó vẫn giữ giá trị cũ, nên chỉ đọc nó ở các mã lệnh thực sự dùng.

Bộ khung TP **minh họa** (chương trình thật của bạn phải theo `ROBOT_PROGRAM_GUIDE.md`; cú pháp cần đối chiếu với controller):
```
LBL[1] ;
  WAIT R[1]>0 ;
  OVERRIDE=R[5]% ;
  SELECT R[1]=1,JMP LBL[10] ;
         =2,JMP LBL[20] ;
         =7,JMP LBL[70] ;
         =9,JMP LBL[90] ;      ! hành động mới
         ELSE,JMP LBL[900] ;
LBL[10] ;                       ! rmove: dịch theo PR[1]
  ...
  JMP LBL[800] ;
LBL[90] ;                       ! hành động mới: viết ở đây
  ...
  JMP LBL[800] ;
LBL[800] ;
  R[1]=0 ;                      ! báo xong: bước CUỐI
  JMP LBL[1] ;
LBL[900] ;
  R[1]=-1 ;                     ! lỗi
  WAIT R[1]=0 ;                 ! chờ fault.clear
  JMP LBL[1] ;
```

## 10. Thêm một hành động mới

### A. Hành động chạy trong chương trình robot (qua `R[1]`)

Ví dụ thêm `motion.home` với mã 9:

1. **Robot:** thêm nhánh mã 9 trong `SELECT` và viết routine; nhớ `R[1]=0` ở cuối, `R[1]=-1` khi lỗi.
2. **Bridge** (`bridge_simple.py`): thêm vào từ điển mã lệnh:
   ```python
   MOTION = {..., "gosafetarge": 8, "home": 9}
   ```
   Nếu hành động cần đích `PR[1]` thì thêm vào `NEEDS_TARGET`; cần số trạm thì thêm vào `NEEDS_STATION`. Không cần viết thêm handler: `motion.home` được nhận tự động.
3. **Cần tham số khác** (ví dụ `R[3]`)? `motion_job` hiện chỉ ghi `PR[1]`, `R[2]`, `R[5]`, nên phải thêm bước ghi và đọc lại tương ứng, và `R[3]` phải nằm trong `register_int`.
4. **Phía điều khiển:** thêm mã mới vào `rcs2/robot/protocol.py` (README nói test sẽ báo nếu lệch), và thêm preset trong tab Console nếu muốn.
5. **Thử:** override 5%, E-stop trong tay, chạy từ tab Console của `bridge_gui.py` trước khi dùng từ chương trình thật.

### B. Lệnh bridge làm trực tiếp với FRRJIf (không qua chương trình robot)

Mẫu một lệnh mới, đặt trong `class Bridge`. Tên `c_<lệnh>` tự thành lệnh `<lệnh>` (dấu `.` thành `_`):
```python
def c_r_readmany(self, c, args):             # lệnh "r.readmany"
    self.need_robot()
    first, n = self.int_arg(args, "index"), self.int_arg(args, "count")
    if not 1 <= n <= 20:
        raise Err("BAD_REQUEST", "count 1..20")
    # lệnh ghi hoặc điều khiển: thêm
    #   if self.armed_by is not c: raise Err("NOT_ARMED", "requires 'arm'")
    def job():                               # chạy trên COM thread
        r = self.com.robot
        return [r.r_get(first + k) for k in range(n)]
    return {"index": first, "values": self.robot_call(job)}
```
Quy tắc: chỉ động vào FRRJIf trong `job()` (qua `robot_call`), kiểm tra tham số **trước** khi tạo job, và dùng `Err(mã, thông báo)` để trả lỗi.

### C. Dùng thêm loại dữ liệu FRRJIf mới

Thêm phương thức vào `ComRobot` theo mẫu `r_get`: `Refresh()` rồi `GetValue`. Đối tượng phải được đăng ký trong `open()` **trước** `Connect()`, ví dụ `AddSysVar` (có trong `FRRJIf_gen.py`):
```python
self.DataSysVar = DataTable.AddSysVar(C.SYSVAR_INT, "$MCR.$GENOVERRIDE")   # ví dụ
```
Cách đọc/ghi xem các phương thức của lớp `_DataSysVar` trong `FRRJIf_gen.py`. Sau đó viết lệnh theo mẫu B.

## 11. Lưu ý và hạn chế của code hiện tại

- **`r.write` và `alarm.clear` không cần arm.** `r.write` chỉ bị chặn với thanh ghi trong `protected_r`, mà mặc định chỉ có `R[1]`.
- **Nút DISARM của GUI** chỉ hủy được arm do chính cửa sổ này giữ, không hủy arm của RCS2.
- **Chỉ xác thực bằng IP** (`allow`); không có mật khẩu.
- **Một lệnh motion tại một thời điểm.** Trong lúc robot chạy, các lệnh COM khác (`r.read`, `pos.read`...) xếp hàng chờ, và `curpos` trong `status` không cập nhật cho tới khi chạy xong.
- Bridge **không còn chế độ giả lập**. Muốn test không cần robot, dùng bản có sim hoặc robot giả như trong phần thử ở mục 7.
