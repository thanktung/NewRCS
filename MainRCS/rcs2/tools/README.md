# Module `rcs2/tools` — công cụ phụ trợ chạy bằng tay / chế độ demo

Không dùng trong vận hành bình thường. Được phép import `ats` và `robot`; không ai trong `core`, `robot`, `ats`... được import ngược lại.

| File | Dùng để |
|---|---|
| `bridge_cli.py` | Thử bridge bằng dòng lệnh |
| `flow_sim.py` | **mô phỏng what-if luồng tray** (planner + sổ sách, không robot): đo box rảnh bao lâu, số sản phẩm/giờ |
| `demo.py` | `start_demo(settings, fixtures, speed, test_time)`: chạy **simulator + ATS giả trong cùng tiến trình** cho `python -m rcs2 --demo`; `DEMO_POINTS`, `DEMO_SEQUENCES` |

## bridge_cli
```powershell
python -m rcs2.tools.bridge_cli --host 127.0.0.1 status
python -m rcs2.tools.bridge_cli --host 127.0.0.1 r-read 1
python -m rcs2.tools.bridge_cli --host 127.0.0.1 move 300 0 200 180 0 0 --override 5
python -m rcs2.tools.bridge_cli --host 127.0.0.1 put 1 --override 5
```
Lệnh chuyển động tự arm trong lúc chạy rồi disarm. **Luôn dùng override thấp và để tay gần nút E-stop khi thử trên robot thật.**
Lệnh: `hello status connect-robot fault-clear alarm-clear r-read r-write pr-read io-read move rmove gosafetarge put get down up gosafehere`.

## flow_sim (thử luật ưu tiên của luồng tray)
```powershell
python -m rcs2.tools.flow_sim                                   # 10 box, 8 tay, 80 sản phẩm, test 120 s
python -m rcs2.tools.flow_sim --boxes 6 --test-time 60 --pass-rate 0.8 --cells 48 --seed 3
python -m rcs2.tools.flow_sim --keep-free 0 --max-pick 4 --no-top-up      # thử cài đặt planner khác
```
In ra: số đạt / NG, số lần test, sản phẩm/giờ, độ dùng của box, robot bận bao nhiêu %, và **thời gian rảnh của box** (trung bình / lớn nhất) — chính là mục tiêu của planner. Thời gian robot (`travel`, `move`, `pick`, `place`, `scan`) là giả định trong `SimConfig`: đo thật rồi chỉnh để kết quả sát thực tế. `FlowSim.check()` kiểm tra các bất biến sau mỗi task (dùng trong `tests/core/test_planner.py`).

## demo
`demo.py` nạp `bridge32/bridge_simple.py` (qua `sys.path`) và chạy `Bridge(sim=True)` + `Server` + một `MockAts` cho mỗi fixture ngay trong ứng dụng.
Đây là chỗ **duy nhất** mã ứng dụng được phép import simulator (test kiến trúc cho phép đúng ngoại lệ này).
Muốn cả cell mô phỏng chạy ở tiến trình riêng, dùng `python bridge32\bridge_simple.py` (xem `bridge32/README.md`).

## Hướng dẫn sửa
- **Thêm lệnh vào bridge_cli:** thêm sub-parser trong `build_parser()` và nhánh xử lý trong `main()`.
- **Đổi điểm / sequence của demo:** `DEMO_POINTS`, `DEMO_SEQUENCES` trong `demo.py` (chỉ là giá trị giữ chỗ).
- **Đổi tốc độ mô phỏng của demo:** tham số `speed` (nhân thời gian chuyển động) và `test_time` của `start_demo`.
