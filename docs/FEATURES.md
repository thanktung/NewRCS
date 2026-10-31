# NewRCS — tính năng và hành vi (tài liệu tham chiếu)

Mô tả **hệ thống làm gì** (chu kỳ fixture, sequence, đăng nhập, alarm, End Effector, tray, chạy/dừng chương trình robot, UO[3], điều khiển thủ công,
khác biệt so với RCS cũ, an toàn). Muốn biết **sửa ở đâu**: xem `MainRCS/README.md` và README của từng module. Kiến trúc: `ARCHITECTURE.md`.
(Phần này trước đây nằm trong README gốc; nội dung bằng tiếng Anh.)

## How it works
* **Fixture cycle:** ATS says *WaitDUT* -> robot *load* sequence -> `CtoT_placeDUTOK` -> ATS result ->
  robot *unload_pass / unload_ng / unload_retest / unload_fqc* sequence -> next DUT. Tested DUTs are unloaded
  before new ones are loaded. One robot job at a time.
* **Sequences are data** (`config/sequences.json`): robot steps (`move`, `get`, `put`, `up`, `down`, `rmove`,
  `gosafehere`, `gosafetarge`), ATS steps, waits. Variables `{fixture}`, `{robot_station}`, `{station}`, `{result}`.
  They are validated at start-up.
* **Robot protocol** (robot program `RSR0001`, see `Robot Base Program/ROBOT_PROGRAM_GUIDE.md`): bridge writes
  `PR[1]`, `R[2]`, `R[5]`, then `R[1]`=command and waits for `R[1]` = 0 (done) / -1 (error); every parameter is read
  back first. Details and safety model: `bridge32/README.md`.
* **Data:** results, logins and error intervals go to a local SQLite outbox first and are uploaded to the **legacy
  MySQL tables** (same names/columns as the old RCS, so the dashboard is unchanged). Nothing is lost while MySQL is
  down; errors still open after a crash are closed on the next start. `mysql.enabled` replaces the old `Updata` flag.
* **Login:** user name = the 8-character **card number**, password = the shared default password. The card is looked up
  in the ESD web service, which returns its **department** (e.g. `MNM561`, `MNM571`); `config/departments.json` maps the
  department to an access **level 1-5** (5 = highest). Unlisted departments are refused (`default_level` 0). The file is
  read at every login, so edits apply without a restart. `min_level` in the same file sets the lowest level for
  `operate` (Start/Stop, fixture switches), `manual` (Manual window) and `teach` (save points); all 1 by default.
  The password is the same for everybody, so it is not a secret: the real gate is the card + department.
  **Automatic logout:** the operator is logged out **3 minutes after logging in** (`settings.json` -> `employee.auto_logout_s`,
  180 by default, `0` = never). With `"auto_logout_idle": true` the 3 minutes count from the last mouse / key use instead of
  from the login. The time left is in the tooltip of the user button (and on the button itself during the last minute).
  When the time is up the open Manual window and any pending confirmation are closed; a robot motion already started is not
  interrupted. Not applied in `--demo` / `--no-login`.
* **Alarms** keep the old codes: 9026 stop, 9011 consecutive NG, 9012 ATS offline, 9013 fixture error,
  9201 robot error, plus 9010 test timeout, 9100 robot link/disarmed and the End Effector alarms 9202 (scanner),
  9203 (heads), 9204 (laser; new).

## End Effector (the tool on the robot flange)
A robot has exactly **ONE End Effector**. It carries three small tools, all optional, declared together in
`settings.json` -> `"end_effector"` (see `config/settings.example.json`); code in `MainRCS/rcs2/devices/` (see its README):

| Tool | What it is | Config key | Code |
|---|---|---|---|
| `heads` | **8** units, each = up/down **cylinder** + **vacuum** valve + pressure sensor, on the FANUC controller I/O | `end_effector.heads` | `heads.py` |
| `scanner` | Keyence SR-710 / SR-X100 barcode reader (reads the DUT code before it is picked) | `end_effector.scanner` | `scanner.py` |
| `laser` | IL-1000 laser sensor that checks the picked DUT | `end_effector.laser` | `laser.py` |

