"""Sequence: một quy trình robot/ATS mô tả bằng dữ liệu (danh sách bước) thay vì bằng code.

Luồng tray dựng các stage của nó thành các danh sách bước như vậy (rcs2/core/tasks.py) và chạy chúng bằng SequenceRunner.
config/sequences.json chứa các điểm đã dạy:

    {"points": {"input_O": {"xyzwpr": [100, 200, 50, 180, 0, 0], "config": [...], "uf": 1, "ut": 1}, ...}}

Các loại bước
  {"robot": "move|rmove|gosafetarge", "pose": "<tên điểm>" | "target": [x,y,z,w,p,r], "override": 10}
  {"robot": "put|get|up|down", "station": 1}
  {"robot": "gosafehere"}
  {"ats": "place_dut_ok|fixture_open|fixture_close|dut_out|request_barcode"}   (ats: "barcode", "sn": "...")
                     bước ats tác động lên fixture của job ({fixture}); {"ats": ..., "fixture": 3} tự ghi rõ fixture
                     (luồng tray chạy các bước không gắn với một fixture)
  Robot có MỘT End Effector; một bước gọi một tool của nó bằng  {"ee": "<tool>", ...}  (các tool được khai báo trong
  settings.json -> "end_effector", xem rcs2/devices/end_effector.py):
  {"ee": "scanner"}   đọc mã vạch bằng đầu đọc của End Effector; tùy chọn
                     "length", "pattern" (regex), "retry", "timeout_s" đè giá trị mặc định của đầu đọc.
                     Mã đọc được thành biến {sn} cho các bước sau và hiện trên thẻ fixture.
                     Đặt bước này TRƯỚC khi robot hút DUT:  move tới ô, scanner, rồi hút, ...
                     Khi không đọc được mã sau mọi lần thử lại, job thất bại (alarm 9202, chưa hút gì).
                     Để gửi mã cho ATS:  {"ats": "barcode", "sn": "{sn}"}
                     "tag" (văn bản, tùy chọn) được trả lại cho bên gọi cùng với mã: on_scan(code, "scanner", tag).
  {"ee": "heads", "vacuum": "on|off", "heads": "all" | [1,2,3]}        van hút của các tay
  {"ee": "heads", "cylinder": "down|up", "heads": "all" | [1,2,3]}     xy lanh của các tay (chờ cảm biến / thời gian ổn định)
  {"ee": "heads", "check": "hold|release", "heads": ..., "timeout_s": 1.0}   cảm biến áp suất: tay nào đang giữ DUT
                     (một tay lỗi -> job thất bại, alarm 9203)
  {"ee": "laser", "check": "ok", "timeout_s": 1.0}   judgement của laser IL-1000 phải là GO (nếu không thì alarm 9204)
  {"wait": 0.5}                {"log": "message"}
Chuỗi có thể chứa {fixture}, {robot_station}, {station}, {result} (và {sn} sau một bước scanner); chúng
được thay giá trị khi bước chạy.
"""
import json
import os
import re
import threading
import time

from ..devices.scanner import ScanCancelled

POSE_OPS = ("move", "rmove", "gosafetarge")
STATION_OPS = ("put", "get", "up", "down")
NO_ARG_OPS = ("gosafehere",)
ATS_ACTIONS = ("place_dut_ok", "fixture_open", "fixture_close", "dut_out", "request_barcode", "barcode")
_VAR = re.compile(r"\{(\w+)\}")


class SequenceError(Exception):
    pass


class JobCancelled(Exception):
    pass


def expand(value, variables):
    """Thay {name} trong chuỗi (đệ quy vào list/dict). Tên không biết thì ném SequenceError."""
    if isinstance(value, str):
        def sub(m):
            if m.group(1) not in variables:
                raise SequenceError("unknown variable {%s} in %r" % (m.group(1), value))
            return str(variables[m.group(1)])
        return _VAR.sub(sub, value)
    if isinstance(value, list):
        return [expand(v, variables) for v in value]
    if isinstance(value, dict):
        return {k: expand(v, variables) for k, v in value.items()}
    return value


def load_sequences(path):
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    data.setdefault("points", {})
    return data


