"""The hash-chained, tamper-evident release ledger.

Each entry's hash covers all of its fields plus the previous entry's hash, so
changing, deleting or reordering any entry breaks every link after it. What the
chain alone cannot catch: an attacker who rewrites the chain from the edited
entry onward, or who cuts entries off the end. Receipts held by students catch
both for their own entries; Phase 5 anchoring catches them for everyone.

Functions take an open connection so the same code runs on the live database,
on an in-memory test database, and on the tamper demo's copy.
"""
import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Iterable

GENESIS = "0" * 64
HASHED_FIELDS = ["entry_id", "kind", "time", "service_id", "student_pseudonym", "profile",
                 "attributes_released", "purpose", "retention_until", "declaration_id",
                 "service_signature", "prev_hash"]


def canonical(entry: dict) -> bytes:
    # Sorted keys, no whitespace, UTF-8. Every value is a string, int or list of
    # strings, so this is unambiguous without a full JCS (RFC 8785) implementation.
    body = {k: entry[k] for k in HASHED_FIELDS}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def compute_hash(entry: dict) -> str:
    return hashlib.sha256(canonical(entry)).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _row(r: sqlite3.Row) -> dict:
    entry = dict(r)
    entry["attributes_released"] = json.loads(entry["attributes_released"])
    return entry


def append(conn: sqlite3.Connection, fields: dict) -> dict:
    """Add one entry. Call inside a single transaction so id and prev_hash can't race."""
    last = conn.execute("SELECT entry_id, entry_hash FROM ledger ORDER BY entry_id DESC LIMIT 1").fetchone()
    entry = {"entry_id": last["entry_id"] + 1 if last else 1,
             "prev_hash": last["entry_hash"] if last else GENESIS,
             "time": fields.get("time") or _now_iso(),
             **{k: v for k, v in fields.items() if k != "time"}}
    entry["attributes_released"] = sorted(entry["attributes_released"])
    entry["entry_hash"] = compute_hash(entry)
    conn.execute(f"INSERT INTO ledger ({', '.join(HASHED_FIELDS)}, entry_hash) "
                 f"VALUES ({', '.join('?' * (len(HASHED_FIELDS) + 1))})",
                 [json.dumps(entry[k]) if k == "attributes_released" else entry[k] for k in HASHED_FIELDS]
                 + [entry["entry_hash"]])
    return entry


def all_entries(conn: sqlite3.Connection) -> list[dict]:
    return [_row(r) for r in conn.execute("SELECT * FROM ledger ORDER BY entry_id")]


def get(conn: sqlite3.Connection, entry_id: int) -> dict | None:
    r = conn.execute("SELECT * FROM ledger WHERE entry_id = ?", (entry_id,)).fetchone()
    return _row(r) if r else None


def entries_for(conn: sqlite3.Connection, pseudonyms: dict[str, str]) -> list[dict]:
    """Entries about one student, given their {service_id: pseudonym} map."""
    if not pseudonyms:
        return []
    where = " OR ".join("(service_id = ? AND student_pseudonym = ?)" for _ in pseudonyms)
    params = [x for pair in pseudonyms.items() for x in pair]
    return [_row(r) for r in conn.execute(f"SELECT * FROM ledger WHERE {where} ORDER BY entry_id DESC", params)]


def store_receipt(conn: sqlite3.Connection, entry_id: int, jws: str):
    conn.execute("INSERT INTO receipts VALUES (?, ?)", (entry_id, jws))


def receipt(conn: sqlite3.Connection, entry_id: int) -> str | None:
    r = conn.execute("SELECT jws FROM receipts WHERE entry_id = ?", (entry_id,)).fetchone()
    return r["jws"] if r else None


@dataclass
class ChainCheck:
    ok: bool
    entries_checked: int
    head_hash: str
    first_bad_entry: int | None = None
    reason: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def verify(entries: Iterable[dict]) -> ChainCheck:
    """Recompute the whole chain from the genesis hash; stop at the first broken link."""
    prev_hash, expected_id, n = GENESIS, 1, 0
    for e in entries:
        if e["entry_id"] != expected_id:
            return ChainCheck(False, n, prev_hash, e["entry_id"], f"expected entry {expected_id} (missing or reordered)")
        if e["prev_hash"] != prev_hash:
            return ChainCheck(False, n, prev_hash, e["entry_id"], "prev_hash does not match the previous entry")
        if compute_hash(e) != e["entry_hash"]:
            return ChainCheck(False, n, prev_hash, e["entry_id"], "entry content does not match its hash")
        prev_hash, expected_id, n = e["entry_hash"], expected_id + 1, n + 1
    return ChainCheck(True, n, prev_hash)
