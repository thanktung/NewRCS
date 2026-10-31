"""Tk front-end of the bridge: traffic log, console, settings form, server start/stop (simulated robot)."""
import ast
import json
import os
import socket
import tempfile
import time
import unittest

from tests.support import bridge as helpers
from rcs2.robot.client import BridgeClient, RobotError

try:
    import tkinter as tk
    root_probe = tk.Tk()
    root_probe.destroy()
    HAVE_TK = True
except Exception:                      # no tkinter / no display
    HAVE_TK = False

if HAVE_TK:
    try:
        import bridge_gui as G
    except ImportError:    # the Tk front-end of the REAL bridge is not part of this repo
        HAVE_TK = False
    import bridge_simple as BS


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@unittest.skipUnless(HAVE_TK, "tkinter / display not available")
class GuiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._old_file = G.SETTINGS_FILE
        G.SETTINGS_FILE = os.path.join(self.tmp, "bridge_settings.json")
        self.errors, self.asked = [], []
        self._mb = (G.messagebox.showerror, G.messagebox.askyesno, G.messagebox.showwarning, G.messagebox.showinfo)
        G.messagebox.showerror = lambda *a, **k: self.errors.append(a)
        G.messagebox.showwarning = lambda *a, **k: self.errors.append(a)
        G.messagebox.showinfo = lambda *a, **k: None
        G.messagebox.askyesno = lambda *a, **k: (self.asked.append(a), True)[1]
        cfg = G.load_settings(None)
        cfg.update({"sim": True, "auto_connect": False, "listen_host": "127.0.0.1", "listen_port": free_port(),
                    "status_s": 0.1, "poll_s": 0.01, "max_station": 120, "sim_delay_s": 0.05})
        self.cfg = cfg
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = G.App(self.root, cfg, autostart=False)
        self.clients = []

    def tearDown(self):
        for c in self.clients:
            c.close()
        try:
            self.app.close_resources()
        except Exception:
            pass
        self.root.destroy()
        G.SETTINGS_FILE = self._old_file
        G.messagebox.showerror, G.messagebox.askyesno, G.messagebox.showwarning, G.messagebox.showinfo = self._mb

    def pump(self, seconds=0.3, until=None):
        end = time.time() + seconds
        while time.time() < end:
            self.root.update()
            if until and until():
                return True
            time.sleep(0.01)
        return bool(until and until())

    def client(self):
        c = BridgeClient("127.0.0.1", self.cfg["listen_port"], ping_interval=0.2)
        c.connect()
        self.clients.append(c)
        return c

    # ---- server + traffic ------------------------------------------------ #
    def test_traffic_shows_rx_and_tx(self):
        self.app.start_server()
        c = self.client()
        c.robot_connect()
        self.pump(0.5)
        texts = [(e["dir"], e["summary"]) for e in self.app.entries]
        self.assertTrue(any(d == "RX" and s.startswith("hello") for d, s in texts), texts[:6])
        self.assertTrue(any(d == "TX" and "ok" in s for d, s in texts))
        self.assertTrue(any(d == "RX" and s.startswith("robot.connect") for d, s in texts))
        rows = [self.app.tree.item(i, "values") for i in self.app.tree.get_children()]
        self.assertTrue(any(v[1] == "RX" and v[3].startswith("hello") for v in rows))
        self.assertGreater(self.app.counts["RX"], 0)
        self.assertGreater(self.app.counts["TX"], 0)

    def test_status_events_and_pings_are_hidden_until_enabled(self):
        self.app.start_server()
        c = self.client()
        c.robot_connect()
        self.pump(1.0)                                    # keep-alive pings + status events arrive
        kinds = {e["kind"] for e in self.app.entries}
        self.assertIn("status", kinds)
        self.assertIn("ping", kinds)
        shown = {e["kind"] for e in self.app._rows.values()}
        self.assertFalse(shown & {"status", "ping"})
        self.app.show_status.set(True)
        self.app.show_ping.set(True)
        self.app._render_all()
        shown = {e["kind"] for e in self.app._rows.values()}
        self.assertTrue({"status", "ping"} <= shown)

    def test_error_rows_and_detail_and_filter(self):
        self.app.start_server()
        c = self.client()
        c.robot_connect()
        with self.assertRaises(RobotError):
            c.move([1, 2, 3, 4, 5, 6])                    # NOT_ARMED
        self.pump(0.5)
        err_rows = [i for i, e in self.app._rows.items() if e["err"]]
        self.assertTrue(err_rows)
        self.app.tree.selection_set(err_rows[-1])
        self.app._show_detail()
        self.assertIn("NOT_ARMED", self.app.detail.get("1.0", "end"))
        self.app.filter_text.set("NOT_ARMED")
        self.app._render_all()
        self.assertTrue(self.app._rows)
        self.assertTrue(all("not_armed" in e["text"].lower() or "not_armed" in e["who"].lower()
                            for e in self.app._rows.values()))

    def test_clear_and_save_traffic(self):
        self.app.start_server()
        self.client().robot_connect()
        self.pump(0.4)
        path = os.path.join(self.tmp, "t.txt")
        G.filedialog.asksaveasfilename = lambda *a, **k: path
        self.app._save_traffic()
        with open(path, encoding="utf-8") as fh:
            body = fh.read()
        self.assertIn("RX", body)
        self.assertIn('"cmd":"hello"', body)
        self.app._clear_traffic()
        self.assertEqual(len(self.app.entries), 0)
        self.assertEqual(self.app.tree.get_children(), ())

    # ---- console ------------------------------------------------------------ #
    def test_console_read_command(self):
        self.app.start_server()
        self.pump(0.2)
        self.app.run_local({"cmd": "robot.connect"})
        self.assertTrue(self.pump(3, lambda: self.app.bridge.snap()["connected"]))
        self.app.cmd_text.delete("1.0", "end")
        self.app.cmd_text.insert("1.0", '{"cmd": "r.read", "args": {"index": 1}}')
        self.app._send_console()
        self.assertTrue(self.pump(3, lambda: '"value": 0' in self.app.answer.get("1.0", "end")))
        who = {e["who"] for e in self.app.entries}
        self.assertIn("local-gui", who)

    def test_console_motion_needs_arm_and_asks_confirmation(self):
        self.app.start_server()
        self.app.run_local({"cmd": "robot.connect"})
        self.assertTrue(self.pump(3, lambda: self.app.bridge.snap()["connected"]))
        self.app.run_local({"cmd": "motion.gosafehere", "args": {"override": 5}})
        self.assertEqual(len(self.asked), 1)              # confirmation dialog was shown
        self.assertTrue(self.pump(3, lambda: "NOT_ARMED" in self.app.answer.get("1.0", "end")))
        self.app.run_local({"cmd": "arm"})
        self.assertTrue(self.pump(3, lambda: self.app.bridge.snap()["armed"]))
        self.app.run_local({"cmd": "motion.gosafehere", "args": {"override": 5}})
        self.assertTrue(self.pump(5, lambda: '"op": "gosafehere"' in self.app.answer.get("1.0", "end")))
        self.app.run_local({"cmd": "disarm"}, force=True)
        self.assertTrue(self.pump(3, lambda: not self.app.bridge.snap()["armed"]))

    def test_console_without_server_warns(self):
        self.app.run_local({"cmd": "status"})
        self.assertTrue(self.errors)

    def test_bad_console_json(self):
        self.app.cmd_text.delete("1.0", "end")
        self.app.cmd_text.insert("1.0", "{not json")
        self.app._send_console()
        self.assertTrue(self.errors)

    # ---- monitor ------------------------------------------------------------- #
    def test_monitor_shows_state(self):
        self.app.start_server()
        c = self.client()
        c.robot_connect()
        c.arm()
        c.move([10, 20, 30, 0, 0, 0], override=20)
        self.assertTrue(self.pump(2, lambda: self.app.mon["armed"].get().startswith("127.0.0.1")))
        self.assertIn("connected", self.app.mon["robot"].get())
        self.assertIn("10.000", self.app.mon["pos"].get() if self.pump(1.0, lambda: "10.000" in self.app.mon["pos"].get()) else "")
        self.assertEqual(self.app.mon["r1"].get(), "0")
        self.assertIn("SIMULATED", self.app.mon["server"].get())

    # ---- settings ------------------------------------------------------------ #
    def test_settings_roundtrip_and_save(self):
        self.app.fill_form(self.cfg)
        out = self.app.read_form()
        for key in ("listen_port", "robot_host", "max_override", "allow", "register_pr", "protected_r", "pose_config",
                    "auto_connect", "sim"):
            self.assertEqual(out[key], self.cfg[key], key)
        self.app.settings_vars["max_override"][0].set("25")
        self.app.settings_vars["allow"][0].set("192.168.5.2, 10.0.0.9")
        self.app.ws_on.set(True)
        self.app.ws_vars["x"][0].set("-100")
        self.app.ws_vars["x"][1].set("300")
        self.app.save_form(apply=False)
        with open(G.SETTINGS_FILE, encoding="utf-8") as fh:
            saved = json.load(fh)
        self.assertEqual(saved["max_override"], 25)
        self.assertEqual(saved["allow"], ["192.168.5.2", "10.0.0.9"])
        self.assertEqual(saved["workspace"]["x"], [-100.0, 300.0])
        self.assertEqual(G.load_settings(G.SETTINGS_FILE)["max_override"], 25)

    def test_settings_validation(self):
        self.app.fill_form(self.cfg)
        v = self.app.settings_vars
        for key, bad in (("max_override", "200"), ("listen_port", "abc"), ("register_int", "5-2"),
                         ("r_station", "1"), ("max_rmove_mm", "-3"), ("protected_r", "7")):
            self.app.fill_form(self.cfg)
            v[key][0].set(bad)
            with self.assertRaises(ValueError, msg=key):
                self.app.read_form()
        self.app.fill_form(self.cfg)
        self.app.ws_on.set(True)
        self.app.ws_vars["z"][0].set("500")
        self.app.ws_vars["z"][1].set("100")
        with self.assertRaises(ValueError):
            self.app.read_form()
        self.app.fill_form(self.cfg)
        v["max_override"][0].set("999")
        self.app.save_form(apply=False)
        self.assertTrue(self.errors)                       # a message box, no file written
        self.assertFalse(os.path.exists(G.SETTINGS_FILE))

    def test_apply_restarts_the_server_with_new_settings(self):
        self.app.start_server()
        c = self.client()
        c.robot_connect()
        new_port = free_port()
        self.app.fill_form(self.cfg)
        self.app.settings_vars["listen_port"][0].set(str(new_port))
        self.app.save_form(apply=True)
        self.assertTrue(self.pump(3, lambda: self.app.bridge is not None and self.app.server is not None))
        self.pump(0.5)
        c2 = BridgeClient("127.0.0.1", new_port, ping_interval=0)
        c2.connect()
        self.clients.append(c2)
        self.assertEqual(c2.hello["mode"], "sim")
        self.assertEqual(self.app.cfg["listen_port"], new_port)

    def test_stop_drops_clients_and_refuses_new_ones(self):
        self.app.start_server()
        c = self.client()
        c.robot_connect()
        self.app.stop_server()
        end = time.time() + 3
        while c.connected and time.time() < end:
            self.pump(0.05)
        self.assertFalse(c.connected)
        self.assertIsNone(self.app.bridge)
        with self.assertRaises((ConnectionError, OSError, RobotError)):
            BridgeClient("127.0.0.1", self.cfg["listen_port"], ping_interval=0, connect_timeout=1.0).connect()

    def test_cannot_start_when_the_port_is_taken(self):
        blocker = socket.socket()
        blocker.bind(("127.0.0.1", 0))
        blocker.listen(1)
        try:
            self.cfg["listen_port"] = blocker.getsockname()[1]
            self.app.cfg = self.cfg
            self.app.start_server()
            self.assertIsNone(self.app.bridge)
            self.assertTrue(self.errors)
        finally:
            blocker.close()

    def test_log_tab_receives_bridge_log(self):
        self.app.start_server()
        self.pump(0.5)
        self.assertIn("server listening", self.app.log_text.get("1.0", "end"))


class SourceTests(unittest.TestCase):
    @unittest.skipUnless(os.path.exists(os.path.join(helpers.ROOT, "bridge32", "bridge_gui.py")),
                         "bridge_gui.py is not in this repo")
    def test_python38_syntax(self):
        with open(os.path.join(helpers.ROOT, "bridge32", "bridge_gui.py"), encoding="utf-8") as fh:
            ast.parse(fh.read(), feature_version=(3, 8))


if __name__ == "__main__":
    unittest.main()
