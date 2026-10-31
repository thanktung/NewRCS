"""Protocol between RCS and the small ATS program of each fixture (unchanged from the old RCS).

Frames are UTF-8 text terminated by "_CEND"; fields inside a frame are separated by '+'.

RCS -> ATS : CtoT_placeDUTOK, B1=<SN>, CtoT_placeBarcode, DUT_OUT, f_open, f_close, aaa (heartbeat)
ATS -> RCS : TtoC_resultPass / resultNG+<item>+<value> / resultRetest / resultRetest1 / resultFQC /
             resultWarning / resultWaitdut / resultBusy / barcode+<SN> / BarcodePass+<SN> / BarcodeNG /
             resultOffsetPass|NG+<offset>+<SN> / AVI... / startOK / readcodeOK / fix_open|close|error

Matching is case-insensitive "contains", exactly like the old program, but the more specific
names are tested first (e.g. Retest1 before Retest, BarcodePass before barcode). The old code
tested "barcode" first, so a BarcodePass frame was treated as a plain barcode there.
"""
import codecs
from dataclasses import dataclass

TERMINATOR = "_CEND"

# ---- event kinds ---------------------------------------------------------- #
PASS = "PASS"
NG = "NG"
RETEST = "RETEST"
RETEST1 = "RETEST1"
FQC = "FQC"
WARNING = "WARNING"
WAITDUT = "WAITDUT"
BUSY = "BUSY"
BARCODE = "BARCODE"
BARCODE_PASS = "BARCODE_PASS"
BARCODE_NG = "BARCODE_NG"
OFFSET_PASS = "OFFSET_PASS"
OFFSET_NG = "OFFSET_NG"
AVI = "AVI"
START_OK = "START_OK"
READCODE_OK = "READCODE_OK"
FIX_OPEN = "FIX_OPEN"
FIX_CLOSE = "FIX_CLOSE"
FIX_ERROR = "FIX_ERROR"
UNKNOWN = "UNKNOWN"

# (upper-case needle, kind) - first match wins
_RULES = [
    ("TTOC_RESULTPASS", PASS),
    ("TTOC_RESULTWAITDUT", WAITDUT),
    ("TTOC_RESULTBUSY", BUSY),
    ("TTOC_RESULTNG", NG),
    ("TTOC_RESULTRETEST1", RETEST1),
    ("TTOC_RESULTCHOUJIAN", FQC),
    ("TTOC_RESULTFQC", FQC),
    ("TTOC_RESULT抽測", FQC),
    ("TTOC_RESULTWARNING", WARNING),
    ("TTOC_RESULTRETEST", RETEST),
    ("TTOC_RESULTOFFSETPASS", OFFSET_PASS),
    ("TTOC_RESULTOFFSETNG", OFFSET_NG),
    ("TTOC_BARCODEPASS", BARCODE_PASS),
    ("TTOC_BARCODENG", BARCODE_NG),
    ("TTOC_BARCODE", BARCODE),
    ("TTOC_AVI", AVI),
    ("TTOC_STARTOK", START_OK),
    ("TTOC_READCODEOK", READCODE_OK),
    ("FIX_ERROR", FIX_ERROR),
    ("FIX_OPEN", FIX_OPEN),
    ("FIX_CLOSE", FIX_CLOSE),
]


@dataclass
class AtsEvent:
    kind: str
    raw: str
    item: str = ""        # NG item
    value: str = ""       # NG value
    sn: str = ""          # barcode / serial number
    offset: str = ""      # position offset
    detail: str = ""      # free text (warning, retest, AVI)

    @property
    def is_result(self):
        return self.kind in (PASS, NG, RETEST, RETEST1, FQC, WARNING, OFFSET_PASS, OFFSET_NG)


def _field(parts, i):
    return parts[i].strip().replace(",", "") if len(parts) > i else ""


def parse_message(text):
    """Frame text (without the terminator) -> AtsEvent."""
    up = text.upper()
    kind = UNKNOWN
    for needle, k in _RULES:
        if needle in up:
            kind = k
            break
    parts = text.split("+")
    ev = AtsEvent(kind=kind, raw=text)
    if kind == NG:
        ev.item, ev.value = _field(parts, 1) or "UnKnown", _field(parts, 2) or "UnKnown"
    elif kind in (BARCODE, BARCODE_PASS):
        ev.sn = _field(parts, 1)
    elif kind in (OFFSET_PASS, OFFSET_NG):
        ev.offset, ev.sn = _field(parts, 1), _field(parts, 2)
    elif kind == RETEST1:
        ev.sn = _field(parts, 1)
    elif kind in (RETEST, WARNING):
        ev.detail = _field(parts, 1)
    elif kind == AVI:
        ev.detail = text
    return ev


class FrameDecoder:
    """Splits a TCP byte stream into frames (the stream may cut or merge frames anywhere)."""

    def __init__(self):
        self._dec = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self._buf = ""

    def feed(self, data):
        self._buf += self._dec.decode(data)
        frames = []
        while True:
            i = self._buf.find(TERMINATOR)
            if i < 0:
                break
            frame, self._buf = self._buf[:i], self._buf[i + len(TERMINATOR):]
            if frame.strip():          # empty frames (e.g. "f_open_CEND_CEND") are ignored
                frames.append(frame)
        return frames


def encode_frame(text):
    return (text + TERMINATOR).encode("utf-8")


# ---- RCS -> ATS message builders ------------------------------------------ #
HEARTBEAT = "aaa"
FIXSTATUS = "fixstatus"


def place_dut_ok():
    return "CtoT_placeDUTOK"


def barcode(sn):
    return "B1=%s," % sn


def request_barcode():
    return "CtoT_placeBarcode"


def dut_out():
    return "DUT_OUT"


def fixture_open():
    return "f_open"


def fixture_close():
    return "f_close"
