import csv
import logging
import tempfile
import unittest
from pathlib import Path

from rcs.config import BASE_DIR, ConfigError, load_config
from rcs.logging_setup import setup_logging
from rcs.traceability import COLUMNS, CsvRecorder

INI = """
[system]
mode = {mode}
[network]
box_host = 127.0.0.1
box_start_port = 5001
robot_host = 10.0.0.5
robot_port = 6000
[scale]
box_count = {boxes}
gripper_heads = {heads}
[tray]
cols = 4
rows = 3
ng_tray_slots =
[layout]
Side A = 1-2
Side B = 3-4
[timing]
poll_interval = 0.2
robot_recv_timeout = 30
robot_max_retries = 3
box_recv_timeout = 5
[robot]
protocol = {protocol}
batch_enabled = {batch}
"""

FIXTURES = """
[fixtures]
1 = 192.168.1.101:6100
3 = 192.168.1.103:6100
"""


class ConfigTests(unittest.TestCase):
    def load(self, fixtures=FIXTURES, **kw):
        params = dict(mode="sim", boxes=4, heads=3, protocol="legacy", batch=0)
        params.update(kw)
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        ini, fx = Path(d.name) / "station.ini", Path(d.name) / "FixtureIP.ini"
        ini.write_text(INI.format(**params), encoding="utf-8")
        if fixtures is not None:
            fx.write_text(fixtures, encoding="utf-8")
        return load_config(ini, fx)

    def test_shipped_station_ini_is_valid(self):
        cfg = load_config()
        self.assertEqual(cfg.box_count, 30)
        self.assertEqual(sorted(cfg.box_address), list(range(1, 31)))
        self.assertEqual(cfg.protocol, "legacy")           # safe default

    def test_sim_mode_ignores_fixture_ips(self):
        cfg = self.load(mode="sim")
        self.assertEqual(cfg.box_address[1], ("127.0.0.1", 5001))
        self.assertEqual(cfg.box_address[4], ("127.0.0.1", 5004))

    def test_real_mode_uses_fixture_ips_with_sim_fallback(self):
        cfg = self.load(mode="real")
        self.assertEqual(cfg.box_address[1], ("192.168.1.101", 6100))
        self.assertEqual(cfg.box_address[3], ("192.168.1.103", 6100))
        self.assertEqual(cfg.box_address[2], ("127.0.0.1", 5002))   # not listed

    def test_ng_slots_default_to_tray_size(self):
        self.assertEqual(self.load().ng_tray_slots, 12)

    def test_fixture_without_port_rejected(self):
        with self.assertRaises(ConfigError):
            self.load(mode="real", fixtures="[fixtures]\n1 = 192.168.1.1\n")

    def test_invalid_values_rejected(self):
        with self.assertRaises(ConfigError):
            self.load(mode="lab")
        with self.assertRaises(ConfigError):
            self.load(protocol="v9")
        with self.assertRaises(ConfigError):
            self.load(heads=1)                      # need >= 2 (one stays free)
        with self.assertRaises(ConfigError):
            self.load(boxes=31)
        with self.assertRaises(ConfigError):
            self.load(boxes=3)                      # layout covers 1..4
        with self.assertRaises(ConfigError):
            self.load(batch=1, protocol="legacy")   # batch needs v2

    def test_batch_with_v2_ok(self):
        cfg = self.load(batch=1, protocol="v2")
        self.assertTrue(cfg.batch_enabled)

    def test_missing_ini(self):
        with self.assertRaises(ConfigError):
            load_config(BASE_DIR / "nope.ini")


class InfraTests(unittest.TestCase):
    def test_csv_recorder_writes_header_once_and_rows(self):
        with tempfile.TemporaryDirectory() as d:
            rec = CsvRecorder(Path(d))
            rec.record({"board_id": 1, "box_id": 2, "head": 0, "result": "PASS",
                        "origin_tray": 1, "origin_slot": 3, "test_seconds": 4.5,
                        "retest": 0, "ignored_extra": "x"})
            rec.record({"board_id": 2, "box_id": 3, "head": 1, "result": "FAIL",
                        "origin_tray": 1, "origin_slot": 4, "test_seconds": 5.0,
                        "retest": 1})
            files = list(Path(d).glob("results_*.csv"))
            self.assertEqual(len(files), 1)
            with files[0].open(encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(list(rows[0].keys()), COLUMNS)
            self.assertEqual([r["result"] for r in rows], ["PASS", "FAIL"])

    def test_csv_recorder_never_raises(self):
        # A path that cannot be created (file used as directory)
        with tempfile.TemporaryDirectory() as d:
            blocker = Path(d) / "f"
            blocker.write_text("x")
            CsvRecorder(blocker / "sub").record({"board_id": 1})

    def test_logging_callback_and_file(self):
        got = []
        with tempfile.TemporaryDirectory() as d:
            handler = setup_logging(Path(d), callback=lambda lvl, msg: got.append((lvl, msg)))
            logging.getLogger("rcs.test").info("hello %d", 7)
            logging.getLogger("rcs.test").debug("hidden")
            for h in logging.getLogger("rcs").handlers:
                h.flush()
            self.assertEqual(got, [(logging.INFO, "hello 7")])
            self.assertIn("hello 7", (Path(d) / "rcs.log").read_text(encoding="utf-8"))
            setup_logging(None)                      # detach handlers (release the file)


if __name__ == "__main__":
    unittest.main()