A sequence addresses a tool with one step kind, `{"ee": "<tool>", ...}` (validated at start-up; a sequence that uses a tool the
End Effector does not carry is refused):
```json
{"ee": "scanner", "length": 14},                              read the code -> {sn}; alarm 9202 if it cannot be read
{"ee": "heads", "cylinder": "down", "heads": "all"},          cylinders of all / some heads ([1,2,3]) down or up
{"ee": "heads", "vacuum": "on",     "heads": "all"},          vacuum valves on / off
{"ee": "heads", "check": "hold",    "heads": "all", "timeout_s": 1.0},   pressure sensors: do the heads hold the DUT? (alarm 9203)
{"ee": "laser", "check": "ok",      "timeout_s": 1.0}         IL-1000 judgement must be GO (alarm 9204)
```
* **heads:** per unit one `vacuum` and `pressure` address (e.g. `RDO[1]`, `RDI[3]`) and the cylinder: a **double coil (bistable 5/2) valve** with `coil_down` /
  `coil_up` outputs and the two end-of-stroke sensors `cyl_down` / `cyl_up` (the other coil is switched off first, both are never on together; the run waits for the
  sensor, alarm 9203 when the cylinder does not arrive), or a single output `cylinder` (one coil + spring return). Outputs are read back after every write. `"enabled": false` refuses every action (the addresses in the
  example are placeholders: fix the wiring, then enable).
* **scanner:** TCP/IP (host + port 9004) or COM port (`pyserial`). `LON` starts a reading, `LOFF` stops it; the code is checked
  (`length`, regex `pattern`) and retried (`retry`).
* **laser:** the IL-1000 **judgement** is read from robot inputs (`ok` = GO, optional `high` / `low`). *Not done yet:* reading
  the measured value itself, and per-head tracking of 8 DUTs. Confirm the real interface (I/O judgement or communication unit).
* The Manual window has one **End Effector** panel with a section per tool (select heads, vacuum / cylinders, pressure of every
  head, LON / LOFF test, read the laser judgement).
* `settings.json` of older versions with top-level `"hands"` / `"scanners"`, and sequence steps `{"hand": ...}` / `{"scan": ...}`,
  are refused with a message that says what to change.

## Trays (main window, first tab "Tray hàng")
Up to four trays are shown in one block, side by side in ONE row: the **input tray** (DUTs waiting to be picked), the **NG tray** (failed DUTs) and, if they are
configured, the **output trays 1 and 2** (passed DUTs only: output 1 is filled first, then output 2). No size is displayed. Their size
(**rows x columns**) is set **only in `config/settings.json`** (restart to apply); there is no size editor in the UI:
```json
"trays": {"input": {"rows": 5, "cols": 8}, "ng": {"rows": 4, "cols": 6}}
```
Rows / columns are whole numbers 1..50. A tray that is not declared is not shown and not counted; an invalid size stops the
start-up with a message. The shipped files contain 5 x 8 and 4 x 6 as a starting point: set the real tray sizes.
* Cells are used in reading order (row by row, from the top left); the yellow outline is the cell used next.
* **Input** starts full: every load takes one cell (blue = still holds a DUT). When it is empty **no new load starts** (fixtures
  wait in "Chờ nạp") until the operator refills it and presses **Nạp lại** (the buttons of the NG and output trays say **Đã dọn**).
* **NG** starts empty: every NG unload (`unload_ng`) fills one cell (red). When it is full the pill turns red and a warning is
  logged; press **Đã dọn** after emptying it. Unloading is never blocked.
* The tab is flagged "Tray hàng ●" when the input tray is empty or the NG tray is full.
* The fill state is kept in memory only: after a restart the input tray counts as full and the NG tray as empty.
* The position inside the tray is **counted only**: the robot positions in `sequences.json` are not changed by it yet.

## Tray flow (`flow.mode: "tray"`): 8 heads, many boxes, product positions from a 3-point tray
The default `classic` flow loads / unloads one fixture per robot sequence. With `"flow": {"mode": "tray"}` (settings.json) the robot serves
**all boxes with all heads** and the positions come from taught points, not from fixed sequences (code: `MainRCS/rcs2/core/`, see its README):
* **Product path:** pick untested products from the input tray into the heads (one product per head, each barcode scanned first) -> put them in
  the boxes that are empty or finished (a finished box is **swapped**: the tested product is taken out by a free head, a new one goes in at
  once) -> send `B1=<SN>` + `CtoT_placeDUTOK` -> when the result arrives a **pass is put into the next cell of output tray 1** (then output 2; without output trays: into the first empty cell of the input tray); a **failure is
  tested again in another box** (never the same one), **3 tests in total**, then it goes to the next cell of the NG tray.
* **Priority:** the box that has waited longest is served first, so no box stays idle long. One head is always kept free to take a tested
  product out. While every box is busy the robot puts tested products away and tops the heads up with fresh products.
* **Positions with all six values:** the cell (r, c) of a tray = O + c * (X-O)/(cols-1) + r * (Y-O)/(rows-1) computed on x y z w p r (a tilted or
  twisted tray is followed). O, X, Y are the first cell, the last cell of the first row and the first cell of the last row, taught with head 1.
  Head k reaches a point Q taught with head 1 with the robot pose `P1(Q) * inverse(A) * Bk` (A / Bk = robot poses with head 1 / head k at the same
  point O): the heads are taught once at O, every other point is taught with head 1 only.
