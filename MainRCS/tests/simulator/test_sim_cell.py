"""The one-file cell simulator (bridge32/bridge_simple.py): fixtures' ATS programs, barcode scanner, robot stations,
the command line, and NewRCS itself running a whole load / test / unload cycle against it."""
import copy
import json
import os
import tempfile
import threading
import time
import unittest

from tests.support import bridge as helpers
import bridge_simple as BS
from rcs2.ats import protocol as AP
from rcs2.ats.client import AtsClient
from rcs2.config import DEFAULTS
from rcs2.core import engine as E
from rcs2.core.sequence import save_sequences
from rcs2.devices import scanner as SC
from rcs2.robot.client import BridgeClient, RobotError
from rcs2.runtime import Runtime


def wait_until(cond, timeout=15.0, what="condition"):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    raise AssertionError("timeout waiting for " + what)


class CellCase(unittest.TestCase):
    fixtures = 2
    over = {}

    def setUp(self):
        cfg = copy.deepcopy(BS.DEFAULTS)
        cfg.update({"auto_connect": True, "status_s": 0.1, "poll_s": 0.01, "sim_delay_s": 0.03, "sim_scan_s": 0.01,
                    "max_station": 120, "allow": ["*"], "sim_test_time_s": 0.3, "sim_test_step_s": 0.0, "sim_seed": 1,
                    "sim_fixtures": dict((str(n), {"port": 0, "station": n}) for n in range(1, self.fixtures + 1)),
                    "sim_scanner": {"port": 0, "read_s": 0.02, "no_read_rate": 0.0, "prefix": "SIM"}})
        cfg.update(self.over)
        self.cfg = cfg
        self.bridge = BS.Bridge(cfg, sim=True)
        self.cell = BS.Cell(self.bridge, cfg, "127.0.0.1").start()
        self.server = BS.Server(("127.0.0.1", 0), BS.Handler)
        self.server.bridge = self.bridge
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.sim = self.bridge.com.robot
        self.clients = []

    def tearDown(self):
        for c in self.clients:
            c.stop() if hasattr(c, "stop") else c.close()
        self.cell.stop()
        self.server.shutdown()
        self.bridge.stop()
        self.server.server_close()

    def ats(self, n, events):
        c = AtsClient(str(n), "127.0.0.1", self.cell.fixtures[n].port, heartbeat_s=0.1, retry_s=0.1,
                      on_event=events.append)
        c.start()
        self.clients.append(c)
        wait_until(lambda: c.connected, what="fixture %d connected" % n)
        return c

    def bridge_client(self):
        c = BridgeClient("127.0.0.1", self.port, ping_interval=0.2)
        c.connect()
        self.clients.append(c)
        return c


def kinds(events):
    return [e.kind for e in events]


class FixtureTests(CellCase):
    def test_connect_gives_waitdut_and_a_test_ends_with_a_result(self):
        events = []
        c = self.ats(1, events)
        wait_until(lambda: AP.WAITDUT in kinds(events), what="WAITDUT")
        c.place_dut_ok()
        wait_until(lambda: AP.START_OK in kinds(events), what="startOK")
        wait_until(lambda: any(e.is_result for e in events), what="a result")
        self.assertEqual(self.cell.fixtures[1].tests, 1)

    def test_forced_results_barcode_and_dut_out(self):
        events = []
        c = self.ats(1, events)
        bc = self.bridge_client()
        bc.call("sim.fixture", {"n": 1, "forced_results": ["NG", "PASS", "RETEST"], "test_time": 0.05})
        for expect in (AP.NG, AP.PASS, AP.RETEST):
            before = len([e for e in events if e.is_result])
            c.place_dut_ok()
            wait_until(lambda: len([e for e in events if e.is_result]) > before, what=expect)
            self.assertEqual([e for e in events if e.is_result][-1].kind, expect)
        ng = next(e for e in events if e.kind == AP.NG)
        self.assertEqual((ng.item, ng.value), ("TEST_ITEM", "12.3"))
        c.send_barcode("ABC123")
        wait_until(lambda: AP.READCODE_OK in kinds(events), what="readcodeOK")
        c.request_barcode()
        wait_until(lambda: AP.BARCODE_PASS in kinds(events), what="BarcodePass")
        self.assertEqual(next(e for e in events if e.kind == AP.BARCODE_PASS).sn, "ABC123")
        n = len([e for e in events if e.kind == AP.WAITDUT])
        c.dut_out()
        wait_until(lambda: len([e for e in events if e.kind == AP.WAITDUT]) == n + 1, what="WAITDUT after DUT_OUT")
        c.fixture_close()
        wait_until(lambda: AP.FIX_CLOSE in kinds(events), what="fix_close")

    def test_fixture_error_and_a_dropped_connection(self):
        events = []
        c = self.ats(2, events)
        bc = self.bridge_client()
        bc.call("sim.fixture", {"n": 2, "error": True})
        wait_until(lambda: AP.FIX_ERROR in kinds(events), what="fix_error")
        bc.call("sim.fixture", {"n": 2, "drop": True})
        wait_until(lambda: not c.connected, what="the ATS program goes away")
        wait_until(lambda: c.connected, what="NewRCS reconnects by itself")

    def test_fixtures_are_independent_ports(self):
        self.assertEqual(len(set(f.port for f in self.cell.fixtures.values())), 2)
        e1, e2 = [], []
        c1, c2 = self.ats(1, e1), self.ats(2, e2)
        c1.place_dut_ok()
        wait_until(lambda: AP.START_OK in kinds(e1), what="fixture 1 starts")
        self.assertNotIn(AP.START_OK, kinds(e2))

    def test_test_without_a_dut_is_started_in_lenient_mode(self):
        events = []
        c = self.ats(1, events)
        c.place_dut_ok()
        wait_until(lambda: AP.START_OK in kinds(events), what="startOK although the robot loaded nothing")


