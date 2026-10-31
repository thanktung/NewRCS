"""End Effector actions of the Manual window (suction heads, barcode scanner, laser)."""
from ..devices.heads import HeadError
from ..devices.laser import LaserError
from ..devices.scanner import ScanError


class EndEffectorOpsMixin:
    # ---- End Effector tools (Manual window): outputs need the bridge armed for that single command ----------- #
    def _tool(self, kind, error):
        tool = self.ee.tool(kind)
        if tool is None:
            raise error("End Effector không có %s (settings.json -> end_effector -> %s)" % (kind, kind))
        return tool

    def heads_action(self, action, heads=None):
        """action: vacuum_on | vacuum_off | cylinder_down | cylinder_up. Refused while a run / robot job is active."""
        label = {"vacuum_on": "bật hút", "vacuum_off": "tắt hút", "cylinder_down": "xy lanh xuống",
                 "cylinder_up": "xy lanh lên"}[action]

        def run():
            tool = self._tool("heads", HeadError)
            if action.startswith("vacuum"):
                tool.vacuum_set(action == "vacuum_on", heads)
            else:
                tool.cylinder_set(action == "cylinder_down", heads)
        self._log_manual("End Effector: %s, đầu %s" % (label, heads or "all"))
        return self._manual_motion(run)                                 # robot I/O: only while the robot program runs

    def heads_status(self):
        """Read-only: state of every head (does not need arm). Only while the robot program runs."""
        self._need_program_running()
        return self._tool("heads", HeadError).status()

    def scan_test(self):
        """One reading (LON) without retries; returns the code. Refused while the reader is used by a robot job."""
        code = self._tool("scanner", ScanError).scan(retry=0, blocking=False)
        self._log_manual("đọc thử máy quét: %s" % code)
        return code

    def scan_stop(self):
        """LOFF: stop a reading in progress."""
        self._tool("scanner", ScanError).stop()

    def laser_status(self):
        """Read-only: the IL-1000 judgement {"ok", "high", "low"} (does not need arm). Only while the robot program runs."""
        self._need_program_running()
        return self._tool("laser", LaserError).status()
