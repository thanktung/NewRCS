"""Default value of every setting (config/settings.json is deep-merged over this).

Add a new setting here first (with a comment saying what it does), then read it with cfg["section"]["key"].
"""

DEFAULTS = {
    # Station identity; used to build the MySQL table names exactly like the old RCS did.
    "identity": {
        "bu": "",
        "model": "Model",
        "stations": ["Station1"],
        "local_ip": "",              # "" = auto-detect the first 10.x.x.x address
    },

    # MySQL dashboard database. 'enabled' replaces the old Setting.ini FE/Updata flag.
    "mysql": {
        "enabled": False,
        "host": "10.169.100.78",
        "port": 3306,
        "user": "root",
        "database": "rcs_dashboard",
        "password_env": "RCS_DB_PASSWORD",     # the password is read from this environment variable
        "connect_timeout_s": 5,
        "flush_interval_s": 2.0,
    },
    "outbox_path": "data/outbox.sqlite",       # local buffer: nothing is lost while MySQL is down

    "employee": {
        "url": "http://10.169.96.12/WS_ESD/CheckEmpRightWithEsd.asmx",
        "timeout_s": 30,
        "check_start": "2026-01-01 00:00:00",
        "check_end": "2050-12-28 23:59:59",
        "departments_path": "config/departments.json",   # department code -> level 1..5 (+ shared password)
        "offline_demo": False,
        "auto_logout_s": 180,          # the operator is logged out this long after logging in (0 = never)
        "auto_logout_idle": False,     # True: counts from the last mouse / key use instead of from the login
    },

    "bridge": {"host": "127.0.0.1", "port": 5600, "token_env": "RCS_BRIDGE_TOKEN",
               "default_override": 10},

    "ats": {
        "heartbeat_s": 0.5,
        "connect_timeout_s": 3.0,
        "retry_s": 2.0,
        # fixture number -> where its ATS program listens
        "fixtures": {
            "1": {"host": "127.0.0.1", "port": 8888, "station": "Station1"},
        },
    },

    # The ONE End Effector of the robot and the tools on it (see rcs2/devices/end_effector.py):
    #   "heads"   suction units: valve + cylinder + pressure sensor each, on the robot I/O  (rcs2/devices/heads.py)
    #   "scanner" Keyence barcode reader                                                    (rcs2/devices/scanner.py)
    #   "laser"   IL-1000 laser check                                                       (rcs2/devices/laser.py)
    # Used by the sequence steps {"ee": "heads" | "scanner" | "laser", ...}
    "end_effector": {},

    # Sizes (rows x cols) of the input tray and the NG tray, set ONLY here: {"input": {"rows": 5, "cols": 8}, "ng": {...}}.
    # Optional OUTPUT trays for the passed products ("output1", then "output2" when the first one is full): without them a passed
    # product goes back into the first empty cell of the input tray.
    # No default: a tray that is not declared is not shown / not counted.
    "trays": {},

    # Starting the robot program through the UOP signals (rcs2/robot/uop.py): rsr = which RSR program (1 -> RSR0001, UI[9]),
    # pulse_s = width of a UI pulse, reset_wait_s / run_wait_s / stop_wait_s = how long to wait for UO[6] FAULT = 0 / UO[3] PROGRUN = 1 / UO[3] PROGRUN = 0;
    # monitor_s = how often UO[3] PROGRUN is read to know whether the robot program runs
    "robot_start": {"rsr": 1, "pulse_s": 0.3, "reset_wait_s": 3.0, "run_wait_s": 5.0, "stop_wait_s": 3.0, "poll_s": 0.05,
                    "monitor_s": 0.5},

    # How the robot serves the boxes (rcs2/core/flow.py). "classic" = one sequence per fixture (sequences.json load / unload_*).
    # "tray" = many boxes, several heads: the planner fetches products from the input tray, swaps them in the boxes and puts them
    # back (tested 3 times at most, each time in another box). Only the keys below can be set; everything else (tray sizes,
    # taught points head_k_at_O / input_O.. / ng_O.. / fixture_N) lives in "trays" and sequences.json -> points.
    "flow": {
        "mode": "classic",             # "classic" | "tray"
        "max_attempts": 3,             # tests per product, every one in another box, then it goes to the NG tray
        "keep_free_heads": 1,          # heads kept free to take a tested product out of a box
        "max_pick": 8,                 # products fetched in one visit to the tray (<= number of heads)
        "max_sort": 8,                 # products put away in one visit to the tray
        "pick_ahead": 0,               # extra products fetched beyond the boxes that wait
        "top_up_when_idle": True,      # fetch products while every box is busy testing
        "fill_heads": True,            # at the tray fill ALL free heads (keep_free_heads stay free) instead of only what the waiting boxes need
        "scan": True,                  # read the barcode of each product before picking it (needs end_effector.scanner)
        "override": None,              # speed (%) of the moves; None = bridge.default_override
        "check_timeout_s": 1.0,        # time given to the pressure sensors after a pick / release
        "via_tray": "",                # optional taught points to pass through when going to the tray / to the boxes
        "via_fixtures": "",
        # After a product is PUT DOWN (box / input tray / NG tray) the IL-1000 laser is moved over `offsets` (2 measuring points, x y z in mm
        # in the frame of the place) and must say GO at each, otherwise the product is tilted (alarm 9204). Needs end_effector.laser and
        # the taught point laser_at_O. places: box | input | output | ng.
        "laser_check": {"enabled": False, "places": ["box", "input", "output"], "offsets": [[-15, 0, 0], [15, 0, 0]], "timeout_s": 1.0},
        "stop_robot_on_drop": True,    # a head lost its product on the way: stop the run AND the robot program (alarm 9208)
    },

    "consecutive_ng": {"limit": 3, "stop_fixture": True},

    "engine": {
        "reload_after_unload": True,   # after taking a tested DUT out, load the next one straight away
        "auto_start_test": True,       # send CtoT_placeDUTOK to the ATS right after the load sequence
        "send_dut_out": False,         # send DUT_OUT to the ATS after unloading
        "test_timeout_s": 300,         # raise alarm 9010 when no result arrives in this time
        "sequences_path": "config/sequences.json",
    },
}
