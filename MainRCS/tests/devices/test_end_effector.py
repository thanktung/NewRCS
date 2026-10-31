"""End Effector: 8 suction heads (cylinder + vacuum + pressure sensor), scanner, IL-1000 laser - tools, steps, engine."""
import unittest

from tests.support import bridge as helpers
from rcs2.config import load_settings
from rcs2.core import engine as E
from rcs2.core import sequence as S
from rcs2.devices import end_effector as EEM
from rcs2.devices import heads as H
from rcs2.devices import laser as L

from tests.support.engine import POINTS, SEQ, EngineCase, FakeRobot, wait_until

HEADS = 8


def heads_cfg(**over):
    cfg = {"enabled": True, "cylinder_s": 0.01, "vacuum_s": 0.01, "pressure_timeout_s": 0.3, "cylinder_timeout_s": 0.3,
           "units": [{"vacuum": "RDO[%d]" % n, "cylinder": "RDO[%d]" % (8 + n), "pressure": "RDI[%d]" % n}
                     for n in range(1, HEADS + 1)]}
    cfg.update(over)
    return cfg


class FakeIo:
    """Bridge io.read / io.write on a dict. Sensors follow the outputs:
         pressure RDI[n] = 1 when valve RDO[n] is on AND head n has a product (`products`)
         cylinder sensors RDI[20+n] (down) / RDI[30+n] (up) follow RDO[8+n] unless head n is in `stuck`.
         `laser` = {ref: value} inputs of the laser judgement (RDI[60] = GO, RDI[61] = HIGH, RDI[62] = LOW)."""

    def __init__(self, products=range(1, HEADS + 1)):
        self.bits = {}
        self.products = set(products)
        self.stuck = set()
        self.writes, self.reads = [], []
        self.fail_write = False
        self.wrong_readback = False
        self.pressure_after_reads = 0           # pressure appears only after this many reads (slow vacuum)
        self._reads_done = 0

    def _sensors(self):
        self._reads_done += 1
        for n in range(1, HEADS + 1):
            on = self.bits.get(("RDO", n), 0) == 1
            ok = on and n in self.products and self._reads_done > self.pressure_after_reads
            self.bits[("RDI", n)] = 1 if ok else 0
            down = self.bits.get(("RDO", 8 + n), 0) == 1
            moving_ok = n not in self.stuck
            self.bits[("RDI", 20 + n)] = 1 if (down and moving_ok) else 0
            self.bits[("RDI", 30 + n)] = 1 if (not down and moving_ok) else 0

    def io_write(self, kind, index, values):
        if self.fail_write:
            raise RuntimeError("NOT_ARMED: io.write requires 'arm'")
        self.writes.append((kind, index, list(values)))
        for i, v in enumerate(values):
            self.bits[(kind, index + i)] = int(v)
        back = [self.bits[(kind, index + i)] for i in range(len(values))]
        return [1 - b for b in back] if self.wrong_readback else back

    def io_read(self, kind, index, count):
        self._sensors()
        self.reads.append((kind, index, count))
        return [self.bits.get((kind, index + i), 0) for i in range(count)]


def make_heads(io=None, **over):
    io = io or FakeIo()
    bank = H.HeadBank.from_config(heads_cfg(**over), io)
    bank.sleep = lambda s: None
    return bank, io


class ParseTests(unittest.TestCase):
    def test_io_references(self):
        self.assertEqual(H.parse_io("RDO[12]"), ("RDO", 12))
        self.assertEqual(H.parse_io(" sdi [ 3 ] "), ("SDI", 3))
        for bad in ("RDO", "RDO[0]", "XYZ[1]", "RDO[a]", "[1]", 5, "RDO[1"):
            with self.assertRaises(ValueError, msg=str(bad)):
                H.parse_io(bad)

    def test_bad_config_is_a_head_error(self):
        for bad in ({"units": []}, {"units": [{"cylinder": "RDO[1]"}]}, {"units": [{"vacuum": "nonsense"}]}, {},
                    {"heads": [{"vacuum": "RDO[1]"}]}):                           # "heads" was the pre End Effector key
            with self.assertRaises(H.HeadError):
                H.HeadBank.from_config(bad, FakeIo())
        self.assertEqual(H.HeadBank.from_config(heads_cfg(), FakeIo()).count, 8)


