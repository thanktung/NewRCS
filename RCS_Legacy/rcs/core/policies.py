"""
policies.py - Pluggable scheduling decisions.

Two extension points, each a small class:

PlacePolicy        where a tested PASS board goes, and when to CHANGE trays.
BoxPriorityPolicy  in which order boxes are served.

Add a new strategy = add a class here and register it in PLACE_POLICIES /
the Scheduler constructor. The Scheduler core does not change.

Policies only READ the scheduler (they must not mutate it) and are always
called with the scheduler lock held.
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from ..models import ACTIVE_STATES, BoardState, BoxRecord, DONE_STATES, BoxState

if TYPE_CHECKING:                       # pragma: no cover
    from .scheduler import Scheduler


# ────────────────────────────────────────────
# Place policies
# ────────────────────────────────────────────
class PlacePolicy:
    name = "base"

    def pass_slot(self, s: "Scheduler", board, reserved: set) -> Optional[tuple]:
        """Return (tray_id, slot) for a PASS board, or None if there is no room
        right now. `reserved` = (tray_id, slot) pairs already planned in the
        same batch (must not be returned again)."""
        raise NotImplementedError

    def can_change(self, s: "Scheduler") -> bool:
        """True when trays may be swapped (CHANGE)."""
        raise NotImplementedError

    # helper shared by policies
    @staticmethod
    def _blocked_by_flight(s: "Scheduler") -> bool:
        """True while some board is still being tested / about to be tested."""
        if s.gripper.untested_heads():
            return True
        return any(r.enabled and r.state in ACTIVE_STATES for r in s.boxes)


class Tray1Policy(PlacePolicy):
    """PASS boards go to the first empty slot of tray 1 (original behaviour).

    CHANGE when tray 1 has nothing left to pick and nothing is in flight.

    A PASS board that cannot be placed because tray 1 is full does NOT block
    CHANGE: it waits on its head and is placed into the new tray 1 afterwards.
    (The old code blocked CHANGE on any tested head -> permanent deadlock.)
    """
    name = "tray1"

    def pass_slot(self, s, board, reserved):
        for i, b in enumerate(s.tray1.slots):
            if b is None and (1, i) not in reserved:
                return (1, i)
        return None

    def can_change(self, s):
        if s.tray1.untested_count() > 0:
            return False
        if self._blocked_by_flight(s):
            return False
        for hid in s.gripper.tested_heads():
            board = s.gripper.heads[hid].board
            if board.state == BoardState.NG:
                return False          # NG waits for NG tray space, not for CHANGE
            # PASS on a head: placeable now -> not our business to CHANGE yet
            if s.tray1.has_empty():
                return False
        return True


class OriginPolicy(PlacePolicy):
    """Every PASS board returns to the exact slot it was picked from.

    No slot-contention at all, so tray 1 can never be "full" while boards are
    in flight. CHANGE when no board that came from tray 1 is still outside it.
    """
    name = "origin"

    def pass_slot(self, s, board, reserved):
        if board.origin is not None:
            tray_id, slot = board.origin
            tray = s.tray_by_id(tray_id)
            if tray is not None and tray.slots[slot] is None \
                    and (tray_id, slot) not in reserved:
                return board.origin
        # Manual / unknown origin -> any free slot of tray 1
        return Tray1Policy().pass_slot(s, board, reserved)

    def can_change(self, s):
        if s.tray1.untested_count() > 0:
            return False
        if self._blocked_by_flight(s):
            return False
        for h in s.gripper.heads:
            if h.board and h.board.origin and h.board.origin[0] == 1 \
                    and h.board.state != BoardState.NG:
                return False
        for r in s.boxes:
            if r.board and r.board.origin and r.board.origin[0] == 1:
                return False
        return True


PLACE_POLICIES = {Tray1Policy.name: Tray1Policy, OriginPolicy.name: OriginPolicy}


def make_place_policy(name: str) -> PlacePolicy:
    try:
        return PLACE_POLICIES[name]()
    except KeyError:
        raise ValueError(f"unknown place policy '{name}'") from None


# ────────────────────────────────────────────
# Box priority
# ────────────────────────────────────────────
class BoxPriorityPolicy:
    """Order in which actionable boxes are served."""

    def order(self, boxes: list) -> list:
        raise NotImplementedError


class FifoPriority(BoxPriorityPolicy):
    """Serve the box that has been waiting longest first (EMPTY or DONE).

    The old code always walked box 1..N, so the last boxes could starve when the
    robot was the bottleneck.
    """

    def order(self, boxes):
        actionable = [r for r in boxes
                      if r.enabled and (r.state == BoxState.EMPTY
                                        or r.state in DONE_STATES)]
        return sorted(actionable, key=lambda r: (r.state_since, r.box_id))