* **Calibration:** Manual window -> *Hiệu chuẩn luồng tray*: save head k at O, the three points of each tray and every box (all six values + CONFIG /
  UF / UT), then compute / move each head to any cell or box to check the poses before running. Start is refused (alarm 9205) while a point is
  missing or inconsistent.
* **Main window:** only a few states are shown. **Input tray cell:** untested (blue) / empty (grey) (/ pass (green) when there are no output trays). **NG tray cell:** empty / NG (red). **Output tray cell:** empty / pass (green). **Head:** empty /
  untested / pass / ng / retest (grey, blue, green, red, orange; one `retest` state, the number of tests allowed is `flow.max_attempts`). The fixture cards show
  `SN · cell it was picked from · test number`.
* **Cycles:** pick = go to the barcode reader, **scan**, pick. Put down (box, output tray / input tray, optional NG tray) = put, then the **IL-1000 laser checks 2 points**
  of the product (a tilted one stops the run, alarm 9204; a box test starts only after the laser says GO). Settings: `flow.laser_check`.
* **Fill the heads at the tray:** a visit to the input tray fills every free head (except the reserved one) with fresh products, so the robot does not
  leave for a box with half-loaded heads and come back to the tray again (`flow.fill_heads`; 10 boxes: 31 -> 21 trips to the tray in the simulation).
* **When tested products are put away:** only when every product on the heads is tested (pass / ng) or every box is busy testing (and when there is no
  room at all, or nothing fresh is left). Retest products go into boxes before fresh ones.
* **Dropped product:** before every head movement the pressure sensors of all carrying heads are checked; a head that lost its product raises alarm
  9208, stops the run and **stops the robot program** (`flow.stop_robot_on_drop`).
* **Tray notices:** alarm 9206 when everything is done and the input tray must be changed (press *Nạp lại*, the run continues by itself), alarm 9207
  when the NG tray is full and alarm 9209 when both output trays are full (press *Đã dọn* of that tray).
* **Stop** takes effect between two stages (a stage = one head picking or placing one product): the books always say where every product is. After a
  failure (drop, laser, a head that does not pick up) clear the heads and boxes by hand and use *Xóa trạng thái luồng*.
* **Try rules without a robot:** `python -m rcs2.tools.flow_sim` (idle time of the boxes, products per hour).
* Not done yet: the simulator does not follow the real position of the products (it checks the command flow, not the coordinates); automatic recovery
  after a drop / laser failure; looking ahead to a box that is about to finish.

## Main window layout
Command bar, KPI strip, fixture cards (the card area is only as tall as its rows need, so there is no empty band
below the last row), then a tab area that takes the remaining height: **Tray hàng** (first, default) and **Nhật ký hoạt động**; on the right the robot and alarm panels.

## Start / stop the robot program (buttons "Chạy chương trình" and "Dừng robot", Robot panel)
Starts `RSR0001` through the UOP signals (code: `rcs2/robot/uop.py`, `Runtime.robot_start_program()`). UI[n] is mapped to the
standard input of the same index, so the UI signals are driven as **SDI[n]** through the bridge (the bridge must list `SDI` in
`io_write_kinds`, it is the default); the UO signals are only read.

| Step | Signal | Check |
|---|---|---|
| 0 | UO[3] PROGRUN already 1 | nothing to do, nothing is written |
| 1 | SDI[1], SDI[2], SDI[3] = 1 (IMSTP, HOLD, SFSPD) and SDI[8] = 1 (ENBL) | outputs read back |
| 2 | pulse SDI[9] (RSR1 -> select RSR0001) | |
| 3 | pulse SDI[5] (RESET) | UO[6] FAULT must go to 0 within `reset_wait_s`, else "robot còn lỗi" |
| 4 | pulse SDI[6] (START) | UO[3] PROGRUN must go to 1 within `run_wait_s`, else "RSR0001 chưa chạy" |

A pulse is 1 -> `pulse_s` -> 0 (the 0 is written even on a failure). On a failure the message lists UO[1] CMDENBL, UO[2] SYSRDY,
UO[3] PROGRUN, UO[6] FAULT, UO[8] TPENBL. The bridge is armed only for the sequence (a latched `R[1] < 0` fault is cleared first),
and the button is refused while a run / robot job is active and needs the `operate` level; it acts at once (no confirmation pop-up).
`settings.json` -> `"robot_start"`: `{"rsr": 1, "pulse_s": 0.3, "reset_wait_s": 3.0, "run_wait_s": 5.0}` (`rsr` 1..8 = UI[9..16]).
Not connected to *Start* of a run yet: the operator starts the robot program first, then presses *Bắt đầu*.

