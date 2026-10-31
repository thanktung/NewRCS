"""Keyence barcode readers: LON / LOFF protocol against a fake TCP reader, a fake COM port, the `scan` sequence
step and the engine (a code that cannot be read must stop the load BEFORE the robot picks anything)."""
import socket
import threading
import time
import unittest

from rcs2.ats import protocol as AP
from rcs2.core import engine as E
from rcs2.core import sequence as S
from rcs2.devices import scanner as SC

from tests.support.engine import POINTS, SEQ, EngineCase, FakeRobot, wait_until


class FakeKeyence:
    """TCP server that behaves like an SR reader. `script` = one entry per LON:
         "CODE"   -> answer CODE + CR           None  -> stay silent (read time-out)
         ("CODE", [b"AB", b"CD"]) -> answer in pieces      "CLOSE" -> answer and then drop the connection"""

    def __init__(self, script=()):
        self.script = list(script)
        self.commands = []
        self._conns = []
        self.srv = socket.socket()
        self.srv.bind(("127.0.0.1", 0))
        self.srv.listen(5)
        self.port = self.srv.getsockname()[1]
        self._stop = False
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self):
        while not self._stop:
            try:
                conn, _ = self.srv.accept()
            except OSError:
                return
            self._conns.append(conn)
            threading.Thread(target=self._serve, args=(conn,), daemon=True).start()

    def _serve(self, conn):
        buf = b""
        while True:
            try:
                data = conn.recv(1024)
            except OSError:
                return
            if not data:
                return
            buf += data
            while b"\n" in buf or b"\r" in buf:
                i = min(x for x in (buf.find(b"\n"), buf.find(b"\r")) if x >= 0)
                cmd, buf = buf[:i].decode(), buf[i + 1:]
                if not cmd:
                    continue
                self.commands.append(cmd)
                if cmd == "LON" and self.script:
                    self._answer(conn, self.script.pop(0))

    def _answer(self, conn, item):
        if item is None:
            return
        if isinstance(item, tuple):
            for piece in item[1]:
                conn.sendall(piece)
                time.sleep(0.05)
            conn.sendall(b"\r")
        elif item == "CLOSE":
            conn.sendall(b"CLOSED00000001\r")
            conn.close()
        else:
            conn.sendall(item.encode() + b"\r")

    def close(self):
        self._stop = True
        self.srv.close()
        for c in self._conns:
            try:
                c.close()
            except OSError:
                pass


def tcp_scanner(fake, **kw):
    kw.setdefault("retry", 0)
    kw.setdefault("timeout_s", 0.5)
    return SC.KeyenceScanner("tay1", SC.TcpTransport("127.0.0.1", fake.port, 1.0), **kw)


