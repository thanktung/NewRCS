"""Fluent light theme: palette, Qt style sheet and the small image assets the style sheet needs.

Usage:  apply_app(app)  once per QApplication, then  widget.setStyleSheet(build_style())  on the main window.
State colours of the fixture cards are the ones in STATE_COLORS (the cards paint them themselves);
labels / badges / buttons are driven by the dynamic properties `state`, `tone` and `kind`.
"""
import os
import tempfile
from string import Template

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt

from . import fluent as F

BG = "#F3F3F3"
SURFACE = "#FFFFFF"
TEXT = F.TEXT
MUTED = F.TEXT_2
ACCENT = F.ACCENT

# fixture state -> (accent strip, state text colour, card fill)
STATE_COLORS = {
    "off":     ("#C8C8C8", "#8A8886", "#FAFAFA"),
    "idle":    ("#8A8886", "#605E5C", "#FFFFFF"),
    "busy":    ("#FFB900", "#9D5D00", "#FFFFFF"),
    "testing": (F.ACCENT, F.ACCENT, "#FFFFFF"),
    "pass":    (F.SUCCESS, F.SUCCESS, "#FFFFFF"),
    "ng":      (F.DANGER, F.DANGER, "#FFFFFF"),
    "warn":    ("#F7630C", F.WARNING, "#FFFFFF"),
    "fault":   (F.DANGER, F.DANGER, "#FFF5F5"),
}

LOG_COLORS = {"debug": "#8A8886", "info": F.TEXT, "warn": F.WARNING, "warning": F.WARNING, "error": F.DANGER}


# --------------------------------------------------------------------------- #
# application level: Fusion base + light palette (Windows may be in dark mode)
# --------------------------------------------------------------------------- #
def apply_app(app):
    app.setStyle("Fusion")
    try:                                              # Qt >= 6.8: ignore the Windows dark mode
        app.styleHints().setColorScheme(Qt.ColorScheme.Light)
    except Exception:
        pass
    pal = QtGui.QPalette()
    roles = {
        QtGui.QPalette.Window: BG, QtGui.QPalette.WindowText: TEXT, QtGui.QPalette.Base: SURFACE,
        QtGui.QPalette.AlternateBase: "#F7F7F7", QtGui.QPalette.Text: TEXT, QtGui.QPalette.Button: SURFACE,
        QtGui.QPalette.ButtonText: TEXT, QtGui.QPalette.Highlight: ACCENT, QtGui.QPalette.HighlightedText: "#FFFFFF",
        QtGui.QPalette.ToolTipBase: SURFACE, QtGui.QPalette.ToolTipText: TEXT,
        QtGui.QPalette.PlaceholderText: "#8A8886", QtGui.QPalette.Link: ACCENT,
    }
    for role, color in roles.items():
        pal.setColor(role, QtGui.QColor(color))
    for role in (QtGui.QPalette.WindowText, QtGui.QPalette.Text, QtGui.QPalette.ButtonText):
        pal.setColor(QtGui.QPalette.Disabled, role, QtGui.QColor(F.TEXT_DISABLED))
    app.setPalette(pal)
    font = QtGui.QFont("Segoe UI Variable Text")
    font.setStyleHint(QtGui.QFont.SansSerif)
    font.setPixelSize(14)
    app.setFont(font)


# --------------------------------------------------------------------------- #
# image assets referenced from the style sheet (arrows, check mark)
# --------------------------------------------------------------------------- #
def _assets():
    folder = os.path.join(tempfile.gettempdir(), "rcs2_fluent_assets")
    os.makedirs(folder, exist_ok=True)

    def draw(name, points, color, closed=False, fill=False, size=12):
        path = os.path.join(folder, name)
        dpr = 2
        pm = QtGui.QPixmap(size * dpr, size * dpr)
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.transparent)
        p = QtGui.QPainter(pm)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        pen = QtGui.QPen(QtGui.QColor(color), 1.4)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        pts = [QtCore.QPointF(x, y) for x, y in points]
        p.drawPolyline(pts)
        p.end()
        pm.save(path, "PNG")
        return path.replace("\\", "/")

    return {
        "chev_down": draw("chev_down.png", [(2.5, 4.5), (6, 8), (9.5, 4.5)], F.TEXT_2),
        "chev_up": draw("chev_up.png", [(2.5, 7.5), (6, 4), (9.5, 7.5)], F.TEXT_2),
        "check": draw("check.png", [(2.5, 6.2), (5, 8.7), (9.5, 3.5)], "#FFFFFF"),
    }


