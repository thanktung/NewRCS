"""Fluent (Windows 11 style, light) building blocks used by the NewRCS windows.

Everything here is view code only: no engine / runtime imports.

  Icons        glyph codes of the "Segoe Fluent Icons" font (Windows 11) with "Segoe MDL2 Assets" (Windows 10)
               as fallback. When neither font exists the icons are simply left out.
  Pill         small tinted status badge (tone: green|red|amber|blue|grey, or success|danger|warning|info|neutral)
  InfoBar      Fluent InfoBar (severity: info|success|warning|error) with a glyph, a title and a message
  Surface      rounded white card with a soft shadow and an optional coloured accent strip on its left edge
  Panel        Surface with a section title and a body layout
  ToggleSwitch Fluent switch (a QAbstractButton: isChecked / setChecked / clicked / click work as usual)
  FlowGrid     grid that re-flows its widgets into 1..N columns depending on the available width
"""
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt

# --------------------------------------------------------------------------- #
# design tokens (Fluent 2, light)
# --------------------------------------------------------------------------- #
ACCENT = "#0F6CBD"
ACCENT_HOVER = "#115EA3"
ACCENT_PRESSED = "#0F548C"
TEXT = "#1B1B1B"
TEXT_2 = "#605E5C"          # secondary text
TEXT_DISABLED = "#A19F9D"
STROKE = "#E0E0E0"
STROKE_STRONG = "#D1D1D1"
SUCCESS = "#107C10"
WARNING = "#9D5D00"
WARNING_FILL = "#FFF4CE"
DANGER = "#C42B1C"
DANGER_FILL = "#FDE7E9"
SUCCESS_FILL = "#DFF6DD"
INFO_FILL = "#EBF3FC"
NEUTRAL_FILL = "#F0F0F0"

# Segoe Fluent Icons code points
ICON = {
    "play": 0xE768, "pause": 0xE769, "stop": 0xE71A, "gear": 0xE713, "person": 0xE77B, "link": 0xE71B,
    "warning": 0xE7BA, "error": 0xEA39, "info": 0xE946, "ok": 0xE930, "cancel": 0xE711, "more": 0xE712,
    "refresh": 0xE72C, "accept": 0xE73E, "database": 0xE968, "move": 0xE7C2, "home": 0xE80F, "robot": 0xE99A,
    "shield": 0xEA18, "save": 0xE74E, "clear": 0xE74D, "list": 0xEA37, "history": 0xE81C, "lock": 0xE72E,
    "arrow_up": 0xE74A, "arrow_down": 0xE74B, "arrow_left": 0xE72B, "arrow_right": 0xE72A, "power": 0xE7E8,
    "sync": 0xE895, "target": 0xE7C1,
}

_TONES = {"green": "success", "red": "danger", "amber": "warning", "blue": "info", "grey": "neutral"}
_ICON_FONT = None


