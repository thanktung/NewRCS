"""Geometry of the tray flow: poses with all 6 values (x, y, z, w, p, r), tray grids and the offsets between the suction heads.

Everything here is pure maths (no I/O, no numpy): it turns a handful of TAUGHT points into the pose the robot must go to for
"head k over cell (r, c) of the tray" or "head k over fixture n".

Poses
  A pose is `[x, y, z, w, p, r]` (mm, degrees, FANUC convention: rotation matrix R = Rz(r) · Ry(p) · Rx(w)). A taught point
  is a pose or a dict {"xyzwpr": [...], "config": [...], "uf": n, "ut": n} (what the Manual window saves). All six values are
  kept and used; the CONFIG / UF / UT of a taught point are carried to the result.

Tray grid (3 points)
  O = cell (row 0, col 0), X = cell (row 0, last col), Y = cell (last row, col 0), all taught with head 1.
  cell(r, c) = O + c * (X - O) / (cols - 1) + r * (Y - O) / (rows - 1), done on EACH of the six values, so a tray that is
  tilted, twisted or shifted is followed (the angle differences are wrapped to -180..180 first).
  O, X and Y must have the same CONFIG / UF / UT, otherwise the grid is refused.

Head offsets (the heads are fixed on the tool, so the offset between two heads is a rigid transform)
  Teach head 1 at the point O: the robot pose is A = P1(O). Teach head k at the SAME point O: the robot pose is Bk = Pk(O).
  A point Q taught with head 1 (robot pose P1(Q)) is reached by head k with the robot pose
        Pk(Q) = P1(Q) * inverse(A) * Bk          (4x4 matrices)
  which is right for every orientation of Q (the offset turns with the tool) - not only a shift of x / y / z. The reader of the
  End Effector (scanner) and its laser sensor (IL-1000) are handled exactly like one more head.

Laser check of a placed product: the laser is moved over measuring points that are given as offsets (x, y, z in mm) in the frame of the
place where the product was put (a cell of a tray, a box): `Layout.laser_poses()`.
"""
import math

REFERENCE_HEAD = 1
SCANNER = "scanner"
LASER = "laser"
ANGLE_FIELDS = (3, 4, 5)


class GeometryError(ValueError):
    """Missing / inconsistent taught points or an impossible grid."""


# ---------------------------------------------------------------------------------------------------------------- #
# poses <-> 4x4 matrices
# ---------------------------------------------------------------------------------------------------------------- #
def wrap180(angle):
    """Angle in degrees -> the equivalent angle in [-180, 180)."""
    return (float(angle) + 180.0) % 360.0 - 180.0


def split_point(value):
    """A taught point -> (six floats, extras). `extras` = {"config", "uf", "ut"} and any 7th..9th value (extended axes)."""
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
    """Six floats -> a point dict. CONFIG / UF / UT (and extended axes) are taken from `like` (a taught point)."""
    _, extras = split_point(like) if like is not None else ([], {"tail": []})
    out = {"xyzwpr": [round(v, 6) for v in xyz6] + list(extras.get("tail", []))}
    for key in ("config", "uf", "ut"):
        if key in extras:
            out[key] = extras[key]
    return out


def to_matrix(xyzwpr):
    """[x, y, z, w, p, r] -> 4x4 matrix (list of 4 rows). R = Rz(r) * Ry(p) * Rx(w)."""
    x, y, z, w, p, r = (float(v) for v in xyzwpr[:6])
    sw, cw = math.sin(math.radians(w)), math.cos(math.radians(w))
    sp, cp = math.sin(math.radians(p)), math.cos(math.radians(p))
    sr, cr = math.sin(math.radians(r)), math.cos(math.radians(r))
    return [[cr * cp, cr * sp * sw - sr * cw, cr * sp * cw + sr * sw, x],
            [sr * cp, sr * sp * sw + cr * cw, sr * sp * cw - cr * sw, y],
            [-sp, cp * sw, cp * cw, z],
            [0.0, 0.0, 0.0, 1.0]]


def from_matrix(m):
    """4x4 matrix -> [x, y, z, w, p, r] (degrees, w and r in [-180, 180], p in [-90, 90])."""
    cp = math.hypot(m[0][0], m[1][0])
    if cp > 1e-9:
        p = math.degrees(math.atan2(-m[2][0], cp))
        w = math.degrees(math.atan2(m[2][1], m[2][2]))
        r = math.degrees(math.atan2(m[1][0], m[0][0]))
    else:                                           # gimbal lock (p = +-90): r is set to 0, w takes the whole rotation
        p = 90.0 if m[2][0] < 0 else -90.0
        r = 0.0
        w = math.degrees(math.atan2(-m[1][2], m[1][1]))
    return [m[0][3], m[1][3], m[2][3], w, p, r]


def mat_mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def mat_inv(m):
    """Inverse of a rigid transform (rotation + translation)."""
    rt = [[m[j][i] for j in range(3)] for i in range(3)]
    t = [-sum(rt[i][k] * m[k][3] for k in range(3)) for i in range(3)]
    return [rt[0] + [t[0]], rt[1] + [t[1]], rt[2] + [t[2]], [0.0, 0.0, 0.0, 1.0]]


def pose_close(a, b, mm=1e-3, deg=1e-3):
    """Are two poses the same? (angles compared modulo 360)."""
    return (all(abs(a[i] - b[i]) <= mm for i in range(3))
            and all(abs(wrap180(a[i] - b[i])) <= deg for i in ANGLE_FIELDS))


