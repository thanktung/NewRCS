"""Sequence validation, variable expansion and the step runner."""
import threading
import unittest

from rcs2.core import sequence as S


class RecordingRobot:
    def __init__(self):
        self.calls = []

    def __getattr__(self, op):
        if op in ("move", "rmove", "gosafetarge", "put", "get", "up", "down", "gosafehere"):
            def call(*args, **kwargs):
                self.calls.append((op, args, kwargs))
            return call
        raise AttributeError(op)


class RecordingAts:
    def __init__(self, connected=True):
        self.connected, self.calls = connected, []

    def place_dut_ok(self):
        self.calls.append("place_dut_ok")
        return self.connected

    def fixture_close(self):
        self.calls.append("fixture_close")
        return self.connected

    def send_barcode(self, sn):
        self.calls.append("barcode:" + sn)
        return self.connected


POINTS = {"home": [0, 0, 300, 180, 0, 0], "above_fixture_1": [100, 200, 250, 180, 0, 0],
          "tilted": {"xyzwpr": [1, 2, 3, 4, 5, 6], "config": [1, 1, 1, 1, 0, 0, 0], "uf": 1, "ut": 1}}


class ValidateTests(unittest.TestCase):
    def check(self, steps, ok=True, points=POINTS):
        if ok:
            S.validate({"s": steps}, points)
        else:
            with self.assertRaises(S.SequenceError):
                S.validate({"s": steps}, points)

    def test_valid(self):
        self.check([{"robot": "move", "pose": "home"}, {"robot": "put", "station": 1}, {"robot": "gosafehere"},
                   {"ats": "place_dut_ok"}, {"wait": 1}, {"log": "x"}, {"robot": "move", "pose": "above_fixture_{fixture}"},
                   {"robot": "rmove", "target": [0, 0, 10, 0, 0, 0], "override": 5}])

    def test_invalid_steps(self):
        self.check([{"robot": "fly"}], ok=False)
        self.check([{"robot": "move", "pose": "nowhere"}], ok=False)
        self.check([{"robot": "move"}], ok=False)
        self.check([{"robot": "move", "pose": "home", "target": [0] * 6}], ok=False)
        self.check([{"robot": "put"}], ok=False)
        self.check([{"ats": "explode"}], ok=False)
        self.check([{"wait": -1}], ok=False)
        self.check([{"wait": 1, "log": "two kinds"}], ok=False)
        self.check([{"robot": "move", "pose": "home", "override": 0}], ok=False)
        self.check(["not an object"], ok=False)

    def test_bad_points(self):
        with self.assertRaises(S.SequenceError):
            S.validate({}, {"p": [1, 2, 3]})


class ExpandTests(unittest.TestCase):
    def test_expand(self):
        self.assertEqual(S.expand({"a": ["x{fixture}", 1]}, {"fixture": 3}), {"a": ["x3", 1]})

    def test_unknown_variable(self):
        with self.assertRaises(S.SequenceError):
            S.expand("{nope}", {})


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.robot = RecordingRobot()
        self.ats = {1: RecordingAts()}
        self.runner = S.SequenceRunner(self.robot, self.ats, POINTS, default_override=12, sleep=lambda s: None)
        self.vars = {"fixture": 1, "robot_station": 4, "station": "Station1", "result": "PASS"}

    def test_robot_steps(self):
        self.runner.run("t", [
            {"robot": "move", "pose": "above_fixture_{fixture}"},
            {"robot": "move", "pose": "tilted", "override": 5},
            {"robot": "put", "station": "{robot_station}"},
            {"robot": "rmove", "target": [0, 0, 5, 0, 0, 0]},
            {"robot": "gosafehere"}], self.vars)
        c = self.robot.calls
        self.assertEqual(c[0], ("move", ([100, 200, 250, 180, 0, 0],), {"override": 12, "config": None, "uf": None, "ut": None}))
        self.assertEqual(c[1][2], {"override": 5, "config": [1, 1, 1, 1, 0, 0, 0], "uf": 1, "ut": 1})
        self.assertEqual(c[2], ("put", (4,), {"override": 12}))
        self.assertEqual(c[3], ("rmove", ([0, 0, 5, 0, 0, 0],), {"override": 12}))
        self.assertEqual(c[4][0], "gosafehere")

    def test_ats_steps(self):
        self.runner.run("t", [{"ats": "fixture_close"}, {"ats": "barcode", "sn": "SN1"}, {"ats": "place_dut_ok"}], self.vars)
        self.assertEqual(self.ats[1].calls, ["fixture_close", "barcode:SN1", "place_dut_ok"])

    def test_ats_not_connected_raises(self):
        self.ats[1].connected = False
        with self.assertRaises(S.SequenceError):
            self.runner.run("t", [{"ats": "place_dut_ok"}], self.vars)

    def test_cancel_between_steps(self):
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(S.JobCancelled):
            self.runner.run("t", [{"robot": "gosafehere"}], self.vars, cancel=cancel)
        self.assertEqual(self.robot.calls, [])

    def test_wait_uses_sleep(self):
        slept = []
        r = S.SequenceRunner(self.robot, self.ats, POINTS, sleep=slept.append)
        r.run("t", [{"wait": 0.5}], self.vars)
        self.assertEqual(slept, [0.5])


class FileLayoutTests(unittest.TestCase):
    DATA = {
        "example": True, "_note": "x",
        "points": {
            "above_input": [300, -200, 250, 180, 0, 0],
            "above_fixture_1": {"xyzwpr": [679.025, 25.199, 788.931, 88.284, -15.223, 140.437],
                                "config": [1, 0, 1, 1, 0, 0, 0], "uf": 0, "ut": 1},
        },
        "sequences": {"load": [{"robot": "move", "pose": "above_input"}, {"robot": "get", "station": 0}],
                      "empty": []},
    }

    def test_every_point_and_step_is_one_line_and_data_is_unchanged(self):
        import json
        text = S.dump_sequences(self.DATA)
        self.assertEqual(json.loads(text), self.DATA)                       # same data, only the layout differs
        lines = text.split("\n")
        self.assertIn('    "above_input": [300, -200, 250, 180, 0, 0],', lines)
        self.assertTrue(any(l.strip().startswith('"above_fixture_1": {"xyzwpr": [679.025, 25.199, 788.931, 88.284, '
                                                  '-15.223, 140.437], "config": [1, 0, 1, 1, 0, 0, 0]')
                            and l.rstrip(",").endswith('"ut": 1}') for l in lines), text)
        self.assertIn('      {"robot": "move", "pose": "above_input"},', lines)
        self.assertIn('      {"robot": "get", "station": 0}', lines)
        self.assertIn('    "empty": []', lines)
        self.assertLess(max(len(l) for l in lines), 160)
        self.assertTrue(text.endswith("}\n"))

    def test_long_value_falls_back_to_several_lines(self):
        import json
        data = {"points": {"p": {"xyzwpr": [1.123456789] * 40}}}
        text = S.dump_sequences(data, width=80)
        self.assertEqual(json.loads(text), data)
        self.assertGreater(text.count("\n"), 6)

    def test_save_is_atomic_and_loadable(self):
        import os
        import tempfile
        path = os.path.join(tempfile.mkdtemp(), "sequences.json")
        S.save_sequences(path, self.DATA)
        self.assertEqual(S.load_sequences(path)["points"]["above_input"], [300, -200, 250, 180, 0, 0])
        self.assertFalse(os.path.exists(path + ".tmp"))


if __name__ == "__main__":
    unittest.main()