class TcpScannerTests(unittest.TestCase):
    def setUp(self):
        self.fake = FakeKeyence()

    def tearDown(self):
        self.fake.close()

    def test_reads_a_code_with_lon(self):
        self.fake.script = ["SN12345678AB"]
        sc = tcp_scanner(self.fake)
        self.assertEqual(sc.scan(), "SN12345678AB")
        self.assertEqual(self.fake.commands, ["LON"])
        sc.close()

    def test_code_split_over_several_packets(self):
        self.fake.script = [("", [b"SN1234", b"5678", b"AB"])]
        sc = tcp_scanner(self.fake)
        self.assertEqual(sc.scan(), "SN12345678AB")

    def test_no_read_then_retry_succeeds(self):
        self.fake.script = ["ERROR", "SN12345678AB"]
        sc = tcp_scanner(self.fake, retry=1)
        self.assertEqual(sc.scan(), "SN12345678AB")
        self.assertEqual(self.fake.commands, ["LON", "LON"])

    def test_timeout_sends_loff_and_gives_up_after_the_retries(self):
        self.fake.script = [None, None, None]
        sc = tcp_scanner(self.fake, retry=2, timeout_s=0.3)
        with self.assertRaises(SC.ScanError) as cm:
            sc.scan()
        self.assertIn("3 lần", str(cm.exception))
        self.assertIn("hết thời gian", str(cm.exception))
        time.sleep(0.1)
        self.assertEqual(self.fake.commands, ["LON", "LOFF"] * 3)

    def test_length_and_pattern_are_checked(self):
        self.fake.script = ["SHORT", "TOOLONGCODE1234", "ab12345678CDEF", "AB12345678CDEF"]
        sc = tcp_scanner(self.fake, length=14, pattern="[A-Z0-9]+", retry=3)
        self.assertEqual(sc.scan(), "AB12345678CDEF")           # 1 too short, 2 too long, 3 lower case, 4 ok
        self.assertEqual(self.fake.commands.count("LON"), 4)
        self.fake.script = ["XX"]
        with self.assertRaises(SC.ScanError) as cm:
            tcp_scanner(self.fake, length=14).scan()
        self.assertIn("dài 2 ký tự, cần 14", str(cm.exception))

    def test_step_can_override_length_and_pattern(self):
        self.fake.script = ["ABC123"]
        sc = tcp_scanner(self.fake, length=14)
        self.assertEqual(sc.scan(length=6, pattern="[A-Z]+[0-9]+"), "ABC123")

    def test_command_error_from_the_reader(self):
        self.fake.script = ["ER,LON,01"]
        with self.assertRaises(SC.ScanError) as cm:
            tcp_scanner(self.fake).scan()
        self.assertIn("ER,LON,01", str(cm.exception))

    def test_reader_not_reachable(self):
        port = self.fake.port
        self.fake.close()
        sc = SC.KeyenceScanner("tay1", SC.TcpTransport("127.0.0.1", port, 0.5), retry=1)
        with self.assertRaises(SC.ScanError) as cm:
            sc.scan()
        self.assertIn("không kết nối được", str(cm.exception))

    def test_reconnects_after_the_reader_dropped_the_link(self):
        self.fake.script = ["CLOSE", "SN12345678AB"]
        sc = tcp_scanner(self.fake, retry=1)
        self.assertEqual(sc.scan(), "CLOSED00000001")
        self.assertEqual(sc.scan(), "SN12345678AB")               # new connection is opened by itself

    def test_stale_data_does_not_leak_into_the_next_reading(self):
        self.fake.script = ["AAAA1111", "BBBB2222"]
        sc = tcp_scanner(self.fake)
        self.assertEqual(sc.scan(), "AAAA1111")
        self.assertEqual(sc.scan(), "BBBB2222")

    def test_cancel_stops_the_reading_with_loff(self):
        self.fake.script = [None]
        sc = tcp_scanner(self.fake, timeout_s=5.0)
        stop = threading.Event()
        threading.Timer(0.3, stop.set).start()
        t0 = time.time()
        with self.assertRaises(SC.ScanCancelled):
            sc.scan(should_stop=stop.is_set)
        self.assertLess(time.time() - t0, 2.0)
        time.sleep(0.1)
        self.assertEqual(self.fake.commands, ["LON", "LOFF"])

    def test_operator_loff_during_a_reading_and_busy_reader(self):
        self.fake.script = [None]
        sc = tcp_scanner(self.fake, timeout_s=1.0)
        result = []
        t = threading.Thread(target=lambda: result.append(self._scan_error(sc)))
        t.start()
        time.sleep(0.3)
        with self.assertRaises(SC.ScanError) as cm:
            sc.scan(blocking=False)                               # the Manual window must not wait for the job
        self.assertIn("đang bận", str(cm.exception))
        sc.stop()                                                 # LOFF while LON is pending
        t.join(3)
        time.sleep(0.1)
        self.assertEqual(self.fake.commands[:2], ["LON", "LOFF"])

    @staticmethod
    def _scan_error(sc):
        try:
            sc.scan()
        except SC.ScanError as ex:
            return ex

    def test_stop_without_a_connection_is_a_noop(self):
        sc = tcp_scanner(self.fake)
        sc.stop()
        self.assertEqual(self.fake.commands, [])