class ActionTests(unittest.TestCase):
    def test_vacuum_all_is_one_contiguous_write_and_waits_for_the_vacuum(self):
        bank, io = make_heads()
        slept = []
        bank.sleep = slept.append
        bank.vacuum_set(True)
        self.assertEqual(io.writes, [("RDO", 1, [1] * 8)])
        self.assertEqual(slept, [0.01])
        bank.vacuum_set(False)
        self.assertEqual(io.writes[-1], ("RDO", 1, [0] * 8))
        self.assertEqual(slept, [0.01])                                    # no waiting when switching off

    def test_head_selection_groups_runs(self):
        bank, io = make_heads()
        bank.vacuum_set(True, [2, 3])
        self.assertEqual(io.writes, [("RDO", 2, [1, 1])])
        io.writes.clear()
        bank.vacuum_set(True, [1, 3, 4, 8])
        self.assertEqual(io.writes, [("RDO", 1, [1]), ("RDO", 3, [1, 1]), ("RDO", 8, [1])])
        for bad in ([], [0], [9], ["1"], [True], 3, "some"):
            with self.assertRaises(H.HeadError, msg=str(bad)):
                bank.vacuum_set(True, bad)

    def test_cylinder_levels_and_inverted_logic(self):
        bank, io = make_heads()
        bank.cylinder_set(True)
        self.assertEqual(io.writes[-1], ("RDO", 9, [1] * 8))
        bank.cylinder_set(False, [1, 2])
        self.assertEqual(io.writes[-1], ("RDO", 9, [0, 0]))
        bank, io = make_heads(cylinder_down=0)                              # valve wired the other way round
        bank.cylinder_set(True, [1])
        self.assertEqual(io.writes[-1], ("RDO", 9, [0]))

    def test_cylinder_waits_for_its_end_position_sensors(self):
        cfg = heads_cfg()
        for n, h in enumerate(cfg["units"], 1):
            h["cyl_down"], h["cyl_up"] = "RDI[%d]" % (20 + n), "RDI[%d]" % (30 + n)
        io = FakeIo()
        bank = H.HeadBank.from_config(cfg, io)
        bank.sleep = lambda s: None
        bank.cylinder_set(True)                                              # all sensors answer -> fine
        io.stuck = {3}
        with self.assertRaises(H.HeadError) as cm:
            bank.cylinder_set(False)
        self.assertIn("đầu 3", str(cm.exception))
        self.assertIn("lên", str(cm.exception))

    def test_write_problems_are_reported(self):
        bank, io = make_heads()
        io.fail_write = True
        with self.assertRaises(H.HeadError) as cm:
            bank.vacuum_set(True)
        self.assertIn("NOT_ARMED", str(cm.exception))
        io.fail_write, io.wrong_readback = False, True
        with self.assertRaises(H.HeadError) as cm:
            bank.vacuum_set(True)
        self.assertIn("đọc lại", str(cm.exception))

    def test_disabled_heads_refuse_everything(self):
        bank, io = make_heads(enabled=False)
        for call in (lambda: bank.vacuum_set(True), lambda: bank.cylinder_set(True), lambda: bank.pressure(),
                     lambda: bank.check(True), lambda: bank.status()):
            with self.assertRaises(H.HeadError) as cm:
                call()
            self.assertIn("enabled", str(cm.exception))
        self.assertEqual(io.writes, [])


