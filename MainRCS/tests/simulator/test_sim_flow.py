"""The tray flow (planner + stages) with the real Runtime, bridge client, heads I/O, scanner and ATS clients against the cell simulator."""
import copy
import os
import tempfile
import threading
import unittest

import bridge_simple as BS
from rcs2.config import DEFAULTS
from rcs2.core import dut as D
from rcs2.core import engine as E
from rcs2.core.sequence import save_sequences
from rcs2.runtime import Runtime
from tests.core.test_flow_engine import BOXES, HEADS, TRAYS, taught_points
from tests.simulator.test_sim_cell import wait_until


class SimFlowCase(unittest.TestCase):
    """A Runtime in the tray flow wired to the cell simulator (also used by the runtime tests)."""
    pass_rate = 0.6
    seed = 5
    trays = TRAYS                          # TRAYS_OUT: with output trays for the passed products
    laser = False                          # True: an IL-1000 on the End Effector and flow.laser_check on (the simulator's laser says GO)

    def setUp(self):
        cfg = copy.deepcopy(BS.DEFAULTS)
        cfg.update({"status_s": 0.1, "poll_s": 0.01, "sim_delay_s": 0.02, "sim_scan_s": 0.01, "allow": ["*"],
                    "sim_test_time_s": 0.4, "sim_test_step_s": 0.1, "sim_seed": self.seed, "sim_pass_rate": self.pass_rate,
                    "sim_fixtures": dict((str(n), {"port": 0, "station": n}) for n in range(1, BOXES + 1)),
                    "sim_scanner": {"port": 0, "read_s": 0.01, "no_read_rate": 0.0, "prefix": "SIM"}})
        self.bridge = BS.Bridge(cfg, sim=True)
        self.cell = BS.Cell(self.bridge, cfg, "127.0.0.1").start()
        self.server = BS.Server(("127.0.0.1", 0), BS.Handler)
        self.server.bridge = self.bridge
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

        self.tmp = tempfile.TemporaryDirectory()
        s = copy.deepcopy(DEFAULTS)
        s["outbox_path"] = "outbox.sqlite"
        s["engine"]["sequences_path"] = "sequences.json"
        s["engine"]["test_timeout_s"] = 20
        s["bridge"].update({"host": "127.0.0.1", "port": self.server.server_address[1], "default_override": 10})
        s["ats"]["fixtures"] = dict((str(n), {"host": "127.0.0.1", "port": self.cell.fixtures[n].port, "station": "Station1",
                                              "robot_station": n}) for n in range(1, BOXES + 1))
        s["ats"].update({"heartbeat_s": 0.1, "retry_s": 0.2})
        s["end_effector"] = {
            "heads": {"enabled": True, "cylinder_s": 0.01, "vacuum_s": 0.01, "pressure_timeout_s": 0.5,
                      "units": [{"vacuum": "RDO[%d]" % n, "cylinder": "RDO[%d]" % (8 + n), "pressure": "RDI[%d]" % n}
                                for n in range(1, HEADS + 1)]},
            "scanner": {"type": "tcp", "host": "127.0.0.1", "port": self.cell.scanner.port, "length": 14, "retry": 1, "timeout_s": 1.0}}
        s["flow"].update({"mode": "tray", "override": 10})
        if self.laser:
            s["end_effector"]["laser"] = {"enabled": True, "model": "IL-1000", "ok": "RDI[20]", "high": "RDI[21]", "low": "RDI[22]",
                                          "active": 1, "timeout_s": 0.5}
            s["flow"]["laser_check"] = {"enabled": True, "places": ["box", "input", "output"], "offsets": [[-15, 0, 0], [15, 0, 0]], "timeout_s": 0.5}
        s["trays"] = self.trays
        save_sequences(os.path.join(self.tmp.name, "sequences.json"), {"points": taught_points(), "sequences": {}})
        self.rt = Runtime(s, self.tmp.name)
        self.rt.start()

    def tearDown(self):
        self.rt.stop()
        self.cell.stop()
        self.server.shutdown()
        self.bridge.stop()
        self.server.server_close()
        self.tmp.cleanup()

    def snap(self):
        return self.rt.engine.snapshot()

    def run_to_the_end(self):
        eng = self.rt.engine
        wait_until(lambda: self.snap()["robot"].get("connected"), what="robot link")
        wait_until(lambda: all(f["connected"] for f in self.snap()["fixtures"]), what="all fixtures connected")
        for n in range(1, BOXES + 1):
            eng.set_enabled(n, True)
        wait_until(lambda: self.snap()["program_running"] is True, what="robot program running")
        eng.start_run()
        wait_until(lambda: self.snap()["run_state"] == E.RUNNING, what="run started")
        wait_until(lambda: self.snap()["flow"]["stats"]["fresh"] == 0 and self.snap()["flow"]["stats"]["in_flight"] == 0
                   or self.snap()["run_state"] != E.RUNNING, timeout=90, what="every product put away")
        return self.snap()


class SimFlowTests(SimFlowCase):
    def test_every_product_is_tested_and_put_away_on_the_simulated_cell(self):
        snap = self.run_to_the_end()
        self.assertEqual(snap["run_state"], E.RUNNING, snap["fault_text"])
        st = snap["flow"]["stats"]
        self.assertEqual((st["passed"] + st["ng"], st["fresh"], st["in_flight"]), (8, 0, 0))
        book = self.rt.engine.flow.book
        for d in book.duts.values():
            boxes = [a[0] for a in d.attempts]
            self.assertEqual(len(boxes), len(set(boxes)), d)                          # never twice in the same box
            self.assertLessEqual(d.tests_made, 3)
            self.assertEqual(d.location[0], D.TRAY if d.final == "PASS" else D.NG_TRAY)
            self.assertEqual(len(d.sn), 14, d)                                       # every product was scanned
        self.assertEqual(self.cell.scanner.reads, 8)                                  # once per product, not per test
        self.assertFalse([a for a in snap["alarms"] if a["code"] in ("9201", "9202", "9203", "9100", "9205")], snap["alarms"])
        self.assertGreater(st["retests"], 0)                                          # pass rate 0.6: some products failed once

    def test_the_results_reach_the_report_outbox(self):
        self.run_to_the_end()
        results = [p for _, k, p in self.rt.sink.outbox.pending(1000) if k == "result"]
        st = self.snap()["flow"]["stats"]
        self.assertEqual(len(results), st["tests"])
        self.assertEqual(sum(1 for r in results if r["result"] == "PASS"), st["passed"])             # a pass ends the product


if __name__ == "__main__":
    unittest.main()
