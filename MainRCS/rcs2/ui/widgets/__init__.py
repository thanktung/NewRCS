"""The widgets of the main window (one file each); the names below are what the windows import."""
from ..kit.fluent import InfoBar, Panel, Pill, Surface, ToggleSwitch, repolish  # noqa: F401
from .alarm_panel import AlarmPanel
from .fixture_card import FixtureCard
from .robot_panel import RobotPanel
from .texts import RESULT_TEXT, STATE_TEXT
from .totals_panel import TotalsPanel
from .tray_panel import HeadsStrip, TrayPanel, TrayView, flow_cell_states
