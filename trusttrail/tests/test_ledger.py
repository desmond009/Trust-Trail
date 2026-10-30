"""Unit tests for the hash chain, on an in-memory database."""
import sqlite3

import pytest

from app import db, ledger


def make_entry(i: int) -> dict:
    return {"kind": "release", "service_id": "lms", "student_pseudonym": f"pseudo-{i % 2}",
            "profile": "partial", "attributes_released": ["sub", "department"],
            "purpose": "Enrol you in courses", "retention_until": "2027-06-30",
            "declaration_id": "abc123", "service_signature": f"sig-{i}"}


@pytest.fixture
def conn():
    c = db.init(sqlite3.connect(":memory:"))
    for i in range(5):
        ledger.append(c, make_entry(i))
    return c


def tamper(conn, sql, *params):
    # Simulates an insider with direct file access: drop the append-only triggers first.
    conn.execute("DROP TRIGGER ledger_no_update")
    conn.execute("DROP TRIGGER ledger_no_delete")
    conn.execute(sql, params)


def rehash_from(conn, start_id):
    """The 'competent attacker': recompute every hash from start_id to the end."""
    entries = ledger.all_entries(conn)
    prev = entries[start_id - 2]["entry_hash"] if start_id > 1 else ledger.GENESIS
    for e in entries[start_id - 1:]:
        e["prev_hash"] = prev
        e["entry_hash"] = ledger.compute_hash(e)
        conn.execute("UPDATE ledger SET prev_hash = ?, entry_hash = ? WHERE entry_id = ?",
                     (e["prev_hash"], e["entry_hash"], e["entry_id"]))
        prev = e["entry_hash"]


def test_empty_ledger_verifies():
    check = ledger.verify([])
    assert check.ok and check.entries_checked == 0 and check.head_hash == ledger.GENESIS


def test_chain_links_and_verifies(conn):
    entries = ledger.all_entries(conn)
    assert [e["entry_id"] for e in entries] == [1, 2, 3, 4, 5]
    assert entries[0]["prev_hash"] == ledger.GENESIS
    assert all(b["prev_hash"] == a["entry_hash"] for a, b in zip(entries, entries[1:]))
    check = ledger.verify(entries)
    assert check.ok and check.entries_checked == 5 and check.head_hash == entries[-1]["entry_hash"]


def test_hash_is_canonical():
    e = {**make_entry(0), "entry_id": 1, "time": "2026-10-30T10:00:00.000000Z", "prev_hash": ledger.GENESIS}
    reordered = dict(reversed(list(e.items())))
    assert ledger.compute_hash(e) == ledger.compute_hash(reordered)
    assert ledger.compute_hash({**e, "purpose": e["purpose"] + " "}) != ledger.compute_hash(e)


def test_triggers_make_ledger_append_only(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE ledger SET purpose = 'x' WHERE entry_id = 2")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM ledger WHERE entry_id = 2")


def test_edited_entry_is_detected(conn):
    tamper(conn, "UPDATE ledger SET attributes_released = '[\"sub\"]' WHERE entry_id = 2")
    check = ledger.verify(ledger.all_entries(conn))
    assert not check.ok and check.first_bad_entry == 2 and "content" in check.reason


def test_edited_and_rehashed_entry_breaks_the_next_link(conn):
    tamper(conn, "UPDATE ledger SET purpose = 'Advertising' WHERE entry_id = 2")
    e = ledger.get(conn, 2)
    conn.execute("UPDATE ledger SET entry_hash = ? WHERE entry_id = 2", (ledger.compute_hash(e),))
    check = ledger.verify(ledger.all_entries(conn))
    assert not check.ok and check.first_bad_entry == 3 and "prev_hash" in check.reason


def test_deleted_entry_is_detected(conn):
    tamper(conn, "DELETE FROM ledger WHERE entry_id = 3")
    check = ledger.verify(ledger.all_entries(conn))
    assert not check.ok and check.first_bad_entry == 4


def test_renumbered_entries_are_detected(conn):
    tamper(conn, "UPDATE ledger SET entry_id = 99 WHERE entry_id = 5")
    check = ledger.verify(ledger.all_entries(conn))
    assert not check.ok and check.first_bad_entry == 99


# --- the limits, written down as tests so nobody overclaims ------------------------

def test_full_rewrite_passes_chain_check_but_not_the_old_head(conn):
    old_head = ledger.verify(ledger.all_entries(conn)).head_hash
    tamper(conn, "UPDATE ledger SET purpose = 'Advertising' WHERE entry_id = 2")
    rehash_from(conn, 2)
    check = ledger.verify(ledger.all_entries(conn))
    assert check.ok                       # the chain alone cannot see this...
    assert check.head_hash != old_head    # ...but a head hash recorded earlier (Phase 5 anchor) can


def test_truncating_the_tail_passes_chain_check(conn):
    tamper(conn, "DELETE FROM ledger WHERE entry_id = 5")
    check = ledger.verify(ledger.all_entries(conn))
    assert check.ok and check.entries_checked == 4   # only receipts or an anchor reveal this


def test_entries_for_one_student(conn):
    mine = ledger.entries_for(conn, {"lms": "pseudo-1"})
    assert [e["entry_id"] for e in mine] == [4, 2]   # newest first, other student excluded
    assert ledger.entries_for(conn, {}) == []