_TEMPLATE = Template(r"""
* { font-family: "Segoe UI Variable Text", "Segoe UI", sans-serif; font-size: 14px; color: $TEXT; }
QMainWindow, QDialog, QMessageBox { background: $BG; }
QMessageBox QPushButton { min-width: 72px; }
QWidget#central { background: $BG; }
QToolTip { background: #FFFFFF; color: $TEXT; border: 1px solid $STROKE_STRONG; padding: 4px 8px; }

/* ---- typography ---------------------------------------------------------------- */
QLabel { background: transparent; }
QLabel#appTitle { font-size: 18px; font-weight: 600; }
QLabel#title { font-size: 20px; font-weight: 600; }
QLabel#subtitle, QLabel#caption { color: $MUTED; font-size: 12px; }
QLabel#sectionTitle { font-size: 14px; font-weight: 600; }
QLabel#muted { color: $MUTED; }
QLabel#mono { font-family: "Cascadia Mono", "Consolas", monospace; font-size: 13px; }
QLabel#kpiValue { font-size: 28px; font-weight: 600; }
QLabel#kpiName, QLabel#statName { color: $MUTED; font-size: 12px; }
QLabel#statValue { font-size: 16px; font-weight: 600; }
QLabel#fixName { font-size: 13px; font-weight: 600; }
QLabel#stateLabel { font-size: 16px; font-weight: 600; }
QLabel#cardStat { font-size: 12px; color: $MUTED; }
QLabel#monoSmall { font-family: "Cascadia Mono", "Consolas", monospace; font-size: 11px; color: $MUTED; }
QLabel#formStatus { color: $MUTED; }
QLabel#formStatus[tone="error"] { color: $DANGER; }
QLabel#formStatus[tone="success"] { color: $SUCCESS; }
QLabel#bigNumber { font-size: 28px; font-weight: 600; }
$STATE_LABELS

/* ---- command bar --------------------------------------------------------------- */
QFrame#commandBar { background: #FFFFFF; border: none; border-bottom: 1px solid $STROKE; }
QFrame#divider { background: $STROKE; border: none; max-width: 1px; min-width: 1px; }
QFrame#hline { background: $STROKE; border: none; max-height: 1px; min-height: 1px; }

/* ---- badges -------------------------------------------------------------------- */
QLabel#pill { border-radius: 10px; padding: 2px 10px; font-weight: 600; font-size: 12px;
              background: $NEUTRAL_FILL; color: $MUTED; }
QLabel#pill[tone="success"] { background: $SUCCESS_FILL; color: $SUCCESS; }
QLabel#pill[tone="danger"]  { background: $DANGER_FILL; color: $DANGER; }
QLabel#pill[tone="warning"] { background: $WARNING_FILL; color: $WARNING; }
QLabel#pill[tone="info"]    { background: $INFO_FILL; color: $ACCENT; }
QLabel#pill[tone="neutral"] { background: $NEUTRAL_FILL; color: $MUTED; }
QLabel#pill[compact="true"] { font-size: 11px; padding: 0 7px; border-radius: 9px; }

/* ---- info bars ----------------------------------------------------------------- */
QFrame#infoBar { border-radius: 4px; border: 1px solid $STROKE; background: #FFFFFF; }
QFrame#infoBar[severity="info"]    { background: $INFO_FILL; border-color: #C7E0F4; }
QFrame#infoBar[severity="success"] { background: $SUCCESS_FILL; border-color: #BCE5B9; }
QFrame#infoBar[severity="warning"] { background: $WARNING_FILL; border-color: #F5E2A0; }
QFrame#infoBar[severity="error"]   { background: $DANGER_FILL; border-color: #F3BFC3; }
QLabel#infoTitle { font-weight: 600; }
QLabel#infoMessage { color: $TEXT; }

/* ---- buttons ------------------------------------------------------------------- */
QPushButton { background: #FFFFFF; border: 1px solid $STROKE_STRONG; border-bottom-color: #BDBDBD;
              border-radius: 4px; padding: 5px 14px; min-height: 22px; font-weight: 400; }
QPushButton:hover { background: #F5F5F5; }
QPushButton:pressed { background: #E6E6E6; border-bottom-color: $STROKE_STRONG; }
QPushButton:disabled { color: $TEXT_DISABLED; background: #F5F5F5; border-color: $STROKE; }
QPushButton:focus { border: 1px solid $TEXT; }
QPushButton[kind="accent"], QMessageBox QPushButton:default { background: $ACCENT; border: 1px solid $ACCENT; color: #FFFFFF; }
QPushButton[kind="accent"]:hover, QMessageBox QPushButton:default:hover { background: $ACCENT_HOVER; border-color: $ACCENT_HOVER; }
QPushButton[kind="accent"]:pressed, QMessageBox QPushButton:default:pressed { background: $ACCENT_PRESSED; border-color: $ACCENT_PRESSED; }
QPushButton[kind="accent"]:disabled { background: #F0F0F0; border-color: $STROKE; color: $TEXT_DISABLED; }
QPushButton[kind="danger"] { background: $DANGER; border: 1px solid $DANGER; color: #FFFFFF; }
QPushButton[kind="danger"]:hover { background: #A62113; border-color: #A62113; }
QPushButton[kind="danger"]:disabled { background: #F0F0F0; border-color: $STROKE; color: $TEXT_DISABLED; }
QPushButton[kind="subtle"] { background: transparent; border: 1px solid transparent; }
QPushButton[kind="subtle"]:hover { background: #EDEDED; }
QPushButton[kind="subtle"]:pressed { background: #E0E0E0; }
QPushButton[kind="subtle"]:disabled { background: transparent; color: $TEXT_DISABLED; }
QPushButton[kind="jog"] { min-height: 30px; font-weight: 600; }
QPushButton[kind="chip"] { min-width: 28px; min-height: 18px; padding: 2px 0; font-weight: 600; border-radius: 4px; }
QPushButton[kind="chip"]:checked { background: $ACCENT; border-color: $ACCENT; color: #FFFFFF; }
QPushButton[kind="chip"]:checked:hover { background: $ACCENT_HOVER; }

QToolButton { background: transparent; border: 1px solid transparent; border-radius: 4px; padding: 4px; }
QToolButton:hover { background: #EDEDED; }
QToolButton:pressed { background: #E0E0E0; }
QToolButton:disabled { color: $TEXT_DISABLED; }
QToolButton::menu-indicator { image: none; width: 0px; }

/* ---- inputs -------------------------------------------------------------------- */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background: #FFFFFF; border: 1px solid $STROKE_STRONG; border-bottom: 1px solid #8A8886;
    border-radius: 4px; padding: 5px 10px; min-height: 22px;
    selection-background-color: $ACCENT; selection-color: #FFFFFF; }
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover { background: #FAFAFA; }
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    background: #FFFFFF; border-bottom: 2px solid $ACCENT; padding-bottom: 4px; }
QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled { background: #F5F5F5; color: $TEXT_DISABLED; border-color: $STROKE; }
QComboBox::drop-down { border: none; width: 28px; }
QComboBox::down-arrow { image: url($CHEV_DOWN); width: 12px; height: 12px; }
QComboBox QAbstractItemView { background: #FFFFFF; border: 1px solid $STROKE_STRONG; padding: 4px; outline: 0;
    selection-background-color: #EDEDED; selection-color: $TEXT; }
QComboBox QAbstractItemView::item { min-height: 28px; padding-left: 8px; border-radius: 4px; }
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button
    { width: 22px; border: none; background: transparent; subcontrol-origin: border; }
QSpinBox::up-button, QDoubleSpinBox::up-button { subcontrol-position: top right; }
QSpinBox::down-button, QDoubleSpinBox::down-button { subcontrol-position: bottom right; }
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow { image: url($CHEV_UP); width: 10px; height: 10px; }
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow { image: url($CHEV_DOWN); width: 10px; height: 10px; }

QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 18px; height: 18px; border-radius: 4px; border: 1px solid #8A8886; background: #FFFFFF; }
QCheckBox::indicator:checked { background: $ACCENT; border-color: $ACCENT; image: url($CHECK); }

/* ---- progress / scroll ---------------------------------------------------------- */
QProgressBar { background: #E6E6E6; border: none; border-radius: 2px; max-height: 4px; min-height: 4px; }
QProgressBar::chunk { background: $ACCENT; border-radius: 2px; }

QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { background: transparent; width: 12px; margin: 2px; }
QScrollBar::handle:vertical { background: #C8C8C8; border-radius: 4px; min-height: 36px; margin: 0 2px; }
QScrollBar::handle:vertical:hover { background: #9E9E9E; }
QScrollBar:horizontal { background: transparent; height: 12px; margin: 2px; }
QScrollBar::handle:horizontal { background: #C8C8C8; border-radius: 4px; min-width: 36px; margin: 2px 0; }
QScrollBar::handle:horizontal:hover { background: #9E9E9E; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QSplitter::handle { background: transparent; }

/* ---- tabs (bottom area of the main window) ----------------------------------------- */
QTabWidget::pane { border: none; background: transparent; top: 0px; }
QTabBar { background: transparent; qproperty-drawBase: 0; }
QTabBar::tab { background: transparent; color: $MUTED; font-weight: 600; padding: 6px 18px 7px 18px;
               margin-right: 2px; border: none; border-bottom: 3px solid transparent; }
QTabBar::tab:hover { color: $TEXT; background: #EDEDED; border-top-left-radius: 4px; border-top-right-radius: 4px; }
QTabBar::tab:selected { color: $TEXT; border-bottom: 3px solid $ACCENT; }

QPlainTextEdit#log { background: transparent; border: none; selection-background-color: $ACCENT;
    font-family: "Cascadia Mono", "Consolas", monospace; font-size: 12px; }

QMenu { background: #FFFFFF; border: 1px solid $STROKE_STRONG; padding: 4px; }
QMenu::item { padding: 7px 28px 7px 12px; border-radius: 4px; margin: 1px 2px; }
QMenu::item:selected { background: #EDEDED; color: $TEXT; }
QMenu::separator { height: 1px; background: $STROKE; margin: 4px 8px; }
""")


def build_style():
    a = _assets()
    state_labels = "\n".join('QLabel#stateLabel[state="%s"] { color: %s; }' % (k, v[1]) for k, v in STATE_COLORS.items())
    return _TEMPLATE.substitute(
        TEXT=F.TEXT, MUTED=F.TEXT_2, BG=BG, STROKE=F.STROKE, STROKE_STRONG=F.STROKE_STRONG,
        TEXT_DISABLED=F.TEXT_DISABLED, ACCENT=F.ACCENT, ACCENT_HOVER=F.ACCENT_HOVER, ACCENT_PRESSED=F.ACCENT_PRESSED,
        SUCCESS=F.SUCCESS, SUCCESS_FILL=F.SUCCESS_FILL, DANGER=F.DANGER, DANGER_FILL=F.DANGER_FILL,
        WARNING=F.WARNING, WARNING_FILL=F.WARNING_FILL, INFO_FILL=F.INFO_FILL, NEUTRAL_FILL=F.NEUTRAL_FILL,
        CHEV_DOWN=a["chev_down"], CHEV_UP=a["chev_up"], CHECK=a["check"], STATE_LABELS=state_labels)


def repolish(widget):
    F.repolish(widget)
