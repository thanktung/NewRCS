"""Hình học của luồng tray: pose đủ 6 giá trị (x, y, z, w, p, r), lưới tray và độ lệch giữa các tay hút.

Mọi thứ ở đây là toán thuần (không I/O, không numpy): nó biến một vài điểm ĐÃ DẠY thành pose robot phải tới cho
"tay k ở trên ô (r, c) của tray" hoặc "tay k ở trên fixture n".

Pose
  Một pose là `[x, y, z, w, p, r]` (mm, độ, quy ước FANUC: ma trận quay R = Rz(r) · Ry(p) · Rx(w)). Một điểm dạy
  là một pose hoặc một dict {"xyzwpr": [...], "config": [...], "uf": n, "ut": n} (những gì cửa sổ Thủ công lưu). Cả sáu giá trị đều
  được giữ và dùng; CONFIG / UF / UT của điểm dạy được mang sang kết quả.

Lưới tray (3 điểm)
  O = ô (hàng 0, cột 0), X = ô (hàng 0, cột cuối), Y = ô (hàng cuối, cột 0), đều dạy bằng tay 1.
  cell(r, c) = O + c * (X - O) / (cols - 1) + r * (Y - O) / (rows - 1), tính trên TỪNG giá trị trong sáu giá trị, nên tray bị
  nghiêng, xoắn hay dịch đều được bám theo (hiệu các góc được đưa về -180..180 trước).
  O, X và Y phải có cùng CONFIG / UF / UT, nếu không lưới bị từ chối.

Độ lệch giữa các tay (các tay gắn cố định trên tool, nên độ lệch giữa hai tay là một phép biến đổi cứng)
  Dạy tay 1 tại điểm O: pose robot là A = P1(O). Dạy tay k tại CÙNG điểm O: pose robot là Bk = Pk(O).
  Một điểm Q dạy bằng tay 1 (pose robot P1(Q)) được tay k tới bằng pose robot
        Pk(Q) = P1(Q) * inverse(A) * Bk          (ma trận 4x4)
  đúng với mọi hướng của Q (độ lệch xoay theo tool) - không chỉ là dịch x / y / z. Đầu đọc mã của
  End Effector (scanner) và cảm biến laser (IL-1000) được xử lý y như thêm một tay nữa.

Kiểm tra laser một sản phẩm đã đặt: đầu laser được đưa qua các điểm đo cho dưới dạng độ lệch (x, y, z mm) trong hệ tọa độ của
chỗ đặt sản phẩm (một ô của tray, một box): `Layout.laser_poses()`.
"""
import math

REFERENCE_HEAD = 1
SCANNER = "scanner"
LASER = "laser"
ANGLE_FIELDS = (3, 4, 5)


class GeometryError(ValueError):
    """Điểm dạy thiếu / không khớp nhau, hoặc lưới không thể có."""


# ---------------------------------------------------------------------------------------------------------------- #
# pose <-> ma trận 4x4
# ---------------------------------------------------------------------------------------------------------------- #
def wrap180(angle):
    """Góc (độ) -> góc tương đương trong [-180, 180)."""
    return (float(angle) + 180.0) % 360.0 - 180.0


def split_point(value):
    """Một điểm dạy -> (sáu số thực, phần thêm). `extras` = {"config", "uf", "ut"} và mọi giá trị thứ 7..9 (trục mở rộng)."""
    if isinstance(value, dict):
        xyz = value.get("xyzwpr")
        extras = {k: value[k] for k in ("config", "uf", "ut") if value.get(k) is not None}
    else:
        xyz, extras = value, {}
    if (not isinstance(xyz, (list, tuple)) or len(xyz) not in (6, 9)
            or any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in xyz)):
        raise GeometryError("a point needs 6 numbers [x, y, z, w, p, r] (or {\"xyzwpr\": [...]}), got %r" % (value,))
    return [float(v) for v in xyz[:6]], dict(extras, tail=[float(v) for v in xyz[6:]])


def make_point(xyz6, like=None):
    """Sáu số thực -> một dict điểm. CONFIG / UF / UT (và trục mở rộng) lấy từ `like` (một điểm dạy)."""
    _, extras = split_point(like) if like is not None else ([], {"tail": []})
    out = {"xyzwpr": [round(v, 6) for v in xyz6] + list(extras.get("tail", []))}
    for key in ("config", "uf", "ut"):
        if key in extras:
            out[key] = extras[key]
    return out