class PressureTests(unittest.TestCase):
    def test_pressure_and_check_hold(self):
        bank, io = make_heads(io=FakeIo(products=[1, 2, 3, 4, 5, 6, 7, 8]))
        bank.vacuum_set(True)
        self.assertEqual(bank.pressure(), {n: True for n in range(1, 9)})
        bank.check(True)                                                     # no exception

    def test_check_names_the_heads_that_do_not_hold(self):
        bank, io = make_heads(io=FakeIo(products=[1, 3, 4, 6, 7, 8]))
        bank.vacuum_set(True)
        with self.assertRaises(H.HeadError) as cm:
            bank.check(True, timeout_s=0.1)
        self.assertIn("đầu 2, 5 không hút được", str(cm.exception))
        bank.check(True, [1, 3])                                             # only the heads that matter
        self.assertEqual(bank.pressure([2, 3]), {2: False, 3: True})

    def test_slow_vacuum_is_waited_for(self):
        io = FakeIo()
        io.pressure_after_reads = 4
        bank, _ = make_heads(io=io)
        bank.vacuum_set(True)
        bank.check(True, timeout_s=1.0)                                      # appears after a few polls

    def test_release_check(self):
        bank, io = make_heads()
        bank.vacuum_set(True)
        bank.vacuum_set(False)
        bank.check(False)                                                    # released
        io.products.add(4)
        io.bits[("RDO", 4)] = 1                                              # head 4 still sucking
        with self.assertRaises(H.HeadError) as cm:
            bank.check(False, timeout_s=0.1)
        self.assertIn("đầu 4 chưa nhả", str(cm.exception))

    def test_head_without_sensor(self):
        cfg = heads_cfg()
        del cfg["units"][1]["pressure"]
        bank = H.HeadBank.from_config(cfg, FakeIo())
        bank.sleep = lambda s: None
        bank.vacuum_set(True)
        self.assertEqual(bank.pressure([1, 2]), {1: True, 2: None})
        bank.check(True)                                                     # head 2 is simply not checked
        with self.assertRaises(H.HeadError):
            bank.check(True, [2])

    def test_status_for_the_manual_window(self):
        bank, io = make_heads(io=FakeIo(products=[2]))
        bank.vacuum_set(True, [1, 2])
        bank.cylinder_set(True, [2])
        rows = {r["n"]: r for r in bank.status()}
        self.assertEqual(rows[1], {"n": 1, "vacuum": True, "cylinder_down": False, "hold": False})
        self.assertEqual(rows[2], {"n": 2, "vacuum": True, "cylinder_down": True, "hold": True})
        self.assertEqual(rows[3]["vacuum"], False)


class LaserTests(unittest.TestCase):
    CFG = {"enabled": True, "model": "IL-1000", "ok": "RDI[60]", "high": "RDI[61]", "low": "RDI[62]", "timeout_s": 0.1}

    def laser(self, **bits):
        io = FakeIo()
        for ref, v in bits.items():
            io.bits[("RDI", int(ref[1:]))] = v
        io._sensors = lambda: None                     # the laser inputs are set by the test, not by the heads
        laser = L.Laser.from_config(self.CFG, io)
        laser.sleep = lambda s: None
        return laser

    def test_go_passes(self):
        self.assertEqual(self.laser(i60=1).check(), {"ok": True, "high": False, "low": False})

    def test_high_and_low_are_named(self):
        for bits, word in (({"i60": 0, "i61": 1}, "HIGH"), ({"i60": 0, "i62": 1}, "LOW"), ({"i60": 0}, "không đạt")):
            with self.assertRaises(L.LaserError) as cm:
                self.laser(**bits).check()
            self.assertIn(word, str(cm.exception))

    def test_active_low_and_optional_inputs(self):
        io = FakeIo()
        laser = L.Laser.from_config({"ok": "RDI[60]", "active": 0}, io)
        io._sensors = lambda: None
        self.assertEqual(laser.status(), {"ok": True, "high": None, "low": None})     # input reads 0 = active

    def test_disabled_and_bad_config(self):
        io = FakeIo()
        laser = L.Laser.from_config(dict(self.CFG, enabled=False), io)
        with self.assertRaises(L.LaserError) as cm:
            laser.check()
        self.assertIn("enabled", str(cm.exception))
        for bad in ({}, {"ok": "nonsense"}):
            with self.assertRaises(L.LaserError):
                L.Laser.from_config(bad, io)