class FakeSerial:
    """Just enough of serial.Serial: data written as LON is answered from `answers`."""
    instances = []

    def __init__(self, port, baud, timeout=None, write_timeout=None):
        self.port, self.baud = port, baud
        self.rx = bytearray()
        self.written = []
        self.answers = FakeSerial.answers
        self.closed = False
        FakeSerial.instances.append(self)

    answers = []

    @property
    def in_waiting(self):
        return len(self.rx)

    def read(self, n):
        out, self.rx = bytes(self.rx[:n]), self.rx[n:]
        return out

    def write(self, data):
        self.written.append(bytes(data))
        if data.startswith(b"LON") and self.answers:
            a = self.answers.pop(0)
            if a is not None:
                self.rx += a.encode() + b"\r"

    def flush(self):
        pass

    def reset_input_buffer(self):
        self.rx.clear()

    def close(self):
        self.closed = True


class SerialScannerTests(unittest.TestCase):
    def setUp(self):
        FakeSerial.instances = []
        FakeSerial.answers = []

    def test_com_port_uses_the_same_protocol(self):
        FakeSerial.answers = ["SN12345678AB"]
        sc = SC.KeyenceScanner.from_config("tay2", {"type": "serial", "port": "COM3", "baud": 19200, "timeout_s": 1},
                                           serial_factory=FakeSerial)
        self.assertEqual(sc.scan(), "SN12345678AB")
        ser = FakeSerial.instances[0]
        self.assertEqual((ser.port, ser.baud), ("COM3", 19200))
        self.assertEqual(ser.written, [b"LON\r\n"])                  # same terminator as the old C# program
        sc.close()
        self.assertTrue(ser.closed)

    def test_com_timeout_sends_loff(self):
        FakeSerial.answers = [None]
        sc = SC.KeyenceScanner.from_config("tay2", {"type": "serial", "port": "COM3", "retry": 0, "timeout_s": 0.3},
                                           serial_factory=FakeSerial)
        with self.assertRaises(SC.ScanError):
            sc.scan()
        self.assertEqual(FakeSerial.instances[0].written, [b"LON\r\n", b"LOFF\r\n"])

    def test_missing_pyserial_is_reported_clearly(self):
        import sys
        saved = sys.modules.get("serial", "absent")
        sys.modules["serial"] = None                               # makes "import serial" fail
        try:
            sc = SC.KeyenceScanner.from_config("tay2", {"type": "serial", "port": "COM3", "retry": 0})
            with self.assertRaises(SC.ScanError) as cm:
                sc.scan()
            self.assertIn("pyserial", str(cm.exception))
        finally:
            if saved == "absent":
                del sys.modules["serial"]
            else:
                sys.modules["serial"] = saved


try:
    import serial  # noqa: F401
    HAVE_PYSERIAL = True
except ImportError:                 # pragma: no cover
    HAVE_PYSERIAL = False


@unittest.skipUnless(HAVE_PYSERIAL, "pyserial not installed")
class RealPyserialTests(unittest.TestCase):
    """The real serial.Serial code path, talking to the fake reader through pyserial's socket:// URL handler."""

    def setUp(self):
        self.fake = FakeKeyence()

    def tearDown(self):
        self.fake.close()

    def scanner(self, **kw):
        cfg = {"type": "serial", "port": "socket://127.0.0.1:%d" % self.fake.port, "retry": 0, "timeout_s": 0.6}
        cfg.update(kw)
        return SC.KeyenceScanner.from_config("tay2", cfg)

    def test_read_with_real_pyserial(self):
        self.fake.script = ["SN12345678AB", ("", [b"AB12", b"CD34"])]
        sc = self.scanner(length=12)
        self.assertEqual(sc.scan(), "SN12345678AB")
        with self.assertRaises(SC.ScanError):                           # second code is 8 long, 12 expected
            sc.scan()
        sc.close()
        self.assertEqual(self.fake.commands, ["LON", "LON"])

    def test_timeout_and_loff_with_real_pyserial(self):
        self.fake.script = [None]
        sc = self.scanner(timeout_s=0.3)
        with self.assertRaises(SC.ScanError):
            sc.scan()
        time.sleep(0.2)
        self.assertEqual(self.fake.commands, ["LON", "LOFF"])
        sc.close()

    def test_unreachable_url_is_a_scan_error(self):
        port = self.fake.port
        self.fake.close()
        with self.assertRaises(SC.ScanError) as cm:
            self.scanner(port="socket://127.0.0.1:%d" % port, retry=1).scan()
        self.assertIn("không kết nối được", str(cm.exception))


