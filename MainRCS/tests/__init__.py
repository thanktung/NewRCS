"""NewRCS tests, one folder per module (see tests/README.md).

Importing this package puts MainRCS/ (the `rcs2` package) and MainRCS/bridge32/ (the simulator, `bridge_simple`)
on sys.path, so every test module can simply `import bridge_simple` / `import rcs2...`."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (ROOT, os.path.join(ROOT, "bridge32")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