class StrictFixtureTests(CellCase):
    over = {"sim_strict_stations": True}

    def test_no_dut_no_test(self):
        events = []
        c = self.ats(1, events)
        c.place_dut_ok()
        time.sleep(0.5)
        self.assertNotIn(AP.START_OK, kinds(events))
        bc = self.bridge_client()
        bc.robot_connect()
        bc.arm()
        bc.get(0, override=10)
        bc.put(1, override=10)                                    # now the robot really loaded fixture 1
        self.assertTrue(self.cell.fixtures[1].state()["dut_inside"])
        c.place_dut_ok()
        wait_until(lambda: AP.START_OK in kinds(events), what="startOK with a DUT inside")


class StationTests(CellCase):
    def test_dut_travels_with_the_robot(self):
        bc = self.bridge_client()
        bc.arm()
        bc.get(0)
        self.assertIsNotNone(self.sim.holding)
        bc.put(2)
        self.assertEqual(self.sim.state()["stations"], {2: 1})
        self.assertTrue(self.sim.dut_at(2))
        self.assertFalse(self.sim.dut_at(1))
        bc.get(2)
        bc.put(8)                                                  # the PASS bin
        self.assertEqual(self.sim.state()["stations"], {8: 1})
        self.assertEqual(bc.call("sim.state")["cell"]["fixtures"]["2"]["dut_inside"], False)   # JSON keys are strings

    def test_strict_mode_refuses_impossible_moves(self):
        self.sim.strict = True
        bc = self.bridge_client()
        bc.arm()
        with self.assertRaises(RobotError) as cm:
            bc.get(5)                                              # nothing there
        self.assertEqual(cm.exception.code, "ROBOT_ERROR")
        bc.fault_clear()
        bc.arm()
        with self.assertRaises(RobotError):
            bc.put(1)                                              # nothing in the hand

    def test_input_tray_can_run_empty(self):
        self.sim.input_left = 1
        self.sim.strict = True
        bc = self.bridge_client()
        bc.arm()
        bc.get(0)
        bc.put(1)
        with self.assertRaises(RobotError):
            bc.get(0)


class ScannerTests(CellCase):
    def scanner(self, **kw):
        t = SC.TcpTransport("127.0.0.1", self.cell.scanner.port)
        sc = SC.KeyenceScanner("scanner", t, **kw)
        self.clients.append(sc)
        return sc

    def test_lon_returns_a_14_character_code_each_time(self):
        sc = self.scanner(length=14, pattern="[A-Z0-9]+")
        a, b = sc.scan(), sc.scan()
        self.assertEqual((len(a), len(b)), (14, 14))
        self.assertNotEqual(a, b)
        self.assertTrue(a.startswith("SIM"))

    def test_no_read_is_retried_then_reported(self):
        sc = self.scanner(retry=1, timeout_s=1.0)
        bc = self.bridge_client()
        bc.call("sim.scanner", {"fail_next": 1})
        self.assertEqual(len(sc.scan()), 14)                       # first attempt ERROR, the retry reads
        bc.call("sim.scanner", {"fail_next": 5})
        with self.assertRaises(SC.ScanError):
            sc.scan()

    def test_loff_stops_a_reading(self):
        self.cell.scanner.read_s = 5.0
        sc = self.scanner(retry=0, timeout_s=0.5)
        with self.assertRaises(SC.ScanError):
            sc.scan(retry=0, timeout_s=0.4)                        # the reader needs 5 s: time-out, LOFF is sent
        self.assertEqual(self.cell.scanner.last_sn, "")


