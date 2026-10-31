# `tests/` — kiểm thử theo module

Mỗi module của `rcs2/` có một thư mục test cùng tên; thêm `simulator/` (file `bridge32/bridge_simple.py`), `support/` (fixture dùng chung) và `test_architecture.py`.

```
tests/
├─ __init__.py              đưa MainRCS/ và MainRCS/bridge32/ vào sys.path (để `import rcs2`, `import bridge_simple`)
├─ test_architecture.py     quy tắc import giữa các module, Qt chỉ ở ui, simulator chỉ dùng thư viện chuẩn
├─ support/
│   ├─ bridge.py            BridgeFixture: chạy simulator trên cổng trống cho một test (`.sim` = robot giả, `.client()`)
│   └─ engine.py            EngineCase (Engine luồng tray nối với đồ giả), FlowRobot, FakeAts, taught_points, tray_settings, wait_until
├─ config/    reporting/   employee/   ats/   devices/   core/   robot/   runtime/   ui/   simulator/
```

| Thư mục | Kiểm tra | Khi nào chạy |
|---|---|---|
| `config` | file mẫu nạp được và hợp lệ | sửa `defaults.py`, `*.example.json` |
| `core` | engine (bắt đầu / dừng, alarm, lỗi + xác nhận, timeout, UO[3]), sequence, tray; **luồng tray:** `test_geometry` (6 bậc tự do), `test_dut`, `test_planner` (quyết định + chạy cả lượt trên mô phỏng), `test_flow_engine` (engine + đồ giả), `test_flow_settings` | sửa `rcs2/core/` |
| `robot` | chạy/dừng UOP, cấu hình `robot_start`, đồng bộ hằng số giao thức | sửa `rcs2/robot/` |
| `ats` | khung tin, ghép luồng, kết nối lại, nhịp tim | sửa `rcs2/ats/` |
| `devices` | đầu hút, laser, scanner, bước `ee` | sửa `rcs2/devices/` |
| `reporting` | tên bảng cũ, outbox, upload, ErrorTracker | sửa `rcs2/reporting/` |
| `employee` | đăng nhập, bộ phận, quyền, file `departments*.json` | sửa `rcs2/employee/` |
| `runtime` | tự đăng xuất, thao tác thủ công, chặn khi UO[3] = 0, chạy cả chu kỳ với demo; `test_flow_ops` (hiệu chuẩn luồng tray) | sửa `rcs2/runtime/` |
| `ui` | dựng cửa sổ chính (offscreen); `test_flow_ui` (màu tray, thanh tay, hộp thoại hiệu chuẩn) | sửa `rcs2/ui/` |
| `simulator` | giao thức bridge, simulator, NewRCS chạy trên simulator; `test_sim_flow` (luồng tray cả chu kỳ trên simulator, lớp nền `SimFlowCase` dùng lại ở test runtime / ui) | sửa `bridge32/` hoặc giao thức |

## Chạy
```powershell
cd MainRCS
python run_tests.py                       # tất cả (≈ 2 phút)
python run_tests.py robot ats             # một vài module
python run_tests.py core -k tray -v       # lọc theo tên test, hiện từng test
python run_tests.py architecture
python -m unittest tests.core.test_engine # một file bằng unittest thuần
```
`run_tests.py` tự đặt `QT_QPA_PLATFORM=offscreen` (không mở cửa sổ) và `PYTHONUTF8=1`.

## Viết test mới
- Đặt vào thư mục của module đang sửa, tên `test_*.py`. Import đồ dùng chung: `from tests.support.engine import EngineCase, FakeRobot, wait_until` hoặc
  `from tests.support import bridge as helpers` (`helpers.BridgeFixture`, `helpers.ROOT`).
- Test engine: kế thừa `EngineCase` (đã có `self.eng` ở luồng tray, `self.robot` giả, `self.ats`, `self.fx(n)`, `self.start()`, `self.answer_tests(...)`). Test dựng `Runtime`: dùng `tray_settings()`.
- Test cần bridge: `helpers.BridgeFixture()` rồi `fx.client()`; nhớ `fx.close()` trong `tearDown`.
- Test cần cả Runtime: xem `tests/runtime/test_program_state.py` (`RuntimeSimTests`) — Runtime trỏ vào `BridgeFixture`.
- Chờ điều kiện bất đồng bộ bằng `wait_until(cond, timeout, what)`, **không** `time.sleep` cố định dài.
- Không để test chạm mạng thật hay file cấu hình thật (dùng thư mục tạm, `Outbox(":memory:")`, `employee.offline_demo`).

## Lưu ý
- `ResourceWarning` về socket chưa đóng và dòng `upload failed ... MySQL down` trong output là bình thường (test cố ý làm DB lỗi).
- `tests/simulator/test_bridge_gui.py` bị bỏ qua vì `bridge_gui.py` (Tk của bridge thật) không có trong repo.