class EndEffectorTests(unittest.TestCase):
    def test_built_from_the_shipped_settings(self):
        import os
        for name in ("settings.json", "settings.example.json"):
            cfg = load_settings(os.path.join(helpers.ROOT, "config", name))
            ee = EEM.build_end_effector(cfg, FakeIo())
            self.assertEqual(ee.capabilities(), {"heads": 8, "scanner": True, "laser": True}, name)
            self.assertIs(ee.tool("heads"), ee.heads)
            with self.assertRaises(KeyError):
                ee.tool("hand")

    def test_one_end_effector_with_optional_tools(self):
        ee = EEM.build_end_effector({}, FakeIo())
        self.assertEqual(ee.capabilities(), {"heads": 0, "scanner": False, "laser": False})
        ee = EEM.build_end_effector({"end_effector": {"heads": heads_cfg()}}, FakeIo())
        self.assertEqual(ee.capabilities(), {"heads": 8, "scanner": False, "laser": False})
        self.assertIsNone(ee.tool("scanner"))

    def test_bad_tool_config_is_reported_by_its_own_error(self):
        with self.assertRaises(H.HeadError):
            EEM.build_end_effector({"end_effector": {"heads": {"units": []}}}, FakeIo())
        with self.assertRaises(EEM.ScanError):
            EEM.build_end_effector({"end_effector": {"scanner": {"type": "usb"}}}, FakeIo())
        with self.assertRaises(L.LaserError):
            EEM.build_end_effector({"end_effector": {"laser": {"enabled": True}}}, FakeIo())

    def test_the_old_hands_and_scanners_sections_are_refused(self):
        import json
        import tempfile
        import os
        for key in ("hands", "scanners"):
            with tempfile.TemporaryDirectory() as d:
                path = os.path.join(d, "settings.json")
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump({key: {"tay1": {}}}, fh)
                with self.assertRaises(ValueError) as cm:
                    load_settings(path)
                self.assertIn("end_effector", str(cm.exception))


CAPS = {"heads": 8, "scanner": True, "laser": True}


class SequenceStepTests(unittest.TestCase):
    PICK = [{"ee": "heads", "cylinder": "down"}, {"ee": "heads", "vacuum": "on", "heads": [1, 2]},
            {"ee": "heads", "cylinder": "up", "heads": "all"},
            {"ee": "heads", "check": "hold", "heads": [1, 2], "timeout_s": 0.5},
            {"ee": "laser", "check": "ok", "timeout_s": 0.5},
            {"ee": "heads", "vacuum": "off"}, {"ee": "heads", "check": "release"}]

    def test_validation(self):
        S.validate({"s": self.PICK}, {}, ee=CAPS)
        S.validate({"s": self.PICK}, {})                                     # tools not checked
        bad_steps = ({"ee": "heads"}, {"ee": "heads", "vacuum": "maybe"},
                     {"ee": "heads", "vacuum": "on", "cylinder": "up"}, {"ee": "heads", "vacuum": "on", "heads": [9]},
                     {"ee": "heads", "vacuum": "on", "heads": []}, {"ee": "heads", "check": "hold", "timeout_s": 0},
                     {"ee": "", "vacuum": "on"}, {"ee": "heads", "vacuum": "on", "robot": "move"},
                     {"ee": "laser"}, {"ee": "laser", "check": "flat"}, {"ee": "laser", "check": "ok", "timeout_s": 99},
                     {"hand": "tay1", "vacuum": "on"}, {"scan": "tay1"})     # the pre End Effector steps are refused
        for step in bad_steps:
            with self.assertRaises(S.SequenceError, msg=str(step)):
                S.validate({"s": [step]}, {}, ee=CAPS)

    def test_a_tool_the_end_effector_does_not_carry_is_refused(self):
        for step, caps in (({"ee": "heads", "vacuum": "on"}, {"heads": 0, "scanner": True, "laser": True}),
                           ({"ee": "laser", "check": "ok"}, {"heads": 8, "scanner": True, "laser": False}),
                           ({"ee": "scanner"}, {"heads": 8, "scanner": False, "laser": True})):
            with self.assertRaises(S.SequenceError) as cm:
                S.validate({"s": [step]}, {}, ee=caps)
            self.assertIn("has no", str(cm.exception))

    def test_runner_drives_the_end_effector(self):
        bank, io = make_heads()
        io.products = set(range(1, 9))
        io.bits[("RDI", 60)] = 1
        laser = L.Laser.from_config(LaserTests.CFG, io)
        laser.sleep = lambda s: None
        ee = EEM.EndEffector(bank, None, laser)
        S.SequenceRunner(object(), {}, {}, ee=ee).run("pick", self.PICK, {"fixture": 1})
        self.assertEqual(io.writes[0], ("RDO", 9, [1] * 8))                  # cylinders down
        self.assertIn(("RDO", 1, [1, 1]), io.writes)                         # vacuum on heads 1 and 2
        self.assertEqual(io.writes[-1], ("RDO", 1, [0] * 8))                 # vacuum off
        with self.assertRaises(S.SequenceError):
            S.SequenceRunner(object(), {}, {}).run("x", [{"ee": "heads", "vacuum": "on"}], {})


