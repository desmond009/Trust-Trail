"""TrustTrail's own SQLite database (declarations, service keys; the ledger from Phase 3).

Deliberately separate from identity_map.db, which links students to pseudonyms.
"""
import sqlite3
import threading
from contextlib import contextmanager

from . import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS service_keys (
    kid           TEXT PRIMARY KEY,
    client_id     TEXT NOT NULL,
    jwk           TEXT NOT NULL,      -- public JWK as JSON
    registered_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS declarations (
    declaration_id  TEXT PRIMARY KEY,  -- first 16 hex chars of jws_sha256
    client_id       TEXT NOT NULL,
    nonce           TEXT NOT NULL,
    attributes      TEXT NOT NULL,     -- JSON list
    purpose         TEXT NOT NULL,
    retention_until TEXT NOT NULL,     -- ISO date
    issued_at       INTEGER NOT NULL,
    expires_at      INTEGER NOT NULL,
    kid             TEXT NOT NULL,
    jws             TEXT NOT NULL,     -- the service's signed declaration, kept verbatim
    jws_sha256      TEXT NOT NULL,
    received_at     INTEGER NOT NULL,
    UNIQUE (client_id, nonce)          -- replay protection
);
"""

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def _connection() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(settings.DATA_DIR / "trusttrail.db", check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.executescript(SCHEMA)
    return _conn


@contextmanager
def tx():
    """One serialised transaction: commits on success, rolls back on error."""
    with _lock:
        conn = _connection()
        with conn:
            yield conn
