"""Run the NewRCS tests, all of them or only the modules you touched.

    python run_tests.py                     every module
    python run_tests.py robot ats           only tests/robot and tests/ats
    python run_tests.py runtime -v          verbose (one line per test)
    python run_tests.py core -k tray        only the tests whose name contains "tray"
    python run_tests.py --list              the module names

Modules = the folders of tests/ (config core robot ats devices reporting employee runtime ui simulator) plus
`architecture` (the import rules between the modules). The Qt tests run "offscreen": no window is opened.
"""
import argparse
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.abspath(__file__))
TESTS = os.path.join(ROOT, "tests")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYTHONUTF8", "1")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def module_names():
    folders = sorted(d for d in os.listdir(TESTS)
                     if os.path.isfile(os.path.join(TESTS, d, "__init__.py")) and d != "support")
    return folders + ["architecture"]


def build_suite(names, pattern):
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for name in names:
        if name == "architecture":
            suite.addTests(loader.loadTestsFromName("tests.test_architecture"))
        else:
            suite.addTests(loader.discover(os.path.join(TESTS, name), pattern="test*.py", top_level_dir=ROOT))
    if pattern:
        picked = unittest.TestSuite()

        def walk(s):
            for t in s:
                if isinstance(t, unittest.TestSuite):
                    walk(t)
                elif pattern.lower() in t.id().lower():
                    picked.addTest(t)
        walk(suite)
        return picked
    return suite


def main(argv=None):
    ap = argparse.ArgumentParser(description="Run the NewRCS tests (see the module docstring).")
    ap.add_argument("modules", nargs="*", help="test module folders; none = all")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("-k", dest="pattern", help="only tests whose id contains this text")
    ap.add_argument("--list", action="store_true", help="print the module names and exit")
    args = ap.parse_args(argv)
    known = module_names()
    if args.list:
        print("\n".join(known))
        return 0
    bad = [m for m in args.modules if m not in known]
    if bad:
        print("unknown module(s): %s (known: %s)" % (", ".join(bad), ", ".join(known)))
        return 2
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    suite = build_suite(args.modules or known, args.pattern)
    result = unittest.TextTestRunner(verbosity=2 if args.verbose else 1, warnings="ignore").run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
