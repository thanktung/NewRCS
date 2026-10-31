"""Entry point. Works both as  `python -m rcs2`  and when this file is run directly (IDE "Run")."""
import os
import sys

if __package__ in (None, ""):
    # started as a plain script: make the project root importable and use absolute imports
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from rcs2.ui.main import main
else:
    from .ui.main import main

if __name__ == "__main__":
    sys.exit(main())
