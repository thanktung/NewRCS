#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""bridge_simple.py - ONE-FILE SIMULATOR of the whole cell for NewRCS (headless, standard library only, Python 3.8+).

Use it when there is no robot and no fixture: NewRCS is started as usual and finds, on one machine (192.168.5.6), a robot
bridge, the ATS program of every fixture and the barcode scanner - each on its own port:

    python bridge32/bridge_simple.py                       # ports are read from ../config/settings.json
    python bridge32/bridge_simple.py --fixtures 4          # ... or without settings.json: bridge 5600, fixtures 8801.., scanner 9004
    python bridge32/bridge_simple.py --cold                # cold controller: emergency-stop state, program not running
    python bridge32/bridge_simple.py --pass-rate 0.5 --test-time 2 --delay 1.5 -v --strict --seed 1

    NewRCS settings.json        bridge   host 192.168.5.6  port 5600
                                ats.fixtures.N  host 192.168.5.6  port 8800 + N   (robot_station N)
                                end_effector.scanner  host 192.168.5.6  port 9004
    The PC that runs this file must own the address 192.168.5.6 (or use 127.0.0.1 in settings.json when NewRCS runs on the
    same PC). The simulator listens on every interface and accepts any client.

It speaks the same TCP / JSON-lines protocol as the real FRRJIf bridge (docs/robot_bridge_guide.md, rcs2/robot/protocol.py)
and stands in for the whole chain  bridge -> FRRJIf -> FANUC controller -> RSR0001, plus:
  * one SimFixture per fixture = the ATS program (frames "..._CEND"): WaitDUT on connect, startOK, a result after the test
    time (PASS / NG+item+value / RETEST by `--pass-rate`), readcodeOK, BarcodePass, fix_open / fix_close. It knows whether the
    robot really put a DUT in its station.
  * SimScanner = the Keyence reader of the End Effector: LON -> a 14 character code, LOFF.
  * the End Effector I/O: RDI[n] follows RDO[n] (vacuum on = product held), RDI[20] = laser judgement GO.

What is simulated
  * Bridge layer (the real rules of the guide): hello / token, allow-list, arm (one client, watchdog, keep-alive),
    motion.* with the limits (override, rmove, workspace, station), BUSY / FAULT_LATCHED / TIMEOUT / ROBOT_ERROR /
    VERIFY_FAILED, r.read / r.write (protected R[1]), pr.*, pos.read, io.read / io.write, alarm.clear, fault.clear,
    status events every `status_s`. Motion replies come back only when the robot has finished (concurrent requests on one
    connection are answered out of order, matched by `id`).
  * Robot program RSR0001 (the contract of section 9 of the guide): waits for R[1] > 0, executes the command (takes
    `sim_delay_s`), sets R[1] = 0 when done, R[1] = -1 on an error (station in `sim_bad_stations`, injected failure) and then
    waits for R[1] = 0 (fault.clear). A program that is stopped in the middle of a command leaves R[1] > 0 and executes
    that command again when it is restarted - like the real TP loop.
  * UOP signals (UI[n] is SDI[n], read-only UO[n]):
        UI1 IMSTP  UI2 HOLD  UI3 SFSPD   level: 1 = normal.  IMSTP 1->0: program aborted + FAULT; HOLD 0: motion paused
                                         (UO5 HELD, UO4 PAUSED, UO3 off); SFSPD 0: motions 3x slower
        UI4 CSTOPI   rising: cycle stop (program ended, R[1] untouched)
        UI5 RESET    rising: clears FAULT (only when IMSTP is on again)
        UI6 START    rising: starts the selected program (needs SDI1-3 = 1, SDI8 = 1, no fault, a program selected)
        UI8 ENBL     must be 1 to select / start
        UI9..UI16    RSR1..RSR8 rising: selects RSR0001..RSR0008 (ack on UO11..UO18)
        UO1 CMDENBL  UO2 SYSRDY  UO3 PROGRUN  UO4 PAUSED  UO5 HELD  UO6 FAULT  UO8 TPENBL  UO10 BUSY  UO11-18 ACK
    Only RSR0001 services the bridge; selecting another RSR runs "a program" that never answers (commands time out).
  * Other I/O: SDI SDO RDI RDO SI SO GI GO banks (bits, default 0). `sim_io_follow` makes inputs follow outputs
    (default: RDI[n] follows RDO[n] for n = 1..8, i.e. a product is always held when the vacuum is on) and `sim_inputs` sets
    initial input values (default RDI[20] = 1: laser judgement GO).

Simulation-only commands (no arm needed), to drive the scenario from a test or a script:
    sim.state    {}                                      program / UOP / register / position dump
    sim.set      {"kind","index","values"}               force any input / bank bits (SDI edges act like the real wiring)
    sim.inject   {"fail_next": n, "verify_fail": bool,   next n motions end with R[1] = -1; make parameter read-back differ;
                  "responding": bool, "bad_stations": []}  program stops answering (TIMEOUT); stations that make the robot fail
    sim.reset    {"cold": bool}                          back to the warm (default) or the cold state
    sim.fixture  {"n", "forced_results": ["NG"], "pass_rate", "test_time", "error": true, "drop": true, "send": "<frame>"}
    sim.scanner  {"fail_next": n, "no_read_rate": 0..1}  scanner that cannot read

