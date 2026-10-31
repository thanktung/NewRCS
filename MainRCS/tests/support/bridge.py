"""Run the single-file bridge (bridge32/bridge_simple.py, simulated robot) on a free local port for a test."""
import copy
import os
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))      # MainRCS/
for p in (ROOT, os.path.join(ROOT, "bridge32")):
    if p not in sys.path:
        sys.path.insert(0, p)

import bridge_simple as BS  # noqa: E402
from rcs2.robot.client import BridgeClient  # noqa: E402


class BridgeFixture:
    """Starts Server + Bridge(sim). `.sim` is the simulated robot (after robot.connect)."""

    def __init__(self, **over):
        cfg = copy.deepcopy(BS.DEFAULTS)
        cfg.update({"auto_connect": False, "status_s": 0.1, "poll_s": 0.01, "max_station": 120,
                    "sim_delay_s": 0.05})
        cfg.update(over)
        self.cfg = cfg
        self.bridge = BS.Bridge(cfg, sim=True)
        self.server = BS.Server(("127.0.0.1", 0), BS.Handler)
        self.server.bridge = self.bridge
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    @property
    def sim(self):
        return self.bridge.com.robot

    def client(self, **kw):
        c = BridgeClient("127.0.0.1", self.port, ping_interval=kw.pop("ping_interval", 0.2), **kw)
        c.connect()
        return c

    def close(self):
        self.server.shutdown()
        self.bridge.stop()
        self.server.server_close()
