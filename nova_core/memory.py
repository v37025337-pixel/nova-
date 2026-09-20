"""One transactional journal; projections are rebuilt instead of separately saved."""

import os
import sqlite3
import tempfile
from pathlib import Path

from .contracts import ContractError, IntegrityError, StaleState, decode, digest, encode

ZERO = "0" * 64


class Journal:
    def __init__(self, path, create=False):
        self.path = Path(path).resolve()
        if not self.path.is_file() and not create:
            raise ContractError("state does not exist; use init or learn")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        try:
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("PRAGMA synchronous=FULL")
            self.db.execute("CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY, prev TEXT NOT NULL, body TEXT NOT NULL, hash TEXT NOT NULL)")
        except Exception:
            self.db.close()
            raise

    def read(self):
        rows = self.db.execute("SELECT seq,prev,body,hash FROM events ORDER BY seq").fetchall()
        previous, events = ZERO, []
        try:
            for index, (seq, prev, raw, token) in enumerate(rows, 1):
                body = decode(raw)
                if seq != index or prev != previous or raw != encode(body) or token != digest([seq, prev, body]):
                    raise IntegrityError("journal hash/sequence mismatch")
                events.append(body)
                previous = token
        except (ValueError, TypeError, UnicodeError) as exc:
            raise IntegrityError("invalid journal: " + str(exc)) from exc
        return events, previous

    def append(self, body, expected_head):
        raw = encode(body)
        if len(raw.encode("utf-8")) > 2_000_000:
            raise ContractError("journal event exceeds replay size limit")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            last = self.db.execute("SELECT seq,hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
            seq, previous = (last[0] + 1, last[1]) if last else (1, ZERO)
            if previous != expected_head:
                raise StaleState("state changed during work; retry from a fresh snapshot")
            token = digest([seq, previous, body])
            self.db.execute("INSERT INTO events VALUES (?,?,?,?)", (seq, previous, raw, token))
            self.db.execute("COMMIT")
            return token
        except Exception:
            self.db.execute("ROLLBACK")
            raise

    def backup(self, destination):
        target = Path(destination).resolve()
        if target.exists():
            raise ContractError("backup destination already exists")
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix="nova-backup-", suffix=".sqlite", dir=target.parent)
        os.close(fd)
        try:
            connection = sqlite3.connect(temporary)
            try:
                self.db.backup(connection)
                connection.execute("PRAGMA journal_mode=DELETE")
            finally:
                connection.close()
            # Exclusive publication: do not overwrite a concurrently created file.
            os.link(temporary, target)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def close(self):
        self.db.close()