# ---- ghi file: bố cục dễ đọc (mỗi điểm / mỗi bước một dòng) -------------------------------------------- #
def dump_sequences(data, width=120):
    """Văn bản JSON của file sequences. Tọa độ nằm trên MỘT dòng:

        "points": {
          "above_input": [300, -200, 250, 180, 0, 0],
          "above_fixture_1": {"xyzwpr": [679.025, 25.199, 788.931, 88.284, -15.223, 140.437], "config": [...], "uf": 0, "ut": 1}
        }
    và mỗi bước của một sequence là một dòng. Cùng dữ liệu như json.dump, chỉ khác bố cục."""
    def fmt(value, depth, indent):
        compact = json.dumps(value, ensure_ascii=False)
        if not isinstance(value, (dict, list)) or not value:
            return compact
        steps_list = isinstance(value, list) and any(isinstance(v, dict) for v in value)
        expand = depth <= 1 or steps_list or len(compact) + indent > width
        if not expand:
            return compact
        pad, inner = " " * indent, " " * (indent + 2)
        if isinstance(value, dict):
            items = ["%s%s: %s" % (inner, json.dumps(k, ensure_ascii=False), fmt(v, depth + 1, indent + 2))
                     for k, v in value.items()]
            return "{\n" + ",\n".join(items) + "\n" + pad + "}"
        items = [inner + fmt(v, depth + 1, indent + 2) for v in value]
        return "[\n" + ",\n".join(items) + "\n" + pad + "]"
    return fmt(data, 0, 0) + "\n"