class ConfigTests(unittest.TestCase):
    def test_from_config_and_validate(self):
        a = SC.KeyenceScanner.from_config("scanner", {"type": "tcp", "host": "1.2.3.4"})
        b = SC.KeyenceScanner.from_config("scanner", {"type": "serial", "port": "COM1"})
        self.assertEqual(a.transport.port, 9004)                    # Keyence default
        self.assertEqual(b.transport.baud, 9600)
        for bad in ({"type": "usb"}, {"type": "tcp"}, {"type": "tcp", "host": "x", "pattern": "["},
                    {"type": "tcp", "host": "x", "length": "abc"}):
            with self.assertRaises(SC.ScanError):
                SC.KeyenceScanner.from_config("scanner", bad)


class FakeScanner:
    """Scanner stand-in for sequence / engine tests: returns the queued codes, raises ScanError for None."""

    def __init__(self, name, codes):
        self.name, self.codes, self.calls = name, list(codes), []

    def scan(self, **kw):
        self.calls.append(kw)
        code = self.codes.pop(0) if self.codes else None
        if code is None:
            raise SC.ScanError("máy quét %s: không đọc được mã sau 3 lần thử - hết thời gian chờ" % self.name)
        return code


class FakeEe:
    """End Effector stand-in carrying only a scanner."""

    def __init__(self, scanner):
        self.scanner = scanner

    def tool(self, kind):
        return self.scanner if kind == "scanner" else None

    def capabilities(self):
        return {"heads": 0, "scanner": self.scanner is not None, "laser": False}


