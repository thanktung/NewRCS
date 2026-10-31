"""DataSink: the single entry point for "send data to the dashboard".

emit() only appends to the local outbox (instant, never raises, never blocks on the network);
a background thread uploads the outbox to MySQL in order, retrying with back-off.
ErrorTracker turns "error started / error ended" events into the legacy interval rows.
"""
import logging
import threading
from datetime import datetime

from .outbox import Outbox

log = logging.getLogger("rcs2.sink")


def _iso(when=None):
    return (when or datetime.now()).isoformat(timespec="seconds")


class DataSink:
    def __init__(self, outbox: Outbox, writer=None, enabled=True, flush_interval_s=2.0, max_backoff_s=30.0):
        self.outbox = outbox
        self.writer = writer                 # object with write_batch(items) -> int, or None
        self.enabled = enabled
        self.flush_interval_s = flush_interval_s
        self.max_backoff_s = max_backoff_s
        self.last_error = ""
        self.uploaded = 0
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread = None
        self._backoff = flush_interval_s

    # ---- producers -------------------------------------------------------- #
    def emit(self, kind, payload):
        try:
            self.outbox.enqueue(kind, payload)
        except Exception:
            log.exception("could not store %s in the outbox", kind)
            return False
        self._wake.set()
        return True

    def emit_login(self, name, staff_id, bp, when=None):
        return self.emit("login", {"staff_name": name, "staff_id": staff_id, "staff_bp": bp, "start": _iso(when)})

    def emit_result(self, ats_ip, fixture_no, result, test_time, product_type="NORMAL", when=None):
        return self.emit("result", {"update_time": _iso(when), "fixture_no": fixture_no, "ats_ip": ats_ip,
                                    "result": result, "test_time": round(float(test_time), 3),
                                    "product_type": product_type})

    def emit_robot_speed(self, robot_name, speed, when=None):
        return self.emit("robot_speed", {"robot_name": robot_name, "speed": speed, "update_time": _iso(when)})

    def emit_ats_hourly(self, fixture, ide, when=None):
        return self.emit("ats_hourly", {"fixture": fixture, "ide": ide, "update_time": _iso(when)})

    # ---- uploader --------------------------------------------------------- #
    def start(self):
        if self._thread is None:
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, name="data-sink", daemon=True)
            self._thread.start()

    def stop(self, flush=True):
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        self._thread = None
        if flush:
            self.flush_once()

    def flush_once(self):
        """Upload what is pending. Returns the number of records uploaded (0 on failure/disabled)."""
        if not self.enabled or self.writer is None:
            return 0
        total = 0
        while True:
            items = self.outbox.pending(200)
            if not items:
                break
            try:
                done = self.writer.write_batch(items)
            except Exception as ex:
                self.last_error = "%s: %s" % (type(ex).__name__, ex)
                self.outbox.mark_failed(items[0][0], self.last_error)
                log.warning("upload failed (%d pending): %s", self.outbox.count(), self.last_error)
                return total if total else -1
            self.outbox.delete([i for i, _, _ in items[:done]])
            total += done
            self.uploaded += done
            if done < len(items):
                self.last_error = "stopped after %d of %d items" % (done, len(items))
                return total
        self.last_error = ""
        return total

    def _loop(self):
        while not self._stop.is_set():
            self._wake.wait(self._backoff)
            self._wake.clear()
            if self._stop.is_set():
                break
            result = self.flush_once()
            if result < 0:
                self._backoff = min(self._backoff * 2, self.max_backoff_s)
            else:
                self._backoff = self.flush_interval_s

    def stats(self):
        return {"pending": self.outbox.count(), "uploaded": self.uploaded, "last_error": self.last_error,
                "enabled": self.enabled}


class ErrorTracker:
    """Errors are intervals. The legacy table needs start AND end in one row, so a row is emitted
    when the error ends. Open errors are also saved in SQLite so a crash/power loss does not lose them:
    on the next start they are closed using the last time the program was known to be alive."""

    def __init__(self, sink: DataSink, station_label=""):
        self.sink = sink
        self.station_label = station_label
        self._open = {}
        self._lock = threading.Lock()

    def raise_error(self, code, message, key=None, when=None):
        key = key or code
        with self._lock:
            if key in self._open:
                return False                         # already active
            start = _iso(when)
            self._open[key] = (code, message, start)
        self.sink.outbox.save_open_error(key, code, message, self.station_label, start)
        return True

    def clear_error(self, key, when=None):
        with self._lock:
            entry = self._open.pop(key, None)
        if entry is None:
            return False
        code, message, start = entry
        self.sink.outbox.delete_open_error(key)
        self.sink.emit("error", {"station": self.station_label, "error_code": code, "error": message,
                                 "start": start, "end": _iso(when)})
        return True

    def is_open(self, key):
        with self._lock:
            return key in self._open

    def active(self):
        """Currently open errors, oldest first: [{'key','code','message','since'}] (for the UI)."""
        with self._lock:
            rows = [{"key": k, "code": c, "message": m, "since": s} for k, (c, m, s) in self._open.items()]
        return sorted(rows, key=lambda r: r["since"])

    def heartbeat(self):
        """Call about once a minute: remembers that the program is alive (used by recover())."""
        self.sink.outbox.set_meta("last_alive", _iso())

    def recover(self):
        """At start-up: close errors left open by a previous run. Returns how many were closed."""
        last_alive = self.sink.outbox.get_meta("last_alive") or _iso()
        n = 0
        for row in self.sink.outbox.open_errors():
            end = max(last_alive, row["start"])
            self.sink.emit("error", {"station": row["station"], "error_code": row["error_code"],
                                     "error": row["error"], "start": row["start"], "end": end})
            self.sink.outbox.delete_open_error(row["key"])
            n += 1
        return n
