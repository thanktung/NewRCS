"""MySQL naming/SQL (legacy layout), outbox retry behaviour and open-error recovery."""
import os
import tempfile
import time
import unittest
from datetime import datetime

from rcs2.reporting.data_sink import DataSink, ErrorTracker
from rcs2.reporting.mysql_writer import MySqlWriter
from rcs2.reporting.outbox import Outbox
from rcs2.reporting.sql_targets import SqlTargets

T = SqlTargets("LS04", ["Station1", "Station2"], "10.1.2.3")


class NamingTests(unittest.TestCase):
    def test_legacy_table_names(self):
        w = datetime(2026, 10, 5, 8, 0, 0)
        self.assertEqual(T.table("error", w), "LS04_Station1_Station2_10_1_2_3_Y2026_M10")
        self.assertEqual(T.table("login", w), "LoginLog_LS04_Station1_Station2_10_1_2_3_Y2026_M10")
        self.assertEqual(T.table("result", w), "TestResult_LS04_Station1_Station2_10_1_2_3_Y2026_M10")
        self.assertEqual(T.table("ats_hourly", w), "ATSHourlyIDE_LS04_Station1_Station2_10_1_2_3_Y2026_M10")
        self.assertEqual(T.table("robot_speed", w), "RobotSpeed_LS04_Station1_Station2_10_1_2_3")
        self.assertEqual(T.station_label, "LS04_Station1_Station2")

    def test_month_comes_from_the_event(self):
        self.assertTrue(T.table("login", "2026-01-31T23:59:59").endswith("Y2026_M01"))

    def test_rejects_unknown_kind_and_backticks(self):
        with self.assertRaises(ValueError):
            T.table("nope", datetime.now())
        with self.assertRaises(ValueError):
            SqlTargets("a`b", ["S"], "1.1.1.1").table("error", datetime.now())

    def test_ddl_and_insert_shapes(self):
        tbl = T.table("error", datetime(2026, 10, 5))
        self.assertIn("Start_Time DATETIME, End_Time DATETIME", T.ddl("error", tbl))
        sql, params = T.insert("error", tbl, {"error_code": "9027", "error": "Open door",
                                              "start": "2026-10-05T08:00:00", "end": "2026-10-05T08:01:00"})
        self.assertIn("(Station, ErrorCode, Error, Start_Time, End_Time)", sql)
        self.assertEqual(params[:3], ("LS04_Station1_Station2", "9027", "Open door"))
        sql, params = T.insert("result", T.table("result", datetime(2026, 10, 5)),
                               {"update_time": "2026-10-05T08:00:00", "fixture_no": "FIXTURE 1",
                                "ats_ip": "10.0.0.5", "result": "PASS", "test_time": 3.21, "product_type": "NORMAL"})
        self.assertIn("(UpdateTime, FixtureNo, ATS_IP, Result, TestTime, ProductType)", sql)
        self.assertEqual(params[1:4], ("FIXTURE 1", "10.0.0.5", "PASS"))


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        if self.conn.fail_on and self.conn.fail_on in sql:
            raise RuntimeError("simulated SQL failure")
        self.conn.log.append((sql, params))


class FakeConn:
    def __init__(self, fail_on=None):
        self.log, self.commits, self.fail_on, self.closed = [], 0, fail_on, False

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass

    def close(self):
        self.closed = True


class WriterTests(unittest.TestCase):
    def test_ensure_table_once_then_inserts(self):
        conn = FakeConn()
        w = MySqlWriter(T, connect_fn=lambda: conn)
        items = [(1, "login", {"staff_name": "A", "staff_id": "1", "staff_bp": "op X", "start": "2026-10-05T08:00:00"}),
                 (2, "login", {"staff_name": "B", "staff_id": "2", "staff_bp": "op X", "start": "2026-10-05T09:00:00"})]
        self.assertEqual(w.write_batch(items), 2)
        creates = [s for s, _ in conn.log if s.startswith("CREATE")]
        inserts = [s for s, _ in conn.log if s.startswith("INSERT")]
        self.assertEqual((len(creates), len(inserts), conn.commits), (1, 2, 2))
        self.assertTrue(conn.closed)

    def test_partial_batch_and_total_failure(self):
        ok = (1, "login", {"staff_name": "A", "staff_id": "1", "staff_bp": "x", "start": "2026-10-05T08:00:00"})
        bad = (2, "robot_speed", {"robot_name": "R", "speed": 5, "update_time": "2026-10-05T08:00:00"})
        conn = FakeConn(fail_on="RobotSpeed")
        self.assertEqual(MySqlWriter(T, connect_fn=lambda: conn).write_batch([ok, bad]), 1)
        with self.assertRaises(RuntimeError):
            MySqlWriter(T, connect_fn=lambda: FakeConn(fail_on="RobotSpeed")).write_batch([bad])