class SimCommandTests(CellCase):
    def test_commands_need_a_cell_only_where_it_matters(self):
        bc = self.bridge_client()
        self.assertEqual(sorted(bc.call("sim.state")["cell"]["fixtures"]), ["1", "2"])
        with self.assertRaises(RobotError) as cm:
            bc.call("sim.fixture", {"n": 9})
        self.assertEqual(cm.exception.code, "BAD_REQUEST")
        with self.assertRaises(RobotError):
            bc.call("sim.fixture", {"n": 1, "forced_results": "NG"})
        with self.assertRaises(RobotError):
            bc.call("sim.scanner", {"no_read_rate": 3})


class CommandLineTests(unittest.TestCase):
    def settings_file(self, tmp):
        path = os.path.join(tmp, "settings.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"bridge": {"host": "192.168.5.6", "port": 5601},
                       "ats": {"fixtures": {"1": {"host": "192.168.5.6", "port": 8801, "robot_station": 1},
                                            "2": {"host": "10.164.125.9", "port": 8802, "robot_station": 7}}},
                       "end_effector": {"scanner": {"type": "tcp", "host": "192.168.5.6", "port": 9100}}}, fh)
        return path

    def test_ports_come_from_the_newrcs_settings(self):
        with tempfile.TemporaryDirectory() as d:
            newrcs = BS.load_newrcs_settings(self.settings_file(d))
            args = BS.build_parser().parse_args([])
            cfg = BS.build_config(args, newrcs)
        self.assertEqual(cfg["listen_port"], 5601)
        self.assertEqual(cfg["listen_host"], "0.0.0.0")
        self.assertEqual(cfg["sim_fixtures"], {"1": {"port": 8801, "station": 1}, "2": {"port": 8802, "station": 7}})
        self.assertEqual(cfg["sim_scanner"]["port"], 9100)
        self.assertEqual(cfg["allow"], ["*"])

    def test_command_line_wins_and_defaults_without_settings(self):
        args = BS.build_parser().parse_args(["--fixtures", "3", "--fixture-port-base", "9001", "--port", "5700",
                                              "--no-scanner", "--cold", "--strict", "--delay", "1.5", "--seed", "7"])
        cfg = BS.build_config(args, None)
        self.assertEqual(sorted(cfg["sim_fixtures"]), ["1", "2", "3"])
        self.assertEqual(cfg["sim_fixtures"]["3"], {"port": 9003, "station": 3})
        self.assertEqual((cfg["listen_port"], cfg["sim_scanner"], cfg["sim_cold"], cfg["sim_strict_stations"],
                          cfg["sim_delay_s"], cfg["sim_seed"]), (5700, None, True, True, 1.5, 7))
        self.assertEqual(len(BS.build_config(BS.build_parser().parse_args([]), None)["sim_fixtures"]), 4)

    def test_settings_that_point_elsewhere_are_reported(self):
        with tempfile.TemporaryDirectory() as d:
            newrcs = BS.load_newrcs_settings(self.settings_file(d))
        text = " | ".join(BS.config_warnings(BS.DEFAULTS, newrcs))
        self.assertIn("10.164.125.9", text)                            # fixture 2 is somewhere else
        self.assertIn("fixtures 2", text)
        self.assertEqual(len(BS.config_warnings(BS.DEFAULTS, newrcs)), 2)   # one line per foreign host

    def test_the_shipped_settings_are_all_simulated_on_one_host(self):
        newrcs = BS.load_newrcs_settings(os.path.join(helpers.ROOT, "config", "settings.json"))
        hosts = set(f["host"] for f in newrcs["fixtures"].values())
        hosts.add(newrcs["bridge_host"])
        hosts.add(newrcs["scanner"]["host"])
        self.assertEqual(hosts, {"192.168.5.6"})                        # one machine, different ports
        ports = [f["port"] for f in newrcs["fixtures"].values()] + [newrcs["bridge_port"], newrcs["scanner"]["port"]]
        self.assertEqual(len(ports), len(set(ports)))

    def test_main_refuses_a_port_that_is_taken(self):
        import socket
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        try:
            port = s.getsockname()[1]
            self.assertEqual(BS.main(["--no-settings", "--host", "127.0.0.1", "--port", str(port), "--fixtures", "1",
                                      "--fixture-port-base", str(port), "--no-scanner"]), 1)
        finally:
            s.close()


