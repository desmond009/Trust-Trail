"""Unit tests for checking a ledger against anchored batches (no chain needed)."""
import sqlite3

from app import anchoring, db, ledger, merkle


def build(n=10):
    conn = db.init(sqlite3.connect(":memory:"))
    for i in range(n):
        ledger.append(conn, {"kind": "release", "service_id": "lms", "student_pseudonym": f"p{i}",
                             "profile": "partial", "attributes_released": ["sub"], "purpose": "x",
                             "retention_until": "2027-01-01", "declaration_id": "d", "service_signature": "s"})
    return conn


def anchor(entries, first, last, batch_id):
    """What the anchoring job would have put on-chain for entries first..last."""
    hashes = [e["entry_hash"] for e in entries if first <= e["entry_id"] <= last]
    return {"batch_id": batch_id, "first_entry_id": first, "last_entry_id": last,
            "root": merkle.root([merkle.leaf_hash(h) for h in hashes]).hex()}


def test_untouched_ledger_matches_its_anchors():
    entries = ledger.all_entries(build())
    batches = [anchor(entries, 1, 6, 0), anchor(entries, 7, 10, 1)]
    assert all(r["ok"] for r in anchoring.verify_ledger_against_chain(entries, batches))


def test_full_rewrite_is_caught_by_the_anchor():
    conn = build()
    batches = [anchor(ledger.all_entries(conn), 1, 10, 0)]
    conn.execute("DROP TRIGGER ledger_no_update")
    conn.execute("UPDATE ledger SET purpose = 'Advertising' WHERE entry_id = 4")
    entries = ledger.all_entries(conn)
    prev = entries[2]["entry_hash"]          # recompute every hash from entry 4 on
    for e in entries[3:]:
        e["prev_hash"] = prev
        e["entry_hash"] = prev = ledger.compute_hash(e)
    assert ledger.verify(entries).ok                       # the chain alone is fooled...
    result = anchoring.verify_ledger_against_chain(entries, batches)
    assert not result[0]["ok"]                             # ...the anchored root is not


def test_edit_with_stored_hash_left_alone_is_caught():
    # Leaves are recomputed from entry content, not taken from the stored entry_hash.
    conn = build()
    batches = [anchor(ledger.all_entries(conn), 1, 10, 0)]
    conn.execute("DROP TRIGGER ledger_no_update")
    conn.execute("UPDATE ledger SET attributes_released = '[]' WHERE entry_id = 2")
    assert not anchoring.verify_ledger_against_chain(ledger.all_entries(conn), batches)[0]["ok"]


def test_truncated_ledger_is_caught():
    conn = build()
    batches = [anchor(ledger.all_entries(conn), 1, 10, 0)]
    conn.execute("DROP TRIGGER ledger_no_delete")
    conn.execute("DELETE FROM ledger WHERE entry_id >= 9")
    result = anchoring.verify_ledger_against_chain(ledger.all_entries(conn), batches)
    assert not result[0]["ok"] and "missing" in result[0]["reason"]


def test_only_the_affected_batch_fails():
    conn = build()
    entries = ledger.all_entries(conn)
    batches = [anchor(entries, 1, 5, 0), anchor(entries, 6, 10, 1)]
    conn.execute("DROP TRIGGER ledger_no_update")
    conn.execute("UPDATE ledger SET purpose = 'x2' WHERE entry_id = 8")
    result = anchoring.verify_ledger_against_chain(ledger.all_entries(conn), batches)
    assert [r["ok"] for r in result] == [True, False]