def to_matrix(xyzwpr):
    """[x, y, z, w, p, r] -> ma trận 4x4 (danh sách 4 hàng). R = Rz(r) * Ry(p) * Rx(w)."""
    x, y, z, w, p, r = (float(v) for v in xyzwpr[:6])
    sw, cw = math.sin(math.radians(w)), math.cos(math.radians(w))
    sp, cp = math.sin(math.radians(p)), math.cos(math.radians(p))
    sr, cr = math.sin(math.radians(r)), math.cos(math.radians(r))
    return [[cr * cp, cr * sp * sw - sr * cw, cr * sp * cw + sr * sw, x],
            [sr * cp, sr * sp * sw + cr * cw, sr * sp * cw - cr * sw, y],
            [-sp, cp * sw, cp * cw, z],
            [0.0, 0.0, 0.0, 1.0]]


def from_matrix(m):
    """Ma trận 4x4 -> [x, y, z, w, p, r] (độ, w và r trong [-180, 180], p trong [-90, 90])."""
    cp = math.hypot(m[0][0], m[1][0])
    if cp > 1e-9:
        p = math.degrees(math.atan2(-m[2][0], cp))
        w = math.degrees(math.atan2(m[2][1], m[2][2]))
        r = math.degrees(math.atan2(m[1][0], m[0][0]))
    else:                                           # gimbal lock (p = +-90): r đặt bằng 0, w nhận toàn bộ góc quay
        p = 90.0 if m[2][0] < 0 else -90.0
        r = 0.0
        w = math.degrees(math.atan2(-m[1][2], m[1][1]))
    return [m[0][3], m[1][3], m[2][3], w, p, r]


def mat_mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def mat_inv(m):
    """Nghịch đảo của một phép biến đổi cứng (quay + tịnh tiến)."""
    rt = [[m[j][i] for j in range(3)] for i in range(3)]
    t = [-sum(rt[i][k] * m[k][3] for k in range(3)) for i in range(3)]
    return [rt[0] + [t[0]], rt[1] + [t[1]], rt[2] + [t[2]], [0.0, 0.0, 0.0, 1.0]]


def pose_close(a, b, mm=1e-3, deg=1e-3):
    """Hai pose có giống nhau không? (góc so sánh theo modulo 360)"""
    return (all(abs(a[i] - b[i]) <= mm for i in range(3))
            and all(abs(wrap180(a[i] - b[i])) <= deg for i in ANGLE_FIELDS))


# ---------------------------------------------------------------------------------------------------------------- #
# lưới tray
# ---------------------------------------------------------------------------------------------------------------- #
class TrayGrid:
    """rows x cols ô tính từ ba điểm dạy O, X, Y (xem docstring của module)."""

    def __init__(self, o, x, y, rows, cols, name="tray"):
        for label, v in (("rows", rows), ("cols", cols)):
            if isinstance(v, bool) or not isinstance(v, int) or v < 1:
                raise GeometryError("%s: %s must be a whole number >= 1 (got %r)" % (name, label, v))
        self.name, self.rows, self.cols = name, rows, cols
        self._o, eo = split_point(o)
        self._x, ex = split_point(x)
        self._y, ey = split_point(y)
        for key in ("config", "uf", "ut"):
            if not (eo.get(key) == ex.get(key) == ey.get(key)):
                raise GeometryError("%s: the points O, X and Y must have the same %s (O=%r, X=%r, Y=%r): teach them again "
                                    "in the same configuration" % (name, key, eo.get(key), ex.get(key), ey.get(key)))
        self._like = o
        self._step_c = self._step(self._x, cols, "X")
        self._step_r = self._step(self._y, rows, "Y")

    def _step(self, end, count, label):
        """Mức thay đổi của sáu giá trị từ ô này sang ô kế tiếp dọc một cạnh (bằng 0 khi cạnh chỉ có một ô)."""
        if count == 1:
            return [0.0] * 6
        step = []
        for i in range(6):
            d = end[i] - self._o[i]
            if i in ANGLE_FIELDS:
                d = wrap180(d)
            step.append(d / (count - 1))
        if all(abs(v) < 1e-9 for v in step):
            raise GeometryError("%s: point %s is the same as point O but the tray has %d cells on that side"
                                % (self.name, label, count))
        return step

    @property
    def capacity(self):
        return self.rows * self.cols

    def index(self, row, col):
        """Vị trí theo thứ tự đọc (từng hàng, trái sang phải) của ô (row, col)."""
        self._check(row, col)
        return row * self.cols + col

    def rc(self, index):
        """(row, col) của ô ở vị trí này theo thứ tự đọc."""
        if not 0 <= index < self.capacity:
            raise GeometryError("%s: cell index %r is outside 0..%d" % (self.name, index, self.capacity - 1))
        return divmod(index, self.cols)

    def _check(self, row, col):
        if not (0 <= row < self.rows and 0 <= col < self.cols):
            raise GeometryError("%s: cell (%r, %r) is outside the tray (%d rows x %d cols)" % (self.name, row, col, self.rows, self.cols))

    def cell(self, row, col):
        """Pose (dict điểm đủ 6 giá trị + CONFIG / UF / UT của O) của ô, theo cách tay 1 phải tới."""
        self._check(row, col)
        v = [self._o[i] + col * self._step_c[i] + row * self._step_r[i] for i in range(6)]
        for i in ANGLE_FIELDS:
            v[i] = wrap180(v[i])
        return make_point(v, like=self._like)

    def cell_by_index(self, index):
        return self.cell(*self.rc(index))