class NewRcsEndToEndTests(unittest.TestCase):
    """The real NewRCS (Runtime + Engine + End Effector + ATS clients + bridge client) against the simulator."""

    def setUp(self):
        cfg = copy.deepcopy(BS.DEFAULTS)
        cfg.update({"status_s": 0.1, "poll_s": 0.01, "sim_delay_s": 0.04, "sim_scan_s": 0.01, "allow": ["*"],
                    "sim_test_time_s": 0.3, "sim_test_step_s": 0.0, "sim_seed": 3, "sim_pass_rate": 0.0,
                    "sim_strict_stations": True,
                    "sim_fixtures": {"1": {"port": 0, "station": 1}, "2": {"port": 0, "station": 2}},
                    "sim_scanner": {"port": 0, "read_s": 0.02, "no_read_rate": 0.0, "prefix": "SIM"}})
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
        s["ats"]["fixtures"] = dict((str(n), {"host": "127.0.0.1", "port": self.cell.fixtures[n].port,
                                              "station": "Station1", "robot_station": n}) for n in (1, 2))
        s["ats"].update({"heartbeat_s": 0.1, "retry_s": 0.2})
        s["end_effector"] = {
            "heads": {"enabled": True, "cylinder_s": 0.01, "vacuum_s": 0.01, "pressure_timeout_s": 0.5,
                      "units": [{"vacuum": "RDO[%d]" % n, "cylinder": "RDO[%d]" % (8 + n), "pressure": "RDI[%d]" % n}
                                for n in range(1, 9)]},
            "scanner": {"type": "tcp", "host": "127.0.0.1", "port": self.cell.scanner.port, "length": 14, "retry": 1,
                        "timeout_s": 1.0},
            "laser": {"enabled": True, "ok": "RDI[20]", "timeout_s": 0.5}}
        pose = [100.0, 0.0, 200.0, 180.0, 0.0, 0.0]
        points = dict((n, list(pose)) for n in ("above_input", "above_pass", "above_ng",
                                                "above_fixture_1", "above_fixture_2"))
        load = [{"robot": "move", "pose": "above_input"}, {"ee": "scanner"},
                {"ee": "heads", "cylinder": "down"}, {"ee": "heads", "vacuum": "on"}, {"ee": "heads", "cylinder": "up"},
                {"ee": "heads", "check": "hold", "timeout_s": 0.5}, {"ee": "laser", "check": "ok"},
                {"robot": "get", "station": 0}, {"robot": "move", "pose": "above_fixture_{fixture}"},
                {"robot": "put", "station": "{robot_station}"}, {"ee": "heads", "vacuum": "off"}]
        seqs = {"load": load,
                "unload_pass": [{"robot": "move", "pose": "above_fixture_{fixture}"},
                                {"robot": "get", "station": "{robot_station}"}, {"robot": "move", "pose": "above_pass"},
                                {"robot": "put", "station": 20}],
                "unload_ng": [{"robot": "move", "pose": "above_fixture_{fixture}"},
                              {"robot": "get", "station": "{robot_station}"}, {"robot": "move", "pose": "above_ng"},
                              {"robot": "put", "station": 21}]}
        save_sequences(os.path.join(self.tmp.name, "sequences.json"), {"points": points, "sequences": seqs})
        s["trays"] = {"input": {"rows": 1, "cols": 3}, "ng": {"rows": 1, "cols": 3}}
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

    def test_load_test_unload_cycles_on_two_fixtures_until_the_input_tray_is_empty(self):
        eng = self.rt.engine
        wait_until(lambda: self.snap()["robot"].get("connected"), what="robot link")
        wait_until(lambda: all(f["connected"] for f in self.snap()["fixtures"]), what="both fixtures connected")
        for n in (1, 2):
            eng.set_enabled(n, True)
        eng.start_run()
        # pass_rate 0: every DUT is NG -> the NG tray fills while the 3 DUTs of the input tray are used up
        wait_until(lambda: self.snap()["trays"]["input"]["exhausted"], timeout=40, what="input tray empty")
        wait_until(lambda: self.snap()["trays"]["ng"]["count"] == 3, timeout=40, what="3 NG in the NG tray")
        snap = self.snap()
        self.assertEqual(snap["run_state"], E.RUNNING, snap["fault_text"])
        self.assertEqual(sum(f["total"] for f in snap["fixtures"]), 3)
        self.assertEqual(self.bridge.com.robot.state()["stations"], {21: 3})        # all three ended in the NG bin
        self.assertEqual(self.cell.scanner.reads, 3)
        self.assertTrue(all(f["sn"] == "" or len(f["sn"]) == 14 for f in snap["fixtures"]))


if __name__ == "__main__":
    unittest.main()
