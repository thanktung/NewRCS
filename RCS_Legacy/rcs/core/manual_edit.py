"""
manual_edit.py - Operator corrections while the system is NOT running.

When a worker removes / adds a board by hand (box, gripper head or input tray)
the software picture must be corrected before Start/Resume. These helpers are
used through Scheduler.manual_set_* (which checks that editing is allowed).
"""

from __future__ import annotations

import logging
from typing import Optional, TYPE_CHECKING

from ..models import BoardState, BoxState

if TYPE_CHECKING:                       # pragma: no cover
    from .scheduler import Scheduler

log = logging.getLogger("rcs.manual")


def set_box(s: "Scheduler", box_id: int, board_state: Optional[BoardState]) -> bool:
    """board_state None -> box empty; otherwise box holds a board in that state."""
    rec = s.box_record(box_id)
    if rec is None:
        return False
    if board_state is None:
        rec.set_state(BoxState.EMPTY)
        rec.board = None
        log.info("[MANUAL] Box%d -> EMPTY (board removed)", box_id)
    else:
        board = rec.board or s.new_manual_board(board_state)
        board.state = board_state
        rec.board = board
        rec.loaded_at = 0.0
        rec.set_state({BoardState.UNTESTED: BoxState.READY,
                       BoardState.PASS: BoxState.PASS,
                       BoardState.NG: BoxState.FAIL}[board_state])
        log.info("[MANUAL] Box%d -> %s (%s)", box_id, rec.state.value, board)
    return True


def set_gripper(s: "Scheduler", head_id: int, board_state: Optional[BoardState]) -> bool:
    if not 0 <= head_id < len(s.gripper.heads):
        return False
    head = s.gripper.heads[head_id]
    if board_state is None:
        head.board = None
        log.info("[MANUAL] Head%d -> empty", head_id)
    else:
        if head.board is None:
            head.board = s.new_manual_board(board_state)
        else:
            head.board.state = board_state
        log.info("[MANUAL] Head%d -> %s", head_id, head.board)
    return True


def set_tray_slot(s: "Scheduler", tray_id: int, slot: int,
                  board_state: Optional[BoardState]) -> bool:
    tray = s.tray_by_id(tray_id)
    if tray is None or not 0 <= slot < len(tray.slots):
        return False
    if board_state is None:
        tray.slots[slot] = None
        log.info("[MANUAL] Tray%d[%d] -> empty", tray_id, slot)
    else:
        board = tray.slots[slot]
        if board is None:
            board = s.new_manual_board(board_state)
            board.origin = (tray_id, slot)
        else:
            board.state = board_state
        tray.slots[slot] = board
        log.info("[MANUAL] Tray%d[%d] -> %s", tray_id, slot, board)
    return True
