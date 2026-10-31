"""theme.py - Design tokens (Fluent / MD3 light theme)."""

from __future__ import annotations

from ..models import BoardState, BoxState

BG = "#F3F3F3"
SURFACE = "#FFFFFF"
SURFACE_ALT = "#FAFAFA"
BORDER = "#E0E0E0"

TEXT_PRI = "#1A1A1A"
TEXT_SEC = "#605E5C"
TEXT_DIS = "#ADADAD"

ACCENT = "#0078D4"
GREEN, GREEN_BG = "#107C10", "#DFF6DD"
RED, RED_BG = "#D13438", "#FDE7E9"
YELLOW, YELLOW_BG = "#CA5010", "#FFF4CE"
BLUE, BLUE_BG = "#0078D4", "#EBF3FC"
PURPLE, PURPLE_BG = "#8764B8", "#F0EBF8"

FONT_UI = "Segoe UI"
FONT_MONO = "Consolas"

R_CARD = "8px"
R_CHIP = "4px"
R_BTN = "6px"

# BoxState -> (background, border, text)
BOX_THEME = {
    BoxState.EMPTY: (SURFACE, BORDER, TEXT_DIS),
    BoxState.READY: (BLUE_BG, BLUE, BLUE),
    BoxState.TESTING: (YELLOW_BG, YELLOW, YELLOW),
    BoxState.PASS: (GREEN_BG, GREEN, GREEN),
    BoxState.FAIL: (RED_BG, RED, RED),
    BoxState.ERROR: (YELLOW_BG, YELLOW, YELLOW),
    BoxState.UNKNOWN: (SURFACE_ALT, BORDER, TEXT_DIS),
}

BOARD_COLOR = {
    BoardState.UNTESTED: BLUE,
    BoardState.PASS: GREEN,
    BoardState.NG: RED,
}
BOARD_BG = {
    BoardState.PASS: GREEN_BG,
    BoardState.NG: RED_BG,
    BoardState.UNTESTED: BLUE_BG,
}

# UI refreshes at most this often, however fast the backend changes.
REFRESH_MS = 100