class FlakyWriter:
    """Fails the first `fail_times` calls like an unreachable database."""

    def __init__(self, fail_times):
        self.fail_times, self.calls, self.written = fail_times, 0, []

    def write_batch(self, items):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise ConnectionError("MySQL down")
        self.written.extend(items)
        return len(items)


class SinkTests(unittest.TestCase):
    def setUp(self):
        self.box = Outbox(":memory:")

    def test_nothing_lost_and_order_kept(self):
        writer = FlakyWriter(fail_times=2)
        sink = DataSink(self.box, writer, flush_interval_s=0.01)
        for i in range(5):
            sink.emit_result("10.0.0.5", "FIXTURE 1", "PASS", i)
        self.assertEqual(sink.flush_once(), -1)           # DB down: kept
        self.assertEqual(sink.flush_once(), -1)
        self.assertEqual(self.box.count(), 5)
        self.assertIn("MySQL down", sink.last_error)
        self.assertEqual(sink.flush_once(), 5)            # DB back
        self.assertEqual(self.box.count(), 0)
        self.assertEqual([p["test_time"] for _, _, p in writer.written], [0, 1, 2, 3, 4])

    def test_background_thread_uploads(self):
        writer = FlakyWriter(fail_times=1)
        sink = DataSink(self.box, writer, flush_interval_s=0.02, max_backoff_s=0.05)
        sink.start()
        sink.emit_login("A", "1", "op X")
        end = time.time() + 3
        while self.box.count() and time.time() < end:
            time.sleep(0.02)
        sink.stop(flush=False)
        self.assertEqual(self.box.count(), 0)
        self.assertEqual(len(writer.written), 1)

    def test_disabled_sink_keeps_data(self):
        sink = DataSink(self.box, FlakyWriter(0), enabled=False)
        sink.emit_login("A", "1", "x")
        self.assertEqual(sink.flush_once(), 0)
        self.assertEqual(self.box.count(), 1)

    def test_emit_never_raises(self):
        box = Outbox(":memory:")
        sink = DataSink(box, None)
        box.close()
        self.assertFalse(sink.emit("login", {}))


class ErrorTrackerTests(unittest.TestCase):
    def test_interval_row_on_clear(self):
        box = Outbox(":memory:")
        sink = DataSink(box, None)
        tr = ErrorTracker(sink, "LS04_Station1")
        self.assertTrue(tr.raise_error("9027", "Open door", when=datetime(2026, 10, 5, 8, 0, 0)))
        self.assertFalse(tr.raise_error("9027", "Open door"))          # duplicate ignored
        self.assertEqual(box.count(), 0)                               # nothing written until it ends
        self.assertTrue(tr.clear_error("9027", when=datetime(2026, 10, 5, 8, 5, 0)))
        self.assertFalse(tr.clear_error("9027"))
        (_, kind, p), = box.pending()
        self.assertEqual((kind, p["error_code"], p["start"], p["end"]),
                         ("error", "9027", "2026-10-05T08:00:00", "2026-10-05T08:05:00"))

    def test_recover_after_crash(self):
        path = os.path.join(tempfile.mkdtemp(), "outbox.sqlite")
        box1 = Outbox(path)
        tr1 = ErrorTracker(DataSink(box1, None), "LS04_Station1")
        tr1.raise_error("9201", "Robot alarm", when=datetime(2026, 10, 5, 8, 0, 0))
        box1.set_meta("last_alive", "2026-10-05T08:30:00")
        box1.close()                                                    # "crash": error never cleared
        box2 = Outbox(path)
        tr2 = ErrorTracker(DataSink(box2, None), "LS04_Station1")
        self.assertEqual(tr2.recover(), 1)
        (_, kind, p), = box2.pending()
        self.assertEqual((kind, p["error_code"], p["end"]), ("error", "9201", "2026-10-05T08:30:00"))
        self.assertEqual(box2.open_errors(), [])
        box2.close()


if __name__ == "__main__":
    unittest.main()
