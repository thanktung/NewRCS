"""Launcher for the RCS PC. In PyCharm: right-click this file -> Run.

    python run_rcs2.py                  real mode (needs config/settings.json and config/sequences.json)
    python run_rcs2.py --demo --autorun simulated robot + mock ATS, no hardware
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rcs2.ui.main import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
