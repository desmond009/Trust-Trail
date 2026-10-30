"""Phase 3 tamper demo: edit the ledger the way an insider with file access could,
and show which checks notice.

    docker compose exec trusttrail python -m scripts.demo_tamper            # safe: attacks a copy
    docker compose exec trusttrail python -m scripts.demo_tamper --live --entry 3
    docker compose exec trusttrail python -m scripts.demo_tamper --restore

Default mode copies the live database and runs five attacks, each on a fresh copy,
then prints a result table. --live edits one entry of the real ledger so you can
press "Verify" on the dashboard; --restore puts it back.
"""
import argparse
import json
import sqlite3
import tempfile

from app import anchoring, db, ledger, receipts
from app.demo_login import login, release
from app.demo_service import DemoService

BACKUP = db.DB_PATH.parent / "tamper_backup.json"
STUDENTS = ["asha", "rohan", "meera", "kabir", "zoya"]


def ensure_entries(minimum=6):
    conn = db.init(sqlite3.connect(db.DB_PATH))
    have = len(ledger.all_entries(conn))
    if have >= minimum:
        return
    decl = DemoService("lms").declare()
    for i in range(minimum - have):
        release(login("lms", STUDENTS[i % 5], "partial").json()["access_token"], decl["declaration_id"])
    print(f"(added {minimum - have} releases so there is something to tamper with)")


def add_unanchored_release():
    decl = DemoService("lms").declare()
    release(login("lms", "asha", "partial").json()["access_token"], decl["declaration_id"])


def copy_of_live() -> sqlite3.Connection:
    copy = db.init(sqlite3.connect(tempfile.mkstemp(suffix=".db")[1]))
    db.init(sqlite3.connect(db.DB_PATH)).backup(copy)
    return copy


def drop_guards(conn):
    # An insider with direct file access can simply remove the append-only triggers.
    conn.execute("DROP TRIGGER IF EXISTS ledger_no_update")
    conn.execute("DROP TRIGGER IF EXISTS ledger_no_delete")


def rehash_from(conn, start_id):
    entries = ledger.all_entries(conn)
    prev = entries[start_id - 2]["entry_hash"] if start_id > 1 else ledger.GENESIS
    for e in entries[start_id - 1:]:
        e["prev_hash"] = prev
        e["entry_hash"] = ledger.compute_hash(e)
        conn.execute("UPDATE ledger SET prev_hash = ?, entry_hash = ? WHERE entry_id = ?",
                     (e["prev_hash"], e["entry_hash"], e["entry_id"]))
        prev = e["entry_hash"]


def attacks(k: int, last_anchored: int, newest: int):
    def edit(c):
        c.execute("UPDATE ledger SET attributes_released = '[\"sub\"]' WHERE entry_id = ?", (k,))

    def edit_one_hash(c):
        c.execute("UPDATE ledger SET purpose = 'Advertising partners' WHERE entry_id = ?", (k,))
        c.execute("UPDATE ledger SET entry_hash = ? WHERE entry_id = ?", (ledger.compute_hash(ledger.get(c, k)), k))

    return [
        (f"A. change entry #{k}'s attributes, leave its hash", edit),
        (f"B. change entry #{k}'s purpose, recompute its hash", edit_one_hash),
        (f"C. delete entry #{k}", lambda c: c.execute("DELETE FROM ledger WHERE entry_id = ?", (k,))),
        (f"D. change entry #{k}, recompute every hash after it",
         lambda c: (c.execute("UPDATE ledger SET purpose = 'Advertising partners' WHERE entry_id = ?", (k,)),
                    rehash_from(c, k))),
        (f"E. cut off the tail (#{last_anchored} onwards)",
         lambda c: c.execute("DELETE FROM ledger WHERE entry_id >= ?", (last_anchored,))),
        (f"F. change entry #{newest} (made after the last anchor), fix its hash",
         lambda c: (c.execute("UPDATE ledger SET purpose = 'Advertising partners' WHERE entry_id = ?", (newest,)),
                    rehash_from(c, newest))),
    ]