Only the simulated robot is implemented: there is no FRRJIf layer in this file (`Bridge(cfg, sim=False)` is refused).
Keep this file parseable by Python 3.8 (tests/test_bridge_simple.py checks it).
"""
import argparse
import copy
import json
import logging
import math
import os
import random
import socket
import socketserver
import sys
import threading
import time

VERSION = "0.1-sim"
PROTOCOL = 1
MAX_LINE = 1 << 20

MOTION = {
    "rmove": 1,
    "move": 2,
    "put": 3,
    "get": 4,
    "down": 5,
    "up": 6,
    "gosafehere": 7,
    "gosafetarge": 8,
}
NEEDS_TARGET = ("rmove", "move", "gosafetarge")
NEEDS_STATION = ("put", "get", "down", "up")
CODE_NAME = dict((v, k) for k, v in MOTION.items())

# errors that take the arm away (guide, section 4)
DISARM_CODES = ("ROBOT_ERROR", "TIMEOUT", "VERIFY_FAILED", "NOT_CONNECTED", "INTERNAL")

IO_SIZE = {"SDI": 1000, "SDO": 1000, "RDI": 100, "RDO": 100, "SI": 100, "SO": 100, "UI": 20, "UO": 20, "GI": 20, "GO": 20}
UO_NAMES = ["CMDENBL", "SYSRDY", "PROGRUN", "PAUSED", "HELD", "FAULT", "ATPERCH", "TPENBL", "BATALM", "BUSY",
            "ACK1", "ACK2", "ACK3", "ACK4", "ACK5", "ACK6", "ACK7", "ACK8", "SNACK", "RESERVE"]


def _default_follow():
    """RDI[n] follows RDO[n] (a product is held while the vacuum is on) for the 8 heads, and the cylinder end-position sensors follow
    the coils: RDI[40+n] (down) <- RDO[8+n] (coil down), RDI[50+n] (up) <- RDO[16+n] (coil up)."""
    follow = dict(("RDI[%d]" % n, "RDO[%d]" % n) for n in range(1, 9))
    follow.update(dict(("RDI[%d]" % (40 + n), "RDO[%d]" % (8 + n)) for n in range(1, 9)))
    follow.update(dict(("RDI[%d]" % (50 + n), "RDO[%d]" % (16 + n)) for n in range(1, 9)))
    return follow


DEFAULTS = {
    # --- network / bridge rules (same names as the real bridge)
    "listen_host": "127.0.0.1",
    "listen_port": 5600,
    "allow": ["127.0.0.1"],          # client IPs; "*" = any. Others are disconnected silently
    "token": "",                     # "" = no token; otherwise hello must carry it
    "robot_host": "sim",
    "auto_connect": True,            # connect to the (simulated) robot at start-up
    "watchdog_s": 5.0,               # the arm is dropped when the armed client is silent this long
    "status_s": 0.5,                 # period of the "status" event
    "poll_s": 0.05,                  # how often a motion polls R[1]
    "op_timeout_s": 60.0,            # default timeout_s of a motion
    "max_override": 30,
    "default_override": 10,
    "max_station": 120,
    "max_rmove_mm": 100.0,
    "max_rmove_deg": 30.0,
    "workspace": None,               # {"x": [lo, hi], "y": [...], "z": [...]} or None = no limit
    "pose_config": [0, 0, 1, 1, 0, 0, 0],
    "pose_uf": -1,
    "pose_ut": -1,
    "protected_r": [1],
    "register_int": [1, 100],        # R[] that can be read / written (inclusive range)
    "register_real": [101, 200],
    "io_write_kinds": ["SDO", "RDO", "SDI"],
    # --- the simulated robot
    "sim_delay_s": 0.3,              # execution time of one command
    "sim_scan_s": 0.04,              # the TP loop needs this long to notice R[1] > 0
    "sim_cold": False,               # True: emergency-stop state, program not running, all UI = 0
    "sim_bad_stations": [99],        # put / get / up / down on these stations ends with R[1] = -1
    "sim_strict_select": False,      # True: an RSR pulse is ignored while the controller has a fault
    "sim_tp_enabled": False,         # UO8 TPENBL
    "sim_inputs": {"RDI[20]": 1},    # initial input bits
    "sim_io_follow": _default_follow(),
    "sim_strict_stations": False,    # True: get from an empty station / put with an empty hand ends with R[1] = -1
    "sim_input_count": None,          # DUTs at station 0 (the input tray); None = unlimited
    # --- the simulated cell around the robot (fixtures' ATS programs + the barcode scanner), used by main()
    "sim_fixtures": {},              # {"1": {"port": 8801, "station": 1}, ...}; empty = no fixture simulated
    "sim_test_time_s": 5.0,          # fixture n needs sim_test_time_s + (n - 1) * sim_test_step_s for one test
    "sim_test_step_s": 0.5,
    "sim_pass_rate": 0.85,
    "sim_retest_rate": 0.0,
    "sim_ng_item": "TEST_ITEM",
    "sim_ng_value": "12.3",
    "sim_seed": None,
    "sim_scanner": {"port": 9004, "read_s": 0.15, "no_read_rate": 0.0, "prefix": "SIM"},   # None = no scanner
}

log = logging.getLogger("bridge.sim")


class Err(Exception):
    """A protocol error: becomes {"ok": false, "error": {"code", "message"}}."""

    def __init__(self, code, message):
        Exception.__init__(self, "%s: %s" % (code, message))
        self.code = code
        self.message = message


def encode(msg):
    return (json.dumps(msg, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def parse_ref(text):
    """'RDO[12]' -> ('RDO', 12)."""
    t = str(text).strip().upper()
    if "[" not in t or not t.endswith("]"):
        raise ValueError("bad I/O reference %r" % (text,))
    kind, idx = t[:-1].split("[", 1)
    return kind.strip(), int(idx)


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


# --------------------------------------------------------------------------- #
# the simulated controller + RSR0001
# --------------------------------------------------------------------------- #
class SimRobot(object):
    """FANUC controller state (registers, position registers, I/O, UOP) and the RSR0001 loop (own thread)."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.lock = threading.RLock()
        self.executed = []              # (code, PR[1] xyzwpr, R[2], R[5]) of every command the program picked up
        self.responding = True          # False: the program does not look at R[1] (commands time out)
        self.fail_next = 0
        self.verify_fail = False
        self.strict = bool(cfg["sim_strict_stations"])
        self.bad_stations = list(cfg["sim_bad_stations"])
        self._quit = threading.Event()
        self._thread = None
        self._follow = {}
        for dst, src in cfg["sim_io_follow"].items():
            skind, sidx = parse_ref(src)
            self._follow.setdefault((skind, sidx), []).append(parse_ref(dst))
        self.reset(cfg["sim_cold"])

    # ---- state ------------------------------------------------------------------------------ #
    def reset(self, cold=False):
        with self.lock:
            self.epoch = getattr(self, "epoch", 0) + 1                   # aborts a command in progress
            self.r = {}
            self.pr = {}
            self.io = dict((k, {}) for k in IO_SIZE)
            self.pos = [0.0] * 6
            self.config = list(self.cfg["pose_config"])
            self.uf, self.ut = 0, 1
            self.running, self.selected, self.busy = False, None, False
            self.fault, self.alarm = False, ""
            self.stations = {}                  # station -> [DUT ids waiting there]; station 0 is the input tray
            self.holding = None                 # DUT id on the End Effector
            self.input_left = self.cfg["sim_input_count"]
            self._dut_seq = getattr(self, "_dut_seq", 0)
            self.ack_until = {}
            if not cold:                                                   # wired-up cell, RSR0001 waiting for commands
                for i in (1, 2, 3, 8):
                    self.io["SDI"][i] = 1
                self.running, self.selected = True, 1
            else:
                self.fault, self.alarm = True, "IMSTP: external emergency stop"
            for ref, value in self.cfg["sim_inputs"].items():
                kind, idx = parse_ref(ref)
                self.io[kind][idx] = int(value)
            for (skind, sidx) in self._follow:
                self._apply_follow(skind, sidx)

    def start(self):
        with self.lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._quit.clear()
            self._thread = threading.Thread(target=self._program, name="sim-rsr0001", daemon=True)
            self._thread.start()

    def stop(self):
        self._quit.set()
        t = self._thread
        if t is not None and t is not threading.current_thread():
            t.join(1.0)

    # ---- registers / position registers / position ---------------------------------------------- #
    def r_get(self, i):
        with self.lock:
            return self.r.get(i, 0)

    def r_set(self, i, value):
        with self.lock:
            self.r[i] = value

    def pr_get(self, group, idx):
        with self.lock:
            pos = self.pr.get((group, idx))
            if pos is None:
                pos = {"xyzwpr": [0.0] * 6, "config": list(self.cfg["pose_config"]), "uf": self.cfg["pose_uf"],
                       "ut": self.cfg["pose_ut"]}
            return copy.deepcopy(pos)

    def pr_set(self, group, idx, pos):
        with self.lock:
            self.pr[(group, idx)] = copy.deepcopy(pos)

    def curpos(self):
        with self.lock:
            return {"xyzwpr": list(self.pos), "config": list(self.config), "uf": self.uf, "ut": self.ut}

    # ---- I/O ------------------------------------------------------------------------------------ #
    def io_get(self, kind, index, count):
        with self.lock:
            out = []
            for i in range(index, index + count):
                if kind == "UO":
                    out.append(self.uo_value(i))
                elif kind == "UI":
                    out.append(self.io["SDI"].get(i, 0))                    # UI[n] is mapped to SDI[n]
                else:
                    out.append(self.io[kind].get(i, 0))
            return out

    def io_set(self, kind, index, values):
        """Writes bits (SDI edges act on the controller like the real UOP wiring); returns the values read back."""
        with self.lock:
            if kind == "UI":
                kind = "SDI"
            for off, v in enumerate(values):
                i, v = index + off, int(v)
                old = self.io[kind].get(i, 0)
                self.io[kind][i] = v
                self._apply_follow(kind, i)
                if kind == "SDI" and old != v:
                    self._on_sdi(i, old, v)
            return self.io_get(kind, index, len(values))

    def _apply_follow(self, kind, idx):
        for dkind, didx in self._follow.get((kind, idx), []):
            self.io[dkind][didx] = self.io[kind].get(idx, 0)

    # ---- UOP --------------------------------------------------------------------------------------- #
    def _sdi(self, i):
        return self.io["SDI"].get(i, 0)

    @property
    def held(self):
        return self._sdi(2) == 0

    def uo_value(self, n):
        run, held = self.running, self.held
        if n == 1:
            return int(self._sdi(8) == 1 and self._sdi(1) == 1 and not self.fault)       # CMDENBL
        if n == 2:
            return int(self._sdi(1) == 1 and not self.fault)                             # SYSRDY
        if n == 3:
            return int(run and not held)                                                 # PROGRUN
        if n == 4:
            return int(run and held)                                                     # PAUSED
        if n == 5:
            return int(held)                                                             # HELD
        if n == 6:
            return int(self.fault)                                                       # FAULT
        if n == 8:
            return int(bool(self.cfg["sim_tp_enabled"]))                                 # TPENBL
        if n == 10:
            return int(self.busy)                                                        # BUSY
        if 11 <= n <= 18:
            return int(time.time() < self.ack_until.get(n - 10, 0.0))                    # ACK1..ACK8
        return 0

    def _abort_program(self, why):
        if self.running:
            log.info("program aborted (%s)", why)
        self.running = False
        self.epoch += 1

    def _on_sdi(self, i, old, new):
        if i == 1 and new == 0:                               # IMSTP released: emergency stop
            self._abort_program("IMSTP")
            self.fault, self.alarm = True, "IMSTP: external emergency stop"
        elif i == 4 and new == 1:                             # CSTOPI: cycle stop
            self._abort_program("CSTOPI")
        elif i == 5 and new == 1:                             # RESET
            if self._sdi(1) == 1:
                self.fault, self.alarm = False, ""
        elif i == 6 and new == 1:                             # START
            ok = (self.selected is not None and not self.running and not self.fault and self._sdi(8) == 1
                  and all(self._sdi(k) == 1 for k in (1, 2, 3)))
            if ok:
                self.running = True
                log.info("program RSR%04d started", self.selected)
        elif 9 <= i <= 16 and new == 1:                       # RSR1..RSR8
            if self._sdi(8) == 1 and not self.running and not (self.cfg["sim_strict_select"] and self.fault):
                self.selected = i - 8
                self.ack_until[i - 8] = time.time() + 0.2
                log.info("program RSR%04d selected", self.selected)

    # ---- alarm / fault ----------------------------------------------------------------------------- #
    def clear_alarm(self):
        """Like a RESET from the teach pendant: works only when the cause (IMSTP) is gone."""
        with self.lock:
            if self.fault and self._sdi(1) == 1:
                self.fault, self.alarm = False, ""
                return True
            return not self.fault

    # ---- the RSR0001 loop -------------------------------------------------------------------------- #
    def _serves_bridge(self):
        return self.responding and self.running and self.selected == 1 and not self.fault

    def _program(self):
        tick = max(0.002, min(0.02, float(self.cfg["poll_s"])))
        while not self._quit.is_set():
            job = None
            with self.lock:
                if self._serves_bridge() and self.r.get(1, 0) > 0:
                    job = (self.epoch, self.r.get(1, 0))
            if job is None:
                self._quit.wait(tick)
                continue
            self._run_command(job[0], job[1])

    def _wait(self, epoch, seconds, tick=0.005):
        """Sleeps `seconds` of program time. Time stands still while HOLD is active. False if the program was stopped."""
        done = 0.0
        while done < seconds:
            if self._quit.is_set():
                return False
            with self.lock:
                if self.epoch != epoch or not self.running:
                    return False
                held = self.held
            time.sleep(tick)
            if not held:
                done += tick
        return True

    def _run_command(self, epoch, code):
        if not self._wait(epoch, float(self.cfg["sim_scan_s"])):
            return
        with self.lock:
            if self.epoch != epoch or self.r.get(1, 0) != code:
                return
            station, override = self.r.get(2, 0), self.r.get(5, 0)
            target = self.pr_get(1, 1)
            self.executed.append((code, list(target["xyzwpr"]), station, override))
            self.busy = True
            speed = 3.0 if self._sdi(3) == 0 else 1.0                       # SFSPD off: safe speed
        name = CODE_NAME.get(code, "?")
        log.info("RSR0001: %s (R[1]=%s, R[2]=%s, R[5]=%s)", name, code, station, override)
        finished = self._wait(epoch, float(self.cfg["sim_delay_s"]) * speed)
        with self.lock:
            self.busy = False
            if not finished or self.epoch != epoch:
                log.info("RSR0001: %s interrupted, R[1] stays %s", name, self.r.get(1))
                return
            error = self._apply(code, target, station)
            if error:
                log.warning("RSR0001: %s failed: %s -> R[1] = -1", name, error)
                self.r[1] = -1                 # the TP program now waits for R[1] = 0 (fault.clear)
            else:
                self.r[1] = 0                  # the LAST step of every command

    def _apply(self, code, target, station):
        """Effect of a finished command on the position; returns an error text or ''."""
        if code not in CODE_NAME:
            return "unknown command code %s" % (code,)
        if self.fail_next > 0:
            self.fail_next -= 1
            return "injected failure (sim.inject fail_next)"
        name = CODE_NAME[code]
        if name in NEEDS_STATION and (station in self.bad_stations or station < 0):
            return "station %s does not exist" % (station,)
        if name in ("get", "put"):
            error = self._take(station) if name == "get" else self._leave(station)
            if error:
                if self.strict:
                    return error
                log.warning("RSR0001: %s (continuing, sim_strict_stations is off)", error)
        xyz = list(target["xyzwpr"])[:6]
        if name == "rmove":
            self.pos = [round(a + b, 6) for a, b in zip(self.pos, xyz)]
        elif name in ("move", "gosafetarge"):
            self.pos = [float(v) for v in xyz]
            self.config, self.uf, self.ut = list(target["config"]), target["uf"], target["ut"]
        return ""

    # ---- DUTs: where they are (so that fixtures know whether the robot really loaded them) --------------- #
    def _new_dut(self):
        self._dut_seq += 1
        return self._dut_seq

    def _take(self, station):
        """`get`: the End Effector picks a DUT. Returns an error text for a situation that cannot happen on a real cell."""
        if self.holding is not None:
            return "get %d: the End Effector already holds DUT %d" % (station, self.holding)
        if station == 0:                                         # the input tray
            if self.input_left is not None:
                if self.input_left <= 0:
                    return "get 0: the input tray is empty"
                self.input_left -= 1
            self.holding = self._new_dut()
            return ""
        waiting = self.stations.get(station)
        if waiting:
            self.holding = waiting.pop(0)
            return ""
        error = "get %d: there is no DUT at station %d" % (station, station)
        if not self.strict:
            self.holding = self._new_dut()                        # lenient: a DUT that nobody put there
        return error

    def _leave(self, station):
        """`put`: the DUT on the End Effector is set down."""
        error = ""
        if self.holding is None:
            if self.strict:
                return "put %d: the End Effector holds no DUT" % station
            self.holding = self._new_dut()
            error = "put %d: the End Effector holds no DUT" % station
        self.stations.setdefault(station, []).append(self.holding)
        self.holding = None
        return error

    def dut_at(self, station):
        with self.lock:
            return bool(self.stations.get(station))

    # ---- dump ---------------------------------------------------------------------------------------- #
    def state(self):
        with self.lock:
            return {
                "program": {"selected": self.selected, "running": self.running, "held": self.held, "busy": self.busy,
                            "fault": self.fault, "alarm": self.alarm, "responding": self.responding,
                            "name": None if self.selected is None else "RSR%04d" % self.selected},
                "r": dict((i, self.r.get(i, 0)) for i in range(1, 11)),
                "uo": dict((i, self.uo_value(i)) for i in range(1, 21)),
                "uo_names": dict((i + 1, n) for i, n in enumerate(UO_NAMES)),
                "sdi": dict((i, self._sdi(i)) for i in range(1, 19)),
                "pos": list(self.pos), "executed": len(self.executed), "holding": self.holding,
                "stations": dict((k, len(v)) for k, v in sorted(self.stations.items()) if v),
                "input_left": self.input_left,
                "inject": {"fail_next": self.fail_next, "verify_fail": self.verify_fail,
                           "bad_stations": list(self.bad_stations)},
            }


