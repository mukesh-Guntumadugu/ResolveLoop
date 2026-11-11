"""Tiny document store on SQLite. Records are JSON bodies keyed by (kind, id) and scoped by tenant.

The data set for the demo is small, so filtering happens in Python. This keeps the schema stable while
the module boundaries (cases, events, playbooks, executions, audit, accounts) evolve.
"""
import json
import sqlite3
import threading
from typing import Any, Callable, Iterable, Optional


class Store:
    def __init__(self, path: str):
        self.path = path
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS records (kind TEXT NOT NULL, id TEXT NOT NULL, tenant_id TEXT NOT NULL,"
            " seq INTEGER NOT NULL, body TEXT NOT NULL, PRIMARY KEY (kind, id))"
        )
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_records_kind_tenant ON records (kind, tenant_id, seq)")

    def put(self, kind: str, obj: dict) -> dict:
        """Insert or update. `obj` must carry `id` and `tenant_id`. Insertion order is kept in `seq`."""
        with self.lock:
            row = self.conn.execute("SELECT seq FROM records WHERE kind=? AND id=?", (kind, obj["id"])).fetchone()
            if row:
                seq = row[0]
            else:
                seq = self.conn.execute("SELECT COALESCE(MAX(seq), 0) + 1 FROM records").fetchone()[0]
            self.conn.execute(
                "INSERT OR REPLACE INTO records (kind, id, tenant_id, seq, body) VALUES (?, ?, ?, ?, ?)",
                (kind, obj["id"], obj["tenant_id"], seq, json.dumps(obj, sort_keys=True)),
            )
        return obj

    def get(self, kind: str, id: str, tenant_id: Optional[str] = None) -> Optional[dict]:
        with self.lock:
            row = self.conn.execute("SELECT body, tenant_id FROM records WHERE kind=? AND id=?", (kind, id)).fetchone()
        if not row:
            return None
        if tenant_id is not None and row[1] != tenant_id:
            return None  # cross-tenant reads look like "not found"
        return json.loads(row[0])

    def list(self, kind: str, tenant_id: Optional[str] = None, where: Optional[Callable[[dict], bool]] = None) -> list:
        with self.lock:
            if tenant_id is None:
                rows = self.conn.execute("SELECT body FROM records WHERE kind=? ORDER BY seq", (kind,)).fetchall()
            else:
                rows = self.conn.execute(
                    "SELECT body FROM records WHERE kind=? AND tenant_id=? ORDER BY seq", (kind, tenant_id)
                ).fetchall()
        out = [json.loads(r[0]) for r in rows]
        if where:
            out = [o for o in out if where(o)]
        return out

    def delete(self, kind: str, id: str) -> None:
        with self.lock:
            self.conn.execute("DELETE FROM records WHERE kind=? AND id=?", (kind, id))

    def clear(self, kinds: Iterable[str], tenant_id: Optional[str] = None) -> None:
        with self.lock:
            for kind in kinds:
                if tenant_id is None:
                    self.conn.execute("DELETE FROM records WHERE kind=?", (kind,))
                else:
                    self.conn.execute("DELETE FROM records WHERE kind=? AND tenant_id=?", (kind, tenant_id))

    def count(self, kind: str, tenant_id: Optional[str] = None) -> int:
        return len(self.list(kind, tenant_id))
