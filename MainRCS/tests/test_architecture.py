"""The module layout of rcs2/ is enforced here: who may import whom, where Qt may be used, what the simulator may import.

When one of these fails you most probably put code in the wrong module (see MainRCS/README.md, "Dependency rules").
If a new dependency is really right, add it to ALLOWED below AND to the table in MainRCS/README.md.
"""
import ast
import os
import sys
import unittest

from tests import ROOT

PKG = os.path.join(ROOT, "rcs2")

# module -> the other rcs2 modules it may import (itself is always allowed)
ALLOWED = {
    "config": set(),
    "robot": set(),
    "ats": set(),
    "devices": set(),
    "reporting": set(),
    "employee": set(),
    "core": {"ats", "devices"},
    "tools": {"ats", "robot", "core"},
    "runtime": {"config", "core", "robot", "ats", "devices", "reporting", "employee"},
    "ui": {"config", "core", "employee", "runtime", "tools"},
}
QT_MODULES = {"PySide6", "PyQt5", "PyQt6", "shiboken6"}


def python_files(folder):
    for base, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in files:
            if f.endswith(".py"):
                yield os.path.join(base, f)


def imports_of(path):
    """[(absolute dotted module name, line)] of every import in the file (also those inside functions)."""
    rel = os.path.relpath(path, ROOT).replace("\\", "/")[:-3]
    parts = rel.split("/")
    package = parts[:-1] if parts[-1] != "__init__" else parts[:-1]
    out = []
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), path)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.extend((a.name, node.lineno) for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package[:len(package) - (node.level - 1)]
                name = ".".join(base + ([node.module] if node.module else []))
                if not node.module:                       # "from . import x": the names are the modules
                    out.extend((name + "." + a.name, node.lineno) for a in node.names)
                    continue
            else:
                name = node.module or ""
            out.append((name, node.lineno))
    return out


def module_of(path):
    rel = os.path.relpath(path, PKG).replace("\\", "/").split("/")
    return rel[0] if len(rel) > 1 else None           # rcs2/__main__.py etc. belong to no module


class ArchitectureTests(unittest.TestCase):
    def test_every_module_folder_is_known(self):
        folders = {d for d in os.listdir(PKG) if os.path.isfile(os.path.join(PKG, d, "__init__.py"))}
        self.assertEqual(folders, set(ALLOWED), "a module folder was added / removed: update ALLOWED and the README tables")

    def test_modules_only_import_what_they_may(self):
        problems = []
        for path in python_files(PKG):
            mod = module_of(path)
            if mod is None:
                continue
            for name, line in imports_of(path):
                top = name.split(".")
                if top[0] != "rcs2" or len(top) < 2:
                    continue
                target = top[1]
                if target in ALLOWED and target != mod and target not in ALLOWED[mod]:
                    problems.append("%s:%d  %s imports %s (%s)" % (os.path.relpath(path, ROOT), line, mod, target, name))
        self.assertEqual(problems, [], "\n" + "\n".join(problems))

    def test_qt_is_used_only_by_the_ui(self):
        problems = []
        for path in python_files(PKG):
            if module_of(path) == "ui":
                continue
            for name, line in imports_of(path):
                if name.split(".")[0] in QT_MODULES:
                    problems.append("%s:%d imports %s" % (os.path.relpath(path, ROOT), line, name))
        self.assertEqual(problems, [], "\n" + "\n".join(problems))

    def test_the_application_never_imports_the_tests_or_the_simulator(self):
        """Only `--demo` (rcs2/tools/demo.py) runs the simulator inside the application."""
        problems = []
        for path in python_files(PKG):
            demo = os.path.relpath(path, PKG).replace("\\", "/") == "tools/demo.py"
            for name, line in imports_of(path):
                if name.split(".")[0] in ("tests", "bridge_simple", "bridge32") and not (demo and name == "bridge_simple"):
                    problems.append("%s:%d imports %s" % (os.path.relpath(path, ROOT), line, name))
        self.assertEqual(problems, [], "\n" + "\n".join(problems))

    def test_the_simulator_stays_one_file_with_only_the_standard_library(self):
        """bridge32/bridge_simple.py must run on a bare Python (it may be copied alone to another PC)."""
        path = os.path.join(ROOT, "bridge32", "bridge_simple.py")
        foreign = sorted({n.split(".")[0] for n, _ in imports_of(path)} - set(sys.stdlib_module_names))
        self.assertEqual(foreign, [], "the simulator imports non-standard modules: %s" % foreign)


if __name__ == "__main__":
    unittest.main()
