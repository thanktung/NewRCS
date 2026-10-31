"""Product trays of the cell: the INPUT tray (DUTs waiting to be picked), the NG tray (failed DUTs put down) and, optionally, two OUTPUT
trays (output1, output2: passed DUTs only, used in this order)

Each tray is a grid of `rows x cols` cells and the size is NOT fixed in code: it is set only in settings.json
(restart to apply):

    "trays": {"input": {"rows": 5, "cols": 8}, "ng": {"rows": 4, "cols": 6}}

Cells are used in reading order (row by row, left to right, starting at the top left).
  input  starts FULL.   Every DUT the robot picks empties the next cell. EMPTY = nothing left to load.
  ng     starts EMPTY.  Every NG DUT the robot puts down fills the next cell. FULL = the tray must be emptied.
  output1 / output2  start EMPTY, like ng: every passed DUT put down fills the next cell (output1 first, then output2).
The operator tells the program when the tray was refilled / emptied (`reset`). The state is not stored on disk: after a
restart the input tray counts as full and the NG tray as empty again.
"""
KINDS = ("input", "ng", "output1", "output2")
TITLES = {"input": "Tray Input", "ng": "Tray NG", "output1": "Tray Output 1", "output2": "Tray Output 2"}      # as the screens show them
MAX_SIDE = 50


class TrayConfigError(ValueError):
    pass


def check_size(kind, rows, cols):
    """(rows, cols) as ints within 1..MAX_SIDE, otherwise TrayConfigError."""
    for label, v in (("số hàng", rows), ("số cột", cols)):
        if isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= MAX_SIDE:
            raise TrayConfigError("tray %s: %s phải là số nguyên từ 1 đến %d (nhận %r)" % (kind, label, MAX_SIDE, v))
    return rows, cols


class Tray:
    def __init__(self, kind, rows, cols):
        if kind not in KINDS:
            raise TrayConfigError("loại tray %r không có (input | ng | output1 | output2)" % kind)
        self.kind = kind
        self.rows, self.cols = check_size(kind, rows, cols)
        self.done = 0                         # cells already used, counted in reading order

    @property
    def capacity(self):
        return self.rows * self.cols

    @property
    def exhausted(self):
        """input: nothing left to pick. ng: no room left to put a DUT."""
        return self.done >= self.capacity

    @property
    def count(self):
        """DUTs inside the tray right now (input: still waiting, ng: already put down)."""
        return self.capacity - self.done if self.kind == "input" else self.done

    def advance(self):
        """One cell used (a DUT picked from the input tray / put into the NG tray). False when there is no cell left."""
        if self.exhausted:
            return False
        self.done += 1
        return True

    def reset(self):
        """The operator refilled the input tray / emptied the NG tray."""
        self.done = 0

    def snapshot(self):
        return {"kind": self.kind, "rows": self.rows, "cols": self.cols, "capacity": self.capacity,
                "done": self.done, "count": self.count, "exhausted": self.exhausted}


def build_trays(cfg):
    """{"input": {"rows", "cols"}, "ng": {...}} -> {kind: Tray}. Kinds that are missing are simply not used."""
    trays = {}
    for kind, size in (cfg or {}).items():
        if str(kind).startswith("_"):
            continue
        if not isinstance(size, dict):
            raise TrayConfigError("tray %s: cần {\"rows\": n, \"cols\": n}" % kind)
        trays[kind] = Tray(kind, size.get("rows"), size.get("cols"))
    return trays

