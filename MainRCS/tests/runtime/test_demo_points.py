"""Demo mode and the tray flow: the sample points make a complete, consistent layout for whatever settings.json declares."""
import copy
import unittest

from rcs2.config import DEFAULTS, load_settings
from rcs2.core import geometry as G
from rcs2.tools.demo import sample_flow_points
from tests.support.bridge import ROOT
import os


class SampleFlowPointsTests(unittest.TestCase):
    def check(self, cfg):
        pts = sample_flow_points(cfg)
        heads = len(cfg["end_effector"]["heads"]["units"])
        fixtures = [int(k) for k in cfg["ats"]["fixtures"]]
        self.assertEqual(G.Layout.missing(pts, cfg["trays"], fixtures, heads, bool(cfg["end_effector"].get("scanner"))), [])
        lay = G.Layout(pts, cfg["trays"], fixtures, heads, bool(cfg["end_effector"].get("scanner")))
        self.assertEqual(lay.input.capacity, cfg["trays"]["input"]["rows"] * cfg["trays"]["input"]["cols"])
        return pts

    def test_the_shipped_settings_get_a_complete_layout(self):
        cfg = load_settings(os.path.join(ROOT, "config", "settings.json"))
        cfg["ats"]["fixtures"] = {str(i): {"host": "127.0.0.1", "port": 1, "station": "S"} for i in range(1, 5)}      # --demo-fixtures 4
        self.assertEqual(self.check(cfg)["fixture_4"]["xyzwpr"][:2], [390.0, 600.0])

    def test_it_follows_the_number_of_heads_and_fixtures(self):
        cfg = copy.deepcopy(DEFAULTS)
        cfg["end_effector"] = {"heads": {"units": [{"vacuum": "RDO[%d]" % n} for n in range(1, 4)]}}
        cfg["trays"] = {"input": {"rows": 2, "cols": 3}, "ng": {"rows": 1, "cols": 4}}
        cfg["ats"]["fixtures"] = {"1": {}, "2": {}}
        pts = self.check(cfg)
        self.assertEqual(sorted(k for k in pts if k.startswith("head_")), ["head_1_at_O", "head_2_at_O", "head_3_at_O"])
        self.assertNotIn("scanner_at_O", pts)


if __name__ == "__main__":
    unittest.main()