class SequenceStepTests(unittest.TestCase):
    def test_validation(self):
        S.validate({"s": [{"ee": "scanner"}]}, {})                                 # tools not checked
        S.validate({"s": [{"ee": "scanner", "length": 14, "pattern": "[A-Z]{14}", "retry": 1, "timeout_s": 2}]}, {},
                   ee={"heads": 0, "scanner": True, "laser": False})
        for step, ee in (({"ee": "scanner"}, {"heads": 8, "scanner": False, "laser": False}),
                         ({"ee": "scanner", "length": -1}, None), ({"ee": "scanner", "retry": 1.5}, None),
                         ({"ee": "scanner", "timeout_s": 0}, None), ({"ee": "scanner", "pattern": "["}, None),
                         ({"ee": "scanner", "robot": "move"}, None), ({"ee": "camera"}, None),
                         ({"scan": "tay1"}, None)):                                # the old step is refused
            with self.assertRaises(S.SequenceError, msg=str(step)):
                S.validate({"s": [step]}, {}, ee=ee)

    def test_runner_scans_sets_sn_and_passes_the_regex_untouched(self):
        sc = FakeScanner("scanner", ["AB12345678CDEF"])
        ats = {1: type("A", (), {"send_barcode": lambda self, sn: seen.append(sn) or True})()}
        seen, got = [], []
        runner = S.SequenceRunner(object(), ats, {}, ee=FakeEe(sc))
        steps = [{"ee": "scanner", "pattern": "[A-Z0-9]{14}", "length": 14}, {"ats": "barcode", "sn": "{sn}"}]
        variables = {"fixture": 1}
        runner.run("load", steps, variables, on_scan=lambda code, name: got.append((code, name)))
        self.assertEqual(variables["sn"], "AB12345678CDEF")
        self.assertEqual(seen, ["AB12345678CDEF"])
        self.assertEqual(got, [("AB12345678CDEF", "scanner")])
        self.assertEqual(sc.calls[0]["pattern"], "[A-Z0-9]{14}")                  # "{14}" was not taken as a variable
        self.assertEqual(sc.calls[0]["length"], 14)

    def test_failed_scan_stops_the_sequence_before_the_next_step(self):
        class Robot:
            picked = False

            def get(self, *a, **k):
                Robot.picked = True
        runner = S.SequenceRunner(Robot(), {}, {}, ee=FakeEe(FakeScanner("scanner", [None])))
        with self.assertRaises(SC.ScanError):
            runner.run("load", [{"ee": "scanner"}, {"robot": "get", "station": 0}], {"fixture": 1})
        self.assertFalse(Robot.picked)

    def test_no_scanner_and_cancel(self):
        with self.assertRaises(S.SequenceError):
            S.SequenceRunner(object(), {}, {}).run("x", [{"ee": "scanner"}], {})
        with self.assertRaises(S.SequenceError):
            S.SequenceRunner(object(), {}, {}, ee=FakeEe(None)).run("x", [{"ee": "scanner"}], {})

        class Cancelling:
            def scan(self, should_stop=None, **kw):
                raise SC.ScanCancelled("đã hủy")
        with self.assertRaises(S.JobCancelled):
            S.SequenceRunner(object(), {}, {}, ee=FakeEe(Cancelling())).run("x", [{"ee": "scanner"}], {})


SCAN_SEQ = dict(SEQ)
SCAN_SEQ["load"] = [{"ee": "scanner"}, {"robot": "get", "station": 0}, {"robot": "put", "station": "{robot_station}"}]


class EngineScanTests(EngineCase):
    fixtures = 1
    codes = ["SN0000000001"]

    def setUp(self):
        super().setUp()
        self.eng.shutdown()                         # replace the engine built by EngineCase
        self.scanner = FakeScanner("scanner", self.codes)
        self.robot = FakeRobot()
        self.eng = E.Engine(self.cfg, self.robot, self.ats, self.sink, self.errors, SCAN_SEQ, POINTS,
                            ee=FakeEe(self.scanner))
        self.eng.start()
        self.eng.on_ats_connection(1, True)
        self.eng.set_enabled(1, True)

    def test_scanned_code_is_shown_on_the_fixture_and_the_dut_is_loaded(self):
        self.start_and_ready(1)
        wait_until(lambda: self.fx(1)["state"] == E.TESTING, what="TESTING")
        self.assertEqual(self.fx(1)["sn"], "SN0000000001")
        self.assertEqual(self.robot.calls[:2], [("get", 0), ("put", 1)])

    def test_unreadable_code_raises_9202_and_nothing_is_picked(self):
        self.scanner.codes = [None]
        self.start_and_ready(1)
        wait_until(lambda: self.eng.snapshot()["run_state"] == E.RUN_FAULT, what="FAULT")
        snap = self.eng.snapshot()
        self.assertTrue(any(a["code"] == "9202" for a in snap["alarms"]), snap["alarms"])
        self.assertFalse(any(a["code"] == "9201" for a in snap["alarms"]))
        self.assertEqual(self.robot.calls, [])                    # the robot never moved
        self.assertIn("không đọc được mã", snap["fault_text"])
        self.assertEqual(self.fx(1)["state"], E.FAULT)

    def test_engine_refuses_a_scanner_step_without_a_scanner_at_start_up(self):
        with self.assertRaises(S.SequenceError):
            E.Engine(self.cfg, self.robot, self.ats, self.sink, self.errors, SCAN_SEQ, POINTS, ee=FakeEe(None))


if __name__ == "__main__":
    unittest.main()
