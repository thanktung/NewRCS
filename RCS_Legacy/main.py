"""
main.py - RCS entry point.

    python main.py                 # uses station.ini next to this file
    python main.py path\to\station.ini

Wires everything together; contains no logic of its own.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QMessageBox

from rcs.clients.factory import TcpClientFactory
from rcs.config import ConfigError, load_config
from rcs.core.scheduler import Scheduler
from rcs.logging_setup import setup_logging
from rcs.persistence import StateStore
from rcs.traceability import CsvRecorder
from rcs.ui import theme as T
from rcs.ui.main_window import StationWindow


def _apply_palette(app: QApplication) -> None:
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(T.BG))
    pal.setColor(QPalette.WindowText, QColor(T.TEXT_PRI))
    pal.setColor(QPalette.Base, QColor(T.SURFACE))
    pal.setColor(QPalette.AlternateBase, QColor(T.SURFACE_ALT))
    pal.setColor(QPalette.Text, QColor(T.TEXT_PRI))
    pal.setColor(QPalette.Button, QColor(T.SURFACE))
    pal.setColor(QPalette.ButtonText, QColor(T.TEXT_PRI))
    pal.setColor(QPalette.Highlight, QColor(T.ACCENT))
    pal.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    app.setPalette(pal)


def main() -> int:
    app = QApplication(sys.argv)
    _apply_palette(app)

    try:
        ini = Path(sys.argv[1]) if len(sys.argv) > 1 else None
        cfg = load_config(ini)
    except (ConfigError, OSError, ValueError) as e:
        QMessageBox.critical(None, "RCS - configuration error", str(e))
        return 2

    store = StateStore(cfg.state_file)
    sched = Scheduler(cfg, TcpClientFactory(), store=store,
                      recorder=CsvRecorder(cfg.results_dir))

    win = StationWindow(sched)
    setup_logging(cfg.log_dir, callback=win.bridge.log.emit)

    saved = store.load()
    if saved:
        ans = QMessageBox.question(
            win, "Khôi phục trạng thái",
            f"Tìm thấy trạng thái đã lưu lúc {saved.get('saved_at', '?')}.\n"
            f"Khôi phục (khay, tay gắp, box, số liệu)?\n\n"
            f"Chọn No nếu đã sắp xếp lại hàng thủ công.")
        if ans == QMessageBox.Yes:
            sched.restore_state(saved)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
