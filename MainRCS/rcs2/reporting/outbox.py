"""Local SQLite outbox: every record is stored here first, so nothing is lost while MySQL is down
or the program crashes. Also stores small key/value metadata and the currently open errors."""
import json
import os
import sqlite3
import threading
import time


class Outbox:
    def __init__(self, path):
        if path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock, self._db:
            self._db.executescript("""
                CREATE TABLE IF NOT EXISTS outbox(
                    id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, payload TEXT NOT NULL,
                    created REAL NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT);
                CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
                CREATE TABLE IF NOT EXISTS open_errors(
                    key TEXT PRIMARY KEY, error_code TEXT, error TEXT, station TEXT, start TEXT);
            """)

    def close(self):
        with self._lock:
            self._db.close()

    # ---- queue ---------------------------------------------------------- #
    def enqueue(self, kind, payload):
        with self._lock, self._db:
            cur = self._db.execute("INSERT INTO outbox(kind, payload, created) VALUES (?,?,?)",
                                   (kind, json.dumps(payload, default=str), time.time()))
            return cur.lastrowid

    def pending(self, limit=200):
        with self._lock:
            rows = self._db.execute(
                "SELECT id, kind, payload FROM outbox ORDER BY id LIMIT ?", (limit,)).fetchall()
        return [(i, k, json.loads(p)) for i, k, p in rows]

    def delete(self, ids):
        if not ids:
            return
        with self._lock, self._db:
            self._db.executemany("DELETE FROM outbox WHERE id=?", [(i,) for i in ids])

    def mark_failed(self, item_id, error):
        with self._lock, self._db:
            self._db.execute("UPDATE outbox SET attempts=attempts+1, last_error=? WHERE id=?",
                             (str(error)[:500], item_id))

    def count(self):
        with self._lock:
            return self._db.execute("SELECT COUNT(*) FROM outbox").fetchone()[0]

    # ---- metadata ------------------------------------------------------- #
    def set_meta(self, key, value):
        with self._lock, self._db:
            self._db.execute("INSERT INTO meta(key,value) VALUES(?,?) "
                             "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))

    def get_meta(self, key, default=None):
        with self._lock:
            row = self._db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    # ---- open errors (errors that started but have not ended yet) -------- #
    def save_open_error(self, key, error_code, error, station, start_iso):
        with self._lock, self._db:
            self._db.execute("INSERT OR REPLACE INTO open_errors(key,error_code,error,station,start) "
                             "VALUES (?,?,?,?,?)", (key, error_code, error, station, start_iso))

    def delete_open_error(self, key):
        with self._lock, self._db:
            self._db.execute("DELETE FROM open_errors WHERE key=?", (key,))

    def open_errors(self):
        with self._lock:
            rows = self._db.execute("SELECT key,error_code,error,station,start FROM open_errors").fetchall()
        return [dict(key=k, error_code=c, error=e, station=s, start=t) for k, c, e, s, t in rows]