# ---------------------------------------------------------------------------------------------------------------- #
# tray grid
# ---------------------------------------------------------------------------------------------------------------- #
class TrayGrid:
    """rows x cols cells computed from the three taught points O, X, Y (see the module docstring)."""

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
        """Change of the six values from one cell to the next along one side (zero when the side has a single cell)."""
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
        """Position in reading order (row by row, left to right) of the cell (row, col)."""
        self._check(row, col)
        return row * self.cols + col

    def rc(self, index):
        """(row, col) of the cell at this position in reading order."""
        if not 0 <= index < self.capacity:
            raise GeometryError("%s: cell index %r is outside 0..%d" % (self.name, index, self.capacity - 1))
        return divmod(index, self.cols)

    def _check(self, row, col):
        if not (0 <= row < self.rows and 0 <= col < self.cols):
            raise GeometryError("%s: cell (%r, %r) is outside the tray (%d rows x %d cols)" % (self.name, row, col, self.rows, self.cols))

    def cell(self, row, col):
        """Pose (point dict with all 6 values + CONFIG / UF / UT of O) of the cell, as head 1 must reach it."""
        self._check(row, col)
        v = [self._o[i] + col * self._step_c[i] + row * self._step_r[i] for i in range(6)]
        for i in ANGLE_FIELDS:
            v[i] = wrap180(v[i])
        return make_point(v, like=self._like)

    def cell_by_index(self, index):
        return self.cell(*self.rc(index))


# ---------------------------------------------------------------------------------------------------------------- #
# heads
# ---------------------------------------------------------------------------------------------------------------- #
class HeadTransforms:
    """Offsets between the heads (and the scanner) from the poses taught at the same point O: `at_o` = {1: pose, 2: pose, ...,
    "scanner": pose}; head 1 is the reference. `pose_for(k, q)` gives the robot pose that puts head k where head 1 is at `q`."""

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
        """Robot pose for head `key` (int, or "scanner") at the taught point `q` (pose or point dict)."""
        if key not in self._t:
            raise GeometryError("no offset for %r (head / scanner not taught at O)" % (key,))
        xyz, _ = split_point(q)
        out = from_matrix(mat_mul(to_matrix(xyz), self._t[key]))
        return make_point(out, like=q)

    def offset(self, key):
        """The six values of the transform head 1 -> `key` (a head, "scanner" or "laser") in the tool frame (for display / checks)."""
        return from_matrix(self._t[key])


# ---------------------------------------------------------------------------------------------------------------- #
# the whole layout (taught points of sequences.json -> poses)
# ---------------------------------------------------------------------------------------------------------------- #
def head_point_name(key):
    return {SCANNER: "scanner_at_O", LASER: "laser_at_O"}.get(key) or "head_%d_at_O" % key


def shift_pose(q, offset):
    """The point `q` moved by `offset` = (dx, dy, dz) mm measured in the frame of `q` (its orientation is kept)."""
    xyz, _ = split_point(q)
    t = [[1.0, 0.0, 0.0, float(offset[0])], [0.0, 1.0, 0.0, float(offset[1])], [0.0, 0.0, 1.0, float(offset[2])], [0.0, 0.0, 0.0, 1.0]]
    return make_point(from_matrix(mat_mul(to_matrix(xyz), t)), like=q)


class Layout:
    """Everything the planner needs to know about WHERE things are, built from the taught points by name:

        head_<k>_at_O  (k = 1..heads)   scanner_at_O (optional)     the same point O taught with each head / the reader
        input_O  input_X  input_Y        the input tray (head 1)
        ng_O  ng_X  ng_Y                 the NG tray (head 1)
        output1_O/X/Y  output2_O/X/Y     the output trays for passed products (head 1), only those that are in settings.json -> trays
        fixture_<n>                      the place of fixture n (head 1)
        laser_at_O (optional)            the laser sensor over the same point O (only when the placed products are checked with it)
    `trays` = {"input": {"rows", "cols"}, "ng": {...}}; `fixtures` = the fixture numbers; `heads` = number of heads.
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
                        for n in self.output_names(trays)]                     # output tray k (0-based) = "output<k+1>"
        self._fixture_points = {n: points["fixture_%d" % n] for n in self.fixtures}

    @staticmethod
    def output_names(trays):
        """The output trays that are configured, in the order they are used: ["output1", "output2"] / ["output1"] / []."""
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
        """Names of the taught points that are not there yet (empty list = complete)."""
        absent = [n for n in cls.required_names(trays, fixtures, heads, scanner, laser) if n not in points]
        for kind in ("input", "ng"):
            if kind not in (trays or {}):
                absent.append("settings.json -> trays -> %s" % kind)
        return absent

    # ---- poses the robot must go to -------------------------------------------------------------- #
    def pick_pose(self, head, index):
        """Head `head` over the cell `index` (reading order) of the INPUT tray."""
        return self.transforms.pose_for(head, self.input.cell_by_index(index))

    def input_pose(self, head, index):
        return self.pick_pose(head, index)

    def ng_pose(self, head, index):
        return self.transforms.pose_for(head, self.ng.cell_by_index(index))

    def output_pose(self, head, tray, index):
        """Head `head` over cell `index` of output tray `tray` (0-based: 0 = output1, 1 = output2)."""
        return self.transforms.pose_for(head, self.outputs[tray].cell_by_index(index))

    def fixture_pose(self, head, number):
        return self.transforms.pose_for(head, self._fixture_points[number])

    def scan_pose(self, index):
        """The barcode reader over the cell `index` of the input tray."""
        return self.transforms.pose_for(SCANNER, self.input.cell_by_index(index))

    def laser_poses(self, kind, ref, offsets):
        """Robot poses that put the laser sensor over the measuring points of the product just placed at `ref`:
        kind "input" / "ng" = cell index of that tray, "output" = (output tray index, cell), "box" = fixture number. `offsets` = [(dx, dy, dz) mm, ...] in the frame of the place."""
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