SEQ_EE = dict(SEQ)
SEQ_EE["load"] = [{"ee": "heads", "cylinder": "down"}, {"ee": "heads", "vacuum": "on"},
                  {"ee": "heads", "cylinder": "up"}, {"ee": "heads", "check": "hold", "timeout_s": 0.2},
                  {"ee": "laser", "check": "ok", "timeout_s": 0.2},
                  {"robot": "get", "station": 0}, {"robot": "put", "station": "{robot_station}"}]


class EngineEndEffectorTests(EngineCase):
    fixtures = 1
    products = range(1, 9)
    laser_go = 1

    def setUp(self):
        super().setUp()
        self.eng.shutdown()
        self.io = FakeIo(self.products)
        self.io.bits[("RDI", 60)] = self.laser_go
        bank = H.HeadBank.from_config(heads_cfg(), self.io)
        bank.sleep = lambda s: None
        laser = L.Laser.from_config(LaserTests.CFG, self.io)
        laser.sleep = lambda s: None
        self.ee = EEM.EndEffector(bank, None, laser)
        self.robot = FakeRobot()
        self.eng = E.Engine(self.cfg, self.robot, self.ats, self.sink, self.errors, SEQ_EE, POINTS, ee=self.ee)
        self.eng.start()
        self.eng.on_ats_connection(1, True)
        self.eng.set_enabled(1, True)

    def test_all_heads_hold_and_the_laser_is_go_then_the_robot_continues(self):
        self.start_and_ready(1)
        wait_until(lambda: self.fx(1)["state"] == E.TESTING, what="TESTING")
        self.assertEqual(self.robot.calls[:2], [("get", 0), ("put", 1)])

    def test_engine_refuses_a_sequence_that_needs_a_missing_tool_at_start_up(self):
        with self.assertRaises(S.SequenceError):
            E.Engine(self.cfg, self.robot, self.ats, self.sink, self.errors, SEQ_EE, POINTS,
                     ee=EEM.EndEffector(self.ee.heads, None, None))              # no laser


class EngineHeadFailureTests(EngineEndEffectorTests):
    products = [1, 2, 3, 4, 6, 7, 8]                    # head 5 never gets a product

    def test_all_heads_hold_and_the_laser_is_go_then_the_robot_continues(self):
        self.start_and_ready(1)
        wait_until(lambda: self.eng.snapshot()["run_state"] == E.RUN_FAULT, what="FAULT")
        snap = self.eng.snapshot()
        self.assertTrue(any(a["code"] == "9203" for a in snap["alarms"]), snap["alarms"])
        self.assertFalse(any(a["code"] == "9201" for a in snap["alarms"]))
        self.assertIn("đầu 5 không hút được", snap["fault_text"])
        self.assertEqual(self.robot.calls, [])                              # the robot did not move on with a bad pick

    def test_engine_refuses_a_sequence_that_needs_a_missing_tool_at_start_up(self):
        pass


