"""Writes outbox items into the legacy MySQL tables (pymysql, parameterised statements)."""
import logging

from .sql_targets import SqlTargets

log = logging.getLogger("rcs2.mysql")


class MySqlWriter:
    """write_batch(items) -> number of items written (in order); raises if the DB is unreachable.

    `connect_fn` is injectable so tests can use a fake DB-API connection.
    """

    def __init__(self, targets: SqlTargets, host="", port=3306, user="", password="", database="",
                 connect_timeout_s=5, connect_fn=None):
        self.targets = targets
        self._params = dict(host=host, port=port, user=user, password=password, database=database,
                            charset="utf8mb4", connect_timeout=connect_timeout_s, autocommit=False)
        self._connect_fn = connect_fn

    def _connect(self):
        if self._connect_fn is not None:
            return self._connect_fn()
        import pymysql
        return pymysql.connect(**self._params)

    def write_batch(self, items):
        """items: [(id, kind, payload)]. Stops at the first failing item; returns how many succeeded."""
        if not items:
            return 0
        conn = self._connect()
        ensured = set()
        done = 0
        try:
            for _id, kind, payload in items:
                table = self.targets.table(kind, self.targets.when_of(kind, payload))
                with conn.cursor() as cur:
                    if table not in ensured:
                        cur.execute(self.targets.ddl(kind, table))
                        ensured.add(table)
                    sql, params = self.targets.insert(kind, table, payload)
                    cur.execute(sql, params)
                conn.commit()
                done += 1
        except Exception as ex:
            try:
                conn.rollback()
            except Exception:
                pass
            if done == 0:
                raise
            log.warning("batch stopped after %d item(s): %s", done, ex)
        finally:
            try:
                conn.close()
            except Exception:
                pass
        return done
