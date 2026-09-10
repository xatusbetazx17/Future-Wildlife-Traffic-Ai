"""Bounded SQLite journal, durable deduplication watermarks and expiring outbox."""

import json
import sqlite3
import threading
from pathlib import Path


class Store:
    def __init__(self, path):
        self.lock = threading.RLock()
        self.file_lock = None
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            self.file_lock = open(str(path) + ".lock", "a+b")
            try:
                if __import__("os").name == "nt":
                    import msvcrt

                    self.file_lock.write(b"0")
                    self.file_lock.flush()
                    self.file_lock.seek(0)
                    msvcrt.locking(self.file_lock.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(self.file_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                self.file_lock.close()
                raise RuntimeError("database already has an owner; run one service worker") from None
        self.db = sqlite3.connect(path, check_same_thread=False, timeout=5)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 1):
            self.close()
            raise RuntimeError("unsupported database schema; migrate before starting")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS observations (
              id TEXT PRIMARY KEY, digest TEXT NOT NULL, site TEXT NOT NULL,
              sensor TEXT NOT NULL, observed REAL NOT NULL, received REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS watermarks (
              site TEXT, sensor TEXT, observed REAL NOT NULL, PRIMARY KEY(site,sensor));
            CREATE TABLE IF NOT EXISTS events (
              seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL,
              site TEXT NOT NULL, created REAL NOT NULL, expires REAL NOT NULL,
              payload TEXT NOT NULL, delivered INTEGER NOT NULL DEFAULT 0);
            CREATE INDEX IF NOT EXISTS events_expiry ON events(expires);
            CREATE TABLE IF NOT EXISTS controls (site TEXT PRIMARY KEY, held INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS audit (
              id INTEGER PRIMARY KEY, site TEXT, created REAL, reason TEXT, held INTEGER);
            PRAGMA user_version=1;
        """)

    def accept(self, obs, digest, epoch):
        """Return False for an identical retry; old timestamps remain rejected after pruning."""
        with self.lock, self.db:
            previous = self.db.execute(
                "SELECT digest FROM observations WHERE id=?", (obs.observation_id,)
            ).fetchone()
            if previous:
                if previous["digest"] != digest:
                    raise ValueError("observation_id reused with different content")
                return False
            last = self.db.execute(
                "SELECT observed FROM watermarks WHERE site=? AND sensor=?", (obs.site_id, obs.sensor_id)
            ).fetchone()
            ts = obs.observed_at.timestamp()
            if last and ts <= last["observed"]:
                raise ValueError("out-of-order or replayed sensor timestamp")
            self.db.execute(
                "INSERT INTO observations VALUES (?,?,?,?,?,?)",
                (obs.observation_id, digest, obs.site_id, obs.sensor_id, ts, epoch),
            )
            self.db.execute(
                "INSERT OR REPLACE INTO watermarks VALUES (?,?,?)", (obs.site_id, obs.sensor_id, ts)
            )
            return True

    def event(self, event, epoch, ttl):
        with self.lock, self.db:
            self.db.execute(
                "INSERT INTO events(id,site,created,expires,payload) VALUES (?,?,?,?,?)",
                (event["event_id"], event["site_id"], epoch, epoch + ttl, json.dumps(event, allow_nan=False)),
            )

    def events(self, now, after=0, limit=100, active_only=False, pending=False):
        where = "seq>?"
        args = [after]
        if active_only or pending:
            where += " AND expires>?"
            args.append(now)
        if pending:
            where += " AND delivered=0"
        with self.lock:
            rows = self.db.execute(
                "SELECT seq,payload FROM events WHERE " + where + " ORDER BY seq LIMIT ?", (*args, limit)
            ).fetchall()
            return [dict(sequence=r["seq"], **json.loads(r["payload"])) for r in rows]

    def delivered(self, event_id):
        with self.lock, self.db:
            self.db.execute("UPDATE events SET delivered=1 WHERE id=?", (event_id,))

    def pending_count(self, now):
        with self.lock:
            return self.db.execute(
                "SELECT count(*) FROM events WHERE delivered=0 AND expires>?", (now,)
            ).fetchone()[0]

    def set_hold(self, site, enabled, reason, epoch):
        with self.lock, self.db:
            self.db.execute("INSERT OR REPLACE INTO controls VALUES (?,?)", (site, int(enabled)))
            self.db.execute(
                "INSERT INTO audit(site,created,reason,held) VALUES (?,?,?,?)",
                (site, epoch, reason, int(enabled)),
            )

    def held(self, site):
        with self.lock:
            row = self.db.execute("SELECT held FROM controls WHERE site=?", (site,)).fetchone()
            return bool(row and row[0])

    def prune(self, now, days, max_obs, max_events):
        cutoff = now - days * 86400
        with self.lock, self.db:
            self.db.execute("DELETE FROM observations WHERE received<?", (cutoff,))
            self.db.execute(
                "DELETE FROM observations WHERE id IN "
                "(SELECT id FROM observations ORDER BY received DESC LIMIT -1 OFFSET ?)",
                (max_obs,),
            )
            self.db.execute("DELETE FROM events WHERE created<?", (cutoff,))
            self.db.execute(
                "DELETE FROM events WHERE seq IN "
                "(SELECT seq FROM events ORDER BY seq DESC LIMIT -1 OFFSET ?)",
                (max_events,),
            )
            self.db.execute("DELETE FROM audit WHERE created<?", (cutoff,))

    def close(self):
        with self.lock:
            if getattr(self, "db", None):
                self.db.close()
                self.db = None
            if self.file_lock:
                self.file_lock.close()
                self.file_lock = None
