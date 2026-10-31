"""Demo mode: a simulated robot bridge and mock ATS programs run inside this process,
so the whole application can be tried without any hardware (python -m rcs2 --demo)."""
import copy
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))      # MainRCS/
BRIDGE_DIR = os.path.join(ROOT, "bridge32")

DEMO_POINTS = {
    "above_input": [300, -200, 250, 180, 0, 0],
    "above_pass": [-300, -200, 250, 180, 0, 0],
    "above_ng": [-300, 200, 250, 180, 0, 0],
    "above_fixture_1": [100, 300, 250, 180, 0, 0],
    "above_fixture_2": [200, 300, 250, 180, 0, 0],
    "above_fixture_3": [300, 300, 250, 180, 0, 0],
    "above_fixture_4": [400, 300, 250, 180, 0, 0],
}

DEMO_SEQUENCES = {
    "load": [
        {"robot": "move", "pose": "above_input"},
        {"robot": "get", "station": 0},
        {"robot": "move", "pose": "above_fixture_{fixture}"},
        {"robot": "put", "station": "{robot_station}"},
    ],
    "unload_pass": [
        {"robot": "move", "pose": "above_fixture_{fixture}"},
        {"robot": "get", "station": "{robot_station}"},
        {"robot": "move", "pose": "above_pass"},
        {"robot": "put", "station": 8},
    ],
    "unload_ng": [
        {"robot": "move", "pose": "above_fixture_{fixture}"},
        {"robot": "get", "station": "{robot_station}"},
        {"robot": "move", "pose": "above_ng"},
        {"robot": "put", "station": 9},
    ],
}


def sample_flow_points(settings):
    """SAMPLE taught points for the tray flow (settings.json -> flow.mode = tray), sized from the settings: one head_k_at_O per head of
    end_effector.heads.units, scanner_at_O, laser_at_O, the three points of every tray (input, NG, output) and fixture_N for every fixture. They only make the simulation
    run - they are NOT real coordinates (a real cell must teach them: Manual -> Hiệu chuẩn luồng tray)."""
    config = [0, 0, 1, 1, 0, 0, 0]

    def pt(x, y, z):
        return {"xyzwpr": [float(x), float(y), float(z), 180.0, 0.0, 0.0], "config": list(config), "uf": 1, "ut": 1}
    ee = settings.get("end_effector") or {}
    heads = len((ee.get("heads") or {}).get("units") or [])
    points = {"head_%d_at_O" % k: pt(500 - 22 * (k - 1), 100, 300) for k in range(1, heads + 1)}      # heads 22 mm apart
    if ee.get("scanner"):
        points["scanner_at_O"] = pt(545, 100, 300)
    if (settings.get("flow") or {}).get("laser_check", {}).get("enabled") and ee.get("laser"):
        points["laser_at_O"] = pt(575, 100, 300)
    trays = settings.get("trays") or {}
    for name, (ox, oy) in (("input", (100, 200)), ("ng", (400, 200)), ("output1", (100, 350)), ("output2", (400, 350))):
        if name in trays:
            rows, cols, pitch = trays[name]["rows"], trays[name]["cols"], 12
            points[name + "_O"] = pt(ox, oy, 50)
            points[name + "_X"] = pt(ox + pitch * (cols - 1), oy, 50)
            points[name + "_Y"] = pt(ox, oy + pitch * (rows - 1), 50)
    for key in settings["ats"]["fixtures"]:
        n = int(key)
        points["fixture_%d" % n] = pt(150 + 80 * ((n - 1) % 7), 600 + 120 * ((n - 1) // 7), 200)
    return points


def start_demo(settings, fixtures=4, speed=0.15, test_time=(3.0, 0.8)):
    """Start the simulated bridge + one mock ATS per fixture. Returns (settings, stop_function).

    `speed` scales the simulated robot motion time; `test_time` = (base, step) seconds of the mock tests.
    """
    if BRIDGE_DIR not in sys.path:
        sys.path.insert(0, BRIDGE_DIR)
    import threading
    import bridge_simple as BS
    from ..ats.mock_ats import MockAts

    cfg = copy.deepcopy(settings)

    bcfg = copy.deepcopy(BS.DEFAULTS)
    bcfg.update({"allow": ["127.0.0.1"], "max_override": 50, "max_station": 20, "auto_connect": True,
                 "sim_delay_s": max(0.02, speed * 3)})
    bcfg.update({"sim_fixtures": {}, "sim_scanner": {"port": 0, "read_s": 0.05, "no_read_rate": 0.0, "prefix": "SIM"}})
    app = BS.Bridge(bcfg, sim=True)
    cell = BS.Cell(app, bcfg, "127.0.0.1").start()                  # the barcode scanner of the End Effector (the ATS are mock ATS below)
    server = BS.Server(("127.0.0.1", 0), BS.Handler)
    server.bridge = app
    threading.Thread(target=server.serve_forever, daemon=True).start()
    cfg["bridge"]["host"], cfg["bridge"]["port"] = "127.0.0.1", server.server_address[1]
    cfg["bridge"]["default_override"] = 20
    scanner = (cfg.get("end_effector") or {}).get("scanner")
    if scanner:
        scanner.update({"type": "tcp", "host": "127.0.0.1", "port": cell.scanner.port})

    mocks = []
    cfg["ats"]["fixtures"] = {}
    for i in range(1, fixtures + 1):
        m = MockAts(port=0, test_time=test_time[0] + test_time[1] * i, pass_rate=0.8, seed=i).start()
        mocks.append(m)
        cfg["ats"]["fixtures"][str(i)] = {"host": "127.0.0.1", "port": m.port, "station": "Station1"}
    cfg["employee"]["offline_demo"] = True
    cfg["engine"]["test_timeout_s"] = 60

    def stop():
        for m in mocks:
            m.stop()
        cell.stop()
        server.shutdown()
        app.stop()
        server.server_close()

    return cfg, stop
