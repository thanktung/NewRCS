# NewRCS

Chương trình giám sát cell robot (trước đây "RCS 2", viết lại từ RCS cũ bằng C#). Gói Python vẫn tên **`rcs2`** (`python -m rcs2`, `import rcs2`).
**Python 64-bit + PySide6** cho ứng dụng; **bridge 32-bit** (FRRJIf, thư viện COM 32-bit nên phải là chương trình riêng) nói chuyện với robot FANUC.
Cả hai chạy trên cùng một PC, nối với nhau bằng TCP.

```
 PC vận hành (Windows)
 ┌───────────────────────────────┐   TCP 5600, JSON   ┌───────────────────────────┐   COM FRRJIf   ┌─────────────┐
 │ NewRCS (Python 64-bit)        │ ◄────────────────► │ bridge (Python 32-bit)    │ ◄─────────────►│ robot FANUC │
 │ UI · engine · MySQL · login   │                    │  hoặc simulator một file  │   (IP robot)   └─────────────┘
 └───────┬───────────────┬───────┘                    └───────────────────────────┘
         │ TCP "_CEND"   │ TCP / COM  LON, LOFF
   ATS của các fixture   máy quét Keyence
```

## Bản đồ thư mục
```
RCS2/
├─ README.md   requirements.txt
├─ MainRCS/                      ứng dụng — vào đây: MainRCS/README.md (bản đồ module + "muốn sửa X thì vào đâu")
│   ├─ rcs2/                     gói Python, chia module (mỗi module có README riêng)
│   │   ├─ config/   core/   robot/   ats/   devices/   reporting/   employee/   runtime/   ui/   tools/
│   ├─ config/                   settings.json · sequences.json · departments.json  (+ README giải thích từng khóa)
│   ├─ bridge32/                 bridge_simple.py — SIMULATOR MỘT FILE (bridge + fixture + scanner giả)
│   ├─ tests/                    test chia theo module + test kiến trúc;  run_tests.py
│   └─ run_rcs2.py
├─ docs/                         ARCHITECTURE.md · FEATURES.md · robot_bridge_guide.md
└─ devtools/                     ui_preview (chụp ảnh + kiểm tra giao diện) · sfcs_probe
```

| Module (`MainRCS/rcs2/`) | Làm gì |
|---|---|
| [`core`](MainRCS/rcs2/core/README.md) | engine lịch chạy, sequence, tray, **luồng tray** (8 tay hút, nhiều box, tray 3 điểm, planner) — **bộ não** |
| [`robot`](MainRCS/rcs2/robot/README.md) | client bridge, giao thức, chạy/dừng chương trình robot (UOP) |
| [`ats`](MainRCS/rcs2/ats/README.md) | giao thức + client ATS của fixture |
| [`devices`](MainRCS/rcs2/devices/README.md) | End Effector: đầu hút, máy quét, laser |
| [`reporting`](MainRCS/rcs2/reporting/README.md) | outbox SQLite → MySQL dashboard |
| [`employee`](MainRCS/rcs2/employee/README.md) | đăng nhập thẻ, phân quyền theo bộ phận |
| [`runtime`](MainRCS/rcs2/runtime/README.md) | lắp ráp + thao tác của người vận hành (không Qt) |
| [`ui`](MainRCS/rcs2/ui/README.md) | giao diện PySide6 |
| [`config`](MainRCS/rcs2/config/README.md) | mặc định + nạp cấu hình |
| [`tools`](MainRCS/rcs2/tools/README.md) | bridge_cli, chế độ demo |

## Chạy thử ngay (không cần phần cứng)
```powershell
cd MainRCS
pip install -r ..\requirements.txt                 # PySide6, pymysql, requests (pyserial nếu máy quét cổng COM)
python run_rcs2.py --demo --autorun                # bridge + ATS giả chạy ngay trong ứng dụng
```
Hoặc chạy **cả cell mô phỏng ở tiến trình riêng** rồi mở NewRCS bình thường (cổng lấy từ `config/settings.json`; xem `MainRCS/bridge32/README.md`):
```powershell
python bridge32\bridge_simple.py        # terminal 1: bridge + 13 fixture + scanner giả
python run_rcs2.py                      # terminal 2 (cần employee.offline_demo hoặc mạng tới ESD để đăng nhập)
```

## Cài đặt thật (một PC, hai Python)
Cần **Python 3.11 64-bit** cho NewRCS (`venv` của dự án) và **Python 3.8+ 32-bit + pywin32** cho bridge thật (FRRJIf đã đăng ký trên PC). Bridge thật **không nằm trong repo này**
(thư mục `bridge32/` hiện chỉ có simulator); giao thức: `docs/robot_bridge_guide.md`.
1. `MainRCS\config\settings.json`: trỏ `bridge`, `ats.fixtures`, `end_effector`... về thiết bị thật (bản gốc trước khi trỏ sang simulator ở `config\archive\settings.json.pre_sim.bak`).
2. `config\sequences.json`: **dạy điểm thật** (cửa sổ Thủ công) rồi xóa dòng `"example": true`.
3. Bí mật bằng biến môi trường: `RCS_DB_PASSWORD`, tùy chọn `RCS_BRIDGE_TOKEN`.
4. `python run_rcs2.py`. Thử bridge: `python -m rcs2.tools.bridge_cli --host 127.0.0.1 status`.

## Phát triển
```powershell
cd MainRCS
python run_tests.py                       # toàn bộ test (~2 phút);  python run_tests.py robot ats  = chỉ module vừa sửa
python ..\devtools\ui_preview\contract_test.py   # sau khi sửa giao diện (và xem ảnh devtools\ui_preview\shots)
```
Mỗi module có README gồm: làm gì / không làm gì, file, quy tắc bất biến, **hướng dẫn sửa từng bước** và test liên quan.
Quy tắc phụ thuộc giữa các module được test canh (`python run_tests.py architecture`).

## Tài liệu
- `MainRCS/README.md` — bản đồ module, quy tắc phụ thuộc, bảng "muốn sửa X thì vào đâu", quy ước, bất biến an toàn
- `docs/ARCHITECTURE.md` — kiến trúc, thread, vòng đời, một chu kỳ fixture, bất biến an toàn
- `docs/FEATURES.md` — tính năng chi tiết (End Effector, tray, chạy/dừng robot, UO[3], thủ công, so với RCS cũ, an toàn)
- `MainRCS/config/README.md` — từng khóa cấu hình · `MainRCS/tests/README.md` — kiểm thử · `devtools/README.md`
