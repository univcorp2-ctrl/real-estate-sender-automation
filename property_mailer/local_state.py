from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

UTC = timezone.utc


class LocalStateStore:
    def __init__(self, database_path: Path):
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                create table if not exists sent_log (
                  id integer primary key autoincrement,
                  audience_key text not null,
                  fingerprint text not null,
                  property_id text not null,
                  campaign_id text,
                  status text not null,
                  sent_at text not null,
                  unique(audience_key, fingerprint)
                );
                create table if not exists job_locks (
                  lock_key text primary key,
                  expires_at text not null
                );
                """
            )

    def acquire_lock(self, key: str, ttl_seconds: int = 1800) -> bool:
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=ttl_seconds)
        with self._connect() as conn:
            conn.execute("delete from job_locks where expires_at < ?", (now.isoformat(),))
            try:
                conn.execute(
                    "insert into job_locks(lock_key, expires_at) values(?, ?)",
                    (key, expires_at.isoformat()),
                )
                return True
            except sqlite3.IntegrityError:
                return False

    def release_lock(self, key: str) -> None:
        with self._connect() as conn:
            conn.execute("delete from job_locks where lock_key = ?", (key,))

    def filter_unsent(self, audience_key: str, fingerprints: list[str]) -> list[str]:
        if not fingerprints:
            return []
        with self._connect() as conn:
            rows = conn.execute(
                "select fingerprint from sent_log where audience_key = ?", (audience_key,)
            ).fetchall()
        sent = {row["fingerprint"] for row in rows}
        return [fp for fp in fingerprints if fp not in sent]

    def mark_sent(self, audience_key: str, records: list[dict[str, str]]) -> None:
        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            conn.executemany(
                """
                insert or ignore into sent_log(audience_key, fingerprint, property_id, campaign_id, status, sent_at)
                values(:audience_key, :fingerprint, :property_id, :campaign_id, :status, :sent_at)
                """,
                [
                    {
                        "audience_key": audience_key,
                        "fingerprint": rec["fingerprint"],
                        "property_id": rec["property_id"],
                        "campaign_id": rec.get("campaign_id", ""),
                        "status": rec.get("status", "sent"),
                        "sent_at": rec.get("sent_at", now),
                    }
                    for rec in records
                ],
            )
