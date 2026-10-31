"""settings.json -> "flow": validated when the program starts; the shipped example stays valid."""
import copy
import json
import os
import unittest

from rcs2.config import DEFAULTS
from rcs2.core.flow import FlowController, FlowError, FlowSettings
from tests.support.bridge import ROOT

TRAYS = {"input": {"rows": 2, "cols": 4}, "ng": {"rows": 1, "cols": 4}}


def cfg(**flow):
    c = copy.deepcopy(DEFAULTS)
    c["flow"].update(flow)
    return c


class FlowSettingsTests(unittest.TestCase):
    def test_the_removed_classic_mode_is_refused_with_a_clear_message(self):
        with self.assertRaises(FlowError) as cm:
            FlowSettings.from_config(cfg(mode="classic"), 8)
        self.assertIn("classic", str(cm.exception))
        FlowSettings.from_config(cfg(), 8)                                          # an old settings.json naming "tray" still loads

    def test_the_defaults(self):
        s = FlowSettings.from_config(cfg(), 8)
        self.assertEqual((s.max_attempts, s.keep_free, s.max_pick, s.max_sort, s.top_up_when_idle, s.scan, s.override),
                         (3, 1, 8, 8, True, True, None))

    def test_values_larger_than_the_number_of_heads_are_cut_to_it(self):
        s = FlowSettings.from_config(cfg(max_pick=20, max_sort=9, pick_ahead=12, keep_free_heads=30), 4)
        self.assertEqual((s.max_pick, s.max_sort, s.pick_ahead, s.keep_free), (4, 4, 4, 3))     # a head always stays usable

    def test_bad_values_are_refused_with_the_key_in_the_message(self):
        for key, value in (("max_attempts", 0), ("max_attempts", True), ("max_pick", "8"), ("override", 0),
                           ("override", 2.5), ("check_timeout_s", 0.01), ("keep_free_heads", -1)):
            with self.subTest(key=key, value=value):
                with self.assertRaises(FlowError) as cm:
                    FlowSettings.from_config(cfg(**{key: value}), 8)
                self.assertIn(key, str(cm.exception))

    def test_the_flow_needs_heads_and_both_trays(self):
        with self.assertRaises(FlowError) as cm:
            FlowSettings.from_config(cfg(), 0)
        self.assertIn("heads", str(cm.exception))
        with self.assertRaises(FlowError) as cm:
            FlowSettings.from_config(cfg(), 1)                                      # one head cannot swap products
        self.assertIn("at least 2", str(cm.exception))
        FlowSettings.from_config(cfg(), 2)
        s = FlowSettings.from_config(cfg(), 4)
        with self.assertRaises(FlowError):
            FlowController(s, {"input": TRAYS["input"]}, [1, 2], 4, True)
        ctl = FlowController(s, TRAYS, [2, 1], 4, True)
        self.assertEqual(ctl.fixture_numbers, [1, 2])
        self.assertEqual((ctl.book.capacity, ctl.book.ng_capacity), (8, 4))

    def test_scan_is_off_without_a_scanner_or_when_switched_off(self):
        s = FlowSettings.from_config(cfg(), 4)
        self.assertFalse(FlowController(s, TRAYS, [1], 4, False).scanner)
        s2 = FlowSettings.from_config(cfg(scan=False), 4)
        self.assertFalse(FlowController(s2, TRAYS, [1], 4, True).scanner)

    def test_laser_check_defaults_and_values(self):
        s = FlowSettings.from_config(cfg(), 8)
        self.assertEqual((s.laser, s.laser_places, len(s.laser_offsets), s.laser_timeout_s, s.stop_robot_on_drop),
                         (False, ("box", "input", "output"), 2, 1.0, True))
        s = FlowSettings.from_config(cfg(laser_check={"enabled": True, "places": ["box", "input", "output", "ng"],
                                                                   "offsets": [[1, 2, 3], [4.5, 0, -1]], "timeout_s": 2}, stop_robot_on_drop=False), 8)
        self.assertEqual((s.laser, s.laser_places, s.laser_offsets, s.laser_timeout_s, s.stop_robot_on_drop),
                         (True, ("box", "input", "output", "ng"), ((1.0, 2.0, 3.0), (4.5, 0.0, -1.0)), 2.0, False))

    def test_bad_laser_check_values_are_refused(self):
        for lc in ({"places": []}, {"places": ["shelf"]}, {"places": "box"}, {"offsets": []}, {"offsets": [[1, 2]]},
                   {"offsets": [[1, 2, "3"]]}, {"offsets": [[0, 0, 0]] * 5}, {"timeout_s": 0}, {"timeout_s": True}):
            with self.subTest(laser_check=lc):
                with self.assertRaises(FlowError) as cm:
                    FlowSettings.from_config(cfg(laser_check=lc), 8)
                self.assertIn("laser_check", str(cm.exception))

    def test_the_shipped_example_flow_block_is_valid(self):
        with open(os.path.join(ROOT, "config", "settings.example.json"), encoding="utf-8-sig") as fh:
            data = json.load(fh)
        self.assertNotIn("mode", data["flow"])
        FlowSettings.from_config(data, 8)


if __name__ == "__main__":
    unittest.main()
