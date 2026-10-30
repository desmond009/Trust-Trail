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

-- Hash-chained ledger: entry_hash = SHA-256(canonical JSON of every other column),
-- and each entry carries the previous entry's hash. See app/ledger.py.
CREATE TABLE IF NOT EXISTS ledger (
    entry_id            INTEGER PRIMARY KEY,  -- 1, 2, 3 ... assigned by us, so gaps show
    kind                TEXT NOT NULL,        -- "release" | "violation" | "trust_reset"
    rule                TEXT NOT NULL,        -- violation rule, "" otherwise
    time                TEXT NOT NULL,        -- ISO 8601 UTC
    service_id          TEXT NOT NULL,
    student_pseudonym   TEXT NOT NULL,        -- per-service pairwise ID, never the real student ID
    profile             TEXT NOT NULL,
    attributes_requested TEXT NOT NULL,       -- JSON list of names the service asked for
    attributes_released TEXT NOT NULL,        -- JSON list of names, never values ([] for a violation)
    purpose             TEXT NOT NULL,
    retention_until     TEXT NOT NULL,
    declaration_id      TEXT NOT NULL,
    service_signature   TEXT NOT NULL,        -- signature part of the service's declaration JWS
    prev_hash           TEXT NOT NULL,
    entry_hash          TEXT NOT NULL
);
-- Append-only inside the application. Someone with direct file access can still
-- drop these triggers; that is what chain verification (and Phase 5 anchoring) is for.
CREATE TRIGGER IF NOT EXISTS ledger_no_update BEFORE UPDATE ON ledger
BEGIN SELECT RAISE(ABORT, 'ledger is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ledger_no_delete BEFORE DELETE ON ledger
BEGIN SELECT RAISE(ABORT, 'ledger is append-only'); END;

-- TrustTrail-signed receipt per release. Not part of the hash chain: a receipt
-- embeds its entry's hash, so it is evidence *about* the chain.
CREATE TABLE IF NOT EXISTS receipts (
    entry_id INTEGER PRIMARY KEY REFERENCES ledger(entry_id),
    jws      TEXT NOT NULL
);

-- Latest trust evaluation per service (derived; the ledger is the source of truth).
CREATE TABLE IF NOT EXISTS trust_state (
    service_id TEXT PRIMARY KEY,
    state      TEXT NOT NULL           -- JSON: score, inputs, tier, cap, ...
);
-- Local record of anchoring transactions (Phase 5). The contract is the source of
-- truth; this caches tx hash, gas and timing so proofs and stats need no chain scan.
CREATE TABLE IF NOT EXISTS anchors (
    deployment       TEXT NOT NULL,     -- deployedAt of the contract deployment: a fresh local
                                        -- chain reuses the same address, so the address alone is ambiguous
    contract_address TEXT NOT NULL,
    chain_id         INTEGER NOT NULL,
    batch_id         INTEGER NOT NULL,
    first_entry_id   INTEGER NOT NULL,
    last_entry_id    INTEGER NOT NULL,
    root             TEXT NOT NULL,     -- hex
    tx_hash          TEXT NOT NULL,
    block_number     INTEGER NOT NULL,
    gas_used         INTEGER NOT NULL,
    anchored_at      INTEGER NOT NULL,  -- block timestamp
    PRIMARY KEY (deployment, batch_id)
);
-- Keycloak event IDs already turned into violations (or ignored), so none counts twice.
CREATE TABLE IF NOT EXISTS processed_events (
    event_id TEXT PRIMARY KEY
);
"""


def init(conn: sqlite3.Connection) -> sqlite3.Connection:
    conn.row_factory = sqlite3.Row
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'anchors'").fetchone() and \
            "deployment" not in {r[1] for r in conn.execute("PRAGMA table_info(anchors)")}:
        conn.execute("DROP TABLE anchors")   # an early Phase 5 cache; the chain is the source of truth
    conn.executescript(SCHEMA)
    columns = {r["name"] for r in conn.execute("PRAGMA table_info(ledger)")}
    if "rule" not in columns:
        # Changing the hashed fields would invalidate every existing entry, so no migration.
        raise RuntimeError("ledger was created before Phase 4 and has a different entry format; "
                           "reset the demo data with: docker compose down -v")
    return conn


DB_PATH = settings.DATA_DIR / "trusttrail.db"
_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def _connection() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = init(sqlite3.connect(DB_PATH, check_same_thread=False))
    return _conn


@contextmanager
def tx():
    """One serialised transaction: commits on success, rolls back on error."""
    with _lock:
        conn = _connection()
        with conn:
            yield conn