class EngineLaserFailureTests(EngineEndEffectorTests):
    laser_go = 0

    def test_all_heads_hold_and_the_laser_is_go_then_the_robot_continues(self):
        self.start_and_ready(1)
        wait_until(lambda: self.eng.snapshot()["run_state"] == E.RUN_FAULT, what="FAULT")
        snap = self.eng.snapshot()
        self.assertTrue(any(a["code"] == "9204" for a in snap["alarms"]), snap["alarms"])
        self.assertEqual(self.robot.calls, [])

    def test_engine_refuses_a_sequence_that_needs_a_missing_tool_at_start_up(self):
        pass


class CoilIo:
    """Bridge I/O of double coil valves. The valve keeps the position of the coil that was energised last (a bistable valve), the end sensors
    show that position (RDI[40+n] down, RDI[50+n] up), pressure RDI[n] follows the vacuum RDO[n]. `active` = level that energises a coil,
    `stuck` = heads whose cylinder never moves."""

    def __init__(self, active=1):
        self.active, self.bits, self.writes, self.stuck = active, {}, [], set()
        self.position = {n: "up" for n in range(1, HEADS + 1)}
        for n in range(1, HEADS + 1):
            self.bits[("RDO", 8 + n)] = self.bits[("RDO", 16 + n)] = 1 - active          # both coils at rest

    def io_write(self, kind, index, values):
        self.writes.append((kind, index, list(values)))
        for i, v in enumerate(values):
            self.bits[(kind, index + i)] = int(v)
        for n in range(1, HEADS + 1):
            if n in self.stuck:
                continue
            if self.bits[("RDO", 8 + n)] == self.active:
                self.position[n] = "down"
            if self.bits[("RDO", 16 + n)] == self.active:
                self.position[n] = "up"
        return [self.bits[(kind, index + i)] for i in range(len(values))]

    def io_read(self, kind, index, count):
        for n in range(1, HEADS + 1):
            self.bits[("RDI", n)] = self.bits.get(("RDO", n), 0)
            self.bits[("RDI", 40 + n)] = 1 if self.position[n] == "down" else 0
            self.bits[("RDI", 50 + n)] = 1 if self.position[n] == "up" else 0
        return [self.bits.get((kind, index + i), 0) for i in range(count)]


def coil_cfg(**over):
    cfg = {"enabled": True, "cylinder_s": 0.0, "vacuum_s": 0.0, "pressure_timeout_s": 0.2, "cylinder_timeout_s": 0.2,
           "units": [{"vacuum": "RDO[%d]" % n, "coil_down": "RDO[%d]" % (8 + n), "coil_up": "RDO[%d]" % (16 + n),
                      "cyl_down": "RDI[%d]" % (40 + n), "cyl_up": "RDI[%d]" % (50 + n), "pressure": "RDI[%d]" % n}
                     for n in range(1, HEADS + 1)]}
    cfg.update(over)
    return cfg