def repolish(widget):
    """Re-apply the style sheet after a dynamic property changed."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)


# --------------------------------------------------------------------------- #
# icons
# --------------------------------------------------------------------------- #
def icon_family():
    """Name of the installed icon font ('' when there is none)."""
    global _ICON_FONT
    if _ICON_FONT is None:
        families = set(QtGui.QFontDatabase.families())
        _ICON_FONT = next((f for f in ("Segoe Fluent Icons", "Segoe MDL2 Assets") if f in families), "")
    return _ICON_FONT


def glyph_pixmap(name, color, size=16, dpr=2.0, gap=0):
    """Glyph as a pixmap; `gap` adds transparent space on the right (icon-to-text distance in buttons)."""
    fam = icon_family()
    pm = QtGui.QPixmap(int((size + gap) * dpr), int(size * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.transparent)
    if not fam or name not in ICON:
        return pm
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.TextAntialiasing)
    font = QtGui.QFont(fam)
    font.setPixelSize(size)
    p.setFont(font)
    p.setPen(QtGui.QColor(color))
    p.drawText(QtCore.QRectF(0, 0, size, size), Qt.AlignCenter, chr(ICON[name]))
    p.end()
    return pm


def glyph_icon(name, color=TEXT, size=16, disabled=TEXT_DISABLED, gap=0):
    """QIcon with a normal and a disabled rendering of a Fluent glyph."""
    icon = QtGui.QIcon()
    if not icon_family():
        return icon
    icon.addPixmap(glyph_pixmap(name, color, size, gap=gap), QtGui.QIcon.Normal)
    icon.addPixmap(glyph_pixmap(name, disabled, size, gap=gap), QtGui.QIcon.Disabled)
    return icon


def button(text="", glyph=None, kind=None, color=TEXT, size=16, gap=6):
    """QPushButton with an optional Fluent glyph. kind: accent | danger | subtle | jog (style sheet property)."""
    b = QtWidgets.QPushButton(text)
    if kind:
        b.setProperty("kind", kind)
    if glyph and icon_family():
        g = gap if text else 0
        b.setIcon(glyph_icon(glyph, color, size, gap=g))
        b.setIconSize(QtCore.QSize(size + g, size))
    return b


class GlyphLabel(QtWidgets.QLabel):
    def __init__(self, name, color=TEXT, size=16):
        super().__init__()
        self.setFixedSize(size + 4, size + 4)
        self.setAlignment(Qt.AlignCenter)
        self.set_glyph(name, color, size)

    def set_glyph(self, name, color, size=None):
        size = size or self.width() - 4
        self.setPixmap(glyph_pixmap(name, color, size))


def confirm(parent, title, text, warning=False, default_yes=False):
    """Yes/No question with Vietnamese buttons (Qt ships no Vietnamese translation). True when the user says Có."""
    box = QtWidgets.QMessageBox(parent)
    box.setIcon(QtWidgets.QMessageBox.Warning if warning else QtWidgets.QMessageBox.Question)
    box.setWindowTitle(title)
    box.setText(text)
    yes = box.addButton("Có", QtWidgets.QMessageBox.YesRole)
    no = box.addButton("Không", QtWidgets.QMessageBox.NoRole)
    box.setDefaultButton(yes if default_yes else no)
    box.exec()
    return box.clickedButton() is yes


# --------------------------------------------------------------------------- #
# badge
# --------------------------------------------------------------------------- #
class Pill(QtWidgets.QLabel):
    """Small tinted status badge. tone: green|red|amber|blue|grey (or success|danger|warning|info|neutral)."""

    def __init__(self, text="", tone="grey", compact=False):
        super().__init__(text)
        self.setObjectName("pill")
        self.setAlignment(Qt.AlignCenter)
        self.setProperty("compact", compact)                 # smaller badge for dense layouts (fixture cards)
        self.setFixedHeight(18 if compact else 22)
        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        self.set(text, tone)

    def set(self, text, tone):
        tone = _TONES.get(tone, tone)
        if self.text() != text:
            self.setText(text)
        if self.property("tone") != tone:
            self.setProperty("tone", tone)
            repolish(self)


# --------------------------------------------------------------------------- #
# info bar
# --------------------------------------------------------------------------- #
_SEVERITY = {"info": ("info", ACCENT), "success": ("ok", SUCCESS), "warning": ("warning", WARNING),
             "error": ("error", DANGER)}


class InfoBar(QtWidgets.QFrame):
    def __init__(self, severity="info", title="", message="", parent=None):
        super().__init__(parent)
        self.setObjectName("infoBar")
        self.setProperty("severity", severity)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(10)
        self.glyph = GlyphLabel("info", ACCENT, 16)
        self.title = QtWidgets.QLabel(title)
        self.title.setObjectName("infoTitle")
        self.message = QtWidgets.QLabel(message)
        self.message.setWordWrap(True)
        self.message.setObjectName("infoMessage")
        text = QtWidgets.QVBoxLayout()
        text.setSpacing(0)
        text.addWidget(self.title)
        text.addWidget(self.message)
        lay.addWidget(self.glyph, 0, Qt.AlignTop)
        lay.addLayout(text, 1)
        self.set(severity, title, message)

    def set(self, severity, title="", message=""):
        glyph, color = _SEVERITY.get(severity, _SEVERITY["info"])
        self.glyph.set_glyph(glyph, color)
        self.title.setText(title)
        self.title.setVisible(bool(title))
        self.message.setText(message)
        self.message.setVisible(bool(message))
        if self.property("severity") != severity:
            self.setProperty("severity", severity)
            repolish(self)


# --------------------------------------------------------------------------- #
# surfaces
# --------------------------------------------------------------------------- #
class Surface(QtWidgets.QFrame):
    """White rounded card with a soft shadow; `set_accent()` draws a coloured strip on the left edge."""
    RADIUS = 8

    def __init__(self):
        super().__init__()
        self.setObjectName("surface")
        self._accent = None
        self._fill = QtGui.QColor("#FFFFFF")
        self._border = QtGui.QColor(STROKE)

    def set_accent(self, color):
        color = QtGui.QColor(color) if color else None
        if color != self._accent:
            self._accent = color
            self.update()

    def set_fill(self, color):
        color = QtGui.QColor(color)
        if color != self._fill:
            self._fill = color
            self.update()

    def paintEvent(self, _event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        r = QtCore.QRectF(self.rect()).adjusted(1.5, 1.0, -1.5, -3.0)
        for dy, alpha in ((2.0, 8), (1.0, 14)):                       # soft elevation shadow
            p.setPen(Qt.NoPen)
            p.setBrush(QtGui.QColor(0, 0, 0, alpha))
            p.drawRoundedRect(r.translated(0, dy), self.RADIUS, self.RADIUS)
        path = QtGui.QPainterPath()
        path.addRoundedRect(r, self.RADIUS, self.RADIUS)
        p.fillPath(path, self._fill)
        if self._accent is not None:
            p.save()
            p.setClipPath(path)
            p.fillRect(QtCore.QRectF(r.left(), r.top(), 4, r.height()), self._accent)
            p.restore()
        p.setPen(QtGui.QPen(self._border, 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r, self.RADIUS, self.RADIUS)


class Panel(Surface):
    """Surface with a section title; add content to `self.body`."""

    def __init__(self, title, glyph=None):
        super().__init__()
        self.body = QtWidgets.QVBoxLayout(self)
        self.body.setContentsMargins(14, 10, 14, 12)
        self.body.setSpacing(8)
        self.header = QtWidgets.QHBoxLayout()
        self.header.setSpacing(8)
        if glyph:
            self.header.addWidget(GlyphLabel(glyph, TEXT_2, 16))
        self.title = QtWidgets.QLabel(title)
        self.title.setObjectName("sectionTitle")
        self.header.addWidget(self.title)
        self.header.addStretch()
        self.body.addLayout(self.header)


# --------------------------------------------------------------------------- #
# toggle switch
# --------------------------------------------------------------------------- #
class ToggleSwitch(QtWidgets.QAbstractButton):
    """Fluent switch with the label on its right."""
    GAP = 12

    def __init__(self, text="", compact=False):
        super().__init__()
        self.TRACK_W, self.TRACK_H = (30, 16) if compact else (40, 20)       # compact: small cards
        self._knob = 10 if compact else 12                                    # knob diameter when off (grows by 2)
        self._height = 22 if compact else 28
        if compact:
            self.GAP = 8
        self.setText(text)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self._pos = 0.0                    # knob position 0..1 (animated towards the checked state)
        self.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)

    def sizeHint(self):
        w = self.TRACK_W + 4
        if self.text():
            w += self.GAP + self.fontMetrics().horizontalAdvance(self.text()) + 4
        return QtCore.QSize(max(w, 90 if self._height < 28 else 120), self._height)

    def minimumSizeHint(self):
        return self.sizeHint()

    def paintEvent(self, _event):
        target = 1.0 if self.isChecked() else 0.0
        if abs(self._pos - target) > 0.01:
            self._pos += (target - self._pos) * 0.45
            QtCore.QTimer.singleShot(16, self.update)
        else:
            self._pos = target
        t, on, enabled = self._pos, self.isChecked(), self.isEnabled()
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        track = QtCore.QRectF(2, (self.height() - self.TRACK_H) / 2, self.TRACK_W, self.TRACK_H)
        if on:
            p.setPen(Qt.NoPen)
            p.setBrush(QtGui.QColor(ACCENT if enabled else "#C8C8C8"))
        else:
            p.setPen(QtGui.QPen(QtGui.QColor("#8A8886" if enabled else "#C8C8C8"), 1))
            p.setBrush(Qt.NoBrush)
            track = track.adjusted(0.5, 0.5, -0.5, -0.5)
        p.drawRoundedRect(track, self.TRACK_H / 2, self.TRACK_H / 2)
        d = self._knob + 2 * t                                    # knob grows slightly when on
        cx = 2 + self.TRACK_H / 2 + t * (self.TRACK_W - self.TRACK_H)
        p.setPen(Qt.NoPen)
        p.setBrush(QtGui.QColor("#FFFFFF" if on else ("#5C5C5C" if enabled else "#C8C8C8")))
        p.drawEllipse(QtCore.QPointF(cx, self.height() / 2), d / 2, d / 2)
        if self.hasFocus() and self.focusPolicy() != Qt.NoFocus:
            p.setBrush(Qt.NoBrush)
            p.setPen(QtGui.QPen(QtGui.QColor(TEXT), 1))
            p.drawRoundedRect(track.adjusted(-2, -2, 2, 2), 12, 12)
        if self.text():
            p.setPen(QtGui.QColor(TEXT if enabled else TEXT_DISABLED))
            p.drawText(QtCore.QRectF(self.TRACK_W + self.GAP + 2, 0, self.width(), self.height()),
                       Qt.AlignVCenter | Qt.AlignLeft, self.text())


# --------------------------------------------------------------------------- #
# responsive grid
# --------------------------------------------------------------------------- #
class FlowGrid(QtWidgets.QWidget):
    """Lays its widgets out in as many columns (1..max_cols) as the width allows.
    `content_height` is the height all rows need; `height_changed(h)` fires when a re-flow changes it, so the owner can
    size its scroll area to the content instead of leaving an empty gap below the last row."""
    height_changed = QtCore.Signal(int)

    def __init__(self, max_cols=4, min_item_width=250, spacing=12):
        super().__init__()
        self.max_cols, self.min_item_width, self.spacing = max_cols, min_item_width, spacing
        self.content_height = 0
        self._items = []
        self._cols = 0
        self._grid = QtWidgets.QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(spacing)

    def set_widgets(self, widgets):
        self._items = list(widgets)
        self._cols = 0
        self._reflow(self.width())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reflow(event.size().width())

    def _reflow(self, width):
        cols = max(1, min(self.max_cols, (width + self.spacing) // (self.min_item_width + self.spacing)))
        if cols == self._cols or not self._items:
            return
        self._cols = cols
        for w in self._items:
            self._grid.removeWidget(w)
        for c in range(self.max_cols + 1):
            self._grid.setColumnStretch(c, 0)
        for r in range(len(self._items) + 2):
            self._grid.setRowStretch(r, 0)
        for i, w in enumerate(self._items):
            self._grid.addWidget(w, i // cols, i % cols)
        for c in range(cols):
            self._grid.setColumnStretch(c, 1)
        rows = (len(self._items) + cols - 1) // cols
        self._grid.setRowStretch(rows, 1)
        item_h = max(max(w.sizeHint().height(), w.minimumHeight()) for w in self._items)
        height = rows * item_h + (rows - 1) * self.spacing
        self.setMinimumHeight(height)
        if height != self.content_height:
            self.content_height = height
            self.height_changed.emit(height)

