# RCS — Robot Control System (PCB test station)

Phần mềm điều phối trạm test PCB: robot Fanuc gắp board từ khay đưa vào tối đa 30 fixture (box) để test,
lấy ra, rồi đặt board PASS/NG về khay. PC giao tiếp với robot và với từng box bằng **TCP/IP**.

```
        ┌──────────── RCS (PC) ────────────┐
        │  UI ─▶ Scheduler ─▶ clients       │
        └─────────────────────┬────────────┘
        TCP (lệnh PICK/LOAD…) │        │ TCP ×30 (box tự đẩy trạng thái)
                              ▼        ▼
                      Robot Fanuc     Fixtures
```

## Chạy nhanh

```powershell
cd D:\Travis\Test-Station\RCS\RCS
..\.venv\Scripts\python.exe sim\robot_simulator.py      # cửa sổ 1: robot giả
..\.venv\Scripts\python.exe sim\box_simulator.py        # cửa sổ 2: 30 box giả
..\.venv\Scripts\python.exe main.py                     # cửa sổ 3: ứng dụng (station.ini: mode = sim)
```

Yêu cầu: Python 3.9+ (đã kiểm thử trên 3.11) và `PySide6` (đã có trong `..\.venv`).

## Tài liệu

| File | Nội dung |
|---|---|
| `docs/ARCHITECTURE.md` | Kiến trúc, luồng cycle, máy trạng thái, luồng/khóa, điểm mở rộng |
| `docs/PROTOCOL_V2.md` | Giao thức robot v2 (seq/ACK/DONE/ERR/batch) + giao thức box |
| `docs/FANUC_INTEGRATION.md` | Việc cần làm phía chương trình Fanuc + checklist nghiệm thu |
| `docs/MAINTENANCE.md` | Cấu hình, test, triển khai trạm mới, cách thêm lệnh/policy, xử lý sự cố |

## Cấu trúc

```
main.py   station.ini   FixtureIP.ini
rcs/      config · models · protocol/ · clients/ · core/ · ui/ · persistence · traceability
sim/      box_simulator · robot_simulator
tests/    unittest      docs/   tài liệu      legacy/  phiên bản cũ (chỉ tham khảo)
```

## Kiểm thử

```powershell
..\.venv\Scripts\python.exe -m unittest discover -s tests -t .
```