class DoubleCoilTests(unittest.TestCase):
    def bank(self, active=1, **over):
        io = CoilIo(active)
        bank = H.HeadBank.from_config(coil_cfg(**over), io)
        bank.sleep = lambda sec: None
        return bank, io

    def test_down_energises_the_down_coil_and_releases_the_other_one_first(self):
        bank, io = self.bank()
        bank.cylinder_set(True, [3])
        self.assertEqual(io.writes[0], ("RDO", 19, [0]))                         # coil up of head 3 off FIRST
        self.assertEqual(io.writes[1], ("RDO", 11, [1]))                         # then coil down on
        self.assertEqual((io.bits[("RDO", 11)], io.bits[("RDO", 19)]), (1, 0))
        bank.cylinder_set(False, [3])
        self.assertEqual(io.writes[2], ("RDO", 11, [0]))
        self.assertEqual(io.writes[3], ("RDO", 19, [1]))
        self.assertEqual((io.bits[("RDO", 11)], io.bits[("RDO", 19)]), (0, 1))

    def test_both_coils_are_never_on_together(self):
        bank, io = self.bank()
        state = {}
        original = io.io_write

        def watch(kind, index, values):
            out = original(kind, index, values)
            for n in range(1, HEADS + 1):
                state.setdefault(n, []).append((io.bits.get(("RDO", 8 + n), 0), io.bits.get(("RDO", 16 + n), 0)))
            return out
        io.io_write = watch
        for down in (True, False, True, False):
            bank.cylinder_set(down)
        self.assertNotIn((1, 1), [pair for pairs in state.values() for pair in pairs])

    def test_the_end_sensors_are_waited_for_and_a_stuck_cylinder_is_named(self):
        bank, io = self.bank()
        bank.cylinder_set(True)                                                  # sensors follow: arrives at once
        io.stuck.add(2)
        with self.assertRaises(H.HeadError) as cm:
            bank.cylinder_set(False, [1, 2, 3])
        self.assertIn("đầu 2", str(cm.exception))
        self.assertIn("lên", str(cm.exception))

    def test_a_pulse_switches_both_coils_off_after_the_move(self):
        bank, io = self.bank(coil_pulse_s=0.05)
        bank.cylinder_set(True, [1])
        self.assertEqual((io.bits[("RDO", 9)], io.bits[("RDO", 17)]), (0, 0))      # the valve keeps its position, the coils rest
        self.assertIn(("RDO", 9, [1]), io.writes)                                  # but the coil WAS energised
        self.assertTrue(bank.status()[0]["cylinder_down"])                          # the valve stayed down: the sensor says so

    def test_inverted_coil_logic(self):
        bank, io = self.bank(active=0, coil_active=0)
        bank.cylinder_set(True, [1])
        self.assertEqual((io.bits[("RDO", 9)], io.bits[("RDO", 17)]), (0, 1))      # energised = 0, idle = 1
        self.assertEqual(io.position[1], "down")

    def test_status_reports_down_from_the_sensor(self):
        bank, io = self.bank()
        bank.cylinder_set(True, [1, 2])
        rows = {r["n"]: r for r in bank.status()}
        self.assertTrue(rows[1]["cylinder_down"] and rows[2]["cylinder_down"])
        self.assertFalse(rows[3]["cylinder_down"])

    def test_without_sensors_the_fixed_time_is_used_and_the_coil_level_tells_the_position(self):
        cfg = coil_cfg(cylinder_s=0.25)
        for u in cfg["units"]:
            del u["cyl_down"], u["cyl_up"]
        io = CoilIo()
        bank = H.HeadBank.from_config(cfg, io)
        sleeps = []
        bank.sleep = sleeps.append
        bank.cylinder_set(True, [1])
        self.assertIn(0.25, sleeps)
        self.assertTrue(bank.status()[0]["cylinder_down"])

    def test_bad_coil_configuration(self):
        for unit in ({"vacuum": "RDO[1]", "coil_down": "RDO[9]"},                                    # one coil only
                     {"vacuum": "RDO[1]", "coil_up": "RDO[17]"},
                     {"vacuum": "RDO[1]", "cylinder": "RDO[9]", "coil_down": "RDO[10]", "coil_up": "RDO[11]"}):   # both kinds
            with self.subTest(unit=unit):
                with self.assertRaises(H.HeadError):
                    H.HeadBank.from_config({"units": [unit]}, CoilIo())

    def test_single_output_heads_still_work_and_can_be_mixed_in(self):
        cfg = coil_cfg()
        cfg["units"][1] = {"vacuum": "RDO[2]", "cylinder": "RDO[10]", "pressure": "RDI[2]"}      # head 2: one coil + spring return
        io = CoilIo()
        bank = H.HeadBank.from_config(cfg, io)
        bank.sleep = lambda sec: None
        bank.cylinder_set(True, [1, 2])
        self.assertEqual((io.bits[("RDO", 9)], io.bits[("RDO", 10)]), (1, 1))                      # both are down


if __name__ == "__main__":
    unittest.main()
