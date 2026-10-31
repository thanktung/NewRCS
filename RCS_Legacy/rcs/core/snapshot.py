"""
snapshot.py - Immutable-ish copy of the scheduler state for the UI.

The UI never touches scheduler internals: it asks for a Snapshot (taken under
the scheduler lock) and renders it. This also makes the UI trivially testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..models import Board, BoxState, SystemState


@dataclass
class BoxView:
    box_id: int
    state: BoxState
    board: Optional[Board]
    enabled: bool
    connected: bool
    state_age_sec: float
    tested: int
    passed: int
    fail_streak: int
    rate_per_hour: float
    pass_pct: Optional[float]


@dataclass
class HeadView:
    head_id: int
    board: Optional[Board]
    enabled: bool


@dataclass
class Snapshot:
    system_state: SystemState
    fault: Optional[str]
    alerts: dict
    mode: str
    protocol: str
    batch: bool
    station_name: str
    robot_connected: bool
    robot_status: str                  # IDLE/BUSY/ALARM/ESTOP/"" (unknown)
    boxes: list = field(default_factory=list)       # list[BoxView]
    heads: list = field(default_factory=list)       # list[HeadView]
    tray1: list = field(default_factory=list)       # list[Optional[Board]]
    tray2: list = field(default_factory=list)
    ng_count: int = 0
    ng_capacity: int = 0
    stats: dict = field(default_factory=dict)       # loaded / pass / ng / change
    system_metrics: dict = field(default_factory=dict)
    manual_edit_allowed: bool = False