def save_sequences(path, data):
    """Ghi nguyên tử (file tạm + thay thế) theo bố cục dễ đọc của dump_sequences()."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(dump_sequences(data))
    os.replace(tmp, path)


_HEAD_ACTIONS = {"vacuum": ("on", "off"), "cylinder": ("down", "up"), "check": ("hold", "release")}
EE_TOOLS = ("heads", "scanner", "laser")
_LEGACY_KEYS = {"hand": '{"ee": "heads", ...}', "scan": '{"ee": "scanner", ...}'}      # các bước của NewRCS trước khi có End Effector


def _check_timeout(step, where, low, high):
    if step.get("timeout_s") is not None and not (
            isinstance(step["timeout_s"], (int, float)) and not isinstance(step["timeout_s"], bool)
            and low <= step["timeout_s"] <= high):
        raise SequenceError("%s: timeout_s must be %g..%g seconds" % (where, low, high))


def _check_ee_step(step, where, ee):
    """`ee` = khả năng của End Effector ({"heads": n, "scanner": bool, "laser": bool}) hoặc None (không kiểm tra)."""
    tool = step["ee"]
    if tool not in EE_TOOLS:
        raise SequenceError("%s: unknown End Effector tool %r (use %s)" % (where, tool, ", ".join(EE_TOOLS)))
    if ee is not None and not ee.get(tool):
        raise SequenceError("%s: the End Effector has no %s (settings.json -> end_effector -> %s)" % (where, tool, tool))
    if tool == "heads":
        actions = [a for a in _HEAD_ACTIONS if a in step]
        if len(actions) != 1:
            raise SequenceError("%s: a heads step needs exactly one of vacuum / cylinder / check" % where)
        action = actions[0]
        if step[action] not in _HEAD_ACTIONS[action]:
            raise SequenceError("%s: %s must be %s" % (where, action,
                                                       " or ".join(repr(v) for v in _HEAD_ACTIONS[action])))
        heads = step.get("heads", "all")
        count = ee.get("heads") if ee else None
        if heads != "all" and (not isinstance(heads, list) or not heads or any(
                isinstance(h, bool) or not isinstance(h, int) or h < 1 or (count and h > count) for h in heads)):
            raise SequenceError("%s: heads must be \"all\" or a list of head numbers%s"
                                % (where, " 1..%d" % count if count else ""))
        _check_timeout(step, where, 0.1, 30)
    elif tool == "scanner":
        if step.get("tag") is not None and not isinstance(step["tag"], str):
            raise SequenceError("%s: 'tag' must be text" % where)
        for key in ("length", "retry"):
            v = step.get(key)
            if v is not None and (isinstance(v, bool) or not isinstance(v, int) or v < 0):
                raise SequenceError("%s: %s must be an integer >= 0" % (where, key))
        _check_timeout(step, where, 0.2, 60)
        if step.get("pattern"):
            try:
                re.compile(step["pattern"])
            except re.error as ex:
                raise SequenceError("%s: invalid pattern: %s" % (where, ex))
    else:                                                                 # laser
        if step.get("check") != "ok":
            raise SequenceError("%s: a laser step needs  \"check\": \"ok\"" % where)
        _check_timeout(step, where, 0.1, 30)


def _check_pose_value(name, value):
    xyz = value.get("xyzwpr") if isinstance(value, dict) else value
    if not isinstance(xyz, list) or len(xyz) not in (6, 9) or any(
            isinstance(v, bool) or not isinstance(v, (int, float)) for v in xyz):
        raise SequenceError("point %r must be 6 numbers [x,y,z,w,p,r] (or {\"xyzwpr\": [...]})" % name)


def validate(sequences, points, ee=None):
    """Kiểm tra tĩnh (chạy lúc khởi động): báo lỗi sớm với thông báo rõ ràng.
    `ee`: End Effector mang những gì, {"heads": số tay hút, "scanner": bool, "laser": bool}
    (EndEffector.capabilities(); None = không kiểm tra tool nào có)."""
    for name, value in points.items():
        _check_pose_value(name, value)
    for sname, steps in sequences.items():
        if not isinstance(steps, list):
            raise SequenceError("sequence %r must be a list of steps" % sname)
        for i, step in enumerate(steps, 1):
            where = "sequence %r step %d" % (sname, i)
            if not isinstance(step, dict):
                raise SequenceError("%s: step must be an object" % where)
            for legacy, replacement in _LEGACY_KEYS.items():
                if legacy in step:
                    raise SequenceError("%s: step %r no longer exists, the robot has one End Effector: use %s"
                                        % (where, legacy, replacement))
            kinds = [k for k in ("robot", "ats", "wait", "log", "ee") if k in step]
            if len(kinds) != 1:
                raise SequenceError("%s: exactly one of robot/ats/wait/log/ee is required" % where)
            kind = kinds[0]
            if kind == "robot":
                op = step["robot"]
                if op in POSE_OPS:
                    if ("pose" in step) == ("target" in step):
                        raise SequenceError("%s: %s needs exactly one of 'pose' or 'target'" % (where, op))
                    if "pose" in step and "{" not in str(step["pose"]) and step["pose"] not in points:
                        raise SequenceError("%s: unknown point %r" % (where, step["pose"]))
                    if "target" in step and not (isinstance(step["target"], (list, dict))):
                        raise SequenceError("%s: 'target' must be a list or object" % where)
                elif op in STATION_OPS:
                    if "station" not in step:
                        raise SequenceError("%s: %s needs 'station'" % (where, op))
                elif op not in NO_ARG_OPS:
                    raise SequenceError("%s: unknown robot op %r" % (where, op))
                ov = step.get("override")
                if ov is not None and (isinstance(ov, bool) or not isinstance(ov, int) or ov < 1):
                    raise SequenceError("%s: override must be a positive integer" % where)
            elif kind == "ats":
                if step["ats"] not in ATS_ACTIONS:
                    raise SequenceError("%s: unknown ats action %r" % (where, step["ats"]))
                n = step.get("fixture")
                if n is not None and (isinstance(n, bool) or not isinstance(n, int) or n < 1):
                    raise SequenceError("%s: 'fixture' must be a fixture number (whole number >= 1)" % where)
            elif kind == "ee":
                _check_ee_step(step, where, ee)
            elif kind == "wait":
                if not isinstance(step["wait"], (int, float)) or not 0 <= step["wait"] <= 600:
                    raise SequenceError("%s: wait must be 0..600 seconds" % where)


class SequenceRunner:
    """Chạy một sequence với một robot client và các ATS client (blocking)."""

    def __init__(self, robot, ats, points, default_override=None, sleep=time.sleep, log=None, ee=None):
        self.robot = robot                  # giống BridgeClient
        self.ats = ats                      # {số fixture: đối tượng giống AtsClient}
        self.ee = ee                        # giống EndEffector (tay hút / đầu đọc mã / laser) hoặc None
        self.points = points
        self.default_override = default_override
        self.sleep = sleep
        self.log = log or (lambda msg: None)

    def run(self, name, steps, variables, cancel=None, on_scan=None):
        """`on_scan(code, tool_name)` được gọi sau mỗi bước scanner thành công."""
        for i, raw in enumerate(steps, 1):
            if cancel is not None and cancel.is_set():
                raise JobCancelled("%s cancelled before step %d" % (name, i))
            if raw.get("ee") == "scanner" and "pattern" in raw:     # một regex như [A-Z0-9]{14} không phải là {biến}
                step = expand({k: v for k, v in raw.items() if k != "pattern"}, variables)
                step["pattern"] = raw["pattern"]
            else:
                step = expand(raw, variables)
            self.log("%s step %d: %s" % (name, i, step))
            try:
                self._do(step, variables, cancel, on_scan)
            except SequenceError:
                raise
            except JobCancelled:
                raise

    # ---- một bước ------------------------------------------------------- #
    def _pose(self, step):
        if "pose" in step:
            if step["pose"] not in self.points:
                raise SequenceError("unknown point %r" % step["pose"])
            value = self.points[step["pose"]]
        else:
            value = step["target"]
        if isinstance(value, dict):
            return list(value["xyzwpr"]), value.get("config"), value.get("uf"), value.get("ut")
        return list(value), None, None, None

    def _override(self, step):
        return step.get("override", self.default_override)

    def _do_ee(self, step, variables, cancel, on_scan):
        """Một bước trên một tool của End Effector (tay hút / đầu đọc mã / laser)."""
        kind = step["ee"]
        tool = self.ee.tool(kind) if self.ee is not None and kind in EE_TOOLS else None
        if tool is None:
            raise SequenceError("the End Effector has no %s configured" % kind)
        if kind == "heads":
            heads = step.get("heads", "all")
            if "vacuum" in step:
                tool.vacuum_set(step["vacuum"] == "on", heads)
            elif "cylinder" in step:
                tool.cylinder_set(step["cylinder"] == "down", heads)
            else:
                tool.check(step["check"] == "hold", heads, step.get("timeout_s"))
        elif kind == "scanner":
            try:
                code = tool.scan(length=step.get("length"), pattern=step.get("pattern"), retry=step.get("retry"),
                                 timeout_s=step.get("timeout_s"),
                                 should_stop=cancel.is_set if cancel is not None else None)
            except ScanCancelled as ex:
                raise JobCancelled(str(ex))
            variables["sn"] = code
            self.log("scanner -> %s" % code)
            if on_scan is not None:
                if step.get("tag") is not None:
                    on_scan(code, "scanner", step["tag"])
                else:
                    on_scan(code, "scanner")
        else:
            tool.check(step.get("timeout_s"))

    def _do(self, step, variables, cancel=None, on_scan=None):
        if "robot" in step:
            op, ov = step["robot"], self._override(step)
            if op in POSE_OPS:
                xyz, config, uf, ut = self._pose(step)
                if op == "rmove":
                    self.robot.rmove(xyz, override=ov)
                else:
                    getattr(self.robot, op)(xyz, override=ov, config=config, uf=uf, ut=ut)
            elif op in STATION_OPS:
                getattr(self.robot, op)(int(step["station"]), override=ov)
            else:
                self.robot.gosafehere(override=ov)
        elif "ats" in step:
            number = step.get("fixture", variables.get("fixture"))
            ats = self.ats.get(int(number)) if number is not None else None
            if ats is None:
                raise SequenceError("no ATS for fixture %s" % number)
            action = step["ats"]
            ok = ats.send_barcode(step.get("sn", "")) if action == "barcode" else getattr(ats, action)()
            if not ok:
                raise SequenceError("ATS of fixture %s is not connected (%s)" % (number, action))
        elif "ee" in step:
            self._do_ee(step, variables, cancel, on_scan)
        elif "wait" in step:
            self.sleep(float(step["wait"]))
        elif "log" in step:
            self.log(str(step["log"]))
