"""The shipped example files must stay valid."""
import json
import os
import unittest

from tests.support import bridge as helpers
from rcs2.config import DEFAULTS, load_settings
from rcs2.core.sequence import load_sequences, validate

ROOT = helpers.ROOT


class ExampleFilesTest(unittest.TestCase):
    def test_settings_example(self):
        cfg = load_settings(os.path.join(ROOT, "config", "settings.example.json"))
        self.assertEqual(sorted(cfg["ats"]["fixtures"]), ["1", "2", "3", "4"])      # replaced, not merged with DEFAULTS
        import ipaddress
        ipaddress.IPv4Address(cfg["bridge"]["host"])               # whatever IP you put there must be valid
        self.assertEqual(cfg["bridge"]["port"], 5600)
        self.assertFalse(cfg["mysql"]["enabled"])
        self.assertNotIn("password", cfg["mysql"])                  # only the NAME of the env variable is stored
        self.assertEqual(cfg["mysql"]["password_env"], "RCS_DB_PASSWORD")
        for key in DEFAULTS:
            self.assertIn(key, cfg)
        self.assertEqual(cfg["employee"]["auto_logout_s"], 180)          # 3 minutes
        self.assertNotIn("hands", cfg)                                    # one End Effector now
        self.assertNotIn("scanners", cfg)
        ee = cfg["end_effector"]
        self.assertEqual(len(ee["heads"]["units"]), 8)                    # 8 cylinder + vacuum units
        self.assertTrue(ee["scanner"] and ee["laser"])                    # scanner + IL-1000 on the same tool
        self.assertEqual(cfg["trays"]["input"], {"rows": 5, "cols": 8})   # tray sizes live in the settings file only
        self.assertEqual(cfg["trays"]["ng"], {"rows": 4, "cols": 6})

    def test_sequences_example(self):
        data = load_sequences(os.path.join(ROOT, "config", "sequences.example.json"))
        self.assertTrue(data["example"])
        validate(data["sequences"], data["points"])
        for name in ("load", "unload_pass", "unload_ng"):
            self.assertIn(name, data["sequences"])


if __name__ == "__main__":
    unittest.main()