# ---------------------------------------------------------------------------------------------------------------- #
# các tay
# ---------------------------------------------------------------------------------------------------------------- #
class HeadTransforms:
    """Độ lệch giữa các tay (và scanner) tính từ các pose dạy tại cùng điểm O: `at_o` = {1: pose, 2: pose, ...,
    "scanner": pose}; tay 1 là chuẩn. `pose_for(k, q)` cho pose robot đưa tay k tới chỗ tay 1 ở tại `q`."""

    def __init__(self, at_o, count=None):
        if REFERENCE_HEAD not in at_o:
            raise GeometryError("head %d (the reference) was not taught at O" % REFERENCE_HEAD)
        self._a, self._a_extras = split_point(at_o[REFERENCE_HEAD])
        self._inv_a = mat_inv(to_matrix(self._a))
        self._t = {}
        for key, value in at_o.items():
            b, _ = split_point(value)
            self._t[key] = mat_mul(self._inv_a, to_matrix(b))          # T = inverse(A) * B
        self.count = count if count is not None else max((k for k in self._t if isinstance(k, int)), default=0)
        for k in range(1, self.count + 1):
            if k not in self._t:
                raise GeometryError("head %d was not taught at O" % k)

    def has(self, key):
        return key in self._t

    def pose_for(self, key, q):
        """Pose robot cho tay `key` (số, hoặc "scanner") tại điểm dạy `q` (pose hoặc dict điểm)."""
        if key not in self._t:
            raise GeometryError("no offset for %r (head / scanner not taught at O)" % (key,))
        xyz, _ = split_point(q)
        out = from_matrix(mat_mul(to_matrix(xyz), self._t[key]))
        return make_point(out, like=q)

    def offset(self, key):
        """Sáu giá trị của phép biến đổi tay 1 -> `key` (một tay, "scanner" hoặc "laser") trong hệ tọa độ tool (để hiển thị / kiểm tra)."""
        return from_matrix(self._t[key])


# ---------------------------------------------------------------------------------------------------------------- #
# toàn bộ layout (điểm dạy của sequences.json -> pose)
# ---------------------------------------------------------------------------------------------------------------- #
def head_point_name(key):
    return {SCANNER: "scanner_at_O", LASER: "laser_at_O"}.get(key) or "head_%d_at_O" % key


def shift_pose(q, offset):
    """Điểm `q` dịch đi `offset` = (dx, dy, dz) mm đo trong hệ tọa độ của `q` (giữ nguyên hướng của nó)."""
    xyz, _ = split_point(q)
    t = [[1.0, 0.0, 0.0, float(offset[0])], [0.0, 1.0, 0.0, float(offset[1])], [0.0, 0.0, 1.0, float(offset[2])], [0.0, 0.0, 0.0, 1.0]]
    return make_point(from_matrix(mat_mul(to_matrix(xyz), t)), like=q)


