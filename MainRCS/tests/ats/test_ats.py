"""ATS protocol parsing, framing and the client against the mock ATS."""
import threading
import time
import unittest

from rcs2.ats import protocol as P
from rcs2.ats.client import AtsClient
from rcs2.ats.mock_ats import MockAts


class ParseTests(unittest.TestCase):
    def test_results(self):
        cases = {
            "TtoC_resultPass": P.PASS,
            "TtoC_resultWaitdut": P.WAITDUT,
            "TtoC_resultBusy": P.BUSY,
            "TtoC_resultRetest1+SN1": P.RETEST1,
            "TtoC_resultRetest+x": P.RETEST,
            "TtoC_resultFQC": P.FQC,
            "TtoC_resultChouJian": P.FQC,
            "TtoC_result抽測": P.FQC,
            "TtoC_resultWarning+door": P.WARNING,
            "TtoC_startOK": P.START_OK,
            "TtoC_readcodeOK": P.READCODE_OK,
            "fix_open": P.FIX_OPEN,
            "fix_close": P.FIX_CLOSE,
            "fix_error": P.FIX_ERROR,
            "something else": P.UNKNOWN,
        }
        for text, kind in cases.items():
            self.assertEqual(P.parse_message(text).kind, kind, text)

    def test_case_insensitive(self):
        self.assertEqual(P.parse_message("ttoc_RESULTPASS").kind, P.PASS)

    def test_ng_fields(self):
        ev = P.parse_message("TtoC_resultNG+VCC_3V3+4.2,")
        self.assertEqual((ev.kind, ev.item, ev.value), (P.NG, "VCC_3V3", "4.2"))
        ev = P.parse_message("TtoC_resultNG")
        self.assertEqual((ev.item, ev.value), ("UnKnown", "UnKnown"))

    def test_barcode_variants_are_distinguished(self):
        # the old program tested "barcode" first and so mistook BarcodePass for a plain barcode
        self.assertEqual(P.parse_message("TtoC_BarcodePass+SN1").kind, P.BARCODE_PASS)
        self.assertEqual(P.parse_message("TtoC_BarcodeNG").kind, P.BARCODE_NG)
        ev = P.parse_message("TtoC_barcode+ABC123")
        self.assertEqual((ev.kind, ev.sn), (P.BARCODE, "ABC123"))

    def test_offset(self):
        ev = P.parse_message("TtoC_resultOffsetPass+1.0,2.0,3.0,0+SN9")
        self.assertEqual((ev.kind, ev.offset, ev.sn), (P.OFFSET_PASS, "1.02.03.00", "SN9"))
        self.assertEqual(P.parse_message("TtoC_resultOffsetNG+0,0+X").kind, P.OFFSET_NG)

    def test_is_result(self):
        self.assertTrue(P.parse_message("TtoC_resultPass").is_result)
        self.assertFalse(P.parse_message("TtoC_startOK").is_result)


class FrameTests(unittest.TestCase):
    def test_split_and_merged(self):
        d = P.FrameDecoder()
        self.assertEqual(d.feed(b"TtoC_resultPa"), [])
        self.assertEqual(d.feed(b"ss_CENDTtoC_start"), ["TtoC_resultPass"])
        self.assertEqual(d.feed(b"OK_CEND"), ["TtoC_startOK"])

    def test_terminator_split_across_reads(self):
        d = P.FrameDecoder()
        self.assertEqual(d.feed(b"a_CE"), [])
        self.assertEqual(d.feed(b"ND"), ["a"])

    def test_double_terminator_is_ignored(self):
        d = P.FrameDecoder()
        self.assertEqual(d.feed(b"f_open_CEND_CEND"), ["f_open"])

    def test_multibyte_split(self):
        data = "TtoC_result抽測_CEND".encode("utf-8")
        d = P.FrameDecoder()
        out = d.feed(data[:-9]) + d.feed(data[-9:])
        self.assertEqual(out, ["TtoC_result抽測"])


class ClientWithMockTests(unittest.TestCase):
    def setUp(self):
        self.mock = MockAts(port=0, test_time=0.1, seed=1).start()
        self.events = []
        self.conn = []
        self.client = AtsClient("1", "127.0.0.1", self.mock.port, heartbeat_s=0.1, retry_s=0.1,
                                on_event=self.events.append, on_connection=self.conn.append)
        self.client.start()

    def tearDown(self):
        self.client.stop()
        self.mock.stop()

    def wait_for(self, kind, timeout=3.0):
        end = time.time() + timeout
        while time.time() < end:
            for ev in list(self.events):
                if ev.kind == kind:
                    return ev
            time.sleep(0.02)
        self.fail("no %s event; got %s" % (kind, [e.kind for e in self.events]))

    def test_connect_and_waitdut(self):
        self.wait_for(P.WAITDUT)
        self.assertTrue(self.client.connected)
        self.assertEqual(self.conn[0], True)

    def test_barcode_then_test_pass(self):
        self.wait_for(P.WAITDUT)
        self.mock.forced_results = ["PASS"]
        self.assertTrue(self.client.send_barcode("SN0001"))
        self.wait_for(P.READCODE_OK)
        self.assertTrue(self.client.place_dut_ok())
        self.wait_for(P.START_OK)
        self.wait_for(P.PASS)
        self.assertIn("B1=SN0001,", self.mock.received)

    def test_ng_result_fields(self):
        self.wait_for(P.WAITDUT)
        self.mock.forced_results = ["NG"]
        self.client.place_dut_ok()
        ev = self.wait_for(P.NG)
        self.assertEqual((ev.item, ev.value), ("TEST_ITEM", "12.3"))

    def test_fixture_commands(self):
        self.wait_for(P.WAITDUT)
        self.client.fixture_close()
        self.wait_for(P.FIX_CLOSE)
        self.client.fixture_open()
        self.wait_for(P.FIX_OPEN)

    def test_send_when_disconnected_returns_false(self):
        c = AtsClient("x", "127.0.0.1", 1)       # never started
        self.assertFalse(c.send("aaa"))

    def test_reconnects_after_ats_restart(self):
        self.wait_for(P.WAITDUT)
        port = self.mock.port
        self.mock.stop()
        end = time.time() + 3
        while self.client.connected and time.time() < end:
            time.sleep(0.05)
        self.assertFalse(self.client.connected)
        self.events.clear()
        self.mock = MockAts(port=port, test_time=0.1).start()
        self.wait_for(P.WAITDUT, timeout=5.0)
        self.assertTrue(self.client.connected)

    def test_heartbeat_keeps_watchdog_quiet(self):
        self.mock.watchdog_s = 0.5
        self.wait_for(P.WAITDUT)
        time.sleep(1.2)
        self.assertTrue(self.client.connected)


if __name__ == "__main__":
    unittest.main()