**Is the robot program running? (UO[3] PROGRUN)** NewRCS reads UO[3] every `robot_start.monitor_s` (0.5 s) and when it opens
(first read after the link is up, written in the log), and shows it in the Robot panel (*Chương trình*: ĐANG CHẠY / DỪNG / ?).
**While it is off no robot operation is possible**: a command written then would stay unanswered in R[1] and be executed later,
when the program is started again. With UO[3] = 0 the *safe position* button and, in the Manual window, jog, go to point, teach
point, clear fault, the heads (vacuum / cylinders) and the laser reading are disabled, and the runtime refuses them too
(error `PROGRAM_STOPPED`; nothing is armed or written). *Bắt đầu* is refused (alarm 9100 "robot_program"), no job is
dispatched, and a run in progress is paused with the same alarm after 1 s. Only the barcode scanner (its own TCP device),
*Kết nối robot*, *Chạy chương trình* (offered only while the program is off) and *Dừng robot* remain available. An unreadable
UO[3] also refuses an operation. *Chạy chương trình* and *Dừng robot* act at once, without a confirmation pop-up.

**Stop (`Runtime.robot_stop_program()`, button "Dừng robot"):** pulse **SDI[4]** (CSTOPI), then **SDI[1], SDI[2], SDI[3] = 0**, then
UO[3] PROGRUN must be 0 within `stop_wait_s` (else "robot chưa dừng, hãy dùng E-stop"). The SDI[1..3] are switched off even if the
pulse failed; any failure says to use the E-stop. Unlike *Start* it is **always allowed** (also while a run, a job or a manual
motion is active): it only arms the bridge if nobody holds the arm, and never takes away an arm held by a running cell. It aborts a
start in progress and then stops the run too (no new job is sent to a stopped robot); a robot job in progress ends with an error.
Starting again switches SDI[1..3] on again. It is not a replacement for the E-stop. UI[4] CSTOPI (cycle stop) and UI[5] RESET
(reset fault) are separate signals: the stop uses only SDI[4], the start uses SDI[5] to reset the fault.

## Manual control (header button **Manual**)
Step jog X/Y/Z/W/P/R ± (linear 0.1-50 mm, angular 0.1-10 deg, speed 1-max_override %), *Move to point* (safe `move` to
a taught point), *Save current position* (teach: position + CONFIG/UF/UT written into `config/sequences.json`, a `.bak`
copy is kept, the engine sees the new point immediately), *Go safe here*, *Clear robot fault*.
* The base program has no continuous jog: **each press is one `rmove`** (joint-interpolated, no path check in the robot).
  Limits are enforced in the bridge (`max_rmove_mm` 100, `max_rmove_deg` 30, `max_override`).
* Each press arms the bridge for that single command and disarms afterwards. Refused while a run is active or a robot
  job is running, and the Start button is disabled while a manual move is in progress.
* Positions are read in the robot's **current user frame** (the one `RSR0001` selects with `UFRAME_NUM`), the same frame
  used by `move`. Verify on the robot that a taught point sent back with *Move to point* lands on the same spot.
* Not available in `--demo` (teaching needs a sequences file).

## What is different from the old RCS (deliberate)
| Old | NewRCS |
|---|---|
| 3rd consecutive NG left the DUT inside the fixture (queue skipped) | the DUT is unloaded, then the fixture is stopped |
| `StopUse` in the INI was overwritten by code | `consecutive_ng.stop_fixture` is honoured |
| DB password hard-coded, SQL injection in login/user forms | password from environment, parameterised SQL |
| DB write failure silently dropped the record | local outbox + retry |
| `TtoC_BarcodePass` matched as plain `barcode` | distinguished |
| `f_open_CEND` sent as `f_open_CEND_CEND` | single terminator |
| Stop/disarm could interrupt a sequence | Stop waits for the running sequence, then disarms |
| Month of a row = time of the upload | month of the event |

Kept on purpose: alarm codes, ATS protocol, legacy table layout. Changed on purpose: the old `op`/`pe` users, the
day-of-month password and the "department contains `M5` -> FE" rule are replaced by card + department level.

## Safety
Motion needs an explicit *arm* from NewRCS; the bridge drops the arm on disconnect/silence/error, caps override
(default 30 %), checks workspace and offsets, and never lets `R[1]` be written raw. **It cannot stop a motion already
running in the robot** - keep the E-stop in reach and commission with a low override.
In `ROBOT_PROGRAM_GUIDE.md` the `PUT/GET/UP/DOWN/SAFEV` programs are commented out in the robot, so `R[1]` returns to 0
without doing anything: a successful `put` from NewRCS does not prove the I/O sequence ran until you enable them.
`config/sequences.example.json` coordinates are placeholders; Start is refused on a real robot while `"example": true`.

## Not ported yet (next phases)
Tray positions for the robot in the `classic` flow (the tray flow computes them), golden sample, retest buffer logic, FQC sampling rules, SFCS stage check,
screw/glue/machine-tool modes, `Data.zip` FTP sync, user management screen, settings editor in the UI.