class Layout:
    """Mọi thứ planner cần biết về VỊ TRÍ của mọi thứ, dựng từ các điểm dạy theo tên:

        head_<k>_at_O  (k = 1..heads)   scanner_at_O (tùy chọn)     cùng một điểm O dạy bằng từng tay / bằng đầu đọc
        input_O  input_X  input_Y        tray Input (tay 1)
        ng_O  ng_X  ng_Y                 tray NG (tay 1)
        output1_O/X/Y  output2_O/X/Y     các tray output cho hàng đạt (tay 1), chỉ những tray có trong settings.json -> trays
        fixture_<n>                      vị trí của fixture n (tay 1)
        laser_at_O (tùy chọn)            cảm biến laser ở trên cùng điểm O (chỉ khi sản phẩm đã đặt được kiểm tra bằng nó)
    `trays` = {"input": {"rows", "cols"}, "ng": {...}}; `fixtures` = số các fixture; `heads` = số tay hút.
    """

    def __init__(self, points, trays, fixtures, heads, scanner=False, laser=False):
        self.heads, self.fixtures, self.scanner, self.laser = heads, list(fixtures), scanner, laser
        missing = self.missing(points, trays, fixtures, heads, scanner, laser)
        if missing:
            raise GeometryError("taught points missing: %s" % ", ".join(missing))
        at_o = {k: points[head_point_name(k)] for k in range(1, heads + 1)}
        if scanner:
            at_o[SCANNER] = points[head_point_name(SCANNER)]
        if laser:
            at_o[LASER] = points[head_point_name(LASER)]
        self.transforms = HeadTransforms(at_o, count=heads)
        self.input = TrayGrid(points["input_O"], points["input_X"], points["input_Y"], trays["input"]["rows"],
                              trays["input"]["cols"], "input tray")
        self.ng = TrayGrid(points["ng_O"], points["ng_X"], points["ng_Y"], trays["ng"]["rows"], trays["ng"]["cols"], "NG tray")
        self.outputs = [TrayGrid(points["%s_O" % n], points["%s_X" % n], points["%s_Y" % n], trays[n]["rows"], trays[n]["cols"], n)
                        for n in self.output_names(trays)]                     # tray output k (bắt đầu từ 0) = "output<k+1>"
        self._fixture_points = {n: points["fixture_%d" % n] for n in self.fixtures}

    @staticmethod
    def output_names(trays):
        """Các tray output được cấu hình, theo thứ tự sử dụng: ["output1", "output2"] / ["output1"] / []."""
        return [n for n in ("output1", "output2") if n in (trays or {})]

    @staticmethod
    def required_names(trays, fixtures, heads, scanner=False, laser=False):
        names = [head_point_name(k) for k in range(1, heads + 1)]
        if scanner:
            names.append(head_point_name(SCANNER))
        if laser:
            names.append(head_point_name(LASER))
        names += ["input_O", "input_X", "input_Y", "ng_O", "ng_X", "ng_Y"]
        for n in Layout.output_names(trays):
            names += ["%s_O" % n, "%s_X" % n, "%s_Y" % n]
        names += ["fixture_%d" % n for n in fixtures]
        return names

    @classmethod
    def missing(cls, points, trays, fixtures, heads, scanner=False, laser=False):
        """Tên các điểm dạy còn thiếu (danh sách rỗng = đủ)."""
        absent = [n for n in cls.required_names(trays, fixtures, heads, scanner, laser) if n not in points]
        for kind in ("input", "ng"):
            if kind not in (trays or {}):
                absent.append("settings.json -> trays -> %s" % kind)
        return absent

    # ---- các pose robot phải tới ----------------------------------------------------------------- #
    def pick_pose(self, head, index):
        """Tay `head` ở trên ô `index` (thứ tự đọc) của tray INPUT."""
        return self.transforms.pose_for(head, self.input.cell_by_index(index))

    def input_pose(self, head, index):
        return self.pick_pose(head, index)

    def ng_pose(self, head, index):
        return self.transforms.pose_for(head, self.ng.cell_by_index(index))

    def output_pose(self, head, tray, index):
        """Tay `head` ở trên ô `index` của tray output `tray` (bắt đầu từ 0: 0 = output1, 1 = output2)."""
        return self.transforms.pose_for(head, self.outputs[tray].cell_by_index(index))

    def fixture_pose(self, head, number):
        return self.transforms.pose_for(head, self._fixture_points[number])

    def scan_pose(self, index):
        """Đầu đọc mã ở trên ô `index` của tray Input."""
        return self.transforms.pose_for(SCANNER, self.input.cell_by_index(index))

    def laser_poses(self, kind, ref, offsets):
        """Các pose robot đưa cảm biến laser tới trên các điểm đo của sản phẩm vừa đặt tại `ref`:
        kind "input" / "ng" = chỉ số ô của tray đó, "output" = (chỉ số tray output, ô), "box" = số fixture. `offsets` = [(dx, dy, dz) mm, ...] trong hệ tọa độ của chỗ đặt."""
        if kind == "input":
            place = self.input.cell_by_index(ref)
        elif kind == "ng":
            place = self.ng.cell_by_index(ref)
        elif kind == "output":
            place = self.outputs[ref[0]].cell_by_index(ref[1])
        elif kind == "box":
            place = self._fixture_points[ref]
        else:
            raise GeometryError("unknown place %r for a laser check (input | output | ng | box)" % (kind,))
        return [self.transforms.pose_for(LASER, shift_pose(place, off)) for off in offsets]
