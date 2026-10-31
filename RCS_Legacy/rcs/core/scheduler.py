"""
scheduler.py - Scheduling brain of the PCB test station.

Responsibilities (and ONLY these):
  * hold the model (trays, gripper, boxes, counters)
  * decide the next robot operations (plan)
  * execute them through the robot gateway and update the model (apply)
  * keep the life-cycle state machine (RUNNING / PAUSED / FAULT ...)

Sockets live in rcs/clients, wire formats in rcs/protocol, strategies in
policies.py, persistence / CSV / UI elsewhere. The scheduler gets its clients
from a factory, so tests run it with in-memory fakes.

Threading model
---------------
* ONE scheduler thread runs the cycles.
* Box listener threads call _on_box_state / _on_box_connection.
* The UI thread calls the public API (start / pause / snapshot / ...).
* `_lock` (RLock) protects the model. It is NEVER held while waiting for the
  robot, so snapshots and box pushes are never blocked by a slow command.
* `_cycle_lock` is held for the duration of a cycle; "is the scheduler thread
  really idle?" == "_cycle_lock is free".

Planning vs applying
--------------------
Every action is an _Op: (wire item, apply callback). _run_ops sends the items
(one command per op, or batched when enabled), and for every item the robot
confirms it calls apply() to move the board in the model. When the robot reports
ERR at batch item k, items < k are applied and the rest are not.
Any unexpected communication result raises _Fault -> state FAULT.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from ..clients.errors import (BoxError, RobotCommandError, RobotError)
from ..clients.factory import TcpClientFactory
from ..config import StationConfig
from ..models import (ACTIVE_STATES, Board, BoardState, BoxRecord, BoxState,
                      DONE_STATES, Gripper, SystemState as S, Tray)
from ..persistence import NullStore
from ..protocol import commands as C
from ..protocol import get_codec
from ..traceability import NullRecorder
from . import manual_edit
from .metrics import ActiveClock, pass_percent, rate_per_hour
from .policies import (BoxPriorityPolicy, FifoPriority, PlacePolicy,
                       make_place_policy)
from .snapshot import BoxView, HeadView, Snapshot
from .state_machine import StateMachine

log = logging.getLogger("rcs.scheduler")

_EMPTY_GUARD_SEC = 2.0     # ignore an "empty" push right after our own LOAD


class ControlError(Exception):
    """An operator action could not be performed (message is user-facing)."""


class _Fault(Exception):
    """Unwinds the current cycle and puts the scheduler into FAULT."""


class _Halt(Exception):
    """Unwinds the current cycle because pause/stop was requested."""


@dataclass
class _Op:
    item: tuple                                   # wire item, () for CHANGE
    apply: Callable[[], None]                     # update the model after success
    recover: dict = field(default_factory=dict)   # ERR code -> callback (no FAULT)


class Scheduler:
    def __init__(self, cfg: StationConfig, factory=None, *, store=None,
                 recorder=None, place_policy: Optional[PlacePolicy] = None,
                 priority: Optional[BoxPriorityPolicy] = None) -> None:
        self.cfg = cfg
        self.factory = factory or TcpClientFactory()
        self.store = store or NullStore()
        self.recorder = recorder or NullRecorder()
        self.place_policy = place_policy or make_place_policy(cfg.place_policy)
        self.priority = priority or FifoPriority()

        # locks / signalling
        self._lock = threading.RLock()
        self._ctl_lock = threading.RLock()
        self._cycle_lock = threading.Lock()
        self._wake = threading.Event()
        self._session_stop = threading.Event()
        self._listeners: list = []

        self.sm = StateMachine(self._on_state_change)
        self.clock = ActiveClock()

        # model
        self._board_counter = 1
        self._manual_id_counter = -1
        self.tray1 = Tray(1, cfg.tray_slots)
        self.tray2 = Tray(2, cfg.tray_slots)
        self._board_counter = self.tray1.prefill(self._board_counter)
        self._board_counter = self.tray2.prefill(self._board_counter)
        self.ng_list: list = []
        self.gripper = Gripper(cfg.gripper_heads)
        self.boxes = [BoxRecord(i) for i in range(1, cfg.box_count + 1)]
        self.stats = {"loaded": 0, "pass": 0, "ng": 0, "change": 0}

        # runtime
        self.robot = None
        self._box_clients: dict = {}
        self._loop_thread: Optional[threading.Thread] = None
        self._hb_thread: Optional[threading.Thread] = None
        self._fault: Optional[str] = None
        self._alerts: dict = {}
        self._robot_status = ""
        self._deferred_fault: Optional[str] = None
        self._ops_done = 0
        self._connect_started = 0.0

        # batching: chunk size of one robot command
        self._batch = False
        self._chunk = 1

    # ════════════════════════════════════════════
    # Observers
    # ════════════════════════════════════════════
    def add_listener(self, fn: Callable[[], None]) -> None:
        """fn() is called (from any thread) whenever the visible state changed.
        Keep it cheap: the UI just sets a dirty flag."""
        self._listeners.append(fn)

    def _notify(self) -> None:
        for fn in self._listeners:
            try:
                fn()
            except Exception:                                  # noqa: BLE001
                log.exception("listener failed")

    def _on_state_change(self, old: S, new: S, reason: str) -> None:
        log.info("STATE %s -> %s%s", old.value, new.value, f" ({reason})" if reason else "")
        if new == S.RUNNING:
            self.clock.start()
        else:
            self.clock.stop()
        self._wake.set()
        self._persist()
        self._notify()

    # ════════════════════════════════════════════
    # Model helpers (used by policies / manual edit)
    # ════════════════════════════════════════════
    def tray_by_id(self, tray_id: int) -> Optional[Tray]:
        return {1: self.tray1, 2: self.tray2}.get(tray_id)

    def box_record(self, box_id: int) -> Optional[BoxRecord]:
        return self.boxes[box_id - 1] if 1 <= box_id <= len(self.boxes) else None

    def new_manual_board(self, state: BoardState) -> Board:
        b = Board(self._manual_id_counter, state)
        self._manual_id_counter -= 1
        return b

    # ════════════════════════════════════════════
    # Alerts / faults
    # ════════════════════════════════════════════
    def _set_alert(self, key: str, msg: str) -> None:
        with self._lock:
            if self._alerts.get(key) == msg:
                return
            self._alerts[key] = msg
        log.warning("ALERT %s: %s", key, msg)
        self._notify()

    def _clear_alert(self, key: str) -> None:
        with self._lock:
            if self._alerts.pop(key, None) is None:
                return
        self._notify()

    def _enter_fault(self, msg: str) -> None:
        with self._lock:
            if self.sm.state in (S.FAULT, S.STOPPED):
                return
            self._fault = msg
        log.error("FAULT: %s", msg)
        self.sm.transition(S.FAULT, msg, strict=False)

    def _defer_fault(self, msg: str) -> None:
        """Remember a problem found inside an apply() callback; _run_ops raises
        it AFTER every apply() of the batch ran (model stays consistent)."""
        if self._deferred_fault is None:
            self._deferred_fault = msg

    def _raise_deferred(self) -> None:
        if self._deferred_fault is not None:
            msg, self._deferred_fault = self._deferred_fault, None
            raise _Fault(msg)

    def _request_pause(self, reason: str) -> None:
        log.warning("auto-pause: %s", reason)
        self.sm.transition(S.PAUSING, reason, strict=False)

    # ════════════════════════════════════════════
    # Connection life-cycle
    # ════════════════════════════════════════════
    def connect(self) -> None:
        """STOPPED -> IDLE. Raises RobotError if the robot is unreachable.
        Boxes connect in the background (a dead box does not block anything)."""
        with self._ctl_lock:
            if self.sm.state != S.STOPPED:
                return
            robot = self.factory.create_robot(self.cfg)
            log.info("connecting robot %s:%d (protocol=%s)",
                     self.cfg.robot_host, self.cfg.robot_port, self.cfg.protocol)
            robot.connect()
            self.robot = robot
            self._batch = bool(self.cfg.batch_enabled and robot.supports_batch)
            self._chunk = self.cfg.batch_max_items if self._batch else 1
            if self.cfg.batch_enabled and not robot.supports_batch:
                log.warning("batch requested but protocol does not support it")

            self._session_stop.clear()
            self._deferred_fault = None
            self._fault = None
            with self._lock:
                for rec in self.boxes:
                    rec.connected = False
                    rec.set_state(BoxState.UNKNOWN)
            self._connect_started = time.monotonic()
            self._box_clients = {}
            for rec in self.boxes:
                client = self.factory.create_box(rec.box_id, self.cfg)
                self._box_clients[rec.box_id] = client
                client.start(self._on_box_state, self._on_box_connection)
            self.sm.transition(S.IDLE, "connected")

            self._loop_thread = threading.Thread(
                target=self._loop, name="scheduler-loop", daemon=True)
            self._loop_thread.start()
            if self.cfg.heartbeat_interval > 0:
                if get_codec(self.cfg.protocol).SUPPORTS_SEQ:
                    self._hb_thread = threading.Thread(
                        target=self._heartbeat_loop, name="robot-heartbeat", daemon=True)
                    self._hb_thread.start()
                else:
                    log.warning("heartbeat needs protocol v2 - ignored")

    def _shutdown(self, emergency: bool) -> None:
        self._session_stop.set()
        self._wake.set()
        if emergency and self.robot is not None:
            self.robot.close()              # cancels the in-flight wait at once
        for t in (self._loop_thread, self._hb_thread):
            if t is not None and t is not threading.current_thread():
                t.join(timeout=self.cfg.robot_done_timeout + 5.0)
        self._loop_thread = self._hb_thread = None
        for client in self._box_clients.values():
            client.stop()
        self._box_clients = {}
        if self.robot is not None:
            self.robot.close()
        with self._lock:
            for rec in self.boxes:
                rec.connected = False
                rec.set_state(BoxState.UNKNOWN)
        self.sm.transition(S.STOPPED, "shutdown", strict=False)

    def stop(self) -> None:
        """Graceful: the robot command in progress is finished, then everything
        is disconnected. State -> STOPPED."""
        with self._ctl_lock:
            if self.sm.state == S.STOPPED:
                return
            self._shutdown(emergency=False)

    def emergency_stop(self) -> None:
        """Immediate: sockets are closed even in the middle of a robot command.
        The physical state is then UNKNOWN - check it before Start."""
        with self._ctl_lock:
            if self.sm.state == S.STOPPED:
                return
            log.error("EMERGENCY STOP requested")
            self._shutdown(emergency=True)

    # ════════════════════════════════════════════
    # Operator controls
    # ════════════════════════════════════════════
    def start(self) -> None:
        """Connect if needed, then run. Also used as Resume."""
        with self._ctl_lock:
            if self.sm.state == S.STOPPED:
                self.connect()
            if self.sm.state == S.FAULT:
                raise ControlError("System is in FAULT - acknowledge the fault first.")
            self.sm.transition(S.RUNNING, "start")

    resume = start

    def pause(self) -> None:
        """Graceful pause: the robot command in progress is finished."""
        with self._ctl_lock:
            self.sm.transition(S.PAUSING, "pause", strict=False)
            self._wake.set()

    def acknowledge_fault(self) -> None:
        """FAULT -> PAUSED. Re-opens the robot link (so no stale reply can
        leak in) and, on protocol v2, clears the robot alarm with RESET.
        The operator should first correct the model with manual edit."""
        with self._ctl_lock:
            if self.sm.state != S.FAULT:
                return
            if self.robot is not None:
                self.robot.close()               # wakes any command still waiting
            if not self._cycle_lock.acquire(timeout=self.cfg.robot_done_timeout + 5):
                raise ControlError("Scheduler thread did not stop - try Emergency Stop.")
            try:
                self._deferred_fault = None
                try:
                    self.robot.reconnect()
                    if get_codec(self.cfg.protocol).SUPPORTS_SEQ:
                        status = self.robot.query_status()
                        if status in (C.ROBOT_ALARM, C.ROBOT_ESTOP):
                            self.robot.execute(C.reset())
                            status = self.robot.query_status()
                        self._robot_status = status
                        if status in (C.ROBOT_ALARM, C.ROBOT_ESTOP):
                            raise ControlError(f"Robot still reports {status}.")
                except RobotError as e:
                    raise ControlError(f"Cannot re-connect to robot: {e}") from e
                self._fault = None
                self.sm.transition(S.PAUSED, "fault acknowledged")
            finally:
                self._cycle_lock.release()

    def clear_ng_tray(self) -> None:
        """Operator emptied the NG tray."""
        with self._lock:
            self.ng_list.clear()
        self._clear_alert("ng_full")
        log.info("NG tray cleared by operator")
        self._persist()
        self._notify()

    # ── enable / disable (any time) ─────────────
    def set_box_enabled(self, box_id: int, enabled: bool) -> bool:
        rec = self.box_record(box_id)
        if rec is None:
            return False
        with self._lock:
            rec.enabled = enabled
            if enabled:
                rec.fail_streak = 0
                self._clear_alert(f"box{box_id}_disabled")
        log.info("[CONFIG] Box%d -> %s", box_id, "ENABLED" if enabled else "DISABLED")
        self._wake.set()
        self._persist()
        self._notify()
        return True

    def set_head_enabled(self, head_id: int, enabled: bool) -> bool:
        if not 0 <= head_id < len(self.gripper.heads):
            return False
        with self._lock:
            self.gripper.heads[head_id].enabled = enabled
        log.info("[CONFIG] Head%d -> %s", head_id, "ENABLED" if enabled else "DISABLED")
        self._wake.set()
        self._persist()
        self._notify()
        return True

    # ── manual edit (only while not running) ────
    def manual_edit_allowed(self) -> bool:
        return (self.sm.state in (S.STOPPED, S.IDLE, S.PAUSED, S.FAULT)
                and not self._cycle_lock.locked())

    def _manual(self, fn, *args) -> bool:
        if not self.manual_edit_allowed():
            return False
        with self._lock:
            ok = fn(self, *args)
        if ok:
            self._persist()
            self._notify()
        return ok

    def manual_set_box(self, box_id: int, board_state) -> bool:
        return self._manual(manual_edit.set_box, box_id, board_state)

    def manual_set_gripper(self, head_id: int, board_state) -> bool:
        return self._manual(manual_edit.set_gripper, head_id, board_state)

    def manual_set_tray_slot(self, tray_id: int, slot: int, board_state) -> bool:
        return self._manual(manual_edit.set_tray_slot, tray_id, slot, board_state)

    # ════════════════════════════════════════════
    # Box callbacks (box listener threads)
    # ════════════════════════════════════════════
    def _on_box_state(self, box_id: int, state: BoxState) -> None:
        rec = self.box_record(box_id)
        if rec is None:
            return
        with self._lock:
            rec.connected = True
            changed = rec.set_state(state)
            # A box that reports EMPTY while we think it holds a board: the
            # board was removed by hand (ignore the echo of our own UNLOAD/LOAD).
            if (state == BoxState.EMPTY and rec.board is not None
                    and time.monotonic() - rec.loaded_at > _EMPTY_GUARD_SEC):
                lost = rec.board
                rec.board = None
                self._set_alert(f"box{box_id}_lost",
                                f"Box{box_id} reports EMPTY but software had {lost} inside")
        self._clear_alert(f"box{box_id}_conn")
        if changed:
            log.info("[PUSH] box%d -> %s", box_id, state.value)
            self._wake.set()
            self._notify()

    def _on_box_connection(self, box_id: int, up: bool) -> None:
        rec = self.box_record(box_id)
        if rec is None:
            return
        with self._lock:
            rec.connected = up
            if not up:
                rec.set_state(BoxState.UNKNOWN)
        if up:
            self._clear_alert(f"box{box_id}_conn")
        else:
            self._set_alert(f"box{box_id}_conn", f"Box{box_id} connection lost")
        self._wake.set()
        self._notify()

    # ════════════════════════════════════════════
    # Heartbeat (protocol v2)
    # ════════════════════════════════════════════
    def _heartbeat_loop(self) -> None:
        interval = self.cfg.heartbeat_interval
        while not self._session_stop.wait(interval):
            if self.sm.state in (S.STOPPED, S.FAULT):
                continue
            try:
                status = self.robot.query_status()
            except RobotError as e:
                self._robot_status = ""
                if self.sm.state in (S.RUNNING, S.PAUSING):
                    self._enter_fault(f"Robot heartbeat lost: {e}")
                continue
            self._robot_status = status
            if status in (C.ROBOT_ALARM, C.ROBOT_ESTOP):
                self._enter_fault(f"Robot reports {status}")
            self._notify()

    # ════════════════════════════════════════════
    # Main loop
    # ════════════════════════════════════════════
    def _loop(self) -> None:
        log.info("scheduler loop started")
        try:
            while not self._session_stop.is_set():
                st = self.sm.state
                if st == S.RUNNING:
                    before = self._ops_done
                    with self._cycle_lock:
                        try:
                            self._run_cycle()
                        except _Halt:
                            pass
                        except _Fault as f:
                            self._enter_fault(str(f))
                        except Exception as e:                          # noqa: BLE001
                            log.exception("unexpected error in cycle")
                            self._enter_fault(f"Unexpected error: {e!r}")
                    if self._ops_done != before:
                        continue                     # made progress -> go again at once
                elif st == S.PAUSING:
                    self.sm.transition(S.PAUSED, "pause complete", strict=False)
                    continue
                self._wake.wait(self.cfg.poll_interval)
                self._wake.clear()
        finally:
            log.info("scheduler loop ended")

    def _checkpoint(self) -> None:
        """Called BEFORE every robot command (never in the middle of one)."""
        if self._session_stop.is_set() or self.sm.state != S.RUNNING:
            raise _Halt()

    def _run_cycle(self) -> None:
        self._checkpoint()
        self._refill_gripper()                  # 1. pick UNTESTED into free heads
        self._process_boxes()                   # 2. unload DONE / load EMPTY boxes
        self._place_all_tested()                # 3. return tested boards
        with self._lock:
            change_now = self.place_policy.can_change(self)
        if change_now:
            self._do_change()                   # 4. swap trays
        self._refill_gripper()                  # 5. refill heads freed in 2-4
        self._load_empty_boxes()                # 6. fill boxes skipped earlier
        self._refill_gripper()
        self._check_watchdog()
        self._notify()

    # ════════════════════════════════════════════
    # Op execution
    # ════════════════════════════════════════════
    def _run_ops(self, name: str, ops: list) -> int:
        """Execute ops through the robot. Returns how many succeeded."""
        done_total = 0
        for i in range(0, len(ops), self._chunk):
            self._checkpoint()
            chunk = ops[i:i + self._chunk]
            cmd = C.RobotCommand(name, tuple(o.item for o in chunk if o.item))
            failure: Optional[RobotCommandError] = None
            try:
                self.robot.execute(cmd)
            except RobotCommandError as e:
                failure = e
            except RobotError as e:
                if self._session_stop.is_set():
                    raise _Halt() from e         # link closed by stop / emergency stop
                raise _Fault(
                    f"Robot {cmd} failed: {e}. Physical state unknown - check the "
                    f"station, correct it with manual edit, then acknowledge."
                ) from e

            n_ok = len(chunk) if failure is None else max(0, min(failure.index, len(chunk)))
            for op in chunk[:n_ok]:
                op.apply()                   # locks internally, box calls outside the lock
            self._ops_done += n_ok
            done_total += n_ok
            self._persist()
            self._raise_deferred()

            if failure is not None:
                failed_op = chunk[n_ok] if n_ok < len(chunk) else None
                handler = failed_op.recover.get(failure.code) if failed_op else None
                if handler is None:
                    raise _Fault(f"Robot refused {cmd}: {failure.code} "
                                 f"(item {failure.index})") from failure
                log.warning("robot %s item %d: %s (recovered)", name,
                            failure.index, failure.code)
                handler()
                self._persist()
                return done_total         # re-plan on the next cycle
        return done_total

    # ════════════════════════════════════════════
    # PICK
    # ════════════════════════════════════════════
    def _plan_pick_slots(self, n: int) -> list:
        """(tray_id, slot) of the next n UNTESTED boards: tray 1 first."""
        picks = []
        for tray in (self.tray1, self.tray2):
            for i, b in enumerate(tray.slots):
                if len(picks) >= n:
                    return picks
                if b is not None and b.state == BoardState.UNTESTED:
                    picks.append((tray.tray_id, i))
        return picks

    def _refill_gripper(self) -> None:
        """Pick UNTESTED boards into free heads, always leaving `reserve` heads
        free so a finished box can always be unloaded (no deadlock).

        Non-batch: reserve = 1. Batch: reserve = number of finished boxes, so
        one UNLOAD batch can take them all.
        """
        with self._lock:
            reserve = 1
            if self._batch:
                reserve = max(1, sum(1 for r in self.boxes
                                     if r.enabled and r.state in DONE_STATES))
            free = self.gripper.empty_heads()
            n = max(0, len(free) - reserve)
            picks = self._plan_pick_slots(n)
            ops = []
            for (tray_id, slot), head in zip(picks, free):
                ops.append(_Op((tray_id, slot, head),
                               self._apply_pick(tray_id, slot, head),
                               recover={C.ErrorCode.NO_PART:
                                        self._recover_no_part(tray_id, slot)}))
        if ops:
            self._run_ops(C.PICK, ops)

    def _apply_pick(self, tray_id: int, slot: int, head: int):
        def apply() -> None:
            with self._lock:
                tray = self.tray_by_id(tray_id)
                board = tray.slots[slot]
                board.origin = (tray_id, slot)
                self.gripper.heads[head].board = board
                tray.slots[slot] = None
            log.info("  PICK tray%d[%d] -> head%d (%s)", tray_id, slot, head, board)
        return apply

    def _recover_no_part(self, tray_id: int, slot: int):
        def recover() -> None:
            with self._lock:
                tray = self.tray_by_id(tray_id)
                lost = tray.slots[slot]
                tray.slots[slot] = None
            self._set_alert(f"nopart_{tray_id}_{slot}",
                            f"Tray{tray_id}[{slot}]: robot found no part (software had {lost})")
        return recover

    # ════════════════════════════════════════════
    # LOAD / UNLOAD
    # ════════════════════════════════════════════
    def _choose_head(self, rec: BoxRecord, heads: list) -> Optional[int]:
        """Head holding an UNTESTED board that has not been tested in this box
        yet (so a board that failed here is re-tested in ANOTHER box).
        None -> nothing suitable for this box right now."""
        for h in heads:
            if rec.box_id not in self.gripper.heads[h].board.tested_in:
                return h
        return None

    def _plan_loads(self, recs: list) -> list:
        heads = list(self.gripper.untested_heads())
        ops = []
        for rec in recs:
            if not heads:
                break
            head = self._choose_head(rec, heads)
            if head is None:
                continue
            heads.remove(head)
            ops.append(_Op((rec.box_id, head), self._apply_load(rec, head)))
        return ops

    def _apply_load(self, rec: BoxRecord, head: int):
        def apply() -> None:
            with self._lock:
                h = self.gripper.heads[head]
                board, h.board = h.board, None
                rec.board = board
                rec.loaded_at = time.monotonic()
                self.stats["loaded"] += 1
            log.info("  LOAD box%d <- head%d (%s)", rec.box_id, head, board)
            # The box call is made WITHOUT the lock: the box listener thread needs
            # the lock for state pushes and also delivers our response.
            if self._box_call(rec, "load"):
                with self._lock:
                    rec.set_state(BoxState.READY)  # optimistic; the box push confirms
        return apply

    def _plan_unloads(self, recs: list) -> list:
        free = list(self.gripper.empty_heads())
        ops = []
        for rec in recs:
            if not free:
                break
            head = free.pop(0)
            ops.append(_Op((rec.box_id, head), self._apply_unload(rec, rec.state, head)))
        return ops

    def _apply_unload(self, rec: BoxRecord, result: BoxState, head: int):
        def apply() -> None:
            auto_disabled = False
            with self._lock:
                board = rec.board or self.new_manual_board(BoardState.UNTESTED)
                rec.board = None
                was_retest = board.retested
                passed = result == BoxState.PASS
                board.tested_in.append(rec.box_id)

                if passed:
                    board.state = BoardState.PASS
                elif (self.cfg.retest_ng and not board.retested
                      and self._other_box_usable(rec.box_id)):
                    board.retested = True        # stays UNTESTED -> goes to another box
                    log.info("  RETEST scheduled for %s (failed in box%d)",
                             board, rec.box_id)
                else:
                    board.state = BoardState.NG
                self.gripper.heads[head].board = board

                rec.tested += 1
                if passed:
                    rec.passed += 1
                    rec.fail_streak = 0
                else:
                    rec.fail_streak += 1
                limit = self.cfg.box_fail_streak_limit
                if limit and rec.fail_streak >= limit and rec.enabled:
                    rec.enabled = False
                    auto_disabled = True
                origin = board.origin or (None, None)
                test_sec = (round(time.monotonic() - rec.loaded_at, 1)
                            if rec.loaded_at else "")
                streak = rec.fail_streak

            if auto_disabled:
                self._set_alert(f"box{rec.box_id}_disabled",
                                f"Box{rec.box_id} auto-disabled after {streak} "
                                f"consecutive failures")
            self.recorder.record({
                "board_id": board.board_id, "box_id": rec.box_id, "head": head,
                "result": result.value.upper(), "origin_tray": origin[0],
                "origin_slot": origin[1], "retest": int(was_retest),
                "test_seconds": test_sec,
            })
            log.info("  UNLOAD box%d -> head%d (%s)", rec.box_id, head, board)
            if self._box_call(rec, "unload"):
                with self._lock:
                    rec.set_state(BoxState.EMPTY)
        return apply

    def _other_box_usable(self, box_id: int) -> bool:
        return any(r.box_id != box_id and r.enabled and r.connected
                   and r.state != BoxState.UNKNOWN for r in self.boxes)

    def _box_call(self, rec: BoxRecord, what: str) -> bool:
        """Tell the box about a LOAD/UNLOAD the robot just did. A refusal means
        software and fixture disagree -> deferred FAULT."""
        client = self._box_clients.get(rec.box_id)
        try:
            resp = getattr(client, what)()
        except (BoxError, AttributeError) as e:
            self._defer_fault(f"Box{rec.box_id} {what.upper()} failed: {e}")
            return False
        if resp != "OK":
            self._defer_fault(f"Box{rec.box_id} answered '{resp}' to {what.upper()} "
                              f"after the robot already did it - check the fixture")
            return False
        return True

    def _load_empty_boxes(self) -> None:
        with self._lock:
            empties = [r for r in self.priority.order(self.boxes)
                       if r.state == BoxState.EMPTY and r.board is None]
            ops = self._plan_loads(empties)
        if ops:
            self._run_ops(C.LOAD, ops)

    # ════════════════════════════════════════════
    # Box processing
    # ════════════════════════════════════════════
    def _process_boxes(self) -> None:
        if self._batch:
            self._process_boxes_batched()
        else:
            self._process_boxes_serial()

    def _process_boxes_serial(self) -> None:
        """One box at a time: EMPTY -> load; DONE -> unload then load at once
        (the robot is already at that box)."""
        with self._lock:
            order = [r.box_id for r in self.priority.order(self.boxes)]
        for box_id in order:
            rec = self.boxes[box_id - 1]
            with self._lock:
                state, enabled = rec.state, rec.enabled
            if not enabled:
                continue
            if state == BoxState.EMPTY and rec.board is None:
                with self._lock:
                    ops = self._plan_loads([rec])
                if ops:
                    self._run_ops(C.LOAD, ops)
            elif state in DONE_STATES:
                with self._lock:
                    free = self.gripper.empty_heads()
                if not free:
                    # No free head: flush tested boards, refill, load idle boxes
                    self._place_all_tested()
                    self._refill_gripper()
                    self._load_empty_boxes()
                    with self._lock:
                        free = self.gripper.empty_heads()
                    if not free:
                        log.debug("  no free head to unload box%d", box_id)
                        continue
                with self._lock:
                    ops = self._plan_unloads([rec])
                if not ops or self._run_ops(C.UNLOAD, ops) == 0:
                    continue
                with self._lock:
                    ops = self._plan_loads([rec])
                if ops:
                    self._run_ops(C.LOAD, ops)

    def _process_boxes_batched(self) -> None:
        """Batch mode: UNLOAD all finished boxes in one command, then LOAD all
        empty boxes in one command (robot decides the travel order)."""
        for _ in range(10):                          # bounded: no endless loop
            with self._lock:
                done = [r for r in self.priority.order(self.boxes)
                        if r.state in DONE_STATES]
            if not done:
                break
            with self._lock:
                free = self.gripper.empty_heads()
            if not free:
                self._place_all_tested()
                self._refill_gripper()
                with self._lock:
                    free = self.gripper.empty_heads()
                if not free:
                    log.debug("  no free head to unload %d finished boxes", len(done))
                    break
            with self._lock:
                ops = self._plan_unloads(done)
            if not ops or self._run_ops(C.UNLOAD, ops) == 0:
                break
            self._load_empty_boxes()
        self._load_empty_boxes()

    # ════════════════════════════════════════════
    # PLACE
    # ════════════════════════════════════════════
    def _place_all_tested(self) -> None:
        with self._lock:
            reserved: set = set()
            ng_planned = 0
            ng_full = False
            ops = []
            for hid in self.gripper.tested_heads():
                board = self.gripper.heads[hid].board
                if board.state == BoardState.PASS:
                    dest = self.place_policy.pass_slot(self, board, reserved)
                    if dest is None:
                        log.info("  [WAIT] no room for %s on head%d (waits for CHANGE)",
                                 board, hid)
                        continue
                    reserved.add(dest)
                    ops.append(_Op((dest[0], dest[1], hid),
                                   self._apply_place_pass(dest, hid)))
                else:
                    slot = len(self.ng_list) + ng_planned
                    if slot >= self.cfg.ng_tray_slots:
                        self._set_alert("ng_full",
                                        "NG tray is FULL - empty it, press 'NG tray emptied', "
                                        "then Resume")
                        ng_full = True
                        continue
                    ng_planned += 1
                    ops.append(_Op((0, slot, hid), self._apply_place_ng(hid)))
        if ops:
            self._run_ops(C.PLACE, ops)          # place what fits first ...
        if ng_full:
            self._request_pause("NG tray full")  # ... then wait for the operator

    def _apply_place_pass(self, dest: tuple, head: int):
        def apply() -> None:
            with self._lock:
                tray = self.tray_by_id(dest[0])
                h = self.gripper.heads[head]
                tray.slots[dest[1]] = h.board
                h.board = None
                self.stats["pass"] += 1
            log.info("  PLACE head%d -> tray%d[%d] (PASS)", head, dest[0], dest[1])
        return apply

    def _apply_place_ng(self, head: int):
        def apply() -> None:
            with self._lock:
                h = self.gripper.heads[head]
                n = len(self.ng_list)
                self.ng_list.append(h.board)
                h.board = None
                self.stats["ng"] += 1
            log.info("  PLACE head%d -> NG_TRAY[%d] (NG)", head, n)
        return apply

    # ════════════════════════════════════════════
    # CHANGE
    # ════════════════════════════════════════════
    def _do_change(self) -> None:
        log.info("[CHANGE] tray 1 finished and nothing in flight -> swapping trays")
        self._run_ops(C.CHANGE, [_Op((), self._apply_change)])

    def _apply_change(self) -> None:
        with self._lock:
            self.tray1 = Tray(1, self.cfg.tray_slots, list(self.tray2.slots))
            self.tray2 = Tray(2, self.cfg.tray_slots)
            self._board_counter = self.tray2.prefill(self._board_counter)
            # Boards in flight that came from the old tray 2 now belong to tray 1
            in_flight = [h.board for h in self.gripper.heads if h.board]
            in_flight += [r.board for r in self.boxes if r.board]
            in_flight += [b for b in self.tray1.slots if b]       # tray that just moved
            for b in in_flight:
                if b.origin and b.origin[0] == 2:
                    b.origin = (1, b.origin[1])
            self.stats["change"] += 1
            first = self._board_counter - self.cfg.tray_slots
        log.info("[CHANGE] done. tray1 <- old tray2, tray2 <- new UNTESTED (B%d-B%d)",
                 first, self._board_counter - 1)

    # ════════════════════════════════════════════
    # Watchdog
    # ════════════════════════════════════════════
    def _check_watchdog(self) -> None:
        now = time.monotonic()
        cfg = self.cfg
        with self._lock:
            recs = list(self.boxes)
        for rec in recs:
            key = f"box{rec.box_id}_watchdog"
            limit = {BoxState.TESTING: cfg.test_timeout_sec,
                     BoxState.READY: cfg.ready_timeout_sec}.get(rec.state, 0.0)
            age = now - rec.state_since
            if rec.enabled and limit > 0 and age > limit:
                self._set_alert(key, f"Box{rec.box_id} has been '{rec.state.value}' "
                                     f"for {age:.0f}s (limit {limit:.0f}s)")
            else:
                self._clear_alert(key)
            if not rec.connected and now - self._connect_started > 10.0:
                self._set_alert(f"box{rec.box_id}_conn", f"Box{rec.box_id} not connected")

    # ════════════════════════════════════════════
    # Persistence
    # ════════════════════════════════════════════
    @staticmethod
    def _board_to_dict(b: Optional[Board]) -> Optional[dict]:
        if b is None:
            return None
        return {"id": b.board_id, "state": b.state.value,
                "origin": list(b.origin) if b.origin else None,
                "retested": b.retested, "tested_in": list(b.tested_in)}

    @staticmethod
    def _board_from_dict(d: Optional[dict]) -> Optional[Board]:
        if d is None:
            return None
        return Board(d["id"], BoardState(d["state"]),
                     tuple(d["origin"]) if d.get("origin") else None,
                     d.get("retested", False), list(d.get("tested_in", [])))

    def export_state(self) -> dict:
        with self._lock:
            bd = self._board_to_dict
            return {
                "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "board_counter": self._board_counter,
                "manual_id_counter": self._manual_id_counter,
                "active_seconds": self.clock.elapsed(),
                "stats": dict(self.stats),
                "tray1": [bd(b) for b in self.tray1.slots],
                "tray2": [bd(b) for b in self.tray2.slots],
                "ng": [bd(b) for b in self.ng_list],
                "gripper": [{"board": bd(h.board), "enabled": h.enabled}
                            for h in self.gripper.heads],
                "boxes": [{"board": bd(r.board), "enabled": r.enabled,
                           "tested": r.tested, "passed": r.passed,
                           "fail_streak": r.fail_streak} for r in self.boxes],
            }

    def restore_state(self, data: dict) -> None:
        """Load a snapshot produced by export_state(). Only while not running."""
        if not self.manual_edit_allowed():
            raise ControlError("Cannot restore while the scheduler is running.")
        fb = self._board_from_dict
        with self._lock:
            n = self.cfg.tray_slots
            for tray, key in ((self.tray1, "tray1"), (self.tray2, "tray2")):
                slots = [fb(d) for d in data[key]][:n]
                tray.slots = slots + [None] * (n - len(slots))
            self.ng_list = [fb(d) for d in data.get("ng", [])]
            for h, d in zip(self.gripper.heads, data.get("gripper", [])):
                h.board, h.enabled = fb(d["board"]), d.get("enabled", True)
            for r, d in zip(self.boxes, data.get("boxes", [])):
                r.board, r.enabled = fb(d["board"]), d.get("enabled", True)
                r.tested, r.passed = d.get("tested", 0), d.get("passed", 0)
                r.fail_streak = d.get("fail_streak", 0)
            self.stats.update(data.get("stats", {}))
            self._board_counter = data.get("board_counter", self._board_counter)
            self._manual_id_counter = data.get("manual_id_counter", self._manual_id_counter)
            self.clock.reset(data.get("active_seconds", 0.0))
        log.info("state restored (saved %s)", data.get("saved_at"))
        self._notify()

    def _persist(self) -> None:
        try:
            self.store.save(self.export_state())
        except Exception:                                      # noqa: BLE001
            log.exception("cannot save station state")

    # ════════════════════════════════════════════
    # Snapshot for the UI
    # ════════════════════════════════════════════
    def snapshot(self) -> Snapshot:
        with self._lock:
            now = time.monotonic()
            elapsed = self.clock.elapsed()
            boxes, tested_total, pass_total = [], 0, 0
            for r in self.boxes:
                tested_total += r.tested
                pass_total += r.passed
                boxes.append(BoxView(
                    r.box_id, r.state, r.board, r.enabled, r.connected,
                    now - r.state_since, r.tested, r.passed, r.fail_streak,
                    rate_per_hour(r.tested, elapsed), pass_percent(r.passed, r.tested)))
            return Snapshot(
                system_state=self.sm.state,
                fault=self._fault,
                alerts=dict(self._alerts),
                mode=self.cfg.mode,
                protocol=self.cfg.protocol,
                batch=self._batch,
                station_name=self.cfg.station_name,
                robot_connected=bool(self.robot and self.robot.connected),
                robot_status=self._robot_status,
                boxes=boxes,
                heads=[HeadView(h.head_id, h.board, h.enabled) for h in self.gripper.heads],
                tray1=list(self.tray1.slots),
                tray2=list(self.tray2.slots),
                ng_count=len(self.ng_list),
                ng_capacity=self.cfg.ng_tray_slots,
                stats=dict(self.stats),
                system_metrics={
                    "tested": tested_total, "pass": pass_total,
                    "rate_per_hour": rate_per_hour(tested_total, elapsed),
                    "pass_pct": pass_percent(pass_total, tested_total),
                    "elapsed_sec": elapsed,
                },
                manual_edit_allowed=self.manual_edit_allowed(),
            )





