"""Robot operations of the operator: start / stop the robot program (UOP), manual motion, safe position, teach points.

Every manual motion arms the bridge only for that one command and disarms right after; all of them need the robot
program to be running (UO[3]) except the sequence that starts it.
"""
import os

from ..core.sequence import save_sequences
from ..robot.client import RobotError
from ..robot.uop import RobotStarter


class RobotOpsMixin:
    # ---- manual control (jog / go to point / teach) -------------------- #
    # Every manual motion arms the bridge only for that one command and disarms right after.
    # Refused while a run is active or a robot job is running.
    def _manual_guard(self):
        snap = self.engine.snapshot()
        if snap["run_state"] == "RUNNING" or snap["current_job"]:
            raise RobotError("BUSY", "hãy dừng chạy (và đợi robot xong việc) trước")
        if not self.bridge.connected:
            raise ConnectionError("chưa kết nối bridge robot")

    def _manual_motion(self, fn, needs_program=True):
        """Runs `fn` with the bridge armed for that one command. Every robot operation needs the robot program to be running
        (UO[3] PROGRUN); only the sequence that starts the program passes `needs_program=False`."""
        if not self._manual_lock.acquire(False):
            raise RobotError("BUSY", "đang có một chuyển động thủ công khác")
        try:
            self._manual_guard()
            if needs_program:
                self._need_program_running()
            self.bridge.arm()
            try:
                return fn()
            finally:
                try:
                    self.bridge.disarm()
                except Exception:
                    pass
        finally:
            self._manual_lock.release()

    @property
    def manual_busy(self):
        return self._manual_lock.locked()

    def manual_override(self):
        return self.cfg["bridge"].get("default_override")

    def robot_start_program(self):
        """Start the robot program (RSR0001) through the UOP signals: SDI[1-3, 8] on, pulse RSR select, pulse RESET and
        check UO[6] FAULT, pulse START and check UO[3] PROGRUN (see rcs2/robot/uop.py). Refused while a run / robot job is
        active. Blocking (a few seconds): call from a worker thread."""
        starter = RobotStarter(self.bridge, self.cfg.get("robot_start"), log_fn=self._log_manual, abort=self._uop_abort)
        self._uop_abort.clear()                                   # a stop pressed earlier must not cancel this start
        self._log_manual("khởi động chương trình %s" % starter.program)

        def run():
            return starter.start()
        if (self.bridge.last_status or {}).get("fault"):          # R[1] < 0 would make the bridge refuse the arm
            try:
                self.bridge.fault_clear()
            except Exception as ex:
                self._log_manual("fault.clear: %s" % ex)
        try:
            result = self._manual_motion(run, needs_program=False)      # it starts the program: it cannot need it running
        finally:
            self._refresh_program_state()
        self._log_manual(result)
        return result

    def robot_stop_program(self):
        """Stop the robot: pulse SDI[4] (CSTOPI), switch SDI[1..3] off, check UO[3] PROGRUN = 0 (rcs2/robot/uop.py).
        Always allowed (also while a run / job / manual motion is active). Afterwards the run is stopped too, so that no new job
        is sent to a robot that no longer runs its program. Blocking: call from a worker thread."""
        self._uop_abort.set()                                     # a start in progress gives up
        starter = RobotStarter(self.bridge, self.cfg.get("robot_start"), log_fn=self._log_manual, abort=self._uop_abort)
        self._log_manual("DỪNG ROBOT (%s)" % starter.program)
        armed_here = False
        try:
            if not self.bridge.connected:
                raise ConnectionError("chưa kết nối bridge robot")
            if not (self.bridge.last_status or {}).get("armed"):  # io.write needs the arm; when a run already holds it, keep it
                if (self.bridge.last_status or {}).get("fault"):
                    try:
                        self.bridge.fault_clear()
                    except Exception as ex:
                        self._log_manual("fault.clear: %s" % ex)
                self.bridge.arm()
                armed_here = True
            try:
                result = starter.stop()
            finally:
                self._refresh_program_state()
                if armed_here:
                    try:
                        self.bridge.disarm()
                    except Exception:
                        pass
            self._log_manual(result)
            return result
        finally:
            self.engine.stop_run()                                # no new job for a stopped robot
            self.engine.wait_processed()                          # ... and its disarm is done before the caller goes on

    def robot_gosafehere(self, override=None):
        """Manual 'retreat to a safe pose' (only when the run is not active)."""
        return self._manual_motion(lambda: self.bridge.gosafehere(override=override or self.manual_override()))

    def manual_rmove(self, offset, override=None):
        """Relative step: offset = [dx, dy, dz, dw, dp, dr] (mm / degrees)."""
        self._log_manual("jog %s ở %s%%" % ([round(v, 3) for v in offset], override))
        return self._manual_motion(lambda: self.bridge.rmove(list(offset), override=override or self.manual_override()))

    def points(self):
        return self._seq_data["points"]

    def manual_move_to(self, name, override=None):
        """Safe move (robot base program checks the path) to a taught point."""
        value = self.points().get(name)
        if value is None:
            raise KeyError("không có điểm %r" % name)
        if isinstance(value, dict):
            xyz, cfg, uf, ut = value["xyzwpr"], value.get("config"), value.get("uf"), value.get("ut")
        else:
            xyz, cfg, uf, ut = value, None, None, None
        self._log_manual("di chuyển tới điểm %s ở %s%%" % (name, override))
        return self._manual_motion(lambda: self.bridge.move(xyz, override=override or self.manual_override(),
                                                            config=cfg, uf=uf, ut=ut))

    def teach_point(self, name):
        """Store the robot's current position (with CONFIG/UF/UT) under `name`.

        Saved into the sequences file (a .bak copy is kept the first time) and made available to the
        running engine immediately. Not possible in demo mode (no file)."""
        import json
        import re
        import shutil
        if not re.fullmatch(r"[A-Za-z0-9_]{1,40}", name or ""):
            raise ValueError("tên điểm: 1-40 chữ cái, chữ số hoặc _")
        if self._seq_path is None:
            raise RuntimeError("chế độ demo: không lưu điểm (không có file sequences)")
        self._need_program_running()                       # every robot operation needs the program to be running
        if not self.bridge.connected:
            raise ConnectionError("robot bridge is not connected")
        pos = self.bridge.pos_read()
        point = {"xyzwpr": [round(v, 3) for v in pos["xyzwpr"]], "config": pos["config"],
                 "uf": pos["uf"], "ut": pos["ut"]}
        with open(self._seq_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        data.setdefault("points", {})[name] = point
        if not os.path.exists(self._seq_path + ".bak"):
            shutil.copyfile(self._seq_path, self._seq_path + ".bak")
        save_sequences(self._seq_path, data)                  # atomic; one point per line
        self.points()[name] = point                 # live: the engine shares this dict
        self._log_manual("đã dạy điểm %s: %s" % (name, point["xyzwpr"]))
        return point

    def robot_fault_clear(self):
        """Clears the latched robot fault (R[1] < 0) of the bridge. Only while the robot program runs."""
        self._need_program_running()
        return self.bridge.fault_clear()

    def _log_manual(self, text):
        who = self.operator.employee.name if self.operator else "-"
        self._emit_log("info", "thủ công (%s): %s" % (who, text))