class ComSim(object):
    """The part of the bridge that talks to the controller. The real bridge has a ComRobot with the same surface
    (FRRJIf, one COM thread); here it is the simulated controller."""

    def __init__(self, cfg):
        self.robot = SimRobot(cfg)
        self.connected = False
        self.host = ""

    def open(self, host):
        self.host = host
        self.robot.start()
        self.connected = True

    def close(self):
        self.connected = False

    def stop(self):
        self.connected = False
        self.robot.stop()

    # R[] / PR[] / position / I/O / alarm
    def r_get(self, i):
        return self.robot.r_get(i)

    def r_set(self, i, v):
        self.robot.r_set(i, v)

    def pr_get(self, group, idx):
        return self.robot.pr_get(group, idx)

    def pr_set(self, group, idx, pos):
        self.robot.pr_set(group, idx, pos)

    def curpos(self):
        return self.robot.curpos()

    def io_get(self, kind, index, count):
        return self.robot.io_get(kind, index, count)

    def io_set(self, kind, index, values):
        return self.robot.io_set(kind, index, values)

    def clear_alarm(self):
        return self.robot.clear_alarm()


# --------------------------------------------------------------------------- #
# the bridge
# --------------------------------------------------------------------------- #
class Bridge(object):
    def __init__(self, cfg, sim=True):
        if not sim:
            raise NotImplementedError("bridge_simple.py only simulates the robot: there is no FRRJIf layer in this file")
        merged = copy.deepcopy(DEFAULTS)
        merged.update(cfg or {})
        self.cfg = merged
        self.sim = True
        self.lock = threading.RLock()
        self.com = ComSim(merged)
        self.armed_by = None               # the client (Handler) that holds the arm
        self.busy = False
        self.op = None
        self.last_result = None
        self.message = ""
        self.clients = []
        self.cell = None                   # Cell (fixtures + scanner), set by Cell()
        self._quit = threading.Event()
        self._threads = [threading.Thread(target=self._watchdog, name="watchdog", daemon=True),
                         threading.Thread(target=self._status_loop, name="status", daemon=True)]
        if merged["auto_connect"]:
            self.com.open(merged["robot_host"])
        for t in self._threads:
            t.start()

    def stop(self):
        self._quit.set()
        for t in self._threads:
            t.join(1.0)
        self.com.stop()

    # ---- clients / events ------------------------------------------------------------------------ #
    def ip_allowed(self, ip):
        allow = self.cfg["allow"]
        return "*" in allow or ip in allow

    def add_client(self, cl):
        with self.lock:
            self.clients.append(cl)

    def remove_client(self, cl):
        with self.lock:
            if cl in self.clients:
                self.clients.remove(cl)
            if self.armed_by is cl:
                self._disarm("client disconnected")

    def _status_loop(self):
        while not self._quit.wait(float(self.cfg["status_s"])):
            event = {"event": "status", "data": self.snap()}
            with self.lock:
                clients = list(self.clients)
            for cl in clients:
                cl.send(event)

    def _watchdog(self):
        while not self._quit.wait(0.1):
            with self.lock:
                cl = self.armed_by
                if cl is not None and time.time() - cl.last_seen > float(self.cfg["watchdog_s"]):
                    self._disarm("watchdog: client silent for %.1fs" % float(self.cfg["watchdog_s"]))

    def _disarm(self, why):
        with self.lock:
            if self.armed_by is not None:
                log.info("disarmed: %s", why)
                self.message = "disarmed: %s" % why
            self.armed_by = None

    # ---- status ---------------------------------------------------------------------------------- #
    def snap(self):
        with self.lock:
            connected = self.com.connected
            r1 = r2 = r5 = None
            curpos = None
            prog = {}
            if connected:
                r1, r2, r5 = self.com.r_get(1), self.com.r_get(2), self.com.r_get(5)
                curpos = list(self.com.curpos()["xyzwpr"])
                st = self.com.robot.state()
                prog = {"program_running": bool(st["program"]["running"]), "program": st["program"]["name"],
                        "controller_fault": bool(st["program"]["fault"])}
            snap = {"connected": connected, "armed": self.armed_by is not None, "busy": self.busy,
                    "fault": r1 is not None and r1 < 0, "pending": r1 is not None and r1 > 0 and not self.busy,
                    "r1": r1, "r2": r2, "r5": r5, "op": self.op, "last_result": self.last_result, "curpos": curpos,
                    "message": self.message, "t": time.time()}
            snap.update(prog)                    # extra (simulation): UOP view of the controller
            return snap

    # ---- request dispatch ------------------------------------------------------------------------ #
    def handle(self, cl, cmd, args):
        """Runs one command for client `cl`; returns the data or raises Err."""
        if not isinstance(cmd, str) or not cmd or any(c not in "abcdefghijklmnopqrstuvwxyz_." for c in cmd):
            raise Err("UNKNOWN_CMD", "unknown command %r" % (cmd,))
        if not isinstance(args, dict):
            raise Err("BAD_REQUEST", "args must be an object")
        if self.cfg["token"] and not cl.authed and cmd != "hello":
            raise Err("NOT_AUTH", "send 'hello' with the token first")
        if cmd.startswith("motion."):
            op = cmd[len("motion."):]
            if op not in MOTION:
                raise Err("UNKNOWN_CMD", "unknown motion %r" % op)
            return self.motion(cl, op, args)
        fn = getattr(self, "cmd_" + cmd.replace(".", "_"), None)
        if fn is None:
            raise Err("UNKNOWN_CMD", "unknown command %r" % cmd)
        return fn(cl, args)

    def _need_connected(self):
        if not self.com.connected:
            raise Err("NOT_CONNECTED", "the robot is not connected: send 'robot.connect'")

    # ---- general commands ------------------------------------------------------------------------ #
    def cmd_hello(self, cl, a):
        if self.cfg["token"] and a.get("token") != self.cfg["token"]:
            raise Err("NOT_AUTH", "wrong token")
        cl.authed = True
        c = self.cfg
        return {"name": "bridge_simple (simulated)", "version": VERSION, "protocol": PROTOCOL, "mode": "sim",
                "robot_host": c["robot_host"],
                "limits": {"max_override": c["max_override"], "default_override": c["default_override"],
                           "max_rmove_mm": float(c["max_rmove_mm"]), "max_rmove_deg": float(c["max_rmove_deg"]),
                           "max_station": c["max_station"], "op_timeout_s": float(c["op_timeout_s"]),
                           "watchdog_s": float(c["watchdog_s"])},
                "state": self.snap()}

    def cmd_ping(self, cl, a):
        return {"t": time.time()}

    def cmd_status(self, cl, a):
        return self.snap()

    def cmd_robot_connect(self, cl, a):
        host = a.get("host") or self.cfg["robot_host"]
        if not isinstance(host, str):
            raise Err("BAD_REQUEST", "host must be a string")
        with self.lock:
            self.com.open(host)
            return {"connected": True, "host": host, "r1": self.com.r_get(1)}

    def cmd_robot_disconnect(self, cl, a):
        with self.lock:
            self.com.close()
            self._disarm("robot.disconnect")
            return {"connected": False}

    def cmd_arm(self, cl, a):
        with self.lock:
            self._need_connected()
            if self.com.r_get(1) < 0:
                raise Err("FAULT_LATCHED", "R[1] < 0: check the robot, then send 'fault.clear'")
            if self.armed_by is not None and self.armed_by is not cl:
                raise Err("FORBIDDEN", "another client holds the arm")
            self.armed_by = cl
            cl.last_seen = time.time()
            return {"armed": True}

    def cmd_disarm(self, cl, a):
        with self.lock:
            if self.armed_by is cl:
                self._disarm("client asked")
            return {"armed": False}

    # ---- registers --------------------------------------------------------------------------------- #
    def _register(self, a):
        i = a.get("index")
        if not _is_int(i):
            raise Err("BAD_REQUEST", "index must be an integer")
        (ilo, ihi), (rlo, rhi) = self.cfg["register_int"], self.cfg["register_real"]
        if ilo <= i <= ihi:
            return i, False
        if rlo <= i <= rhi:
            return i, True
        raise Err("BAD_REQUEST", "R[%d] is not registered (int %d..%d, real %d..%d)" % (i, ilo, ihi, rlo, rhi))

    def cmd_r_read(self, cl, a):
        with self.lock:
            self._need_connected()
            i, real = self._register(a)
            v = self.com.r_get(i)
            return {"index": i, "value": float(v) if real else int(v)}

    def cmd_r_write(self, cl, a):
        with self.lock:
            self._need_connected()
            i, real = self._register(a)
            if i in self.cfg["protected_r"]:
                raise Err("FORBIDDEN", "R[%d] is protected" % i)
            v = a.get("value")
            if not _is_num(v):
                raise Err("BAD_REQUEST", "value must be a finite number")
            if not real:
                if float(v) != int(v):
                    raise Err("BAD_REQUEST", "R[%d] is an integer register" % i)
                v = int(v)
            else:
                v = float(v)
            self.com.r_set(i, v)
            return {"index": i, "value": self.com.r_get(i)}

    # ---- position registers / position ------------------------------------------------------------- #
    def _target(self, t):
        """{"xyzwpr": [6 | 9 numbers], "config"?, "uf"?, "ut"?} -> normalised pose dict."""
        if not isinstance(t, dict):
            raise Err("BAD_REQUEST", "target must be an object")
        xyz = t.get("xyzwpr")
        if not isinstance(xyz, list) or len(xyz) not in (6, 9) or not all(_is_num(v) for v in xyz):
            raise Err("BAD_REQUEST", "xyzwpr must be 6 or 9 finite numbers")
        config = t.get("config", self.cfg["pose_config"])
        if not isinstance(config, list) or len(config) != 7 or not all(_is_int(v) for v in config):
            raise Err("BAD_REQUEST", "config must be 7 integers")
        uf, ut = t.get("uf", self.cfg["pose_uf"]), t.get("ut", self.cfg["pose_ut"])
        if not _is_int(uf) or not _is_int(ut):
            raise Err("BAD_REQUEST", "uf and ut must be integers")
        return {"xyzwpr": [float(v) for v in xyz], "config": list(config), "uf": uf, "ut": ut}

    def _pr_index(self, a):
        g, i = a.get("group"), a.get("index")
        if not _is_int(g) or not _is_int(i) or not 1 <= g <= 8 or not 1 <= i <= 100:
            raise Err("BAD_REQUEST", "group must be 1..8 and index 1..100")
        return g, i

    def cmd_pr_read(self, cl, a):
        with self.lock:
            self._need_connected()
            g, i = self._pr_index(a)
            return {"pos": self.com.pr_get(g, i)}

    def cmd_pr_write(self, cl, a):
        with self.lock:
            self._need_connected()
            g, i = self._pr_index(a)
            self.com.pr_set(g, i, self._target(a))
            return {"pos": self.com.pr_get(g, i)}

    def cmd_pos_read(self, cl, a):
        with self.lock:
            self._need_connected()
            return self.com.curpos()

    # ---- I/O --------------------------------------------------------------------------------------- #
    def _io_args(self, a, key_values):
        kind, index = a.get("kind"), a.get("index")
        if not isinstance(kind, str) or kind.upper() not in IO_SIZE:
            raise Err("BAD_REQUEST", "kind must be one of %s" % " ".join(sorted(IO_SIZE)))
        kind = kind.upper()
        if not _is_int(index) or index < 1:
            raise Err("BAD_REQUEST", "index must be an integer >= 1")
        count = a.get(key_values)
        return kind, index, count

    def cmd_io_read(self, cl, a):
        with self.lock:
            self._need_connected()
            kind, index, count = self._io_args(a, "count")
            count = 1 if count is None else count
            if not _is_int(count) or not 1 <= count <= 100:
                raise Err("BAD_REQUEST", "count must be 1..100")
            if index + count - 1 > IO_SIZE[kind]:
                raise Err("BAD_REQUEST", "%s[%d..%d] is out of range (max %d)" % (kind, index, index + count - 1, IO_SIZE[kind]))
            return {"kind": kind, "index": index, "values": self.com.io_get(kind, index, count)}

    def cmd_io_write(self, cl, a):
        with self.lock:
            self._need_connected()
            if self.armed_by is not cl:
                raise Err("NOT_ARMED", "send 'arm' before io.write")
            kind, index, values = self._io_args(a, "values")
            if kind not in self.cfg["io_write_kinds"]:
                raise Err("FORBIDDEN", "%s cannot be written (allowed: %s)" % (kind, ", ".join(self.cfg["io_write_kinds"])))
            if (not isinstance(values, list) or not 1 <= len(values) <= 100
                    or not all(_is_int(v) and v in (0, 1) for v in values)):
                raise Err("BAD_REQUEST", "values must be a list of 1..100 bits (0 / 1)")
            if index + len(values) - 1 > IO_SIZE[kind]:
                raise Err("BAD_REQUEST", "%s[%d..%d] is out of range (max %d)" % (kind, index, index + len(values) - 1, IO_SIZE[kind]))
            back = self.com.io_set(kind, index, values)
            if self.com.robot.verify_fail:
                back = [1 - b for b in back]                     # injected read-back mismatch
            return {"kind": kind, "index": index, "values": back}

    # ---- alarm / fault ---------------------------------------------------------------------------- #
    def cmd_alarm_clear(self, cl, a):
        with self.lock:
            self._need_connected()
            return {"cleared": bool(self.com.clear_alarm())}

    def cmd_fault_clear(self, cl, a):
        with self.lock:
            self._need_connected()
            r1 = self.com.r_get(1)
            if r1 > 0 and not a.get("force"):
                raise Err("BUSY", "R[1] = %d: the robot is executing a command" % r1)
            if r1 != 0:
                self.com.r_set(1, 0)
                self.message = "fault cleared"
            return {"r1": self.com.r_get(1)}

    # ---- motion ------------------------------------------------------------------------------------ #
    def _override(self, a):
        ov = a.get("override", self.cfg["default_override"])
        if not _is_int(ov):
            raise Err("BAD_REQUEST", "override must be an integer")
        if not 1 <= ov <= self.cfg["max_override"]:
            raise Err("LIMIT", "override must be 1..%d" % self.cfg["max_override"])
        return ov

    def _timeout(self, a):
        t = a.get("timeout_s", self.cfg["op_timeout_s"])
        if not _is_num(t):
            raise Err("BAD_REQUEST", "timeout_s must be a number")
        if not 1 <= t <= 600:
            raise Err("LIMIT", "timeout_s must be 1..600")
        return float(t)

    def _check_workspace(self, xyz):
        ws = self.cfg["workspace"]
        if not ws:
            return
        for axis, v in zip("xyz", xyz[:3]):
            if axis in ws and not ws[axis][0] <= v <= ws[axis][1]:
                raise Err("LIMIT", "%s = %.1f is outside the workspace %s" % (axis.upper(), v, ws[axis]))

    def motion(self, cl, op, a):
        code = MOTION[op]
        with self.lock:
            self._need_connected()
            if self.armed_by is not cl:
                raise Err("NOT_ARMED", "send 'arm' before motion commands")
            override = self._override(a)
            timeout_s = self._timeout(a)
            target = station = None
            if op in NEEDS_TARGET:
                target = self._target(a.get("target"))
                if op == "rmove":
                    off = target["xyzwpr"]
                    if math.sqrt(off[0] ** 2 + off[1] ** 2 + off[2] ** 2) > float(self.cfg["max_rmove_mm"]):
                        raise Err("LIMIT", "rmove distance is over %g mm" % self.cfg["max_rmove_mm"])
                    if any(abs(v) > float(self.cfg["max_rmove_deg"]) for v in off[3:6]):
                        raise Err("LIMIT", "rmove rotation is over %g deg" % self.cfg["max_rmove_deg"])
                else:
                    self._check_workspace(target["xyzwpr"])
            if op in NEEDS_STATION:
                station = a.get("station")
                if not _is_int(station):
                    raise Err("BAD_REQUEST", "station must be an integer")
                if not 0 <= station <= self.cfg["max_station"]:
                    raise Err("LIMIT", "station must be 0..%d" % self.cfg["max_station"])
            if self.busy:
                raise Err("BUSY", "another motion is running")
            self.busy, self.op, self.message = True, op, "running %s" % op
        t0 = time.time()
        try:
            result = self._motion_job(op, code, override, target, station, timeout_s, t0)
            with self.lock:
                self.last_result = {"op": op, "ok": True, "elapsed_s": result["elapsed_s"]}
                self.message = "%s done" % op
            return result
        except Err as ex:
            with self.lock:
                self.last_result = {"op": op, "ok": False, "error": ex.code}
                if ex.code in DISARM_CODES:
                    self._disarm("%s during %s" % (ex.code, op))
                self.message = "%s: %s" % (ex.code, ex.message)
            raise
        finally:
            with self.lock:
                self.busy, self.op = False, None

    def _write_check(self, label, write, read, equal):
        write()
        if not equal(read()):
            raise Err("VERIFY_FAILED", "%s read back different from what was written" % label)

    def _motion_job(self, op, code, override, target, station, timeout_s, t0):
        com = self.com
        try:
            r1 = com.r_get(1)
            if r1 > 0:
                raise Err("BUSY", "R[1] = %d: the robot is still executing a command" % r1)
            if r1 < 0:
                raise Err("FAULT_LATCHED", "R[1] = %d: send 'fault.clear' after checking the robot" % r1)
            bad = com.robot.verify_fail
            if target is not None:
                com.pr_set(1, 1, target)
                back = com.pr_get(1, 1)
                if bad or any(abs(a - b) > 0.01 for a, b in zip(back["xyzwpr"], target["xyzwpr"])):
                    raise Err("VERIFY_FAILED", "PR[1] read back different from what was written")
            if station is not None:
                com.r_set(2, station)
                if bad or com.r_get(2) != station:
                    raise Err("VERIFY_FAILED", "R[2] read back different from what was written")
            com.r_set(5, override)
            if bad or com.r_get(5) != override:
                raise Err("VERIFY_FAILED", "R[5] read back different from what was written")
            com.r_set(1, code)                         # from here on the robot owns the command
            poll = float(self.cfg["poll_s"])
            deadline = t0 + timeout_s
            while True:
                if not com.connected:
                    raise Err("NOT_CONNECTED", "the robot link was lost during %s" % op)
                r1 = com.r_get(1)
                if r1 == 0:
                    return {"op": op, "code": code, "elapsed_s": round(time.time() - t0, 3), "r1": 0,
                            "override": override}
                if r1 < 0:
                    raise Err("ROBOT_ERROR", "robot reported R[1]=%d during %s" % (r1, op))
                if time.time() >= deadline:
                    raise Err("TIMEOUT", "no answer from the robot within %.1fs during %s (R[1]=%d, it may still be "
                                         "running)" % (timeout_s, op, r1))
                time.sleep(poll)
        except Err:
            raise
        except Exception as ex:                          # a real bridge would see COM errors here
            raise Err("INTERNAL", "%s: %s" % (type(ex).__name__, ex))

    # ---- simulation-only commands ----------------------------------------------------------------- #
    def cmd_sim_state(self, cl, a):
        with self.lock:
            st = self.com.robot.state()
        if self.cell is not None:
            st["cell"] = self.cell.state()
        return st

    def _cell_item(self, what):
        if self.cell is None:
            raise Err("BAD_REQUEST", "this simulator has no fixtures / scanner (start it as a cell)")
        return what

    def cmd_sim_fixture(self, cl, a):
        """{"n": 1, "forced_results": ["NG", "PASS"], "pass_rate": 0.5, "test_time": 2, "error": true, "drop": true,
        "send": "<raw frame>"}  -> state of that fixture."""
        self._cell_item(None)
        n = a.get("n")
        if not _is_int(n) or n not in self.cell.fixtures:
            raise Err("BAD_REQUEST", "n must be one of %s" % sorted(self.cell.fixtures))
        return self.cell.fixtures[n].control(a)

    def cmd_sim_scanner(self, cl, a):
        """{"fail_next": 2, "no_read_rate": 0.1}  -> state of the barcode scanner."""
        self._cell_item(None)
        if self.cell.scanner is None:
            raise Err("BAD_REQUEST", "no scanner is simulated")
        return self.cell.scanner.control(a)

    def cmd_sim_set(self, cl, a):
        kind, index, values = self._io_args(a, "values")
        if kind == "UO":
            raise Err("BAD_REQUEST", "UO[] is derived from the controller state, it cannot be forced")
        if not isinstance(values, list) or not values or not all(_is_int(v) for v in values):
            raise Err("BAD_REQUEST", "values must be a list of integers")
        if index + len(values) - 1 > IO_SIZE[kind]:
            raise Err("BAD_REQUEST", "out of range")
        return {"kind": kind, "index": index, "values": self.com.io_set(kind, index, values)}

    def cmd_sim_inject(self, cl, a):
        robot = self.com.robot
        with robot.lock:
            if "fail_next" in a:
                if not _is_int(a["fail_next"]) or a["fail_next"] < 0:
                    raise Err("BAD_REQUEST", "fail_next must be an integer >= 0")
                robot.fail_next = a["fail_next"]
            if "verify_fail" in a:
                robot.verify_fail = bool(a["verify_fail"])
            if "responding" in a:
                robot.responding = bool(a["responding"])
            if "bad_stations" in a:
                if not isinstance(a["bad_stations"], list) or not all(_is_int(v) for v in a["bad_stations"]):
                    raise Err("BAD_REQUEST", "bad_stations must be a list of integers")
                robot.bad_stations = list(a["bad_stations"])
            return {"fail_next": robot.fail_next, "verify_fail": robot.verify_fail, "responding": robot.responding,
                    "bad_stations": list(robot.bad_stations)}

    def cmd_sim_reset(self, cl, a):
        with self.lock:
            self.com.robot.reset(bool(a.get("cold", False)))
            self._disarm("sim.reset")
            return self.com.robot.state()


