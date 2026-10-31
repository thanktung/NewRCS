"""Application entry point:  python -m rcs2 [--config config/settings.json] [--demo]"""
import argparse
import logging
import logging.handlers
import os
import sys

from ..config import load_settings

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def setup_logging(log_dir):
    os.makedirs(log_dir, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    fileh = logging.handlers.TimedRotatingFileHandler(os.path.join(log_dir, "rcs2.log"), when="midnight",
                                                      backupCount=30, encoding="utf-8")
    fileh.setFormatter(fmt)
    root.addHandler(fileh)
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="rcs2", description="NewRCS - robot cell supervisor")
    ap.add_argument("--config", default=os.path.join(ROOT, "config", "settings.json"))
    ap.add_argument("--demo", action="store_true", help="simulated robot + mock ATS, no hardware needed")
    ap.add_argument("--no-login", action="store_true", help="do not require a login (demo implies it)")
    ap.add_argument("--demo-fixtures", type=int, default=4)
    ap.add_argument("--screenshot", help="save a screenshot to this file after --seconds and exit")
    ap.add_argument("--autorun", action="store_true", help="demo: enable all fixtures and start immediately")
    ap.add_argument("--seconds", type=float, default=8.0)
    args = ap.parse_args(argv)

    setup_logging(os.path.join(ROOT, "logs"))
    from PySide6 import QtCore, QtWidgets
    app = QtWidgets.QApplication(sys.argv[:1])
    from .kit.theme import apply_app
    apply_app(app)                                   # Fluent light palette, also for early message boxes

    stop_demo = None
    try:
        if args.demo:
            from ..tools.demo import DEMO_POINTS, DEMO_SEQUENCES, sample_flow_points, start_demo
            base = load_settings(args.config if os.path.exists(args.config) else None)
            base["outbox_path"] = os.path.join(ROOT, "data", "outbox_demo.sqlite")
            settings, stop_demo = start_demo(base, fixtures=args.demo_fixtures)
            points = dict(DEMO_POINTS)
            if settings["flow"]["mode"] == "tray":
                points.update(sample_flow_points(settings))              # sample coordinates so that the tray flow can run
            seq = {"points": points, "sequences": DEMO_SEQUENCES, "example": True}
        else:
            if not os.path.exists(args.config):
                raise FileNotFoundError(
                    "Không tìm thấy file cấu hình: %s\nHãy sao chép config\\settings.example.json thành "
                    "config\\settings.json rồi chỉnh sửa, hoặc thử  python -m rcs2 --demo" % args.config)
            settings, seq = load_settings(args.config), None
        from ..runtime import Runtime
        rt = Runtime(settings, ROOT, seq)
    except Exception as ex:
        QtWidgets.QMessageBox.critical(None, "NewRCS", "Không thể khởi động:\n\n%s" % ex)
        if stop_demo:
            stop_demo()
        return 2

    from .windows.main_window import MainWindow
    win = MainWindow(rt, settings, require_login=not (args.demo or args.no_login))
    rt.start()
    win.show()

    if args.autorun and args.demo:
        def autorun():
            for n in rt.ats:
                rt.engine.set_enabled(n, True)
            rt.engine.start_run()
        QtCore.QTimer.singleShot(2500, autorun)
    if args.screenshot:
        def shoot():
            win.grab().save(args.screenshot)
            win.no_confirm = True
            win.close()
        QtCore.QTimer.singleShot(int(args.seconds * 1000), shoot)

    code = app.exec()
    if stop_demo:
        stop_demo()
    return code


if __name__ == "__main__":
    sys.exit(main())