def tamper_matrix(k: int | None = None) -> tuple[list[dict], dict]:
    """Run every attack on a fresh copy of the live database; return what each check saw."""
    ensure_entries()
    # Anchor everything first, so the blockchain column has something to compare with,
    # then add one release after the anchor to show the anchoring window (attack F).
    anchorer = anchoring.Anchorer()
    anchorer.run_once()
    batches = anchorer.on_chain_batches()
    add_unanchored_release()
    live = db.init(sqlite3.connect(db.DB_PATH))
    entries = ledger.all_entries(live)
    before = ledger.verify(entries)
    if not before.ok:
        raise SystemExit(f"live ledger is already broken at #{before.first_bad_entry}; run --restore first")
    # Evidence kept outside the database: the receipts students downloaded, and
    # the Merkle roots on-chain (read above). Captured before the attacks.
    held_hashes = {e["entry_id"]: receipts.verify(jws)["entry_hash"]
                   for e in entries if (jws := ledger.receipt(live, e["entry_id"]))}
    # Default target: a release in the middle (releases have receipts; violations don't).
    releases = [e["entry_id"] for e in entries if e["kind"] == "release" and e["entry_id"] > 1]
    k = k or releases[len(releases) // 2]
    info = {"entries": len(entries), "anchored_up_to": batches[-1]["last_entry_id"],
            "batches": len(batches), "target": k}

    rows = []
    for name, attack in attacks(k, info["anchored_up_to"], len(entries)):
        c = copy_of_live()
        drop_guards(c)
        attack(c)
        after = ledger.all_entries(c)
        check = ledger.verify(after)
        by_id = {e["entry_id"]: e for e in after}
        failed = [r for r in anchoring.verify_ledger_against_chain(after, batches) if not r["ok"]]
        rows.append({"attack": name[0], "name": name,
                     "chain_detected": not check.ok, "chain_first_bad": check.first_bad_entry,
                     "receipts_failed": sum(1 for i, h in held_hashes.items()
                                            if i not in by_id or ledger.compute_hash(by_id[i]) != h),
                     "anchor_detected": bool(failed), "anchor_batch": failed[0]["batch_id"] if failed else None})
    return rows, info


def run_copy_mode(k: int | None):
    rows, info = tamper_matrix(k)
    print(f"Ledger has {info['entries']} entries; 1-{info['anchored_up_to']} anchored in {info['batches']} "
          f"on-chain batch(es), #{info['entries']} not yet. Attacking entry #{info['target']}.\n")
    table = [(r["name"],
              f"DETECTED at #{r['chain_first_bad']}" if r["chain_detected"] else "not detected",
              f"{r['receipts_failed']} receipt(s) fail" if r["receipts_failed"] else "all match",
              f"DETECTED (batch #{r['anchor_batch']})" if r["anchor_detected"] else "not detected")
             for r in rows]
    header = ("Attack", "Chain check", "Student receipts", "Blockchain anchor")
    w = [max(len(r[i]) for r in table + [header]) for i in range(4)]
    print("  ".join(h.ljust(w[i]) for i, h in enumerate(header)))
    print("  ".join("-" * x for x in w))
    for r in table:
        print("  ".join(v.ljust(w[i]) for i, v in enumerate(r)))
    print("\nThe live ledger was not modified (each attack ran on a copy).")
    print("D and E pass the chain check: a consistent rewrite or a cut-off tail is caught only by\n"
          "evidence kept outside the database: students' receipts, or the Merkle roots anchored on-chain.\n"
          "F shows the anchoring window: an entry newer than the last batch is protected only by\n"
          "receipts until the next anchor (at most one interval later).")


def run_live(k: int):
    conn = db.init(sqlite3.connect(db.DB_PATH))
    entry = ledger.get(conn, k)
    if entry is None:
        raise SystemExit(f"no entry #{k}")
    if BACKUP.exists():
        raise SystemExit(f"a live tamper is already active ({BACKUP}); run --restore first")
    BACKUP.write_text(json.dumps({"entry_id": k, "attributes_released": entry["attributes_released"]}))
    with conn:
        drop_guards(conn)
        conn.execute("UPDATE ledger SET attributes_released = '[\"sub\"]' WHERE entry_id = ?", (k,))
        conn.executescript(db.SCHEMA)   # put the guards back
    print(f"Entry #{k}: attributes_released {entry['attributes_released']} -> ['sub'] (hash left as it was).")
    print("Now: GET /ledger/verify, or press Verify on the dashboard. Undo with --restore.")


def restore():
    if not BACKUP.exists():
        raise SystemExit("nothing to restore")
    saved = json.loads(BACKUP.read_text())
    conn = db.init(sqlite3.connect(db.DB_PATH))
    with conn:
        drop_guards(conn)
        conn.execute("UPDATE ledger SET attributes_released = ? WHERE entry_id = ?",
                     (json.dumps(saved["attributes_released"]), saved["entry_id"]))
        conn.executescript(db.SCHEMA)
    BACKUP.unlink()
    print(f"Entry #{saved['entry_id']} restored; ledger verifies: {ledger.verify(ledger.all_entries(conn)).ok}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--live", action="store_true", help="tamper with the real ledger (undo with --restore)")
    p.add_argument("--restore", action="store_true")
    p.add_argument("--entry", type=int, help="entry to attack")
    a = p.parse_args()
    if a.restore:
        restore()
    elif a.live:
        run_live(a.entry or 1)
    else:
        run_copy_mode(a.entry)