# --------------------------------------------------------------------------- #
# the cell around the robot: fixtures (ATS programs) and the barcode scanner
# --------------------------------------------------------------------------- #
TERMINATOR = "_CEND"          # every ATS frame ends with it (NewRCS <-> ATS protocol, rcs2/ats/protocol.py)


def _frame(text):
    return (text + TERMINATOR).encode("utf-8")


class _Listener(object):
    """A small threaded TCP listener: calls `serve(conn, addr)` on a thread for every connection."""

    def __init__(self, name, host, port):
        self.name, self.host, self.port = name, host, port
        self._srv = None
        self._quit = threading.Event()
        self._thread = None
        self.conns = []
        self._clock = threading.Lock()

    def start(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            srv.bind((self.host, self.port))
        except OSError as ex:
            srv.close()
            raise OSError("%s: cannot listen on %s:%d (%s) - is another simulator or the real program running?"
                          % (self.name, self.host, self.port, ex))
        srv.listen(4)
        srv.settimeout(0.3)
        self.port = srv.getsockname()[1]
        self._srv = srv
        self._thread = threading.Thread(target=self._accept, name=self.name, daemon=True)
        self._thread.start()
        return self

    def stop(self):
        self._quit.set()
        self.drop_all()
        if self._srv is not None:
            self._srv.close()
        if self._thread is not None:
            self._thread.join(1.0)

    def drop_all(self):
        with self._clock:
            conns, self.conns = self.conns, []
        for c in conns:
            try:
                c.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                c.close()
            except OSError:
                pass

    def _accept(self):
        while not self._quit.is_set():
            try:
                conn, addr = self._srv.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.on_accept(conn)
            with self._clock:
                self.conns.append(conn)
            threading.Thread(target=self._run, args=(conn, addr), name=self.name + "-conn", daemon=True).start()

    def _run(self, conn, addr):
        try:
            self.serve(conn, addr)
        finally:
            with self._clock:
                if conn in self.conns:
                    self.conns.remove(conn)
            try:
                conn.close()
            except OSError:
                pass

    def on_accept(self, conn):
        pass

    def serve(self, conn, addr):
        raise NotImplementedError

    @property
    def connected(self):
        with self._clock:
            return bool(self.conns)


class SimFixture(_Listener):
    """The ATS program of one fixture. NewRCS connects to it, sends heartbeats and commands; it answers like the real one:

        on connect              TtoC_resultWaitdut
        CtoT_placeDUTOK         TtoC_startOK, then after `test_time` TtoC_resultPass | resultNG+item+value | resultRetest+sn
        B1=<SN>,                TtoC_readcodeOK              CtoT_placeBarcode  TtoC_BarcodePass+<SN>
        DUT_OUT                 TtoC_resultWaitdut           f_open / f_close   fix_open / fix_close   fixstatus  fix_*
    It also knows whether the robot really put a DUT into its station (`robot.dut_at`): a test without a DUT is logged,
    and in strict mode it is not started at all (NewRCS then runs into its test time-out, which exposes the bug).
    """

    def __init__(self, number, host, port, station, robot, test_time, pass_rate, retest_rate, ng_item, ng_value,
                 seed=None, strict=False):
        _Listener.__init__(self, "fixture-%d" % number, host, port)
        self.number, self.station, self.robot, self.strict = number, station, robot, strict
        self.test_time, self.pass_rate, self.retest_rate = test_time, pass_rate, retest_rate
        self.ng_item, self.ng_value = ng_item, ng_value
        self.forced_results = []
        self.fix_state = "fix_open"
        self.current_sn = ""
        self.testing = False
        self.tests = 0
        self.last_result = ""
        self.received = []
        self._rng = random.Random(None if seed is None else seed + number)
        self._wlock = threading.Lock()

    # ---- sending ----------------------------------------------------------------------------------- #
    def send(self, text, conn=None):
        with self._clock:
            targets = [conn] if conn is not None else list(self.conns)
        for c in targets:
            try:
                with self._wlock:
                    c.sendall(_frame(text))
            except OSError:
                pass
        if text.lower() != "aaa":
            log.info("[fixture %d] -> %s", self.number, text)

    def on_accept(self, conn):
        self.drop_all()                                    # a new NewRCS replaces the old connection

    def serve(self, conn, addr):
        conn.settimeout(0.5)
        buf = ""
        log.info("[fixture %d] NewRCS connected from %s", self.number, addr[0])
        self.send("TtoC_resultWaitdut", conn)
        while not self._quit.is_set():
            try:
                data = conn.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            if not data:
                break
            buf += data.decode("utf-8", "replace")
            while True:
                i = buf.find(TERMINATOR)
                if i < 0:
                    break
                frame, buf = buf[:i].strip(), buf[i + len(TERMINATOR):]
                if frame:
                    self._handle(frame, conn)
        log.info("[fixture %d] NewRCS disconnected", self.number)

    # ---- behaviour --------------------------------------------------------------------------------- #
    def _handle(self, frame, conn):
        low = frame.lower()
        if "aaa" in low:
            return                                          # heartbeat
        if low == "fixstatus":
            self.send(self.fix_state, conn)
            return
        self.received.append(frame)
        del self.received[:-30]
        log.info("[fixture %d] <- %s", self.number, frame)
        if "placedutok" in low:
            self._start_test(conn)
        elif low.startswith("b1="):
            self.current_sn = frame[3:].strip().rstrip(",").replace("Code0:", "")
            self.send("TtoC_readcodeOK", conn)
        elif "placebarcode" in low:
            self.send("TtoC_BarcodePass+%s" % (self.current_sn or "SN000000"), conn)
        elif "dut_out" in low:
            self.send("TtoC_resultWaitdut", conn)
        elif low == "f_open":
            self.fix_state = "fix_open"
            self.send("fix_open", conn)
        elif low == "f_close":
            self.fix_state = "fix_close"
            self.send("fix_close", conn)

    def _start_test(self, conn):
        has_dut = self.robot.dut_at(self.station)
        if not has_dut:
            log.warning("[fixture %d] CtoT_placeDUTOK but the robot put no DUT at station %d", self.number, self.station)
            if self.strict:
                return                                      # no answer: NewRCS ends in its test time-out
        if self.testing:
            self.send("TtoC_resultBusy", conn)
            return
        self.testing = True
        self.send("TtoC_startOK", conn)
        threading.Thread(target=self._run_test, name="test-%d" % self.number, daemon=True).start()

    def _next_result(self):
        if self.forced_results:
            return str(self.forced_results.pop(0)).upper()
        r = self._rng.random()
        if r < self.retest_rate:
            return "RETEST"
        return "PASS" if self._rng.random() < self.pass_rate else "NG"

    def result_frame(self, result):
        result = result.upper()
        if result == "PASS":
            return "TtoC_resultPass"
        if result == "RETEST":
            return "TtoC_resultRetest+%s" % (self.current_sn or "SN")
        if result == "FQC":
            return "TtoC_resultFQC"
        if result == "WARNING":
            return "TtoC_resultWarning+SIM_WARNING"
        return "TtoC_resultNG+%s+%s" % (self.ng_item, self.ng_value)

    def _run_test(self):
        end = time.time() + float(self.test_time)
        while time.time() < end and not self._quit.is_set():
            time.sleep(0.05)
        result = self._next_result()
        self.tests += 1
        self.last_result = result
        self.testing = False
        if not self._quit.is_set():
            self.send(self.result_frame(result))

    # ---- control from sim.fixture ------------------------------------------------------------------- #
    def control(self, a):
        if "forced_results" in a:
            res = a["forced_results"]
            if not isinstance(res, list) or not all(isinstance(v, str) for v in res):
                raise Err("BAD_REQUEST", "forced_results must be a list of PASS / NG / RETEST / FQC / WARNING")
            self.forced_results = list(res)
        for key in ("pass_rate", "retest_rate", "test_time"):
            if key in a:
                if not _is_num(a[key]) or a[key] < 0:
                    raise Err("BAD_REQUEST", "%s must be a number >= 0" % key)
                setattr(self, key, float(a[key]))
        if a.get("error"):
            self.send("fix_error")                         # the fixture reports a fault (alarm 9013)
        if a.get("send"):
            self.send(str(a["send"]))                      # any raw frame
        if a.get("drop"):
            self.drop_all()                                # the ATS program goes away (alarm 9012)
        return self.state()

    def state(self):
        return {"number": self.number, "port": self.port, "station": self.station, "connected": self.connected,
                "fixture": self.fix_state, "testing": self.testing, "tests": self.tests, "last_result": self.last_result,
                "dut_inside": self.robot.dut_at(self.station), "forced_results": list(self.forced_results),
                "pass_rate": self.pass_rate, "test_time": self.test_time, "received": list(self.received[-5:])}


class SimScanner(_Listener):
    """The Keyence barcode reader of the End Effector (SR-710 / SR-X100 protocol of rcs2/devices/scanner.py):
    'LON' -> the code + CR LF after `read_s` (or 'ERROR' = no read); 'LOFF' stops a reading in progress."""

    def __init__(self, host, port, read_s=0.15, no_read_rate=0.0, prefix="SIM", seed=None):
        _Listener.__init__(self, "scanner", host, port)
        self.read_s, self.no_read_rate, self.prefix = read_s, no_read_rate, prefix
        self.fail_next = 0
        self.reads = 0
        self.last_sn = ""
        self._count = 0
        self._rng = random.Random(seed)
        self._slock = threading.Lock()

    def next_sn(self):
        with self._slock:
            self._count += 1
            return "%s%0*d" % (self.prefix, max(1, 14 - len(self.prefix)), self._count)

    def serve(self, conn, addr):
        conn.settimeout(0.5)
        buf = ""
        cancel = threading.Event()
        log.info("[scanner] NewRCS connected from %s", addr[0])
        while not self._quit.is_set():
            try:
                data = conn.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            if not data:
                break
            buf += data.decode("ascii", "replace")
            while True:
                cut = [i for i in (buf.find("\r"), buf.find("\n")) if i >= 0]
                if not cut:
                    break
                cmd, buf = buf[:min(cut)].strip().upper(), buf[min(cut) + 1:]
                if cmd == "LON":
                    cancel.set()
                    cancel = threading.Event()
                    threading.Thread(target=self._read, args=(conn, cancel), daemon=True).start()
                elif cmd == "LOFF":
                    cancel.set()
                elif cmd:
                    self._send("ER,%s,01" % cmd, conn)
        cancel.set()

    def _send(self, text, conn):
        try:
            conn.sendall((text + "\r\n").encode("ascii", "replace"))
        except OSError:
            pass

    def _read(self, conn, cancel):
        if cancel.wait(self.read_s):
            return                                           # LOFF arrived: reading stopped, no answer
        self.reads += 1
        if self.fail_next > 0 or self._rng.random() < self.no_read_rate:
            self.fail_next = max(0, self.fail_next - 1)
            self._send("ERROR", conn)
            return
        self.last_sn = self.next_sn()
        log.info("[scanner] read %s", self.last_sn)
        self._send(self.last_sn, conn)

    def control(self, a):
        if "fail_next" in a:
            if not _is_int(a["fail_next"]) or a["fail_next"] < 0:
                raise Err("BAD_REQUEST", "fail_next must be an integer >= 0")
            self.fail_next = a["fail_next"]
        if "no_read_rate" in a:
            if not _is_num(a["no_read_rate"]) or not 0 <= a["no_read_rate"] <= 1:
                raise Err("BAD_REQUEST", "no_read_rate must be 0..1")
            self.no_read_rate = float(a["no_read_rate"])
        return self.state()

    def state(self):
        return {"port": self.port, "connected": self.connected, "reads": self.reads, "last_sn": self.last_sn,
                "fail_next": self.fail_next, "no_read_rate": self.no_read_rate}


class Cell(object):
    """Everything around the robot that NewRCS talks to: the fixtures' ATS programs and the barcode scanner.
    They share the simulated robot, so a fixture knows whether a DUT was really loaded into it."""

    def __init__(self, bridge, cfg, host="0.0.0.0"):
        robot = bridge.com.robot
        self.host = host
        self.fixtures = {}
        for key, f in sorted(cfg["sim_fixtures"].items(), key=lambda kv: int(kv[0])):
            n = int(key)
            self.fixtures[n] = SimFixture(
                n, host, int(f["port"]), int(f.get("station", n)), robot,
                float(f.get("test_time", cfg["sim_test_time_s"] + (n - 1) * cfg["sim_test_step_s"])),
                float(f.get("pass_rate", cfg["sim_pass_rate"])), float(cfg["sim_retest_rate"]),
                cfg["sim_ng_item"], cfg["sim_ng_value"], cfg["sim_seed"], bool(cfg["sim_strict_stations"]))
        sc = cfg.get("sim_scanner")
        self.scanner = None
        if sc:
            self.scanner = SimScanner(host, int(sc["port"]), float(sc.get("read_s", 0.15)),
                                      float(sc.get("no_read_rate", 0.0)), str(sc.get("prefix", "SIM")), cfg["sim_seed"])
        bridge.cell = self

    def listeners(self):
        return list(self.fixtures.values()) + ([self.scanner] if self.scanner is not None else [])

    def start(self):
        started = []
        try:
            for item in self.listeners():
                item.start()
                started.append(item)
        except OSError:
            for item in started:
                item.stop()
            raise
        return self

    def stop(self):
        for item in self.listeners():
            item.stop()

    def state(self):
        return {"fixtures": dict((n, f.state()) for n, f in sorted(self.fixtures.items())),
                "scanner": None if self.scanner is None else self.scanner.state()}


# --------------------------------------------------------------------------- #
# TCP server
# --------------------------------------------------------------------------- #
class Server(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True
    request_queue_size = 16
    bridge = None                      # set by the owner right after construction

    def handle_error(self, request, client_address):
        pass                           # a dropped connection is normal


class Handler(socketserver.StreamRequestHandler):
    """One client connection: one request per line. Motions run in their own thread so that the connection can
    answer pings (and BUSY) while the robot is moving; replies are matched by `id`."""

    def handle(self):
        bridge = self.server.bridge
        if not bridge.ip_allowed(self.client_address[0]):
            return                                           # silent close, as documented
        self.wlock = threading.Lock()
        self.last_seen = time.time()
        self.authed = not bridge.cfg["token"]
        bridge.add_client(self)
        try:
            while True:
                try:
                    line = self.rfile.readline(MAX_LINE + 1)
                except (OSError, ValueError):
                    break
                if not line:
                    break
                self.last_seen = time.time()
                if len(line) > MAX_LINE:
                    self.send({"id": None, "ok": False, "error": {"code": "BAD_REQUEST", "message": "line too long"}})
                    break
                try:
                    msg = json.loads(line.decode("utf-8"))
                    if not isinstance(msg, dict):
                        raise ValueError("not an object")
                except ValueError:
                    self.send({"id": None, "ok": False, "error": {"code": "BAD_REQUEST", "message": "invalid JSON"}})
                    continue
                cmd = msg.get("cmd")
                if isinstance(cmd, str) and cmd.startswith("motion."):
                    threading.Thread(target=self._serve, args=(msg,), daemon=True).start()
                else:
                    self._serve(msg)
        finally:
            bridge.remove_client(self)

    def _serve(self, msg):
        rid, cmd, args = msg.get("id"), msg.get("cmd"), msg.get("args")
        bridge = self.server.bridge
        try:
            data = bridge.handle(self, cmd, {} if args is None else args)
            reply = {"id": rid, "ok": True, "data": data}
        except Err as ex:
            reply = {"id": rid, "ok": False, "error": {"code": ex.code, "message": ex.message}}
        except Exception as ex:                                # a bug must not kill the connection
            log.exception("command %r failed", cmd)
            reply = {"id": rid, "ok": False, "error": {"code": "INTERNAL", "message": "%s: %s" % (type(ex).__name__, ex)}}
        if bridge.cfg.get("verbose"):
            log.info("%s -> %s", cmd, "ok" if reply["ok"] else reply["error"]["code"])
        self.send(reply)

    def send(self, obj):
        try:
            with self.wlock:
                self.wfile.write(encode(obj))
                self.wfile.flush()
        except (OSError, ValueError):
            pass


# --------------------------------------------------------------------------- #
# command line
# --------------------------------------------------------------------------- #
def build_parser():
    ap = argparse.ArgumentParser(
        description="Simulates the whole cell for NewRCS in ONE process: the robot bridge (no robot needed), the ATS program "
                    "of every fixture and the barcode scanner. Reads the ports from NewRCS's config/settings.json.")
    ap.add_argument("--settings", help="NewRCS settings.json to take the ports from (default: ../config/settings.json "
                                       "next to this file, when it exists)")
    ap.add_argument("--no-settings", action="store_true", help="do not read settings.json: use --fixtures / --*-port")
    ap.add_argument("--host", default=None, help="address to listen on (default 0.0.0.0 = every interface)")
    ap.add_argument("--port", type=int, default=None, help="bridge port (default: settings.json bridge.port, else %d)"
                    % DEFAULTS["listen_port"])
    ap.add_argument("--fixtures", type=int, default=None, help="number of fixtures to simulate (without settings.json: 4)")
    ap.add_argument("--fixture-port-base", type=int, default=8801, help="fixture n listens on base + n - 1 (default 8801)")
    ap.add_argument("--scanner-port", type=int, default=None, help="barcode scanner port (default 9004)")
    ap.add_argument("--no-scanner", action="store_true", help="do not simulate the barcode scanner")
    ap.add_argument("--test-time", type=float, help="seconds one test takes on fixture 1 (default %g; +%g per fixture)"
                    % (DEFAULTS["sim_test_time_s"], DEFAULTS["sim_test_step_s"]))
    ap.add_argument("--pass-rate", type=float, help="probability of PASS (default %g)" % DEFAULTS["sim_pass_rate"])
    ap.add_argument("--retest-rate", type=float, help="probability of RETEST")
    ap.add_argument("--delay", type=float, help="seconds one robot command takes (default %g)" % DEFAULTS["sim_delay_s"])
    ap.add_argument("--cold", action="store_true", help="cold controller: emergency stop, program not running, all UI = 0")
    ap.add_argument("--strict", action="store_true",
                    help="robot errors for impossible pick / place, and a fixture ignores a test start without a DUT")
    ap.add_argument("--seed", type=int, help="seed of the random results (repeatable runs)")
    ap.add_argument("--allow", action="append", help="allow only these client IPs (default: any)")
    ap.add_argument("--token", default=os.environ.get("RCS_BRIDGE_TOKEN", ""), help="bridge token (env RCS_BRIDGE_TOKEN)")
    ap.add_argument("--config", help="JSON file with extra bridge settings (see DEFAULTS)")
    ap.add_argument("--robot-host", help="accepted for compatibility with the real bridge; ignored")
    ap.add_argument("--sim", action="store_true", help="accepted for compatibility: this file is always a simulation")
    ap.add_argument("-v", "--verbose", action="store_true", help="log every command and frame")
    return ap


def load_newrcs_settings(path):
    """What the simulator needs from NewRCS's settings.json: bridge port, fixtures, scanner port."""
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    out = {"bridge_host": (data.get("bridge") or {}).get("host"), "bridge_port": (data.get("bridge") or {}).get("port"),
           "fixtures": {}, "scanner": None}
    for key, f in ((data.get("ats") or {}).get("fixtures") or {}).items():
        out["fixtures"][str(key)] = {"port": int(f["port"]), "station": int(f.get("robot_station", key)),
                                     "host": f.get("host", "")}
    sc = (data.get("end_effector") or {}).get("scanner")
    if sc and str(sc.get("type", "tcp")).lower() == "tcp":
        out["scanner"] = {"port": int(sc.get("port", 9004)), "host": sc.get("host", "")}
    return out


def local_addresses():
    addrs = set(["127.0.0.1", "0.0.0.0", "localhost"])
    try:
        addrs.update(socket.gethostbyname_ex(socket.gethostname())[2])
    except OSError:
        pass
    return addrs


def build_config(args, newrcs=None):
    cfg = copy.deepcopy(DEFAULTS)
    cfg["listen_host"] = "0.0.0.0"
    cfg["allow"] = ["*"]
    if args.config:
        with open(args.config, "r", encoding="utf-8") as fh:
            cfg.update(json.load(fh))
    if newrcs and newrcs.get("bridge_port"):
        cfg["listen_port"] = int(newrcs["bridge_port"])
    if args.host:
        cfg["listen_host"] = args.host
    if args.port:
        cfg["listen_port"] = args.port
    if args.allow:
        cfg["allow"] = list(args.allow)
    if args.token:
        cfg["token"] = args.token
    # fixtures: from settings.json, or --fixtures N, or 4
    fixtures = {}
    if newrcs and args.fixtures is None:
        fixtures = dict((k, {"port": v["port"], "station": v["station"]}) for k, v in newrcs["fixtures"].items())
    else:
        for n in range(1, (4 if args.fixtures is None else args.fixtures) + 1):
            fixtures[str(n)] = {"port": args.fixture_port_base + n - 1, "station": n}
    cfg["sim_fixtures"] = fixtures
    if args.no_scanner:
        cfg["sim_scanner"] = None
    elif cfg["sim_scanner"] is not None:
        port = args.scanner_port or (newrcs["scanner"]["port"] if newrcs and newrcs.get("scanner") else None)
        cfg["sim_scanner"] = dict(cfg["sim_scanner"], port=port or cfg["sim_scanner"]["port"])
    for arg, key in (("test_time", "sim_test_time_s"), ("pass_rate", "sim_pass_rate"), ("retest_rate", "sim_retest_rate"),
                     ("delay", "sim_delay_s"), ("seed", "sim_seed")):
        if getattr(args, arg) is not None:
            cfg[key] = getattr(args, arg)
    cfg["sim_cold"] = bool(args.cold) or cfg["sim_cold"]
    cfg["sim_strict_stations"] = bool(args.strict) or cfg["sim_strict_stations"]
    cfg["verbose"] = bool(args.verbose)
    return cfg


def config_warnings(cfg, newrcs):
    """Settings of NewRCS that point somewhere else than this simulator (NewRCS would never reach it), one line per host."""
    if not newrcs:
        return []
    here = local_addresses()
    by_host = {}
    if newrcs.get("bridge_host"):
        by_host.setdefault(newrcs["bridge_host"], []).append("bridge")
    fixtures = {}
    for n, f in sorted(newrcs["fixtures"].items(), key=lambda kv: int(kv[0])):
        if f["host"]:
            fixtures.setdefault(f["host"], []).append(n)
    for host, numbers in fixtures.items():
        by_host.setdefault(host, []).append("fixtures " + ", ".join(numbers))
    sc = newrcs.get("scanner")
    if sc and sc["host"]:
        by_host.setdefault(sc["host"], []).append("scanner")
    return ["%s is not an address of this PC but settings.json uses it for: %s"
            % (host, "; ".join(what)) for host, what in sorted(by_host.items()) if host not in here]


def main(argv=None):
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(asctime)s %(levelname)-7s %(message)s")
    newrcs, path = None, args.settings
    if not args.no_settings:
        path = path or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config", "settings.json")
        if os.path.exists(path):
            try:
                newrcs = load_newrcs_settings(path)
            except (OSError, ValueError, KeyError) as ex:
                print("cannot use %s (%s): continuing with the command line / defaults" % (path, ex))
        elif args.settings:
            print("settings file not found: %s" % args.settings)
            return 2
    cfg = build_config(args, newrcs)
    bridge = Bridge(cfg, sim=True)
    cell = Cell(bridge, cfg, cfg["listen_host"])
    server = None
    try:
        cell.start()
        server = Server((cfg["listen_host"], cfg["listen_port"]), Handler)
    except OSError as ex:
        cell.stop()
        bridge.stop()
        print("cannot start: %s" % ex)
        return 1
    server.bridge = bridge
    print("=" * 78)
    print("NewRCS cell simulator %s - NO robot, NO fixtures needed" % VERSION)
    print("  source of ports : %s" % (os.path.abspath(path) if newrcs else "command line / defaults"))
    print("  robot bridge    : %s:%d   program %s" % (cfg["listen_host"], cfg["listen_port"],
                                                     "RSR0001 NOT running (cold)" if cfg["sim_cold"] else "RSR0001 running"))
    for n, f in sorted(cell.fixtures.items()):
        print("  fixture %-2d      : port %d   robot station %d   test %.1fs" % (n, f.port, f.station, f.test_time))
    if cell.scanner is not None:
        print("  barcode scanner : port %d" % cell.scanner.port)
    print("  clients allowed : %s%s" % (",".join(cfg["allow"]), "   (token required)" if cfg["token"] else ""))
    for w in config_warnings(cfg, newrcs):
        print("  WARNING         : %s" % w)
        print("                    -> NewRCS cannot reach the simulator there: give this PC that address, or change settings.json")
    print("Ctrl+C to stop.")
    print("=" * 78)
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("stopping")
    finally:
        cell.stop()
        bridge.stop()
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
